#!/usr/bin/env python3
"""Build a CPU-only, audited six-source numeric-variant SFT candidate.

This script creates two 50-row arms from the already frozen 32-row English
training set: audited v1-v3 worked answers for six sources, and matched exact
v0 repeats for those same source slots. It does not train or evaluate a model.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import sympy as sp
from transformers import AutoTokenizer

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
BASE_PATH = ROOT / "docs/research/qwen35-external-teacher-2026-09-25/heldout-near-transfer/train.json"
VARIANTS_PATH = ROOT / "benchmarks/humpty_configurations_v2/training_variants.jsonl"
AUDITS_PATH = ROOT / "docs/research/qwen35-external-teacher-2026-09-24/audits.json"
MODEL_PATH = ROOT / "docs/research/qwen35-self-materials-2026-09-23/model.json"
HELDOUT = {"H03", "H04", "H08", "H14", "H15"}
SOURCES = ("H01", "H02", "H07", "DA02", "DB02", "DB06")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def pmap(prompt: str, replacements: list[tuple[str, str]]) -> str:
    for old, new in replacements:
        count = prompt.count(old)
        assert count == 1, (old, count)
        prompt = prompt.replace(old, new)
    return prompt


def h01_answer(v: str, givens: dict) -> str:
    m = sp.Rational(givens["BC"]) / 2
    t = sp.sympify(givens["AM"])
    gap = sp.simplify(t**2 - m**2)
    ans = sp.simplify(t - m**2 / t)
    assert gap > 0
    base = BASE_BY_SOURCE["H01"]["answer"]
    marker = "\n\nHere m=12/2=6 and t=10. Hence AP=10−36/10=32/5."
    assert base.endswith(marker)
    proof = base[: -len(marker)]
    return proof + (
        f"\n\nHere m=BC/2={sp.sstr(m)} and t=AM={sp.sstr(t)}. "
        f"The acute-angle branch is t²−m²={sp.sstr(gap)}>0, so P is strictly between M and A. "
        f"Therefore AP=t−m²/t={sp.sstr(t)}−{sp.sstr(m**2)}/{sp.sstr(t)}={sp.sstr(ans)}."
    )


def h02_proof(v: str, givens: dict) -> tuple[str, dict]:
    m = sp.Rational(givens["BC"]) / 2
    t = sp.sympify(givens["AM"])
    h = sp.sympify(givens["AK"])
    x = sp.sqrt(sp.simplify(t**2 - h**2))
    dvals = [sp.Rational(givens["BD1"]) - m, sp.Rational(givens["BD2"]) - m]
    ac2 = sp.simplify((x - m) ** 2 + h**2)
    ab2 = sp.simplify((x + m) ** 2 + h**2)
    s_u = [sp.factor(1 - 2*m*(m-d)/ac2) for d in dvals]
    s_v = [sp.factor(1 - 2*m*(m+d)/ab2) for d in dvals]
    delta = abs(dvals[1] - dvals[0])
    ans = sp.simplify(delta * t / h)
    acute_a = sp.simplify(t**2 - m**2)
    ab_side2 = sp.simplify(ab2)
    ac_side2 = sp.simplify(ac2)
    bc_side2 = sp.simplify((2*m)**2)
    assert x > 0 and x < m and h > 0 and acute_a > 0
    assert all(-m < d < m for d in dvals)
    assert all(a != 0 for a in s_u + s_v)
    assert len({ab_side2, ac_side2, bc_side2}) == 3
    proof = f"""We prove that, for this nondegenerate construction, moving D along BC by a distance δ moves the center Z by δ·AM/AK.

Set M=(0,0), B=(−m,0), C=(m,0), A=(x,h), and D=(d,0), where h=AK>0 and t²=x²+h² with t=AM. Normalize the equation of circle AUV as
F_d(X,Y)=X²+Y²+αX+βY+γ=0.

