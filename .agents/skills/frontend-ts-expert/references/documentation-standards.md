# Documentation standards (frontend)

Documentation is a **first-class deliverable**. Stale docs are treated as defects.

## Inline: JSDoc / TSDoc

- Every **exported** function, component, type, and interface: document purpose, parameters, return value, and at least one **`@example`** when non-trivial.
- Non-exported symbols: add comments only for **non-obvious "why"**, not for "what" the code already states.
- Use `@deprecated` with migration guidance when sunsetting APIs.

## Component README

For non-trivial components (shared library, complex widgets), add or maintain **`README.md`** in the component folder:

- Purpose and when to use
- Usage examples (code snippets showing common variants)
- Props table (manual or generated) with types, defaults, and descriptions
- States / variants with visual context if helpful
- Known limitations
- Links to UX specs: `WF-NNN`, `FLOW-NNN` when applicable

## API surface

- If the project exposes a **component library** or shared package, keep **`API.md`** or **TypeDoc** (or equivalent) aligned with exports.
- Re-generate or review API docs when public types change.

## Changelog

- On **behavioral or API changes** to existing UI, update **`CHANGELOG.md`** (project root or package) using [Keep a Changelog](https://keepachangelog.com/) format.
- **Breaking changes** must be explicit: props removed, renamed, or semantically changed.
- Group entries under `Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`.

## Spec traceability

- In `CMP-NNN` / `PAGE-NNN` specs, maintain **Current implementation** (file paths).
- When moving or renaming files, **update specs in the same change** as the code.

## Same change rule

When modifying code, update in the **same task** all of: JSDoc, README (if any), changelog (if user-visible change), and spec paths. Do not defer.
