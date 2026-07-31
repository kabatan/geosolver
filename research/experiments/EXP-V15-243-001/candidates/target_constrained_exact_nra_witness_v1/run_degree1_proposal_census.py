#!/usr/bin/env python3
"""Aggregate-only degree-one adapter for the existing exact NRA candidate.

This file adds no compiler or solver.  It converts a root-owned primitive
degree-one projection into ``TargetProposal``, calls the existing
``candidate.prove`` backend on the existing digest-pinned primitive cover, and
uses the existing exact source runtime for a fresh untouched replay.  Because
the input is not the complete ordinary proposal, every external result is
HOLD even when the three internal checks pass.
"""

from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import importlib.util
import itertools
import json
import math
import os
from pathlib import Path
import re
import sys
from typing import Mapping

import sympy as sp

import applicability
import candidate as backend


RUNTIME_ROOT = Path(
    os.environ.get(
        "GEOTARGET_EXPERIMENT_RUNTIME",
        "/home/kabatan/work/solver-experiment-runtime/solver",
    )
).resolve()
RUR_ADAPTER_PATH = (
    RUNTIME_ROOT
    / "research/experiments/EXP-REAL61-002/rur_semantic_replay/adapter.py"
)
RUR_ADAPTER_SHA256 = "7bd09aaab95f90802e83ae09704975e776c6774a2eb9ea785c0a65b474593bc2"
EXACT_RUNTIME_PATH = (
    RUNTIME_ROOT / "research/experiments/EXP-REAL61-002/exact_replay/exact_runtime.py"
)
EXACT_RUNTIME_SHA256 = "f57e6fdd730d75e2c6b73d497a5041afd6c714d6c644c8e558cf3ef281c52242"


