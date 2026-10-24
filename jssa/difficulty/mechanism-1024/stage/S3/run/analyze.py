"""Mechanical preregistration-10 judgments from saved pre-verification values."""
import csv
import hashlib
import json
from pathlib import Path
from mpmath import mp

mp.dps = 750
OUT = Path(__file__).resolve().parent
M = json.loads((OUT / "pre-run-hashes.json").read_text())
ROOT = Path(M["scratch"])
ARMS = ["T0", "T1", "T2"]
FIVE = ["AIME-2018-II-14", "HMMT-2023-FEB-GEO-07", "JMO-2013-PRE-05", "JMO-2024-PRE-06", "aime-2002-2-14"]


def read(p):
    return json.loads(p.read_text()) if p.exists() else None


def digits(row):
    if row is None or row.get("absolute_error") is None:
        return None
    error = mp.mpf(row["absolute_error"])
    return min(mp.mpf(600), -mp.log10(error)) if error else mp.mpf(600)


def best(rows):
    rows = [r for r in rows if r.get("absolute_error") is not None and mp.isfinite(mp.mpf(r["absolute_error"]))]
    return min(rows, key=lambda r: mp.mpf(r["absolute_error"])) if rows else None


def short(value):
    return mp.nstr(mp.mpf(value), 25) if value is not None else None


def write_csv(path, rows):
    keys = list(dict.fromkeys(k for r in rows for k in r)) or ["arm", "source_uid", "sequence", "error_digits", "missing"]
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def fmt(value):
    return "欠測" if value is None else f"{float(str(value)):.2f}"


