#!/usr/bin/env python3
"""Proof-only target identity over the complete typed algebraic cover.

Unlike the earlier closed-affine subset lowerer, this experiment asks the
frozen typed compiler to lower the source and raw target in one shared state.
Every auxiliary equation and predicate is retained.  A bounded sparse
cofactor identity proves ``h`` or the fixed real-radical repair ``h**2``.

This module never releases a target.  Source-root and branch certificates are
mandatory inputs, are digest-bound, and remain independent conjuncts.
"""

from __future__ import annotations

import ast
from fractions import Fraction
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Mapping, Sequence

import sympy as sp


HERE = Path(__file__).resolve().parent
RUNTIME_ROOT = Path(
    os.environ.get("GEOTARGET_CURRENT_RUNTIME_ROOT", "/home/kabatan/work/solver-experiment-runtime/solver")
).resolve()
DIRECT_PATH = HERE.parent / "guided_target_ideal_membership_v1/ideal_membership.py"
TYPED_PATH = (
    RUNTIME_ROOT
    / "research/experiments/EXP-V15-243-001/candidates/typed_guard_algebraic_extension/typed_guard_adapter.py"
)
LOCAL_PATH = TYPED_PATH.with_name("local_worker_adapter.py")
FROZEN_SHA256 = {
    DIRECT_PATH: "74915d163e471df9e745735a8f5e3f7a128950d72c94d581c6435ffd081b60b4",
    TYPED_PATH: "1d93005c49cf4e3360b8b64449022be46e97ae59cc437ef889f5289e239709b4",
    LOCAL_PATH: "711a14c9bcce7bd99c770768199f4b778b819434b1bcf0b9454024d0cea68150",
}
SCHEMA = "geotarget.guided-target-typed-cover-membership-proof/v1"
COVER_CERTIFICATE_SCHEMA = "geotarget.generated-exact-typed-cover-witness/v1"
MAX_VARIABLES = 12
MAX_EQUATIONS = 20
MAX_DEGREE = 6
MAX_TERMS = 400


class CoverRejected(RuntimeError):
    pass


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_sha(value: object) -> str:
    return _sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode("utf-8")
    )


def _load(name: str, path: Path) -> Any:
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


for _path, _digest in FROZEN_SHA256.items():
    if _sha256(_path.read_bytes()) != _digest:
        raise RuntimeError(f"frozen proof/compiler dependency changed: {_path}")
BASE = _load("guided_target_typed_cover_frozen_direct", DIRECT_PATH)
_prior = sys.modules.get("typed_guard_adapter")
TYPED = _load("typed_guard_adapter", TYPED_PATH)
LOCAL = _load("guided_target_typed_cover_local", LOCAL_PATH)
if _prior is None:
    del sys.modules["typed_guard_adapter"]
else:
    sys.modules["typed_guard_adapter"] = _prior


def prepare_source_root_job(source_path: Path, endpoint: Sequence[float]) -> dict[str, Any]:
    """Prepare the frozen source-only job; the raw answer is not read by it."""

    return LOCAL.prepare_source_certificate_job(source_path, endpoint)


def _poly(expression: Any, symbols: Sequence[sp.Symbol]) -> sp.Expr:
    value = sp.expand(sp.sympify(expression))
    polynomial = sp.Poly(value, *symbols, domain=sp.QQ)
    if polynomial.total_degree() > MAX_DEGREE or len(polynomial.terms()) > MAX_TERMS:
        raise CoverRejected("typed cover polynomial cap exceeded")
    return polynomial.as_expr()


