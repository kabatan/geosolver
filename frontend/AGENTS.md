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

## Design system (2026-08-22)

On 2026-08-22 the owner selected a refined-blue accent system (single blue
ramp, violet reserved for intersection snap / derived indicators), no dark
mode, and a token-first stylesheet. All styling lives in `src/styles/`
(`tokens.css` is the source of truth for color/type/shape/elevation/motion;
surfaces are split by area). Keep new styles on tokens; do not reintroduce
magic values or sub-11px type. `App.tsx` re-exports the pure problem/format
API (`catalogPaletteGroups`, `guardToFormula`, etc.) that tests import;
shared types live in `types.ts`, canvas rendering in `canvasParts.tsx`,
small UI parts under `components/`.

## Shapr3D Help Center visual direction (2026-08-23)

The owner selected the Shapr3D Help Center as the visual reference while
keeping GeoTarget's existing functionality and GeoGebra-derived interaction
model. Use a light-only, flat editorial system: near-black chrome (`#0d0d0d`),
electric blue (`#1d4eff`), pale cyan information surfaces (`#e8f9ff` and
`#c6effe`), heavy headings, square controls, restrained overlays, and no
decorative gradients or card stacks. Preserve the four workbench regions, but
the right inspector becomes a drawer below 1440px and solver execution remains
persistently reachable. Existing saved pane sizes must not be overwritten.

## Dark geometric workstation direction (2026-08-23, supersedes visual theme)

The owner later selected a dark Shapr3D sketching/video reference and explicitly
authorized a large visual departure. The default UI is now a near-black
geometric workstation: the canvas and precision grid dominate, peripheral panes
read as compact command decks, construction geometry uses luminous cyan, blue
marks selection, and magenta is reserved for live progress/timeline emphasis.
This supersedes the earlier light Help Center theme while retaining all API,
V15, geometry, keyboard, accessibility, and persistence contracts.

## Spatial Command direction (2026-08-23, current visual authority)

The owner rejected the video-workstation and generic white three-pane variants
as AI-looking, then selected the `Spatial Command` mock. It supersedes every
earlier visual-theme paragraph above. Use a matte graphite model index fused to
the left edge, a warm mineral drafting canvas, a hard-edged floating tool bench,
a selection-attached constraint plate, and a single bottom solver instrument
rail with safety-orange execution signal. The geometry owns the viewport; do
not restore a full-width app header, permanent right inspector, media-player
composition, magenta timeline, rounded SaaS cards, blue CTA, gradients, glass,
glow, or invented logo. Keep the real interaction, V15, accessibility,
persistence, icon, math keyboard, and solver contracts described above.
