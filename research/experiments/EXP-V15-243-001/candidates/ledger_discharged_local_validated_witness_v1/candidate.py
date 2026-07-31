"""Disposable D0 seam: typed replay discharge before the frozen C3V local link.

This is deliberately not a compiler.  It accepts only obligations whose exact
meaning is already present in a typed payload, proves them on a digest-bound
Krawczyk box, and then calls the already-frozen localized FGLM link.  Original
DSL replay remains mandatory and this module can never release a target.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any, Mapping, Sequence

import sympy as sp


FROZEN_LINK = Path(
    "/home/kabatan/work/solver-experiment-runtime/solver/research/experiments/"
    "EXP-V15-243-001/candidates/c3v_target_link_modernization/localized_link.py"
)
FROZEN_LINK_SHA256 = "d1b0ddef62ce1cfc52639364184cadcd0a97a1cf82fa61c724e49f0a47a016bd"
SCHEMA = "geotarget.typed-ledger-krawczyk-normalizer/v1"


def canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def _load_frozen_link() -> Any:
    if hashlib.sha256(FROZEN_LINK.read_bytes()).hexdigest() != FROZEN_LINK_SHA256:
        raise ValueError("frozen localized-link hash mismatch")
    name = "ledger_d0_frozen_localized_link"
    spec = importlib.util.spec_from_file_location(name, FROZEN_LINK)
    if spec is None or spec.loader is None:
        raise ValueError("frozen localized-link is not importable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _q(value: object, label: str) -> sp.Rational:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError(f"{label} is not an exact rational")
    parsed = Fraction(value)
    return sp.Rational(parsed.numerator, parsed.denominator)


Interval = tuple[sp.Rational, sp.Rational]


def _interval(value: object, label: str) -> Interval:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f"{label} is not a two-endpoint interval")
    lo, hi = _q(value[0], f"{label}.lo"), _q(value[1], f"{label}.hi")
    if lo > hi:
        raise ValueError(f"{label} is reversed")
    return lo, hi


def _add(left: Interval, right: Interval) -> Interval:
    return left[0] + right[0], left[1] + right[1]


def _mul(left: Interval, right: Interval) -> Interval:
    products = [a * b for a in left for b in right]
    return min(products), max(products)


def _pow(value: Interval, exponent: int) -> Interval:
    if exponent < 0:
        raise ValueError("negative powers are unsupported")
    if exponent == 0:
        return sp.Rational(1), sp.Rational(1)
    if exponent % 2 == 1:
        return value[0] ** exponent, value[1] ** exponent
    candidates = [value[0] ** exponent, value[1] ** exponent]
    if value[0] <= 0 <= value[1]:
        candidates.append(sp.Rational(0))
    return min(candidates), max(candidates)


def _eval_interval(expression: sp.Expr, boxes: Mapping[sp.Symbol, Interval]) -> Interval:
    if expression.is_Rational:
        value = sp.Rational(expression)
        return value, value
    if expression.is_Symbol and expression in boxes:
        return boxes[expression]
    if expression.is_Add:
        result = (sp.Rational(0), sp.Rational(0))
        for item in expression.args:
            result = _add(result, _eval_interval(item, boxes))
        return result
    if expression.is_Mul:
        result = (sp.Rational(1), sp.Rational(1))
        for item in expression.args:
            result = _mul(result, _eval_interval(item, boxes))
        return result
    if expression.is_Pow and expression.exp.is_Integer:
        return _pow(_eval_interval(expression.base, boxes), int(expression.exp))
    raise ValueError(f"unsupported exact interval expression: {expression}")


def _proves_relation(interval: Interval, relation: str) -> bool:
    lo, hi = interval
    if relation == "gt":
        return lo > 0
    if relation == "lt":
        return hi < 0
    if relation == "ne":
        return hi < 0 or lo > 0
    if relation == "ge":
        return lo >= 0
    if relation == "le":
        return hi <= 0
    if relation == "eq":
        return lo == hi == 0
    raise ValueError(f"unsupported relation {relation!r}")


def _legacy_digest(item: object) -> str:
    if not isinstance(item, dict):
        raise ValueError("legacy obligation is not an object")
    return canonical_sha256(item)


def _covered(item: Mapping[str, Any]) -> list[str]:
    values = item.get("covers_legacy_sha256")
    if not isinstance(values, list) or not values or any(
        not isinstance(value, str) or len(value) != 64 for value in values
    ):
        raise ValueError("typed obligation has no exact legacy binding")
    return list(values)


def _discharge_guard(
    item: Mapping[str, Any], symbols: Mapping[str, sp.Symbol], boxes: Mapping[sp.Symbol, Interval]
) -> dict[str, Any]:
    expression = sp.sympify(item.get("expression"), locals=symbols)
    if not expression.free_symbols <= set(boxes):
        raise ValueError("guard uses a variable outside the certified root box")
    enclosure = _eval_interval(expression, boxes)
    relation = item.get("relation")
    if not isinstance(relation, str) or not _proves_relation(enclosure, relation):
        raise ValueError("strict canonical guard is not proved on the entire root box")
    return {"kind": "canonical-guard", "interval": [str(enclosure[0]), str(enclosure[1])]}


def _discharge_selector(
    item: Mapping[str, Any], symbols: Mapping[str, sp.Symbol], boxes: Mapping[sp.Symbol, Interval]
) -> dict[str, Any]:
    branch = sp.sympify(item.get("branch_expression"), locals=symbols)
    separation = sp.sympify(item.get("separation_expression"), locals=symbols)
    if not (branch.free_symbols | separation.free_symbols) <= set(boxes):
        raise ValueError("selector uses a variable outside the certified root box")
    branch_interval = _eval_interval(branch, boxes)
    separation_interval = _eval_interval(separation, boxes)
    if not _proves_relation(branch_interval, str(item.get("branch_relation"))):
        raise ValueError("intersection branch selector is not proved")
    if not _proves_relation(separation_interval, "ne"):
        raise ValueError("intersection alternatives may be coincident")
    return {
        "kind": "intersection-selector",
        "branch_interval": list(map(str, branch_interval)),
        "separation_interval": list(map(str, separation_interval)),
    }


def _inside(value: sp.Rational, bound: Mapping[str, Any]) -> bool:
    lo = _q(bound.get("lower"), "parameter lower")
    hi = _q(bound.get("upper"), "parameter upper")
    if lo > hi:
        raise ValueError("parameter bounds are reversed")
    lower_ok = value >= lo if bound.get("lower_closed") is True else value > lo
    upper_ok = value <= hi if bound.get("upper_closed") is True else value < hi
    return lower_ok and upper_ok


def _discharge_periodic(
    item: Mapping[str, Any], symbols: Mapping[str, sp.Symbol], boxes: Mapping[sp.Symbol, Interval]
) -> dict[str, Any]:
    cosine = symbols.get(str(item.get("cosine_variable")))
    sine = symbols.get(str(item.get("sine_variable")))
    if cosine not in boxes or sine not in boxes:
        raise ValueError("periodic reconstruction variables are not certified")
    turn = _q(item.get("principal_turn"), "principal turn")
    frequency = _q(item.get("frequency"), "frequency")
    offset = _q(item.get("offset"), "offset")
    sheet = item.get("selected_sheet")
    if frequency == 0 or not isinstance(sheet, int) or isinstance(sheet, bool):
        raise ValueError("periodic affine sheet is malformed")
    exact_cos = sp.simplify(sp.cos(2 * sp.pi * turn))
    exact_sin = sp.simplify(sp.sin(2 * sp.pi * turn))
    if not exact_cos.is_Rational or not exact_sin.is_Rational:
        raise ValueError("D0 only discharges exact rational unit-circle turns")
    parameter = sp.cancel((turn + sheet - offset) / frequency)
    bound = item.get("parameter_bound")
    if not isinstance(bound, dict) or not _inside(parameter, bound):
        raise ValueError("selected periodic sheet violates its source bound")

    lo = _q(bound.get("lower"), "parameter lower")
    hi = _q(bound.get("upper"), "parameter upper")
    scaled = [frequency * lo + offset - turn, frequency * hi + offset - turn]
    scan_lo = int(sp.floor(min(scaled))) - 2
    scan_hi = int(sp.ceiling(max(scaled))) + 2
    admissible = [
        k
        for k in range(scan_lo, scan_hi + 1)
        if _inside(sp.cancel((turn + k - offset) / frequency), bound)
    ]
    if admissible != [sheet]:
        raise ValueError("periodic source bound does not select one exact sheet")
    if not (boxes[cosine][0] <= exact_cos <= boxes[cosine][1]):
        raise ValueError("reconstructed cosine is outside the certified box")
    if not (boxes[sine][0] <= exact_sin <= boxes[sine][1]):
        raise ValueError("reconstructed sine is outside the certified box")
    if sp.simplify(exact_cos**2 + exact_sin**2 - 1) != 0:
        raise ValueError("periodic reconstruction is not on the unit circle")
    for guard in item.get("parameter_guards", []):
        if not isinstance(guard, dict):
            raise ValueError("parameter guard is not typed")
        rhs = _q(guard.get("rhs"), "parameter guard rhs")
        if not _proves_relation((parameter - rhs, parameter - rhs), str(guard.get("relation"))):
            raise ValueError("reconstructed parameter violates a source guard")
    return {
        "kind": "periodic-sheet-reconstruction",
        "parameter": str(parameter),
        "sheet": sheet,
        "cosine": str(exact_cos),
        "sine": str(exact_sin),
    }


def normalize_and_discharge(job: dict[str, Any], certificate: dict[str, Any]) -> dict[str, Any]:
    """Normalize one Krawczyk certificate after exact typed-ledger discharge."""

    try:
        if canonical_sha256({k: v for k, v in job.items() if k != "job_sha256"}) != job.get(
            "job_sha256"
        ):
            raise ValueError("job self-digest mismatch")
        if canonical_sha256(
            {k: v for k, v in certificate.items() if k != "artifact_sha256"}
        ) != certificate.get("artifact_sha256"):
            raise ValueError("Krawczyk certificate self-digest mismatch")
        if certificate.get("status") != "VERIFIED":
            raise ValueError("Krawczyk certificate is not VERIFIED")
        for key in ("job_sha256", "system_sha256", "source_sha256"):
            if certificate.get(key) != job.get(key):
                raise ValueError(f"Krawczyk certificate {key} binding mismatch")
        for key in (
            "regular_unique_root_verified",
            "all_compiled_equations_verified",
            "all_compiled_predicates_verified",
            "target_interval_exactly_derived_from_source_box",
        ):
            if certificate.get(key) is not True:
                raise ValueError(f"Krawczyk certificate lacks {key}")

        system = job.get("system")
        if not isinstance(system, dict):
            raise ValueError("job system is absent")
        names = system.get("variables")
        equations = system.get("source_equations")
        target = system.get("target_expression")
        if not isinstance(names, list) or not isinstance(equations, list) or not isinstance(target, str):
            raise ValueError("job system is malformed")
        statement = {
            "variables": names,
            "source_equations": equations,
            "target_expression": target,
        }
        if canonical_sha256(statement) != job.get("system_sha256"):
            raise ValueError("job system digest mismatch")
        symbols = {name: sp.Symbol(name, real=True) for name in names}
        raw_box = certificate.get("certified_box")
        if not isinstance(raw_box, list) or len(raw_box) != len(names):
            raise ValueError("certified root box is absent")
        boxes = {
            symbols[name]: _interval(interval, f"box[{name}]")
            for name, interval in zip(names, raw_box, strict=True)
        }

        legacy = system.get("replay_obligations")
        typed = system.get("typed_replay_obligations")
        if not isinstance(legacy, list) or not isinstance(typed, list):
            raise ValueError("replay ledgers are absent")
        expected = [_legacy_digest(item) for item in legacy]
        observed: list[str] = []
        proofs = []
        for item in typed:
            if not isinstance(item, dict):
                raise ValueError("typed obligation is not an object")
            observed.extend(_covered(item))
            kind = item.get("kind")
            if kind == "canonical-guard":
                proofs.append(_discharge_guard(item, symbols, boxes))
            elif kind == "intersection-selector":
                proofs.append(_discharge_selector(item, symbols, boxes))
            elif kind == "periodic-sheet-reconstruction":
                proofs.append(_discharge_periodic(item, symbols, boxes))
            else:
                raise ValueError(f"unsupported typed obligation {kind!r}")
        if sorted(observed) != sorted(expected) or len(observed) != len(set(observed)):
            raise ValueError("typed ledger is not the strict complement of the legacy ledger")

        target_interval = _interval(certificate.get("certified_target_interval"), "target interval")
        body: dict[str, Any] = {
            "schema_version": SCHEMA,
            "status": "VERIFIED",
            "system_sha256": job["system_sha256"],
            "source_sha256": job["source_sha256"],
            "source_root_exists": True,
            "source_root_unique_in_box": True,
            "all_source_equations_verified": True,
            "all_source_predicates_verified": True,
            "target_interval_exactly_derived_from_source_box": True,
            "certified_target_interval": list(map(str, target_interval)),
            "typed_replay_ledger_sha256": canonical_sha256(typed),
            "legacy_replay_ledger_sha256": canonical_sha256(legacy),
            "typed_obligation_proofs": proofs,
            "upstream_krawczyk_certificate_sha256": certificate["artifact_sha256"],
            "canonical_source_replay_required": True,
            "authority": False,
            "target_release": False,
            "truth_used": False,
            "coverage": "UNKNOWN",
        }
        body["artifact_sha256"] = canonical_sha256(body)
        return body
    except (ValueError, TypeError, KeyError, sp.SympifyError) as error:
        body = {
            "schema_version": SCHEMA,
            "status": "NOT_CERTIFIED",
            "reason": f"{type(error).__name__}:{error}",
            "canonical_source_replay_required": True,
            "authority": False,
            "target_release": False,
            "truth_used": False,
            "coverage": "UNKNOWN",
        }
        body["artifact_sha256"] = canonical_sha256(body)
        return body


def prove_proposal(
    *,
    job: dict[str, Any],
    certificate: dict[str, Any],
    coefficients_high_to_low: Sequence[int],
    descriptor_selection_interval: Sequence[str | int],
) -> dict[str, Any]:
    normalized = normalize_and_discharge(job, certificate)
    if normalized.get("status") != "VERIFIED":
        return normalized
    system = job["system"]
    link = _load_frozen_link()
    result = link.prove_with_verified_source_certificate(
        variables=system["variables"],
        source_equations=system["source_equations"],
        target_expression=system["target_expression"],
        coefficients_high_to_low=coefficients_high_to_low,
        descriptor_selection_interval=descriptor_selection_interval,
        source_certificate=normalized,
    )
    # Even a proved link is only a proposal until untouched canonical replay.
    result["canonical_source_replay_required"] = True
    result["authority"] = False
    result["target_release"] = False
    return result


__all__ = ["canonical_sha256", "normalize_and_discharge", "prove_proposal"]
