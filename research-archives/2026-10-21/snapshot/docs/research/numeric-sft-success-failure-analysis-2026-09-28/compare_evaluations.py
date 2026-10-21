"""Read-only reconstruction of two numeric transfer evaluations and their saved budgets.

Run with ``.venv/bin/python compare_evaluations.py``. No model is invoked. The
old published score ledger is used as scored; new intermediate responses are
parsed with the same numeric parser used by the frozen new scorer.
"""
from __future__ import annotations

import collections
import difflib
import hashlib
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OLD_DOC = ROOT / "docs/research/transfer-reanalysis-2026-09-26"
NEW_DOC = ROOT / "docs/research/numeric-sft-dose-control-2026-09-28"
OLD = ROOT / "qwen/.runtime/transfer_followup_20260926"
NEW = ROOT / "qwen/.runtime/numeric_sft_dose_control_20260928"
sys.path.insert(0, str(ROOT / "docs/research/related-numeric-sft-2026-09-28"))
import analyze as numeric_parser  # noqa: E402


def load(path: Path):
    return json.loads(path.read_text())


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha(obj) -> str:
    encoded = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def natural(row: dict) -> bool:
    return row["finish_reason"] == "stop" and row["numeric_correct"] is True


def outcome(row: dict) -> dict:
    return {k: row.get(k) for k in ("finish_reason", "numeric_correct", "cap")}


def outcome_changed(first: dict, second: dict) -> bool:
    return any(first[k] != second[k] for k in ("finish_reason", "numeric_correct"))


def count(rows: list[dict]) -> dict:
    return {"n": len(rows), "natural_stop": sum(x["finish_reason"] == "stop" for x in rows),
            "natural_stop_correct": sum(natural(x) for x in rows),
            "length": sum(x["finish_reason"] == "length" for x in rows),
            "unparsed": sum(x["numeric_correct"] is None for x in rows)}


def score_raw(raw: dict, target: float, cap: int) -> dict:
    parsed, _, _ = numeric_parser.parse(raw["raw_text"])
    value = None
    if parsed is not None:
        try:
            candidate = float(numeric_parser.parse_numeric(parsed))
            if math.isfinite(candidate):
                value = candidate
        except (ValueError, TypeError, OverflowError):
            pass
    correct = None if value is None else (abs(value - target) <= 1e-4 or
                                          abs(value - target) / abs(target) <= 1e-5)
    return {"finish_reason": raw["finish_reason"], "numeric_correct": correct,
            "cap": cap, "tokens": len(raw["completion_ids"])}


