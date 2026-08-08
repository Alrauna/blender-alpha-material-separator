# macOS Apple Silicon CI Design

Date: 2026-08-08

Status: Approved in conversation; implementation not started

## Objective

Add native macOS Apple Silicon to the existing Blender 5.2 validation matrix.
The new `CI / macOS — Blender 5.2` job must run the same ordinary unit,
headless Blender, source-validation, build, and built-ZIP validation gates as
the existing Windows and Linux jobs.

The change validates the extension on a third operating system and CPU
architecture. It does not change extension runtime behavior, packaging shape,
release publication, or repository settings.

## Reference and adopted decisions

The implementation follows the proven platform acquisition shape in
`Alrauna/material-combiner-addon`:

- GitHub-hosted `macos-15` runner;
- platform key `macos` and label `macOS`;
- Blender 5.2.0 Apple Silicon disk image
  `blender-5.2.0-macos-arm64.dmg`;
- committed archive SHA-256
  `ed4d8390166dec5ea0a2813a03db6221f206ce016442be7f59f41d760972568a`;
- `Blender.app/Contents/MacOS/Blender` as the executable;
- `Blender.app/Contents/Resources/5.2/python/bin/python3.*` as bundled Python;
- `hdiutil attach -nobrowse -readonly -plist` with `plistlib` parsing;
- an exact single mount point, symlink-preserving application-bundle copy, and
  detachment in `finally`.

Only the macOS platform-acquisition details are adopted. This repository keeps
its existing workflow structure, PowerShell steps, test commands, release job,
and stricter current CI trust contracts. GitHub's published `macos-15` Apple
Silicon runner inventory includes PowerShell 7, so the existing `pwsh` steps do
not need a shell conversion:
<https://github.com/actions/runner-images/blob/main/images/macos/macos-15-arm64-Readme.md>.

## Workflow design

Extend the `validate` job's existing explicit matrix with:

```yaml
- runner: macos-15
  label: macOS
  platform: macos
```

The matrix entry uses every existing validation step unchanged:

1. credential-free pinned checkout;
2. verified Blender 5.2.0 acquisition;
3. bundled-Python unit tests;
4. complete background Blender suite with auto-execution disabled;
5. source extension validation;
6. extension ZIP build into the runner's temporary directory;
7. version-independent discovery of exactly one AMS ZIP;
8. built-ZIP validation.

The job name remains `CI / ${{ matrix.label }} — Blender 5.2`, producing the
stable check name `CI / macOS — Blender 5.2`.

The release and release-gate jobs remain Windows/Linux-dependent exactly as
they are. Adding macOS to the validation matrix makes a manual release wait for
the third validation leg through the existing `needs: [validate,
release_gate]`; publication still rebuilds on Windows and publishes the same
single platform-independent ZIP.

No action, cache, artifact transfer, dependency, container, self-hosted runner,
permission, trigger, or new network source is added.

## Verified Blender acquisition

`scripts/ci.py` will represent each platform with explicit archive root,
executable path, and bundled-Python directory metadata. Windows and Linux
values preserve their current resolved paths. macOS adds the DMG-specific
values listed above.

The existing three-path checksum process remains authoritative:

- system DNS HTTPS download;
- Cloudflare DNS-over-HTTPS HTTPS download;
- Quad9 DNS-over-TLS resolution followed by hostname-preserving HTTPS;
- byte-identical checksum manifests;
- agreement with the committed SHA-256;
- archive hash before extraction;
- exact `Blender 5.2.0 LTS` executable banner after extraction.

For macOS extraction, `hdiutil` returns a plist. The implementation parses
`system-entities`, accepts exactly one nonempty `mount-point`, checks that
`Blender.app` exists there, and copies it under the extraction directory with
`symlinks=True`. Once a mount point is known, detachment is attempted in
`finally`, including when validation or copying fails. Attach failure raises
directly because no mount is available to detach. Detach failure does not mask
an earlier extraction failure; hosted-runner cleanup remains a fallback after
the process exits.

All subprocess calls remain argument lists with no shell execution. GitHub
output values retain the existing newline rejection.

## Failure behavior

The new matrix leg fails closed when:

- any resolver or committed checksum disagrees;
- the DMG hash differs;
- `hdiutil` fails or returns malformed plist;
- zero or multiple mount points are reported;
- `Blender.app`, the executable, or bundled Python is missing;
- Blender reports any version other than the exact 5.2.0 LTS banner;
- any ordinary validation step fails;
- ZIP discovery finds anything other than exactly one AMS archive.

No macOS-specific `continue-on-error`, exclusion, or reduced test path is
allowed. Full parity is the acceptance criterion.

## Test-first implementation

The first production change will be preceded by failing unit and workflow
contract assertions covering:

- the exact macOS filename, committed SHA-256, application root, executable,
  and Python directory;
- `macos-15`, `macOS`, and `platform: macos` in the validation matrix;
- the stable macOS check name in documentation;
- plist parsing and the exact `hdiutil` attach arguments;
- one-mount enforcement;
- symlink-preserving `Blender.app` copy;
- detach on success and on a failure after attachment;
- macOS executable and bundled-Python path discovery;
- preservation of existing Windows and Linux platform identities and paths.

After GREEN on the targeted tests, the ordinary local completion gate is:

```powershell
$Blender52 = 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
$Python52 = 'C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe'
& $Python52 -m unittest discover -s tests/unit -t . -v
& $Blender52 --factory-startup --background --disable-autoexec `
  --python-exit-code 1 --python tests/blender/run_all.py
& $Blender52 --factory-startup --command extension validate addon
git diff --check
```

Windows cannot execute `hdiutil` or prove the Apple Silicon binary runs.
Therefore the hosted `CI / macOS — Blender 5.2` result is the authoritative
integration acceptance for DMG mounting, native execution, the complete
headless suite, and ZIP validation on macOS.

## Documentation and rollout

Update `docs/testing.md` to describe three validation checks and the exact
macOS acquisition and parity behavior. Update the CI workflow contract tests so
the third stable runner and check cannot disappear silently. Update
`docs/HANDOFF.md` with branch status, commands actually run, and hosted
validation still pending.

Repository branch protection is outside this branch. After the hosted macOS
job passes, making `CI / macOS — Blender 5.2` a required merge check needs
separate explicit approval and a repository-settings operation. Documentation
must not claim it is required until that setting is confirmed.

The private material reference smoke, installed-ZIP UI walkthrough, release
gate, and performance benchmark are not required: this branch changes CI
platform coverage only and no extension behavior, material analysis,
assignment, cache, packaging format, or performance path.

## Non-goals

- macOS Intel support;
- split-platform extension archives;
- universal binaries;
- changes to release assets or the release runner;
- shell conversion from PowerShell to Bash;
- concurrency, caching, artifacts, linters, Dependabot, or runner-cost work;
- runtime code changes;
- branch-protection or other GitHub repository-setting changes.
