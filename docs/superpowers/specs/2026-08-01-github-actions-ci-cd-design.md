# GitHub Actions CI/CD design

Date: 2026-08-01

## Objective

Add a minimal GitHub Actions workflow that validates Blender Alpha Material
Separator 1.0.0 on GitHub-hosted Windows and Linux runners, blocks merging when
either platform fails, and publishes releases only through an explicit manual
action from `main`.

The design trusts GitHub-hosted runners and native GitHub release services. It
does not trust network-fetched Blender archives until they match Blender.org's
published SHA-256 values and independently committed expected hashes.

## Scope

The workflow will:

- validate pull requests targeting `main`;
- validate pushes to `main`;
- support an explicit manual release dispatch;
- test the same commit with Blender 5.2.0 LTS on Windows and Linux;
- build and validate an extension ZIP on each validation runner, then discard
  it with the runner;
- build a fresh release ZIP from the validated commit during publication;
- publish the ZIP and `SHA256SUMS.txt` through a draft-first immutable GitHub
  release.

The workflow will not use:

- third-party actions;
- secrets or long-lived credentials;
- dependency or build caches;
- containers or self-hosted runners;
- setup actions or external package installers;
- scheduled runs;
- `pull_request_target`;
- performance regression thresholds;
- private `.blend` files or `.local-references/` content;
- workflow artifact transfer between jobs.

## Workflow architecture

Use one workflow at `.github/workflows/ci.yml`.

### Triggers

- `pull_request` targeting `main`.
- `push` to `main`.
- `workflow_dispatch` with one required release-version input in strict
  `X.Y.Z` form.

Manual publication is permitted only when the dispatch ref is
`refs/heads/main`, the repository is public, and the requested version equals
the manifest version.

### Platform validation

Use one matrix validation definition with explicit Windows and Linux entries
and stable displayed job names:

- `CI / Windows — Blender 5.2`
- `CI / Linux — Blender 5.2`

Both entries:

1. Check out the triggering commit with `actions/checkout` pinned to a verified
   full commit SHA and persisted Git credentials disabled.
2. Establish the approved Blender download trust chain.
3. Run the unit suite with Blender's bundled Python.
4. Run the complete headless Blender suite with auto-execution disabled.
5. Validate the extension source.
6. Build the extension ZIP.
7. Validate that exact ZIP.
8. Allow the runner and ZIP to be destroyed after the job.

The workflow-level token permission is `contents: read`. Validation jobs
receive no write permission and no secrets.

Both named checks will be required before merging to `main`.

### Publication

The publication job:

- runs only for `workflow_dispatch` from `main`;
- waits for both matrix entries to pass;
- requires a protected `release` environment;
- receives job-scoped `contents: write`;
- checks out the exact validated commit with persisted Git credentials
  disabled;
- repeats the verified Windows Blender setup;
- builds and validates a fresh ZIP;
- computes the ZIP's SHA-256 and writes `SHA256SUMS.txt`;
- refuses an existing tag or release;
- creates the release as a draft;
- uploads the ZIP and checksum file;
- downloads the stored ZIP into a new temporary directory;
- requires its SHA-256 to match the pre-upload value;
- publishes the draft only after every check succeeds.

`GH_TOKEN` is supplied only to the individual GitHub CLI commands that inspect,
create, upload, download, or publish the release. It is not placed in the
environment of Blender, test, build, hashing, or packaging steps.

If verification fails after draft creation, the workflow leaves the draft
unpublished for inspection and fails. It does not automatically delete or
overwrite a tag, release, or asset.

## Blender download trust chain

Pin the exact Blender 5.2.0 LTS Windows x64 and Linux x64 archive filenames,
HTTPS URLs, official checksum-file URL, and SHA-256 values.

The expected Windows and Linux archive hashes must be copied from Blender.org's
published checksum data, reviewed, and committed. A checksum retrieved during
the workflow is never the sole trust anchor.

For each runner:

1. Download the same small Blender.org checksum file through:
   - the runner's system DNS;
   - Cloudflare DNS-over-HTTPS;
   - Quad9 DNS-over-HTTPS.
2. Require HTTPS certificate and hostname validation on all three paths.
3. Allow HTTPS only and reject an unexpected redirect.
4. Require the three checksum files to be byte-for-byte identical.
5. Require the relevant Blender.org entry to equal the committed expected
   archive hash.
6. Download the platform archive from its exact approved Blender.org URL into a
   new temporary directory.
7. Calculate its SHA-256 before extraction.
8. Require the calculated hash, resolver-consensus hash, and committed hash to
   agree.
9. Extract only after all checks pass.
10. Require the executable to report Blender 5.2.0 before using it.

Exact DNS IP comparison is intentionally excluded. CDN addresses and resolver
caches may legitimately differ, making an IP-equality gate brittle. Comparing
the TLS-authenticated checksum content reached through the three resolver paths
provides a deterministic check without assuming identical network routes.

