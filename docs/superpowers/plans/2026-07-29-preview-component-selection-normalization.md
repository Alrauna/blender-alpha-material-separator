# Preview Component Selection Normalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

Repository override: execute inline with `superpowers:executing-plans` unless
the user explicitly requests subagent or parallel execution.

**Goal:** Make Preview clear stale vertex and edge selections before entering face-select Edit Mode so only components belonging to the final selected faces are highlighted.

**Architecture:** Preserve the authoritative face plan and existing Object Mode polygon-selection path. Immediately before writing final polygon states for an object that will enter Preview Edit Mode, clear that mesh's vertex and edge selection flags; Blender will then derive component highlighting from the selected polygons when Edit Mode begins. Do not change classification, assignment, review tokens, public operators, or the unavoidable highlight on an edge shared by a selected and unselected face.

**Tech Stack:** Blender 5.2 RNA and BMesh test inspection, Python 3.13, existing headless Blender test runner, PowerShell build scripts.

## Global Constraints

- Preserve extension version `0.1.0`, API `1.2`, public operator IDs, arguments, selection modes, classifications, policies, payloads, and assignment behavior.
- Change selection presentation only. Material assignment must continue to use the exact reviewed face plan.
- Normalize vertex and edge flags only for analyzed target objects that will enter Edit Mode.
- Preserve final polygon semantics for `REPLACE`, `ADD`, and `SUBTRACT`.
- Preserve component flags when `enter_edit_mode=False`.
- Do not alter skipped, unsafe, unrelated, or non-target mesh component flags.
- A selected face's boundary components are expected to be selected. A shared edge between a selected alpha face and an opaque neighbor therefore remains highlighted.
- Preserve multi-object Edit Mode, analysis ID, exact review token, dependency-graph revalidation behavior, undo, and no-topology-change guarantees.
- Add no public property, preference, setting, operator, dependency, overlay, or BMesh production path.
- Execute inline by default. Do not dispatch subagents or parallel writers
  without explicit user approval.
- Use ordinary RNA loops first because the generated diagnostic proved them correct. Record Preview timing before and after; stop for review rather than adding a second implementation if the established 25 percent same-machine gate is exceeded.
- Run the ignored private default-example smoke because this changes Preview behavior. Never commit its files, helper, names, face sets, or raw output.
- Rebuild and validate the ignored extension ZIP.

---

### Task 1: Reproduce and Fix Stale Preview Components

**Files:**
- Modify: `tests/blender/test_analysis_preview.py:1-110,449-594`
- Modify: `addon/operators/select_faces.py:145-205`

**Interfaces:**
- Preserves: `bpy.ops.alpha_material_separator.select_faces(...)`
- Preserves: `selection_mode` values `REPLACE`, `ADD`, and `SUBTRACT`
- Preserves: `enter_edit_mode=False` component-selection state
- Produces: selected Edit Mode edges and vertices that each belong to at least one selected face
- Produces: no selected component belonging exclusively to an unselected face

- [x] **Step 1: Add the generated three-face fixture and selection inspector**

Add `import bmesh` to `tests/blender/test_analysis_preview.py`.

Add a fixture with two adjacent quads and one disconnected quad. The left UV
half samples one affected texel; the other faces sample one opaque texel:

