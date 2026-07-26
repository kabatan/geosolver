# GeoTarget experiment freeze — 2026-07-27

This directory is the Git-resident index for the final experimental state used
to choose `champion_v2_poc_preloaded`. Large and confidential artifacts are not
stored in Git. They are preserved in the external, checksummed archives listed
in `ARCHIVE_INVENTORY.json`.

The selected arm is the 2026-07-22 `champion_v2_poc_preloaded` run:

- exact target sets accepted: 131 / 145
- extra or false exact targets: 0
- provenance closure: 503 files
- provenance closure SHA-256:
  `9fa23aecdb9372dfd961b46224b88937c3317eaeb56796a05142563f26078f15`
- wrapper SHA-256:
  `e1405739201b0cb1d72e8f9ab6ca402b5e71918e569888993c4fdd13022c7301`
- precision preload SHA-256:
  `1139fa3ae5f4805b4791bc3f99fb6dd89b38f0cdc778c29871eb7d3469e3c403`

`CHAMPION_CLOSURE_MANIFEST.json` is extracted unchanged from the recorded
execution plan and is the authority for the frozen transitive implementation.

