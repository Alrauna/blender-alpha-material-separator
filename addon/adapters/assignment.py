# SPDX-License-Identifier: GPL-3.0-or-later
"""Preflighted, derived-only, idempotent material-slot assignment."""

from __future__ import annotations

from dataclasses import dataclass, field

import bpy

from ..core import FaceClass
from ..unsupported import (
    UNSUPPORTED_SCOPE_FACE_LOCAL,
    UNSUPPORTED_SCOPE_MATERIAL_SOURCE,
    unsupported_scope,
)
from .analysis import AnalysisReport, MaterialGroupAnalysis, ObjectAnalysis
from .material_metadata import (
    DerivedDecision,
    SOURCE_NAME,
    create_derived_material,
    inspect_metadata,
    refresh_diagnostic_name,
    resolve_derived_material,
)


@dataclass(slots=True)
class ObjectMutation:
    object: bpy.types.Object
    source: bpy.types.Material
    face_indices: tuple[int, ...]


@dataclass(slots=True)
class GroupDisposition:
    object_name: str
    material_name: str
    material_pointer: int
    action: str
    reason: str
    total_faces: int
    faces_to_alpha: int = 0
    faces_left_source: int = 0
    face_local_unsupported: int = 0
    material_source_unsupported: int = 0
    uncertain_to_alpha: int = 0

    def public_payload(self) -> dict[str, object]:
        return {
            "action": self.action,
            "face_local_unsupported": self.face_local_unsupported,
            "faces_left_source": self.faces_left_source,
            "faces_to_alpha": self.faces_to_alpha,
            "material": self.material_name,
            "material_source_unsupported": self.material_source_unsupported,
            "object": self.object_name,
            "reason": self.reason,
            "total_faces": self.total_faces,
            "uncertain_to_alpha": self.uncertain_to_alpha,
        }


@dataclass(slots=True)
class AssignmentPlan:
    decisions: dict[int, DerivedDecision] = field(default_factory=dict)
    sources: dict[int, bpy.types.Material] = field(default_factory=dict)
    source_fingerprints: dict[int, str] = field(default_factory=dict)
    mutations: list[ObjectMutation] = field(default_factory=list)
    blocked: list[dict[str, str]] = field(default_factory=list)
    dispositions: list[GroupDisposition] = field(default_factory=list)
    already_derived: int = 0
    planned_slots: int = 0

    @property
    def actionable(self) -> bool:
        return bool(self.mutations)

    @property
    def skipped_group_count(self) -> int:
        skip_actions = {
            "LEAVE_UNCHANGED_NO_ALPHA_SOURCE",
            "PARTIAL_MOVE_KEEP_UNCERTAIN",
            "SKIP_GROUP",
        }
        return sum(item.action in skip_actions for item in self.dispositions)

    @property
    def has_skips(self) -> bool:
        return bool(self.blocked) or self.skipped_group_count > 0

    def public_payload(self) -> dict:
        return {
            "already_derived_groups": self.already_derived,
            "blocked": list(self.blocked),
            "dispositions": [item.public_payload() for item in self.dispositions],
            "faces_to_reassign": sum(len(item.face_indices) for item in self.mutations),
            "face_local_unsupported_to_alpha": sum(
                item.uncertain_to_alpha for item in self.dispositions
            ),
            "material_source_groups_left_unchanged": sum(
                item.action == "LEAVE_UNCHANGED_NO_ALPHA_SOURCE"
                for item in self.dispositions
            ),
            "planned_additional_slots": self.planned_slots,
            "skipped_material_groups": self.skipped_group_count,
            "destinations": {
                source.name: (
                    self.decisions[pointer].material.name
                    if self.decisions[pointer].material is not None
                    else f"{source.name}__AMS_ALPHA"
                )
                for pointer, source in self.sources.items()
                if pointer in self.decisions
                and self.decisions[pointer].action in {"CREATE", "REUSE"}
            },
            "source_decisions": {
                source.name: self.decisions[pointer].action
                for pointer, source in self.sources.items()
                if pointer in self.decisions
            },
        }


