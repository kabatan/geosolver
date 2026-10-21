#!/usr/bin/env python3
"""CPU-only comparison of the successful 56-row and later 80-row numeric SFT recipes.

Reads frozen training data/configs/receipts and already-saved loss-probe summaries.
It does not import a model, tokenize new text, start training, or inspect evaluation
answers. Run from any directory with Python 3:

  python3 docs/research/numeric-sft-success-failure-analysis-2026-09-28/recipe-comparison.py
"""
from __future__ import annotations

from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
OUT_DIR = Path(__file__).resolve().parent
NUMERIC = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")
NUMBER = re.compile(r"(?<![A-Za-z_])[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")


def read_json(rel: str) -> Any:
    return json.loads((ROOT / rel).read_text())


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_file(rel: str) -> str:
    return digest_bytes((ROOT / rel).read_bytes())


def median(values: list[float]) -> float:
    return statistics.median(values)


def target_signature(text: str) -> int:
    mantissa = re.split("[eE]", text, maxsplit=1)[0]
    digits = "".join(ch for ch in mantissa if ch.isdigit()).lstrip("0").rstrip("0")
    return max(1, len(digits))


def numeric_stats(targets: list[str]) -> dict[str, Any]:
    decimals = [Decimal(x) for x in targets]
    values = [float(x) for x in decimals]
    places = [max(0, -x.as_tuple().exponent) for x in decimals]
    sig = [target_signature(x) for x in targets]
    abs_values = [abs(x) for x in values]
    return {
        "count": len(targets),
        "numeric_only_count": sum(bool(NUMERIC.fullmatch(x)) for x in targets),
        "exact_python_17g_count": sum(format(float(x), ".17g") == x for x in targets),
        "positive_count": sum(x > 0 for x in decimals),
        "negative_count": sum(x < 0 for x in decimals),
        "zero_count": sum(x == 0 for x in decimals),
        "minimum": min(values),
        "median": median(values),
        "mean": statistics.fmean(values),
        "maximum": max(values),
        "absolute_minimum": min(abs_values),
        "absolute_maximum": max(abs_values),
        "scale_bins_abs": {
            "below_1": sum(x < 1 for x in abs_values),
            "1_to_below_10": sum(1 <= x < 10 for x in abs_values),
            "10_or_more": sum(x >= 10 for x in abs_values),
        },
        "decimal_places_min_median_max": [min(places), median(places), max(places)],
        "significant_digits_min_median_max": [min(sig), median(sig), max(sig)],
        "significant_digits_histogram": {
            str(k): v for k, v in sorted(Counter(sig).items())
        },
        "target_characters_min_median_max": [
            min(map(len, targets)), median(list(map(float, map(len, targets)))), max(map(len, targets))
        ],
    }


