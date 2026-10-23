"""Q19 採点（prereg-5）。既存の research_runner の _answer_keys / read_run_outcome をそのまま使う。
使い方: python score_q19.py <unsealed dir> <unseen-1983 dir> <出力dir>"""
import csv, json, sys, glob, collections, statistics
sys.path.insert(0, "benchmarks")
from pathlib import Path
import research_runner as rr
from geosolver.exact import describe_exact

U, W, OUT = map(Path, sys.argv[1:4])
target = set((W / "prereg/target-26.txt").read_text().split())
audit = {r["id"]: r for r in csv.DictReader(open(W / "audit/audit.csv", encoding="utf-8"))}
rows = []
for f in sorted(U.glob("runs/*/*.json")):
    raw = json.loads(f.read_text(encoding="utf-8"))
    cid = raw["case_id"]
    a = audit[cid]
    ref = (a["primary_answer"] or a["secondary_answer"]).strip()
    if ref.isdigit(): ref = str(int(ref))  # AIME答の先頭0（026→26）は表記の差。監査表にも明記
    # 対象26問は一次解答。参考表は二次解答の場合あり
    try:
      exp = sorted({rr._canonical_json(describe_exact(v).canonical_key()) for v in rr.reference_expressions(ref)})
    except Exception as e:
      exp = ["UNPARSEABLE:" + ref]
    act = rr._answer_keys(raw.get("solver_result"))
    oc = rr.read_run_outcome(raw)
    res = raw.get("solver_result") or {}
    rows.append(dict(case_id=cid, seed=raw["seed"], verdict=a["verdict"], in_target=cid in target, reference=ref,
                     matched=bool(oc["normal_completion"] and act == exp), n_answers=len(act),
                     extra=len(set(act) - set(exp)), status=oc["status"], failure_stage=oc.get("failure_stage"),
                     termination=res.get("termination_reason"), elapsed=res.get("elapsed_seconds"),
                     diag_identified=(res.get("diagnostics") or {}).get("exact_identified"),
                     diag_numeric=(res.get("diagnostics") or {}).get("numeric_feasible")))
OUT.mkdir(parents=True, exist_ok=True)
with open(OUT / "assessment.jsonl", "w", encoding="utf-8") as fh:
    for r in rows: fh.write(json.dumps(r, ensure_ascii=False) + "\n")
def summarize(sel):
    sel = [r for r in rows if sel(r)]
    per = collections.defaultdict(list)
    for r in sel: per[r["case_id"]].append(r)
    return sel, per
for name, fn in [("target26", lambda r: r["in_target"]), ("others", lambda r: not r["in_target"])]:
    sel, per = summarize(fn)
    print(name, "runs", len(sel), "matched", sum(r["matched"] for r in sel), "problems", len(per),
          ">=3seed", sum(sum(x["matched"] for x in v) >= 3 for v in per.values()))