def _load(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


if (
    hashlib.sha256(RUR_ADAPTER_PATH.read_bytes()).hexdigest() != RUR_ADAPTER_SHA256
    or hashlib.sha256(EXACT_RUNTIME_PATH.read_bytes()).hexdigest()
    != EXACT_RUNTIME_SHA256
):
    raise RuntimeError("frozen RUR semantic replay closure changed")
RUR = _load("geotarget_nra_degree1_rur_semantic_replay", RUR_ADAPTER_PATH)


_AFFINE_PERIODIC = re.compile(
    r"\s*\(atan2\((?P<y>[^,]+),(?P<x>[^)]+)\) \+ 2\*pi\*k - "
    r"\((?P<offset>.+)\)\)/\((?P<coefficient>.+)\); choose k by source bounds/guards\s*"
)
_RADIAN_MOD = re.compile(r"\s*atan2\((?P<y>[^,]+),(?P<x>[^)]+)\) mod 2\*pi\s*")
_TURN_MOD = re.compile(
    r"\s*atan2\((?P<y>[^,]+),(?P<x>[^)]+)\)/\(2\*pi\) mod 1\s*"
)


REQUEST_KEYS = frozenset(
    {"source_path", "endpoint", "candidate_relation_high_to_low"}
)
FORBIDDEN_KEYS = frozenset(
    {
        "id",
        "family",
        "truth",
        "answer",
        "target",
        "outcome",
        "result",
        "score",
        "known_count",
    }
)
STRATA = (
    "direct-polynomial",
    "periodic-ledger",
    "algebraic-cover-reconstruction",
    "selector-or-branch-ledger",
)
FAILURE_CLASSES = (
    "POST_PROCESS_OUTSIDE_RAW_TARGET_THEOREM",
    "DEGREE_ONE_PROJECTION_REJECTED",
    "EXISTING_PRIMITIVE_COVER_REJECTED",
    "EXISTING_TARGET_GRAPH_REJECTED",
    "BACKEND_RESOURCE_OR_TIMEOUT",
    "BACKEND_UNSAT_OR_NO_WITNESS",
    "BACKEND_OUTSIDE_COMPLETE_SUBSET",
    "UNTOUCHED_SOURCE_REPLAY_REJECTED",
    "UNTOUCHED_TARGET_LINK_REJECTED",
    "OTHER_FAIL_CLOSED",
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requests", type=Path, required=True)
    parser.add_argument("--requests-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-cpu", type=int, default=14)
    parser.add_argument("--backend-timeout-seconds", type=float, default=3.0)
    return parser


def _proposal(coefficients: object) -> backend.TargetProposal:
    if (
        not isinstance(coefficients, list)
        or len(coefficients) != 2
        or any(not isinstance(item, int) or isinstance(item, bool) for item in coefficients)
    ):
        raise backend.NotProved("DEGREE_ONE_PROJECTION_REJECTED")
    leading, constant = coefficients
    common = math.gcd(abs(leading), abs(constant))
    if leading <= 0 or common != 1:
        raise backend.NotProved("DEGREE_ONE_PROJECTION_REJECTED")
    root = Fraction(-constant, leading)
    # A degree-one primitive polynomial has exactly this one real root.  The
    # fixed rational padding is an isolator construction, not target truth.
    return backend.TargetProposal(
        tuple(coefficients),
        0,
        root - 1,
        root + 1,
    )


def _validate_endpoint(value: object) -> None:
    if not isinstance(value, list) or not value:
        raise backend.NotProved("MALFORMED_ENDPOINT_LEDGER")
    converted = [float(item) for item in value]
    if any(not math.isfinite(item) for item in converted):
        raise backend.NotProved("MALFORMED_ENDPOINT_LEDGER")


def _failure_class(reason: object) -> str:
    text = str(reason)
    if "POST_PROCESS" in text:
        return "POST_PROCESS_OUTSIDE_RAW_TARGET_THEOREM"
    if "DEGREE_ONE_PROJECTION" in text or "PROPOSAL_" in text or "ISOLATOR" in text:
        return "DEGREE_ONE_PROJECTION_REJECTED"
    if "LEGACY_PRIMITIVE_COVER" in text:
        return "EXISTING_PRIMITIVE_COVER_REJECTED"
    if "LEGACY_TARGET_GRAPH" in text:
        return "EXISTING_TARGET_GRAPH_REJECTED"
    if "TIMEOUT" in text or "RESOURCE_" in text:
        return "BACKEND_RESOURCE_OR_TIMEOUT"
    if "UNSAT" in text or "NO_WITNESS" in text:
        return "BACKEND_UNSAT_OR_NO_WITNESS"
    if "POSITIVE_DIMENSIONAL" in text or "COMPLETE_SOLUTION" in text:
        return "BACKEND_OUTSIDE_COMPLETE_SUBSET"
    if "SOURCE_REPLAY" in text:
        return "UNTOUCHED_SOURCE_REPLAY_REJECTED"
    if "TARGET_LINK" in text:
        return "UNTOUCHED_TARGET_LINK_REJECTED"
    return "OTHER_FAIL_CLOSED"


def _validate_bridge_ledger(
    document: Mapping[str, object],
    source: backend.PolynomialSource,
    bridge: object,
) -> Mapping[str, object]:
    if not isinstance(bridge, Mapping):
        raise backend.NotProved("SOURCE_REPLAY_BRIDGE_LEDGER_MISSING")
    expected = bridge.get("bridge_ledger_sha256")
    unsigned = dict(bridge)
    unsigned.pop("bridge_ledger_sha256", None)
    if not isinstance(expected, str) or backend._canonical_sha256(unsigned) != expected:
        raise backend.NotProved("SOURCE_REPLAY_BRIDGE_LEDGER_DIGEST_MISMATCH")
    if bridge.get("source_document_sha256") != backend._canonical_sha256(document):
        raise backend.NotProved("SOURCE_REPLAY_BRIDGE_SOURCE_DIGEST_MISMATCH")
    if bridge.get("cover_variables") != list(source.variables):
        raise backend.NotProved("SOURCE_REPLAY_BRIDGE_VARIABLE_LEDGER_MISMATCH")
    if bridge.get("cover_target_variable") != str(source.raw_target):
        raise backend.NotProved("SOURCE_REPLAY_BRIDGE_TARGET_LEDGER_MISMATCH")
    if not isinstance(bridge.get("reconstruction"), list) or not isinstance(
        bridge.get("replay_obligations"), list
    ):
        raise backend.NotProved("SOURCE_REPLAY_BRIDGE_RECONSTRUCTION_LEDGER_MALFORMED")
    replayed_source, replayed_metadata = applicability._legacy_target_link_source(
        document, include_private_bridge_ledger=True
    )
    replayed_bridge = replayed_metadata.get("private_bridge_ledger")
    source_statement = {
        "variables": list(source.variables),
        "equations": [str(item) for item in source.equations],
        "guard": str(source.guard),
        "raw_target": str(source.raw_target),
        "definedness": [str(item) for item in source.definedness],
    }
    replayed_source_statement = {
        "variables": list(replayed_source.variables),
        "equations": [str(item) for item in replayed_source.equations],
        "guard": str(replayed_source.guard),
        "raw_target": str(replayed_source.raw_target),
        "definedness": [str(item) for item in replayed_source.definedness],
    }
    if source_statement != replayed_source_statement or bridge != replayed_bridge:
        raise backend.NotProved("SOURCE_REPLAY_BRIDGE_EXACT_RECOMPILE_MISMATCH")
    return bridge


def _common_embedding(values: list[sp.Expr]):
    nonrational = [sp.sympify(value) for value in values if value.is_Rational is not True]
    symbol = sp.Symbol("__nra_bridge_theta")
    if not nonrational:
        return sp.Integer(0), sp.Poly(symbol, symbol, domain=sp.QQ), (sp.Integer(0), sp.Integer(0))
    primitive = sp.to_number_field(nonrational)
    theta = primitive.as_expr()
    descriptor = backend._descriptor(theta)
    if descriptor.get("kind") == "Rational":
        return theta, sp.Poly(symbol, symbol, domain=sp.QQ), (theta, theta)
    coefficients = descriptor["minimal_polynomial_high_to_low"]
    polynomial = sp.Poly.from_list(coefficients, gens=symbol, domain=sp.ZZ)
    interval = descriptor["isolating_interval"]
    lower = sp.Rational(*interval["lower"])
    upper = sp.Rational(*interval["upper"])
    return theta, polynomial, (lower, upper)


def _coordinate_options(
    document: Mapping[str, object],
    bridge: Mapping[str, object],
    coordinate_map: Mapping[str, sp.Expr],
):
    raw_names = document.get("variables", {}).get("names")
    if not isinstance(raw_names, list) or not all(
        isinstance(name, str) and name for name in raw_names
    ):
        raise backend.NotProved("SOURCE_REPLAY_RAW_VARIABLE_LEDGER_MALFORMED")
    by_variable: dict[str, list[Mapping[str, object]]] = {}
    for item in bridge["reconstruction"]:
        if not isinstance(item, Mapping) or not isinstance(item.get("variable"), str):
            raise backend.NotProved("SOURCE_REPLAY_RECONSTRUCTION_ENTRY_MALFORMED")
        by_variable.setdefault(str(item["variable"]), []).append(item)

    option_sets = []
    periodic_used = False
    for name in raw_names:
        if name in coordinate_map:
            option_sets.append(
                [RUR._CoordinateOption(coordinate_map[name], {"kind": "DIRECT"})]
            )
            continue
        entries = by_variable.get(name, [])
        if len(entries) != 1:
            raise backend.NotProved("SOURCE_REPLAY_RECONSTRUCTION_ENTRY_COUNT")
        formula = str(entries[0].get("formula"))
        standard = RUR._ATAN2_RECONSTRUCTION.fullmatch(formula)
        affine = _AFFINE_PERIODIC.fullmatch(formula)
        radian = _RADIAN_MOD.fullmatch(formula)
        turn = _TURN_MOD.fullmatch(formula)
        match = standard or affine or radian or turn
        if match is None:
            raise backend.NotProved("SOURCE_REPLAY_RECONSTRUCTION_FORMULA_UNSUPPORTED")
        y_name, x_name = match.group("y").strip(), match.group("x").strip()
        if y_name not in coordinate_map or x_name not in coordinate_map:
            raise backend.NotProved("SOURCE_REPLAY_RECONSTRUCTION_COORDINATE_MISSING")
        angle = sp.atan2(coordinate_map[y_name], coordinate_map[x_name])
        if standard is not None:
            indices = RUR._period_indices_from_bounds(dict(document), name)
            values = [angle + 2 * sp.pi * index for index in indices]
        else:
            indices = range(-RUR.MAX_PERIOD_INDEX, RUR.MAX_PERIOD_INDEX + 1)
            if affine is not None:
                offset = sp.sympify(affine.group("offset"))
                coefficient = sp.sympify(affine.group("coefficient"))
                if coefficient == 0 or coefficient.free_symbols:
                    raise backend.NotProved("SOURCE_REPLAY_AFFINE_PHASE_MALFORMED")
                values = [
                    (angle + 2 * sp.pi * index - offset) / coefficient
                    for index in indices
                ]
            elif turn is not None:
                values = [angle / (2 * sp.pi) + index for index in indices]
            else:
                values = [angle + 2 * sp.pi * index for index in indices]
        periodic_used = True
        option_sets.append(
            [
                RUR._CoordinateOption(value, {"kind": "PERIODIC_RECONSTRUCTION"})
                for value in values
            ]
        )
    combination_count = math.prod(len(options) for options in option_sets)
    if combination_count > RUR.MAX_RECONSTRUCTION_COMBINATIONS:
        raise backend.NotProved("SOURCE_REPLAY_RECONSTRUCTION_COMBINATION_CAP")
    return raw_names, option_sets, periodic_used


def _replay_existing_witness(
    document: Mapping[str, object],
    source: backend.PolynomialSource,
    witness: Mapping[str, object],
    bridge: object,
) -> dict[str, bool]:
    bridge = _validate_bridge_ledger(document, source, bridge)
    descriptors = witness.get("model_descriptors")
    if not isinstance(descriptors, Mapping):
        raise backend.NotProved("SOURCE_REPLAY_MODEL_LEDGER_MISSING")
    if any(name not in descriptors for name in source.variables):
        raise backend.NotProved("SOURCE_REPLAY_COVER_COORDINATE_MISSING")
    coordinate_map = {
        name: backend._from_descriptor(descriptors[name]) for name in source.variables
    }
    target_descriptor = descriptors.get("__nra_raw_target")
    if not isinstance(target_descriptor, Mapping):
        raise backend.NotProved("TARGET_LINK_MODEL_LEDGER_MISSING")
    backend_target = backend._from_descriptor(target_descriptor)
    cover_target = str(bridge["cover_target_variable"])
    if sp.simplify(coordinate_map[cover_target] - backend_target) != 0:
        raise backend.NotProved("TARGET_LINK_COVER_COORDINATE_MISMATCH")

    theta, polynomial, interval = _common_embedding(
        [*coordinate_map.values(), backend_target]
    )
    raw_names, option_sets, periodic_used = _coordinate_options(
        document, bridge, coordinate_map
    )
    accepted = 0
    with RUR._single_embedding_runtime(theta, polynomial, interval):
        for combination in itertools.product(*option_sets):
            coordinates = [option.value for option in combination]
            try:
                RUR.RUNTIME.replay_document(
                    dict(document), coordinates, backend_target
                )
            except Exception:
                continue
            accepted += 1
    if accepted != 1:
        raise backend.NotProved(
            "SOURCE_REPLAY_NO_UNIQUE_RECONSTRUCTION"
            if accepted == 0
            else "SOURCE_REPLAY_AMBIGUOUS_RECONSTRUCTION"
        )
    replay_kinds = {
        str(item.get("kind"))
        for item in bridge["replay_obligations"]
        if isinstance(item, Mapping)
    }
    return {
        "qqbar_embedding_ready": True,
        "periodic_reconstruction_used": periodic_used,
        "selector_or_branch_ledger_bound": bool(
            replay_kinds
            - {
                "canonical-guard",
                "raw-source-target-link",
                "trig-parameter-reconstruction",
                "periodic-parameter-bound",
            }
        ),
        "untouched_source_replay_pass": True,
        "untouched_target_link_pass": True,
    }


def _assess_request(
    request: Mapping[str, object], *, timeout_seconds: float
) -> dict[str, object]:
    """Return a private fixed-category row; never a witness or target value."""

    private = {
        "descriptor_accepted": False,
        "primitive_cover_ready": False,
        "backend_attempted": False,
        "backend_witness_ready": False,
        "qqbar_embedding_ready": False,
        "periodic_reconstruction_used": False,
        "selector_or_branch_ledger_bound": False,
        "untouched_source_replay_pass": False,
        "untouched_target_link_pass": False,
        "thin_join_ready": False,
        "stratum": "none",
        "failure_class": "OTHER_FAIL_CLOSED",
        "internal_candidate_authority_observed": False,
    }
    try:
        _validate_endpoint(request["endpoint"])
        proposal = _proposal(request["candidate_relation_high_to_low"])
        private["descriptor_accepted"] = True
        source_path = Path(str(request["source_path"]))
        document = json.loads(source_path.read_bytes())
        if not isinstance(document, Mapping):
            raise backend.NotProved("LEGACY_PRIMITIVE_COVER_SOURCE_NOT_MAPPING")
        if document.get("post_process") not in (None, ""):
            raise backend.NotProved("POST_PROCESS_OUTSIDE_RAW_TARGET_THEOREM")

        source, metadata = applicability._legacy_target_link_source(
            document, include_private_bridge_ledger=True
        )
        stratum = str(metadata.get("structural_stratum"))
        if stratum not in STRATA:
            raise backend.NotProved("LEGACY_PRIMITIVE_COVER_UNKNOWN_STRATUM")
        private["stratum"] = stratum
        private["primitive_cover_ready"] = True
        private["backend_attempted"] = True
        witness = backend.prove(
            source,
            proposal,
            timeout_seconds=timeout_seconds,
        )
        if witness.get("authority_pass") is not True:
            raise backend.NotProved(str(witness.get("reason", "BACKEND_NO_WITNESS")))
        private["internal_candidate_authority_observed"] = True
        private["backend_witness_ready"] = True

        replay = _replay_existing_witness(
            document,
            source,
            witness,
            metadata.get("private_bridge_ledger"),
        )
        private.update(replay)
        private["thin_join_ready"] = True
        private["failure_class"] = "NONE"
        return private
    except Exception as error:
        private["failure_class"] = _failure_class(error)
        return private


def main() -> int:
    arguments = _parser().parse_args()
    if os.sched_getaffinity(0) != {arguments.expected_cpu}:
        raise SystemExit("degree-one NRA census must be pinned to the expected CPU")
    if not math.isfinite(arguments.backend_timeout_seconds) or arguments.backend_timeout_seconds <= 0:
        raise SystemExit("backend timeout must be finite and positive")
    payload = arguments.requests.read_bytes()
    observed_sha256 = hashlib.sha256(payload).hexdigest()
    if observed_sha256 != arguments.requests_sha256.lower():
        raise SystemExit("requests SHA-256 mismatch")
    requests = json.loads(payload)
    if not isinstance(requests, list):
        raise SystemExit("requests must be an array")

    counts = {
        "descriptor_accepted": 0,
        "descriptor_rejected": 0,
        "primitive_cover_ready": 0,
        "backend_attempted": 0,
        "backend_witness_ready": 0,
        "qqbar_embedding_ready": 0,
        "periodic_reconstruction_used": 0,
        "selector_or_branch_ledger_bound": 0,
        "untouched_source_replay_pass": 0,
        "untouched_target_link_pass": 0,
        "thin_join_ready": 0,
        "internal_candidate_authority_observed": 0,
    }
    failures = {key: 0 for key in FAILURE_CLASSES}
    cover_strata = {key: 0 for key in STRATA}
    join_strata = {key: 0 for key in STRATA}

    for request in requests:
        if not isinstance(request, Mapping) or FORBIDDEN_KEYS & set(request):
            raise SystemExit("request crossed the identity/truth boundary")
        if set(request) != REQUEST_KEYS:
            raise SystemExit("request has unexpected keys")
        row = _assess_request(
            request,
            timeout_seconds=arguments.backend_timeout_seconds,
        )
        if row["descriptor_accepted"]:
            counts["descriptor_accepted"] += 1
        else:
            counts["descriptor_rejected"] += 1
        for key in (
            "primitive_cover_ready",
            "backend_attempted",
            "backend_witness_ready",
            "qqbar_embedding_ready",
            "periodic_reconstruction_used",
            "selector_or_branch_ledger_bound",
            "untouched_source_replay_pass",
            "untouched_target_link_pass",
            "thin_join_ready",
            "internal_candidate_authority_observed",
        ):
            if row[key]:
                counts[key] += 1
        stratum = str(row["stratum"])
        if row["primitive_cover_ready"] and stratum in cover_strata:
            cover_strata[stratum] += 1
        if row["thin_join_ready"] and stratum in join_strata:
            join_strata[stratum] += 1
        failure = str(row["failure_class"])
        if failure != "NONE":
            if failure not in failures:
                failure = "OTHER_FAIL_CLOSED"
            failures[failure] += 1

    aggregate = {
        "schema_version": "geotarget.target-constrained-nra-degree1-census/v1",
        "requests_sha256": observed_sha256,
        "request_count": len(requests),
        **counts,
        "failure_taxonomy": failures,
        "primitive_cover_fixed_strata": cover_strata,
        "thin_join_fixed_strata": join_strata,
        "individual_records_emitted": False,
        "raw_failure_reasons_emitted": False,
        "witnesses_or_targets_emitted": False,
        "endpoint_used_for_routing_or_backend": False,
        "ordinary_full_proposal_binding": False,
        "degree_one_projection_only": True,
        "authority_pass": False,
        "target_release": False,
        "common_worker_integration": "HOLD",
        "truth_used": False,
        "formal_scorer_used": False,
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(aggregate, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(aggregate, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
