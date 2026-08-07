# Credits & Support Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Credits & Support panel above the Alpha Material Separator panel showing the version, maintainer, and a GitHub issues link, all read from `blender_manifest.toml`, and make the manifest the single place a release version is edited.

**Architecture:** A new bpy-free `addon/manifest.py` reads the packaged manifest once at import and exposes the version tuple, maintainer name, and issues URL. `api_contract.EXTENSION_VERSION` becomes a value parsed from that module instead of a hand-edited constant, so `dotted()` and both existing call sites keep their current shapes. `addon/panel.py` gains a top-level panel ordered above the main panel. The manifest read uses the Windows extended-length prefix so a long install path cannot silently blank a version that is both published in the public payload and written into material metadata.

**Tech Stack:** Python 3.13 with stdlib `tomllib`, Blender 5.2 RNA/UI, `unittest`, existing headless Blender runner.

**Design approval:** Approved in conversation on 2026-08-07, including option B for long-path handling.

## Global Constraints

- Target Blender 5.2 LTS; manifest minimum stays `5.2.0`.
- Keep `# SPDX-License-Identifier: GPL-3.0-or-later` on every file.
- `API_VERSION` stays `(1, 2)`. The public payload keeps its existing keys and
  its `extension_version` string format.
- `addon/manifest.py` and `addon/api_contract.py` must remain importable without
  `bpy`. `tests/unit/test_api_contract.py::test_core_import_does_not_require_bpy`
  asserts `bpy` is never in `sys.modules`.
- No new dependency, no runtime network request from the addon. `wm.url_open`
  hands a URL to the user's browser on an explicit click and is permitted.
- The panel must never raise from `draw()`; a raising panel breaks the whole
  sidebar region. Missing manifest values omit their row instead.
- Do not change classification, rasterization, assignment, or any analysis
  behavior.
- Keep user copy to one sentence per Blender label.
- Never commit `.local-references/`, `.packaged-releases/`, `.test-output/`, or
  `__pycache__/`.

Commands used throughout:

```powershell
$Blender52 = 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
$Python52 = 'C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe'
```

---

### Task 1: Add the manifest reader

**Files:**
- Create: `addon/manifest.py`
- Create: `tests/unit/test_manifest.py`

**Interfaces:**
- Produces: `read() -> dict`, `version_tuple() -> tuple[int, ...]`,
  `maintainer_name() -> str`, `issues_url() -> str`, and module constant
  `MANIFEST_PATH: Path`, all importable without `bpy`.

- [ ] **Step 1: Write the failing unit tests**

Create `tests/unit/test_manifest.py`:

```python
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import tomllib
import unittest
from pathlib import Path

from addon import manifest

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "addon" / "blender_manifest.toml"


class ManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw = tomllib.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_reads_the_packaged_manifest(self) -> None:
        self.assertEqual(manifest.read()["version"], self.raw["version"])

    def test_version_tuple_matches_the_manifest(self) -> None:
        expected = tuple(int(part) for part in self.raw["version"].split("."))
        self.assertEqual(manifest.version_tuple(), expected)

    def test_maintainer_name_drops_the_contact_address(self) -> None:
        name = manifest.maintainer_name()
        self.assertTrue(name)
        self.assertNotIn("@", name)
        self.assertNotIn("<", name)
        self.assertTrue(self.raw["maintainer"].startswith(name))

    def test_issues_url_is_derived_from_the_website(self) -> None:
        self.assertEqual(
            manifest.issues_url(), f"{self.raw['website'].rstrip('/')}/issues"
        )

    def test_unreadable_manifest_degrades_instead_of_raising(self) -> None:
        missing = Path("does-not-exist") / "blender_manifest.toml"
        self.assertEqual(manifest.read(missing), {})
        self.assertEqual(manifest.version_tuple(missing), ())
        self.assertEqual(manifest.maintainer_name(missing), "")
        self.assertEqual(manifest.issues_url(missing), "")

    def test_malformed_version_yields_an_empty_tuple(self) -> None:
        self.assertEqual(manifest._parse_version("not.a.version"), ())
        self.assertEqual(manifest._parse_version(""), ())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test and confirm RED**

Run:

```powershell
& $Python52 -m unittest tests.unit.test_manifest -v
```

Expected: FAIL with `ModuleNotFoundError` or `ImportError` for
`addon.manifest`.

- [ ] **Step 3: Add the module**

Create `addon/manifest.py`:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
"""Read the packaged extension manifest as the single source of identity.

The manifest is the only place a release version is edited. Everything else
derives from it, so a bump cannot leave a second copy behind.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

MANIFEST_PATH = Path(__file__).resolve().parent / "blender_manifest.toml"


def _readable(path: Path) -> Path:
    """Return a path Blender's Python can open on Windows.

    An installed extension can sit past the Windows MAX_PATH limit, where a
    plain absolute path fails to open. The extended-length prefix avoids that.
    It applies only to absolute Windows paths that are not already prefixed.
    """
    text = str(path)
    if len(text) < 250 or not text[1:3] == ":\\" or text.startswith("\\\\?\\"):
        return path
    return Path(f"\\\\?\\{text}")


def read(path: Path | None = None) -> dict:
    """Return the parsed manifest, or an empty mapping if unreadable.

    A missing or malformed manifest must not raise. The version reaches both the
    public capability payload and the metadata written onto derived materials,
    so an honest empty value is preferable to a crash or a stale guess.
    """
    try:
        target = _readable(path or MANIFEST_PATH)
        return tomllib.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError, tomllib.TOMLDecodeError):
        return {}


def _parse_version(raw: str) -> tuple[int, ...]:
    parts = str(raw).split(".")
    if not raw or not all(part.isdigit() for part in parts):
        return ()
    return tuple(int(part) for part in parts)


def version_tuple(path: Path | None = None) -> tuple[int, ...]:
    """Return the manifest version as integers, or an empty tuple."""
    return _parse_version(read(path).get("version", ""))


def maintainer_name(path: Path | None = None) -> str:
    """Return the maintainer without the contact address."""
    return str(read(path).get("maintainer", "")).split(" <")[0].strip()


def issues_url(path: Path | None = None) -> str:
    """Return the project issue tracker, or an empty string."""
    website = str(read(path).get("website", "")).rstrip("/")
    return f"{website}/issues" if website else ""
```

