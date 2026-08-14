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
import numpy

from .. import runtime
from ..core import (
    AddressMode,
    AnalysisSettings,
    ClassificationResult,
    FaceClass,
    InvalidRasterInput,
    RasterStats,
    classify_counted,
    rasterize_batch,
)
from ..core import alpha as alpha_core
from ..core.classify import classify_stats
from . import gpu_raster
from ..overrides import MaterialOverride, OverrideConfigError
from ..unsupported import unsupported_scope
from .fingerprints import material_fingerprint, source_fingerprint
from . import image_data
from .image_data import (
    ImageReadError,
    ImageSnapshot,
    ImageSnapshotBuilder,
    read_image_snapshot,
)
from .material_metadata import POINTER_PROPERTY, PREFIX
from .material_resolver import MaterialResolution, resolve_material

ImageCache = dict[tuple[int, str, float], ImageSnapshot]

# Polygons per batched rasterization pass, independent of the caller's step
# budget. Measured: 256 beats both smaller and larger windows by about 20
# percent because the intermediate arrays stay in cache.
_RASTER_BATCH_POLYGONS = 256

# Polygons the GPU path lets pile up before it submits a dispatch. Every
# dispatch allocates and uploads its own textures, so a small one is nearly all
# fixed cost: at the modal cadence's roughly 1,300 polygons per flush the path
# returns 11.9%, and at 512 per step it is slower than the CPU outright. The
# responsiveness contract bounds one `step`, not one dispatch, so holding faces
# back across steps buys the larger dispatch without a longer callback.
# Measured: 16,384 returns 23.9% for about 60 ms on the worst step.
_GPU_SUBMIT_POLYGONS = 16_384


def _phase_totals() -> dict[str, float]:
    """Process-wide phase accumulators, sampled as deltas around one analysis."""
    totals = {
        f"phase_image_{name}_seconds": seconds
        for name, seconds in image_data.PHASE_SECONDS.items()
    }
    totals.update(
        {
            f"phase_{name}_seconds": seconds
            for name, seconds in alpha_core.PHASE_SECONDS.items()
        }
    )
    return totals


@dataclass(frozen=True, slots=True)
class AnalysisConfig:
    image_name: str = ""
    uv_map_name: str = ""
    image_channel: str = "ALPHA"
    address_mode: str = "AUTO"
    settings: AnalysisSettings = AnalysisSettings()
    material_overrides: tuple[MaterialOverride, ...] = ()
    #: The reader's manual CPU fallback, and the exact-kernel opt-in. Neither is
    #: in `payload()` directly: what changes the numbers is the width they were
    #: computed at, which these two together resolve to.
    use_gpu: bool = True
    high_precision: bool = False

    def precision(self) -> str:
        """The width this configuration computes at, as an input signature field.

        The CPU and the double-precision kernel are exact reproductions of each
        other, so they are one input under three of the four combinations. The
        default single-precision kernel can classify a face differently, so it
        has to be told apart from them.
        """
        return "EXACT" if not self.use_gpu or self.high_precision else "FP32"

    def payload(self) -> dict[str, Any]:
        return {
            "address_mode": self.address_mode,
            "image_channel": self.image_channel,
            "image_name": self.image_name,
            "material_overrides": [item.payload() for item in self.material_overrides],
            "precision": self.precision(),
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
    affected_texels: int = 0
    covered_texels: int = 0

    def public_count(self, face_class: FaceClass) -> int:
        return len(self.face_indices[face_class])


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
    structural_signature: str
    assignment_signature: str
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
                        "unsupported_scope": "DATA_SAFETY",
                    }
                )
                continue
            analyzed_objects += 1
            analyzed_polygons += len(result.faces)
            groups = []
            for material_pointer, group in result.groups.items():
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
                unsupported_scopes = Counter(
                    unsupported_scope(
                        face.result.unsupported_reason,
                        material_supported=group.resolution.supported,
                    )
                    for face in group_faces
                    if face.result.classification == FaceClass.UNSUPPORTED
                )
                move_count = (
                    len(group.face_indices[FaceClass.ALPHA_AFFECTED])
                    + len(group.face_indices[FaceClass.MIXED])
                    + int(unsupported_scopes["FACE_LOCAL"])
                )
                if group.resolution.supported and move_count:
                    planned_materials.add(group.material.as_pointer())
                    estimated_slots += 1
                if not group.resolution.supported:
                    default_disposition = "LEAVE_UNCHANGED"
                    default_planned_action = "LEAVE_UNCHANGED_NO_ALPHA_SOURCE"
                elif group.public_count(FaceClass.SUPPRESSED):
                    default_disposition = "REVIEW_REQUIRED"
                    default_planned_action = "SKIP_GROUP"
                elif move_count:
                    default_disposition = "SPLIT"
                    default_planned_action = (
                        "MOVE_UNCERTAIN_TO_ALPHA"
                        if unsupported_scopes["FACE_LOCAL"]
                        else "MOVE_TO_ALPHA"
                    )
                else:
                    default_disposition = "NO_CHANGES"
                    default_planned_action = "NO_CHANGES_NEEDED"
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
                            face_class.value: group.public_count(face_class)
                            for face_class in FaceClass
                        },
                        "covered_texels": group.covered_texels,
                        "default_disposition": default_disposition,
                        "default_planned_action": default_planned_action,
                        "image": resolution.image.name_full if resolution.image else "",
                        "material": group.material.name,
                        "resolution": resolution.source_kind
                        if resolution.supported
                        else resolution.reason,
                        "source_kind": resolution.source_kind,
                        "source_method": resolution.source_kind,
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
                        "unsupported_scopes": dict(
                            sorted(unsupported_scopes.items())
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
            "validation_state": (
                runtime.validation_state()
                if runtime.report(self.analysis_id) is self
                else runtime.VALIDATION_CLEAN
            ),
            "pending_scopes": (
                sorted(runtime.pending_scopes())
                if runtime.report(self.analysis_id) is self
                else []
            ),
            "dirty_reason": (
                runtime.dirty_reason()
                if runtime.report(self.analysis_id) is self
                else ""
            ),
        }


