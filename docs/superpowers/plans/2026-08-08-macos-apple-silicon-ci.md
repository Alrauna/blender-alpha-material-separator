# macOS Apple Silicon CI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans task-by-task. subagent-driven-development is allowed only when the user explicitly requests subagents.

**Goal:** Add CI / macOS — Blender 5.2 to the existing validation matrix with full Windows/Linux parity using a hash-verified Blender 5.2.0 Apple Silicon DMG.

**Architecture:** Make archive root, Blender executable, and bundled-Python paths explicit platform metadata. Add one macOS-only hdiutil extraction adapter and one macos-15 matrix row; keep every validation step shared.

**Tech Stack:** Python 3.13 standard library, unittest.mock, GitHub Actions YAML, PowerShell 7, Blender 5.2 CLI.

## Global Constraints

- Use macos-15 and blender-5.2.0-macos-arm64.dmg.
- Require SHA-256 ed4d8390166dec5ea0a2813a03db6221f206ce016442be7f59f41d760972568a.
- Preserve system DNS, Cloudflare DoH, Quad9 DoT, TLS, committed hash, exact archive root, and exact Blender-version checks.
- Preserve read-only default permissions, pinned checkout, disabled checkout credentials, and the Windows-only release writer.
- Add no action, cache, artifact, dependency, container, permission, trigger, or network source.
- Run the same unit, complete headless, source-validation, build, and ZIP-validation steps on all three platforms.
- Do not change addon behavior, release output, branch protection, or repository settings.
- Demonstrate RED before production/configuration edits; stage explicit paths only.

---

### Task 1: Verified Apple Silicon Blender acquisition

**Files:**
- Modify: tests/unit/test_ci.py
- Modify: scripts/ci.py

**Interfaces:**
- Produces PLATFORMS["macos"], extract_dmg(archive: Path, output: Path, root: str) -> None, and bundled_python_path(platform: str, root: Path) -> Path.
- Adds root and python_dir metadata for every platform while preserving Windows/Linux resolved paths.

- [ ] **Step 1: Write failing identity and path tests**

Add plistlib to test imports and:

~~~python
MACOS_SHA256 = (
    "ed4d8390166dec5ea0a2813a03db6221"
    "f206ce016442be7f59f41d760972568a"
)
~~~

Extend test_fixed_blender_5_2_0_trust_anchors:

~~~python
macos = ci.PLATFORMS["macos"]
self.assertEqual(macos["filename"], "blender-5.2.0-macos-arm64.dmg")
self.assertEqual(macos["sha256"], MACOS_SHA256)
self.assertEqual(macos["root"], "Blender.app")
self.assertEqual(macos["executable"], "Contents/MacOS/Blender")
self.assertEqual(
    macos["python_dir"],
    "Contents/Resources/5.2/python/bin",
)
self.assertEqual(macos["python_pattern"], "python3.*")
~~~

Add test_platform_paths_cover_archives_and_application_bundles. In a temporary directory, create each platform's metadata root, executable, and one matching Python file. Assert blender_executable_path and bundled_python_path return those exact resolved files for windows, linux, and macos. This is the paired preservation test for existing paths.

- [ ] **Step 2: Run identity/path tests and record RED**

~~~powershell
$Python52 = 'C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe'
& $Python52 -m unittest tests.unit.test_ci.CiTrustTests.test_fixed_blender_5_2_0_trust_anchors tests.unit.test_ci.CiTrustTests.test_platform_paths_cover_archives_and_application_bundles -v
~~~

Expected: FAIL because macos metadata and bundled_python_path do not exist.

- [ ] **Step 3: Write failing DMG lifecycle tests**

Add:

~~~python
def dmg_plist(*mount_points: Path) -> bytes:
    return plistlib.dumps(
        {
            "system-entities": [
                {"mount-point": str(mount)}
                for mount in mount_points
            ]
        }
    )
~~~

Add test_extract_dmg_copies_one_bundle_and_detaches. Mock attach stdout to one mount, Path.is_dir to true, and shutil.copytree. Assert:

~~~python
copytree.assert_called_once_with(
    Path("/Volumes/Blender/Blender.app"),
    Path("out/Blender.app"),
    symlinks=True,
)
self.assertEqual(
    run.call_args_list,
    [
        mock.call(
            [
                "hdiutil", "attach", "-nobrowse", "-readonly",
                "-plist", "blender.dmg",
            ],
            check=True,
            capture_output=True,
        ),
        mock.call(
            ["hdiutil", "detach", "/Volumes/Blender", "-quiet"],
            check=False,
        ),
    ],
)
~~~

Add test_extract_dmg_requires_exactly_one_mount for zero and two mount points, both raising ValueError matching "one mount point". Add test_extract_dmg_detaches_after_copy_failure: make copytree raise RuntimeError("copy failed"), assert the original error survives, and assert detach is the final subprocess call.

