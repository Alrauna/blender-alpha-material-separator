# Analysis performance plan

Make Analyze materially faster without changing what it classifies. GPU
acceleration is a candidate optimization gated on measurement, not the
specification. The CPU implementation stays authoritative, and a successful
outcome does not require shipping GPU code — if the optimized CPU path makes
GPU acceleration uneconomical, that is a result worth documenting.

## Why this shape

`docs/performance.md` (2026-08-01, "Analyze responsiveness") is current
authority:

| Metric | Value |
| --- | ---: |
| High tier cold | 71.556 s |
| 8K full digest | 45.163 s |
| 4K full digest | 1.202 s |
| Peak working set | 2.92 GiB |

Image extraction is **47.6 s of 71.6 s**; the 8K image alone is 63%. An
accelerator that runs after extraction is capped at **1.50x** even if it makes
everything else free. The repository already hit this wall from the CPU side: a
four-worker multiprocessing prototype reached 2.14x isolated, projected 1.29x
whole-workflow, and was rejected under the 20% keep threshold.

So: fix the measured bottleneck, re-profile, and choose the next target from the
new profile — never from a historical one that a landed optimization may have
invalidated.

## Verified environment findings

Measured 2026-08-12 by direct probe of the installed Blender, not from
documentation. An earlier draft of this plan inferred from `gpu.types` and
`GPUShader` that compute dispatch was unavailable. That inference was wrong.

| Question | Measured answer |
| --- | --- |
| Blender | 5.2.0 LTS (`fbe6228777e7`) |
| numpy | 2.3.4, bundled |
| `pixels.foreach_get(numpy.float32)` | accepted |
| Compute dispatch | `gpu.compute.dispatch(shader, x, y, z)` exists and executes |
| Headless GPU | `gpu.init()` succeeds in `--background` |
| Backend / device | OPENGL, NVIDIA RTX 4080 |
| Exact integer readback | **`R32UI` returned exact values; `R32F` exact for small integers** |
| `R32I` readback | **broken** — `GPUTexture.read()` returns a `FLOAT` Buffer, so signed values decode as garbage |
| Storage buffers (SSBO) | absent; data moves via `GPUTexture` images and `GPUUniformBuf` |
| Image slots | `max_images_get() == 8` |
| Capability queries | `compute_shader_support_get` and `shader_image_load_store_support_get` are **deprecated** in 5.2 — "all platforms have support" |
| Memory barrier | no `gpu.state.memory_barrier`; `read()` synchronized correctly without one in this probe |
| Work-group limits | `max_work_group_count_get`/`_size_get` take an axis index argument |

So the existence question is answered: an exact, integer, CPU-visible GPU result
is achievable through Blender's own API with no third-party runtime. What is
**not** answered is whether it is fast enough to matter at 8K scale, and that is
the only question Stage 6 needs to ask.

Limits of this probe, stated plainly: one machine, one vendor, OpenGL backend,
a 4x4 texture and a trivial kernel. It proves capability, not throughput, not
portability, and not synchronization correctness under load. Because the
capability queries are deprecated as universally true, do not build capability
detection ceremony around them — detect failure, not support.

## Ground rules

- Preserve exact positive-area coverage and classification semantics. No
  approximation, sampling, relaxed epsilon, conservative mip result, or altered
  boundary behavior to make a faster implementation agree.
- Byte-identical `blake2b` digests are the correctness gate wherever the
  canonical pixel representation changes.
- Vectorization is not automatically exact. Control dtype, operation order,
  comparison, rounding, degenerates, and boundaries explicitly. If an optimized
  form cannot reproduce the oracle exactly, reject the optimization rather than
  weaken correctness. This binds numpy exactly as hard as it binds GPU code.
- RED/GREEN per stage, smallest relevant regression first.
- Same-session benchmarks only, wall time **and** peak working set every time,
  whole-workflow rather than isolated kernels.
- Re-profile after every landed optimization, before choosing the next.
- One `codex/` topic branch per reviewable change, from freshly fetched
  `origin/main`. No stacking production PRs on unmerged branches. Experimental
  GPU branches may be discarded rather than merged.
- Negative results go in `docs/performance.md`. They are results.

## Correctness architecture

