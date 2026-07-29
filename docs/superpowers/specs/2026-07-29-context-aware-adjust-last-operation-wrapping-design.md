# Context-Aware Adjust Last Operation Wrapping Design

## Problem

Blender calls the assignment operator's `draw()` method in two different UI
hosts:

- the warning confirmation dialog requested by the extension; and
- Blender's native Adjust Last Operation HUD after assignment.

The confirmation dialog has an adaptive requested width between 420 and 560
pixels. The operator currently retains that width and uses it every time
`draw()` runs. When Blender later reuses `draw()` in the much narrower HUD,
the extension still emits confirmation-width labels. Blender then shortens
those labels with ellipses.

## Approved outcome

Keep the existing confirmation and completion sentences, but wrap them for the
UI host that is currently drawing them:

- In a `HUD` region, use the current region width.
- In every other context, continue using the retained adaptive confirmation
  width.
- If a HUD-like test or exceptional context has no usable region width, fall
  back conservatively rather than raising an error.

The native HUD may become taller when its width is narrow. Complete readable
sentences are preferred over ellipses.

## Minimal implementation

Change only the assignment operator's presentation path:

1. In `draw(context)`, inspect `context.region`.
2. When `context.region.type == "HUD"` and its width is positive, pass that
   width to the existing `ui_text_lines()` helper.
3. Otherwise pass the existing `_confirmation_draw_width`.
4. Use the chosen width for every confirmation sentence, including the final
   safety and undo sentence.

Do not add new user-facing copy, RNA properties, persistent state, dependencies,
or a second wrapping implementation. Do not attempt to resize Blender's native
HUD. Blender owns that region and users may resize it.

## Testing

Extend the existing generated Blender assignment-policy test:

- draw with a non-HUD context and prove the retained confirmation width still
  keeps the existing wide-dialog behavior;
- draw the same saved plan with a narrow `HUD` region and prove it emits more
  wrapped labels;
- prove joining the HUD label text reconstructs the original sentences;
- prove the separator before the final safety sentence remains;
- prove a missing or unusable region falls back without an exception.

Run the complete ordinary unit suite, headless Blender suite, source extension
validation, and `git diff --check`. This is presentation-only, so the private
before/after `.blend` smoke is not required.

Rebuild and validate the ignored extension ZIP because the user tests the
installed artifact. Manually confirm in Blender 5.2 that:

- the Apply confirmation remains adaptive and readable;
- after applying, the bottom-left Adjust Last Operation HUD contains no
  ellipsized extension sentences at its normal width;
- narrowing the HUD wraps at word boundaries; and
- expanding it reduces wrapping without changing the reported facts.

## Non-goals

- No analysis, preview, assignment-plan, material, cache, or API changes.
- No change to extension version `0.1.0` or API `1.2`.
- No custom HUD, popup replacement, font measurement, or Blender UI patch.
- No separate compact completion vocabulary.
