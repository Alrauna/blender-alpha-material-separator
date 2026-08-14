<!-- SPDX-License-Identifier: GPL-3.0-or-later -->

# GPU single-precision analysis design

Status: proposed. Not approved, not implemented.

Companion to `docs/gpu-rasterization.md`, which describes the kernel this
changes. Read that first; this document only records what is different.

## Objective

Make single-precision (fp32) the GPU kernel's default arithmetic on any machine
whose driver runs the kernel, and keep the existing double-precision (fp64)
kernel as an explicit *High precision GPU acceleration* mode in Expert Analysis
Settings.

A GPU without fp64 stops being a GPU this extension refuses. After this branch
it accelerates by default like any other, and the only consequence of missing
fp64 is that the high-precision checkbox cannot be switched on.

## Non-goals

- No fp16, no mixed precision, no automatic escalation from fp32 to fp64.
- No change to the CPU path, which stays the exactness oracle for everything.
- No per-material, per-object, or per-image precision selection.
- No change to the raster budget, the span cap, the fallback rules, the
  coverage cache, or the batch partitioning.
- No new texture format, no new upload channel, no new dependency.
- The report does not gain a user-visible "this ran in fp32" field. The input
  signature records it; a support field can be added later if reports actually
  turn out to need one.

## Why

Three reasons, in the order they matter.

**Coverage.** fp64 is the single largest reason a machine falls back to the
CPU. Metal has no `double` at all, so every Apple Silicon machine is on the CPU
today, and consumer drivers that do expose `double` are the ones most likely to
run it at a small fraction of fp32 rate. fp32 is universal.

**Speed.** Two independent wins. The triangle upload shrinks by 3× — an fp32
coordinate is one 32-bit word where an fp64 coordinate is three, and the merged
branch's measurements put a real share of the remaining GPU time in transfer.
Separately, consumer GPUs run fp64 at 1/16 to 1/64 of fp32 throughput, so the
arithmetic itself gets faster by a factor that is large wherever the kernel is
ALU-bound. The merged fp64 kernel took 27.2% off total analysis time on the
realistic tier; fp32 has to beat that, and the gate below says what happens if
it does not.

**Honesty about the requirement.** fp64 was chosen so GPU counts would be
bit-identical to CPU counts, which made the GPU path free of any correctness
argument: the self-test either reproduced the oracle exactly or the GPU was
refused. That is a *verification* convenience, not a geometric requirement. The
question this branch answers is what it actually costs to give it up.

## What changes about correctness

This is the load-bearing section. Everything else is plumbing.

### What the current guarantee is

The CPU rasterizer computes exact positive-area coverage of float64 UV
triangles against texel cells. The fp64 kernel reproduces it bit for bit,
verified per machine by `_self_test()` against `rasterize_batch`. Two devices,
one answer.

### What fp32 gives up

An fp32 coordinate carries a 24-bit significand, so two things round that do
not round today:

1. **The upload.** The CPU's coordinate is `uv * dimension` in float64.
   Narrowing it to fp32 rounds it by up to half an ulp.
2. **The span arithmetic.** The slope divisions and the multiply-add chain in
   the kernel each round, adding a few more ulps.

Together the computed boundary of a scanline span can sit up to roughly
`8 ulp` from the true boundary — about `5e-7` relative, which is `2e-3` of a
texel at coordinate 4096.

A count changes only when a true span boundary lies within that distance of a
texel edge *and* the rounding carries it across. The consequence is one texel
gained or lost at the end of one scanline run of one triangle, and it changes
the reported classification only if that texel is the one that decides the
face.

### The direction is not guaranteed, and that is the real cost

A gained texel is harmless in the repository's terms: a face that gains an
alpha texel moves to alpha, and over-moving is the direction the goal calls
safe. A *lost* texel is the failure the goal forbids — a transparent face left
on an opaque material.

So fp32 cannot be sold as conservative by construction, and this design does
not try to. Two rejected attempts at making it so, recorded so they are not
re-proposed:

