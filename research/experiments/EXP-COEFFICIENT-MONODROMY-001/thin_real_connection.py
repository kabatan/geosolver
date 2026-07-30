"""Thin source-only bridge from the frozen v15 polynomial compiler.

This module owns neither source compilation nor answer authority.  It accepts
only a direct, one-variable QQ polynomial emitted by the pinned existing
compiler/reducer, sends its numerical roots through coefficient monodromy, and
returns only descriptors accepted by the caller's canonical replay function.
"""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

import sympy as sp

try:
    from . import candidate
except ImportError:
    import candidate


PINNED_FILES = {
    "research/experiments/EXP-V15-243-001/candidates/eligible_polynomial_homotopy_revisit/candidate.py": "37641aff3755b05297013d3ae7bec406ad923fc8af139061d4960a0bc76a8c49",
    "research/experiments/EXP-REAL61-002/algebraic_lane/compiler.py": "f127f7f1e2f93161e1353f07222e93ffacfa1c2dbd4e68e5b1fd23a8a3b10318",
    "research/experiments/EXP-REAL61-004/polynomial_homotopy_proposal/reducer.py": "39ef2316816776d7c2f782102e9dca2930a8edd8ba13151b04afa68f88fc10e8",
}


CanonicalReplay = Callable[[tuple[float, ...]], str | None]


@dataclass(frozen=True)
class ConnectedResult:
    baseline_payload: bytes
    descriptors: tuple[str, ...]
    baseline_work: int
    side_work: int
    side_work_used: int
    eligible: bool
    reason: str
    canonical_replay_calls: int = 0
    canonical_replay_rejections: int = 0
    loops_attempted: int = 0
    loops_completed: int = 0


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_pinned_compiler(common_control_root: Path) -> Any:
    for relative, expected in PINNED_FILES.items():
        path = common_control_root / relative
        if not path.is_file() or _sha256(path) != expected:
            raise RuntimeError(f"PINNED_DEPENDENCY_MISMATCH:{relative}")
    path = common_control_root / next(iter(PINNED_FILES))
    specification = importlib.util.spec_from_file_location(
        "coefficient_monodromy_pinned_source_compiler", path
    )
    if specification is None or specification.loader is None:
        raise RuntimeError("PINNED_COMPILER_LOAD_FAILED")
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def _fractions(polynomial: sp.Poly) -> tuple[Fraction, ...]:
    result = []
    for coefficient in polynomial.all_coeffs():
        if not coefficient.is_Rational:
            raise ValueError("NON_RATIONAL_COEFFICIENT")
        result.append(Fraction(int(coefficient.p), int(coefficient.q)))
    return tuple(result)


def _append_unique(baseline: Sequence[str], accepted: Sequence[str]) -> tuple[str, ...]:
    # Do not normalize, sort, copy through JSON, or otherwise rewrite the
    # baseline descriptor byte strings.  The side route is append-only.
    output = list(baseline)
    seen = set(baseline)
    for descriptor in accepted:
        if descriptor not in seen:
            output.append(descriptor)
            seen.add(descriptor)
    return tuple(output)


def _safe_replay(replay: CanonicalReplay, point: tuple[float, ...]) -> str | None:
    try:
        descriptor = replay(point)
    except Exception:  # noqa: BLE001 - authority failure must reject, not escape
        return None
    return descriptor if isinstance(descriptor, str) else None


def connect(
    document: Mapping[str, Any],
    *,
    source_sha256: str,
    accepted_source_point: Sequence[float],
    baseline_payload: bytes,
    baseline_descriptors: Sequence[str],
    total_work: int,
    canonical_replay: CanonicalReplay,
    common_control_root: Path,
) -> ConnectedResult:
    """Run the bounded additive route, failing closed on every seam mismatch."""

    baseline_work, side_work = candidate.split_work(total_work)

    def stopped(reason: str) -> ConnectedResult:
        return ConnectedResult(
            baseline_payload=baseline_payload,
            descriptors=tuple(baseline_descriptors),
            baseline_work=baseline_work,
            side_work=side_work,
            side_work_used=0,
            eligible=False,
            reason=reason,
        )

    try:
        compiler = _load_pinned_compiler(common_control_root)
        caps = compiler.Caps(max_degree=candidate.MAX_DEGREE)
        compiled = compiler.compile_source(
            document, source_sha256=source_sha256, caps=caps
        )
    except Exception as error:  # noqa: BLE001 - external compiler must fail closed
        return stopped(f"SOURCE_COMPILE_REJECTED:{type(error).__name__}")

    original_names = tuple(
        str(name) for name in document.get("variables", {}).get("names", ())
    )
    if len(original_names) != 1 or len(accepted_source_point) != 1:
        return stopped("NOT_DIRECT_RAW_UNIVARIATE")
    if len(compiled.variables) != 1 or len(compiled.equations) != 1:
        return stopped("NOT_REDUCED_UNIVARIATE")
    variable = compiled.variables[0]
    if variable.name != original_names[0]:
        return stopped("REDUCED_VARIABLE_NOT_RAW_VARIABLE")
    if compiled.source_reconstruction or compiled.replay_obligations:
        return stopped("NONTRIVIAL_SOURCE_RECONSTRUCTION_OR_REPLAY")

    try:
        polynomial = sp.Poly(compiled.equations[0], variable, domain=sp.QQ)
        if sp.gcd(polynomial, polynomial.diff()).degree() != 0:
            return stopped("NOT_EXACT_SQUARE_FREE")
        source = candidate.PolynomialSource(
            coefficients_high_to_low=_fractions(polynomial),
            square_free_certificate=True,
        )
    except (ArithmeticError, TypeError, ValueError, sp.PolynomialError):
        return stopped("QQ_UNIVARIATE_EXTRACTION_FAILED")

    # Bind the numerical start to the same replay authority used below.  The
    # returned descriptor need not be re-added; baseline remains byte-identical.
    replay_calls = 1
    if _safe_replay(canonical_replay, (float(accepted_source_point[0]),)) is None:
        return stopped("ACCEPTED_START_CANONICAL_REPLAY_FAILED")

    route = candidate.discover(
        source,
        accepted_start=float(accepted_source_point[0]),
        side_work_cap=side_work,
    )
    accepted_descriptors: list[str] = []
    rejected = 0
    for proposal in route.proposals:
        if abs(proposal.imag) > 1.0e-7:
            rejected += 1
            continue
        try:
            point = compiler.reconstruct_source_coordinates(
                compiled, document, [float(proposal.real)]
            )
        except (ArithmeticError, KeyError, TypeError, ValueError):
            rejected += 1
            continue
        replay_calls += 1
        descriptor = _safe_replay(canonical_replay, tuple(point))
        if descriptor is None:
            rejected += 1
        else:
            accepted_descriptors.append(descriptor)

    return ConnectedResult(
        baseline_payload=baseline_payload,
        descriptors=_append_unique(baseline_descriptors, accepted_descriptors),
        baseline_work=baseline_work,
        side_work=side_work,
        side_work_used=route.charged_work,
        eligible=route.eligible,
        reason=route.reason,
        canonical_replay_calls=replay_calls,
        canonical_replay_rejections=rejected,
        loops_attempted=route.loops_attempted,
        loops_completed=route.loops_completed,
    )
