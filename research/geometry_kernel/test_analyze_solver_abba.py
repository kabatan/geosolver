from __future__ import annotations

from research.geometry_kernel.analyze_solver_abba import analyze_abba_legs


def _row(
    descriptor: str,
    wall: float,
    *,
    cpu: float | None = None,
    accepted: bool = True,
    status: str = "EXACT_SET_EQUAL",
    extra: int = 0,
) -> dict[str, object]:
    return {
        "descriptors": frozenset({descriptor}),
        "wall_seconds": wall,
        "cpu_seconds": wall if cpu is None else cpu,
        "peak_rss_bytes": 100,
        "accepted": accepted,
        "status": status,
        "extra_identity_count": extra,
        "returned_descriptor_error": None,
        "truth_descriptor_error": None,
    }


def _leg(seed: int, code: str, wall: float, descriptor: str = "d") -> dict[str, object]:
    return {
        "seed": seed,
        "code": code,
        "rows": {
            "FAMILY(A)": _row(descriptor, wall),
            "OTHER(B)": _row(descriptor, wall),
        },
    }


def test_abba_accepts_union_preservation_and_clustered_speedup() -> None:
    legs = []
    for seed in range(5):
        legs.extend(
            [
                _leg(seed, "a1", 100.0),
                _leg(seed, "b1", 80.0),
                _leg(seed, "b2", 80.0),
                _leg(seed, "a2", 100.0),
            ]
        )

    report = analyze_abba_legs(legs, bootstrap_resamples=200, seed=3)

    assert report["correctness_gate_passed"] is True
    assert report["performance_gate_passed_before_jobs7"] is True
    assert report["lost_descriptor_count"] == 0
    assert report["wall_family_clustered_bootstrap"]["upper_95"] < 1.0


def test_abba_union_allows_replica_variation_but_rejects_loss_and_truth_extra() -> None:
    legs = [
        {"seed": 0, "code": "a1", "rows": {"F(A)": _row("one", 10.0)}},
        {"seed": 0, "code": "b1", "rows": {"F(A)": _row("two", 8.0, extra=1)}},
        {"seed": 0, "code": "b2", "rows": {"F(A)": _row("two", 8.0)}},
        {"seed": 0, "code": "a2", "rows": {"F(A)": _row("one", 10.0)}},
    ]

    report = analyze_abba_legs(legs, bootstrap_resamples=20)

    assert report["correctness_gate_passed"] is False
    assert report["lost_descriptor_count"] == 1
    assert report["truth_outside_descriptor_run_count"] == 1


def test_abba_requires_complete_four_leg_seed() -> None:
    legs = [_leg(0, "a1", 1.0), _leg(0, "b1", 1.0)]

    try:
        analyze_abba_legs(legs)
    except ValueError as error:
        assert "exactly A1/B1/B2/A2" in str(error)
    else:
        raise AssertionError("incomplete ABBA seed was accepted")
