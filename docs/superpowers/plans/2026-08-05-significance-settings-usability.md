# Significance Settings Usability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop a below-significance face from cancelling its entire material group, so Minimum Affected Pixels and Minimum Affected Fraction are usable across their whole range.

**Architecture:** Change the `suppressed_policy` default from `CANCEL_SOURCE_MATERIAL` to `KEEP_SOURCE` in the settings group and both operators. Correct the user-facing text that names the old default. Add the missing gate, margin, and blocked-group tests. Classification arithmetic, rasterization, margin semantics, and the public payload are unchanged.

**Tech Stack:** Python 3.13, Blender 5.2 RNA/operators/UI, existing pure-Python core and presentation helpers, `unittest`, existing headless Blender runner.

## Global Constraints

- Target Blender 5.2 LTS; manifest minimum stays `5.2.0`.
- Keep `GPL-3.0-or-later` and the `# SPDX-License-Identifier: GPL-3.0-or-later` header on every new file.
- Public identity stays `alpha_material_separator`.
- `API_VERSION` stays `(1, 2)`. The public payload shape does not change.
- Do not change `mixed_policy`, `unsupported_policy`, or `derived_conflict_policy` defaults.
- Do not change classification arithmetic, gate comparisons, rasterization, or `margin_texels` behavior.
- `CANCEL_SOURCE_MATERIAL` stays selectable and must keep blocking a group.
- Add no operator, panel, button, property, or dependency.
- Keep user copy to one sentence per Blender label.
- Commit each task separately, staging explicit paths only.
- Never commit `.local-references/`, `.packaged-releases/`, `.test-output/`, or `__pycache__/`.

Commands used throughout:

```powershell
$Blender52 = 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
$Python52 = 'C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe'
```

---

### Task 1: Characterize the gates and the margin

These tests lock in behavior that is already correct, so they must pass on
first run. They exist because Task 2 and Task 3 change code nearby, and
nothing currently covers the gate boundaries or the margin interactions.

**Files:**
- Modify: `tests/unit/test_alpha_classification.py`
- Modify: `tests/unit/test_rasterization.py`

**Interfaces:**
- Consumes: `classify_polygon`, `AlphaGrid`, `AnalysisSettings`, `FaceClass` from `addon.core`; `rasterize_polygon` from `addon.core.raster`.
- Produces: no production interface. Test-only.

- [ ] **Step 1: Add the gate boundary and no-op tests**

Append these methods to the existing `AlphaClassificationTests` class in
`tests/unit/test_alpha_classification.py`. `SQUARE` covers a 2x2 texel region,
and `AlphaGrid(2, 2, (True, False, False, False))` gives one affected texel out
of four, a fraction of `0.25`.

```python
    def test_affected_count_equal_to_minimum_is_not_suppressed(self):
        result = classify_polygon(
            SQUARE,
            AlphaGrid(2, 2, (True, False, False, False)),
            settings=AnalysisSettings(min_affected_texels=1),
        )
        self.assertEqual(result.classification, FaceClass.MIXED)
        self.assertEqual(result.failed_gates, ())

    def test_affected_count_below_minimum_is_suppressed(self):
        result = classify_polygon(
            SQUARE,
            AlphaGrid(2, 2, (True, False, False, False)),
            settings=AnalysisSettings(min_affected_texels=2),
        )
        self.assertEqual(result.classification, FaceClass.SUPPRESSED)
        self.assertEqual(result.failed_gates, ("MIN_AFFECTED_TEXELS",))

    def test_affected_fraction_equal_to_minimum_is_not_suppressed(self):
        result = classify_polygon(
            SQUARE,
            AlphaGrid(2, 2, (True, False, False, False)),
            settings=AnalysisSettings(min_affected_fraction=0.25),
        )
        self.assertEqual(result.classification, FaceClass.MIXED)
        self.assertEqual(result.failed_gates, ())

    def test_affected_fraction_below_minimum_is_suppressed(self):
        result = classify_polygon(
            SQUARE,
            AlphaGrid(2, 2, (True, False, False, False)),
            settings=AnalysisSettings(min_affected_fraction=0.26),
        )
        self.assertEqual(result.classification, FaceClass.SUPPRESSED)
        self.assertEqual(result.failed_gates, ("MIN_AFFECTED_FRACTION",))

    def test_texel_minimums_of_zero_and_one_never_suppress(self):
        # A face with no affected texels returns OPAQUE before the gates run,
        # so affected is always at least one here. Both values are no-ops.
        for minimum in (0, 1):
            with self.subTest(minimum=minimum):
                result = classify_polygon(
                    SQUARE,
                    AlphaGrid(2, 2, (True, False, False, False)),
                    settings=AnalysisSettings(min_affected_texels=minimum),
                )
                self.assertEqual(result.classification, FaceClass.MIXED)
                self.assertEqual(result.failed_gates, ())
```

