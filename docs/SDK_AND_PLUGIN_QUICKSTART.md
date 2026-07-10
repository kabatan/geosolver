# SDK and open-world plugin quickstart

This guide exercises the source-tree APIs that exist today: Python authors and
validates canonical JSON; Julia owns numerical callbacks, plugin registration,
evaluation, solving and evidence. Python does **not** load callbacks or launch
Julia, and a problem document never installs code.

The executable example is in
[`examples/open_world_plugin`](../examples/open_world_plugin). It defines a
plugin-private `HiddenPoint2`, a differentiable constructor and an incidence
relation for the unit circle. Core receives only typed calls and scalar
residuals—the point representation and formula remain black-box Julia code.

## 1. Prepare the source tree

From the repository root, install the locked environments:

```powershell
julia +1.12.6 --startup-file=no --history-file=no --project=julia -e "using Pkg; Pkg.instantiate()"
uv sync --project python --frozen --group dev
```

GeoTarget currently targets Julia 1.12.6 and Python 3.12 or 3.13.

## 2. Define the Julia semantics

[`BlackBoxCirclePlugin.jl`](../examples/open_world_plugin/BlackBoxCirclePlugin.jl)
creates one immutable `PluginSpec`. Its essential structure is:

```julia
struct HiddenPoint2{T<:Real}
    x::T
    y::T
end

hidden_point2(x::Real, y::Real) = HiddenPoint2(promote(x, y)...)
unit_circle_residual(p::HiddenPoint2) = p.x * p.x + p.y * p.y - one(p.x)

kernel = OperatorKernel(
    unit_circle_residual;
    capabilities=CapabilitySet(C0, C1, C2),
    smoothness=SMOOTH_C1,
    derivative_mode=DERIVATIVE_AUTODIFF,
    generic_numeric=true,
)
```

The complete file also declares typed signatures, an explicit truth predicate,
`RELATION_TRUTH_APPROXIMATE_ZERO`, stable plugin/version/ABI IDs and a content
hash. `generic_numeric=true` is valid here because the same implementation
intentionally accepts both `Float64` and `BigFloat`; it is not an automatic
claim that arbitrary code supports high precision.

No global registration occurs. The application runner
[`geotarget_custom.jl`](../examples/open_world_plugin/geotarget_custom.jl)
constructs an allowlist, registers the built-in scalar provider and the custom
plugin, freezes the registry, then injects it into `GeoTargetApp.main`.

## 3. Author canonical problem JSON in Python

[`build_problem.py`](../examples/open_world_plugin/build_problem.py) uses the
generic `ProblemBuilder`:

```python
x = builder.variable("x", type_id=SCALAR, lower=0.5, upper=1.5)
zero = builder.literal(0.0, type_id=SCALAR)
point = builder.call(HIDDEN_POINT, x, zero)
incidence = builder.call(UNIT_CIRCLE, point)
problem = builder.relation(incidence).target(x).build()
```

The positive bounds select the right-hand intersection, so the expected target
is `x = 1`. Generate and validate the checked-in document:

```powershell
uv run --project python python examples/open_world_plugin/build_problem.py --output examples/open_world_plugin/problem.json
uv run --project python geotarget validate examples/open_world_plugin/problem.json
uv run --project python geotarget validate examples/open_world_plugin/options.json --schema solve-options
```

Python validation checks JSON Schema plus graph-wide references, role
separation and plugin ownership. The Julia validation below additionally
requires exact lock matches against executable plugins in the injected
registry:

```powershell
julia +1.12.6 --startup-file=no --history-file=no --project=julia examples/open_world_plugin/geotarget_custom.jl validate examples/open_world_plugin/problem.json
julia +1.12.6 --startup-file=no --history-file=no --project=julia examples/open_world_plugin/geotarget_custom.jl eval examples/open_world_plugin/problem.json --x 1
```

The evaluation should have status `ok`, target `1`, and a zero relation
residual.

## 4. Hand the problem to the solver

For the small source-tree smoke example, `--compile=min -O0` avoids spending
most of the wall budget compiling one dynamically specialized graph. Do not use
those two flags for performance measurements or substantial solves.

```powershell
julia +1.12.6 --compile=min -O0 --startup-file=no --history-file=no --project=julia examples/open_world_plugin/geotarget_custom.jl solve examples/open_world_plugin/problem.json --options examples/open_world_plugin/options.json --evidence evidence.json --max-actions 2
```

The canonical result contains a provisional enclosure around `1` whose
configuration received an independent canonical C2 point replay;
`evidence.json` contains that replay artifact and the deterministic event
trace. This replay is not a root-existence or forward-error proof.
`--max-actions 2` deliberately stops at a short reproducible prefix.
`search_status: "finished_unknown"` and
`target_image_status: "finite_observed"` do not certify that the search found
every answer. Remove `--max-actions`, use normal Julia compilation and choose a
budget/preset appropriate to the real problem for an anytime run.

## Plugin authoring contract

Before relying on a custom plugin:

- Give every plugin, type, operation and selector a stable qualified ID. Change
  the content hash whenever executable semantics or ABI metadata change; bump
  the version for a released semantic change.
- Declare only capabilities implemented on every reachable path. `C0` is
  mandatory; `C1`, `C2`, `C3V` and `C3A` are explicit promises, not requests
  for Core to synthesize support.
- Keep residual, truth, guard, domain, branch and target meanings separate.
  Relation truth is fail-closed by default. Use `approximate_zero` only for an
  explicit equality predicate that may be false at a nonzero numerical
  approximation independently accepted by the residual gate.
- Keep kernels deterministic and type-generic when declaring generic numeric
  support. Return finite values or typed domain/branch semantics; do not hide
  invalid geometry in arbitrary penalties.
- Register code explicitly in an allowlisted `RegistryBuilder`. A JSON lock
  selects an already trusted plugin; it never discovers or loads one.
- Exercise `validate`, `eval`, solve-result round trips and both `Float64` and
  advertised higher-precision paths before shipping the lock metadata.

## Current SDK limits

- The Python command provides authoring, canonicalization and validation only;
  it does not spawn the Julia application. Handoff is an explicit JSON file or
  application-managed transport.
- There is no dynamic plugin package loader or generated Python wrapper layer.
  Custom applications inject a `FrozenPluginRegistry` as shown above.
- The production runner currently requires `worker_count = 1`.
- `validate_candidate` and its current C2 replay are point checks, not
  root-existence, forward-error or all-roots proofs. The solve path also
  requires a usable target-image classification and does not promote an
  inconclusive image. Exact answers require separately supported proof paths;
  capability metadata alone never promotes an answer.

The example is protected by Python artifact tests and a Julia custom-registry
CLI solve test in the normal integration suite.
