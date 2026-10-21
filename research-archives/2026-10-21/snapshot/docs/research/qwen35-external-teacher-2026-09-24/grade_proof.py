"""Frozen manual review of the twelve proof-development generations."""

import hashlib
import json
from pathlib import Path

ROOT = Path("qwen/.runtime/qwen35_external_teacher_20260924/eval-proof-all37-en-32k")
REASONS = {
    ("EV02", 0): "The displayed orthocenter formula is not an orthocenter formula, and the later reflection/linear-system argument has no derivation from the feet E,F.",
    ("EV02", 1): "With A=(0,a), B=(-b,0), C=(c,0), the stated H=(0,-bc/a) has the wrong altitude equations; E,F and the final algebra contain undefined symbols.",
    ("DU01", 0): "Claims the two defined circles are tangent at A to each other, although their respective tangent lines are AC and AB; subsequent center and midpoint formulas are unsupported.",
    ("DU01", 1): "The proposed circumcircle has nonzero constant p0, so it does not pass through A=(0,0); its tangent and center calculations cannot prove the claim.",
    ("OB01", 0): "The circle equations include non-circle terms and free parameters, and the alleged factorization/collinearity is not derived from the two specified circles.",
    ("OB01", 1): "Assumes AB and AC direction vectors are perpendicular unit vectors for a general acute triangle; the resulting coordinates and circles are invalid.",
    ("AP01", 0): "The proposed FA*FP=FN*FC is not a valid criterion for A,N,F,P cyclicity; subsequent variables and coordinate identities are unsupported.",
    ("AP01", 1): "Sets b dot c=0 and |b|=|c|=1 for a general scalene triangle, then asserts unverified formulas for F and a circle center.",
    ("N01", 0): "The orthocenter coordinates are false and the proof claims three vectors are linearly independent in the plane; no valid cyclicity derivation remains.",
    ("N01", 1): "Falsely places every acute triangle's orthocenter between A and M and derives P=M; the claimed product does not establish B,C,H,P cyclicity.",
    ("N02", 0): "Uses an undefined reflected-point power theorem and unsupported angular equations; it never derives the claimed metric relation from the circles.",
    ("N02", 1): "The proposed equations are not valid circle equations for the prescribed tangencies, and the derivation contains contradictory root/sign claims.",
}


def main():
    rows = []
    for (config, sample), reason in REASONS.items():
        path = ROOT / f"diverse-en-proof-{config}-{sample}.json"
        data = json.loads(path.read_text())
        assert data["source_id"] == config and data["sample"] == sample
        rows.append({"config": config, "sample": sample, "status": "invalid",
                     "valid_auxiliary_used": False, "reason": reason,
                     "finish": data["finish_reason"],
                     "tokens": len(data["completion_ids"]),
                     "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    (ROOT / "manual-grades.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
    print({"valid": 0, "total": len(rows),
           "truncated": sum(r["finish"] == "length" for r in rows)})


if __name__ == "__main__":
    main()
