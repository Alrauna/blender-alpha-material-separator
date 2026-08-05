# Significance Settings Usability Design

**Status:** Proposed for user review
**Date:** 2026-08-05
**Target version:** 1.1.0

## Goal

Make **Minimum Affected Pixels** and **Minimum Affected Fraction** usable across
their whole range. A face whose alpha evidence falls below either gate must stay
on its source material instead of cancelling the entire material group.

## Current behavior and cause

Analysis, classification, and settings plumbing are all correct. The defect is a
policy interaction between two correct components.

`classify_coverage` marks a face `SUPPRESSED` when it falls below either gate
(`addon/core/classify.py:92-109`). The gate comparison is `affected < minimum`,
so a face passes when its affected count equals the minimum.

`build_assignment_plan` then blocks an entire material group when that group
contains any `SUPPRESSED` face and `suppressed_policy` is
`CANCEL_SOURCE_MATERIAL` (`addon/adapters/assignment.py:284-290`).
`CANCEL_SOURCE_MATERIAL` is the shipped default in `addon/properties.py:207`,
`addon/operators/assign_materials.py:144`, and
`addon/operators/select_faces.py:73`.

A face that passes the gate is therefore discarded because a sibling face in the
same material did not.

### Reproduction

One material, two faces. Face A covers four affected texels. Face B covers one.

| `min_affected_texels` | `suppressed_policy` | Faces to move | Blocked | Apply |
| --- | --- | --- | --- | --- |
| 1 | `CANCEL_SOURCE_MATERIAL` | 2 | none | enabled |
| 2 | `CANCEL_SOURCE_MATERIAL` | 0 | `SUPPRESSED_FACES` | disabled |
| 2 | `KEEP_SOURCE` | 1 | none | enabled |
| 2 | `TO_ALPHA` | 2 | none | enabled |

Face A passes the gate by a factor of two and still fails to move in the second
row.

### Why the settings appear to have no usable range

`classify_coverage` returns `OPAQUE` before the gates whenever `affected` is
zero, so `affected` is always at least one when a gate runs. Values `0` and `1`
therefore can never suppress anything, and `2` is the first effective value.
`min_affected_fraction` behaves the same way: `0.0` disables the gate and any
larger value can suppress. Under the shipped default, both settings move
directly from no effect to cancelling a material group.

### Supporting inconsistency

`mixed_policy` already defaults to `TO_ALPHA` (`addon/properties.py:198`).
`MIXED` faces carry more classification ambiguity than below-significance faces,
yet they do not cancel their group. Only `SUPPRESSED` does. Changing the
`suppressed_policy` default removes an existing inconsistency rather than
introducing an exception.

## Approved behavior

### Policy defaults

Change the `suppressed_policy` default from `CANCEL_SOURCE_MATERIAL` to
`KEEP_SOURCE` at all three sites: `addon/properties.py:207`,
`addon/operators/assign_materials.py:144`, and
`addon/operators/select_faces.py:73`.

A below-significance face stays on its source material. Its siblings are
assigned on their own evidence. No face moves without sufficient evidence, so
the conservative guarantee that matters is preserved: the change stops a
qualifying face from being discarded because of a neighbour's score.

Both the guided UI default and the scripted operator default change, so one rule
explains the behavior everywhere. This alters the implicit behavior of scripted
callers that never named a policy, which is why the release carries a minor
version bump.

### User-visible text

The enum item description `Conservative default` currently sits on
`CANCEL_SOURCE_MATERIAL` in all three enums. Move it to `KEEP_SOURCE` so the
description matches the code.

Revise the `SUPPRESSED_FACES` remedy sentence in `addon/presentation.py:60`.
That message now appears only when a user has deliberately selected
`CANCEL_SOURCE_MATERIAL`, so it must name the concrete action that restores the
group rather than instructing the reader to change an unnamed policy.

Reuse the existing retained-face reporting. `FACES_RETAINED_BY_POLICY`
(`addon/presentation.py:66`) and the `Faces kept by policy` label
(`addon/panel.py:160`) already exist. Verify that both report below-significance
faces under the new default. Add no operator, button, property, or panel.

