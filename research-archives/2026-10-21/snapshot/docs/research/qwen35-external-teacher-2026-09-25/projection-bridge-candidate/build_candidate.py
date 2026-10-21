#!/usr/bin/env python3
"""Build untrained projection-bridge candidate arms.

Inputs are restricted to the accepted English v0 H03/H04/H14 teacher rows and
the frozen 32-row near-transfer base. Token counts use the frozen run tokenizer
only; this script does not train or invoke a model.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "projection-bridge-candidate"
BASE_PATH = ROOT / "heldout-near-transfer" / "train.json"
TEACHER_PATH = ROOT.parent / "qwen35-external-teacher-2026-09-24" / "train.json"
AUDIT_PATH = ROOT.parent / "qwen35-external-teacher-2026-09-24" / "audits.json"
TOKENIZER_PATH = (
    ROOT.parents[2]
    / "qwen"
    / ".runtime"
    / "qwen35_external_teacher_20260925"
    / "train-near-32-original"
    / "tokenizer"
    / "tokenizer.json"
)

TARGETS = ("H03", "H04", "H14")
ROTATIONS = (
    ("rotation-1", "H03", ("H04", "H14")),
    ("rotation-2", "H04", ("H03", "H14")),
    ("rotation-3", "H14", ("H03", "H04")),
)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def dump_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def source_problem(row: dict[str, Any]) -> str:
    return row["prompt"].split("\n\n", 1)[1].strip()


def qa(row_id: str, source_id: str, prompt: str, answer: str) -> dict[str, str]:
    return {
        "id": row_id,
        "source": f"external-{source_id}-v0",
        "prompt": prompt.strip(),
        "answer": answer.strip(),
    }


def count_answer_tokens(text: str, tokenizer: Any) -> int:
    # The frozen protocol trains visible answer text plus one EOS token.
    return len(tokenizer.encode(text, add_special_tokens=False).ids) + 1


def treatment_rows(source_id: str, original: dict[str, Any]) -> list[dict[str, str]]:
    problem = source_problem(original)
    context = problem + "\n\n"

    if source_id == "H03":
        return [
            qa(
                f"{source_id}-focus-1",
                source_id,
                context
                + "Identify the relation that turns the three constructed "
                "median-circle intersections into a simple center computation.",
                """
For each vertex, the second circle-median intersection is the perpendicular
projection of H onto that median. In M_a-centered coordinates with
B=(-m,0), C=(m,0), and A=(x,y), it is
P_a=(m^2/(x^2+y^2))A. Acuteness makes the coefficient lie in (0,1).
Because the centroid G lies on each median, (P_a-H) is perpendicular to
(P_a-G); cyclically, the three points lie on the circle with diameter HG.
Its center is Z=(H+G)/2.
""",
            ),
            qa(
                f"{source_id}-focus-2",
                source_id,
                context
                + "Prove the projection relation and the resulting circle-center "
                "formula from the stated construction. Include the decisive "
                "intersection calculation and branch conditions, but do not "
                "substitute the given OH.",
                """
Work at A with M_a=(0,0), B=(-m,0), C=(m,0), A=(x,y), y>0, and
r^2=x^2+y^2. Put b=CA and c=AB. Since the triangle is scalene, b!=c;
the two angle-bisector intersections with BC have coordinates
k=m(c-b)/(c+b) and l=m(c+b)/(c-b), so kl=m^2. The circle through
A,(k,0),(l,0) has equation
X^2+Y^2-(k+l)X+eta Y+m^2=0. Substituting A fixes eta. On the median,
(X,Y)=s(x,y), and the equation factors as
(s-1)(r^2s-m^2)=0. Thus the second root is s=m^2/r^2.
Acuteness at A gives r^2-m^2=(B-A) dot (C-A)>0, so 0<s<1:
the root is distinct from A and lies on the segment AM_a.

The altitude equations give H=(x,(m^2-x^2)/y), hence A dot H=m^2.
Since P_a=sA, A dot P_a=m^2 too, so HP_a is perpendicular to AM_a.
The same argument applies cyclically. As G lies on each median,
(P_a-H) dot (P_a-G)=0. Therefore all three constructed points lie on
the circle with diameter HG; nondegeneracy identifies it with their
circumcircle, whose center is Z=(H+G)/2.
""",
            ),
            qa(
                f"{source_id}-focus-3",
                source_id,
                original["prompt"],
                """