- [ ] **Step 2: Add the margin interaction test**

Append this method to the same class. The face covers the affected centre of a
4x4 grid. A one-texel margin expands coverage to the full grid, which adds
twelve opaque texels.

```python
    def test_margin_expands_coverage_and_can_reclassify_a_face(self):
        centre = tuple(
            1 <= x <= 2 and 1 <= y <= 2
            for y in range(4)
            for x in range(4)
        )
        grid = AlphaGrid(4, 4, centre)
        face = (
            ((1.0, 1.0), (3.0, 1.0), (3.0, 3.0)),
            ((1.0, 1.0), (3.0, 3.0), (1.0, 3.0)),
        )

        exact = classify_polygon(face, grid, settings=AnalysisSettings())
        self.assertEqual(exact.classification, FaceClass.ALPHA_AFFECTED)
        self.assertEqual(exact.covered_texels, 4)
        self.assertEqual(exact.affected_fraction, 1.0)

        expanded = classify_polygon(
            face, grid, settings=AnalysisSettings(margin_texels=1)
        )
        self.assertEqual(expanded.classification, FaceClass.MIXED)
        self.assertEqual(expanded.covered_texels, 16)
        self.assertEqual(expanded.affected_texels, 4)
        self.assertEqual(expanded.affected_fraction, 0.25)
```

- [ ] **Step 3: Run the new tests and confirm they pass**

Run:

```powershell
& $Python52 -m unittest tests.unit.test_alpha_classification -v
```

Expected: PASS. These characterize existing correct behavior. If any fail,
stop and investigate before continuing — the assumption that classification is
correct would be wrong.

- [ ] **Step 4: Run the full unit suite**

Run:

```powershell
& $Python52 -m unittest discover -s tests/unit -t . -v
```