problems, candidates, missing, refs_missing, iterations = [], [], [], [], []
numerics = {}
for task in M["inputs"]:
    case = task["case_id"]
    d = ROOT / "runs" / case
    initial = read(d / "initial.json")
    reference = read(d / "references.json")
    if not reference or not reference["available"]:
        refs_missing.append(dict(case_id=case, reason=(reference or {}).get("error", "reference stage missing")))
    p = dict(case_id=case, seed=0, group=task["group"], focus_five=case in FIVE,
             order=">".join(task["arm_order"]), initial_candidates=len(task["candidate_uids"]),
             search_seconds_S1=initial["search_seconds"], reference_available=bool(reference and reference["available"]),
             reference_error=(reference or {}).get("error"), reference_seconds=(reference or {}).get("seconds"))
    values = {}
    for arm in ARMS:
        ref, mes, ver = [read(d / (arm + suffix)) for suffix in (".refinement.json", ".measure.json", ".verification.json")]
        if not (ref and mes and ver and ver["complete"]):
            missing.append(case+":"+arm+":"+"/".join(k for k, v in (("精密化", ref), ("測定", mes), ("最終検証", ver and ver["complete"])) if not v))
        rows = mes["rows"] if mes else []
        b = best(rows)
        values[arm] = digits(b)
        prefix = arm + "_"
        p.update({prefix+"best_error_digits": short(values[arm]), prefix+"best_absolute_error": short(b["absolute_error"]) if b else None,
                  prefix+"best_candidate_uid": b["candidate_uid"] if b else None,
                  prefix+"best_normalized_l2": short(b.get("normalized_l2")) if b else None,
                  prefix+"refinement_seconds": ref["seconds"] if ref else None,
                  prefix+"measurement_seconds": mes["seconds"] if mes else None,
                  prefix+"verification_seconds": ver["seconds"] if ver else None,
                  prefix+"attempted": ref["attempted"] if ref else None,
                  prefix+"returned": ref["returned"] if ref else None,
                  prefix+"unattempted": ref["unattempted"] if ref else None,
                  prefix+"deadline_hit": ref["deadline_hit"] if ref else None,
                  prefix+"immediate_pass_count": sum(r["immediate_pass"] for r in rows) if mes else None,
                  prefix+"final_pass_count": sum(r["final_pass"] for r in ver["rows"]) if ver else None,
                  prefix+"verification_unattempted": sum(r["status"] == "unattempted_deadline" for r in ver["rows"]) if ver else None,
                  prefix+"verification_timedout": sum(r["status"] == "deadline_reached" for r in ver["rows"]) if ver else None,
                  prefix+"missing_answer": sum(r.get("absolute_error") is None for r in rows) if mes else None,
                  prefix+"missing_residual": sum("normalized_l2" not in r for r in rows) if mes else None})
        verification = {r["rank"]: r for r in ver["rows"]} if ver else {}
        seen = set()
        for r in rows:
            row = dict(r)
            seen.add(r["source_uid"])
            v = verification.get(r["rank"])
            row.update(refinement_seconds=(ref or {}).get("candidate_seconds", {}).get(r["source_uid"]),
                       final_pass=v["final_pass"] if v else None,
                       final_status=v["status"] if v else "missing", final_seconds=v["seconds"] if v else None,
                       final_normalized_residual=v.get("normalized_residual") if v else None)
            for k in ("answer", "absolute_error", "solver_residual", "original_residual_norm", "normalized_l2", "normalized_max", "final_normalized_residual"):
                if k in row:
                    row[k] = short(row[k])
            candidates.append(row)
        for c in initial["candidates"]:
            if c["candidate_uid"] not in seen:
                candidates.append(dict(case_id=case, seed=0, arm=arm, candidate_id=c["candidate_id"],
                    candidate_uid=c["candidate_uid"], source_uid=c["candidate_uid"], status="not_returned" if ref else "refinement_missing",
                    immediate_pass=False if ref else None, final_pass=False if ref else None, final_status="not_returned" if ref else "missing"))
        if case == M["trace_case"]:
            trace = read(d / (arm + ".iteration-errors.json"))
            if trace:
                iterations.extend(trace["rows"])
                p[prefix+"iteration_measurement_seconds"] = trace.get("seconds")
                if not trace["rows"]:
                    missing.append(case+":"+arm+":反復軌跡:"+str(trace.get("missing")))
            else:
                missing.append(case+":"+arm+":反復軌跡")
    s1 = best(read(d / "S1-BASE.measure.json")["rows"])
    values["S1"] = digits(s1)
    p["S1_BASE_best_error_digits"] = short(values["S1"])
    for key, a, b in (("T2_minus_T1", "T2", "T1"), ("T1_minus_T0", "T1", "T0"), ("T2_minus_S1", "T2", "S1")):
        p[key] = short(values[a]-values[b]) if values[a] is not None and values[b] is not None else None
    t0, t1, t2 = [values[a] for a in ARMS]
    if any(v is None for v in (t0, t1, t2)):
        typ = "欠測"
    elif abs(t0-t1) <= 20 and t2-max(t0, t1) >= 40:
        typ = "接点型"
    elif abs(t1-t2) <= 20 and min(t1, t2)-t0 >= 40:
        typ = "絶対値型"
    elif max(t0, t1, t2)-min(t0, t1, t2) <= 20:
        typ = "同程度"
    else:
        typ = "混合/中間/逆方向"
    p["reading_type"] = typ
    numerics[case] = values
    problems.append(p)

focus = [p for p in problems if p["case_id"] in FIVE]
group_a = [p for p in focus if p["group"] == "A"]
group_b = [p for p in problems if p["group"] == "B"]


def compare(p, a, b, threshold, absolute=False):
    a, b = numerics[p["case_id"]][a], numerics[p["case_id"]][b]
    if a is None or b is None:
        return None
    return abs(a-b) <= threshold if absolute else a-b >= threshold


q1 = [compare(p, "T2", "T1", 40) for p in group_a]
q2 = [compare(p, "T1", "T0", 40) for p in focus]
q3 = [compare(p, "T2", "T1", 20, True) for p in group_b]
q4 = [compare(p, "T2", "S1", 20, True) for p in focus]
counts = {"Q1": sum(v is True for v in q1), "Q2": sum(v is True for v in q2), "Q3": sum(v is True for v in q3), "Q4": sum(v is True for v in q4)}
judgments = dict(Q1="当たり" if counts["Q1"] >= min(4, len(group_a)) else "外れ",
    Q2="外れ" if counts["Q2"] >= 2 else ("判定不能" if None in q2 else "当たり"),
    Q3="当たり" if all(v is True for v in q3) else "外れ",
    Q4="当たり" if all(v is True for v in q4) else "外れ")
