#!/usr/bin/env python3
"""Freeze matched claim-only and proof-supplied diagnostic jobs for fresh4."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[5]
BASE = ROOT / "docs/research/qwen35-external-teacher-2026-09-25/heldout-near-transfer"
OUT = BASE / "proof-gap-diagnostic-fresh4"
FRESH4 = BASE / "followup-fresh4/eval_jobs.json"
RELATION_GIVEN = BASE / "followup-relation-given-fresh4/eval_jobs.json"

CONDITION_C = OUT / "condition_c_claim_jobs.json"
CONDITION_D = OUT / "condition_d_proof_jobs.json"
PROTOCOL = OUT / "PROTOCOL.md"
AUDIT = OUT / "math_source_audit.json"
HASHES = OUT / "hashes.json"

LEMMA = (
    "\n\nGeneral lemma (you may use this without proof): In any nondegenerate "
    "triangle ABC, let H be its orthocenter and M the midpoint of BC. If P is "
    "the orthogonal projection of H onto line AM, then the directed-vector "
    "identity (vector MP) dot (vector MA) = (BC/2)^2 holds. Equivalently, "
    "vector MP = ((BC/2)^2 / AM^2) vector MA. Here AM and BC in the formula "
    "are lengths; the arrows in the identity denote directed vectors. This "
    "lemma does not identify any problem-defined point elsewhere."
)

CLAIMS = {
    "H03": (
        "For each vertex, each problem-defined second intersection P_a, P_b, "
        "P_c is the orthogonal projection of H onto the corresponding median "
        "AM_a, BM_b, CM_c."
    ),
    "H04": (
        "For the intersection T selected by the stated order, "
        "AT^2 = MT^2 - (BC/2)^2."
    ),
    "H14": "The problem-defined point R is the orthogonal projection of H onto line AM.",
}

PROOFS = {
    "H03": r"""Supplied construction-to-foot proof for this condition (use it as an established lemma; do not claim that you independently proved it):

For the A-construction, put M_a=(0,0), B=(-m,0), C=(m,0), A=(x,y), with m=BC/2 and rho^2=x^2+y^2. Let q=CA and r=AB. Since the triangle is scalene, q != r. The internal and external angle-bisector intersections with BC have coordinates k=m(r-q)/(r+q) and l=m(r+q)/(r-q), so kl=m^2. A circle through (k,0),(l,0) has equation X^2+Y^2+uX+wY+m^2=0. On AM_a, write (X,Y)=s(x,y). The resulting quadratic in s has leading coefficient rho^2, constant term m^2, and one root s=1 because it passes through A. Its other root is s=m^2/rho^2. Acuteness at A gives rho^2-m^2=(B-A) dot (C-A)>0, so this root lies strictly between 0 and 1. It is therefore the defined second intersection P_a.

The orthocenter has coordinates H=(x,(m^2-x^2)/y), whence H dot A=m^2. With P_a=(m^2/rho^2)A, (H-P_a) dot A=0; since P_a lies on AM_a, it is the perpendicular foot. Relabeling the vertices proves the same statement for P_b and P_c. The proof also establishes the selected second-intersection branch.""",
    "H04": r"""Supplied projection-relation derivation for this condition (use it as established; the remaining task is yours):

Put M=(0,0), B=(-m,0), C=(m,0), A=(x,y), and rho^2=x^2+y^2, where m=BC/2. The orthocenter is H=(x,(m^2-x^2)/y), so H dot A=m^2. Since the problem explicitly defines P as the foot on AM, write P=lambda A. The perpendicularity (H-P) dot A=0 gives lambda rho^2=m^2. Acuteness at A gives rho^2-m^2=(A-B) dot (A-C)>0, so 0<lambda=m^2/rho^2<1. Thus the projection is distinct from A and the factor 1-lambda is nonzero.""",
    "H14": r"""Supplied construction-to-foot proof for this condition (use it as an established lemma; do not claim that you independently proved it):

Put M=(0,0), B=(-m,0), C=(m,0), A=(u,v), S=u^2+v^2, and delta=S-m^2. Acuteness at A gives delta>0. The circumcircle Omega has equation X^2+Y^2-(delta/v)Y-m^2=0; its reflection Omega* across BC has equation X^2+Y^2+(delta/v)Y-m^2=0. Write U=AB^2>0 and parameterize the second intersection D on line AB as W=A+t(B-A). Direct substitution gives |W-C|^2-|A-C|^2=t(Ut-2delta), so the non-A point on the circle centered at C with radius CA has t=2delta/U>0. Substitution in Omega* gives F_*(W)=(t-1)(Ut-2delta), so D lies on Omega*. By symmetry, E also lies on Omega*.

