"""Append the separate supplement, preserving the committed original report verbatim."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import execute_supplement as outer


def table(headers, rows):
    return "\n".join(["| " + " | ".join(headers) + " |",
                      "| " + " | ".join("---" for _ in headers) + " |",
                      *("| " + " | ".join(map(str, row)) + " |" for row in rows)])


def fraction(value):
    return f'{value["correct"]}/{value["runs"]}（{100 * value["correct"] / value["runs"]:.1f}%）'


def main():
    outer.file_limits()
    base, work = outer.BASE, outer.WORK
    lock, gate = outer.verify_gate()
    summary = outer.read(work / "summary.json")
    floor = outer.read(work / "floor-reproduction.json")
    completion = outer.read(outer.DEST / "completion.json")
    assert completion["completed_runs"] == 31
    rows = list(csv.DictReader((work / "results.csv").open()))
    original = outer.git("show", outer.COMMIT + ":" + str((base / "answer.md").relative_to(outer.ROOT)))
    assert (base / "answer.md").read_bytes() == original
    main_count, diagnostic = summary["main"], summary["diagnostic"]
    preamble = (
        f'**補遺の要点：主対象は{main_count["correct"]}/25（点予測16/25）、原因調査は{diagnostic["correct"]}/6（点予測3/6）。'
        'AIME-1996-15は5/5正答で、元の床演算不具合も評価器単体で再現した。'
        f'HMMT-2022の2件は5MBを超える一時出力の書込みで異常終了し、不正解に計上した。**\n\n'
        '元の主解析20/45・P1〜P4・凍結版の元DSLによる85/130は維持する。'
        '以下の既存本文は旧採点時点の記述をそのまま残し、補遺の別表と単純累積値を末尾に追記した。\n\n---\n\n'
    )
    assert main_count["output_record_missing"] == 2
    assert len(summary["missing_output_evidence"]) == 2
    assert all(e["file_limit_cause_inferred_from_write_trace_and_oversize_payload"]
               for e in summary["missing_output_evidence"])
    assert next(p for p in summary["predictions"] if p["name"] == "AIME-1996-15")["correct"] == 5
    parts = ["\n\n---\n\n**Q29d補遺：明示許可後の31実行（別表）**\n",
             f'主対象は **{fraction(main_count)}**、原因調査は **{fraction(diagnostic)}**。'
             '予測・lock・修正版ランナー・score.py・凍結srcを変更せず、固定順の8バッチで25+6実行した。'
             '旧主解析の欠落行へ成功例を代入せず、追加seed・再試行は行っていない。\n',
             '**補遺予測の判定**\n']
    comparisons = []
    labels = {"main_total": "主対象合計", "diagnostic_seed205_repeats": "原因調査 seed205の2反復",
              "diagnostic_new_missing": "原因調査 新seed206/207/209/210", "diagnostic_total": "原因調査合計"}
    for p in summary["predictions"]:
        interval = f'{p["interval_low"]}〜{p["interval_high"]}/{p["runs"]}' if p["interval_low"] is not None else "未設定"
        inside = "区間内" if p["inside_fixed_interval"] else "区間外"
        if p["inside_fixed_interval"] is None:
            inside = "判定なし"
        comparisons.append([labels.get(p["name"], p["name"]), f'{p["predicted_correct"]}/{p["runs"]}',
                            interval, f'{p["correct"]}/{p["runs"]}', f'{p["difference_from_point"]:+d}',
                            "一致" if p["point_exactly_met"] else "不一致", inside])
    parts += [table(["対象", "点予測", "主観的約90%区間", "実測", "点予測との差", "点予測の当否", "区間判定"], comparisons),
              '\n主対象の点予測16/25は外れた。問題別の点予測が一致したのはAIME-1983-12だけで、5問とも固定区間内。'
              '合計の予測区間は事前設定されていないため合計の区間判定はしない。'
              'これらは主観的予測区間であり、独立Bernoulli試行の信頼区間ではない。\n',
              '**主対象25件の全結果**\n']
    by_id = {p["case_id"]: [r for r in rows if r["group"] == "main" and r["case_id"] == p["case_id"]]
             for p in lock["predictions"]["main_by_problem"]}
    trial_table = []
    for cid, trials in by_id.items():
        trials.sort(key=lambda r: int(r["seed"]))
        cells = ["正答" if r["matched"] == "True" else "答えなし" if r["status"] == "no_answer_found"
                 else "異常終了・出力欠落" for r in trials]
        successful = next((r for r in trials if r["matched"] == "True"), None)
        values = f'`{successful["answers"]}` → `{successful["official_outputs"]}`' if successful else "—"
        trial_table.append([cid, *cells, values])
    parts += [table(["問題", "206", "207", "208", "209", "210", "正答時の幾何量→公式出力"], trial_table),
              '\nAIME-1983-12の5件は正常終了の0答で、全件 `numeric_feasible=False`。'
              '今回の補遺では有限予算で答えが得られなかったことを確認できたが、旧P4の成立理由や判定を遡って変更しない。\n',
              '**保存状態と5MB制約**\n',
              table(["対象", "保存要約", "取得できたsolver出力", "要約保存失敗", "solver出力欠落", "正常終了の答えなし"],
                    [[label, f'{c["saved_summaries"]}/{c["runs"]}', f'{c["solver_outputs_available"]}/{c["runs"]}',
                      c["summary_save_failures"], c["output_record_missing"], c["no_answer_found"]]
                     for label, c in [("主対象", main_count), ("原因調査", diagnostic)]]),
              '\n外側管理で、一時solver出力も含め `RLIMIT_FSIZE=4,999,999 byte`、core dump禁止を設定した。'
              'HMMT-2022-FEB-GEO-07のseed207/210は `cli.py:61` の `output.write_text(payload, ...)` で異常終了'
              '（returncode=1、外側timeoutなし）。保存されたstderr冒頭のpayload表示は、残余部分だけでそれぞれ'
              '5,217,714文字・5,218,060文字を示し、5MB上限を超える。'
              'この書込み箇所・payload長・継承上限から、ファイルサイズ制限による失敗と判断した。'
              '固定ランナーが保持するstderrは先頭2,000文字なので、例外末尾のerrnoそのものは確認できない。\n',
              '2件のログには `solved` 表示もあるが、解答集合は取得できていない。'
              '0答や探索失敗と読み替えず、固定score.pyによる `process_crash`・不正解として分母に残した。'
              '修正版の要約保存assertion失敗は0件。上限・圧縮・採点器を変えての再実行はしていない。\n',
              '**AIME-1991-14：原因調査6件（主対象へ合算しない）**\n']
    diag_rows = [r for r in rows if r["group"] != "main"]
    parts += [table(["群", "seed", "判定", "返却値", "solver秒", "開始UTC", "終了UTC"],
                    [[r["group"], r["seed"], "正答" if r["matched"] == "True" else r["status"],
                      r["answers"] or ("0答" if r["status"] == "no_answer_found" else "不明"),
                      f'{float(r["solver_seconds"]):.3f}' if r["solver_seconds"] else "—",
                      r["started_at_utc"], r["finished_at_utc"]] for r in diag_rows]),
              '\nseed205は2/2成功し、点予測0/2は不一致、固定区間0〜2/2には入った。'
              'Q19のseed205の失敗は今回の2反復では再現しなかった。入力矛盾を示す結果ではなく、'
              '過去の失敗に対する乱数・共有機負荷・停止条件の寄与はこの6件だけでは分離できない。'
              '既存のseed208の正答は既知の参照として残し、今回の6件へ混ぜていない。\n',
              '**AIME-1996-15の床演算不具合：探索を追加しない単体再現**\n',
              f'凍結srcのHP評価器 `safe_eval_expr_hp` に、既存の証人 `r=7/9` を100桁で与えた。'
              f'元target `(1000*r) // 1` は `{floor["original_target_error"]["exception_type"]}` となり、'
              f'直接原因は `{floor["original_target_error"]["cause_type"]}: {floor["original_target_error"]["cause_message"]}`。'
              '同じ評価器で書き直し後のtarget `r` は正常に評価され、固定score.pyの `floor_1000` は777を返した。'
              '補遺の5/5正答とも整合する。床演算実装は未修正で、この単体再現を追加のsolver実行や元の全失敗の原因証明とは扱わない。\n',
              '**元の数値を維持した併記**\n']
    cumulative = summary["arithmetic_all_execution_counts_requested_by_user"]
    parts += [table(["対象", "元の集計（変更なし）", "補遺のみ", "全実行の単純累積（参考）"],
                    [["主解析／主対象", "20/45（44.4%）", fraction(main_count), fraction(cumulative["main"])],
                     ["変更8問／補遺の変更4問", "20/40（50.0%）", fraction(summary["changed_supplement"]), fraction(cumulative["changed8"])],
                     ["原因調査", "1/7（14.3%）", fraction(diagnostic), fraction(cumulative["diagnostic"])],
                     ["凍結版・元DSL（Q19）", "85/130（65.4%）", "対象外", "85/130（変更なし）"]]),
              '\n単純累積はユーザー指定による算術上の併記で、旧欠落行も分母に残して追加実行を加算した。'
              '新しい比較実験の成功率推定や予測検証には使用しない。'
              '**旧P1＝不成立、P2＝不成立、P3＝不成立、P4＝成立（数値上のみ）を維持する。** '
              '既存結果・保存欠落を知った後に選んだ補遺であり、未使用問題に対する事前予測の成立とは呼ばない。\n',
              '**実行境界・時刻・照合記録**\n',
              table(["出来事", "UTC"], [
                  ["補遺予測lock", lock["locked_at_utc"]],
                  ["commit b83ad62のcommitter時刻", "2026-10-23T15:49:18Z"],
                  ["push完了（ユーザー明示申告）", "2026-10-23T15:49:21Z"],
                  ["補遺campaign開始", summary["timing"]["execution_started_at_utc"]],
                  ["最初の個別実行開始", summary["timing"]["first_run_started_at_utc"]],
                  ["最後の個別実行終了", summary["timing"]["last_run_finished_at_utc"]],
                  ["床演算の単体再現", floor["reproduced_at_utc"]]]),
              '\ncommitの存在だけでは投入せず、今回の別タスクでの明示許可とpush申告を記録した。'
              '`git log` でcommitを確認し、ローカルのremote-tracking refにも含まれることを照合した。'
              'push時刻をGitから独立に復元したとは主張しない。\n',
              f'補遺lockのSHA-256は `{outer.LOCK_SHA}`、修正版ランナーは `{outer.RUNNER_SHA}`。'
              f'いずれもcommit `b83ad62` と作業ファイルが一致した。予測本文は `{lock["prediction_sha256"]}`、'
              f'固定score.pyは `{lock["score_sha256"]}`。'
              '実行前と各バッチ前に、lockを含む46ファイルのcommit／作業内容、既存証拠64ファイル、旧lockの37ファイルを照合した。\n',
              f'凍結srcは `{lock["frozen_commit"]}`、Git treeは `{lock["source_git_tree"]}`、'
              f'source hashは `{lock["source_hash"]}`。元preflightと同じPython・依存バージョン、'
              '180秒・1コア・各BLAS/OMP thread=1・再帰上限10,000・外側watchdog188秒を確認した。'
              'CPUは `[7,15,10,14]` の独立した物理コア。実測した実行区間の最大重複は4、8バッチは全worker終了後に順次投入した。'
              f'最長バッチは{max(b["wall_seconds"] for b in summary["timing"]["batches"]):.3f}秒。'
              '共有機負荷まで過去と同じとは保証しない。\n',
              f'31件全ての保存記録を固定score.pyで再採点し、保存済み判定と一致した。'
              '一時solver出力を取得できた記録は実行source・入力hash・依存・CPU契約を照合し、違反はなかった。'
              '封印tar・封印生データにはアクセスしていない。'
              f'保存成果物の最大サイズは完了時点で{completion["max_file_bytes_before_this_receipt"]:,} byte。'
              '一時出力にもOSのファイル上限を継承させ、5MBを超えるファイルを作らなかった。\n',
              '**再現手順と成果物**\n',
              '外側の [execute_supplement.py](execute_supplement.py) を用意し、`prepare` の後に `batch 1` から `batch 8` を別コマンドで順番に実行した。'
              '`run_campaign_supplement.py run` は使っていない。spawn workerではHEREだけを `supplement-work/` に向け、'
              '元のinitialize_worker／worker／採点経路を使った。固定DSLは同一バイト列のコピーで、ROOT・RUNTIME・CORPUS・score参照先を維持した。\n',
              '```sh\nenv PYTHONDONTWRITEBYTECODE=1 /home/kabatan/work/solver/.venv/bin/python -B jssa/difficulty/unseen-1983/failure-audit/d/execute_supplement.py prepare\n'
              '# 続いて batch 1〜8 をそれぞれ別コマンドで順次実行（各番号は一度だけ）\n'
              'env PYTHONDONTWRITEBYTECODE=1 /home/kabatan/work/solver/.venv/bin/python -B jssa/difficulty/unseen-1983/failure-audit/d/execute_supplement.py batch 1\n'
              'env PYTHONDONTWRITEBYTECODE=1 /home/kabatan/work/solver/.venv/bin/python -B jssa/difficulty/unseen-1983/failure-audit/d/analyze_supplement.py\n```\n',
              '[全31件の結果・時刻・hash](supplement-work/results.csv)、'
              '[予測比較](supplement-work/prediction-comparisons.csv)、[補遺集計](supplement-work/summary.json)、'
              '[床演算再現](supplement-work/floor-reproduction.json)、[実行前照合](supplement-work/stage2-verification.json)、'
              '[開始manifest](supplement-work/campaign/execution-manifest.json)、[完了receipt](supplement-work/campaign/completion.json)。\n']
    appendix = "\n".join(parts).encode()
    updated = preamble.encode() + original + appendix
    assert len(updated) < 5_000_000
    (base / "answer.md").write_bytes(updated)
    assert updated[len(preamble.encode()):len(preamble.encode()) + len(original)] == original
    for rel, digest in {**lock["files_sha256"], **lock["evidence_files_sha256"]}.items():
        if outer.ROOT / rel != base / "answer.md":
            assert outer.sha(outer.ROOT / rel) == digest, rel
    files = [p for p in work.rglob("*") if p.is_file()]
    assert all(p.stat().st_size < 5_000_000 for p in files)
    outer.save_new(work / "report-verification.json", {
        "verified_at_utc": outer.now(), "answer_sha256": outer.sha(base / "answer.md"),
        "original_answer_sha256": hashlib.sha256(original).hexdigest(),
        "original_answer_body_preserved_verbatim": True,
        "permitted_answer_change": "new summary preamble and separate appendix only",
        "all_other_locked_and_evidence_files_unchanged": True,
        "prediction_lock_sha256": outer.sha(base / "prediction-supplement.lock.json"),
        "fixed_runner_sha256": outer.sha(base / "run_campaign_supplement.py"),
        "fixed_score_sha256": outer.sha(base / "score.py"),
        "report_script_sha256": outer.sha(__file__), "all_new_files_below_5000000_bytes": True,
    })
    print(json.dumps({"answer_bytes": len(updated), "main": main_count, "diagnostic": diagnostic}, ensure_ascii=False))


if __name__ == "__main__":
    main()