- **Round every span outward by the error bound.** Fatal on the most common UV
  layout there is. Islands snapped to texel boundaries produce coordinates that
  are exactly representable and exactly on an edge, and padding them always
  pulls in one extra column and row of a neighbouring island — often that
  island's transparent padding. It would flip large numbers of genuinely opaque
  faces to alpha and destroy the optimization the extension exists to perform.
- **Detect ambiguous boundaries in the kernel and recount those polygons on the
  CPU.** Exact by construction and it reuses `rasterize_batch` on a subset, but
  a boundary that lands exactly on a texel edge is maximally ambiguous, and
  snapped UVs put nearly every boundary there. The common case would fall back
  wholesale.

What actually protects the reader is the shape of the error, and it is worth
stating precisely because it is better than it first sounds: the case where a
boundary sits exactly on a texel edge is also the case where `uv * dimension`
is a small dyadic number that fp32 represents *exactly*, so the boundary does
not move at all. The coordinates that round are the arbitrary ones, and an
arbitrary boundary is almost never within `2e-3` of a texel edge. The two
populations barely overlap. "Barely" is a measurement, not a proof, which is
why the default flip is gated on one.

### The invariant this contradicts

`AGENTS.md` currently reads:

> Use exact positive-area UV triangle/texel-cell coverage. Do not use centroid,
> vertex-only, sparse fixed sampling, or an approximation after a raster budget
> failure.

An fp32 default is not centroid, vertex-only, or sparse sampling, and it is not
a post-budget-failure approximation — it is the same exact coverage rule
evaluated in narrower arithmetic. The distinction is real but it is too fine to
leave to the reader of the invariant. **This branch must amend that paragraph,
and the amendment needs explicit approval before any code lands.** Proposed
replacement:

> Use exact positive-area UV triangle/texel-cell coverage. Do not use centroid,
> vertex-only, or sparse fixed sampling, and never approximate after a raster
> budget failure. The CPU path and the high-precision GPU path evaluate that
> rule in double precision and agree bit for bit. The default GPU path
> evaluates the same rule in single precision, where a span boundary can move
> by a few ulps; that is the only approved departure, it is measured before it
> ships, and it is switchable off in Expert Analysis Settings.

## Architecture

### One templated source, two kernels

`_SOURCE` is already a `%`-template. It gains one more substitution, the scalar
type, and the body stops naming `double`:

- Every `double` in the body becomes `scalar`, defined by the template as
  `double` or `float`.
- Every literal `0.0lf` / `1.0lf` becomes `scalar(0.0)` / `scalar(1.0)`. An
  explicit constructor is legal in both variants where the `lf` suffix is legal
  in only one. For the fp64 variant these are the same values, so the existing
  self-test proves the rewrite changed nothing.
- `precise` is kept on both. In fp32 it is no longer defending bit-equality
  with the CPU, but it still makes the result independent of whether a driver
  contracts a multiply-add, and the input signature promises a reader that the
  same scene analysed twice gives the same report.
- `chunked(int slot)` becomes `coord(int slot)`, and the template supplies one
  of two bodies: the existing three-word `packDouble2x32` reassembly, or, for
  fp32, `uintBitsToFloat(uint(imageLoad(tris, at(slot)).r))`.

Note for anyone editing the template: the `22 / 10 / 12` shifts inside
`chunked` are the fp64 coordinate chunking and are unrelated to `_BITS`, which
is the alpha-mask word width. Only the first disappears in the fp32 variant.

### Upload

`_prepare` grows the same branch. fp64 keeps `_chunked`; fp32 uploads
`triangles.astype(numpy.float32).view(numpy.uint32)` through the existing R32UI
texture and lets `uintBitsToFloat` reinterpret it on the other side. No new
format, no new exactness question about the transfer itself — the bits that
arrive are the bits that left — and one third of the words.

### The capability probe

`available()` today answers one question and caches one shader. It becomes two
of each, keyed by precision:

```python
def available(*, high_precision: bool = False) -> bool: ...
def reason(*, high_precision: bool = False) -> str: ...
```

The default argument keeps every existing call site — panel, properties,
engine, tests, benchmarks — unchanged.

