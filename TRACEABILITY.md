# Traceability

| Product authority | Frozen evidence |
|---|---|
| Engine ID | `champion-v2-poc-preloaded-20260722` |
| Entrypoint SHA-256 | `e1405739201b0cb1d72e8f9ab6ca402b5e71918e569888993c4fdd13022c7301` |
| Precision preload SHA-256 | `1139fa3ae5f4805b4791bc3f99fb6dd89b38f0cdc778c29871eb7d3469e3c403` |
| Transitive closure | 503 files / `9fa23aecdb9372dfd961b46224b88937c3317eaeb56796a05142563f26078f15` |
| Selection result | 131/145 accepted exact sets, extra 0 |
| Evidence location | branch `experiment`, tag `champion-v2-poc-preloaded-20260722` |

`src/geotarget/_engine/product-manifest.json` maps every frozen source path and
hash to its product path. `geotarget doctor` is the executable enforcement
point.
