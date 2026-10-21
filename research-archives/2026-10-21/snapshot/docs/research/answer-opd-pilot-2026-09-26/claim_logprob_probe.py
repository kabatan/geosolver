"""Score audited claim spans under frozen-base hinted and unhinted prompts.

The probe uses the original round-001 completion token IDs, in non-thinking
mode. q0 is the frozen base on the student prompt; qhint is the same frozen
base on the correct numeric-answer-hinted prompt. It does not load an adapter,
generate text, compute gradients, or update weights.

Build and freeze a pre-run manifest on CPU:
  claim_logprob_probe.py build-manifest --out claim-logprob-manifest.json

After the parent task schedules the GPU measurement:
  claim_logprob_probe.py score --manifest claim-logprob-manifest.json \
    --out /path/to/new/probe-output
"""

import argparse
import gc
import hashlib
import importlib.metadata
import json
import math
import time
from pathlib import Path

import torch


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[2]
CONFIG_PATH = HERE / "config.json"
DEFAULT_RUNTIME = PROJECT_ROOT / "qwen/.runtime/answer_opd_pilot_20260926/stage1/round-001/rollout"
DEFAULT_BATCH = DEFAULT_RUNTIME / "batch.json"
DEFAULT_RAW = DEFAULT_RUNTIME / "raw_rollouts.json"
DEFAULT_POOL = HERE / "train-pool.json"
DEFAULT_MANIFEST = HERE / "claim-logprob-manifest.json"


CLAIM_SPECS = [
    {
        "claim_id": "H04_projection_product",
        "rollout_id": "rollout-0001-H04-v1",
        "source_id": "H04",
        "variant": "v1",
        "needle": "MP \\cdot MA = 9",
        "math_label": "verified_valid",
        "scope": "The audited coordinate derivation gives MP*MA=9=MB^2 for this numeric case.",
    },
    {
        "claim_id": "H01_general_projection_factor",
        "rollout_id": "rollout-0003-H01-v2",
        "source_id": "H01",
        "variant": "v2",
        "needle": "k = \\frac{(BC/2)^2}{AM^2}",
        "math_label": "verified_valid",
        "scope": "The audited coordinate derivation identifies the projection factor k for the general BC and AM values.",
    },
    {
        "claim_id": "DA01_mispaired_similarity_ratio",
        "rollout_id": "rollout-0002-DA01-v2",
        "source_id": "DA01",
        "variant": "v2",
        "needle": "$$ \\frac{AB}{TC} = \\frac{BT}{CA} = \\frac{AT}{TA} $$",
        "math_label": "definitely_false",
        "scope": "The angle correspondence is A-to-C, B-to-A, T-to-T; this side ratio mispairs the sides and drives an invalid congruence inference.",
    },
    {
        "claim_id": "H07_wrong_second_intersection_root",
        "rollout_id": "rollout-0005-H07-v3",
        "source_id": "H07",
        "variant": "v3",
        "needle": " x_M + x_D = 10 \\implies x_D = 10 - x_M",
        "math_label": "definitely_false",
        "scope": "For the stated circle intersection at y=2, the quadratic roots sum to 5, not 10.",
    },
    {
        "claim_id": "H15_false_symmedian_sine_ratio",
        "rollout_id": "rollout-0008-H15-v2",
        "source_id": "H15",
        "variant": "v2",
        "needle": "$$ \\frac{\\sin \\alpha_1}{\\sin(60^\\circ - \\alpha_1)} = \\frac{c^2}{b^2}",
        "math_label": "definitely_false",
        "scope": "The symmedian cevian area ratio includes a side factor; the sine ratio should be c/b, not c^2/b^2.",
    },
    {
        "claim_id": "H14_unsupported_right_triangle_premise",
        "rollout_id": "rollout-0007-H14-v2",
        "source_id": "H14",
        "variant": "v2",
        "needle": "So $AH$ must be the hypotenuse?",
        "math_label": "unsupported_but_not_false",
        "scope": "The right-triangle premise is not derived from the construction. It is kept separate from false claims; the span is a tentative assumption, not a verified theorem.",
    },
]


def digest_bytes(data):
    return hashlib.sha256(data).hexdigest()


def digest_file(path):
    return digest_bytes(Path(path).read_bytes())


def canonical_ids_hash(ids):
    return digest_bytes(json.dumps(ids, separators=(",", ":")).encode("utf-8"))


