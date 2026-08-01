# Human-first README Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the dense multipurpose README with a concise,
renderer-agnostic end-user guide that relies on Blender's guided interface and
links developer material under `docs/`.

**Architecture:** Keep `README.md` as the single public entry point for
installation, the default workflow, result interpretation, safety, and common
recovery. Preserve deeper material, testing, integration, and performance
information in their existing focused documents. Use the existing README
contract test to protect essential user promises without locking prose to one
exact wording.

**Tech Stack:** Markdown, Python standard-library `unittest`, regular
expressions, Git.

## Global Constraints

- Version remains `1.0.0`; Blender target remains 5.2 LTS.
- Preserve the final UI labels exactly: **Analyze Selected Meshes**,
  **Preview Faces to Move**, **Apply Material Separation**,
  **Material Details**, and **Set Manual Alpha Source**.
- The README must not contain `Unity`, `VRChat`, `.packaged-releases/`, or
  `.local-references/`.
- The README is for end users. Developer commands and repository conventions
  remain under `docs/` and are linked rather than repeated.
- Keep only `docs/images/01-panel-simple.png` in the README.
- Preserve `GPL-3.0-or-later` and the canonical `LICENSE` link.
- Do not change extension behavior, source code, UI, screenshots, or public
  API.
- This documentation-only change requires no Blender or private-reference
  smoke.

---

### Task 1: Rewrite and verify the end-user README

**Files:**
- Modify: `tests/unit/test_readme_contract.py`
- Modify: `README.md`
- Modify after verification: `docs/HANDOFF.md`

**Interfaces:**
- Consumes: the final UI labels and behavior already implemented by the
  extension.
- Produces: a concise public README and a semantic documentation contract.

- [x] **Step 1: Replace the old README structure contract with a failing concise contract**

In `tests/unit/test_readme_contract.py`, keep the existing relative-link
validation and the essential release, workflow, safety, partial-apply,
optional-preview, out-of-range UV, stale-result, and friendly-status checks.
Make these focused changes:

```python
def test_end_user_sections_exist_in_order(self) -> None:
    headings = (
        "What it does",
        "Install",
        "Quick start",
        "Understanding the results",
        "When a material needs help",
        "Safety, undo, and reruns",
        "After export",
        "Troubleshooting",
        "More documentation",
        "License",
    )
    positions = [self.text.index(f"## {heading}") for heading in headings]
    self.assertEqual(positions, sorted(positions))


def test_readme_excludes_renderer_and_repository_specific_copy(self) -> None:
    for text in (
        "Unity",
        "VRChat",
        ".packaged-releases/",
        ".local-references/",
        "## Developer documentation",
    ):
        self.assertNotIn(text, self.text)


def test_readme_uses_one_screenshot_and_links_deeper_docs(self) -> None:
    images = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", self.text)
    self.assertEqual(images, ["docs/images/01-panel-simple.png"])
    for target in (
        "docs/material-support.md",
        "docs/testing.md",
        "docs/integration-api.md",
        "docs/performance.md",
    ):
        self.assertIn(f"]({target})", self.text)
```

Update `test_defaults_and_safety_caveats_are_documented` so it no longer
requires `Unity`, while retaining:

```python
for text in (
    "Blender 5.2",
    "one object",
    "does not cut geometry",
    "Ctrl+Z",
    "draw call",
    "per-material",
    "UV coordinates may be below 0 or above 1",
):
    self.assertIn(text, self.text)
```

Keep the existing exact checks for:

```text
3D View
open the **AMS** tab
Analyze Selected Meshes
Preview Faces to Move
Apply Material Separation
Material Details
Simple
Expert
Version 1.0.0 targets Blender 5.2 LTS.
alpha_material_separator-1.0.0.zip
Preview is recommended but optional
Apply without Preview always asks for confirmation
Assignment-only plan changes require confirmation, not another analysis
Inputs Changed — Analyze Again
Left unchanged — no alpha source selected
Already separated — no additional changes
```

- [x] **Step 2: Run the focused contract and verify RED**

Run:

```powershell
$Python52 = 'C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe'
& $Python52 -m unittest tests.unit.test_readme_contract -v
```