Set M=(0,0), B=(-m,0), C=(m,0), A=(x,y), and r^2=x^2+y^2; let
b=CA and c=AB. Since the triangle is scalene, b!=c. The angle-bisector feet on BC
have coordinates k=m(c-b)/(c+b) and l=m(c+b)/(c-b), so kl=m^2.
The circle through A,(k,0),(l,0) has equation
X^2+Y^2-(k+l)X+eta Y+m^2=0. Substitution of A fixes eta; on the median
(X,Y)=s(x,y), its equation factors as (s-1)(r^2s-m^2)=0. Thus the
second intersection is P=(m^2/r^2)A. Acuteness gives
r^2-m^2=(B-A) dot (C-A)>0, so this root is distinct from A and lies
strictly between M and A.

The altitude equations give H=(x,(m^2-x^2)/y), hence A dot H=m^2;
also A dot P=m^2, so HP is perpendicular to AM. Cyclically the three
constructed points P_i are projections of H onto the medians. Since G
lies on each median, (P_i-H) dot (P_i-G)=0, so the P_i lie on the
circle with diameter HG. Nondegeneracy identifies this as their
circumcircle, whose center is Z=(H+G)/2.

With O as origin, let a,b,c be the vertex vectors. Since
|a|=|b|=|c|, (b+c) dot (b-c)=|b|^2-|c|^2=0 and
(a+c) dot (c-a)=|c|^2-|a|^2=0. Thus h=a+b+c lies on two altitudes,
so it is the orthocenter vector; the centroid vector is g=h/3.
Therefore z=(h+g)/2=2h/3, and OZ=(2/3)OH=(2/3)6=4.
""",
            ),
        ]

    if source_id == "H04":
        return [
            qa(
                f"{source_id}-focus-1",
                source_id,
                context
                + "State the useful construction-specific relation, including "
                "how the acute-angle projection and the ordered T,B,C branch "
                "determine its applicability.",
                """
If m=BC/2 and P is the foot from H to AM, then P=(m^2/AM^2)A
in M-centered coordinates. Acuteness ensures 0<m^2/AM^2<1, so P is
not A. The perpendicular-bisector condition TA=TP then yields
AT^2=MT^2-m^2. On the stated exterior branch T-B-C this is also
AT^2=TB*TC.
""",
            ),
            qa(
                f"{source_id}-focus-2",
                source_id,
                context
                + "Derive the relation from the orthocenter projection and "
                "perpendicular-bisector condition. Show why the cancelled "
                "factor is nonzero and preserve the stated branch.",
                """
Set M=(0,0), B=(-m,0), C=(m,0), A=(x,y), y>0, and r^2=x^2+y^2.
The altitude equations give H=(x,(m^2-x^2)/y), so A dot H=m^2.
The projection onto AM is P=lambda A, lambda=m^2/r^2. Since A is acute,
r^2-m^2=(B-A) dot (C-A)>0; hence 0<lambda<1 and P!=A.
Write T=(s,0). TA=TP because T lies on the perpendicular bisector of AP.
Expanding,
0=TA^2-TP^2=(1-lambda)((1+lambda)r^2-2sx).
Since lambda!=1, 2sx=r^2+m^2. Thus
AT^2=r^2-2sx+s^2=s^2-m^2=MT^2-(BC/2)^2.
The ordering T-B-C selects the exterior point left of B; there
MT=TB+BC/2, so the same expression is TB*TC.
""",
            ),
            qa(
                f"{source_id}-focus-3",
                source_id,
                original["prompt"],
                integrated_treatment_answer(source_id),
            ),
        ]

    if source_id == "H14":
        return [
            qa(
                f"{source_id}-focus-1",
                source_id,
                context
                + "Identify a relation that replaces the two constructed "
                "circles by a direct orthocenter-projection computation.",
                """
The common point R other than M is the perpendicular projection of H
onto AM. In M-centered coordinates with B=(-m,0), C=(m,0),
A=(u,v), S=u^2+v^2, it is R=(m^2/S)A. Acuteness gives
0<m^2/S<1, so R lies strictly between M and A. Thus HR is
perpendicular to AR and triangle AHR is right at R.
""",
            ),
            qa(
                f"{source_id}-focus-2",
                source_id,
                context
                + "Prove the common-point projection relation. Justify the "
                "inversion correspondences, positive ray/branch choices, and "
                "nonzero conditions.",
                """
