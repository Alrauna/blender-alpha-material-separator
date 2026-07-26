# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import unittest

from addon.presentation import (
    CLASS_COPY,
    KNOWN_GUIDANCE_CODES,
    classes_to_move,
    guidance_for,
    requires_confirmation,
    review_signature,
    workflow_view,
)


class PresentationTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
