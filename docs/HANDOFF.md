# Repository handoff

Updated: 2026-08-12

## Current branch objective

`feat/gpu-acceleration` is based on `origin/main` commit `6973a44`. It
implements `PLAN.md`, the staged analysis performance plan. The plan's thesis is
that GPU acceleration is a candidate gated on measurement, not a specification:
the CPU implementation stays authoritative, every later target is chosen from a
fresh profile, and a successful outcome does not require shipping GPU code.

Stages 1 through 5 are complete. Stage 6A and 6B are complete, 6B twice: once
against the grid fixture and then again against a realistic tier that ranks the
candidates differently. The shared prerequisite both remaining paths needed --
flat-array coverage -- has landed, so the gate is open with a stable baseline.
No GPU prototype has been built and none is authorized.

## Decisions

- Implemented on this one branch with a coherent commit per stage, rather than
  the five separate `codex/*` branches `PLAN.md` names. Those would each need
  their own authorized pull request, and stacking production pull requests is
  not permitted. **This deviates from the plan's branch layout and has not been
  confirmed by the user.**
- Stage 5's premise dissolved before it began. High-tier coverage reuse has
  measured faster than cold in every run on this machine since vectorization
  started, so the planned coverage-cache defect investigation has no defect to
  debug. Recorded in `docs/performance.md` as resolved by measurement rather
  than opened as a debugging task.
- Bit-equality with the replaced rasterizer was rejected as a correctness gate
  because that code is not stable under vertex permutation. The gate is the
  order-independent positive-area oracle from `docs/algorithm.md`.
- `addon/core` now depends on numpy, so `tests/unit` runs on Blender's bundled
  interpreter. CI already did this; `docs/testing.md` now matches. The core
  remains free of `bpy`.
- Row prefixes keep a `uint32` accumulator instead of the plan's int64 default.
  The bound is proven and the justification is recorded in
  `docs/performance.md`.

- Stage 6 stopped at the ranking rather than prototyping a dataflow, because the
  surviving GPU candidate and the CPU alternative share a prerequisite that
  moves the baseline. Recorded in `docs/performance.md`.
- Two claims in the first version of that ranking were wrong and are corrected
  in place: Blender's shader interface *does* expose exact `double` and
  `int64_t`, and the bandwidth-bound reduction measurements do *not* price the
  fused rasterize-and-classify candidate, which has a different dataflow.
- The grid fixture misranks accelerators, so a `realistic` tier was added rather
  than continuing to rank from it. Its shape was learned from an authorized
  private asset and then reproduced from generated data, so the evidence is
  committable; no private number entered the repository. Ranking uses this tier,
  not High complexity.
- Classification was rejected at 14.3 percent on the grid and is 25.8 percent on
  the realistic tier, which clears the keep threshold. **The Stage 6B ranking
  changed as a result and the earlier grid-based ranking is superseded.**
- Flat-array coverage was approved and implemented after a scratchpad prototype
  measured batched counting at 9.5x on the realistic tier's real run
  distribution, exact against the shipped counter. Scope was deliberately cut to
  counting plus the representation; batched rasterization is a separate,
  unapproved decision.
- `Coverage` uses one `(3, n)` int64 array rather than three arrays or a dict.
  Chosen on measurement, not taste: it is cheaper to build than the dict it
  replaces, which is why rasterization improved as well.
- `Coverage` sets `eq=False`. A generated `__eq__` would compare span arrays
  with `==` and return an array rather than a bool.
- The unattributed remainder was engine construction, which ran before
  `metrics` existed and so sat outside every phase accumulator. Two timers now
  cover it and unattributed fell 30.7 percent to 11.6 percent. What remains is
  diffuse interpreter overhead in the stepping loop, not a phase.
- `_structural_signature` is 15.4 percent of the realistic tier and was left
  alone deliberately. Vectorizing it changes the digest value, which is a
  stale-detection fingerprint, so it needs its own approval.
- Stage 3's own name — vectorize the rasterizer — is still unfulfilled. numpy
  inside the per-polygon call was measured 2.7x slower and stays rejected.
  Batching every triangle measured 1.4x, but that measurement was dominated by a
  1.282 s scatter into per-polygon dicts which no longer exists, **so batching
  the rasterizer needs re-measuring before it can be judged again.**

## Commits

- `af5de91` — vectorized image extraction and per-phase instrumentation
  (Stages 1 and 2);
- `f01a016` — cross-section scanline rasterization (Stage 3);
- `8b1b812` — `numpy.cumsum` row prefixes (Stage 4);
- `f749202` — Stage 6A spike and Stage 6B ranking;
- `3a8b636` — corrected numpy rasterizer projection;
- `34629bf` — corrected the exactness blocker and the fixture's representativeness;
- `405c9f3` — Stage 6 handoff correction;
- `d7e7ae3` — realistic benchmark tier and the re-ranked Stage 6 gate;
- `7b25abd` — flat-array coverage and batched alpha counting;
- `e1f2cbc` — the flat-array coverage result.