Take M=(0,0), B=(-m,0), C=(m,0), A=(u,v), v>0, S=u^2+v^2,
and delta=S-m^2. Acuteness gives |u|<m and delta>0. The circumcircle
Omega and its reflection Omega* in BC have equations
x^2+y^2-(delta/v)y-m^2=0 and x^2+y^2+(delta/v)y-m^2=0.
Parametrize AB by W(t)=A+t(B-A) and put U=(u+m)^2+v^2>0.
The circle centered at C with radius CA gives
|W-C|^2-|A-C|^2=t(Ut-2delta); substitution into Omega* gives
(t-1)(Ut-2delta). Thus the specified second point D has
t=2delta/U>0 and lies on Omega*. By symmetry E also lies on Omega*.

Inversion I(X)=m^2 X/|X|^2 maps Omega* onto Omega with positive scale.
It preserves each ray from M; because M is inside Omega, each such ray
meets Omega once, so P=I(D) and Q=I(E), with no opposite-ray ambiguity.
The inversion images of AB and AC are circles through M, B, I(A) and
M, C, I(A), respectively, since inversion fixes B and C. These are
exactly circles BPM and CQM; their distinctness and the nondegeneracy
assumptions make their second common point R=I(A)=(m^2/S)A.

The altitude equations give H=(u,(m^2-u^2)/v), so A dot H=m^2.
Also A dot R=(m^2/S)|A|^2=m^2, hence (H-R) dot A=0.
Acuteness yields 0<m^2/S<1, so R lies on AM and HR is perpendicular
to AM. Thus R is the required projection.
""",
            ),
            qa(
                f"{source_id}-focus-3",
                source_id,
                original["prompt"],
                integrated_treatment_answer(source_id),
            ),
        ]

    raise ValueError(source_id)


def control_answers(source_id: str) -> list[str]:
    openings = ("Set ", "Write ", "Take ")
    if source_id == "H03":
        body = """M=0, B=(-m,0), C=(m,0), A=(x,y), r^2=x^2+y^2, and
b=CA,c=AB. Since the triangle is scalene, b!=c; the angle-bisector feet are
k=m(c-b)/(c+b), l=m(c+b)/(c-b), so kl=m^2. The circle AKL has
constant term m^2; restricting it to median sA gives
(s-1)(r^2s-m^2)=0. Since acute A gives r^2-m^2=(B-A) dot (C-A)>0,
the second point is P=(m^2/r^2)A. Altitudes give
H=(x,(m^2-x^2)/y), so A dot H=A dot P=m^2 and HP perp AM.
Cyclically these are H's median projections; (P_i-H) dot (P_i-G)=0,
so they lie on the diameter-HG circle and Z=(H+G)/2. With O=0 and
equal-length vertex vectors a,b,c, (b+c) dot (b-c)=0 and
(a+c) dot (c-a)=0, so h=a+b+c lies on two altitudes and g=h/3.
Thus z=2h/3 and OZ=(2/3)OH=4.
"""
    elif source_id == "H04":
        body = """M=0, B=(-3,0), C=(3,0), A=(x,y), r^2=x^2+y^2.
Altitudes give H=(x,(9-x^2)/y), hence P=9A/r^2; A acute gives
r^2-9=(B-A) dot (C-A)>0. With T=(s,0), expanding TA^2-TP^2 gives
(1-9/r^2)(r^2+9-2sx)=0, hence 2sx=r^2+9.
Then AT^2=r^2-2sx+s^2=MT^2-9. T-B-C, BT=2 give MT=5;
thus AT=4.
"""
    elif source_id == "H14":
        body = """M=0, B=(-m,0), C=(m,0), A=(u,v), v>0, S=u^2+v^2,