Probe order for `high_precision=False`: the background opt-in gate, then build,
then `_self_test`. **`_has_fp64()` is no longer consulted.** For
`high_precision=True`: the same background gate, then `_has_fp64()`, then build,
then the fp64 self-test. Each is probed lazily on first ask and cached
separately, so a reader who never opens the Expert panel never pays for the
fp64 probe.

`NO_FP64` stops being a reason `available()` can return and becomes a reason
only `reason(high_precision=True)` can return.

### The fp32 self-test needs its own fixture

The current fixture is adversarial on purpose — coordinates near `1e7`, UVs far
outside the unit square, a degenerate triangle, non-axis-aligned middle
vertices — and it demands equality with the CPU oracle with no tolerance. fp32
cannot pass it, and loosening it to a tolerance would throw away the only thing
that catches a miscompiled kernel.

So the fp32 variant gets a second fixture, built so that fp32 is *provably*
exact on it, and keeps equality with no tolerance:

- Every coordinate is a small dyadic number (multiples of `0.25`, magnitude
  under `256`), exactly representable in fp32.
- Every triangle's vertical extents are powers of two, so each of the three
  slope divisions is an exact quotient and the multiply-add chain that follows
  is exact.
- Everything the current fixture exists to catch is preserved: non-power-of-two
  grid dimensions and negative coordinates (the GLSL negative-`%` defect),
  coordinates outside the unit square on both sides of both axes, a degenerate
  triangle, a three-triangle polygon, and middle vertices strictly inside a
  band.

A unit test asserts the fixture's exactness properties directly, so a later
edit that adds a convenient-looking `1.3` to it fails on an ordinary machine
rather than silently weakening a GPU self-test that only some machines run.

### Precision becomes an analysis input

It has to. fp32 and fp64 can produce different reports, so a report has to
record which one produced it or the STALE detection lies.

`AnalysisConfig` gains `high_precision: bool = False` alongside `use_gpu`, and
`payload()` gains exactly one derived field:

```python
"precision": "EXACT" if not self.use_gpu or self.high_precision else "FP32",
```

Derived rather than two booleans, because the CPU and the fp64 GPU produce
identical reports and switching between them still must not make a report
stale. That property is preserved exactly; what changes is that switching
*into or out of fp32* now does make it stale, correctly.

This reverses one of the merged branch's deliberate omissions — the comment on
`AnalysisConfig.use_gpu` saying the device is not an input rests on a premise
that fp32 makes false. Two consequences:

- `tests/blender/test_gpu_raster.py:166`, which asserts
  `AnalysisConfig().payload() == AnalysisConfig(use_gpu=False).payload()`, must
  now assert the opposite, plus the equality that survives:
  `AnalysisConfig(use_gpu=False).payload() ==
  AnalysisConfig(high_precision=True).payload()`.
- Neither toggle gains an `update=` callback. `_settings_changed` clears the
  review outright; the input signature already marks a mismatched report STALE,
  which is the more informative outcome and the smaller change. A reader who
  flips precision to compare keeps the report they are comparing against.

`high_precision_gpu` stays **out** of `ANALYSIS_SETTING_NAMES`, exactly like
`disable_gpu_acceleration`: it is a machine-and-precision choice, not one of
the analysis parameters that "Reset to Default Values" restores, and it is read
from the scene settings rather than passed as an `analyze()` keyword. The
existing test at `tests/blender/test_expert_analysis_settings.py:182` gains a
sibling assertion for the new name. No API version bump.

### Properties and panel

A second property, symmetric with the existing pair:

```python
def _high_precision_get(self) -> bool:
    # Forced off where fp64 cannot run, so the engine and any script read the
    # same refusal the panel draws.
    if _fp64_unavailable():
        return False
    return self.get("high_precision_gpu", False)

def _high_precision_set(self, value: bool) -> None:
    self["high_precision_gpu"] = bool(value)
```

`high_precision_gpu: BoolProperty(name="High precision GPU acceleration", ...)`,
default `False`, description along the lines of *"Analyse in double precision
on the GPU. Slower, and bit-identical to CPU analysis"*.

