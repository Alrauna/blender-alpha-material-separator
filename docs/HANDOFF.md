# Repository handoff

Updated: 2026-08-07

## Current objective

Review `feat/api-fixes-1.2` and open its pull request, then finish the
installed-ZIP interactive acceptance.

## In flight: the integration-contract fixes on feat/api-fixes-1.2

Twelve commits, rebased onto `origin/main` at `042a084` after 1.1.1 landed, and
not yet pushed. All six defects a reviewer found while integrating CATS are
fixed. `API_VERSION` stays `(1, 2)` and the manifest is untouched: every change
either corrects a payload that already contradicted documented 1.2 behavior or
adds a status code, and neither is a new API surface.

- `capability_payload()["address_modes"]` no longer strips `AUTO`. It is now
  `OVERRIDE_ADDRESS_MODES` outright, so the published list is the list the
  parser accepts and the property defaults to. A new test drives every
  published mode through `parse_material_overrides_json` so the payload cannot
  drift from the parser again.
- `ANALYSIS_SETTING_NAMES` now lives in `addon/api_contract.py`, inside what
  `api_major` guards, and `addon/properties.py` re-exports it. Both existing
  importers are unchanged.
- `analyze`'s legacy `image_name`, `uv_map_name`, and `image_channel` carry
  `options={"SKIP_SAVE"}`, which let three per-draw reset assignments come out
  of `_set_analysis_properties` in `addon/panel.py`. `SKIP_SAVE` does not affect
  explicitly passed keyword arguments, so callers are unaffected.
- The modal cancel path publishes `ANALYSIS_CANCELLED` before `_finish_modal`
  tags a redraw, matching every other path.
- `RESULT_STALE` is published from `runtime._sync_public_validation_state`, the
  single choke point both `mark_dirty` and the stale branch of
  `record_validation` funnel through, so `last_status_code` can no longer read
  `ANALYSIS_COMPLETE` while `validation_state` reads `STALE`. This was the
  defect the integrator actually hit. Assignment still reports `STALE_ANALYSIS`,
  which is verified from call ordering rather than assumed:
  `validate_report` publishes `RESULT_STALE` inside itself and the operator's
  own status is the later write.
- `tests/blender/test_ux_overrides.py` now asserts the panel-built
  `material_overrides_json` through classification counts, not only its shape.

`reset_analysis_settings` remains deliberately excluded: it is `INTERNAL` and
absent from `PUBLIC_OPERATOR_IDS`, so promoting it would create a contract
obligation that does not exist today.

## State

`main` is at `042a084`, which merged
[#11](https://github.com/Alrauna/blender-alpha-material-separator/pull/11): the
manifest-derived extension version, the Credits & Support panel, and the 1.1.1
manifest bump. The newest published GitHub release is still `v1.1.0` from
`098f13c` with `alpha_material_separator-1.1.0.zip` and `SHA256SUMS.txt`.
**1.1.1 is not released.** `addon/` has changed since `v1.1.0`, so the published
artifact is no longer byte-identical to the tree and a 1.1.1 release is
outstanding whenever the user wants one.

Four pull requests merged between `v1.1.0` and 1.1.1 without touching `addon/`:

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
  `addon/blender_manifest.toml` as of 1.1.1, so a release edits the
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

Run on 2026-08-07 with Blender 5.2.0 LTS and its bundled Python 3.13.13, on
`feat/api-fixes-1.2` after the rebase onto `042a084`:

- 103 unit tests passed.
- The headless Blender suite exited 0, ending
  `ALPHA_MATERIAL_SEPARATOR_BLENDER_TESTS_OK`, with the new
  `ALPHA_MATERIAL_SEPARATOR_INTEGRATION_CONTRACT_TESTS_OK` among the markers.
- `extension validate addon` succeeded.
- `git diff --check` reported no whitespace errors.

Archive build and validation were not re-run for this branch, and the benchmark
suite was not run. Nothing here changes packaging or performance behavior. The
private `.local-references/default-example/` smoke is deliberately **not**
required either: no change on this branch touches material resolution,
rasterization, classification, cache validity, preview plans, assignment plans,
or mutation safety.

Run on 2026-08-05 with the same toolchain, on `main` content:

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
- The panel-override count test proves that dropping the override collection
  entirely is caught. It holds one override at a time, so it does not prove that
  dropping one material out of several would be caught. Closing that gap needs a
  second override-needing material and new fixtures, which is why it was left
  out of this branch.
- The cancel-path ordering test captures the live operator instance by
  monkeypatching `execute()`, because `bpy.types.Operator` subclasses cannot be
  instantiated directly in Blender 5.2. It asserts that background-mode dispatch
  really goes through the patch and resets `is_analyzing` if not, but an orphaned
  timer and modal handler would remain in that case; no public Blender API
  reclaims them. The test fails loudly rather than silently, and the assumption
  held on every run.
- `RESULT_STALE`'s companion test — that a clean result keeps its success status
  — passes with the production change reverted. It is an over-firing guard, not
  evidence for the fix.
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

**Manual alpha source usability** is the one objective from 1.1.1 testing still
unstarted, and it does not belong on `feat/api-fixes-1.2`. The Image field is a
real image-ID selector, but the flow dead-ends. An override carrying a material and no image resolves
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

Three smaller items are deliberately deferred rather than carried on the
fixes branch: the partial-drop override coverage named under known warnings
above, the two missing PEP 8 blank lines at `addon/runtime.py:328-329`, and
`docs/integration-api.md` gaining a worked example of reading
`last_status_code` and `validation_state` together.

## Recommended next action

Review the `feat/api-fixes-1.2` diff, then open its pull request against `main`
and let both CI checks run. Nothing on the branch needs a decision: both open
questions were settled during planning — no `API_VERSION` bump, because the
published `address_modes` list contradicted documented 1.2 behavior rather than
adding a feature, and `RESULT_STALE` is published rather than merely documented,
from the shared sync point instead of from `mark_dirty` alone.

A 1.1.1 release is outstanding whenever the user wants it; the branch does not
block it.
