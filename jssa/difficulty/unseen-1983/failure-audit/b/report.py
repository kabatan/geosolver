"""Build bounded Q29b evidence tables; never rewrite the frozen assessment."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import subprocess
from collections import Counter

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[4]
BASE=OUT.parents[1]
IDS=["AIME-1996-13","AIME-1996-15","AIME-1997-04","HMMT-2022-FEB-GEO-07","HMMT-2023-FEB-GEO-06"]
EXPECTED=dict(zip(IDS,[65,777,17,16902,68]))


def read(path):
    return json.loads((OUT/path).read_text())


def write_csv(name,rows):
    with (OUT/name).open("w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]))
        w.writeheader();w.writerows(rows)
    assert (OUT/name).stat().st_size<4_900_000


def decimals(answers):
    return [a["value"]["decimal"] for a in answers if a.get("kind")=="algebraic"]


def numeric_ok(candidate):
    return (candidate is not None and candidate.get("evaluation_status")=="ok" and
            candidate.get("guard_ok") and candidate.get("hard_feasible") and
            float(candidate["residual_norm_float"])<1e-6)


def compact_status(r):
    if "answers" in r:
        answers=decimals(r["answers"])
    else:
        answers=r.get("summary",{}).get("exact_assembly",{}).get("answer_values",r.get("accepted_answers",[]))
    return r.get("status"),answers,r.get("elapsed_seconds",r.get("elapsed"))


def build():
    original=[json.loads(s) for s in (BASE/"prereg/q19-scored/assessment.jsonl").read_text().splitlines()]
    target=[r for r in original if r["in_target"]]
    assert len(target)==130 and sum(r["matched"] for r in target)==85
    frozen=[r for r in original if r["case_id"] in IDS]
    assert len(frozen)==25
    write_csv("frozen-assessment.csv",frozen)
    features={r["id"]:r for r in read("development-comparison.json")["targets"]}
    summary=[];conditions=[];runs=[]
    notes={
      IDS[0]:"整数4変数+Bézoutを含む7変数。解は箱内。近傍では正答を検証でき、通常探索の到達失敗。整数条件だけが原因との因果断定はしない。",
      IDS[1]:"幾何は成立。高精度mpfの//が未実装でanswer_missing。狭義の探索失敗ではなく目標評価の実装不具合。",
      IDS[2]:"整数4変数+Bézoutを含む9変数（開発群最大値）。解は箱内。近傍では成功、通常seed 201は900秒枠でも不成功。",
      IDS[3]:"a=169と全Bézout証人の|k|>=84が通常箱・NOMAD拡張箱の外。箱外起点注入はSIGSEGV。HP直注入では正答検証可。APIの保存失敗を探索時間切れと混同しない。",
      IDS[4]:"角度・整数・凸性9不等式。座標の初期箱は±360、実際の座標は絶対値3未満。近傍と900秒枠で成功。箱幅単独の因果効果は未測定。",
    }
    for cid in IDS:
        w=read(f"witnesses/{cid}.json")
        for precision in w:
            for c in precision["conditions"]:
                conditions.append({"id":cid,"precision_dps":precision["dps"],**c})
        assert all(z["all_original_conditions_pass"] and z["solver_guard"][0] and z["solver_hard"]["hard_feasible"] for z in w)
        w=w[-1]
        old=[r for r in frozen if r["case_id"]==cid]
        old201=next(r for r in old if r["seed"]==201)
        nat=read(f"runs/natural-900-{cid}.json")
        near=read(f"runs/near-180-{cid}.json")
        local=read(f"local/{cid}-float.json")
        hp=read(f"local/{cid}-hp.json")
        assert hp["ambient_dps"]==180
        if near["status"]!="process_failed": assert near["ambient_dps"]==180
        tiny=[r for r in local if r["epsilon"]==1e-4]
        f=features[cid]
        s,a,t=compact_status(nat)
        ns,na,nt=compact_status(near)
        category="探索の失敗" if cid!=IDS[1] else "solver実装不具合（目標評価）"
        row={"問題":cid,"原因分類":category,"DSLの数学的誤り":"検出なし・正しい配置あり",
          "凍結180秒_5seed正解数":sum(r["matched"] for r in old),"凍結180秒_seed201":old201["status"],
          "診断900秒_API":s,"診断900秒_API答":";".join(a),"診断900秒_API経過秒":t,
          "近傍float候補採用_微小摂動3点":sum(bool(numeric_ok(r.get("candidate"))) for r in tiny),
          "近傍HP直注入_検証済答":";".join(sorted(set(hp.get("assembly",{}).get("answer_values",[])))),
          "近傍全工程180秒":ns,"近傍全工程_検証済答":";".join(sorted(set(na))),"近傍全工程経過秒":nt,
          "別結果_900秒worker計算本体":"", "別結果_900秒worker経過秒":"",
          "別結果_近傍と箱拡大180秒":"", "別結果_箱拡大検証済答":"", "別結果_箱拡大経過秒":"",
          "160桁最大等式残差":w["max_abs_equality_residual"],"最小原文不等式余裕":w["min_original_inequality_margin"],
          "変数数":f["variables"],"等式数":f["equalities"],"不等式数":f["inequalities"],"IsInteger呼出数":f["IsInteger_calls"],
          "探索箱外変数":";".join(w["witness_outside_search_box"]),"所見":notes[cid]}
        if cid==IDS[3]:
            mem=read(f"runs/worker-memory-900-{cid}.json")
            exp=read(f"runs/near-180-{cid}-expanded-box-control.json")
            es,ea,et=compact_status(exp)
            row.update({"別結果_900秒worker計算本体":mem["solver_status"],
                        "別結果_900秒worker経過秒":mem["elapsed_seconds"],
                        "別結果_近傍と箱拡大180秒":es,
                        "別結果_箱拡大検証済答":";".join(sorted(set(ea))),
                        "別結果_箱拡大経過秒":et})
        summary.append(row)
        for r in old:
            runs.append(dict(id=cid,group="original_frozen_assessment",seed=r["seed"],budget_seconds=180,
                             status=r["status"],answer=str(EXPECTED[cid]) if r["matched"] else "",elapsed=r["elapsed"],
                             part_of_original_85_of_130=True,source="../../prereg/q19-scored/assessment.jsonl"))
        for group,rec,src,budget in [("new_public_API",nat,f"runs/natural-900-{cid}.json",900),
                                    ("oracle_near_full_pipeline",near,f"runs/near-180-{cid}.json",180)]:
            st,ans,elapsed=compact_status(rec)
            runs.append(dict(id=cid,group=group,seed=201,budget_seconds=budget,status=st,answer=";".join(sorted(set(ans))),
                             elapsed=elapsed,part_of_original_85_of_130=False,source=src))
    write_csv("summary.csv",summary)
    write_csv("witness-conditions.csv",conditions)
    # Additional observations are separate rows, not substitutes for the public-API run.
    for file,group in [(f"runs/natural-900-{IDS[3]}-io-observed.json","public_API_IO_observation"),
                       (f"runs/worker-memory-900-{IDS[3]}.json","frozen_worker_execute_memory_output"),
                       (f"runs/near-180-{IDS[3]}-expanded-box-control.json","oracle_near_expanded_box_control")]:
        r=read(file)
        st,ans,elapsed=compact_status(r)
        runs.append(dict(id=IDS[3],group=group,seed=201,budget_seconds=180 if "near-" in file else 900,
            status=r.get("solver_status") or st,answer=";".join(sorted(set(ans))),elapsed=elapsed,
            part_of_original_85_of_130=False,source=file))
    write_csv("runs.csv",runs)
    manifest=read("manifest.json")
    assert subprocess.check_output(["git","diff","60db4b6","--","src"],cwd=ROOT)==b""
    checked={}
    for rel,h in {**manifest["sources"],**manifest["src_files"]}.items():
        got=hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()
        assert got==h,rel
        checked[rel]=True
    extra=[ROOT/"benchmarks/cases.jsonl",OUT/"audit.py",OUT/"report.py"]
    for year in (2022,2023):
        extra.append(Path(f"/home/kabatan/work/solver-research-assets/corpus97-sources/hmmt-{year}-geo-solutions.txt"))
    inventory={str(f.relative_to(OUT)):f.stat().st_size for f in OUT.rglob("*") if f.is_file() and f.name!="delivery-check.json"}
    assert all(size<5_000_000 for size in inventory.values())
    result=dict(original_score={"correct":85,"runs":130,"unchanged":True},all_5_witnesses_pass=True,
                source_hashes_unchanged=len(checked),current_src_equals_60db4b6=True,
                extra_input_sha256={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in extra},
                max_file_bytes=max(inventory.values()),file_sizes=inventory,
                summary_rows=len(summary),condition_rows=len(conditions),run_rows=len(runs))
    (OUT/"delivery-check.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:v for k,v in result.items() if k not in ("file_sizes","extra_input_sha256")},ensure_ascii=False,indent=2))
    for r in summary:print(r["問題"],r["診断900秒_API"],r["近傍全工程180秒"],r["近傍HP直注入_検証済答"])


if __name__=="__main__": build()