def read_json(path):
    return json.loads(Path(path).read_text())


def decode_ids(tokenizer, ids):
    # Match rollout_worker.py, which saved raw_text using this decode call.
    return tokenizer.decode(ids, skip_special_tokens=False)


def align_claim_span(tokenizer, ids, raw_text, needle, rollout_id):
    occurrences = raw_text.count(needle)
    if occurrences != 1:
        raise ValueError(
            f"{rollout_id}: claim text must occur exactly once; found {occurrences}: {needle!r}"
        )
    char_start = raw_text.find(needle)
    char_end = char_start + len(needle)

    # Decode every original-token prefix once. This provides an auditable
    # character-to-token boundary map without re-tokenizing the claim string.
    wanted_prefixes = {raw_text[:char_start], raw_text[:char_end], raw_text}
    prefix_matches = {text: [] for text in wanted_prefixes}
    prefix_matches.setdefault("", [])
    special_ids = set(tokenizer.all_special_ids)
    special_suffix_candidates = []
    decoded_full = None
    for token_end in range(len(ids) + 1):
        text = decode_ids(tokenizer, ids[:token_end])
        if token_end == len(ids):
            decoded_full = text
        if text in prefix_matches:
            prefix_matches[text].append(token_end)
        if text == raw_text and all(token_id in special_ids for token_id in ids[token_end:]):
            suffix_text = decode_ids(tokenizer, ids[token_end:])
            if decoded_full is None or decoded_full == raw_text + suffix_text:
                special_suffix_candidates.append((token_end, suffix_text))

    suffix = ""
    if decoded_full == raw_text:
        content_token_end = len(ids)
    else:
        candidates = [item for item in special_suffix_candidates if item[1]]
        if len(candidates) != 1 or not decoded_full.startswith(raw_text):
            raise ValueError(
                f"{rollout_id}: full completion decode does not exactly align with raw_text; "
                f"raw chars={len(raw_text)}, decoded chars={len(decoded_full or '')}"
            )
        content_token_end, suffix = candidates[0]
        if decoded_full != raw_text + suffix:
            raise ValueError(f"{rollout_id}: unmatched trailing decode text {suffix!r}")

    start_candidates = [i for i in prefix_matches[raw_text[:char_start]] if i <= content_token_end]
    end_candidates = [i for i in prefix_matches[raw_text[:char_end]] if i <= content_token_end]
    if len(start_candidates) != 1 or len(end_candidates) != 1:
        raise ValueError(
            f"{rollout_id}: ambiguous or absent token boundary for claim chars "
            f"[{char_start},{char_end}); starts={start_candidates}, ends={end_candidates}"
        )
    token_start, token_end = start_candidates[0], end_candidates[0]
    if token_start >= token_end:
        raise ValueError(f"{rollout_id}: empty or reversed original-token span")
    if decode_ids(tokenizer, ids[token_start:token_end]) != needle:
        raise ValueError(
            f"{rollout_id}: original-token slice does not decode exactly to claim text; "
            "refusing a character/token alignment guess"
        )

    return dict(
        text=needle,
        char_range=[char_start, char_end],
        token_range=[token_start, token_end],
        exact_full_decode=(decoded_full == raw_text),
        special_token_suffix=suffix,
    )


