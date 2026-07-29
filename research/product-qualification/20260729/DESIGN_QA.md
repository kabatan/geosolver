# GeoTarget construction UI — design QA

## Reference and implementation captures

- Reference: GeoGebra Geometry, desktop, tool and object-property flows.
  - `/tmp/geotarget-geogebra-audit/01-geometry-start.png`
  - `/tmp/geotarget-geogebra-audit/02-all-tools.png`
  - `/tmp/geotarget-geogebra-audit/03-algebra-view.png`
  - `/tmp/geotarget-geogebra-audit/04-point-properties.png`
  - `/tmp/geotarget-geogebra-audit/05-mobile-properties.png`
- Implementation: GeoTarget at `http://127.0.0.1:8765/`, Firefox desktop window,
  2493×1408 coordinate viewport captured at 1800×1017.
  - `/tmp/geotarget-geogebra-audit/06-geotarget-tools.png`
- Side-by-side comparison:
  - `/tmp/geotarget-geogebra-audit/07-source-implementation-comparison.png`
- Formula-keyboard reference supplied by the owner (691×221):
  - `/home/kabatan/.local/state/codex-desktop/tmp/codex-clipboard-be6c221c-5080-4d7d-9dad-f89bf7f4c52e.png`
- Formula-keyboard implementation at a 1009×1286 CSS-pixel viewport, `123`
  selected and formula input focused (680×226 crop):
  - `/home/kabatan/work/solver/design-qa-math-keyboard.jpg`
- Formula-keyboard side-by-side comparison, reference left and implementation
  right:
  - `/home/kabatan/work/solver/design-qa-math-keyboard-comparison.png`

The comparison is scoped to the construction experience. GeoTarget keeps its
own branding, licensed Phosphor icons, V15 source model, and solver inspector;
GeoGebra artwork and branding are not copied.

## States verified

- Desktop basic Tools view and Algebra/Tools rail.
- Contextual Point tool: blank, existing point, line, segment, and circle.
- Free-point and one-parameter constrained-point dragging.
- Blank-canvas line, segment, circle, and polygon authoring with atomic undo.
- Full categorized tool palette and diagram-based guided argument selection.
- Fixed/free/derived visual states and Algebra object actions.
- Basic, Style, and Advanced object settings; project-local color, size, line,
  label, and caption metadata.
- Keyboard crosshair placement, object-tree selection, draft cancellation,
  modal focus handling, and tab patterns.
- Formula, unified-condition, guided-construction, and property-definition
  fields open the same on-screen math keyboard and retain their active caret.
- `123`, catalog-derived `f(x)`, `ABC`, and symbol tabs; insertion, deletion,
  caret movement, confirmation, and close behavior.

## QA history

1. Initial review found pointer-only coordinate creation, stale drafts across
   Undo, incomplete line-like argument handling, an unrestricted Length tool,
   missing style controls, and undersized typography.
2. Those findings were resolved with a shared keyboard/pointer construction
   path, draft-first Undo, canonical inline-Line preview support, typed guided
   slots, GeoGebra-style property tabs, project style metadata, and a readable
   type floor.
3. Automated checks cover free and constrained dragging, keyboard placement,
   polygon closure, nested carrier actions, visibility controls, and atomic
   history behavior.
4. The current refinement reduces default points from 5 to 3.5 SVG units,
   reduces line/selection weight, removes the all-carriers glow from Point
   mode, and tightens label treatment. It also adds a 14 CSS-pixel
   line/segment/ray intersection affordance and frame-scheduled, unsnapped
   dragging. The interaction behavior is covered by 40/40 frontend tests.
5. The owner then supplied a compact tabbed math-keyboard reference. The
   implementation matches its pale panel, violet active tab, four-row key
   rhythm, central numeric split, rounded white keys, gray action keys, and
   top-right overflow/close control. Product-specific additions preserve the
   V15 function catalog and accessible labels without changing the reference's
   visual hierarchy.
6. Real-browser testing entered `x<6`, confirmed it as the normalized condition
   `x < 6`, restored the project with Undo, and inserted `Point()` from `f(x)`
   with the caret placed inside the call. Reloading restored an empty formula
   input and the original one-condition project.
7. Independent gates found modal focus ownership, stale targets, incomplete
   function reachability, inconsistent `π` normalization, tab semantics, and
   placeholder-glyph issues. The keyboard now renders as a real child of the
   catalog dialog, destroys stale targets on lifecycle changes, exposes every
   non-legacy catalog function in a scrolling panel, canonicalizes `π` to
   `pi`, limits symbol keys to supported V15 syntax, implements roving tabs and
   Escape/focus restoration, and uses legible x-based template labels.
8. The repaired modal path was verified in the live browser: clicking the V15
   definition field opened a keyboard owned by the dialog, `π` inserted at the
   active caret, and Cancel removed both the dialog and keyboard without
   changing the project.
9. A second gate pass found focus-target Escape handling, disconnected-target
   actions, long function labels, responsive function columns, and the target
   formula connection. Escape is now captured while the keyboard is open,
   every action rejects detached fields, the function panel uses four desktop
   or three compact columns with ellipsis and full-name tooltips, and both
   target inputs open the same keyboard. Live-browser inspection confirmed a
   156.75-pixel long-function key with ellipsis/title and Escape returning focus
   to the target field while closing only the keyboard.
10. The final caret audit found the Solver-pane target displayed canonical
    `pi` while the keyboard advanced by the single visible `π` character. That
    field now renders display math (`π`) while retaining canonical V15 state
    (`pi`); the `π` then `÷` regression produces visible `π/` and stored `pi/`.
    Its physical-keyboard/IME change path now uses the same canonicalizer; a
    direct visible `π/2` edit is stored as V15 `pi/2` as well.

## Result

The current math-keyboard build was captured from the live local UI and
compared side-by-side with the owner-supplied visual. Its component anatomy,
density, spacing, control grouping, color hierarchy, and interaction state are
faithful at the intended compact desktop size. No P0–P2 visual or interaction
finding remains in this scope.

Current automated verification: frontend typecheck passed, all 76 frontend
tests passed, the production build completed, and real-browser input/Undo/
function-insertion checks passed while preserving the existing project.

final result: passed
