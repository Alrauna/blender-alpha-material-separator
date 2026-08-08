# SPDX-License-Identifier: GPL-3.0-or-later
"""Headless tests for the published integration contract."""

from __future__ import annotations

import bpy

LEGACY_PER_CALL_ARGUMENTS = ("image_name", "uv_map_name", "image_channel")


def _assert_legacy_arguments_do_not_persist() -> None:
    """A stale value from a previous invocation must not silently apply."""

    properties = bpy.ops.alpha_material_separator.analyze.get_rna_type().properties
    for name in LEGACY_PER_CALL_ARGUMENTS:
        definition = properties[name]
        assert definition.is_skip_save, (name, definition.is_skip_save)


def run() -> None:
    _assert_legacy_arguments_do_not_persist()
    print("ALPHA_MATERIAL_SEPARATOR_INTEGRATION_CONTRACT_TESTS_OK")