The inversion I(X)=m^2 X/|X|^2 maps Omega* to Omega by substitution in their equations and preserves each ray from M. Since M is inside Omega (it is the midpoint of chord BC), each positive ray from M meets Omega once; hence P=I(D) and Q=I(E). Inversion maps line AB, which does not pass through M, to a circle through M, B=I(B), and I(A). Since D is on AB, P=I(D) lies on that same circle; therefore the circle BPM is this image circle and contains I(A). Similarly CQM contains I(A). I(A) is different from M, so the non-M common point is R=I(A)=(m^2/S)A.

The orthocenter is H=(u,(m^2-u^2)/v), giving H dot A=m^2=R dot A. Also 0<m^2/S<1, so R lies on AM. Therefore (H-R) dot A=0: R is the perpendicular foot on AM. These steps establish the ray and non-M intersection branches.""",
}

DOWNSTREAM = {
    "H03": (
        "Now use the supplied foot identification to derive the circle through "
        "P_a,P_b,P_c and its center from first principles. Relate that center "
        "to O and H, prove the needed vector relation for an arbitrary triangle, "
        "and then apply the given OH to find OZ. State why the circle center is "
        "the one specified in the problem."
    ),
    "H04": (
        "Now use the supplied projection relation and the defining perpendicular "
        "bisector condition TA=TP to derive the relation needed for AT. Show "
        "every cancellation is valid, use the stated order T,B,C to select the "
        "correct branch and sign, and compute AT."
    ),
    "H14": (
        "Now use the supplied foot identification and the given AH and AR to "
        "derive the area of triangle AHR. Justify the right angle, the positive "
        "square-root branch, and the use of the given lengths."
    ),
}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    for path in (CONDITION_C, CONDITION_D, PROTOCOL, AUDIT, HASHES):
        if path.exists():
            raise SystemExit(f"Refusing to overwrite existing artifact: {path}")

    fresh = read_json(FRESH4)
    relation_given = read_json(RELATION_GIVEN)
    relation_by_id = {j["id"]: j for j in relation_given}
    selected = []
    for source_id in ("H03", "H04", "H14"):
        candidates = [
            j for j in fresh
            if j["source_id"] == source_id and j.get("fresh4_instance") == 1
        ]
        if len(candidates) != 1:
            raise ValueError(f"Expected exactly one first fresh4 record for {source_id}")
        job = candidates[0]
        paired = relation_by_id.get(job["id"])
        if paired is None:
            raise ValueError(f"Missing relation-given counterpart for {job['id']}")
        for field in ("source_id", "seed", "english_problem"):
            if job[field] != paired[field]:
                raise ValueError(f"Fresh4/relation-given mismatch for {job['id']} field {field}")
        selected.append((job, paired))

    c_jobs, d_jobs = [], []
    for fresh_job, base_job in selected:
        source_id = fresh_job["source_id"]
        base_message = base_job["messages"][0]["content"]
        c_message = (
            base_message
            + "\n\nCondition C — claim supplied, proof withheld.\n"
            + f"The target statement to test is: {CLAIMS[source_id]}\n"
            + "This statement is a conjecture, not an accepted fact. Prove or refute it "
            + "from the original construction. If it is true, provide the decisive "
            + "construction argument, establish the selected intersection/order/branch, "
            + "and justify all nonzero factors before use or cancellation. Then complete "
            + "the original numerical problem. The general lemma above may be used only "
            + "after its point's foot hypothesis has been established."
        )
        c_job = dict(fresh_job)
        c_job["id"] = fresh_job["id"] + "-condition-C"
        c_job["messages"] = [{"role": "user", "content": c_message}]
        c_job["diagnostic_condition"] = "C_claim_only_proof_required"
        c_job["paired_fresh4_id"] = fresh_job["id"]
        c_jobs.append(c_job)

        d_message = (
            base_message
            + "\n\nCondition D — construction-to-relation proof supplied.\n"
            + PROOFS[source_id]
            + "\n\nFor this condition the preceding derivation is supplied information; "
            + "do not present it as your independently established proof. Complete the "
            + "following downstream task, including its branch/sign and nonzero-factor "
            + "checks, then solve the original numerical problem: "
            + DOWNSTREAM[source_id]
        )
        d_job = dict(fresh_job)
        d_job["id"] = fresh_job["id"] + "-condition-D"
        d_job["messages"] = [{"role": "user", "content": d_message}]
        d_job["diagnostic_condition"] = "D_proof_supplied_downstream_execution"
        d_job["paired_fresh4_id"] = fresh_job["id"]
        d_jobs.append(d_job)

    OUT.mkdir(parents=True, exist_ok=True)
    CONDITION_C.write_text(json.dumps(c_jobs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    CONDITION_D.write_text(json.dumps(d_jobs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    protocol = """# Fresh4 construction-to-relation proof-gap diagnostic

