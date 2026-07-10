# Open-world black-box plugin example

This directory is the executable companion to
[`docs/SDK_AND_PLUGIN_QUICKSTART.md`](../../docs/SDK_AND_PLUGIN_QUICKSTART.md).

- `BlackBoxCirclePlugin.jl` owns the numerical object and callbacks.
- `build_problem.py` authors canonical protocol JSON without executing Julia.
- `geotarget_custom.jl` injects the trusted plugins into the Julia application.
- `problem.json` and `options.json` are checked-in, schema-valid artifacts.

Run the commands in the quickstart from the repository root. The Python and
Julia integration tests verify that the generated problem remains canonical
and reaches the public solve-result protocol.
