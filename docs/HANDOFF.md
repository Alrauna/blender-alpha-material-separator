# Repository handoff

Updated: 2026-08-07

## Current objective

Land `chore/release-1.2.0`, then run the 1.2.0 release gate.

## In flight: `chore/release-1.2.0`

Three commits, rebased onto `main` at `504027c` after
[#12](https://github.com/Alrauna/blender-alpha-material-separator/pull/12)
merged. The branch is no longer stacked. Three separate objectives ride here by
explicit user decision rather than because they belong together:

- **The 1.2.0 bump** is `addon/blender_manifest.toml` and `README.md` only,
  which is the release process the manifest-derived `EXTENSION_VERSION` bought
  in 1.1.1. The unit suite passing untouched after the bump is the proof that no
  third file carries the version.
- **The AGENTS.md policy expansion** adds a Testing and CI Requirements section
  and rewrites the Git policy around branch scope, stacked-PR avoidance, and a
  branch completion and handoff procedure.
- **`step=1` on the two Expert float settings.** Alpha Threshold and Minimum
  Affected Fraction inherited Blender's default drag step of 3, which moves a
  precision-4 setting 0.03 at a time. Blender's step unit is 1/100, so `step=1`
  gives 0.01 increments. The integer settings already stepped by 1.

`alpha_material_separator-1.2.0.zip` is built and validated locally, and the
manifest sits at the archive root where the credits panel reads it. The archive
is in the ignored `.packaged-releases/`, so it does not survive a clean, and a
release rebuilds from the validated commit anyway.

**The 1.2.0 release gate is not run.** Only archive build and validation are
done. Clean-ZIP installation, save/reopen, FBX material assignment, performance
baselines, the interactive UI checklist, and Unity material/submesh validation
all remain outstanding, and none of them can run headlessly.

## State

`main` is at `504027c`, which merged
[#12](https://github.com/Alrauna/blender-alpha-material-separator/pull/12): the
six integration-contract defects a reviewer found while integrating CATS.
`API_VERSION` stayed `(1, 2)` and the manifest was untouched, because every
change either corrected a payload that already contradicted documented 1.2
behavior or added a status code. `feat/api-fixes-1.2` is merged and deleted on
GitHub; the local branch still exists and can be pruned.

The newest published GitHub release is `v1.1.1`, tagged at `042a084`, carrying
`alpha_material_separator-1.1.1.zip` and `SHA256SUMS.txt`. **1.2.0 is not
released.** `addon/` has changed since `v1.1.1`, so the published artifact is no
longer byte-identical to the tree.

Earlier releases: `v1.1.0` from `098f13c`, `v1.0.0`. The 1.1.0 behavior work
landed in
[#4](https://github.com/Alrauna/blender-alpha-material-separator/pull/4):
below-significance faces default to `KEEP_SOURCE` instead of cancelling their
whole material group, the seven Expert analysis tooltips are written for
artists, the panel has a Reset to Default Values button, and Minimum Affected
Pixels no longer offers a value that does nothing. The 1.1.1 credits panel and
manifest-derived version landed in
[#11](https://github.com/Alrauna/blender-alpha-material-separator/pull/11).

## Important decisions and constraints

- Adding a status code has a panel obligation. `_draw_status_problem` in
  `addon/panel.py` holds a closed-world `normal` set of codes that are *not*
  problems and renders anything else as a red alert box with
  `presentation.guidance_for`'s unknown-code default. `RESULT_STALE` was absent
  from both, so nudging any Expert setting drew **"This input needs review"**
  directly above the correct **"Inputs Changed — Analyze Again"** copy.
  **Any future status code must be added to that set or to `_GUIDANCE`**, and
  nothing yet couples the two automatically. A panel-drawing regression test
  asserts both halves, so suppressing all feedback fails too.
- `EXTENSION_VERSION` in `addon/api_contract.py` is derived from
  `addon/blender_manifest.toml` as of 1.1.1, so a release edits the manifest and
  `README.md` only. `tests/unit/test_api_contract.py` cross-checks the two,
  which is what caught the hand-edited mismatch during the 1.1.0 bump.
- `README.md` is the only document that names a version, and
  `tests/unit/test_readme_contract.py` derives that version from the manifest.
  Keep other documents version-neutral rather than bumping them each release.
- `reset_analysis_settings` stays out of `PUBLIC_OPERATOR_IDS`: it is
  `INTERNAL`, and promoting it would create a contract obligation that does not
  exist today.
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
`chore/release-1.2.0` after the rebase onto `504027c`:

- 103 unit tests passed.
- The headless Blender suite exited 0, ending
  `ALPHA_MATERIAL_SEPARATOR_BLENDER_TESTS_OK`.
- `extension validate addon` succeeded.
- A cleared `.packaged-releases` produced exactly one archive,
  `alpha_material_separator-1.2.0.zip` at 69,608 bytes, which validated.
- `git diff --check` reported no whitespace errors.

Both required CI checks passed on
[#12](https://github.com/Alrauna/blender-alpha-material-separator/pull/12)
before merge: `CI / Windows — Blender 5.2` and `CI / Linux — Blender 5.2`.

The benchmark suite was not run on this branch; nothing here changes performance
behavior. The private `.local-references/default-example/` smoke is deliberately
**not** required either: no change on this branch touches material resolution,
rasterization, classification, cache validity, preview plans, assignment plans,
or mutation safety. `step=1` changes only how far a drag moves a slider.

Run on 2026-08-05 with the same toolchain, on then-current `main` content: 95
unit tests, the full headless suite, source validation, a single validating
archive, and a benchmark run of more than ten minutes that wrote
`.test-output/benchmarks/baseline.json`. That directory is ignored, so the
baseline does not survive into another session.

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
  second override-needing material and new fixtures.
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
- `step=1` has no automated coverage. It is a Blender UI presentation argument
  with no observable effect outside interactive dragging, so the check is the
  interactive one below.
- A large share of faces in the private example report `UNSUPPORTED`. That share
  was identical before and after the 1.1.0 change, so it is not a regression,
  but it is unexplained and worth a separate investigation into whether those
  materials are genuinely unresolvable or the resolver has a gap.
- `PLAN.md` at the repository root is the completed 1.0 release plan. AGENTS.md
  says a milestone's plan is deleted once that milestone is complete, so this
  file is drift; git history retains it. Removing it is not on this branch.
- Expected local output includes LF-to-CRLF Git notices.

## Remaining tasks

Finish the installed-ZIP interactive acceptance. The user installed
`alpha_material_separator-1.1.0.zip`, restarted Blender, exercised the rewritten
Expert analysis tooltips on hover, and reported that the build feels good to
use. Still unconfirmed in an installed build:

- Analyze → Preview → Tab to Object Mode → Apply without a second analysis.
- A below-significance face reporting under `Faces kept by policy` rather than
  blocking its material group.
- Reset to Default Values against an existing analysis reporting that inputs
  changed.
- Minimum Affected Pixels refusing to go below 1, with 2 still filtering.
- Alpha Threshold and Minimum Affected Fraction dragging in 0.01 steps.

The 1.1.1 credits panel is confirmed in an installed build: it appears above
Alpha Material Separator, and version, maintainer, and the issue-tracker button
all read correctly.

## Follow-up work, not started

**An integer 0–255 Alpha Threshold** was proposed and dropped without design
work. Worth recording why it is not obvious: the shipped default already does
what it was meant to do. A texel is affected when `alpha < threshold`, and at
0.999 every 8-bit alpha except 255 is affected, so "needs alpha at all" is
already the default behavior. The change would be presentation plus precision,
not classification, and it would put a public `FloatProperty` on the `analyze`
operator at risk of a type change — which is an `API_VERSION` question, not a UI
question. Revisit with a spec, or not at all.

**Manual alpha source usability** remains the one objective from 1.1.1 testing
still unstarted. The Image field is a real image-ID selector, but the flow
dead-ends. An override carrying a material and no image resolves through the
automatic path that already failed, so `Set Manual Alpha Source` followed by
Analyze reports the identical failure; the field that must be filled lives in a
`DEFAULT_CLOSED` child panel the button does not open; adding the override marks
the report stale, so the Material Details list the user clicked from is replaced
by **Inputs Changed**; there is no way to load an image from disk; and
`uv_map_name` is free text where a typo makes the whole material unsupported.
Candidate fixes, smallest first: treat an image-less override as incomplete
through the existing `invalid_overrides` path, use `template_ID` with
`open="image.open"`, `prop_search` the UV name against the active object's
layers, and drop or grey overrides whose material left the selection instead of
raising `OVERRIDE_TARGET_NOT_SELECTED`. Drawing the override editor inline in
Material Details is the real fix and needs its own spec.

Two smaller items stay deferred: the two missing PEP 8 blank lines at
`addon/runtime.py:328-329`, and `docs/integration-api.md` gaining a worked
example of reading `last_status_code` and `validation_state` together.

## Recommended next action

Open the `chore/release-1.2.0` pull request against `main` and let both CI
checks run. After it merges, run the 1.2.0 release gate — clean-ZIP install,
save/reopen, FBX material assignment, performance baselines, the interactive UI
checklist above, and Unity material/submesh validation — then publish the
release through the protected manual job.