def load_inputs(batch_path, raw_path, pool_path):
    config = read_json(CONFIG_PATH)
    meta_path = Path(config["model_metadata"]).resolve()
    meta = read_json(meta_path)
    if meta.get("model_id") != "Qwen/Qwen3.5-9B" or not Path(meta["snapshot"]).is_dir():
        raise ValueError("Expected the configured local Qwen3.5-9B snapshot")

    batch_path = Path(batch_path).resolve()
    raw_path = Path(raw_path).resolve()
    pool_path = Path(pool_path).resolve()
    batch = read_json(batch_path)
    raw_rows = read_json(raw_path)
    pool_rows = read_json(pool_path)
    if batch.get("round") != 1 or batch.get("policy_adapter_sha256") is not None:
        raise ValueError("Claim probe requires the unchanged base-policy round-one batch")
    batch_examples = batch.get("examples")
    if not isinstance(batch_examples, list):
        raise ValueError("Round-one batch has no examples list")
    raw_by_id = {x.get("id"): x for x in raw_rows if isinstance(x, dict)}
    batch_by_id = {x.get("id"): x for x in batch_examples if isinstance(x, dict)}
    pool_by_id = {x.get("id"): x for x in pool_rows if isinstance(x, dict)}

    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(meta["snapshot"], local_files_only=True)
    claims = []
    for spec in CLAIM_SPECS:
        rollout_id = spec["rollout_id"]
        if rollout_id not in raw_by_id or rollout_id not in batch_by_id:
            raise ValueError(f"Missing fixed round-one rollout or batch row: {rollout_id}")
        raw = raw_by_id[rollout_id]
        row = batch_by_id[rollout_id]
        pool_id = f"{spec['source_id']}-{spec['variant']}"
        if pool_id not in pool_by_id:
            raise ValueError(f"Missing numeric training-pool row: {pool_id}")
        pool = pool_by_id[pool_id]
        if raw.get("source_id") != spec["source_id"] or raw.get("variant") != spec["variant"]:
            raise ValueError(f"{rollout_id}: source/config identity mismatch")
        if pool.get("source_id") != spec["source_id"] or pool.get("variant") != spec["variant"]:
            raise ValueError(f"{pool_id}: training-pool identity mismatch")
        if row.get("student_thinking") is not False or row.get("teacher_thinking") is not False:
            raise ValueError(f"{rollout_id}: only non-thinking prompt IDs are allowed")
        for field in ("student_prompt_ids", "teacher_prompt_ids", "completion_ids"):
            values = row.get(field)
            if (not isinstance(values, list) or
                    any(type(token) is not int or token < 0 for token in values)):
                raise ValueError(f"{rollout_id}: invalid {field}")
        if raw.get("completion_ids") != row["completion_ids"]:
            raise ValueError(f"{rollout_id}: batch completion IDs differ from saved raw rollout IDs")
        if raw.get("finish_reason") != row.get("finish_reason"):
            raise ValueError(f"{rollout_id}: finish reason mismatch")

        numeric_hint = pool.get("reference")
        if not isinstance(numeric_hint, str) or not numeric_hint:
            raise ValueError(f"{pool_id}: missing exact numeric answer hint")
        student_text = decode_ids(tokenizer, row["student_prompt_ids"])
        teacher_text = decode_ids(tokenizer, row["teacher_prompt_ids"])
        expected_hint = f"Verified exact numeric-answer hint: {numeric_hint}"
        if expected_hint not in teacher_text or "Verified exact numeric-answer hint:" in student_text:
            raise ValueError(f"{rollout_id}: prompt IDs do not encode the expected q0/qhint pair")

        alignment = align_claim_span(
            tokenizer, row["completion_ids"], raw["raw_text"], spec["needle"], rollout_id
        )
        claims.append({
            "claim_id": spec["claim_id"],
            "rollout_id": rollout_id,
            "source_id": spec["source_id"],
            "variant": spec["variant"],
            "math_label": spec["math_label"],
            "scope": spec["scope"],
            "text": alignment["text"],
            "char_range": alignment["char_range"],
            "token_range": alignment["token_range"],
            "exact_full_decode": alignment["exact_full_decode"],
            "special_token_suffix": alignment["special_token_suffix"],
            "numeric_answer_hint": numeric_hint,
            "finish_reason": row["finish_reason"],
            "completion_token_count": len(row["completion_ids"]),
            "completion_ids_sha256": canonical_ids_hash(row["completion_ids"]),
            "raw_text_sha256": digest_bytes(raw["raw_text"].encode("utf-8")),
            "student_prompt_ids_sha256": canonical_ids_hash(row["student_prompt_ids"]),
            "teacher_prompt_ids_sha256": canonical_ids_hash(row["teacher_prompt_ids"]),
        })

    return dict(
        claims=claims,
        batch_path=batch_path,
        raw_path=raw_path,
        pool_path=pool_path,
        meta_path=meta_path,
        model_metadata=meta,
        config=config,
        hashes={
            "batch_sha256": digest_file(batch_path),
            "raw_rollouts_sha256": digest_file(raw_path),
            "train_pool_sha256": digest_file(pool_path),
            "model_metadata_sha256": digest_file(meta_path),
            "config_sha256": digest_file(CONFIG_PATH),
        },
        tokenizer_version=importlib.metadata.version("transformers"),
    )


