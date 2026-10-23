# sol-3：未使用20問の予測（事前登録2 A）

対象は `../new2026/cases.jsonl` の20問。判定基準は
`../ghost-1023/preregistration-2.md` の A1・A2。本ディレクトリの
`run_predictions.py` は手順 (1)〜(3) と予測の固定までを実施し、
**p の集計・A1/A2 の判定 (4) は、ユーザー側の予測固定commitとorigin追跡refの一致を確認した後に実施した。**
この README は進行・検証の記録のため更新するが、固定後の `predictions.csv` は変更しない。

## 実行条件（結果を見る前に固定）

- Python は `/home/kabatan/work/solver/.venv/bin/python`。環境・依存関係は変更しない。
- `src/` は読み取りのみ。出力は本ディレクトリ内。最大4並列、BLAS等は各1スレッド。
- seed 5、各200出発点。`probe_basins.py` と同じ箱・乱数・局所探索・終点分類を使う。
  200点を途中で切らないため、全体の時間上限だけ86400秒とした。
  局所探索の `max_nfev` や残差・答えの許容誤差等は変更しない。
  200点に満たない場合は予測の固定前に停止する。
- raw は個々の出発点・終点・分類を保存するが、counts / hits_by_ref / p_any 等は作らない。
  予測作成コードは終点からは G の除外判定に必要な hit の座標だけを使う。
  hit の個数は予測CSVや特徴量に書かない。`has_hits` は sol-1 と同じく記録する。
- φ は保存した200出発点の hard feasibility を満たす割合。
  全出発点が `default_rng(5)` で再現され、保存済み `start_feasible` が評価器で再現されることを検証する。
- G は `ghost_exact.py` の `prepare_summary` / `solve_chunk` を再利用する。
  全 hit で常に一致する点対を除き、残る各点対について
  `default_rng([0,i,j])` の20出発点、元の等式＋座標差2行、LM、残差ノルム ≤ 1e-10。
  次元・ランク・中心差分・LM上限・0行追加・例外記録も sol-1 と同じ。
  `n_pairs_found > 0` を G=1 とする。`per-pair.csv` に証人と数値失敗を保存する。
- `inputs/model-1023.json` は元の固定係数ファイルのバイトコピー。
  full のロジットは intercept + n_vars 係数 + G係数×G + φ係数×φ、
  nvars_only は intercept + n_vars 係数。
  n_vars は1を基準、7以上を7にまとめる。モデルの再学習・特徴選択をしない。
- (4) で使う実測 p は hits/200、実測ロジットは
  `ln((hits+0.5)/(misses+0.5))`（0.5加算の平滑化オッズの対数）。
  固定モデルの target 欄の表記はこの意味に解釈する。
  A1 は full の予測ロジットと p の Spearman 順位相関 ≥ 0.4、
  A2 はロジットの二乗誤差の合計 full < nvars_only。両条件をそのまま報告する。

## 既存 jssa スクリプトへの最小修正

- `../probe_basins.py`：`load_case` の任意引数 `cases_path` と CLI `--cases` を追加し、
  JSONL を差し替え可能にした。`--defer-summary` を追加し、個票保存直後に終了して
  p・hit数の集計と表示を保留する。このモードでは失敗した出発点も `start` を保存する。
  オプション未指定の従来動作は維持する。
- `../ghost_exact.py`：`prepare_problem` / `prepare_summary` に任意引数 `raw_dir` を追加し、
  hit座標の読み込み先だけを差し替え可能にした。点対探索の実装・数値条件は変更しない。

## 実行と固定

リポジトリのルートから実行：

```bash
PYTHONDONTWRITEBYTECODE=1 /home/kabatan/work/solver/.venv/bin/python -u \
  jssa/difficulty/new2026-predict/run_predictions.py --workers 4 \
  > jssa/difficulty/new2026-predict/run.log 2>&1
```

`run-manifest.json` に開始時刻・条件・入力とコードのSHA-256を記録し、
`inputs/` にケース・固定モデル・事前登録をコピーする。
予測を書き出す直前に入力・コードが変更されていないことを検証する。
`predictions.csv` は排他的な新規作成で1度だけ書き出し、fsync 後にSHA-256と作成UTC時刻を
`predictions.sha256` に保存する。スクリプトは既存の予測CSVまたはハッシュがあれば起動を拒否する。
`freeze-manifest.json` は raw 全20ファイルと点対CSVのハッシュ、段階別所要時間を記録する。
予測が未作成の場合のみ、完了済み raw と問題単位のGチェックポイントから再開できる。

## commit・push 後の集計

ユーザーが予測を commit・push したと確認してから、その commit を指定して実行する：

```bash
PYTHONDONTWRITEBYTECODE=1 /home/kabatan/work/solver/.venv/bin/python \
  jssa/difficulty/new2026-predict/score_predictions.py --commit COMMIT_SHA
```