- [ ] **Step 4: Run lifecycle tests and record RED**

~~~powershell
& $Python52 -m unittest tests.unit.test_ci.CiTrustTests.test_extract_dmg_copies_one_bundle_and_detaches tests.unit.test_ci.CiTrustTests.test_extract_dmg_requires_exactly_one_mount tests.unit.test_ci.CiTrustTests.test_extract_dmg_detaches_after_copy_failure -v
~~~

Expected: ERROR because extract_dmg does not exist.

- [ ] **Step 5: Implement minimal acquisition support**

Import plistlib. Add root and python_dir to Windows/Linux with their current values. Add:

~~~python
"macos": {
    "filename": "blender-5.2.0-macos-arm64.dmg",
    "sha256": (
        "ed4d8390166dec5ea0a2813a03db6221"
        "f206ce016442be7f59f41d760972568a"
    ),
    "root": "Blender.app",
    "executable": "Contents/MacOS/Blender",
    "python_dir": "Contents/Resources/5.2/python/bin",
    "python_pattern": "python3.*",
},
~~~

Implement:

~~~python
def extract_dmg(archive: Path, output: Path, root: str) -> None:
    attached = subprocess.run(
        [
            "hdiutil", "attach", "-nobrowse", "-readonly",
            "-plist", str(archive),
        ],
        check=True,
        capture_output=True,
    )
    entities = plistlib.loads(attached.stdout)["system-entities"]
    mount_points = [
        entity["mount-point"]
        for entity in entities
        if entity.get("mount-point")
    ]
    if len(mount_points) != 1:
        raise ValueError(f"expected one mount point, got {mount_points}")
    mount = Path(mount_points[0])
    try:
        source = mount / root
        if not source.is_dir():
            raise ValueError(f"{root} not found in the disk image")
        shutil.copytree(source, output / root, symlinks=True)
    finally:
        subprocess.run(
            ["hdiutil", "detach", str(mount), "-quiet"],
            check=False,
        )
~~~

Dispatch extract_archive to extract_dmg on macos, retain filter="data" on Linux, and retain ordinary unpacking on Windows.

Change blender_executable_path to extracted / metadata["root"] / metadata["executable"], retaining is_file validation. Implement:

~~~python
def bundled_python_path(platform: str, root: Path) -> Path:
    metadata = PLATFORMS[platform]
    matches = [
        path.resolve()
        for path in (root / metadata["python_dir"]).glob(
            metadata["python_pattern"]
        )
        if path.is_file() and "config" not in path.name
    ]
    if not matches:
        raise ValueError("bundled Python executable was not found")
    return min(matches, key=lambda path: len(path.name))
~~~

In prepare_blender use root = extract_dir / metadata["root"] and python = bundled_python_path(platform, root).

- [ ] **Step 6: Run GREEN and the complete unit suite**

~~~powershell
& $Python52 -m unittest tests.unit.test_ci -v
& $Python52 -m unittest discover -s tests/unit -t . -v
~~~

Expected: all CI trust tests and the complete unit suite pass; the path test proves Windows/Linux preservation.

- [ ] **Step 7: Commit**

~~~powershell
git add -- scripts/ci.py tests/unit/test_ci.py
git diff --cached --check
git diff --cached
git commit -m "ci: acquire verified Blender on Apple Silicon"
~~~

---

### Task 2: Full-parity validation matrix

**Files:**
- Modify: tests/unit/test_ci_workflow_contract.py
- Modify: .github/workflows/ci.yml
- Modify: docs/testing.md

**Interfaces:**
- Consumes prepare-blender --platform macos.
- Produces stable check CI / macOS — Blender 5.2 on macos-15 through the existing shared validate job.

- [ ] **Step 1: Write failing workflow contracts**

Extend test_validation_triggers_and_stable_names with runner: macos-15, label: macOS, and platform: macos.

Add:

~~~python
def test_macos_uses_the_complete_shared_validation_job(self) -> None:
    validate = self.text.split("\n  release_gate:\n", 1)[0]
    self.assertIn("runner: macos-15", validate)
    self.assertIn("label: macOS", validate)
    self.assertIn("platform: macos", validate)
    self.assertEqual(validate.count("steps:"), 1)
    self.assertNotIn("continue-on-error", validate)
    self.assertNotIn("matrix.platform != 'macos'", validate)
~~~

Extend test_ci_security_and_rollout_are_documented so docs/testing.md must contain CI / macOS — Blender 5.2, macos-15, blender-5.2.0-macos-arm64.dmg, and hdiutil.

- [ ] **Step 2: Run contract tests and record RED**

~~~powershell
& $Python52 -m unittest tests.unit.test_ci_workflow_contract -v
~~~

