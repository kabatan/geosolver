# Research cleanup — 2026-10-21

The research branch is narrowed to the latest GeoSolver pipeline, GMB environment, solver corpus and GMB comparison infrastructure. Learning experiments and historical outputs are archived here.

`snapshot/` is the complete pre-cleanup Git-visible working tree, including modified and untracked files. Its 2026-10-11 solver source identity is `sha256:f92ee9ba5bea9b124f19e79e95d89e47e66252fede326bb1a569eb1d318e969b`. This is a working-tree snapshot, not a claim that the old research HEAD contained those changes. Snapshot files and patches retain original line endings and whitespace without normalization. See `snapshot-manifest.json` for byte hashes, original HEAD and status, and the patch files for tracked changes.

The removed source modules are the production-disabled integer-segment enumerator and positive-radius sampler. Mixed tests retain coverage for active functionality in research; original versions remain in this snapshot. Contact analysis still used by the current refiner remains in research.

`local-manifest.json` records the same-filesystem moves of Qwen environments, checkpoints, logs, historical evaluations, retired source directories and generated artifacts. Root device/inode, recursive entry counts and byte totals were checked before and after every move. This avoids copying roughly 98 GB.

Local-only storage (not included in Git clones):

```text
/home/kabatan/work/solver-experiment/research-archives/2026-10-21/local/original-tree/
```

Original paths and virtual-environment shebangs are preserved as historical evidence; relocated environments may need rebuilding. Shared external model caches were not moved. Existing experiment history and the unrelated `research-archives/solver-analysis/` directory were left untouched.

`validation-before.json` and `validation-after.json` record checks. The cleanup does not rerun performance campaigns, and prior benchmark timing claims apply only to the pre-cleanup snapshot. Research's `docs/archive.md` points here.
