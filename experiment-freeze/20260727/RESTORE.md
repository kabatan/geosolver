# Restoring the 2026-07-27 experiment freeze

The external archive root is:

`/home/kabatan/work/solver-artifacts/experiment-freeze-20260727/`

Verify the archive containers before extracting:

```bash
cd /home/kabatan/work/solver-artifacts/experiment-freeze-20260727
sha256sum --check ARCHIVE_SHA256SUMS
```

Extract into new, empty directories. Do not extract over a working repository:

```bash
mkdir -p /path/to/restore/solver /path/to/restore/geosolver
tar --zstd -xf solver-workspace.tar.zst -C /path/to/restore/solver
tar --zstd -xf geosolver-workspace.tar.zst -C /path/to/restore/geosolver
```

The corresponding `*-files.sha256.tsv`, `*-git-status.txt`, and `*-head.txt`
files record the content hash, size, type, tracking state, dirty state, and Git
HEAD at freeze time. `VERIFICATION.txt` records the completed extract-and-compare
check.

