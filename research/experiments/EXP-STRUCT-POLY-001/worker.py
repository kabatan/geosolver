#!/usr/bin/env python3
"""Proposal-only EXP-STRUCT-POLY-001 overlay for the frozen full-v15 champion."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import time
from typing import Mapping, Sequence

from btf_polynomial_pipeline import (
    detect_btf_polynomial_plan,
    run_btf_polynomial_side_route,
)


HERE = Path(__file__).resolve().parent
STRUCTURE_ROOT = HERE.parent / "EXP-STRUCT-001"
if str(STRUCTURE_ROOT) not in sys.path:
    sys.path.insert(0, str(STRUCTURE_ROOT))
from champion_overlay import install as install_proposal_overlay


DEFAULT_FROZEN_ROOT = Path("/home/kabatan/work/solver-experiment-runtime/solver")
FROZEN_ROOT = Path(os.environ.get("GEOTARGET_FROZEN_ROOT", DEFAULT_FROZEN_ROOT))
FROZEN_PYTHON = FROZEN_ROOT / "python/.venv/bin/python"
FROZEN_WORKER = (
    FROZEN_ROOT
    / "research/experiments/EXP-V15-243-001/repro_20260722/workers/"
    "champion_v2_poc_preloaded.py"
)
EXPECTED_FROZEN_WORKER_SHA256 = (
    "e1405739201b0cb1d72e8f9ab6ca402b5e71918e569888993c4fdd13022c7301"
)
EXPECTED_DEPENDENCY_SHA256 = {
    "block_structure.py": "9cb9ce02dc75c63945e350561509e73bbbea401091f400a8cdc0ed69b3dada06",
    "champion_overlay.py": "eff02f620c1e0cf9d61f9962d880d70ab2d97a57517b8c859b8f883ca405a5a2",
    "polynomial_side_route.py": "d7ccd1c9cd63135b4092d957ec15b7965cfba8bf82ea2a37553615a2e8a666c3",
    "btf_polynomial_pipeline.py": "9ac89ed200e97a80a2b91d44f338600c4d586c0ddad973e36785b8629f3ce557",
}
MAXIMUM_SIDE_SECONDS = 2.0
MAXIMUM_SYMBOLIC_BLOCKS = 4
MAXIMUM_CARTESIAN_PROPOSALS = 32
ORIGINAL_REPLAY_RESERVE_SECONDS = 1.0
BASELINE_QUOTA = 0.75
LAST_FACTORY_AUDIT: dict[str, object] = {}


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _mechanism_hash() -> str:
    return _sha256(Path(__file__).read_bytes())


def _closure_hash() -> str:
    payload = b"".join(
        path.read_bytes()
        for path in (
            HERE.parent / "EXP-STRUCT-001/block_structure.py",
            HERE.parent / "EXP-STRUCT-001/champion_overlay.py",
            HERE.parent / "EXP-POLY-001/polynomial_side_route.py",
            HERE / "btf_polynomial_pipeline.py",
        )
    )
    return _sha256(payload)


def _verify_closure() -> None:
    if not FROZEN_PYTHON.is_file() or not FROZEN_WORKER.is_file():
        raise RuntimeError("frozen full-v15 champion closure is unavailable")
    if _sha256(FROZEN_WORKER.read_bytes()) != EXPECTED_FROZEN_WORKER_SHA256:
        raise RuntimeError("frozen full-v15 champion digest changed")
    dependencies = {
        "block_structure.py": HERE.parent / "EXP-STRUCT-001/block_structure.py",
        "champion_overlay.py": HERE.parent / "EXP-STRUCT-001/champion_overlay.py",
        "polynomial_side_route.py": HERE.parent / "EXP-POLY-001/polynomial_side_route.py",
        "btf_polynomial_pipeline.py": HERE / "btf_polynomial_pipeline.py",
    }
    for name, path in dependencies.items():
        if not path.is_file() or _sha256(path.read_bytes()) != EXPECTED_DEPENDENCY_SHA256[name]:
            raise RuntimeError(f"proposal dependency changed: {name}")
    arm = json.loads((HERE / "arm.json").read_text(encoding="utf-8"))
    if not isinstance(arm, Mapping) or arm.get("mechanism_hash") != _mechanism_hash():
        raise RuntimeError("common arm mechanism hash mismatch")


def _argument(arguments: Sequence[str], option: str) -> str | None:
    positions = [index for index, value in enumerate(arguments) if value == option]
    if len(positions) != 1 or positions[0] + 1 >= len(arguments):
        return None
    return arguments[positions[0] + 1]


def frozen_command(arguments: Sequence[str]) -> tuple[str, ...]:
    return (str(FROZEN_PYTHON), str(FROZEN_WORKER), *arguments)


def _delegate(arguments: Sequence[str]) -> None:
    os.execv(str(FROZEN_PYTHON), frozen_command(arguments))


def _source(arguments: Sequence[str]) -> tuple[Path, dict[str, object]] | None:
    raw_path = _argument(arguments, "--source")
    expected = _argument(arguments, "--source-sha256")
    if raw_path is None or expected is None:
        return None
    path = Path(raw_path)
    try:
        payload = path.read_bytes()
        document = json.loads(payload)
    except (OSError, json.JSONDecodeError):
        return None
    if (
        _sha256(payload) != expected
        or not isinstance(document, dict)
        or document.get("task") != "solve"
    ):
        return None
    return path, document


def _load_frozen():
    name = "geotarget_exp_struct_poly_001_frozen_champion"
    if str(FROZEN_WORKER.parent) not in sys.path:
        sys.path.insert(0, str(FROZEN_WORKER.parent))
    specification = importlib.util.spec_from_file_location(name, FROZEN_WORKER)
    if specification is None or specification.loader is None:
        raise ImportError(FROZEN_WORKER)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def _proposal_factory(document, _structure_plan, starts, hard_deadline):
    LAST_FACTORY_AUDIT.clear()
    began = time.monotonic()
    available = min(
        MAXIMUM_SIDE_SECONDS,
        hard_deadline - began - ORIGINAL_REPLAY_RESERVE_SECONDS,
    )
    LAST_FACTORY_AUDIT.update(
        {
            "templates_available": len(starts),
            "template_policy": "FIRST_FINITE_BASELINE_ENDPOINT",
            "local_acceptance_authority": False,
            "maximum_side_seconds": MAXIMUM_SIDE_SECONDS,
            "maximum_symbolic_blocks": MAXIMUM_SYMBOLIC_BLOCKS,
            "maximum_cartesian_proposals": MAXIMUM_CARTESIAN_PROPOSALS,
        }
    )
    if not starts or not math.isfinite(available) or available <= 0.26:
        LAST_FACTORY_AUDIT["status"] = "INSUFFICIENT_SELECTION_RESERVE"
        LAST_FACTORY_AUDIT["proposal_count"] = 0
        return ()
    result = run_btf_polynomial_side_route(
        document,
        starts[0],
        # This arm has no local acceptance authority. Every generated point is
        # deliberately rejected here and then presented to original source
        # replay by champion_overlay.merge_block_proposals.
        lambda _point: False,
        total_starts=4,
        baseline_quota=BASELINE_QUOTA,
        timeout_seconds=available,
        maximum_symbolic_blocks=MAXIMUM_SYMBOLIC_BLOCKS,
        maximum_cartesian_proposals=MAXIMUM_CARTESIAN_PROPOSALS,
    )
    elapsed = time.monotonic() - began
    LAST_FACTORY_AUDIT.update(
        {
            "status": result.status,
            "active_polynomial_blocks": len(result.plan.active_blocks),
            "proposal_count": len(result.proposals),
            "locally_verified_count": len(result.verified),
            "elapsed_seconds": elapsed,
            "within_two_second_cap": elapsed <= MAXIMUM_SIDE_SECONDS,
        }
    )
    if elapsed > MAXIMUM_SIDE_SECONDS or result.status != "complete":
        return ()
    return result.proposals


def install_full_v15(document: Mapping[str, object]):
    """Load and patch the frozen champion at its existing replay seam."""

    _verify_closure()
    frozen = _load_frozen()
    candidate = frozen.CHAMPION
    base = candidate.BASE
    protected_names = (
        "_service_candidates",
        "_run_hp_candidate",
        "_run_restoration_candidate",
        "_authority_descriptor",
        "_descriptor_key",
    )
    protected = {name: getattr(base, name) for name in protected_names}
    replay_audit = install_proposal_overlay(
        candidate,
        proposal_factory=_proposal_factory,
        mechanism_hash=_mechanism_hash(),
        maximum_block_proposals=MAXIMUM_CARTESIAN_PROPOSALS,
    )
    installed_plan = base._plan

    def plan(**kwargs):
        value = installed_plan(_structure_document=document, **kwargs)
        value.update(
            {
                "exp_struct_poly_001": {
                    "mode": "PROPOSAL_ONLY_BEFORE_ORIGINAL_FRESH_SOURCE_REPLAY",
                    "mechanism_hash": _mechanism_hash(),
                    "closure_hash": _closure_hash(),
                    "baseline_search_starts_unchanged": True,
                    "baseline_callback_quota_unchanged": True,
                    "baseline_endpoints_before_proposals": True,
                    "maximum_side_seconds": MAXIMUM_SIDE_SECONDS,
                    "minimum_original_replay_reserve_seconds": ORIGINAL_REPLAY_RESERVE_SECONDS,
                    "maximum_symbolic_blocks": MAXIMUM_SYMBOLIC_BLOCKS,
                    "maximum_cartesian_proposals": MAXIMUM_CARTESIAN_PROPOSALS,
                    "local_candidate_authority": False,
                    "source_replay_guard_hp_exact_descriptor_authority": "ORIGINAL_CHAMPION",
                    "case_id_family_truth_target_count_routing": False,
                }
            }
        )
        return value

    base._plan = plan
    if any(getattr(base, name) is not value for name, value in protected.items()):
        raise RuntimeError("original HP or exact descriptor authority changed")
    return frozen, replay_audit


def _atomic_json(path: Path, document: Mapping[str, object]) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(document, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    arguments = tuple(sys.argv[1:])
    source = _source(arguments)
    if source is None:
        _delegate(arguments)
    _path, document = source
    plan = detect_btf_polynomial_plan(document)
    if not plan.applicable:
        _delegate(arguments)
    frozen, replay_audit = install_full_v15(document)
    frozen.main()
    raw_output = _argument(arguments, "--output")
    if raw_output is not None:
        _atomic_json(
            Path(raw_output).resolve() / "EXP-STRUCT-POLY-001-TELEMETRY.json",
            {
                "schema_version": "geotarget.exp-struct-poly-001-worker-telemetry/v1",
                "mechanism_hash": _mechanism_hash(),
                "closure_hash": _closure_hash(),
                "source_sha256": _argument(arguments, "--source-sha256"),
                "replay_seam": replay_audit(),
                "proposal_factory": dict(LAST_FACTORY_AUDIT),
                "baseline_search_or_quota_modified": False,
                "local_candidate_authority": False,
            },
        )


if __name__ == "__main__":
    main()
