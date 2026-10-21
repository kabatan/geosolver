#!/usr/bin/env python3
"""Freeze a third, collision-checked nine-job numeric evaluation set.

CPU-only: canonical exact generators prepare the problems; separate exact
checks validate the decisive answer formula and the stated construction
branches. Only frozen problem inputs/keys are read for fresh1/fresh2 collision
checks. No model generations are read or produced.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
HELDOUT_DIR = HERE.parent
FRESH2_DIR = HELDOUT_DIR / "followup-fresh2"
AUTHORING_DIR = ROOT / "benchmarks/humpty_configurations_v2/authoring"
ENGLISH_DIR = ROOT / "docs/research/qwen35-diverse-sft-2026-09-24"
sys.path.insert(0, str(ROOT))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BASE = load_module("fresh3_near_transfer_helpers", HELDOUT_DIR / "freeze_near_transfer.py")
GEN = BASE.GEN
PREP = BASE.PREP
ENGLISH = BASE.ENGLISH
S = GEN.s

IDS = ["H03", "H04", "H08", "H14", "H15", "H01", "H02", "H07", "H13"]
TARGET_IDS = {"H03", "H04", "H08", "H14", "H15"}
RETENTION_IDS = {"H01", "H02", "H07", "H13"}
GROUPS = {
    "H03": "orthocenter_median_projection",
    "H04": "orthocenter_median_projection",
    "H14": "orthocenter_median_projection",
    "H08": "tangent_circle_reflection_near_transfer",
    "H15": "three_reflection_midpoint_independent_case",
}

# Deterministic tuples. Each tuple uses at least one parameter outside its
# canonical finite sampling domain; the exact visible givens are then checked
# against every source v0-v3 row and both earlier frozen numeric sets.
FRESH3_VALUES = {
    "H03": (12, -7, 5, 2, 7),
    "H04": (12, 1, 12),
    "H08": (2, 8, 4, 5),
    "H14": (18, 16, 12),
    "H15": (10, 4),
    "H01": (14, 17, S.Rational(1, 3)),
    "H02": (15, 6, 14, 3, 7),
    "H07": (11, 2, 3),
    "H13": (11, (5, 12, 13), 1),
}


class FixedChoices:
    """Replay one fixed parameter tuple through a canonical generator."""

    def __init__(self, values):
        self.values = iter(values)

    def choice(self, _choices):
        return next(self.values)


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(name: str, value):
    path = HERE / name
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    return sha_file(path)


def is_positive(value):
    return S.simplify(value).is_positive is True


def is_negative(value):
    return S.simplify(value).is_negative is True


def require_positive(value, label):
    value = S.simplify(value)
    assert value.is_positive is True, (label, value)


def require_negative(value, label):
    value = S.simplify(value)
    assert value.is_negative is True, (label, value)


def vector_equal(left, right):
    return all(S.simplify(left[index] - right[index]) == 0 for index in range(left.rows))


def check_acute_scalene(a, b, c):
    dots = [
        (b - a).dot(c - a),
        (a - b).dot(c - b),
        (a - c).dot(b - c),
    ]
    for index, value in enumerate(dots):
        require_positive(value, f"acute-angle-dot-{index}")
    side_squares = [GEN.norm(a - b), GEN.norm(b - c), GEN.norm(c - a)]
    for i in range(3):
        for j in range(i + 1, 3):
            assert S.simplify(side_squares[i] - side_squares[j]) != 0, side_squares
    return {
        "acute_triangle": True,
        "scalene_triangle": True,
        "positive_angle_dot_products": [str(S.simplify(x)) for x in dots],
    }


def check_h01(params):
    m, t, u = map(S.Rational, params)
    a = GEN.pt(t * (1 - u**2) / (1 + u**2), 2 * t * u / (1 + u**2))
    b, c, mid = GEN.pt(-m, 0), GEN.pt(m, 0), GEN.pt(0, 0)
    out = check_acute_scalene(a, b, c)
    h = GEN.sorthocenter(a, b, c)
    foot = GEN.sfoot(h, mid, a)
    lam = S.simplify(foot.dot(a) / GEN.norm(a))
    assert is_positive(lam) and is_positive(1 - lam), ("projection-on-segment", lam)
    assert S.simplify(lam - m**2 / t**2) == 0
    out["orthocenter_projection_is_on_median_segment"] = True
    out["projection_parameter"] = str(lam)
    return out


def check_h02(params):
    w, ax, ay, i1, i2 = map(S.Rational, params)
    a, b, c = GEN.pt(ax, ay), GEN.pt(-w, 0), GEN.pt(w, 0)
    out = check_acute_scalene(a, b, c)
    k = GEN.sfoot(a, b, c)
    assert is_positive(GEN.norm(k - b) - GEN.norm(k - c)), "BK>KC"
    d1, d2 = GEN.pt(-w + i1, 0), GEN.pt(-w + i2, 0)
    assert is_positive(i1) and is_positive(i2 - i1) and is_positive(2 * w - i2)
    for index, d in enumerate((d1, d2), start=1):
        circle_abd = GEN.scircle(a, b, d)
        circle_acd = GEN.scircle(a, c, d)
        u = GEN.ssecond(a, c, circle_abd, a)
        v = GEN.ssecond(a, b, circle_acd, a)
        assert S.simplify((u - a).dot(u - a)) != 0
        assert S.simplify((v - a).dot(v - a)) != 0
        z = GEN.scenter(GEN.scircle(a, u, v))
        assert vector_equal(GEN.sfoot(z, b, c), d), index
    out.update({
        "foot_branch_BK_greater_than_KC": True,
        "D1_D2_strictly_ordered_inside_BC": True,
        "both_center_constructions_noncollinear_and_finite": True,
    })
    return out


def check_h03(params):
    target, bx, cx, ax, ay = map(S.Rational, params)
    a, b, c = GEN.pt(ax, ay), GEN.pt(bx, 0), GEN.pt(cx, 0)
    out = check_acute_scalene(a, b, c)
    o, h = GEN.scenter(GEN.scircle(a, b, c)), GEN.sorthocenter(a, b, c)
    oh = GEN.slength(o, h)
    require_positive(oh, "OH")
    scale = target / oh
    assert is_positive(scale)
    a, b, c = [GEN.simp(scale * point) for point in (a, b, c)]
    o, h = GEN.scenter(GEN.scircle(a, b, c)), GEN.sorthocenter(a, b, c)
    assert S.simplify(GEN.slength(o, h) - target) == 0
    ps = []
    for vertex, q, r in ((a, b, c), (b, c, a), (c, a, b)):
        lvq, lvr = GEN.slength(vertex, q), GEN.slength(vertex, r)
        assert S.simplify(lvq - lvr) != 0
        ki = GEN.simp((lvr * q + lvq * r) / (lvq + lvr))
        ke = GEN.simp((lvr * q - lvq * r) / (lvr - lvq))
        mid = (q + r) / 2
        point = GEN.ssecond(vertex, mid, GEN.scircle(vertex, ki, ke), vertex)
        assert vector_equal(point, GEN.sfoot(h, vertex, mid))
        ps.append(point)
    z = GEN.scenter(GEN.scircle(*ps))
    centroid = (a + b + c) / 3
    assert vector_equal(z, (h + centroid) / 2)
    out["positive_OH_target_and_all_three_second_intersections_are_projection_branches"] = True
    out["circumcenter_relation_reconstructed_exactly"] = True
    return out


def check_h04(params):
    bc, ax, ay2 = map(S.Rational, params)
    a, b, c = GEN.pt(ax, S.sqrt(ay2)), GEN.pt(0, 0), GEN.pt(bc, 0)
    out = check_acute_scalene(a, b, c)
    mid, h = S.simplify((b + c) / 2), GEN.sorthocenter(a, b, c)
    p = GEN.sfoot(h, a, mid)
    perpendicular_bisector_mid = S.simplify((a + p) / 2)
    t = GEN.sline(perpendicular_bisector_mid,
                  perpendicular_bisector_mid + GEN.rot(a - p), b, c)
    assert S.simplify(t[1]) == 0
    require_negative(t[0], "T_before_B")
    assert S.simplify(-t[0] - GEN.slength(b, t)) == 0
    out["perpendicular_bisector_intersection_is_before_B"] = True
    out["T_B_C_order_matches_problem_text"] = True
    return out


def check_h07(params):
    c, x0, y0 = map(S.Rational, params)
    a, b, m_point = GEN.pt(0, 0), GEN.pt(c, 0), GEN.pt(x0, y0)
    r1 = S.simplify((x0**2 + y0**2) / (2 * y0))
    r2 = S.simplify(((x0 - c)**2 + y0**2) / (2 * y0))
    w = S.Matrix([0, -2 * r1, 0])
    z = S.Matrix([-2 * c, -2 * r2, c**2])
    n = GEN.sother_circle(w, z, m_point)
    out = check_acute_scalene(n, a, b)
    require_positive(m_point[1], "M_above_AB")
    require_positive(n[1] - m_point[1], "M_closer_to_AB_than_N")
    require_positive(c - x0, "M_foot_inside_AB")
    o = S.simplify((a + b) / 2)
    f = GEN.sfoot(m_point, a, b)
    c2 = GEN.ssecond(m_point, m_point + GEN.pt(1, 0), w, m_point)
    d2 = GEN.ssecond(m_point, m_point + GEN.pt(1, 0), z, m_point)
    e = GEN.sline(a, c2, b, d2)
    p, q = GEN.sline(a, n, c2, d2), GEN.sline(b, n, c2, d2)
    assert vector_equal((p + q) / 2, m_point)
    assert vector_equal(e, GEN.sreflect(m_point, a, b))
    require_positive(GEN.slength(o, n), "ON_positive")
    assert S.simplify(f[1]) == 0
    out.update({
        "two_tangent_circle_intersection_order_checked": True,
        "M_is_the_nearer_intersection": True,
        "EPQ_construction_finite_and_symmetric_about_M": True,
    })
    return out


def check_h08(params):
    px, qx, ax, ay = map(S.Rational, params)
    p, q, a = GEN.pt(px, 0), GEN.pt(qx, 0), GEN.pt(ax, ay)
    out = check_acute_scalene(a, p, q)
    r1 = S.simplify(((ax - px)**2 + ay**2) / (2 * ay))
    r2 = S.simplify(((ax - qx)**2 + ay**2) / (2 * ay))
    w = S.Matrix([-2 * px, -2 * r1, px**2])
    z = S.Matrix([-2 * qx, -2 * r2, qx**2])
    b = GEN.sother_circle(w, z, a)
    require_positive(b[1], "B_above_PQ")
    assert S.simplify(b - a) != GEN.pt(0, 0)
    c = GEN.sreflect(b, p, q)
    area2 = S.simplify(GEN.scross(p - a, c - a))
    assert area2 != 0
    out.update({
        "A_B_on_both_tangent_circles": True,
        "B_is_the_second_intersection_on_the_nearer_branch": True,
        "reflected_C_gives_nonzero_triangle_area": True,
    })
    return out


def check_h13(params):
    bc, tri, scale = params
    bc, scale = S.Rational(bc), S.Rational(scale)
    tri = tuple(S.Rational(x) for x in tri)
    du, dv = tri[0] * scale, tri[1] * scale
    a = GEN.pt(bc - du, dv)
    b, c = GEN.pt(0, 0), GEN.pt(bc, 0)
    out = check_acute_scalene(a, b, c)
    mid = S.simplify((a + c) / 2)
    circle = GEN.scircle(b, mid, c)
    k = GEN.sline(c, c + GEN.rot(c - GEN.scenter(circle)),
                  b, b + GEN.rot(c - b))
    side_a = GEN.scross(c - b, a - b)
    side_k = GEN.scross(c - b, k - b)
    assert S.simplify(side_a * side_k).is_negative is True
    j = GEN.sline(a, k, b, mid)
    for start, end in ((a, k), (b, mid)):
        parameter = S.simplify((j - start).dot(end - start) / GEN.norm(end - start))
        assert is_positive(parameter) and is_positive(1 - parameter), parameter
    z = GEN.scenter(GEN.scircle(b, j, k))
    assert S.simplify(GEN.scross(z - a, c - a)) == 0
    out.update({
        "K_is_on_the_side_of_BC_opposite_A": True,
        "J_is_inside_both_defining_segments": True,
        "BJK_center_lies_on_AC": True,
    })
    return out


def check_h14(params):
    w_, ax, ay = map(S.Rational, params)
    a, b, c = GEN.pt(ax, ay), GEN.pt(-w_, 0), GEN.pt(w_, 0)
    out = check_acute_scalene(a, b, c)
    m, h = S.simplify((b + c) / 2), GEN.sorthocenter(a, b, c)
    circumcircle = GEN.scircle(a, b, c)

    def radial(center, radius_squared):
        return S.Matrix([-2 * center[0], -2 * center[1], GEN.norm(center) - radius_squared])

    d = GEN.ssecond(a, b, radial(c, GEN.norm(c - a)), a)
    e = GEN.ssecond(a, c, radial(b, GEN.norm(b - a)), a)

    def positive_ray_hit(start, through, circle):
        t = S.symbols("fresh3_ray_t", real=True)
        polynomial = S.factor(GEN.son(start + t * (through - start), circle))
        roots = S.solve(polynomial, t)
        signs = [S.sign(S.simplify(root)) for root in roots]
        assert all(sign in (-1, 1) for sign in signs), (roots, signs)
        positive_roots = [root for root, sign in zip(roots, signs, strict=True) if sign == 1]
        assert len(positive_roots) == 1, (roots, signs)
        root = positive_roots[0]
        point = S.simplify(start + root * (through - start))
        assert S.simplify(GEN.son(point, circle)) == 0
        return point, root

    p, tp = positive_ray_hit(m, d, circumcircle)
    q, tq = positive_ray_hit(m, e, circumcircle)
    require_positive(tp, "MD_positive_ray_branch")
    require_positive(tq, "ME_positive_ray_branch")
    r = GEN.sother_circle(GEN.scircle(b, p, m), GEN.scircle(c, q, m), m)
    foot = GEN.sfoot(h, a, m)
    assert vector_equal(r, foot)
    assert not vector_equal(r, m)
    assert S.simplify(GEN.sarea(a, h, r)).is_positive is True
    out.update({
        "MD_ME_intersections_use_unique_positive_ray_roots": True,
        "R_is_the_non_M_circle_intersection_and_orthocenter_projection": True,
        "AHR_nonzero_area": True,
    })
    return out


def check_h15(params):
    c_, b_ = map(S.Rational, params)
    assert S.simplify(c_ - b_) != 0
    a, b, c = GEN.pt(0, 0), GEN.pt(c_, 0), GEN.pt(b_ / 2, b_ * S.sqrt(3) / 2)
    assert S.simplify(GEN.scross(b - a, c - a)).is_positive is True
    assert len({str(S.simplify(GEN.norm(a - b))),
                str(S.simplify(GEN.norm(b - c))),
                str(S.simplify(GEN.norm(c - a)))}) == 3
    circle = GEN.scircle(a, b, c)
    x = GEN.sline(b, b + GEN.rot(b - GEN.scenter(circle)),
                  c, c + GEN.rot(c - GEN.scenter(circle)))
    d = GEN.ssecond(a, x, circle, a)
    e = GEN.sreflect(d, b, c)
    b0, c0 = GEN.sreflect(e, a, c), GEN.sreflect(e, a, b)
    line_cross = GEN.scross(b0 - b, c0 - c)
    assert S.simplify(line_cross) != 0
    k = GEN.sline(b, b0, c, c0)
    assert vector_equal(k, (a + d) / 2)
    assert not vector_equal(k, b)
    return {
        "angle_A_exactly_60_degrees_and_triangle_scalene": True,
        "reflection_lines_are_distinct_and_intersect_finitely": True,
        "three_reflection_midpoint_branch_checked_exactly": True,
    }


BRANCH_CHECKERS = {
    "H03": check_h03,
    "H04": check_h04,
    "H08": check_h08,
    "H14": check_h14,
    "H15": check_h15,
    "H01": check_h01,
    "H02": check_h02,
    "H07": check_h07,
    "H13": check_h13,
}


def canonical_givens(cid, problem):
    return {key: S.simplify(value) for key, value in GEN.read_givens(cid, problem).items()}


def json_givens(values):
    return {key: str(S.simplify(value)) for key, value in values.items()}


def json_params(cid, values):
    def convert(value):
        if isinstance(value, tuple):
            return [convert(part) for part in value]
        if isinstance(value, S.Basic):
            return str(value)
        return value
    return {key: convert(value) for key, value in BASE.param_dict(cid, values).items()}


def key_givens(values):
    return {key: S.simplify(S.sympify(value)) for key, value in values.items()}


def main():
    originals, variants, variants_by_id = BASE.load_source_records()
    fresh1_keys = json.loads((HELDOUT_DIR / "answer_key.json").read_text())
    fresh2_keys = json.loads((FRESH2_DIR / "answer_key.json").read_text())
    fresh1_jobs = json.loads((HELDOUT_DIR / "eval_jobs.json").read_text())
    fresh2_jobs = json.loads((FRESH2_DIR / "eval_jobs.json").read_text())
    fresh1_key_by_id = {row["id"]: row for row in fresh1_keys}
    fresh2_key_by_id = {row["id"]: row for row in fresh2_keys}
    fresh1_job_by_id = {row["source_id"]: row for row in fresh1_jobs}
    fresh2_job_by_id = {row["source_id"]: row for row in fresh2_jobs}
    assert set(fresh1_key_by_id) == set(fresh2_key_by_id) == set(IDS)
    assert set(fresh1_job_by_id) == set(fresh2_job_by_id) == set(IDS)
    audits = {row["id"]: row for row in json.loads(BASE.AUDITS.read_text())}

    rows_by_id = {}
    jobs_by_id = {}
    check_rows = []
    for cid in IDS:
        chosen = FRESH3_VALUES[cid]
        raw = GEN.GENERATORS[cid](FixedChoices(chosen))
        assert raw is not None, f"canonical generator rejected {cid} {chosen}"
        row = GEN.checked_record(cid, raw, "fresh3", "followup_fresh3")
        givens = canonical_givens(cid, row["problem"])
        exact_answer = S.simplify(S.sympify(row["answer_exact"]))
        independent_answer = S.simplify(GEN.independent_shape_answer(cid, givens))
        assert S.simplify(exact_answer - independent_answer) == 0, (cid, exact_answer, independent_answer)
        branch_checks = BRANCH_CHECKERS[cid](chosen)
        assert branch_checks and all(branch_checks.values()), (cid, branch_checks)

        known_train_signatures = {
            GEN.signature(cid, old["problem"])
            for old in variants_by_id[cid]
        }
        assert {old["variant"] for old in variants_by_id[cid]} == {"v0", "v1", "v2", "v3"}, cid
        signature = GEN.signature(cid, row["problem"])
        assert signature not in known_train_signatures, (cid, "v0-v3 collision")
        for prior_label, prior_key in (("fresh1", fresh1_key_by_id[cid]), ("fresh2", fresh2_key_by_id[cid])):
            prior_givens = key_givens(prior_key["givens"])
            assert givens != prior_givens, (cid, f"{prior_label} givens collision")
            assert row["problem"] != prior_key["problem"], (cid, f"{prior_label} canonical text collision")

        old_metric_values = BASE.old_visible_metric_values(cid)
        visible_key = BASE.VISIBLE_KEY[cid]
        visible_metric = givens[visible_key]
        assert visible_metric not in old_metric_values, (cid, visible_key, visible_metric)

        row["givens"] = json_givens(givens)
        stage = "near-transfer-fresh3" if cid in TARGET_IDS else "near-retention-fresh3"
        job = PREP.job(row, stage, 0)
        assert job["english_problem"] == ENGLISH.NUMERIC_EN[cid].format(**row["givens"])
        assert not any("\u3040" <= ch <= "\u9fff" for ch in job["english_problem"])
        assert "answer_exact" not in job
        job["evaluation_role"] = "heldout_transfer" if cid in TARGET_IDS else "source_retention_control"
        job["transfer_cluster"] = GROUPS.get(cid)
        for prior_label, prior_job in (("fresh1", fresh1_job_by_id[cid]), ("fresh2", fresh2_job_by_id[cid])):
            assert job["evaluation_role"] == prior_job["evaluation_role"], (cid, prior_label, "role mismatch")
            assert job["english_problem"] != prior_job["english_problem"], (cid, f"{prior_label} English-text collision")
            assert job["seed"] != prior_job["seed"], (cid, f"{prior_label} seed collision")

        training_english_texts = {
            ENGLISH.NUMERIC_EN[cid].format(**old["givens"])
            for old in variants_by_id[cid]
        }
        training_problem_texts = {old["problem"] for old in variants_by_id[cid]}
        assert job["english_problem"] not in training_english_texts, (cid, "v0-v3 English text collision")
        assert row["problem"] not in training_problem_texts, (cid, "v0-v3 canonical text collision")

        rows_by_id[cid] = row
        jobs_by_id[cid] = job
        check_rows.append({
            "id": cid,
            "role": job["evaluation_role"],
            "transfer_cluster": GROUPS.get(cid),
            "generator": f"canonical {cid} exact construction via fixed-choice wrapper",
            "parameters": json_params(cid, chosen),
            "visible_novelty_given": visible_key,
            "visible_novelty_value": str(visible_metric),
            "visible_given_outside_original_finite_parameter_projection": True,
            "generator_internal_construction_assertions": "passed",
            "independent_exact_answer_formula": str(independent_answer),
            "exact_answer_match": True,
            "independent_branch_checks": branch_checks,
            "v0_v3_full_givens_collision": False,
            "fresh1_full_givens_collision": False,
            "fresh2_full_givens_collision": False,
            "v0_v3_canonical_text_collision": False,
            "fresh1_canonical_text_collision": False,
            "fresh2_canonical_text_collision": False,
            "v0_v3_english_text_collision": False,
            "fresh1_english_text_collision": False,
            "fresh2_english_text_collision": False,
            "fresh1_seed_distinct": True,
            "fresh2_seed_distinct": True,
            "signature_sha256": sha_bytes(repr(signature).encode()),
            "canonical_problem_sha256": sha_bytes(row["problem"].encode()),
            "english_problem_sha256": sha_bytes(job["english_problem"].encode()),
            "givens": row["givens"],
            "answer_exact": row["answer_exact"],
        })

    all_jobs = [jobs_by_id[cid] for cid in IDS]
    target_jobs = [jobs_by_id[cid] for cid in IDS if cid in TARGET_IDS]
    retention_jobs = [jobs_by_id[cid] for cid in IDS if cid in RETENTION_IDS]
    answer_key = []
    for cid in IDS:
        row, job = rows_by_id[cid], jobs_by_id[cid]
        answer_key.append({
            "job_id": job["id"],
            "id": cid,
            "role": job["evaluation_role"],
            "transfer_cluster": GROUPS.get(cid),
            "canonical_problem": row["problem"],
            "english_problem": job["english_problem"],
            "givens": row["givens"],
            "answer_exact": row["answer_exact"],
            "params": row["params"],
            "decisive_lemma_expected": audits[cid]["decisive_lemma"],
            "answer_key_is_grader_only": True,
        })

    source_paths = [
        AUTHORING_DIR / "gen_variants.py",
        AUTHORING_DIR / "variant_templates.json",
        AUTHORING_DIR / "h_revision.json",
        AUTHORING_DIR / "da_revision.json",
        AUTHORING_DIR / "db_revision.json",
        AUTHORING_DIR / "verify_h_revision.py",
        AUTHORING_DIR / "verify_da_revision.py",
        AUTHORING_DIR / "verify_db_revision.py",
        ROOT / "benchmarks/humpty_configurations_v2/training_problems.jsonl",
        ROOT / "benchmarks/humpty_configurations_v2/training_variants.jsonl",
        ROOT / "docs/research/qwen35-external-teacher-2026-09-24/audits.json",
        ENGLISH_DIR / "english_templates.py",
        ENGLISH_DIR / "prepare_english.py",
        HELDOUT_DIR / "freeze_near_transfer.py",
        HELDOUT_DIR / "eval_jobs.json",
        HELDOUT_DIR / "answer_key.json",
        HELDOUT_DIR / "hashes.json",
        FRESH2_DIR / "freeze_fresh2.py",
        FRESH2_DIR / "eval_jobs.json",
        FRESH2_DIR / "answer_key.json",
        FRESH2_DIR / "hashes.json",
    ]
    source_hashes = {str(path.relative_to(ROOT)): sha_file(path) for path in source_paths}
    checks = {
        "status": "passed",
        "purpose": "third fresh numeric input set for a later diverse-source teacher comparison",
        "job_count": len(all_jobs),
        "target_ids": [cid for cid in IDS if cid in TARGET_IDS],
        "retention_ids": [cid for cid in IDS if cid in RETENTION_IDS],
        "all_nine_roles_match_fresh1_fresh2": True,
        "all_jobs_use_fixed_unique_per_job_seed": len({job["seed"] for job in all_jobs}) == len(all_jobs),
        "answer_key_absent_from_model_messages": all("answer_exact" not in job for job in all_jobs),
        "v0_v3_givens_and_problem_text_collisions": 0,
        "fresh1_givens_and_problem_text_collisions": 0,
        "fresh2_givens_and_problem_text_collisions": 0,
        "independent_exact_answer_and_branch_checks": "passed for all nine IDs",
        "gpu_used": False,
        "model_outputs_opened": False,
        "evaluation_executed": False,
        "checks_by_id": check_rows,
        "source_hashes": source_hashes,
    }

    jobs_hash = write_json("eval_jobs.json", all_jobs)
    target_hash = write_json("target_eval_jobs.json", target_jobs)
    retention_hash = write_json("retention_control_jobs.json", retention_jobs)
    answer_hash = write_json("answer_key.json", answer_key)
    checks_hash = write_json("construction_checks.json", checks)
    created = {
        "eval_jobs.json": jobs_hash,
        "target_eval_jobs.json": target_hash,
        "retention_control_jobs.json": retention_hash,
        "answer_key.json": answer_hash,
        "construction_checks.json": checks_hash,
        "PROTOCOL.md": sha_file(HERE / "PROTOCOL.md"),
        "freeze_fresh3.py": sha_file(Path(__file__)),
    }
    hash_manifest = {
        "label": "fresh3; nine new exact numeric jobs; no model evaluation performed",
        "created_artifacts_sha256": created,
        "source_artifacts_sha256": source_hashes,
        "runtime": {"python": sys.version.split()[0], "sympy": S.__version__},
        "reproduction": ".venv/bin/python3.12 docs/research/qwen35-external-teacher-2026-09-25/heldout-near-transfer/followup-fresh3/freeze_fresh3.py",
        "candidate_parameter_tuples": {cid: json_params(cid, FRESH3_VALUES[cid]) for cid in IDS},
    }
    hashes_hash = write_json("hashes.json", hash_manifest)
    print(json.dumps({
        "status": "passed",
        "job_count": len(all_jobs),
        "target_ids": [cid for cid in IDS if cid in TARGET_IDS],
        "retention_ids": [cid for cid in IDS if cid in RETENTION_IDS],
        "eval_jobs_sha256": jobs_hash,
        "target_eval_jobs_sha256": target_hash,
        "retention_control_jobs_sha256": retention_hash,
        "answer_key_sha256": answer_hash,
        "construction_checks_sha256": checks_hash,
        "hashes_json_sha256": hashes_hash,
        "gpu_used": False,
        "model_outputs_opened": False,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
