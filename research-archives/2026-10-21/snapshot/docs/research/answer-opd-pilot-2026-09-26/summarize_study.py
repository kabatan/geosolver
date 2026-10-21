"""Collect receipts and explicit grades without inferring ungraded failures."""
import argparse
import collections
import json
import statistics
from pathlib import Path


HERE = Path(__file__).resolve().parent
PRIMARY = "same_configuration_general_proof"


def read(path):
    return json.loads(path.read_text())


def evaluation(directory):
    if not (directory / "receipt.json").exists():
        return None
    receipt = read(directory / "receipt.json")
    rows = [x for p in sorted(directory.glob("*.json"))
            if isinstance(x := read(p), dict) and "final_text" in x]
    by_role = {}
    for role in sorted({x['evaluation_role'] for x in rows}):
        selected = [x for x in rows if x['evaluation_role'] == role]
        lengths = [len(x['completion_ids']) for x in selected]
        by_role[role] = dict(outputs=len(selected), completion_tokens=sum(lengths),
                            mean_completion_tokens=statistics.mean(lengths),
                            median_completion_tokens=statistics.median(lengths),
                            finish_reasons=dict(collections.Counter(x['finish_reason'] for x in selected)))
    return dict(receipt=receipt, outputs=len(rows), by_role=by_role,
                completion_tokens=sum(len(x["completion_ids"]) for x in rows),
                finish_reasons=dict(collections.Counter(x["finish_reason"] for x in rows)))


def proof_counts(rows):
    return dict(graded=len(rows), correct=sum(x["complete_proof"] for x in rows),
                conservative=sum(x["complete_proof"] and not x["ancillary_math_error"]
                                 for x in rows))


