# GeoSolver frontend guidance

The frontend is the Spatial Command workbench for GeoSolver. Preserve its current three-pane workflow, keyboard accessibility, responsive layout, project persistence, and canvas interactions.

The public solver boundary uses `GeometryProblem` from `src/problemModel.ts`: `variables`, `constructions`, `conditions`, and `target`. Keep the UI's editable state behind that adapter; do not expose internal search vocabulary or legacy document fields through JSON, HTTP, or exported projects.

Use the packaged catalog as the authority for functions and tool icons. Keep SVG icon geometry in `public/assets/tool-icons.svg` and do not add generated screenshots, visual-review evidence, or unused design assets to the product tree.

Before committing frontend changes, run `pnpm test`, `pnpm build`, and `pnpm test:sites`. For interaction or layout changes, also verify the production-facing page in the browser at desktop and narrow viewport widths.
