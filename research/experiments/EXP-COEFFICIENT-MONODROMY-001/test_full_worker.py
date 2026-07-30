from __future__ import annotations

import hashlib
import json
from pathlib import Path

import full_worker
from run_full_worker_smoke import FakeBase, FakeClock, _candidate, _document, run

HERE = Path(__file__).resolve().parent


def test_repair_a_core15_source_only_full_worker_smokes(tmp_path: Path) -> None:
    result = run(tmp_path)
    assert result["gate"]["passed"] is True
    assert result["truth_scorer_case_outcome_or_holdout_read"] is False
    assert result["aggregate"] == {
        "case_count": 15,
        "execute_count": 5,
        "execute_side_addition_count": 5,
        "zero_tail_identity_count": 5,
        "opaque_identity_count": 5,
        "full_baseline_deadline_count": 15,
    }


def test_arm_binds_runner_compatible_full_worker() -> None:
    arm = json.loads((HERE / "arm.json").read_text())
    assert arm["entrypoint"] == "full_worker.py"
    assert (
        hashlib.sha256((HERE / "full_worker.py").read_bytes()).hexdigest()
        == arm["mechanism_hash"]
    )


def test_current_adaptive_and_thin_dependencies_are_hash_bound() -> None:
    full_worker._verify_dependencies()
    assert full_worker.BASELINE_FLOOR == 0.75
    assert full_worker.BASELINE_SERVICE_FRACTION == 1.0
    assert full_worker.ADAPTIVE_ENTRYPOINT_SHA256 == (
        "7d6f168d8679732c672842e6b7a44573d190449ad0fbe4cc09a7b9112ddc9500"
    )


def test_side_exception_returns_exact_baseline_object(tmp_path: Path) -> None:
    class ExplodingThin:
        @staticmethod
        def connect(*_args, canonical_replay, **_kwargs):
            assert canonical_replay((-2.0,)) == "R:-2.00000000"
            raise RuntimeError("generated side failure")

    source = tmp_path / "side-exception.json"
    payload = json.dumps(
        _document("x**2 - 4"), sort_keys=True, separators=(",", ":")
    ).encode()
    source.write_bytes(payload)
    base = FakeBase()
    full_worker.install(
        base,
        frozen_root=Path("/home/kabatan/work/solver-experiment-runtime/solver"),
        clock=FakeClock(0.0),
        thin=ExplodingThin(),
    )
    observed = base._service_candidates(
        source=source,
        source_sha256=hashlib.sha256(payload).hexdigest(),
        candidates=(_candidate((2.0,)),),
        cpu=31,
        output=tmp_path / "output",
        hard_deadline=100.0,
    )
    assert observed is base.baseline_result
    assert all(observed[index] is base.baseline_result[index] for index in range(3))
