"""Audit technical integrity of the fit-512 and prior-format diagnostics.

This script intentionally does not read grading files, private keys, decoded
answer text, or numeric targets. It checks only frozen inputs, receipts,
training state continuity, job identity, decoder settings, and model artifacts.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
OUT = ROOT / "qwen/.runtime/proof_numeric_pilot_20260928"
MODEL_META = ROOT / "docs/research/qwen35-self-materials-2026-09-23/model.json"
GENERATOR = ROOT / "docs/research/transfer-reanalysis-2026-09-26/generate_batch.py"


class Pending(RuntimeError):
    """A required stage has not completed yet; safe to rerun later."""


class AuditFailure(RuntimeError):
    """A completed artifact failed a technical integrity check."""


def need(path: Path, what: str | None = None) -> Path:
    if not path.exists():
        raise Pending(f"missing {what or path}")
    return path


def read_json(path: Path, what: str | None = None) -> Any:
    need(path, what)
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise Pending(f"{what or path} is currently not valid JSON: {exc}") from exc


def sha(path: Path) -> str:
    need(path)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AuditFailure(message)


def complete_status(receipt: dict[str, Any], label: str) -> None:
    status = receipt.get("status")
    if status in ("running", "starting", None):
        raise Pending(f"{label} is not complete (status={status!r})")
    require(status == "complete", f"{label} status is {status!r}, expected 'complete'")


def verify_freeze(name: str) -> str:
    path = need(OUT / name, name)
    frozen = read_json(path, name)
    entries = frozen.get("sha256")
    require(isinstance(entries, dict) and entries, f"{name} has no sha256 manifest")
    for item, expected in entries.items():
        actual = sha(Path(item))
        require(actual == expected, f"freeze hash mismatch: {item}")
    return sha(path)


def check_receipt(
    receipt: dict[str, Any],
    *,
    label: str,
    jobs_path: Path,
    cap: int,
    context: int,
    adapter_sha256: str | None,
    model_revision: str,
    model_metadata_sha256: str,
    driver_sha256: str,
    anchor: dict[str, Any] | None = None,
) -> None:
    complete_status(receipt, label)
    expected = {
        "completed_jobs": len(read_json(jobs_path)),
        "jobs_sha256": sha(jobs_path),
        "model_revision": model_revision,
        "model_metadata_sha256": model_metadata_sha256,
        "driver_sha256": driver_sha256,
        "cap": cap,
        "context": context,
        "batch_size": 4,
        "samples": 1,
        "temperature": 0.7,
        "top_p": 0.95,
        "top_k": 20,
        "presence_penalty": 0.2,
        "enable_thinking": False,
        "adapter_sha256": adapter_sha256,
    }
    for key, value in expected.items():
        require(receipt.get(key) == value, f"{label}: {key} mismatch")
    if anchor is not None:
        for key in (
            "model_revision", "model_metadata_sha256", "driver_sha256",
            "batch_size", "samples", "temperature", "top_p", "top_k",
            "presence_penalty", "enable_thinking",
        ):
            require(receipt.get(key) == anchor.get(key), f"{label}: decoder/model differs from primary ({key})")


def read_jobs(path: Path, expected_count: int, label: str) -> list[dict[str, Any]]:
    jobs = read_json(path, label)
    require(isinstance(jobs, list), f"{label} must be a JSON list")
    require(len(jobs) == expected_count, f"{label} has {len(jobs)} jobs, expected {expected_count}")
    ids = [job.get("id") for job in jobs]
    require(all(isinstance(value, str) for value in ids), f"{label} has a missing job id")
    require(len(set(ids)) == len(ids), f"{label} has duplicate job ids")
    seeds = [job.get("seed") for job in jobs]
    require(len(set(seeds)) == len(seeds), f"{label} has duplicate seeds")
    return jobs


def output_path(folder: Path, job: dict[str, Any]) -> Path:
    return folder / f"{job['id']}-0.json"


def inspect_run_outputs(
    *,
    folder: Path,
    jobs: list[dict[str, Any]],
    cap: int,
    adapter_path: Path | None,
    model_revision: str,
    counterpart_prompts: dict[str, list[int]] | None = None,
) -> tuple[set[str], dict[str, list[int]]]:
    need(folder, str(folder))
    files = list(folder.glob("AP01-*-0.json"))
    require(len(files) == len(jobs), f"{folder}: got {len(files)} output files for {len(jobs)} jobs")
    capped: set[str] = set()
    prompts: dict[str, list[int]] = {}
    expected_adapter = str(adapter_path) if adapter_path else None
    for job in jobs:
        path = need(output_path(folder, job), f"output {job['id']} in {folder.name}")
        result = read_json(path, f"output {job['id']} in {folder.name}")
        for key in ("id", "source_id", "seed", "messages", "split"):
            if key in job:
                require(result.get(key) == job[key], f"{path}: {key} differs from frozen job")
        require(result.get("revision") == model_revision, f"{path}: model revision mismatch")
        require(result.get("sample") == 0, f"{path}: sample index mismatch")
        require(result.get("adapter") == expected_adapter, f"{path}: adapter path mismatch")
        finish = result.get("finish_reason")
        require(finish in ("stop", "length"), f"{path}: invalid finish_reason {finish!r}")
        completion_ids = result.get("completion_ids")
        prompt_ids = result.get("prompt_ids")
        require(isinstance(completion_ids, list), f"{path}: missing completion token list")
        require(isinstance(prompt_ids, list), f"{path}: missing prompt token list")
        require(len(completion_ids) <= cap, f"{path}: completion exceeded cap")
        if finish == "length":
            capped.add(job["id"])
        if counterpart_prompts is not None:
            require(job["id"] in counterpart_prompts, f"{path}: no counterpart prompt")
            require(prompt_ids == counterpart_prompts[job["id"]], f"{path}: tokenized prompt differs across arms")
        prompts[job["id"]] = prompt_ids
    return capped, prompts


def compare_job_identity(a: dict[str, Any], b: dict[str, Any], label: str) -> None:
    for key in ("id", "source_id", "seed", "messages", "split"):
        if key in a or key in b:
            require(a.get(key) == b.get(key), f"{label}: jobs differ at {key}")


def audit_training(model_revision: str, model_metadata_sha256: str, data_sha256: str) -> dict[str, Any]:
    cfg32 = read_json(HERE / "config-32.json", "config-32.json")
    cfg128 = read_json(HERE / "config-128.json", "config-128.json")
    cfg512 = read_json(HERE / "config-512.json", "config-512.json")
    trainer512 = HERE / "train_fit512.py"
    fit_amendment = HERE / "AMENDMENT-FIT-CHECK.md"
    require(cfg32.get("updates") == 32, "config-32 does not specify 32 updates")
    require(cfg128.get("updates") == 128, "config-128 does not specify 128 updates")
    require(cfg512.get("updates") == 512, "config-512 does not specify 512 updates")
    require(cfg128.get("prior_checkpoint") == str(OUT / "train32/final"), "config-128 prior checkpoint mismatch")
    require(cfg512.get("prior_checkpoint") == str(OUT / "train128/final"), "config-512 prior checkpoint mismatch")
    require(cfg512.get("extension_wrapper_sha256") == sha(trainer512), "config-512 wrapper hash mismatch")
    require(cfg512.get("fit_amendment_sha256") == sha(fit_amendment), "config-512 amendment hash mismatch")

    extension_keys = {
        "updates", "prior_checkpoint", "extension_wrapper_sha256", "fit_amendment_sha256",
    }
    for key, value in cfg128.items():
        if key not in extension_keys:
            require(cfg512.get(key) == value, f"config-512 changed inherited config field {key}")
    for key, value in cfg32.items():
        if key not in extension_keys:
            require(cfg128.get(key) == value, f"config-128 changed initial recipe field {key}")
    require(cfg512.get("dataset_sha256") == data_sha256, "config-512 dataset hash mismatch")
    require(cfg512.get("model_revision") == model_revision, "config-512 model revision mismatch")
    require(cfg512.get("model_metadata_sha256") == model_metadata_sha256, "config-512 model metadata hash mismatch")
    require(cfg512.get("seed") == cfg128.get("seed") == cfg32.get("seed"), "training seed changed across continuations")

    receipts: dict[int, dict[str, Any]] = {}
    # (new optimizer updates in this stage, examples processed in this stage,
    # cumulative optimizer step recorded at the saved checkpoint).
    expected_updates = {32: (32, 128, 32), 128: (96, 384, 128), 512: (384, 1536, 512)}
    for update, relative in (
        (32, "train32/final/receipt.json"),
        (128, "train128/final/receipt.json"),
        (512, "train512/final/receipt.json"),
    ):
        receipt = read_json(OUT / relative, f"train-{update} final receipt")
        complete_status(receipt, f"train-{update} final receipt")
        receipts[update] = receipt
        stage_updates, stage_examples, cumulative_step = expected_updates[update]
        require(receipt.get("global_updates") == update, f"train-{update}: global update mismatch")
        require(receipt.get("planned_updates") == update, f"train-{update}: planned update mismatch")
        require(receipt.get("optimizer_step_min") == cumulative_step, f"train-{update}: optimizer step minimum mismatch")
        require(receipt.get("optimizer_step_max") == cumulative_step, f"train-{update}: optimizer step maximum mismatch")
        require(receipt.get("updates") == stage_updates, f"train-{update}: continuation update count mismatch")
        require(receipt.get("examples_processed") == stage_examples, f"train-{update}: examples processed mismatch")
        require(receipt.get("n_examples") == 256, f"train-{update}: dataset row count mismatch")
        require(receipt.get("dataset_sha256") == data_sha256, f"train-{update}: dataset hash mismatch")
        require(receipt.get("model_revision") == model_revision, f"train-{update}: model revision mismatch")
        require(receipt.get("model_metadata_sha256") == model_metadata_sha256, f"train-{update}: model metadata hash mismatch")
        config_path = HERE / f"config-{update}.json"
        require(receipt.get("config_sha256") == sha(config_path), f"train-{update}: config hash mismatch")
        order_path = OUT / f"train{update}/example-order.json"
        require(receipt.get("example_order_sha256") == sha(order_path), f"train-{update}: example order hash mismatch")
        require(receipt.get("optimizer_sha256") == sha(OUT / f"train{update}/final/optimizer.pt"), f"train-{update}: optimizer artifact hash mismatch")
        require(receipt.get("adapter_sha256") == sha(OUT / f"train{update}/final/adapter/adapter_model.safetensors"), f"train-{update}: adapter artifact hash mismatch")
        require(receipt.get("vllm_adapter_sha256") == sha(OUT / f"train{update}/final/adapter-vllm/adapter_model.safetensors"), f"train-{update}: inference adapter hash mismatch")
        if update > 32:
            prior_update = 32 if update == 128 else 128
            prior = receipts[prior_update]
            expected_checkpoint = OUT / f"train{prior_update}/final"
            require(receipt.get("prior_checkpoint") == str(expected_checkpoint), f"train-{update}: prior checkpoint path mismatch")
            require(receipt.get("optimizer_state_loaded") is True, f"train-{update}: optimizer state not loaded")
            require(receipt.get("prior_optimizer_sha256") == prior.get("optimizer_sha256"), f"train-{update}: optimizer state continuity mismatch")
            require(receipt.get("prior_adapter_sha256") == prior.get("adapter_sha256"), f"train-{update}: adapter continuation mismatch")
            require(receipt.get("prior_vllm_adapter_sha256") == prior.get("vllm_adapter_sha256"), f"train-{update}: inference adapter continuation mismatch")

    data_path = OUT / "data/train.json"
    data_rows = read_json(data_path, "training dataset")
    ids = [row.get("id") for row in data_rows]
    require(len(ids) == 256 and len(set(ids)) == 256, "training dataset IDs are not 256 unique rows")
    order_path = OUT / "train512/example-order.json"
    order = read_json(order_path, "512-update example order")
    require(len(order) == 8 * len(ids), "512-update order is not eight full dataset passes")
    require({row.get("epoch") for row in order} == set(range(8)), "512-update order does not contain epochs 0 through 7")
    counts: dict[str, int] = {}
    for row in order:
        row_id = row.get("id")
        require(row_id in set(ids), "512-update order contains an ID outside the training dataset")
        counts[row_id] = counts.get(row_id, 0) + 1
    require(counts == {row_id: 8 for row_id in ids}, "512-update order does not present each row eight times")
    total_presentations = sum(receipts[u]["examples_processed"] for u in (32, 128, 512))
    require(total_presentations == 8 * len(ids), "actual processed examples do not total eight dataset passes")
    require(receipts[512]["global_updates"] == 512, "final cumulative global update count is not 512")
    # 32, 128, and 512 receipt global_updates are cumulative checkpoints, while
    # the scheduled optimizer updates across the three stages are 32 + 96 + 384.
    require(32 + receipts[128]["updates"] + receipts[512]["updates"] == 512, "cumulative trained optimizer steps are not 512")
    order32 = read_json(OUT / "train32/example-order.json", "32-update example order")
    order128 = read_json(OUT / "train128/example-order.json", "128-update example order")
    require(order128[:len(order32)] == order32, "128-update schedule does not preserve the first 32 updates")
    require(order[:len(order128)] == order128, "512-update schedule does not preserve the first 128 updates")

    return {
        "dataset_sha256": data_sha256,
        "unique_training_rows": len(ids),
        "scheduled_epochs": 8,
        "actual_example_presentations": total_presentations,
        "final_global_updates": receipts[512]["global_updates"],
        "continuation_updates_128_to_512": receipts[512]["updates"],
        "optimizer_continuity": True,
        "adapter_sha256_512": receipts[512]["vllm_adapter_sha256"],
        "model_revision": model_revision,
    }


def audit_fit512_probe(
    *,
    model_revision: str,
    model_metadata_sha256: str,
    driver_sha256: str,
    primary_numeric_receipt: dict[str, Any],
    train128_adapter: Path,
    train512_adapter: Path,
) -> dict[str, Any]:
    completion = read_json(OUT / "fit512-completion.json", "fit512 completion")
    require(completion.get("status") == "generated", "fit512 completion status mismatch")
    require(completion.get("probe_count") == 4, "fit512 completion does not report four probes")
    source_jobs = read_jobs(OUT / "data/numeric-jobs.json", 12, "primary numeric jobs")
    expected_jobs = [job for job in source_jobs if job.get("split") == "train_probe"]
    require(len(expected_jobs) == 4, "primary numeric jobs do not have exactly four train_probe rows")
    jobs_path = OUT / "fit512-probe-jobs.json"
    jobs = read_jobs(jobs_path, 4, "fit512 probe jobs")
    for actual, expected in zip(jobs, expected_jobs):
        compare_job_identity(actual, expected, "fit512 probe selection")
    prior_jobs = {job["id"]: job for job in read_json(OUT / "data/numeric-jobs.json")}
    sft128_folder = OUT / "sft-numeric"
    prior_prompt_ids: dict[str, list[int]] = {}
    for job in jobs:
        reference = read_json(output_path(sft128_folder, prior_jobs[job["id"]]), f"SFT128 probe reference {job['id']}")
        require(reference.get("seed") == job.get("seed"), f"SFT128 probe seed mismatch for {job['id']}")
        require(reference.get("messages") == job.get("messages"), f"SFT128 probe prompt mismatch for {job['id']}")
        require(isinstance(reference.get("prompt_ids"), list), f"SFT128 probe lacks tokenized prompt for {job['id']}")
        prior_prompt_ids[job["id"]] = reference["prompt_ids"]

    adapter_sha = sha(train512_adapter / "adapter_model.safetensors")
    base_receipt = read_json(OUT / "sft-numeric/receipt.json", "primary SFT128 numeric receipt")
    require(base_receipt.get("adapter_sha256") == sha(train128_adapter / "adapter_model.safetensors"), "primary SFT128 receipt adapter hash mismatch")
    folder = OUT / "fit512-probe"
    receipt = read_json(folder / "receipt.json", "fit512 probe receipt")
    check_receipt(
        receipt, label="fit512 probe", jobs_path=jobs_path, cap=32768, context=40960,
        adapter_sha256=adapter_sha, model_revision=model_revision,
        model_metadata_sha256=model_metadata_sha256, driver_sha256=driver_sha256,
        anchor=primary_numeric_receipt,
    )
    capped, _ = inspect_run_outputs(
        folder=folder, jobs=jobs, cap=32768, adapter_path=train512_adapter,
        model_revision=model_revision, counterpart_prompts=prior_prompt_ids,
    )
    listed_extended = completion.get("extended_jobs")
    require(isinstance(listed_extended, list), "fit512 completion extended_jobs is not a list")
    require(set(listed_extended) == capped and len(listed_extended) == len(capped), "fit512 extension set differs from capped probes")

    if capped:
        extension_path = OUT / "fit512-probe-extension-jobs.json"
        extension_jobs = read_jobs(extension_path, len(capped), "fit512 probe extension jobs")
        require({job["id"] for job in extension_jobs} == capped, "fit512 extension jobs differ from capped probe IDs")
        for ext in extension_jobs:
            compare_job_identity(ext, next(job for job in jobs if job["id"] == ext["id"]), "fit512 extended probe")
        extended_receipt = read_json(OUT / "fit512-probe-81k/receipt.json", "fit512 extended probe receipt")
        check_receipt(
            extended_receipt, label="fit512 extended probe", jobs_path=extension_path,
            cap=81920, context=98304, adapter_sha256=adapter_sha,
            model_revision=model_revision, model_metadata_sha256=model_metadata_sha256,
            driver_sha256=driver_sha256, anchor=primary_numeric_receipt,
        )
        extended_capped, _ = inspect_run_outputs(
            folder=OUT / "fit512-probe-81k", jobs=extension_jobs, cap=81920,
            adapter_path=train512_adapter, model_revision=model_revision,
            counterpart_prompts=prior_prompt_ids,
        )
        return {"jobs": 4, "adapter_sha256": adapter_sha, "capped_at_32k": sorted(capped),
                "still_capped_at_81k": sorted(extended_capped)}
    require(not (OUT / "fit512-probe-extension-jobs.json").exists(), "fit512 extension file exists despite no capped probe")
    require(not (OUT / "fit512-probe-81k").exists(), "fit512 extended probe output exists despite no capped probe")
    return {"jobs": 4, "adapter_sha256": adapter_sha, "capped_at_32k": [], "still_capped_at_81k": []}


def audit_prior_format(
    *,
    model_revision: str,
    model_metadata_sha256: str,
    driver_sha256: str,
    primary_numeric_receipt: dict[str, Any],
    adapters: dict[str, Path | None],
) -> dict[str, Any]:
    completion = read_json(OUT / "prior-format-completion.json", "prior-format completion")
    require(completion.get("status") == "generated_and_blinded", "prior-format completion status mismatch")
    require(completion.get("outputs") == 12, "prior-format completion does not report 12 outputs")
    original = read_jobs(OUT / "data/numeric-jobs.json", 12, "primary numeric jobs")[:4]
    require([job["id"] for job in original] == [f"AP01-num-{idx:02d}" for idx in range(4)], "prior-format base jobs are not the frozen first four")
    jobs_path = OUT / "prior-format-jobs.json"
    jobs = read_jobs(jobs_path, 4, "prior-format jobs")
    before = "Solve the following geometry problem. Give the exact numerical answer and explain your reasoning in English. You have no access to tools."
    after = "End with a single line of the form Answer: <exact numerical expression>."
    suffix = " Give the requested length as a decimal rounded to six digits after the decimal point."
    for idx, (job, source) in enumerate(zip(jobs, original)):
        require(job.get("id") == f"AP01-style-{idx:02d}", f"prior-format job {idx} id mismatch")
        require(job.get("original_job_id") == source.get("id"), f"prior-format job {idx} source id mismatch")
        require(job.get("split") == "prior_format_heldout", f"prior-format job {idx} split mismatch")
        for key in ("source_id", "variant", "replicate", "seed", "evaluation_role", "transfer_group"):
            if key in source:
                require(job.get(key) == source.get(key), f"prior-format job {idx} changed source field {key}")
        source_body = source["messages"][0]["content"]
        require(source_body.endswith(suffix), f"prior-format source job {idx} prompt suffix mismatch")
        expected_content = before + "\n\n" + source_body[:-len(suffix)] + "\n\n" + after
        require(job.get("messages") == [{"role": "user", "content": expected_content}], f"prior-format job {idx} prompt transform mismatch")

    arm_order = ("base", "sft128", "sft512")
    primary_prompts: dict[str, list[int]] = {}
    for arm in arm_order:
        folder = OUT / f"prior-format-{arm}"
        receipt = read_json(folder / "receipt.json", f"prior-format {arm} receipt")
        expected_adapter = sha(adapters[arm] / "adapter_model.safetensors") if adapters[arm] else None
        check_receipt(
            receipt, label=f"prior-format {arm}", jobs_path=jobs_path, cap=32768,
            context=40960, adapter_sha256=expected_adapter,
            model_revision=model_revision, model_metadata_sha256=model_metadata_sha256,
            driver_sha256=driver_sha256, anchor=primary_numeric_receipt,
        )
        _, prompts = inspect_run_outputs(
            folder=folder, jobs=jobs, cap=32768, adapter_path=adapters[arm],
            model_revision=model_revision,
            counterpart_prompts=primary_prompts if primary_prompts else None,
        )
        if not primary_prompts:
            primary_prompts = prompts

    initial_capped: set[str] = set()
    for arm in arm_order:
        capped, _ = inspect_run_outputs(
            folder=OUT / f"prior-format-{arm}", jobs=jobs, cap=32768,
            adapter_path=adapters[arm], model_revision=model_revision,
        )
        initial_capped.update(capped)

    extension_path = OUT / "prior-format-extension-jobs.json"
    still_capped: set[str] = set()
    if initial_capped:
        extension_jobs = read_jobs(extension_path, len(initial_capped), "prior-format common extension jobs")
        require({job["id"] for job in extension_jobs} == initial_capped, "prior-format extension is not the common capped-job union")
        jobs_by_id = {job["id"]: job for job in jobs}
        for ext in extension_jobs:
            compare_job_identity(ext, jobs_by_id[ext["id"]], "prior-format common extension")
        extended_prompts: dict[str, list[int]] = {}
        for arm in arm_order:
            folder = OUT / f"prior-format-{arm}-81k"
            receipt = read_json(folder / "receipt.json", f"prior-format {arm} 81k receipt")
            expected_adapter = sha(adapters[arm] / "adapter_model.safetensors") if adapters[arm] else None
            check_receipt(
                receipt, label=f"prior-format {arm} 81k", jobs_path=extension_path,
                cap=81920, context=98304, adapter_sha256=expected_adapter,
                model_revision=model_revision, model_metadata_sha256=model_metadata_sha256,
                driver_sha256=driver_sha256, anchor=primary_numeric_receipt,
            )
            capped, prompts = inspect_run_outputs(
                folder=folder, jobs=extension_jobs, cap=81920,
                adapter_path=adapters[arm], model_revision=model_revision,
                counterpart_prompts={job["id"]: primary_prompts[job["id"]] for job in extension_jobs},
            )
            still_capped.update(capped)
            if extended_prompts:
                for job_id, prompt_ids in prompts.items():
                    require(extended_prompts[job_id] == prompt_ids, f"prior-format 81k prompt differs across arms for {job_id}")
            else:
                extended_prompts = prompts
            short_prompts = inspect_prompts_only(OUT / f"prior-format-{arm}", extension_jobs)
            require(short_prompts == prompts, f"prior-format prompt changed when rerunning {arm} at 81k")
    else:
        require(not extension_path.exists(), "prior-format extension file exists despite no capped job")
        for arm in arm_order:
            require(not (OUT / f"prior-format-{arm}-81k").exists(), f"prior-format {arm} 81k output exists despite no capped job")

    return {
        "arms": list(arm_order),
        "jobs_per_arm": len(jobs),
        "shared_seed_prompt_checks": True,
        "common_capped_union_reruns": sorted(initial_capped),
        "still_capped_after_81k": sorted(still_capped),
        "adapter_sha256": {
            "base": None,
            "sft128": sha(adapters["sft128"] / "adapter_model.safetensors"),
            "sft512": sha(adapters["sft512"] / "adapter_model.safetensors"),
        },
    }


def inspect_prompts_only(folder: Path, jobs: list[dict[str, Any]]) -> dict[str, list[int]]:
    result: dict[str, list[int]] = {}
    for job in jobs:
        record = read_json(output_path(folder, job), f"prompt identity {job['id']}")
        prompt_ids = record.get("prompt_ids")
        require(isinstance(prompt_ids, list), f"{folder.name}/{job['id']}: prompt IDs missing")
        result[job["id"]] = prompt_ids
    return result


def audit() -> dict[str, Any]:
    # The primary fixed run and the two prerequisite freezes must remain intact.
    freeze_hashes = {
        "primary": verify_freeze("freeze.json"),
        "execution": verify_freeze("execution-freeze.json"),
        "fit512": verify_freeze("fit512-freeze.json"),
        "prior_format": verify_freeze("prior-format-freeze.json"),
    }
    if (OUT / "coordinate-completion.json").exists():
        freeze_hashes["coordinate"] = verify_freeze("coordinate-freeze.json")

    primary_completion = read_json(OUT / "completion.json", "primary completion")
    require(primary_completion.get("status") == "generated_and_blinded", "primary run is not complete")
    coordinate_completion = read_json(OUT / "coordinate-completion.json", "coordinate diagnostic completion")
    require(coordinate_completion.get("status") == "generated_and_blinded", "coordinate diagnostic is not complete")
    coordinate_jobs = read_jobs(OUT / "coordinate-jobs.json", 2, "coordinate prerequisite jobs")
    require(len(coordinate_jobs) == 2, "coordinate prerequisite job count mismatch")

    metadata = read_json(MODEL_META, "model metadata")
    model_revision = metadata.get("revision")
    require(isinstance(model_revision, str) and model_revision, "model metadata revision missing")
    model_metadata_sha256 = sha(MODEL_META)
    driver_sha256 = sha(GENERATOR)
    data_sha256 = sha(OUT / "data/train.json")

    training = audit_training(model_revision, model_metadata_sha256, data_sha256)
    primary_numeric_receipt = read_json(OUT / "sft-numeric/receipt.json", "primary numeric SFT receipt")
    primary_base_receipt = read_json(OUT / "base-numeric/receipt.json", "primary numeric base receipt")
    complete_status(primary_numeric_receipt, "primary numeric SFT receipt")
    complete_status(primary_base_receipt, "primary numeric base receipt")
    require(primary_numeric_receipt.get("adapter_sha256") == sha(OUT / "train128/final/adapter-vllm/adapter_model.safetensors"), "primary SFT128 generation adapter hash mismatch")
    require(primary_base_receipt.get("adapter_sha256") is None, "primary base generation unexpectedly used an adapter")
    fit_probe = audit_fit512_probe(
        model_revision=model_revision,
        model_metadata_sha256=model_metadata_sha256,
        driver_sha256=driver_sha256,
        primary_numeric_receipt=primary_numeric_receipt,
        train128_adapter=OUT / "train128/final/adapter-vllm",
        train512_adapter=OUT / "train512/final/adapter-vllm",
    )
    prior_format = audit_prior_format(
        model_revision=model_revision,
        model_metadata_sha256=model_metadata_sha256,
        driver_sha256=driver_sha256,
        primary_numeric_receipt=primary_numeric_receipt,
        adapters={
            "base": None,
            "sft128": OUT / "train128/final/adapter-vllm",
            "sft512": OUT / "train512/final/adapter-vllm",
        },
    )
    return {
        "status": "pass",
        "freeze_sha256": freeze_hashes,
        "fit512_training": training,
        "fit512_probe": fit_probe,
        "prior_format": prior_format,
        "answer_or_grade_content_read": False,
    }


def main() -> int:
    try:
        result = audit()
    except Pending as exc:
        print(f"PENDING: {exc}", file=sys.stderr)
        return 2
    except AuditFailure as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    output = OUT / "diagnostic-integrity.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
    temporary.replace(output)
    encoded = json.dumps(result, sort_keys=True, separators=(",", ":"))
    print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
