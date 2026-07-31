"""Pinned QQBar terminal for stable rational-coordinate proposals."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import hashlib
import importlib.util
from pathlib import Path
import sys
import time
from typing import Any, Mapping, Sequence

import sympy as sp

from candidate import CoordinateProposal


EXACT_PATH = Path(
    "/home/kabatan/work/solver-experiment-runtime/solver/research/experiments/"
    "EXP-V15-243-001/candidates/exact_coordinate_replay/candidate.py"
)
EXACT_SHA256 = "e0f24e605e7e7211d134ddea66e66adbb89307148a8f03c1afebd4a2c969c66f"
DAG_PATH = Path(
    "/home/kabatan/work/solver-experiment-runtime/solver/research/experiments/"
    "EXP-REAL61-004/qqbar_exact_replay/dag_compile.py"
)
DAG_SHA256 = "9b83181004a8ea2ea73f2974129e37ce252f7d352937b9f8b601b39eddf03d18"
QQBAR_WORKER = DAG_PATH.parent / "qqbar_worker.jl"
QQBAR_WORKER_SHA256 = "3ac6415600da77f8748a11d15fa47eb3dcb9f8deada375388fc762a155df0b4a"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


for _path, _expected in (
    (EXACT_PATH, EXACT_SHA256),
    (DAG_PATH, DAG_SHA256),
    (QQBAR_WORKER, QQBAR_WORKER_SHA256),
):
    if not _path.is_file() or _sha(_path) != _expected:
        raise RuntimeError(f"frozen exact-coordinate closure changed: {_path}")


def _load_exact():
    specification = importlib.util.spec_from_file_location(
        "geotarget_single_prime_hensel_exact_coordinate", EXACT_PATH
    )
    if specification is None or specification.loader is None:
        raise RuntimeError("cannot load exact-coordinate replay")
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    if Path(module.__file__).resolve() != EXACT_PATH.resolve():
        raise RuntimeError("exact-coordinate replay identity changed")
    return module


EXACT = _load_exact()


@dataclass(frozen=True, slots=True)
class ExactTerminal:
    status: str
    authority_pass: bool
    target_descriptor: Mapping[str, object] | None
    replay: Mapping[str, object] | None
    failure: str | None
    elapsed_cpu_seconds: float
    coordinates_from_float64: bool = False
    target_hp_lanes_are_proposal_only: bool = True


def rational_coordinate_descriptor(value: sp.Rational) -> dict[str, object]:
    value = sp.Rational(value)
    point = str(value)
    return {
        "status": "ALGEBRAIC_PROPOSAL",
        "coefficients_high_to_low": [int(value.q), -int(value.p)],
        "polynomial_metadata": {
            "square_free": True,
            "irreducible_over_Q": True,
            "isolating_interval": {
                "left": point,
                "right": point,
                "multiplicity": 1,
                "real_root_index": 0,
            },
        },
        "independent_confirmation_residual": "0",
        "numeric_lanes_used_only_for_proposal": True,
        "proposal_shortcut": "SAME_BRANCH_STABLE_HENSEL_RATIONAL_POINT",
    }


def linear_target_descriptor(coefficients: Sequence[int]) -> dict[str, object]:
    if (
        len(coefficients) != 2
        or any(not isinstance(value, int) or isinstance(value, bool) for value in coefficients)
        or int(coefficients[0]) == 0
    ):
        raise ValueError("target proposal is not a linear integer relation")
    polynomial = sp.Poly.from_list(list(coefficients), sp.Symbol("t"), domain=sp.ZZ)
    _content, primitive = polynomial.primitive()
    if primitive.LC() < 0:
        primitive = -primitive
    high = [int(value) for value in primitive.all_coeffs()]
    root = Fraction(-high[1], high[0])
    descriptor = rational_coordinate_descriptor(sp.Rational(root.numerator, root.denominator))
    descriptor["coefficients_high_to_low"] = high
    descriptor["proposal_shortcut"] = "FROZEN_ORDINARY_HP_LINEAR_RELATION_PROPOSAL"
    return descriptor


def _replay(
    document: Mapping[str, Any],
    proposal: CoordinateProposal,
    *,
    target: Mapping[str, Any],
    timeout_seconds: float,
) -> ExactTerminal:
    started = time.process_time()
    try:
        if type(proposal) is not CoordinateProposal:
            raise ValueError("terminal requires a stable Hensel CoordinateProposal")
        names = ((document.get("variables") or {}).get("names") or [])
        if not isinstance(names, list) or len(names) != len(proposal.exact_coordinates):
            raise ValueError("source coordinate dimension mismatch")
        values = tuple(sp.sympify(text) for text in proposal.exact_coordinates)
        if any(value.is_Rational is not True for value in values):
            raise ValueError("Hensel terminal accepts exact rational coordinates only")
        coordinates = [rational_coordinate_descriptor(sp.Rational(value)) for value in values]
        prepared, _lowering = EXACT.prepare_document(document)
        job = EXACT.DAG.compile_document(
            prepared,
            coordinate_descriptors=[EXACT._job_descriptor(item) for item in coordinates],
            target_descriptor=EXACT._job_descriptor(target),
        )
        EXACT._normalize_exact_guard_calls(job)
        replay = EXACT._run_qqbar(job, timeout_seconds=float(timeout_seconds))
        EXACT._validate_replay_terminal(
            replay,
            document=prepared,
            coordinate_root_indices=[0] * len(coordinates),
            target_root_index=int(
                EXACT._qqbar_descriptor(target)["isolating_interval"]["real_root_index"]
            ),
        )
        descriptor = EXACT._qqbar_descriptor(target)
        descriptor["isolating_interval"]["real_root_index"] = int(
            replay["target_root_attestation"]["attested_real_root_index"]
        )
        return ExactTerminal(
            "EXACT_SOURCE_GUARD_RAW_TARGET_REPLAY_READY", True, descriptor,
            dict(replay), None, time.process_time() - started,
        )
    except Exception as error:
        return ExactTerminal(
            "EXACT_REPLAY_REJECTED", False, None, None,
            f"{type(error).__name__}:{str(error)[:300]}",
            time.process_time() - started,
        )


def replay_exact_source_guard_raw_target(
    document: Mapping[str, Any],
    proposal: CoordinateProposal,
    *,
    target_hp_lane_a: str,
    target_hp_lane_b: str,
    timeout_seconds: float,
) -> ExactTerminal:
    target = EXACT.recognize_algebraic(target_hp_lane_a, target_hp_lane_b)
    return _replay(document, proposal, target=target, timeout_seconds=timeout_seconds)


def replay_exact_with_linear_hp_relation(
    document: Mapping[str, Any],
    proposal: CoordinateProposal,
    *,
    target_coefficients_high_to_low: Sequence[int],
    timeout_seconds: float,
) -> ExactTerminal:
    return _replay(
        document,
        proposal,
        target=linear_target_descriptor(target_coefficients_high_to_low),
        timeout_seconds=timeout_seconds,
    )


__all__ = [
    "ExactTerminal", "linear_target_descriptor", "rational_coordinate_descriptor",
    "replay_exact_source_guard_raw_target", "replay_exact_with_linear_hp_relation",
]