@dataclass(slots=True)
class _PreparedObject:
    """One selected object's resolved materials and loop-triangle layout.

    The triangles are three arrays rather than a dict of lists: `triangle_loops`
    is every loop triangle's three loop indices, and a polygon's triangles are
    the `triangle_counts` rows starting at `triangle_starts`. The UV arrays are
    filled lazily, because a UV map that no resolved material names is never
    read.
    """

    object: bpy.types.Object
    result: ObjectAnalysis
    resolutions: dict[int, MaterialResolution]
    snapshots: dict[int, ImageSnapshot]
    triangle_loops: numpy.ndarray
    triangle_starts: numpy.ndarray
    triangle_counts: numpy.ndarray
    # UV map name -> (coordinates, mask of non-finite loops, or None if none).
    uv_arrays: dict[str, tuple[numpy.ndarray, numpy.ndarray | None]] = field(
        default_factory=dict
    )
    # (UV map name, width, height) -> texel-edge coordinates, or None if the
    # object has no such UV map.
    texel_grids: dict[tuple[str, int, int], numpy.ndarray | None] = field(
        default_factory=dict
    )


@dataclass(slots=True)
class _DeferredFace:
    """One polygon awaiting the step chunk's batched rasterization and count.

    Holds the polygon index rather than the polygon, because that is all
    recording needs and an RNA reference is not worth carrying across the chunk.
    `coverage` is already set on a cache hit; otherwise `triangles` carries the
    raster input until the chunk is rasterized. `classified` short-circuits
    counting for a polygon the rasterizer reported as unsupported.
    """

    prepared: _PreparedObject
    polygon_index: int
    slot_index: int
    material: bpy.types.Material
    resolution: MaterialResolution
    snapshot: ImageSnapshot
    coverage: Any
    coverage_key: str
    triangles: Any = None
    classified: ClassificationResult | None = None


@dataclass(slots=True)
class _InFlight:
    """One chunk's faces and the GPU dispatches that will classify them.

    Reading a result texture waits for the dispatch that fills it, so the chunk
    is submitted and then left alone while the next chunk's UV traversal runs.
    Holding the batches also holds their textures, which the GPU is still
    reading.
    """

    faces: list[_DeferredFace]
    # (positions in `faces`, partial counts, the `gpu_raster` collect token).
    batches: list[tuple[list[int], Any, Any]]


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


# Explicit little-endian widths so the packed blocks keep the byte layout the
# per-element `struct.pack` calls they replaced used.
_F8 = numpy.dtype("<f8")
_I4 = numpy.dtype("<i4")


def _packed(collection, attribute: str, per_element: int, dtype) -> bytes:
    """One mesh attribute as a single contiguous block.

    `foreach_get` fills the whole array in C, so hashing a mesh costs one update
    per attribute rather than a `struct.pack` and two updates per element.
    """
    values = numpy.empty(len(collection) * per_element, dtype=dtype)
    collection.foreach_get(attribute, values)
    return values.tobytes()


def _uv_bytes(layer) -> bytes:
    """Every coordinate in one UV layer, as one block of little-endian doubles."""
    modern = getattr(layer, "uv", None)
    if modern is not None:
        return _packed(modern, "vector", 2, _F8)
    return _packed(layer.data, "uv", 2, _F8)


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


def _image_state(image: bpy.types.Image) -> dict[str, Any]:
    """Return cheap participating-image state without reading pixels."""

    return {
        "alpha_mode": image.alpha_mode,
        "channels": image.channels,
        "dimensions": [int(image.size[0]), int(image.size[1])],
        "filepath": image.filepath,
        "image_name": image.name_full,
        "image_pointer": image.as_pointer(),
        "is_dirty": bool(image.is_dirty),
        "packed": bool(image.packed_file),
        "source": image.source,
    }


def _structural_signature(
    objects: Iterable[bpy.types.Object], config: AnalysisConfig
) -> str:
    """Hash every mesh-side analysis input without reading image pixels.

    Face selection, active selection, object transforms, and Object/Edit Mode
    are intentionally absent: none changes which base-mesh UV texels a polygon
    covers. Resolver results and participating image state are included here;
    unrelated shader branches are assignment inputs, not classification inputs.
    Participating image pixels remain in the authoritative full signature and
    are rechecked whenever their mutation state cannot be proven reusable.
    """

    signature = _Signature()
    # V2: mesh arrays are hashed one length-prefixed block per attribute rather
    # than one framed chunk per element. Same inputs, different encoding, and
    # the digest is only ever compared to another one from this same process.
    signature.add("ALPHA_MATERIAL_SEPARATOR_STRUCTURAL_V2")
    signature.add(config.payload())
    explicit_image = _explicit_image(config)
    override_by_material = {
        item.material_name: item for item in config.material_overrides
    }
    encountered_materials: set[str] = set()
    for object_ in sorted(objects, key=lambda item: (item.name_full, item.as_pointer())):
        if object_.type != "MESH":
            signature.add(
                {
                    "object_name": object_.name_full,
                    "object_pointer": object_.as_pointer(),
                    "object_type": object_.type,
                }
            )
            continue
        mesh = object_.data
        unsafe = _mesh_is_safe(object_)
        signature.add(
            {
                "mesh_editable": getattr(mesh, "is_editable", True),
                "mesh_library": mesh.library.filepath if mesh.library else "",
                "mesh_name": mesh.name_full,
                "mesh_pointer": mesh.as_pointer(),
                "mesh_users": mesh.users,
                "object_name": object_.name_full,
                "object_pointer": object_.as_pointer(),
                "object_type": object_.type,
                "skip": unsafe,
            }
        )
        signature.add_bytes(_packed(mesh.vertices, "co", 3, _F8))
        signature.add_bytes(_packed(mesh.edges, "vertices", 2, _I4))
        signature.add_bytes(_packed(mesh.loops, "vertex_index", 1, _I4))
        signature.add_bytes(_packed(mesh.polygons, "loop_start", 1, _I4))
        signature.add_bytes(_packed(mesh.polygons, "loop_total", 1, _I4))
        signature.add_bytes(_packed(mesh.polygons, "material_index", 1, _I4))
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
            signature.add_bytes(_uv_bytes(layer))
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
            resolution = _resolve_configured_material(
                material,
                mesh,
                config,
                explicit_image,
                override_by_material,
            )
            signature.add(
                {
                    "address": resolution.address_mode.value,
                    "channel": resolution.channel,
                    "image": (
                        _image_state(resolution.image)
                        if resolution.supported and resolution.image is not None
                        else None
                    ),
                    "reason": resolution.reason,
                    "source_kind": resolution.source_kind,
                    "supported": resolution.supported,
                    "uv": resolution.uv_map_name,
                }
            )
    unused_overrides = sorted(set(override_by_material) - encountered_materials)
    if unused_overrides:
        raise OverrideConfigError(
            "OVERRIDE_TARGET_NOT_SELECTED",
            "Override target material is not used by the selected meshes: "
            + ", ".join(unused_overrides),
        )
    return signature.hexdigest()


