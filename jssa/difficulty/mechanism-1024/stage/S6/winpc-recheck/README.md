# S6の「負荷の確認」：WinPC(WSL)で同じseedを再実行する依頼

主表（事前登録13の判定）は元の実行（スーパーPC、共有機のload1が平均 4.77e+1、最大 8.53e+1）のまま。ここは負荷の影響を見る別の確認で、判定には使わない。

## 対象（recheck-list.csv、18の(問題, seed)）
- T1とT2で正誤が分かれた実行：AIME-2018-II-14、JMO-2013-PRE-05、JMO-2014-PRE-01、JMO-2024-PRE-06（各 seed 501〜503、T2が成功・T1が180秒打切り）、HMMT-2023-FEB-GEO-07（seed 502・503：T1成功・T2失敗）。
- 170秒を超えた実行：上記のほか HMMT-2016-FEB-GEO-10（seed 502、両方）、HMMT-2026-FEB-GEO-09（seed 503、両方）、JMO-2015-PRE-02（seed 502、T1）、HMMT-2023-FEB-GEO-07（seed 501、T1）。
- 各行で T2 と T1 の両構成を、同じseedで再実行する（問題×seed×構成＝36ジョブ）。

## 手順
1. ソース：S3実装（source_hash sha256:add5afaf829806ca3cbd11fb07b69d956102752e1c6738b0630581a3ceb121eb）。凍結版60db4b6に、既存patch（jssa-ablation-67ad79a）、`../../switches/new-switches.patch`、`../../S3/switch.patch` をこの順に当てる。順序・手順の詳細とハッシュは `../../S8/patches/`、`../../S8/run-on-winpc.md`（S8準備で作成中のものと共通）を参照。当てた後の source_hash が上の値と一致することを確認する。
2. 環境：`PYTHONPATH=<そのsrc>`、`PYTHONDONTWRITEBYTECODE=1`、`OMP_NUM_THREADS=OPENBLAS_NUM_THREADS=MKL_NUM_THREADS=NUMEXPR_NUM_THREADS=VECLIB_MAXIMUM_THREADS=BLIS_NUM_THREADS=OMP_THREAD_LIMIT=1`。T2は `GEOSOLVER_S3_TANGENCY_MODE` 未設定、T1は `GEOSOLVER_S3_TANGENCY_MODE=T1`。`GEOSOLVER_ABLATE_*` は全て未設定。
3. 実行：`geosolver.application.cli:solve`、`--time-limit-seconds 180 --cores 1 --seed <seed>`、1ジョブ1コア固定（taskset）。元の実行の `../run/driver.py` と `../run/grade.py`、`../run/references.json` をそのまま使い、対象をこの18行に絞る。採点は元と同じ。再試行しない。
4. 記録：各ジョブの開始時の1分load average、wall time、答え集合、正誤。時間は参考値。
5. 並列：WinPCの空きコアに合わせ、最大でもコア数−2。同じseedの T2/T1 は同時刻に近づけて走らせる。

元の実行の入力ハッシュは `../run/` の freeze.json / receipts、元の結果は `../run/per-run.csv`。