Expected: PASS, with six more tests than the current 88.

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_alpha_classification.py
git commit -m "test: characterize significance gates and pixel margin"
```

---

### Task 2: Default below-significance faces to Keep Source

**Files:**
- Create: `tests/blender/test_significance_settings.py`
- Modify: `tests/blender/run_all.py`
- Modify: `addon/properties.py:207`
- Modify: `addon/operators/assign_materials.py:144`
- Modify: `addon/operators/select_faces.py:73`

**Interfaces:**
- Consumes: `_clear_scene`, `_material`, `_quad` from `tests.blender.test_analysis_preview`; `runtime.report`; `build_assignment_plan` from `addon.adapters.assignment`.
- Produces: `run()` in `tests/blender/test_significance_settings.py`, imported by `run_all.py` as `run_significance_settings_tests`.

- [ ] **Step 1: Write the failing headless regression**

Create `tests/blender/test_significance_settings.py`:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
"""Below-significance faces must not cancel their material group."""

from __future__ import annotations

import bpy

from addon import runtime
from addon.adapters.assignment import build_assignment_plan
from tests.blender.test_analysis_preview import _clear_scene

WIDTH = HEIGHT = 4


def _image():
    image = bpy.data.images.new("AMS_GATE_IMAGE", width=WIDTH, height=HEIGHT, alpha=True)
    pixels = []
    for y in range(HEIGHT):
        for x in range(WIDTH):
            transparent = x < 2 and y < 2
            pixels.extend((1.0, 1.0, 1.0, 0.0 if transparent else 1.0))
    image.pixels.foreach_set(pixels)
    return image


def _material(image):
    material = bpy.data.materials.new("AMS_GATE_SOURCE")
    material.use_nodes = True
    tree = material.node_tree
    principled = tree.nodes["Principled BSDF"]
    texture = tree.nodes.new("ShaderNodeTexImage")
    texture.image = image
    tree.links.new(texture.outputs["Alpha"], principled.inputs["Alpha"])
    material.blend_method = "BLEND"
    return material


def _two_face_object(material):
    """Face 0 covers four affected texels. Face 1 covers one."""
    mesh = bpy.data.meshes.new("AMS_GATE_MESH")
    mesh.from_pydata(
        (
            (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0),
            (2.0, 0.0, 0.0), (3.0, 0.0, 0.0), (3.0, 1.0, 0.0), (2.0, 1.0, 0.0),
        ),
        (),
        ((0, 1, 2, 3), (4, 5, 6, 7)),
    )
    mesh.materials.append(material)
    uv_layer = mesh.uv_layers.new(name="UVMap", do_init=False)
    uv_layer.active_render = True
    quarter = 1.0 / WIDTH
    face_uvs = {
        0: ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)),
        1: ((0.0, 0.0), (quarter, 0.0), (quarter, quarter), (0.0, quarter)),
    }
    for polygon in mesh.polygons:
        corners = face_uvs[polygon.index]
        for corner, loop_index in enumerate(polygon.loop_indices):
            uv_layer.uv[loop_index].vector = corners[corner]
    object_ = bpy.data.objects.new("AMS_GATE_OBJECT", mesh)
    bpy.context.collection.objects.link(object_)
    object_.select_set(True)
    bpy.context.view_layer.objects.active = object_
    return object_


def _plan(suppressed_policy):
    state = bpy.context.window_manager.alpha_material_separator_api
    report = runtime.report(state.analysis_id)
    return build_assignment_plan(
        report,
        mixed_policy="TO_ALPHA",
        suppressed_policy=suppressed_policy,
        unsupported_policy="CANCEL_SOURCE_MATERIAL",
        conflict_policy="CANCEL_SOURCE_MATERIAL",
    ).public_payload()


def _assert_defaults_keep_source():
    settings = bpy.context.window_manager.alpha_material_separator_settings
    assert settings.bl_rna.properties["suppressed_policy"].default == "KEEP_SOURCE"
    for operator in (
        bpy.types.ALPHA_MATERIAL_SEPARATOR_OT_assign_materials,
        bpy.types.ALPHA_MATERIAL_SEPARATOR_OT_select_faces,
    ):
        assert (
            operator.bl_rna.properties["suppressed_policy"].default == "KEEP_SOURCE"
        ), operator.bl_rna.identifier


def _assert_sibling_face_survives():
    result = bpy.ops.alpha_material_separator.analyze(min_affected_texels=2)
    assert result == {"FINISHED"}, result

    default_plan = _plan("KEEP_SOURCE")
    assert default_plan["blocked"] == [], default_plan["blocked"]
    assert default_plan["faces_to_reassign"] == 1, default_plan

    blocked_plan = _plan("CANCEL_SOURCE_MATERIAL")
    reasons = [entry.get("reason") for entry in blocked_plan["blocked"]]
    assert reasons == ["SUPPRESSED_FACES"], reasons
    assert blocked_plan["faces_to_reassign"] == 0, blocked_plan


def run() -> None:
    _clear_scene()
    _two_face_object(_material(_image()))
    _assert_defaults_keep_source()
    _assert_sibling_face_survives()
    _clear_scene()
    print("ALPHA_MATERIAL_SEPARATOR_SIGNIFICANCE_TESTS_OK")
```

- [ ] **Step 2: Register the new module in the headless runner**

In `tests/blender/run_all.py`, add this import beside the other test imports:

```python
from tests.blender.test_significance_settings import (  # noqa: E402
    run as run_significance_settings_tests,
)
```

Then add this call inside the `if iteration == 0:` block, after
`run_assignment_policy_tests()`:

```python
            run_significance_settings_tests()
```

- [ ] **Step 3: Run the headless suite and confirm RED**

Run:

```powershell
& $Blender52 --factory-startup --background --disable-autoexec --python-exit-code 1 --python tests/blender/run_all.py
```

Expected: FAIL inside `_assert_defaults_keep_source`, because the shipped
default is still `CANCEL_SOURCE_MATERIAL`.

