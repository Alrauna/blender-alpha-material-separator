# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only Blender mesh analysis and authoritative stale-result signatures."""

from __future__ import annotations

import hashlib
import json
import struct
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

import bpy

from .. import runtime
from ..core import (
    AddressMode,
    AnalysisSettings,
    ClassificationResult,
    FaceClass,
    InvalidRasterInput,
    RasterBudgetExceeded,
    classify_coverage,
    rasterize_polygon,
    uv_to_texel_edge,
)
from ..overrides import MaterialOverride, OverrideConfigError
from .fingerprints import material_fingerprint, source_fingerprint
from .image_data import (
    AnalysisImageCache,
    ImageReadError,
    ImageSnapshot,
    ImageSnapshotBuilder,
)
from .material_resolver import MaterialResolution, resolve_material


@dataclass(frozen=True, slots=True)
class AnalysisConfig:
    image_name: str = ""
    uv_map_name: str = ""
    image_channel: str = "ALPHA"
    address_mode: str = "AUTO"
    settings: AnalysisSettings = AnalysisSettings()
    material_overrides: tuple[MaterialOverride, ...] = ()

    def payload(self) -> dict[str, Any]:
        return {
            "address_mode": self.address_mode,
            "image_channel": self.image_channel,
            "image_name": self.image_name,
            "material_overrides": [item.payload() for item in self.material_overrides],
            "settings": asdict(self.settings),
            "uv_map_name": self.uv_map_name,
        }


@dataclass(frozen=True, slots=True)
class FaceAnalysis:
    polygon_index: int
    material_slot: int
    material_pointer: int
    result: ClassificationResult


@dataclass(slots=True)
class MaterialGroupAnalysis:
    material: bpy.types.Material
    resolution: MaterialResolution
    image_digest: str = ""
    source_fingerprint: str = ""
    face_indices: dict[FaceClass, list[int]] = field(
        default_factory=lambda: defaultdict(list)
    )
    counts: Counter = field(default_factory=Counter)
    affected_texels: int = 0
    covered_texels: int = 0


@dataclass(slots=True)
class ObjectAnalysis:
    object: bpy.types.Object
    faces: dict[int, FaceAnalysis] = field(default_factory=dict)
    groups: dict[int, MaterialGroupAnalysis] = field(default_factory=dict)
    skipped_reason: str = ""


@dataclass(slots=True)
class AnalysisReport:
    analysis_id: str
    input_signature: str
    config: AnalysisConfig
    objects: tuple[bpy.types.Object, ...]
    object_results: dict[int, ObjectAnalysis]
    counts: Counter
    skip_counts: Counter
    created_monotonic: float
    elapsed_seconds: float
    metrics: Counter

    def public_payload(self) -> dict[str, Any]:
        object_payload = []
        planned_materials: set[int] = set()
        estimated_slots = 0
        analyzed_objects = 0
        analyzed_polygons = 0
        for result in self.object_results.values():
            if result.skipped_reason:
                object_payload.append(
                    {
                        "name": result.object.name,
                        "skip_reason": result.skipped_reason,
                    }
                )
                continue
            analyzed_objects += 1
            analyzed_polygons += len(result.faces)
            groups = []
            for material_pointer, group in result.groups.items():
                move_count = len(group.face_indices[FaceClass.ALPHA_AFFECTED]) + len(
                    group.face_indices[FaceClass.MIXED]
                )
                if move_count:
                    planned_materials.add(group.material.as_pointer())
                    estimated_slots += 1
                group_faces = tuple(
                    face
                    for face in result.faces.values()
                    if face.material_pointer == material_pointer
                )
                unsupported_reasons = Counter(
                    face.result.unsupported_reason
                    for face in group_faces
                    if face.result.unsupported_reason
                )
                suppressed_failed_gates = Counter(
                    gate
                    for face in group_faces
                    if face.result.classification == FaceClass.SUPPRESSED
                    for gate in face.result.failed_gates
                )
                suppressed_shapes = Counter(
                    face.result.unsuppressed_shape.value
                    for face in group_faces
                    if face.result.classification == FaceClass.SUPPRESSED
                    and face.result.unsuppressed_shape is not None
                )
                resolution = group.resolution
                groups.append(
                    {
                        "affected_texels": group.affected_texels,
                        "address_mode": resolution.address_mode.value,
                        "alpha_material": f"{group.material.name}__AMS_ALPHA",
                        "channel": resolution.channel,
                        "counts": {
                            face_class.value: int(group.counts[face_class])
                            for face_class in FaceClass
                        },
                        "covered_texels": group.covered_texels,
                        "image": resolution.image.name_full if resolution.image else "",
                        "material": group.material.name,
                        "resolution": resolution.source_kind
                        if resolution.supported
                        else resolution.reason,
                        "source_kind": resolution.source_kind,
                        "supported": resolution.supported,
                        "suppressed_failed_gates": dict(
                            sorted(suppressed_failed_gates.items())
                        ),
                        "suppressed_unsuppressed_shapes": dict(
                            sorted(suppressed_shapes.items())
                        ),
                        "unsupported_reasons": dict(
                            sorted(unsupported_reasons.items())
                        ),
                        "uv_map": resolution.uv_map_name,
                    }
                )
            object_payload.append(
                {
                    "groups": groups,
                    "name": result.object.name,
                    "polygon_count": len(result.faces),
                }
            )
        return {
            "analysis_id": self.analysis_id,
            "analyzed_object_count": analyzed_objects,
            "analyzed_polygon_count": analyzed_polygons,
            "counts": {
                face_class.value: int(self.counts[face_class])
                for face_class in FaceClass
            },
            "elapsed_seconds": self.elapsed_seconds,
            "estimated_additional_material_slots": estimated_slots,
            "materials_to_create_or_reuse": len(planned_materials),
            "metrics": dict(sorted(self.metrics.items())),
            "objects": object_payload,
            "selected_object_count": len(self.objects),
            "skip_counts": dict(sorted(self.skip_counts.items())),
        }