A simple CPU reference defines semantics; the optimized numpy path and any GPU
path are both validated against it by differential test. The reference need not
remain the production execution path, and duplicate production implementations
are not retained for theoretical portability — but keep a small reference form
in tests wherever that is cheap and materially improves differential coverage.

## Preflight

Done — numpy 2.3.4 and `foreach_get` acceptance are confirmed above. The
extension bundles no numpy of its own.

---

## Stage 1 — Vectorize image extraction

Branch `codex/vectorize-image-read`.

**Problem.** `MAX_BULK_WORKING_BYTES` is 384 MiB. An 8K RGBA float32 source is
1.00 GiB for the raw buffer alone (`8192 x 8192 x 4 x 4`), and the working
estimate at `addon/adapters/image_data.py:62` is larger still because the
pipeline needs further arrays. So 8K always takes the lower-memory path, which
slices `image.pixels`, materializes a Python list per chunk, converts to
`array("f")`, extracts a channel, and then runs a per-value Python loop
(`image_data.py:144-148`). That is the 45.163 s. The bulk path carries the same
loop at `image_data.py:123-128`.

**Bulk fast path.** `foreach_get` into a contiguous `numpy.float32` RGBA buffer,
then vectorized channel extraction, `numpy.isfinite(...).all()` validation, and
`values < threshold` for the mask.

**Low-memory path.** `foreach_get` is all-or-nothing, not a chunked operation —
do not describe it as one. The fallback keeps bounded `image.pixels[a:b]`
acquisition and converts each bounded chunk into numpy for vectorized channel,
validity, and threshold work. The two paths need not share a data-acquisition
mechanism; they must produce identical canonical results.

**Memory.** Raise `MAX_BULK_WORKING_BYTES` so 8K attempts the fast path, keeping
the existing `except MemoryError -> use_bulk_read = False` handler at
`image_data.py:98-107`. Do not call this a guaranteed adaptive policy: an OS may
page, compress, overcommit, satisfy the allocation with severe latency, or fail
later somewhere else. Mark it with a `ponytail:` comment naming that ceiling.
Benchmark peak working set, total latency, and behavior under ordinary memory
pressure; if pathological paging appears, replace allocation-by-failure with an
explicit policy in a later reviewable change. Do not add `psutil` for this.

**Two things that would silently corrupt the digest.**

- `LUMINANCE` computes `0.2126r + 0.7152g + 0.0722b` in Python float64 and then
  rounds into `array("f")`. Explicitly promote operands to float64, preserve the
  canonical expression order, convert to float32 exactly once. Never rely on
  implicit numpy promotion, never compute it in float32.
- Channel views are non-contiguous. `numpy.ascontiguousarray` before
  `tobytes()` so hashed bytes reproduce the canonical sequence.

**Instrumentation.** Add per-phase timers distinguishing extraction, digest,
mask generation where separable, rasterization, prefix construction, counting,
cache-key construction, cache lookup, and cache construction, with negligible or
explicitly controllable overhead. The harness today times whole analysis,
digests, and prefix first/reuse only. Every later stage is chosen from this
split, so it is production instrumentation and belongs in this branch.

**RED.** `tests/blender/test_image_data.py` requiring identical digest bytes,
mask bytes, returned metadata, and error behavior across component counts
1/2/3/4, channels `ALPHA`/`RED`/`GREEN`/`BLUE`/`LUMINANCE`, finite/NaN/+inf/-inf
inputs, threshold boundary cases, and both read paths. Force path selection
explicitly via `rows_per_chunk` so no test outcome depends on host RAM. Commit
generated canonical golden values, and keep a small independent reference form
in the test rather than relying on goldens alone once the production loop is
gone.

**Acceptance.** Byte-identical digests and masks, unchanged errors, unit suite
green, headless suite green, measured whole-Analyze improvement, peak working
set recorded, read path recorded per tier. The expected large speedup is a
hypothesis, not an acceptance criterion.

**Memory decision rule.** The 8K fast path may raise peak by roughly 1 GiB on a
2.92 GiB baseline, past the repository's 25% limit. If it breaches, document the
exact increase, justify it from measured performance, and carry an explicitly
re-approved baseline in the same PR. Do not silently redefine the baseline.

## Stage 2 — Re-profile