Expected: FAIL because the old README uses the old headings, contains
renderer-specific names and repository-local paths, and embeds four
screenshots.

- [x] **Step 3: Rewrite `README.md` with the approved compact structure**

Use these exact section headings in order:

```markdown
## What it does
## Install
## Quick start
## Understanding the results
## When a material needs help
## Safety, undo, and reruns
## After export
## Troubleshooting
## More documentation
## License
```

Apply these content boundaries:

- **What it does:** two short paragraphs. Explain that opaque faces remain on
  the source material, alpha-affected faces use `__AMS_ALPHA`, the result is
  one object with multiple material sections, and geometry is not cut.
- **Install:** retain the exact ZIP filename, Blender 5.2 installation steps,
  **3D View → N → AMS** location, and save-before-processing advice.
- **Quick start:** use four numbered actions: select, analyze, optionally
  preview, and apply. Mention that Analyze may leave Edit Mode, Material
  Details is normally collapsed, Preview changes selection only, Apply without
  Preview confirms, and supported materials proceed independently.
- **Understanding the results:** retain one three-column table for the five
  plain-language classifications and their default actions.
- **When a material needs help:** explain the advisory, Material Details, and
  Set Manual Alpha Source. Summarize per-material image/channel/UV/addressing
  selection in no more than two short paragraphs plus four compact bullets.
  State that UV coordinates may be below 0 or above 1. Link the material
  support matrix instead of listing automatic node patterns.
- **Safety, undo, and reruns:** use compact bullets for Analyze, Preview, and
  Apply. State preservation guarantees, `Ctrl+Z`, safe skips, idempotence,
  confirmed stale-input behavior, and assignment-only confirmation without
  reanalysis.
- **After export:** use renderer-agnostic language. Explain source and
  `__AMS_ALPHA` roles, manual downstream material configuration, possible
  transparent-work reduction versus an additional material section/draw call,
  and rendering differences caused by filtering, compression, clipping, or
  shaders.
- **Troubleshooting:** retain only these common symptoms with one-sentence
  remedies:
  - no mesh selected;
  - no clear alpha image;
  - unsupported alpha processing;
  - no active render UV;
  - inputs changed;
  - uncertain faces use alpha;
  - unresolved material left unchanged;
  - shared/linked/read-only data;
  - already separated;
  - slow analysis or cancellation.
- **More documentation:** link only the material-support matrix, testing and
  contributing guide, integration API, and performance guide.
- **License:** retain the exact SPDX expression and `LICENSE` link.

Delete:

- the detailed Simple-versus-Expert settings inventory;
- the long automatic resolver implementation explanation;
- the extended stale-cache internals;
- technical codes and rare troubleshooting cases;
- renderer/product-specific names and links;
- the developer command block;
- repository-local path conventions;
- three nonessential screenshots.

- [x] **Step 4: Run the focused contract and verify GREEN**

Run:

```powershell
& $Python52 -m unittest tests.unit.test_readme_contract -v
```

Expected: all README contract tests pass.

- [x] **Step 5: Run the complete documentation change gate**

Run:

```powershell
& $Python52 -m unittest discover -s tests/unit -t . -v
git diff --check
```

Expected: all unit tests pass and Git reports no whitespace errors.

- [x] **Step 6: Review the rendered source and commit the rewrite**

Check:

```powershell
git diff -- README.md tests/unit/test_readme_contract.py
git status --short
```

Confirm that the README contains only one image, every relative link resolves,
the forbidden strings are absent, and no unrelated file is staged. Then:

```powershell
git add -- README.md tests/unit/test_readme_contract.py
git diff --cached --check
git commit -m "docs: simplify the end-user README"
```

- [x] **Step 7: Update the handoff and commit it separately**

Update `docs/HANDOFF.md` with:

- the README commit hash;
- the exact focused RED and GREEN results;
- the complete unit-test count;
- confirmation that `git diff --check` passed;
- the remaining CI push/hosted-run boundary;
- the next recommended action.

Then run and commit:

```powershell
git diff --check -- docs/HANDOFF.md
git add -- docs/HANDOFF.md
git diff --cached --check
git commit -m "docs: hand off README simplification"
git status --short
```

Expected: a clean working tree. Do not push.
