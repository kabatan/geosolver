#!/usr/bin/env python3
"""Build the source-audited raw geometric answer ledger.

The old ``published_answer`` column is deliberately retained as a contest
presentation reference.  ``exact_answer_set`` is a different field: it is the
exact value set of the expression in the DSL's ``answer`` field.  In
particular, an AIME ``p+q`` answer stores the underlying reduced fraction,
not ``p+q``.

The overrides below were checked against the complete statement in the DSL
and the exact algebraic form of the requested geometric quantity.  Cases for
which the current source record does not yet provide an independently
checked exact expression remain explicitly ``unresolved`` and are excluded
from strict accuracy rather than being guessed from a solver output.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


# Raw target expressions for cases whose contest statement asks for a
# presentation derived from the geometric quantity.  These are not contest
# answer integers.  Multi-valued entries intentionally preserve every exact
# branch allowed by the source constraints.
RAW_OVERRIDES: dict[str, list[str]] = {
    "AIME-2006-II-06": ["1/2 - sqrt(3)/6"],
    "AIME-2006-II-09": ["19 - 3*sqrt(5)"],
    "AIME-2006-II-12": ["429*sqrt(3)/433"],
    "AIME-2007-I-09": ["680/57"],
    "AIME-2007-I-12": ["50*CRootOf(x**4 + 48*x**3 - 262*x**2 + 48*x + 73, 3)"],
    # The statement says that both side lengths are possible; the requested
    # radicand is a contest presentation, not the DSL target.
    "AIME-2007-I-15": [
        "231/10 - 3*sqrt(989)/10",
        "231/10 + 3*sqrt(989)/10",
    ],
    "AIME-2007-II-15": ["260/129"],
    "AIME-2008-II-11": ["44 - 6*sqrt(35)"],
    "AIME-2009-I-12": ["8/3"],
    "AIME-2009-II-05": ["27/5"],
    "AIME-2009-II-10": ["60*sqrt(13)/23"],
    "AIME-2010-I-15": ["22/23"],
    "AIME-2010-II-09": ["4/7"],
    "AIME-2010-II-14": ["3 + 2*sqrt(2)"],
    "AIME-2010-II-15": ["725/507"],
    "AIME-2011-I-02": ["-12 + 3*sqrt(21)"],
    "AIME-2011-I-14": ["5 - 4*sqrt(2)"],
    "AIME-2011-II-04": ["31/20"],
    "AIME-2011-II-10": ["4050/7"],
    "AIME-2011-II-13": ["4*CRootOf(x**4 - 12*x**2 + 9, 3)"],
    "AIME-2012-I-12": ["4*sqrt(3)/11"],
    "AIME-2012-II-15": ["900/19"],
    "AIME-2013-I-09": ["39*sqrt(39)/35"],
    "AIME-2013-II-04": ["25*sqrt(3)/12"],
    "AIME-2013-II-05": ["3*sqrt(3)/14"],
    "AIME-2013-II-08": ["5 + sqrt(267)"],
    "AIME-2013-II-13": ["3*sqrt(7)"],
    "AIME-2013-II-15": ["37/24 - sqrt(35)/18"],
    "AIME-2014-II-08": ["-14 + 4*sqrt(15)"],
    "AIME-2014-II-11": ["7/22 - 3*sqrt(3)/22"],
    "AIME-2014-II-14": ["75/2"],
    "AIME-2015-II-07": ["36/125"],
    "AIME-2015-II-11": ["18/5"],
    "AIME-2015-II-15": ["64/65"],
    "AIME-2016-I-06": ["10/3"],
    "AIME-2016-II-10": ["35/8"],
    "AIME-2018-I-04": ["250/39"],
    "AIME-2018-II-14": ["168/59"],
    "AIME-2019-I-15": ["61/4"],
    "AIME-2019-II-01": ["54/5"],
    "AIME-2019-II-15": ["560*sqrt(14)"],
    "AIME-2020-I-01": ["540/7"],
    "AIME-2020-I-13": ["15*sqrt(7)/14"],
    "AIME-2020-I-15": ["5*CRootOf(16*x**4 - 328*x**2 + 945, 3)"],
    "AIME-2021-I-02": ["105/4"],
    "AIME-2022-I-08": ["3*sqrt(39) - 3*sqrt(3)"],
    "AIME-2022-I-11": ["147*sqrt(3)"],
    "AIME-2023-II-09": ["18*sqrt(15)"],
    "AIME-2023-II-12": ["99*sqrt(37)/74"],
    "AIME-2025-II-06": ["288/5"],
    "AIME-2025-II-12": ["(-1 + 9*sqrt(5))/4"],
    "AIME-2025-II-14": ["104*sqrt(3)"],
    "HMMT-2021-FEB-GEO-04": ["900/11"],
    "HMMT-2021-FEB-GEO-05": ["49/400"],
    "HMMT-2022-FEB-GEO-03": ["3/4"],
    "HMMT-2022-FEB-GEO-05": ["361/4"],
    "HMMT-2022-FEB-GEO-06": ["208*sqrt(17)/85"],
    # The source asks for the angle in degrees, so the DSL answer expression
    # explicitly projects its internal radian Angle to the requested degree
    # measure.  This is part of the DSL target, not post-processing.
    "JMO-2016-PRE-03": ["95"],
}


UNRESOLVED_RAW = {
    "AIME-2008-I-10",
    "AIME-2014-I-15",
    "AIME-2019-I-13",
    "AIME-2019-II-11",
    "AIME-2021-I-11",
    "AIME-2021-II-12",
    "AIME-2021-II-14",
    "HMMT-2021-FEB-GEO-09",
    "HMMT-2022-FEB-GEO-10",
}


def _parts(value: object) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    return [part.strip() for part in str(value).split(";") if part.strip()]


def main() -> None:
    audits: dict[str, dict] = {}
    for line in (ROOT / "manual_audit.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        keys = [row.get("problem_id"), row.get("dedupe_key")]
        if row.get("dsl_path"):
            keys.append(Path(row["dsl_path"]).stem)
        for key in keys:
            if key:
                audits[str(key)] = row

    out: list[dict] = []
    for path in sorted((ROOT / "dsl").glob("*.json")):
        case = json.loads(path.read_text(encoding="utf-8"))
        case_id = path.stem
        audit = audits.get(case_id, {})
        if case_id in RAW_OVERRIDES:
            exact = RAW_OVERRIDES[case_id]
            status = "verified"
            basis = "manual statement review; raw DSL quantity retained"
        elif case_id in UNRESOLVED_RAW:
            exact = []
            status = "unresolved"
            basis = "source statement read; raw exact value still needs an independent solution audit"
        elif str(case.get("solver_coverage", "")).startswith("reference_only"):
            exact = _parts(audit.get("published_answer"))
            status = "not_executable" if exact else "unresolved"
            basis = "reference-only source row; no solver score"
        elif audit.get("published_answer") not in (None, ""):
            # No presentation transform is present in these cases, so the
            # official answer ledger is already the raw quantity in `answer`.
            exact = _parts(audit["published_answer"])
            status = "verified"
            basis = "official answer ledger; DSL answer is the raw quantity"
        else:
            exact = []
            status = "unresolved"
            basis = "source statement read; no independent exact answer ledger"

        out.append(
            {
                "case_id": case_id,
                "dsl_path": str(path.relative_to(ROOT)),
                "source_statement_sha256": hashlib.sha256(case["source_statement"].encode("utf-8")).hexdigest(),
                "exact_answer_set": exact,
                "truth_status": status,
                "truth_basis": basis,
                "presentation_answer": audit.get("published_answer"),
            }
        )
    (ROOT / "exact_truth.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in out),
        encoding="utf-8",
    )
    print(json.dumps({
        "rows": len(out),
        "verified": sum(row["truth_status"] == "verified" for row in out),
        "unresolved": sum(row["truth_status"] == "unresolved" for row in out),
        "not_executable": sum(row["truth_status"] == "not_executable" for row in out),
        "override_rows": len(RAW_OVERRIDES),
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
