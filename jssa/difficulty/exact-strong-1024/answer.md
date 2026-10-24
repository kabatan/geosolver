# 段階A：汎用規則による厳密法パイプライン

`run_strong.py`、`batch.sh`、`strong_translate.py` を作成した。Tへの消去、DSL由来の非零因子による飽和、三角定数の最小多項式化、DSL未知数0の直接評価を実装した。採用する代数計算経路はSingular 4.4.1。msolve 0.9.4も指定PATHで使用可能だが、この実装は呼ばない。

規則と命令別の表は [rules.md](rules.md)。元変換器を変更せず、問題別の式・パラメータ・座標を追加していない。求解入力から参照答えと問題文を除去している。[pipeline-freeze.json](pipeline-freeze.json) に5問実行前のコードハッシュを残した。凍結版は `/tmp/exstrong-clean` の60db4b679b04167175c51c479c87c22fa663fda0、実測source_hashは `sha256:d8fd9bb8392ad2984276bab3386e033669246ee79586317917c322d31b4541f5` で一致した。

## 開発用5問

| 問題 | 結果区分 | 確認した値 | 全体壁秒 | 代数計算秒 | 復元・検証秒 |
|---|---|---|---:|---:|---:|
| AIME-2005-I-01 | 変換不能 | なし | 0.403 | — | — |
| AIME-2012-I-14 | 答え集合を確認 | 375 | 0.502 | 0.011 | 0.078 |
| HMMT-2011-FEB-GUTS-01 | 一部確認・集合は未確定 | 1/3 | 0.903 | 0.014 | 0.413 |
| HMMT-2019-FEB-GUTS-17 | 一部確認・集合は未確定 | 4/5 + 22*sqrt(3)/15 | 363.888 | 85.737 | 276.645 |
| HMMT-2023-FEB-GUTS-03 | 答え集合を確認 | sqrt(21) | 0.703 | 0.011 | 0.309 |

AIME-2012は375、HMMT-2023は√21でposthoc-20の手処理と同じ答え集合を確認した。復元座標は過去の証人を使わず生成した。

HMMT-2011は1/3の図を検証でき、確認済み値は手処理と一致する。ただし消去候補5/3は自由座標の有限標本だけでは全配置を除外できず、未解決に残った。負の2候補は主値根号と矛盾して除外した。posthocの u=v=1/3 という人手の導出を追加しなかったため、答え集合の確定には至らない。

AIME-2005は目標が円面積のπを含み `NONALGEBRAIC_PI`。posthocで人手が行った K/π への目標変更はR3の範囲外なので行わず、300πには到達しなかった。

HMMT-2019の手処理は候補式までで、元々全候補の復元・絞込みは未完了だった。飽和済み式や過去の62次式は再利用していない。 今回は `verified_subset`。処理済みの候補は確認1、除外54、未解決7。 今回のDSLからTの消去式と辞書式基底を新規に計算できた。 未解決理由の記録：`verification_unresolved:verification_error:IRCompileError`。

手順・候補別の扱い・証人・時間は [dev5-results.md](dev5-results.md) と [JSON](dev5-results.json)。合成入力の11チェックも通過した（[smoke-checks.json](smoke-checks.json)）。さらに `x=cos(pi/7), T=x` の合成入力を全工程に通し、意図した根だけの確認を得た（[trig-pipeline-check.json](trig-pipeline-check.json)）。5問にDSL未知数0や一般の三角定数の例はないため、その経路は合成入力だけで確認した。開発外34問や開発群の一括実行・採点はしていない。既知5問の動作確認からsolver並みの能力とは結論しない。

## exp1固定変換器からの差分

| 項目 | exp1 | 今回 |
|---|---|---|
| 目標 | 通常のmsolve実行では未追加。別の消去経路でTを追加 | 常にTを追加し、先にTへ射影 |
| 非零条件 | 記録済み分母等を積にしてRabinowitsch変数を追加。既存等式の使用変数に限定 | 厳密不等式、直線・円・非退化・凸多角形等も記録。因子ごとにSingularで飽和 |
| 三角定数 | 根号置換、またはcosの最小多項式と単位円等式 | sin/cosそれぞれの最小多項式。復元時に数体上で意図した根を選択 |
| DSL未知数0 | 補助変数を含む代数系を求解し得る | 代数ソルバー呼出し0、凍結版で直接評価 |
| 正次元の図 | 消去候補を記録しても復元せず終了する経路あり | 辞書式基底から厳密に復元。自由座標は共通の有限有理標本、未確認候補は未解決 |
| 資源・成否 | 求解と検証に別々の時間枠を持つ経路あり | 全工程合計600秒、問ごと合計RSS8 GiB監視、再試行なし。完全・一部・未解決を区別 |

