"""Single-prime stable rational-coordinate proposals; never an authority."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib.util
from pathlib import Path
import sys
import time
from typing import Any, Mapping, Sequence

import sympy as sp


FROZEN_ROOT = Path(
    "/home/kabatan/work/solver-experiment-runtime/solver/research/experiments/"
    "EXP-V15-243-001/candidates"
)
OLD_PATH = FROZEN_ROOT / "wave14_padic_hensel_source_proposal/candidate.py"
STAGED_PATH = FROZEN_ROOT / "wave14_padic_hensel_staged_cycle/candidate.py"
OLD_SHA256 = "0b3c8d4edde5f6de61358aa88c2d0b26b7eb2c927fc5664f5d7f9980566aa34c"
STAGED_SHA256 = "51c278458f600cd5d2b1b8f21fdfab585404af473e2e78f15f559eaec5865269"
STABILITY_EXPONENT = 5


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(name: str, path: Path, expected: str) -> Any:
    if not path.is_file() or _sha(path) != expected:
        raise RuntimeError(f"frozen Hensel dependency changed: {path}")
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise RuntimeError(f"cannot load frozen Hensel dependency: {path}")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    if Path(module.__file__).resolve() != path.resolve():
        raise RuntimeError("loaded Hensel dependency identity changed")
    return module


OLD = _load("geotarget_single_prime_hensel_frozen_old", OLD_PATH, OLD_SHA256)
STAGED = _load("geotarget_single_prime_hensel_frozen_staged", STAGED_PATH, STAGED_SHA256)
ProposalEnvelope = OLD.ProposalEnvelope
ProposalBoundaryError = OLD.ProposalBoundaryError
canonical_proposal_envelope = OLD.canonical_proposal_envelope
PRIME_SCHEDULE = tuple(OLD.PRIME_SCHEDULE)


@dataclass(frozen=True, slots=True)
class CoordinateProposal:
    exact_coordinates: tuple[str, ...]
    selected_prime: int
    modulus_exponents: tuple[int, int]
    proposal_authority: bool = False
    release: bool = False
    descriptor: None = None
    existing_exact_source_guard_raw_target_replay_required: bool = True


@dataclass(frozen=True, slots=True)
class ProposalBatch:
    candidates: tuple[CoordinateProposal, ...]
    work: Mapping[str, int]
    reason: str
    elapsed_cpu_seconds: float
    proposal_authority: bool = False
    release: bool = False
    descriptor: None = None


def _lift_pair(
    symbols: Sequence[sp.Symbol],
    polynomials: Sequence[sp.Poly],
    root: Sequence[int],
    prime: int,
) -> tuple[tuple[int, ...], int, tuple[int, ...], int, int] | None:
    """Lift one modular branch once, capturing the same branch at p^k,p^(k+1)."""

    rows = OLD._regular_rows(symbols, polynomials, root, prime)
    if rows is None:
        return None
    value = tuple(int(item) % prime for item in root)
    modulus = prime
    low = None
    low_modulus = 0
    steps = 0
    for exponent in range(1, STABILITY_EXPONENT + 1):
        substitution = dict(zip(symbols, value, strict=True))
        selected = [int(polynomials[row].eval(substitution)) for row in rows]
        if any(item % modulus for item in selected):
            return None
        jacobian = sp.Matrix(
            [
                [
                    int(sp.diff(polynomials[row].as_expr(), symbol).subs(substitution))
                    % prime
                    for symbol in symbols
                ]
                for row in rows
            ]
        )
        try:
            inverse = jacobian.inv_mod(prime)
        except Exception:
            return None
        right = sp.Matrix([-(item // modulus) % prime for item in selected])
        digits = tuple(int(item) % prime for item in inverse * right)
        proposed = tuple(
            coordinate + modulus * digit
            for coordinate, digit in zip(value, digits, strict=True)
        )
        next_modulus = modulus * prime
        next_substitution = dict(zip(symbols, proposed, strict=True))
        if any(int(polynomial.eval(next_substitution)) % next_modulus for polynomial in polynomials):
            return None
        value, modulus = proposed, next_modulus
        steps += 1
        if exponent + 1 == STABILITY_EXPONENT:
            low, low_modulus = tuple(item % modulus for item in value), modulus
    if low is None or modulus != prime ** (STABILITY_EXPONENT + 1):
        return None
    return low, low_modulus, tuple(item % modulus for item in value), modulus, steps


def _reconstruct_tuple(residues: Sequence[int], modulus: int):
    values = tuple(OLD.rational_reconstruct(int(value), modulus) for value in residues)
    if any(value is None for value in values):
        return None
    return tuple(value for value in values if value is not None)


def propose(envelope: ProposalEnvelope) -> ProposalBatch:
    if type(envelope) is not ProposalEnvelope:
        raise ProposalBoundaryError("single-prime proposal accepts only frozen ProposalEnvelope")
    started = time.process_time()
    work = {
        "prime_attempt_count": 0,
        "degree_drop_prime_count": 0,
        "no_root_prime_count": 0,
        "singular_image_prime_count": 0,
        "selected_prime_count": 0,
        "modular_root_count": 0,
        "lifted_branch_count": 0,
        "hensel_digit_step_count": 0,
        "tuple_reconstruction_pair_count": 0,
        "tuple_stability_pass_count": 0,
        "exact_substitution_count": 0,
        "exact_substitution_pass_count": 0,
        "cross_prime_cartesian_pair_count": 0,
        "crt_merge_count": 0,
    }
    try:
        symbols, polynomials = OLD._compiled_polynomials(envelope.source_projection)
        selected_prime = None
        selected_roots = ()
        for prime in PRIME_SCHEDULE:
            work["prime_attempt_count"] += 1
            if not OLD._degree_stable(polynomials, prime):
                work["degree_drop_prime_count"] += 1
                continue
            roots = OLD._modular_roots(symbols, polynomials, prime)
            if not roots:
                work["no_root_prime_count"] += 1
                continue
            regular = tuple(
                root
                for root in roots
                if OLD._regular_rows(symbols, polynomials, root, prime) is not None
            )
            if not regular or len(regular) != len(roots):
                work["singular_image_prime_count"] += 1
                continue
            selected_prime, selected_roots = int(prime), regular
            work["selected_prime_count"] = 1
            work["modular_root_count"] = len(regular)
            break
        if selected_prime is None:
            return ProposalBatch((), work, "no-deterministic-nonsingular-good-prime", time.process_time() - started)

        candidates = []
        for root in selected_roots:
            lifted = _lift_pair(symbols, polynomials, root, selected_prime)
            if lifted is None:
                continue
            low_residues, low_modulus, high_residues, high_modulus, steps = lifted
            work["lifted_branch_count"] += 1
            work["hensel_digit_step_count"] += steps
            work["tuple_reconstruction_pair_count"] += 1
            low = _reconstruct_tuple(low_residues, low_modulus)
            high = _reconstruct_tuple(high_residues, high_modulus)
            if low is None or high is None or low != high:
                continue
            work["tuple_stability_pass_count"] += 1
            values = tuple(sp.Rational(value.numerator, value.denominator) for value in high)
            work["exact_substitution_count"] += 1
            substitution = dict(zip(symbols, values, strict=True))
            if not all(polynomial.eval(substitution) == 0 for polynomial in polynomials):
                continue
            work["exact_substitution_pass_count"] += 1
            candidates.append(
                CoordinateProposal(
                    tuple(sp.srepr(value) for value in values),
                    selected_prime,
                    (STABILITY_EXPONENT, STABILITY_EXPONENT + 1),
                )
            )
        unique = {item.exact_coordinates: item for item in candidates}
        ordered = tuple(unique[key] for key in sorted(unique))
        return ProposalBatch(
            ordered,
            work,
            "single-prime-same-branch-stable-tuple-proposed-not-authority",
            time.process_time() - started,
        )
    except Exception as error:
        work["fail_closed_count"] = 1
        return ProposalBatch(
            (), work, f"fail-closed:{type(error).__name__}:{str(error)[:180]}",
            time.process_time() - started,
        )


def boundary_manifest() -> dict[str, object]:
    return {
        "source_projection_only": True,
        "frozen_old_sha256": OLD_SHA256,
        "frozen_staged_sha256": STAGED_SHA256,
        "deterministic_prime_schedule": list(PRIME_SCHEDULE),
        "selected_good_prime_count_maximum": 1,
        "stable_modulus_exponents": [STABILITY_EXPONENT, STABILITY_EXPONENT + 1],
        "same_modular_branch_both_lifts": True,
        "same_modulus_all_coordinates": True,
        "tuple_stability_required": True,
        "exact_polynomial_substitution_required": True,
        "cross_prime_cartesian_product": False,
        "crt_used": False,
        "proposal_authority": False,
        "target_or_truth_input": False,
        "existing_exact_source_guard_raw_target_replay_required": True,
        "release": False,
    }


__all__ = [
    "CoordinateProposal", "OLD", "ProposalBatch", "ProposalBoundaryError",
    "ProposalEnvelope", "STAGED", "boundary_manifest",
    "canonical_proposal_envelope", "propose",
]