def make_manifest(args):
    prepared = load_inputs(args.batch, args.raw_rollouts, args.train_pool)
    manifest = {
        "schema_version": 1,
        "status": "frozen_pre_run_claim_manifest",
        "selection_scope": (
            "Post-hoc selected audited spans from the fixed original round-001 batch; "
            "not a random sample and not the study's main endpoint."
        ),
        "scoring_scope": (
            "Mean log probability of the original observed completion tokens in each claim span, "
            "under the frozen base q0 prompt without the numeric hint and qhint prompt with the "
            "correct exact numeric-answer hint. No proof is generated or repaired."
        ),
        "token_scope": (
            "Half-open token_range indexes into the original completion_ids. Token i is scored "
            "conditioned on its original prompt IDs and completion_ids before i."
        ),
        "tokenizer_alignment": {
            "decode_call": "tokenizer.decode(ids, skip_special_tokens=False), matching rollout_worker.py",
            "method": "Decode original completion ID prefixes; require exact raw-text boundaries and exact span decode. No claim text is re-tokenized.",
            "tokenizer_model_revision": prepared["model_metadata"]["revision"],
            "transformers_version": prepared["tokenizer_version"],
        },
        "mode": "non-thinking; original round-001 student_prompt_ids and teacher_prompt_ids",
        "model": {
            "model_id": prepared["model_metadata"]["model_id"],
            "revision": prepared["model_metadata"]["revision"],
        },
        "source_paths": {
            "batch": str(prepared["batch_path"]),
            "raw_rollouts": str(prepared["raw_path"]),
            "train_pool_numeric_labels": str(prepared["pool_path"]),
            "model_metadata": str(prepared["meta_path"]),
            "study_config": str(CONFIG_PATH.resolve()),
        },
        "source_hashes": prepared["hashes"],
        "claims": prepared["claims"],
    }
    out = Path(args.out).resolve()
    if out.exists():
        raise FileExistsError(f"Refusing to replace frozen claim manifest: {out}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"manifest": str(out), "claims": len(prepared["claims"]),
                      "source_hashes": prepared["hashes"]}, ensure_ascii=False))


def forward_claim_logits(model, prompt_ids, completion_ids, token_range, device):
    start, end = token_range
    claim_ids = completion_ids[start:end]
    if not claim_ids:
        raise ValueError("Claim span has no original completion IDs")
    # For target token offsets [start,end), the preceding causal-logit rows are
    # positions prompt_len+start-1 through prompt_len+end-2. Keeping len+1 rows
    # from the prefix through end gives exactly those rows after dropping the last.
    input_values = prompt_ids + completion_ids[:end]
    input_ids = torch.tensor([input_values], dtype=torch.long, device=device)
    with torch.no_grad():
        output = model(input_ids=input_ids, use_cache=False,
                       logits_to_keep=(end - start) + 1)
        logits = output.logits[0, :-1].detach()
    if logits.ndim != 2 or logits.shape[0] != len(claim_ids):
        raise AssertionError(
            f"Causal target alignment failed: got {tuple(logits.shape)}, "
            f"expected ({len(claim_ids)}, vocab)"
        )
    cpu_logits = logits.to(device="cpu", dtype=torch.bfloat16).contiguous()
    if not torch.isfinite(cpu_logits).all().item():
        raise ValueError("Nonfinite claim logits")
    del input_ids, output, logits
    gc.collect()
    torch.cuda.empty_cache()
    return cpu_logits


def streamed_target_logprobs(logits_cpu, target_ids, device, chunk_tokens=64):
    """Full-vocabulary FP32 normalizers with raw selected-span logits CPU-offloaded."""
    if logits_cpu.ndim != 2 or logits_cpu.shape[0] != len(target_ids):
        raise ValueError("Claim logits and original target-token IDs are misaligned")
    if chunk_tokens < 1:
        raise ValueError("chunk_tokens must be positive")
    values = []
    for start in range(0, len(target_ids), chunk_tokens):
        end = min(start + chunk_tokens, len(target_ids))
        logits = logits_cpu[start:end].to(device=device, dtype=torch.float32)
        targets = torch.tensor(target_ids[start:end], dtype=torch.long, device=device)
        if targets.numel() and (int(targets.min()) < 0 or int(targets.max()) >= logits.shape[-1]):
            raise ValueError("Observed token ID lies outside the model vocabulary")
        log_probs = torch.log_softmax(logits, dim=-1)
        rows = torch.arange(end - start, device=device)
        values.append(log_probs[rows, targets].detach().cpu())
        del logits, targets, log_probs, rows
    result = torch.cat(values) if values else torch.empty(0, dtype=torch.float32)
    if not torch.isfinite(result).all().item():
        raise ValueError("Nonfinite selected-token log probabilities")
    return result


