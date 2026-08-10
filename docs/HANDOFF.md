# Repository handoff

Updated: 2026-08-10

## Current branch objective

`codex/simplify-agents-policy` is based on refreshed `origin/main` commit
`8e5cc5a`. Its bounded objective is to make `AGENTS.md` a concise, internally
consistent entry point while preserving every product, testing, CI, release,
privacy, and Git safety invariant in conditional authoritative documentation.

The user approved the revision direction after a read-only policy audit. The
approved design is recorded in
`docs/superpowers/specs/2026-08-10-agents-policy-simplification-design.md`.

## Current state

- The previous release-artifact handoff branch has merged into `main` as
  `8e5cc5a`.
- No production, workflow, test, or release behavior has changed on this
  branch.
- The written design is awaiting the repository-required user review before an
  implementation plan is created.
- Detailed CI and validation policy already exists in `docs/testing.md`; the
  redesign will reuse it rather than introduce duplicate CI/release manuals.

## Next action

Review and approve the written design. Then create the concise test-first
implementation plan, obtain plan approval, update the documentation contract
before policy edits, and execute the approved documentation-only change.

The unpublished 1.3.1 draft cleanup (release ID `367440347`) and release
dispatch remain separate work and are untouched by this branch.