## Purpose

This CPU-frozen diagnostic separates three stages on one matched numerical item
per source ID (H03, H04, H14): identifying/proving the construction bridge,
using an already established bridge, and finishing the requested relation and
numerical application. It is for stage localization, not a confirmatory result.

Condition C supplies only a target-specific claim, explicitly labels it a
conjecture, and requires a proof or refutation from the stated construction.
For H03 and H14 the claim is the hidden construction-to-foot mapping. H04
already defines P as the foot, so its claim is the downstream identity linking
the perpendicular-bisector construction to AT.

Condition D supplies the decisive construction-to-foot/projection derivation
and asks for downstream relation use, branch handling, and application. D is an
execution diagnostic only. Its supplied bridge must never be scored as an
independent proof or independent transfer.

Both conditions are built from the existing relation-given fresh4 jobs, so they
share the same original English problem, generic projection lemma, numerical
givens, job seed, and standard instructions. Each C/D pair has a unique job ID
but the same `seed` and `english_problem` as its paired fresh4 item. No expected
target value, answer key, construction parameter, or model output is included.

## Interpretation

Score H03, H04, and H14 separately. For A (original), B (generic lemma only),
and C (claim only), grade both mapping/claim proof and downstream reasoning.
For D, mark the bridge as `supplied/not scored`; grade only downstream
mathematics, branches, and application. D success cannot establish independent
proof ability.

- C succeeds while B fails: a target claim may help focus search, but the
  evidence remains small and prompt-sensitive.
- C fails while D succeeds: the supplied construction bridge helps execution;
  the main observed gap is before or during bridge derivation.
- D fails: downstream relation execution, branch control, or application also
  remains a problem; inspect the response to localize it.
- B succeeds but A fails: the generic relation helps, while discovery or the
  construction bridge remains unresolved.

These patterns are diagnostic, not causal proof by themselves: C and D differ
in the amount of mathematical help; only one numeric item per source is used;
fresh4 source families have been examined in earlier work; and prompt changes
can affect generation. The first fresh4 numeric instance is reused exactly to
pair conditions and is not a new untouched holdout.

## Reproduction and integrity

From the repository root, run:

```bash
python3 docs/research/qwen35-external-teacher-2026-09-25/heldout-near-transfer/proof-gap-diagnostic-fresh4/build_proof_gap_diagnostic.py
```

