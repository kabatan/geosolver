#!/usr/bin/env python3
"""Freeze a result-informed supplementary numeric retention diagnostic.

This CPU-only preparation reads the historical base grades only to select
source configuration IDs. It writes exclusively into this directory and does
not open evaluation answer text, the old numeric dev prompts, or second-seed
outputs.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import string
import sys
from collections import defaultdict
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
EXTERNAL_DIR = HERE.parent
HELDOUT_DIR = EXTERNAL_DIR / "heldout-near-transfer"
AUTHORING_DIR = ROOT / "benchmarks/humpty_configurations_v2/authoring"
GEN_PATH = AUTHORING_DIR / "gen_variants.py"
ORIGINALS_PATH = ROOT / "benchmarks/humpty_configurations_v2/training_problems.jsonl"
TRAIN_VARIANTS_PATH = ROOT / "benchmarks/humpty_configurations_v2/training_variants.jsonl"
TEMPLATES_PATH = AUTHORING_DIR / "variant_templates.json"
TEACHER_TRAIN_PATH = HELDOUT_DIR / "train.json"
SPLIT_PATH = HELDOUT_DIR / "split_manifest.json"
AUDITS_PATH = ROOT / "docs/research/qwen35-external-teacher-2026-09-24/audits.json"
BASE_GRADES_PATH = ROOT / "qwen/.runtime/qwen35_diverse_sft_20260924/eval-numeric-base-en-32k/manual-grades.json"
ENGLISH_DIR = ROOT / "docs/research/qwen35-diverse-sft-2026-09-24"
DA_VERIFIER_PATH = AUTHORING_DIR / "verify_da_revision.py"
DB_VERIFIER_PATH = AUTHORING_DIR / "verify_db_revision.py"

sys.path.insert(0, str(ENGLISH_DIR))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GEN = load_module("supp_retention_gen_variants", GEN_PATH)
ENGLISH = load_module("supp_retention_english_templates", ENGLISH_DIR / "english_templates.py")
PREP = load_module("supp_retention_prepare_english", ENGLISH_DIR / "prepare_english.py")
S = GEN.s


SELECTED_IDS = ["DB02", "DA18", "DB06", "H12", "HX01", "DA03", "DA07"]
TARGET_IDS = {"H03", "H04", "H08", "H14", "H15"}
CURRENT_RETENTION_IDS = {"H01", "H02", "H07", "H13"}
SCALE_IDS = {"DB02", "DA18", "DB06", "H12", "DA03", "DA07"}
SCALE = S.Rational(7, 4)
SHAPE_PARAMS = {
    # This includes an explicit value outside the canonical finite sampling
    # options while retaining the canonical construction implementation.
    "HX01": (8, 3, 7),
}


class FixedChoices:
    """Replay fixed parameters through a canonical generator's choice API."""

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


def slots(template: str):
    return {field for _, field, _, _ in string.Formatter().parse(template) if field}


def exact_card_givens(card):
    return {row["name"]: S.sympify(row["value"]) for row in card["givens"]}


def assert_close(actual, expected, tol=1e-8):
    delta = abs(float(actual) - float(S.N(expected)))
    assert delta <= tol, (actual, expected, delta, tol)
    return delta


def frozen_rows_by_id(rows):
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["id"]].append(row)
    return grouped


