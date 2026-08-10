# AGENTS Policy Simplification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:executing-plans` to implement this plan task-by-task. The
> repository requires inline execution by default; use
> `superpowers:subagent-driven-development` only if the user explicitly
> authorizes subagents. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the contradictory 392-line `AGENTS.md` with a concise policy
router and move detailed development procedure to permanent conditional
documentation without weakening product, test, CI, release, privacy, or Git
safety.

**Architecture:** `AGENTS.md` will retain the product goal, non-negotiable
invariants, task-routing rules, a compact validation matrix, and publication
guards. `docs/development-workflow.md` will own the detailed risk-tiered process,
branch, review, artifact, handoff, and completion rules, while existing
`docs/testing.md`, `docs/performance.md`, and `docs/material-support.md` remain
authoritative for their domains. A focused unit contract will prevent the
removed contradictions and volatile CI detail from returning to the always-
loaded entry point.

**Tech Stack:** Markdown, Python 3 standard-library `unittest`, Git.

## Global Constraints

- This is a process-documentation change; do not modify the add-on, manifest,
  CI workflow, release behavior, material-support policy, or product coverage.
- Target Blender 5.2 LTS; retain manifest minimum `5.2.0` and
  `GPL-3.0-or-later` identity requirements verbatim.
- Preserve every Blender analysis, assignment, uncertainty, non-mutation, and
  data-preservation invariant currently in `AGENTS.md`.
- Preserve private-input confidentiality and explicit authorization for the
  ignored `.local-references` acceptance layer.
- Preserve protected `main`, PR-only landing, and explicit approval for push,
  PR creation, merge, tags, releases, and repository-setting changes.
- Preserve the CI permission, pinned-action, Blender-download, DNS consensus,
  artifact-identity, attestation, and exact-byte publication contracts in
  permanent documentation and tests.
- Use inline execution. Do not dispatch subagents unless the user explicitly
  selects the subagent-driven option.
- Keep the approved design and this plan on the topic branch through review;
  do not perform the old commit-then-delete lifecycle.

---

### Task 1: Establish the policy-routing contract

**Files:**

- Create: `tests/unit/test_agent_policy_contract.py`
- Modify: `tests/unit/test_ci_workflow_contract.py`
- Test: `tests/unit/test_agent_policy_contract.py`
- Test: `tests/unit/test_ci_workflow_contract.py`

**Interfaces:**

- Consumes: the approved decisions in
  `docs/superpowers/specs/2026-08-10-agents-policy-simplification-design.md`
  and permanent CI wording already present in `docs/testing.md` and `PLAN.md`.
- Produces: a stable documentation contract for the concise router, preserved
  invariants, conditional-policy links, conflict-free workflow wording, and
  permanent placement of CI/security details.

- [ ] **Step 1: Add the failing concise-router contract**

Create `tests/unit/test_agent_policy_contract.py` with this complete contract:

```python
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class AgentPolicyContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.agents_path = ROOT / "AGENTS.md"
        cls.workflow_path = ROOT / "docs" / "development-workflow.md"
        cls.agents = cls.agents_path.read_text(encoding="utf-8")

    def test_entry_point_is_concise_and_routes_conditional_policy(self) -> None:
        self.assertTrue(self.workflow_path.is_file())
        self.assertLessEqual(len(self.agents.splitlines()), 180)
        for path in (
            "docs/development-workflow.md",
            "docs/testing.md",
            "docs/performance.md",
            "docs/material-support.md",
        ):
            self.assertIn(f"`{path}`", self.agents)

    def test_entry_point_retains_product_safety_invariants(self) -> None:
        for text in (
            "Blender 5.2 LTS",
            "minimum is `5.2.0`",
            "`GPL-3.0-or-later`",
            "`alpha_material_separator`",
            "Analyze original/base meshes, not evaluated modifier topology.",
            "Do not use centroid, vertex-only, sparse fixed sampling",
            "Source materials remain unchanged.",
            "Never modify unselected objects",
            "No topology changes",
            "No runtime network",
        ):
            self.assertIn(text, self.agents)

    def test_entry_point_drops_retired_conflicting_process(self) -> None:
        for text in (
            "Delete them from `main` once the milestone",
            "`requesting-code-review` for major or risky milestones",
            "`finishing-a-development-branch` only when integration",
            "An agent cannot drive the Blender UI",
            "Update `docs/HANDOFF.md` at the end of a turn that changes",
            "$Blender52",
            "Quad9's HTTP/2-only DoH endpoint",
        ):
            self.assertNotIn(text, self.agents)

    def test_workflow_resolves_execution_and_handoff_conflicts(self) -> None:
        self.assertTrue(self.workflow_path.is_file())
        workflow = self.workflow_path.read_text(encoding="utf-8")
        for text in (
            "before the first tracked edit",
            "The user's explicit request counts as design approval",
            "Inline execution is the default",
            "explicit user authorization",
            "Do not offer a local merge",
            "durable pause",
            "freshly fetched `origin/main`",
        ):
            self.assertIn(text, workflow)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Move the existing CI-documentation contract off `AGENTS.md`**

In
`tests/unit/test_ci_workflow_contract.py::CiWorkflowContractTests.test_ci_security_and_rollout_are_documented`,
assert the new permanent workflow document exists before reading it:

```python
workflow_path = ROOT / "docs" / "development-workflow.md"
self.assertTrue(workflow_path.is_file())
workflow = workflow_path.read_text(encoding="utf-8")
```

Replace the source combinations as follows:

```python
for text in (
    "actions/checkout",
    "persist-credentials: false",
    "contents: read",
    "contents: write",
):
    self.assertIn(text, testing)
