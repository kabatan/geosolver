# sol-5: 誤差の単調変換（40問）

## 実行前の固定事項

- 判定基準: `../ghost-1023/preregistration-3.md`。対象は同フォルダの `transform-targets.csv` 全40問（L/H各20問）。T1: Lの差の中央値 ≥ 0.10、T2: Hの差の中央値の絶対値 ≤ 0.03、T3: 救済出発点の初期hard違反率 ≥ 0.80。T1またはT2が外れたら指定の機構を主張しない。
- 対象IDを文字列でソートし、0始まりの順位 `target_rank` を固定。共通64出発点は `default_rng([3, target_rank])`、探索箱内一様。対象CSVの群別行順を乱数の順位には使わない。
- `a` は astra-B と同じ `default_rng([102312, feature_index])` の別16点の有効な拡張残差ノルムの中央値、下限1e-6。`feature_index` は `basins-323.csv` の n_vars>=1 全292問をID順にした0始まりの順位。既存featuresにaがある38問では一致を本実験前に確認する。AIME-2013-II-04、HMMT-2006-FEB-GEO-03はastra-Bのfeaturesでは等式数<変数数で除外されaがないため、同じ方法で計算する。指定対象から除外しない（guard/hardの2行を含む拡張残差はLMの行数条件を満たす）。
- astra-B `experiment.py` を読み取り専用でimportし、`context`, `vector_function`, `valid_call`, `norm`, `radial`, `solve` を直接使用。変換は base: R、sharpen: (1+||R||²/a²)R。
- LM: 各条件を出発点から直接上限320で実行。ftol=xtol=gtol=1e-14、method=lm、1実行30秒（astra-Bと同じ協調的deadline）。80からの結果の流用はしない。
- 採点: 元の等式残差<=1e-8、guard、hard feasibility、元の箱、答えの相対許容1e-6（astra-B solve）。初期hard feasibilityは元のevaluatorで別途記録。
- timeout / error / missing_answer / missing は欠測として区別し、成功・失敗にしない。既存solveのwrong_answerで答え値が取得不能な場合のみmissing_answerとして明示（original_clsも保存）。上限320到達自体は時間切れではなく、得られた終点を元の基準で採点。
- 問題の率は観測できた実行のhits/observedと、計画64点を分母にした欠測込みの上下限を記録。主T1/T2は全40問の64対が揃う場合のみ計算。T3の救済はbaseが観測された非hitかつsharpenがhitの対。欠測を非hitとみなさない。救済点に初期hard欠測があればT3は判定不能。
- 本実験前に astra-B のreplication 2問（各100点、seed [102317, feature_index]、base/sharpen、上限320）を再実行し、出発点・a・各点の分類が保存結果に一致することを確認。再現失敗時は本実験を開始しない。
- 最大4ワーカープロセス、BLAS/OMP各1スレッド。Pythonは指定の既存環境、`-B`使用。書き込みはこのフォルダだけ。依存追加、src変更、commit/pushはしない。

## コマンド

repoルートで:

```
/home/kabatan/work/solver/.venv/bin/python -B jssa/difficulty/transform-check/run.py prepare
/home/kabatan/work/solver/.venv/bin/python -B jssa/difficulty/transform-check/run.py run
/home/kabatan/work/solver/.venv/bin/python -B jssa/difficulty/transform-check/run.py summarize
```

`prepare` は入力・コードのSHA256、環境、順位、較正16点、共通64点をmanifest/calibrationに保存し、再現を確認する。`run` はmanifestのハッシュと再現確認を検証して各問のraw JSONを保存する。`summarize` はrawからCSVとscore.mdを再生成する。既存rawがあれば実験を上書きせず検証して再利用する。

所要時間・欠測・判定は実行後の `score.md` を参照。raw JSONは各点の元の終点、分類、残差、採点条件、評価回数、エラーを含む。CSVの空欄は欠測または該当なしであり、0やFalseではない。

初回prepareは、既存featuresに全40問のaがあるという事前チェックの仮定が誤り、3問目の較正時に停止した（最適化前、manifest固定前）。上記2問の扱いを明記しチェックを修正してから再実行した。元のログは`prepare-initial.log`に保存。変換・較正法・対象・乱数・判定基準の変更はない。
