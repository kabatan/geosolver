"""Manual claim/proof/use audit for the 12 concise-prompt self-material answers."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path("qwen/.runtime/qwen35_self_materials_20260923/fresh-material-20260924")

JUDGMENTS = {
    "H01-fresh-0": ("true_but_weak", False, "H,P,D,M cyclic is true from two right angles, but its proposed calculation-saving application invokes unsupported or misidentified angle relations."),
    "H01-fresh-1": ("true", True, "A contiguous final subanswer proves MP·AM=BC²/4 from the original altitude and projection equations and gives a direct length example; earlier exploratory false claims are excluded verbatim."),
    "H01-fresh-2": ("unproved_or_false", False, "Ends with an explicitly unproved PH/HM formula and a varying coefficient."),
    "H01-fresh-3": ("elementary_but_unsettled", False, "The final tan relation for the altitude-median angle is elementary, but the full answer has unsettled preceding conjectures and does not produce a concise verified useful training unit."),
    "DA05-fresh-0": ("false", False, "Claims triangle BDE similar to BCA via unsupported angle relations; contradicted by the exact DA05 witness."),
    "DA05-fresh-1": ("false", False, "Final ME=2MD contradicts the exact DA05 witness; its decisive algebra is omitted."),
    "DA05-fresh-2": ("false", False, "Final proposed AE:EC side-length ratio contradicts the exact DA05 witness; coordinate derivation omitted."),
    "DA05-fresh-3": ("false", False, "Final AD=BC contradicts the exact DA05 witness; circle angle correspondence is invalid."),
    "DA15-fresh-0": ("false", False, "B,C,D,E are not generally cyclic; exact witness circle determinant is nonzero."),
    "DA15-fresh-1": ("false", False, "D,E,M are distinct and collinear, so D,E,F,M cannot be four points on a nondegenerate circle."),
    "DA15-fresh-2": ("false", False, "Its final AF/FM formula is selected from a single numerical match despite unresolved inconsistency; contradicted by the exact DA15 witness."),
    "DA15-fresh-3": ("false", False, "O,D,E,F cyclicity contradicts the exact DA15 witness; central step is asserted."),
}

rows = []
for key, (claim_status, selected_teacher_unit, reason) in JUDGMENTS.items():
    path = ROOT / (key + ".json")
    raw = path.read_bytes()
    answer = json.loads(raw)
    assert answer["finish_reason"] == "stop"
    rows.append(dict(id=key, source=str(path), source_sha256=hashlib.sha256(raw).hexdigest(),
                     source_configuration=key.split("-")[0], claim_status=claim_status,
                     selected_teacher_unit=selected_teacher_unit,
                     answer_tokens=answer["tokens"], reason=reason))
assert len(rows) == 12
(HERE / "fresh-grades.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
summary = dict(n=len(rows), teacher_units=sum(x["selected_teacher_unit"] for x in rows),
               configurations_with_teacher_units=sorted({x["source_configuration"] for x in rows
                                                         if x["selected_teacher_unit"]}),
               total_answer_tokens=sum(x["answer_tokens"] for x in rows))
(HERE / "fresh-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
print(summary)
