# Repository handoff

Updated: 2026-08-08

## Current objective

`fix/stale-analysis-privacy` is complete and unpushed, staying local for review.
The 1.2.0 release gate remains outstanding and is unaffected by that branch; see
"Remaining tasks" below for what a following session should pick up.

## Completed: `fix/stale-analysis-privacy`

The branch name is narrower than the work. It was created for the
stale-analysis privacy question, which is findings 3 and 4 of six from a
reviewer integrating this extension into `Alrauna/Cats-Blender-Plugin`'s
Overdraw Prevention panel; the branch grew to publish gating, the review
signature, and status severity so that panel can mirror Analyze/Preview/Apply
without importing extension internals or reimplementing a private table. It is
unpushed, so `git branch -m` is still free, and no PR has been opened.

The approved design is
`docs/superpowers/specs/2026-08-08-published-workflow-surface-design.md` (git
history retains it; deleted from the tree per `AGENTS.md` now that the
milestone is complete and committed, along with the implementation plan at
`docs/superpowers/plans/2026-08-08-published-workflow-surface.md`).

Four of the six reported integration gaps were genuine defects, confirmed by
investigation before implementation:

- **The assignment plan was unreachable before assignment.** `actionable` gates
  `can_preview`/`can_apply` but the payload that would let a consumer derive it
  only reached the public surface from `assign_materials`, after the consumer
  had already committed to applying.
- **The review signature was unreachable.** A consumer passing an empty
  `expected_review_signature` silently reads as *already previewed*, losing
  both the not-previewed warning and `REVIEW_CHANGED` protection.
- **`RESULT_STALE` had no `_GUIDANCE` entry.** Invisible only because the
  panel's private `normal` set returned early before reaching guidance lookup.
- **Severity was private and closed-world.** The panel's `normal` set was a
  severity table consumers had to reimplement by hand, and the reimplementation
  already diverged from the extension on `STALE_ANALYSIS`.

One reported gap was correct behavior with an overclaiming comment:
`RECHECK_PENDING` publishing no status is right — the extension's own panel
gates on confirmed-stale only, and widening the guard would hide buttons on
harmless selection/mode changes. Only the comment in
`runtime._sync_public_validation_state` was corrected; the guard is unchanged.
One gap was a misreading: release detection already worked through the
long-published `extension_version`, set by `query_capabilities` and derived
from `blender_manifest.toml` since 1.1.1; what was missing was a documented
minor-bump policy and a worked example, which `docs/integration-api.md`'s new
`## Versioning` section now supplies.

What shipped, across six commits (`4ad1f20` design approval,
`30d91e9` plan, `75b6e1e` `api_contract.py` payload shape,
`8d1cd97`/`77f58f0` shared `addon/workflow.py` snapshot and `workflow_json` RNA
getter, `f227782` status severity and the `RESULT_STALE` guidance fix) plus this
documentation commit:

- `addon/api_contract.py`: `WORKFLOW_STATES`, `WORKFLOW_FIELDS`,
  `workflow_payload()`, `degraded_workflow_payload()`, `STATUS_SEVERITIES`, and
  `severity_for()`. `API_VERSION` is `(1, 3)`.
- `addon/workflow.py` (new): `snapshot(context)`, the single computation the
  panel draws from and `workflow_json` serializes, so drawn and published state
  cannot drift. No memoization; a `ponytail:` comment records the upgrade path,
  gated on the redraw benchmark below rather than assumption.
- `addon/properties.py`: read-only `workflow_json` `StringProperty(get=...)`
  on `ALPHA_MATERIAL_SEPARATOR_PG_api_state`. The getter is total — any
  exception publishes `degraded_workflow_payload()` rather than raising,
  because a `get=` callback runs during panel draw.
- `addon/panel.py`: draws from the shared snapshot instead of computing gating
  inline; `_draw_status_problem` now branches on `severity_for()` instead of a
  private closed set.
- `docs/integration-api.md`: `## Versioning` and `## Workflow state` sections,
  a `workflow_json` bullet, and a `severity` paragraph after the assignment
  status table. `docs/testing.md` names the new coverage in its checkpoint
  paragraph.

Validation actually performed on this branch (2026-08-08, Blender 5.2.0 LTS,
bundled Python 3.13.13):

- 111 unit tests passed (`tests/unit`), up from the 103 recorded on
  `chore/release-1.2.0`.
- The headless Blender suite exited 0, ending
  `ALPHA_MATERIAL_SEPARATOR_BLENDER_TESTS_OK`, including the new
  `ALPHA_MATERIAL_SEPARATOR_PUBLISHED_WORKFLOW_TESTS_OK` marker.