delta=S-m^2>0. Omega: x^2+y^2-(delta/v)y-m^2=0; Omega* is
its reflection in BC. On AB, W=A+t(B-A), U=|AB|^2>0. Then
|W-C|^2-|A-C|^2=t(Ut-2delta), Omega*(W)=(t-1)(Ut-2delta),
so D,E lie on Omega* at t=2delta/U>0. Inversion
I(X)=m^2X/|X|^2 sends Omega* to Omega: substituting
(x,y)=m^2(X,Y)/(X^2+Y^2) into Omega* gives
X^2+Y^2-(delta/v)Y-m^2=0. It fixes B,C and rays. M has power
-m^2, hence P=I(D), Q=I(E) are the unique
positive-ray intersections. AB: vx-(u+m)y+mv=0; inversion gives its
image circle v(X^2+Y^2)+mvX-m(u+m)Y=0 through M,B,I(A),P.
Similarly AC maps to CQM through I(A), so R=I(A)=(m^2/S)A.
Altitudes give H=(u,(m^2-u^2)/v), A dot H=A dot R=m^2.
As 0<m^2/S<1, R is the foot on AM. Therefore AHR is right,
HR=sqrt(10^2-6^2)=8, and area is 24.
"""
    else:
        raise ValueError(source_id)
    return [opening + body for opening in openings]


def integrated_treatment_answer(source_id: str) -> str:
    # The control's shortest full-solution template also serves the unhinted
    # third treatment slot; remove its control-only variant opening.
    return control_answers(source_id)[0][len("Set "):]


def control_prompt_variants(original: dict[str, Any]) -> list[str]:
    problem = source_problem(original)
    wrappers = (
        "Find the exact requested quantity in this configuration. Explain "
        "the key geometric relation from the stated objects and its conditions.",
        "Work out the geometry problem below with a self-contained argument "
        "from the construction to the numerical answer.",
    )
    return [original["prompt"], *(f"{wrapper}\n\n{problem}" for wrapper in wrappers)]


def control_rows(source_id: str, original: dict[str, Any]) -> list[dict[str, str]]:
    prompts = control_prompt_variants(original)
    answers = control_answers(source_id)
    if len(prompts) != 3 or len(answers) != 3:
        raise SystemExit(f"{source_id}: expected three control prompt-answer slots")
    return [
        qa(f"{source_id}-integrated-{i}", source_id, prompt, answer)
        for i, (prompt, answer) in enumerate(zip(prompts, answers), 1)
    ]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    base = read_json(BASE_PATH)
    source_rows = read_json(TEACHER_PATH)
    audits = read_json(AUDIT_PATH)
    audit_by_id = {row["id"]: row for row in audits}
    src_by_id = {row["source"]: row for row in source_rows if row.get("source") in TARGETS}

    if len(base) != 32:
        raise SystemExit(f"Expected 32 base rows, found {len(base)}")
    base_sources = {row["source"] for row in base}
    if any(target in base_sources for target in TARGETS):
        raise SystemExit("Projection target source unexpectedly appears in base")
    if any(
        target in json.dumps(row, ensure_ascii=False)
        for row in base
        for target in TARGETS
    ):
        raise SystemExit("Projection target label or source text unexpectedly appears in base")
    if set(src_by_id) != set(TARGETS):
        raise SystemExit(f"Selected v0 sources mismatch: {sorted(src_by_id)}")
    for target in TARGETS:
        report = audit_by_id.get(target)
        if not report or not all(
            report.get(key) is True
            for key in ("numeric", "true_relation", "proof", "use", "branches_checked")
        ) or report.get("status") != "accept":
            raise SystemExit(f"Source {target} lacks accepted audited v0 proof")

    from tokenizers import Tokenizer

    tokenizer = Tokenizer.from_file(str(TOKENIZER_PATH))
    base_tokens = sum(count_answer_tokens(row["answer"], tokenizer) for row in base)
    mapping: dict[str, Any] = {}
    for rotation_name, omitted_id, permitted in ROTATIONS:
        rotation_dir = OUT / rotation_name
        allowed_ids = {f"external-{sid}-v0" for sid in permitted}
        treatment: list[dict[str, str]] = []
        control: list[dict[str, str]] = []
        for sid in permitted:
            treatment.extend(treatment_rows(sid, src_by_id[sid]))
            control.extend(control_rows(sid, src_by_id[sid]))
        for sid in permitted:
            source_tag = f"external-{sid}-v0"
            treatment_source = [row for row in treatment if row["source"] == source_tag]
            control_source = [row for row in control if row["source"] == source_tag]
            standard_prompt = src_by_id[sid]["prompt"]
            control_prompts = [row["prompt"] for row in control_source]
            if len(treatment_source) != 3 or treatment_source[2]["prompt"] != standard_prompt:
                raise SystemExit(f"{rotation_name} {sid}: treatment lacks standard full-task slot")
            if (
                len(control_source) != 3
                or control_prompts[0] != standard_prompt
                or len(set(control_prompts)) != 3
            ):
                raise SystemExit(f"{rotation_name} {sid}: control standard/paraphrased prompts mismatch")
        for arm_name, rows in (("treatment", treatment), ("control", control)):
            if len(rows) != 6:
                raise SystemExit(f"{rotation_name} {arm_name}: expected 6 additions")
            if {row["source"] for row in rows} != allowed_ids:
                raise SystemExit(f"{rotation_name} {arm_name}: source mismatch")
            if any(row["source"] == f"external-{omitted_id}-v0" for row in rows):
                raise SystemExit(f"{rotation_name} {arm_name}: excluded source leaked")
            if any(omitted_id in (row["prompt"] + row["answer"] + row["source"] + row["id"])
                   for row in rows):
                raise SystemExit(f"{rotation_name} {arm_name}: excluded ID text leaked")
            counts = {sid: 0 for sid in permitted}
            for row in rows:
                sid = row["source"].split("-")[1]
                counts[sid] += 1
            if counts != {sid: 3 for sid in permitted}:
                raise SystemExit(f"{rotation_name} {arm_name}: slot balance mismatch {counts}")
            row_ids = [row["id"] for row in rows]
            if len(set(row_ids)) != len(row_ids):
                raise SystemExit(f"{rotation_name} {arm_name}: duplicate added row IDs")

        add_dir = rotation_dir / "additions"
        dump_json(add_dir / "treatment.json", treatment)
        dump_json(add_dir / "control.json", control)
        treatment_train = base + treatment
        control_train = base + control
        dump_json(rotation_dir / "train-treatment.json", treatment_train)
        dump_json(rotation_dir / "train-control.json", control_train)

        treatment_tokens = sum(count_answer_tokens(row["answer"], tokenizer) for row in treatment)
        control_tokens = sum(count_answer_tokens(row["answer"], tokenizer) for row in control)
        treatment_by_source = {
            sid: sum(
                count_answer_tokens(row["answer"], tokenizer)
                for row in treatment
                if row["source"] == f"external-{sid}-v0"
            )
            for sid in permitted
        }
        control_by_source = {
            sid: sum(
                count_answer_tokens(row["answer"], tokenizer)
                for row in control
                if row["source"] == f"external-{sid}-v0"
            )
            for sid in permitted
        }
        merged_treatment_tokens = base_tokens + treatment_tokens
        merged_control_tokens = base_tokens + control_tokens
        mismatch = (
            100.0 * abs(treatment_tokens - control_tokens) / max(treatment_tokens, control_tokens)
            if max(treatment_tokens, control_tokens)
            else 0.0
        )
        merged_mismatch = (
            100.0 * abs(merged_treatment_tokens - merged_control_tokens)
            / max(merged_treatment_tokens, merged_control_tokens)
            if max(merged_treatment_tokens, merged_control_tokens)
            else 0.0
        )
        if merged_mismatch > 2.0:
            raise SystemExit(
                f"{rotation_name}: merged target-token mismatch {merged_mismatch:.3f}% "
                "exceeds the exploratory 2% tolerance"
            )
        mapping[rotation_name] = {
            "omitted_target_id_audit_only": omitted_id,
            "permitted_v0_source_ids": [f"external-{sid}-v0" for sid in permitted],
            "base_source_count": len(base),
            "added_rows_per_arm": 6,
            "added_rows_per_source_per_arm": 3,
            "merged_row_count_per_arm": 38,
            "merged_unique_source_count_per_arm": len(base_sources | allowed_ids),
            "heldout_id_occurs_in_training_rows": False,
            "assistant_target_tokens_in_additions_including_eos": {
                "treatment": treatment_tokens,
                "control": control_tokens,
                "treatment_by_permitted_source": treatment_by_source,
                "control_by_permitted_source": control_by_source,
                "absolute_mismatch": abs(treatment_tokens - control_tokens),
                "relative_mismatch_percent_of_larger_arm": round(mismatch, 2),
            },
            "assistant_target_tokens_in_merged_38_row_dataset_including_eos": {
                "shared_32_row_base": base_tokens,
                "treatment": merged_treatment_tokens,
                "control": merged_control_tokens,
                "absolute_mismatch": abs(merged_treatment_tokens - merged_control_tokens),
                "relative_mismatch_percent_of_larger_arm": round(merged_mismatch, 3),
            },
            "files": {
                "additions_treatment": f"{rotation_name}/additions/treatment.json",
                "additions_control": f"{rotation_name}/additions/control.json",
                "train_treatment": f"{rotation_name}/train-treatment.json",
                "train_control": f"{rotation_name}/train-control.json",
            },
        }

    source_hashes = {
        str(path.relative_to(ROOT.parents[2])): sha256(path)
        for path in (BASE_PATH, TEACHER_PATH, AUDIT_PATH, TOKENIZER_PATH)
    }
    created_hashes = {
        str(path.relative_to(OUT)): sha256(path)
        for path in sorted(OUT.rglob("*.json"))
        if path.name not in {"audit-manifest.json", "candidate-hashes.json"}
    }
    manifest = {
        "status": "candidate_untrained",
        "purpose": (
            "CPU-only decomposed projection-bridge positive-control candidate; "
            "not a trained result or confirmatory evidence"
        ),
        "source_counts": {
            "frozen_32_common_base_rows": len(base),
            "frozen_32_common_base_distinct_sources": len(base_sources),
            "audited_v0_teacher_rows_in_source_file": len(source_rows),
            "audit_records_in_source_file": len(audits),
            "audited_rows_selected": 3,
            "selected_ids": [f"external-{sid}-v0" for sid in TARGETS],
            "selected_audit_records": 3,
            "rows_added_per_arm_per_rotation": 6,
            "merged_rows_per_arm_per_rotation": 38,
        },
        "selected_source_audits": {
            target: {
                key: audit_by_id[target].get(key)
                for key in (
                    "status",
                    "numeric",
                    "true_relation",
                    "proof",
                    "use",
                    "branches_checked",
                    "decisive_lemma",
                    "reviewer_reason",
                )
            }
            for target in TARGETS
        },
        "source_hashes_sha256": source_hashes,
        "tokenizer": {
            "path": str(TOKENIZER_PATH.relative_to(ROOT.parents[2])),
            "sha256": source_hashes[str(TOKENIZER_PATH.relative_to(ROOT.parents[2]))],
            "counting_rule": "Qwen tokenizer answer text plus one EOS token; no model call",
            "shared_32_row_base_assistant_target_tokens_including_eos": base_tokens,
        },
        "token_budget_acceptance": {
            "status": "exploratory_approximate_merged_dataset_match",
            "max_relative_merged_mismatch_percent_of_larger_arm": 2.0,
            "strict_token_match": False,
            "added_row_mismatch_reported_separately": True,
        },
        "rotations": mapping,
        "created_file_hashes_sha256": created_hashes,
        "math_caveats": {
            "H03": [
                "The acute angle at the active vertex gives r^2>m^2, selecting the second median-circle root in (0,1).",
                "The angle-bisector coordinate formulas use b!=c; the source is scalene.",
                "The assumed nondegenerate constructions identify the three-point circumcircle with the diameter-HG circle.",
            ],
            "H04": [
                "Acuteness gives lambda=m^2/r^2<1, so cancelling 1-lambda is valid and P!=A.",
                "T-B-C fixes T outside BC; with the source values T is left of B and MT=BT+BC/2.",
                "The final positive square root is used because AT is a length.",
            ],
            "H14": [
                "Acuteness gives delta=S-m^2>0 and 0<m^2/S<1; these select positive second-intersection and segment-projection branches.",
                "The inversion is defined at D and E under the stated nondegeneracy; M is interior to Omega, so the positive ray intersection is unique.",
                "The two inverted lines are distinct for the scalene source; stated nondegeneracy identifies the common point other than M.",
                "AH=10 and AR=6 make the projected right triangle nondegenerate.",
            ],
        },
    }
    dump_json(OUT / "audit-manifest.json", manifest)
    sidecar_hashes = {
        str(path.relative_to(OUT)): sha256(path)
        for path in sorted(OUT.rglob("*"))
        if path.is_file() and path.name != "candidate-hashes.json"
    }
    dump_json(
        OUT / "candidate-hashes.json",
        {
            "scope": "All candidate files except this self-referential sidecar",
            "sha256": sidecar_hashes,
        },
    )


if __name__ == "__main__":
    main()
