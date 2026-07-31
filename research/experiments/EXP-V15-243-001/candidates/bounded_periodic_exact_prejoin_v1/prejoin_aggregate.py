#!/usr/bin/env python3.12
"""Truth-blind aggregate: endpoint -> ordinary proposal -> exact NRA prejoin.

The root benchmark owner supplies anonymous paired roots.  Individual source,
endpoint, descriptor, witness, and failure records are never emitted.  msolve
is measured as source-cover readiness; the stricter ``fully_bound`` count is
reserved for an ordinary descriptor that passes the existing NRA witness and
untouched-source replay from Repair A.
"""

from __future__ import annotations

import argparse
from collections import Counter
from fractions import Fraction
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import tempfile
from typing import Mapping


ARMS = ("control", "candidate")
ROW_KEYS = frozenset(("pair", "arm", "source", "source_sha256", "artifact_root"))
FORBIDDEN_KEYS = frozenset(
    ("id", "case_id", "problem_id", "family", "truth", "score", "outcome", "result", "known_count")
)
EXPECTED_HELPER_SHA256 = {
    "ordinary_proposal_binding.py": "e60b3ce96b619a1b6b6b183d7390c51fb6349972f4b9167f8b1b20f468039640",
    "applicability.py": "8b3ae91409f56f9ba08597bd022fba0497c1e63341fcc5a04bd0e44c46c95b26",
    "candidate.py": "7b98bdfb018d566994291ad75cb2e7f28f62adc960a784ca54d3b68b796586ff",
    "run_degree1_proposal_census.py": "4028b556d53be1ce7adc3cc899347998d12ac490eea8dfc947187a9f8984f4aa",
}
EXPECTED_MSOLVE_SHA256 = "24d6cee020256043f6ad4657ffa84a8b4e9188ab9ff18bf3e9339672a3229349"
EXPECTED_BOUNDARY_SHA256 = "a36520a416d0b8c900bca6b79192c7014812c9b1270be09248347f0f19e167e9"
EXPECTED_NRA_APPROVED_ROOTS = {
    "APPROVED_SOURCE_ROOT": Path(
        "/home/kabatan/work/solver-experiment-results/partial-ideal-root-readiness-v1/degree1-inputs"
    ).resolve(),
    "APPROVED_PANEL_ROOT": Path(
        "/home/kabatan/work/solver-experiment-results/target-constrained-nra-ordinary-binding-v1"
    ).resolve(),
    "APPROVED_PROPOSAL_ROOT": Path(
        "/home/kabatan/work/solver-experiment-results/target-constrained-nra-ordinary-binding-v1/ordinary-proposals"
    ).resolve(),
    "APPROVED_ORIGINAL_RESULT_ROOT": Path(
        "/home/kabatan/work/solver-experiment-results/formal-control-development145-180-seed0/artifacts"
    ).resolve(),
}


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _load(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def _require_sha(path: Path, expected: str) -> None:
    if not path.is_file() or _sha256(path.read_bytes()) != expected:
        raise SystemExit(f"pinned helper changed: {path.name}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--nra-root", type=Path, required=True)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-cpu", type=int, default=14)
    parser.add_argument("--nra-timeout-seconds", type=float, default=2.0)
    return parser


def _read_mapping(path: Path) -> Mapping[str, object] | None:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, Mapping) else None


def _authority_artifacts(root: Path):
    root = root.resolve()
    if not root.is_dir():
        return
    for path in sorted(root.rglob("authority.json")):
        if path.is_symlink():
            continue
        try:
            path.resolve().relative_to(root)
        except ValueError:
            continue
        value = _read_mapping(path)
        if value is not None:
            yield value


def _ordinary_attempts(result: Mapping[str, object]):
    for key in ("ordinary_hp_proposal", "ordinary_hp_attempt"):
        value = result.get(key)
        if isinstance(value, Mapping):
            yield value


