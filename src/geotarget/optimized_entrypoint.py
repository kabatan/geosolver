"""Run the champion through product-owned, qualified scheduling adapters."""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

from geotarget.engine import engine_root
from geotarget.optimized_search import install as install_search
from geotarget.parallel import install as install_hp


def main() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--product-cpus", required=True)
    arguments, frozen_arguments = parser.parse_known_args()
    cpus = tuple(int(value) for value in arguments.product_cpus.split(","))
    if not cpus or len(set(cpus)) != len(cpus):
        raise SystemExit("optimized engine requires distinct physical CPUs")
    runtime = engine_root() / "runtime"
    entrypoint = (
        runtime
        / "solver/research/experiments/EXP-V15-243-001/repro_20260722/workers"
        / "champion_v2_poc_preloaded.py"
    )
    sys.path.insert(0, str(entrypoint.parent))
    specification = importlib.util.spec_from_file_location(
        "geotarget_product_optimized_champion", entrypoint
    )
    if specification is None or specification.loader is None:
        raise ImportError(entrypoint)
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    frozen_parser = argparse.ArgumentParser(add_help=False)
    frozen_parser.add_argument("--output", type=Path, required=True)
    frozen_parser.add_argument("--source-sha256", required=True)
    frozen_options, _unknown = frozen_parser.parse_known_args(frozen_arguments)
    module.CHAMPION.BASE.HP_BRIDGE = Path(__file__).with_name("hp_slot_entrypoint.py")
    install_hp(
        module.CHAMPION.BASE,
        cpus,
        reservoir_checkpoint_path=frozen_options.output / "candidate-reservoir.json",
        source_sha256=frozen_options.source_sha256,
    )
    install_search(module.CHAMPION.BASE, cpus)
    sys.argv = [str(entrypoint), *frozen_arguments]
    module.main()


if __name__ == "__main__":
    main()