def _assignment_signature(objects: Iterable[bpy.types.Object]) -> str:
    """Hash source/derived state that may change the reviewed mutation plan."""

    signature = _Signature()
    signature.add("ALPHA_MATERIAL_SEPARATOR_ASSIGNMENT_V1")
    source_pointers: set[int] = set()
    fingerprints: dict[int, str] = {}

    def fingerprint(material) -> str:
        pointer = material.as_pointer()
        if pointer not in fingerprints:
            fingerprints[pointer] = material_fingerprint(material)
        return fingerprints[pointer]

    for object_ in sorted(objects, key=lambda item: (item.name_full, item.as_pointer())):
        if object_.type != "MESH":
            continue
        for slot_index, slot in enumerate(object_.material_slots):
            material = slot.material
            if material is None:
                signature.add((object_.as_pointer(), slot_index, slot.link, 0))
                continue
            pointer = material.as_pointer()
            source_pointers.add(pointer)
            source = getattr(material, POINTER_PROPERTY, None)
            signature.add(
                {
                    "editable": bool(getattr(material, "is_editable", True)),
                    "fingerprint": fingerprint(material),
                    "library": material.library.filepath if material.library else "",
                    "link": slot.link,
                    "material_name": material.name_full,
                    "material_pointer": pointer,
                    "metadata": sorted(
                        (key, material.get(key))
                        for key in material.keys()
                        if key.startswith(PREFIX)
                    ),
                    "object_pointer": object_.as_pointer(),
                    "slot_index": slot_index,
                    "source_pointer": source.as_pointer() if source else 0,
                }
            )
    for material in sorted(
        bpy.data.materials, key=lambda item: (item.name_full, item.as_pointer())
    ):
        source = getattr(material, POINTER_PROPERTY, None)
        if source is None or source.as_pointer() not in source_pointers:
            continue
        signature.add(
            {
                "fingerprint": fingerprint(material),
                "material_name": material.name_full,
                "material_pointer": material.as_pointer(),
                "metadata": sorted(
                    (key, material.get(key))
                    for key in material.keys()
                    if key.startswith(PREFIX)
                ),
                "source_pointer": source.as_pointer(),
            }
        )
    return signature.hexdigest()


def _requires_conservative_image_recheck(report: AnalysisReport) -> bool:
    """Generated or already-dirty images cannot rely on update hints alone."""

    for object_result in report.object_results.values():
        for group in object_result.groups.values():
            image = group.resolution.image
            if image is None:
                continue
            if image.source == "GENERATED" or bool(image.is_dirty):
                return True
    return False


def _explicit_image(config: AnalysisConfig):
    return bpy.data.images.get(config.image_name) if config.image_name else None


def _resolve_configured_material(
    material: bpy.types.Material,
    mesh: bpy.types.Mesh,
    config: AnalysisConfig,
    explicit_image,
    override_by_material: dict[str, MaterialOverride],
) -> MaterialResolution:
    material_override = override_by_material.get(material.name_full)
    if material_override is not None:
        override_image = (
            bpy.data.images.get(material_override.image_name)
            if material_override.image_name
            else None
        )
        if material_override.image_name and override_image is None:
            return MaterialResolution(
                material=material,
                supported=False,
                reason="IMAGE_OVERRIDE_NOT_FOUND",
            )
        return resolve_material(
            material,
            mesh,
            explicit_image=override_image,
            explicit_uv=material_override.uv_map_name,
            explicit_channel=material_override.image_channel,
            requested_address_mode=material_override.address_mode,
        )
    if config.image_name and explicit_image is None:
        return MaterialResolution(
            material=material,
            supported=False,
            reason="IMAGE_OVERRIDE_NOT_FOUND",
        )
    return resolve_material(
        material,
        mesh,
        explicit_image=explicit_image,
        explicit_uv=config.uv_map_name,
        explicit_channel=config.image_channel,
        requested_address_mode=config.address_mode,
    )


def _image_snapshot(
    cache: ImageCache,
    image: bpy.types.Image,
    *,
    channel: str,
    threshold: float,
) -> ImageSnapshot:
    key = (image.as_pointer(), channel, threshold)
    snapshot = cache.get(key)
    if snapshot is None:
        snapshot = read_image_snapshot(image, channel=channel, threshold=threshold)
        cache[key] = snapshot
    return snapshot