- `extension validate addon` succeeded.
- A cleared `.packaged-releases` produced exactly one archive,
  `alpha_material_separator-1.2.0.zip` at 72,584 bytes (up from 69,608 on
  `chore/release-1.2.0`, consistent with the added workflow surface), which
  validated by its discovered path.
- `git diff main...HEAD --check` and the final `git diff --check` reported no
  whitespace errors.
- `git diff main...HEAD --stat` was reviewed; the `default_planned_action`
  defect, manual alpha source usability, and the two missing PEP 8 blank lines
  in `runtime.py` do not appear anywhere in the diff outside prose describing
  them as explicitly out of scope.
- `tests/blender/run_benchmarks.py` ran twice in the same session on the same
  machine — this branch, then `main` in a throwaway worktree — each doing its
  own discarded warm-up plus five measured runs. All 29 timed fields were
  compared. The worst movement was `+17.5%` on
  `analysis.large_tiled_uv.coverage_reuse_seconds`, inside the 25 percent gate,
  and the spread is symmetric: `analysis.high.cold_seconds_median_5` fell 8.7
  percent and `digest.8192.prefix_build_seconds` fell 27.3 percent on the same
  pair. That two-sided spread across ~25-minute runs is machine noise.
  **This measures nothing about the changed path.** `run_benchmarks.py` imports
  `addon.runtime`, the analysis adapters, `build_assignment_plan`, and
  `review_signature`; it does not import `addon/workflow.py` or
  `addon/panel.py`, so no benchmarked case builds a snapshot or reads
  `workflow_json`. The run is evidence that the branch did not disturb the
  analysis and digest paths, not evidence about redraw cost. The `ponytail:`
  memoization note in `addon/workflow.py` therefore stays un-triggered and
  un-refuted; deciding it needs an interactive redraw measurement that does not
  exist yet.

Not run, and not claimable: installed-ZIP interactive acceptance of the
external Cats-Blender-Plugin Overdraw Prevention panel gating correctly
against a real installed build — this is the one item the design's own testing
section names as user-performed and un-drivable by an agent. The private
`.local-references/` before/after smoke was also not run; it is not required
here because this change does not alter material resolution, rasterization,
classification, cache validity, preview plans, assignment plans, or mutation
safety — it publishes state those paths already compute.

## Completed: `chore/release-1.2.0`

Merged as [#13](https://github.com/Alrauna/blender-alpha-material-separator/pull/13)
at `e696c4e`. Three commits, rebased onto `main` at `504027c` after
[#12](https://github.com/Alrauna/blender-alpha-material-separator/pull/12)
merged. The branch was not stacked. Three separate objectives rode there by
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

`main` is at `e696c4e`, which merged
[#13](https://github.com/Alrauna/blender-alpha-material-separator/pull/13).
Before that it was at `504027c`, which merged
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

**`report_json`'s `default_planned_action` is stale relative to shipped
defaults.** Found while investigating the integration API on 2026-08-08.
`AnalysisReport.public_payload` returns `SKIP_GROUP` for any group holding
`SUPPRESSED` faces, but the shipped `suppressed_policy` has been `KEEP_SOURCE`
since 1.1.0, which produces `PARTIAL_MOVE_KEEP_POLICY`. It is the only
plan-shaped data a consumer receives after analyze, and it misreports. Needs its
own reproduction and branch; deliberately excluded from the workflow-surface
work.

Two smaller items stay deferred: the two missing PEP 8 blank lines at
`addon/runtime.py:328-329`, and `docs/integration-api.md` gaining a worked
example of reading `last_status_code` and `validation_state` together. The
second was expected to fold into the workflow-surface branch and did not —
that branch's `## Workflow state` section publishes both values inside one
snapshot, which removes most of the reason to read them separately, but no
worked example of the pairing was written. Add it, or close it as superseded.

## Recommended next action

Review `fix/stale-analysis-privacy` and, if it is accepted, open its pull
request against `main`. It is complete, validated, and local; nothing has been
pushed. The one item it cannot close itself is the installed-ZIP interactive
acceptance named above.

Then pick a following branch from the deferred list: `report_json`'s
`default_planned_action`, manual alpha source usability, or the two PEP 8 blank
lines. None of them belong on the completed branch.

The 1.2.0 release gate is still outstanding and independent: clean-ZIP install,
save/reopen, FBX material assignment, performance baselines, the interactive UI
checklist above, and Unity material/submesh validation, then publication through
the protected manual job.