q4_worse = [p["case_id"] for p in focus if compare(p, "S1", "T2", 40) is True]
if judgments["Q4"] == "外れ" and q4_worse:
    branch = 4
    reading = "分岐4：T2がS1ありより明らかに悪い。登録上は距離0・半径補助式との組合せも効くという読み。ただし今回T2はS1ありと同じ式であり、共有機負荷・時間打切りの影響を除けず、組合せの因果効果をこの比較だけで確認したとは言えない。"
elif all(p["reading_type"] == "同程度" for p in problems):
    branch, reading = 5, "分岐5：3条件に差がない。現在の改善を接する条件に固有の効果として押し出さない。"
elif all(p["reading_type"] == "接点型" for p in focus):
    branch, reading = 1, "分岐1：T0≈T1でT2だけ良い。接点を使う変換の寄与を支持する。"
elif all(p["reading_type"] == "絶対値型" for p in focus):
    branch, reading = 2, "分岐2：T0だけ悪くT1≈T2。主な改善は絶対値の扱いとして主張を縮める。"
else:
    branch, reading = 3, "分岐3：問題によって分かれる。複数の原因を処理しているとし、問題ごとの内訳を示す。中間差や逆方向も接点・絶対値の単独効果に割り当てない。"
if any(p["reading_type"] == "欠測" for p in problems):
    reading += " 欠測があるため、この全体分類は暫定である。"

events = [json.loads(l) for l in (ROOT / "events.jsonl").read_text().splitlines()]
loads = [e["loadavg"][0] for e in events]
bad = [e for e in events if e.get("returncode", 0) != 0]
notes = {"Q1": f"{counts['Q1']}/{len(group_a)}問（必要4問、欠測{q1.count(None)}）",
         "Q2": f"改善{counts['Q2']}/5問（上限1問、欠測{q2.count(None)}）",
         "Q3": f"{counts['Q3']}/6問が20桁以内（全て必要、欠測{q3.count(None)}）",
         "Q4": f"{counts['Q4']}/5問がS1ありと20桁以内（全て必要、欠測{q4.count(None)}）"}
lines = ["| 予測 | 判定 | 固定条件の結果 |", "|---|---|---|"]
lines += [f"| {q} | {judgments[q]} | {notes[q]} |" for q in judgments]
lines += ["", reading, "", "桁数は最終検証で修正する前の、精密化直後の最良候補の目標値絶対誤差の−log10（上限600）。大きいほど良い。通過状態で候補を選別していない。差ありは40桁以上、同程度は20桁以内。", "",
          "| 問題 | 群 | T0 | T1 | T2 | S1あり（参考） | 内訳 |", "|---|---|---:|---:|---:|---:|---|"]
for p in problems:
    v = numerics[p["case_id"]]
    lines.append(f"| {p['case_id']} | {p['group']} | {fmt(v['T0'])} | {fmt(v['T1'])} | {fmt(v['T2'])} | {fmt(v['S1'])} | {p['reading_type']} |")
lines += ["", "大改善5問の差（丸め前の値で判定）：", "", "| 問題 | T2−T1 | T1−T0 | T2−S1あり |", "|---|---:|---:|---:|"]
for p in focus:
    lines.append(f"| {p['case_id']} | {fmt(p['T2_minus_T1'])} | {fmt(p['T1_minus_T0'])} | {fmt(p['T2_minus_S1'])} |")
lines += ["", "通過数と精密化時間（T0 / T1 / T2）：", "", "| 問題 | 直後通過 | 最終通過 | 精密化秒 |", "|---|---:|---:|---:|"]
for p in problems:
    cells = [" / ".join(str(p[a+"_"+key]) for a in ARMS) for key in ("immediate_pass_count", "final_pass_count")]
    cells.append(" / ".join(fmt(p[a+"_refinement_seconds"]) for a in ARMS))
    lines.append("| "+p["case_id"]+" | "+" | ".join(cells)+" |")
