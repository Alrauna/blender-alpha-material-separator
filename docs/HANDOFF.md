# Repository handoff

Updated: 2026-08-05

## Current objective

Await the user's detailed brief on the Expert-mode features that need rework,
then begin that work with investigation and design.

## Completed work

- The CI/CD milestone is complete. Pull request
  [#2](https://github.com/Alrauna/blender-alpha-material-separator/pull/2)
  merged to `main` at `b8af812` on 2026-08-01, with
  `CI / Windows — Blender 5.2` and `CI / Linux — Blender 5.2` passing on the
  pull request, on the merge push, and on a manual dispatch.
- Release `v1.0.0` was published from `b8af812` on 2026-08-01 with
  `alpha_material_separator-1.0.0.zip` and `SHA256SUMS.txt`. The user approved
  and tested that release.
- Pull request
  [#3](https://github.com/Alrauna/blender-alpha-material-separator/pull/3)
  merged at `aabb65a` on 2026-08-03. It is a Copilot Autofix one-line change
  setting `context.minimum_version` to `ssl.TLSVersion.TLSv1_2` in
  `quad9_addresses`. Hosted CI passed and CodeQL alert 1
  (`py/insecure-protocol`) is now `fixed`.
- `CLAUDE.md` is now tracked and redirects to `AGENTS.md`.
- Classic branch protection is applied to `main` with user approval. Both
  `CI / Windows — Blender 5.2` and `CI / Linux — Blender 5.2` are required
  status checks bound to the GitHub Actions app (`app_id` 15368), force pushes
  and branch deletion are blocked, and administrators are included. Strict
  up-to-date branches, required reviews, linear history, and branch locking
  are all off. Verified by reading the protection endpoint back.

## Important decisions and constraints

- The TLS autofix stays as it is, with no retroactive regression test, by
  explicit user decision. Revisit only when further CI/CD work is required.
  It is effectively a no-op hardening because the default context already
  floors at TLS 1.2 on the bundled Python 3.13.
- Because administrators are included in branch protection, `main` no longer
  accepts a direct push. Every change now needs a pull request whose two CI
  checks pass. Reverting that single setting is one API call if the
  restriction becomes an obstacle.
- Documentation commits stay local for now by explicit user decision. Do not
  push them without separate approval.
- Keep the Blender version check exact. Existing checksum consensus, committed
  SHA-256 anchors, safe extraction, and least-privilege workflow controls
  remain unchanged.
- Do not push, merge, tag, release, or change repository settings without
  explicit approval.

## Files changed and why

- `CLAUDE.md`: point Claude Code at the shared `AGENTS.md` policy.
- `docs/HANDOFF.md`: replace the stale pre-merge state with the verified
  post-release state.

## Validation commands and results

Run on 2026-08-05 against `main` at `aabb65a` with Blender 5.2.0 LTS
(built 2026-07-14) and its bundled Python 3.13.13.

```powershell
& $Python52 -m unittest discover -s tests/unit -t . -v
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 --python tests/blender/run_all.py
& $Blender52 --factory-startup --command extension validate addon
& $Blender52 --factory-startup --command extension build `
  --source-dir addon --output-dir .packaged-releases
& $Blender52 --factory-startup --command extension validate $Archive
git diff --check
```

Results: 88 unit tests passed; the headless Blender suite exited 0 with every
expected completion marker including the revalidation matrix, preservation,
and FBX export; source validation succeeded; the archive built and validated;
and the diff check reported no whitespace errors.

## Known failures, warnings, and unverified assumptions

- No known failures. Working tree is clean and `main` matches `origin/main`
  apart from the local, unpushed `CLAUDE.md` commit.
- `docs/superpowers/plans/2026-08-01-github-actions-ci-cd.md` still has
  unchecked boxes for steps that the merge history and hosted runs show were
  executed. They remain unchecked because the current agent did not run those
  exact commands.
- Three earlier plans still show unchecked installed-ZIP interactive
  acceptance steps. Whether those acceptances were performed and left unticked
  is unverified.
- The local recovery branch `feat/alpha-material-separator-0.1` no longer
  exists. Its history is contained in `main`, so nothing is lost.
- The git policy in `AGENTS.md` still directs work to `ci/automation`, which is
  merged and stale.
- Expected local output includes LF-to-CRLF Git notices.

## Remaining tasks in priority order

1. Receive the Expert-mode rework brief, then investigate and design before any
   production edit.
2. Decide when to push the local documentation commits. They now require a
   pull request because `main` is protected.

## Recommended next action

Wait for the Expert-mode rework brief. Expert mode is the `SIMPLE`/`EXPERT`
toggle in `addon/properties.py` that gates the Analysis Settings, Overrides,
Inspection, Policies, and Technical child panels in `addon/panel.py`.
