# Prototype Instructions

Run the local server yourself and open the preview in the browser available to this environment. Do not give the user server-start instructions when you can run it.

Before making substantial visual changes, use the Product Design plugin's `get-context` skill when the visual source is unclear or no longer matches the current goal. When the user gives durable prototype-specific design feedback, preferences, or decisions, record them in `AGENTS.md`.

When implementing from a selected generated mock, treat that image as the source of truth for layout, component anatomy, density, spacing, color, typography, visible content, and hierarchy.

Build app UI in `src/`. Keep `.openai/hosting.json`, `worker/index.js`, `scripts/prepare-sites-build.mjs`, and `tests/sites-worker.test.mjs` intact so the same local prototype can be handed to Sites. Before a Sites handoff, run `npm run build` and `npm run test:sites`; the build must leave `dist/client/index.html`, `dist/server/index.js`, and `dist/.openai/hosting.json`.

## GeoTarget visual authority

The selected target is the refined Algebra-first Workbench approved on
2026-07-27. Preserve its quiet 48px app bar, 300px construction table, dominant
canvas, 210px command editor, and 350px solver inspector. The owner explicitly
asked to avoid AI-looking feature density, decorative cards, invented logos,
and unnatural Japanese. Prefer flat sections, aligned rows, real controls,
restrained borders, and generous working space.