Expected: FAIL because the matrix row and documentation are absent.

- [ ] **Step 3: Add the single matrix row**

Append only:

~~~yaml
- runner: macos-15
  label: macOS
  platform: macos
~~~

Do not condition or duplicate any validation step; do not change release jobs.

- [ ] **Step 4: Document parity and rollout**

In docs/testing.md:

- change two stable checks to three and add the macOS check;
- identify macos-15 as Apple Silicon;
- state it runs the same unit, complete headless, source validation, build, and ZIP validation;
- document the official DMG, committed hash, plist-parsed hdiutil mount, symlink-preserving Blender.app copy, and detach;
- state the check is not required branch protection until separately approved and confirmed;
- retain current private-smoke and benchmark exclusions.

- [ ] **Step 5: Run GREEN and full units**

~~~powershell
& $Python52 -m unittest tests.unit.test_ci_workflow_contract -v
& $Python52 -m unittest discover -s tests/unit -t . -v
~~~

Expected: workflow contracts and complete units pass.

- [ ] **Step 6: Commit**

~~~powershell
git add -- .github/workflows/ci.yml tests/unit/test_ci_workflow_contract.py docs/testing.md
git diff --cached --check
git diff --cached
git commit -m "ci: validate Blender on macOS Apple Silicon"
~~~

---

### Task 3: Local completion gate and review handoff

**Files:**
- Modify: docs/HANDOFF.md
- Preserve until hosted success: the design spec and this plan.

- [ ] **Step 1: Re-run targeted tests**

~~~powershell
& $Python52 -m unittest tests.unit.test_ci tests.unit.test_ci_workflow_contract -v
~~~

- [ ] **Step 2: Run the full local gate**

~~~powershell
$Blender52 = 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
& $Python52 -m unittest discover -s tests/unit -t . -v
& $Blender52 --factory-startup --background --disable-autoexec --python-exit-code 1 --python tests/blender/run_all.py
& $Blender52 --factory-startup --command extension validate addon
Remove-Item .\.packaged-releases\*.zip -ErrorAction SilentlyContinue
& $Blender52 --factory-startup --command extension build --source-dir addon --output-dir .packaged-releases
$Archive = @(Get-ChildItem .\.packaged-releases\alpha_material_separator-*.zip)
if ($Archive.Count -ne 1) { throw "Expected exactly one AMS ZIP, found $($Archive.Count)." }
& $Blender52 --factory-startup --command extension validate $Archive[0].FullName
git diff --check
~~~

Expected: units and headless pass; source and exactly one built ZIP validate; whitespace is clean.

- [ ] **Step 3: Review security and scope**

Invoke superpowers:requesting-code-review. Review origin/main...HEAD and confirm resolver/TLS/hash controls are unchanged; no action, permission, trigger, cache, artifact, dependency, redirect, or release behavior was added; DMG calls use argument lists, read-only mount, plist, one mount, symlink copy, and finally detach; Windows/Linux paths are preserved; macOS shares every validation step; no addon runtime file changed.

Use superpowers:receiving-code-review before acting on feedback and rerun affected gates.

- [ ] **Step 4: Update and commit handoff**

Record commit IDs, files, commands/results, archive validation, and why private smoke, benchmark, and installed UI are not required. State macOS remains unexecuted until push/PR and recommend obtaining publication authority. Do not call the milestone complete or remove spec/plan.

~~~powershell
git add -- docs/HANDOFF.md
git diff --cached --check
git diff --cached
git commit -m "docs: hand off macOS CI validation"
~~~

---

### Task 4: Hosted acceptance and milestone cleanup

**Files:**
- Modify: docs/HANDOFF.md
- Delete only after hosted success: design spec and implementation plan.

- [ ] **Step 1: Stop for authority**

Do not push or open a PR without explicit user approval.

- [ ] **Step 2: Require three hosted successes**

Require CI / Windows — Blender 5.2, CI / Linux — Blender 5.2, and CI / macOS — Blender 5.2. Use github:gh-fix-ci for failures. Never exclude or soften macOS to get green.

- [ ] **Step 3: Record acceptance and remove completed artifacts**

After all three pass, update HANDOFF, remove the spec and plan, inspect the staged diff, and commit:

~~~powershell
git rm docs/superpowers/specs/2026-08-08-macos-apple-silicon-ci-design.md docs/superpowers/plans/2026-08-08-macos-apple-silicon-ci.md
git add -- docs/HANDOFF.md
git diff --cached --check
git diff --cached
git commit -m "docs: close macOS CI milestone"
~~~

- [ ] **Step 4: Re-run hosted checks after cleanup**

Push only with approval and require all three hosted checks again. Branch-protection changes remain separate and explicitly approved.
