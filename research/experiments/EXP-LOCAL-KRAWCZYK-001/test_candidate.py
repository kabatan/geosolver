from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import candidate
import run_generated_d0


def test_work_split_is_fixed_at_seventy_five_percent() -> None:
    assert candidate.split_work(16) == (12, 4)
    assert candidate.split_work(13) == (10, 3)


def test_generated_gate() -> None:
    result = run_generated_d0.run()
    assert result["gate"]["passed"] is True
    assert result["aggregate"]["descriptor_losses"] == 0
    assert result["aggregate"]["false_or_extra"] == 0


def test_canonical_exception_fails_closed_and_keeps_baseline_bytes() -> None:
    x = candidate.Var(0)

    def broken(_point, _box):
        raise RuntimeError("authority unavailable")

    payload = b"opaque\x00baseline"
    result = candidate.rescue(
        candidate.TypedLocalSource((x - 1.0,), 1),
        near_roots=(candidate.NearRoot((1.0,), 0.05),),
        baseline_payload=payload,
        baseline_descriptors=("baseline",),
        total_work=16,
        canonical_accept=broken,
    )
    assert result.baseline_payload == payload
    assert result.descriptors == ("baseline",)
    assert result.certified_boxes == 1
    assert result.canonical_rejections == 1


def test_candidate_imports_hash_pinned_existing_dag() -> None:
    assert (
        candidate.INTERVAL_SHA256
        == "b2a17ddc6321c3157f89965a8c76fd18f376c8974c3d4288bf430ff70bc6e2a3"
    )
    assert candidate.INTERVAL_PATH.name == "interval_rescue.py"