def dense_cpu_self_check():
    generator = torch.Generator(device="cpu").manual_seed(731)
    logits = torch.randn((7, 31), generator=generator, dtype=torch.float32)
    targets = [0, 2, 7, 11, 13, 22, 30]
    chunked = streamed_target_logprobs(logits, targets, torch.device("cpu"), chunk_tokens=3)
    dense = torch.log_softmax(logits, dim=-1).gather(
        1, torch.tensor(targets, dtype=torch.long).unsqueeze(1)
    ).squeeze(1)
    torch.testing.assert_close(chunked, dense, rtol=2e-6, atol=2e-6)
    print("dense CPU selected-token log-probability check passed")


def load_score_inputs(args):
    manifest_path = Path(args.manifest).resolve()
    manifest = read_json(manifest_path)
    if manifest.get("status") != "frozen_pre_run_claim_manifest":
        raise ValueError("Manifest is not marked frozen_pre_run_claim_manifest")
    prepared = load_inputs(args.batch, args.raw_rollouts, args.train_pool)
    if prepared["hashes"] != manifest.get("source_hashes"):
        raise ValueError("One or more frozen manifest source hashes changed")
    if prepared["claims"] != manifest.get("claims"):
        raise ValueError("Claim text or original token alignment differs from frozen manifest")
    prepared["manifest_path"] = manifest_path
    prepared["manifest"] = manifest
    prepared["manifest_sha256"] = digest_file(manifest_path)
    return prepared


