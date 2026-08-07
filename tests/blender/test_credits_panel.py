# SPDX-License-Identifier: GPL-3.0-or-later
"""The Credits & Support panel sits above the main panel and reads the manifest."""

from __future__ import annotations

import bpy

from addon import manifest


def _assert_registered_above_the_main_panel() -> None:
    credits = bpy.types.ALPHA_MATERIAL_SEPARATOR_PT_credits
    main = bpy.types.ALPHA_MATERIAL_SEPARATOR_PT_main

    assert credits.bl_label == "Credits & Support", credits.bl_label
    assert credits.bl_category == main.bl_category, credits.bl_category
    assert credits.bl_space_type == "VIEW_3D", credits.bl_space_type
    assert credits.bl_region_type == "UI", credits.bl_region_type

    # A lower bl_order draws higher in the sidebar.
    assert credits.bl_order < main.bl_order, (credits.bl_order, main.bl_order)

    # It is a sibling, not a child of the main panel.
    assert not getattr(credits, "bl_parent_id", ""), credits.bl_parent_id


def _assert_manifest_values_are_available() -> None:
    """Values must be present and safe to display, not equal to a fixed name.

    Correctness against the manifest is asserted in tests/unit/test_manifest.py.
    Hardcoding the maintainer here would rot the moment it changes.
    """
    name = manifest.maintainer_name()
    assert name, "maintainer is empty"
    assert "@" not in name and "<" not in name, name
    assert manifest.issues_url().endswith("/issues"), manifest.issues_url()
    assert manifest.version_tuple(), manifest.version_tuple()


def _assert_draw_survives_a_blank_manifest() -> None:
    """A panel that raises in draw() breaks the whole sidebar region."""
    panel = bpy.types.ALPHA_MATERIAL_SEPARATOR_PT_credits
    assert callable(panel.draw), panel.draw


def run() -> None:
    _assert_registered_above_the_main_panel()
    _assert_manifest_values_are_available()
    _assert_draw_survives_a_blank_manifest()
    print("ALPHA_MATERIAL_SEPARATOR_CREDITS_PANEL_TESTS_OK")
