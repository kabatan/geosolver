"""Summarize all planned slots; never runs or changes the solver."""
from common import *
import csv
from collections import Counter
import math
import statistics
from benchmarks import research_runner as research
from geosolver.exact import describe_exact


def csv_write(path, rows):
    with Path(path).open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def describe(values):
    values = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    return dict(n=len(values), total=sum(values), mean=statistics.mean(values) if values else None,
                median=statistics.median(values) if values else None,
                minimum=min(values) if values else None, maximum=max(values) if values else None)


def main(retained=None):
    manifest = read(HERE / "manifest.json")
    cases = {c.identifier:c for c in research._load_cases()}
    rows, keyed = [], {}
    for m in manifest:
        case = cases[m["id"]]
        expected = sorted({research._canonical_json(describe_exact(v).canonical_key())
                           for ref in case.references for v in research.reference_expressions(ref)})
        for mode in ("B","R"):
            run_dir = HERE / "campaign" / mode / "runs" / m["id"]
            raw_path, receipt_path = run_dir / "0.json", run_dir / "0.receipt.json"
            if retained is not None:
                import zlib
                item = retained.get((m["id"],mode))
                receipt,raw = (item[0],json.loads(zlib.decompress(item[1]))) if item else (None,None)
            else:
                raw = read(raw_path) if raw_path.exists() else None
                receipt = read(receipt_path) if receipt_path.exists() else None
            row = dict(id=m["id"], mode=mode, seed=0, completed=raw is not None and receipt is not None,
                       signed_applicable=m["signed_applicable"], n_vars=m["n_vars"],
                       matched=False, status="pending", termination_reason=None, failure_stage=None,
                       solver_seconds=None, process_seconds=None, cpu_seconds=None, cost=180.0,
                       audit_verified=False, local_search_calls=0, augmented_calls=0,
                       hard_calls=0, hard_bypassed=0, signed_rows_applied=0, signed_rows_changed=0,
                       signed_fallback_evaluations=0, hp_smoothing_calls=0,
                       contract_issues="", runner_error=False, scoring_error=None,
                       cpu=None, started_unix=None, finished_unix=None,
                       load_start_1m=None, load_end_1m=None)
            if raw:
                out = research.read_run_outcome(raw)
                audit = receipt["audit"] if receipt else audit_summary(run_dir / "0.audit.jsonl")
                try:
                    answer_match = research._answer_keys(raw.get("solver_result")) == expected
                except Exception as exc:
                    answer_match = False
                    row["scoring_error"] = repr(exc)
                row.update(matched=bool(out["normal_completion"] and answer_match and audit["verified"]),
                           status=out["status"], termination_reason=out["termination_reason"],
                           failure_stage=out["failure_stage"], solver_seconds=out["wall_seconds"],
                           process_seconds=out["process_wall_seconds"], cpu_seconds=out["cpu_seconds"],
                           audit_verified=audit["verified"],
                           contract_issues=";".join(raw.get("execution_contract_issues",[])))
                if out["normal_completion"] and not answer_match and out["status"] == "solved":
                    row["status"] = "wrong_answer_set"
                for key in ("local_search_calls","augmented_calls","hard_calls","hard_bypassed",
                            "signed_rows_applied","signed_rows_changed","signed_fallback_evaluations",
                            "hp_smoothing_calls"):
                    row[key] = audit["counts"].get(key,0)
                if row["matched"] and row["solver_seconds"] is not None:
                    row["cost"] = min(180.0,float(row["solver_seconds"]))
            if receipt:
                row.update(cpu=receipt["cpu"], started_unix=receipt["started_unix"],
                           finished_unix=receipt["finished_unix"],
                           load_start_1m=receipt["start_loadavg"][0],
                           load_end_1m=receipt["end_loadavg"][0],
                           runner_error=bool(receipt["runner_error"]))
            rows.append(row)
            keyed[(m["id"],mode)] = row
    paired = []
    for m in manifest:
        b,r = (keyed[(m["id"],mode)] for mode in ("B","R"))
        paired.append(dict(id=m["id"], signed_applicable=m["signed_applicable"], n_vars=m["n_vars"],
            completed=b["completed"] and r["completed"], correct_B=b["matched"], correct_R=r["matched"],
            delta=int(r["matched"])-int(b["matched"]), cost_B=b["cost"], cost_R=r["cost"],
            cost_delta=r["cost"]-b["cost"], status_B=b["status"], status_R=r["status"],
            hard_calls_B=b["hard_calls"], hard_bypassed_R=r["hard_bypassed"],
            signed_rows_R=r["signed_rows_applied"],
            start_skew_seconds=abs(r["started_unix"]-b["started_unix"]) if r["started_unix"] and b["started_unix"] else None,
            touched=bool(b["augmented_calls"] or r["augmented_calls"])))
    observed = [r for r in paired if r["completed"]]
    gains = [r["id"] for r in observed if r["delta"] > 0]
    losses = [r["id"] for r in observed if r["delta"] < 0]
    complete = len(observed) == 323
    infra = sum(r["completed"] and (not r["audit_verified"] or bool(r["contract_issues"])
                                  or r["runner_error"] or r["scoring_error"] is not None) for r in rows)
    summary = dict(utc=now(), exploratory=True, timing_reference_only=True,
                   planned_pairs=323, completed_pairs=len(observed), planned_runs=646,
                   completed_runs=sum(r["completed"] for r in rows), complete=complete,
                   gains=gains, losses=losses, net_gain=len(gains)-len(losses),
                   unresolved_infrastructure_runs=infra, modes={},
                   start_skew_seconds=describe(r["start_skew_seconds"] for r in observed),
                   untouched_discordances=[r["id"] for r in observed if r["delta"] and not r["touched"]])
    for mode in ("B","R"):
        rr = [r for r in rows if r["mode"]==mode and r["completed"]]
        summary["modes"][mode] = dict(correct=sum(r["matched"] for r in rr), completed=len(rr), pending=323-len(rr),
            failures=sum(not r["matched"] for r in rr), statuses=dict(Counter(r["status"] for r in rr)),
            termination_reasons=dict(Counter(str(r["termination_reason"]) for r in rr)),
            solver_seconds=describe(r["solver_seconds"] for r in rr),
            process_seconds=describe(r["process_seconds"] for r in rr),
            cpu_seconds=describe(r["cpu_seconds"] for r in rr), cost=describe(r["cost"] for r in rr),
            load_start=describe(r["load_start_1m"] for r in rr),
            local_search_reached=sum(r["local_search_calls"]>0 for r in rr),
            hard_called_cases=sum(r["hard_calls"]>0 for r in rr),
            signed_applied_cases=sum(r["signed_rows_applied"]>0 for r in rr),
            signed_changed_cases=sum(r["signed_rows_changed"]>0 for r in rr),
            signed_fallback_evaluations=sum(r["signed_fallback_evaluations"] for r in rr),
            hp_smoothing_reached=sum(r["hp_smoothing_calls"]>0 for r in rr),
            audit_unverified=sum(not r["audit_verified"] for r in rr),
            contract_errors=sum(bool(r["contract_issues"]) for r in rr),
            scoring_errors=sum(r["scoring_error"] is not None for r in rr))
    summary["strata"] = []
    for target in (False,True):
        rr = [r for r in observed if r["signed_applicable"] == target]
        summary["strata"].append(dict(signed_applicable=target,n=len(rr),
            correct_B=sum(r["correct_B"] for r in rr),correct_R=sum(r["correct_R"] for r in rr),
            gains=sum(r["delta"]>0 for r in rr),losses=sum(r["delta"]<0 for r in rr)))
    if complete:
        import numpy as np
        from scipy.stats import binomtest
        rng = np.random.default_rng(131023)
        deltas = np.array([r["delta"] for r in paired])
        costs = np.array([r["cost_delta"] for r in paired])
        boots = np.empty((10000,2))
        for i in range(10000):
            ix = rng.integers(0,323,323)
            boots[i] = deltas[ix].mean(),costs[ix].mean()
        summary["accuracy_delta_ci95"] = np.percentile(boots[:,0],[2.5,97.5]).tolist()
        summary["cost_delta_ci95"] = np.percentile(boots[:,1],[2.5,97.5]).tolist()
        summary["mcnemar_exact_p"] = float(binomtest(len(gains),len(gains)+len(losses),0.5).pvalue) if gains or losses else 1.0
        no,yes = summary["strata"]
        summary["predictions"] = dict(P1=summary["net_gain"]>=3 and len(losses)<=2,
            P2=(yes["gains"]/yes["n"] > no["gains"]/no["n"]) if yes["n"] and no["n"] else None,
            P3=summary["modes"]["R"]["cost"]["mean"]<=0.9*summary["modes"]["B"]["cost"]["mean"])
        summary["improvement_gate"] = summary["net_gain"]>=1 and infra==0
        series = {i.split("-")[0].upper() for i in gains}
        summary["A_decision"] = ("続行候補" if summary["net_gain"]>=5 and len(losses)<=2 and len(series)>=2
                                  else "縮小") if summary["improvement_gate"] else "中止"
    else:
        summary["A_decision"] = "縮小（暫定・未完了）"
    csv_write(HERE / "per-run.csv", rows)
    csv_write(HERE / "per-problem.csv", paired)
    dump(HERE / "summary.json", summary)
    if not complete:
        b,r = (summary["modes"][m] for m in ("B","R"))
        text = f'''Aの中心を担えるか：縮小（暫定）。完成{len(observed)}/323組では全体の効果を判定できない。事前登録の基準を保持して実行中。

## 結論（実行途中）

Q13の開発323問・seed 0・180秒・1コアの探索的比較は{summary['completed_runs']}/646実行が完了した。現時点の完了実行では凍結Bの正答{b['correct']}/{b['completed']}、パッチRの正答{r['correct']}/{r['completed']}。対応完了組で救済{len(gains)}、喪失{len(losses)}。処理順はID順であり、この途中部分を全体へ外挿しない。

## 根拠と限界

[事前登録](preregistration.md)を新規探索前に固定し、予測・基準は変えていない。[実装・入力ロック](execution-lock.json)、[入力規則の対象](manifest.json)、[実行別表](per-run.csv)、[問題別表](per-problem.csv)、[途中集計](summary.json)を保存した。接条件規則は26/323問、変数なし31問も対象に含む。局所探索のみでhard罰則を0とし、既存精密化用の接触式を倍精度探索へ拡張する。元の候補採否・精密化・最終検証は保持する。

実行済みの不正答・失敗はB={b['failures']}、R={r['failures']}。予定未完了はB={b['pending']}、R={r['pending']}であり、solver失敗とは区別する。未解決の実行契約・フック・採点異常は{infra}件。機能検査の導入失敗1回を探索前に修正し、人工残差15例×2条件は合格した。記録経路の異常で中断した2試行は全保存した（合計完了カウンタ312件、保存307件、うち出力欠落5件・監査未確認16件、完了記録欠落5件）。これは監査を返却結果へ同梱し、親メモリにも控えを持つ運用へ修正した第3試行である。数値関数7個のAST一致と人工例B/R各1回の起動を確認済み（[逸脱記録](deviations.md)、[数値コード同一性](numerical-code-identity.json)）。旧試行の成功は継ぎ足さない。I/O手順には事前登録からの逸脱があるが、予測・基準は変えていない。

最大8並列、4組のB/Rを同時に開始し、問題番号の偶奇でコア・投入順を交替している。高負荷のため時間計測は参考扱い。正答純増がなければ「中止」とし、時間差だけでは救済しない。改善ゲート通過時のみQ2用の事前登録文を作り、未使用問題では実行しない。ネットワーク・pip・src編集・既存成果物編集・commit/pushは行っていない。

更新UTC：{summary['utc']}
'''
        (HERE / "answer.md").write_text(text)
    print(json.dumps({k:summary[k] for k in ("completed_pairs","completed_runs","net_gain","gains","losses","unresolved_infrastructure_runs","A_decision")},ensure_ascii=False))

if __name__=="__main__":
    main()
