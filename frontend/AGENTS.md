# Prototype Instructions

Run the local server yourself and open the preview in the browser available to this environment. Do not give the user server-start instructions when you can run it.

Before making substantial visual changes, use the Product Design plugin's `get-context` skill when the visual source is unclear or no longer matches the current goal. When the user gives durable prototype-specific design feedback, preferences, or decisions, record them in `AGENTS.md`.

When implementing from a selected generated mock, treat that image as the source of truth for layout, component anatomy, density, spacing, color, typography, visible content, and hierarchy.

Build app UI in `src/`. Keep `.openai/hosting.json`, `worker/index.js`, `scripts/prepare-sites-build.mjs`, and `tests/sites-worker.test.mjs` intact so the same local prototype can be handed to Sites. Before a Sites handoff, run `npm run build` and `npm run test:sites`; the build must leave `dist/client/index.html`, `dist/server/index.js`, and `dist/.openai/hosting.json`.

## GeoTarget visual authority

The current visual and interaction authority is GeoGebra Geometry's desktop
construction experience, selected by the owner on 2026-07-28. Reproduce its
interaction model and information architecture closely: Algebra/Tools rail,
compact basic-tool grid, categorized full palette, contextual Point tool,
direct canvas argument selection, draggable free and constrained points,
object visibility/status rows, and an object settings inspector. Keep
GeoTarget branding, licensed icons, the V15 source of truth, and the solver
inspector; do not copy protected GeoGebra artwork or branding. The owner also
asked to avoid AI-looking feature density, decorative cards, invented logos,
and unnatural Japanese. Prefer flat sections, aligned rows, real controls,
restrained borders, and generous working space.

On 2026-07-27 the owner rejected the prototype as substantially less usable
than GeoGebra and reported that visible features did not behave as expected.
The product bar is therefore functional direct manipulation: every visible
canvas primitive must come from the current V15 problem (or an explicitly
labelled solver witness), Point/Segment/Line/Circle/Polygon must be drawable on
the canvas, and no toolbar control may be decorative or a no-op. Preserve the
champion-native JSON as the single source of truth and verify core flows in the
real browser before handoff.

Computed geometry values such as angles, distances, lengths, areas, radii, and
ratios are persistent measurement objects in the project UI. Creating a
measurement must not silently replace the solver target; setting a measurement
as the target is a separate, explicit action, matching GeoGebra's object model.

Condition authoring is mathematical in the product UI. Show and accept familiar
relations such as `<`, `≤`, `=`, `≠`, `≥`, and bounded expressions; keep
`AssumeLt`, `AssumeLe`, `AssumeGe`, `Bound`, and related V15 calls confined to
the canonical JSON/internal adapter boundary.
In scalar UI expressions, accept an unambiguous concatenation of two existing
point IDs such as `AB` as shorthand for `Distance(A, B)`. Preserve a real object
named `AB` and ambiguous concatenations, and always store the expanded V15 form.
Do not expose the engine's guard/constraint split as separate UI sections;
present both as one editable condition list. Do not add a standalone formula
tool or a separate catch-all formula field. Open the GeoGebra-style math
keyboard contextually when the user focuses or clicks a condition,
construction, measurement, or target expression field. Close it and clear the
active expression as soon as the user moves to a non-expression control; the
keyboard must never continue editing a hidden or previously focused field.

The owner expects formula, condition, and construction fields to offer a
GeoGebra-style on-screen math keyboard, not only a plain text input. Keep the
compact `123`, `f(x)`, `ABC`, and symbol tabs; insert at the active caret without
stealing focus; and provide working delete, caret, confirm, and close actions.
Generate the function tab from the non-legacy V15 catalog so the keyboard and
the solver DSL cannot silently drift apart.

Mathematical expressions must read as mathematical notation throughout the UI,
not as raw monospace code. Keep editable V15 text as the canonical value, but
pair expression fields with a KaTeX-quality live preview and use the same
presentation component for object definitions, conditions, measurements,
targets, catalog signatures, and exact solver results. Render common geometry
notation naturally (segment length, angle, fraction, root, relation, interval)
without changing, reparsing, or rewriting the V15 expression sent to the solver.

Guided authoring uses `authoring.ts` as its executable contract for argument
types, canonical order, supporting-line coercion, and output kind. Never infer
whether a tool creates a construction or measurement from its palette/catalog
category. Every guided construction must pass the representative preview
contract test before it is exposed in the UI.

The expanded tool palette is derived from `dsl_catalog.json`; do not maintain a
second hand-picked list of V15 functions. Every non-`legacy_read_only` entry
must remain reachable as a tool. Prefer diagram selection for typed geometric
arguments, and require an explicit control for branch choices such as
`vertex`, `side`, `first`, and orientation.

The owner supplied `geotarget-tool-icons-v5` on 2026-07-29 as the visual
authority for all 79 non-legacy V15 tools. Preserve its SVG geometry and color
semantics (black reference geometry, blue inputs, red constructed outputs,
orange measurements, green conditions); editing actions may retain the
existing product icons. The left algebra/tools pane, right inspector/solver
pane, and bottom problem editor must remain user-resizable, keyboard operable,
and persist their sizes locally.
