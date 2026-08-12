# Testing and interactive verification

## Automated checkpoint commands

```powershell
$Blender52 = 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
$Python52 = 'C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe'

& $Python52 -m unittest discover -s tests/unit -t . -v
& $Blender52 --factory-startup --background --python-exit-code 1 --python tests/blender/run_all.py
& $Blender52 --factory-startup --command extension validate addon
Remove-Item .\.packaged-releases\*.zip -ErrorAction SilentlyContinue
.\scripts\build_extension.ps1 -Blender $Blender52

$Archive = (Get-ChildItem .\.packaged-releases\alpha_material_separator-*.zip | Select-Object -ExpandProperty FullName)
& $Blender52 --factory-startup --command extension validate $Archive

$IsolatedRoot = Join-Path (Resolve-Path .\.test-output).Path "isolated-install-$PID"
$env:BLENDER_USER_CONFIG = Join-Path $IsolatedRoot 'config'
$env:BLENDER_USER_SCRIPTS = Join-Path $IsolatedRoot 'scripts'
$env:BLENDER_USER_DATAFILES = Join-Path $IsolatedRoot 'datafiles'
New-Item -ItemType Directory -Force -Path $env:BLENDER_USER_CONFIG | Out-Null
New-Item -ItemType Directory -Force -Path $env:BLENDER_USER_SCRIPTS | Out-Null
New-Item -ItemType Directory -Force -Path $env:BLENDER_USER_DATAFILES | Out-Null
& $Blender52 --command extension install-file -r user_default -e $Archive
& $Blender52 --background --python-exit-code 1 --python tests/blender/verify_installed_zip.py
```

The unit layer uses Blender's bundled interpreter because `addon/core` depends
on numpy for image extraction and row prefixes. The core still imports without
`bpy`; it is not importable on a bare Python that lacks numpy. CI matches this
by running `tests/unit` on the prepared Blender Python.

When all commands above pass, the checkpoint verifies ordinary-Python import
without `bpy`, deterministic
coverage/classification and API 1.3 capability JSON, registration/unregistration,
Simple and Expert workflow state, the published workflow surface and its
RECHECK_PENDING gating, per-material overrides, analysis progress and
cancellation, review-token invalidation, warning confirmation, preview,
stale-result refusal, safe assignment, every documented material-identity
transition, completion summaries, preservation, save/reopen, FBX
export/reimport, README contracts, and anonymized synthetic characterization.
Do not mark the installed-ZIP or exact interaction checkboxes complete merely
because the source-tree headless suite passed.

## GitHub Actions CI/CD

Pull requests targeting `main` and pushes to `main` run three stable checks:

- `CI / Windows — Blender 5.2`
- `CI / Linux — Blender 5.2`
- `CI / macOS — Blender 5.2`

All three use Blender 5.2.0 exactly and run the unit suite, complete headless
Blender suite with auto-execution disabled, source validation, extension build,
and version-independent discovery and validation of the generated AMS ZIPs.
Each runner builds and discards its own ZIP. The `macos-15` runner is Apple
Silicon; macOS is not excluded from or allowed to ignore any shared validation
step.
Ordinary validation uses no workflow artifacts, caches, setup actions, package
installers, containers, self-hosted runners, or third-party actions. The manual
release path uses one short-lived workflow artifact and official GitHub actions
pinned to reviewed full commit SHAs.

All uses of `actions/checkout` remain confined to read-only jobs, pinned to a
reviewed full commit SHA, and configured with `persist-credentials: false`.
The read-only release-package job continues to use unauthenticated native Git
for exact-`GITHUB_SHA` source retrieval instead of checkout credentials.
Workflow permissions remain `contents: read` by default. Only the protected
manual `release_publish` job may use `contents: write`; artifact consumers may
add `actions: read`, and `GH_TOKEN` belongs only on individual `gh` command
steps. Adding an action, dependency, cache, artifact transfer, trigger, runner
type, permission, or network source requires design review and explicit user
approval.