## GPU findings worth not rediscovering

Full detail is in `docs/performance.md`; the three that would cost a future
agent the most time:

- `GPUTexture` has no write method and its constructor accepts only a `FLOAT`
  buffer, so `R32F` is the only exact CPU-to-GPU channel and it is exact only
  below 2^24. `R32UI` output readback is exact.
- `gpu.texture.from_image()` returns `SRGB8_A8` for byte images and `RGBA16F`
  for float images, so it cannot carry float image data losslessly.
- `gpu.compute.dispatch()` leaves the shader bound, and releasing the shader
  while it is bound hard-crashes Blender on the next bind. `gpu.shader.unbind()`
  is mandatory, not hygiene.
- `double`, `int64_t` and `uint64_t` compile and compute exactly through
  `GPUShaderCreateInfo` on OpenGL/NVIDIA. Metal has no fp64, so `double` cannot
  reach the *Backend-portable* claim level even though it works here.

## Verification evidence

Fresh local results on this branch:

- unit suite on Blender's bundled Python 3.13.13: 135 passed;
- headless Blender suite: exit 0, all 18 modules OK, including the new
  `ALPHA_MATERIAL_SEPARATOR_IMAGE_DATA_OK`;
- `git diff --check`: clean before each commit;
- same-session before/after benchmarks per stage, each with wall time and peak
  working set, recorded in `docs/performance.md`.

High-tier cold analysis across the three landed changes, each percentage
same-session:

| Stage | Before | After | Change |
| --- | ---: | ---: | ---: |
| Image extraction | 80.239 s | 23.101 s | -71.2% |
| Rasterization | 22.825 s | 14.612 s | -36.0% |
| Row prefixes | 14.049 s | 11.342 s | -19.3% |
| Flat-array coverage | 10.983 s | 6.963 s | -36.6% |

The realistic tier, which is the one that ranks candidates, went 11.604 s to
6.444 s on that last change, a 44.5 percent improvement.

Peak working set never regressed; it fell slightly at Stages 1 and 4, was flat
at Stage 3, and fell 2949.8 MiB to 2080.4 MiB with flat-array coverage. Coverage totals, run counts, and scanline counts are identical
before and after every stage on the benchmark fixtures.

## Limitations

- **Coverage is slightly tighter than before on some exactly-representable
  triangles.** The replaced rasterizer emitted cells whose intersection with the
  triangle has zero area, contradicting its own documented positive-area rule;
  18 of 4,000 quarter-grid triangles were affected. The new code matches the
  oracle exactly there. The dropped cells have no positive-area overlap, so the
  only possible effect is fewer spurious alpha classifications, and the new path
  never under-covers the oracle across 14,000 randomized triangles. This is a
  real behavior change that has not been confirmed by the user.
- Stage 4 improved the high tier 19.3 percent, marginally below the repository's
  20 percent keep threshold. Recorded rather than rounded; the reasoning for
  keeping it is in `docs/performance.md`.
- Private characterization was authorized and run. Its script and output stay in
  the session scratchpad and were never committed, per the user's instruction
  that tests using local references remain local. Only the derived fixture shape
  entered the repository.
- No packaging, installed-ZIP, export, Unity, or human interaction gate has been
  run, none of which this branch's changes have yet required.
- Rasterization is the dominant cost at 37.2 percent of the realistic tier,
  followed by the structural signature at 15.4 percent, UV traversal at 15.1
  percent, and classification at 8.5 percent. Unattributed time is 11.6 percent
  and is diffuse stepping-loop overhead rather than a single target.
- The 47 percent attributed to the flat-array change did not transfer from
  high-tier scale. The measured result is 44.5 percent on the realistic tier and
  36.6 percent on the high tier.

## Next action

Decide whether to vectorize `_structural_signature`. It is 15.4 percent of the
realistic tier, second only to rasterization, and it hashes one `struct.pack`
plus two `blake2b.update` calls per vertex, edge, loop, polygon and UV.
Replacing that with `foreach_get` into arrays and one update per attribute is
straightforward, but it changes the digest value. The digest is a
stale-detection fingerprint, so whether it is ever compared across sessions has
to be established first. This needs explicit approval; it is not folded into the
instrumentation change.

Three items are open and none is authorized:

- batched rasterization, the second half of the original flat-array design. The
  1.282 s scatter that capped drop-in batching at 1.4x no longer exists, so the
  measurement that rejected it needs redoing before the option is judged;
- a 6E prototype of the fused rasterize-and-classify GPU dataflow, now worth at
  most 43.2 percent of the realistic tier rather than 66.6 percent.

If both are declined, the branch is complete as a measurement result: the high
tier went from 80.239 s to 6.963 s and the realistic tier stands at 6.444 s.

Push and pull-request creation require separate authorization and have not been
requested.
