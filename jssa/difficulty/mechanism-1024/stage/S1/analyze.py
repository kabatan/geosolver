"""Apply pre-fixed S1 rules without adjusting thresholds or rerunning targets."""
import csv
import hashlib
import json
import math
import os
from pathlib import Path
from mpmath import mp

mp.dps = 750
OUT = Path(__file__).resolve().parent
M = json.loads((OUT / "pre-run-hashes.json").read_text())
ROOT = Path(M["scratch"])
ARMS = ["BASE", "NO_RESIDUAL_REWRITE"]


def read(p):
    return json.loads(p.read_text()) if p.exists() else None


def short(x):
    return mp.nstr(mp.mpf(x), 25) if x is not None else None


def write_csv(path, rows):
    keys = list(dict.fromkeys(k for row in rows for k in row))
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def fmt(x):
    return "欠測" if x is None else f"{x:.2f}"


problems, candidates, missing = [], [], []
for task in M["inputs"]:
    case = task["case_id"]
    d = ROOT / "runs" / case
    initial = read(d / "initial.json")
    p = {"case_id": case, "seed": 0, "p1_group": task["p1_group"], "order": ">".join(task["arm_order"]),
         "initial_candidates": len(initial["candidates"]) if initial else None,
         "search_seconds": initial["search_seconds"] if initial else None}
    if not initial:
        missing.append(case + ":主探索候補")
    best = {}
    for arm in ARMS:
        ref = read(d / (arm + ".refinement.json"))
        mes = read(d / (arm + ".measure.json"))
        ver = read(d / (arm + ".verification.json"))
        if not (ref and mes and ver and ver["complete"]):
            missing.append(case + ":" + arm + ":" + "/".join(n for n, obj in (("精密化", ref), ("測定", mes), ("最終検証", ver)) if not obj))
        rows = mes["rows"] if mes else []
        usable = [r for r in rows if r.get("absolute_error") is not None]
        best[arm] = min(usable, key=lambda r: mp.mpf(r["absolute_error"])) if usable else None
        b = best[arm]
        prefix = arm + "_"
        p.update({prefix + "refinement_seconds": ref["seconds"] if ref else None,
            prefix + "measurement_seconds": mes["seconds"] if mes else None,
            prefix + "verification_seconds": ver["seconds"] if ver else None,
            prefix + "deadline_hit": ref["deadline_hit"] if ref else None,
            prefix + "attempted": ref["attempted"] if ref else None,
            prefix + "returned": ref["returned"] if ref else None,
            prefix + "unattempted": ref["unattempted"] if ref else None,
            prefix + "immediate_pass_count": sum(r["immediate_pass"] for r in rows) if mes else None,
            prefix + "final_pass_count": sum(r["final_pass"] for r in ver["rows"]) if ver else None,
            prefix + "verification_unattempted": sum(r["status"] == "unattempted_deadline" for r in ver["rows"]) if ver else None,
            prefix + "verification_timedout": sum(r["status"] == "deadline_reached" for r in ver["rows"]) if ver else None,
            prefix + "verification_complete": bool(ver and ver["complete"]),
            prefix + "best_candidate_uid": b["candidate_uid"] if b else None,
            prefix + "best_absolute_error": short(b["absolute_error"]) if b else None,
            prefix + "best_error_digits": b["error_digits"] if b else None,
            prefix + "best_normalized_l2": short(b.get("normalized_l2")) if b else None,
            prefix + "missing_answer": len(rows)-len(usable) if mes else None,
            prefix + "missing_residual": sum("normalized_l2" not in r for r in rows) if mes else None})
        verification = {r["rank"]: r for r in ver["rows"]} if ver else {}
        seen_sources = set()
        for r in rows:
            row = dict(r)
            row["refinement_seconds"] = (ref or {}).get("candidate_seconds", {}).get(r["source_uid"])
            seen_sources.add(r["source_uid"])
            v = verification.get(r["rank"])
            row.update(final_pass=v["final_pass"] if v else None, final_status=v["status"] if v else "missing",
                final_seconds=v["seconds"] if v else None,
                final_normalized_residual=v.get("normalized_residual") if v else None)
            for k in ("answer", "absolute_error", "solver_residual", "original_residual_norm", "normalized_l2", "normalized_max", "final_normalized_residual"):
                if k in row:
                    row[k] = short(row[k])
            candidates.append(row)
        if initial:
            for c in initial["candidates"]:
                if c["candidate_uid"] not in seen_sources:
                    candidates.append({"case_id": case, "seed": 0, "arm": arm,
                        "candidate_id": c["candidate_id"], "candidate_uid": c["candidate_uid"], "source_uid": c["candidate_uid"],
                        "status": "not_returned" if ref else "refinement_missing", "immediate_pass": False if ref else None,
                        "final_pass": False if ref else None, "final_status": "not_returned" if ref else "missing"})
    base, off = best[ARMS[0]], best[ARMS[1]]
    p["p1_met"] = bool(base and off and base["p1_base_threshold"] and off["p1_without_threshold"]) if task["p1_group"] else None
    p["error_digits_gap"] = abs(base["error_digits"]-off["error_digits"]) if base and off else None
    p["p2_met"] = p["error_digits_gap"] is not None and p["error_digits_gap"] <= 20 if not task["p1_group"] else None
    for stage, count in (("immediate", "immediate_pass_count"), ("final", "final_pass_count")):
        a, b = p[ARMS[0]+"_"+count], p[ARMS[1]+"_"+count]
        p[stage+"_base_only"] = bool(a and not b) if a is not None and b is not None else None
    problems.append(p)