def _compile_complete_cover(document: Mapping[str, Any]) -> dict[str, Any]:
    if document.get("task") != "solve" or document.get("post_process") not in (None, ""):
        raise CoverRejected("raw solve target without post-process is required")
    answer = document.get("answer")
    if not isinstance(answer, str) or not answer.strip():
        raise CoverRejected("raw scalar target is absent")
    # Identity is deliberately not provided to the compiler or any routing key.
    anonymous = {key: value for key, value in document.items() if key != "id"}
    compiler = TYPED.TypedGuardCompiler(dict(anonymous))
    source_result = compiler.compile()
    if (
        source_result.interval_local_ready is not True
        or source_result.unsupported
        or source_result.reconstruction
        or source_result.replay_obligations
        or any(TYPED._contains_any(item) for item in compiler.typed_guard_obligations)
    ):
        raise CoverRejected("source cover has unsupported reconstruction/selector/replay")
    source_equation_count = len(compiler.equations)
    source_predicate_count = len(compiler.predicates)
    try:
        target = compiler.eval(ast.parse(answer, mode="eval").body, "raw-target")
    except (SyntaxError, TYPED.Unsupported, TypeError, ValueError) as error:
        raise CoverRejected(f"typed target lowering failed: {error}") from error
    if not isinstance(target, sp.Expr):
        raise CoverRejected("typed target is not scalar")
    if compiler.reconstruction or compiler.replay:
        raise CoverRejected("target introduced reconstruction/selector/replay")
    if len(compiler.unknowns) > MAX_VARIABLES or not 1 <= len(compiler.equations) <= MAX_EQUATIONS:
        raise CoverRejected("typed cover size cap exceeded")
    symbols = tuple(compiler.unknowns)
    equations = tuple(_poly(expression, symbols) for expression, _source in compiler.equations)
    # polynomialize can add denominator definedness predicates.  Iterate to a fixed point.
    target_expression = compiler.polynomialize(sp.sympify(target), "raw-target-expression")
    predicates: list[dict[str, str]] = []
    index = 0
    while index < len(compiler.predicates):
        predicate = compiler.predicates[index]
        predicates.append(
            {
                "expression": str(_poly(compiler.polynomialize(predicate.expression, predicate.source), symbols)),
                "relation": predicate.relation,
                "source": predicate.source,
            }
        )
        index += 1
        if index > 64:
            raise CoverRejected("definedness predicate cap exceeded")
    target_expression = _poly(target_expression, symbols)
    ledger = {
        "variables": [symbol.name for symbol in symbols],
        "equations": [str(item) for item in equations],
        "predicates": predicates,
        "typed_guard_obligations": compiler.typed_guard_obligations,
        "source_equation_count": source_equation_count,
        "source_predicate_count": source_predicate_count,
        "target_expression": str(target_expression),
        "reconstruction": [],
        "replay_obligations": [],
    }
    return {
        "symbols": symbols,
        "equations": equations,
        "predicates": predicates,
        "target": target_expression,
        "ledger": ledger,
        "cover_sha256": _canonical_sha(ledger),
    }


def _relation_holds(value: sp.Expr, relation: str) -> bool:
    value = sp.factor(value)
    if value.is_rational is not True:
        return False
    if relation == "eq":
        return value == 0
    if relation == "ne":
        return value != 0
    if relation == "gt":
        return bool(value > 0)
    if relation == "ge":
        return bool(value >= 0)
    if relation == "lt":
        return bool(value < 0)
    if relation == "le":
        return bool(value <= 0)
    return False


def exact_cover_certificate_for_generated_test(
    source_path: Path,
    *,
    assignment: Mapping[str, str | int],
    source_job: Mapping[str, Any],
    source_certificate: Mapping[str, Any],
) -> dict[str, Any]:
    """Create a digest binding only; exact equations/predicates are rechecked later."""

    document = json.loads(source_path.read_bytes())
    cover = _compile_complete_cover(document)
    return {
        "schema_version": COVER_CERTIFICATE_SCHEMA,
        "generated_fixture_only": True,
        "cover_sha256": cover["cover_sha256"],
        "source_job_sha256": source_job.get("job_sha256"),
        "source_certificate_sha256": _canonical_sha(source_certificate),
        "assignment": {str(key): str(value) for key, value in assignment.items()},
    }