Acceptance activity for Stage 1, same PR. Run `tests/blender/run_benchmarks.py`
before and after in one session. Record total Analyze time, the full per-phase
split, peak working set, selected read path, image dimensions, and tier. Update
`docs/performance.md`. Choose all later work from this profile.

---

## Stages 3-5 — CPU optimization

Ordered below by expected size. That order is a hypothesis, not a commitment;
Stage 2 decides, and each stage proceeds only if it is still material.

**Stage 3 — vectorize the rasterizer.** Branch `codex/vectorize-rasterizer`.
After extraction is fixed the residual is ~24 s. Prefix construction accounts
for roughly 3.7 s of it — 0.61 + 0.61 + 2.52 from the per-image table at
`docs/performance.md:62-67`, which belongs to the first baseline and was not
republished on 2026-08-01, so treat it as an estimate Stage 2 replaces with a
measurement. The bulk is `_clip_y` scanline clipping over 301,088 triangles and
4,469,760 runs in Python, allocating lists per row
(`addon/core/raster.py:31-70`). `docs/performance.md` records an
allocation-reduction attempt worth only 4.8% — a different change, not evidence
against vectorization.

Gate on the existing fixed-seed clipping oracle
(`tests/unit/test_rasterization.py:122`, oracle at `:57`) plus explicit
adversarial cases: vertices and edges exactly on texel boundaries, near-horizontal
and near-vertical edges, sub-texel and degenerate triangles, edge-only and
point-only contact, negative UVs, REPEAT and MIRROR boundaries, large accepted
coordinates, and coordinates near internal limits. Reject the change if the
complexity is not justified by measured whole-workflow improvement.

**Stage 4 — vectorize row prefixes.** Branch `codex/vectorize-alpha-prefixes`.
`numpy.cumsum` replaces the Python loop at `addon/core/alpha.py:14`. Choose the
accumulator dtype explicitly rather than inheriting numpy's default — the Python
reference uses arbitrary-precision integers, so the fixed-width replacement needs
a proven bound: maximum prefix value <= maximum supported pixels in one row or
query < chosen integer maximum. `int64` unless something justifies otherwise.

This touches the `bpy`-free core, which `tests/unit` runs outside Blender, so
numpy becomes a test requirement there too; accept that rather than building a
dual-path dispatcher. Prefix values must be exactly identical integers across
empty, single-pixel, all-unaffected, all-affected, alternating, random, and
maximum-width rows, including REPEAT and MIRROR inputs.

**Stage 5 — coverage-cache regression.** Branch `codex/coverage-cache-cost`.
Reuse has measured slower than cold at the high tier; the cache hashes every
triangle's float64 UVs and retains an entry per polygon
(`addon/adapters/analysis.py:1038-1053`). Treat a reuse path slower than cold as
a defect: begin with systematic debugging and instrument key construction, UV
serialization, BLAKE2b, lookup, hit and miss handling, entry construction,
retained volume, polygon iteration, and cache lifecycle separately. Do not
redesign until the source is measured. Either fix it with a regression test and
measured improvement, or demonstrate the structure is not worthwhile at that
scale and record the negative result.

---

## Stage 6 — GPU feasibility gate

No production GPU backend until Stage 6 passes. Stages 1-5 must be landed or
explicitly rejected from current measurements first, and every GPU comparison is
against the then-current optimized CPU implementation — never the original
baseline, and never the pre-numpy implementation.

**6A — Scale spike.** Branch `codex/gpu-capability-spike`, discardable. The
existence question is already answered above, so this spike is about scale, not
capability. Extend the exact-`R32UI` proof to realistic sizes: allocation and
upload of 4K/8K-scale data through image bindings within the 8-slot limit, a
reduction strategy that returns a compact result rather than a full buffer,
repeated dispatch, and synchronization that stays correct under load — the probe
above needed no barrier, but none is exposed, so verify rather than assume.
Measure shader creation, cold execution, warm execution, synchronization,
readback, and total CPU-visible latency. Use unsigned integer formats for any
value that must be exact; `R32I` readback is broken through `GPUTexture.read()`.
If no practical complete path to an exact CPU-visible result exists at scale,
document the limitation and stop — do not jump to an external runtime.