The implementation will use native runner tools and standard-library code
only. It will not add DNS libraries, scanners, certificate pinning, fixed
Blender IPs, DNS-over-HTTPS actions, or other network dependencies.

## Release integrity

Before the first release:

- make the repository public;
- create and protect a `release` environment restricted to `main`;
- enable immutable releases.

The release version must:

- match `X.Y.Z`;
- match `addon/blender_manifest.toml`;
- correspond to tag `vX.Y.Z`;
- not already have a tag or release.

The release ZIP must:

- be built from the dispatched `main` commit after both platform checks pass;
- pass Blender extension validation;
- have its SHA-256 published in `SHA256SUMS.txt`;
- retain the same SHA-256 after upload and download from the draft release.

Draft-first publication allows all assets to be present and verified before
GitHub locks the published release tag and assets.

## Security boundaries

The design protects against:

- ordinary system-DNS poisoning;
- one resolver returning different Blender.org checksum content;
- archive-only or checksum-only replacement;
- insecure-protocol downgrade;
- accidental version mismatch;
- release publication from a non-`main` branch;
- test or build code receiving a repository write token;
- accidental replacement of an existing release;
- corruption or substitution during the normal upload/download path;
- later mutation of a published immutable release.

The design does not claim to protect against:

- a compromise of GitHub's runner or release platform inside the explicitly
  approved trust boundary;
- a Blender release that was already malicious when its official hash was
  reviewed and committed;
- compromise of all independent resolver paths, TLS validation, Blender.org,
  and the committed checksum together;
- compromised repository-owner credentials or deliberately approved malicious
  source changes.

No workflow can eliminate all unknown vulnerabilities. The goal is narrow
permissions, independent content verification, fail-closed publication, and
the smallest practical automation surface.

## Error handling

Every trust or validation failure stops the affected job. Messages identify the
failed layer without printing tokens or unnecessary network detail:

- TLS or download failure;
- resolver-content disagreement;
- official-versus-committed checksum disagreement;
- archive hash mismatch;
- Blender version mismatch;
- unit or headless test failure;
- source or ZIP validation failure;
- invalid release input;
- private-repository publication attempt;
- existing tag or release;
- uploaded-asset hash mismatch;
- draft publication failure.

Publication never continues after a failed prerequisite.

## Performance policy

CI runs correctness and benchmark-contract tests but does not enforce the
repository's 25 percent same-machine performance threshold. GitHub-hosted
runner hardware and load are not stable enough for that threshold to be a
reliable merge gate.

The established local same-machine benchmark remains the release performance
authority.

## Test strategy

Add generated, redistributable contracts before workflow implementation.
Tests will prove:

- approved triggers and no scheduled or privileged PR trigger;
- stable Windows and Linux check names;
- read-only default permissions;
- write permission limited to publication;
- full-SHA checkout pinning and disabled credential persistence;
- absence of secrets, caches, containers, self-hosted runners, setup actions,
  third-party actions, and artifact-transfer actions;
- fixed HTTPS Blender URLs and well-formed SHA-256 values;
- fail-closed checksum and resolver-consensus behavior;
- strict release-version and manifest agreement;
- `main`, public-repository, environment, and validation-job release gates;
- refusal to overwrite an existing tag or release;
- draft-first publication and post-upload hash comparison.

The ordinary project gate remains:

- all unit tests;
- the complete headless Blender suite;
- source manifest validation;
- extension build and ZIP validation;
- `git diff --check`.

The private default-example smoke is not required because this milestone does
not change material resolution, rasterization, classification, cache validity,
preview plans, assignment plans, or mutation behavior.

## Rollout

1. Implement and locally validate workflow contracts on `ci/automation`.
2. Push the branch only after separate user approval.
3. Allow Windows and Linux checks to run on GitHub.
4. Correct runner-specific issues without weakening the security boundaries.
5. Configure both check names as required for `main`.
6. Require pull requests, current branches, and protection from force-push or
   deletion.
7. Make the repository public.
8. Configure the protected `release` environment.
9. Enable immutable releases.
10. Manually dispatch release `1.0.0` from `main`.
11. Verify the published immutable release and downloadable asset.

GitHub requires a status check to run before it can be selected as required, so
the initial workflow push is a documented bootstrap exception.

On GitHub Free, private repositories can report the checks but cannot enforce
protected-branch requirements. Enforcement becomes available after the
repository is public.

## Approval boundaries

This design authorizes preparation of a separate test-first implementation plan
after written-spec review. It does not authorize:

- workflow implementation;
- network retrieval during implementation beyond the approved Blender and DNS
  characterization in the eventual plan;
- push or pull-request creation;
- repository visibility changes;
- branch-protection or environment changes;
- immutable-release configuration;
- tag or release creation.

Each remote mutation still requires explicit user approval.