## 未対応と限界

π単体・円面積は変換不能（`NONALGEBRAIC_PI`）。非代数的定数、未対応命令、整数条件、Or/Notを含む条件、角度値の目標・未対応の角演算も理由付きで止まる。代数根の復元でSymPyが扱えない場合は未解決となる。未対応を問題ごとに救済しない。

飽和は不等式の正負・凸性・交点の実在を完全には表さない。判別式≠0を課すと接点を失うため、接続等式と元DSL検証を併用する。自由座標の5有理標本、最大4096節点では完全な実量化消去にならず、標本の失敗から不存在を推定しない。最終検証器自体も数値検証の契約に従う。

各子プロセスのアドレス空間を8 GiBに制限し、問ごとの子孫RSS合計も0.1秒間隔で監視する。合計RSS上限の検知には最大でその間隔の遅れがある。ファイル上限は2,900,000 byte。他タスクのプロセスには触れていない。システム導入、git commit、pushは行っていない。

## 実行方法

既存Python環境を利用する。新規導入は不要。checkoutが消えている環境では、リポジトリのルートで次のように作り直し、hashを確認する（同名checkoutがある場合は上書きしない）。

```bash
git clone --shared --no-checkout . /tmp/exstrong-clean
git -C /tmp/exstrong-clean checkout --detach 60db4b6
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/tmp/exstrong-clean/src \
  /home/kabatan/work/solver/.venv/bin/python -c \
  'from geosolver.runtime.integrity import source_tree_hash; print(source_tree_hash())'
```

1問の処理例。既存の試行台帳がある出力先は拒否するので、今回の `dev5-runs/` は再利用しない。

```bash
/home/kabatan/work/solver/.venv/bin/python \
  jssa/difficulty/exact-strong-1024/run_strong.py AIME-2012-I-14 \
  --out /tmp/exstrong-one-example/AIME-2012-I-14.json
```

以下は**段階Bで初めて実行するコマンド**であり、今回実行していない。リポジトリのルートで実行する。両群とも各1回・600秒・8 GiB・4並列で、別々の出力先になる。`--stage-b` は段階Aの5問制限を明示的に解除する。

```bash
OUT=jssa/difficulty/exact-strong-1024
PY=/home/kabatan/work/solver/.venv/bin/python
export PATH=/tmp/q6-tools/bin:$PATH
export PYTHONDONTWRITEBYTECODE=1

# 開発外34問（AとBのJSONLからIDだけを列挙）
"$PY" - <<'PY' > "$OUT/stage-b-34-ids.txt"
import json
from pathlib import Path
for group in 'ab':
    for line in Path(f'jssa/difficulty/unseen-2/{group}/cases.jsonl').read_text().splitlines():
        print(json.loads(line)['id'])
PY
bash "$OUT/batch.sh" "$OUT/stage-b-34" --stage-b \
  --cases jssa/difficulty/unseen-2/a/cases.jsonl \
  --cases jssa/difficulty/unseen-2/b/cases.jsonl < "$OUT/stage-b-34-ids.txt"

# 開発群323問
"$PY" - <<'PY' > "$OUT/stage-b-development-ids.txt"
import json
from pathlib import Path
for line in Path('benchmarks/cases.jsonl').read_text().splitlines():
    print(json.loads(line)['id'])
PY
bash "$OUT/batch.sh" "$OUT/stage-b-development" --stage-b \
  --cases benchmarks/cases.jsonl < "$OUT/stage-b-development-ids.txt"
```

段階Bは今回の5問を含む34問について別の新規実験として実施する手順である。今回の結果をそのまま再試行したり、失敗問だけ追加予算で救済したりしない。ID・参照値の集合比較による評価は実行器には含めていない。
