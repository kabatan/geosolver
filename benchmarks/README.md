# Benchmarks

Only neutral, newly generated benchmark definitions and compact manifests are
stored here. Raw outputs belong under ignored `benchmarks/results/raw/` paths.
Locked, blind and prospective partitions are access-controlled by their
manifests and are never reused for tuning after they are opened.

Fast, non-gating numerical algorithm comparisons use the thin
[solver laboratory](solver_lab/README.md). Its raw JSON output remains under the
ignored `results/raw/` tree.

The initial tested envelope, critical strata, truth levels and U1-U5 unknown
levels are defined in [RESEARCH_ENVELOPE.md](RESEARCH_ENVELOPE.md) and
`manifests/m0-m4-tested-envelope.json`. Retired solver outputs are not Gold
truth and no retired runtime asset is imported.
