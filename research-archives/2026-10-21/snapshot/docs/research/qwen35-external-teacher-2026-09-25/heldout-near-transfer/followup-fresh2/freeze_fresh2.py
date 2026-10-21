#!/usr/bin/env python3
"""Freeze new numeric English jobs for the 38-row exploratory follow-up.

This imports the canonical geometry generator and the earlier near-transfer
freeze helpers, but writes only inside this followup-fresh2 directory. It does
not open existing evaluation jobs, answer keys, or model outputs.
"""
from __future__ import annotations

import hashlib
import importlib.util
import itertools
import json
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
BASE_DIR = HERE.parent
sys.path.insert(0, str(ROOT))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module at {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BASE = load_module("fresh2_near_transfer_helpers", BASE_DIR / "freeze_near_transfer.py")
GEN = BASE.GEN
PREP = BASE.PREP
S = GEN.s

TARGET_IDS = ["H03", "H04", "H08", "H14", "H15"]
RETENTION_IDS = ["H01", "H02", "H07", "H13"]
IDS = TARGET_IDS + RETENTION_IDS
GROUPS = {
    "H03": "orthocenter_median_projection",
    "H04": "orthocenter_median_projection",
    "H14": "orthocenter_median_projection",
    "H08": "tangent_circle_reflection_near_transfer",
    "H15": "three_reflection_midpoint_independent_case",
}

# Deterministic candidate domains. Each target is outside the old finite
# projection domain in its designated visible given. The ordered Cartesian
# product selects the first candidate passing every exact check.
FRESH2_DOMAINS = {
    "H03": ([11], [-7, -6, -5], [5, 6, 7, 8], [2, 3, 4], [7, 8, 9]),
    "H04": ([11], [1, 2, 3], [5, 6, 7, 11]),
    "H08": ([1], [7], [2, 3], [5]),
    "H14": ([17], [10, 12, 14, 16], [8, 10, 12]),
    "H15": ([9], [3, 4, 5, 7]),
    "H01": ([13], [14, 15, 16, 17],
            [S.Rational(1, 3), S.Rational(1, 4), S.Rational(2, 5), S.Rational(1, 5)]),
    "H02": ([14], [3, 4, 5, 6], [7, 8, 9, 10, 11, 12, 13],
            [3, 4, 5, 6], [7, 8, 9, 10, 11, 12, 13]),
    "H07": ([10], [2, 3], [2, 3]),
    "H13": ([10], [(3, 4, 5), (5, 12, 13), (8, 15, 17),
                    (7, 24, 25), (9, 12, 15)], [1, 2]),
}

# Known fresh1 generator inputs from its completed freeze report. Replaying
# these tuples through the generator allows a local exact collision check
# without opening fresh1/repeat1 evaluation artifacts.
FRESH1_VALUES = {
    "H03": (7, -7, 5, 2, 7),
    "H04": (10, 1, 11),
    "H08": (0, 4, 3, 5),
    "H14": (15, 10, 12),
    "H15": (8, 3),
    "H01": (12, 13, S.Rational(1, 3)),
    "H02": (13, 3, 13, 3, 7),
    "H07": (9, 2, 3),
    "H13": (9, (5, 12, 13), 1),
}


class FixedChoices:
    """Replay wrapper compatible with the canonical generator's choice API."""
    def __init__(self, values):
        self.values = iter(values)

    def choice(self, _options):
        return next(self.values)


def sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(name: str, data) -> str:
    path = HERE / name
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    return sha_file(path)


def make_record(cid: str, values):
    rec = GEN.GENERATORS[cid](FixedChoices(values))
    if rec is None:
        return None
    return GEN.checked_record(cid, rec, "fresh2", "followup_fresh2")


def replay_fresh1_records():
    records = {}
    for cid, values in FRESH1_VALUES.items():
        rec = GEN.GENERATORS[cid](FixedChoices(values))
        if rec is None:
            raise AssertionError(f"Could not replay the known fresh1 tuple for {cid}")
        records[cid] = GEN.checked_record(cid, rec, "fresh1_reference", "collision_check")
    return records


def choose_fresh2(cid, known_exact, scaled, fresh1):
    old_metrics = BASE.old_visible_metric_values(cid)
    fresh1_sig = GEN.signature(cid, fresh1["problem"])
    fresh1_givens = GEN.read_givens(cid, fresh1["problem"])
    for values in itertools.product(*FRESH2_DOMAINS[cid]):
        try:
            if tuple(values) == tuple(FRESH1_VALUES[cid]):
                continue
            rec = make_record(cid, values)
            if rec is None:
                continue
            sig = GEN.signature(cid, rec["problem"])
            givens = GEN.read_givens(cid, rec["problem"])
            metric_key = BASE.VISIBLE_KEY[cid]
            metric = S.simplify(givens[metric_key])
            if sig == fresh1_sig or givens == fresh1_givens:
                continue
            if sig in known_exact or sig in scaled:
                continue
            if metric in old_metrics:
                continue
            assert sig != fresh1_sig and givens != fresh1_givens
            assert tuple(values) != tuple(FRESH1_VALUES[cid])
            assert sig not in known_exact and sig not in scaled
            assert metric not in old_metrics
            assert S.simplify(GEN.parse_numeric(rec["answer_exact"]) - GEN.independent_shape_answer(cid, givens)) == 0
            return rec, values, metric_key, metric, sig
        except (AssertionError, ZeroDivisionError, ValueError, TypeError, StopIteration):
            continue
    raise RuntimeError(f"No valid fresh2 candidate found for {cid}")


def main():
    originals, variants, variants_by_id = BASE.load_source_records()
    fresh1_records = replay_fresh1_records()

    # Verify that every held-out target remains absent from each of the three
    # 38-row follow-up training compositions. Only training datasets are read.
    arm_dir = ROOT / "docs/research/qwen35-external-teacher-2026-09-25/relation-discrimination-v2"
    train_paths = {
        "direct-multi": arm_dir / "train-38-direct-multi.json",
        "repeat": arm_dir / "train-38-repeat.json",
        "balanced-qa": arm_dir / "train-38-balanced-qa.json",
    }
    train_source_ids = {}
    for arm, path in train_paths.items():
        rows = json.loads(path.read_text())
        assert len(rows) == 38, (arm, len(rows))
        ids = {r["source"] for r in rows}
        assert not (ids & set(TARGET_IDS)), (arm, sorted(ids & set(TARGET_IDS)))
        train_source_ids[arm] = sorted(ids)

    records = {}
    checks = []
    for cid in IDS:
        seen_exact = BASE.known_exact_signatures(cid, originals, variants_by_id.get(cid, []))
        scaled = BASE.scaled_v0_signatures(cid, originals)
        rec, chosen, metric_key, metric, sig = choose_fresh2(
            cid, seen_exact, scaled, fresh1_records[cid]
        )
        assert tuple(chosen) != tuple(FRESH1_VALUES[cid])
        records[cid] = rec
        givens = GEN.read_givens(cid, rec["problem"])
        fresh1_givens = GEN.read_givens(cid, fresh1_records[cid]["problem"])
        assert givens != fresh1_givens
        checks.append({
            "id": cid,
            "role": "heldout_transfer" if cid in TARGET_IDS else "source_retention_control",
            "generator": f"canonical {cid} generator via local fixed-choice wrapper",
            "parameters": {k: str(v) for k, v in BASE.param_dict(cid, chosen).items()},
            "visible_novelty_given": metric_key,
            "visible_novelty_value": str(metric),
            "fresh1_numeric_givens_distinct": True,
            "fresh1_problem_text_distinct": rec["problem"] != fresh1_records[cid]["problem"],
            "repeat1_collision_avoided_by_fresh1_distinction": True,
            "generator_internal_branch_assertions": "passed",
            "exact_template_roundtrip": True,
            "independent_shape_answer_check": "passed",
            "signature_absent_from_original_v0_v3": True,
            "visible_given_absent_from_exhaustive_canonical_generator_projection": True,
            "signature_absent_from_canonical_similarity_scales": True,
            "fresh1_parameter_tuple_not_reused": True,
            "signature_sha256": hashlib.sha256(repr(sig).encode()).hexdigest(),
            "problem_sha256": hashlib.sha256(rec["problem"].encode()).hexdigest(),
        })

    audits = {r["id"]: r for r in json.loads(BASE.AUDITS.read_text())}
    answer_key = []
    target_jobs = []
    retention_jobs = []
    for cid in IDS:
        rec = records[cid]
        answer_key.append({
            "id": cid,
            "role": "heldout_transfer" if cid in TARGET_IDS else "source_retention_control",
            "problem": rec["problem"],
            "givens": rec["givens"],
            "answer_exact": rec["answer_exact"],
            "params": rec["params"],
            "decisive_lemma_expected": audits[cid]["decisive_lemma"],
            "transfer_cluster": GROUPS.get(cid),
        })
        stage = "near-transfer-fresh2" if cid in TARGET_IDS else "near-retention-fresh2"
        job = PREP.job(rec, stage, 0)
        job["evaluation_role"] = "heldout_transfer" if cid in TARGET_IDS else "source_retention_control"
        job["transfer_cluster"] = GROUPS.get(cid)
        old_stage = "near-transfer" if cid in TARGET_IDS else "near-retention"
        fresh1_seed = PREP.job(fresh1_records[cid], old_stage, 0)["seed"]
        repeat1_seed = PREP.job(fresh1_records[cid], old_stage, 1)["seed"]
        assert job["seed"] not in {fresh1_seed, repeat1_seed}
        check = next(row for row in checks if row["id"] == cid)
        check["fresh1_seed_distinct"] = job["seed"] != fresh1_seed
        check["repeat1_seed_distinct"] = job["seed"] != repeat1_seed
        (target_jobs if cid in TARGET_IDS else retention_jobs).append(job)

    all_jobs = target_jobs + retention_jobs
    assert len(all_jobs) == 9
    assert [j["source_id"] for j in all_jobs] == IDS
    assert len({j["seed"] for j in all_jobs}) == 9
    assert all(j["variant"] == "fresh2" for j in all_jobs)
    assert all(j["english_problem"] for j in all_jobs)

    jobs_hash = write_json("eval_jobs.json", all_jobs)
    target_hash = write_json("target_eval_jobs.json", target_jobs)
    retention_hash = write_json("retention_control_jobs.json", retention_jobs)
    key_hash = write_json("answer_key.json", answer_key)
    check_hash = write_json("construction_checks.json", {
        "status": "passed",
        "scope": "CPU-only candidate construction and exact answer checks; no evaluation execution",
        "generator_source": str(BASE.GEN_PATH.relative_to(ROOT)),
        "generator_source_sha256": sha_file(BASE.GEN_PATH),
        "fresh1_or_repeat1_evaluation_artifacts_opened": False,
        "existing_model_outputs_opened": False,
        "fresh1_numeric_collision_test": "replayed the known fresh1 construction parameter tuples through the canonical generator; no fresh2 visible-given tuple or problem text matched",
        "repeat1_numeric_collision_test": "repeat1 reuses fresh1 numerical constructions with a different sampling seed; every fresh2 visible-given tuple differs from its fresh1 counterpart",
        "target_ids_absent_from_all_38_row_arms": {
            arm: {"row_count": 38, "heldout_target_ids_absent": True,
                  "present_source_ids": ids}
            for arm, ids in train_source_ids.items()
        },
        "per_configuration_checks": checks,
    })

    protocol = '''# Fresh2 numeric evaluation for the 38-row exploratory follow-up

## Scope

This folder freezes a second, distinct set of English numeric jobs for the next exploratory comparison of the 38-row `direct-multi`, `repeat`, and `balanced-qa` datasets. It reuses the same nine configuration IDs and transfer/retention roles as the primary near-transfer set: targets H03/H04/H08/H14/H15 and retention controls H01/H02/H07/H13. Every arm, including the untouched base if evaluated, must receive the same `eval_jobs.json` prompt text and per-job seed.

The five target configurations are absent from all three 38-row training datasets, as verified directly against their `source` fields and recorded in `construction_checks.json`. H03/H04/H14 are one correlated orthocenter/median-projection family; H08 is the tangent-circle/reflection probe; H15 is a separate three-reflection case. The four retention items are source-configuration controls, not independent transfer targets.

## Freshness and exact checks

Jobs were generated with the canonical geometry generator, its internal branch assertions, exact approved-template roundtrip checks, and the independent shape-answer formulas from `heldout-near-transfer/freeze_near_transfer.py`. Each visible novelty given lies outside the exhaustive finite projection of its original generator parameter domain. Each construction signature is absent from original v0-v3 training variants and the predefined similarity scales. `freeze_fresh2.py` replays the known fresh1 tuples in memory and rejects matching parameter/given/problem instances; fresh1 and repeat1 evaluation files and all generated model outputs were not opened. Since repeat1 keeps the fresh1 numerical constructions and changes only sampling seeds, the per-ID fresh1 instance distinction also prevents an exact numerical repeat1 collision. Fresh2 job seeds are regenerated deterministically from the fresh2 stage labels and checked against both corresponding fresh1/repeat1 seeds.

The evaluator-only `answer_key.json` is separate from all jobs and must never enter model context. The jobs retain the approved English numeric templates. `hashes.json` records the source and artifact digests. No training, model generation, or scoring was performed as part of this freeze.

## Use and interpretation

If this follow-up is run, compare untouched base and the three independently trained 38-row arms on the same nine jobs, decoding settings, and frozen seeds. Keep the scorer blind to arm. Record exact-value, useful-relation, proof, and correct-use components separately; complete success requires all components. Report H03/H04/H14 together, H08 and H15 separately, plus the four retention controls. These small, correlated, development-informed results are exploratory and cannot by themselves establish autonomous relation discovery or the broader research hypothesis. Do not select a checkpoint, prompt, or decoding recipe from these outcomes.
'''
    protocol_path = HERE / "PROTOCOL.md"
    protocol_path.write_text(protocol)

    source_files = [
        BASE.GEN_PATH,
        BASE.TRAIN_PROBLEMS,
        BASE.TRAIN_VARIANTS,
        BASE.TEMPLATES_PATH,
        BASE.ENGLISH_DIR / "english_templates.py",
        BASE.ENGLISH_DIR / "prepare_english.py",
        BASE.AUDITS,
        BASE_DIR / "freeze_near_transfer.py",
        *train_paths.values(),
    ]
    provenance = {
        "source_hashes": {str(path.relative_to(ROOT)): sha_file(path) for path in source_files},
        "fresh2_freeze_script_sha256": sha_file(Path(__file__)),
        "runtime": {"python": sys.version.split()[0], "sympy": S.__version__},
        "created_files": {
            "eval_jobs.json": jobs_hash,
            "target_eval_jobs.json": target_hash,
            "retention_control_jobs.json": retention_hash,
            "answer_key.json": key_hash,
            "construction_checks.json": check_hash,
            "PROTOCOL.md": sha_file(protocol_path),
        },
        "manifest": {
            "job_count": len(all_jobs),
            "target_ids": TARGET_IDS,
            "retention_ids": RETENTION_IDS,
            "fresh1_repeat1_eval_files_opened": False,
            "model_outputs_opened": False,
            "gpu_used": False,
            "evaluation_executed": False,
        },
    }
    write_json("hashes.json", provenance)
    print(json.dumps({
        "jobs": len(all_jobs),
        "source_ids": [j["source_id"] for j in all_jobs],
        "seeds": [j["seed"] for j in all_jobs],
        "target_absence_in_38_row_arms": {k: not (set(v) & set(TARGET_IDS)) for k, v in train_source_ids.items()},
        "evaluation_executed": False,
        "gpu_used": False,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