def score(args):
    prepared = load_score_inputs(args)
    if not torch.cuda.is_available():
        raise RuntimeError("The scoring command requires CUDA; manifest building and CPU checks do not")
    if not torch.cuda.is_bf16_supported():
        raise RuntimeError("The configured Qwen3.5 probe requires CUDA BF16 support")

    from transformers import AutoModelForCausalLM

    output_dir = Path(args.out).resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    receipt = {
        "status": "running",
        "start_unix": time.time(),
        "driver_sha256": digest_file(__file__),
        "manifest_path": str(prepared["manifest_path"]),
        "manifest_sha256": prepared["manifest_sha256"],
        "source_hashes": prepared["hashes"],
        "model_id": prepared["model_metadata"]["model_id"],
        "model_revision": prepared["model_metadata"]["revision"],
        "claims": [
            {k: claim[k] for k in (
                "claim_id", "rollout_id", "source_id", "variant", "math_label", "text",
                "char_range", "token_range", "numeric_answer_hint", "completion_ids_sha256"
            )}
            for claim in prepared["claims"]
        ],
        "conditions": {
            "q0": "same frozen base, adapter-free, original unhinted student_prompt_ids",
            "qhint": "same frozen base, adapter-free, original prompt_ids with the verified numeric-answer hint",
            "score": "mean log probability of the identical original observed completion token IDs in the claim span",
        },
        "token_alignment": "Frozen half-open token ranges were revalidated by exact decode of the original completion ID prefixes and claim slices.",
        "normalization": "full-vocabulary FP32 log_softmax, raw claim-span logits CPU-offloaded as BF16 and transferred in token chunks",
        "model_copies": 1,
        "thinking": False,
        "device": torch.cuda.get_device_name(0),
        "events": [],
    }
    (output_dir / "receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    started = time.monotonic()
    max_memory = 0
    try:
        device = torch.device("cuda:0")
        model = AutoModelForCausalLM.from_pretrained(
            prepared["model_metadata"]["snapshot"], dtype=torch.bfloat16,
            device_map="cuda", attn_implementation="sdpa", local_files_only=True
        )
        model.eval()
        if any(parameter.requires_grad for parameter in model.parameters()):
            for parameter in model.parameters():
                parameter.requires_grad_(False)

        row_map = {x["id"]: x for x in read_json(prepared["batch_path"])["examples"]}
        for claim in prepared["claims"]:
            row = row_map[claim["rollout_id"]]
            start, end = claim["token_range"]
            if (len(row["student_prompt_ids"]) + end > prepared["config"]["max_sequence_tokens"] or
                    len(row["teacher_prompt_ids"]) + end > prepared["config"]["max_sequence_tokens"]):
                raise ValueError(f"{claim['claim_id']}: prompt plus claim prefix exceeds context limit")
            if torch.cuda.is_available():
                torch.cuda.reset_peak_memory_stats(device)
            q0_logits = forward_claim_logits(
                model, row["student_prompt_ids"], row["completion_ids"], (start, end), device
            )
            qhint_logits = forward_claim_logits(
                model, row["teacher_prompt_ids"], row["completion_ids"], (start, end), device
            )
            target_ids = row["completion_ids"][start:end]
            q0_logp = streamed_target_logprobs(q0_logits, target_ids, device, args.chunk_tokens)
            qhint_logp = streamed_target_logprobs(qhint_logits, target_ids, device, args.chunk_tokens)
            delta = qhint_logp - q0_logp
            event = {
                "claim_id": claim["claim_id"],
                "rollout_id": claim["rollout_id"],
                "math_label": claim["math_label"],
                "text": claim["text"],
                "char_range": claim["char_range"],
                "token_range": claim["token_range"],
                "tokens_scored": len(target_ids),
                "mean_q0_logprob_nats_per_token": float(q0_logp.mean()),
                "mean_qhint_logprob_nats_per_token": float(qhint_logp.mean()),
                "mean_qhint_minus_q0_nats_per_token": float(delta.mean()),
                "sum_q0_logprob_nats": float(q0_logp.sum()),
                "sum_qhint_logprob_nats": float(qhint_logp.sum()),
                "sum_qhint_minus_q0_nats": float(delta.sum()),
                "peak_allocated_gib": torch.cuda.max_memory_allocated(device) / 2**30,
            }
            if not all(math.isfinite(event[k]) for k in (
                "mean_q0_logprob_nats_per_token", "mean_qhint_logprob_nats_per_token",
                "mean_qhint_minus_q0_nats_per_token"
            )):
                raise ValueError(f"{claim['claim_id']}: nonfinite log probability")
            max_memory = max(max_memory, torch.cuda.max_memory_allocated(device))
            receipt["events"].append(event)
            (output_dir / "receipt.json").write_text(
                json.dumps(receipt, ensure_ascii=False, indent=2) + "\n"
            )
            print(json.dumps(event, ensure_ascii=False), flush=True)
            del q0_logits, qhint_logits, q0_logp, qhint_logp, delta
            gc.collect()
            torch.cuda.empty_cache()
        receipt.update(
            status="complete",
            summary={
                "claims": len(receipt["events"]),
                "mean_qhint_minus_q0_nats_per_token": sum(
                    x["mean_qhint_minus_q0_nats_per_token"] for x in receipt["events"]
                ) / len(receipt["events"]),
            },
            peak_allocated_gib=max_memory / 2**30,
            elapsed_seconds=time.monotonic() - started,
            interpretation_note=(
                "Post-hoc selected audited claim spans only. This measures frozen-base "
                "conditioning sensitivity, not proof correctness, teacher quality, or the study endpoint."
            ),
        )
    except BaseException as exc:
        receipt.update(status="failed", error=repr(exc))
        raise
    finally:
        receipt["end_unix"] = time.time()
        receipt["elapsed_seconds"] = time.monotonic() - started
        (output_dir / "receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build-manifest", help="decode and freeze audited spans; CPU/tokenizer only")
    score_parser = sub.add_parser("score", help="score the frozen claim spans; CUDA required")
    for command_parser in (build, score_parser):
        command_parser.add_argument("--batch", type=Path, default=DEFAULT_BATCH)
        command_parser.add_argument("--raw-rollouts", type=Path, default=DEFAULT_RAW)
        command_parser.add_argument("--train-pool", type=Path, default=DEFAULT_POOL)
    build.add_argument("--out", type=Path, default=DEFAULT_MANIFEST)
    score_parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    score_parser.add_argument("--out", type=Path, required=True)
    score_parser.add_argument("--chunk-tokens", type=int, default=64)
    args = parser.parse_args()
    if args.command == "build-manifest":
        make_manifest(args)
    else:
        if not 1 <= args.chunk_tokens <= 1024:
            parser.error("--chunk-tokens must be in [1, 1024]")
        score(args)


if __name__ == "__main__":
    main()
