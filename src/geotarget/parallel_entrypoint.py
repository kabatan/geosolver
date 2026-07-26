"""Run the byte-frozen champion with only its HP work ordinals sharded."""

from __future__ import annotations

import argparse
import importlib.util
import sys

from geotarget.engine import engine_root
from geotarget.parallel import install


def main() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--product-cpus", required=True)
    arguments, frozen_arguments = parser.parse_known_args()
    cpus = tuple(int(value) for value in arguments.product_cpus.split(","))
    runtime = engine_root() / "runtime"
    entrypoint = (
        runtime
        / "solver/research/experiments/EXP-V15-243-001/repro_20260722/workers"
        / "champion_v2_poc_preloaded.py"
    )
    sys.path.insert(0, str(entrypoint.parent))
    specification = importlib.util.spec_from_file_location(
        "geotarget_product_parallel_frozen", entrypoint
    )
    if specification is None or specification.loader is None:
        raise ImportError(entrypoint)
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    install(module.CHAMPION.BASE, cpus)
    sys.argv = [str(entrypoint), *frozen_arguments]
    module.main()


if __name__ == "__main__":
    main()
