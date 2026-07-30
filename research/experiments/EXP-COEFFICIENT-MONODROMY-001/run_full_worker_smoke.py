"""Three source-only connection smokes; no scorer or corpus outcome is read."""

from __future__ import annotations

import hashlib
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import full_worker

FROZEN_ROOT = Path("/home/kabatan/work/solver-experiment-runtime/solver")


@dataclass(frozen=True)
class FakeCandidate:
    endpoint: tuple[float, ...]
    endpoint_sha256: str


class FakeClock:
    def __init__(self, now: float):
        self.now = now

    def __call__(self) -> float:
        return self.now


def _endpoint_sha(point: Sequence[float]) -> str:
    payload = json.dumps(tuple(point), separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _candidate(point: Sequence[float]) -> FakeCandidate:
    endpoint = tuple(float(value) for value in point)
    return FakeCandidate(endpoint, _endpoint_sha(endpoint))


def _descriptor(point: Sequence[float]) -> dict[str, object]:
    value = float(point[0])
    return {
        "key": f"R:{value:+.8f}",
        "minimal_polynomial_high_to_low": [1, -value],
        "selected_real_root_index": 0,
    }


class FakeBase:
    SCHEMA = "generated-fake-final-schema/v1"
    FINALIZE_RESERVE_SECONDS = 3.0
    MIN_HP_ATTEMPT_SECONDS = 0.01

    def __init__(self):
        self.calls: list[dict[str, object]] = []
        self._plan = lambda **kwargs: {"source": str(kwargs["source"])}
        self._service_candidates = self.service
        self._descriptor_key = lambda descriptor: str(descriptor["key"])
        self._fresh_replay_candidates = self.fresh
        self._source_contract = self.source_contract

    def service(
        self,
        *,
        source: Path,
        source_sha256: str,
        candidates: Sequence[FakeCandidate],
        cpu: int,
        output: Path,
        hard_deadline: float,
    ):
        del source, source_sha256, cpu
        self.calls.append(
            {
                "output": str(output),
                "hard_deadline": hard_deadline,
                "candidate_count": len(candidates),
            }
        )
        attempts = []
        descriptors = {}
        for row in candidates:
            descriptor = _descriptor(row.endpoint)
            attempts.append(
                {
                    "authority_pass": True,
                    "endpoint_float64_sha256": row.endpoint_sha256,
                    "descriptor": descriptor,
                }
            )
            descriptors[str(descriptor["key"])] = descriptor
        return attempts, descriptors, {"fake_existing_canonical_service": True}

    @staticmethod
    def fresh(
        _document: Mapping[str, object],
        endpoints: Sequence[Sequence[float]],
        *,
        hard_deadline: float,
    ) -> tuple[FakeCandidate, ...]:
        del hard_deadline
        return tuple(_candidate(point) for point in endpoints)

    @staticmethod
    def source_contract(source: Path, source_sha256: str):
        payload = source.read_bytes()
        if hashlib.sha256(payload).hexdigest() != source_sha256:
            raise ValueError("source SHA mismatch")
        return payload, json.loads(payload)


def _document(expression: str) -> dict[str, object]:
    return {
        "id": "generated-source-only",
        "task": "solve",
        "variables": {"names": ["x"]},
        "construction": [],
        "constraints": [{"def": expression, "value": 0}],
        "guards": [],
        "answer": "x",
        "post_process": "",
    }


def _run_one(
    temporary: Path,
    *,
    label: str,
    expression: str,
    clock_now: float,
    hard_deadline: float,
) -> dict[str, object]:
    source = temporary / f"{label}.json"
    payload = json.dumps(
        _document(expression), sort_keys=True, separators=(",", ":")
    ).encode()
    source.write_bytes(payload)
    base = FakeBase()
    binding = full_worker.install(
        base,
        frozen_root=FROZEN_ROOT,
        clock=FakeClock(clock_now),
    )
    start = _candidate((2.0,))
    attempts, descriptors, statistics = base._service_candidates(
        source=source,
        source_sha256=hashlib.sha256(payload).hexdigest(),
        candidates=(start,),
        cpu=31,
        output=temporary / f"{label}-output",
        hard_deadline=hard_deadline,
    )
    plan = base._plan(source=source)
    keys = tuple(descriptors)
    return {
        "label": label,
        "descriptor_keys": keys,
        "baseline_first": bool(keys and keys[0] == "R:+2.00000000"),
        "side_descriptor_count": statistics[
            "coefficient_monodromy_side_descriptor_count"
        ],
        "route_reason": statistics["coefficient_monodromy_route_reason"],
        "attempt_count": len(attempts),
        "baseline_deadline": statistics["coefficient_monodromy_baseline_deadline"],
        "plan_binding": plan["coefficient_monodromy_full_worker"] is True,
        "binding_authority_unchanged": binding["canonical_authority_unchanged"],
    }


def run(temporary: Path) -> dict[str, object]:
    temporary.mkdir(parents=True, exist_ok=True)
    execute = _run_one(
        temporary,
        label="execute",
        expression="x**2 - 4",
        clock_now=0.0,
        hard_deadline=100.0,
    )
    deadline = _run_one(
        temporary,
        label="deadline",
        expression="x**2 - 4",
        clock_now=98.0,
        hard_deadline=100.0,
    )
    opaque = _run_one(
        temporary,
        label="opaque-fallback",
        expression="sin(x)",
        clock_now=0.0,
        hard_deadline=100.0,
    )
    passed = all(
        (
            execute["baseline_first"],
            execute["side_descriptor_count"] >= 1,
            execute["plan_binding"],
            execute["binding_authority_unchanged"],
            deadline["baseline_first"],
            deadline["side_descriptor_count"] == 0,
            deadline["baseline_deadline"] == 100.0,
            opaque["baseline_first"],
            opaque["side_descriptor_count"] == 0,
            str(opaque["route_reason"]).startswith("SOURCE_COMPILE_REJECTED")
            or opaque["route_reason"] == "NOT_REDUCED_UNIVARIATE",
        )
    )
    return {
        "schema": "geotarget.exp-coefficient-monodromy-full-worker-smoke/v1",
        "formal_run": False,
        "truth_scorer_case_outcome_or_holdout_read": False,
        "cases": [execute, deadline, opaque],
        "gate": {"passed": passed, "case_count": 3},
    }


def main() -> None:
    import tempfile

    with tempfile.TemporaryDirectory(prefix="coefficient-full-worker-") as raw:
        result = run(Path(raw))
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if result["gate"]["passed"] else 1)


if __name__ == "__main__":
    main()
