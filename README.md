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

Research preview. The public Julia solve path, open-world plugin ABI, Python
canonical problem builder/validator, deterministic proposal/search loop,
independent candidate replay and checkpoint/resume protocol are implemented and
covered by cross-language tests. Algorithm selection and robustness promotion
continue through preregistered experiments. No solver-completeness claim is
made: ordinary numerical results remain finite observations, not a proof that
all target values were found.

Start with the executable [SDK and plugin quickstart](docs/SDK_AND_PLUGIN_QUICKSTART.md).
It shows a plugin-private differentiable geometric object, Python problem
authoring, registry validation, evaluation and the Julia CLI solve handoff.

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
The current maintainer handoff and restart boundary are recorded in
[docs/operations/HANDOFF.md](docs/operations/HANDOFF.md).

## Source-tree commands

The Python `geotarget` command authors and validates protocol documents; it
does not launch Julia. The Julia application entry point is explicit:

```powershell
uv run --project python geotarget validate problem.json
julia +1.12.6 --startup-file=no --history-file=no --project=julia julia/app/geotarget.jl solve problem.json --options options.json --evidence evidence.json
```

The default Julia application allowlists only the built-in geometry plugin.
Custom applications inject a frozen registry as demonstrated by the
quickstart. `worker_count > 1` is not available in the production runner yet.

## License

No public license has been granted. The repository is private/all rights
reserved until the owner explicitly chooses a license.