**6B — Rank candidates from measurement.** For each remaining cost record CPU
wall time, input and output volume, independent work items, dispatch count,
batching opportunity, synchronization requirements, data reuse, expected
arithmetic intensity, and exactness difficulty. Do not pick a workload because
it maps neatly to a shader, and do not assume prefix-based counting is worth
moving merely because it is integer work — an O(1) CPU prefix lookup is a very
low bar for GPU submission, transfer, and synchronization to clear.

**6C — Digest and dataflow.** The canonical BLAKE2b fingerprint may require CPU
traversal of all participating pixels whenever Blender cannot prove them
unchanged. That caps the achievable speedup; it does not by itself eliminate any
architecture.

| Architecture | Position |
| --- | --- |
| A — CPU canonical extraction, GPU downstream | Lowest risk. Digest unchanged, easiest correctness proof; cannot remove CPU extraction, and needs enough downstream GPU work to pay for the overhead. |
| B — reuse Blender's resident GPU texture | Viable only if measurement shows resident-resource reuse materially reduces other costs, and only after 6D proves compatible representation. |
| C — GPU-derived canonical fingerprint | Out of scope. Do not reimplement BLAKE2b on GPU or alter fingerprint semantics to make B attractive. If fingerprinting becomes the measured blocker, open a separate design review. |

**6D — Characterize the resident GPU image.** Only if a live candidate needs
`gpu.texture.from_image()`. Do not assume it matches `image.pixels`: check
width, height, channel representation per channel, straight vs premultiplied
alpha, byte vs float images, color-managed vs non-color data, 4K and 8K, and
Blender texture-size limits. If the representation differs in any way that
affects exact classification, the resident texture cannot be the canonical
source for that operation — which does not invalidate GPU acceleration on
CPU-prepared canonical resources.

**6E — Prototype complete dataflows.** Only candidates justified by 6B, and not
all of them. Time everything needed to obtain a usable CPU-visible answer: CPU
preparation, allocation, upload, dispatch, execution, reduction,
synchronization, readback, cleanup. Record cold and warm, CPU peak, and GPU
memory impact where measurable. Command submission is not completion; never
claim acceleration from asynchronous enqueue time.

**6F — Exactness gate.** Require `reference CPU == optimized numpy CPU == GPU`
on all committed deterministic cases and the fixed-seed differential suite, plus
new cases for whatever moved. Never weaken the oracle to accommodate the
implementation. Rasterization need not move to the GPU at all — if it is cheap
after Stage 3, leave it. If an exact GPU formulation is attempted, it must prove
agreement across the same adversarial list as Stage 3; an f32 rasterizer that
merely agrees on ordinary assets fails, and an integer or fixed-point
formulation is the route, not a relaxed oracle.

**6G — Runtime context and failure policy.** GPU work must never make ordinary
Analyze unavailable. Do not call Blender GPU APIs from arbitrary worker threads;
keep any CPU multiprocessing or threading separate from GPU context ownership;
create resources only where Blender permits; do not assume headless and
interactive contexts behave identically — `gpu.init()` is required for the
former; clean up deterministically. Design internally for AUTO/CPU/GPU
selection even with no public selector: AUTO attempts GPU only when the workload
is eligible, capability is present, and size exceeds the measured crossover,
and any failure disables the relevant GPU path for the session and falls back to
CPU. Never report GPU execution when CPU actually ran.

**6H — Crossover.** Measure initialization, shader creation, cold dispatch, warm
dispatch, upload, synchronization, and readback separately, then derive a simple
conservative heuristic from inputs such as image pixels, triangle count, run
count, batch size, or reusable GPU data. Do not fit a complex cost model to one
computer. If no robust crossover exists, CPU stays the default.

**6I — Claim levels.** Distinguish API portability from verified portability.
*Experimental*: exact on tested cases, faster on one realistic workload, one
device family — this is the level the probe above supports. *Backend-portable*:
uses Blender's abstraction, no vendor-specific path, CPU fallback retained;
describable as implemented against Blender's cross-platform GPU abstraction, but
claiming nothing about verified hardware coverage. *Verified*: exact and
successful on at least two materially different vendor/backend families —
usefully NVIDIA, AMD, Intel, and Apple Silicon/Metal. CI has no GPU and
`docs/testing.md:54-55` keeps self-hosted runners and installers out of it, so
this is local and contributor validation by decision. For every GPU validation
record Blender version, OS, GPU vendor and model, driver, backend, workload,
cold and warm timings, CPU comparison, correctness, and fallback result. Claim
only what was tested.