def _nra_proof_ready(document, descriptor, binding, *, timeout_seconds: float) -> bool:
    identity = binding.BOUNDARY.descriptor_identity(descriptor)
    parsed = binding.BOUNDARY.exact_descriptor(descriptor)
    if identity is None or parsed is None or len(identity[0]) != 2:
        return False
    isolator = parsed.get("isolating_interval")
    if not isinstance(isolator, Mapping):
        return False
    try:
        lower = Fraction(str(isolator.get("left")))
        upper = Fraction(str(isolator.get("right")))
    except (ValueError, ZeroDivisionError):
        return False
    if lower >= upper:
        return False
    proposal = binding.backend.TargetProposal(identity[0], identity[1], lower, upper)
    try:
        source, metadata = binding.applicability._legacy_target_link_source(
            document, include_private_bridge_ledger=True
        )
        witness = binding.backend.prove(source, proposal, timeout_seconds=timeout_seconds)
        if witness.get("authority_pass") is not True:
            return False
        replay = binding._replay_existing_witness(
            document,
            source,
            witness,
            metadata.get("private_bridge_ledger"),
        )
        return bool(
            replay.get("untouched_source_replay_pass") is True
            and replay.get("untouched_target_link_pass") is True
        )
    except Exception:
        return False


def _atomic_write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("ascii") + b"\n"
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
        handle.write(payload)
        temporary = Path(handle.name)
    os.replace(temporary, path)


