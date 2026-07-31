#!/usr/bin/env python3
"""Install the categorical fallback behind the frozen exact-outer boundary."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys


class IntegrationError(RuntimeError):
    pass


HERE = Path(__file__).resolve().parent
RUNTIME_ROOT = Path("/home/kabatan/work/solver-experiment-runtime/solver")
requested_runtime = os.environ.get("GEOTARGET_CURRENT_RUNTIME_ROOT")
if requested_runtime is not None and Path(requested_runtime).resolve() != RUNTIME_ROOT:
    raise IntegrationError("alternate current runtime root is forbidden")
CURRENT_OUTER = (
    RUNTIME_ROOT
    / "research/experiments/EXP-V15-243-001/candidates/exact_outer_decorator/worker.py"
)
CURRENT_BOUNDARY = CURRENT_OUTER.parent / "authority_boundary.py"
CATEGORICAL_WORKER = HERE / "categorical_fallback_worker.py"
PINNED_SCHEDULER = (
    RUNTIME_ROOT
    / "research/experiments/EXP-V15-243-001/candidates/"
    "hp_scheduler_preserve_binding/worker.py"
)
SCHEDULER_ENV = "GEOTARGET_EXACT_OUTER_SCHEDULER_WORKER"
EXACT_MODE_ENV = "GEOTARGET_EXACT_OUTER_MODE"
PINNED_EXACT_MODE = "CONFIRM_ALL_AUTHORITIES"
CHAMPION_ENV = "GEOTARGET_HP_PRESERVE_CHAMPION_WORKER"
PINNED_CHAMPION = (
    RUNTIME_ROOT
    / "research/experiments/EXP-V15-243-001/champion_v2/worker.py"
)
HP_ARM_ENV = "GEOTARGET_HP_PRESERVE_BINDING_ARM"
PINNED_HP_ARM = "ADAPTIVE_NO_1280"
SCHEDULER_RUNTIME_BINDING = PINNED_SCHEDULER.with_name("runtime_binding.py")
SCHEDULER_RESOURCE_BRIDGE = PINNED_SCHEDULER.with_name("resource_bridge.py")
HP_LOCK_WORKER = PINNED_SCHEDULER.parent.parent / "hp_lock_scheduler/worker.py"
PYTHON_ENV = RUNTIME_ROOT / "python/.venv"
SITE_PACKAGES = PYTHON_ENV / "lib/python3.12/site-packages"
PYTHON_ENVIRONMENT_FILES = {
    PYTHON_ENV / "pyvenv.cfg": "df9924cf29c7574204083500a8f062501ccaa42ab95aa437ca74c982e83fafee",
    SITE_PACKAGES / "numpy-2.5.1.dist-info/METADATA": "6ae45122ee97050e48849438320430d05f01814f72e66e69cbeed027d2c6a1e8",
    SITE_PACKAGES / "scipy-1.18.0.dist-info/METADATA": "157bd150af3af33b40ec61489be8153752b269fb10c4b45b8cea5104f3235420",
    SITE_PACKAGES / "mpmath-1.3.0.dist-info/METADATA": "44b66ea444b9c0d19ae94815d356bf047ae6b680c19268b5c265687cd6a81406",
    SITE_PACKAGES / "sympy-1.14.0.dist-info/METADATA": "b756c2fbfd5be05ac5bdb0ebca61f55618f30f633ed92d88a5687429313a7595",
    SITE_PACKAGES / "numpy/__init__.py": "09295a80660f17925ae23765ce8cbd7ff7ceae968d5f2f89349f1cb74c0b9e11",
    SITE_PACKAGES / "scipy/__init__.py": "39ccae300a4739cc53719bd3b39ce3f8f66e736c6eb672006e338a4c5cc3dc76",
    SITE_PACKAGES / "mpmath/__init__.py": "b241584d2c1fc0304b0a1015ea923749d7b0800411dd406dcab7c82bf25d9fe8",
    SITE_PACKAGES / "sympy/__init__.py": "4e9476348ba105feab28d82f5bcf6cdba2e3e84de6e059bbfe7a13728c0a4ab0",
}


def _pin_environment(name: str, value: str, *, path: bool = False) -> None:
    requested = os.environ.get(name)
    matches = (
        Path(requested).resolve() == Path(value).resolve()
        if path and requested is not None
        else requested == value
    )
    if requested is not None and not matches:
        raise IntegrationError(f"alternate frozen environment value is forbidden: {name}")
    os.environ[name] = value


_pin_environment(SCHEDULER_ENV, str(PINNED_SCHEDULER), path=True)
_pin_environment(EXACT_MODE_ENV, PINNED_EXACT_MODE)
_pin_environment(CHAMPION_ENV, str(PINNED_CHAMPION), path=True)
_pin_environment(HP_ARM_ENV, PINNED_HP_ARM)
EXPECTED_SHA256 = {
    CURRENT_OUTER: "05650c1016f3974c0f74845037c76604eb38f2f4a337cc700721f0e148d9d3f7",
    CURRENT_BOUNDARY: "a36520a416d0b8c900bca6b79192c7014812c9b1270be09248347f0f19e167e9",
    CATEGORICAL_WORKER: "73c5a8be044f37d7815df08572318cf7294cb5b4008d57983e8367a8ae58bee6",
    PINNED_SCHEDULER: "5453a30c46d3050c0520a6492f149595bf93d4f2794e3e1fa86d7d60c2365702",
    PINNED_CHAMPION: "241128047481cc8a428ff99dcb9d840cbc2ade3e87ddb564bb1a920fe10346ca",
    SCHEDULER_RUNTIME_BINDING: "4ca4b16b0ae391fda96a2eb6bb3808344abcba49057d4eb1c5da257be7138004",
    SCHEDULER_RESOURCE_BRIDGE: "24b59589ba38a929ddfa48dab1953558592dff0f8209202eb8f29d00457d8dc2",
    HP_LOCK_WORKER: "48e86f29beca80587f15a1b691e1d45e7cc0a41d9855c80f4618d3efe6c1b141",
    **PYTHON_ENVIRONMENT_FILES,
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_categorical_freeze() -> dict[str, str]:
    observed = {
        str(path): _sha256(path) if path.is_file() else "MISSING"
        for path in EXPECTED_SHA256
    }
    expected = {str(path): digest for path, digest in EXPECTED_SHA256.items()}
    if observed != expected:
        raise IntegrationError("categorical exact-coordinate closure changed")
    return observed


def _load(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


# Every executable root which can run during import is verified first.
verify_categorical_freeze()
OUTER = _load("categorical_portfolio_current_exact_outer", CURRENT_OUTER)
BASE = OUTER.BASE
EXACT_OUTER = BASE._run_hp_candidate
CAPTURE_COUNT = 1

# The frozen outer still runs the ordinary endpoint first, owns resource
# custody, and calls its strict _consume_fallback boundary on this disposable
# one-refinement exact worker's terminal.
OUTER.EXACT_WORKER = CATEGORICAL_WORKER


def _run(**kwargs):
    verify_categorical_freeze()
    return EXACT_OUTER(**kwargs)


if getattr(BASE, "_categorical_exact_coordinate_portfolio_installed", False):
    raise IntegrationError("categorical exact-coordinate portfolio installed twice")
BASE._run_hp_candidate = _run
BASE._categorical_exact_coordinate_portfolio_installed = True


def closure_manifest() -> dict[str, object]:
    return {
        "schema_version": "geotarget.categorical-exact-coordinate-closure/v1",
        "files": verify_categorical_freeze(),
        "ordinary_endpoint_first": True,
        "existing_exact_outer_consumer_unchanged": True,
        "single_numeric_refinement": True,
        "qreflect_point_point_exact_opcode_only": True,
        "sector_internal_generic_baseline_first": True,
        "scheduler_path_and_sha256_pinned": True,
        "exact_outer_mode": PINNED_EXACT_MODE,
        "selected_champion_worker": str(PINNED_CHAMPION),
        "selected_hp_arm": PINNED_HP_ARM,
        "python_3_12_11_package_manifest_pinned": True,
        "target_set_completeness_claim": False,
        "case_family_truth_target_count_routing": False,
    }


def main() -> None:
    verify_categorical_freeze()
    OUTER.SCHEDULER_MODULE.main()


if __name__ == "__main__":
    main()