@dataclass(slots=True)
class _PreparedObject:
    object: bpy.types.Object
    result: ObjectAnalysis
    resolutions: dict[int, MaterialResolution]
    snapshots: dict[int, ImageSnapshot]
    triangle_loops: dict[int, list[tuple[int, int, int]]]


class _Signature:
    def __init__(self) -> None:
        self._digest = hashlib.blake2b(digest_size=32)
        self.add("ALPHA_MATERIAL_SEPARATOR_INPUT_V2")

    def add(self, value: Any) -> None:
        encoded = json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode()
        self._digest.update(struct.pack("<Q", len(encoded)))
        self._digest.update(encoded)

    def add_bytes(self, value: bytes) -> None:
        self._digest.update(struct.pack("<Q", len(value)))
        self._digest.update(value)

    def hexdigest(self) -> str:
        return self._digest.hexdigest()


def _uv_values(layer) -> Iterable[tuple[float, float]]:
    modern = getattr(layer, "uv", None)
    if modern is not None:
        for item in modern:
            yield (float(item.vector[0]), float(item.vector[1]))
        return
    for item in layer.data:
        yield (float(item.uv[0]), float(item.uv[1]))


def _mesh_is_safe(object_: bpy.types.Object) -> str:
    mesh = object_.data
    if mesh.users > 1:
        return "MULTI_USER_MESH"
    if mesh.library is not None:
        return "LINKED_MESH"
    if not getattr(mesh, "is_editable", True):
        return "READ_ONLY_MESH"
    if object_.override_library is not None and not getattr(mesh, "is_editable", True):
        return "OVERRIDE_RESTRICTED_MESH"
    return ""


def _explicit_image(config: AnalysisConfig):
    return bpy.data.images.get(config.image_name) if config.image_name else None