missing_answers = sum(p[a+"_missing_answer"] or 0 for p in problems for a in ARMS)
unattempted = sum(p[a+"_unattempted"] or 0 for p in problems for a in ARMS)
vu = sum(p[a+"_verification_unattempted"] or 0 for p in problems for a in ARMS)
vt = sum(p[a+"_verification_timedout"] or 0 for p in problems for a in ARMS)
lines += ["", f"欠測：参照値を作れない問題{len(refs_missing)}問、目標誤差を測れない返却候補{missing_answers}件、工程・反復軌跡の欠測{len(missing)}件。精密化未処理{unattempted}候補、最終検証未処理{vu}候補・処理中時間切れ{vt}候補。工程の非ゼロ終了{len(bad)}件。", "", "| 参照値の欠測問題 | 理由 |", "|---|---|"]
lines += [f"| {r['case_id']} | {r['reason']} |" for r in refs_missing] or ["| なし | 修復版と同じ参照式の700桁評価に全12問成功 |"]
if missing:
    lines += ["", "欠測内訳："+"、".join(missing)+"。"]
lines += ["", "S1で測定不備により欠測だった問題も、今回は同じ式を型制約の外で評価した結果だけを用いた。参照図や丸め値での代用はない。Q4の比較元は現存するS1の修復済み700桁測定である。", "",
 f"実行機は{M['host']}。2並列、CPU affinity {M['cpus']}、各1コア、内部スレッド1。工程前後・30秒間隔の1分load averageは{min(loads):.2f}〜{max(loads):.2f}。各条件の90秒は壁時計上限であり、負荷と打切りに影響される。速度の一般化はしない。", "",
 "S1の同じ224候補・順序・Config・seed 0を使用し、探索・精密化の再試行はしていない。最終検証は凍結版でスイッチ解除、各集合別枠90秒。通過は数値的な検証であり、厳密な存在証明ではない。", "",
 "AIME 2018 II-14の各条件の最良候補の軌跡はiterations-AIME-2018-II-14.csv。初期/最終点、LM段階初期点、LM反復、Newtonのyieldを区別し、失敗したNewton試行も残す。誤差は保存点から計測時計の外で評価した。観測フックの負担は90秒に含まれる。予測を置かない記述用データである。", "",
 "残差は元の条件をS1の保存尺度で正規化したL2・最大絶対値。JMO 2024の尺度算出不能10条件はS1どおり除数1。per-candidate.csvに誤差・残差・通過・時間、per-problem.csvに問題別集計を保存した。CSVの長い数値は25有効桁、判定は保存された700桁の誤差から行った。", "",
 f"精密化src：`{M['source_hash']}`。検証src：`{M['frozen_source_hash']}`。生データ：`{ROOT}`、一覧はraw-hashes.json。実行前固定はpre-run-hashes.jsonと../rules.md。12問・1 seedの比較であり、統計的な一般化はしない。commit/pushはしていない。", ""]
write_csv(OUT / "per-candidate.csv", candidates)
write_csv(OUT / "per-problem.csv", problems)
for row in iterations:
    for k in ("answer", "absolute_error"):
        if k in row:
            row[k] = short(row[k])
write_csv(OUT / "iterations-AIME-2018-II-14.csv", iterations)
(OUT / "answer.md").write_text("\n".join(lines))
(OUT / "judgments.json").write_text(json.dumps(dict(judgments=judgments, counts=counts,
    comparisons={"Q1":q1,"Q2":q2,"Q3":q3,"Q4":q4}, reading_branch=branch, q4_worse=q4_worse,
    missing=missing, missing_references=refs_missing, nonzero_stages=bad), ensure_ascii=False, indent=2)+"\n")
raw = {str(p.relative_to(ROOT)): dict(sha256=hashlib.sha256(p.read_bytes()).hexdigest(), bytes=p.stat().st_size)
       for p in sorted(ROOT.rglob("*")) if p.is_file()}
(OUT / "raw-hashes.json").write_text(json.dumps(raw, indent=2)+"\n")
for p in OUT.rglob("*"):
    if p.is_file():
        assert p.stat().st_size <= 3_000_000, p
print(json.dumps(dict(judgments=judgments, branch=branch), ensure_ascii=False))