```python
def _preview_component_object(name: str):
    image = bpy.data.images.new(f"{name}_IMAGE", width=2, height=1, alpha=True)
    image.pixels.foreach_set(
        (1.0, 1.0, 1.0, 0.0, 1.0, 1.0, 1.0, 1.0)
    )
    material, _tree, _principled, _texture = _material(
        f"{name}_MATERIAL",
        image,
    )
    mesh = bpy.data.meshes.new(f"{name}_MESH")
    mesh.from_pydata(
        (
            (0, 0, 0),
            (1, 0, 0),
            (2, 0, 0),
            (0, 1, 0),
            (1, 1, 0),
            (2, 1, 0),
            (3, 0, 0),
            (4, 0, 0),
            (3, 1, 0),
            (4, 1, 0),
        ),
        (),
        ((0, 1, 4, 3), (1, 2, 5, 4), (6, 7, 9, 8)),
    )
    mesh.materials.append(material)
    uv_layer = mesh.uv_layers.new(name="UVMap", do_init=False)
    uv_layer.active_render = True
    coordinates = (
        ((0.0, 0.0), (0.5, 0.0), (0.5, 1.0), (0.0, 1.0)),
        ((0.5, 0.0), (1.0, 0.0), (1.0, 1.0), (0.5, 1.0)),
        ((0.5, 0.0), (1.0, 0.0), (1.0, 1.0), (0.5, 1.0)),
    )
    modern = getattr(uv_layer, "uv", None)
    for polygon in mesh.polygons:
        for offset, loop_index in enumerate(polygon.loop_indices):
            value = coordinates[polygon.index][offset]
            if modern is not None:
                modern[loop_index].vector = value
            else:
                uv_layer.data[loop_index].uv = value
    object_ = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(object_)
    object_.select_set(True)
    return object_
```

Add an Edit Mode assertion that permits shared boundaries but rejects stale
components belonging only to opaque faces:

```python
def _assert_face_derived_component_selection(object_, expected_faces):
    edit_mesh = bmesh.from_edit_mesh(object_.data)
    selected_faces = {face.index for face in edit_mesh.faces if face.select}
    assert selected_faces == set(expected_faces), selected_faces
    assert all(
        any(face.select for face in edge.link_faces)
        for edge in edit_mesh.edges
        if edge.select
    )
    assert all(
        any(face.select for face in vertex.link_faces)
        for vertex in edit_mesh.verts
        if vertex.select
    )
```

- [x] **Step 2: Add the failing real-operator regression**

Add `_preview_component_selection_test()` and call it from `run()` before the
existing analysis fixture:

```python
def _preview_component_selection_test():
    _clear_scene()
    first = _preview_component_object("AMS_PREVIEW_COMPONENT_A")
    second = _preview_component_object("AMS_PREVIEW_COMPONENT_B")
    bpy.context.view_layer.objects.active = first
    analyzed = bpy.ops.alpha_material_separator.analyze()
    state = bpy.context.window_manager.alpha_material_separator_api
    assert analyzed == {"FINISHED"}, state.last_status_json
    payload = json.loads(state.report_json)
    assert payload["counts"]["ALPHA_AFFECTED"] == 2, payload
    assert payload["counts"]["OPAQUE"] == 4, payload

    for object_ in (first, second):
        for vertex in object_.data.vertices:
            vertex.select = True
        for edge in object_.data.edges:
            edge.select = True
        for polygon in object_.data.polygons:
            polygon.select = True

    previewed = bpy.ops.alpha_material_separator.select_faces(
        expected_analysis_id=state.analysis_id,
        preview_assignment_plan=True,
        mixed_policy="TO_ALPHA",
        suppressed_policy="CANCEL_SOURCE_MATERIAL",
        unsupported_policy="TO_ALPHA",
        derived_conflict_policy="CANCEL_SOURCE_MATERIAL",
        selection_mode="REPLACE",
        enter_edit_mode=True,
    )
    assert previewed == {"FINISHED"}, state.last_status_json
    _assert_face_derived_component_selection(first, {0})
    _assert_face_derived_component_selection(second, {0})
```

Before leaving the helper, capture:

```python
    ui = bpy.context.window_manager.alpha_material_separator_ui
    reviewed = (ui.reviewed_analysis_id, ui.reviewed_policy_signature)
```

Repeat the same plan-derived Preview once from Edit Mode and assert the same
face-derived component state, unchanged `state.analysis_id`, and unchanged
`reviewed` tuple afterward.

- [x] **Step 3: Add selection-mode and compatibility regressions**

Use fresh one-object fixtures for these cases:

```python
cases = (
    ("REPLACE", {0, 1, 2}, {0}),
    ("ADD", {1}, {0, 1}),
    ("SUBTRACT", {0, 1, 2}, {1, 2}),
)
```

For each case, set the initial polygon set, preselect every edge and vertex,
run Preview for `{"ALPHA_AFFECTED"}`, and assert the expected final face set
and face-derived component state.

Add one `enter_edit_mode=False` case. Snapshot every vertex and edge selection
flag before Preview and assert those flags remain byte-for-byte equal afterward.

In the existing safe-plan Preview test, seed stale component flags on skipped
`first` and `shared` meshes and assert they remain unchanged while the target
`safe` object enters Edit Mode.

- [x] **Step 4: Run the headless suite and verify RED**

Run:

```powershell
$Blender52 = 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 --python tests/blender/run_all.py
```

Expected: fail in `_assert_face_derived_component_selection()` because the
current operator leaves selected edges or vertices whose linked faces are all
unselected. The reported polygon face sets must already match expectations,
proving the defect is component-only.

- [x] **Step 5: Record the pre-fix Preview timing**

Create ignored `.test-output/profile_preview_selection.py`. Generate a
50,000-polygon mesh with alternating alpha/opaque UV regions, seed all vertex
and edge flags, analyze once, then measure one discarded Preview warm-up and
five `REPLACE` Preview runs. Record the median locally without committing the
script or raw output.

- [x] **Step 6: Implement the minimal target-only normalization**

In `ALPHA_MATERIAL_SEPARATOR_OT_select_faces.execute()`, immediately after
obtaining `mesh` and before writing polygon selection, add:

```python
            if (
                self.enter_edit_mode
                and result.object.as_pointer() in target_pointers
            ):
                for vertex in mesh.vertices:
                    vertex.select = False
                for edge in mesh.edges:
                    edge.select = False
```

Do not clear components on non-target objects or when
`enter_edit_mode=False`. Leave all existing polygon selection logic and
`mesh.update()` placement unchanged.

- [x] **Step 7: Run the generated regression and complete headless suite**

Run:

```powershell
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 --python tests/blender/run_all.py
```

Expected: `ALPHA_MATERIAL_SEPARATOR_ANALYSIS_PREVIEW_TESTS_OK` and
`ALPHA_MATERIAL_SEPARATOR_BLENDER_TESTS_OK`. All three selection modes,
repeat Preview, multi-object Edit Mode, non-target preservation, and
`enter_edit_mode=False` compatibility pass.

- [x] **Step 8: Re-run the Preview timing**

Run the same ignored profiler with one discarded warm-up and five measurements.
Record the new median and component counts. If the same-machine Preview median
regresses by more than 25 percent, stop and present the evidence before trying
`foreach_set`, BMesh, or another implementation.

- [x] **Step 9: Commit the independently verified behavior**

Run:

```powershell
git add -- addon/operators/select_faces.py tests/blender/test_analysis_preview.py
git diff --cached --check
git diff --cached --name-only
git commit -m "fix: normalize preview component selection"
```

Expected: only the Preview operator and generated Blender regression are in the
commit.

---

### Task 2: Validate the Real Workflow and Document Preview Semantics

**Files:**
- Modify: `README.md:39-43,146-153`
- Modify: `docs/testing.md:120-156`
- Modify: `docs/HANDOFF.md`
- Modify ignored local helper:
  `.local-references/default-example/_validate_analysis.py`

**Interfaces:**
- Documents: Preview selects exact planned faces and derives component
  highlighting from those faces
- Documents: shared alpha/opaque boundary edges still highlight normally
- Preserves: private semantic lower-bound policy and immutable references

- [x] **Step 1: Extend the ignored private Preview smoke**

Before its Preview call, seed selected vertex and edge flags on every eligible
target mesh. After Preview enters multi-object Edit Mode, inspect each target
through BMesh and assert:

