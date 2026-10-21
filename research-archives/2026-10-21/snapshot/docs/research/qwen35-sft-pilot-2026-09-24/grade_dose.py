"""Manual answer-level audit of the mapped 30-update dose probe."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path("qwen/.runtime/qwen35_sft_pilot_20260924")
BASE = ROOT / "proof-baseline"
DOSE = ROOT / "proof-after-dose-mapped"

DECISIONS = {
    "EV02-0": (False, "Moves through circle and radical-axis ideas but never calculates the decisive T direction; simply asserts HT perpendicular AM."),
    "EV02-1": (False, "Ends after an elementary cyclic-angle observation; target perpendicularity is not established."),
    "DU01-0": (True, "Retracts a wrong intermediate sign, then computes U=(0,c/(2 sin A)), V=(b/2,-b cot A/2); the UV slope is -(b cos A+c)/(b sin A), the negative reciprocal of the standard AK symmedian slope."),
    "DU01-1": (False, "Uses a false radical-axis/line-of-centers claim and assumes K lies on unrelated axes, then cites the target as a conclusion."),
    "OB01-0": (True, "Uses inversion about A with squared radius AB*AF=AC*AE, mapping the tangent circles to lines; their intersection is a parallelogram vertex whose A-vector is twice AN."),
    "OB01-1": (True, "After correcting an earlier ratio comparison, inversion yields AX'=(k^2/(b cos A))u+(k^2/(c cos A))v, proportional to AN=(c/2)u+(b/2)v."),
    "AP01-0": (False, "Stops before calculating the relation for F or deriving A,N,F,P concyclic; also makes false collinearity claims."),
    "AP01-1": (False, "After many withdrawn conjectures, only restates the decisive cyclic-angle condition and asserts it follows from the construction without a derivation."),
    "N01-0": (True, "Despite extraneous wrong remarks about special cases, a complete coordinate derivation computes H and its projection P, derives the circle BCH, and substitutes P to obtain zero."),
    "N01-1": (True, "A complete coordinate calculation computes H, P and the circle BCH, then substitutes P and simplifies exactly to zero; unrelated preliminary attempts are retracted."),
    "N02-0": (True, "Uses both tangent-chord angle identities, establishes triangles ABT and CAT similar with the correct correspondence, and derives BT/AT=AT/CT; earlier tangents are rejected."),
    "N02-1": (False, "Asserts the false angles ATB=ATC=A (they are 180-A for the interior T), gives an inconsistent similarity correspondence and side ratios, and reaches the target only by invalid steps."),
}


def main():
    expected = [f"{c}-{i}" for c in ("EV02", "DU01", "OB01", "AP01", "N01", "N02") for i in range(2)]
    missing = sorted(set(expected) - set(DECISIONS))
    if missing:
        raise SystemExit(f"Manual decisions still needed: {missing}")
    rows = []
    for id in expected:
        valid, reason = DECISIONS[id]
        f = DOSE / f"{id}.json"
        b = BASE / f"{id}.json"
        raw = f.read_bytes()
        d = json.loads(raw)
        old = json.loads(b.read_bytes())
        config = id.split("-")[0]
        rows.append(dict(id=id, source=str(f), source_sha256=hashlib.sha256(raw).hexdigest(),
                         source_configuration=config, valid_proof=valid,
                         frozen_same_configuration=config in ("AP01", "N01", "N02"),
                         actual_train_configuration_overlap=config in ("AP01", "N01"),
                         unchanged_tokens=d["completion_ids"] == old["completion_ids"],
                         answer_tokens=len(d["completion_ids"]), finish_reason=d["finish_reason"], reason=reason))
    (HERE / "dose-grades.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
    summary = dict(n=len(rows), valid=sum(x["valid_proof"] for x in rows),
                   frozen_same_configuration_valid=sum(x["valid_proof"] and x["frozen_same_configuration"] for x in rows),
                   frozen_transfer_valid=sum(x["valid_proof"] and not x["frozen_same_configuration"] for x in rows),
                   actual_train_configuration_overlap_valid=sum(x["valid_proof"] and x["actual_train_configuration_overlap"] for x in rows),
                   actual_untrained_configuration_valid=sum(x["valid_proof"] and not x["actual_train_configuration_overlap"] for x in rows),
                   unchanged_answers=sum(x["unchanged_tokens"] for x in rows),
                   by_configuration={config: sum(x["valid_proof"] for x in rows if x["source_configuration"] == config)
                                     for config in ("AP01", "DU01", "EV02", "N01", "N02", "OB01")})
    (HERE / "dose-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
