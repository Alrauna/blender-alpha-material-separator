# Width-Aware UI Wrapping Design

## Objective

Keep short Blender UI sentences on one visual line when space permits while
wrapping longer text at word boundaries on narrow displays. Replace the current
fixed 34- and 52-character limits without changing workflow behavior or copy.

## Behavior

- Panel messages use the current sidebar region width.
- The Apply confirmation dialog selects a requested width between 420 and 560
  pixels from its longest sentence, capped to the usable window width.
- The dialog draws using the same effective width selected when it opens.
- Each source sentence remains intact when it fits.
- Text that does not fit wraps only between words. Long words are not split.
- Icons appear only on the first visual line, matching current behavior.
- Empty text still produces one empty label.

The change applies to the shared panel-label path so status messages, remedies,
completion copy, Material Details, and future callers behave consistently. It
also applies to the Apply confirmation dialog. It does not alter the generated
sentences, assignment plan, confirmation rules, or public API.

## Implementation Shape

Add one small pure presentation helper that accepts text and available width
and returns visual lines. Blender-facing code supplies the available width:

- the panel derives it from `context.region.width`, minus a conservative
  allowance for panel padding and icons;
- the confirmation operator derives its requested width from the longest
  confirmation sentence, clamps it to 420–560 pixels and the current window,
  and retains that width for `draw()`.

Because Blender labels do not provide native wrapping or dependable glyph
measurement, the helper uses one documented conservative average character
width. Minimum line capacity prevents unusable output in extremely narrow
regions. This remains an approximation, but it responds to actual UI width and
avoids the current unrelated fixed limits.

## Testing

Test first with generated text only:

- narrow, ordinary, and wide widths produce monotonically fewer visual lines;
- sentences that fit remain one line;
- narrow text wraps at word boundaries without splitting long words;
- empty text and first-line icon behavior remain unchanged;
- dialog width clamps at 420 and 560 pixels and respects a smaller usable
  window;
- the width used by dialog drawing equals the width chosen during invocation;
- existing confirmation text and panel presentation contracts remain intact.

Then run the ordinary unit suite, headless Blender suite, source extension
validation, and `git diff --check`. Rebuild and validate the ignored ZIP because
the change affects installed UI behavior. Private before/after `.blend` smoke
testing is unnecessary because the change does not alter assignment-plan data.

## Non-Goals

- Pixel-perfect font measurement.
- Copy rewriting or alternate short/long sentence variants.
- Changes to analysis, preview, assignment, classifications, or material data.
- New settings, dependencies, or public API fields.