p1 = sum(bool(p["p1_met"]) for p in problems if p["p1_group"])
p2 = sum(bool(p["p2_met"]) for p in problems if not p["p1_group"])
seven = [p for p in problems if p["p1_group"]]
before = sum(bool(p["immediate_base_only"]) for p in seven)
after = sum(bool(p["final_base_only"]) for p in seven)
p3_missing = any(p["immediate_base_only"] is None or p["final_base_only"] is None or not all(p[a+"_verification_complete"] for a in ARMS) for p in seven)
judgments = {"P1": "当たり" if p1 >= 6 else "外れ", "P2": "当たり" if p2 == 5 else "外れ", "P3": "判定不能" if p3_missing else ("当たり" if after <= before else "外れ")}
write_csv(OUT / "per-candidate.csv", candidates)
write_csv(OUT / "per-problem.csv", problems)

events = [json.loads(l) for l in (ROOT / "events.jsonl").read_text().splitlines()]
loads = [e["loadavg"][0] for e in events]
bad = [e for e in events if e.get("returncode", 0) != 0]
unattempted = sum(p[a+"_unattempted"] or 0 for p in problems for a in ARMS)
verify_unattempted = sum(p[a+"_verification_unattempted"] or 0 for p in problems for a in ARMS)
verify_timeout = sum(p[a+"_verification_timedout"] or 0 for p in problems for a in ARMS)
missing_answers = sum(p[a+"_missing_answer"] or 0 for p in problems for a in ARMS)
lines = ["| 予測 | 判定 | 固定条件に対する数値 |", "|---|---|---|",
    f"| P1 | {judgments['P1']} | {p1}/7問（必要6問以上） |",
    f"| P2 | {judgments['P2']} | {p2}/5問が20桁以内（必要5問すべて） |",
    f"| P3 | {judgments['P3']} | ありだけ通過：精密化直後{before}問 → 最終検証後{after}問（7問） |", "",
    "seed 0、同じ主探索候補、各構成90秒で精密化した。下表の桁数は残差ではなく、参照値への目標値の絶対誤差の −log10。値が大きいほど誤差が小さい。最良候補は通過状態で選別していない。", "",
    "| 問題 | 群 | 初期候補 | 誤差桁数 あり / なし | 桁差 | 直後通過数 あり / なし | 最終通過数 あり / なし | 精密化秒 あり / なし |",
    "|---|---|---:|---:|---:|---:|---:|---:|"]
for p in problems:
    a, b = ARMS
    lines.append(f"| {p['case_id']} | {'P1・P3' if p['p1_group'] else 'P2'} | {p['initial_candidates']} | {fmt(p[a+'_best_error_digits'])} / {fmt(p[b+'_best_error_digits'])} | {fmt(p['error_digits_gap'])} | {p[a+'_immediate_pass_count']} / {p[b+'_immediate_pass_count']} | {p[a+'_final_pass_count']} / {p[b+'_final_pass_count']} | {fmt(p[a+'_refinement_seconds'])} / {fmt(p[b+'_refinement_seconds'])} |")
lines += ["", f"欠測工程：{len(missing)}件。目標値を評価できない返却候補：{missing_answers}件。精密化の時間上限で未処理：{unattempted}候補。最終検証で未処理：{verify_unattempted}候補、処理中の時間切れ：{verify_timeout}候補。工程の非ゼロ終了：{len(bad)}件。"]
if missing:
    lines += ["欠測内訳：" + "、".join(missing) + "。"]
lines += ["", f"実行機は {M['host']}（{M['platform']}）。2並列、CPU affinity {M['cpus']}、各1コア、内部スレッド1。1分load averageは工程開始・終了時に {min(loads):.2f}〜{max(loads):.2f}。共有機の高負荷下の壁時計時間であり、速度の一般化はできない。", "",
    "残差は元の条件を、保存初期候補から固定した共通除数で正規化して評価した。候補別の残差・目標誤差・通過・時間は per-candidate.csv、問題別の最良誤差と工程時間は per-problem.csv にある。各CSVの長い数値は25有効桁で保存し、判定は/tmpの700桁測定値で行った。規則は rules.md に実行前固定した。", "",
    f"精密化src：`{M['source_hash']}`。最終検証src：凍結版60db4b6 `{M['frozen_source_hash']}`。最終検証は両構成とも書き換えスイッチを解除し、別枠90秒で行った。これは数値的な通過であり、厳密な存在証明や完全な答え集合の回収を示すものではない。", "",
    "12問・1 seedの段階比較である。停止したのは接条件の符号付き残差・距離0の座標差・半径補助式の書き換え群全体なので、接条件だけの効果には分けられない。", "",
    f"生データと座標：`{ROOT}`（リポジトリ外）。入力と実行スクリプトのhashは pre-run-hashes.json、生データのhashは raw-hashes.json。再試行・問題差し替えは行っていない。", ""]
(OUT / "answer.md").write_text("\n".join(lines))
raw_files = sorted(p for p in ROOT.rglob("*") if p.is_file() and "src" not in p.parts and "__pycache__" not in p.parts)
(OUT / "raw-hashes.json").write_text(json.dumps({str(p.relative_to(ROOT)): {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size} for p in raw_files}, indent=2)+"\n")
(OUT / "judgments.json").write_text(json.dumps({"judgments": judgments, "P1_met": p1, "P2_met": p2,
    "P3_before": before, "P3_after": after, "missing": missing, "nonzero_stages": bad}, ensure_ascii=False, indent=2)+"\n")
for p in OUT.rglob("*"):
    if p.is_file():
        assert p.stat().st_size <= 3_000_000, p
print(json.dumps(judgments, ensure_ascii=False))