The panel draws it directly under the existing checkbox, below the reset
button, as a two-row GPU group:

```
[ ] Disable GPU acceleration
[ ] High precision GPU acceleration
```

Row enablement:

- GPU unusable at all: both rows disabled, existing message drawn, minus its
  `NO_FP64` branch — that reason can no longer reach it.
- GPU usable, fp64 missing: the high-precision row alone is disabled, with new
  copy that does not claim acceleration is off. Proposed: *"This GPU does not
  compute in double precision. Analysis still runs on the GPU in single
  precision; use Disable GPU acceleration for exact results."*
- GPU usable, "Disable GPU acceleration" checked: the high-precision row is
  disabled because there is no GPU in play, and its stored value persists.

`_gpu_unavailable_message()` loses its `NO_FP64` branch; a new
`_fp64_unavailable_message()` carries the copy above.

### Engine wiring

`counted_batch(..., high_precision: bool)` selects the cached shader and the
upload branch. `analysis.py:1060`'s guard becomes
`config.use_gpu and gpu_raster.available(high_precision=config.high_precision)`
with the existing `margin_texels` fallback untouched. `operators/analyze.py`
passes `high_precision=settings.high_precision_gpu` next to the `use_gpu` it
already passes.

## Test strategy

RED before GREEN on each, smallest relevant regression first.

1. **Unit** — the fp32 self-test fixture is exactly representable: every
   coordinate survives a float32 round trip, and every slope quotient is exact.
2. **Headless** — `AnalysisConfig.payload()` precision matrix: default ≠ CPU,
   CPU == high precision, and the field's four input combinations. Headless
   rather than unit only because `adapters/analysis.py` imports `bpy` at module
   scope; `adapters/gpu_raster.py` does not, which is why test 1 can be a unit
   test.
3. **Headless** — `available()` is true with `_has_fp64` monkeypatched to
   `False`, `reason()` is `OK`, and `available(high_precision=True)` is false
   with `NO_FP64`.
4. **Headless** — the fp32 kernel reproduces the CPU counts on the new fixture
   in all four address modes, with no tolerance. This is `_self_test` itself,
   run through the public probe.
5. **Headless** — the engine equality test runs twice, once per precision. The
   high-precision run must equal the CPU report exactly; the fp32 run must
   equal it on the generated scene, which is built from exactly representable
   coordinates.
6. **Headless** — the panel draws the high-precision row disabled with the new
   message when fp64 is absent, and both rows disabled when the GPU is.

Tests 3 through 6 sit inside the existing background opt-in, so CI keeps
running them on the CPU-only path and this machine runs them opted in.

## The measurement gate

The default does not flip until this is recorded in `docs/performance.md`,
same-session protocol, one Blender session per tier.

**Speed.** Realistic tier (150,544 faces), three configurations: CPU, GPU fp64,
GPU fp32. fp32 must be at least as fast as fp64. If it is not, the branch stops
and reports rather than flipping the default — the coverage argument alone can
still justify shipping fp32 as the *fallback* for machines without fp64, which
is a different and smaller change.

**Disagreement.** The same realistic tier analysed under both precisions, with
the fp64 report as oracle, reporting three numbers: faces whose classification
differs, of which how many gained alpha, and how many lost it. Acceptance:

- Any face that *loses* alpha classification blocks the flip until it is
  understood. That is the unsafe direction and the goal forbids it.
- Faces that gain alpha are reported as a rate and accepted.

Both runs are recorded with `run_benchmarks.py`, which already stamps `device`
into its JSON; it gains `precision` the same way, for the same reason — so a
number cannot later be read as having come from the other kernel.

## Validation

Full production-branch matrix: the unit suite, both headless runs (default for
the fallback, opted in for the kernel), and source validation. Packaging is
untouched, so no ZIP rebuild is required unless the addon source changes —
which it does, so the clean build and installed-ZIP check run too.

## Preservation checks

- CPU results are byte-identical to `main` on the unit and headless suites.
- The fp64 kernel is byte-identical to `main` after the template rewrite,
  proven by the unchanged adversarial self-test fixture.