def summarize_dataset(name: str, data_rel: str, token_rel: str) -> dict[str, Any]:
    raw = (ROOT / data_rel).read_bytes()
    rows = json.loads(raw)
    token_rows = read_json(token_rel)
    token_by_id = {x["id"]: x for x in token_rows}
    if len(token_by_id) != len(token_rows) or set(token_by_id) != {x["id"] for x in rows}:
        raise ValueError(f"tokenization IDs do not exactly cover {name}")
    if not rows:
        raise ValueError(f"empty dataset: {name}")

    prefixes = [x["messages"][0]["content"].split("\n\n", 1)[0] for x in rows]
    prefix = prefixes[0]
    if any(x != prefix for x in prefixes):
        raise ValueError(f"instruction prefix varies within {name}")
    bodies: dict[str, list[dict[str, Any]]] = defaultdict(list)
    target_strings = []
    template_keys = set()
    target_hash_matches = 0
    row_stats = []
    for row in rows:
        if row.get("kind") != "numeric" or len(row.get("messages", [])) != 1:
            raise ValueError(f"unexpected training row schema: {row.get('id')}")
        content = row["messages"][0]["content"]
        if not content.startswith(prefix + "\n\n"):
            raise ValueError(f"prompt does not begin with exact training prefix: {row['id']}")
        body = content[len(prefix) + 2 :]
        target = row["target"]
        target_strings.append(target)
        tok = token_by_id[row["id"]]
        target_hash_matches += hashlib.sha256(target.encode()).hexdigest() == tok["target_text_sha256"]
        literals = NUMBER.findall(body)
        decimal_literals = [x for x in literals if "." in x or "e" in x.lower()]
        normalized = NUMBER.sub("<N>", body)
        template_keys.add(normalized)
        item = {
            "id": row["id"],
            "body": body,
            "normalized_body": normalized,
            "numeric_literal_count": len(literals),
            "decimal_literal_count": len(decimal_literals),
            "prompt_tokens": tok["prompt_tokens"],
            "target_tokens_including_eos": tok["target_tokens"],
            "prompt_characters": len(content),
            "target": target,
        }
        bodies[row["source_id"]].append(item)
        row_stats.append(item)

    if target_hash_matches != len(rows):
        raise ValueError(f"target hashes do not match saved tokenization for {name}")
    groups = {}
    for source, items in sorted(bodies.items()):
        targets = [x["target"] for x in items]
        num_givens = [x["numeric_literal_count"] for x in items]
        dec_givens = [x["decimal_literal_count"] for x in items]
        prompt_tok = [x["prompt_tokens"] for x in items]
        target_tok = [x["target_tokens_including_eos"] for x in items]
        prompt_chars = [x["prompt_characters"] for x in items]
        groups[source] = {
            "examples": len(items),
            "normalized_shape_templates": len({x["normalized_body"] for x in items}),
            "numeric_literals_per_prompt_min_median_max": [min(num_givens), median(num_givens), max(num_givens)],
            "decimal_literals_per_prompt_min_median_max": [min(dec_givens), median(dec_givens), max(dec_givens)],
            "prompt_tokens_min_median_max": [min(prompt_tok), median(prompt_tok), max(prompt_tok)],
            "target_tokens_including_eos_min_median_max": [min(target_tok), median(target_tok), max(target_tok)],
            "prompt_characters_min_median_max": [min(prompt_chars), median(prompt_chars), max(prompt_chars)],
            "target": numeric_stats(targets),
            "normalized_shape_preview": items[0]["normalized_body"][:260].replace("\n", " "),
        }

    prompt_tokens = [x["prompt_tokens"] for x in row_stats]
    target_tokens = [x["target_tokens_including_eos"] for x in row_stats]
    prompt_characters = [x["prompt_characters"] for x in row_stats]
    all_numeric_literals = [x["numeric_literal_count"] for x in row_stats]
    all_decimal_literals = [x["decimal_literal_count"] for x in row_stats]
    return {
        "name": name,
        "path": data_rel,
        "sha256": digest_bytes(raw),
        "bytes": len(raw),
        "rows": len(rows),
        "unique_ids": len({x["id"] for x in rows}),
        "source_count": len(bodies),
        "examples_per_source": sorted(Counter(x["source_id"] for x in rows).values()),
        "source_ids": sorted(bodies),
        "source_groups": groups,
        "unique_normalized_shape_templates": len(template_keys),
        "instruction_prefix": prefix,
        "instruction_prefix_characters": len(prefix),
        "instruction_prefix_sha256": digest_bytes(prefix.encode()),
        "instruction_prefixes_all_identical": True,
        "prompt_tokens_min_median_max": [min(prompt_tokens), median(prompt_tokens), max(prompt_tokens)],
        "target_tokens_including_eos_min_median_max": [min(target_tokens), median(target_tokens), max(target_tokens)],
        "prompt_characters_min_median_max": [min(prompt_characters), median(prompt_characters), max(prompt_characters)],
        "numeric_literals_per_prompt_min_median_max": [min(all_numeric_literals), median(all_numeric_literals), max(all_numeric_literals)],
        "decimal_literals_per_prompt_min_median_max": [min(all_decimal_literals), median(all_decimal_literals), max(all_decimal_literals)],
        "tokenization_rows": len(token_rows),
        "tokenization_target_hash_matches": target_hash_matches,
        "unique_target_token_sum_including_eos": sum(target_tokens),
        "target": numeric_stats(target_strings),
        "ids": [x["id"] for x in rows],
        "messages_by_id": {x["id"]: x["messages"] for x in rows},
    }


