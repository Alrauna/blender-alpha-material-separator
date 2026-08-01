# AMS Sidebar Name Design

**Status:** Proposed for user review
**Date:** 2026-08-01

## Goal

Shorten the Blender 3D View sidebar tab from **Alpha Material** to **AMS**.

## Approved scope

- Set the main panel and its Expert child panels to the native Blender sidebar
  category `AMS`.
- Update README text that identifies the sidebar tab as **Alpha Material** so
  it instead directs users to **AMS**.
- Leave the public product name **Blender Alpha Material Separator**, the panel
  heading **Alpha Material Separator**, operator labels, extension ID, package
  name, and API unchanged.
- Do not rewrite historical implementation plans that record the old UI name.

## Test-first verification

1. Change the existing README contract to require the `AMS` sidebar location
   and demonstrate that it fails against the current README.
2. Add a headless Blender assertion that the registered main and Expert panel
   category is `AMS` and demonstrate that it fails against the current panels.
3. Change only the two shared panel-category declarations and current README
   references.
4. Run the focused RED/GREEN tests, complete unit suite, complete headless
   Blender suite, source validation, and `git diff --check`.

## Non-goals

- No change to extension identity or operator namespaces.
- No broad abbreviation of **Alpha Material Separator**.
- No panel layout, workflow, behavior, or screenshot change.