- No topology, UV, material, or selection behaviour changes anywhere.
- `ANALYSIS_SETTING_NAMES`, `API_VERSION`, and the panel's settings block are
  unchanged; the only public surface added is one scene property.

## Risks

1. **The disagreement measurement comes back worse than expected.** Most
   likely single point of failure. Mitigated by making the flip conditional on
   it rather than assuming the answer, and by the high-precision mode being
   built first, so a bad result still leaves a shippable branch.
2. **Two kernels, twice the driver surface.** A driver can miscompile one and
   not the other. Both have their own self-test on their own fixture, and both
   refuse the GPU on failure.
3. **The fp32 fixture is too easy.** Exactly representable by construction
   means it cannot catch a driver that rounds badly, only one that computes
   wrongly. Accepted: the adversarial fixture still exists and still runs on
   fp64, and the disagreement measurement is what covers real inputs.
4. **The error bound in this document is engineering, not proof.** `8 ulp` is
   an argued bound over a division and a short multiply-add chain, not a
   verified one. Nothing in the implementation depends on the number — it is
   not a tolerance anywhere in the code — so a wrong estimate misleads a reader
   of the doc rather than a caller of the kernel.
5. **README copy is currently wrong for this branch.** It tells the reader that
   missing fp64 disables acceleration. Rewriting it is part of the last commit,
   not an afterthought.

## Implementation plan

Approved wording for the `AGENTS.md` amendment is in hand; the remaining
approval items are listed at the end of this document.

Preconditions: on `feat/gpu-fp32-support`, based on `origin/main` `343a575`,
clean tree. Run the unit suite and both headless suites before the first
production edit, so every later failure is attributable to this branch.

Each commit is RED, then GREEN, then its own check, and is committed before the
next begins. Run the smallest listed check during the loop and the commit's
full check before committing. GPU work needs the opted-in headless run:

```powershell
$env:ALPHA_MATERIAL_SEPARATOR_GPU_IN_BACKGROUND = '1'
& $Blender52 --factory-startup --background --python-exit-code 1 --python tests/blender/run_all.py
Remove-Item env:ALPHA_MATERIAL_SEPARATOR_GPU_IN_BACKGROUND
```

Record material deviations in this section as they happen. A finding that
changes behaviour, scope, risk, or architecture stops for renewed approval.

### Deviations

- **The fp32 upload is simpler than designed.** No `uintBitsToFloat`, no bit
  reinterpretation: the triangle texture is already `R32F` and `_texture`
  already narrows to float32, so a single-precision coordinate rides through
  the existing channel verbatim and `coord()` is one `imageLoad`. The
  three-word chunking exists only because a double does not fit that channel.
- **The precision argument is required, not defaulted, on the batch entry
  points.** `submit_batch` and `counted_batch` take `high_precision` with no
  default, and the engine passes `True` until commit 4. Otherwise commit 2
  would have moved every existing caller onto the new kernel silently, and the
  exactness suite — coordinates near `1e7` — would have started failing for a
  reason that has nothing to do with a defect. The default flip is now one
  line in the commit that introduces the setting.
- **`_assert_matches_cpu` defaults to high precision.** That helper carries the
  bit-equality contract, which belongs to the double-precision kernel; the
  single-precision kernel is held to it only on the fixture built for it.

### Commit 1 — template the kernel on its scalar type

Inert by construction, so no RED: the existing fp64 self-test is the check, and
it demands bit-equality with the CPU oracle. If it still passes, the rewrite
changed nothing.

GREEN, `addon/adapters/gpu_raster.py` only:

- Prepend `#define scalar %(scalar)s` to `_SOURCE` and replace every `double`
  in the body with `scalar`. `chunked()` keeps its `double` return for now.
- Replace every `0.0lf` / `1.0lf` literal with `scalar(0.0)` / `scalar(1.0)`.
  An explicit constructor is legal at both widths; the `lf` suffix is not.
- `_build()` takes the scalar name and passes it into the format dictionary
  beside `bits` and `cap`. Its one caller passes `"double"`.