このコードは集計前に、記録ハッシュ・指定commit中の予測バイト列・現在の予測・raw・コード・入力の一致を検証する。
今回のpushの確認方法は、HEADとローカルのorigin追跡refの一致による。
`predictions.csv` は読み取り専用で扱い、末尾でも同一バイト列を確認する。
結果は `outcomes.csv` と `score.md` を排他的に新規作成する。
基準を満たさなければ「未使用問題では確認できなかった」と報告し、開発集合内の結果と区別する。
agent は git commit・push を行わない。

## 限界・実施記録

G は有限20出発点の数値探索であり、代数的な存在・不存在の証明ではない。
点の座標が評価できない場合やLMの失敗、数値ランク欠測も元の sol-1 の規則どおり記録する。
チェックポイントの JSON は Python の `Infinity` を許す（全試行失敗の best_res）；
最終CSVでは元の sol-1 同様 `inf` と記録する。失敗を隠すために式や対象点対を変えない。
`per-pair.csv` は `solve_pair` の返り値をそのまま保存するため、found=1 かつ dim=-1 は
全成功点でランク計算が失敗した欠測を意味する（n_rank_failed も参照）。
G は dim でなく found のみから判定する。

予測固定後は `verify_predictions.py` で、固定ハッシュ、20問のID、全4,000出発点の件数、
φと固定係数からの予測式、Gの集約、有限 best_x の残差、存在する dim_x の中心差分ランクと
特異値を再検証する。検証結果は `verification.json`。この検証も p は集計しない。

## 実施結果・所要時間

- 開始 UTC：2026-10-23T06:48:22.976093+00:00（15:48:22 JST）。
- 予測固定 UTC：2026-10-23T07:06:00.132556+00:00（16:06:00 JST）。
- 実験 wall time 1,057.156秒（17分37秒）。probe 250.921秒、G 806.222秒。
  実装・手順確認は別途約4分。検証1.547秒、集計コマンド約0.74秒。
- 指定Python、最大4並列で一度の本計測を完了。中断・再開・条件変更なし。
  依存関係のインストール、src/の変更、agentによるcommit・pushなし。
- 全20問で各200出発点を保存。Gは456点対×20出発点＝9,120試行。
  29点対（2問）で残差基準を満たした。φと両固定モデルの予測を20行のCSVに保存。
- 予測SHA-256：`68c2009f158ee181b5b6ad3b8e13c851c42cd3f135ea12d14e0280d2c652b5d0`。
  作成時刻とともに `predictions.sha256` に記録。
- ユーザー側の予測固定commit：`8930f5d00bbd50b1a6b80bdb0d1630fea001cb3c`
  （commit時刻16:07:01 JST）。集計前にHEADおよび
  `refs/remotes/origin/claude/project-thread-9bdbbg` がこのcommitと一致することを確認した。
  agentはcommit・pushを実行していない。指定commitの予測バイト列、現在の予測、固定ハッシュの一致を確認してから
  初めてpを集計した（07:08:57 UTC / 16:08:57 JST）。
- A1成立：full予測とpのSpearman順位相関 **0.791229037885 ≥ 0.4**。
- A2成立：ロジット二乗誤差の合計 **full 125.602487409 < nvars_only 161.971228243**。
  事前登録Aの両基準を満たした。20問の結果であり、個々の予測が正確だという主張ではない。
  問題別の実測と誤差は `outcomes.csv`、判定は `score.md`。
- 検証成功：20行の特徴量・固定式・ハッシュ、有限な残差証人449個、ランク証人29個の
  中心差分と特異値が一致。集計後も予測CSVは固定commitとバイト単位で一致した。
  さらにrawとoutcomesの全20行を照合し、平均順位によるSpearmanと二乗誤差を独立に再計算して一致した。

### うまくいかなかった点・数値的限界

- Gの9,120試行のうち141試行は `Residuals are not finite in the initial point` の
  ValueError、1,268試行はmax_nfevに到達した。数値ランク計算の失敗は0。
  評価上限停止でも残差基準を満たせば、元のsol-1と同じく found とする。
- GEO-08の `bis = AngleBisector(B, A, C)` は直線だが、指定された
  `ghost_scan.point_names` は点候補に含める。その `bis` を含む7点対は全20試行が非有限残差で失敗した。
  規則を変えず、そのまま n_pairs_all_failed=7 と記録した。
  このため G=0 を退化解不存在の証明とは扱わない。
- GUTS-18、JMO-PRE-03では200出発点のhitが0だった。Gの点対除外はなし。
  結果を見てDSL・探索条件・予測・モデルを変更していない。
- GEO-05は10変数で、probeに243.9秒を要した。予測係数は登録済みの「7変数以上」を適用。
- 出力全体は約2 MB、最大の単一ファイルは約107 KB。大容量ファイルは作成していない。
