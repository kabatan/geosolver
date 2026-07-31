#!/usr/bin/env python3.12
"""Aggregate-only source gate; exact QQBar execution is explicit and locked."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Mapping

import candidate
import exact_connector


APPROVED_REQUESTS = Path(
    "/home/kabatan/work/solver-experiment-results/partial-ideal-root-readiness-v1/degree1-requests.json"
).resolve()
APPROVED_SOURCE_ROOT = APPROVED_REQUESTS.parent / "degree1-inputs"
REQUESTS_SHA256 = "ee424315256582652ea0df72a05c21903a5fd4366867c6788129a79e4f80fd35"
REQUEST_PROVENANCE = APPROVED_REQUESTS.parent / "DEGREE1_REQUEST_AGGREGATE.json"
REQUEST_PROVENANCE_SHA256 = "c686498c6fec6b5a8f6d03eae68ef991ed1ea6998d3ea9479ba78d25f9ea74d3"
SOURCE_BYTES_AGGREGATE_SHA256 = "c035f6498a7b23acca5e45353a1566903e9e68967d2b82e5764061b3976532e3"
EXPECTED_CANDIDATE_SHA256 = "a5a113faf7bfa070e52edd21293ccf53bc05832a2c85cc74e787d60b109c5314"
EXPECTED_CONNECTOR_SHA256 = "c56319e0830737f03e912eb371b0b6ca4c65917fc04e20c9252bd063b55ef30e"
HERE = Path(__file__).resolve().parent
ROW_KEYS = frozenset(("candidate_relation_high_to_low", "endpoint", "source_path"))
FORBIDDEN_SOURCE_KEYS = frozenset(
    ("id", "case_id", "problem_id", "family", "truth", "outcome", "result", "score")
)


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _source_projection(document: Mapping[str, object]) -> dict[str, object]:
    return {
        key: document.get(key)
        for key in ("task", "variables", "construction", "constraints", "guards", "bounds")
    }


def _signature(envelope) -> str:
    symbols, polynomials = candidate.OLD._compiled_polynomials(envelope.source_projection)
    degree = max(int(item.total_degree()) for item in polynomials)
    terms = sum(len(item.terms()) for item in polynomials)
    band = "01-04" if terms <= 4 else "05-08" if terms <= 8 else "09-16" if terms <= 16 else "17+"
    return f"N{len(symbols)}-D{degree}-T{band}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requests", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--private-accepted", type=Path, required=True)
    parser.add_argument("--exact-timeout-seconds", type=float, default=20.0)
    parser.add_argument("--execute-exact", action="store_true")
    arguments = parser.parse_args()
    if arguments.output.exists() or arguments.private_accepted.exists():
        raise SystemExit("refusing existing real-gate output")
    if arguments.requests.resolve() != APPROVED_REQUESTS:
        raise SystemExit("unapproved request panel")
    if _sha(APPROVED_REQUESTS.read_bytes()) != REQUESTS_SHA256:
        raise SystemExit("request panel changed")
    if _sha(REQUEST_PROVENANCE.read_bytes()) != REQUEST_PROVENANCE_SHA256:
        raise SystemExit("request provenance changed")
    if _sha((HERE / "candidate.py").read_bytes()) != EXPECTED_CANDIDATE_SHA256:
        raise SystemExit("single-prime candidate changed")
    if _sha((HERE / "exact_connector.py").read_bytes()) != EXPECTED_CONNECTOR_SHA256:
        raise SystemExit("single-prime exact connector changed")

    rows = json.loads(APPROVED_REQUESTS.read_bytes())
    if (
        not isinstance(rows, list)
        or len(rows) != 85
        or any(not isinstance(row, Mapping) or set(row) != ROW_KEYS for row in rows)
    ):
        raise SystemExit("anonymous request schema changed")
    source_digests = []
    prepared = []
    for row in rows:
        raw_path = Path(str(row["source_path"])).absolute()
        if raw_path.is_symlink():
            raise SystemExit("source projection is a symlink")
        source = raw_path.resolve()
        if (
            source.parent != APPROVED_SOURCE_ROOT
            or source.suffix != ".json"
            or len(source.stem) != 4
            or not source.stem.isdigit()
        ):
            raise SystemExit("source escaped fixed anonymous projection root")
        payload = source.read_bytes()
        digest = _sha(payload)
        source_digests.append({"source_sha256": digest})
        document = json.loads(payload)
        if not isinstance(document, Mapping) or FORBIDDEN_SOURCE_KEYS & set(document):
            raise SystemExit("source crossed identity/truth/outcome boundary")
        prepared.append((row, source, digest, document))
    digest_payload = (
        json.dumps(source_digests, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("ascii")
    if _sha(digest_payload) != SOURCE_BYTES_AGGREGATE_SHA256:
        raise SystemExit("anonymous source-byte aggregate changed")

    counters = Counter()
    ready_sources = set()
    ready_signatures = set()
    private = []
    for row, source, source_sha, document in prepared:
        counters["source_count"] += 1
        try:
            envelope = candidate.canonical_proposal_envelope(_source_projection(document))
            signature = _signature(envelope)
            batch = candidate.propose(envelope)
        except Exception:
            counters["compile_inapplicable"] += 1
            continue
        counters["good_prime_source_count"] += int(batch.work.get("selected_prime_count", 0) > 0)
        counters["stable_tuple_source_count"] += int(batch.work.get("tuple_stability_pass_count", 0) > 0)
        counters["exact_substitution_source_count"] += int(
            batch.work.get("exact_substitution_pass_count", 0) > 0
        )
        counters["coordinate_proposal_count"] += len(batch.candidates)
        if not arguments.execute_exact:
            continue
        relation = row["candidate_relation_high_to_low"]
        if not isinstance(relation, list) or len(relation) != 2:
            counters["nonlinear_or_malformed_hp_relation"] += 1
            continue
        # The source-only Hensel candidate never receives relation, endpoint,
        # raw target, truth or outcome. The frozen ordinary-HP relation enters
        # only here as an untrusted target proposal for complete QQBar replay.
        for proposal in batch.candidates:
            counters["qqbar_attempt_count"] += 1
            terminal = exact_connector.replay_exact_with_linear_hp_relation(
                document,
                proposal,
                target_coefficients_high_to_low=relation,
                timeout_seconds=arguments.exact_timeout_seconds,
            )
            if not terminal.authority_pass:
                counters["qqbar_rejected_count"] += 1
                continue
            replay = terminal.replay
            valid = bool(
                isinstance(replay, Mapping)
                and replay.get("status") == "EXACT_REPLAY_ACCEPTED"
                and replay.get("truth_used") is False
                and replay.get("source_raw_answer_exact") is True
                and replay.get("target_link_exact") is True
                and terminal.coordinates_from_float64 is False
                and terminal.target_hp_lanes_are_proposal_only is True
            )
            if not valid:
                counters["invalid_authority_count"] += 1
                continue
            ready_sources.add(source_sha)
            ready_signatures.add(signature)
            counters["authority_ready_attempt_count"] += 1
            private.append({"source_sha256": source_sha, "signature": signature})

    gate = bool(
        arguments.execute_exact
        and len(ready_sources) >= 2
        and len(ready_signatures) >= 2
        and counters["invalid_authority_count"] == 0
    )
    private = sorted(
        {json.dumps(item, sort_keys=True, separators=(",", ":")) for item in private}
    )
    private_payload = ("[" + ",".join(private) + "]\n").encode("ascii")
    aggregate = {
        "schema_version": "geotarget.single-prime-stable-hensel-real-gate/v1",
        "request_count": len(rows),
        "requests_sha256": REQUESTS_SHA256,
        "request_provenance_sha256": REQUEST_PROVENANCE_SHA256,
        "source_bytes_aggregate_sha256": SOURCE_BYTES_AGGREGATE_SHA256,
        "good_prime_source_count": counters["good_prime_source_count"],
        "stable_tuple_source_count": counters["stable_tuple_source_count"],
        "exact_substitution_source_count": counters["exact_substitution_source_count"],
        "coordinate_proposal_count": counters["coordinate_proposal_count"],
        "authority_ready_source_count": len(ready_sources) if arguments.execute_exact else None,
        "authority_ready_signature_count": len(ready_signatures) if arguments.execute_exact else None,
        "invalid_authority_count": counters["invalid_authority_count"] if arguments.execute_exact else None,
        "gate_pass": gate if arguments.execute_exact else None,
        "status_histogram": dict(sorted(counters.items())),
        "private_accepted_sha256": _sha(private_payload),
        "case_level_output_emitted": False,
        "hensel_candidate_received_endpoint_relation_target_truth_outcome": False,
        "ordinary_hp_relation_used_only_as_untrusted_exact_replay_target_proposal": True,
        "qqbar_replay_is_sole_authority": True,
        "target_release": False,
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.private_accepted.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(aggregate, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8"
    )
    arguments.private_accepted.write_bytes(private_payload)
    print(json.dumps(aggregate, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