def _prepare(
    objects: Iterable[bpy.types.Object],
    config: AnalysisConfig,
    *,
    image_cache: AnalysisImageCache | None = None,
    load_images: bool = True,
) -> tuple[list[_PreparedObject], AnalysisImageCache, str]:
    image_cache = image_cache or AnalysisImageCache()
    if config.material_overrides and config.image_name:
        raise OverrideConfigError(
            "OVERRIDE_CONFLICT",
            "Legacy selection-wide image override cannot be combined with per-material overrides",
        )
    signature = _Signature()
    signature.add(config.payload())
    explicit_image = _explicit_image(config)
    override_by_material = {
        item.material_name: item for item in config.material_overrides
    }
    encountered_materials: set[str] = set()
    signature.add(
        {
            "explicit_image_requested": config.image_name,
            "explicit_image_pointer": explicit_image.as_pointer() if explicit_image else 0,
        }
    )
    prepared: list[_PreparedObject] = []

    for object_ in sorted(objects, key=lambda item: (item.name_full, item.as_pointer())):
        if object_.type != "MESH":
            continue
        mesh = object_.data
        result = ObjectAnalysis(object_)
        unsafe = _mesh_is_safe(object_)
        if unsafe:
            result.skipped_reason = unsafe

        signature.add(
            {
                "mesh_editable": getattr(mesh, "is_editable", True),
                "mesh_library": mesh.library.filepath if mesh.library else "",
                "mesh_name": mesh.name_full,
                "mesh_pointer": mesh.as_pointer(),
                "mesh_users": mesh.users,
                "object_name": object_.name_full,
                "object_pointer": object_.as_pointer(),
                "skip": unsafe,
            }
        )
        for vertex in mesh.vertices:
            signature.add_bytes(struct.pack("<3d", *vertex.co))
        for edge in mesh.edges:
            signature.add_bytes(struct.pack("<2I", *edge.vertices))
        for loop in mesh.loops:
            signature.add_bytes(struct.pack("<I", loop.vertex_index))
        for polygon in mesh.polygons:
            signature.add_bytes(
                struct.pack(
                    "<3I",
                    polygon.loop_start,
                    polygon.loop_total,
                    polygon.material_index,
                )
            )

        active_uv = mesh.uv_layers.active
        signature.add(
            {
                "active_uv": active_uv.name if active_uv else "",
                "uv_layers": [
                    {
                        "active_render": bool(getattr(layer, "active_render", False)),
                        "name": layer.name,
                    }
                    for layer in mesh.uv_layers
                ],
            }
        )
        for layer in mesh.uv_layers:
            for uv in _uv_values(layer):
                signature.add_bytes(struct.pack("<2d", *uv))

        resolutions: dict[int, MaterialResolution] = {}
        snapshots: dict[int, ImageSnapshot] = {}
        signature.add({"slot_count": len(object_.material_slots)})
        for slot_index, slot in enumerate(object_.material_slots):
            material = slot.material
            signature.add(
                {
                    "link": slot.link,
                    "material_name": material.name_full if material else "",
                    "material_pointer": material.as_pointer() if material else 0,
                    "slot_index": slot_index,
                }
            )
            if material is None:
                continue
            encountered_materials.add(material.name_full)
            signature.add(material_fingerprint(material))
            material_override = override_by_material.get(material.name_full)
            if material_override is not None:
                override_image = (
                    bpy.data.images.get(material_override.image_name)
                    if material_override.image_name
                    else None
                )
                if material_override.image_name and override_image is None:
                    resolution = MaterialResolution(
                        material=material,
                        supported=False,
                        reason="IMAGE_OVERRIDE_NOT_FOUND",
                    )
                else:
                    resolution = resolve_material(
                        material,
                        mesh,
                        explicit_image=override_image,
                        explicit_uv=material_override.uv_map_name,
                        explicit_channel=material_override.image_channel,
                        requested_address_mode=material_override.address_mode,
                    )
            elif config.image_name and explicit_image is None:
                resolution = MaterialResolution(
                    material=material,
                    supported=False,
                    reason="IMAGE_OVERRIDE_NOT_FOUND",
                )
            else:
                resolution = resolve_material(
                    material,
                    mesh,
                    explicit_image=explicit_image,
                    explicit_uv=config.uv_map_name,
                    explicit_channel=config.image_channel,
                    requested_address_mode=config.address_mode,
                )
            resolutions[slot_index] = resolution
            signature.add(
                {
                    "address": resolution.address_mode.value,
                    "channel": resolution.channel,
                    "reason": resolution.reason,
                    "source_kind": resolution.source_kind,
                    "supported": resolution.supported,
                    "uv": resolution.uv_map_name,
                }
            )
            if resolution.supported and resolution.image is not None:
                if load_images:
                    try:
                        snapshot = image_cache.get(
                            resolution.image,
                            channel=resolution.channel,
                            threshold=config.settings.alpha_threshold,
                        )
                    except ImageReadError as error:
                        resolution = MaterialResolution(
                            material=material,
                            supported=False,
                            reason=f"IMAGE_READ_ERROR:{error}",
                        )
                        resolutions[slot_index] = resolution
                        signature.add(resolution.reason)
                    else:
                        snapshots[slot_index] = snapshot
                        image = resolution.image
                        signature.add(
                            {
                                "alpha_mode": image.alpha_mode,
                                "channels": image.channels,
                                "digest": snapshot.digest,
                                "dimensions": [snapshot.width, snapshot.height],
                                "filepath": image.filepath,
                                "image_name": image.name_full,
                                "image_pointer": image.as_pointer(),
                                "is_dirty": image.is_dirty,
                                "packed": bool(image.packed_file),
                                "source": image.source,
                            }
                        )
                else:
                    signature.add(
                        {
                            "deferred_image_pointer": resolution.image.as_pointer(),
                            "deferred_image_channel": resolution.channel,
                        }
                    )

        mesh.calc_loop_triangles()
        triangle_loops: dict[int, list[tuple[int, int, int]]] = defaultdict(list)
        for triangle in mesh.loop_triangles:
            triangle_loops[triangle.polygon_index].append(tuple(triangle.loops))
        prepared.append(
            _PreparedObject(
                object=object_,
                result=result,
                resolutions=resolutions,
                snapshots=snapshots,
                triangle_loops=triangle_loops,
            )
        )
    unused_overrides = sorted(set(override_by_material) - encountered_materials)
    if unused_overrides:
        raise OverrideConfigError(
            "OVERRIDE_TARGET_NOT_SELECTED",
            "Override target material is not used by the selected meshes: "
            + ", ".join(unused_overrides),
        )
    return prepared, image_cache, signature.hexdigest()


