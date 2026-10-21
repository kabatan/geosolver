#!/usr/bin/env python3
"""Freeze a geometry-family near-transfer split without reading d1 or model outputs.

All generated records, jobs, labels, and reports are written beside this script.
The geometry code is imported read-only from the canonical authoring generator;
the local ChoiceSequence wrapper permits preregistered fresh parameter values.
"""

from __future__ import annotations

import hashlib
import importlib.util
import itertools
import json
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))

GEN_PATH = ROOT / "benchmarks/humpty_configurations_v2/authoring/gen_variants.py"
TRAIN_PROBLEMS = ROOT / "benchmarks/humpty_configurations_v2/training_problems.jsonl"
TRAIN_VARIANTS = ROOT / "benchmarks/humpty_configurations_v2/training_variants.jsonl"
TEACHERS = ROOT / "docs/research/qwen35-external-teacher-2026-09-24/train.json"
AUDITS = ROOT / "docs/research/qwen35-external-teacher-2026-09-24/audits.json"
TEACHER_MANIFEST = ROOT / "docs/research/qwen35-external-teacher-2026-09-24/manifest.json"
TEACHER_PROTOCOL = ROOT / "docs/research/qwen35-external-teacher-2026-09-24/train-protocol.json"
ENGLISH_DIR = ROOT / "docs/research/qwen35-diverse-sft-2026-09-24"
TEMPLATES_PATH = ROOT / "benchmarks/humpty_configurations_v2/authoring/variant_templates.json"
sys.path.insert(0, str(ENGLISH_DIR))

TARGET_IDS = ["H03", "H04", "H08", "H14", "H15"]
RETENTION_IDS = ["H01", "H02", "H07", "H13"]
HELDOUT_IDS = set(TARGET_IDS)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GEN = load_module("near_transfer_gen_variants", GEN_PATH)
ENGLISH = load_module("near_transfer_english_templates", ENGLISH_DIR / "english_templates.py")
PREP = load_module("near_transfer_prepare_english", ENGLISH_DIR / "prepare_english.py")
S = GEN.s


class ChoiceSequence:
    """Local replay wrapper: ordered values may extend canonical choice lists."""

    def __init__(self, values):
        self.values = iter(values)

    def choice(self, _canonical_choices):
        return next(self.values)


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(name: str, obj):
    path = HERE / name
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")
    return sha_file(path)


def pnum(v):
    return S.Rational(v)


# These domains mirror the canonical generator's choices. Their designated
# visible-given projections are enumerated locally; exact prior v0-v3 and scale
# signatures are also compared. No eval_variants.jsonl/d1 file or model output is opened.
OLD_DOMAINS = {
    "H01": ([4, 5, 7, 8, 9, 10, 11], [6, 8, 9, 10, 11, 13, 14, 15],
            [S.Rational(1, 3), S.Rational(1, 4), S.Rational(2, 5), S.Rational(1, 5)]),
    "H02": ([7, 8, 9, 10, 12], [3, 4, 5, 6], [7, 8, 9, 10, 11],
            [3, 4, 5, 6], [7, 8, 9, 10, 11]),
    "H03": ([5, 6, 8, 9, 10], [-7, -6, -5], [5, 6, 7, 8],
            [2, 3, 4], [7, 8, 9]),
    "H04": ([5, 6, 7, 8, 9], [1, 2, 3], [5, 6, 7, 11]),
    "H07": ([5, 6, 7, 8], [2, 3], [2, 3]),
    "H08": ([0, 1], [4, 5, 6, 8], [2, 3], [2, 3, 4]),
    "H13": ([5, 6, 7, 8], [[3, 4, 5], [5, 12, 13], [8, 15, 17],
                           [7, 24, 25], [9, 12, 15]], [1, 2]),
    "H14": ([8, 10, 12, 14], [10, 12, 14, 16], [8, 10, 12]),
    "H15": ([3, 4, 5, 6], [3, 4, 5, 7]),
}

