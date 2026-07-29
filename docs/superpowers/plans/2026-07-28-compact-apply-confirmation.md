# Compact Apply Confirmation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the unbounded Apply warning dialog with the approved count-only Option B summary while preserving exact preflight validation and assignment safety.

**Architecture:** Extend the existing assignment-plan payload with the two missing action-specific counts, then generate all confirmation sentences in one pure presentation helper. The Blender operator will draw only those bounded sentences in a native 420-pixel dialog; detailed names remain in Review and Material Details.

**Tech Stack:** Python 3.11, Blender 5.2 RNA/UI API, `unittest`, headless Blender integration tests, PowerShell packaging scripts.

## Global Constraints

- Preserve extension version `0.1.0`, public API `1.2`, operator IDs, classifications, policies, and scripted execution behavior.
- Every displayed number must describe an exact assignment-plan outcome, never a broad report total.
- The popup must contain no object, material, image, UV, or destination names.
- Keep the existing confirmation trigger, mandatory guided Preview, plan fingerprint, synchronous revalidation, atomic undo, and idempotence.
- Use Blender's native `invoke_props_dialog`; add no persistent state, operator, dependency, disclosure, search, pagination, or network behavior.
- Preserve topology, source shaders/materials, images, UVs, rigging, modifiers, parenting, and unselected objects.
- Keep private files, names, paths, raw output, and packaged ZIPs uncommitted.
- Work on `feat/alpha-material-separator-0.1`; create local commits only and do not push.

---

### Task 1: Add exact mixed and suppressed assignment outcomes

**Files:**
- Modify: `addon/adapters/assignment.py:35-185, 410-500`
- Test: `tests/blender/test_assignment_policies.py:70-180`

**Interfaces:**
- Consumes: existing `MaterialGroupAnalysis.face_indices`, active assignment policies, and final derived-material decisions.
- Produces: additive plan payload integers `mixed_faces_to_alpha` and `suppressed_faces_to_alpha`.

- [ ] **Step 1: Add failing suppressed-outcome assertions**

Immediately after the generated suppressed analysis in `run()`, build both policy plans and assert that only the plan moving the face reports it:

```python
suppressed_report = runtime.report(state.analysis_id)
suppressed_blocked_plan = build_assignment_plan(
    suppressed_report,
    mixed_policy="TO_ALPHA",
    suppressed_policy="CANCEL_SOURCE_MATERIAL",
    unsupported_policy="TO_ALPHA",
    conflict_policy="CANCEL_SOURCE_MATERIAL",
)
suppressed_move_plan = build_assignment_plan(
    suppressed_report,
    mixed_policy="TO_ALPHA",
    suppressed_policy="TO_ALPHA",
    unsupported_policy="TO_ALPHA",
    conflict_policy="CANCEL_SOURCE_MATERIAL",
)
assert suppressed_blocked_plan.public_payload()["suppressed_faces_to_alpha"] == 0
assert suppressed_move_plan.public_payload()["suppressed_faces_to_alpha"] == 1
```

- [ ] **Step 2: Add failing mixed-outcome assertions**

In the generated partial-material scenario, assert the actionable plan counts its one moved mixed face while the source-wide blocked plan does not:

```python
assert public_plan["mixed_faces_to_alpha"] == 1, public_plan
assert public_plan["suppressed_faces_to_alpha"] == 0, public_plan
blocked_payload = blocked_plan.public_payload()
assert blocked_payload["mixed_faces_to_alpha"] == 0, blocked_payload
```

- [ ] **Step 3: Run the Blender suite and verify RED**

Run:

```powershell
$Blender52 = 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 --python tests/blender/run_all.py
```

Expected: fail with `KeyError: 'suppressed_faces_to_alpha'` or `KeyError: 'mixed_faces_to_alpha'`.

- [ ] **Step 4: Store the two counts on each group disposition**

Add fields and public payload entries to `GroupDisposition`:

```python
mixed_to_alpha: int = 0
suppressed_to_alpha: int = 0

# In public_payload():
"mixed_to_alpha": self.mixed_to_alpha,
"suppressed_to_alpha": self.suppressed_to_alpha,
```

