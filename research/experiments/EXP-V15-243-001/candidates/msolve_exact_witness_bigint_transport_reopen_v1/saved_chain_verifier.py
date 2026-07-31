"""Read-only D0 verifier for the already-saved msolve/RUR/QQBar chain."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import sympy as sp


RUNTIME = Path("/home/kabatan/work/solver-experiment-runtime/solver")
MSOLVE = RUNTIME / "research/experiments/EXP-REAL61-004/msolve_exact_witness"
REPLAY_PATH = Path(
    "/home/kabatan/work/solver-artifacts/EXP-V15-243-001/"
    "MSOLVE_EXACT_WITNESS_BIGINT_TRANSPORT_REOPEN_V1/FROZEN_SURPRISE_P9_REPLAY.json"
)
SELECTION_PATH = MSOLVE / "results/d0/SURPRISE_P9.selection.json"
FACTOR_PATH = MSOLVE / "results/d0/SURPRISE_P9.factor.json"
EXPECTED_SHA256 = {
    REPLAY_PATH: "f17cc8115026a03aeaa8c5d2b2c8de62a3994fb861c6917afbaef03a36cbb05d",
    SELECTION_PATH: "5f9d41f321c744ff362d4e2bff3a92d44c2e15f37703f6aae0aecf135f244e27",
    FACTOR_PATH: "308b7677e5199fa6c90d1b4fccd88441002deac1551363bad7ce459b7322790e",
}


class SavedChainRejected(ValueError):
    pass


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def load_frozen() -> tuple[Mapping[str, Any], bytes, Mapping[str, Any], bytes, Mapping[str, Any], bytes]:
    loaded = []
    for path, expected in EXPECTED_SHA256.items():
        payload = path.read_bytes()
        if _sha256(payload) != expected:
            raise SavedChainRejected("FROZEN_ARTIFACT_SHA256_MISMATCH")
        document = json.loads(payload)
        if not isinstance(document, Mapping):
            raise SavedChainRejected("FROZEN_ARTIFACT_NOT_MAPPING")
        loaded.extend((document, payload))
    return tuple(loaded)  # type: ignore[return-value]


def verify_saved_chain(
    replay: Mapping[str, Any],
    replay_bytes: bytes,
    selection: Mapping[str, Any],
    selection_bytes: bytes,
    factor: Mapping[str, Any],
    factor_bytes: bytes,
    *,
    require_frozen_replay_sha: bool = True,
) -> dict[str, Any]:
    bindings = replay.get("source_artifact_bindings")
    checks = replay.get("exact_checks")
    qqbar = replay.get("qqbar_replay")
    original = replay.get("original_dsl_replay")
    if not all(isinstance(item, Mapping) for item in (bindings, checks, qqbar, original)):
        raise SavedChainRejected("SAVED_CHAIN_LEDGER_MALFORMED")
    if not (
        (not require_frozen_replay_sha or _sha256(replay_bytes) == EXPECTED_SHA256[REPLAY_PATH])
        and bindings.get("numeric_box_selection_sha256") == _sha256(selection_bytes)
        and bindings.get("selected_factor_sha256") == _sha256(factor_bytes)
        and factor.get("selection_sha256") == _sha256(selection_bytes)
        and factor.get("msolve_output_sha256") == selection.get("msolve_output_sha256")
    ):
        raise SavedChainRejected("SAVED_CHAIN_ALL_BYTES_BINDING_MISMATCH")
    raw_factor = factor.get("selected_factor_coefficients_low_to_high")
    interval = factor.get("selected_interval")
    selection_interval = selection.get("theta_isolating_interval")
    if not (
        isinstance(raw_factor, list)
        and isinstance(interval, Mapping)
        and isinstance(selection_interval, Mapping)
        and factor.get("status")
        == "IRREDUCIBLE_FACTOR_SELECTED_BY_EXACT_THETA_INTERVAL"
        and factor.get("factorization_exact") is True
        and factor.get("factor_irreducible_over_Q") is True
        and factor.get("selected_factor_multiplicity_in_radical_eliminant") == 1
        and factor.get("selection_used_truth") is False
    ):
        raise SavedChainRejected("SAVED_FACTOR_LEDGER_REJECTED")
    theta = sp.Symbol("saved_theta")
    polynomial = sp.Poly.from_list(list(reversed(raw_factor)), gens=theta, domain=sp.ZZ)
    left = sp.Rational(str(interval["left"]))
    right = sp.Rational(str(interval["right"]))
    outer_left = sp.Rational(str(selection_interval["left"]))
    outer_right = sp.Rational(str(selection_interval["right"]))
    if not (
        outer_left <= left <= right <= outer_right
        and int(polynomial.count_roots(left, right)) == 1
        and polynomial.is_sqf is True
        and polynomial.is_irreducible is True
        and factor.get("selected_factor_degree") == polynomial.degree()
        and replay.get("selected_theta_degree") == polynomial.degree()
    ):
        raise SavedChainRejected("SAVED_FACTOR_ROOT_NOT_UNIQUE")
    expected_relations = (
        int(checks["source_relation_count"])
        + int(checks["rur_relation_count"])
        + int(checks["compiler_equation_count"])
    )
    expected_guards = int(checks["source_guard_count"]) + int(
        checks["compiler_predicate_count"]
    )
    if not (
        replay.get("status") == "EXACT_V2_WITNESS_REPLAY_VERIFIED"
        and replay.get("authority") is False
        and replay.get("truth_used") is False
        and replay.get("completeness_claim") == "NOT_MADE"
        and qqbar.get("status") == "EXACT_REPLAY_ACCEPTED"
        and qqbar.get("source_relation_count") == expected_relations
        and qqbar.get("source_guard_count") == expected_guards
        and qqbar.get("source_bound_count") == checks["source_bound_count"]
        and qqbar.get("source_raw_answer_exact") is True
        and qqbar.get("target_link_exact") is True
        and original.get("status") == "VERIFIED"
        and original.get("exact_replay_passed") is True
        and original.get("source_relations_exact") == checks["source_relation_count"]
        and original.get("source_guards_exact") == checks["source_guard_count"]
        and original.get("source_bounds_exact") == checks["source_bound_count"]
        and original.get("source_raw_answer_exact") is True
    ):
        raise SavedChainRejected("SAVED_QQBAR_SOURCE_BRANCH_TARGET_REPLAY_REJECTED")
    return {
        "saved_chain_pass": True,
        "selected_theta_degree": polynomial.degree(),
        "source_relation_count": checks["source_relation_count"],
        "source_guard_count": checks["source_guard_count"],
        "source_bound_count": checks["source_bound_count"],
        "compiler_predicate_count": checks["compiler_predicate_count"],
        "authority_pass": False,
        "target_release": False,
        "completeness_claim": "NOT_MADE",
    }


def canonical_mutation_bytes(value: object) -> bytes:
    """Canonical bytes used only to prove that an in-memory mutation is rejected."""

    return _canonical_bytes(value)
