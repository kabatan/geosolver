# GeoTarget design QA

## Visual authority

- Selected target: `docs/design/selected-algebra-workbench.png`
- Final implementation: `docs/design/implementation-final.jpg`
- Side-by-side evidence: `docs/design/comparison-final.png`
- Browser viewport: 1440 × 1024 CSS px
- Target source: 1487 × 1058 px
- Comparison normalization: both images fit into 720 × 512 px without cropping
- State compared: initial/ready workbench with the command editor focused

## Iterations

1. The first implementation pass revealed three P2 differences: a compressed command editor, too few autocomplete rows, and a missing target row in the construction sequence.
2. The editor height was matched to the reference, four realistic `Distance` signatures were added, and `T1` was added to the sequence.
3. The final side-by-side comparison found no remaining P0, P1, or P2 visual issue. Full-size inspection covered the construction table, canvas/toolbars, command editor, resource controls, and exact-result card.

## Functional browser checks

- Construction tool menu, point tool, canvas selection, zoom, undo/redo controls
- Command, JSON, and log tabs; invalid raw JSON preservation
- Solve creation and polling through the local API
- Immediate cancellation through the frozen-engine process group; result classified as `cancelled`
- Complete solve flow using the champion-compatible initial V15 problem
- Exact-result and witness presentation, import/export controls, and keyboard-visible semantic control tree
- No browser console error was observed during the final interaction pass

## Intentional residual differences

- The reference image shows four cores; the product defaults to one because parallel work-item sharding is not exposed by the byte-frozen champion and therefore fails closed.
- Geometry and labels are slightly rescaled to fit the production 1440 × 1024 viewport.
- Experimental proof metadata was omitted from the product result card; stable engine, hash, checkpoint, exact descriptor, and witness fields remain.

final result: passed
