# GeoTarget frozen-runtime provenance

This experiment-branch record stores the research sources that were bundled
into the qualified GeoTarget runtime on `main`.

The product copies on `main` live under
`src/geotarget/_engine/runtime/solver/research/`. The source paths recorded in
`src/geotarget/_engine/product-manifest.json` resolve to this branch's
`research/` tree, so the frozen artifact and its research provenance remain
separate.

The snapshot contains 128 source files. The qualified runtime retains only the
files needed by the selected entrypoint and its five dynamically loaded precision
runtime dependencies; trace-only candidates, source-only runners, restoration experiments,
and experiment-local Julia metadata are kept here and are not packaged by
`main`.