def _verify_source_and_cover(
    source_path: Path,
    cover: Mapping[str, Any],
    source_job: Mapping[str, Any],
    source_certificate: Mapping[str, Any],
    cover_certificate: Mapping[str, Any],
) -> dict[sp.Symbol, sp.Rational]:
    LOCAL.verify_source_certificate_binding(source_path, dict(source_job), dict(source_certificate))
    system = source_job.get("system")
    if not (
        source_job.get("schema_version") == "geotarget.typed-guard-source-certificate-job/v2"
        and source_job.get("authority") == "SOURCE_ROOT_AND_TYPED_GUARDS_ONLY_NO_TARGET_AUTHORITY"
        and source_job.get("target_read") is False
        and source_job.get("truth_used") is False
        and isinstance(system, Mapping)
        and system.get("source_target_not_read") is True
        and system.get("reconstruction") == []
        and system.get("replay_obligations") == []
        and source_certificate.get("schema_version") == "geotarget.local-krawczyk-certificate/v1"
        and source_certificate.get("status") == "VERIFIED"
        and source_certificate.get("unique_regular_root_in_rational_box") is True
        and source_certificate.get("strict_krawczyk_inclusion") is True
        and source_certificate.get("all_source_predicates_interval_valid") is True
        and source_certificate.get("target_equality_requires_exact_link") is True
        and source_certificate.get("coverage") == "UNKNOWN"
    ):
        raise CoverRejected("source-root/typed-guard certificate is incomplete")
    if not (
        isinstance(cover_certificate, Mapping)
        and cover_certificate.get("schema_version") == COVER_CERTIFICATE_SCHEMA
        and cover_certificate.get("generated_fixture_only") is True
        and cover_certificate.get("cover_sha256") == cover.get("cover_sha256")
        and cover_certificate.get("source_job_sha256") == source_job.get("job_sha256")
        and cover_certificate.get("source_certificate_sha256") == _canonical_sha(source_certificate)
        and isinstance(cover_certificate.get("assignment"), Mapping)
    ):
        raise CoverRejected("complete cover certificate binding changed")
    symbols = cover["symbols"]
    raw_assignment = cover_certificate["assignment"]
    if set(raw_assignment) != {symbol.name for symbol in symbols}:
        raise CoverRejected("cover assignment is incomplete or has extra variables")
    try:
        assignment = {symbol: sp.Rational(str(raw_assignment[symbol.name])) for symbol in symbols}
    except (TypeError, ValueError, ZeroDivisionError) as error:
        raise CoverRejected("cover assignment is not exact rational data") from error
    if any(sp.expand(equation.subs(assignment)) != 0 for equation in cover["equations"]):
        raise CoverRejected("complete equation ledger does not vanish at certified root")
    for predicate in cover["predicates"]:
        expression = sp.sympify(predicate["expression"], locals={s.name: s for s in symbols})
        if not _relation_holds(sp.expand(expression.subs(assignment)), predicate["relation"]):
            raise CoverRejected("cover branch/definedness predicate failed")
    job_variables = system.get("variables")
    local_box = source_job.get("local_box")
    if not isinstance(job_variables, list) or not isinstance(local_box, list) or len(job_variables) != len(local_box):
        raise CoverRejected("source-root box ledger is malformed")
    by_name = {symbol.name: value for symbol, value in assignment.items()}
    for name, interval in zip(job_variables, local_box, strict=True):
        if name not in by_name or not isinstance(interval, Mapping):
            raise CoverRejected("source-root variables are not cover-bound")
        if not sp.Rational(interval["lower"]) <= by_name[name] <= sp.Rational(interval["upper"]):
            raise CoverRejected("cover root lies outside certified source-root box")
    return assignment


def _unproved(reason: str, source_sha256: str, elapsed: float) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA,
        "status": "TYPED_COVER_IDENTITY_NOT_PROVED",
        "reason": reason,
        "source_sha256": source_sha256,
        "authority_pass": False,
        "target_release": False,
        "common_worker_integration": "HOLD",
        "truth_used": False,
        "elapsed_wall_seconds": elapsed,
    }