- [ ] **Step 4: Run the test and confirm GREEN**

Run:

```powershell
& $Python52 -m unittest tests.unit.test_manifest -v
```

Expected: PASS, 6 tests.

- [ ] **Step 5: Run the full unit suite**

Run:

```powershell
& $Python52 -m unittest discover -s tests/unit -t . -v
```

Expected: PASS. `test_core_import_does_not_require_bpy` must still pass, proving
the new module pulled in no `bpy`.

- [ ] **Step 6: Commit**

```bash
git add addon/manifest.py tests/unit/test_manifest.py
git commit -m "feat: read extension identity from the packaged manifest"
```

---

### Task 2: Derive EXTENSION_VERSION from the manifest

**Files:**
- Modify: `addon/api_contract.py:12`
- Modify: `tests/unit/test_api_contract.py:31`

**Interfaces:**
- Consumes: `addon.manifest.version_tuple`.
- Preserves: `EXTENSION_VERSION: tuple[int, ...]`, `dotted()`, and the
  `extension_version` payload key and string format. `material_metadata.py:218`
  is unchanged.

- [ ] **Step 1: Rewrite the cross-check as a derivation check**

In `tests/unit/test_api_contract.py`, replace the hardcoded assertion:

```python
        self.assertEqual(payload["extension_version"], "1.1.0")
```

with a derivation assertion that needs no editing at release time:

```python
        self.assertEqual(
            payload["extension_version"],
            api_contract.dotted(manifest.version_tuple()),
        )
```

Add the import beside the existing ones:

```python
from addon import manifest
```

Leave the following line, which already compares the payload against the
manifest file, exactly as it is. It is the assertion that proves derivation
reaches the manifest on disk:

```python
        manifest_data = tomllib.loads(MANIFEST.read_text(encoding="utf8"))
        self.assertEqual(manifest_data["version"], payload["extension_version"])
```

Note: the existing local variable is named `manifest`. Rename it to
`manifest_data` so it does not shadow the imported module, and update its one
use on the next line.

- [ ] **Step 2: Run the test and confirm it still passes**

Run:

```powershell
& $Python52 -m unittest tests.unit.test_api_contract -v
```

Expected: PASS. This step is deliberately not RED. `EXTENSION_VERSION` is
currently `(1, 1, 0)` and the manifest currently says `1.1.0`, so the derivation
assertion is satisfied either way. Task 4 provides the real proof by bumping the
manifest alone.

- [ ] **Step 3: Derive the constant**

In `addon/api_contract.py`, add the import beside the existing one:

```python
from .manifest import version_tuple as _manifest_version
```

Then replace:

```python
EXTENSION_VERSION = (1, 1, 0)
```

with:

```python
# Derived so a release bumps blender_manifest.toml and nothing else.
EXTENSION_VERSION = _manifest_version()
```

- [ ] **Step 4: Run the full unit suite**

Run:

```powershell
& $Python52 -m unittest discover -s tests/unit -t . -v
```

Expected: PASS, including `test_core_import_does_not_require_bpy`.

- [ ] **Step 5: Run the headless Blender suite**

Run:

