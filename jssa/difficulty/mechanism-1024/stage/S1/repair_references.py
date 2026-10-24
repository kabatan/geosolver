"""Recover reference evaluation lost to HP constructor guards, using saved coordinates."""
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
WORKER = OUT / "worker.py"
OLD = '    with mp.workdps(700), high_precision_mode():\n        refs = [_eval_exact_to_mpf(r, 700) for r in TASK["reference_expressions"]]\n'
NEW = '    with mp.workdps(700):\n        refs = [_eval_exact_to_mpf(r, 700) for r in TASK["reference_expressions"]]\n    assert all(r is not None and mp.isfinite(r) for r in refs)\n    with mp.workdps(700), high_precision_mode():\n'

if len(sys.argv) > 1:
    case, arm = sys.argv[1:3]
    assert hashlib.sha256(WORKER.read_bytes()).hexdigest() == M["files"][str(WORKER)]
    source = WORKER.read_text()
    assert source.count(OLD) == 1
    source = source.replace(OLD, NEW).replace("error_digits=float(digits)", "error_digits=float(str(digits))")
    sys.argv = [str(WORKER), str(ROOT), "measure", case, arm]
    exec(compile(source, str(WORKER), "exec"))
else:
    assert not (ROOT / "reference-repair-started.json").exists()
    tasks = []
    for task in M["inputs"]:
        for arm in task["arm_order"]:
            path = ROOT / "runs" / task["case_id"] / (arm + ".measure.json")
            data = json.loads(path.read_text())
            if any("NoneType" in row.get("answer_error", "") for row in data["rows"]):
                tasks.append((task["case_id"], arm))
    record = {"created_utc": datetime.now(timezone.utc).isoformat(), "files": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__), OUT / "reference-repair.md")},
        "original_worker_sha256": M["files"][str(WORKER)], "old": OLD, "new": NEW,
        "other_change": "error_digits=float(digits) -> error_digits=float(str(digits)) (already documented)",
        "affected": tasks, "solver_reruns": 0}
    (OUT / "reference-repair-hashes.json").write_text(json.dumps(record, ensure_ascii=False, indent=2)+"\n")
    (ROOT / "reference-repair-started.json").write_text(json.dumps(record, ensure_ascii=False, indent=2)+"\n")
    prior = ROOT / "reference-evaluation-error-reports"
    prior.mkdir()
    for name in ("answer.md", "per-problem.csv", "per-candidate.csv", "judgments.json", "raw-hashes.json"):
        shutil.copyfile(OUT / name, prior / name)
    for case, arm in tasks:
        d = ROOT / "runs" / case
        (d / (arm + ".measure.json")).rename(d / (arm + ".measure-reference-error.json"))
        env = {k: v for k, v in os.environ.items() if not k.startswith("GEOSOLVER_ABLATE_")}
        env.update(M["thread_environment"])
        env.update(PYTHONPATH=str(ROOT / "final/src"), PYTHONDONTWRITEBYTECODE="1")
        with (d / (arm + ".reference-repair.log")).open("w") as log:
            subprocess.run(["taskset", "-c", str(M["cpus"][0]), M["python"], "-B", str(OUT / "repair_references.py"), case, arm],
                env=env, stdout=log, stderr=subprocess.STDOUT, timeout=90, check=True)
        with (OUT / "progress.md").open("a") as f:
            f.write(f"\n保存座標の参照値評価修復完了: {case} {arm}\n")
    subprocess.run([M["python"], "-B", str(OUT / "analyze.py")], check=True)
    with (OUT / "answer.md").open("a") as f:
        f.write("\n測定実装に2点の不備があり、保存座標から測定を修復した。桁数表示は `float(digits)` を `float(str(digits))` に変更し、無理数の参照値5問は型制約に妨げられない場所で同じ式を同じ700桁で評価した。探索・精密化・最終検証は再実行していない。元スクリプト、失敗した測定、暫定集計は保存し、各修復スクリプトのhashを修復前に別ファイルへ記録した。判定ルール・参照式・閾値は変更していない。\n")
    with (OUT / "progress.md").open("a") as f:
        f.write("\n参照値評価の修復と再集計完了。探索・精密化・検証の再実行なし。最終監査へ。\n")