On line AB, circles AUV and ACD share the two distinct intersections A,V. Their restrictions to AB have the same leading coefficient, so they agree on that line. On the horizontal axis, circle ACD has restriction (X−m)(X−d), hence F_d(B)=2m(m+d). Similarly, comparing AUV with ABD on AC gives F_d(C)=2m(m−d). But F_d(B)=m²−αm+γ and F_d(C)=m²+αm+γ. Adding and subtracting yield γ=m² and α=−2d. Since A lies on the circle, β=(2dx−t²−m²)/h. Therefore
Z(d)=(d,(t²+m²−2dx)/(2h)).

For d₂−d₁=δ, the center displacement is (δ,−xδ/h). Its length is |δ|√(1+x²/h²)=|δ|t/h. Thus Z₁Z₂=|BD₂−BD₁|·AM/AK.

For variant {v}, m={sp.sstr(m)}, x={sp.sstr(x)}, h={sp.sstr(h)}, t²={sp.sstr(t**2)}, and t²−m²={sp.sstr(acute_a)}>0. Also −m<x<m, so the triangle is acute at B and C, while t²−m²>0 gives acuteness at A. The squared side lengths are AB²={sp.sstr(ab_side2)}, AC²={sp.sstr(ac_side2)}, BC²={sp.sstr(bc_side2)}, which are pairwise different. The two D coordinates are d₁={sp.sstr(dvals[0])} and d₂={sp.sstr(dvals[1])}, both strictly between −m and m.

To check the circle centers are defined, parametrize U=A+s_U(C−A) and V=A+s_V(B−A). Restricting the corresponding circle equations gives s_U=1−2m(m−d)/AC² and s_V=1−2m(m+d)/AB². For d₁,d₂ these values are s_U=({sp.sstr(s_u[0])},{sp.sstr(s_u[1])}) and s_V=({sp.sstr(s_v[0])},{sp.sstr(s_v[1])}); none is zero. Thus U≠A and V≠A, and since they lie on distinct sidelines, A,U,V are noncollinear. The defining circles and centers are nondegenerate.