def main() -> None:
    old_jobs_path = OLD_DOC / "eval-jobs-v2.json"
    new_jobs_path = NEW / "transfer-jobs.json"
    old_score_path = OLD / "numeric-extended-score.json"
    new_score_path = NEW / "transfer-scores.json"
    old_jobs = {x["id"]: x for x in load(old_jobs_path)}
    new_jobs = {x["id"]: x for x in load(new_jobs_path)
                if x["split"] == "untrained_configuration"}
    old_score, new_score = load(old_score_path), load(new_score_path)
    common = sorted(set(old_jobs) & set(new_jobs))
    removed = sorted(set(old_jobs) - set(new_jobs))
    assert len(old_jobs) == 24 and len(new_jobs) == len(common) == 16 and len(removed) == 8
    old_source = {j["source_id"] for j in old_jobs.values()}
    new_source = {j["source_id"] for j in new_jobs.values()}
    assert len(old_source) == 12 and len(new_source) == 8 and len(old_source - new_source) == 4

    old_32 = {arm: {x["job_id"]: x for x in old_score["numeric_32k"]["conditions"][arm]["jobs"]}
              for arm in ("base", "numeric128")}
    old_final = {arm: {x["job_id"]: x for x in old_score["extended_budget_24_job_summary"]["conditions"][arm]["jobs"]}
                 for arm in ("base", "numeric128")}
    new_final = {arm: {x["job_id"]: x for x in new_score["numeric"]
                       if x["arm"] == arm and x["split"] == "untrained_configuration"}
                 for arm in ("base", "correct128", "correct512", "shuffled512")}
    for arm in old_32:
        assert len(old_32[arm]) == len(old_final[arm]) == 24
        for row in old_final[arm].values():
            assert sha(Path(row["source_file"])) == row["raw_file_sha256"]
    for arm in new_final:
        assert len(new_final[arm]) == 16
        for row in new_final[arm].values():
            assert sha(Path(row["file"])) == row["file_sha256"]

    input_hashes = {str(p): sha(p) for p in (old_jobs_path, new_jobs_path,
                                             old_score_path, new_score_path)}
    job_comparison = []
    old_raw_32 = {}
    new_raw_32 = {}
    old_settings = old_score["condition_run_provenance"]["base"]["32k"]["settings"]
    old_driver = OLD_DOC / "generate_batch.py"
    new_driver = ROOT / "docs/research/related-numeric-sft-2026-09-28/generate_batch.py"
    assert sha(old_driver) == old_settings["driver_sha256"]
    for arm in ("base", "numeric128"):
        for stage in ("32k", "81k"):
            record = old_score["condition_run_provenance"][arm][stage]
            receipt_path = Path(record["receipt_path"])
            assert sha(receipt_path) == record["receipt_sha256"]
            input_hashes[str(receipt_path)] = sha(receipt_path)
    new_ref_32 = load(NEW / "transfer-reference-base-32768.json")
    new_receipt_32 = load(Path(new_ref_32["directory"]) / "receipt.json")
    assert sha(new_driver) == new_receipt_32["driver_sha256"]
    input_hashes[str(old_driver)] = sha(old_driver)
    input_hashes[str(new_driver)] = sha(new_driver)
    driver_diff = list(difflib.unified_diff(old_driver.read_text().splitlines(),
                                            new_driver.read_text().splitlines(), lineterm=""))
    new_correct128_ref = load(NEW / "transfer-reference-correct128-32768.json")
    new_correct128_receipt = load(Path(new_correct128_ref["directory"]) / "receipt.json")
    old_numeric128_adapter_sha = old_score["condition_run_provenance"]["numeric128"]["32k"]["settings"]["adapter_sha256"]
    assert old_numeric128_adapter_sha != new_correct128_receipt["adapter_sha256"]
    common_settings = ("model_revision", "batch_size", "samples", "temperature", "top_p",
                       "top_k", "presence_penalty", "enable_thinking", "cap", "context")
    setting_diff = {k: {"old": old_settings[k], "new": new_receipt_32[k]}
                    for k in common_settings if old_settings[k] != new_receipt_32[k]}
    for job_id in common:
        a, b = old_jobs[job_id], new_jobs[job_id]
        assert a["source_id"] == b["source_id"] and a["replicate"] == b["replicate"]
        old_path = OLD / "numeric-base-32768" / f"{job_id}-0.json"
        new_path = Path(new_ref_32["directory"]) / f"{job_id}-0.json"
        oa, nb = load(old_path), load(new_path)
        assert sha(old_path) == old_32["base"][job_id]["raw_file_sha256"]
        assert sha(new_path) == new_ref_32["response_sha256"][job_id]
        assert oa["messages"] == a["messages"] and nb["messages"] == b["messages"]
        assert oa["seed"] == a["seed"] and nb["seed"] == b["seed"]
        old_raw_32[job_id], new_raw_32[job_id] = oa, nb
        diff = list(difflib.unified_diff(a["messages"][0]["content"].splitlines(),
                                         b["messages"][0]["content"].splitlines(), lineterm=""))
        job_comparison.append({
            "job_id": job_id, "source_id": a["source_id"],
            "prompt_identical": a["messages"] == b["messages"],
            "prompt_sha256_old": canonical_sha(a["messages"]),
            "prompt_sha256_new": canonical_sha(b["messages"]),
            "prompt_diff": diff,
            "prompt_token_ids_identical": oa["prompt_ids"] == nb["prompt_ids"],
            "prompt_token_ids_sha256_old": canonical_sha(oa["prompt_ids"]),
            "prompt_token_ids_sha256_new": canonical_sha(nb["prompt_ids"]),
            "seed_old": a["seed"], "seed_new": b["seed"],
            "batch_start_old": oa["batch_start"], "batch_start_new": nb["batch_start"],
            "old_final_cap_base": old_final["base"][job_id]["cap"],
            "old_final_cap_numeric128": old_final["numeric128"][job_id]["cap"],
            "new_final_cap_base": new_final["base"][job_id]["cap"],
            "new_final_cap_correct128": new_final["correct128"][job_id]["cap"],
            "new_final_cap_correct512": new_final["correct512"][job_id]["cap"],
            "new_final_cap_shuffled512": new_final["shuffled512"][job_id]["cap"],
            "givens_identical_because_full_problem_text_identical": a["messages"] == b["messages"],
        })

    # Reconstruct each new saved stage for numeric jobs, carrying forward jobs
    # that were not regenerated at that stage. Compare the last stage to the
    # frozen final numeric score, so this analysis cannot silently drift.
    new_stage_rows = {}
    new_stage_direct = {}
    new_prefix_checks = {}
    stage_refs = {}
    targets = {j: new_final["base"][j]["target"] for j in common}
    for arm in new_final:
        carried = {}
        new_stage_rows[arm], new_stage_direct[arm] = {}, {}
        raw_history = {}
        new_prefix_checks[arm] = []
        for cap in (32768, 81920, 131072):
            ref_path = NEW / f"transfer-reference-{arm}-{cap}.json"
            ref = load(ref_path)
            directory = Path(ref["directory"])
            receipt_path = directory / "receipt.json"
            assert sha(receipt_path) == ref["receipt_sha256"]
            input_hashes[str(ref_path)] = sha(ref_path)
            input_hashes[str(receipt_path)] = sha(receipt_path)
            stage_refs[f"{arm}/{cap}"] = {"origin": ref["origin"],
                                          "jobs_sha256": ref["jobs_sha256"],
                                          "receipt_sha256": ref["receipt_sha256"]}
            direct = {}
            for job_id in common:
                if job_id not in ref["response_sha256"]:
                    continue
                path = directory / f"{job_id}-0.json"
                assert sha(path) == ref["response_sha256"][job_id]
                raw = load(path)
                assert raw["messages"] == new_jobs[job_id]["messages"]
                assert raw["seed"] == new_jobs[job_id]["seed"]
                direct[job_id] = score_raw(raw, targets[job_id], cap)
                direct[job_id]["response_sha256"] = sha(path)
                if cap > 32768:
                    first = raw_history["32768"][job_id]["completion_ids"]
                    previous_cap = 32768 if cap == 81920 else 81920
                    previous = raw_history[str(previous_cap)][job_id]["completion_ids"]
                    current = raw["completion_ids"]
                    new_prefix_checks[arm].append({
                        "job_id": job_id, "source_id": new_jobs[job_id]["source_id"], "cap": cap,
                        "first_32k_is_prefix": current[:len(first)] == first,
                        "previous_stage_is_prefix": current[:len(previous)] == previous,
                    })
                raw_history.setdefault(str(cap), {})[job_id] = raw
            carried.update(direct)
            new_stage_direct[arm][str(cap)] = direct
            new_stage_rows[arm][str(cap)] = dict(carried)
        assert len(carried) == 16
        for job_id in common:
            actual = new_final[arm][job_id]
            reconstructed = carried[job_id]
            assert all(actual[k] == reconstructed[k] for k in ("finish_reason", "numeric_correct", "cap")), \
                f"Stage score mismatch {arm}/{job_id}"

    old_stage = {}
    for arm in old_final:
        old_stage[arm] = {}
        for name, ledger in (("32768", old_32[arm]), ("final_81920_or_32768", old_final[arm])):
            old_stage[arm][name] = {
                "common_8_sources": count([ledger[j] for j in common]),
                "removed_4_sources": count([ledger[j] for j in removed]),
                "all_12_sources": count([ledger[j] for j in old_jobs]),
            }
    new_stage = {}
    for arm in new_final:
        new_stage[arm] = {}
        for cap in (32768, 81920, 131072):
            direct = new_stage_direct[arm][str(cap)]
            carried = new_stage_rows[arm][str(cap)]
            new_stage[arm][str(cap)] = {"direct_numeric_jobs": len(direct),
                                        "direct": count(list(direct.values())),
                                        "all_16_with_carry_forward": count(list(carried.values()))}

    old_changes = {}
    for arm in old_final:
        old_changes[arm] = [{"job_id": j, "source_id": old_jobs[j]["source_id"],
                             "at_32768": outcome(old_32[arm][j]),
                             "at_final": outcome(old_final[arm][j]),
                             "prefix_identical_to_32k": next(
                                 x["prefix_identical_to_32k"] for x in old_score["source_ledger"]
                                 if x["condition"] == arm and x["job_id"] == j)}
                            for j in common if outcome_changed(old_32[arm][j], old_final[arm][j])]
    new_changes = {}
    for arm in new_final:
        new_changes[arm] = []
        for cap in (81920, 131072):
            previous = new_stage_rows[arm][str(32768 if cap == 81920 else 81920)]
            direct = new_stage_direct[arm][str(cap)]
            for j, row in direct.items():
                if outcome_changed(previous[j], row):
                    new_changes[arm].append({"job_id": j, "source_id": new_jobs[j]["source_id"],
                                             "from_cap": previous[j]["cap"], "to_cap": cap,
                                             "before": outcome(previous[j]), "after": outcome(row)})

    source_table = []
    for source in sorted(old_source):
        old_ids = sorted(j for j, x in old_jobs.items() if x["source_id"] == source)
        new_ids = sorted(j for j, x in new_jobs.items() if x["source_id"] == source)
        source_table.append({
            "source_id": source, "in_new_evaluation": bool(new_ids), "job_ids": old_ids,
            "old_base": sum(natural(old_final["base"][j]) for j in old_ids),
            "old_numeric128": sum(natural(old_final["numeric128"][j]) for j in old_ids),
            "new_base": sum(natural(new_final["base"][j]) for j in new_ids),
            "new_correct128": sum(natural(new_final["correct128"][j]) for j in new_ids),
            "new_correct512": sum(natural(new_final["correct512"][j]) for j in new_ids),
            "new_shuffled512": sum(natural(new_final["shuffled512"][j]) for j in new_ids),
        })
    cross_run_pair_changes = {}
    for old_arm, new_arm in (("base", "base"), ("numeric128", "correct128")):
        changed = []
        for j in common:
            oa, nb = old_final[old_arm][j], new_final[new_arm][j]
            if natural(oa) != natural(nb):
                changed.append({"job_id": j, "source_id": old_jobs[j]["source_id"],
                                "old_natural_correct": natural(oa),
                                "new_natural_correct": natural(nb),
                                "old_finish": oa["finish_reason"], "new_finish": nb["finish_reason"],
                                "old_cap": oa["cap"], "new_cap": nb["cap"]})
        cross_run_pair_changes[f"{old_arm}_to_{new_arm}"] = changed

    result = {
        "scope": "posthoc common-source comparison; not a randomized causal experiment",
        "input_sha256": input_hashes,
        "source_and_job_sets": {"old_sources": sorted(old_source), "new_sources": sorted(new_source),
                                "removed_sources": sorted(old_source - new_source),
                                "common_job_ids": common, "removed_job_ids": removed},
        "source_table": source_table,
        "old_saved_budgets": old_stage,
        "new_saved_budgets": new_stage,
        "old_budget_outcome_changes_common": old_changes,
        "new_budget_outcome_changes_common": new_changes,
        "new_regeneration_prefix_checks": new_prefix_checks,
        "old_vs_new_final_correctness_changes": cross_run_pair_changes,
        "comparability": {
            "common_32k_generation_settings_differences": setting_diff,
            "old_driver_sha256": old_settings["driver_sha256"],
            "new_driver_sha256": new_receipt_32["driver_sha256"],
            "driver_unified_diff": driver_diff,
            "old_numeric128_adapter_sha256": old_numeric128_adapter_sha,
            "new_correct128_adapter_sha256": new_correct128_receipt["adapter_sha256"],
            "old_base_adapter_sha256": old_settings["adapter_sha256"],
            "new_base_adapter_sha256": new_receipt_32["adapter_sha256"],
            "old_32k_jobs_sha256": old_settings["jobs_sha256"],
            "new_32k_jobs_sha256": new_receipt_32["jobs_sha256"],
            "all_common_prompts_identical": all(x["prompt_identical"] for x in job_comparison),
            "all_common_prompt_token_ids_identical": all(x["prompt_token_ids_identical"] for x in job_comparison),
            "all_common_seeds_differ": all(x["seed_old"] != x["seed_new"] for x in job_comparison),
            "batch_start_changed_count": sum(x["batch_start_old"] != x["batch_start_new"] for x in job_comparison),
            "old_vs_new_final_cap_base_changed_count": sum(x["old_final_cap_base"] != x["new_final_cap_base"] for x in job_comparison),
            "old_vs_new_final_cap_128_changed_count": sum(x["old_final_cap_numeric128"] != x["new_final_cap_correct128"] for x in job_comparison),
            "jobs": job_comparison,
            "new_stage_references": stage_refs,
            "old_81k_retry_job_ids": old_score["retry_union_ids"],
            "new_81k_numeric_job_ids": sorted(new_stage_direct["base"]["81920"]),
            "new_131k_numeric_job_ids": sorted(new_stage_direct["base"]["131072"]),
        },
    }
    path = HERE / "evaluation-comparison.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    old_c = old_stage["base"]["final_81920_or_32768"]["common_8_sources"]["natural_stop_correct"]
    old_t = old_stage["numeric128"]["final_81920_or_32768"]["common_8_sources"]["natural_stop_correct"]
    old_r_c = old_stage["base"]["final_81920_or_32768"]["removed_4_sources"]["natural_stop_correct"]
    old_r_t = old_stage["numeric128"]["final_81920_or_32768"]["removed_4_sources"]["natural_stop_correct"]
    rows = ["# Evaluation comparability audit", "",
            f"Old 12-source result decomposes into common eight sources **{old_c}→{old_t}/16** "
            f"and removed four sources **{old_r_c}→{old_r_t}/8**. "
            "This is a posthoc subset of saved responses, not a newly randomized causal experiment.", "",
            "| Source | Old base/2 | Old numeric128/2 | New base/2 | New correct128/2 | New correct512/2 | New shuffle512/2 |",
            "|---|---:|---:|---:|---:|---:|---:|"]
    for x in source_table:
        rows.append(f"| {x['source_id']} | {x['old_base']} | {x['old_numeric128']} | "
                    f"{x['new_base'] if x['in_new_evaluation'] else '—'} | "
                    f"{x['new_correct128'] if x['in_new_evaluation'] else '—'} | "
                    f"{x['new_correct512'] if x['in_new_evaluation'] else '—'} | "
                    f"{x['new_shuffled512'] if x['in_new_evaluation'] else '—'} |")
    rows += ["", "All 16 common job IDs have byte-identical problem text and identical model prompt-token IDs; hence stated numerical givens are identical. "
             "All 16 inference seeds differ. The 32k model revision, sampling parameters, batch size, cap and context match; "
             f"driver hashes differ (`{old_settings['driver_sha256']}` vs `{new_receipt_32['driver_sha256']}`), "
             "but the source diff only adds the 131k cap/context pair to the allowed bounds. "
             f"Batch-start positions differ for {result['comparability']['batch_start_changed_count']}/16 jobs because the batch job lists changed. "
             "Final caps differ in "
             f"{result['comparability']['old_vs_new_final_cap_base_changed_count']}/16 base jobs and "
             f"{result['comparability']['old_vs_new_final_cap_128_changed_count']}/16 128-update jobs. "
             "The JSON contains per-job seed, prompt/hash, token-hash, batch and cap comparisons and empty prompt diffs.", "",
             "The old 128-update numeric adapter was trained on 56 examples in seven constructions; the new correct128 "
             "adapter was trained on 80 examples in ten constructions. Their adapter hashes differ "
             f"(`{old_numeric128_adapter_sha}` vs `{new_correct128_receipt['adapter_sha256']}`). "
             "Thus only the base condition reuses the same checkpoint across studies; the two 128-update SFT results "
             "also differ in training data. Their cross-run answer flips cannot be assigned solely to inference changes.", "",
             "## Saved-budget outcomes", "",
             "| Evaluation/arm | 32k common | 81k-with-carry common | 131k-with-carry common |",
             "|---|---:|---:|---:|"]
    for arm in ("base", "numeric128"):
        initial = old_stage[arm]["32768"]["common_8_sources"]
        final = old_stage[arm]["final_81920_or_32768"]["common_8_sources"]
        rows.append(f"| Old {arm} | {initial['natural_stop_correct']}/16 (stop {initial['natural_stop']}) | "
                    f"{final['natural_stop_correct']}/16 (stop {final['natural_stop']}) | — |")
    for arm in new_final:
        cells = []
        for cap in (32768, 81920, 131072):
            x = new_stage[arm][str(cap)]["all_16_with_carry_forward"]
            cells.append(f"{x['natural_stop_correct']}/16 (stop {x['natural_stop']})")
        rows.append(f"| New {arm} | " + " | ".join(cells) + " |")
    rows += ["", "The 81k/131k columns carry forward non-regenerated jobs. The response at a larger cap is a fresh sample, "
             "not a continuation of the 32k prefix; exact token-prefix checks for every regenerated new response are "
             "recorded in the JSON, alongside the old saved prefix ledger. All saved stage-specific outcome changes and final cross-run job flips "
             "are enumerated in the JSON. Consequently, observed one- or two-answer differences across runs can be "
             "consistent with changed inference seeds, batch composition and selective regeneration; this audit cannot "
             "apportion their effects or infer what would have happened under identical seeds.", "",
             "The old 11→16/24 gain includes **3** net answers in the retained sources and **2** in the four omitted sources. "
             "The new 16-job score and old restricted score therefore differ in both evaluation composition and stochastic "
             "realizations. A matched-seed, matched-job-list replication is needed to attribute a transfer difference to training.", "",
             f"Reproduce: `.venv/bin/python {path.parent / 'compare_evaluations.py'}`. "
             "This script reads saved jobs, receipts, responses and score ledgers only; it does not generate or train a model."]
    (HERE / "evaluation-comparison.md").write_text("\n".join(rows) + "\n")
    print(json.dumps({"old_common": [old_c, old_t], "old_removed": [old_r_c, old_r_t],
                      "report": str(path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