TRAIN_PARAMETER_KEYS = [
    "seed", "learning_rate", "grad_accumulation", "grad_clip", "lora_rank",
    "lora_alpha", "lora_modules", "ce_chunk_tokens", "max_target_tokens",
    "max_sequence_tokens", "enable_thinking",
]


def run_summary(name: str, config_rel: str, receipt_rel: str) -> dict[str, Any]:
    config = read_json(config_rel)
    receipt = read_json(receipt_rel)
    return {
        "name": name,
        "config_path": config_rel,
        "config_sha256": digest_file(config_rel),
        "config": {k: config.get(k) for k in [
            "dataset_sha256", "model_revision", "updates", "seed", "learning_rate",
            "grad_accumulation", "grad_clip", "lora_rank", "lora_alpha", "lora_modules",
            "ce_chunk_tokens", "max_target_tokens", "max_sequence_tokens", "enable_thinking",
            "prior_checkpoint", "protocol_sha256", "extension_wrapper_sha256",
        ]},
        "receipt_path": receipt_rel,
        "receipt": {k: receipt.get(k) for k in [
            "status", "updates", "global_updates", "examples_processed", "n_examples",
            "dataset_sha256", "model_revision", "driver_sha256", "harness_sha256",
            "unique_target_tokens", "planned_target_tokens", "trained_target_tokens",
            "optimizer_step_min", "optimizer_step_max", "optimizer_state_loaded",
            "prior_checkpoint", "final_checkpoint", "adapter_sha256", "vllm_adapter_sha256",
            "processed_order_sha256",
        ]},
        "receipt_training_parameters": {k: receipt.get("training_parameters", {}).get(k) for k in TRAIN_PARAMETER_KEYS},
    }


def probe_comparison() -> dict[str, Any]:
    base = read_json("qwen/.runtime/related_numeric_sft_20260928/base-digit-probe/summary.json")
    trained = read_json("qwen/.runtime/related_numeric_sft_20260928/sft-a-digit-probe/summary.json")
    groups = {}
    base_train = base["train"]["groups"]
    trained_train = trained["train"]["groups"]
    target_count = base_train["all_target"]["token_count"]
    total_delta = trained_train["all_target"]["token_weighted_mean_ce"] - base_train["all_target"]["token_weighted_mean_ce"]
    for name in ["leading_6_digits", "remaining_digits", "format_only", "eos", "all_target"]:
        b = base_train[name]
        t = trained_train[name]
        groups[name] = {
            "token_count": b["token_count"],
            "base_token_weighted_mean_ce": b["token_weighted_mean_ce"],
            "sft_a_token_weighted_mean_ce": t["token_weighted_mean_ce"],
            "ce_delta_sft_minus_base": t["token_weighted_mean_ce"] - b["token_weighted_mean_ce"],
            "base_token_weighted_top1_accuracy": b["token_weighted_top1_accuracy"],
            "sft_a_token_weighted_top1_accuracy": t["token_weighted_top1_accuracy"],
            "top1_delta_sft_minus_base": t["token_weighted_top1_accuracy"] - b["token_weighted_top1_accuracy"],
            "contribution_to_all_target_ce_delta": (
                (t["token_weighted_mean_ce"] - b["token_weighted_mean_ce"])
                * b["token_count"] / target_count
            ) if name != "all_target" else total_delta,
        }
    new_shape = {}
    for name in ["leading_6_digits", "remaining_digits", "format_only", "eos", "all_target"]:
        b = base["new_shape"]["groups"][name]
        t = trained["new_shape"]["groups"][name]
        new_shape[name] = {
            "token_count": b["token_count"],
            "base_token_weighted_mean_ce": b["token_weighted_mean_ce"],
            "sft_a_token_weighted_mean_ce": t["token_weighted_mean_ce"],
            "ce_delta_sft_minus_base": t["token_weighted_mean_ce"] - b["token_weighted_mean_ce"],
            "base_token_weighted_top1_accuracy": b["token_weighted_top1_accuracy"],
            "sft_a_token_weighted_top1_accuracy": t["token_weighted_top1_accuracy"],
        }
    return {
        "scope": "Existing saved token-level teacher-forced probe; scores each target token with the complete gold target prefix available.",
        "probe_definition": "first six significant-digit tokens (leading zero ignored; sign, decimal/exponent markers, and EOS excluded), remaining digit tokens, formatting-only tokens, and EOS; tokenizer decode units were checked by the probe.",
        "train": {
            "base_examples": base["train"]["examples"],
            "sft_a_examples": trained["train"]["examples"],
            "groups": groups,
        },
        "new_shape": {
            "base_examples": base["new_shape"]["examples"],
            "sft_a_examples": trained["new_shape"]["examples"],
            "groups": new_shape,
        },
        "old_56_digit_probe": "not measured in the saved recipe artifacts inspected; old training-loss diagnostic is aggregate/position-indexed teacher-forced loss, not first-significant-digit versus remaining-digit groups.",
    }