# Candidate parameters are fixed before generation. Heldout targets use a
# parameter outside the old generator domain in at least one dimension. The
# retention controls also use an out-of-domain scale/length. These are local
# wrapper overrides, not changes to canonical generators or benchmark files.
FRESH_DOMAINS = {
    "H03": ([7], [-7, -6, -5], [5, 6, 7, 8], [2, 3, 4], [7, 8, 9]),
    "H04": ([10], [1, 2, 3], [5, 6, 7, 11]),
    "H08": ([0, 1], [4, 5, 6, 7, 8], [2, 3], [5]),
    "H14": ([15], [10, 12, 14, 16], [8, 10, 12]),
    "H15": ([8], [3, 4, 5, 7]),
    "H01": ([12], [13, 14, 15, 16, 17],
            [S.Rational(1, 3), S.Rational(1, 4), S.Rational(2, 5), S.Rational(1, 5)]),
    "H02": ([13], [3, 4, 5, 6], [7, 8, 9, 10, 11, 12, 13],
            [3, 4, 5, 6], [7, 8, 9, 10, 11]),
    "H07": ([9], [2, 3], [2, 3]),
    "H13": ([9], [[3, 4, 5], [5, 12, 13], [8, 15, 17],
                   [7, 24, 25], [9, 12, 15]], [1, 2]),
}

PARAM_NAMES = {
    "H01": ("m", "t", "u"), "H02": ("w", "ax", "ay", "i1", "i2"),
    "H03": ("target", "bx", "cx", "ax", "ay"),
    "H04": ("bc", "ax", "ay2"), "H07": ("c", "x0", "y0"),
    "H08": ("px", "qx", "ax", "ay"),
    "H13": ("bc", "tri", "scale"), "H14": ("w", "ax", "ay"),
    "H15": ("c", "b"),
}


def param_dict(cid, values):
    return dict(zip(PARAM_NAMES[cid], values, strict=True))


VISIBLE_KEY = {
    "H01": "BC", "H02": "BC", "H03": "OH", "H04": "BC",
    "H07": "AB", "H08": "AP", "H13": "BC", "H14": "AH", "H15": "AB",
}


def old_visible_metric(cid, values):
    """Project each finite canonical parameter tuple to a visible given."""
    p = param_dict(cid, values)
    if cid == "H01": return S.Rational(2 * p["m"])
    if cid == "H02": return S.Rational(2 * p["w"])
    if cid == "H03": return S.Rational(p["target"])
    if cid == "H04": return S.Rational(p["bc"])
    if cid == "H07": return S.Rational(p["c"])
    if cid == "H08": return S.simplify(S.sqrt((p["ax"] - p["px"])**2 + p["ay"]**2))
    if cid == "H13": return S.Rational(p["bc"])
    if cid == "H14":
        w, x, y = (S.Rational(p[k]) for k in ("w", "ax", "ay"))
        return S.simplify(abs((w**2 - x**2 - y**2) / y))
    if cid == "H15": return S.Rational(p["c"])
    raise ValueError(cid)


def old_visible_metric_values(cid):
    return {old_visible_metric(cid, values) for values in itertools.product(*OLD_DOMAINS[cid])}


def make_fresh_record(cid, seen_exact, old_domain_metrics, scaled_signatures):
    for values in itertools.product(*FRESH_DOMAINS[cid]):
        try:
            rec = GEN.GENERATORS[cid](ChoiceSequence(values))
            if rec is None:
                continue
            sig = GEN.signature(cid, rec["problem"])
            metric_key = VISIBLE_KEY[cid]
            metric = S.simplify(GEN.read_givens(cid, rec["problem"])[metric_key])
            if sig in seen_exact or sig in scaled_signatures or metric in old_domain_metrics:
                continue
            checked = GEN.checked_record(cid, rec, "fresh1", "frozen_fresh")
            return checked, values, metric_key, metric
        except (AssertionError, ZeroDivisionError, ValueError, TypeError, StopIteration):
            continue
    raise RuntimeError(f"No valid unique fresh candidate found for {cid}")


def load_source_records():
    originals = {r["id"]: r for r in read_jsonl(TRAIN_PROBLEMS)}
    variants = read_jsonl(TRAIN_VARIANTS)
    by_id = {}
    for row in variants:
        by_id.setdefault(row["id"], []).append(row)
    return originals, variants, by_id


