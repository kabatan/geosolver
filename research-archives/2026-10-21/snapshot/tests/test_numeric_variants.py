import hashlib
import json
import runpy
from pathlib import Path

import pytest
import sympy as s

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "benchmarks/humpty_configurations_v2"
G = runpy.run_path(str(DATA / "authoring/gen_variants.py"))


def rows(name):
    return [json.loads(line) for line in (DATA / name).read_text().splitlines()]


def test_templates_reconstruct_all_approved_problems_exactly():
    for row in rows("training_problems.jsonl"):
        spec = G["templates"]()[row["id"]]
        assert spec["template"].format(**spec["base_literals"]) == row["problem"]
        assert (
            hashlib.sha256(row["problem"].encode()).hexdigest() == spec["approved_problem_sha256"]
        )


def test_every_record_preserves_prose_and_has_a_verified_numeric_label():
    originals = {r["id"]: r for r in rows("training_problems.jsonl")}
    train, dev = rows("training_variants.jsonl"), rows("eval_variants.jsonl")
    assert len(train) == 148 and len(dev) == 37
    seen = set()
    for row in train + dev:
        cid = row["id"]
        givens = G["read_givens"](cid, row["problem"])
        sig = G["signature"](cid, row["problem"])
        assert sig not in seen, (cid, row["variant"])
        seen.add(sig)
        assert "求めよ" in row["problem"]
        if row["augmentation"] == "similarity":
            k = s.Rational(row["params"]["scale"])
            assert k > 0
            spec = G["templates"]()[cid]
            for name, value in givens.items():
                assert (
                    s.simplify(
                        value
                        - s.sympify(spec["base_givens"][name])
                        * k ** spec["given_scale_degrees"][name]
                    )
                    == 0
                )
            expected = s.sympify(originals[cid]["answer_exact"]) * k ** spec["answer_scale_degree"]
        elif row["augmentation"] == "shape":
            expected = G["independent_shape_answer"](cid, givens)
        else:
            assert row["problem"] == originals[cid]["problem"]
            expected = s.sympify(originals[cid]["answer_exact"])
        assert s.simplify(s.sympify(row["answer_exact"]) - expected) == 0


def test_corrupted_definitions_questions_and_extra_hints_are_rejected():
    originals = {r["id"]: r for r in rows("training_problems.jsonl")}
    cases = [
        ("H07", originals["H07"]["problem"].replace("E=AC∩BD", "E=AP∩BQ")),
        ("DA09", originals["DA09"]["problem"].replace("の内心をIとする", "")),
        ("DB15", originals["DB15"]["problem"].replace("DTを求めよ", "")),
        ("HX01", originals["HX01"]["problem"] + "J,A,Lは共線である。"),
    ]
    for cid, problem in cases:
        with pytest.raises(ValueError):
            G["read_givens"](cid, problem)


def test_scaling_preserves_definition_and_question():
    originals = {r["id"]: r for r in rows("training_problems.jsonl")}
    for cid, required in [
        ("DA09", ["内心をIとする", "PA<PB", "点をPとする", "CTの長さを求めよ"]),
        ("DB15", ["のときDTを求めよ"]),
    ]:
        result = G["scaled_variant"](originals[cid], None, s.Rational(3, 2))
        for text in required:
            assert text in result["problem"]


def test_h07_explicit_geometry_distinguishes_the_wrong_definition():
    a, b = s.Point(0, 0), s.Point(6, 0)
    n = s.Point(s.Rational(6, 5), s.Rational(18, 5))
    horizontal = s.Line(s.Point(0, 2), s.Point(1, 2))
    p = s.Line(a, n).intersection(horizontal)[0]
    q = s.Line(b, n).intersection(horizontal)[0]
    correct_e = s.Line(a, s.Point(-2, 2)).intersection(s.Line(b, s.Point(10, 2)))[0]
    wrong_e = s.Line(a, p).intersection(s.Line(b, q))[0]
    assert abs(s.Triangle(correct_e, p, q).area) == s.Rational(16, 3)
    assert abs(s.Triangle(wrong_e, p, q).area) == s.Rational(32, 15)


def test_scalene_domain_is_not_silently_weakened():
    # Two historical HX01 variants were isosceles despite the approved prose.
    for params in [
        {"bc": "6", "ax": "3", "ay_num": "5"},
        {"bc": "6", "ax": "2", "ay_num": "5"},
    ]:
        assert G["gen_HX01"](G["Replay"]("HX01", params)) is None


def test_repaired_original_witnesses_are_scalene_and_keep_simple_answers():
    h = runpy.run_path(str(DATA / "authoring/verify_h_revision.py"))["build"]()
    da = runpy.run_path(str(DATA / "authoring/verify_da_revision.py"))["construct"]()
    for cid, witness, names in [
        ("H07", h["H07"], ["N", "A", "B"]),
        ("H08", h["H08"], ["A", "P", "Q"]),
        ("DA05", da["DA05"], ["A", "B", "C"]),
    ]:
        points = [s.Matrix([s.sympify(v) for v in witness["points"][key]]) for key in names]
        lengths = sorted(float((points[i] - points[(i + 1) % 3]).norm()) for i in range(3))
        assert min(lengths[1] - lengths[0], lengths[2] - lengths[1]) > 1e-8, cid
    assert s.sympify(h["H07"]["answer"]) == 9
    assert s.sympify(h["H08"]["answer"]) == s.Rational(27, 2)
    assert abs(da["DA05"]["answer"] - 5) < 1e-8