Finally, |BD₂−BD₁|={sp.sstr(delta)}, so
Z₁Z₂={sp.sstr(delta)}·({sp.sstr(t)})/({sp.sstr(h)})={sp.sstr(ans)}."""
    audit = {
        "m": sp.sstr(m), "x": sp.sstr(x), "h": sp.sstr(h), "t_squared": sp.sstr(t**2),
        "acute_A_dot": sp.sstr(acute_a), "d1": sp.sstr(dvals[0]), "d2": sp.sstr(dvals[1]),
        "AB_squared": sp.sstr(ab_side2), "AC_squared": sp.sstr(ac_side2), "BC_squared": sp.sstr(bc_side2),
        "sU": [sp.sstr(x) for x in s_u], "sV": [sp.sstr(x) for x in s_v],
        "exact_answer": sp.sstr(ans), "formula": "|BD2-BD1|*AM/AK",
    }
    return proof, audit


def h07_answer(v: str, givens: dict) -> tuple[str, dict]:
    ab = sp.sympify(givens["AB"])
    mf = sp.sympify(givens["MF"])
    on = sp.sympify(givens["ON"])
    a = ab / 2
    lam = sp.simplify(a**2 / on**2)
    pq = sp.simplify(ab * (1-lam))
    height = 2*mf
    area = sp.simplify(pq*height/2)
    assert 0 < lam < 1 and pq > 0 and mf > 0
    base = BASE_BY_SOURCE["H07"]["answer"]
    marker = "\n\nFor the given numbers, a=4, ON²=(8sqrt(10)/5)²=128/5, and λ=16/(128/5)=5/8. Thus PQ=8(1−5/8)=3 and the altitude is 2·3=6. The required area is (1/2)·3·6=9."
    assert base.endswith(marker)
    proof = base[: -len(marker)]
    final = (
        f"\n\nFor variant {v}, a=AB/2={sp.sstr(a)} and ON²={sp.sstr(on**2)}, so "
        f"λ=OA²/ON²={sp.sstr(a**2)}/{sp.sstr(on**2)}={sp.sstr(lam)}. This is strictly between 0 and 1, "
        f"which verifies the ordered-ray branch M=λN. Hence PQ=AB(1−λ)={sp.sstr(pq)}>0, "
        f"and the distance from E to PQ is 2MF={sp.sstr(height)}. Therefore "
        f"area(EPQ)=PQ·(2MF)/2={sp.sstr(pq)}·{sp.sstr(height)}/2={sp.sstr(area)}."
    )
    audit = {
        "half_AB": sp.sstr(a), "ON_squared": sp.sstr(on**2), "lambda": sp.sstr(lam),
        "lambda_branch": "0<lambda<1", "PQ": sp.sstr(pq), "height": sp.sstr(height),
        "exact_answer": sp.sstr(area),
    }
    # Reconstruct the exact authoring witness for each numeric variant.  With
    # O=(0,0), A=(-a,0), B=(a,0), the generator used M=(x0-a,y0) and N=M/lambda.
    params = {"v1": (sp.Integer(7), sp.Integer(3), sp.Integer(3)),
              "v2": (sp.Integer(8), sp.Integer(2), sp.Integer(3)),
              "v3": (sp.Integer(5), sp.Integer(3), sp.Integer(2))}
    c, x0, y0 = params[v]
    assert c == ab
    mx, my = x0-a, y0
    nx, ny = sp.simplify(mx/lam), sp.simplify(my/lam)
    on2 = sp.simplify(nx**2 + ny**2)
    side_a2 = sp.simplify((nx+a)**2 + ny**2)
    side_b2 = sp.simplify((nx-a)**2 + ny**2)
    assert on2 == on**2 and sp.simplify(lam*nx) == mx and sp.simplify(lam*ny) == my
    r_a = sp.simplify(((mx+a)**2+my**2)/(2*my))
    r_b = sp.simplify(((mx-a)**2+my**2)/(2*my))
    circle_a_residual = sp.simplify((nx+a)**2+ny**2-2*r_a*ny)
    circle_b_residual = sp.simplify((nx-a)**2+ny**2-2*r_b*ny)
    assert my == mf and ny > my > 0
    assert r_a > 0 and r_b > 0 and circle_a_residual == 0 and circle_b_residual == 0
    assert abs(nx) < a and on2 > a**2 and len({side_a2,side_b2,ab**2}) == 3
    audit["exact_acute_scalene_witness"] = {
        "M_minus_O": [sp.sstr(mx), sp.sstr(my)],
        "N_minus_O": [sp.sstr(nx), sp.sstr(ny)],
        "NA_squared": sp.sstr(side_a2), "NB_squared": sp.sstr(side_b2), "AB_squared": sp.sstr(ab**2),
        "circle_radii_at_A_and_B": [sp.sstr(r_a), sp.sstr(r_b)],
        "tests": ["|N_x|<AB/2", "ON^2>(AB/2)^2", "side squares pairwise distinct", "M=lambda*N, 0<lambda<1", "positive tangent-circle radii; both circles pass through M and N"],
    }
    return proof + final, audit


def da02_answer(v: str, givens: dict) -> tuple[str, dict]:
    c = sp.sympify(givens["AB"])
    b = sp.sympify(givens["AC"])
    scale = sp.simplify(c / 10)
    assert sp.simplify(b / 8) == scale and b != c and scale > 0
    answer = sp.simplify(abs(b-c))
    base = BASE_BY_SOURCE["DA02"]["answer"]
    marker = "\n\nHere b=8 and c=10, so TK=2."
    assert marker in base
    proof = base.split(marker, 1)[0]
    # Keep the complete general proof; the problem stipulates an interior T.
    # The explicit v0 Fermat-point witness is not needed for the conditional result.
    final = (
        f"\n\nFor this variant, b=AC={sp.sstr(b)} and c=AB={sp.sstr(c)}. "
        f"The unequal-side condition holds, so the second intersection is distinct, and the proven relation gives "
        f"TK=|b−c|=|{sp.sstr(c)}−{sp.sstr(b)}|={sp.sstr(answer)}."
    )
    return proof + final, {
        "homothety_scale_from_v0": sp.sstr(scale), "AB": sp.sstr(c), "AC": sp.sstr(b),
        "AB_neq_AC": True, "exact_answer": sp.sstr(answer),
        "existence_branch": "positive homothety of audited v0 Fermat configuration; T remains interior",
    }


def db02_answer(v: str, givens: dict) -> tuple[str, dict]:
    a = sp.sympify(givens["BC"])
    c = sp.sympify(givens["AB"])
    b = sp.sympify(givens["AC"])
    scale = sp.simplify(a / 12)
    assert sp.simplify(c / 7) == scale and sp.simplify(b / 11) == scale and scale > 0
    p = sp.simplify(c**2/a)
    cq = sp.simplify(b**2/a)
    qx = sp.simplify(a-cq)
    bx = sp.simplify(6*scale)
    assert 0 < p < a and 0 < cq < a
    proof = f"""A dilation of the audited v0 configuration by the positive factor s={sp.sstr(scale)} preserves all the angles, interior points, and midpoint conditions. To see the coordinates and intersection parameter directly, take