self.assertIn("Do not push", workflow)

for text in (
    "read-only release-package job builds once",
    "same current-run workflow artifact",
    "re-downloads the stored ZIP",
):
    self.assertIn(text, testing + plan)
```

Keep the final download-verification group, but require each phrase in
`testing + plan` rather than `testing + agents + plan`. Remove the now-unused
`agents` read from that test. Do not weaken any string requirement; only change
its authoritative document source.

- [ ] **Step 3: Run the new contract to verify RED**

Run:

```powershell
python -m unittest tests.unit.test_agent_policy_contract -v
```

Expected: FAIL because `docs/development-workflow.md` does not exist, the old
`AGENTS.md` exceeds 180 lines, and it still contains the retired process text.

- [ ] **Step 4: Run the adjusted CI documentation contract to verify RED**

Run:

```powershell
python -m unittest `
  tests.unit.test_ci_workflow_contract.CiWorkflowContractTests.test_ci_security_and_rollout_are_documented `
  -v
```

Expected: FAIL because `docs/development-workflow.md` does not yet exist and
`docs/testing.md` does not yet contain the relocated checkout credential
requirements.

### Task 2: Implement the concise router and permanent workflow documentation

**Files:**

- Modify: `AGENTS.md`
- Create: `docs/development-workflow.md`
- Modify: `docs/testing.md`
- Modify: `README.md`
- Test: `tests/unit/test_agent_policy_contract.py`
- Test: `tests/unit/test_ci_workflow_contract.py`
- Test: `tests/unit/test_readme_contract.py`

**Interfaces:**

- Consumes: the RED contracts from Task 1 and the existing detailed policy in
  `AGENTS.md`, `docs/testing.md`, `docs/performance.md`, and
  `docs/material-support.md`.
- Produces: an `AGENTS.md` entry point of at most 180 lines, a permanent
  development workflow, preserved CI security documentation, and discoverable
  documentation links.

- [ ] **Step 1: Rewrite `AGENTS.md` as the entry point**

Replace its duplicated workflow, test methodology, CI internals, command
blocks, release checklist, and extended Git procedure with these sections:

```text
# Blender Alpha Material Separator repository guidance
## Goal
## Repository map and policy routing
## Instruction precedence
## Development workflow summary
## Compatibility and safety invariants
## Material support and private inputs
## Validation matrix
## Git and publication guard
## Handoff
```

The content must state all of the following directly:

- the existing overdraw goal and conservative-error preference;
- Blender 5.2 LTS, minimum `5.2.0`, `GPL-3.0-or-later`, and public identity;
- original/base mesh analysis and the intended Edit-to-Object Mode transition;
- exact UV texel coverage and prohibition of centroid, vertex-only, sparse
  fixed sampling, and post-budget approximation;
- Analyze immutability, Preview's allowed selection/mode effects, and Apply's
  exact reviewed mutation allowlist;
- source-material immutability, no topology changes, preservation list,
  uncertainty rules, local derived-material rules, undo, and idempotence;
- no modification of unselected objects, no silent localization, no CATS, no
  runtime network, telemetry, updater, or installer;
- no third-party runtime dependency shipped with or required by the extension;
- direct links to `docs/development-workflow.md`, `docs/testing.md`,
  `docs/performance.md`, and `docs/material-support.md` with task-routing
  conditions;
- direct user/safety precedence over repository docs, then skills, then generic
  defaults;
- concise risk tiers and the requirement to stop only for material changes to
  approved behavior, scope, risk, or architecture;
- the validation trigger matrix from the approved design;
- protected `main`, PR-only landing, and separate approval for publication and
  remote/repository mutations;
- handoff updates only at durable pauses, ownership transfer, material blockers,
  or branch completion.

Do not retain any retired string prohibited by
`test_entry_point_drops_retired_conflicting_process`. Keep the complete file at
or below 180 lines.

- [ ] **Step 2: Create the permanent development workflow**

Create `docs/development-workflow.md` with these sections and exact decisions:

```text
# Development workflow
## Scope and precedence
## Choose the workflow by risk
## Investigate and test first
## Branch before tracked edits
## Designs and implementation plans
## Execution and review
## Verification and completion
## Handoff maintenance
## Git publication safety
```

The document must state:

- branch suitability is checked before the first tracked edit, including specs,
  plans, and handoffs;
- fresh branches use freshly fetched `origin/main`, with a reported base SHA
  and user decision when freshness cannot be established;
- the user's explicit request counts as design approval for a narrow,
  unambiguous change;
- written design and plan approval remain mandatory for ambiguous, architectural,
  public-contract, material-support, security, or high-risk work;
- durable design records may remain committed; implementation plans are not
  automatically committed and deleted, and a committed plan stays through PR
  review until separately superseded;
- Inline execution is the default; subagent implementation, parallel dispatch,
  and reviewer subagents require explicit user authorization;
- self-review is the fallback when reviewer delegation is not authorized;
- targeted verification precedes coherent commits, while the applicable full
  branch gate precedes completion claims;
- Do not offer a local merge; report the verified branch ready and obtain
  separate approval before push or PR creation;
- `docs/HANDOFF.md` changes only at a durable pause, ownership transfer,
  material blocker, or branch completion;
- Do not push, merge, publish, create tags, alter repository settings, rewrite
  published history, delete branches, or discard work without the surrounding
  explicit authorization;
- unrelated discoveries are recorded as follow-up work rather than silently
  added to the branch.

- [ ] **Step 3: Complete the permanent testing and CI routing**

In the `GitHub Actions CI/CD` section of `docs/testing.md`, add this preserved
checkout contract near the other ordinary validation restrictions:

```markdown
All `actions/checkout` use remains confined to read-only jobs, pinned to a
reviewed full commit SHA, and configured with `persist-credentials: false`.
The read-only release-package job continues to use unauthenticated native Git
for exact-`GITHUB_SHA` source retrieval instead of checkout credentials.
```

In `Required test layers`, clarify the automation boundary with this policy:

```markdown
Committed and CI tests are deterministic and independent of private machine
state. The ignored `.local-references` validator is a separate, user-authorized
local acceptance layer. If an automated regression is genuinely impractical,
document why, retain the closest automated contract, and report the remaining
manual interaction explicitly.

