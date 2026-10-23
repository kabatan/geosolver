Q22a 保存図からの隠れた一致：実行・成果物案内

判定と候補(a)〜(h)は[answer.md](answer.md)。固定した代理特徴は人間難度のLOYO誤差を改善しなかった。公式解答の最短推論深さは未測定であり、数値候補を定理と呼ばない。

| ファイル | 内容 |
|---|---|
| [preregistration.md](preregistration.md) | 数値列挙前に固定した対象・語彙・閾値・評価・予言 |
| [registration-lock.json](registration-lock.json) | 実験コード、事前登録、元入力、src、保存終点の382ファイルのSHA-256 |
| [manifest.json](manifest.json) | 対象131問、年度、LOYOのfold |
| [experiment.py](experiment.py) | 保存hit再検査、数値列挙、明示関係除去、摂動、固定評価 |
| [features.json](features.json) / [features.csv](features.csv) | 全131問の特徴とstatus。欠測10問も残す |
| [figures/](figures/) | 各問の再検査、座標、作図深さ、明示関係抽出、候補の対象名・誤差・摂動判定 |
| [loyo-predictions.csv](loyo-predictions.csv) | 座標を得た121問での人間難度比較。fold外予測と二乗誤差 |
| [loyo-baseline-all.csv](loyo-baseline-all.csv) | 全131問の構造基準。主比較の分母とは別 |
| [loyo-local-difficulty.csv](loyo-local-difficulty.csv) | 保存された探索の難度Dを対象とする99問の比較 |
| [summary.json](summary.json) | 主結果、副次結果、感度分析、除外、P1〜P4の判定 |
| [primitive-validation.json](primitive-validation.json) | 各幾何述語の正負の基本例と変換不変性チェックの記録 |
| [run-metadata.json](run-metadata.json) / [run.log](run.log) | 図の再評価・列挙・摂動の計測約13.96秒（LOYO集計等を除く）、新規局所探索0回、環境情報、問題別進行記録 |
| [audit.py](audit.py) / [audit-results.json](audit-results.json) | 結果取得後に書いた独立検算・事前指定2例の内容監査 |
| [content-audit.svg](content-audit.svg) / [content-audit.png](content-audit.png) | 保存座標から作成した2例の図。B7だけは公式解答から事後的に追加 |
| [sources.md](sources.md) | 確認した文献・一次資料・既存結果と、未確認の範囲 |

**再実行。** リポジトリのルートから次を実行する。Pythonは指定された既存環境を使う。インストールは不要。数値ライブラリは1スレッド、1プロセスで動く。srcへの書き込み・新規局所探索・精密化は行わない。出力はこのディレクトリ内に限る。主実験の再実行はfeatures、各予測、summary、計測時刻などを上書きするため、最初の記録を保持する場合は事前にこのディレクトリ全体を複製する。

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  /home/kabatan/work/solver/.venv/bin/python \
  jssa/strategy/astra-consult-18/q22a-hidden-coincidence/experiment.py
```

registerモードは2026-10-23 13:44:32 UTCに実行済み。再実行時に登録を作り直して整合性を装わない。通常の実行は登録ハッシュが変わっていれば停止する。evaluate/analyzeに相当する処理は全てここに置き、元のsolverは変更していない。保存候補を生成せず特徴表から固定評価だけ再計算する場合のモード名はanalyze。

主結果を変更せず、保存CSV・候補の整合性と2例を検算するには次を実行する。図は標準SVGとして生成する。指定Python環境にはmatplotlibが無いため、追加導入せず標準ライブラリで座標図を記述した。

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  /home/kabatan/work/solver/.venv/bin/python \
  jssa/strategy/astra-consult-18/q22a-hidden-coincidence/audit.py
```

PNGは既存のImageMagick/InkscapeでSVGを描画し、目視確認した。監査コードはSVGとaudit-results.jsonを更新するが、登録コード・features・予測・summaryは変えない。共円の外心検算は陽性候補の別計算であり、数値誤差を伴う。HMMTの相似は空間索引を使わない全対比較でも同じ集合になった。意味上の隠れた定理の全数監査ではない。

**読み方の注意。** hidden列は指定した構文的除去の残りであり、公式原文に無いことを保証しない。depthは作図DAGの深さであり、推論深さではない。solution_dependentは作図変数の摂動で破れた数値関係であり、重要な定理と同義ではない。変数0の22問ではpと摂動対照は未定義。B_Cの当該特徴は実装上0を置いているため、これを「解に依存する関係が無い」と解釈しない。

人間難度は既存Easy2Hard由来のhuman列で、個々人の発見時間を測っていない。LOYO分割は新規列挙前に固定したが、131問そのものは既知の開発集合である。相談5の0.80/0.70を得た元手順は未確認。主結果の否定は、固定した数値一致の代理特徴についてであり、人間の証明深さに関する普遍的否定ではない。