When constructing `face_indices`, derive the counts from the exact group lists:

```python
mixed_to_alpha = 0
suppressed_to_alpha = 0
if mixed_policy == "TO_ALPHA":
    mixed_faces = group.face_indices[FaceClass.MIXED]
    face_indices.extend(mixed_faces)
    mixed_to_alpha = len(mixed_faces)
elif mixed_policy == "KEEP_SOURCE":
    retained_by_policy += len(group.face_indices[FaceClass.MIXED])
if suppressed_policy == "TO_ALPHA":
    suppressed_faces = group.face_indices[FaceClass.SUPPRESSED]
    face_indices.extend(suppressed_faces)
    suppressed_to_alpha = len(suppressed_faces)
elif suppressed_policy == "KEEP_SOURCE":
    retained_by_policy += len(group.face_indices[FaceClass.SUPPRESSED])
```

Pass `mixed_to_alpha` and `suppressed_to_alpha` into the actionable
`GroupDisposition`. Leave them at zero for unchanged, already-separated, and
initially blocked dispositions.

- [ ] **Step 5: Clear action counts when derived-material preflight blocks a source**

Extend the existing decision-block reconciliation:

```python
disposition.faces_to_alpha = 0
disposition.uncertain_to_alpha = 0
disposition.mixed_to_alpha = 0
disposition.suppressed_to_alpha = 0
disposition.faces_left_source = disposition.total_faces
disposition.retained_by_policy = 0
```

- [ ] **Step 6: Aggregate the additive plan fields**

Add to `AssignmentPlan.public_payload()`:

```python
"mixed_faces_to_alpha": sum(
    item.mixed_to_alpha for item in self.dispositions
),
"suppressed_faces_to_alpha": sum(
    item.suppressed_to_alpha for item in self.dispositions
),
```

- [ ] **Step 7: Run the Blender suite and verify GREEN**

Run the command from Step 3. Expected: the complete Blender suite prints
`ALPHA_MATERIAL_SEPARATOR_BLENDER_TESTS_OK` and exits zero.

### Task 2: Generate the bounded count-only copy

**Files:**
- Modify: `addon/presentation.py:114-260`
- Test: `tests/unit/test_presentation.py:7-190`

**Interfaces:**
- Consumes: the JSON-compatible `AssignmentPlan.public_payload()` dictionary.
- Produces: `assignment_confirmation_lines(plan_payload: dict) -> tuple[str, ...]`.

- [ ] **Step 1: Add the failing representative-copy test**

Import `assignment_confirmation_lines` and add:

```python
def test_compact_assignment_confirmation_representative_copy(self) -> None:
    lines = assignment_confirmation_lines(
        {
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
    )
    self.assertEqual(
        lines,
        (
            "Move 65,775 reviewed faces to alpha materials and add 29 material slots.",
            "This includes 57,731 mixed faces and 2,577 uncertain faces.",
            "23 unresolved material groups will remain unchanged.",
            (
                "Only material slots and face assignments change—no topology "
                "or source shader changes. Ctrl+Z to undo."
            ),
        ),
    )
```

- [ ] **Step 2: Add failing adaptive and privacy tests**

Add:

```python
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
        "dispositions": [{"object": "PRIVATE_OBJECT", "material": "PRIVATE_MATERIAL"}],
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
```

- [ ] **Step 3: Run the focused unit test and verify RED**

Run:

```powershell
$Python52 = 'C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe'
& $Python52 -m unittest tests.unit.test_presentation -v
```

Expected: fail because `assignment_confirmation_lines` does not exist.

- [ ] **Step 4: Implement the pure sentence generator**

Add to `addon/presentation.py`:

```python
def _counted(count: int, singular: str, plural: str | None = None) -> str:
    word = singular if count == 1 else (plural or f"{singular}s")
    return f"{count:,} {word}"


def assignment_confirmation_lines(plan_payload: dict) -> tuple[str, ...]:
    faces = int(plan_payload.get("faces_to_reassign", 0))
    slots = int(plan_payload.get("planned_additional_slots", 0))
    mixed = int(plan_payload.get("mixed_faces_to_alpha", 0))
    uncertain = int(plan_payload.get("face_local_unsupported_to_alpha", 0))
    suppressed = int(plan_payload.get("suppressed_faces_to_alpha", 0))
    retained = int(plan_payload.get("retained_faces_by_policy", 0))
    unresolved = int(
        plan_payload.get("material_source_groups_left_unchanged", 0)
    )
    skipped_groups = int(plan_payload.get("skipped_material_groups", 0))
    skipped_objects = int(plan_payload.get("skipped_object_count", 0))
    lines = []

    action = ""
    if faces:
        destination = "an alpha material" if faces == 1 else "alpha materials"
        action = f"Move {_counted(faces, 'reviewed face')} to {destination}"
    if slots:
        slot_clause = f"add {_counted(slots, 'material slot')}"
        action = f"{action} and {slot_clause}" if action else slot_clause.capitalize()
    if action:
        lines.append(f"{action}.")

    included = []
    if mixed:
        included.append(_counted(mixed, "mixed face"))
    if uncertain:
        included.append(_counted(uncertain, "uncertain face"))
    if included:
        lines.append(f"This includes {' and '.join(included)}.")
    if suppressed:
        lines.append(
            f"Move {_counted(suppressed, 'below-significance face')} to alpha."
        )
    if retained:
        if retained == 1:
            lines.append(
                "1 reviewed face will remain on its source material by policy."
            )
        else:
            lines.append(
                f"{retained:,} reviewed faces will remain on their source "
                "materials by policy."
            )
    if unresolved:
        lines.append(
            f"{_counted(unresolved, 'unresolved material group')} "
            "will remain unchanged."
        )

    skipped = []
    if skipped_groups:
        skipped.append(_counted(skipped_groups, "material group"))
    if skipped_objects:
        skipped.append(_counted(skipped_objects, "object"))
    if skipped:
        lines.append(f"Skip {' and '.join(skipped)}.")

    lines.append(
        "Only material slots and face assignments change—no topology or "
        "source shader changes. Ctrl+Z to undo."
    )
    return tuple(lines)
```

- [ ] **Step 5: Run focused and full unit tests**

Run:

```powershell
& $Python52 -m unittest tests.unit.test_presentation -v
& $Python52 -m unittest discover -s tests/unit -t . -v
```

Expected: all tests pass.

### Task 3: Replace the unbounded Blender dialog

**Files:**
- Modify: `addon/operators/assign_materials.py:1-240`
- Modify: `tests/blender/test_assignment_policies.py`
- Modify: `tests/unit/test_readme_contract.py`

**Interfaces:**
- Consumes: `assignment_confirmation_lines(plan_payload)`.
- Produces: a native dialog with `width=420`, title `Apply Material Separation`, and confirm text `Apply`.

- [ ] **Step 1: Add failing dialog-contract assertions**

In `tests/blender/test_assignment_policies.py`, import the operator and constants:

```python
from addon.operators.assign_materials import (
    ALPHA_MATERIAL_SEPARATOR_OT_assign_materials,
    _CONFIRMATION_TEXT,
    _CONFIRMATION_TITLE,
    _CONFIRMATION_WIDTH,
)
```

Add:

```python
assert _CONFIRMATION_WIDTH == 420
assert _CONFIRMATION_TITLE == "Apply Material Separation"
assert _CONFIRMATION_TEXT == "Apply"
```

In `tests/unit/test_readme_contract.py`, add an operator-source contract:

```python
ASSIGN_OPERATOR = ROOT / "addon" / "operators" / "assign_materials.py"

def test_apply_confirmation_is_bounded_and_count_only(self) -> None:
    source = ASSIGN_OPERATOR.read_text(encoding="utf8")
    for required in (
        "assignment_confirmation_lines",
        "width=_CONFIRMATION_WIDTH",
        "title=_CONFIRMATION_TITLE",
        "confirm_text=_CONFIRMATION_TEXT",
    ):
        self.assertIn(required, source)
    for removed in (
        "Faces that could not be analyzed:",
        "Leave {disposition.get('material'",
        "for source, derived in sorted(destinations.items())",
        "f\"{disposition.get('object', 'Object')} / \"",
    ):
        self.assertNotIn(removed, source)
```