The builder reads the frozen fresh4 and relation-given job files to assemble
prompts. It hashes the named audit/protocol sources as opaque bytes, but does
not parse answer keys, construction-check values, model outputs, or scores; it
does not invoke a model or GPU. It refuses to overwrite generated artifacts.
`hashes.json` records source and generated SHA-256 digests. Do not modify the
fresh4 source jobs. Freeze decoding and scoring before any later evaluation.
"""
    PROTOCOL.write_text(protocol, encoding="utf-8")

    audit = {
        "status": "passed_cpu_prompt_and_symbolic_math_review",
        "scope": "prepare two matched English diagnostic conditions; no model evaluation",
        "gpu_used": False,
        "model_outputs_opened": False,
        "scores_inspected": False,
        "answer_key_read_by_builder": False,
        "selected_inputs": [
            {
                "source_id": job["source_id"],
                "fresh4_id": job["id"],
                "seed": job["seed"],
                "fresh4_instance": job["fresh4_instance"],
                "same_numeric_problem_in_C_and_D": True,
                "expected_answer_in_prompt": False,
            }
            for job, _ in selected
        ],
        "condition_c_claims": CLAIMS,
        "condition_c_scoring": "The stated claim is not accepted as established; grade its proof/refutation from the problem construction, branch and nonzero checks, and downstream solution.",
        "condition_d_scoring": "The supplied bridge is not independent evidence and receives no proof/transfer credit; grade only downstream relation execution, branch/sign, and application.",
        "math_checks": {
            "H03": [
                "Angle-bisector intercepts k=m(r-q)/(r+q) and l=m(r+q)/(r-q) are finite for scalene q!=r and satisfy kl=m^2.",
                "The median-circle parameter roots have product m^2/(x^2+y^2); one root is A (s=1), so the second root is m^2/(x^2+y^2).",
                "Acuteness gives x^2+y^2-m^2=(B-A) dot (C-A)>0; hence the second root is distinct and lies in (0,1).",
                "H=(x,(m^2-x^2)/y), H dot A=m^2; with P=(m^2/(x^2+y^2))A, (H-P) dot A=0, proving the foot mapping. Cyclic relabeling covers all three points.",
                "Given the foot mapping, each P_i lies on the diameter-HG circle because P_i lies on its median with G and HP_i is perpendicular to that median. Its center is the midpoint of H and G. The usual vector identity h=a+b+c for O-origin circumradius vectors yields g=h/3 and z=2h/3; the prompt asks the model to derive these downstream steps.",
            ],
            "H04": [
                "The foot P is explicit. In centered coordinates H=(x,(m^2-x^2)/y), so H dot A=m^2 and P=lambda A implies lambda=m^2/rho^2.",
                "Acuteness yields rho^2-m^2>0 and lambda<1, justifying division by 1-lambda.",
                "TA=TP with T=(t,0) gives 2tx=rho^2+m^2; therefore AT^2=t^2-m^2=MT^2-m^2. The T,B,C order selects T before B and the positive length branch.",
            ],
            "H14": [
                "With delta=S-m^2>0, the second-radius-circle root on AB is t=2delta/AB^2>0 and lies on the reflected circumcircle Omega*; symmetry gives E on Omega*.",
                "Inversion I(X)=m^2 X/|X|^2 maps Omega* to Omega and preserves positive rays. M is inside Omega, so P=I(D) and Q=I(E) are the selected ray intersections.",
                "Inversion maps AB to a circle through M,B,I(A), containing P=I(D); likewise AC maps to a circle through M,C,I(A), containing Q=I(E). Thus R=I(A) is the non-M common point.",
                "R=(m^2/S)A with 0<m^2/S<1. Since H dot A=m^2=R dot A, HR is perpendicular to AM, proving the foot mapping and the selected branch.",
            ],
        },
        "limits": [
            "Only one repeated numeric item per source ID is used; repeated IDs are not independent geometry families.",
            "The source families were examined in prior work; this is not an untouched confirmatory evaluation.",
            "C versus D is a deliberately unequal-help stage-localization contrast and should not be described as a clean estimate of a training effect.",
        ],
    }
    AUDIT.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    provenance = [
        FRESH4,
        RELATION_GIVEN,
        BASE / "followup-fresh4/PROTOCOL.md",
        BASE / "followup-fresh4/INDEPENDENT_AUDIT.md",
        BASE / "followup-relation-given-fresh4/PROTOCOL.md",
        BASE / "followup-relation-given-fresh4/math_audit.json",
        BASE.parent / "projection-bridge-candidate/INDEPENDENT_AUDIT.md",
        BASE.parent / "projection-bridge-candidate/MATH_CAVEATS.md",
    ]
    hashes = {
        "label": "proof-gap diagnostic C/D freeze; no evaluation performed",
        "source_artifacts_sha256": {str(p.relative_to(ROOT)): sha256(p) for p in provenance},
        "generated_artifacts_sha256": {
            str(p.relative_to(ROOT)): sha256(p)
            for p in (CONDITION_C, CONDITION_D, PROTOCOL, AUDIT)
        },
        "builder_sha256": sha256(Path(__file__).resolve()),
        "selection": "first fresh4 numeric job for each of H03,H04,H14; matched C/D to the existing relation-given item by id, seed, and exact english_problem",
        "answer_key_or_model_outputs_used": False,
        "gpu_used": False,
    }
    HASHES.write_text(json.dumps(hashes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"created": [str(p.relative_to(ROOT)) for p in (CONDITION_C, CONDITION_D, PROTOCOL, AUDIT, HASHES)]}, indent=2))


if __name__ == "__main__":
    main()
