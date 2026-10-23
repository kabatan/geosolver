# Q3 一歩診断 W：再現とファイル対応

結論は [answer.md](answer.md)。全292問は開発群であり、結果は探索的。
未使用問題向けの固定文は [preregistration-unseen.md](preregistration-unseen.md)。
Q2へのW計算・局所探索は実行していない。

## 実行環境

- Python `/home/kabatan/work/solver/.venv/bin/python`、3.12.11。
- NumPy 2.5.1、SciPy 1.18.0。既存環境を使用、pip/installなし。
- `PYTHONPATH=src`、Python `-B`、BLAS/OpenMP各1スレッド、最大4 worker。
- `src/` と既存ファイルへの編集なし。Nは各worker内の一時的monkeypatchだけ。
- 全出力を本フォルダに限定。個々のファイルを20MB未満に分割。
- git commit/pushなし。元実験の未追跡ファイルや他担当の成果物には触れない。

## 実行順

repo rootで実行したコマンド（それぞれ前の完了後）。既存freezeは上書き不可。
現在の成果物を検算する場合はverifyとanalyze_exactを使う。
当初のanalyzeは保存済みの訂正前集計を再現するために残している。

```bash
env PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 /home/kabatan/work/solver/.venv/bin/python -B jssa/difficulty/wall-diagnostic/verify_math.py
env PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 /home/kabatan/work/solver/.venv/bin/python -B jssa/difficulty/wall-diagnostic/experiment.py freeze
env PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 /home/kabatan/work/solver/.venv/bin/python -B jssa/difficulty/wall-diagnostic/experiment.py diagnose --workers 4
env PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 /home/kabatan/work/solver/.venv/bin/python -B jssa/difficulty/wall-diagnostic/analyze.py --diagnostics-only
env PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 /home/kabatan/work/solver/.venv/bin/python -B jssa/difficulty/wall-diagnostic/experiment.py paired --workers 4
env PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 /home/kabatan/work/solver/.venv/bin/python -B jssa/difficulty/wall-diagnostic/experiment.py verify
env PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 /home/kabatan/work/solver/.venv/bin/python -B jssa/difficulty/wall-diagnostic/analyze_exact.py
```

diagnose/pairedは既にある問題別JSONを飛ばすため、途中再開にも使える。
全て揃った後に再び呼ぶとrun.jsonの実行時間記録は今回呼び出し分になるので、
完成した成果物でこれらのphaseを再実行する必要はない。

## 定義上の注意

Wの残差は等式ベクトルと元の10倍guard行で、hard行だけを除く。
λ=1e-3と列ノルム尺度を固定した減衰最小二乗方向を一度だけ計算し、
9段階のαのうち箱内で1%以上下がる最初の点のhard判定を調べる。
本物のMINPACKの適応的な信頼領域・受理・停止の全過程を再現するものではない。
Gの失敗終点に基づくWや、64点から作ったQとは定義が違う。

公式答え・保存終点は特徴関数に渡さない。`read_case(scoring=False)` は
ID/DSLのみを返し、`diagnostic()` はrawの保存startも読み込まない。
箱はDSLから推定。`paired()` で保存箱と一致を確認する。
有限評価の判定では元実装の全行1e10への置換を有効残差として受け入れない。

局所比較は各問F/Iの先頭30保存始点までを用いる。`D_F` はFの10点以上、
`R_saved` は保存F/I各10点以上を要求。欠測や診断不能を0にしない。
`D_all` と選択方策のpは、このF/Iを各30点までに切った始点混合での値であり、
探索箱の自然な許容率で重み付けした成功確率ではない。
元55,097点の保存pと、新規11,445点のpを混ぜてB/N差を作らない。

Nの残差変更は探索中のみ。候補構築は元のhard/guardを評価し、採点時には
monkeypatchも復元済み。各呼び出しは元のdeadlineに加えPOSIXの5秒timerを使い、
局所呼び出しがtime outしても次の始点を残す。終了後の答え採点時間は実時間に含む。
保存Bは元の問題単位120秒予算、新規Bは各試行5秒なので、差を検算して報告する。

## 成果物

|ファイル|内容|
|---|---|
|preregistration.md|W・対象・介入・統計・未知群の規則。初回計算前に固定|
|freeze.json / manifest.json|凍結時刻・全src/コードのハッシュ、292問のDSL/rawハッシュ|
|before-local.json|新しい局所探索前の採点入力・集計コード等の追加ハッシュ|
|registration-note.md|他担当によるQ1/Q2フォルダ同時作成の時刻差の説明|
|experiment.py|W測定、凍結照合、B/N実行。未使用問題の実行入口なし|
|verify_math.py / math-checks.json|解析解による方向・α・失敗処理・guard保持の検算|
|diagnostics/*.json|各問256点の入力・一歩・理由・残差・時間|
|paired/*.json|保存始点と同じ座標のB/N終点・分類・時間・status・差し替え呼び出し数|
|per-problem.csv / per-start.csv|結合済みの全問表／全始点の対応表|
|high-group.csv|高群13問を全件掲載した抜粋。Powellの少数Fは主解析欠測のまま|
|summary.json|相関、問題単位区間、群別成績、固定基準の成否|
|summary-interim.json / per-problem-interim.csv|W終了時、B/N実行前の暫定結果（保存）|
|interim-answer.md|B/N測定中に先に書いた暫定結論|
|baseline-disagreements.csv|保存Bと再実行Bの分類が異なる全件|
|outcome-counts.csv / transitions.csv|成功以外も含めた分類と救済/悪化の全内訳|
|diagnose-run.json / paired-run.json|開始/完了時刻、4並列の実時間、エラー|
|audit_delivery.py / delivery-audit.json|乱数再生・対応始点・分類・下降条件・相関の独立検算|
|analyze_exact.py / rounding-correction.md|当たり数から差を計算し、数学的同率を保つ訂正集計と説明|
|rounding-before/|訂正前の結果・回答。元のanalyze.pyは変更せず保存|

最終検算（新しい局所探索はしない）：

```bash
env PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 /home/kabatan/work/solver/.venv/bin/python -B jssa/difficulty/wall-diagnostic/audit_delivery.py
```

元の登録を変えず、W測定は2026-10-23 11:49:06〜11:51:01 UTC、
B/N測定は11:52:34〜12:04:17 UTCに完了。実時間はそれぞれ115秒と703秒。

## 一次資料で確認した範囲

[SciPy least_squares公式仕様](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.least_squares.html)
はLMのMINPACK実装、停止条件、bounds非対応を説明している。
今回のWは既知の減衰最小二乗に基づく代理指標で、LMの新アルゴリズムではない。

[NOMAD 4公式資料](https://nomad-4-user-guide.readthedocs.io/en/latest/GettingStarted.html)
はProgressive Barrierでの違反許容とExtreme Barrierでの違反点除外を区別する。
探索途中で違反を許すこと自体を新規性とは主張しない。
本担当は幾何ソルバー文献の網羅調査や既知の滑らかな処理との実験比較をしていない。