def _block(plan: AssignmentPlan, material, reason: str, *, object_name: str = "") -> None:
    blocked = {"material": material.name, "reason": reason}
    if object_name:
        blocked["object"] = object_name
    plan.blocked.append(blocked)


def _unsupported_indices(
    object_result: ObjectAnalysis,
    group: MaterialGroupAnalysis,
) -> dict[str, list[int]]:
    by_scope = {
        UNSUPPORTED_SCOPE_FACE_LOCAL: [],
        UNSUPPORTED_SCOPE_MATERIAL_SOURCE: [],
    }
    for face_index in group.face_indices[FaceClass.UNSUPPORTED]:
        face = object_result.faces.get(face_index)
        reason = face.result.unsupported_reason if face is not None else None
        scope = unsupported_scope(
            reason,
            material_supported=group.resolution.supported,
        )
        by_scope[scope].append(face_index)
    return by_scope


def preview_face_indices(plan: AssignmentPlan) -> dict[int, frozenset[int]]:
    """Return the exact per-object polygon set that execution would reassign."""

    targets: dict[int, set[int]] = {}
    for mutation in plan.mutations:
        targets.setdefault(mutation.object.as_pointer(), set()).update(
            mutation.face_indices
        )
    return {pointer: frozenset(indices) for pointer, indices in targets.items()}


