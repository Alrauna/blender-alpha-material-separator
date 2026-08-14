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
2. **Unit** — `AnalysisConfig.payload()` precision matrix: default ≠ CPU,
   CPU == high precision, and the field's four input combinations.
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

## Commit boundaries

1. Probe split: precision-keyed shaders and reasons, `available()` and
   `reason()` keyword, fp64 no longer gating fp32. Tests 3.
2. Templated source and the fp32 upload branch, with the new fixture and its
   self-test. Tests 1 and 4; the fp64 self-test proves the rewrite is inert.
3. Settings property, panel row, panel copy. Tests 6.
4. `precision` in `payload()`, `high_precision` through `AnalysisConfig` to the
   engine and the operator. Tests 2 and 5.
5. Measurement: benchmark precision stamping, the three-way timing, the
   disagreement count, `docs/performance.md`.
6. Documentation: the `AGENTS.md` invariant amendment, README *Speed*,
   `docs/gpu-rasterization.md` cross-reference and the removal of its *Future
   work* section, `docs/HANDOFF.md`.

## Approval needed before implementation

1. The `AGENTS.md` invariant amendment quoted above.
2. Precision entering the input signature, which makes a completed report go
   STALE when the reader toggles either GPU checkbox.
3. The proposed panel copy for a GPU without fp64.
4. The measurement gate's acceptance criteria, in particular that any face
   losing alpha classification blocks the default flip.
