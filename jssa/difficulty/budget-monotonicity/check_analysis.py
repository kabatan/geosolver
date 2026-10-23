"""Small truth-table checks for the registered metrics; no solver invocation."""
from __future__ import annotations

import itertools

import analyze_stage2 as analysis
import execute_stage2 as execution


def main():
    checks = []
    for triple in itertools.product((0, 1), repeat=3):
        pattern = "".join(map(str, triple))
        actual = analysis.metric_flags(list(triple) * 3)
        expected = {
            "N": int(pattern in {"100", "101", "010", "110"}),
            "R": int(pattern in {"100", "101", "010", "110"}),
            "R3": int(pattern in {"100", "101", "010", "110"}),
            "V": int(pattern in {"101", "010"}),
        }
        assert actual == expected, (pattern, actual, expected)
        checks.append("all_three_seeds_" + pattern)
    # Two seeds can regress on different pairs without satisfying registered R.
    assert analysis.metric_flags([1, 0, 0, 0, 1, 0, 0, 1, 1])["R"] == 0
    checks.append("R_requires_the_same_budget_pair")
    flags = analysis.metric_flags([1, 0, 0, 1, 0, 1, 1, 1, 0])
    assert (flags["R"], flags["R3"]) == (1, 0)
    checks.append("R_and_R3_are_distinct")
    assert analysis.bounds([None] * 9) == {m: [0, 1] for m in ("N", "R", "R3", "V")}
    assert analysis.bounds([1, None, 0, 1, 1, 1, 1, 1, 1])["N"] == [1, 1]
    assert analysis.bounds([1, 0, None, 1, 0, None, None, None, None])["R"] == [1, 1]
    assert analysis.bounds([0] * 6 + [None] * 3)["R"] == [0, 0]
    checks.extend(["all_missing_bounds", "known_loss_despite_missing_middle", "known_R_despite_other_missing", "one_unknown_seed_cannot_create_R"])
    assert analysis.range_grade([0, 8], [1, 8]) == "判定不能"
    assert analysis.range_grade([0, 0], [1, 8]) == "不成立"
    assert analysis.range_grade([1, 8], [1, 8]) == "成立"
    checks.append("forecast_ranges_respect_missing_bounds")
    for counts, verdict in (((0, 0, 0, 0), "判定対象なし"), ((3, 0, 0, 1), "成立"),
                            ((1, 0, 0, 1), "不成立"), ((10, 0, 0, 2), "不成立")):
        strata = {group: {"N": [n, n]} for group, n in zip("ABCD", counts, strict=True)}
        assert analysis.concentration_grade(strata)["verdict"] == verdict
        checks.append("P3_" + "_".join(map(str, counts)))
    execution.save(execution.BASE / "analysis-checks.json", {
        "checked_utc": execution.now(), "solver_runs": 0,
        "analysis_sha256": execution.sha(analysis.__file__),
        "checks_sha256": execution.sha(__file__), "passed": checks,
    })
    print(f"{len(checks)} metric and missing-data checks passed; solver runs: 0.")


if __name__ == "__main__":
    main()
