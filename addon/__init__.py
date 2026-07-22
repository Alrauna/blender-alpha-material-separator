# SPDX-License-Identifier: GPL-3.0-or-later
"""Blender extension entry point.

Blender imports this package before calling :func:`register`. Blender-facing
modules therefore stay behind the function boundary so the pure package can be
imported by ordinary Python without requiring ``bpy``.
"""


def register() -> None:
    """Register the extension with Blender."""
    from .registration import register as register_extension

    register_extension()


def unregister() -> None:
    """Unregister every extension-owned Blender resource."""
    from .registration import unregister as unregister_extension

    unregister_extension()