- [ ] **Step 2: Run focused tests and verify RED**

Run:

```powershell
& $Python52 -m unittest `
  tests.unit.test_readme_contract.ReadmeContractTests.test_apply_confirmation_is_bounded_and_count_only -v
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 --python tests/blender/run_all.py
```

Expected: the unit source contract fails and Blender import fails because the
confirmation constants do not exist.

- [ ] **Step 3: Replace the dialog drawing code**

In `addon/operators/assign_materials.py`:

```python
import textwrap

from ..presentation import (
    assignment_confirmation_lines,
    assignment_plan_signature,
    requires_confirmation,
    review_signature,
)

_CONFIRMATION_WIDTH = 420
_CONFIRMATION_TITLE = "Apply Material Separation"
_CONFIRMATION_TEXT = "Apply"
```

Remove `_confirmation_report_json`, stop serializing the report for drawing,
and replace the dialog call:

```python
return context.window_manager.invoke_props_dialog(
    self,
    width=_CONFIRMATION_WIDTH,
    title=_CONFIRMATION_TITLE,
    confirm_text=_CONFIRMATION_TEXT,
)
```

Replace `draw()` with:

```python
def draw(self, _context) -> None:
    plan = json.loads(self._confirmation_plan_json)
    lines = assignment_confirmation_lines(plan)
    for line in lines[:-1]:
        for wrapped in textwrap.wrap(
            line, width=52, break_long_words=False
        ) or ("",):
            self.layout.label(text=wrapped)
    self.layout.separator()
    for wrapped in textwrap.wrap(
        lines[-1], width=52, break_long_words=False
    ):
        self.layout.label(text=wrapped)
```

Delete the old report counts, object warnings, blocked-material list,
unchanged-material list, destination list, per-object/material face list, and
four-line footer.

- [ ] **Step 4: Add a real-plan cancel-boundary test**

Create a recording `WindowManager` proxy inside
`tests/blender/test_assignment_policies.py`:

```python
class _CancelledDialogWindowManager:
    def __init__(self, real):
        self._real = real
        self.options = None

    def __getattr__(self, name):
        return getattr(self._real, name)

    def invoke_props_dialog(self, _operator, **options):
        self.options = options
        return {"CANCELLED"}