**6J — Keep or abort.** Keep only with exact oracle agreement, no relaxed
semantics, no unresolved representation mismatch, controlled CPU fallback,
**>=20% whole-workflow improvement** on at least one realistic supported
workload inclusive of preparation, transfer, execution, synchronization,
reduction and readback, and no unacceptable increase in CPU memory, GPU memory,
Analyze startup latency, persistent GPU resources, or Blender stability.

On failure: stop, remove experimental production code, keep the benchmark and
prototype results, and record the outcome in `docs/performance.md` specifically
enough that a future agent does not repeat it without new evidence.

## Stages 7-9 — Production, validation, control

**Stage 7** (`codex/gpu-analysis-backend`, only after 6J passes) implements only
the workload proven worthwhile, with the smallest abstraction two real
implementations require: CPU callable independently, GPU callable independently
for differential tests, AUTO selection separated from computation, GPU failure
translated into controlled CPU fallback, GPU lifecycle kept out of the pure core
where practical. Do not simultaneously redesign fingerprints or unrelated
rasterization, add a public selector, or design hypothetical backend subclasses.

**Stage 8** adds deterministic CPU/GPU differential coverage for everything
moved, keeps CI validating reference semantics, optimized CPU semantics, shader
source construction where practical, and non-GPU fallback logic, and provides a
documented local GPU validation runner reporting device and backend. Ordinary
contributors must not need vendor SDKs or package installers.

**Stage 9** — a user-facing backend selector is a public UX and API change
requiring its own design and approval under `AGENTS.md:53`. Do not add one
merely because two implementations exist.

## Deliberately not doing

- **Hierarchical opacity / mip pyramid.** `AlphaGrid.count_run`
  (`addon/core/alpha.py:110`) already answers coverage queries exactly in O(1)
  per run for any length, including REPEAT and MIRROR, and coverage is already
  reduced to merged intervals. Do not replace an exact answer with a
  conservative `maybe`.
- **A speculative backend framework.** No CUDA/WebGPU/Metal/Vulkan hierarchy
  before multiple real implementations exist.
- **Dual pure-Python/numpy production paths.** numpy is present; verified.
- **Approximate f32 rasterization**, GPU-derived fingerprints, vendor SDKs,
  native helper processes, and GPU mesh editing.

## Verification

```bash
python -m unittest discover -s tests/unit -t .
```

```bash
'/c/Program Files/Blender Foundation/Blender 5.2/blender.exe' --factory-startup --background --python-exit-code 1 --python tests/blender/run_all.py
```

Plus `tests/blender/run_benchmarks.py` same-session before/after,
`git diff --check`, new `docs/performance.md` rows per landed stage recording old
and new measurements, conditions, memory impact, and what was kept or rejected
and why, and a `docs/HANDOFF.md` update at each branch completion recording goal,
completed work, test and benchmark status, unresolved risks, and the next
measured bottleneck.

## Policy status

The third-party runtime dependency ban, the single-ZIP constraint, and the
committed-test determinism sentence are removed from `AGENTS.md` and
`docs/testing.md` — currently uncommitted on `feat/gpu-acceleration`. They stay
removed.

That removes policy as a blocker; it does not make an external GPU runtime a
good idea, and the probe above makes it markedly less likely to be needed — the
exact-integer compute path exists inside Blender itself, with no dependency, no
packaging change, and headless test support. Keep the removed rules as
engineering defaults anyway: avoid third-party native runtime dependencies,
prefer simple packaging, prefer a single distributable package.

If Blender-native GPU proves insufficient **and** a meaningful GPU-suitable
bottleneck still remains, an external runtime becomes an ordinary architecture
decision requiring its own plan and approval, justified by measurement and
covering runtime choice, supported operating systems and CPU architectures,
supported GPU vendors, licensing, binary provenance, build reproducibility,
package size, Python/Blender ABI compatibility, per-platform packaging including
macOS signing, driver requirements, offline installation, update strategy,
failure isolation, security surface, CPU fallback, and maintenance burden.