def main() -> int:
    arguments = _parser().parse_args()
    if os.sched_getaffinity(0) != {arguments.expected_cpu}:
        raise SystemExit("prejoin probe must be pinned to the expected CPU")
    if not math.isfinite(arguments.nra_timeout_seconds) or arguments.nra_timeout_seconds <= 0:
        raise SystemExit("NRA timeout must be finite and positive")

    payload = arguments.manifest.read_bytes()
    if _sha256(payload) != arguments.manifest_sha256.lower():
        raise SystemExit("manifest SHA-256 mismatch")
    rows = json.loads(payload)
    if not isinstance(rows, list) or not rows:
        raise SystemExit("manifest must be a nonempty list")
    if any(not isinstance(row, Mapping) or set(row) != ROW_KEYS for row in rows):
        raise SystemExit("manifest row schema mismatch")
    pairs = Counter((row["pair"], row["arm"]) for row in rows)
    if any(count != 1 for count in pairs.values()):
        raise SystemExit("duplicate pair/arm")
    pair_ids = {row["pair"] for row in rows}
    if any({arm for pair, arm in pairs if pair == item} != set(ARMS) for item in pair_ids):
        raise SystemExit("every anonymous pair needs control and candidate")

    nra_root = arguments.nra_root.resolve()
    runtime_root = arguments.runtime_root.resolve()
    for name, expected in EXPECTED_HELPER_SHA256.items():
        _require_sha(nra_root / name, expected)
    msolve_path = (
        runtime_root
        / "research/experiments/EXP-REAL61-004/msolve_all_real_proposal/source_compile.py"
    )
    boundary_path = (
        runtime_root
        / "research/experiments/EXP-V15-243-001/candidates/exact_outer_decorator/authority_boundary.py"
    )
    _require_sha(msolve_path, EXPECTED_MSOLVE_SHA256)
    _require_sha(boundary_path, EXPECTED_BOUNDARY_SHA256)
    if str(nra_root) not in sys.path:
        sys.path.insert(0, str(nra_root))
    binding = _load("geotarget_prejoin_existing_nra_binding", nra_root / "ordinary_proposal_binding.py")
    if any(
        Path(getattr(binding, name)).resolve() != expected
        for name, expected in EXPECTED_NRA_APPROVED_ROOTS.items()
    ):
        raise SystemExit("pinned NRA custody roots changed")
    msolve = _load("geotarget_prejoin_existing_msolve_source_compile", msolve_path)
    boundary = _load("geotarget_prejoin_authority_boundary", boundary_path)

    per_pair: dict[tuple[object, str], dict[str, object]] = {}
    totals = {arm: Counter() for arm in ARMS}
    for row in rows:
        arm = str(row["arm"])
        if arm not in ARMS or not isinstance(row["pair"], int):
            raise SystemExit("anonymous pair or arm malformed")
        source = Path(str(row["source"])).resolve()
        artifact_root = Path(str(row["artifact_root"])).resolve()
        source_payload = source.read_bytes()
        if _sha256(source_payload) != row["source_sha256"]:
            raise SystemExit("source digest mismatch")
        document = json.loads(source_payload)
        if not isinstance(document, Mapping) or FORBIDDEN_KEYS & set(document):
            raise SystemExit("source crossed identity/truth boundary")

        msolve_cover, _input = msolve.compile_source_document(
            dict(document), source_bytes=source_payload
        )
        if msolve_cover.get("status") == "ELIGIBLE_MSOLVE_DIMENSION_PROBE":
            totals[arm]["msolve_source_cover_ready"] += 1

        exact_identities: set[object] = set()
        ordinary_bound: set[object] = set()
        nra_ready: set[object] = set()
        malformed = 0
        source_binding_rejected = 0
        artifact_count = 0
        for result in _authority_artifacts(artifact_root):
            artifact_count += 1
            if result.get("source_sha256") != row["source_sha256"]:
                source_binding_rejected += 1
                continue
            if result.get("authority_pass") is True:
                identity = boundary.descriptor_identity(result.get("descriptor"))
                if result.get("status") == "TARGET_AUTHORITY_READY" and identity is not None:
                    exact_identities.add(identity)
                else:
                    malformed += 1
            for ordinary in _ordinary_attempts(result):
                endpoint_sha = ordinary.get("endpoint_float64_sha256")
                if (
                    ordinary.get("status") != "TARGET_AUTHORITY_READY"
                    or ordinary.get("authority_pass") is not True
                    or not isinstance(endpoint_sha, str)
                    or result.get("endpoint_float64_sha256") != endpoint_sha
                ):
                    continue
                descriptor = boundary.exact_descriptor(ordinary.get("descriptor"))
                identity = boundary.descriptor_identity(ordinary.get("descriptor"))
                if descriptor is None or identity is None:
                    malformed += 1
                    continue
                ordinary_bound.add(identity)
                if _nra_proof_ready(
                    dict(document), descriptor, binding,
                    timeout_seconds=arguments.nra_timeout_seconds,
                ):
                    nra_ready.add(identity)

        totals[arm]["authority_artifact_count"] += artifact_count
        totals[arm]["exact_authority_target_count"] += len(exact_identities)
        totals[arm]["ordinary_fully_bound_target_count"] += len(ordinary_bound)
        totals[arm]["nra_proof_ready_target_count"] += len(nra_ready)
        totals[arm]["malformed_authority_count"] += malformed
        totals[arm]["result_source_binding_rejected_count"] += source_binding_rejected
        per_pair[(row["pair"], arm)] = {
            "exact": exact_identities,
            "nra": nra_ready,
        }

    exact_loss = 0
    exact_gain = 0
    fully_bound_gain = 0
    for pair in pair_ids:
        control = per_pair[(pair, "control")]
        candidate = per_pair[(pair, "candidate")]
        exact_loss += len(control["exact"] - candidate["exact"])
        exact_gain += len(candidate["exact"] - control["exact"])
        fully_bound_gain += len(candidate["nra"] - control["nra"])

    aggregate = {
        "schema_version": "geotarget.bounded-periodic-exact-prejoin-aggregate/v1",
        "anonymous_pair_count": len(pair_ids),
        "manifest_sha256": arguments.manifest_sha256.lower(),
        "arms": {arm: dict(sorted(totals[arm].items())) for arm in ARMS},
        "candidate_additional_exact_authority_target_count": exact_gain,
        "candidate_control_exact_authority_loss_count": exact_loss,
        "candidate_additional_fully_bound_nra_proof_ready_target_count": fully_bound_gain,
        "false_authority_proxy_malformed_count": (
            totals["candidate"]["malformed_authority_count"]
            + totals["candidate"]["result_source_binding_rejected_count"]
        ),
        "gate": {
            "additional_fully_bound_proof_ready_target_gte_1": fully_bound_gain >= 1,
            "false_authority_proxy_zero": (
                totals["candidate"]["malformed_authority_count"] == 0
                and totals["candidate"]["result_source_binding_rejected_count"] == 0
            ),
            "control_authority_loss_zero": exact_loss == 0,
        },
        "individual_records_emitted": False,
        "paths_descriptors_targets_witnesses_emitted": False,
        "authority_pass": False,
        "target_release": False,
        "target_set_completeness_claim": False,
        "truth_used": False,
        "case_family_target_count_outcome_routing": False,
    }
    _atomic_write(arguments.output, aggregate)
    print(json.dumps(aggregate, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
