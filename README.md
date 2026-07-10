# GeoTarget

GeoTarget is an anytime numerical solver for geometry problems whose answer is
a finite set of real scalar target values. Its primary objective is to maximize
the probability of recovering **all distinct target values** within a fixed
budget while keeping every reported answer independently verifiable.

The project is a clean-slate implementation with:

- a Julia numerical core;
- an open-world typed construction graph and Julia plugin ABI;
- a Python problem builder and JSON/CLI protocol;
- separate discovery, high-precision validation, and exact-target proof levels;
- reproducible, family-disjoint research and benchmark gates.

The implementation is intentionally research-driven. Product invariants and
answer semantics are fixed in [CHARTER.md](CHARTER.md); search policies are
promoted only through preregistered experiments.

## Current status

Bootstrap/M0. The public ABI and vertical slice are under construction. No
solver-completeness claim is made yet.

## Repository map

```text
julia/GeoTargetBase/       Stable graph, plugin ABI, result and status types
julia/GeoTargetCore/       Compiler, oracle, search, archive and verification
julia/GeoTargetGeometry/   Built-in geometry implemented through the plugin ABI
python/                    Python builder and CLI client
docs/                      ADRs, research ledger, milestones and specifications
benchmarks/                Generated families, manifests and compact results
scripts/                   Reproducible developer and CI entry points
```

Operational protocol: [checkpoint and resume](docs/operations/CHECKPOINTS.md).

## License

No public license has been granted. The repository is private/all rights
reserved until the owner explicitly chooses a license.