def known_exact_signatures(cid, original, variants):
    known = set()
    if cid in original:
        known.add(GEN.signature(cid, original[cid]["problem"]))
    for row in variants:
        if row["id"] == cid:
            known.add(GEN.signature(cid, row["problem"]))
    return known


def scaled_v0_signatures(cid, original):
    card = GEN.load_cards()[cid]
    known = set()
    for k in GEN.SCALE_FACTORS:
        try:
            rec = GEN.scaled_variant(original[cid], card, k)
            known.add(GEN.signature(cid, rec["problem"]))
        except (AssertionError, ZeroDivisionError, ValueError, TypeError):
            pass
    return known


def main():
    originals, variants, variants_by_id = load_source_records()
    teachers = json.loads(TEACHERS.read_text())
    audits = {r["id"]: r for r in json.loads(AUDITS.read_text())}
    assert len(teachers) == 37 and len(audits) == 37
    assert {r["source"] for r in teachers} == set(audits)

    train_rows = [r for r in teachers if r["source"] not in HELDOUT_IDS]
    assert len(train_rows) == 32 and {r["source"] for r in train_rows}.isdisjoint(HELDOUT_IDS)
    assert len({r["source"] for r in train_rows}) == 32

    all_records = {}
    generation_audit = []
    for cid in TARGET_IDS + RETENTION_IDS:
        seen_exact = known_exact_signatures(cid, originals, variants_by_id.get(cid, []))
        old_domain_metrics = old_visible_metric_values(cid)
        scaled_signatures = scaled_v0_signatures(cid, originals)
        rec, chosen, metric_key, metric = make_fresh_record(
            cid, seen_exact, old_domain_metrics, scaled_signatures
        )
        sig = GEN.signature(cid, rec["problem"])
        assert sig not in seen_exact and sig not in scaled_signatures
        assert metric not in old_domain_metrics
        all_records[cid] = rec
        generation_audit.append({
            "id": cid,
            "role": "heldout_transfer" if cid in TARGET_IDS else "source_retention_control",
            "generator": f"canonical {cid} construction via local wrapper",
            "parameters": {k: str(v) for k, v in param_dict(cid, chosen).items()},
            "visible_novelty_given": metric_key,
            "visible_novelty_value": str(metric),
            "parameter_domain_extended": True,
            "exact_template_roundtrip": True,
            "independent_shape_answer_check": True,
            "generator_internal_branch_assertions": "passed",
            "signature_absent_from_original_v0_v3": True,
            "visible_given_absent_from_exhaustive_canonical_generator_projection": True,
            "signature_absent_from_canonical_similarity_scales": True,
            "signature_sha256": sha_bytes(repr(sig).encode()),
        })

    # Freeze the split from external teacher answers only; no v1-v3 answer is added.
    train_hash = write_json("train.json", train_rows)

    expected_lemmas = {
        "H03": "The second circle-median intersection is the orthocenter projection onto that median; H01 teaches the projection parameter (BC/2)^2/AM^2.",
        "H04": "Target lemma: AT^2=MT^2-(BC/2)^2. H01 teaches the same half-base-square projection term; DA05 independently uses MD·ME=(BC/2)^2. These are meaningful lemma-level overlaps.",
        "H08": "Target lemma: angle CAP=angle BAQ on the acute branch. H07 teaches tangent-circle equations and a reflection across the base; DA01/DA04/DA06/DA11/DA16/DB01 contain related tangent-circle methods, but none of their audited decisive lemmas is this angle equality.",
        "H14": "R is the orthogonal projection of H onto AM; H01 teaches the matching orthocenter projection formula. This is direct lemma-family overlap.",
        "H15": "K is the midpoint of AD after three reflections. H07 teaches one reflection with tangent circles; DA15 has perpendicular-bisector intersections, but no audited teacher gives the three-reflection midpoint lemma.",
    }
    groups = {
        "H03": "orthocenter_median_projection",
        "H04": "orthocenter_median_projection",
        "H14": "orthocenter_median_projection",
        "H08": "tangent_circle_reflection_near_transfer",
        "H15": "three_reflection_midpoint_independent_case",
    }
    labels = []
    for cid in TARGET_IDS + RETENTION_IDS:
        rec = all_records[cid]
        labels.append({
            "id": cid,
            "role": "heldout_transfer" if cid in TARGET_IDS else "source_retention_control",
            "problem": rec["problem"],
            "givens": rec["givens"],
            "answer_exact": rec["answer_exact"],
            "params": rec["params"],
            "decisive_lemma_expected": audits[cid]["decisive_lemma"] if cid in audits else None,
            "transfer_cluster": groups.get(cid),
            "train_overlap_note": expected_lemmas.get(cid, "Source configuration is trained; the numeric parameters are fresh."),
        })
    labels_hash = write_json("answer_key.json", labels)

    def make_jobs(ids, stage):
        output = []
        for cid in ids:
            row = all_records[cid]
            job = PREP.job(row, stage, 0)
            job["evaluation_role"] = "heldout_transfer" if cid in TARGET_IDS else "source_retention_control"
            job["transfer_cluster"] = groups.get(cid)
            output.append(job)
        return output

    target_jobs = make_jobs(TARGET_IDS, "near-transfer")
    retention_jobs = make_jobs(RETENTION_IDS, "near-retention")
    all_jobs = target_jobs + retention_jobs
    target_jobs_hash = write_json("target_eval_jobs.json", target_jobs)
    retention_jobs_hash = write_json("retention_control_jobs.json", retention_jobs)
    jobs_hash = write_json("eval_jobs.json", all_jobs)

    # A second pass is pre-rendered for all jobs. It may only be executed as one
    # complete batch under the sequential decision rule in protocol.md.
    repeat_jobs = []
    for cid in TARGET_IDS + RETENTION_IDS:
        row = all_records[cid]
        stage = "near-transfer" if cid in TARGET_IDS else "near-retention"
        job = PREP.job(row, stage, 1)
        job["evaluation_role"] = "heldout_transfer" if cid in TARGET_IDS else "source_retention_control"
        job["transfer_cluster"] = groups.get(cid)
        repeat_jobs.append(job)
    repeat_hash = write_json("eval_jobs_repeat1.json", repeat_jobs)

    overlap_table = {
        "scope": "Audited decisive lemmas from the 37 external-teacher answers; configuration names alone were not treated as proof of independence.",
        "rows": [
            {"target": "H03", "target_cluster": groups["H03"], "sources": ["H01"], "overlap": "direct projection-lemma ingredient", "details": expected_lemmas["H03"]},
            {"target": "H04", "target_cluster": groups["H04"], "sources": ["H01", "DA05"], "overlap": "direct algebraic ingredient / same half-base-square term", "details": expected_lemmas["H04"]},
            {"target": "H14", "target_cluster": groups["H14"], "sources": ["H01"], "overlap": "direct projection lemma", "details": expected_lemmas["H14"]},
            {"target": "H08", "target_cluster": groups["H08"], "sources": ["H07", "DA01", "DA04", "DA06", "DA11", "DA16", "DB01"], "overlap": "method-level tangent-circle/reflection overlap; no audited exact angle lemma", "details": expected_lemmas["H08"]},
            {"target": "H15", "target_cluster": groups["H15"], "sources": ["H07", "DA15"], "overlap": "weak reflection / perpendicular-bisector method overlap; no audited three-reflection midpoint lemma", "details": expected_lemmas["H15"]},
        ],
        "effective_independent_target_clusters": 3,
        "interpretation": "H03/H04/H14 are three configuration IDs but one projection-lemma family. H08 is a tangent-circle/reflection near-transfer probe. H15 is a separate three-reflection discovery case; do not group it with H08.",
    }
    overlap_hash = write_json("lemma_overlap.json", overlap_table)

    split = {
        "status": "frozen_candidate_posthoc_exploratory",
        "scope": "Near-transfer positive-control split using audited external-teacher answers.",
        "prior_context_exposure": "Not a blind preregistration: an earlier assistant subtask had already inspected portions of the existing d1/English job material and the target set was selected from an audited overlap review. This freeze run did not open eval_variants.jsonl, existing d1 rows, or model outputs.",
        "source_ids": sorted(r["source"] for r in train_rows),
        "heldout_target_ids": TARGET_IDS,
        "heldout_family_groups": groups,
        "fresh_retention_control_ids": RETENTION_IDS,
        "teacher_rows": {"original": 37, "train": len(train_rows), "heldout": 5, "augmentation_used": "v0 teacher answers only"},
        "no_teacher_answer_for_heldout_targets": True,
        "no_v1_v3_teacher_answers_added": True,
        "freeze_run_no_eval_variants_or_model_outputs_read": True,
        "d1_handling": "The d1 file was not opened in this freeze run. Candidate signatures were checked against all v0-v3 training variants and predefined similarity scales. For original-generator d1 candidates, a visible given was selected outside the exact projection of the generator's full finite parameter domain; this establishes noncollision without exposing or selecting from actual d1 values.",
        "selection_rule": "For each ID, choose the first valid tuple in the fixed Cartesian parameter order, after exact construction/answer checks, with signature absent from v0-v3 and predefined similarity scales, and with its designated visible given outside the exhaustive projection of the original generator domain.",
        "train_json_sha256": train_hash,
        "target_jobs_sha256": target_jobs_hash,
        "retention_jobs_sha256": retention_jobs_hash,
        "all_jobs_sha256": jobs_hash,
        "repeat_jobs_sha256": repeat_hash,
        "answer_key_sha256": labels_hash,
        "lemma_overlap_sha256": overlap_hash,
    }
    split_hash = write_json("split_manifest.json", split)
    construction_hash = write_json("construction_checks.json", {
        "status": "passed",
        "generator_source": str(GEN_PATH.relative_to(ROOT)),
        "generator_source_sha256": sha_file(GEN_PATH),
        "freeze_script_sha256": sha_file(Path(__file__)),
        "template_source_sha256": sha_file(TEMPLATES_PATH),
        "template_sha256_by_id": {cid: GEN.templates()[cid]["template_sha256"] if "template_sha256" in GEN.templates()[cid] else sha_bytes(GEN.templates()[cid]["template"].encode()) for cid in TARGET_IDS + RETENTION_IDS},
        "construction_checks": generation_audit,
        "non_read_conditions": {
            "eval_variants_jsonl_opened": False,
            "model_evaluation_outputs_opened": False,
            "existing_d1_values_opened": False,
        },
    })
    provenance = {
        "source_hashes": {
            str(p.relative_to(ROOT)): sha_file(p)
            for p in [GEN_PATH, TRAIN_PROBLEMS, TRAIN_VARIANTS, TEACHERS, AUDITS,
                      TEACHER_MANIFEST, TEACHER_PROTOCOL, TEMPLATES_PATH,
                      ENGLISH_DIR / "english_templates.py", ENGLISH_DIR / "prepare_english.py"]
        },
        "freeze_script_sha256": sha_file(Path(__file__)),
        "runtime": {"python": sys.version.split()[0], "sympy": S.__version__},
        "created_files": {
            "train.json": train_hash,
            "answer_key.json": labels_hash,
            "target_eval_jobs.json": target_jobs_hash,
            "retention_control_jobs.json": retention_jobs_hash,
            "eval_jobs.json": jobs_hash,
            "eval_jobs_repeat1.json": repeat_hash,
            "lemma_overlap.json": overlap_hash,
            "split_manifest.json": split_hash,
            "construction_checks.json": construction_hash,
        },
    }
    protocol_path = HERE / "PROTOCOL.md"
    if protocol_path.exists():
        provenance["created_files"]["PROTOCOL.md"] = sha_file(protocol_path)
    write_json("hashes.json", provenance)
    print(json.dumps({
        "train_rows": len(train_rows),
        "heldout_targets": TARGET_IDS,
        "retention_controls": RETENTION_IDS,
        "target_jobs": len(target_jobs),
        "retention_jobs": len(retention_jobs),
        "split_sha256": split_hash,
        "d1_opened": False,
        "model_outputs_opened": False,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
