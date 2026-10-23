# sol-2: 3点の共線退化の独立探索

実行開始（UTC）: 2026-10-23T07:12:03.187772+00:00。
今回の実行 wall time: 2.298 秒（入力読込・チェックポイント検証・再計算・CSV最終整列まで）。
保持した正常完了: 251 問、今回再試行/新規処理: 41 問。
問題別secの合計: 32084.757 秒（保持分 32071.991 秒、今回分 12.767 秒）。
secは各問題の全chunkの処理時間の合計で、重複する座標前処理も含む。並列実行のwall timeやCPU時間とは異なる。
旧READMEの実行開始UTC: 2026-10-23T05:24:42.251211+00:00。旧READMEには初回wall time 4245.173秒の記録があるが、その後の再開・停止・待機を含む全セッションの実稼働wall timeは復元できない。旧開始UTCから現在までの経過を実稼働時間とは呼ばない。
Python: `/home/kabatan/work/solver/.venv/bin/python`、NumPy 2.5.1、SciPy 1.18.0。
今回のworker数: 6（BLASは各1 thread）、chunk-size: 40。

```bash
PYTHONDONTWRITEBYTECODE=1 /home/kabatan/work/solver/.venv/bin/python jssa/difficulty/ghost_exact_triple.py --workers 6 --chunk-size 40 --starts 20 --out jssa/difficulty/ghost-exact --resume
```

## 固定した手順

- 対象は `minima/basins-323.csv` の n_vars >= 1 の292問。問題番号は全行の0始まり位置。DSLは `benchmarks/cases.jsonl`。対象・閾値・乱数・出発点数を結果に応じて変えない。
- `ghost_scan.point_names` の返り値を辞書順に使用。一部の非点作図名も候補集合に残す。全候補名の座標を `construction_coordinates` / `answer_float` と比較し、相対誤差1e-9以下を検証する。検証には最初のhitと `default_rng(123456)` の20ランダム点を使う。座標を検証できない問題は `error` とし、名前や組を削除して通さない。
- raw-323 records の cls=hit だけを参照し、全正解図で abs(符号付き面積) < 1e-6 * 図の直径^2 の組を除外。正解図なしは除外なし、has_hits=0。非正解終点は参照しない。
- 12点超で適格組が200超なら `default_rng([1, 問題番号])` で非復元抽出200組。
- 各組(i,j,k)の `default_rng([0,i,j,k])` から探索箱 `infer_problem_bounds` 内の一様乱数20出発点。元の未正規化の等式Fに `(Q-P)×(R-P)/2` を1行追加。不等式・ガード・箱外罰則なし。LM自体は箱に制限されない。
- `least_squares(method='lm', ftol=xtol=gtol=1e-14, max_nfev=100*n_vars)`。m<nなら0行でパディング。評価不能/非有限の出発点はLM例外に数え、別解法に置換しない。成功しても全出発点を処理する。
- found=1は終点の拡張残差L2ノルム <= 1e-10。LM終了statusによらず残差で判定。best_resは返った終点の最小残差（全例外ならinf）。
- 成功終点で中心差分 h_j=1e-6*max(1,abs(u_j))、特異値が最大値の1e-8倍未満なら0。全特異値0ならrank=0。dim=n-rankの最大値と証人・特異値を保存。成功なしはdim=-1、次元評価失敗はn_rank_errors。
- scaleは図の直径/正解図直径の中央値。100超の終点を膨張として補助集計。正解図なしはnan。無限遠の解の存在検証ではない。
- chunkは負荷分散だけに使用。`--resume`はCSVの構造・組の一意性・出発点数・問題別集計の一致と座標検証済みを確認した完了問題を保持し、不整合・未完了・errorは問題単位で再試行する。

## 結果

- 処理済み問題数: 292 / 292、status: {'ok': 251, 'error': 41}。errorも処理済みだが探索成功とは数えない。
- 正常処理の has_hits=0: 22。
- 探索3点組: 8660、found組: 1625。
- G3=1の問題（found組が1以上）: 75、最大D3: 5。
- LM出発点: 173200、LM例外: 13806、max_nfev到達: 9307、次元評価例外: 8。
- 前処理等の失敗: 41問。下表は最終例外理由、完全なtracebackは `per-problem-triple.csv` のerror列。