def build_assignment_plan(
    report: AnalysisReport,
    *,
    mixed_policy: str,
    suppressed_policy: str,
    unsupported_policy: str,
    conflict_policy: str,
) -> AssignmentPlan:
    plan = AssignmentPlan()
    current_fingerprints: dict[int, str] = {}

    for object_result in report.object_results.values():
        if object_result.skipped_reason:
            continue
        for pointer, group in object_result.groups.items():
            state = inspect_metadata(group.material)
            if state.kind == "SOURCE":
                current_fingerprints[pointer] = group.source_fingerprint

    required_sources: set[int] = set()
    pending: list[tuple[object, bpy.types.Material, tuple[int, ...]]] = []
    pending_derived: list[
        tuple[bpy.types.Object, bpy.types.Material, bpy.types.Material, tuple[int, ...]]
    ] = []
    for object_result in report.object_results.values():
        if object_result.skipped_reason:
            continue
        for group in object_result.groups.values():
            object_name = object_result.object.name
            total_faces = sum(int(group.counts[face_class]) for face_class in FaceClass)
            state = inspect_metadata(group.material)
            if state.kind == "DERIVED":
                source = state.source
                source_pointer = source.as_pointer()
                fingerprint = current_fingerprints.get(source_pointer)
                if not fingerprint:
                    _block(
                        plan,
                        group.material,
                        "SOURCE_NOT_IN_ANALYZED_SLOTS",
                        object_name=object_name,
                    )
                    plan.dispositions.append(
                        GroupDisposition(
                            object_name,
                            group.material.name,
                            group.material.as_pointer(),
                            "SKIP_GROUP",
                            "SOURCE_NOT_IN_ANALYZED_SLOTS",
                            total_faces,
                            faces_left_source=total_faces,
                        )
                    )
                    continue
                required_sources.add(source_pointer)
                plan.sources[source_pointer] = source
                plan.source_fingerprints[source_pointer] = fingerprint
                plan.already_derived += 1
                plan.dispositions.append(
                    GroupDisposition(
                        object_name,
                        group.material.name,
                        group.material.as_pointer(),
                        "ALREADY_SEPARATED",
                        "ALREADY_SEPARATED",
                        total_faces,
                        faces_left_source=total_faces,
                    )
                )
                derived_faces = tuple(
                    sorted(
                        face_index
                        for face_indices in group.face_indices.values()
                        for face_index in face_indices
                    )
                )
                if derived_faces:
                    pending_derived.append(
                        (object_result.object, source, group.material, derived_faces)
                    )
                continue
            if state.kind != "SOURCE":
                reason = state.reason or "METADATA_CONFLICT"
                _block(plan, group.material, reason, object_name=object_name)
                plan.dispositions.append(
                    GroupDisposition(
                        object_name,
                        group.material.name,
                        group.material.as_pointer(),
                        "SKIP_GROUP",
                        reason,
                        total_faces,
                        faces_left_source=total_faces,
                    )
                )
                continue

            unsupported = _unsupported_indices(object_result, group)
            face_local_unsupported = unsupported[UNSUPPORTED_SCOPE_FACE_LOCAL]
            material_source_unsupported = unsupported[
                UNSUPPORTED_SCOPE_MATERIAL_SOURCE
            ]

            if face_local_unsupported and unsupported_policy == "CANCEL_SOURCE_MATERIAL":
                _block(
                    plan,
                    group.material,
                    "FACE_LOCAL_UNSUPPORTED_FACES",
                    object_name=object_name,
                )
                plan.dispositions.append(
                    GroupDisposition(
                        object_name,
                        group.material.name,
                        group.material.as_pointer(),
                        "SKIP_GROUP",
                        "FACE_LOCAL_UNSUPPORTED_FACES",
                        total_faces,
                        faces_left_source=total_faces,
                        face_local_unsupported=len(face_local_unsupported),
                        material_source_unsupported=len(material_source_unsupported),
                    )
                )
                continue
            if group.counts[FaceClass.SUPPRESSED] and suppressed_policy == "CANCEL_SOURCE_MATERIAL":
                _block(plan, group.material, "SUPPRESSED_FACES", object_name=object_name)
                plan.dispositions.append(
                    GroupDisposition(
                        object_name,
                        group.material.name,
                        group.material.as_pointer(),
                        "SKIP_GROUP",
                        "SUPPRESSED_FACES",
                        total_faces,
                        faces_left_source=total_faces,
                        face_local_unsupported=len(face_local_unsupported),
                        material_source_unsupported=len(material_source_unsupported),
                    )
                )
                continue
            if group.counts[FaceClass.MIXED] and mixed_policy == "CANCEL_SOURCE_MATERIAL":
                _block(plan, group.material, "MIXED_FACES", object_name=object_name)
                plan.dispositions.append(
                    GroupDisposition(
                        object_name,
                        group.material.name,
                        group.material.as_pointer(),
                        "SKIP_GROUP",
                        "MIXED_FACES",
                        total_faces,
                        faces_left_source=total_faces,
                        face_local_unsupported=len(face_local_unsupported),
                        material_source_unsupported=len(material_source_unsupported),
                    )
                )
                continue

            face_indices = list(group.face_indices[FaceClass.ALPHA_AFFECTED])
            if mixed_policy == "TO_ALPHA":
                face_indices.extend(group.face_indices[FaceClass.MIXED])
            if suppressed_policy == "TO_ALPHA":
                face_indices.extend(group.face_indices[FaceClass.SUPPRESSED])
            if unsupported_policy == "TO_ALPHA":
                face_indices.extend(face_local_unsupported)
            if not face_indices:
                if material_source_unsupported:
                    action = "LEAVE_UNCHANGED_NO_ALPHA_SOURCE"
                    reason = group.resolution.reason or "MATERIAL_ALPHA_SOURCE_UNRESOLVED"
                elif face_local_unsupported:
                    action = "PARTIAL_MOVE_KEEP_UNCERTAIN"
                    reason = "FACE_LOCAL_UNSUPPORTED_KEPT_SOURCE"
                else:
                    action = "NO_CHANGES_NEEDED"
                    reason = "NO_ALPHA_FACES"
                plan.dispositions.append(
                    GroupDisposition(
                        object_name,
                        group.material.name,
                        group.material.as_pointer(),
                        action,
                        reason,
                        total_faces,
                        faces_left_source=total_faces,
                        face_local_unsupported=len(face_local_unsupported),
                        material_source_unsupported=len(material_source_unsupported),
                    )
                )
                continue
            if face_local_unsupported and unsupported_policy == "TO_ALPHA":
                action = "MOVE_UNCERTAIN_TO_ALPHA"
                reason = "FACE_LOCAL_UNSUPPORTED_TO_ALPHA"
                uncertain_to_alpha = len(face_local_unsupported)
            elif face_local_unsupported:
                action = "PARTIAL_MOVE_KEEP_UNCERTAIN"
                reason = "FACE_LOCAL_UNSUPPORTED_KEPT_SOURCE"
                uncertain_to_alpha = 0
            else:
                action = "MOVE_TO_ALPHA"
                reason = "CLASSIFIED_ALPHA_FACES"
                uncertain_to_alpha = 0
            faces_left_source = total_faces - len(set(face_indices))
            plan.dispositions.append(
                GroupDisposition(
                    object_name,
                    group.material.name,
                    group.material.as_pointer(),
                    action,
                    reason,
                    total_faces,
                    faces_to_alpha=len(set(face_indices)),
                    faces_left_source=faces_left_source,
                    face_local_unsupported=len(face_local_unsupported),
                    material_source_unsupported=len(material_source_unsupported),
                    uncertain_to_alpha=uncertain_to_alpha,
                )
            )
            source_pointer = group.material.as_pointer()
            required_sources.add(source_pointer)
            plan.sources[source_pointer] = group.material
            plan.source_fingerprints[source_pointer] = group.source_fingerprint
            pending.append((object_result.object, group.material, tuple(sorted(face_indices))))

    for source_pointer in sorted(required_sources):
        source = plan.sources[source_pointer]
        decision = resolve_derived_material(
            source,
            plan.source_fingerprints[source_pointer],
            conflict_policy=conflict_policy,
        )
        plan.decisions[source_pointer] = decision
        if decision.action == "BLOCK":
            _block(plan, source, decision.reason)
            for disposition in plan.dispositions:
                if disposition.material_pointer != source_pointer:
                    continue
                if disposition.action in {
                    "MOVE_TO_ALPHA",
                    "MOVE_UNCERTAIN_TO_ALPHA",
                    "PARTIAL_MOVE_KEEP_UNCERTAIN",
                }:
                    disposition.action = "SKIP_GROUP"
                    disposition.reason = decision.reason
                    disposition.faces_to_alpha = 0
                    disposition.uncertain_to_alpha = 0
                    disposition.faces_left_source = disposition.total_faces

    blocked_sources = {
        pointer
        for pointer, decision in plan.decisions.items()
        if decision.action == "BLOCK"
    }
    for object_, source, face_indices in pending:
        if source.as_pointer() in blocked_sources:
            continue
        plan.mutations.append(ObjectMutation(object_, source, face_indices))
    for object_, source, current_derived, face_indices in pending_derived:
        decision = plan.decisions.get(source.as_pointer())
        if decision is None or decision.action == "BLOCK":
            continue
        if decision.action == "CREATE" or decision.material != current_derived:
            plan.mutations.append(ObjectMutation(object_, source, face_indices))

    planned_slot_pairs = set()
    for mutation in plan.mutations:
        decision = plan.decisions[mutation.source.as_pointer()]
        derived = decision.material
        if derived is None or all(
            slot.material != derived for slot in mutation.object.material_slots
        ):
            planned_slot_pairs.add(
                (mutation.object.as_pointer(), mutation.source.as_pointer())
            )
    plan.planned_slots = len(planned_slot_pairs)
    return plan


