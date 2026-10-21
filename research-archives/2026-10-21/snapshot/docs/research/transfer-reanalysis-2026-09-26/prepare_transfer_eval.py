"""Prepare an exploratory numeric transfer evaluation; never launches a model.

The checkpoints have not trained on these configuration IDs. This is not a
claim of pretraining decontamination or a previously unused research benchmark.
"""
import hashlib
import json
import runpy
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BENCH = ROOT / "benchmarks/humpty_configurations_v2"
RESEARCH = ROOT / "docs/research"
TEMPLATE = RESEARCH / "qwen35-diverse-sft-2026-09-24/english_templates.py"
GROUPS = {
    "related_construction": ["H02", "H03", "H08", "DA03", "DA06", "DA15"],
    "different_construction_or_composition": ["H12", "DA07", "DA11", "DB01", "DB08", "DB16"],
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def main():
    training_paths = {
        "opd": RESEARCH / "answer-opd-pilot-2026-09-26/train-pool.json",
        "code32": ROOT / "qwen/.runtime/program_self_training_20260926/selection/train-code.json",
        "numeric32": ROOT / "qwen/.runtime/program_self_training_20260926/selection/train-numeric.json",
    }
    training_ids = {k: sorted({r["source_id"] for r in json.loads(p.read_text())})
                    for k, p in training_paths.items()}
    selected = {cid for group in GROUPS.values() for cid in group}
    assert len(selected) == 12
    assert all(not selected.intersection(ids) for ids in training_ids.values())
    variants = [json.loads(line) for line in (BENCH / "training_variants.jsonl").read_text().splitlines()]
    originals = {r["id"]: r for r in variants if r["variant"] == "v0"}
    catalogue = {r["id"]: r for r in json.loads((BENCH / "revisions.json").read_text())}
    templates = runpy.run_path(str(TEMPLATE))["NUMERIC_EN"]
    jobs, keys, units = [], [], []
    for group, ids in GROUPS.items():
        for cid in ids:
            row = originals[cid]
            prompt = ("Solve the following geometry problem. Give the exact numerical answer "
                      "and explain your reasoning in English. You have no access to tools.\n\n"
                      + templates[cid].format(**row["givens"]))
            units.append({"source_id": cid, "group": group,
                          "legacy_structural_group": catalogue[cid]["legacy_structural_group"],
                          "query": catalogue[cid]["query"],
                          "variant": "v0", "augmentation": row["augmentation"]})
            for replicate in (1, 2):
                jid = f"numeric-transfer-{cid.lower()}-s{replicate}"
                seed = int(hashlib.sha256(jid.encode()).hexdigest()[:8], 16) % (2**31)
                jobs.append({"id": jid, "source_id": cid, "variant": "v0",
                             "replicate": replicate, "seed": seed,
                             "evaluation_role": "untrained_configuration_numeric_solution",
                             "transfer_group": group,
                             "messages": [{"role": "user", "content": prompt}]})
                keys.append({"id": jid, "source_id": cid, "answer_exact": row["answer_exact"]})
    assert len(jobs) == len(keys) == 24
    assert len({j["id"] for j in jobs}) == 24
    # Answer keys and researcher solutions are never put in the model job file.
    assert all(set(j).isdisjoint({"answer_exact", "geometry_solution_ja"}) for j in jobs)
    write("eval-jobs.json", jobs)
    write("answer-key.researcher-only.json", keys)
    write("manifest.json", {
        "status": "prepared_not_executed",
        "scope": "Exploratory checkpoint transfer audit, not a fresh confirmatory benchmark.",
        "conditions": ["base", "code32", "numeric32"],
        "training_source_ids": training_ids,
        "configuration_overlap": {k: [] for k in training_ids},
        "units": units, "configuration_count": 12,
        "jobs_per_condition": 24, "total_model_outputs": 72,
        "replicates_are": "Two decoding seeds for one numerical problem per configuration, not independent problems or training seeds.",
        "group_warning": "Researcher-assigned construction groups; all draw on the same broad geometry domain. No claim of disjoint underlying theorem families.",
        "variant_warning": "Ten selected IDs have only similarity variants in the existing pool; v0 alone is used here. Independent non-similar follow-up needs new audited instances.",
        "generation": {"cap": 32768, "context": 40960, "samples": 1,
                       "temperature": 0.7, "top_p": 0.95, "top_k": 20,
                       "presence_penalty": 0.2, "thinking": False},
        "truncation_policy": "Retain all outcomes. For any capped job, repeat the matched job in all three conditions at cap 81920/context 98304 with the original seed. Report both budgets; unresolved caps remain censored, not mathematical counterevidence.",
        "source_hashes": {str(p.relative_to(ROOT)): digest(p) for p in
                          [*training_paths.values(), TEMPLATE, BENCH / "training_variants.jsonl", BENCH / "revisions.json"]},
        "output_hashes": {n: digest(HERE / n) for n in ["eval-jobs.json", "answer-key.researcher-only.json"]},
    })
    print(json.dumps({"status": "prepared_not_executed", "configurations": 12,
                      "jobs_per_condition": 24, "training_id_overlap": False}))


if __name__ == "__main__":
    main()
