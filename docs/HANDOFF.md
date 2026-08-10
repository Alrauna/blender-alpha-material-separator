# Repository handoff

Updated: 2026-08-10

## Completed branch objective

`codex/simplify-agents-policy` is based on refreshed `origin/main` commit
`8e5cc5a`. Its bounded objective is complete: make `AGENTS.md` a concise,
internally consistent entry point while preserving every product, testing, CI,
release, privacy, and Git safety invariant in conditional authoritative
documentation.

`AGENTS.md` is now 148 lines instead of 392. It retains the product goal,
Blender and mutation-safety invariants, task routing, risk tiers, validation
matrix, and publication guards. Detailed branch, design, plan, review, commit,
handoff, and publication procedure now lives in
`docs/development-workflow.md`. Existing `docs/testing.md`,
`docs/performance.md`, and `docs/material-support.md` remain authoritative for
their domains.

## Decisions

- Repository safety limits prevail over conflicting instructions. Conditional
  repository documentation overrides incompatible generic skill steps.
- A narrow, explicit user request counts as design approval. Ambiguous,
  architectural, public-contract, material-support, security, performance-
  policy, and other high-risk work retains written design and plan approval.
- Branch suitability is checked before the first tracked edit, including specs,
  plans, and handoffs. New topic branches start from freshly fetched
  `origin/main`.
- Inline execution and self-review are the defaults. Subagent implementation,
  parallel dispatch, and reviewer subagents require explicit user authorization.
- Durable design records may remain committed. Written implementation plans are
  not automatically committed and deleted in one milestone; a committed plan
  stays through pull-request review until separately superseded.
- The repository completion path verifies and hands off the topic branch. It
  never offers a local merge into protected `main`.
- `docs/HANDOFF.md` changes only at a durable pause, ownership transfer,
  material blocker, or branch completion.
- Push, PR creation or merge, tags, releases, repository settings, failed-draft
  cleanup, and other publication remain separately authorized.

## Commits

- `729bcb2` — approved AGENTS policy simplification design;
- `a61e27e` — approved test-first implementation plan;
- `0deeaa4` — concise policy router, permanent workflow documentation, README
  routing, preserved CI/security documentation, and adjusted CI documentation
  contract.

The design and plan remain on the branch through review under the new artifact
lifecycle.

## Test-first evidence and deviation

The existing CI security documentation contract was changed first to read its
workflow and checkout requirements from permanent documentation instead of
`AGENTS.md`. Before documentation edits, the focused test failed solely because
`docs/development-workflow.md` did not exist. After the rewrite it passed.

The approved plan initially proposed a new test that would grep `AGENTS.md`
wording and line count. The required test-quality guidance prohibits tests that
merely detect changes in human or agent-instruction prose, so that test was not
created. The deviation is recorded in the implementation plan. Policy
preservation instead used the existing README link resolver, focused
preservation and retired-wording searches, direct specification-to-diff review,
`git diff --check`, and the complete unit suite. This reduced brittle test debt
without changing the approved scope or safety requirements.

## Verification evidence

Fresh local results:

- baseline unit suite before implementation: 125 passed;
- RED CI documentation contract: 1 expected failure for the missing permanent
  workflow document;
- focused CI workflow contract module after implementation: 22 passed;
- README and relative-link contract module: 9 passed;
- combined affected contract gate: 31 passed;
- complete unit suite after implementation: 125 passed;
- conditional policy targets: 4/4 present;
- `AGENTS.md` size: 148 lines;
- required product, workflow, CI/security, and publication phrases found in
  their intended authoritative documents;
- retired contradictory and machine-specific wording absent from `AGENTS.md`;
- `git diff --check`: no errors before the implementation commit;
- complete branch scope: eight approved documentation/contract files, with no
  add-on, manifest, GitHub workflow, packaging, performance baseline, private
  input, or generated output change.

The headless Blender suite, source/archive validation, private-reference smoke,
performance benchmarks, installed-ZIP acceptance, FBX, and Unity checks were
not applicable because this branch changes no product, package, resolver,
rasterizer, classifier, cache, Preview, Apply, assignment, preservation, CI
workflow, or release behavior.

## Limitations and next action

No known limitation remains inside this branch's scope. The branch is ready for
user review. Push and pull-request creation require separate authorization.

The unpublished 1.3.1 draft cleanup (release ID `367440347`) and release
dispatch remain separate work and are untouched by this branch.
