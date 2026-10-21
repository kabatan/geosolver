"""Alternate fresh vLLM rollouts and one-pass LoRA training rounds.

Each round launches separate processes so generation releases its GPU memory
before the trainer loads. Evaluation is a separate frozen-protocol operation.
"""

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path = Path(path)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temp.replace(path)


def launch(command, log_path, timeout):
    with Path(log_path).open("w") as log:
        subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                       check=True, timeout=timeout)


def validate_inputs(args, config, pool):
    from rollout_worker import read_pool, rollout_settings
    from train_worker import parameters

    settings = rollout_settings(config)
    parameters(config)
    rows = read_pool(pool)
    if (args.start_round < 1 or args.end_round < args.start_round or
            args.end_round * settings["batch_size"] > len(rows)):
        raise ValueError("Requested rounds exceed ordered training pool")
    if args.start_round > 1 and not args.prior_checkpoint:
        raise ValueError("Resuming after round one requires --prior-checkpoint")
    if args.start_round == 1 and args.prior_checkpoint:
        raise ValueError("Round one starts from base without a prior checkpoint")
    prior = Path(args.prior_checkpoint).resolve() if args.prior_checkpoint else None
    if prior:
        prior_receipt = json.loads((prior / "receipt.json").read_text())
        if prior_receipt.get("status") != "complete" or prior_receipt.get("round") != args.start_round - 1:
            raise ValueError("Prior checkpoint does not immediately precede requested range")
    if config["model_metadata"] is None or not Path(config["model_metadata"]).is_file():
        raise ValueError("Missing model metadata")
    return settings, rows, prior


def main(args):
    config_path, pool_path = Path(args.config).resolve(), Path(args.pool).resolve()
    config = json.loads(config_path.read_text())
    settings, rows, checkpoint = validate_inputs(args, config, pool_path)
    eval_path = Path(args.eval_jobs).resolve() if args.eval_jobs else None
    if eval_path and not eval_path.is_file():
        raise ValueError("Missing frozen evaluation jobs")
    if args.preflight:
        print(json.dumps(dict(status="preflight_pass", start_round=args.start_round,
                              end_round=args.end_round,
                              examples=(args.end_round-args.start_round+1)*8,
                              expected_updates=(args.end_round-args.start_round+1)*2,
                              first_id=rows[(args.start_round-1)*8]["id"],
                              last_id=rows[args.end_round*8-1]["id"])), flush=True)
        return
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    receipt = dict(status="running", start_unix=time.time(),
                   start_round=args.start_round, end_round=args.end_round,
                   config_sha256=digest(config_path), pool_sha256=digest(pool_path),
                   eval_jobs=str(eval_path) if eval_path else None,
                   eval_jobs_sha256=digest(eval_path) if eval_path else None,
                   driver_sha256=digest(__file__),
                   rollout_driver_sha256=digest(HERE / "rollout_worker.py"),
                   trainer_driver_sha256=digest(HERE / "train_worker.py"),
                   initial_checkpoint=str(checkpoint) if checkpoint else None,
                   rounds_completed=0, updates=0)
    write_json(out / "receipt.json", receipt)
    started = time.monotonic()
    try:
        for round_number in range(args.start_round, args.end_round + 1):
            round_dir = out / f"round-{round_number:03d}"
            round_dir.mkdir()
            rollout_dir = round_dir / "rollout"
            command = [sys.executable, str(HERE / "rollout_worker.py"),
                       "--config", str(config_path), "--pool", str(pool_path),
                       "--round", str(round_number),
                       "--start-index", str((round_number - 1) * 8),
                       "--out", str(rollout_dir)]
            if checkpoint:
                command.extend(["--checkpoint", str(checkpoint)])
            tick = time.monotonic()
            launch(command, round_dir / "rollout.log",
                   int(config.get("rollout_timeout_seconds", 7200)))
            rollout_receipt = json.loads((rollout_dir / "receipt.json").read_text())
            if rollout_receipt.get("status") != "complete":
                raise AssertionError(f"Round {round_number} rollout did not complete")
            training_config = dict(config)
            training_config["prior_checkpoint"] = str(checkpoint) if checkpoint else None
            training_config_path = round_dir / "training-config.json"
            write_json(training_config_path, training_config)
            train_dir = round_dir / "train"
            command = [sys.executable, str(HERE / "train_worker.py"),
                       "--config", str(training_config_path),
                       "--batch", str(rollout_dir / "batch.json"),
                       "--out", str(train_dir)]
            launch(command, round_dir / "train.log",
                   int(config.get("train_timeout_seconds", 3600)))
            train_receipt = json.loads((train_dir / "receipt.json").read_text())
            if (train_receipt.get("status") != "complete" or
                    train_receipt.get("n_examples") != 8 or
                    train_receipt.get("updates") != 2):
                raise AssertionError(f"Round {round_number} trainer did not finish 8 examples/2 updates")
            checkpoint = train_dir
            receipt["rounds_completed"] += 1
            receipt["updates"] += train_receipt["updates"]
            receipt["last_checkpoint"] = str(checkpoint)
            receipt["last_adapter_sha256"] = train_receipt["adapter_sha256"]
            receipt["last_vllm_adapter_sha256"] = train_receipt["vllm_adapter_sha256"]
            write_json(out / "receipt.json", receipt)
            print(json.dumps(dict(round=round_number, ids=rollout_receipt["ids"],
                                  updates=train_receipt["updates"],
                                  cumulative_updates=receipt["updates"],
                                  seconds=time.monotonic()-tick,
                                  checkpoint=str(checkpoint))), flush=True)
        receipt["status"] = "complete"
    except BaseException as exc:
        receipt.update(status="failed", error=repr(exc))
        raise
    finally:
        receipt.update(end_unix=time.time(), elapsed_seconds=time.monotonic()-started)
        write_json(out / "receipt.json", receipt)
        print(json.dumps(receipt, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--pool", required=True)
    parser.add_argument("--eval-jobs")
    parser.add_argument("--out")
    parser.add_argument("--start-round", type=int, default=1)
    parser.add_argument("--end-round", type=int, required=True)
    parser.add_argument("--prior-checkpoint")
    parser.add_argument("--preflight", action="store_true")
    options = parser.parse_args()
    if not options.preflight and not options.out:
        parser.error("--out is required except for --preflight")
    main(options)