B=(0,0), C=(12s,0), A=(3s,2√10 s).
Then AB=7s, AC=11s, and BC=12s, exactly the givens in this variant.

From ∠PAB=∠BCA and ∠ABP=∠ABC, triangles ABP and CBA are similar; likewise triangles ACQ and BCA are similar. Therefore BP=AB²/BC=49s/12 and CQ=AC²/BC=121s/12. Both lie strictly inside BC because 0<49/12<12 and 0<121/12<12. Thus P=(49s/12,0) and Q=(23s/12,0).

Since P and Q are the midpoints of AM and AN,
M=2P−A=(31s/6,−2√10 s),  N=2Q−A=(5s/6,−2√10 s).
Write the intersection as X=t(M−B)=C+t(N−C). The equal vertical coordinates give the same parameter t on both lines. The horizontal coordinates then give
(31s/6)t=12s−(67s/6)t,
so t=36/49. The denominator is nonzero, and 0<t<1, proving that X is the unique intersection and lies inside both segments BM and CN.

Finally,
BM²=(31s/6)²+(2√10 s)²=(2401/36)s²,
so BM=49s/6 and BX=t·BM=(36/49)(49s/6)=6s={sp.sstr(bx)}."""
    return proof, {
        "homothety_scale_from_v0": sp.sstr(scale), "BP": sp.sstr(p), "CQ": sp.sstr(cq),
        "P_interior": True, "Q_interior": True, "intersection_parameter": "36/49",
        "exact_answer": sp.sstr(bx),
    }


def db06_answer(v: str, givens: dict) -> tuple[str, dict]:
    vals = {k: sp.sympify(givens[k]) for k in ("AB_squared","BC_squared","CD_squared","DA_squared","AC_squared","BD_squared")}
    scale2 = sp.simplify(vals["AB_squared"] / 4)
    scale = sp.sqrt(scale2)
    refs = {"AB_squared":4,"BC_squared":5,"CD_squared":10,"DA_squared":8,"AC_squared":12,"BD_squared":sp.Rational(40,3)}
    assert all(sp.simplify(vals[k] / refs[k]) == scale2 for k in refs)
    assert sp.simplify(vals["AB_squared"]*vals["CD_squared"]-vals["BC_squared"]*vals["DA_squared"]) == 0
    four = sp.simplify(scale2 * sp.Rational(5,3))
    answer = sp.simplify(four/4)
    base = BASE_BY_SOURCE["DB06"]["answer"]
    marker1 = "First observe the construction-relevant side-product equality\nAB·CD = √(4·10) = √(5·8) = BC·DA.\n"
    assert marker1 in base
    marker2 = "Finally, for any four position vectors a,b,c,d, direct expansion gives\n"
    assert marker2 in base
    body = base[base.index(marker1) + len(marker1):base.index(marker2)]
    vector = f"""Finally, for any four position vectors a,b,c,d, direct expansion gives