### Explicitly unchanged

- `mixed_policy`, `unsupported_policy`, and `derived_conflict_policy` defaults.
- Classification arithmetic, gate comparisons, and gate boundaries.
- Rasterization and `margin_texels` behavior.
- Public payload shape, so `API_VERSION` stays `(1, 2)`.
- `CANCEL_SOURCE_MATERIAL` remains selectable and must keep blocking a group.

## Pixel Margin

`margin_texels` dilates unioned per-face coverage by N texels in every direction
after triangle coverage is combined (`addon/core/raster.py:135-146`). Each run
grows N texels wider and repeats across N rows above and below. Its purpose is
to include alpha texels just outside the exact UV footprint so that bilinear
filtering, mipmapping, and texture bleed at render time cannot introduce
transparency that exact coverage missed. The default `0` analyzes exact coverage
only.

This design does not change that behavior. It adds the missing tests and
documents two interactions:

- Dilation raises `covered_texels` with texels usually outside the real shape and
  usually opaque, which lowers `affected_fraction` and makes
  `min_affected_fraction` more likely to suppress.
- Dilation can reclassify an `ALPHA_AFFECTED` face as `MIXED` by adding opaque
  neighbours.

## Testing

Current coverage is one unit test (`tests/unit/test_alpha_classification.py:89`),
two headless assertions (`tests/blender/test_assignment_policies.py:272`), and
one rasterization test (`tests/unit/test_rasterization.py:102`). Nothing covers
the gate boundaries, the settings' effect on plan or UI state, the margin
interactions, or the blocked-group state.

Pure-Python tests:

- A face with `affected == minimum` classifies as its unsuppressed shape, and
  `affected == minimum - 1` classifies `SUPPRESSED` with the
  `MIN_AFFECTED_TEXELS` gate recorded.
- The same paired boundary for `min_affected_fraction` and its gate name.
- `min_affected_texels` of `0` and `1` never suppress any face.
- `margin_texels` raises `covered_texels`, lowers `affected_fraction` for a
  fixed affected count, and can reclassify `ALPHA_AFFECTED` as `MIXED`.
- The `SUPPRESSED_FACES` presentation entry names a concrete remedy, and the
  `Conservative default` description belongs to `KEEP_SOURCE`.

Headless Blender tests:

- Regression: two faces in one material, one above and one below the gate. Under
  the default policy the group is not blocked, the qualifying face moves, and
  the below-significance face stays on its source.
- The resolved default for `suppressed_policy` is `KEEP_SOURCE` in the settings
  group, the assignment operator, and the selection operator.
- An explicit `CANCEL_SOURCE_MATERIAL` still blocks the group and still reports
  `SUPPRESSED_FACES`, preserving the deliberate escape.

Preservation assertions follow the existing rules. Only reviewed derived-material
creation or reuse, namespaced metadata writes, material-slot additions or reuse,
and planned polygon material-index changes are permitted.

## Risk

Corrected during implementation. This section originally claimed that every
existing test named its policy explicitly and that the blast radius was
therefore small. Two tests did rely on the shipped default:

- `tests/blender/test_assignment_policies.py:297` called the assignment
  operator without naming a policy and asserted `CANCELLED`. It now names
  `CANCEL_SOURCE_MATERIAL` so it keeps covering the blocking path. The
  operator-level default outcome moved into the new regression, so no coverage
  was lost.
- `tests/blender/test_simplification_contracts.py:29` pins the public RNA
  defaults and failed by design. Its pinned value is now `KEEP_SOURCE`. The
  enum identifier order is unchanged.

Both continue to assert that no face is moved, so the change alters the
reported status rather than any mutation.

`addon/api_contract.py` carries `EXTENSION_VERSION` independently of the
manifest, so a release bump must change both. `test_api_contract.py`
cross-checks them.

Settings live on `WindowManager` (`addon/registration.py:51`) and are not saved
into blend files, so the new default applies on the next session with no
migration.

The scripted operator default changes on a publicly released 1.0.0. Bump the
manifest to `1.1.0` for this release.
