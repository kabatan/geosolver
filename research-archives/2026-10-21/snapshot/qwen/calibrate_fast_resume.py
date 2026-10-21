"""CPU-only completed-round resume test using a real FP16 checkpoint."""

import json
import shutil
import sys
from pathlib import Path
from unittest.mock import patch

from .common import file_hash, write_json
from .grpo_run import main as run_main


def main():
    root = Path("qwen/.runtime/exp03_budgeted/preparation")
    selection = json.loads((root / "selected_calibration.json").read_text())
    checkpoint = root / selection["natural"] / "update"
    smoke = root / "resume_smoke"
    if smoke.exists():
        raise ValueError("Use the preserved resume test; do not overwrite it")
    config = json.loads(Path("qwen/.runtime/exp02_tech/live/manifest.json").read_text())["config"]
    config.update({"technical_calibration": True, "route": "fp16_native", "max_seqs": 4})
    config["lr"] = selection["lr"]
    config.pop("budget_ledger", None)
    config_path = root / "resume_config.json"
    write_json(config_path, config)
    target = smoke / "round-000/update"
    shutil.copytree(checkpoint, target)
    before = {
        str(p.relative_to(checkpoint)): file_hash(p) for p in checkpoint.rglob("*") if p.is_file()
    }
    with (
        patch.object(
            sys,
            "argv",
            [
                "resume",
                "--config",
                str(config_path),
                "--output",
                str(smoke),
                "--through-round",
                "1",
            ],
        ),
        patch(
            "qwen.grpo_run.run_worker", side_effect=AssertionError("GPU worker must not launch")
        ) as worker,
    ):
        run_main()
    after = {
        str(p.relative_to(checkpoint)): file_hash(p) for p in checkpoint.rglob("*") if p.is_file()
    }
    finished = json.loads((smoke / "COMPLETE.json").read_text())
    report = {
        "workers_launched": worker.call_count,
        "checkpoint_unchanged": before == after,
        "rounds_completed": finished["rounds_completed"],
        "adapter_sha256": file_hash(Path(finished["adapter"]) / "adapter_model.safetensors"),
    }
    assert report["workers_launched"] == 0 and report["checkpoint_unchanged"]
    write_json(root / "resume_check.json", report)
    print(json.dumps(report))


if __name__ == "__main__":
    main()
