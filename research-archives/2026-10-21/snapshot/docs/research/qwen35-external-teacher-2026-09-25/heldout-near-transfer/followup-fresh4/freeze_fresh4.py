#!/usr/bin/env python3
"""Freeze six exact, English-only fresh4 target inputs; do not run model evals.

The fixed candidate tuples are replayed through the canonical exact
construction generators. The fresh3 CPU branch checkers and independent
shape-answer formulas are reused. Only grader-only keys are written with exact
answers and construction branch conditions; model jobs contain prompts only.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
HELDOUT = HERE.parent
FRESH2 = HELDOUT / "followup-fresh2"
FRESH3 = HELDOUT / "followup-fresh3"
AUTHORING = ROOT / "benchmarks/humpty_configurations_v2/authoring"
ENGLISH_DIR = ROOT / "docs/research/qwen35-diverse-sft-2026-09-24"
VARIANTS = ROOT / "benchmarks/humpty_configurations_v2/training_variants.jsonl"
sys.path.insert(0, str(ROOT))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BASE = load_module("fresh4_near_transfer_helpers", HELDOUT / "freeze_near_transfer.py")
CHECKS = load_module("fresh4_reused_exact_checkers", FRESH3 / "freeze_fresh3.py")
GEN, PREP, ENGLISH = BASE.GEN, BASE.PREP, BASE.ENGLISH
S = GEN.s

IDS = ["H03", "H04", "H14"]
CLUSTER = "orthocenter_median_projection"
ROLE = "heldout_transfer"

# This ordered list is fixed before exact generation. Each item uses the
# existing canonical generator parameter order documented by BASE.PARAM_NAMES.
# The two H03/H04 numeric givens and two H14 metric values are distinct.
CANDIDATE_ORDER = {
    "H03": [
        (13, -7, 5, 2, 7),
        (14, -7, 5, 2, 7),
    ],
    "H04": [
        (13, 1, 13),
        (14, 1, 14),
    ],
    "H14": [
        (19, 16, 12),
        (20, 18, 12),
    ],
}


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def write_json(name: str, value) -> str:
    path = HERE / name
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    return sha_file(path)


def read_json(path: Path):
    return json.loads(path.read_text())


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def key_text(row):
    return row.get("canonical_problem", row.get("problem"))


def normalized_givens(cid, givens):
    return {key: S.simplify(S.sympify(value)) for key, value in givens.items()}


def json_params(cid, values):
    def convert(value):
        if isinstance(value, tuple):
            return [convert(part) for part in value]
        if isinstance(value, S.Basic):
            return str(value)
        return value
    return {key: convert(value) for key, value in BASE.param_dict(cid, values).items()}


def exact_h04_branch_conditions(params):
    bc, ax, ay2 = map(S.Rational, params)
    am2 = S.simplify((ax - bc / 2) ** 2 + ay2)
    half_base2 = S.simplify((bc / 2) ** 2)
    acute_a_dot = S.simplify(ay2 - ax * (bc - ax))
    assert S.simplify(am2 - half_base2 - acute_a_dot) == 0
    assert acute_a_dot.is_positive is True
    assert S.simplify(am2 - half_base2).is_zero is False
    return {
        "acute_angle_at_A_dot_product": str(acute_a_dot),
        "AM_squared_minus_half_BC_squared": str(S.simplify(am2 - half_base2)),
        "factor_nonzero_by_acute_branch": True,
        "T_before_B_and_T_B_C_order": True,
    }


def main():
    # The only old evaluation artifacts opened here are frozen problem inputs
    # and numeric answer-key givens for collision checks. No model outputs,
    # LOO answers, or condition scores are read.
    prior_paths = {
        "fresh1": (HELDOUT / "answer_key.json", HELDOUT / "eval_jobs.json"),
        "fresh2": (FRESH2 / "answer_key.json", FRESH2 / "eval_jobs.json"),
        "fresh3": (FRESH3 / "answer_key.json", FRESH3 / "eval_jobs.json"),
    }
    prior = {}
    for label, (key_path, jobs_path) in prior_paths.items():
        keys = [row for row in read_json(key_path) if row.get("id") in IDS]
        jobs = [row for row in read_json(jobs_path) if row.get("source_id") in IDS]
        assert {row["id"] for row in keys} == set(IDS), (label, "missing target key")
        assert {row["source_id"] for row in jobs} == set(IDS), (label, "missing target job")
        prior[label] = {
            "keys": {row["id"]: row for row in keys},
            "jobs": {row["source_id"]: row for row in jobs},
        }

    # For v0-v3, read only each target row's visible givens, variant label,
    # and canonical problem text; solution/proof fields are never accessed.
    variant_rows = read_jsonl(VARIANTS)
    variants_by_id = {
        cid: [row for row in variant_rows if row.get("id") == cid]
        for cid in IDS
    }
    for cid in IDS:
        assert {row.get("variant") for row in variants_by_id[cid]} == {"v0", "v1", "v2", "v3"}, cid

    jobs_out, keys_out, check_rows = [], [], []
    all_seeds = set()
    for cid in IDS:
        assert len(CANDIDATE_ORDER[cid]) == 2
        prior_givens = {
            label: normalized_givens(cid, prior[label]["keys"][cid]["givens"])
            for label in prior
        }
        teacher_givens = {
            row["variant"]: normalized_givens(cid, row["givens"])
            for row in variants_by_id[cid]
        }
        assert len({tuple(sorted(map(str, g.items()))) for g in teacher_givens.values()}) == 4
        prior_texts = {
            label: key_text(prior[label]["keys"][cid])
            for label in prior
        }
        prior_english = {
            label: prior[label]["jobs"][cid]["english_problem"]
            for label in prior
        }
        prior_seeds = {
            prior[label]["jobs"][cid]["seed"]
            for label in prior
        }
        old_visible_values = BASE.old_visible_metric_values(cid)
        visible_key = BASE.VISIBLE_KEY[cid]

        for instance_index, params in enumerate(CANDIDATE_ORDER[cid], start=1):
            raw = GEN.GENERATORS[cid](CHECKS.FixedChoices(params))
            assert raw is not None, (cid, instance_index, "canonical generator rejected fixed tuple")
            rec = GEN.checked_record(cid, raw, "fresh4", "followup_fresh4")
            givens = CHECKS.canonical_givens(cid, rec["problem"])
            exact_answer = S.simplify(S.sympify(rec["answer_exact"]))
            independent_answer = S.simplify(GEN.independent_shape_answer(cid, givens))
            assert S.simplify(exact_answer - independent_answer) == 0, (cid, instance_index)
            branch_conditions = CHECKS.BRANCH_CHECKERS[cid](params)
            assert branch_conditions and all(branch_conditions.values()), (cid, instance_index, branch_conditions)
            if cid == "H04":
                branch_conditions.update(exact_h04_branch_conditions(params))

            signature = GEN.signature(cid, rec["problem"])
            source_signatures = {
                GEN.signature(cid, row["problem"])
                for row in variants_by_id[cid]
            }
            assert signature not in source_signatures, (cid, instance_index, "v0-v3 signature collision")
            assert rec["problem"] not in {row["problem"] for row in variants_by_id[cid]}, (cid, instance_index, "v0-v3 text collision")

            visible_value = S.simplify(givens[visible_key])
            assert visible_value not in old_visible_values, (cid, instance_index, "old visible-metric collision")
            for label in prior:
                assert givens != prior_givens[label], (cid, instance_index, label, "full-givens collision")
                assert rec["problem"] != prior_texts[label], (cid, instance_index, label, "canonical-text collision")
                assert visible_value != prior_givens[label][visible_key], (cid, instance_index, label, "visible-metric collision")
            for version, old_givens in teacher_givens.items():
                assert givens != old_givens, (cid, instance_index, version, "teacher full-givens collision")
                assert visible_value != old_givens[visible_key], (cid, instance_index, version, "teacher visible-metric collision")

            rec["givens"] = CHECKS.json_givens(givens)
            job = PREP.job(rec, "near-transfer-fresh4", instance_index - 1)
            job["evaluation_role"] = ROLE
            job["transfer_cluster"] = CLUSTER
            job["fresh4_instance"] = instance_index
            message_text = job["messages"][0]["content"]
            assert message_text == PREP.ENGLISH_INSTRUCTION + job["english_problem"]
            assert not re.search(r"[ぁ-んァ-ン一-龥]", message_text)
            assert "answer_exact" not in json.dumps(job, ensure_ascii=False)
            assert job["english_problem"] not in set(prior_english.values()), (cid, instance_index, "English-text collision")
            assert job["seed"] not in prior_seeds and job["seed"] not in all_seeds, (cid, instance_index, "seed collision")
            all_seeds.add(job["seed"])
            jobs_out.append(job)

            exclusion_manifest = {
                "fresh1_full_givens_distinct": True,
                "fresh2_full_givens_distinct": True,
                "fresh3_full_givens_distinct": True,
                "teacher_v0_v3_full_givens_distinct": {
                    version: True for version in sorted(teacher_givens)
                },
                "visible_metric_absent_from_original_finite_projection": True,
                "canonical_signature_absent_from_teacher_v0_v3": True,
                "canonical_and_english_text_distinct_from_fresh1_fresh2_fresh3": True,
            }
            check_row = {
                "job_id": job["id"],
                "id": cid,
                "instance_index": instance_index,
                "role": ROLE,
                "transfer_cluster": CLUSTER,
                "candidate_order_index": instance_index,
                "generator": f"canonical {cid} exact construction via fixed-choice wrapper",
                "parameters": json_params(cid, params),
                "visible_novelty_given": visible_key,
                "visible_novelty_value": str(visible_value),
                "generator_internal_construction_assertions": "passed",
                "independent_shape_answer": str(independent_answer),
                "exact_answer_matches_independent_formula": True,
                "branch_conditions": branch_conditions,
                "collision_exclusions": exclusion_manifest,
                "sha256": {
                    "canonical_problem": sha_bytes(rec["problem"].encode()),
                    "english_problem": sha_bytes(job["english_problem"].encode()),
                    "generator_signature": sha_bytes(repr(signature).encode()),
                },
                "givens": rec["givens"],
            }
            check_rows.append(check_row)
            keys_out.append({
                "job_id": job["id"],
                "id": cid,
                "instance_index": instance_index,
                "role": ROLE,
                "transfer_cluster": CLUSTER,
                "canonical_problem": rec["problem"],
                "english_problem": job["english_problem"],
                "givens": rec["givens"],
                "answer_exact": rec["answer_exact"],
                "parameters": json_params(cid, params),
                "branch_conditions": branch_conditions,
                "answer_key_is_grader_only": True,
            })

    assert len(jobs_out) == len(keys_out) == len(check_rows) == 6
    assert [row["id"] for row in keys_out] == ["H03", "H03", "H04", "H04", "H14", "H14"]
    assert len({row["id"] + ":" + str(row["instance_index"]) for row in keys_out}) == 6
    assert len({row["seed"] for row in jobs_out}) == 6
    assert all("answer_exact" not in job for job in jobs_out)

    jobs_hash = write_json("eval_jobs.json", jobs_out)
    targets_hash = write_json("target_eval_jobs.json", jobs_out)
    keys_hash = write_json("answer_key.json", keys_out)
    checks = {
        "status": "passed",
        "purpose": "exploratory fresh4 numerical inputs for a possible decomposed projection-bridge leave-one-ID-out comparison",
        "job_count": 6,
        "target_ids": IDS,
        "instances_per_id": 2,
        "transfer_cluster": CLUSTER,
        "candidate_order": {cid: [json_params(cid, p) for p in CANDIDATE_ORDER[cid]] for cid in IDS},
        "all_jobs_english_only": True,
        "answer_key_and_branch_conditions_absent_from_model_messages": True,
        "exact_generator_and_independent_answer_checks": "passed for all six",
        "construction_branch_checks": "passed for all six",
        "collision_checks": "fresh1/fresh2/fresh3 full givens and text; teacher v0-v3 full givens, signatures, and text; original finite visible-metric projections",
        "gpu_used": False,
        "model_outputs_opened": False,
        "loo_answers_or_condition_scores_opened": False,
        "evaluation_executed": False,
        "checks_by_job": check_rows,
    }
    checks_hash = write_json("construction_checks.json", checks)

    source_paths = [
        AUTHORING / "gen_variants.py",
        AUTHORING / "variant_templates.json",
        VARIANTS,
        ENGLISH_DIR / "english_templates.py",
        ENGLISH_DIR / "prepare_english.py",
        HELDOUT / "freeze_near_transfer.py",
        HELDOUT / "eval_jobs.json",
        HELDOUT / "answer_key.json",
        HELDOUT / "hashes.json",
        FRESH2 / "freeze_fresh2.py",
        FRESH2 / "eval_jobs.json",
        FRESH2 / "answer_key.json",
        FRESH2 / "hashes.json",
        FRESH3 / "freeze_fresh3.py",
        FRESH3 / "eval_jobs.json",
        FRESH3 / "answer_key.json",
        FRESH3 / "hashes.json",
    ]
    source_hashes = {str(path.relative_to(ROOT)): sha_file(path) for path in source_paths}
    created_hashes = {
        "eval_jobs.json": jobs_hash,
        "target_eval_jobs.json": targets_hash,
        "answer_key.json": keys_hash,
        "construction_checks.json": checks_hash,
        "PROTOCOL.md": sha_file(HERE / "PROTOCOL.md"),
        "freeze_fresh4.py": sha_file(Path(__file__)),
    }
    manifest = {
        "label": "fresh4; six exact English target inputs; no model evaluation performed",
        "created_artifacts_sha256": created_hashes,
        "source_artifacts_sha256": source_hashes,
        "runtime": {"python": sys.version.split()[0], "sympy": S.__version__},
        "reproduction": ".venv/bin/python3.12 docs/research/qwen35-external-teacher-2026-09-25/heldout-near-transfer/followup-fresh4/freeze_fresh4.py",
        "candidate_parameter_tuples": {cid: [json_params(cid, p) for p in CANDIDATE_ORDER[cid]] for cid in IDS},
    }
    hashes_hash = write_json("hashes.json", manifest)
    print(json.dumps({
        "status": "passed",
        "job_count": len(jobs_out),
        "target_ids": IDS,
        "eval_jobs_sha256": jobs_hash,
        "target_eval_jobs_sha256": targets_hash,
        "answer_key_sha256": keys_hash,
        "construction_checks_sha256": checks_hash,
        "hashes_json_sha256": hashes_hash,
        "gpu_used": False,
        "model_outputs_opened": False,
        "loo_answers_or_condition_scores_opened": False,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
