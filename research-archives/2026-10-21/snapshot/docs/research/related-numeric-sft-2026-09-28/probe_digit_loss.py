"""Teacher-forced digit-position loss probe for the frozen numeric SFT data.

This measures token CE/accuracy while conditioning on the complete gold prefix.
It does not measure self-generated numeric answers or mathematical ability.

CPU-only schema/tokenization validation:
  python probe_digit_loss.py --preflight --out /path/to/new-output-dir

Model scoring is a single-GPU, sequential pass. Run it through the repository's
exclusive GPU guard at docs/research/program-self-training-2026-09-26/gpu_job.py.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import sys
import time
from typing import Any

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("PYTORCH_ALLOC_CONF", "expandable_segments:True")

import torch
import torch.nn.functional as F


ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
TRAINER_PATH = ROOT / "docs/research/program-self-training-2026-09-26/train_sft.py"
PREPARE_DATA_PATH = HERE / "prepare_data.py"
RUNTIME = ROOT / "qwen/.runtime/related_numeric_sft_20260928"
TRAIN_DATA_PATH = RUNTIME / "train.json"
PROVENANCE_PATH = RUNTIME / "data-provenance.json"
DATA_FREEZE_PATH = RUNTIME / "data-freeze.json"
DEFAULT_CONFIG = HERE / "config-sft-a-128.json"
NUMERIC = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )
    temporary.replace(path)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def literal_assignment(path: Path, name: str) -> str:
    """Read a literal constant from prepare_data.py without executing it."""
    tree = ast.parse(path.read_text(), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name
            for target in node.targets
        ):
            value = ast.literal_eval(node.value)
            if not isinstance(value, str):
                raise ValueError(f"{name} must be a string literal")
            return value
    raise ValueError(f"could not find literal {name} in {path}")


def load_trainer():
    spec = importlib.util.spec_from_file_location("frozen_numeric_sft_trainer", TRAINER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load trainer: {TRAINER_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(TRAINER_PATH.parent))
    spec.loader.exec_module(module)
    return module


def make_probe_rows(
    config_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], str, Any, dict[str, Any]]:
    config = load_json(config_path)
    dataset_path = Path(config["dataset"]).resolve()
    metadata_path = Path(config["model_metadata"]).resolve()
    provenance_path = PROVENANCE_PATH.resolve()
    freeze = load_json(DATA_FREEZE_PATH)

    if dataset_path != TRAIN_DATA_PATH.resolve():
        raise ValueError(f"config dataset is not the frozen numeric dataset: {dataset_path}")
    if sha256(dataset_path) != config["dataset_sha256"]:
        raise ValueError("dataset hash differs from config")
    if sha256(metadata_path) != config["model_metadata_sha256"]:
        raise ValueError("model metadata hash differs from config")
    if Path(config["model_metadata"]).resolve() != metadata_path:
        raise ValueError("invalid model metadata path")
    frozen_hashes = freeze.get("sha256", {})
    for path in (dataset_path, provenance_path, config_path.resolve()):
        expected = frozen_hashes.get(str(path))
        if expected is None or expected != sha256(path):
            raise ValueError(f"file is missing from data freeze or hash differs: {path}")

    metadata = load_json(metadata_path)
    if metadata.get("revision") != config["model_revision"]:
        raise ValueError("model revision differs from config")
    if not Path(metadata["snapshot"]).is_dir():
        raise ValueError("pinned model snapshot is unavailable")

    raw = load_json(dataset_path)
    provenance = load_json(provenance_path)
    if not isinstance(raw, list) or len(raw) != 80:
        raise ValueError("expected the frozen 80-row training dataset")
    if not isinstance(provenance, list) or len(provenance) != 120:
        raise ValueError("expected 120 rows in frozen data provenance")
    by_id = {row.get("id"): row for row in provenance}
    if len(by_id) != len(provenance):
        raise ValueError("duplicate provenance IDs")

    prefix = literal_assignment(PREPARE_DATA_PATH, "TRAIN_PREFIX")
    expected_prefix = (
        "Solve the following numerical geometry problem. Give only the requested numerical value, "
        "with at least 10 significant digits when appropriate. Do not give a proof or explanation.\n\n"
    )
    if prefix != expected_prefix:
        raise ValueError("TRAIN_PREFIX changed from the audited prompt")

    sources = Counter(row.get("source_id") for row in raw)
    if len(raw) != len({row.get("id") for row in raw}):
        raise ValueError("duplicate training IDs")
    if len(sources) != 10 or set(sources.values()) != {8}:
        raise ValueError("expected 10 source types with 8 training rows each")

    target_fields = {"id", "source_id", "kind", "messages", "target"}
    for row in raw:
        if set(row) != target_fields or row["kind"] != "numeric":
            raise ValueError(f"unexpected training row schema: {row.get('id')}")
        source = by_id.get(row["id"])
        if source is None or source["split"] != "train":
            raise ValueError(f"training row has no matching train provenance: {row['id']}")
        expected_messages = [{"role": "user", "content": prefix + source["problem_en"]}]
        if row["messages"] != expected_messages or row["source_id"] != source["source_id"]:
            raise ValueError(f"training prompt/source differs from provenance: {row['id']}")
        validate_target(row["id"], row["target"])
        if row["target"] != source["target"]:
            raise ValueError(f"training target differs from provenance: {row['id']}")

    sources_sorted = sorted(sources)
    ninth_rows = []
    for source_id in sources_sorted:
        item_id = f"{source_id}-variant-09"
        item = by_id.get(item_id)
        if item is None or item["split"] != "heldout" or item.get("id") != item_id:
            raise ValueError(f"missing frozen ninth/heldout example for {source_id}")
        validate_target(item_id, item["target"])
        ninth_rows.append(
            {
                "id": item_id,
                "source_id": source_id,
                "kind": "numeric",
                "messages": [{"role": "user", "content": prefix + item["problem_en"]}],
                "target": item["target"],
                "split": "new_shape",
            }
        )

    rows = [dict(row, split="train") for row in raw] + ninth_rows
    if len(rows) != 90 or len({row["id"] for row in rows}) != len(rows):
        raise ValueError("expected 90 unique rows after adding the 10 ninth examples")

    trainer = load_trainer()
    # The frozen trainer allows direct runs only through update 32. The only
    # settings used here are its validated token/sequence limits and recipe.
    fixed = trainer.parameters(dict(config, updates=32, prior_checkpoint=None))
    return config, metadata, rows, prefix, trainer, fixed


def validate_target(case_id: str, target: str) -> None:
    if not isinstance(target, str) or not NUMERIC.fullmatch(target):
        raise ValueError(f"non-numeric target: {case_id}")
    value = float(target)
    if not math.isfinite(value):
        raise ValueError(f"nonfinite target: {case_id}")
    if format(value, ".17g") != target:
        raise ValueError(f"target is not the frozen .17g representation: {case_id}")


def significant_positions(text: str) -> tuple[list[int], list[int]]:
    """Return character offsets for the first six and remaining mantissa digits."""
    mantissa_end = min(
        [pos for marker in "eE" if (pos := text.find(marker)) >= 0] or [len(text)]
    )
    mantissa = text[:mantissa_end]
    digit_positions = [i for i, char in enumerate(mantissa) if char.isdigit()]
    first_nonzero_index = next(
        (i for i, position in enumerate(digit_positions) if mantissa[position] != "0"),
        None,
    )
    if first_nonzero_index is None:
        raise ValueError("distance target has no nonzero significant digit")
    significant = digit_positions[first_nonzero_index:]
    return significant[:6], significant[6:]


def token_units(tokenizer: Any, target: str, target_ids: list[int]) -> list[dict[str, Any]]:
    """Verify numeric-token decode and return exact character spans per token."""
    if not target_ids or target_ids[-1] != tokenizer.eos_token_id:
        raise ValueError("assistant target must end in the template EOS")
    number_ids = target_ids[:-1]
    encoded = tokenizer(target, add_special_tokens=False, return_offsets_mapping=True)
    ids = list(encoded["input_ids"])
    offsets = [tuple(map(int, pair)) for pair in encoded["offset_mapping"]]
    if ids != number_ids:
        raise ValueError("standalone numeric tokenization differs from trainer target IDs")
    decoded = tokenizer.decode(
        number_ids, skip_special_tokens=False, clean_up_tokenization_spaces=False
    )
    if decoded != target:
        raise ValueError("decoded numeric token sequence does not reproduce target text")
    if len(offsets) != len(ids):
        raise ValueError("tokenizer offset count differs from token count")

    displayed = tokenizer.convert_ids_to_tokens(ids)
    if isinstance(displayed, str):
        displayed = [displayed]
    units = []
    cursor = 0
    for index, ((start, end), token_id) in enumerate(zip(offsets, ids)):
        if start != cursor or not start < end <= len(target):
            raise ValueError(f"non-contiguous decode span at target token {index}")
        piece = target[start:end]
        if not piece:
            raise ValueError(f"empty decode unit at target token {index}")
        # Losses are reported as digit-token losses. Stop rather than silently
        # assigning a multi-character BPE piece to an individual digit.
        if any(char.isdigit() for char in piece) and (len(piece) != 1 or not piece.isdigit()):
            raise ValueError(
                f"numeric digit shares a token with other characters in {target!r}: {piece!r}"
            )
        units.append(
            {
                "position": index,
                "token_id": int(token_id),
                "token_text": displayed[index],
                "decoded_unit": piece,
                "char_start": start,
                "char_end": end,
            }
        )
        cursor = end
    if cursor != len(target) or "".join(unit["decoded_unit"] for unit in units) != target:
        raise ValueError("per-token decode units do not reconstruct the target")
    return units


def classify_target_tokens(
    tokenizer: Any, target: str, target_ids: list[int]
) -> tuple[list[dict[str, Any]], dict[str, list[int]], int]:
    units = token_units(tokenizer, target, target_ids)
    leading_positions, remaining_positions = significant_positions(target)
    leading_chars, remaining_chars = set(leading_positions), set(remaining_positions)
    groups: dict[str, list[int]] = {
        "leading_6_digits": [],
        "remaining_digits": [],
        "format_only": [],
    }
    boundary_crossings = 0
    for unit in units:
        covered = set(range(unit["char_start"], unit["char_end"]))
        has_leading = bool(covered & leading_chars)
        has_remaining = bool(covered & remaining_chars)
        if has_leading:
            groups["leading_6_digits"].append(unit["position"])
            if has_remaining:
                boundary_crossings += 1
        elif has_remaining:
            groups["remaining_digits"].append(unit["position"])
        else:
            # Includes sign, decimal point, leading zeros and exponent text.
            groups["format_only"].append(unit["position"])
    if not groups["leading_6_digits"]:
        raise ValueError("tokenization contains no leading significant-digit token")
    eos_index = len(target_ids) - 1
    all_units = units + [
        {
            "position": eos_index,
            "token_id": int(target_ids[-1]),
            "token_text": tokenizer.convert_ids_to_tokens(int(target_ids[-1])),
            "decoded_unit": tokenizer.decode(
                [int(target_ids[-1])],
                skip_special_tokens=False,
                clean_up_tokenization_spaces=False,
            ),
            "char_start": len(target),
            "char_end": len(target),
        }
    ]
    return all_units, {**groups, "eos": [eos_index], "all_target": list(range(len(target_ids)))}, boundary_crossings


def group_stats(indices: list[int], losses: list[float], hits: list[bool]) -> dict[str, Any]:
    if not indices:
        return {"token_count": 0, "mean_ce": None, "top1_accuracy": None}
    return {
        "token_count": len(indices),
        "mean_ce": sum(losses[index] for index in indices) / len(indices),
        "top1_accuracy": sum(bool(hits[index]) for index in indices) / len(indices),
        "ce_sum": sum(losses[index] for index in indices),
        "top1_correct": sum(bool(hits[index]) for index in indices),
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for split in ("train", "new_shape"):
        split_rows = [row for row in rows if row["split"] == split]
        groups: dict[str, Any] = {}
        for name in (
            "leading_6_digits",
            "remaining_digits",
            "format_only",
            "eos",
            "all_target",
        ):
            token_count = sum(row["groups"][name]["token_count"] for row in split_rows)
            ce_sum = sum(row["groups"][name].get("ce_sum", 0.0) for row in split_rows)
            correct = sum(row["groups"][name].get("top1_correct", 0) for row in split_rows)
            macro = [
                row["groups"][name]["mean_ce"]
                for row in split_rows
                if row["groups"][name]["mean_ce"] is not None
            ]
            macro_top1 = [
                row["groups"][name]["top1_accuracy"]
                for row in split_rows
                if row["groups"][name]["top1_accuracy"] is not None
            ]
            groups[name] = {
                "token_count": token_count,
                "token_weighted_mean_ce": ce_sum / token_count if token_count else None,
                "token_weighted_top1_accuracy": correct / token_count if token_count else None,
                "example_macro_mean_ce": sum(macro) / len(macro) if macro else None,
                "example_macro_top1_accuracy": (
                    sum(macro_top1) / len(macro_top1) if macro_top1 else None
                ),
                "examples_with_tokens": len(macro),
            }
        result[split] = {"examples": len(split_rows), "groups": groups}
    return result


def score_rows(
    args: argparse.Namespace,
    metadata: dict[str, Any],
    rows: list[dict[str, Any]],
    tokenizer: Any,
    tokenized: list[dict[str, Any]],
    output_dir: Path,
) -> None:
    if not torch.cuda.is_available():
        raise RuntimeError("model scoring requires CUDA; use --preflight for CPU-only checks")
    from peft import PeftModel
    from transformers import AutoModelForCausalLM

    model = AutoModelForCausalLM.from_pretrained(
        metadata["snapshot"],
        dtype=torch.bfloat16,
        device_map="cuda",
        attn_implementation="sdpa",
        local_files_only=True,
    )
    if args.adapter:
        adapter_path = args.adapter.resolve()
        if not adapter_path.is_dir() or not (adapter_path / "adapter_config.json").is_file():
            raise ValueError("--adapter must be a Transformers PEFT adapter directory")
        model = PeftModel.from_pretrained(model, adapter_path, is_trainable=False)
    model.eval()
    device = torch.device("cuda")
    label_by_id = {row["id"]: row for row in rows}
    completed = []
    with (output_dir / "token-losses.jsonl").open("x") as stream:
        for token_row in tokenized:
            raw = label_by_id[token_row["id"]]
            prompt_ids = token_row["prompt_ids"]
            target_ids = token_row["target_ids"]
            n = len(target_ids)
            input_ids = torch.tensor(
                [prompt_ids + target_ids], dtype=torch.long, device=device
            )
            target = torch.tensor(target_ids, dtype=torch.long, device=device)
            with torch.no_grad():
                output = model(input_ids=input_ids, use_cache=False, logits_to_keep=n + 1)
                logits = output.logits[0, :-1, :]
                if len(logits) != n:
                    raise AssertionError(f"causal alignment mismatch: {token_row['id']}")
                token_losses = F.cross_entropy(
                    logits.float(), target, reduction="none"
                ).detach().cpu().tolist()
                hits = (logits.argmax(dim=-1) == target).detach().cpu().tolist()
            torch.cuda.synchronize()

            units, indices, crossings = classify_target_tokens(
                tokenizer, raw["target"], target_ids
            )
            for unit in units:
                pos = unit["position"]
                unit["nll"] = float(token_losses[pos])
                unit["top1_correct"] = bool(hits[pos])
                if pos == n - 1:
                    unit["class"] = "eos"
                elif pos in indices["leading_6_digits"]:
                    unit["class"] = "leading_6_digits"
                elif pos in indices["remaining_digits"]:
                    unit["class"] = "remaining_digits"
                else:
                    unit["class"] = "format_only"

            groups = {
                name: group_stats(positions, token_losses, hits)
                for name, positions in indices.items()
            }
            result = {
                "id": raw["id"],
                "source_id": raw["source_id"],
                "split": raw["split"],
                "target": raw["target"],
                "prompt_tokens": len(prompt_ids),
                "target_tokens": n,
                "leading_six_significant_digits_available": min(
                    6, len(significant_positions(raw["target"])[0])
                ),
                "leading_tail_boundary_crossing_tokens": crossings,
                "groups": groups,
                "target_token_details": units,
            }
            stream.write(json.dumps(result, ensure_ascii=False, allow_nan=False) + "\n")
            stream.flush()
            completed.append(result)
            del input_ids, target, output, logits

    write_json(output_dir / "summary.json", summarize(completed))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument(
        "--adapter",
        type=Path,
        help="optional Transformers/PEFT adapter directory (omit for the pinned base model)",
    )
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--preflight",
        action="store_true",
        help="validate schema, frozen hashes, exact training prompts and token decode without loading weights",
    )
    args = parser.parse_args()
    config_path = args.config.resolve()
    if not config_path.is_file():
        raise FileNotFoundError(config_path)
    if args.adapter and (
        not args.adapter.is_dir() or not (args.adapter / "adapter_config.json").is_file()
    ):
        raise ValueError("--adapter must be a Transformers PEFT adapter directory")

    config, metadata, rows, _, trainer, fixed = make_probe_rows(config_path)
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(metadata["snapshot"], local_files_only=True)
    if not tokenizer.is_fast:
        raise ValueError("fast tokenizer with offset mappings is required for digit-token grouping")
    tokenized = trainer.tokenize_rows(rows, tokenizer, fixed)
    split_by_id = {row["id"]: row["split"] for row in rows}
    raw_by_id = {row["id"]: row for row in rows}
    tokenization_rows = []
    for token_row in tokenized:
        raw = raw_by_id[token_row["id"]]
        units, groups, crossings = classify_target_tokens(
            tokenizer, raw["target"], token_row["target_ids"]
        )
        tokenization_rows.append(
            {
                "id": token_row["id"],
                "source_id": token_row["source_id"],
                "split": split_by_id[token_row["id"]],
                "target": raw["target"],
                "prompt_tokens": len(token_row["prompt_ids"]),
                "target_tokens": len(token_row["target_ids"]),
                "leading_six_significant_digits_available": min(
                    6, len(significant_positions(raw["target"])[0])
                ),
                "leading_tail_boundary_crossing_tokens": crossings,
                "token_groups": groups,
                "target_token_units": units,
            }
        )

    output_dir = args.out.resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    base_metadata = {
        "status": "preflight_complete" if args.preflight else "running",
        "start_unix": time.time(),
        "config": str(config_path),
        "config_sha256": sha256(config_path),
        "dataset": config["dataset"],
        "dataset_sha256": config["dataset_sha256"],
        "data_provenance_sha256": sha256(PROVENANCE_PATH),
        "model_revision": config["model_revision"],
        "model_metadata_sha256": config["model_metadata_sha256"],
        "trainer_sha256": sha256(TRAINER_PATH),
        "adapter": str(args.adapter.resolve()) if args.adapter else None,
        "rows": len(rows),
        "training_examples": 80,
        "ninth_examples": 10,
        "loss_context": "complete prompt and complete gold assistant target prefix",
        "interpretation": "teacher-forced token statistics; not self-generated numeric accuracy or proof ability",
        "digit_grouping": (
            "one-token-per-digit is required and verified; first six non-leading-zero mantissa digit tokens are leading_6_digits; subsequent mantissa digit tokens are remaining_digits; sign, decimal point, leading zeros, exponent text, and EOS are excluded from those groups"
        ),
        "model_loaded": False if args.preflight else None,
    }
    if args.preflight:
        base_metadata.update(
            status="preflight_complete",
            model_loaded=False,
            device="cpu",
            preflight={
                "prompt_prefix_matches_prepare_data": True,
                "dataset_schema_and_hash": "pass",
                "all_targets_are_finite_roundtrip_17g": True,
                "trainer_tokenization_and_eos": "pass",
                "numeric_token_decode_and_offsets": "pass",
                "one_token_per_digit": "pass",
                "max_prompt_tokens": max(len(row["prompt_ids"]) for row in tokenized),
                "max_target_tokens": max(len(row["target_ids"]) for row in tokenized),
                "train_sequence_limit": fixed["max_sequence_tokens"],
                "train_target_limit": fixed["max_target_tokens"],
            },
        )
        write_json(output_dir / "preflight.json", base_metadata)
        with (output_dir / "tokenization.jsonl").open("x") as stream:
            for row in tokenization_rows:
                stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
        print(json.dumps(base_metadata, ensure_ascii=False))
        return

    base_metadata.update(model_loaded=True, device="cuda", status="running")
    write_json(output_dir / "run.json", base_metadata)
    score_rows(args, metadata, rows, tokenizer, tokenized, output_dir)
    base_metadata.update(status="complete", end_unix=time.time())
    write_json(output_dir / "run.json", base_metadata)
    print(json.dumps({"status": "complete", "out": str(output_dir)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
