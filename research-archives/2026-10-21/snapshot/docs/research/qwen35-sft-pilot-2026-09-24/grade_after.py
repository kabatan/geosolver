"""Manual, answer-level proof audit for the frozen six-update LoRA comparison."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = Path("qwen/.runtime/qwen35_sft_pilot_20260924/proof-baseline")
AFTER = Path("qwen/.runtime/qwen35_sft_pilot_20260924/proof-after-multiconfig-mapped")

DECISIONS = {
    "EV02-0": (False, "The decisive direction and perpendicularity are asserted without the needed calculation."),
    "EV02-1": (False, "The altitude/median construction is not carried through to a valid calculation of the target perpendicularity."),
    "DU01-0": (False, "Falsely calls AK an external angle bisector and gives incorrect U/V length and similarity claims; the required perpendicularity is unsupported."),
    "DU01-1": (True, "Corrects the coordinate signs, derives U and V and the UV slope, then uses the standard tangent-intersection/symmedian theorem to calculate AK's isogonal slope and obtain slope product -1."),
    "OB01-0": (True, "Subtracts the two explicit circle equations to derive the AX slope, which equals the AN median slope; an independent rational-coordinate witness also checks the relation."),
    "OB01-1": (False, "The key nine-point-circle and midline identity is invoked without derivation, so the proposed collinearity is not proved."),
    "AP01-0": (False, "Does not derive the decisive angle PFA=C, leaving the claimed cyclicity unsupported."),
    "AP01-1": (False, "Asserts the decisive angle AFP=C without proving it from the construction."),
    "N01-0": (False, "Claims angle BPC=A without deriving it; the needed configuration-specific algebra is missing."),
    "N01-1": (False, "Uses the false intermediate claim that H,L,M,P are cyclic, then asserts the target relation."),
    "N02-0": (True, "After explicitly rejecting wrong angle and vertex correspondences, the final four-step argument uses the interior arc choice, obtains both tangent-chord angle equalities, identifies triangle ABT similar to CAT, and derives AT^2=BT*CT."),
    "N02-1": (True, "Applies the tangent-chord theorem to AT on each circle, matches both corresponding angles of triangles ABT and CAT, and derives AT^2=BT*CT from their side ratio."),
}


def main():
    rows = []
    for id, (valid, reason) in DECISIONS.items():
        f = AFTER / (id + ".json")
        b = BASE / (id + ".json")
        d = json.loads(f.read_text())
        old = json.loads(b.read_text())
        config = id.split("-")[0]
        rows.append(dict(id=id, source=str(f), source_sha256=hashlib.sha256(f.read_bytes()).hexdigest(),
                         source_configuration=config, valid_proof=valid,
                         frozen_same_configuration=config in ("AP01", "N01", "N02"),
                         actual_train_configuration_overlap=config in ("AP01", "N01"),
                         unchanged_tokens=d["completion_ids"] == old["completion_ids"],
                         answer_tokens=len(d["completion_ids"]), finish_reason=d["finish_reason"], reason=reason))
    (HERE / "after-grades.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
    summary = dict(n=len(rows), valid=sum(x["valid_proof"] for x in rows),
                   frozen_same_configuration_valid=sum(x["valid_proof"] and x["frozen_same_configuration"] for x in rows),
                   frozen_transfer_valid=sum(x["valid_proof"] and not x["frozen_same_configuration"] for x in rows),
                   actual_train_configuration_overlap_valid=sum(x["valid_proof"] and x["actual_train_configuration_overlap"] for x in rows),
                   actual_untrained_configuration_valid=sum(x["valid_proof"] and not x["actual_train_configuration_overlap"] for x in rows),
                   unchanged_answers=sum(x["unchanged_tokens"] for x in rows),
                   by_configuration={config: sum(x["valid_proof"] for x in rows if x["source_configuration"] == config)
                                     for config in ("AP01", "DU01", "EV02", "N01", "N02", "OB01")})
    (HERE / "after-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
