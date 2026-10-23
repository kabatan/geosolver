"""Step (4). Run ONLY after the user has committed and pushed predictions.csv.

The committed prediction bytes, recorded SHA-256, frozen raw files, and code
are verified BEFORE any p aggregation. Never writes predictions.csv.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
from scipy.stats import spearmanr

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
REL = "jssa/difficulty/new2026-predict/predictions.csv"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", required=True, help="user-confirmed pushed commit containing frozen predictions")
    args = parser.parse_args()
    if (OUT / "score.md").exists() or (OUT / "outcomes.csv").exists():
        parser.error("score outputs already exist; refusing overwrite")
    before = (OUT / "predictions.csv").read_bytes()
    expected = (OUT / "predictions.sha256").read_text().split()[0]
    freeze = json.loads((OUT / "freeze-manifest.json").read_text())
    assert sha(before) == expected == freeze["predictions_sha256"]
    commit = subprocess.check_output(["git", "rev-parse", "--verify", f"{args.commit}^{{commit}}"], cwd=ROOT, text=True).strip()
    committed = subprocess.check_output(["git", "show", f"{commit}:{REL}"], cwd=ROOT)
    assert committed == before, "committed predictions differ; STOP before aggregation"
    manifest = json.loads((OUT / "run-manifest.json").read_text())
    for path, expected_sha in manifest["input_sha256"].items():
        assert sha((ROOT / path).read_bytes()) == expected_sha, f"input changed: {path}"
    assert sha((OUT / "per-pair.csv").read_bytes()) == freeze["per_pair_sha256"]
    predictions = list(csv.DictReader(before.decode().splitlines()))
    for row in predictions:
        raw_path = OUT / "raw" / f"{row['id']}.json"
        assert sha(raw_path.read_bytes()) == freeze["raw_sha256"][row["id"]]
    # First outcome aggregation occurs here, after every integrity gate.
    outcomes = []
    for row in predictions:
        raw = json.loads((OUT / "raw" / f"{row['id']}.json").read_text())
        records = raw["records"]
        assert len(records) == raw["starts_done"] == 200
        hits = sum(r["cls"] == "hit" for r in records)
        observed = math.log((hits + 0.5) / (200 - hits + 0.5))
        full, baseline = float(row["pred_logit_full"]), float(row["pred_logit_nvars_only"])
        outcomes.append(dict(id=row["id"], starts=200, hits=hits, misses=200-hits,
                             p=hits/200, observed_logit=observed,
                             pred_logit_full=full, pred_logit_nvars_only=baseline,
                             squared_error_full=(full-observed)**2,
                             squared_error_nvars_only=(baseline-observed)**2))
    rho = float(spearmanr([r["pred_logit_full"] for r in outcomes], [r["p"] for r in outcomes]).statistic)
    full_sse = sum(r["squared_error_full"] for r in outcomes)
    baseline_sse = sum(r["squared_error_nvars_only"] for r in outcomes)
    a1, a2 = rho >= 0.4, full_sse < baseline_sse
    with (OUT / "outcomes.csv").open("x", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(outcomes[0]))
        writer.writeheader()
        writer.writerows(outcomes)
    conclusion = "事前登録AのA1・A2をともに満たした。" if a1 and a2 else "未使用問題では確認できなかった。292問の結果は開発集合内の結果として残す。"
    text = f"""# 事前登録2 A：未使用20問の判定

集計 UTC: {datetime.now(UTC).isoformat()}。予測の固定 UTC: {freeze['frozen_utc']}。
ユーザー確認のcommit: `{commit}`。予測SHA-256: `{expected}`。

- A1（{'成立' if a1 else '不成立'}）：full予測と実測pのSpearman順位相関 = {rho:.12g}（基準 ≥ 0.4）。
- A2（{'成立' if a2 else '不成立'}）：ロジット二乗誤差の合計 full = {full_sse:.12g}、nvars_only = {baseline_sse:.12g}（基準 full < nvars_only）。

{conclusion}

実測p = hits/200。実測ロジット = ln((hits+0.5)/(misses+0.5))。
固定モデルのtarget欄はこの平滑化オッズの対数を指すものとして扱う。
係数、φ、G、予測は結果に応じて変更していない。予測・入力・rawのハッシュを集計前に検証した。
個票はoutcomes.csv。Gの数値探索の失敗・有限試行の限界はREADME.mdとper-pair.csvを参照。
"""
    with (OUT / "score.md").open("x") as stream:
        stream.write(text)
    assert (OUT / "predictions.csv").read_bytes() == before
    print(text)


if __name__ == "__main__":
    main()
