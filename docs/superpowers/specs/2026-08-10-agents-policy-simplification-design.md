# AGENTS Policy Simplification Design

## Goal

Make `AGENTS.md` a concise, internally consistent entry point that preserves
the extension's product and safety invariants while removing workflow conflicts,
duplicate test policy, unnecessary approval latency, and volatile CI details.

This is a process-documentation change. It must not alter the extension,
manifest, CI workflow, release behavior, material-support policy, or test
coverage.

## Context

The current `AGENTS.md` mixes six different concerns:

1. enduring product and mutation-safety invariants;
2. Superpowers and Ponytail workflow orchestration;
3. detailed test specifications for several subsystems;
4. live CI and release implementation details;
5. machine-specific validation commands; and
6. branch, commit, and handoff procedure.

Several incorporated Superpowers skills disagree with the repository rules.
For example, the repository requires a review skill that can operate only by
dispatching a subagent while separately prohibiting subagents without explicit
user authorization. Plan execution also invokes a finishing workflow that
offers local merging even though this repository lands every change through a
pull request to protected `main`.

The current document also requires committed plan artifacts to be deleted after
completion, although deletion itself requires another commit and may prevent
the documents from ever reaching `main`. Its branch rule starts before
implementation rather than before the earlier tracked design and plan edits.

## Considered approaches

### 1. Patch only the direct contradictions

Edit a few workflow sentences and leave the duplicated testing, CI, commands,
and Git sections in place.

This has the smallest immediate diff, but every task would continue loading
hundreds of lines of mostly irrelevant and partly duplicated policy. It would
also leave future contradictions likely as the CI and testing documentation
evolves.

### 2. Keep `AGENTS.md` as a concise router and invariant set

Retain the product goal, non-negotiable Blender/data invariants, a risk-tiered
development workflow, a short validation matrix, Git/publication safety, and
links to conditional authoritative documents. Reuse `docs/testing.md`,
`docs/performance.md`, and `docs/material-support.md`; add one focused
development-workflow document for process and branch details that remain too
large for the entry point.

This is the selected approach. It removes contradictions and recurring context
cost without weakening any product, test, preservation, CI, or release guard.

### 3. Replace all repository policy with generic skills

Delete most local workflow guidance and rely on the installed skills.

This is rejected because the generic skills do not know the repository's
protected-branch workflow, Blender preservation rules, private-input limits,
or release-security design.

## Design

### Policy hierarchy

`AGENTS.md` remains the entry point and states the precedence explicitly:

1. direct user instructions and repository safety invariants;
2. task-specific repository documentation linked from `AGENTS.md`;
3. applicable Superpowers and Ponytail workflows;
4. generic agent defaults.

Repository-specific instructions override incompatible generic skill steps.
In particular, the agent must not offer a local merge, dispatch a subagent
without explicit authorization, or create ceremony that the risk tier does not
require.

### Risk-tiered workflow

The workflow has three paths:

- Read-only inspection, status reporting, and mechanical documentation edits
  may proceed directly with evidence and proportionate validation.
- A narrow change with explicit requested behavior treats the user's request as
  design approval. The agent states a concise implementation plan and proceeds
  unless the user requested a plan checkpoint or investigation changes scope,
  behavior, risk, or architecture.
- Ambiguous, architectural, public-contract, material-support, security,
  performance-policy, or otherwise high-risk work requires a written design and
  explicit approval. A multi-step implementation then receives a test-first
  plan and approval before execution.

All defects still begin with systematic debugging and a root-cause
reproduction. Production behavior changes still use RED/GREEN TDD. Narrow work
does not skip reasoning or testing; it skips redundant approval gates when the
user has already supplied and approved the behavior.

### Design and plan artifacts

Branch suitability is established before the first tracked edit, including a
specification, plan, or handoff update.

Durable design decisions may be committed and retained. Implementation plans
are not required to be committed merely to satisfy a workflow. When a written
plan is useful for review or multi-session execution, keep it on the topic
branch and through the pull request rather than committing and deleting it in
the same milestone. A later cleanup may remove a genuinely superseded document
as its own intentional change.

### Execution, review, and completion

Inline execution is the default. Subagent-driven implementation, parallel
dispatch, and reviewer subagents require explicit user authorization. Without
that authorization, substantive production changes receive a deliberate
self-review of the complete diff and requirements.