```python
assert all(
    any(face.select for face in edge.link_faces)
    for edge in edit_mesh.edges
    if edge.select
)
assert all(
    any(face.select for face in vertex.link_faces)
    for vertex in edit_mesh.verts
    if vertex.select
)
```

Continue asserting that the selected face set equals assignment plan `P`.
Do not emit object/material names, raw component sets, private paths, or graph
details.

- [x] **Step 2: Run the private before/after smoke**

Run:

```powershell
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 `
  --python .local-references\default-example\_validate_analysis.py -- `
  .local-references\default-example\before.blend `
  .local-references\default-example\after.blend
```

Expected: the new component-selection gate, exact face plan, out-of-range UV,
assignment, preservation, and immutable-reference checks pass. The command may
end nonzero only for the already recorded 1,176-face `OPAQUE` semantic
lower-bound discrepancy; any additional mismatch is a regression.

- [x] **Step 3: Update end-user and testing documentation**

In `README.md`, add:

```markdown
Preview clears unrelated edge and vertex selections before entering face-select
Edit Mode, so highlighted components come from the faces being previewed. An
edge shared by a selected alpha face and an opaque neighbor still highlights
because it belongs to the selected face.
```

In `docs/testing.md`, add and execute an interactive checklist item:

```markdown
- [ ] Preselect edges and vertices on adjacent and disconnected opaque faces,
  run Preview, and confirm only components belonging to selected faces remain
  highlighted. Confirm a shared selected/unselected boundary edge remains
  highlighted normally.
```

Mark it complete only after running the installed-ZIP interaction.

- [x] **Step 4: Run the complete change gate**

Run:

```powershell
$Python52 = 'C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe'
& $Python52 -m unittest discover -s tests/unit -t . -v
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 --python tests/blender/run_all.py
& $Blender52 --factory-startup --command extension validate addon
git diff --check
```

Expected: every unit test passes, the Blender runner reaches
`ALPHA_MATERIAL_SEPARATOR_BLENDER_TESTS_OK`, source validation succeeds, and
`git diff --check` reports no whitespace errors.

- [x] **Step 5: Build and validate the installable ZIP**

Run:

```powershell
.\scripts\build_extension.ps1 -Blender $Blender52
$Archive = (Resolve-Path `
  .\.packaged-releases\alpha_material_separator-0.1.0.zip).Path
& $Blender52 --factory-startup --command extension validate $Archive
Get-Item -LiteralPath $Archive | Select-Object FullName,Length
Get-FileHash -Algorithm SHA256 -LiteralPath $Archive
```

Expected: source and archive validation pass. Record the ignored archive size
and SHA-256 in `docs/HANDOFF.md`.

- [x] **Step 6: Perform installed-ZIP visual acceptance**

Using an isolated Blender 5.2 profile and generated three-face fixture:

1. Select all vertices and edges in Edit Mode.
2. Return to Object Mode and run Analyze.
3. Run **Preview Faces to Move**.
4. Confirm the affected face and its boundary components are highlighted.
5. Confirm the disconnected opaque face has no highlighted component.
6. Confirm the shared boundary with the adjacent opaque face remains
   highlighted.
7. Repeat Preview and verify the same result.
8. Apply and confirm the face/material result is unchanged.

Record the interaction in `docs/testing.md`; do not mark it complete from a
headless test alone.

- [x] **Step 7: Update the handoff and commit documentation**

Update `docs/HANDOFF.md` with the root cause, implementation commit, RED/GREEN
commands, Preview medians, private-smoke status, archive hash, installed-ZIP
result, known warnings, remaining tasks, and the next action.

Run:

```powershell
git add -- README.md docs/testing.md docs/HANDOFF.md `
  docs/superpowers/plans/2026-07-29-preview-component-selection-normalization.md
git diff --cached --check
git diff --cached --name-only
git commit -m "docs: document normalized face preview"
git status --short
```

Expected: only public documentation, the completed plan record, and handoff are
in the documentation commit. The working tree is clean; private helpers,
generated outputs, and the ZIP remain ignored and uncommitted.