Check: the opted-in headless run. `assert_probe_is_total` and the four-mode
self-test inside `available()` both have to stay green.

### Commit 2 — the fp32 kernel, its fixture, and the probe split

RED first, in this order:

1. `tests/unit/test_rasterization.py` gains `class Fp32SelfTestFixture`, which
   imports `gpu_raster._FP32_FIXTURE` and asserts the two properties that make
   equality-without-tolerance possible: every coordinate survives a float32
   round trip, and every triangle's three vertical extents are powers of two so
   each slope division is exact. Fails with `AttributeError`.
2. `tests/blender/test_gpu_raster.py` gains
   `assert_fp32_is_the_default_probe()`: with `_has_fp64` patched to `False`
   and the shader cache cleared, `available()` is `True` and `reason()` is
   `OK`, while `available(high_precision=True)` is `False` with a `NO_FP64`
   reason. Fails with `TypeError` on the keyword.
3. `tests/blender/test_gpu_raster.py` gains
   `assert_the_fp32_kernel_matches_the_cpu()`, running the new fixture through
   `counted_batch(..., high_precision=False)` in all four address modes against
   `_assert_matches_cpu`, with no tolerance.
4. `assert_the_probe_measures_fp64()` keeps its `_has_fp64` unit assertions; its
   closing block, which asserts `available()` is `False` without fp64, moves
   into the new test and becomes `available(high_precision=True)`.

GREEN, `addon/adapters/gpu_raster.py`:

- `_FP32_FIXTURE`: the triangles, counts, and grid below, beside the existing
  adversarial fixture. `_self_test(shader, precision)` picks by precision.
- `%(coord)s` in the template, substituted with either the existing three-word
  `packDouble2x32` reassembly or
  a one-line fp32 reader that returns
  `uintBitsToFloat(uint(imageLoad(tris, at(slot)).r))`.
- The upload branches the same way: fp32 packs
  `triangles.astype(numpy.float32).view(numpy.uint32)` into the same R32UI
  texture, one word per coordinate instead of three.
- `_shaders` and `_reasons` become dictionaries keyed `"FP32"` / `"FP64"`,
  replacing the `_shader` / `_reason` globals. `available(*, high_precision=
  False)` and `reason(*, high_precision=False)` read them; a private `_probe`
  holds what `available()` does today, consulting `_has_fp64()` only for FP64.
  The three existing tests that save and restore `_shader` / `_reason` snapshot
  the dictionaries instead, which is shorter than what they do now.
- `_submit` and `counted_batch` take the precision through to the packing.

Check: unit suite, then the opted-in headless run.

### Commit 3 — the setting and the panel

RED, `tests/blender/test_expert_analysis_settings.py`:

1. `_assert_public_setting_names_are_guarded` gains
   `assert HIGH_PRECISION not in ANALYSIS_SETTING_NAMES`.
2. New `_assert_high_precision_follows_the_hardware()`, mirroring the existing
   GPU-toggle test: the property reads `False` after being set `True` when
   `_has_fp64` is patched off, and toggles normally when it is not.
3. `_assert_an_unusable_gpu_says_why` drops its `NO_FP64` case — that reason can
   no longer reach `_gpu_unavailable_message` — and a new case asserts the fp64
   copy is drawn while the acceleration copy is not.

GREEN:

- `addon/properties.py`: `_fp64_unavailable()`, `_high_precision_get/_set`
  mirroring the existing pair, and the `high_precision_gpu` BoolProperty with
  no `update=`.
- `addon/panel.py`: `_fp64_unavailable_message()`, the second row under the
  existing one, and its enablement — off when the GPU is unusable, off when
  "Disable GPU acceleration" is checked, off when fp64 is missing.

Watch for: the existing panel tests stub `gpu_raster.available = lambda: False`.
The panel now calls `available(high_precision=True)` during draw, so those stubs
become `lambda **_: False` and the `reason` stubs `lambda **_: "..."`. This is
the change most likely to produce a confusing `TypeError`.

Check: both headless runs.

### Commit 4 — precision as an analysis input

RED, `tests/blender/test_gpu_raster.py`:

1. `assert_the_setting_can_refuse_the_gpu` inverts its payload assertion:
   default `!=` `use_gpu=False`, and `use_gpu=False` `==` `high_precision=True`.
   Its docstring changes with it; the current one states the premise fp32
   invalidates.
2. The same test gains the four-way precision matrix from test strategy item 2.
3. `assert_the_engine_agrees_with_itself` runs twice, once per precision. The
   high-precision run must equal the CPU report exactly.
4. `tests/blender/test_expert_analysis_settings.py`'s
   `_assert_the_gpu_toggle_keeps_a_report` becomes the new contract: a default
   fp32 report goes `STALE` when the reader disables the GPU, and a CPU report
   stays `CLEAN` when the reader switches high precision on. The reset still
   leaves both toggles alone.

GREEN: `AnalysisConfig.high_precision` and the derived `"precision"` field in
`payload()`; the engine guard at `addon/adapters/analysis.py:1060` passing
`high_precision` to `available()` and `counted_batch`; and
`addon/operators/analyze.py:135` reading the new setting beside `use_gpu`.

Check: unit suite, both headless runs.

### Commit 5 — the measurement

`tests/blender/run_benchmarks.py` gains a `--precision` argument and stamps the
resolved precision into its JSON next to `device`. Then the same-session
protocol from `docs/performance.md`, realistic tier, three configurations, plus
the disagreement count: the same scene analysed at both precisions in one
session, counting faces whose classification differs and splitting them by
direction. Results and the acceptance decision go into `docs/performance.md`.

No RED. This commit measures; it changes no analysis behaviour. The contract
test that already imports `run_benchmarks` covers the argument plumbing.

### Commit 6 — documentation

`AGENTS.md` invariant amendment, README *Speed* (currently wrong: it tells the
reader a missing fp64 disables acceleration), `docs/gpu-rasterization.md`
cross-reference plus removal of its now-executed *Future work* section, this
document's status line, and `docs/HANDOFF.md`.

### The verified fp32 fixture

Exactness was confirmed before planning rather than assumed. The kernel's band
arithmetic was reproduced at both widths over every scanline of every triangle
below: all 82 rows produce bit-identical span endpoints in float32 and float64,
and every coordinate survives a float32 round trip. Against the same 53×17
patterned grid the existing fixture uses, the CPU oracle gives covered texels
`[297, 270, 0, 984, 168, 203]` and four distinct per-mode affected vectors, so
the fixture discriminates address modes rather than merely running.

```python
[[-72.5, -24.25], [-40.5, -24.25], [-40.5, -16.25]],
[[-72.5, -24.25], [-40.5, -16.25], [-72.5, -16.25]],
[[-20.0, 1.25], [9.75, 1.25], [9.75, 9.25]],
[[-20.0, 1.25], [9.75, 9.25], [-20.0, 9.25]],
[[2.0, 7.0], [2.0, 7.0], [20.0, 11.0]],
[[-34.0, -2.0], [100.5, -2.0], [100.5, 6.0]],
[[-34.0, -2.0], [100.5, 6.0], [30.0, 6.0]],
[[-34.0, -2.0], [30.0, 6.0], [-34.0, 2.0]],
[[6.0, 1.25], [38.5, 5.25], [8.0, 9.25]],
[[-10.25, 10.5], [-46.5, 14.5], [-6.0, 18.5]],
# counts: [2, 2, 1, 3, 1, 1]
```

It keeps every property the adversarial fixture has except large magnitudes:
non-power-of-two grid dimensions and negative rows and columns for the GLSL
negative-`%` defect, coordinates outside the image on both sides of both axes,
a degenerate triangle, a three-triangle polygon, and two triangles whose middle
vertex is the extremum strictly inside a band.

## Approval needed before implementation

1. The `AGENTS.md` invariant amendment quoted above.
2. Precision entering the input signature, which makes a completed report go
   STALE when the reader toggles either GPU checkbox.
3. The proposed panel copy for a GPU without fp64.
4. The measurement gate's acceptance criteria, in particular that any face
   losing alpha classification blocks the default flip.