The workflow downloads Blender only from its fixed Blender.org HTTPS URL. It
retrieves Blender.org's checksum file through system DNS, Cloudflare DoH, and
Quad9 DoT, requires byte-identical content, verifies the relevant value against
the committed SHA-256 trust anchor, hashes the archive before extraction, and
requires the executable to report Blender 5.2.0. The DoT response must be a
complete standard A/IN response echoing the exact query. Each direct A answer
owner must match that query case-insensitively, and compressed names may point
only to previously validated label boundaries. CNAME expansion is unsupported
and therefore fails closed. Pass at most 16 distinct valid addresses to curl,
which keeps `download.blender.org` as the validated TLS hostname. Curl has a
30-second connection timeout, a fixed total limit, and two retries. Linux tar
extraction uses Python's safe data filter and selects Blender from the
exact archive root. Any malformed response, disagreement, or timeout fails
closed.
On macOS, the pinned archive is
`blender-5.2.0-macos-arm64.dmg`, with committed SHA-256
`ed4d8390166dec5ea0a2813a03db6221f206ce016442be7f59f41d760972568a`.
The helper mounts it read-only with `hdiutil`, parses the mount point from plist
output, requires exactly one mounted volume containing `Blender.app`, preserves
bundle symlinks while copying, and detaches the volume even when copying fails.

The first hosted run showed that Quad9's HTTP/2-only DoH endpoint is
incompatible with the Windows runner's curl path. The approved standard-library
Quad9 DoT replacement passed a live local resolution and pinned HTTPS checksum
download. Hosted Windows, Linux, and macOS must still prove port 853
availability; do not weaken or remove the independent resolver or
byte-consensus gate.

The existing protected checks remain Windows and Linux. Making the macOS check
required in branch protection is a separate repository-setting change and must
wait for explicit approval after the hosted Apple Silicon job is confirmed.

Manual dispatch requires a strict `X.Y.Z` version. Publication additionally
requires `main`, a public repository, successful Windows, Linux, and macOS
validation, and the protected `release` environment.

`release_package` is read-only. It fetches exact `GITHUB_SHA` through
unauthenticated native Git, verifies that checkout, builds and validates the ZIP
once, writes `SHA256SUMS.txt`, and publishes both files as
`ams-release-package`. The only added action is
`actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a`
(v7.0.1), configured with `retention-days: 1`, `compression-level: 0`, exact
file paths, and failure when neither configured file exists. Both downstream
consumers independently download the same current-run workflow artifact, verify
it, and reject a partial or expanded file set.

`release_attestation` has exactly `actions: read`, `contents: read`,
`id-token: write`, and `attestations: write`. Its one token-bearing native step
uses `gh run download $env:GITHUB_RUN_ID` with the current repository and exact
artifact name. It requires only the expected ZIP and checksum, then verifies
both checksum identity and the producer-reported ZIP digest before running
`actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6`
(v4.2.2) on that ZIP.

`release_publish` depends on both earlier jobs, runs in the protected `release`
environment with `actions: read` and `contents: write`, and executes no action.
It independently downloads the same current-run artifact with native
`gh run download`, repeats the file-set, checksum, and digest checks, and
refuses any existing tag or release before mutation. Only then does it create a
draft targeted at exact `GITHUB_SHA`, upload those exact two files, re-download
the stored ZIP, verify the same digest, and publish. `GH_TOKEN` remains exposed
only to individual native GitHub CLI steps.

A package or attestation failure creates no draft. A failure after draft
creation leaves an unpublished draft. No path publishes before successful
attestation and stored-release ZIP digest verification.

In summary, the read-only release-package job builds once from exact
`GITHUB_SHA`. Attestation and protected publication independently download the
same current-run workflow artifact and verify its producer-reported SHA-256.
Publication uploads those exact bytes, re-downloads the stored ZIP, re-hashes
it, and publishes only after attestation succeeds.

After downloading a published extension ZIP, discover the AMS archives and
verify that every discovered digest and provenance is bound to this
repository's release workflow:

```powershell
$Archives = @(Get-ChildItem -Filter 'alpha_material_separator-*.zip' -File)
if ($Archives.Count -lt 1) { throw "Expected at least one AMS ZIP." }
foreach ($Archive in $Archives) {
  gh attestation verify $Archive.FullName `
    --repo Alrauna/blender-alpha-material-separator
}
```

An attestation identifies the source workflow and artifact digest; it does not
claim that the artifact is vulnerability-free. Hosted acceptance must still
confirm the workflow-artifact handoff, publication, and verification of the
downloaded release ZIP after publication is separately authorized.

GitHub-hosted runner timing is variable, so CI runs correctness benchmark
contracts but does not enforce a hosted performance threshold. The repository's
25 percent same-machine limit remains the local authority. This CI-only
milestone does not require the private before/after smoke because it changes no
resolver, rasterizer, cache, Preview, Apply, or preservation behavior.
Blender native extension-repository hosting remains a separate milestone.

The corresponding local gate is:

```powershell
$Blender52 = 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
$Python52 = 'C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe'
& $Python52 -m unittest discover -s tests/unit -t . -v
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 --python tests/blender/run_all.py
& $Blender52 --factory-startup --command extension validate addon
Remove-Item .\.packaged-releases\*.zip -ErrorAction SilentlyContinue
& $Blender52 --factory-startup --command extension build `
  --source-dir addon --output-dir .packaged-releases
& $Blender52 --factory-startup --command extension validate `
  (Get-ChildItem .\.packaged-releases\alpha_material_separator-*.zip |
    Select-Object -ExpandProperty FullName)
```

## Required test layers

Every behavior defect first receives a generated or synthetic failing
regression. Verification then proceeds through pure-Python tests, headless
Blender state-transition and mutation tests, semantic preservation checks,
installed-ZIP interaction, and instrumented performance measurements.

The ignored `.local-references` validator is a separate, user-authorized local
acceptance layer. If an automated regression is genuinely impractical, document
why, retain the closest automated contract, and report the remaining manual
interaction explicitly.

Installed-ZIP UI acceptance requires human confirmation unless the current
harness is capable of controlling Blender and the user explicitly authorizes
it. Agent-run UI automation is supporting evidence and does not silently
replace a required human acceptance result.

Private before/after files are local structural references only. No identifying
name, path, asset, raw graph dump, raw measurement, or screenshot enters a
committed test or report. Committed regressions reproduce the relevant shape
with generated materials, textures, meshes, and collapsed UVs.

When the ignored default before/after pair is present, relevant Blender smoke
passes must also run its local multi-object validator:

```powershell
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 `
  --python .local-references\default-example\_validate_analysis.py -- `
  .local-references\default-example\before.blend `
  .local-references\default-example\after.blend
```

This local layer must exercise all mesh objects even when some materials or
faces remain explicitly unsupported. It checks Analyze → exact-plan Preview →
Object Mode → Apply without reanalysis, semantic changed-face coverage,
source/derived material roles, immutable reference files, and preservation of
meshes, source graphs, images, armatures, transforms, parenting, and original
slots. It also proves that at least one multi-image material resolves from its
supported Base Color authority and that positive-area faces whose UVs lie
outside 0–1 use their actual addressing modes.

The after example is an early-development, hand-made performance reference,
not a per-face partition oracle. The extension may conservatively move
additional alpha-evidence and `MIXED` faces, while faces included in a broad
hand-made alpha section may correctly classify `OPAQUE` from their sampled A
values. Generated fixtures remain authoritative for classification behavior;
private data or raw output must never become a committed fixture or result.

Current status after the 2026-07-26 resolver correction: the resolver, workflow,
out-of-range UV, exact-plan, derived-role, and preservation gates pass. The
remaining 1,176 `OPAQUE` differences are a known artifact of the hand-made
after partition and are reported only as an anonymized aggregate diagnostic.
Do not weaken authority resolution or silently change raster margins to imitate
that manual grouping.

For invalidation behavior, every harmless event has a paired real-change test:

| Event | Expected result |
| --- | --- |
| Face selection, active face/object, or Object/Edit Mode toggle | Same analysis ID and review token; zero rasterization and image-digest rows. |
| Unrelated mesh, material, or image update | No report or review change. |
| Relevant topology, UV, material index/slot, or Alpha/Base Color authority change | Confirmed stale; review cleared; assignment performs zero mutation. |
| Assignment-only source graph edit outside the resolved authority | Analysis retained with zero image-digest rows; exact-plan review cleared and Preview required again. |
| Relevant image pixel/reload/pack/replace change | Conservative participating-channel validation, then confirmed stale if content/state differs. |
| Assignment-policy change | Analysis retained; another exact-plan preview required. |
| Analysis setting or manual-source change | Confirmed stale; another analysis required. |
| Apply before a deferred recheck runs | Synchronous preflight drains the recheck and blocks any real change atomically. |

Assignment tests combine a resolved source containing opaque,
alpha-affected, mixed, and face-local uncertain faces with an unresolved source
that remains unchanged. They assert exact Preview/Apply plan equivalence,
partial success, confirmation cancellation, undo/redo, idempotence,
save/reopen, and preservation of every non-allowlisted datablock property.

## Interactive Blender smoke checklist

Executed on 2026-07-22 and repeated for the preview/revalidation changes on
2026-07-25 with Blender 5.2.0 LTS. The UI observations used a generated
two-object grid and generated image; no private reference asset was used.
Machine-state assertions that are difficult to prove visually were also checked
by the corresponding headless regression test.

- [x] Install/development-load the extension and confirm the panel appears in
  the 3D View sidebar. The built ZIP was also installed into an isolated Blender
  configuration by the automated installation test.
- [x] Confirm empty and invalid selections produce clear messages.
- [x] Confirm Simple mode presents only Analyze, Review, and Apply, and Expert
  mode exposes the default-closed analysis, manual-source, alternate-class,
  policy, and diagnostics panels without changing analysis inputs.
- [x] Verify per-material image, channel, UV, and addressing records. Channel
  choice remains disabled until an explicit image is selected; unlisted
  materials continue using automatic detection.
- [x] Run a nontrivial analysis and observe progress advancing continuously.
- [x] Press Escape and confirm cancellation leaves no partial report or data
  change. The installed ZIP passed this check on 2026-08-01; the cursor and
  sidebar percentages can briefly disagree and remain a follow-up UX issue.
- [x] Verify the plain-language result counts and the suppressed/unsupported
  explanations and remedies. Raw codes and analysis IDs remain Expert-only.
- [x] Preview affected and mixed classes and confirm selected faces are visible.
- [x] Preview multiple eligible objects in multi-object Edit Mode.
- [x] Preselect edges and vertices on adjacent and disconnected opaque faces,
  run Preview, and confirm only components belonging to selected faces remain
  highlighted. Confirm a shared selected/unselected boundary edge remains
  highlighted normally.
- [x] Start Analyze from multi-object Mesh Edit Mode and confirm it switches to
  Object Mode before reading base-mesh UV/loop data, completes successfully,
  and preserves mesh contents.
- [x] Confirm shared, linked, read-only, and multi-user meshes are skipped by
  preflight. Exact non-mutation is asserted by the preservation and assignment
  policy tests.
- [x] Change a real reviewed input and confirm stale-result refusal.
- [x] In the rebuilt ZIP, complete Analyze → Preview → `Tab` to Object Mode
  → Apply without another analysis. Confirm the analysis ID and preview token
  survive, no image digest or rasterization runs, and the intended split is
  applied. The installed-ZIP walkthrough kept Apply enabled after a face
  selection change and the Object Mode transition; the instrumented headless
  matrix confirmed zero digest and rasterization work.
- [x] Confirm Apply is enabled immediately after a current actionable analysis,
  before Preview.
- [x] Apply an unpreviewed clean plan and confirm the dialog begins with
  **Faces have not been previewed.**
- [x] Cancel the unpreviewed dialog and confirm zero changes to faces, material
  slots, materials, and metadata.
- [x] Confirm the same unpreviewed plan, verify the exact planned assignment,
  then undo it completely with Ctrl+Z.
- [x] Preview the exact clean plan and confirm Apply retains its immediate
  no-warning behavior through the generated Blender workflow test.