def validate_report(report: AnalysisReport) -> tuple[bool, str]:
    try:
        for object_ in report.objects:
            if object_.name_full not in bpy.data.objects or bpy.data.objects.get(object_.name_full) != object_:
                return False, "OBJECT_DELETED_OR_REPLACED"
        _prepared, _cache, signature = _prepare(report.objects, report.config)
    except (ReferenceError, RuntimeError, ValueError):
        return False, "INPUT_DATABLOCK_UNAVAILABLE"
    return (signature == report.input_signature, "OK" if signature == report.input_signature else "INPUTS_CHANGED")


class AnalysisEngine:
    """Chunkable main-thread engine used by synchronous and modal operators."""

    def __init__(
        self,
        objects: Iterable[bpy.types.Object],
        config: AnalysisConfig,
        *,
        defer_images: bool = False,
    ) -> None:
        self.objects = tuple(objects)
        self.config = config
        self.started = time.perf_counter()
        self.image_cache = AnalysisImageCache()
        self._deferred_images = defer_images
        self._image_builders: list[ImageSnapshotBuilder] = []
        self._image_builder_index = 0
        if defer_images:
            self.prepared, _cache, _provisional_signature = _prepare(
                self.objects,
                config,
                image_cache=self.image_cache,
                load_images=False,
            )
            self.signature = ""
            unique_requests = {}
            for prepared in self.prepared:
                for resolution in prepared.resolutions.values():
                    if resolution.supported and resolution.image is not None:
                        key = (
                            resolution.image.as_pointer(),
                            resolution.channel,
                            config.settings.alpha_threshold,
                        )
                        unique_requests.setdefault(
                            key,
                            (resolution.image, resolution.channel),
                        )
            self._image_builders = [
                ImageSnapshotBuilder(
                    image,
                    channel=channel,
                    threshold=config.settings.alpha_threshold,
                )
                for image, channel in unique_requests.values()
            ]
        else:
            self.prepared, self.image_cache, self.signature = _prepare(
                self.objects,
                config,
                image_cache=self.image_cache,
            )
        polygon_total = sum(len(item.object.data.polygons) for item in self.prepared)
        self.total = polygon_total + sum(
            builder.height for builder in self._image_builders
        )
        self.completed = 0
        self.cancelled = False
        self._prepared_index = 0
        self._polygon_index = 0
        self.counts: Counter = Counter()
        self.skip_counts: Counter = Counter()
        self.metrics: Counter = Counter()
        if not defer_images:
            self._initialize_groups()

    def _initialize_groups(self) -> None:
        for prepared in self.prepared:
            if prepared.result.skipped_reason:
                self.skip_counts[prepared.result.skipped_reason] += 1
                continue
            for slot_index, resolution in prepared.resolutions.items():
                slot = prepared.object.material_slots[slot_index]
                material = slot.material
                if material is None:
                    continue
                pointer = material.as_pointer()
                snapshot = prepared.snapshots.get(slot_index)
                digest = snapshot.digest if snapshot is not None else ""
                prepared.result.groups.setdefault(
                    pointer,
                    MaterialGroupAnalysis(
                        material=material,
                        resolution=resolution,
                        image_digest=digest,
                        source_fingerprint=source_fingerprint(material, digest),
                    ),
                )

    def _finalize_deferred_images(self) -> None:
        self.prepared, self.image_cache, self.signature = _prepare(
            self.objects,
            self.config,
            image_cache=self.image_cache,
            load_images=True,
        )
        self._deferred_images = False
        self._initialize_groups()

    def cancel(self) -> None:
        self.cancelled = True

    def _record_unsupported(
        self,
        prepared: _PreparedObject,
        polygon: bpy.types.MeshPolygon,
        reason: str,
        material: bpy.types.Material | None,
    ) -> None:
        result = ClassificationResult(
            classification=FaceClass.UNSUPPORTED,
            covered_texels=0,
            affected_texels=0,
            opaque_texels=0,
            affected_fraction=0.0,
            unsupported_reason=reason,
        )
        pointer = material.as_pointer() if material else 0
        prepared.result.faces[polygon.index] = FaceAnalysis(
            polygon.index, polygon.material_index, pointer, result
        )
        self.counts[FaceClass.UNSUPPORTED] += 1
        if material is not None:
            resolution = prepared.resolutions.get(polygon.material_index)
            if resolution is None:
                resolution = MaterialResolution(material, False, reason)
            group = prepared.result.groups.get(pointer)
            if group is None:
                group = MaterialGroupAnalysis(
                    material=material,
                    resolution=resolution,
                    source_fingerprint=source_fingerprint(material, ""),
                )
                prepared.result.groups[pointer] = group
            group.face_indices[FaceClass.UNSUPPORTED].append(polygon.index)
            group.counts[FaceClass.UNSUPPORTED] += 1

    def _analyze_polygon(self, prepared: _PreparedObject, polygon) -> None:
        object_ = prepared.object
        if prepared.result.skipped_reason:
            return
        slot_index = polygon.material_index
        slot = object_.material_slots[slot_index] if slot_index < len(object_.material_slots) else None
        material = slot.material if slot else None
        if material is None:
            self._record_unsupported(prepared, polygon, "MATERIAL_SLOT_EMPTY", None)
            return
        resolution = prepared.resolutions.get(slot_index)
        if resolution is None or not resolution.supported:
            self._record_unsupported(
                prepared,
                polygon,
                resolution.reason if resolution else "MATERIAL_UNRESOLVED",
                material,
            )
            return
        snapshot = prepared.snapshots.get(slot_index)
        if snapshot is None:
            self._record_unsupported(prepared, polygon, "IMAGE_SNAPSHOT_MISSING", material)
            return
        uv_layer = object_.data.uv_layers.get(resolution.uv_map_name)
        loop_triangles = prepared.triangle_loops.get(polygon.index, ())
        if uv_layer is None or not loop_triangles:
            self._record_unsupported(prepared, polygon, "UV_TRIANGLES_UNAVAILABLE", material)
            return

        uv_data = getattr(uv_layer, "uv", None)
        triangles = []
        for loops in loop_triangles:
            points = []
            for loop_index in loops:
                if uv_data is not None:
                    uv = uv_data[loop_index].vector
                else:
                    uv = uv_layer.data[loop_index].uv
                points.append(uv_to_texel_edge(uv, snapshot.width, snapshot.height))
            triangles.append(tuple(points))
        cache_digest = hashlib.blake2b(digest_size=24)
        cache_digest.update(b"AMS_COVERAGE_V1")
        cache_digest.update(
            struct.pack(
                "<5Q",
                snapshot.width,
                snapshot.height,
                self.config.settings.margin_texels,
                self.config.settings.max_scanlines,
                self.config.settings.max_run_emissions,
            )
        )
        for triangle in triangles:
            for point in triangle:
                cache_digest.update(struct.pack("<2d", *point))
        coverage_key = cache_digest.hexdigest()
        coverage = runtime.coverage_get(coverage_key)
        if coverage is None:
            self.metrics["coverage_cache_misses"] += 1
            try:
                coverage = rasterize_polygon(
                    triangles,
                    margin_texels=self.config.settings.margin_texels,
                    max_scanlines=self.config.settings.max_scanlines,
                    max_run_emissions=self.config.settings.max_run_emissions,
                )
            except RasterBudgetExceeded as error:
                classified = ClassificationResult(
                    classification=FaceClass.UNSUPPORTED,
                    covered_texels=0,
                    affected_texels=0,
                    opaque_texels=0,
                    affected_fraction=0.0,
                    unsupported_reason=f"BUDGET_{error.budget.upper()}",
                )
            except InvalidRasterInput:
                classified = ClassificationResult(
                    classification=FaceClass.UNSUPPORTED,
                    covered_texels=0,
                    affected_texels=0,
                    opaque_texels=0,
                    affected_fraction=0.0,
                    unsupported_reason="INVALID_UV",
                )
            else:
                runtime.coverage_set(coverage_key, coverage)
                classified = classify_coverage(
                    coverage,
                    snapshot.grid,
                    address_mode=resolution.address_mode,
                    settings=self.config.settings,
                )
        else:
            self.metrics["coverage_cache_hits"] += 1
            classified = classify_coverage(
                coverage,
                snapshot.grid,
                address_mode=resolution.address_mode,
                settings=self.config.settings,
            )
        pointer = material.as_pointer()
        face = FaceAnalysis(polygon.index, slot_index, pointer, classified)
        prepared.result.faces[polygon.index] = face
        group = prepared.result.groups.get(pointer)
        if group is None:
            group = MaterialGroupAnalysis(
                material=material,
                resolution=resolution,
                image_digest=snapshot.digest,
                source_fingerprint=source_fingerprint(material, snapshot.digest),
            )
            prepared.result.groups[pointer] = group
        group.face_indices[classified.classification].append(polygon.index)
        group.counts[classified.classification] += 1
        group.affected_texels += classified.affected_texels
        group.covered_texels += classified.covered_texels
        self.counts[classified.classification] += 1
        if classified.raster_stats is not None:
            stats = classified.raster_stats
            self.metrics.update(
                {
                    "triangles": stats.triangles,
                    "degenerate_triangles": stats.degenerate_triangles,
                    "scanlines": stats.scanlines,
                    "emitted_runs": stats.emitted_runs,
                    "union_runs": stats.union_runs,
                    "covered_texels": stats.covered_texels,
                }
            )

    def step(self, polygon_budget: int = 128) -> bool:
        if self.cancelled:
            return True
        if self._deferred_images:
            if self._image_builder_index < len(self._image_builders):
                builder = self._image_builders[self._image_builder_index]
                rows = builder.step()
                self.completed += rows
                self.metrics["image_digest_rows"] += rows
                if builder.complete:
                    snapshot = builder.finish()
                    self.image_cache.store_for_threshold(
                        snapshot, self.config.settings.alpha_threshold
                    )
                    self.metrics["full_image_digests"] += 1
                    self._image_builder_index += 1
                return False
            self._finalize_deferred_images()
        processed = 0
        while self._prepared_index < len(self.prepared) and processed < polygon_budget:
            prepared = self.prepared[self._prepared_index]
            polygons = prepared.object.data.polygons
            while self._polygon_index < len(polygons) and processed < polygon_budget:
                self._analyze_polygon(prepared, polygons[self._polygon_index])
                self._polygon_index += 1
                self.completed += 1
                processed += 1
            if self._polygon_index >= len(polygons):
                self._polygon_index = 0
                self._prepared_index += 1
        return self._prepared_index >= len(self.prepared)

    def finish(self) -> AnalysisReport:
        if (
            self.cancelled
            or self._deferred_images
            or self._prepared_index < len(self.prepared)
        ):
            raise RuntimeError("analysis is incomplete")
        analysis_id = hashlib.blake2b(
            (self.signature + json.dumps(self.config.payload(), sort_keys=True)).encode(),
            digest_size=16,
        ).hexdigest()
        return AnalysisReport(
            analysis_id=analysis_id,
            input_signature=self.signature,
            config=self.config,
            objects=self.objects,
            object_results={
                item.object.as_pointer(): item.result for item in self.prepared
            },
            counts=self.counts,
            skip_counts=self.skip_counts,
            created_monotonic=time.monotonic(),
            elapsed_seconds=time.perf_counter() - self.started,
            metrics=self.metrics,
        )