def make_report(result: dict[str, Any]) -> str:
    old = result["datasets"]["old56"]
    new = result["datasets"]["new80"]
    dose = result["datasets"]["dose_correct80"]
    o, n = old["target"], new["target"]
    probe = result["digit_probe"]
    train_probe = probe["train"]["groups"]
    source_tables = []
    for dataset_key, label in [("old56", "old56"), ("new80", "new80")]:
        ds = result["datasets"][dataset_key]
        source_tables.extend([
            f"### {label} source families",
            "",
            "| Source | N | Decimal givens, median | Prompt tokens, median | Target range | Normalized construction preview |",
            "|---|---:|---:|---:|---:|---|",
        ])
        for source, group in ds["source_groups"].items():
            lo, hi = group["target"]["minimum"], group["target"]["maximum"]
            preview = group["normalized_shape_preview"].replace("|", "\\|")[:105]
            source_tables.append(
                f"| {source} | {group['examples']} | {group['decimal_literals_per_prompt_min_median_max'][1]:g} | "
                f"{group['prompt_tokens_min_median_max'][1]:g} | {lo:.5g}–{hi:.5g} | {preview} |"
            )
        source_tables.append("")
    lines = [
        "# Numeric SFT: successful 56-row versus 80-row recipe comparison",
        "",
        "This is a read-only CPU audit of the frozen training datasets, configs, trainer receipts, tokenization receipts, and already-saved digit-probe summaries. It did not run a model or inspect held-out answer keys. The differences below are observed confounds; this audit alone does not identify a single causal factor.",
        "",
        "## What stayed fixed",
        "",
        f"Both recipes use **{result['model']['model_id']}** at revision `{result['model']['revision']}`, the same `train_sft.py` driver hash and harness hash, LoRA rank/alpha/modules, AdamW (`weight_decay=0`), learning rate `5e-6`, gradient accumulation 4, clip 1.0, target/sequence caps 4096/8192, CE chunk 64, and `enable_thinking=false`. At 128 cumulative updates, both have 512 example presentations. The matched primary seed is `{result['recipe_comparison']['seed_old_and_new_a']}`.",
        "",
        f"The exact English instruction prefix is byte-identical across every row: `{old['instruction_prefix']}` Its SHA-256 is `{old['instruction_prefix_sha256']}`. Both datasets enforce one user prompt and a numeric-only assistant target; target strings pass the Python `.17g` round-trip check ({o['exact_python_17g_count']}/{old['rows']} old, {n['exact_python_17g_count']}/{new['rows']} new). The trainer masks loss to the assistant target including EOS. The body after the prefix is different geometry content and different numeric instances.",
        "",
        "The dose-control `train-correct.json` is byte-identical to the 80-row related-SFT `train.json`; it is the same training data, not a third dataset. Its longer 512-update run changes the training dose, not the 80 prompt/target pairs.",
        "",
        "## What changed in the 128-update comparison",
        "",
        f"The old dataset has **{old['rows']} rows / {old['source_count']} normalized shape templates** ({', '.join(old['source_ids'])}); the new dataset has **{new['rows']} rows / {new['source_count']} templates** ({', '.join(new['source_ids'])}). Each source family has 8 numeric parameterizations. Only the family label `DA01` is shared; row IDs do not overlap. Same label does not establish identical prompts: this audit compares rendered bodies, not labels alone.",
        f"At 128 updates, both chains process 512 examples and nearly the same number of assistant target tokens: **{result['recipes']['old128']['receipt']['planned_target_tokens']:,} old vs {result['recipes']['new_a128']['receipt']['planned_target_tokens']:,} new** (including the EOS tokens counted in tokenization). Per-example repeat exposure nevertheless falls from 512/56 = **{512/old['rows']:.2f}** to 512/80 = **{512/new['rows']:.2f}** presentations per row on average. This is the clearest recipe-level dose difference at fixed updates: equal total presentations, broader set, fewer repeats per item. The dataset cardinality also changes the deterministic order, even with the same seed.",
        f"Prompt/token counts: the old prompt is {old['prompt_tokens_min_median_max'][1]:.1f} tokens median and the new prompt {new['prompt_tokens_min_median_max'][1]:.1f}; target is {old['target_tokens_including_eos_min_median_max'][1]:.1f} vs {new['target_tokens_including_eos_min_median_max'][1]:.1f} tokens median (target-token counts include EOS). The output lengths are close; the new tasks are not simply longer numeric labels.",
        f"Target-value distribution changes materially: old range **{o['minimum']:.6g}–{o['maximum']:.6g}** (median {o['median']:.6g}; {o['scale_bins_abs']['below_1']} below 1), new range **{n['minimum']:.6g}–{n['maximum']:.6g}** (median {n['median']:.6g}; {n['scale_bins_abs']['below_1']} below 1). The old set includes a much larger upper tail; the new set adds sub-unit values. Lexical significant-digit counts are {o['significant_digits_min_median_max']} old vs {n['significant_digits_min_median_max']} new; both are rounded through the same `.17g` formatting rule.",
        "",
        "Shape breadth also changes. The old families include orthocenter/midpoint-foot constructions (H01/H04), a two-circle configuration (H07), tangent/circle geometry (H13/H15, DA01/DA05); the 80-row set mixes ten distinct bodies including tangent-circle, Fermat-point/circumcenter, chord-interior tangency, midpoint, and cevian constructions. Source IDs are construction labels, not proof that all prompts within the set have equal mathematical complexity. The per-family shape previews, input-literal counts, prompt lengths, and output ranges are preserved in the JSON for inspection.",
        "",
        *source_tables,
        "## Saved digit-loss diagnostic",
        "",
        f"The available 80-row probe compares base to SFT-A-128 under **teacher forcing**: each token is evaluated with the full correct answer prefix. On the 80 training rows, all-target token-weighted CE is {train_probe['all_target']['base_token_weighted_mean_ce']:.3f} → {train_probe['all_target']['sft_a_token_weighted_mean_ce']:.3f} (Δ {train_probe['all_target']['ce_delta_sft_minus_base']:.3f}). The target has {train_probe['all_target']['token_count']} scored tokens: the first six significant digits contribute Δ {train_probe['leading_6_digits']['contribution_to_all_target_ce_delta']:.3f} to the all-target change, remaining digits Δ {train_probe['remaining_digits']['contribution_to_all_target_ce_delta']:.3f}, format tokens Δ {train_probe['format_only']['contribution_to_all_target_ce_delta']:.3f}, while EOS contributes **+{train_probe['eos']['contribution_to_all_target_ce_delta']:.3f}** (worse). Most of the CE reduction therefore comes from later digits, with a smaller first-six-digit gain; token/format loss also improves and EOS loss worsens. This is a conditional next-token fit result, not evidence that the model can generate a correct answer unaided.",
        "",
        f"The 80-row SFT-A-128 also has a saved posthoc greedy direct-number fit summary: {result['new80_greedy_fit']['sft_a']['trained_all']['within_10pct']} / {result['new80_greedy_fit']['sft_a']['trained_all']['n']} training answers and {result['new80_greedy_fit']['sft_a']['new_shape']['within_10pct']} / {result['new80_greedy_fit']['sft_a']['new_shape']['n']} new-shape answers are within 10%. The old 56-row saved loss diagnostic is also teacher-forced, but it reports aggregate loss by presentation and token-weighted aggregates rather than these semantic digit groups. No comparable old56 first-six-versus-remaining-digit probe or exact-training-prompt greedy/free-generation fit score was found in the old recipe artifacts inspected.",
        "",
        "## Interpretation",
        "",
        "The training recipe machinery is effectively held constant between old128 and new A128; the observed changes are in the teaching set and its per-example exposure. The new 80-row set offers three more source shapes and expands numeric scale downward below 1 while dropping the old extreme upper tail. It also reduces average repeats per example by about 30% at the same optimizer-step count, even though total target-token presentations remain within 0.6%. Any of these could matter, and they change together. The comparison cannot say which caused the outcome. The dose-control correct512 run is a separate dose comparison (512 updates, 25.6 mean passes through the 80 rows), not evidence that 128-update differences are caused by the learning rate or optimizer.",
        "",
        f"A minimal next causal check, if needed, is to score the saved old128 adapter on its exact 56 training prompts with the same greedy decoding settings used by the 80-row direct-fit diagnostic, then compare each dataset's train-fit to its own held-out transfer under a common generation seed. This would fill the missing old free-generation-fit baseline; it would not by itself isolate dataset breadth from repetitions. The exact old adapter is `qwen/.runtime/program_self_training_followup_20260926/train-numeric128/final/adapter-vllm` (saved VLLM adapter SHA-256: `{result['recipes']['old128']['receipt']['vllm_adapter_sha256']}`).",
        "",
        "## Reproduction",
        "",
        "Run `python3 docs/research/numeric-sft-success-failure-analysis-2026-09-28/recipe-comparison.py` from the repository root. It reads only the frozen training data/config/receipts and the saved CE summaries, then regenerates this report and `recipe-comparison.json`.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    old = summarize_dataset(
        "old56",
        "qwen/.runtime/program_self_training_20260926/selection/train-numeric.json",
        "qwen/.runtime/program_self_training_20260926/train-numeric/tokenization.json",
    )
    new = summarize_dataset(
        "new80",
        "qwen/.runtime/related_numeric_sft_20260928/train.json",
        "qwen/.runtime/related_numeric_sft_20260928/sft-a-train32/tokenization.json",
    )
    dose = summarize_dataset(
        "dose_correct80",
        "qwen/.runtime/numeric_sft_dose_control_20260928/train-correct.json",
        "qwen/.runtime/numeric_sft_dose_control_20260928/correct-train512/tokenization.json",
    )
    if dose["sha256"] != new["sha256"] or dose["messages_by_id"] != new["messages_by_id"]:
        raise ValueError("dose-control correct data is not identical to related numeric train data")
    common_ids = sorted(set(old["ids"]) & set(new["ids"]))
    exact_common_prompts = [
        x for x in common_ids if old["messages_by_id"][x] == new["messages_by_id"][x]
    ]
    old_config = read_json("docs/research/program-self-training-followup-2026-09-26/config-numeric128.json")
    new_config = read_json("docs/research/related-numeric-sft-2026-09-28/config-sft-a-128.json")
    keys = [
        "model_metadata_sha256", "model_revision", "updates", "seed", "learning_rate",
        "grad_accumulation", "grad_clip", "lora_rank", "lora_alpha", "lora_modules",
        "ce_chunk_tokens", "max_target_tokens", "max_sequence_tokens", "enable_thinking",
    ]
    matching = [k for k in keys if old_config.get(k) == new_config.get(k)]
    differing = [k for k in keys if old_config.get(k) != new_config.get(k)]
    recipes = {
        "old32": run_summary(
            "old numeric 32-step start",
            "docs/research/program-self-training-2026-09-26/config-numeric.json",
            "qwen/.runtime/program_self_training_20260926/train-numeric/receipt.json",
        ),
        "old128": run_summary(
            "old numeric cumulative 128-step final",
            "docs/research/program-self-training-followup-2026-09-26/config-numeric128.json",
            "qwen/.runtime/program_self_training_followup_20260926/train-numeric128/receipt.json",
        ),
        "new_a32": run_summary(
            "new 80-row SFT-A 32-step start",
            "docs/research/related-numeric-sft-2026-09-28/config-sft-a-32.json",
            "qwen/.runtime/related_numeric_sft_20260928/sft-a-train32/receipt.json",
        ),
        "new_a128": run_summary(
            "new 80-row SFT-A cumulative 128-step final",
            "docs/research/related-numeric-sft-2026-09-28/config-sft-a-128.json",
            "qwen/.runtime/related_numeric_sft_20260928/sft-a-train128/receipt.json",
        ),
        "new_b128": run_summary(
            "new 80-row independent-seed SFT-B cumulative 128-step final",
            "docs/research/related-numeric-sft-2026-09-28/config-sft-b-128.json",
            "qwen/.runtime/related_numeric_sft_20260928/sft-b-train128/receipt.json",
        ),
        "dose_correct512": run_summary(
            "same new 80-row data cumulative 512-step correct arm",
            "docs/research/numeric-sft-dose-control-2026-09-28/config-correct-512.json",
            "qwen/.runtime/numeric_sft_dose_control_20260928/correct-train512/receipt.json",
        ),
    }
    old_diag = read_json("docs/research/program-self-training-followup-2026-09-26/training-loss-diagnostic.json")
    greedy = read_json("qwen/.runtime/related_numeric_sft_20260928/greedy-fit-scores.json")
    greedy_sft_a = greedy["summary"]["sft-a"]
    result = {
        "schema_version": 1,
        "generated_by": "recipe-comparison.py; standard-library CPU audit only",
        "inputs": {
            "old_data": old["path"],
            "new_data": new["path"],
            "dose_correct_data": dose["path"],
            "saved_probe_summaries": [
                "qwen/.runtime/related_numeric_sft_20260928/base-digit-probe/summary.json",
                "qwen/.runtime/related_numeric_sft_20260928/sft-a-digit-probe/summary.json",
            ],
        },
        "model": read_json("docs/research/qwen35-self-materials-2026-09-23/model.json"),
        "trainer": {
            "path": "docs/research/program-self-training-2026-09-26/train_sft.py",
            "sha256": digest_file("docs/research/program-self-training-2026-09-26/train_sft.py"),
            "driver_sha256_old_receipt": recipes["old128"]["receipt"]["driver_sha256"],
            "driver_sha256_new_receipt": recipes["new_a128"]["receipt"]["driver_sha256"],
            "harness_sha256_old_receipt": recipes["old128"]["receipt"]["harness_sha256"],
            "harness_sha256_new_receipt": recipes["new_a128"]["receipt"]["harness_sha256"],
            "optimizer": "torch.optim.AdamW",
            "weight_decay": 0,
            "target_loss_mask": "assistant target including EOS only",
            "tokenization": "apply_chat_template; add_generation_prompt for prompt; gold assistant target plus EOS; no thinking",
            "tokenization_receipt_note": "saved target_tokens includes EOS and each target hash was rechecked against the raw target string",
        },
        "datasets": {"old56": old, "new80": new, "dose_correct80": dose},
        "recipe_comparison": {
            "128_update_config_fields_equal": matching,
            "128_update_config_fields_different": differing,
            "seed_old_and_new_a": old_config["seed"],
            "common_example_ids": common_ids,
            "common_ids_with_byte_identical_full_prompt": exact_common_prompts,
            "old_stage32_presentations": recipes["old32"]["receipt"]["examples_processed"],
            "old_stage32_to128_presentations": recipes["old128"]["receipt"]["examples_processed"],
            "old_cumulative_presentations_at_128": recipes["old128"]["receipt"]["global_updates"] * recipes["old128"]["receipt_training_parameters"]["grad_accumulation"],
            "new_stage32_presentations": recipes["new_a32"]["receipt"]["examples_processed"],
            "new_stage32_to128_presentations": recipes["new_a128"]["receipt"]["examples_processed"],
            "new_cumulative_presentations_at_128": recipes["new_a128"]["receipt"]["global_updates"] * recipes["new_a128"]["receipt_training_parameters"]["grad_accumulation"],
            "old_avg_presentations_per_example": 512 / old["rows"],
            "new_avg_presentations_per_example": 512 / new["rows"],
            "old128_planned_target_tokens": recipes["old128"]["receipt"]["planned_target_tokens"],
            "new128_planned_target_tokens": recipes["new_a128"]["receipt"]["planned_target_tokens"],
            "old128_target_token_exposure_delta_new_minus_old": recipes["new_a128"]["receipt"]["planned_target_tokens"] - recipes["old128"]["receipt"]["planned_target_tokens"],
            "old32_to128_prior_chain": recipes["old128"]["receipt"]["prior_checkpoint"],
            "new_a32_to128_prior_chain": recipes["new_a128"]["receipt"]["prior_checkpoint"],
            "new_dose512_cumulative_steps": recipes["dose_correct512"]["receipt"]["global_updates"],
            "new_dose512_planned_target_tokens": recipes["dose_correct512"]["receipt"]["planned_target_tokens"],
            "new_dose512_avg_presentations_per_example": 2048 / new["rows"],
            "non_training_config_differences": {
                "dataset_path_old": old_config["dataset"],
                "dataset_path_new": new_config["dataset"],
                "dataset_sha256_old": old_config["dataset_sha256"],
                "dataset_sha256_new": new_config["dataset_sha256"],
                "protocol_sha256_old": old_config.get("protocol_sha256"),
                "protocol_sha256_new": new_config.get("protocol_sha256"),
                "prior_checkpoint_old": old_config.get("prior_checkpoint"),
                "prior_checkpoint_new": new_config.get("prior_checkpoint"),
                "extension_wrapper_sha256_old": old_config.get("extension_wrapper_sha256"),
                "extension_wrapper_sha256_new": new_config.get("extension_wrapper_sha256"),
                "seed_a_fresh_chains_start_from_base": True,
            },
        },
        "recipes": recipes,
        "digit_probe": probe_comparison(),
        "new80_greedy_fit": {
            "path": "qwen/.runtime/related_numeric_sft_20260928/greedy-fit-scores.json",
            "status": greedy["status"],
            "scope": greedy["scope"],
            "sft_a": {
                "trained_all": {k: greedy_sft_a["trained_all"][k] for k in [
                    "n", "median_relative_error", "mean_relative_error", "within_1pct", "within_5pct", "within_10pct"
                ]},
                "new_shape": {k: greedy_sft_a["new_shape"][k] for k in [
                    "n", "median_relative_error", "mean_relative_error", "within_1pct", "within_5pct", "within_10pct"
                ]},
            },
            "old56_direct_fit_equivalent": "not found in the inspected old recipe artifacts",
        },
        "old_saved_training_loss_diagnostic": {
            "path": "docs/research/program-self-training-followup-2026-09-26/training-loss-diagnostic.json",
            "scope": old_diag["scope"],
            "numeric_combined128": old_diag["groups"]["numeric"]["stages"]["combined128"],
            "semantic_digit_groups_present": False,
            "free_generation_fit_present_in_old_recipe_artifacts_inspected": False,
            "note": "stored aggregate teacher-forced loss by recorded presentation/token position; not semantically grouped into significant digits, punctuation, and EOS",
        },
        "causal_limits": [
            "At old128 vs new A128, optimizer/trainer settings and total presentations are matched, but dataset size, source constructions, prompts, targets, target scales, within-example repetition, and resulting order all change together.",
            "Similar cumulative assistant-target token counts do not isolate the effect of breadth versus repeated exposure; they only show that total supervised target-token exposure is nearly matched.",
            "The 512-step correct arm is a distinct dose condition and cannot by itself attribute the 128-step old-versus-new outcome to any single data property.",
            "The saved 80-row digit probe is teacher-forced and does not establish free-generation or general numeric reasoning; no matching old56 semantic digit-group probe was found.",
        ],
    }
    # Exclude bulky internal join maps from the serialized audit.
    for ds in result["datasets"].values():
        ds.pop("messages_by_id", None)
        ds.pop("ids", None)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "recipe-comparison.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    )
    (OUT_DIR / "recipe-comparison.md").write_text(make_report(result))
    print(f"wrote {OUT_DIR / 'recipe-comparison.json'}")
    print(f"wrote {OUT_DIR / 'recipe-comparison.md'}")


if __name__ == "__main__":
    main()