Installed-ZIP UI acceptance requires human confirmation unless the current
harness is capable of controlling Blender and the user explicitly authorizes
it. Agent-run UI automation is supporting evidence and does not silently
replace a required human acceptance result.
```

Do not remove or weaken the existing state-invalidation, Preview, assignment,
preservation, performance, private-reference, CI, attestation, or publication
details.

- [ ] **Step 4: Make the workflow document discoverable**

Add this documentation link immediately before the existing testing link in
the README documentation list:

```markdown
- [Development workflow](docs/development-workflow.md)
```

Preserve the existing `docs/testing.md` link and every other README entry.

- [ ] **Step 5: Run focused GREEN verification**

Run:

```powershell
python -m unittest tests.unit.test_agent_policy_contract -v
python -m unittest `
  tests.unit.test_ci_workflow_contract.CiWorkflowContractTests.test_ci_security_and_rollout_are_documented `
  -v
python -m unittest tests.unit.test_readme_contract -v
```

Expected: all focused contracts PASS.

- [ ] **Step 6: Review and commit the policy implementation unit**

Run:

```powershell
git diff --check
git diff -- AGENTS.md docs/development-workflow.md docs/testing.md README.md `
  tests/unit/test_agent_policy_contract.py `
  tests/unit/test_ci_workflow_contract.py
