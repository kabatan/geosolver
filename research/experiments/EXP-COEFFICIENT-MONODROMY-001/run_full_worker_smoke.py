"""Core-15 source-only Repair-A smokes; no scorer or outcome is read."""

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

import full_worker  # noqa: E402

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
        self.baseline_result = None
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
        result = (
            attempts,
            descriptors,
            {"fake_existing_canonical_service": True},
        )
        if self.baseline_result is None:
            self.baseline_result = result
        return result

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
    category: str,
    expression: str,
    accepted_start: float,
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
    start = _candidate((accepted_start,))
    observed = base._service_candidates(
        source=source,
        source_sha256=hashlib.sha256(payload).hexdigest(),
        candidates=(start,),
        cpu=31,
        output=temporary / f"{label}-output",
        hard_deadline=hard_deadline,
    )
    attempts, descriptors, statistics = observed
    plan = base._plan(source=source)
    keys = tuple(descriptors)
    baseline = base.baseline_result
    return {
        "label": label,
        "category": category,
        "descriptor_keys": keys,
        "baseline_first": bool(keys and keys[0] == f"R:{accepted_start:+.8f}"),
        "side_descriptor_count": statistics.get(
            "coefficient_monodromy_side_descriptor_count", 0
        ),
        "attempt_count": len(attempts),
        "baseline_call_hard_deadline": base.calls[0]["hard_deadline"],
        "baseline_result_identity": observed is baseline,
        "baseline_contained_identity": bool(
            baseline is not None
            and all(observed[index] is baseline[index] for index in range(3))
        ),
        "plan_binding": plan["coefficient_monodromy_full_worker"] is True,
        "plan_full_baseline": (
            plan["coefficient_monodromy_service_baseline_fraction"] == 1.0
            and plan["coefficient_monodromy_baseline_service_budget_reduced"] is False
            and plan["coefficient_monodromy_tail_only_after_baseline_return"] is True
        ),
        "binding_authority_unchanged": binding["canonical_authority_unchanged"],
    }


def run(temporary: Path) -> dict[str, object]:
    temporary.mkdir(parents=True, exist_ok=True)
    cases: list[dict[str, object]] = []
    for value in range(2, 7):
        cases.append(
            _run_one(
                temporary,
                label=f"execute-{value}",
                category="execute",
                expression=f"x**2 - {value * value}",
                accepted_start=float(value),
                clock_now=0.0,
                hard_deadline=100.0,
            )
        )
    for value in range(7, 12):
        cases.append(
            _run_one(
                temporary,
                label=f"zero-tail-{value}",
                category="zero-tail",
                expression=f"x**2 - {value * value}",
                accepted_start=float(value),
                clock_now=98.0,
                hard_deadline=100.0,
            )
        )
    opaque_expressions = (
        "sin(x)",
        "cos(x)",
        "exp(x) - 1",
        "log(x)",
        "Abs(x) - 2",
    )
    for ordinal, expression in enumerate(opaque_expressions):
        cases.append(
            _run_one(
                temporary,
                label=f"opaque-{ordinal}",
                category="opaque",
                expression=expression,
                accepted_start=2.0,
                clock_now=0.0,
                hard_deadline=100.0,
            )
        )

    execute = [row for row in cases if row["category"] == "execute"]
    zero_tail = [row for row in cases if row["category"] == "zero-tail"]
    opaque = [row for row in cases if row["category"] == "opaque"]
    common = all(
        row["baseline_first"]
        and row["baseline_call_hard_deadline"] == 100.0
        and row["plan_binding"]
        and row["plan_full_baseline"]
        and row["binding_authority_unchanged"]
        for row in cases
    )
    passed = bool(
        len(cases) == 15
        and len(execute) == len(zero_tail) == len(opaque) == 5
        and common
        and all(
            row["side_descriptor_count"] >= 1
            and row["baseline_result_identity"] is False
            for row in execute
        )
        and all(
            row["side_descriptor_count"] == 0
            and row["baseline_result_identity"] is True
            and row["baseline_contained_identity"] is True
            for row in zero_tail + opaque
        )
    )
    return {
        "schema": "geotarget.exp-coefficient-monodromy-repair-a-core15/v1",
        "formal_run": False,
        "truth_scorer_case_outcome_or_holdout_read": False,
        "aggregate": {
            "case_count": len(cases),
            "execute_count": len(execute),
            "execute_side_addition_count": sum(
                row["side_descriptor_count"] >= 1 for row in execute
            ),
            "zero_tail_identity_count": sum(
                row["baseline_result_identity"] is True for row in zero_tail
            ),
            "opaque_identity_count": sum(
                row["baseline_result_identity"] is True for row in opaque
            ),
            "full_baseline_deadline_count": sum(
                row["baseline_call_hard_deadline"] == 100.0 for row in cases
            ),
        },
        "gate": {"passed": passed, "case_count": len(cases)},
    }


def main() -> None:
    import tempfile

    with tempfile.TemporaryDirectory(prefix="coefficient-full-worker-") as raw:
        result = run(Path(raw))
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if result["gate"]["passed"] else 1)


if __name__ == "__main__":
    main()