```

For the generated actionable warning plan, instantiate the operator with its
reviewed analysis and signature, call `invoke()` using a
`SimpleNamespace(window_manager=proxy, object=bpy.context.object)`, and assert:

```python
indices_before = tuple(
    polygon.material_index for polygon in partial.data.polygons
)
slots_before = tuple(slot.material for slot in partial.material_slots)
cancelled = operator.invoke(proxy_context, None)
assert cancelled == {"CANCELLED"}
assert proxy.options == {
    "width": 420,
    "title": "Apply Material Separation",
    "confirm_text": "Apply",
}
assert tuple(
    polygon.material_index for polygon in partial.data.polygons
) == indices_before
assert tuple(slot.material for slot in partial.material_slots) == slots_before
```

Use the existing `review_signature(..., plan.public_payload())` helper to set
`operator.expected_review_signature`, so this exercises the real report,
validation, plan construction, and review equivalence before the native dialog
boundary.

- [ ] **Step 5: Run focused and complete automated tests**

Run:

```powershell
& $Python52 -m unittest discover -s tests/unit -t . -v
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 --python tests/blender/run_all.py
```

Expected: all unit tests and the complete Blender suite pass, including the
existing preflight-change, partial-success, undo/redo, idempotence,
preservation, and registration checks.

### Task 4: Documentation, private smoke, and package

**Files:**
- Modify: `README.md`
- Modify: `docs/testing.md`
- Modify: `docs/HANDOFF.md`
- Modify locally only: `.local-references/default-example/_diagnose_rerun_tooltip.py`

**Interfaces:**
- Documents: the count-only confirmation and where detailed names remain.
- Produces locally: validated `.packaged-releases/alpha_material_separator-0.1.0.zip`.

- [ ] **Step 1: Update end-user documentation**

In the README's Simple workflow and troubleshooting sections, state:

```markdown
When confirmation is required, the popup reports only aggregate assignment
outcomes. Object, material, image, UV, and destination details remain under
Review → Material Details.
```

Update `docs/testing.md` with unchecked manual acceptance items for the compact
popup at narrow/wide layouts and 100%/150% UI scale. Do not mark an interaction
complete until it has actually been performed.

- [ ] **Step 2: Extend the ignored before/after smoke**

Update the ignored helper to call `assignment_confirmation_lines(plan_payload)`
for both private files, collect all private object/material names internally,
and assert:

```python
summary = "\n".join(assignment_confirmation_lines(plan.public_payload()))
assert len(assignment_confirmation_lines(plan.public_payload())) <= 7
assert not any(name and name in summary for name in private_names)
assert plan.public_payload()["faces_to_reassign"] == sum(
    len(mutation.face_indices) for mutation in plan.mutations
)
```

Print only anonymous counts such as `summary_rows`, `faces_to_reassign`,
`unchanged_groups`, `skipped_groups`, and `skipped_objects`.

- [ ] **Step 3: Run both private smokes**

Run:

```powershell
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 `
  --python .local-references\default-example\_diagnose_rerun_tooltip.py -- `
  .local-references\default-example\before.blend
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 `
  --python .local-references\default-example\_diagnose_rerun_tooltip.py -- `
  .local-references\default-example\after.blend
```

Expected: both analyze all eligible meshes, emit only anonymized aggregates,
keep the summary at seven or fewer semantic rows, and leave both files
unchanged.

- [ ] **Step 4: Validate and rebuild the extension**

Run:

```powershell
& $Blender52 --factory-startup --command extension validate addon
& $Blender52 --factory-startup --command extension build `
  --source-dir addon --output-dir .packaged-releases
$Archive = (Resolve-Path `
  .\.packaged-releases\alpha_material_separator-0.1.0.zip).Path
& $Blender52 --factory-startup --command extension validate $Archive
Get-FileHash -Algorithm SHA256 $Archive
git diff --check
```

Expected: source validation, build, and archive validation succeed; record the
archive size/hash. `git diff --check` may report only the repository's existing
LF-to-CRLF checkout warnings.

- [ ] **Step 5: Perform installed-ZIP visual acceptance**

In a clean Blender 5.2 configuration:

1. Install the rebuilt ZIP.
2. Use a generated warning plan and the lawful private messy example.
3. Confirm the popup title is **Apply Material Separation** and the positive
   action is **Apply**.
4. Confirm the popup contains only counts and bounded prose, with no names or
   destination pairs.
5. Inspect at narrow/wide layouts and 100%/150% UI scale.
6. Cancel and verify zero changes.
7. Open again, Apply, verify exact reviewed changes, then press Ctrl+Z.

- [ ] **Step 6: Update the handoff and create local commits**

Record the RED/GREEN evidence, exact commands, private aggregate status, manual
visual status, package hash, known warnings, and next action in
`docs/HANDOFF.md`.

Create coherent local commits only after the corresponding gates pass:

```powershell
git add addon/adapters/assignment.py addon/presentation.py `
  addon/operators/assign_materials.py tests/unit/test_presentation.py `
  tests/unit/test_readme_contract.py tests/blender/test_assignment_policies.py
git commit -m "feat: compact the apply confirmation"

git add README.md docs/testing.md docs/HANDOFF.md `
  docs/superpowers/plans/2026-07-28-compact-apply-confirmation.md
git commit -m "docs: document compact apply confirmation"
```

Do not stage the ignored private helper, private assets, packaged ZIP,
`.test-output`, or raw smoke output. Do not push.