def main():
    originals = {row["id"]: row for row in read_jsonl(ORIGINALS_PATH)}
    train_variants = read_jsonl(TRAIN_VARIANTS_PATH)
    train_variant_rows = frozen_rows_by_id(train_variants)
    training_sources = {row["source"] for row in json.loads(TEACHER_TRAIN_PATH.read_text())}
    split = json.loads(SPLIT_PATH.read_text())
    source_targets = set(split["heldout_target_ids"])
    historical_rows = json.loads(BASE_GRADES_PATH.read_text())
    historical_by_id = frozen_rows_by_id(
        [{**row, "id": row["config"]} for row in historical_rows]
    )
    audits = {row["id"]: row for row in json.loads(AUDITS_PATH.read_text())}
    cards = GEN.load_cards()
    assert source_targets == TARGET_IDS, (source_targets, TARGET_IDS)
    assert set(SELECTED_IDS).issubset(training_sources)
    assert set(SELECTED_IDS).isdisjoint(TARGET_IDS)
    assert set(SELECTED_IDS).isdisjoint(CURRENT_RETENTION_IDS)
    assert set(SELECTED_IDS).issubset(originals)
    assert SCALE not in GEN.SCALE_FACTORS
    assert set(SELECTED_IDS).issubset(historical_by_id)

    historical_metrics = {}
    for cid in SELECTED_IDS:
        rows = historical_by_id[cid]
        assert len(rows) == 2, (cid, len(rows))
        metrics = {
            name: sum(bool(row[name]) for row in rows)
            for name in ("complete", "exact", "relation", "proof", "applied")
        }
        historical_metrics[cid] = {
            "sample_count": len(rows),
            "successful_samples": metrics,
            "selection_stratum": (
                "historically_complete"
                if metrics["complete"] > 0
                else "historically_exact_relation_application_without_complete_proof"
            ),
        }

    expected_prior_complete = {"DB02", "DA18", "DB06"}
    assert {
        cid for cid, row in historical_metrics.items()
        if row["successful_samples"]["complete"] > 0
    } == expected_prior_complete
    for cid in ("H12", "HX01", "DA03", "DA07"):
        metrics = historical_metrics[cid]["successful_samples"]
        assert metrics == {"complete": 0, "exact": 2, "relation": 2, "proof": 0, "applied": 2}

    generated = {}
    construction_rows = []
    for cid in SELECTED_IDS:
        original = originals[cid]
        if cid in SCALE_IDS:
            raw = GEN.scaled_variant(original, cards[cid], SCALE)
            check_kind = "exact_similarity_transform_of_v0"
            parameters = {"scale": str(SCALE)}
        else:
            raw = GEN.GENERATORS[cid](FixedChoices(SHAPE_PARAMS[cid]))
            assert raw is not None, f"canonical generator rejected {cid} parameters"
            check_kind = "canonical_shape_generator_with_fixed_parameter_extension"
            parameters = {key: str(value) for key, value in raw["params"].items()}

        row = GEN.checked_record(cid, raw, "supp-retention-v1", "supplementary-retention")
        givens = GEN.read_givens(cid, row["problem"])
        row["givens"] = {key: str(value) for key, value in givens.items()}

        old_variant_signatures = {
            GEN.signature(cid, old["problem"])
            for old in train_variant_rows[cid]
        }
        assert len(train_variant_rows[cid]) == 4, (cid, len(train_variant_rows[cid]))
        assert GEN.signature(cid, row["problem"]) not in old_variant_signatures, cid
        assert row["problem"] != original["problem"], cid

        if cid in SCALE_IDS:
            old_givens = GEN.read_givens(cid, original["problem"])
            degrees = GEN.templates()[cid]["given_scale_degrees"]
            assert set(degrees) == set(old_givens) == set(givens), cid
            for name, degree in degrees.items():
                assert S.simplify(givens[name] - old_givens[name] * SCALE**degree) == 0, (cid, name)
            answer_degree = GEN.templates()[cid]["answer_scale_degree"]
            assert S.simplify(
                S.sympify(row["answer_exact"])
                - S.sympify(original["answer_exact"]) * SCALE**answer_degree
            ) == 0, cid
            if cid in {"H12"}:
                GEN.eq(S.sympify(row["answer_exact"]), GEN.independent_shape_answer(cid, givens))
        else:
            GEN.eq(S.sympify(row["answer_exact"]), GEN.independent_shape_answer(cid, givens))

        english_template = ENGLISH.NUMERIC_EN[cid]
        assert slots(english_template) == set(GEN.templates()[cid]["base_literals"]), cid
        job = PREP.job(row, "supplementary-retention", 0)
        assert job["english_problem"] == english_template.format(**row["givens"]), cid
        assert not re.search(r"[ぁ-んァ-ン一-龥]", job["english_problem"]), cid
        assert "answer_exact" not in job
        job["evaluation_role"] = "supplementary_source_retention"
        job["study_label"] = "result-informed_supplementary_retention_diagnostic"
        job["confirmatory_status"] = "not_a_confirmatory_transfer_test"
        generated[cid] = {"row": row, "job": job, "check_kind": check_kind, "parameters": parameters}

        construction_rows.append({
            "source_id": cid,
            "role": "supplementary_source_retention",
            "construction_check": check_kind,
            "parameters": parameters,
            "exact_problem_template_roundtrip": True,
            "approved_english_template_slot_match": True,
            "english_render_contains_no_japanese_script": True,
            "canonical_generator_or_scaler_internal_checks": "passed",
            "answer_key_exact_check": "passed",
            "answer_exact": row["answer_exact"],
            "givens": row["givens"],
            "signature_sha256": sha_bytes(repr(GEN.signature(cid, row["problem"])).encode()),
            "training_v0_v3_signature_collision": False,
            "historical_base_selection": historical_metrics[cid],
        })

    # Recheck original constructions with the authoring witnesses before
    # relying on exact similarity scaling for IDs without shape generators.
    da_ids = {"DA03", "DA07", "DA18"}
    db_ids = {"DB02", "DB06"}
    da = load_module("supp_retention_verify_da", DA_VERIFIER_PATH)
    db = load_module("supp_retention_verify_db", DB_VERIFIER_PATH)
    da_witnesses = da.construct()
    db_witnesses = db.build()
    witness_summary = {}
    for cid in sorted(da_ids):
        card = cards[cid]
        original_givens = GEN.read_givens(cid, originals[cid]["problem"])
        card_givens = exact_card_givens(card)
        witness = da_witnesses[cid]
        assert set(original_givens) == set(card_givens) == set(witness["given_values"]), cid
        assert S.simplify(S.sympify(originals[cid]["answer_exact"]) - S.sympify(card["answer_exact"])) == 0
        for name in original_givens:
            assert S.simplify(original_givens[name] - card_givens[name]) == 0, (cid, name)
            assert_close(witness["given_values"][name], card_givens[name], tol=da.TOL)
        assert_close(witness["answer"], card["answer_exact"], tol=da.TOL)
        witness_summary[cid] = {
            "authoring_witness": "verify_da_revision.construct",
            "all_original_givens_matched_card": True,
            "original_answer_matched_card_within_tolerance": da.TOL,
            "fresh_answer_exactly_preserves_similarity_degree": True,
        }
    for cid in sorted(db_ids):
        card = cards[cid]
        original_givens = GEN.read_givens(cid, originals[cid]["problem"])
        card_givens = exact_card_givens(card)
        witness = db_witnesses[cid]
        witness_givens = {key: S.sympify(value) for key, value in witness["given_values"].items()}
        assert set(original_givens) == set(card_givens) == set(witness_givens), cid
        assert S.simplify(S.sympify(originals[cid]["answer_exact"]) - S.sympify(card["answer_exact"])) == 0
        for name in original_givens:
            assert S.simplify(original_givens[name] - card_givens[name]) == 0, (cid, name)
            assert S.simplify(witness_givens[name] - card_givens[name]) == 0, (cid, name)
        assert S.simplify(S.sympify(witness["answer"]) - S.sympify(card["answer_exact"])) == 0, cid
        witness_summary[cid] = {
            "authoring_witness": "verify_db_revision.build",
            "all_original_givens_matched_card_exactly": True,
            "original_answer_matched_card_exactly": True,
            "fresh_answer_exactly_preserves_similarity_degree": True,
        }

    jobs = [generated[cid]["job"] for cid in SELECTED_IDS]
    answer_key = []
    for cid in SELECTED_IDS:
        job = generated[cid]["job"]
        row = generated[cid]["row"]
        answer_key.append({
            "job_id": job["id"],
            "source_id": cid,
            "role": "supplementary_source_retention",
            "english_problem": job["english_problem"],
            "givens": row["givens"],
            "answer_exact": row["answer_exact"],
            "decisive_lemma_expected": audits[cid]["decisive_lemma"],
            "construction_method": generated[cid]["check_kind"],
            "construction_parameters": generated[cid]["parameters"],
            "historical_base_selection": historical_metrics[cid],
            "answer_key_is_grader_only": True,
        })

    selection = {
        "status": "result_informed_supplementary_retention_diagnostic",
        "interpretation": "Not a confirmatory transfer test. IDs were selected after reading historical untouched-base numeric development grades.",
        "historical_baseline_source": str(BASE_GRADES_PATH.relative_to(ROOT)),
        "historical_baseline_sha256": sha_file(BASE_GRADES_PATH),
        "historical_baseline_scope": "37 configuration IDs, two generated samples per ID; only grade fields were used, not answer text.",
        "selection_rule": "Exclude the five held-out targets and the four existing retention controls. Include all remaining source IDs with at least one complete untouched-base sample (DB02, DA18, DB06), then four remaining source IDs with 2/2 exact answer, useful relation, and application but 0/2 complete proof (H12, HX01, DA03, DA07).",
        "selected_ids": SELECTED_IDS,
        "excluded_heldout_target_ids": sorted(TARGET_IDS),
        "excluded_existing_retention_ids": sorted(CURRENT_RETENTION_IDS),
        "selected_historical_metrics": historical_metrics,
        "historical_old_prompt_reused": False,
        "fresh_numeric_instances": True,
        "selection_depended_on_historical_base_results": True,
        "limits": [
            "The fresh numeric values were not evaluated on the untouched base when selected; historical same-configuration success does not guarantee success on these values.",
            "The same source configurations and underlying geometry families were already exposed during development.",
            "Any observed adapter result is descriptive retention evidence and cannot confirm new-configuration transfer.",
        ],
    }

    checks = {
        "status": "passed",
        "scope": "CPU-only candidate construction, exact answer, English template, source-ID boundary, and training-variant novelty checks.",
        "target_ids_excluded": sorted(TARGET_IDS),
        "existing_retention_ids_excluded": sorted(CURRENT_RETENTION_IDS),
        "all_selected_ids_are_in_32_row_near_transfer_training_source_set": True,
        "all_selected_ids_are_outside_near_transfer_target_ids": True,
        "all_selected_ids_are_outside_existing_retention_ids": True,
        "no_eval_variants_jsonl_opened": True,
        "no_model_evaluation_answer_text_opened_during_freeze": True,
        "no_near_transfer_or_fresh2_generation_outputs_opened": True,
        "no_second_seed_outputs_opened": True,
        "gpu_used": False,
        "source_variant_rows_checked_per_id": 4,
        "nondegenerate_canonical_construction_checks": "passed",
        "exact_answer_checks": "passed",
        "training_variant_exact_signature_collisions": 0,
        "independent_authoring_witnesses": witness_summary,
        "construction_checks": construction_rows,
        "source_hashes": {
            str(path.relative_to(ROOT)): sha_file(path)
            for path in [GEN_PATH, ORIGINALS_PATH, TRAIN_VARIANTS_PATH, TEMPLATES_PATH,
                         TEACHER_TRAIN_PATH, SPLIT_PATH, AUDITS_PATH, BASE_GRADES_PATH,
                         ENGLISH_DIR / "english_templates.py", ENGLISH_DIR / "prepare_english.py",
                         DA_VERIFIER_PATH, DB_VERIFIER_PATH,
                         AUTHORING_DIR / "da_revision.json", AUTHORING_DIR / "db_revision.json"]
        },
    }

    jobs_hash = write_json("eval_jobs.json", jobs)
    answer_key_hash = write_json("answer_key.json", answer_key)
    selection_hash = write_json("selection_basis.json", selection)
    checks_hash = write_json("construction_checks.json", checks)

    created = {
        "eval_jobs.json": jobs_hash,
        "answer_key.json": answer_key_hash,
        "selection_basis.json": selection_hash,
        "construction_checks.json": checks_hash,
        "PROTOCOL.md": sha_file(HERE / "PROTOCOL.md"),
        "freeze_supplementary_retention.py": sha_file(Path(__file__)),
    }
    provenance = {
        "artifact_label": "result-informed supplementary retention diagnostic; not a confirmatory transfer test",
        "created_artifacts_sha256": created,
        "source_artifacts_sha256": checks["source_hashes"],
        "runtime": {"python": sys.version.split()[0], "sympy": S.__version__},
        "reproduction": ".venv/bin/python3.12 docs/research/qwen35-external-teacher-2026-09-25/supplementary-retention-sentinel/freeze_supplementary_retention.py",
        "jobs": len(jobs),
        "selected_ids": SELECTED_IDS,
        "historical_selection_basis_sha256": selection["historical_baseline_sha256"],
    }
    hashes_hash = write_json("hashes.json", provenance)
    print(json.dumps({
        "status": "passed",
        "jobs": len(jobs),
        "ids": SELECTED_IDS,
        "eval_jobs_sha256": jobs_hash,
        "answer_key_sha256": answer_key_hash,
        "selection_basis_sha256": selection_hash,
        "construction_checks_sha256": checks_hash,
        "hashes_json_sha256": hashes_hash,
        "gpu_used": False,
        "second_seed_outputs_opened": False,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