- [x] Change only assignment preflight, confirm no reanalysis is required, and
  verify Apply forces confirmation until the revised plan is previewed.
- [x] Repeat Object/Edit toggles, face selection changes, active-object changes,
  and multi-object Edit Mode transitions without a false stale message.
  Selection and mode changes were repeated in the installed ZIP; active-object
  and transition permutations are covered by the instrumented headless matrix.
- [x] Review analyzed objects, source material, resolved image/UV/channel,
  destination material, skips, faces to move, and estimated slot/section
  increase before assignment.
- [x] Confirm each successful analysis automatically collapses the native
  **Material Details (N)** disclosure, duplicate material results count once,
  and a single advisory above it points to unsupported materials. Expand it in
  narrow and wide sidebars and confirm all existing cards and **Set Manual
  Alpha Source** actions remain usable. Cancellation must preserve the prior
  report and disclosure state.
- [x] Confirm the warning popup after **Apply Material Separation** contains
  only aggregate plan-outcome counts, stays bounded without material/object
  lists, and uses the native **Apply Material Separation** title and **Apply**
  confirmation action. Check narrow/wide layouts and 100%/150% UI scale;
  cancel with zero mutation, then reopen, apply, and undo with Ctrl+Z.
- [x] Assign directly from the Edit Mode preview and verify the intended material
  partition.
- [x] Process a generated two-material case where one resolved source has
  collapsed-UV faces and another material has no traceable alpha source. Confirm
  uncertain faces move to alpha, the unresolved material stays unchanged, and
  useful work is not globally blocked.
- [x] Undo and redo assignment from the 3D View.
- [x] Confirm the completion card reports moved faces, created/reused material,
  added slots, Ctrl+Z guidance, and the Unity handoff. Rerun and confirm
  “Already separated — no additional changes”; regression tests also assert no
  duplicate datablocks or slots.
- [x] Disable, re-enable, and confirm clean panel/operator lifecycle through the
  isolated ZIP installation and registration lifecycle tests.

The optional-preview, Material Details, count-only confirmation, two-material
partial-apply, 150% scale, and ordinary Unity material/submesh checks above
were reported as passing by the user on 2026-08-01. The previewed clean-plan
no-warning path is additionally covered by the generated Blender tests.

The documentation captures under `docs/images/` were generated from this
redistributable synthetic scene, cropped to remove the local file path, and
checked against the final button labels. The live walkthrough was performed at
the default UI scale with a narrow sidebar; automated layout/state checks cover
long labels and both interface modes.

Ordinary Unity material/submesh validation passed. A VRChat SDK/shader run
remains separate reference evidence for only the recorded stack.

## Preservation snapshots

Headless tests permit changes only to reviewed material slots and polygon
material indices. They compare topology, vertex groups, armatures, shape keys,
UVs, normals, attributes, modifiers, parenting, images, source materials, and
unselected objects before and after assignment and undo.

## Cache and timing assertions

Cache tests record component-fingerprint calls, participating image-digest rows,
rasterized polygons, coverage hits/misses, validity transitions, and elapsed
time. A mode-only recheck must record zero image-digest rows and zero rasterized
polygons. Use one discarded warm-up and five measured runs. On the approved
same-machine structural workflow, the new mode-exit recheck targets a median
below one second and below 15 percent of cold analysis; established same-machine
metrics retain the 25 percent unexplained-regression gate.

The generated revalidation benchmark also discards one warm-up and records five
calls to the real final Apply preflight. It asserts that report identity,
polygon material indices, material slots, and material datablocks remain
unchanged. The 2026-08-01 median was 0.0353 seconds with zero image-digest rows
and zero rasterized polygons.

The Analyze throughput regression also exercises both image-reader paths.
Eligible images must use one native bulk read with no Python slices; an
explicit chunk size, an oversized working estimate, or a rejected native call
must use the existing complete-row fallback. Both paths must produce identical
digests and affected-texel grids for every supported component count/channel,
and non-finite participating values must still fail. Modal analysis prepares
the selected inputs once, traverses each UV layer once, and fingerprints each
shared material once per assignment signature.