def _execute_assignment_plan_inner(
    plan: AssignmentPlan,
    created: dict[int, bpy.types.Material],
) -> dict:
    for pointer, decision in plan.decisions.items():
        source = plan.sources[pointer]
        if decision.action == "CREATE":
            created[pointer] = create_derived_material(
                source,
                plan.source_fingerprints[pointer],
                source_uuid_ref=decision.source_uuid_ref,
            )
        elif decision.action == "REUSE":
            created[pointer] = decision.material
        if pointer in created:
            refresh_diagnostic_name(created[pointer], source)

    changed_faces = 0
    added_slots = 0
    for mutation in plan.mutations:
        derived = created[mutation.source.as_pointer()]
        slot_index = next(
            (
                index
                for index, slot in enumerate(mutation.object.material_slots)
                if slot.material == derived
            ),
            -1,
        )
        if slot_index < 0:
            mutation.object.data.materials.append(derived)
            slot_index = len(mutation.object.material_slots) - 1
            added_slots += 1
        for polygon_index in mutation.face_indices:
            polygon = mutation.object.data.polygons[polygon_index]
            if polygon.material_index != slot_index:
                polygon.material_index = slot_index
                changed_faces += 1
        mutation.object.data.update()
    return {
        "added_material_slots": added_slots,
        "changed_faces": changed_faces,
        "created_materials": sum(
            decision.action == "CREATE" for decision in plan.decisions.values()
        ),
        "reused_materials": sum(
            decision.action == "REUSE" for decision in plan.decisions.values()
        ),
        "materials": [
            {
                "action": plan.decisions[pointer].action,
                "derived": material.name,
                "source": plan.sources[pointer].name,
            }
            for pointer, material in sorted(
                created.items(), key=lambda item: plan.sources[item[0]].name
            )
        ],
        "blocked_material_groups": len(plan.blocked),
        "skipped_material_groups": plan.skipped_group_count,
        "unchanged_material_groups": sum(
            item.action == "LEAVE_UNCHANGED_NO_ALPHA_SOURCE"
            for item in plan.dispositions
        ),
    }