- [ ] **Step 4: Change the settings group default**

In `addon/properties.py`, replace the `suppressed_policy` block at line 200:

```python
    suppressed_policy: EnumProperty(
        name="Below-Significance Evidence",
        items=(
            ("CANCEL_SOURCE_MATERIAL", "Skip entire material group", "Skip after informed review"),
            ("TO_ALPHA", "Move to alpha", "Move after informed review"),
            ("KEEP_SOURCE", "Keep on source", "Conservative default"),
        ),
        default="KEEP_SOURCE",
        update=_policy_changed,
    )
```

- [ ] **Step 5: Change the assignment operator default**

In `addon/operators/assign_materials.py`, replace the `suppressed_policy` block
at line 133:

```python
    suppressed_policy: EnumProperty(
        name="Suppressed Evidence",
        items=(
            (
                "CANCEL_SOURCE_MATERIAL",
                "Skip this entire material group",
                "Skip after informed review",
            ),
            ("TO_ALPHA", "Move to Alpha", "Move after informed review"),
            ("KEEP_SOURCE", "Keep Source", "Conservative default"),
        ),
        default="KEEP_SOURCE",
    )
```

- [ ] **Step 6: Change the selection operator default**

In `addon/operators/select_faces.py`, replace the `suppressed_policy` block at
line 66:

```python
    suppressed_policy: EnumProperty(
        name="Suppressed Evidence",
        items=(
            ("CANCEL_SOURCE_MATERIAL", "Skip Group", "Skip the material group"),
            ("TO_ALPHA", "Move to Alpha", "Move suppressed faces to alpha"),
            ("KEEP_SOURCE", "Keep Source", "Leave suppressed faces on the source"),
        ),
        default="KEEP_SOURCE",
        options={"HIDDEN", "SKIP_SAVE"},
    )
```

- [ ] **Step 7: Run the headless suite and confirm GREEN**

Run:

```powershell
& $Blender52 --factory-startup --background --disable-autoexec --python-exit-code 1 --python tests/blender/run_all.py
```

Expected: exit code 0, including
`ALPHA_MATERIAL_SEPARATOR_SIGNIFICANCE_TESTS_OK` and every pre-existing
completion marker. The two tests at
`tests/blender/test_assignment_policies.py:272` and `:303` pass an explicit
policy and must still pass unchanged.

- [ ] **Step 8: Run the unit suite**

Run:

```powershell
& $Python52 -m unittest discover -s tests/unit -t . -v
```

Expected: PASS. `classes_to_move` returns the same tuple for `KEEP_SOURCE` and
`CANCEL_SOURCE_MATERIAL`, so no presentation test changes.

- [ ] **Step 9: Commit**

```bash
git add tests/blender/test_significance_settings.py tests/blender/run_all.py addon/properties.py addon/operators/assign_materials.py addon/operators/select_faces.py
git commit -m "fix: keep below-significance faces on their source material"
```

---

### Task 3: Correct the user-facing copy

**Files:**
- Modify: `addon/presentation.py:60`
- Modify: `README.md:54`
- Modify: `tests/unit/test_presentation.py`

**Interfaces:**
- Consumes: `guidance_for` from `addon.presentation`.
- Produces: no production interface. Copy only.

- [ ] **Step 1: Write the failing copy test**

Append this method to `PresentationTests` in `tests/unit/test_presentation.py`:

```python
    def test_suppressed_guidance_names_the_recovering_policy(self) -> None:
        title, remedy = guidance_for("SUPPRESSED_FACES")
        self.assertEqual(title, "Alpha evidence is below the significance setting")
        self.assertIn("Keep on source", remedy)
```

- [ ] **Step 2: Run the test and confirm RED**

Run:

```powershell
& $Python52 -m unittest tests.unit.test_presentation.PresentationTests.test_suppressed_guidance_names_the_recovering_policy -v
```

Expected: FAIL. The current remedy is
`Review the affected material group or change its Expert policy deliberately.`

- [ ] **Step 3: Rewrite the remedy sentence**

In `addon/presentation.py`, replace the `SUPPRESSED_FACES` entry at line 60:

```python
    "SUPPRESSED_FACES": ("Alpha evidence is below the significance setting", "Set Below-Significance Evidence to Keep on source to assign the rest of this material group."),
```

- [ ] **Step 4: Run the test and confirm GREEN**

Run:

```powershell
& $Python52 -m unittest tests.unit.test_presentation.PresentationTests.test_suppressed_guidance_names_the_recovering_policy -v
```

Expected: PASS.

- [ ] **Step 5: Correct the README behavior table**

In `README.md`, replace the below-significance row at line 54:

```markdown
| **Below significance—needs review** | Alpha evidence exists but is below an Expert minimum. | Those faces stay on the source material; the rest of the group is still assigned. |
```

- [ ] **Step 6: Run the unit suite**

Run:

```powershell
& $Python52 -m unittest discover -s tests/unit -t . -v
```

Expected: PASS, including `tests.unit.test_readme_contract`.

- [ ] **Step 7: Commit**

```bash
git add addon/presentation.py README.md tests/unit/test_presentation.py
git commit -m "docs: describe the below-significance recovery accurately"
```

---

### Task 4: Document Pixel Margin and release 1.1.0

**Files:**
- Modify: `addon/blender_manifest.toml:4`
- Modify: `docs/algorithm.md:13`
- Modify: `docs/HANDOFF.md`

**Interfaces:**
- Consumes: nothing.
- Produces: manifest version `1.1.0`.

- [ ] **Step 1: Expand the margin description**

In `docs/algorithm.md`, replace line 13:

```markdown
5. Apply the optional Chebyshev texel margin. This dilates the unioned coverage
   by the configured number of texels in every direction so that alpha texels
   just outside the exact UV footprint are counted, which matches bilinear
   filtering and mipmap bleed at render time. A margin also raises the covered
   texel count with texels that are usually opaque, which lowers the affected
   fraction and can reclassify a fully affected face as mixed.
```

- [ ] **Step 2: Bump the manifest version**

In `addon/blender_manifest.toml`, change line 4:

```toml
version = "1.1.0"
```

- [ ] **Step 3: Validate the extension source**

Run:

```powershell
& $Blender52 --factory-startup --command extension validate addon
```

Expected: `Success parsing TOML in "addon"`.

- [ ] **Step 4: Build and validate the archive**

Run:

```powershell
& $Blender52 --factory-startup --command extension build --source-dir addon --output-dir .packaged-releases
$Archive = (Resolve-Path .\.packaged-releases\alpha_material_separator-1.1.0.zip).Path
& $Blender52 --factory-startup --command extension validate $Archive
```

Expected: the archive builds as `alpha_material_separator-1.1.0.zip` and
validates.

- [ ] **Step 5: Run the complete change gate**

Run:

```powershell
& $Python52 -m unittest discover -s tests/unit -t . -v
& $Blender52 --factory-startup --background --disable-autoexec --python-exit-code 1 --python tests/blender/run_all.py
& $Blender52 --factory-startup --command extension validate addon
git diff --check
```

Expected: unit suite passes, headless suite exits 0, source validation
succeeds, and the diff check reports no whitespace errors.

- [ ] **Step 6: Update the handoff**

Rewrite the objective, completed work, and remaining tasks in
`docs/HANDOFF.md` to record: the reproduced root cause, the new `KEEP_SOURCE`
default across all three sites, the corrected copy, the added gate and margin
coverage, the `1.1.0` manifest bump, and the still-outstanding items — the
private before/after smoke, the installed-ZIP interactive acceptance, and the
deferred `docs/superpowers/` deletion.

- [ ] **Step 7: Commit**

```bash
git add addon/blender_manifest.toml docs/algorithm.md docs/HANDOFF.md
git commit -m "docs: document pixel margin and target 1.1.0"
```

---

## Remaining acceptance, not covered by this plan

These need the user and cannot be completed headlessly:

- [ ] Private `.local-references/default-example/` before/after smoke. Required
      because this change alters assignment plans.
- [ ] Installed-ZIP interactive acceptance in a clean Blender 5.2 configuration,
      including Analyze → Preview → Tab to Object Mode → Apply.
- [ ] Confirm in the real panel that a below-significance face now reports under
      `Faces kept by policy` rather than blocking the group.
