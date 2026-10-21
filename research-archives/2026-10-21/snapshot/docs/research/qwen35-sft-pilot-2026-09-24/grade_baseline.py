"""Record manual proof audit and source hashes for the frozen 12-answer baseline."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path("qwen/.runtime/qwen35_sft_pilot_20260924/proof-baseline")

# The booleans below are manual judgments of the saved full answers, not LLM grading.
# A restated conclusion or an asserted intermediate equality is not a proof.
JUDGMENTS = {
    "EV02-0": (False, "HT⊥AM is concluded after an unproved claim about the direction of HT; the alleged angle relation for median and altitude is unsupported."),
    "EV02-1": (False, "Uses an incorrect H coordinate and merely says the required slope identity follows after computing T, without deriving T."),
    "DU01-0": (False, "UV·AK=0 is asserted as the omitted decisive algebraic step; the claimed angle-bisector reasoning does not establish it."),
    "DU01-1": (False, "Conflicting U coordinates and no completed calculation of UV·AK; the final assertion is unsupported."),
    "OB01-0": (False, "A,N,X collinearity is attributed to an unnamed similarity/radical-axis property; no core calculation or proof."),
    "OB01-1": (False, "Lists tangent-chord relations but does not derive the radical axis direction; explicitly prioritizes a theorem claim over contradictory calculation."),
    "AP01-0": (False, "The essential ∠PFN=A is asserted by an unexplained halving of ∠BFC; the decisive angle step is unsupported."),
    "AP01-1": (False, "Cites the very statement to be proved and never derives the needed cyclic angle equality."),
    "N01-0": (False, "Assumes triangle PMC similar to triangle AHM with no valid derivation, then assumes the target cyclic angle equality."),
    "N01-1": (False, "States ∠HPC=∠HBC, equivalent to the conclusion, without deriving it; acknowledges an earlier false angle identification."),
    "N02-0": (True, "Final proof correctly gets ∠CAT=∠ABT and ∠BAT=∠ACT by tangent-chord theorem, then triangle TAB similar to TCA and AT²=BT·CT. Earlier angle exploration is explicitly revised."),
    "N02-1": (True, "Final formal proof correctly applies tangent-chord theorem to both circles, gives the matching two angles and proportional sides, yielding AT²=BT·CT. Earlier confused notation is corrected."),
}

rows = []
for key, (valid, reason) in JUDGMENTS.items():
    path = ROOT / (key + ".json")
    raw = path.read_bytes()
    answer = json.loads(raw)
    assert answer["finish_reason"] == "stop"
    rows.append(dict(id=key, source=str(path), source_sha256=hashlib.sha256(raw).hexdigest(),
                     source_configuration=key.split("-")[0], valid_proof=valid,
                     same_configuration=key.split("-")[0] in ("AP01", "N01", "N02"),
                     answer_tokens=len(answer["completion_ids"]), reason=reason))
assert len(rows) == 12
(HERE / "baseline-grades.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
summary = dict(n=len(rows), valid=sum(x["valid_proof"] for x in rows),
               same_configuration_valid=sum(x["valid_proof"] and x["same_configuration"] for x in rows),
               transfer_valid=sum(x["valid_proof"] and not x["same_configuration"] for x in rows),
               by_configuration={c: sum(x["valid_proof"] for x in rows if x["source_configuration"] == c)
                                 for c in sorted({x["source_configuration"] for x in rows})})
(HERE / "baseline-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
print(summary)