def prove_typed_cover_identity(
    source_path: Path,
    *,
    ordinary_proposal: Mapping[str, Any],
    source_job: Mapping[str, Any],
    source_certificate: Mapping[str, Any],
    cover_certificate: Mapping[str, Any],
    timeout_seconds: float = 3.0,
) -> dict[str, Any]:
    started = time.monotonic()
    source_sha = _sha256(source_path.read_bytes()) if source_path.is_file() else "UNAVAILABLE"
    try:
        if ordinary_proposal.get("status") != "TARGET_AUTHORITY_READY" or ordinary_proposal.get("authority_pass") is not True:
            raise CoverRejected("ordinary exact proposal is not ready")
        rational, relation = BASE.rational_candidate_from_descriptor(ordinary_proposal.get("descriptor"))
        proposal_sha = _canonical_sha(ordinary_proposal)
        document = json.loads(source_path.read_bytes())
        cover = _compile_complete_cover(document)
        _verify_source_and_cover(source_path, cover, source_job, source_certificate, cover_certificate)
        q = sp.Rational(rational.numerator, rational.denominator)
        h = _poly(cover["target"] - q, cover["symbols"])
        selected_power = None
        cofactors = None
        powered = None
        for power in (1, 2):
            candidate = _poly(h**power, cover["symbols"])
            witness = BASE._cofactor_witness(cover["equations"], candidate, cover["symbols"])
            if witness is not None:
                selected_power, cofactors, powered = power, witness, candidate
                break
        if cofactors is None or powered is None or selected_power is None:
            raise CoverRejected("bounded complete-ledger sparse cofactor identity unavailable")
        if time.monotonic() - started > timeout_seconds:
            raise CoverRejected("proof deadline exceeded")
        statement = {
            "theorem": "COMPLETE_TYPED_COVER_COFACTOR_IDENTITY",
            "source_sha256": source_sha,
            "ordinary_proposal_sha256": proposal_sha,
            "candidate_relation": relation,
            "source_job_sha256": source_job.get("job_sha256"),
            "source_certificate_sha256": _canonical_sha(source_certificate),
            "cover_sha256": cover["cover_sha256"],
            "complete_equation_ledger": cover["ledger"]["equations"],
            "complete_predicate_ledger": cover["ledger"]["predicates"],
            "typed_guard_obligations": cover["ledger"]["typed_guard_obligations"],
            "target_minus_q": str(h),
            "radical_power": selected_power,
            "powered_relation": str(powered),
            "source_equation_cofactors": [str(item) for item in cofactors],
        }
        return {
            "schema_version": SCHEMA,
            "status": "TYPED_COVER_IDENTITY_PROVED_HOLD",
            "source_sha256": source_sha,
            "ordinary_proposal_sha256": proposal_sha,
            "cover_sha256": cover["cover_sha256"],
            "radical_power": selected_power,
            "complete_equation_count": len(cover["equations"]),
            "complete_predicate_count": len(cover["predicates"]),
            "all_cover_equations_adopted": True,
            "all_cover_predicates_exactly_checked_at_certified_root": True,
            "source_root_certificate_bound": True,
            "cofactor_witness_complete": True,
            "statement": statement,
            "statement_sha256": _canonical_sha(statement),
            "authority_pass": False,
            "target_release": False,
            "common_worker_integration": "HOLD",
            "truth_used": False,
            "elapsed_wall_seconds": time.monotonic() - started,
        }
    except Exception as error:
        reason = str(error) if isinstance(error, (CoverRejected, BASE.ProofOnlyRejected)) else f"{type(error).__name__}: {error}"
        return _unproved(reason, source_sha, time.monotonic() - started)


def verify_typed_cover_proof(source_path: Path, *, artifact: Mapping[str, Any], **kwargs: Any) -> None:
    replayed = prove_typed_cover_identity(source_path, **kwargs)
    mandatory = (
        "schema_version", "status", "source_sha256", "ordinary_proposal_sha256",
        "cover_sha256", "radical_power", "complete_equation_count",
        "complete_predicate_count", "all_cover_equations_adopted",
        "cofactor_witness_complete", "statement", "statement_sha256",
    )
    if replayed.get("status") != "TYPED_COVER_IDENTITY_PROVED_HOLD" or any(
        artifact.get(key) != replayed.get(key) for key in mandatory
    ):
        raise CoverRejected("typed cover proof differs from exact replay")
    if _canonical_sha(artifact.get("statement")) != artifact.get("statement_sha256"):
        raise CoverRejected("typed cover statement digest changed")
    if artifact.get("authority_pass") is not False or artifact.get("target_release") is not False:
        raise CoverRejected("proof-only artifact claims release authority")


__all__ = [
    "COVER_CERTIFICATE_SCHEMA", "CoverRejected", "exact_cover_certificate_for_generated_test",
    "prepare_source_root_job", "prove_typed_cover_identity", "verify_typed_cover_proof",
]