| id | status | 理由 |
| --- | --- | --- |
| AIME-2006-I-07 | error | ValueError: no defined coordinate validation point: Areg |
| AIME-2006-II-12 | error | ValueError: no defined coordinate validation point: l1 |
| AIME-2013-II-08 | error | ValueError: no defined coordinate validation point: c20 |
| AIME-2015-I-06 | error | ValueError: no defined coordinate validation point: evecx |
| AIME-2019-I-15 | error | ValueError: no defined coordinate validation point: Q |
| AIME-2019-II-11 | error | ValueError: no defined coordinate validation point: K |
| AIME-2020-I-13 | error | ValueError: no defined coordinate validation point: L |
| AIME-2020-II-13 | error | ValueError: no defined coordinate validation point: l1 |
| AIME-2021-I-13 | error | ValueError: no defined coordinate validation point: B |
| AIME-2022-I-11 | error | ValueError: no defined coordinate validation point: r |
| AIME-2022-II-15 | error | ValueError: no defined coordinate validation point: r2 |
| AIME-2023-II-09 | error | ValueError: no defined coordinate validation point: L |
| AIME-2025-II-12 | error | ValueError: no defined coordinate validation point: theta |
| HMMT-2006-FEB-GEO-06 | error | ValueError: no defined coordinate validation point: L |
| HMMT-2007-FEB-GEO-08 | error | ValueError: no defined coordinate validation point: bc |
| HMMT-2008-FEB-GEO-02 | error | ValueError: no defined coordinate validation point: R |
| HMMT-2008-FEB-GEO-03 | error | ValueError: no defined coordinate validation point: L2 |
| HMMT-2008-FEB-GEO-07 | error | ValueError: no defined coordinate validation point: Kx |
| HMMT-2008-FEB-GEO-10 | error | ValueError: no defined coordinate validation point: ell |
| HMMT-2013-FEB-GEO-10 | error | ValueError: no defined coordinate validation point: Lbis |
| HMMT-2014-FEB-GEO-03 | error | ValueError: no defined coordinate validation point: external |
| HMMT-2014-FEB-GEO-10 | error | ValueError: no defined coordinate validation point: R |
| HMMT-2016-FEB-GEO-10 | error | ValueError: no defined coordinate validation point: BAx |
| HMMT-2017-FEB-GEO-05 | error | ValueError: no defined coordinate validation point: l1 |
| HMMT-2017-FEB-GEO-10 | error | ValueError: no defined coordinate validation point: l1 |
| HMMT-2018-FEB-GEO-05 | error | ValueError: no defined coordinate validation point: bis |
| HMMT-2020-FEB-GEO-07 | error | ValueError: no defined coordinate validation point: u |
| HMMT-2020-FEB-GEO-08 | error | ValueError: no defined coordinate validation point: bis |
| HMMT-2020-FEB-GEO-09 | error | ValueError: no defined coordinate validation point: q |
| HMMT-2024-FEB-GEO-03 | error | ValueError: no defined coordinate validation point: L |
| HMMT-2024-FEB-GEO-06 | error | ValueError: no defined coordinate validation point: r |
| HMMT-2025-FEB-GEO-04 | error | ValueError: no defined coordinate validation point: dn |
| JMO-2011-PRE-11 | error | ValueError: no defined coordinate validation point: l1 |
| JMO-2018-PRE-09 | error | ValueError: no defined coordinate validation point: exc |
| JMO-2020-PRE-11 | error | ValueError: no defined coordinate validation point: GammaA |
| JMO-2024-PRE-06 | error | ValueError: no defined coordinate validation point: F |
| JMO-2025-PRE-05 | error | ValueError: no defined coordinate validation point: l1 |
| aime-2000-2-10 | error | ValueError: no defined coordinate validation point: line_ab |
| aime-2001-1-4 | error | ValueError: no defined coordinate validation point: a_angle_bisector |
| aime-2002-1-10 | error | ValueError: no defined coordinate validation point: angle_bisector |
| aime-2003-1-15 | error | ValueError: no defined coordinate validation point: angle_bisector |

## 引き継ぎ時の不整合と修復

`/tmp/ghost-triple-resume.log` の最後は最終整列時の `int(None)` TypeErrorだった。
引き継ぎCSVを変更前に `.before-resume` へ保存した。問題CSVには正常な27列の292行に加え、26列の53行とNULバイトが混入。組CSVには完全一致する重複行があった。混入の発生原因は特定していない。
引き継いだコードは未検証座標をunavailable_pointsへ記録して処理を続けていたため、今回の指定に従い前処理失敗へ戻した。該当問題の旧okは保持せず再試行した。
不足するi,j,kに仮値を入れることはせず、構造不正行を隔離、完全一致する組行だけ重複除去し、問題別集計が一致した結果を保持した。不整合な問題は再試行対象にする。最終整列は検証済み整数キーを使う。

