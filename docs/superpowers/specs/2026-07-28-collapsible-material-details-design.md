# Collapsible Material Details

## Goal

Keep **2. Review** readable when an analysis contains many objects and
materials, without hiding whether a material needs user attention.

## Review layout

The face totals, classification totals, **Preview Faces to Move**, and preview
completion guidance remain directly visible in **2. Review**.

The existing deduplicated per-material cards move into one Blender-native
disclosure row:

> Material Details (N)

`N` is the number of unique material cards that will be shown. The row uses
Blender's standard right/down disclosure triangle. It is collapsed by default.
Expanding it shows the existing supported-material image, UV, channel, and
destination details, plus the existing unsupported-material explanation and
**Set Manual Alpha Source** action.

Object-level safety warnings are not material details and remain directly
visible outside the disclosure.

## Alpha-source advisory

When at least one unique material card is unsupported and offers
**Set Manual Alpha Source**, show one advisory box immediately above the
disclosure:

> N materials may need an alpha source.
>
> Open Material Details below to review them.

Use singular grammar for one material. The advisory is informational rather
than a new blocker and does not change analysis or assignment policy. Do not
show it when every material card has a supported source.

## State behavior

Store the disclosure state as transient UI state:

- every successfully published analysis collapses Material Details;
- expanding or collapsing it does not invalidate analysis or review;
- switching Simple/Expert modes preserves its current state;
- canceled or failed replacement analysis preserves the previous complete
  report and its disclosure state;
- clearing results does not require special handling because the next
  successful analysis collapses it.

No state is saved into the `.blend` file.

## Scope

Reuse the existing report payload and material-card deduplication identity.
Do not change classifications, resolver behavior, analysis signatures,
assignment plans, operator IDs, API payloads, or public version numbers.
Do not add a panel class, operator, dependency, search, filtering, pagination,
or per-material expansion state.

## Verification

Automated coverage must prove:

- repeated material groups still produce one detail card;
- the disclosure label reports the deduplicated card count;
- the advisory reports the deduplicated unsupported-material count with correct
  singular/plural copy;
- no advisory appears when every material is supported;
- successful analysis resets the disclosure to collapsed;
- canceled or failed replacement analysis preserves its previous state;
- expanding the disclosure does not alter analysis or review state;
- registration and unregistration clean up the transient property.

Manual ZIP verification must confirm the disclosure and advisory remain usable
with narrow and wide sidebars, long material names, and the private messy
before-example without committing any private output.
