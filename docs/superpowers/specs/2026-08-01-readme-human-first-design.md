# Human-first README redesign

Date: 2026-08-01

## Objective

Rewrite `README.md` as a concise end-user guide that complements Blender's
guided Analyze → Review → Apply interface. The README should help a new user
install the extension, complete the default workflow, understand the result,
recover from common problems, and find deeper documentation without reading
implementation details.

## Audience and scope

The README is for extension users, not repository maintainers. Developer
commands, repository-local paths, contributor conventions, CI details, and
private-reference guidance belong under `docs/` and appear in the README only
as links when useful.

The extension is presented as a general tool for separating opaque and
alpha-affected faces into material sections. The README must not name Unity or
VRChat or frame one downstream renderer as the primary use case.

## Information architecture

Use this order:

1. **What it does**
   - Explain the resulting source and `__AMS_ALPHA` material sections.
   - State that the object remains one object and geometry is not cut.
2. **Install**
   - Require Blender 5.2 LTS.
   - Give ZIP installation steps and the exact **3D View → N → AMS** location.
3. **Quick start**
   - Select meshes.
   - Run **Analyze Selected Meshes**.
   - Optionally run **Preview Faces to Move**.
   - Run **Apply Material Separation** and inspect the result.
4. **Understanding the results**
   - Retain the five plain-language outcomes and their default actions in one
     compact table.
5. **When a material needs help**
   - Explain the collapsed **Material Details** area and
     **Set Manual Alpha Source**.
   - Give only the minimum image, channel, UV, and addressing guidance needed
     to recover.
   - Link the complete material-support matrix for node-pattern details.
6. **Safety, undo, and reruns**
   - Distinguish the effects of Analyze, Preview, and Apply.
   - Explain undo, confirmed stale inputs, safe skips, optional Preview, and
     idempotent reruns.
7. **After export**
   - Describe the source material as the opaque candidate and `__AMS_ALPHA` as
     the alpha-capable candidate.
   - State that downstream renderer configuration remains manual.
   - Note that a separate material section may reduce transparent rendering
     work while adding a draw call.
   - Note that Blender image alpha cannot reproduce every target renderer's
     filtering, compression, clipping, or shader behavior.
8. **Troubleshooting**
   - Keep only common user-facing symptoms and direct remedies.
   - Refer rare or technical cases to deeper documentation.
9. **More documentation**
   - Link material support, testing/contributing, integration API, and
     performance documentation.
10. **License**
    - Retain `GPL-3.0-or-later` and the canonical `LICENSE` link.

## Presentation rules

- Keep the basics basic; do not duplicate explanations already presented by
  the Blender panel.
- Prefer short paragraphs, numbered actions, and one compact outcome table.
- Keep only the Simple-panel screenshot in the README.
- Use the final UI labels exactly.
- Describe advanced behavior in plain language before linking technical docs.
- Remove the developer command block and repository-local conventions,
  including `.packaged-releases/` and `.local-references/`.
- Remove explicit Unity and VRChat mentions from the README.

## Accuracy requirements

The shorter README must still state:

- Version `1.0.0` targets Blender 5.2 LTS.
- Analyze may switch Mesh Edit Mode to Object Mode.
- Preview is optional and changes selection only.
- Apply without a matching Preview asks for confirmation.
- Supported material groups can proceed when unrelated groups remain
  unresolved.
- UV coordinates outside 0–1 are analyzable through the chosen addressing
  mode.
- Analyze does not persistently change mesh or material data.
- Apply changes only planned material slots and polygon material assignments.
- Source shaders, topology, rigging, UVs, images, and unselected objects are
  preserved.
- Repeated runs reuse valid derived materials and slots.
- A confirmed classification-input change requires analysis again.

## Verification

Update `tests/unit/test_readme_contract.py` before rewriting the README:

- Replace the old long section-order contract with the approved concise
  structure.
- Preserve exact installation and workflow-label checks.
- Preserve release identity, safety, partial-apply, optional-preview,
  out-of-range UV, stale-result, and friendly-status requirements.
- Reject explicit `Unity`, `VRChat`, `.packaged-releases/`, and
  `.local-references/` text.
- Verify every relative link resolves within the repository.

Run the focused README contract, the complete unit suite, and
`git diff --check`. No Blender or private-reference smoke is required because
this change affects documentation presentation only.