今回のチェックポイント検査件数: `{'per-problem-triple.csv:malformed_rows': 53, 'identical_duplicate_triples': 2092}`。
再試行対象として検出した既存問題: ['AIME-2006-I-07', 'AIME-2006-II-12', 'AIME-2013-II-08', 'AIME-2015-I-06', 'AIME-2019-I-15', 'AIME-2019-II-11', 'AIME-2020-I-13', 'AIME-2020-II-13', 'AIME-2021-I-13', 'AIME-2022-I-11', 'AIME-2022-II-15', 'AIME-2023-II-09', 'AIME-2025-II-12', 'HMMT-2006-FEB-GEO-06', 'HMMT-2007-FEB-GEO-08', 'HMMT-2008-FEB-GEO-02', 'HMMT-2008-FEB-GEO-03', 'HMMT-2008-FEB-GEO-07', 'HMMT-2008-FEB-GEO-10', 'HMMT-2013-FEB-GEO-10', 'HMMT-2014-FEB-GEO-03', 'HMMT-2014-FEB-GEO-10', 'HMMT-2016-FEB-GEO-10', 'HMMT-2017-FEB-GEO-05', 'HMMT-2017-FEB-GEO-10', 'HMMT-2018-FEB-GEO-05', 'HMMT-2020-FEB-GEO-07', 'HMMT-2020-FEB-GEO-08', 'HMMT-2020-FEB-GEO-09', 'HMMT-2024-FEB-GEO-03', 'HMMT-2024-FEB-GEO-06', 'HMMT-2025-FEB-GEO-04', 'JMO-2011-PRE-11', 'JMO-2018-PRE-09', 'JMO-2020-PRE-11', 'JMO-2024-PRE-06', 'JMO-2025-PRE-05', 'aime-2000-2-10', 'aime-2001-1-4', 'aime-2002-1-10', 'aime-2003-1-15']。
別ディレクトリから取り込んだ完了問題: []。

## 出力と限界

- `per-triple.csv`: 組ごとの結果、成功・例外・打ち切り件数、証人、尺度。
- `per-problem-triple.csv`: 問題ごとの集計、除外・標本化・座標検証・所要時間、error理由。
- `README-triple.md`: 手順、集計、実行時間、修復履歴。

sol-2は符号付き面積0を探索するため、3点共線（点の一致も含む）が対象であり、3点すべての同一点への一致だけを数えた実験ではない。
有限回の局所探索なのでfound=0は不存在の証明ではない。found=1も1e-10の数値判定であり代数的厳密証明ではない。n-rankは特異点で真の次元を過大評価しうる。ガード違反や箱外の証人も含む。status=okは処理完了を意味し、各出発点の収束を保証しない。error問題のG3/D3は未測定。H1〜H4の予測検定は実施していない。

入力とコードの SHA-256:

- `benchmarks/cases.jsonl`: `c5f92269783add80779a38b4159f298b7f49300386bca0008bb02d3c82d3fccb`
- `jssa/difficulty/minima/basins-323.csv`: `2b240b15e67903c3d161a736a4bf766aa2b282bcbb42742bcaec2ec917f46420`
- `jssa/difficulty/ghost-1023/preregistration.md`: `4d9b4676e45145c7ed3cc1f181f9911bb39e374d06f1c1512f3e131f8280a60a`
- `jssa/difficulty/ghost_exact_triple.py`: `e05e309a5cbd596c4e2e63462aac7a54722cd4115d72c53ca4853b941e122d32`

## 最終検証

再開コマンドはCSVとREADMEの最終出力まで完了した。終了コードは1（41問がerrorのための仕様どおりの終了値）で、最終整列の例外はない。実行ログは `resume-triple.log`。

検証スクリプトで以下を確認済み:

- 対象292 IDを過不足なく1行ずつ出力し、statusはok=251/error=41。
- CSVの全行の列数・欠損値・NULバイト・整列・組キーの一意性を検査し、すべて合格。
- 全問題で組数・found数・出発点数・LM例外・打ち切り・ランク例外・nfev・膨張件数が組CSVと一致。点名とi,j,kの対応、20出発点、残差によるfound判定も一致。
- 保持した251問の問題別結果は変更前のCSVと全列完全一致。41 error問題はいずれも座標検証失敗で、今回のLM実行数は0。これらをfound=0の測定結果とは解釈しない。
- None/空文字/非整数の整列キーを明示的なValueErrorとして検出する回帰チェック、および列数不足行を隔離するチェックが合格。

この作業では指定venvを使用し、依存関係のインストール、src/の変更、commit/pushは行っていない。変更前バックアップ、実行ログを含む書き込み先は `jssa/difficulty/ghost-exact/` と `jssa/difficulty/ghost_exact_triple.py` のみ。