def training_summary(runtime):
    """Summarize only completed training attempts and their paired rollout receipts."""
    runtime = Path(runtime).resolve()
    training = {}
    completed_by_logical_round = {}
    seen_rollout_ids = {}

    for stage_receipt_path in sorted(runtime.glob("stage*/receipt.json")):
        directory = stage_receipt_path.parent
        stage = directory.name
        # stage2-resume is a physical continuation of stage2. Keeping it separate in
        # the report preserves its receipt/config provenance; this key prevents a
        # duplicated logical round from being counted across the two directories.
        logical_stage = "stage2" if stage == "stage2-resume" else stage
        completed_records = []
        round_records = []
        finish_by_config = collections.defaultdict(collections.Counter)
        finish_without_ids = collections.Counter()
        unique_by_config = collections.Counter()
        unique_rollouts_with_ids = 0
        rollout_records_seen = 0
        rollout_records_without_ids = 0
        rollout_id_unavailable_rounds = 0
        finish_reason_unavailable_rounds = 0
        rollout_worker_seconds = 0.0

        round_dirs = []
        for round_dir in directory.glob("round-*"):
            suffix = round_dir.name.removeprefix("round-")
            if round_dir.is_dir() and suffix.isdigit():
                round_dirs.append((int(suffix), round_dir))

        for round_number, round_dir in sorted(round_dirs):
            attempt_paths = sorted(round_dir.glob("train*/receipt.json"))
            if not attempt_paths:
                continue

            attempts = []
            complete_attempts = []
            for receipt_path in attempt_paths:
                receipt = read(receipt_path)
                attempt = dict(
                    directory=receipt_path.parent.name,
                    receipt_path=str(receipt_path.relative_to(runtime)),
                    receipt=receipt,
                )
                attempts.append(attempt)
                if receipt.get("status") == "complete":
                    assert receipt.get("round", round_number) == round_number, (
                        f"Training receipt round mismatch in {receipt_path}: "
                        f"expected {round_number}, got {receipt.get('round')}"
                    )
                    complete_attempts.append(attempt)

            assert len(complete_attempts) <= 1, (
                f"Multiple completed train directories for logical stage {logical_stage} "
                f"round {round_number}: "
                + ", ".join(x["receipt_path"] for x in complete_attempts)
            )

            counted = complete_attempts[0] if complete_attempts else None
            round_record = dict(
                round=round_number,
                logical_stage=logical_stage,
                training_attempts=attempts,
                counted_training_receipt_path=(counted["receipt_path"] if counted else None),
                counted_training_receipt=(counted["receipt"] if counted else None),
                rollout_receipt_path=None,
                rollout_receipt_status=None,
                rollout_ids_available=None,
                rollout_finish_reasons_available=None,
                rollout_records_seen=None,
                rollout_records_without_ids=0,
                unique_rollout_records=None,
            )

            if counted:
                logical_key = (logical_stage, round_number)
                previous_path = completed_by_logical_round.get(logical_key)
                assert previous_path is None, (
                    f"Multiple completed train directories for logical stage "
                    f"{logical_stage} round {round_number}: {previous_path}, "
                    f"{counted['receipt_path']}"
                )
                completed_by_logical_round[logical_key] = counted["receipt_path"]
                completed_records.append((round_number, counted))

                rollout_path = round_dir / "rollout" / "receipt.json"
                round_record["rollout_receipt_path"] = (
                    str(rollout_path.relative_to(runtime)) if rollout_path.exists() else None
                )
                if rollout_path.exists():
                    rollout = read(rollout_path)
                    round_record["rollout_receipt_status"] = rollout.get("status")
                    if rollout.get("status") == "complete":
                        raw_ids = rollout.get("ids")
                        raw_reasons = rollout.get("finish_reasons")
                        reasons = raw_reasons if isinstance(raw_reasons, list) else None
                        round_record["rollout_finish_reasons_available"] = reasons is not None
                        if reasons is None:
                            finish_reason_unavailable_rounds += 1

                        if raw_ids is None:
                            # Legacy receipts may omit IDs. Keep their finish-reason
                            # record counts, but never present them as unique IDs.
                            round_record["rollout_ids_available"] = False
                            unidentified_count = len(reasons) if reasons is not None else None
                            round_record["rollout_records_seen"] = unidentified_count
                            round_record["rollout_records_without_ids"] = unidentified_count or 0
                            rollout_id_unavailable_rounds += 1
                            if reasons is not None:
                                assert all(isinstance(x, str) for x in reasons), (
                                    f"Invalid finish reasons in {rollout_path}"
                                )
                                finish_without_ids.update(reasons)
                                rollout_records_without_ids += len(reasons)
                                rollout_records_seen += len(reasons)
                        else:
                            assert isinstance(raw_ids, list), (
                                f"Rollout ids must be a list in {rollout_path}"
                            )
                            ids = raw_ids
                            if reasons is not None:
                                assert len(ids) == len(reasons), (
                                    f"Rollout id/finish-reason length mismatch in {rollout_path}"
                                )
                            round_record["rollout_ids_available"] = True
                            round_record["rollout_records_seen"] = len(ids)
                            round_record["unique_rollout_records"] = len(ids)
                            rollout_records_seen += len(ids)
                            unique_rollouts_with_ids += len(ids)
                            for i, identity in enumerate(ids):
                                assert isinstance(identity, str), (
                                    f"Non-string rollout id in {rollout_path}: {identity!r}"
                                )
                                previous = seen_rollout_ids.get(identity)
                                location = str(rollout_path.relative_to(runtime))
                                assert previous is None, (
                                    f"Duplicate global rollout ID {identity!r}: "
                                    f"{previous} and {location}"
                                )
                                seen_rollout_ids[identity] = location
                                parts = identity.split("-")
                                config = parts[2] if len(parts) > 2 and parts[0] == "rollout" else "unknown"
                                unique_by_config[config] += 1
                                if reasons is not None:
                                    finish_by_config[config][reasons[i]] += 1

                        rollout_worker_seconds += rollout.get("elapsed_seconds", 0.0)
                    else:
                        rollout_id_unavailable_rounds += 1
                        finish_reason_unavailable_rounds += 1
                else:
                    rollout_id_unavailable_rounds += 1
                    finish_reason_unavailable_rounds += 1

            round_records.append(round_record)

        completed_receipts = [attempt["receipt"] for _, attempt in completed_records]
        final_round, final_attempt = completed_records[-1] if completed_records else (None, None)
        final_receipt = final_attempt["receipt"] if final_attempt else {}
        training[stage] = dict(
            logical_stage=logical_stage,
            receipt_path=str(stage_receipt_path.relative_to(runtime)),
            receipt=read(stage_receipt_path),
            completed_rounds=len(completed_receipts),
            optimizer_updates=sum(x.get("updates", 0) for x in completed_receipts),
            examples=sum(x.get("examples_processed", 0) for x in completed_receipts),
            completion_tokens=sum(x.get("trained_completion_tokens", 0) for x in completed_receipts),
            capped_prefixes=sum(x.get("truncated_prefixes", 0) for x in completed_receipts),
            rollout_records_seen=rollout_records_seen,
            rollout_records_without_ids=rollout_records_without_ids,
            unique_rollouts=(unique_rollouts_with_ids if rollout_id_unavailable_rounds == 0 else None),
            unique_rollouts_with_ids=unique_rollouts_with_ids,
            unique_rollouts_status=(
                "complete" if completed_records and rollout_id_unavailable_rounds == 0
                else "partial" if unique_rollouts_with_ids
                else "unavailable"
            ),
            unique_rollouts_by_configuration=(
                dict(sorted(unique_by_config.items())) if rollout_id_unavailable_rounds == 0 else None
            ),
            unique_rollouts_by_configuration_with_ids=dict(sorted(unique_by_config.items())),
            rollout_finish_reasons_by_configuration={
                config: dict(sorted(counter.items()))
                for config, counter in sorted(finish_by_config.items())
            },
            rollout_finish_reasons_by_configuration_status=(
                "complete" if completed_records and finish_reason_unavailable_rounds == 0
                and rollout_id_unavailable_rounds == 0
                else "partial" if finish_by_config or finish_without_ids
                else "unavailable"
            ),
            rollout_finish_reasons_without_ids=dict(sorted(finish_without_ids.items())),
            peak_allocated_gib=max(
                (x["peak_allocated_gib"] for x in completed_receipts
                 if x.get("peak_allocated_gib") is not None), default=None
            ),
            train_worker_seconds=sum(x.get("elapsed_seconds", 0.0) for x in completed_receipts),
            rollout_worker_seconds=rollout_worker_seconds,
            final_completed_round=final_round,
            final_adapter_sha256=final_receipt.get("adapter_sha256"),
            final_vllm_adapter_sha256=final_receipt.get("vllm_adapter_sha256"),
            final_optimizer_sha256=final_receipt.get("optimizer_sha256"),
            final_hash_receipt_path=(final_attempt["receipt_path"] if final_attempt else None),
            rounds=round_records,
        )
    return training


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runtime", type=Path, required=True)
    ap.add_argument("--proof-grades", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    proof = read(a.proof_grades) if a.proof_grades else []
    identities = [(x["condition"], x["job_id"]) for x in proof]
    assert len(identities) == len(set(identities)), "Duplicate proof grades"
    for x in proof:
        assert type(x["complete_proof"]) is bool
        assert isinstance(x["ancillary_math_error"], (bool, str))
    conditions = {}
    for condition in ("base", "step32", "step64"):
        out = dict(main_evaluation=evaluation(a.runtime / f"eval-{condition}"),
                   numeric_probe_evaluation=evaluation(a.runtime / f"eval-numeric-{condition}"))
        grades = [x for x in proof if x["condition"] == condition]
        if grades:
            out["proofs"] = {role: proof_counts([x for x in grades if x["role"] == role])
                             for role in sorted({x["role"] for x in grades})}
            out["proofs_by_configuration"] = {
                source: proof_counts([x for x in grades if x["source_id"] == source])
                for source in sorted({x["source_id"] for x in grades})}
        for group in ("elementary", "numeric-probe"):
            path = HERE / f"{group}-{condition}-grades.json"
            if path.exists():
                rows = read(path)
                assert all(x["condition"] == condition for x in rows)
                out[group] = dict(graded=len(rows), correct=sum(x["numeric_correct"] for x in rows))
        conditions[condition] = out
    comparisons = {}
    base = {x["job_id"]: x for x in proof if x["condition"] == "base"}
    for condition in ("step32", "step64"):
        target = {x["job_id"]: x for x in proof if x["condition"] == condition}
        common = sorted(set(base) & set(target))
        for role in sorted({base[k]["role"] for k in common}):
            jobs = [k for k in common if base[k]["role"] == role]
            wins = [k for k in jobs if target[k]["complete_proof"] and not base[k]["complete_proof"]]
            losses = [k for k in jobs if base[k]["complete_proof"] and not target[k]["complete_proof"]]
            comparisons[f"{condition}_vs_base/{role}"] = dict(
                paired=len(jobs), wins=wins, losses=losses, net=len(wins)-len(losses))
    training = training_summary(a.runtime)
    diagnostics = {}
    for condition in ("step32", "step64"):
        path = a.runtime / f"distribution-{condition}" / "receipt.json"
        if path.exists():
            probe = read(path)
            diagnostics[condition] = {k: probe.get(k) for k in
                ("status", "n_examples", "summary", "elapsed_seconds", "interpretation_note")}
    result = dict(conditions=conditions, paired_comparisons=comparisons, training=training,
                  fixed_prefix_distribution_diagnostics=diagnostics,
                  notes=["Missing grades are ungraded, not failures.",
                         "Two samples per theorem are not independent theorems.",
                         "Worker seconds exclude some process startup/teardown; use study wall time too.",
                         "Training summaries count only rounds with one completed train receipt; failed attempts are retained as provenance but not included in training totals.",
                         "Rollout counts and finish reasons are restricted to complete rollout receipts paired with completed training rounds; rollout IDs must be globally unique.",
                         "Legacy rollout receipts without IDs retain finish-reason record counts but have unavailable unique-rollout counts."])
    a.out.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps(dict(out=str(a.out), proof_grades=len(proof),
                         completed_rounds={k: v["completed_rounds"] for k,v in training.items()})))


if __name__ == "__main__":
    main()