Verification is proportional during development and comprehensive at the
branch gate. The repository-specific completion path supersedes the generic
finishing menu: verify the branch, update the durable handoff, and report it
ready. Push, PR creation, merging, tags, releases, repository settings, and
other publication remain separately authorized. Local merging into `main` is
never offered.

### Validation routing

`AGENTS.md` contains a compact trigger matrix:

- each RED/GREEN cycle runs the smallest relevant regression;
- each coherent commit runs affected tests and static checks;
- production branch completion runs unit tests, headless Blender tests, and
  source validation;
- packaging changes build and validate exactly one clean archive;
- performance-sensitive changes run the same-session benchmark protocol in
  `docs/performance.md`;
- release work follows the complete automated and interactive gates in
  `docs/testing.md`.

Committed and CI tests remain deterministic and independent of private machine
state. The ignored `.local-references` smoke is explicitly a separate,
user-authorized local acceptance layer. If a production defect cannot
practically receive an automated regression, the agent documents why, records
the closest automated protection, and reports the remaining manual check
instead of facing contradictory absolute rules.

An in-scope discovered failure receives a regression automatically when
practical. An unrelated failure is recorded as follow-up work and does not
silently expand the branch.

Installed-ZIP UI acceptance requires human confirmation unless the current
harness is both capable and explicitly authorized to control Blender. Agent-run
UI automation may provide supporting evidence but does not silently replace a
required human acceptance result.

### Handoff policy

`docs/HANDOFF.md` is updated only at a durable pause, ownership transfer,
material blocker, or branch completion. Branch switches, generated outputs,
and ordinary intermediate tool activity do not independently require a handoff
edit. The handoff describes the current branch and immediate next action, not a
per-turn transcript.

### Documentation routing

The detailed state-invalidation, Preview, assignment, preservation, private
acceptance, installed-ZIP, CI, release, and command policies move out of the
always-loaded entry point by reference, not by deletion:

- `docs/testing.md` remains authoritative for test layers, commands, CI/CD,
  release validation, installed-ZIP acceptance, and subsystem matrices;
- `docs/performance.md` remains authoritative for benchmark instrumentation and
  the same-session regression threshold;
- `docs/material-support.md` remains authoritative for approved automatic
  resolver patterns and unsupported cases;
- a focused development-workflow document holds the detailed branch, review,
  handoff, and publication procedure.

The existing CI documentation contract is updated to require the security
details in their permanent documentation rather than duplicating them in
`AGENTS.md`.

### Dependency and portability wording

The dependency invariant is clarified as no third-party runtime dependency
shipped with or required by the extension. Test or build tooling remains
subject to explicit repository approval.

Machine-specific command examples live in `docs/testing.md` and scripts. The
entry point names the gates rather than hard-coding one workstation's Blender
paths.

“Up-to-date `main`” means a topic branch based on freshly fetched
`origin/main`. If the remote cannot be checked, the agent reports the base SHA
and asks before proceeding with a potentially stale base. In a managed
workspace that prevents Git metadata writes, the agent uses native workspace
controls when available and reports the limitation instead of silently mixing
scope.

## Preservation requirements

The revision must preserve, without weakening:

- every Blender compatibility, identity, analysis, assignment, uncertainty,
  non-mutation, and data-preservation invariant;
- generated and redistributable regression requirements for production
  behavior;
- private-input confidentiality and user authorization;
- protected `main`, PR-only landing, and explicit publication approval;
- CI permission, action pinning, Blender-download verification, artifact
  identity, attestation, and release-publication contracts;
- version-independent ordinary ZIP discovery and the release-only strict
  filename path.

## Validation

This documentation/process change does not require the Blender product matrix.
Validation will include:

1. a focused documentation contract updated first so it fails against the old
   duplicated policy and passes after the new routing is in place;
2. the complete unit suite, because existing CI documentation contracts read
   both `AGENTS.md` and `docs/testing.md`;
3. link and referenced-file checks for every conditional policy destination;
4. searches for retired contradictory wording, including mandatory local
   merging, mandatory reviewer-subagent use, commit-then-delete plan lifecycle,
   and categorical inability to control Blender;
5. `git diff --check` and a complete branch-diff review.

No add-on, Blender, private-reference, packaging, performance, or installed-ZIP
test is applicable because no product or installable behavior changes.