def _prepare(
    objects: Iterable[bpy.types.Object],
    config: AnalysisConfig,
    *,
    image_cache: ImageCache | None = None,
    load_images: bool = True,
) -> tuple[list[_PreparedObject], ImageCache]:
    image_cache = {} if image_cache is None else image_cache
    if config.material_overrides and config.image_name:
        raise OverrideConfigError(
            "OVERRIDE_CONFLICT",
            "Legacy selection-wide image override cannot be combined with per-material overrides",
        )
    explicit_image = _explicit_image(config)
    override_by_material = {
        item.material_name: item for item in config.material_overrides
    }
    encountered_materials: set[str] = set()
    prepared: list[_PreparedObject] = []

    for object_ in sorted(objects, key=lambda item: (item.name_full, item.as_pointer())):
        if object_.type != "MESH":
            continue
        mesh = object_.data
        result = ObjectAnalysis(object_)
        unsafe = _mesh_is_safe(object_)
        if unsafe:
            result.skipped_reason = unsafe

        resolutions: dict[int, MaterialResolution] = {}
        snapshots: dict[int, ImageSnapshot] = {}
        for slot_index, slot in enumerate(object_.material_slots):
            material = slot.material
            if material is None:
                continue
            encountered_materials.add(material.name_full)
            resolution = _resolve_configured_material(
                material,
                mesh,
                config,
                explicit_image,
                override_by_material,
            )
            resolutions[slot_index] = resolution
            if resolution.supported and resolution.image is not None:
                if load_images:
                    try:
                        snapshot = _image_snapshot(
                            image_cache,
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
                    else:
                        snapshots[slot_index] = snapshot

        mesh.calc_loop_triangles()
        triangle_loops, starts, counts = _triangle_layout(mesh)
        prepared.append(
            _PreparedObject(
                object=object_,
                result=result,
                resolutions=resolutions,
                snapshots=snapshots,
                triangle_loops=triangle_loops,
                triangle_starts=starts,
                triangle_counts=counts,
            )
        )
    unused_overrides = sorted(set(override_by_material) - encountered_materials)
    if unused_overrides:
        raise OverrideConfigError(
            "OVERRIDE_TARGET_NOT_SELECTED",
            "Override target material is not used by the selected meshes: "
            + ", ".join(unused_overrides),
        )
    return prepared, image_cache


def _triangle_layout(
    mesh: bpy.types.Mesh,
) -> tuple[numpy.ndarray, numpy.ndarray, numpy.ndarray]:
    """Every loop triangle's loops, plus each polygon's slice of them.

    Call `calc_loop_triangles` first. Two whole-attribute reads replace a Python
    loop that built one tuple and one dict entry per triangle.
    """
    count = len(mesh.loop_triangles)
    loops = numpy.empty(count * 3, dtype=numpy.int32)
    mesh.loop_triangles.foreach_get("loops", loops)
    loops = loops.reshape(-1, 3)
    polygon = numpy.empty(count, dtype=numpy.int32)
    mesh.loop_triangles.foreach_get("polygon_index", polygon)
    # Blender emits loop triangles grouped by polygon, which is what lets a
    # polygon be a slice rather than a dict entry. Sorting when it is not is
    # cheaper than depending on it; stable keeps the within-polygon order the
    # dict preserved.
    if count and (numpy.diff(polygon) < 0).any():
        order = numpy.argsort(polygon, kind="stable")
        loops, polygon = loops[order], polygon[order]
    counts = numpy.bincount(polygon, minlength=len(mesh.polygons)).astype(numpy.int64)
    starts = numpy.concatenate(
        (numpy.zeros(1, dtype=numpy.int64), numpy.cumsum(counts))
    )[:-1]
    return loops, starts, counts


def _coverage_key(snapshot, triangles: numpy.ndarray, settings) -> str:
    """The coverage cache key for one polygon's texel-space triangles."""
    digest = hashlib.blake2b(digest_size=24)
    # V2: the triangles are hashed as one contiguous block rather than two
    # doubles at a time. The coverage cache is a process-local dict, so no
    # stored key is ever compared against one from another encoding.
    digest.update(b"AMS_COVERAGE_V2")
    digest.update(
        struct.pack(
            "<5Q",
            snapshot.width,
            snapshot.height,
            settings.margin_texels,
            settings.max_scanlines,
            settings.max_run_emissions,
        )
    )
    digest.update(triangles.tobytes())
    return digest.hexdigest()


def _input_signature(
    structural_signature: str,
    prepared: Iterable[_PreparedObject],
    config: AnalysisConfig,
) -> str:
    """Combine structural authority with the participating pixel digests."""

    signature = _Signature()
    signature.add("ALPHA_MATERIAL_SEPARATOR_INPUT_V3")
    signature.add(structural_signature)
    signature.add(config.payload())
    for item in prepared:
        signature.add(item.object.as_pointer())
        for slot_index, resolution in sorted(item.resolutions.items()):
            snapshot = item.snapshots.get(slot_index)
            signature.add(
                {
                    "channel": resolution.channel,
                    "component_count": (
                        snapshot.component_count if snapshot is not None else 0
                    ),
                    "digest": snapshot.digest if snapshot is not None else "",
                    "height": snapshot.height if snapshot is not None else 0,
                    "image_pointer": (
                        resolution.image.as_pointer()
                        if resolution.image is not None
                        else 0
                    ),
                    "reason": resolution.reason,
                    "slot_index": slot_index,
                    "supported": resolution.supported,
                    "width": snapshot.width if snapshot is not None else 0,
                }
            )
    return signature.hexdigest()


def validate_report(report: AnalysisReport) -> tuple[bool, str]:
    validation_started = time.perf_counter()
    current_report = runtime.report(report.analysis_id) is report

    def record(
        mode: str,
        valid: bool,
        reason: str,
        *,
        image_digest_rows: int = 0,
    ) -> None:
        if not current_report:
            return
        runtime.record_validation(
            mode,
            valid,
            reason,
            component_hash_calls=1,
            image_digest_rows=image_digest_rows,
            rasterized_polygons=0,
            coverage_hits=0,
            coverage_misses=0,
            elapsed_seconds=time.perf_counter() - validation_started,
        )

    if current_report and runtime.validation_state() == runtime.VALIDATION_STALE:
        return False, runtime.dirty_reason() or "INPUTS_CHANGED"

    pending = runtime.pending_scopes() if current_report else frozenset()
    classification_only_recheck = (
        bool(pending) and "IMAGE" not in pending and "UNKNOWN" not in pending
    )
    attempted_mode = "STRUCTURAL"
    try:
        for object_ in report.objects:
            if object_.name_full not in bpy.data.objects or bpy.data.objects.get(object_.name_full) != object_:
                reason = "OBJECT_DELETED_OR_REPLACED"
                record("STRUCTURAL", False, reason)
                return False, reason
        structural_signature = _structural_signature(report.objects, report.config)
        structural_valid = structural_signature == report.structural_signature
        if not structural_valid:
            record("STRUCTURAL", False, "INPUTS_CHANGED")
            return False, "INPUTS_CHANGED"
        assignment_signature = _assignment_signature(report.objects)
        if assignment_signature != report.assignment_signature:
            report.assignment_signature = assignment_signature
            for window_manager in bpy.data.window_managers:
                runtime.clear_review(window_manager)
        conservative_image_recheck = _requires_conservative_image_recheck(report)
        can_reuse_images = (
            current_report
            and runtime.validation_is_current(report.analysis_id)
            and not conservative_image_recheck
        )
        if (
            classification_only_recheck and not conservative_image_recheck
        ) or can_reuse_images:
            record("STRUCTURAL", True, "OK")
            return True, "OK"
        attempted_mode = "FULL"
        prepared, _cache = _prepare(
            report.objects,
            report.config,
        )
        signature = _input_signature(
            structural_signature,
            prepared,
            report.config,
        )
    except (OverrideConfigError, ReferenceError, RuntimeError, ValueError):
        reason = "INPUT_DATABLOCK_UNAVAILABLE"
        record(attempted_mode, False, reason)
        return False, reason
    valid = signature == report.input_signature
    reason = "OK" if valid else "INPUTS_CHANGED"
    digest_rows = sum(snapshot.height for snapshot in _cache.values())
    record("FULL", valid, reason, image_digest_rows=digest_rows)
    return valid, reason


def validate_report_for_publication(report: AnalysisReport) -> tuple[bool, str]:
    """Reject a modal report assembled across changing authoritative inputs.

    Stable file-backed images use the structural signature, whose cheap image
    state includes identity, bindings, dimensions, packing, and dirty state.
    Generated or already-dirty images receive a second authoritative digest
    because Blender exposes no reliable pixel revision for them.
    """

    try:
        for object_ in report.objects:
            if (
                object_.name_full not in bpy.data.objects
                or bpy.data.objects.get(object_.name_full) != object_
            ):
                return False, "OBJECT_DELETED_OR_REPLACED"
        if (
            _structural_signature(report.objects, report.config)
            != report.structural_signature
        ):
            return False, "INPUTS_CHANGED"
    except (AttributeError, ReferenceError, RuntimeError, ValueError):
        return False, "INPUT_DATABLOCK_UNAVAILABLE"
    if _requires_conservative_image_recheck(report):
        return validate_report(report)
    return True, "OK"


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
        self._phase_baseline = _phase_totals()
        signature_started = time.perf_counter()
        self.structural_signature = _structural_signature(self.objects, self.config)
        self.assignment_signature = _assignment_signature(self.objects)
        prepare_started = time.perf_counter()
        prepare_baseline = sum(_phase_totals().values())
        self.image_cache: ImageCache = {}
        self._deferred_images = defer_images
        self._image_builders: list[ImageSnapshotBuilder] = []
        self._image_builder_index = 0
        if defer_images:
            self.prepared, _cache = _prepare(
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
            self.prepared, self.image_cache = _prepare(
                self.objects,
                config,
                image_cache=self.image_cache,
            )
            self.signature = _input_signature(
                self.structural_signature,
                self.prepared,
                self.config,
            )
        construction_finished = time.perf_counter()
        polygon_total = sum(len(item.object.data.polygons) for item in self.prepared)
        self.total = polygon_total + sum(
            builder.height for builder in self._image_builders
        )
        self.completed = 0
        self.cancelled = False
        self._prepared_index = 0
        self._polygon_index = 0
        self._pending: list[_DeferredFace] = []
        self._inflight: _InFlight | None = None
        # The GPU kernel fuses rasterizing and counting, so it cannot use a
        # coverage cache keyed on geometry alone, and it has nothing to dilate
        # for a raster margin. Both make it a whole-run decision rather than a
        # per-chunk one. Tests and the performance protocol force it either way.
        self._gpu = (
            config.use_gpu
            and gpu_raster.available(high_precision=config.high_precision)
            and not self.config.settings.margin_texels
        )
        self.counts: Counter = Counter()
        self.skip_counts: Counter = Counter()
        self.metrics: Counter = Counter()
        # Construction runs before `metrics` exists, so its two phases are
        # recorded here rather than timed in place. Prepare subtracts the image
        # phases it nests, which are reported separately as their own deltas.
        self.metrics["phase_signature_seconds"] = prepare_started - signature_started
        self.metrics["phase_prepare_seconds"] = (
            construction_finished
            - prepare_started
            - (sum(_phase_totals().values()) - prepare_baseline)
        )
        if not defer_images:
            self._initialize_groups()

    @property
    def stage(self) -> str:
        if (
            self._deferred_images
            and self._image_builder_index < len(self._image_builders)
        ):
            return "Reading Textures"
        return "Analyzing Faces"

    def close(self) -> None:
        for builder in self._image_builders:
            builder.close()

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
        for prepared in self.prepared:
            for slot_index, resolution in prepared.resolutions.items():
                if not resolution.supported or resolution.image is None:
                    continue
                key = (
                    resolution.image.as_pointer(),
                    resolution.channel,
                    self.config.settings.alpha_threshold,
                )
                snapshot = self.image_cache.get(key)
                if snapshot is None:
                    raise RuntimeError("completed image snapshot is unavailable")
                prepared.snapshots[slot_index] = snapshot
        self.signature = _input_signature(
            self.structural_signature,
            self.prepared,
            self.config,
        )
        self._deferred_images = False
        self._initialize_groups()

    def cancel(self) -> None:
        self.cancelled = True
        # Dropped rather than collected. Nothing will read the result, and the
        # handles hold GPU textures that only release when they do.
        self._inflight = None
        self.close()

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

    def _texel_grid(
        self, prepared: _PreparedObject, uv_map_name: str, snapshot: ImageSnapshot
    ) -> numpy.ndarray | None:
        """Every loop's UV scaled to `snapshot`'s texel edges, or None.

        None means the object has no such UV map. Cached per image size rather
        than per material slot, because slots sharing a size share the scaling.
        """
        key = (uv_map_name, snapshot.width, snapshot.height)
        grid = prepared.texel_grids.get(key, False)
        if grid is not False:
            return grid
        stored = prepared.uv_arrays.get(uv_map_name)
        if stored is None:
            mesh = prepared.object.data
            layer = mesh.uv_layers.get(uv_map_name)
            if layer is None:
                prepared.texel_grids[key] = None
                return None
            coordinates = numpy.empty(len(mesh.loops) * 2, dtype=numpy.float64)
            layer.uv.foreach_get("vector", coordinates)
            coordinates = coordinates.reshape(-1, 2)
            finite = numpy.isfinite(coordinates).all(axis=1)
            stored = (coordinates, None if finite.all() else ~finite)
            prepared.uv_arrays[uv_map_name] = stored
        if snapshot.width <= 0 or snapshot.height <= 0:
            raise InvalidRasterInput("image dimensions must be positive")
        grid = stored[0] * numpy.array(
            (snapshot.width, snapshot.height), dtype=numpy.float64
        )
        prepared.texel_grids[key] = grid
        return grid

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
        uv_started = time.perf_counter()
        triangle_count = int(prepared.triangle_counts[polygon.index])
        texel = (
            self._texel_grid(prepared, resolution.uv_map_name, snapshot)
            if triangle_count
            else None
        )
        if texel is None:
            self.metrics["phase_uv_seconds"] += time.perf_counter() - uv_started
            self._record_unsupported(prepared, polygon, "UV_TRIANGLES_UNAVAILABLE", material)
            return
        start = int(prepared.triangle_starts[polygon.index])
        loops = prepared.triangle_loops[start : start + triangle_count]
        non_finite = prepared.uv_arrays[resolution.uv_map_name][1]
        if non_finite is not None and non_finite[loops].any():
            # What `uv_to_texel_edge` raised when this was read point by point.
            # Reproduced deliberately: the abort is existing behaviour, and
            # turning it into a per-face reason is a separate decision.
            raise InvalidRasterInput("UV coordinates must be two finite values")
        triangles = texel[loops]
        if self._gpu:
            # No digest and no lookup: the cache stores spans keyed on geometry
            # and image size, and a kernel that returns counts cannot use such
            # an entry. Skipping the hash is also worth more than the cache
            # saves, which `docs/gpu-rasterization.md` records.
            self.metrics["phase_uv_seconds"] += time.perf_counter() - uv_started
            self.metrics["coverage_cache_bypassed"] += 1
            self._pending.append(
                _DeferredFace(
                    prepared=prepared,
                    polygon_index=polygon.index,
                    slot_index=slot_index,
                    material=material,
                    resolution=resolution,
                    snapshot=snapshot,
                    coverage=None,
                    coverage_key="",
                    triangles=triangles,
                )
            )
            return
        key_started = time.perf_counter()
        coverage_key = _coverage_key(snapshot, triangles, self.config.settings)
        lookup_started = time.perf_counter()
        coverage = runtime.coverage_get(coverage_key)
        lookup_finished = time.perf_counter()
        self.metrics["phase_uv_seconds"] += key_started - uv_started
        self.metrics["phase_cache_key_seconds"] += lookup_started - key_started
        self.metrics["phase_cache_lookup_seconds"] += lookup_finished - lookup_started
        if coverage is None:
            self.metrics["coverage_cache_misses"] += 1
        else:
            self.metrics["coverage_cache_hits"] += 1
        # Rasterizing and counting are both deferred so a whole step chunk can
        # share one pass. One polygon at a time costs a Python call per triangle
        # and per run, and a real mesh produces millions of both.
        self._pending.append(
            _DeferredFace(
                prepared=prepared,
                polygon_index=polygon.index,
                slot_index=slot_index,
                material=material,
                resolution=resolution,
                snapshot=snapshot,
                coverage=coverage,
                coverage_key=coverage_key,
                triangles=None if coverage is not None else triangles,
            )
        )

    def _record_face(
        self, deferred: _DeferredFace, classified: ClassificationResult
    ) -> None:
        prepared = deferred.prepared
        polygon_index = deferred.polygon_index
        material = deferred.material
        pointer = material.as_pointer()
        snapshot = deferred.snapshot
        face = FaceAnalysis(polygon_index, deferred.slot_index, pointer, classified)
        prepared.result.faces[polygon_index] = face
        group = prepared.result.groups.get(pointer)
        if group is None:
            group = MaterialGroupAnalysis(
                material=material,
                resolution=deferred.resolution,
                image_digest=snapshot.digest,
                source_fingerprint=source_fingerprint(material, snapshot.digest),
            )
            prepared.result.groups[pointer] = group
        group.face_indices[classified.classification].append(polygon_index)
        group.affected_texels += classified.affected_texels
        group.covered_texels += classified.covered_texels
        self.counts[classified.classification] += 1

    def _rasterize_pending(self) -> None:
        """Rasterize this chunk's coverage-cache misses in batched sub-chunks.

        Deduplicated by cache key first: two polygons with identical UV
        triangles used to share one coverage through the cache, and batching
        them would otherwise rasterize both.
        """
        misses: dict[str, list[_DeferredFace]] = {}
        duplicates = 0
        for deferred in self._pending:
            if deferred.triangles is None:
                continue
            group = misses.setdefault(deferred.coverage_key, [])
            duplicates += bool(group)
            group.append(deferred)
        # Both copies of an in-chunk duplicate miss the cache, because they are
        # looked up before either is stored. Counting the second as a hit keeps
        # the reuse metric measuring reuse rather than lookup ordering.
        self.metrics["coverage_cache_hits"] += duplicates
        self.metrics["coverage_cache_misses"] -= duplicates
        if not misses:
            return
        settings = self.config.settings
        keys = list(misses)
        for begin in range(0, len(keys), _RASTER_BATCH_POLYGONS):
            window = keys[begin : begin + _RASTER_BATCH_POLYGONS]
            started = time.perf_counter()
            batches = [misses[key][0].triangles for key in window]
            results = rasterize_batch(
                numpy.concatenate(batches),
                numpy.fromiter(
                    (len(batch) for batch in batches),
                    dtype=numpy.int64,
                    count=len(batches),
                ),
                margin_texels=settings.margin_texels,
                max_scanlines=settings.max_scanlines,
                max_run_emissions=settings.max_run_emissions,
            )
            stored_started = time.perf_counter()
            self.metrics["phase_raster_seconds"] += stored_started - started
            for key, result in zip(window, results):
                if isinstance(result, str):
                    unsupported = ClassificationResult(
                        classification=FaceClass.UNSUPPORTED,
                        covered_texels=0,
                        affected_texels=0,
                        opaque_texels=0,
                        affected_fraction=0.0,
                        unsupported_reason=result,
                    )
                    for deferred in misses[key]:
                        deferred.classified = unsupported
                    continue
                runtime.coverage_set(key, result)
                for deferred in misses[key]:
                    deferred.coverage = result
            self.metrics["phase_cache_store_seconds"] += (
                time.perf_counter() - stored_started
            )

    def _unsupported_face(self, reason: str) -> ClassificationResult:
        return ClassificationResult(
            classification=FaceClass.UNSUPPORTED,
            covered_texels=0,
            affected_texels=0,
            opaque_texels=0,
            affected_fraction=0.0,
            unsupported_reason=reason,
        )

    def _submit_pending(self) -> _InFlight | None:
        """Queue every dispatch this chunk needs, without reading any of them.

        Grouped by image and address mode exactly as the CPU counting pass is,
        because one dispatch shares one alpha mask. `None` means the kernel
        declined a batch and the caller must run the CPU path instead.
        """
        settings = self.config.settings
        started = time.perf_counter()
        groups: dict[tuple[int, AddressMode], list[int]] = defaultdict(list)
        for position, deferred in enumerate(self._pending):
            key = (id(deferred.snapshot.grid), deferred.resolution.address_mode)
            groups[key].append(position)

        # One dispatch per group, not one per `_RASTER_BATCH_POLYGONS`. That
        # window keeps the CPU rasterizer's intermediates in cache; the kernel
        # has no such working set, and each extra dispatch is another fixed cost
        # for the same work.
        batches: list[tuple[list[int], Any, Any]] = []
        for window in groups.values():
            first = self._pending[window[0]]
            triangles = [self._pending[position].triangles for position in window]
            counts, pending = gpu_raster.submit_batch(
                numpy.concatenate(triangles),
                numpy.fromiter(
                    (len(one) for one in triangles),
                    dtype=numpy.int64,
                    count=len(triangles),
                ),
                first.snapshot.grid,
                first.resolution.address_mode,
                settings=settings,
                high_precision=self.config.high_precision,
            )
            if counts is None:
                # Nothing is recorded yet, so abandoning the batches already
                # submitted only wastes their work. Their textures go with the
                # discarded handles.
                self.metrics["phase_raster_seconds"] += time.perf_counter() - started
                return None
            batches.append((window, counts, pending))
        self.metrics["phase_raster_seconds"] += time.perf_counter() - started
        return _InFlight(faces=self._pending, batches=batches)

    def _collect_inflight(self, inflight: _InFlight) -> None:
        """Read a submitted chunk, classify it, and record its faces."""
        settings = self.config.settings
        started = time.perf_counter()
        collected = [
            (window, gpu_raster.collect_batch(counts, pending))
            for window, counts, pending in inflight.batches
        ]
        classify_started = time.perf_counter()
        self.metrics["phase_raster_seconds"] += classify_started - started

        faces = inflight.faces
        classifications: list[ClassificationResult | None] = [None] * len(faces)
        for window, produced in collected:
            for offset, position in enumerate(window):
                reason = produced.reasons.get(offset)
                classifications[position] = (
                    self._unsupported_face(reason)
                    if reason is not None
                    else classify_stats(
                        RasterStats(
                            triangles=int(produced.triangles[offset]),
                            degenerate_triangles=int(
                                produced.degenerate_triangles[offset]
                            ),
                            scanlines=int(produced.scanlines[offset]),
                            emitted_runs=int(produced.emitted_runs[offset]),
                            union_runs=int(produced.union_runs[offset]),
                            covered_texels=int(produced.covered_texels[offset]),
                        ),
                        int(produced.affected[offset]),
                        settings=settings,
                    )
                )
        self.metrics["phase_classify_seconds"] += time.perf_counter() - classify_started
        self._record_pending(faces, classifications)

    def _drain_inflight(self) -> None:
        """Finish any submitted chunk. Safe to call when there is none."""
        if self._inflight is not None:
            inflight, self._inflight = self._inflight, None
            self._collect_inflight(inflight)

    def _flush_pending(self, *, final: bool = False) -> None:
        """Rasterize, count and classify every polygon deferred this chunk.

        Counting is grouped by image and address mode because a batch shares one
        prefix gather. Results are recorded in the original polygon order so
        neither grouping reorders the report.

        The GPU path holds its polygons back until there are enough to be worth
        a dispatch, so most calls do nothing at all. `final` overrides that and
        is how the last, short chunk gets submitted.
        """
        if not self._pending:
            return
        if self._gpu:
            if not final and len(self._pending) < _GPU_SUBMIT_POLYGONS:
                return
            submitted = self._submit_pending()
            if submitted is not None:
                # The previous chunk is read only now, with this one's
                # dispatches already queued behind it, so the wait for it has
                # been running under this chunk's UV traversal. Faces are
                # recorded one chunk later than they are deferred.
                self._drain_inflight()
                self._inflight = submitted
                self._pending = []
                return
            # A declined batch is not a failure, only a slower route. Turning
            # the path off for the rest of the run keeps one analysis on one
            # implementation rather than alternating between two. These faces
            # were never looked up, so they are misses the CPU path is about to
            # rasterize; without the key it dedups them all into one.
            # Whatever is in flight was submitted before the decline and is
            # still owed a recording, and draining it here also keeps chunks in
            # the order they were deferred.
            self._drain_inflight()
            self._gpu = False
            self.metrics["coverage_cache_misses"] += len(self._pending)
            for deferred in self._pending:
                deferred.coverage_key = _coverage_key(
                    deferred.snapshot, deferred.triangles, self.config.settings
                )
        self._rasterize_pending()
        started = time.perf_counter()
        groups: dict[tuple[int, AddressMode], list[int]] = defaultdict(list)
        for position, deferred in enumerate(self._pending):
            if deferred.classified is not None:
                continue
            key = (id(deferred.snapshot.grid), deferred.resolution.address_mode)
            groups[key].append(position)
        affected = [0] * len(self._pending)
        for positions in groups.values():
            first = self._pending[positions[0]]
            counts = first.snapshot.grid.count_batch(
                [self._pending[position].coverage for position in positions],
                first.resolution.address_mode,
            )
            for position, count in zip(positions, counts):
                affected[position] = count
        classifications = [
            deferred.classified
            if deferred.classified is not None
            else classify_counted(
                deferred.coverage, count, settings=self.config.settings
            )
            for deferred, count in zip(self._pending, affected)
        ]
        self.metrics["phase_classify_seconds"] += time.perf_counter() - started
        faces, self._pending = self._pending, []
        self._record_pending(faces, classifications)

    def _record_pending(
        self,
        faces: list[_DeferredFace],
        classifications: list[ClassificationResult],
    ) -> None:
        """Record one chunk's faces and its raster counters."""
        # The six raster counters are summed into locals and added to `metrics`
        # once per chunk. Adding them per face cost more than the whole of the
        # rest of `_record_face`: a fresh dict literal and a `Counter.update`
        # 150,544 times over.
        rasterized = False
        triangles = degenerate = scanlines = emitted = union = covered = 0
        for deferred, classified in zip(faces, classifications):
            self._record_face(deferred, classified)
            stats = classified.raster_stats
            if stats is not None:
                rasterized = True
                triangles += stats.triangles
                degenerate += stats.degenerate_triangles
                scanlines += stats.scanlines
                emitted += stats.emitted_runs
                union += stats.union_runs
                covered += stats.covered_texels
        if not rasterized:
            # A chunk in which nothing rasterized left these keys absent before,
            # and `report.metrics` is the whole counter, so creating them at zero
            # would change the report rather than only its timing.
            return
        metrics = self.metrics
        metrics["triangles"] += triangles
        metrics["degenerate_triangles"] += degenerate
        metrics["scanlines"] += scanlines
        metrics["emitted_runs"] += emitted
        metrics["union_runs"] += union
        metrics["covered_texels"] += covered

    def step(
        self,
        polygon_budget: int = 128,
        *,
        time_budget_seconds: float | None = None,
        clock=None,
    ) -> bool:
        if self.cancelled:
            return True
        if time_budget_seconds is not None:
            clock = clock or time.perf_counter
            deadline = clock() + time_budget_seconds
        else:
            deadline = None
        if self._deferred_images:
            if self._image_builder_index < len(self._image_builders):
                # Vectorized chunks are far shorter than one timer interval, so
                # spend the same budget here instead of one chunk per callback.
                while self._image_builder_index < len(self._image_builders):
                    builder = self._image_builders[self._image_builder_index]
                    rows = builder.step()
                    self.completed += rows
                    self.metrics["image_digest_rows"] += rows
                    if builder.complete:
                        snapshot = builder.finish()
                        key = (
                            snapshot.image.as_pointer(),
                            snapshot.channel,
                            self.config.settings.alpha_threshold,
                        )
                        self.image_cache[key] = snapshot
                        self.metrics["full_image_digests"] += 1
                        self._image_builder_index += 1
                    if deadline is None or clock() >= deadline:
                        break
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
                if deadline is not None and clock() >= deadline:
                    self._flush_pending()
                    return False
            if self._polygon_index >= len(polygons):
                self._polygon_index = 0
                self._prepared_index += 1
        if self._prepared_index < len(self.prepared):
            self._flush_pending()
            return False
        # Nothing will call back again, so the held polygons have to be
        # submitted and the chunk still in flight has to be read, or neither
        # reaches the report.
        self._flush_pending(final=True)
        self._drain_inflight()
        return True

    def finish(self) -> AnalysisReport:
        if (
            self.cancelled
            or self._deferred_images
            or self._prepared_index < len(self.prepared)
            # A report built over a chunk still on the GPU would be short those
            # faces and look complete. `step` drains when it returns True, so
            # this only fires for a caller that skipped that.
            or self._inflight is not None
        ):
            raise RuntimeError("analysis is incomplete")
        for name, total in _phase_totals().items():
            self.metrics[name] += total - self._phase_baseline.get(name, 0.0)
        analysis_id = hashlib.blake2b(
            (self.signature + json.dumps(self.config.payload(), sort_keys=True)).encode(),
            digest_size=16,
        ).hexdigest()
        return AnalysisReport(
            analysis_id=analysis_id,
            input_signature=self.signature,
            structural_signature=self.structural_signature,
            assignment_signature=self.assignment_signature,
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