def execute_assignment_plan(plan: AssignmentPlan) -> dict:
    """Execute atomically and restore the reviewed state after an unexpected error."""

    object_snapshots: dict[int, tuple[bpy.types.Object, int, dict[int, int]]] = {}
    for mutation in plan.mutations:
        pointer = mutation.object.as_pointer()
        snapshot = object_snapshots.get(pointer)
        if snapshot is None:
            snapshot = (mutation.object, len(mutation.object.data.materials), {})
            object_snapshots[pointer] = snapshot
        face_states = snapshot[2]
        for polygon_index in mutation.face_indices:
            face_states.setdefault(
                polygon_index,
                mutation.object.data.polygons[polygon_index].material_index,
            )

    created: dict[int, bpy.types.Material] = {}
    reused_name_metadata: list[tuple[bpy.types.Material, bool, object]] = []
    for decision in plan.decisions.values():
        if decision.action != "REUSE" or decision.material is None:
            continue
        material = decision.material
        reused_name_metadata.append(
            (material, SOURCE_NAME in material, material.get(SOURCE_NAME))
        )
    try:
        return _execute_assignment_plan_inner(plan, created)
    except Exception:
        for object_, original_slot_count, face_states in object_snapshots.values():
            try:
                for polygon_index, material_index in face_states.items():
                    object_.data.polygons[polygon_index].material_index = material_index
                while len(object_.data.materials) > original_slot_count:
                    object_.data.materials.pop(index=len(object_.data.materials) - 1)
                object_.data.update()
            except (ReferenceError, RuntimeError, IndexError):
                pass
        for material, existed, value in reused_name_metadata:
            try:
                if existed:
                    material[SOURCE_NAME] = value
                elif SOURCE_NAME in material:
                    del material[SOURCE_NAME]
            except (ReferenceError, RuntimeError):
                pass
        for pointer, material in tuple(created.items()):
            decision = plan.decisions.get(pointer)
            if decision is None or decision.action != "CREATE":
                continue
            try:
                if material.users == 0 and bpy.data.materials.get(material.name) == material:
                    bpy.data.materials.remove(material)
            except (ReferenceError, RuntimeError):
                pass
        raise
