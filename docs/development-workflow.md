# Development workflow

## Scope and precedence

Repository safety invariants and direct user instructions take precedence over
this workflow, with safety limits prevailing if they conflict. This document
then overrides incompatible generic skill steps.
Use applicable Superpowers phases for disciplined investigation, design,
planning, implementation, review, and verification, with Ponytail enforcing the
smallest correct scope throughout.

Do not turn skill invocation into ceremony. Reasoning, root-cause investigation,
test evidence, preservation checks, and material approval decisions remain
mandatory where their risk applies.

## Choose the workflow by risk

Read-only inspection, status reporting, and mechanical documentation corrections
may proceed directly with evidence and proportionate validation.

The user's explicit request counts as design approval for a narrow, unambiguous
change. State a concise execution plan and proceed unless the user requested a
plan checkpoint. This path still requires investigation, appropriate tests,
review, and verification.

Use a written design and obtain explicit approval before changing ambiguous or
high-risk behavior, architecture, public APIs, material resolution, assignment
safety, cache or performance policy, security, CI/CD trust boundaries, or
repository process policy. Multi-step implementation then receives a test-first
plan and approval before execution. Stop again only when findings materially
change the agreed behavior, scope, risk, or architecture.

## Investigate and test first

Begin every defect or unexpected result with systematic debugging. Establish a
reproduction and root cause before proposing or editing production code. Trace
callers, consumers, public contracts, integration points, relevant tests, CI,
packaging, and preservation risks in proportion to the possible blast radius.

Production behavior changes use RED/GREEN TDD: create a generated or synthetic
regression, watch it fail for the intended reason, implement the smallest fix,
and watch it pass. If automation is genuinely impractical, document why, keep
the closest automated contract, and report the remaining manual check.

Never weaken, delete, skip, or rewrite a valid failing test merely to obtain a
green run. Add practical regressions for in-scope discoveries. Record unrelated
failures as follow-up work rather than silently expanding the branch.

## Branch before tracked edits

Inspect branch scope, its relationship to `main`, existing commits, the working
tree, and suitable local branches before the first tracked edit—including a
specification, plan, or handoff update.

Use an existing suitable branch or create a `codex/` topic branch. New topic
branches start from freshly fetched `origin/main`. If remote freshness cannot
be established, report the intended base SHA and obtain a user decision before
proceeding on a potentially stale base. In a managed workspace that prevents
Git metadata writes, use native workspace controls when available and report
the limitation; never mix the change into an unrelated branch.

One branch has one coherent objective. A distinct bug, refactor, cleanup, or
milestone belongs on a separate branch even when it touches the same component.
Do not create stacked pull requests without explicit approval. When dependent
work needs an unmerged branch, merge the prerequisite through its approved flow,
refresh `main`, and only then begin the dependent branch.

Preserve unrelated user changes. Do not discard, rewrite, stage, or commit them
to obtain a clean tree. Never commit ignored, private, credential-bearing,
machine-local, reference-only, or generated outputs unless the repository
explicitly requires the artifact.

## Designs and implementation plans

Scale documentation to risk. Durable design decisions may be committed and
retained. An implementation plan is not automatically committed merely to prove
that planning occurred. If a written plan is useful for review or multi-session
execution, keep it on the topic branch and through pull-request review. Remove a
committed design or plan only through a later intentional change when it is
genuinely superseded; do not commit and delete it in one milestone by default.

A useful implementation plan names exact files, RED/GREEN checks, validation,
preservation checks, and coherent commit boundaries. Record material deviations.
Obtain renewed approval only if a finding changes behavior, scope, risk, or
architecture.

## Execution and review

Inline execution is the default. Subagent-driven implementation, parallel
dispatch, and reviewer subagents require explicit user authorization and safely
independent work. When delegation is not authorized, perform a deliberate
self-review of the complete diff against the approved requirements.

Implement the smallest correct change. Prefer existing helpers, Blender and
Python native behavior, the standard library, minimal dependencies, minimal
abstractions, and deletion over speculative flexibility. Do not simplify away
validation, security, accessibility, preservation, or error handling that
prevents data loss.

Commit each coherent verified unit before beginning a materially different
unit. Stage explicit paths, inspect the staged diff, and ensure the commit
message describes only its contents.

## Verification and completion

During implementation, run the smallest relevant test frequently and affected
tests before each coherent commit. Before a completion claim, run the full gate
selected by `AGENTS.md`, `docs/testing.md`, and `docs/performance.md`; read the
fresh output and report failures rather than extrapolating from partial checks.

Review the complete branch diff and commit history for accidental scope growth.
The branch is complete only when its objective and acceptance criteria are met,
applicable validation passes, required documentation is current, and no known
in-scope blocker remains.

Use the repository-specific completion path: update the durable handoff and
report the verified branch ready for review or separately authorized
publication. Do not offer a local merge. Do not automatically invoke a generic
finishing workflow that conflicts with protected `main` or the authorization
rules below.

## Handoff maintenance

Update `docs/HANDOFF.md` at a durable pause, ownership transfer, material
blocker, or branch completion—not after every tool action or turn. State the
branch purpose and base, important decisions, completed work, exact validation
and results, known limitations or follow-up work, and the immediate next action.
Remove stale details that no longer affect that next action.

When a branch is complete and the next objective needs another branch, recommend
a new task after the handoff is accurate. Do not extend a completed branch with
unrelated work merely because the conversation continues.

## Git publication safety

`main` is protected and accepts changes only through a pull request based on
`main`. Do not offer a local merge. Do not push, merge, publish, create tags,
initialize another repository, change remotes, change repository settings or
visibility, configure protection, delete branches, rewrite published history,
or discard work without the surrounding explicit authorization. A rejected
push is investigated; it never authorizes a force push.

If publication is authorized, verify the branch first, push its named topic
branch, and create a pull request based on `main`. Keep the branch and workspace
for review feedback. Release publication, failed-draft cleanup, and repository
administration remain separately authorized operations.
