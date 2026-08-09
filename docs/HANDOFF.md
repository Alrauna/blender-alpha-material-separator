# Repository handoff

Updated: 2026-08-09

## Current objective

`codex/ci-release-attestation-1.3.1` is a topic branch from refreshed `main` at
`fb80d9d8e8b793e239a9b879172ae2dbe165000a`. Its bounded objective is to add
least-privilege GitHub build-provenance attestation for the exact extension ZIP
stored on a draft release and to prepare version 1.3.1.

Implementation is locally complete through these commits:

- `872c403` — approved release-attestation design and corrected repository
  handoff;
- `fb56115` — approved RED/GREEN implementation plan;
- `e3358ae` — three-job release split and workflow security contracts;
- `2405ae8` — version 1.3.1, permanent verification guidance, and documentation
  contracts;
- `8c21bfd` — isolated validated release outputs through step-local environment
  variables and strengthened native-`gh` token-scope contracts.

The implementation has not been pushed, published, tagged, or submitted as a
pull request. Repository settings and environment rules are unchanged.

## Implemented release boundary

- `release_draft` is the protected Windows job with `contents: write`. It
  retains exact unauthenticated `GITHUB_SHA` fetch, Blender build/validation,
  strict release identity, `SHA256SUMS.txt`, existing tag/release refusal,
  draft creation, asset upload, stored-ZIP download, and digest verification.
  It executes no action and exposes only validated version, tag, archive name,
  and SHA-256 outputs.
- `release_attestation` depends on the successful draft job. It independently
  downloads and hashes the stored ZIP, then runs
  `actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6`
  (v4.2.2). Its token permissions are exactly `contents: read`,
  `id-token: write`, and `attestations: write`; it never receives
  `contents: write`.
- `release_publish` depends on both earlier jobs. It is protected, has
  `contents: write`, executes no action, and publishes the draft through one
  native `gh release edit` step.
- All three jobs repeat the manual-dispatch, `main`, and public-repository
  guards. `GH_TOKEN` is present only on individual native `gh` steps.
- A failed build, upload, download, digest comparison, or attestation cannot
  publish the release. A post-draft failure leaves an unpublished draft.

Only `addon/blender_manifest.toml` and `README.md` carry the permanent product
version 1.3.1. Public API version remains 1.3. `docs/testing.md` keeps consumer
verification version-neutral by discovering exactly one
`alpha_material_separator-*.zip` before calling `gh attestation verify`.

## TDD evidence

Before the workflow edit, the two new focused contracts failed because the
three release jobs, native stored-ZIP hash, and attestation action were absent.
After the minimum workflow split, those two tests and the complete workflow
contract module passed. Review follow-up added a failing regression for direct
release-output interpolation before the minimum environment-variable fix; the
strengthened module now contains 17 passing tests.

Before documentation changed, the provenance documentation contract failed on
the missing `actions/attest` guidance. After changing only the manifest to
1.3.1, the existing README identity contract failed because README still named
1.3.0. The minimal documentation and README updates made the focused 21-test
set pass.

## Fresh local validation

Run on 2026-08-09 with Blender 5.2.0 LTS and bundled Python 3.13.13:

- focused workflow, README, manifest, and API contracts: 45 tests passed;
- complete unit suite: 120 tests passed;
- complete headless Blender suite exited 0 and ended
  `ALPHA_MATERIAL_SEPARATOR_BLENDER_TESTS_OK`;
- Blender source validation succeeded;
- the verified `.packaged-releases` directory was cleared of ZIPs, then built
  exactly one `alpha_material_separator-1.3.1.zip` at 72,588 bytes;
- Blender archive validation succeeded for that discovered ZIP;
- `git diff --check main...HEAD` reported no whitespace error before handoff
  closeout;
- the ignored generated archive was not staged.

Private-reference smoke, performance benchmarks, and installed interactive
material-workflow checks were not required because this branch changes no
resolver, rasterizer, classifier, cache, Preview, Apply, or preservation
behavior.

## Review status

The complete branch diff was reviewed locally for job count and ordering,
action allowlisting, exact pinning, permissions, environment guards, token
scope, subject path, stored digest flow, unchanged validation jobs/triggers,
version scope, and accidental generated output. Independent review reported no
Critical or Important findings. It raised two Minor hardening opportunities:
avoid direct interpolation of validated draft outputs into PowerShell and make
the `GH_TOKEN` contract prove exact native-`gh` step scope. Both were addressed
test-first in `8c21bfd` and the complete workflow contract module then passed.

## Hosted checks still pending

Pull-request validation can prove that the workflow parses and that the stable
Windows, Linux, and macOS jobs remain green, but it cannot exercise the guarded
manual release jobs.

The first separately authorized manual 1.3.1 dispatch must confirm:

- a job whose `GITHUB_TOKEN` has only `contents: read` can download the private
  draft-release asset;
- whether `release_draft` and `release_publish` referencing the protected
  `release` environment require one approval or two;
- the pinned action creates provenance for the exact downloaded ZIP;
- failed attestation leaves the release as a draft;
- after publication, the downloaded asset passes the version-neutral
  `gh attestation verify` command documented in `docs/testing.md`.

If read-only draft access fails, return to design review. Do not move the action
into a `contents: write` job or add a long-lived release token as an unreviewed
workaround.

## Next action

The branch is ready for final review and pull-request preparation. Pushing or
opening a draft pull request requires separate user authorization. The guarded
manual release and hosted checks remain future, separately authorized work.