```powershell
& $Blender52 --factory-startup --background --disable-autoexec --python-exit-code 1 --python tests/blender/run_all.py
```

Expected: exit 0. This exercises `material_metadata.py`, which stamps
`dotted(EXTENSION_VERSION)` onto derived materials, so a broken derivation would
surface in the assignment and preservation tests.

- [ ] **Step 6: Commit**

```bash
git add addon/api_contract.py tests/unit/test_api_contract.py
git commit -m "refactor: derive the extension version from the manifest"
```

---

### Task 3: Add the Credits & Support panel

**Files:**
- Modify: `addon/panel.py` (imports, new panel class, `bl_order` on the main panel)
- Modify: `addon/registration.py`
- Create: `tests/blender/test_credits_panel.py`
- Modify: `tests/blender/run_all.py`

**Interfaces:**
- Consumes: `addon.manifest.maintainer_name`, `addon.manifest.issues_url`,
  `addon.manifest.version_tuple`.
- Produces: `ALPHA_MATERIAL_SEPARATOR_PT_credits` with
  `bl_idname = "ALPHA_MATERIAL_SEPARATOR_PT_credits"`, `bl_category = "AMS"`,
  `bl_order = 0`; and `run()` in the new test module, imported by `run_all.py`
  as `run_credits_panel_tests`.

- [ ] **Step 1: Write the failing headless test**

Create `tests/blender/test_credits_panel.py`:

```python
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
```

- [ ] **Step 2: Register the module in the headless runner**

In `tests/blender/run_all.py`, add beside the other test imports:

```python
from tests.blender.test_credits_panel import (  # noqa: E402
    run as run_credits_panel_tests,
)
```

Add this call inside the `if iteration == 0:` block, after
`run_expert_analysis_settings_tests()`:

```python
            run_credits_panel_tests()
```

- [ ] **Step 3: Run the headless suite and confirm RED**

Run:

```powershell
& $Blender52 --factory-startup --background --disable-autoexec --python-exit-code 1 --python tests/blender/run_all.py
```

Expected: FAIL with `AttributeError` on
`bpy.types.ALPHA_MATERIAL_SEPARATOR_PT_credits`.

- [ ] **Step 4: Add the panel**

In `addon/panel.py`, add this new import line beside the other local imports,
after `from .adapters.assignment import build_assignment_plan`:

```python
from .manifest import issues_url, maintainer_name, version_tuple
```

Add `bl_order` to the existing main panel so the ordering is explicit rather
than dependent on registration order. In
`ALPHA_MATERIAL_SEPARATOR_PT_main`, after `bl_category = "AMS"`:

```python
    bl_order = 1
```

Then add this class immediately above `ALPHA_MATERIAL_SEPARATOR_PT_main`:

```python
class ALPHA_MATERIAL_SEPARATOR_PT_credits(bpy.types.Panel):
    """Show maintainer and support links read from the packaged manifest."""

    bl_idname = "ALPHA_MATERIAL_SEPARATOR_PT_credits"
    bl_label = "Credits & Support"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "AMS"
    bl_order = 0

    def draw(self, _context: bpy.types.Context) -> None:
        layout = self.layout
        self._draw_header(layout)
        self._draw_contact(layout)
        self._draw_support(layout)

    @staticmethod
    def _draw_header(layout: bpy.types.UILayout) -> None:
        box = layout.box()
        column = box.column()
        column.scale_y = 1.2
        version = ".".join(str(part) for part in version_tuple())
        column.label(text=f"Alpha Material Separator {version}".strip())
        maintainer = maintainer_name()
        if maintainer:
            row = box.row(align=True)
            row.scale_y = 1.2
            row.alignment = "LEFT"
            row.label(text="Maintained by:")
            row.label(text=maintainer)

    @staticmethod
    def _link(layout: bpy.types.UILayout, text: str, url: str) -> None:
        row = layout.row()
        row.enabled = bool(url)
        row.operator("wm.url_open", text=text, icon="URL").url = url

    def _draw_contact(self, layout: bpy.types.UILayout) -> None:
        box = layout.box()
        column = box.column(align=True)
        column.scale_y = 1.2
        column.label(text="Found an issue?")
        self._link(column, "Report Bug on GitHub", issues_url())

    def _draw_support(self, layout: bpy.types.UILayout) -> None:
        # Second box is a placeholder for a Discord link that does not exist
        # yet; it deliberately repeats the issue tracker until then.
        box = layout.box()
        column = box.column(align=True)
        column.scale_y = 1.2
        column.label(text="Report Issues:")
        self._link(column, "GitHub Issues", issues_url())
```

- [ ] **Step 5: Register the panel**

In `addon/registration.py`, add to `_CLASSES` immediately before
`panel.ALPHA_MATERIAL_SEPARATOR_PT_main`:

```python
    panel.ALPHA_MATERIAL_SEPARATOR_PT_credits,
```

- [ ] **Step 6: Run the headless suite and confirm GREEN**

Run:

```powershell
& $Blender52 --factory-startup --background --disable-autoexec --python-exit-code 1 --python tests/blender/run_all.py
```

Expected: exit 0 including
`ALPHA_MATERIAL_SEPARATOR_CREDITS_PANEL_TESTS_OK`. The existing
`assert_unregistered()` check must still pass, proving the new panel unregisters
cleanly.

- [ ] **Step 7: Run the unit suite and validate the source**

Run:

```powershell
& $Python52 -m unittest discover -s tests/unit -t . -v
& $Blender52 --factory-startup --command extension validate addon
```

Expected: both pass.

- [ ] **Step 8: Commit**

```bash
git add addon/panel.py addon/registration.py tests/blender/test_credits_panel.py tests/blender/run_all.py
git commit -m "feat: add a Credits & Support panel above the workflow panel"
```

---

### Task 4: Release 1.1.1 by bumping the manifest alone

This task is the proof that Task 2 worked. Only `blender_manifest.toml` carries
a version; every other file must follow without being edited.

**Files:**
- Modify: `addon/blender_manifest.toml:4`
- Modify: `README.md` (two version mentions)
- Modify: `docs/HANDOFF.md`

- [ ] **Step 1: Bump the manifest**

In `addon/blender_manifest.toml`, change `version = "1.1.0"` to
`version = "1.1.1"`. Leave `schema_version` alone.

- [ ] **Step 2: Run the unit suite and confirm exactly one expected failure**

Run:

```powershell
& $Python52 -m unittest discover -s tests/unit -t . -v
```

Expected: `tests.unit.test_readme_contract` fails because the README still says
`1.1.0`. `test_api_contract` must **pass**, proving `EXTENSION_VERSION` followed
the manifest with no edit. If `test_api_contract` fails, Task 2 is wrong; stop
and fix it rather than editing the constant.

- [ ] **Step 3: Update the README**

In `README.md`, change both mentions to 1.1.1:

```markdown
Version 1.1.1 targets Blender 5.2 LTS.
```

```markdown
1. Download `alpha_material_separator-1.1.1.zip`. Do not unzip it.
```

- [ ] **Step 4: Run the complete change gate**

Run:

```powershell
& $Python52 -m unittest discover -s tests/unit -t . -v
& $Blender52 --factory-startup --background --disable-autoexec --python-exit-code 1 --python tests/blender/run_all.py
& $Blender52 --factory-startup --command extension validate addon
Remove-Item .\.packaged-releases\*.zip -ErrorAction SilentlyContinue
& $Blender52 --factory-startup --command extension build --source-dir addon --output-dir .packaged-releases
$Archive = (Get-ChildItem .\.packaged-releases\alpha_material_separator-*.zip | Select-Object -ExpandProperty FullName)
& $Blender52 --factory-startup --command extension validate $Archive
git diff --check
```

Expected: all pass, and the archive builds as
`alpha_material_separator-1.1.1.zip`.

- [ ] **Step 5: Confirm the packaged manifest is readable from inside the ZIP layout**

The panel reads a file that must be present in the built archive. Confirm it is:

```powershell
Add-Type -AssemblyName System.IO.Compression.FileSystem
$Zip = [System.IO.Compression.ZipFile]::OpenRead($Archive)
try {
    $Zip.Entries | Where-Object { $_.Name -eq 'blender_manifest.toml' } |
      Select-Object -ExpandProperty FullName
} finally {
    $Zip.Dispose()
}
```

Expected: one entry, `blender_manifest.toml`. Dispose the handle, or the archive
stays locked and the next build fails to overwrite it.

- [ ] **Step 6: Update the handoff and commit**

Record in `docs/HANDOFF.md`: the new panel, that the manifest is now the single
version edit point, that `EXTENSION_VERSION` is derived, and that the installed
acceptance items for 1.1.1 are pending.

```bash
git add addon/blender_manifest.toml README.md docs/HANDOFF.md
git commit -m "chore: release 1.1.1 from a single manifest edit"
```

---

## Remaining acceptance, not covered by this plan

User-performed; an agent cannot drive the Blender UI:

- [ ] Install `alpha_material_separator-1.1.1.zip` in a clean Blender 5.2
      configuration and confirm Credits & Support appears **above** Alpha
      Material Separator in the AMS tab.
- [ ] Confirm the version and maintainer read correctly, and that
      **Report Bug on GitHub** opens the issue tracker.
- [ ] The four 1.1.0 interactions still outstanding in `docs/HANDOFF.md`.
