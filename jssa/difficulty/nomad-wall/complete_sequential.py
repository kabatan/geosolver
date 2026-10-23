"""Complete still-unstarted supplemental slots without another helper layer."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("q14_completion", HERE / "complete_unstarted.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def main():
    inventory = json.loads((HERE / "initial-attempt-inventory.json").read_text())
    pending = [row for row in inventory["missing_slots"] if not row["solver_started"]]
    old = {str(p.relative_to(HERE)): hashlib.sha256(p.read_bytes()).hexdigest()
           for p in (HERE / "completion").glob("*/runs/*/[012].json")}
    event = {"created_unix": time.time(), "preexisting_raw_sha256": old,
             "reason": "supplemental child helper cannot see precreated empty directories; use one sequential parent and persistent directory markers",
             "jobs": 1, "solver_code_or_parameters_changed": False}
    path = HERE / "completion-sequential-receipt.json"
    assert not path.exists()
    path.write_text(json.dumps(event, indent=2))
    # Persist run directories as nonempty before spawning a solver child.
    for row in pending:
        folder = HERE / "completion" / row["mode"] / "runs" / row["id"]
        temp = folder / f"{row['seed']}.temp"
        temp.mkdir(parents=True, exist_ok=True)
        (temp / "directory-marker.json").write_text(json.dumps(
            {"id": row["id"], "seed": row["seed"], "mode": row["mode"]}))
    errors = []
    pairs = list(dict.fromkeys((row["id"], row["seed"]) for row in pending))
    for identifier, seed in pairs:
        existing_cpus = set()
        for mode in ("B", "N"):
            raw = HERE / "completion" / mode / "runs" / identifier / f"{seed}.json"
            if raw.exists():
                cpu = json.loads(raw.read_text()).get("process", {}).get("assigned_cpu")
                if cpu is not None:
                    existing_cpus.add(cpu)
        assert len(existing_cpus) <= 1
        cpu = next(iter(existing_cpus), 0)
        try:
            module.pair(identifier, seed, cpu)
        except Exception:
            error = {"id": identifier, "seed": seed, "traceback": traceback.format_exc()}
            errors.append(error)
            print(json.dumps(error), flush=True)
    assert all(hashlib.sha256((HERE / p).read_bytes()).hexdigest() == h for p, h in old.items())
    event["finished_unix"] = time.time()
    event["errors"] = errors
    event["final_raw_count"] = len(list((HERE / "completion").glob("*/runs/*/[012].json")))
    path.write_text(json.dumps(event, indent=2))
    print(json.dumps({"final_raw_count": event["final_raw_count"], "errors": len(errors)}), flush=True)


if __name__ == "__main__":
    main()
