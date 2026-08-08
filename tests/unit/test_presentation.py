# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import unittest

from addon.presentation import (
    CLASS_COPY,
    KNOWN_GUIDANCE_CODES,
    alpha_source_advisory,
    already_separated_tooltip,
    assignment_confirmation_lines,
    classes_to_move,
    guidance_for,
    requires_confirmation,
    review_material_cards,
    review_signature,
    ui_text_lines,
    workflow_view,
)


class PresentationTests(unittest.TestCase):
    def test_width_aware_ui_text_keeps_and_wraps_sentences(self) -> None:
        sentence = "Open Material Details below to review it."

        wide = ui_text_lines(sentence, 560)
        ordinary = ui_text_lines(sentence, 420)
        narrow = ui_text_lines(sentence, 180)

        self.assertEqual(wide, (sentence,))
        self.assertEqual(ordinary, (sentence,))
        self.assertGreater(len(narrow), 1)
        self.assertEqual(" ".join(narrow), sentence)
        self.assertGreaterEqual(len(narrow), len(ordinary))
        self.assertGreaterEqual(len(ordinary), len(wide))
        self.assertEqual(ui_text_lines("", 180), ("",))

        long_word = "AlphaMaterialSeparatorIdentifier"
        self.assertEqual(ui_text_lines(long_word, 80), (long_word,))

    def test_compact_assignment_confirmation_representative_copy(self) -> None:
        plan = {
            "faces_to_reassign": 65_775,
            "planned_additional_slots": 29,
            "mixed_faces_to_alpha": 57_731,
            "face_local_unsupported_to_alpha": 2_577,
            "suppressed_faces_to_alpha": 0,
            "retained_faces_by_policy": 0,
            "material_source_groups_left_unchanged": 23,
            "skipped_material_groups": 0,
            "skipped_object_count": 0,
        }
        lines = assignment_confirmation_lines(plan)
        self.assertEqual(
            lines,
            (
                (
                    "Move 65,775 reviewed faces to alpha materials and add "
                    "29 material slots."
                ),
                "This includes 57,731 mixed faces and 2,577 uncertain faces.",
                "23 unresolved material groups will remain unchanged.",
                (
                    "Only material slots and face assignments change—no topology "
                    "or source shader changes. Ctrl+Z to undo."
                ),
            ),
        )
        self.assertEqual(
            assignment_confirmation_lines(plan, previewed=False),
            ("Faces have not been previewed.", *lines),
        )
        self.assertEqual(
            assignment_confirmation_lines(plan, previewed=True),
            lines,
        )

    def test_compact_assignment_confirmation_adapts_and_omits_names(self) -> None:
        plan = {
            "faces_to_reassign": 1,
            "planned_additional_slots": 0,
            "mixed_faces_to_alpha": 1,
            "face_local_unsupported_to_alpha": 0,
            "suppressed_faces_to_alpha": 1,
            "retained_faces_by_policy": 1,
            "material_source_groups_left_unchanged": 1,
            "skipped_material_groups": 1,
            "skipped_object_count": 1,
            "destinations": {"PRIVATE_SOURCE": "PRIVATE_DESTINATION"},
            "dispositions": [
                {"object": "PRIVATE_OBJECT", "material": "PRIVATE_MATERIAL"}
            ],
        }
        lines = assignment_confirmation_lines(plan)
        self.assertEqual(
            lines,
            (
                "Move 1 reviewed face to an alpha material.",
                "This includes 1 mixed face.",
                "Move 1 below-significance face to alpha.",
                "1 reviewed face will remain on its source material by policy.",
                "1 unresolved material group will remain unchanged.",
                "Skip 1 material group and 1 object.",
                (
                    "Only material slots and face assignments change—no topology "
                    "or source shader changes. Ctrl+Z to undo."
                ),
            ),
        )
        joined = "\n".join(lines)
        for private_name in (
            "PRIVATE_SOURCE",
            "PRIVATE_DESTINATION",
            "PRIVATE_OBJECT",
            "PRIVATE_MATERIAL",
        ):
            self.assertNotIn(private_name, joined)
        self.assertLessEqual(len(lines), 7)

    def test_compact_assignment_confirmation_omits_zero_clauses(self) -> None:
        lines = assignment_confirmation_lines(
            {
                "faces_to_reassign": 2,
                "planned_additional_slots": 0,
                "mixed_faces_to_alpha": 0,
                "face_local_unsupported_to_alpha": 0,
                "suppressed_faces_to_alpha": 0,
                "retained_faces_by_policy": 0,
                "material_source_groups_left_unchanged": 0,
                "skipped_material_groups": 0,
                "skipped_object_count": 0,
            }
        )
        self.assertEqual(len(lines), 2)
        self.assertNotIn("0", "\n".join(lines))

    def test_material_cards_are_deduplicated_by_displayed_result(self) -> None:
        supported = {
            "material": "Body",
            "supported": True,
            "resolution": "OK",
            "image": "Body.png",
            "uv_map": "UVMap",
            "channel": "ALPHA",
            "address_mode": "REPEAT",
            "source_method": "UNIQUE_BASE_COLOR_IMAGE_ALPHA",
            "alpha_material": "Body__AMS_ALPHA",
        }
        unsupported = {
            "material": "Hair",
            "supported": False,
            "resolution": "NO_AUTHORITATIVE_ALPHA_IMAGE",
        }
        report = {
            "objects": (
                {"groups": (supported, unsupported)},
                {"groups": (dict(supported),), "skip_reason": ""},
                {"groups": (unsupported,), "skip_reason": "LINKED_MESH"},
            )
        }

        cards = review_material_cards(report)

        self.assertEqual(cards, (supported, unsupported))

    def test_alpha_source_advisory_uses_singular_and_plural_copy(self) -> None:
        supported = {"material": "Body", "supported": True}
        unsupported = {"material": "Hair", "supported": False}

        self.assertIsNone(alpha_source_advisory((supported,)))
        self.assertEqual(
            alpha_source_advisory((unsupported,)),
            (
                "1 material may need an alpha source.",
                "Open Material Details below to review it.",
            ),
        )
        self.assertEqual(
            alpha_source_advisory((unsupported, dict(unsupported, material="Eyes"))),
            (
                "2 materials may need an alpha source.",
                "Open Material Details below to review them.",
            ),
        )

    def test_already_separated_tooltip_is_state_specific(self) -> None:
        self.assertEqual(
            already_separated_tooltip(
                already_derived=True, actionable=False
            ),
            (
                "All faces on the selected meshes are optimally assigned. "
                "No faces need to be moved."
            ),
        )
        self.assertEqual(
            already_separated_tooltip(
                already_derived=True, actionable=True
            ),
            "",
        )
        self.assertEqual(
            already_separated_tooltip(
                already_derived=False, actionable=False
            ),
            "",
        )

    def test_plain_language_classification_labels(self) -> None:
        self.assertEqual(CLASS_COPY["OPAQUE"][0], "Stay on opaque material")
        self.assertEqual(CLASS_COPY["ALPHA_AFFECTED"][0], "Move to alpha material")
        self.assertEqual(
            CLASS_COPY["MIXED"][0],
            "Mixed—must use alpha without cutting geometry",
        )
        self.assertEqual(
            CLASS_COPY["SUPPRESSED"][0], "Below significance—needs review"
        )
        self.assertEqual(CLASS_COPY["UNSUPPORTED"][0], "Could not analyze")

    def test_guidance_has_safe_unknown_fallback(self) -> None:
        self.assertIn("review", guidance_for("FUTURE_CODE")[0].lower())
        for code in KNOWN_GUIDANCE_CODES:
            title, remedy = guidance_for(code)
            self.assertTrue(title, code)
            self.assertTrue(remedy, code)
        title, remedy = guidance_for("NO_POSITIVE_AREA_UV_COVERAGE")
        self.assertIn("collapse", title)
        self.assertIn("outside 0–1", remedy)

    def test_suppressed_guidance_names_the_recovering_policy(self) -> None:
        title, remedy = guidance_for("SUPPRESSED_FACES")
        self.assertEqual(title, "Alpha evidence is below the significance setting")
        self.assertIn("Keep on source", remedy)

    def test_default_preview_classes_and_signature(self) -> None:
        self.assertEqual(
            classes_to_move("TO_ALPHA", "CANCEL_SOURCE_MATERIAL"),
            ("ALPHA_AFFECTED", "MIXED"),
        )
        first = review_signature("id", "TO_ALPHA", "CANCEL_SOURCE_MATERIAL", "KEEP_SOURCE", "REUSE_EXISTING")
        second = review_signature("id", "KEEP_SOURCE", "CANCEL_SOURCE_MATERIAL", "KEEP_SOURCE", "REUSE_EXISTING")
        self.assertNotEqual(first, second)
        first_plan = review_signature(
            "id",
            "TO_ALPHA",
            "CANCEL_SOURCE_MATERIAL",
            "KEEP_SOURCE",
            "REUSE_EXISTING",
            {"faces_to_reassign": 1, "source_decisions": {"Body": "REUSE"}},
        )
        changed_plan = review_signature(
            "id",
            "TO_ALPHA",
            "CANCEL_SOURCE_MATERIAL",
            "KEEP_SOURCE",
            "REUSE_EXISTING",
            {"faces_to_reassign": 1, "source_decisions": {"Body": "CREATE"}},
        )
        self.assertNotEqual(first_plan, changed_plan)

    def test_warning_only_confirmation(self) -> None:
        clean = {"counts": {"MIXED": 0, "SUPPRESSED": 0, "UNSUPPORTED": 0}, "skip_counts": {}}
        self.assertFalse(requires_confirmation(clean, {"blocked": []}))
        mixed = {"counts": {"MIXED": 1}, "skip_counts": {}}
        self.assertTrue(requires_confirmation(mixed, {"blocked": []}))
        self.assertTrue(requires_confirmation(clean, {"blocked": [{"reason": "SOURCE_CHANGED"}]}))

    def test_workflow_states(self) -> None:
        idle = workflow_view(
            eligible_objects=0, running=False, has_report=False, stale=False,
            reviewed=False, actionable=False, completed=False,
        )
        self.assertEqual(idle["state"], "IDLE")
        self.assertFalse(idle["can_analyze"])
        running = workflow_view(
            eligible_objects=1, running=True, has_report=True, stale=False,
            reviewed=True, actionable=True, completed=False,
        )
        self.assertEqual(running["state"], "RUNNING")
        self.assertFalse(running["can_apply"])
        reviewed = workflow_view(
            eligible_objects=1, running=False, has_report=True, stale=False,
            reviewed=True, actionable=True, completed=False,
        )
        self.assertEqual(reviewed["state"], "REVIEWED")
        self.assertTrue(reviewed["can_apply"])
        ready_without_preview = workflow_view(
            eligible_objects=1,
            running=False,
            has_report=True,
            stale=False,
            reviewed=False,
            actionable=True,
            completed=False,
        )
        self.assertEqual(ready_without_preview["state"], "READY_TO_REVIEW")
        self.assertTrue(ready_without_preview["can_preview"])
        self.assertTrue(ready_without_preview["can_apply"])

        cases = (
            ("READY_TO_ANALYZE", dict(eligible_objects=1)),
            (
                "READY_TO_REVIEW",
                dict(eligible_objects=1, has_report=True, actionable=True),
            ),
            (
                "STALE",
                dict(eligible_objects=1, has_report=True, stale=True),
            ),
            (
                "NO_CHANGE",
                dict(eligible_objects=1, has_report=True, actionable=False),
            ),
            ("COMPLETED", dict(eligible_objects=1, completed=True)),
        )
        defaults = dict(
            eligible_objects=0,
            running=False,
            has_report=False,
            stale=False,
            reviewed=False,
            actionable=False,
            completed=False,
        )
        for expected, changes in cases:
            arguments = defaults | changes
            with self.subTest(expected=expected):
                view = workflow_view(**arguments)
                self.assertEqual(view["state"], expected)
                if expected in {"STALE", "NO_CHANGE", "COMPLETED"}:
                    self.assertFalse(view["can_apply"])
                if expected == "NO_CHANGE":
                    self.assertFalse(view["can_preview"])

    def test_stale_results_have_real_guidance(self) -> None:
        title, remedy = guidance_for("RESULT_STALE")
        self.assertEqual(title, "Inputs Changed — Analyze Again")
        self.assertNotEqual(title, guidance_for("A_CODE_WITH_NO_ENTRY")[0])
        self.assertTrue(remedy)

    def test_no_silent_status_code_carries_user_facing_guidance(self) -> None:
        """A code with remedy copy must never be classified as nothing to see.

        Marking a code OK suppresses its alert box entirely. Writing guidance
        for such a code is the drift that hid the missing RESULT_STALE entry,
        so the two tables are coupled here.
        """
        from addon.api_contract import STATUS_SEVERITIES, severity_for

        silent = {code for code in STATUS_SEVERITIES if severity_for(code) == "OK"}
        self.assertEqual(silent & KNOWN_GUIDANCE_CODES, set())


if __name__ == "__main__":
    unittest.main()
