"""Repair a serialization-only failure from saved coordinates, never rerun solver stages."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
M = json.loads((OUT / "pre-run-hashes.json").read_text())
ROOT = Path(M["scratch"])

if len(sys.argv) > 1:
    case, arm = sys.argv[1:3]
    worker = OUT / "worker.py"
    assert hashlib.sha256(worker.read_bytes()).hexdigest() == M["files"][str(worker)]
    source = worker.read_text()
    old = "error_digits=float(digits)"
    new = "error_digits=float(str(digits))"
    assert source.count(old) == 1
    sys.argv = [str(worker), str(ROOT), "measure", case, arm]
    exec(compile(source.replace(old, new), str(worker), "exec"))
else:
    events = [json.loads(l) for l in (ROOT / "events.jsonl").read_text().splitlines()]
    assert events[-1]["stage"] == "campaign_done", "Wait until both campaign streams finish"
    assert not (ROOT / "measurement-repair-started.json").exists(), "Only one measurement repair"
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in (OUT / "repair_measurement.py", OUT / "measurement-repair.md")}
    repair = {"created_utc": datetime.now(timezone.utc).isoformat(), "reason": "float(mpf) serialization inside high_precision_mode rejected; use float(str(mpf)) for the error_digits display field only", "files": hashes,
        "original_worker_sha256": M["files"][str(OUT / "worker.py")],
        "changes": {"error_digits=float(digits)": "error_digits=float(str(digits))"},
        "unchanged": ["saved initial candidates", "saved refined coordinates", "refinement", "final verification", "references", "thresholds", "rules.md"]}
    (OUT / "measurement-repair-hashes.json").write_text(json.dumps(repair, ensure_ascii=False, indent=2)+"\n")
    (ROOT / "measurement-repair-started.json").write_text(json.dumps(repair, ensure_ascii=False, indent=2)+"\n")
    prior = ROOT / "serialization-error-reports"
    prior.mkdir()
    for name in ("answer.md", "per-problem.csv", "per-candidate.csv", "judgments.json", "raw-hashes.json"):
        if (OUT / name).exists():
            shutil.copyfile(OUT / name, prior / name)
    for task in M["inputs"]:
        for arm in task["arm_order"]:
            d = ROOT / "runs" / task["case_id"]
            if not (d / (arm + ".refined.pkl")).exists():
                continue
            path = d / (arm + ".measure.json")
            if path.exists():
                path.rename(d / (arm + ".measure-serialization-error.json"))
            env = {k: v for k, v in os.environ.items() if not k.startswith("GEOSOLVER_ABLATE_")}
            env.update(M["thread_environment"])
            env.update(PYTHONPATH=str(ROOT / "final/src"), PYTHONDONTWRITEBYTECODE="1")
            with (d / (arm + ".measure-repair.log")).open("w") as log:
                subprocess.run(["taskset", "-c", str(M["cpus"][0]), M["python"], "-B", str(OUT / "repair_measurement.py"), task["case_id"], arm],
                    env=env, stdout=log, stderr=subprocess.STDOUT, timeout=90, check=True)
            with (OUT / "progress.md").open("a") as f:
                f.write(f"\n保存座標から測定修復完了: {task['case_id']} {arm}\n")
    subprocess.run([M["python"], "-B", str(OUT / "analyze.py")], check=True)
    with (OUT / "answer.md").open("a") as f:
        f.write("\n測定スクリプトの桁数表示用変換が高精度型制約に拒否されたため、全構成の保存済み座標から測定を再計算した。修正は `float(digits)` → `float(str(digits))` の1箇所のみ。探索・精密化・最終検証は再実行していない。修復前の自動集計は/tmpに退避し、最終判定には使っていない。元スクリプト・失敗した測定を保存し、追加スクリプトのhashを measurement-repair-hashes.json に測定修復前に記録した。判定ルール・参照値・閾値は変更していない。\n")
    with (OUT / "progress.md").open("a") as f:
        f.write("\n全12問・24構成完了。表示変換の修復と固定ルールによる集計を完了。\n")