```

Verify the diff changes no `.github`, `addon`, manifest, release, or Blender
runtime file. Stage only the six listed files and commit:

```powershell
git add -- AGENTS.md docs/development-workflow.md docs/testing.md README.md `
  tests/unit/test_agent_policy_contract.py `
  tests/unit/test_ci_workflow_contract.py
git commit -m "docs: simplify repository agent policy"
```

### Task 3: Verify preservation and close the branch handoff

**Files:**

- Modify: `docs/HANDOFF.md`
- Test: `tests/unit/test_agent_policy_contract.py`
- Test: `tests/unit/test_ci_workflow_contract.py`
- Test: `tests/unit/test_readme_contract.py`

**Interfaces:**

- Consumes: the completed Task 2 documentation and contract commit.
- Produces: fresh full-unit verification, preservation evidence, a complete
  branch diff review, and a durable handoff ready for user-authorized PR work.

- [ ] **Step 1: Run the complete unit gate**

Run:

```powershell
$Python52 = 'C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe'
& $Python52 -m unittest discover -s tests/unit -t . -v
```

Expected: all unit tests PASS with zero failures or errors.

- [ ] **Step 2: Run policy preservation searches**

Run:

```powershell
rg -n "Blender 5.2 LTS|minimum is `5.2.0`|GPL-3.0-or-later|alpha_material_separator|original/base meshes|centroid|Source materials remain unchanged|Never modify unselected objects|No topology changes|No runtime network" AGENTS.md
rg -n "actions/checkout|persist-credentials: false|Quad9 DoT|validated label boundaries|at most 16|release_package|release_attestation|release_publish|same current-run workflow artifact|re-downloads the stored ZIP" docs/testing.md PLAN.md
rg -n "before the first tracked edit|explicit request counts as design approval|Inline execution is the default|explicit user authorization|Do not offer a local merge|durable pause|freshly fetched `origin/main`|Do not push" docs/development-workflow.md
```

Expected: every required product, CI/security, and workflow phrase is found in
its intended authoritative document.

- [ ] **Step 3: Review the complete branch for scope and specification coverage**

Run:

```powershell
git diff --stat origin/main...HEAD
git diff origin/main...HEAD -- AGENTS.md README.md docs tests/unit
git log --oneline origin/main..HEAD
```

Check every section of
`docs/superpowers/specs/2026-08-10-agents-policy-simplification-design.md`
against the diff. Confirm that no add-on, workflow, manifest, packaging,
performance baseline, private input, or generated output changed.

- [ ] **Step 4: Update the durable handoff**

Replace the in-progress state in `docs/HANDOFF.md` with:

- branch purpose and base SHA;
- the design, plan, contract, and implementation commits;
- the risk-tier, inline-execution, self-review, artifact-lifecycle, branch,
  handoff, and publication decisions;
- exact focused and full-unit commands and results;
- explicit statement that Blender, private-reference, packaging, performance,
  and installed-ZIP gates were not applicable;
- no known limitation inside branch scope;
- next action: user review, then separately authorized push and PR creation.

Retain the note that unpublished 1.3.1 draft cleanup and release dispatch are
separate work.

- [ ] **Step 5: Run the final documentation gate and commit the handoff**

Run:

```powershell
git diff --check
git status --short
```

Stage only the handoff and commit:

```powershell
git add -- docs/HANDOFF.md
git diff --cached --check
git diff --cached -- docs/HANDOFF.md
git commit -m "docs: close AGENTS policy simplification"
```

- [ ] **Step 6: Verify the committed branch state**

Run fresh:

```powershell
& $Python52 -m unittest discover -s tests/unit -t . -v
git diff --check
git status --short --branch
git log --oneline origin/main..HEAD
```

Expected: the complete unit suite passes, the worktree has no uncommitted
tracked changes, and the branch contains only the approved design, plan,
policy-contract, documentation, and handoff commits.
