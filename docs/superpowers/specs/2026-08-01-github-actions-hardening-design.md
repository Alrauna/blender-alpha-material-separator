# GitHub Actions pre-push hardening design

Date: 2026-08-01

## Objective

Correct the audited security and reliability weaknesses in the local
`ci/automation` workflow before its first push, without expanding the
extension, publication surface, or dependency set.

This design preserves the approved Windows/Linux validation, Blender download
trust chain, protected manual publication, draft-first release, and immutable
release model.

## Scope

This milestone will:

- remove `actions/checkout` from the write-authorized release job;
- fetch the exact public release commit with unauthenticated native Git;
- remove dispatch-ref and repository-visibility values from shell source;
- validate the ordinary CI ZIP without a hard-coded extension version;
- add bounded curl connection, transfer, and retry behavior;
- use safe tar extraction for the Linux Blender archive; and
- retain every existing validation, checksum, token, and release gate.

This milestone will not:

- publish a Blender extension repository or `index.json`;
- add a custom updater, signing key, artifact attestation, or GitHub Pages;
- add workflow artifact transfer, caches, setup actions, or dependencies;
- change extension code, behavior, API, packaging contents, or permissions;
- push, open a pull request, alter GitHub settings, or publish a release.

Blender native extension-repository hosting is a separate later milestone.
AMS will not contain a custom updater.

## Release source retrieval

Read-only validation and release-gate jobs retain the pinned
`actions/checkout` action with `contents: read` and
`persist-credentials: false`.

The release job retains job-scoped `contents: write` but invokes no action. It
uses native Git to:

1. initialize the empty GitHub workspace;
2. add the public repository as an unauthenticated HTTPS remote;
3. fetch only the exact commit in `GITHUB_SHA`;
4. check out that commit in detached mode; and
5. require `git rev-parse HEAD` to equal `GITHUB_SHA`.

The repository must already be public and the dispatch ref must be `main`.
Git receives no token or credential. `GH_TOKEN` remains present only in the
individual GitHub CLI steps that inspect, create, upload, download, or publish
the release.

Any Git fetch, checkout, or identity mismatch stops publication.

## Release gating

The `release_gate` job uses a GitHub `if:` expression to require:

- `workflow_dispatch`;
- `refs/heads/main`; and
- public repository visibility.

The duplicate PowerShell checks for ref and visibility are removed. This keeps
potentially untrusted ref text out of shell source. The remaining gate command
validates the environment-provided release version against
`addon/blender_manifest.toml`.

Invalid dispatch contexts are skipped before shell execution.

## Version-independent validation ZIP

The ordinary Windows/Linux validation job builds into a new temporary release
directory. It then:

1. finds ZIP files matching the AMS package prefix;
2. requires exactly one match; and
3. passes that exact path to Blender extension validation.

This removes `1.0.0` from ordinary CI without adding a second version parser.
No result or multiple results fail the job.

The publication job retains its stricter version-derived archive name because
the release version is validated against the manifest before use.

## Bounded network behavior

Every curl request retains:

- HTTPS-only protocol;
- TLS 1.2 or newer;
- certificate and hostname validation;
- redirect rejection;
- exact HTTP 200 validation;
- system-DNS, Cloudflare DoH, and Quad9 DoH checksum consensus; and
- committed SHA-256 agreement before extraction.

Each request adds:

- a 30-second connection timeout;
- a fixed total transfer/retry time limit;
- two retries with a short fixed delay; and
- retry coverage for transient DNS, connection, and HTTP failures.

Retries do not disable or bypass any TLS, HTTP, resolver-consensus, or checksum
requirement. Exhaustion is a hard failure.

The existing RFC 8484 fallback remains deferred unless GitHub-hosted runners
reproduce the local curl/Quad9 failure.

## Archive extraction

The verified Linux `.tar.xz` archive uses Python's `filter="data"` extraction
mode. Windows ZIP extraction remains unchanged because ZIP extraction does not
accept this tar filter.

Extraction still begins only after the archive matches the committed SHA-256.

## Failure behavior

The workflow fails closed when:

- native Git cannot fetch or check out the exact commit;
- checked-out `HEAD` differs from `GITHUB_SHA`;
- the build emits zero or multiple AMS ZIP files;
- network retry or timeout limits are exhausted;
- resolver checksum content disagrees;
- an archive hash, Blender version, source validation, or ZIP validation fails;
- release input disagrees with the manifest;
- a tag or release already exists; or
- the stored release ZIP does not retain its pre-upload hash.

A failure after draft creation leaves an unpublished draft for inspection.
Automation never overwrites or deletes an existing tag, release, asset, or
draft.

## Test-first contracts

RED tests must first establish each current defect. The smallest production
changes then make them GREEN.

Generated contracts will prove:

- no `actions/checkout` or other action runs in the write-authorized job;
- checkout remains full-SHA pinned and read-only in the other jobs;
- native Git fetches and verifies the exact `GITHUB_SHA` without credentials;
- dispatch ref and visibility never enter shell source;
- ordinary ZIP validation contains no fixed AMS release version;
- ordinary validation requires exactly one built ZIP;
- curl commands contain bounded connection, transfer, and retry options;
- retries retain HTTPS-only and fail-closed behavior;
- Linux uses safe tar filtering; and
- all existing platform, resolver, checksum, token-scope, draft-first, and
  post-upload verification contracts remain intact.

The completion gate is:

1. focused CI helper and workflow contracts;
2. the complete unit suite;
3. the complete headless Blender suite;
4. source extension validation;
5. fresh ZIP build and exact archive validation;
6. extension-package boundary inspection;
7. `git diff --check`;
8. independent correctness and security review; and
9. Ponytail over-engineering review.

The private before/after `.blend` smoke is not required because this milestone
does not affect material resolution, rasterization, classification, cache
validity, preview, assignment, or mutation behavior.

## Rollout boundary

After local implementation, verification, review, and scoped commits, work
stops for approval.

Separate approval remains required before:

- pushing `ci/automation` or opening a pull request;
- changing repository visibility, branch protection, release-environment
  protection, or immutable-release settings;
- merging the branch or publishing release `1.0.0`; and
- designing or deploying Blender extension-repository hosting.
