# SPDX-License-Identifier: GPL-3.0-or-later
"""Preflighted, derived-only, idempotent material-slot assignment."""

from __future__ import annotations

from dataclasses import dataclass, field

import bpy

from ..core import FaceClass
from .analysis import AnalysisReport
from .material_metadata import (
    DerivedDecision,
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
class AssignmentPlan:
    decisions: dict[int, DerivedDecision] = field(default_factory=dict)
    sources: dict[int, bpy.types.Material] = field(default_factory=dict)
    source_fingerprints: dict[int, str] = field(default_factory=dict)
    mutations: list[ObjectMutation] = field(default_factory=list)
    blocked: list[dict[str, str]] = field(default_factory=list)
    already_derived: int = 0
    planned_slots: int = 0

    def public_payload(self) -> dict:
        return {
            "already_derived_groups": self.already_derived,
            "blocked": list(self.blocked),
            "faces_to_reassign": sum(len(item.face_indices) for item in self.mutations),
            "planned_additional_slots": self.planned_slots,
            "source_decisions": {
                source.name: self.decisions[pointer].action
                for pointer, source in self.sources.items()
                if pointer in self.decisions
            },
        }


def _block(plan: AssignmentPlan, material, reason: str) -> None:
    plan.blocked.append({"material": material.name, "reason": reason})


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
            state = inspect_metadata(group.material)
            if state.kind == "DERIVED":
                source = state.source
                source_pointer = source.as_pointer()
                fingerprint = current_fingerprints.get(source_pointer)
                if not fingerprint:
                    _block(plan, group.material, "SOURCE_NOT_IN_ANALYZED_SLOTS")
                    continue
                required_sources.add(source_pointer)
                plan.sources[source_pointer] = source
                plan.source_fingerprints[source_pointer] = fingerprint
                plan.already_derived += 1
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
                _block(plan, group.material, state.reason or "METADATA_CONFLICT")
                continue

            if group.counts[FaceClass.UNSUPPORTED] and unsupported_policy == "CANCEL_SOURCE_MATERIAL":
                _block(plan, group.material, "UNSUPPORTED_FACES")
                continue
            if group.counts[FaceClass.SUPPRESSED] and suppressed_policy == "CANCEL_SOURCE_MATERIAL":
                _block(plan, group.material, "SUPPRESSED_FACES")
                continue
            if group.counts[FaceClass.MIXED] and mixed_policy == "CANCEL_SOURCE_MATERIAL":
                _block(plan, group.material, "MIXED_FACES")
                continue

            face_indices = list(group.face_indices[FaceClass.ALPHA_AFFECTED])
            if mixed_policy == "TO_ALPHA":
                face_indices.extend(group.face_indices[FaceClass.MIXED])
            if suppressed_policy == "TO_ALPHA":
                face_indices.extend(group.face_indices[FaceClass.SUPPRESSED])
            if not face_indices:
                continue
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


def execute_assignment_plan(plan: AssignmentPlan) -> dict:
    created: dict[int, bpy.types.Material] = {}
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
    }
