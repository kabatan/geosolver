"""Finalize report metadata after the successful independent audit; no solves."""
import csv
import gzip
import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
audit = json.loads((OUT / "final-audit.json").read_text())
assert audit["runs"] == 648 and audit["frozen_regrading_matches"]
assert audit["original_reporting_verdicts_and_per_problem_identical"]
path = OUT / "per-run.csv"
rows = list(csv.DictReader(path.open()))
original_columns = list(rows[0])
for row in rows:
    handoffs = json.loads(row["handoffs"])
    assert any(h["kind"] == "main" for h in handoffs)
    # The fixed source calls search_algebraic_branches at primary stage entry
    # before this observed handoff. None of these arms disables that call.
    row["algebraic_preprocessing_invoked"] = "True"
    row["algebraic_invocation_evidence"] = "primary handoff + fixed control flow"
    row["runtime_failure"] = str(row["normal_completion"] == "False" and row["category"] not in ("timeout", "missing"))
    row["worker_error"] = ""
    if row["runtime_failure"] == "True":
        with gzip.open(row["raw_path"], "rt") as stream:
            raw = json.load(stream)
        row["worker_error"] = (raw.get("solver_result") or {}).get("error", "")
stream = io.StringIO(newline="")
writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
writer.writeheader()
writer.writerows(rows)
payload = stream.getvalue().encode()
assert len(payload) < 3_000_000
roundtrip = list(csv.DictReader(io.StringIO(payload.decode())))
assert len(roundtrip) == 648
assert all(all(a[k] == b[k] for k in original_columns) for a, b in zip(rows, roundtrip, strict=True))
path.write_bytes(payload)
answer = (OUT / "answer.md").read_text()
answer = "\n".join(line for line in answer.splitlines() if not line.startswith("D3の1.0超：")) + "\n"
answer += ("\n照合：648個の登録キーと648件の起動記録が一致。最大同時実行数16。凍結版での再採点、実行前の集計処理との問題別結果・判定の照合が通過した（`final-audit.json`）。\n"
           "段階summaryの欠測は第2探索・救済・初期処理・精密化が各1件で、同じworker例外の実行。代数的前処理の呼出入口は、全648実行の主精密化への引継ぎ記録と固定コードの順序から確認した。候補を生成したかは別列に保存した。\n"
           "worker例外：HMMT-2011-equilateral-hexagon、seed 403、NO_DIVERSE_SELECTION。construction H returned no object。再試行なし。\n"
           "CSVの出力整理の変更とハッシュは `reporting-revision.json` に記録。solver・観測ラッパー・入力・予測・閾値・採点・時間比の計算は変更していない。\n")
(OUT / "answer.md").write_text(answer)
now = datetime.now(timezone.utc).isoformat()
(OUT / "progress.md").write_text(
    f"# 事前登録7b：完了\n\n更新 UTC: {now}\n\n完了: 648/648。集計・最終照合完了。\n\n"
    "並列上限16（実測最大16）、180秒・1コア、seed 401–403。再試行・追加seedなし。\n\n"
    "生結果の欠測0、worker artifact欠落1、計数欠測0。失敗・時間切れも集計した。\n\n"
    "入力・ソースのハッシュ不変、凍結版の再採点と実行前の判定処理との照合が通過。時間は他作業の負荷を含む参考値。\n")
for p in OUT.rglob("*"):
    assert not p.is_file() or p.stat().st_size <= 3_000_000, str(p)
files = {str(p.relative_to(OUT)): {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size}
         for p in sorted(OUT.rglob("*")) if p.is_file() and p.name != "final-files.json"}
(OUT / "final-files.json").write_text(json.dumps({"completed_utc": now, "files": files}, indent=2) + "\n")
print(json.dumps({"runs": 648, "per_run_csv_bytes": len(payload), "finished_utc": now}))