|b+d−a−c|² = |a−b|²+|b−c|²+|c−d|²+|d−a|²−|a−c|²−|b−d|².
Since X=(b+d)/2 and Y=(a+c)/2, this becomes
4XY²=AB²+BC²+CD²+DA²−AC²−BD².

All six squared lengths in this variant are s² times the v0 values, with s²={sp.sstr(scale2)}. Therefore
4XY²=s²(4+5+10+8−12−40/3)={sp.sstr(four)},
and XY²={sp.sstr(answer)}."""
    proof = (
        f"The six squared lengths are all s² multiples of the v0 values, where s²={sp.sstr(scale2)}. "
        "Consequently AB·CD=BC·DA, the exact side-product condition used below.\n\n" + body + vector
    )
    return proof, {
        "homothety_scale_squared_from_v0": sp.sstr(scale2),
        "side_product_left_squared": sp.sstr(vals["AB_squared"]*vals["CD_squared"]),
        "side_product_right_squared": sp.sstr(vals["BC_squared"]*vals["DA_squared"]),
        "four_XY_squared": sp.sstr(four), "exact_answer": sp.sstr(answer),
        "interior_and_cyclic_branch": "positive homothety of audited convex cyclic v0 configuration",
    }


PROMPT_REPLACEMENTS = {
    ("H01","v1"): [("BC=12","BC=22"),("AM=10","AM=13")],
    ("H01","v2"): [("BC=12","BC=18"),("AM=10","AM=11")],
    ("H01","v3"): [("BC=12","BC=20"),("AM=10","AM=13")],
    ("H02","v1"): [("BC=16","BC=18"),("AM=10","AM=2*sqrt(34)"),("AK=8","AK=10"),("BD1=6","BD1=5"),("BD2=9","BD2=7")],
    ("H02","v2"): [("BC=16","BC=16"),("AM=10","AM=sqrt(109)"),("AK=8","AK=10"),("BD1=6","BD1=6"),("BD2=9","BD2=10")],
    ("H02","v3"): [("BC=16","BC=16"),("AM=10","AM=sqrt(146)"),("AK=8","AK=11"),("BD1=6","BD1=5"),("BD2=9","BD2=8")],
    ("H07","v1"): [("AB=8","AB=7"),("ON=8*sqrt(10)/5","ON=49*sqrt(37)/74")],
    ("H07","v2"): [("AB=8","AB=8"),("ON=8*sqrt(10)/5","ON=16*sqrt(13)/13")],
    ("H07","v3"): [("AB=8","AB=5"),("ON=8*sqrt(10)/5","ON=25*sqrt(17)/34"),("MF=3","MF=2")],
    ("DA02","v1"): [("AB=10","AB=25/2"),("AC=8","AC=10")],
    ("DA02","v2"): [("AB=10","AB=20/3"),("AC=8","AC=16/3")],
    ("DA02","v3"): [("AB=10","AB=5"),("AC=8","AC=4")],
    ("DB02","v1"): [("AB=7","AB=21/2"),("AC=11","AC=33/2"),("BC=12","BC=18")],
    ("DB02","v2"): [("AB=7","AB=21"),("AC=11","AC=33"),("BC=12","BC=36")],
    ("DB02","v3"): [("AB=7","AB=14/3"),("AC=11","AC=22/3"),("BC=12","BC=8")],
    ("DB06","v1"): [("AB²=4","AB²=25/4"),("BC²=5","BC²=125/16"),("CD²=10","CD²=125/8"),("DA²=8","DA²=25/2"),("AC²=12","AC²=75/4"),("BD²=40/3","BD²=125/6")],
    ("DB06","v2"): [("AB²=4","AB²=1"),("BC²=5","BC²=5/4"),("CD²=10","CD²=5/2"),("DA²=8","DA²=2"),("AC²=12","AC²=3"),("BD²=40/3","BD²=10/3")],
    ("DB06","v3"): [("AB²=4","AB²=64/9"),("BC²=5","BC²=80/9"),("CD²=10","CD²=160/9"),("DA²=8","DA²=128/9"),("AC²=12","AC²=64/3"),("BD²=40/3","BD²=640/27")],
}

PROMPT_GIVEN_LABELS = {
    "H01": [("BC", "BC"), ("AM", "AM")],
    "H02": [("BC", "BC"), ("AM", "AM"), ("AK", "AK"), ("BD1", "BD1"), ("BD2", "BD2")],
    "H07": [("AB", "AB"), ("ON", "ON"), ("MF", "MF")],
    "DA02": [("AB", "AB"), ("AC", "AC")],
    "DB02": [("AB", "AB"), ("AC", "AC"), ("BC", "BC")],
    "DB06": [("AB_squared", "AB²"), ("BC_squared", "BC²"), ("CD_squared", "CD²"),
             ("DA_squared", "DA²"), ("AC_squared", "AC²"), ("BD_squared", "BD²")],
}


BASE = json.loads(BASE_PATH.read_text())
BASE_BY_SOURCE = {row["source"]: row for row in BASE}
VARIANTS = load_jsonl(VARIANTS_PATH)
VARIANT_BY_ID = {(row["id"],row["variant"]): row for row in VARIANTS if row.get("split")=="train"}
AUDITS = {row["id"]: row for row in json.loads(AUDITS_PATH.read_text())}


def answer_for(source: str, v: str, givens: dict) -> tuple[str, dict]:
    if source == "H01":
        m=sp.Rational(givens["BC"])/2; t=sp.sympify(givens["AM"])
        gap=sp.simplify(t**2-m**2)
        u=sp.sympify(VARIANT_BY_ID[(source,v)]["params"]["u"])
        x=sp.simplify(t*(1-u**2)/(1+u**2))
        side_squares={sp.simplify((2*m)**2),sp.simplify(t**2+m**2+2*m*x),sp.simplify(t**2+m**2-2*m*x)}
        assert gap>0 and 0<x<m and len(side_squares)==3
        return h01_answer(v,givens), {"m":sp.sstr(m),"t":sp.sstr(t),"u_generator":sp.sstr(u),"x_witness":sp.sstr(x),"acute_A_dot":sp.sstr(gap),"side_squares_pairwise_distinct":True,"exact_answer":sp.sstr(t-m**2/t)}
    if source == "H02": return h02_proof(v,givens)
    if source == "H07": return h07_answer(v,givens)
    if source == "DA02": return da02_answer(v,givens)
    if source == "DB02": return db02_answer(v,givens)
    if source == "DB06": return db06_answer(v,givens)
    raise AssertionError(source)


def build() -> None:
    assert len(BASE)==32 and len(BASE_BY_SOURCE)==32
    assert not ({r["source"] for r in BASE}&HELDOUT)
    assert all(AUDITS[s]["status"]=="accept" and all(AUDITS[s][k] is True for k in ("numeric","true_relation","proof","use","branches_checked")) for s in SOURCES)
    assert all(s in BASE_BY_SOURCE for s in SOURCES)
    multi=[dict(row) for row in BASE]
    repeat=[dict(row) for row in BASE]
    checks=[]
    for source in SOURCES:
        source_base=BASE_BY_SOURCE[source]
        for v in ("v1","v2","v3"):
            variant=VARIANT_BY_ID[(source,v)]
            assert variant["problem"] and variant["answer_exact"]
            assert variant["augmentation"] in ("shape","similarity")
            prompt=pmap(source_base["prompt"],PROMPT_REPLACEMENTS[(source,v)])
            if source=="H07":
                ambiguous="Two circles tangent to line AB at A and B intersect at M and N on the same side of AB, with M closer to AB than N."
                explicit="The first circle is tangent to line AB at A, and the second circle is tangent to line AB at B. The circles intersect at M and N on the same side of AB, with M closer to AB than N."
                assert prompt.count(ambiguous)==1
                prompt=prompt.replace(ambiguous,explicit)
            answer,branch=answer_for(source,v,variant["givens"])
            expected=sp.simplify(sp.sympify(variant["answer_exact"]))
            assert sp.simplify(sp.sympify(branch["exact_answer"])-expected)==0,(source,v,branch,variant["answer_exact"])
            for key,label in PROMPT_GIVEN_LABELS[source]:
                assert f"{label}={variant['givens'][key]}" in prompt, (source,v,key,variant["givens"][key])
            if source=="DA02":
                assert "angle BAC=60 degrees" in prompt
            assert "日本語" not in prompt and not re.search(r"[\u3040-\u30ff\u3400-\u9fff]",prompt+answer)
            assert prompt!=source_base["prompt"] and answer
            assert sp.sstr(expected) in answer, (source,v,sp.sstr(expected))
            assert len(answer.split()) < 1200, (source,v,"answer exceeds 1200 words")
            row_id=f"external-{source}-{v}-audited"
            multi.append({"id":row_id,"source":source,"prompt":prompt,"answer":answer})
            repeat.append({"id":f"repeat-{source}-{v}-exact-v0","source":source,"prompt":source_base["prompt"],"answer":source_base["answer"]})
            checks.append({
                "source":source,"variant":v,"variant_problem_hash":digest_bytes(variant["problem"].encode()),
                "variant_answer_exact":variant["answer_exact"],"derived_answer_exact":sp.sstr(expected),
                "prompt_givens":variant["givens"],"prompt_replacements":PROMPT_REPLACEMENTS[(source,v)],
                "source_v0_audit_status":AUDITS[source]["status"],"source_v0_decisive_lemma":AUDITS[source]["decisive_lemma"],
                "checks":branch,"row_id":row_id,
                "semantic_prompt_clarification":("first circle tangent at A; second circle tangent at B" if source=="H07" else None),
            })
    assert len(multi)==50 and len(repeat)==50
    assert len({r["id"] for r in multi})==50 and len({r["id"] for r in repeat})==50
    assert len({r["source"] for r in multi})==32 and len({r["source"] for r in repeat})==32
    assert not ({r["source"] for r in multi}|{r["source"] for r in repeat}) & HELDOUT
    for source in SOURCES:
        assert sum(r["source"]==source for r in multi)==4
        assert sum(r["source"]==source for r in repeat)==4
    assert [r["source"] for r in multi] == [r["source"] for r in repeat]
    # Exact-v0 repeat slots preserve the common base's text byte-for-byte.
    for source in SOURCES:
        b=BASE_BY_SOURCE[source]
        for v in ("v1","v2","v3"):
            r=next(x for x in repeat if x["id"]==f"repeat-{source}-{v}-exact-v0")
            assert r["prompt"]==b["prompt"] and r["answer"]==b["answer"]

    model=json.loads(MODEL_PATH.read_text())
    tokenizer=AutoTokenizer.from_pretrained(model["snapshot"],local_files_only=True)
    def tok(rows):
        out=[]
        for row in rows:
            prompt=tokenizer.apply_chat_template([{"role":"user","content":row["prompt"]}],tokenize=False,add_generation_prompt=True,enable_thinking=False)
            full=tokenizer.apply_chat_template([{"role":"user","content":row["prompt"]},{"role":"assistant","content":row["answer"]}],tokenize=False,enable_thinking=False)
            assert full.startswith(prompt)
            answer_text=full[len(prompt):].rstrip()
            pids=tokenizer.encode(prompt,add_special_tokens=False)
            aids=tokenizer.encode(answer_text,add_special_tokens=False)
            assert aids[-1]==tokenizer.eos_token_id and len(aids)>20
            assert len(pids)+len(aids)<=8192,row["id"]
            out.append({"id":row["id"],"source":row["source"],"prompt_tokens":len(pids),"assistant_tokens_including_eos":len(aids),"sequence_tokens":len(pids)+len(aids)})
        return out
    multi_tok=tok(multi); repeat_tok=tok(repeat)
    def totals(rows):
        return {
            "rows":len(rows),
            "prompt_tokens":sum(x["prompt_tokens"] for x in rows),
            "assistant_tokens_including_eos":sum(x["assistant_tokens_including_eos"] for x in rows),
            "sequence_tokens":sum(x["sequence_tokens"] for x in rows),
            "max_sequence_tokens":max(x["sequence_tokens"] for x in rows),
        }
    multi_path=OUT/"train-50-six-source-v1-v3.json"
    repeat_path=OUT/"train-50-six-source-v0-repeat-control.json"
    multi_path.write_text(json.dumps(multi,ensure_ascii=False,indent=2)+"\n")
    repeat_path.write_text(json.dumps(repeat,ensure_ascii=False,indent=2)+"\n")
    audit={
        "status":"CPU-only candidate audit complete; no training/evaluation performed",
        "sources":list(SOURCES),"heldout_sources_excluded":sorted(HELDOUT),
        "common_base_rows":32,"new_rows_per_arm":18,"rows_per_arm":50,"distinct_sources_per_arm":32,
        "variant_checks":checks,
        "base_dataset_sha256":sha256(BASE_PATH),"variants_source_sha256":sha256(VARIANTS_PATH),"source_audits_sha256":sha256(AUDITS_PATH),
        "multi_answer_tokens_including_eos":sum(x["assistant_tokens_including_eos"] for x in multi_tok),
        "repeat_answer_tokens_including_eos":sum(x["assistant_tokens_including_eos"] for x in repeat_tok),
        "token_difference_percent_of_repeat":round(100*(sum(x["assistant_tokens_including_eos"] for x in multi_tok)-sum(x["assistant_tokens_including_eos"] for x in repeat_tok))/sum(x["assistant_tokens_including_eos"] for x in repeat_tok),4),
        "max_sequence_tokens":max(x["sequence_tokens"] for x in multi_tok+repeat_tok),
        "token_totals": {"multi":totals(multi_tok),"repeat_control":totals(repeat_tok)},
        "sequence_token_difference_percent_of_repeat":round(100*(totals(multi_tok)["sequence_tokens"]-totals(repeat_tok)["sequence_tokens"])/totals(repeat_tok)["sequence_tokens"],4),
        "cjk_chars":0,
    }
    (OUT/"variant-audit.json").write_text(json.dumps(audit,ensure_ascii=False,indent=2)+"\n")
    (OUT/"token-audit.json").write_text(json.dumps({"tokenizer_revision":model["revision"],"method":"Qwen chat template, CPU only, assistant-through-EOS exactly as train.py","multi":multi_tok,"repeat_control":repeat_tok},ensure_ascii=False,indent=2)+"\n")
    hashes={p.name:sha256(p) for p in [multi_path,repeat_path,OUT/"variant-audit.json",OUT/"token-audit.json",OUT/"PROTOCOL.md"] if p.exists()}
    hashes.update({"base32_sha256":sha256(BASE_PATH),"benchmark_training_variants_sha256":sha256(VARIANTS_PATH),"v0_audits_sha256":sha256(AUDITS_PATH)})
    (OUT/"hashes.json").write_text(json.dumps(hashes,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"rows":50,"multi_sha256":hashes[multi_path.name],"repeat_sha256":hashes[repeat_path.name],"multi_answer_tokens":audit["multi_answer_tokens_including_eos"],"repeat_answer_tokens":audit["repeat_answer_tokens_including_eos"],"max_sequence_tokens":audit["max_sequence_tokens"]},indent=2))


if __name__=="__main__":
    OUT.mkdir(parents=True,exist_ok=True)
    build()
