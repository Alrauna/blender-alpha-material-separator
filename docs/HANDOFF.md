# Repository handoff

Updated: 2026-08-07

## Current objective

Land `feat/credits-support-panel-1.1.1`, then finish the installed-ZIP
interactive acceptance.

## In flight: 1.1.1 on feat/credits-support-panel-1.1.1

Four commits, verified locally, not yet pushed.

- `addon/manifest.py` is a new bpy-free reader for the packaged manifest. It
  reads once, degrades to empty values rather than raising, and applies the
  Windows extended-length prefix because an installed extension can sit past
  `MAX_PATH` where a plain path will not open.
- `EXTENSION_VERSION` in `addon/api_contract.py` is now derived from that module
  instead of hand-edited. **A release now edits `addon/blender_manifest.toml`
  and `README.md` only.** That was proved rather than assumed: bumping the
  manifest alone left `test_api_contract` passing untouched and failed only
  `test_readme_contract`.
- `ALPHA_MATERIAL_SEPARATOR_PT_credits` is a new Credits & Support panel above
  the workflow panel, showing version, maintainer, and issue tracker from the
  manifest. Ordering is explicit through `bl_order` on both panels rather than
  relying on registration order. It uses the built-in `wm.url_open`, so there is
  no new operator and no icon system.
- The second box in that panel deliberately repeats the issue tracker. It is a
  placeholder for a Discord link that does not exist yet, and a comment in
  `addon/panel.py` says so.
- The manifest is confirmed present at the root of the built archive, which is
  what the panel reads once installed.

Verified on this branch: 101 unit tests, headless suite exit 0 with 15 markers
including `ALPHA_MATERIAL_SEPARATOR_CREDITS_PANEL_TESTS_OK`, source validation,
and `alpha_material_separator-1.1.1.zip` built and validated.

The user installed that archive and confirmed the panel reads correctly, which
closes the 1.1.1 interactive acceptance for this scope.
`docs/superpowers/plans/2026-08-07-credits-support-panel.md` is deleted as the
last step of the milestone; git history retains the approved wording.

## State

`main` is at `1ed2a22`. There are no open pull requests, no other branches
local or remote, and no unpushed work. Release `v1.1.0` is published from
`098f13c` with `alpha_material_separator-1.1.0.zip` and `SHA256SUMS.txt`.

Four pull requests merged after that release, but none of them touched
`addon/`. The published artifact is therefore still byte-identical to the
current `addon/` tree, so no re-release is needed:

- [#6](https://github.com/Alrauna/blender-alpha-material-separator/pull/6)
  removed `docs/superpowers/` and two orphaned files after a repository-wide
  over-engineering audit.
- [#8](https://github.com/Alrauna/blender-alpha-material-separator/pull/8)
  documented 1.1.0 and made `test_readme_contract.py` derive the version from
  the manifest instead of hardcoding it.
- [#9](https://github.com/Alrauna/blender-alpha-material-separator/pull/9)
  stated the overdraw purpose in plain English in the README and `AGENTS.md`.
- [#10](https://github.com/Alrauna/blender-alpha-material-separator/pull/10)
  refreshed `AGENTS.md` against reality and removed hardcoded versions from the
  remaining documents.

The 1.1.0 behavior work itself landed in
[#4](https://github.com/Alrauna/blender-alpha-material-separator/pull/4):
below-significance faces now default to `KEEP_SOURCE` instead of cancelling
their whole material group, the seven Expert analysis tooltips are written for
artists, the panel has a Reset to Default Values button, and Minimum Affected
Pixels no longer offers a value that does nothing.

## Important decisions and constraints

- `EXTENSION_VERSION` in `addon/api_contract.py` is derived from
  `addon/blender_manifest.toml` as of this branch, so a release edits the
  manifest and `README.md` only. `tests/unit/test_api_contract.py` still
  cross-checks the two, which is what caught the hand-edited mismatch during the
  1.1.0 bump.
- `README.md` is the only document that names a version, and
  `tests/unit/test_readme_contract.py` derives that version from the manifest.
  Keep other documents version-neutral rather than bumping them each release.
- The TLS autofix in `quad9_addresses` stays as it is, with no retroactive
  regression test, by explicit user decision. Revisit only when further CI/CD
  work is required.
- The GitHub Advanced Security "Code scanning AI findings" run fails on every
  pull request with `400 The requested model is not supported`. It is a
  GitHub-side model availability problem inside Copilot Autofix, it fails before
  analyzing anything, and it is not a required check. Ignore it; do not change
  code to satisfy it.
- Do not push, merge, tag, release, or change repository settings without
  explicit approval.

## Validation commands and results

Run on 2026-08-05 with Blender 5.2.0 LTS and its bundled Python 3.13.13, on
`main` content:

- 95 unit tests passed.
- The headless Blender suite exited 0 with every completion marker, including
  `ALPHA_MATERIAL_SEPARATOR_SIGNIFICANCE_TESTS_OK` and
  `ALPHA_MATERIAL_SEPARATOR_EXPERT_SETTINGS_TESTS_OK`.
- Source validation succeeded, and a cleared `.packaged-releases` produced
  exactly one archive that validated.
- The benchmark suite exited 0 and wrote `.test-output/benchmarks/baseline.json`
  after more than ten minutes. That directory is ignored, so the baseline does
  not survive into another session.
- `git diff --check` reported no whitespace errors.

The private `.local-references/default-example/` acceptance was run with the
ignored helper in that directory, against both the 1.1.0 branch and the
pre-change `main`. Both runs succeeded and produced an identical aggregate
result, which is the expected outcome: the default `min_affected_texels` of 1
never suppresses a face, so the `KEEP_SOURCE` default has nothing to act on
until a significance gate is deliberately raised. Faces whose UVs fall outside
the base tile were analyzed rather than rejected. Aggregate counts, raw output,
and identifying detail are deliberately not recorded here.

## Known warnings and unverified assumptions

- No known failures.
- A large share of faces in the private example report `UNSUPPORTED`. That share
  was identical before and after the 1.1.0 change, so it is not a regression,
  but it is unexplained and worth a separate investigation into whether those
  materials are genuinely unresolvable or the resolver has a gap.
- Expected local output includes LF-to-CRLF Git notices.

## Remaining tasks

Finish the installed-ZIP interactive acceptance. The user installed
`alpha_material_separator-1.1.0.zip`, restarted Blender, exercised the rewritten
Expert analysis tooltips on hover, and reported that the build feels good to
use. Still unconfirmed in the installed build:

- Analyze → Preview → Tab to Object Mode → Apply without a second analysis.
- A below-significance face reporting under `Faces kept by policy` rather than
  blocking its material group.
- Reset to Default Values against an existing analysis reporting that inputs
  changed.
- Minimum Affected Pixels refusing to go below 1, with 2 still filtering.

The 1.1.1 credits panel is confirmed in an installed build: it appears above
Alpha Material Separator, and version, maintainer, and the issue-tracker button
all read correctly.

## Follow-up work, not started

Two separate objectives came out of 1.1.1 testing. Neither belongs on the
credits-panel branch.

**Manual alpha source usability.** The Image field is a real image-ID selector,
but the flow dead-ends. An override carrying a material and no image resolves
through the automatic path that already failed, so `Set Manual Alpha Source`
followed by Analyze reports the identical failure; the field that must be filled
lives in a `DEFAULT_CLOSED` child panel the button does not open; adding the
override marks the report stale, so the Material Details list the user clicked
from is replaced by **Inputs Changed**; there is no way to load an image from
disk; and `uv_map_name` is free text where a typo makes the whole material
unsupported. Candidate fixes, smallest first: treat an image-less override as
incomplete through the existing `invalid_overrides` path, use `template_ID` with
`open="image.open"`, `prop_search` the UV name against the active object's
layers, and drop or grey overrides whose material left the selection instead of
raising `OVERRIDE_TARGET_NOT_SELECTED`. Drawing the override editor inline in
Material Details is the real fix and needs its own spec.

**Integration-contract defects,** on `feat/api-fixes-1.2`, from a reviewer
working on CATS integration. All six were verified against the code:

- `capability_payload()["address_modes"]` strips `AUTO`, but the parser accepts
  it, `docs/integration-api.md` documents it, and it is the property default
  every override starts at. The payload contradicts its own documentation.
- `analyze`'s legacy `image_name`, `uv_map_name`, and `image_channel` lack
  `SKIP_SAVE`, which is the only reason the panel resets three fields per draw.
- The modal cancel path calls `_finish_modal` — which tags a redraw — before
  publishing `ANALYSIS_CANCELLED`. Every other path publishes first.
- `validation_state` flips to `STALE` while `last_status_code` still reads
  `ANALYSIS_COMPLETE`, so a consumer reading either field alone is wrong.
- `ANALYSIS_SETTING_NAMES` is load-bearing for callers but lives in
  `properties.py`, outside anything `api_major` guards.
- A count-asserting test is missing for panel-built `material_overrides_json`.

`reset_analysis_settings` is deliberately excluded: it is `INTERNAL` and absent
from `PUBLIC_OPERATOR_IDS`, so promoting it would create a contract obligation
that does not exist today.

## Recommended next action

Land `feat/credits-support-panel-1.1.1`, then execute the API fixes on
`feat/api-fixes-1.2`. Two decisions are open there: whether correcting
`address_modes` warrants an API minor bump (the recommendation is no, because
the published list contradicted documented 1.2 behavior rather than adding a
feature), and whether `mark_dirty` should publish a `RESULT_STALE` status rather
than only documenting that `validation_state` must be read alongside the code.
