# 数値RLの時間・学習信号・実更新の有限検査

2026-09-30。Qwen3.5-9B、RTX 5090 32GB。結論は、**非ゼロの学習信号は存在し、長い回答の全文更新も実行できる。ただし、現設定をそのまま数千問へ拡大する根拠は不足する**。主な未解決点は、数値報酬と幾何能力のずれ、および学習側と生成側の更新反映の不一致である。生成時間も小さくない。

この有限検査は完了した。本格的なRLキャンペーン、継続更新の安定性検証、未教授の幾何的性質・証明への転移評価は実施していない。以下の「実更新成功」は、研究目的の達成を意味しない。

## 研究意図と検査範囲

研究目的は、対象の幾何的性質や解法を知らずに作れる経験から重みを学習し、モデル自身が直接教えていない幾何的能力を獲得すること。別問題の妥当な数値解法や、同構図の未教授の一般証明への転移が対象になる。solverの成功、数値の近似適合、訓練問題への再回答を、その転移成功へ置き換えない。正しい座標計算や適用可能な既知の性質は認め、既知の性質の再証明や新定理発見を一律には要求しない。

旧数値SFTの否定的結果から、データ量・構図の多様性不足はまだ排除できない。最大448行でも7構図であり、数千の多様な問題を学習した結果ではない。旧4B RLも40群・160回答・9更新だった。旧ログを再集計すると、自然終了した全回答で正誤が混在する群は13/40、打切りを含めた見かけの混在群は18/40だった。生成は3,260,458 tokens・4.391時間、9学習実行の合計は718.14秒・約12分。この小規模結果でRL全般や研究方針を否定することはできない。

今回の12問は、7問の独立作図検証済みの連続数値問題と、5問の整数・分数問題からなる。構図は計9種。目的に沿って選んだ小標本であり、母集団の成功率・混在率の推定ではない。二つの層は問題と形状も異なるため、「簡単な数値表現にした効果」を因果的に比較できない。

## 事前固定と実行

モデルrevisionは `c202236235762e1c871ad0ccb60c8ee5ba337b9a`。各問4回答、temperature=1、top_p=1、top_k=-1、presence penalty=0、thinking無効。正解・目標定理・解法は生成プロンプトに入れていない。数値正答は絶対誤差1e-4または相対誤差1e-5で判定し、GPU生成前に固定した。

初回completion上限16384、context上限40960。1件でも打切りなら、その問題の4回答を上限32768で新規生成した。途中の続きを生成したり、正答だけを残したりしていない。打切りを不正解として更新に使っていない。最終版48回答は全件自然終了・数値抽出可能だった。置換された初回回答も保存している。

更新対象は、最終自然終了の混在群のうち総completion tokensが最小・最大の2群。数学評定や期待改善で選んでいない。同じbaseから独立に1更新ずつ行った。最小は整数H04、最大は連続H07だった。

元のプロトコル・実装は保持した。失敗後の追加検査は別ソース・別receiptと事前のamendmentとして記録し、元の失敗を成功に書き換えていない。主要な記録は末尾にリンクする。

## 学習信号の量と意味

| 層 | 問題／回答 | 数値報酬1 | 正誤混在群 | 正例に完成した妥当な幾何経路 | その経路と最終算術がともに妥当 |
|---|---:|---:|---:|---:|---:|
| 連続数値 | 7／28 | 8 | 3 | 7 | 0 |
| 整数・分数 | 5／20 | 8 | 3 | 6 | 6 |
| 合計 | 12／48 | 16 | 6 | 13 | 6 |

6/12群、24回答に非ゼロadvantageがある。残りは全正答2群・全不正解4群で、今回のreward−群平均ではadvantageが0になる。50%という混在率はこの選択標本の記述値である。

数値正例16件と、混在群の不正例16件、計32件・609,514文字を全文レビューした。全不正解群の不正例はこの数学レビューの対象に含まれない。評定は親AIによる非盲検であり、独立した人間査読ではない。評定は報酬・群選択・勾配には反映していない。途中に誤った探索があっても、外部から修理せずに完成した独立の妥当な経路があれば認めた。「13件の幾何経路が妥当」は「13全文が無誤謬」という意味ではない。

| 混在群 | 報酬（4回答） | 完成した妥当な幾何経路 | 信号の評価 |
|---|---|---|---|
| 連続H04 | 0,1,1,0 | ×,○,○,× | 正しい一般導出と誤った射影・垂心処理を区別する。ただし正例の最終小数計算も不整合 |
| 連続H07 | 0,0,0,1 | ○,○,○,○ | 全員が正しい一般面積式に到達。報酬差は算術だけで、正しい幾何を含む3回答にも負advantage |
| 連続DA05 | 0,1,0,0 | ×,×,×,× | 正例も核心関係を推測している。妥当な幾何正例を強化する群とは言えない |
| 整数H04 | 0,1,0,0 | ×,○,×,× | 一般導出・厳密解と、符号誤り・推測を区別する |
| 整数DA01 | 1,0,1,0 | ○,×,×,× | 妥当な正例を含むが、もう一つの正例には核心の角関係の誤りが残る |
| 整数DA07 | 0,0,1,0 | ×,×,×,× | 正例も根拠のない対称性・長さの推測から数値に到達 |

H04の二つの群は同じ構図であり、独立した2構図の成功ではない。整数DA01は別構図の有用な正例を含むものの、報酬の品質が混在する。

連続H07の正しい式は、面積 `AB·MF·(1−AB²/(4ON²))`。4回答とも到達するが、小数計算だけで報酬が分かれた。連続H01も全4回答が一般式 `AP=|AM−BC²/(4AM)|` を導く一方、最終算術は厳密には不整合で、許容差内のため全正答になる。整数H01は全4件で一般導出と厳密解が妥当だが、全正答なので相対信号が消える。

整数DA01の第3回答は、正しい相似や長さ関係をかなり含む。しかし繰り返し用いたTでの角の向きが誤り、完成した正しい証明経路とは保守的に認めなかった。単なる当て推量と同一の質ではなく、評定境界にも感度がある。個別根拠は `math-review.json` に保存した。

したがって、**信号が全く出ないという懸念は否定できるが、「その信号が狙う幾何能力を十分に強化する」という懸念は残る**。許容差を広げれば正しい幾何の算術落ちは減り得るが、推測正答も増えるため、単なる閾値変更は解決とは言えない。

## 全文更新の実測と失敗

LoRA r8/alpha16/dropout0、attention・linear attention・MLPの計10target modules、20,054,016学習パラメータ。BF16 base、FP32 LoRA、lr5e-6、gradient clip1、AdamW。全4回答の因果文脈とcompletionを保持した。LM headはfull vocabularyのまま64tokenずつ計算し、gradient checkpointとCPU activation offloadを使用した。学習系列を1024tokensに切っていない。

元実装は生成／learnerの更新前token log-probability差について、平均絶対差≤.02・最大絶対差≤.2を事前要求した。最小群は最大差.3740、最大群は.2470で失敗し、いずれも逆伝播前に停止した。**元プロトコルの実更新は0回、fidelity gateは不合格のまま**である。

その後、別の追加プロトコルで、既存のtoken importance sampling correction（TIS、上限2）を使って実更新の時間・メモリを確認した。重みは `exp(learner_old.detach−sampled_actor_logp)` を上限2で打ち切る。通常のclipped objectiveにdetached重みを掛け、ratioの基準は更新前learnerとした。閾値を緩めた原検査の再試行ではない。これはtoken単位のsurrogate補正であり、系列prefix全体の厳密なimportance correctionでも、backend差の解消でもない。TISを用いる前に、正負advantageの閉形式勾配とfull vocabulary headのFP32/BF16勾配をCPUで検証した。[TRLのGRPO資料](https://huggingface.co/docs/trl/v0.27.1/en/grpo_trainer)にも生成backendとの差に対するimportance補正が記載されているが、今回の長期安定性を保証するものではない。

| 追加TIS実更新 | 最小：整数H04 | 最大：連続H07 |
|---|---:|---:|
| 全4回答completion tokens | 32,610 | 42,593 |
| forward/backward | 47.60秒 | 70.82秒 |
| optimizer | 0.088秒 | 0.065秒 |
| loading | 2.07秒 | 2.12秒 |
| 保存・tensor再読込照合 | 0.322秒 | 0.322秒 |
| worker全体 | 54.09秒 | 77.66秒 |
| peak GPU allocated | 23.98 GiB | 25.12 GiB |
| peak GPU reserved | 24.34 GiB | 25.54 GiB |
| gradient norm | .03576 | .02905 |
| 実optimizer step | 1 | 1 |

両群とも有限・非ゼロ勾配、400 LoRA tensors中200の変化、400全件の保存値一致、optimizer再読込step=1、vLLM形式へのmappingのtensor値一致を確認した。最初のB=0 LoRA stepではB側200 tensorsが変わり、A側200が不変なのは期待される。TIS重みの上限打切りは今回0件、相対ESSは約.9994–.9995。これらは全文更新の実行可能性の証拠である。幾何能力改善や転移の証拠にはならない。特に最大群H07は算術だけの信号であり、時間検査のために更新した。

## 生成側への反映と数値精度

最小群の保存adapterをvLLMに読み込み、同一engineで未装着base・B=0 LoRA対照・更新LoRAを比較した。4回答×1024 completion tokensの固定prefixをteacher forcingした。prefixは接続検査用で、全文学習の代わりではない。

B=0 LoRAと未装着baseは一致し、更新LoRAによるlog-probabilityの変化は観測された。しかしHF learnerとvLLM actorの**更新前後の差分**のcosineは.0416で、方向の一致は弱かった。保存・読み込み・mappingの照合を通っても、期待した更新が生成側の確率へ忠実に反映するとは確認できない。

同じBF16学習済みadapterを使い、base計算とactor LoRA計算をFP16にした追加固定prefix検査も実施した。新規生成・新規更新は0件で、問題・報酬・保存重みを変えていない。

| 固定4096tokensの比較 | BF16 | FP16追加診断 |
|---|---:|---:|
| 更新前backend差：平均絶対logp差 | .00722 | .000908 |
| 更新前backend差：最大絶対logp差 | .21291 | .03694 |
| actor更新差分：RMS | .02245 | .003008 |
| learner更新差分：RMS | .02362 | .003077 |
| actor／learner更新差分cosine | .04157 | .05367 |

FP16で絶対的なbackend差は低下したが、差分方向の一致は改善したとは言えない。これは小さい1step更新の信号が丸め・kernel差に埋もれる可能性とも整合するが、原因を同定した結果ではない。mapping不具合、kernel経路差、精度の影響をこの検査だけで断定しない。FP16全文更新・FP16 rollout速度・繰返し更新の安定性は未検証である。大規模投資の前に、更新信号を数値差から分離できる条件で接続検査を通す必要がある。

BF16 updated actorでは同じ訓練問題H04に新たに4回答を生成し、報酬は1,1,1,0だった。全文の追加レビューでも最初の3件に完成した一般導出と厳密解が確認された。ただし同じ訓練問題・4回答だけであり、baseの1/4から学習改善したという推定にも、転移の証拠にも使わない。この4件のレビューは主screenの32件と別保存した。

## 時間：主な負担は生成

| 実行区間 | 回答／tokens | 生成時間 | worker全体 |
|---|---:|---:|---:|
| 初回screen | 48／453,418 | 33.78分 | 34.05分 |
| 打切り2群の全回答再生成 | 8／62,226 | 4.67分 | 4.95分 |
| screen実支出合計 | 56／515,644 | 38.45分 | 39.00分 |
| 最終採用48回答のみ | 48／427,358 | 30.89分 | 初回との重複を含むため別途加算しない |
| updated LoRA actor追加生成 | 4／28,006 | 3.85分 | 4.09分 |

最終回答は平均8,903、中央値9,112.5、最大15,240 tokens。自然終了が1024tokens以内だった回答は0/48。ただしこれは観測済み回答の長さであり、1024上限で改めて生成した全回答が必ず失敗するという実験結果ではない。

base screenの生成速度は約230.55 tokens/秒。LoRA装着後の追加生成は約121.31 tokens/秒で、今回の構成では大きく低下した。追加生成の対象は1問だけなので、汎用的なLoRA速度推定とは言えない。それでもbaseだけの速度を本学習全体へ適用すると費用を過小評価する恐れがある。

以下は、今回のscreenの長さ・上限延長費用、混在率50%、実測47.6–70.8秒の更新費用を維持し、LoRA生成速度121.31 tokens/秒を適用した条件付き外挿。各問4回答・1周。信頼区間ではなく、数値条件の違いによるシナリオである。

| 問題数 | LoRA生成 | 混在群の学習 | 合計（loading等を除く） |
|---|---:|---:|---:|
| 256 | 25.19時間 | 1.69–2.52時間 | **26.88–27.71時間** |
| 1,024 | 100.76時間 | 6.78–10.08時間 | **107.54–110.84時間：約4.5–4.6日** |
| 3,443 | 338.77時間 | 22.80–33.91時間 | **361.57–372.68時間：約15.1–15.5日** |

数千問は不可能とは言えないが、数時間で試行錯誤できる規模でもない。問題分布・回答長・更新後の速度・混在率・再生成率で変わる。複数周なら生成と学習の項は概ね周数倍。G=8への並列効率は未測定で、G=4から単純に同じ速度を仮定しない。

表にloading・save・actor reload・失敗再試行・guard起動は含めていない。実測ではlearner load約2.1秒、save/照合約.32秒、BF16 actor load約12.1秒。更新／再配置のバッチ数に応じて追加が必要になる。FP16 actorの追加検査では初期loadに102.6秒かかり、compile/cache条件にも感度がある。FP16運用をこの表の速度で見積もれるとは確認していない。base速度だけを使う楽観的な3,443問の外挿は約207–218時間だが、LoRA装着後の実測と合わないため本学習の代表値には採用しない。

学習objectiveは全completion tokensの共通正規化であり、回答ごとの等重み平均ではない。最小群では正例4,394 tokensに対し、不正例の合計は28,216 tokens。長い不正例のtoken数も更新に影響する。長文・報酬・正規化の組合せを固定せずに別アルゴリズムの時間や効果を移植できない。

## 前例から判断できること

[GeometryZero v3](https://arxiv.org/html/2506.07160v3)は数値問題から証明への移行を報告する。訓練は3,443問、G=8、completion上限1024、4 H100、全パラメータ更新で、GCPOは補助線の有無による対照群と長さ報酬も使う。今回の1 GPU・長文・LoRA・数値正答のみのGRPO型検査とは条件が異なる。したがって前例はRLを検討する理由にはなるが、今回の費用や信号の品質、研究意図に沿う転移の成功確率を与えない。

## 次の研究判断

現時点の有望度は**条件付きで試す根拠がある段階**。データ不足の可能性とRLの前例は残り、今回も有用な幾何の正負を区別する群が観測された。ただし「非ゼロ勾配が出るから数千問を回せばよい」とは判断しない。

次の実験は、まず小規模で生成／learnerの更新反映を数値誤差から分離し、複数更新でも接続とoptimizerが安定することを確認する。そのうえで構図・形状を増やし、正解・対象解法を知らずに作る経験という制約を保ちながら、算術落ち・推測正答・全正答／全不正解による信号消失を測定する。数学レビューは診断として使い、これを暗黙に教師報酬へ投入しない。外部計算器や証明検証器を報酬に追加する場合は、経験の種類が変わる別実験として定義する。

成功判定は最初から、直接教えない幾何的性質・解法・証明を含む固定holdoutとbase対照で行う。同構図の形状変更による数値性能と、構図を跨ぐ転移や一般証明を区別して報告する。訓練正答率が上がっても、その研究上の評価を置き換えない。今回の結果は研究方針の否定ではなく、RLに投資する前に除くべき実装と報酬の交絡を具体化した結果である。

## 失敗と監査

- 初回起動で補助ファイル `signal.py` がPython標準ライブラリを隠し、importに失敗した。名称を変更し、生成・更新0件の失敗receiptを保持した。
- 元の最小・最大probeはfidelity gateで停止し、実更新0件。原ソースと失敗receiptを保持した。
- TIS追加検証時にvenvにpytestがなく、その呼出しは失敗。追加installはせず、閉形式とdense参照を比較する独立CPU検証を実行して合格した。system pythonで集計を呼んだ際のsympy不在も、既存venvで再実行して解決した。
- 原CPU検証は実際の小型Qwen3.5のlinear/full attention、causal context、checkpointとLoRA勾配を含む6件。テスト追加前のfreeze hashと、追加後の6件の検証hashは別記録で保持した。
- 最終監査のpassはsource/hash・全文保持・receipt・review bindingの照合が通った意味であり、原fidelity gate合格、数学の独立査読、改善・転移成功を意味しない。
- 全GPU検査は終了した。実験のPython/vLLM GPUプロセスは残っておらず、desktopプロセスは停止・変更していない。

## 再確認用の記録

保存データのrootは `/home/kabatan/work/solver/qwen/.runtime/numeric_rl_feasibility_20260930`。

- [事前プロトコル](/home/kabatan/work/solver/docs/research/numeric-rl-feasibility-2026-09-30/PROTOCOL.md)、[混在群の全文レビュー追加](/home/kabatan/work/solver/docs/research/numeric-rl-feasibility-2026-09-30/QUALITY_SCOPE_AMENDMENT.md)、[TIS追加検査](/home/kabatan/work/solver/docs/research/numeric-rl-feasibility-2026-09-30/IMPORTANCE_CORRECTION_AMENDMENT.md)、[B=0対照](/home/kabatan/work/solver/docs/research/numeric-rl-feasibility-2026-09-30/ZERO_ADAPTER_CONTROL_AMENDMENT.md)、[精度追加診断](/home/kabatan/work/solver/docs/research/numeric-rl-feasibility-2026-09-30/PRECISION_DIAGNOSTIC_AMENDMENT.md)
- [48回答・報酬・advantage](/home/kabatan/work/solver/qwen/.runtime/numeric_rl_feasibility_20260930/screen-scores.json)、[32全文の数学評定](/home/kabatan/work/solver/qwen/.runtime/numeric_rl_feasibility_20260930/math-review.json)、[機械的監査](/home/kabatan/work/solver/qwen/.runtime/numeric_rl_feasibility_20260930/mechanical-audit.json)
- [元の最小群失敗](/home/kabatan/work/solver/qwen/.runtime/numeric_rl_feasibility_20260930/probe-short/receipt.json)、[元の最大群失敗](/home/kabatan/work/solver/qwen/.runtime/numeric_rl_feasibility_20260930/probe-long/receipt.json)、[TIS最小群の実更新](/home/kabatan/work/solver/qwen/.runtime/numeric_rl_feasibility_20260930/probe-short-tis/receipt.json)、[TIS最大群の実更新](/home/kabatan/work/solver/qwen/.runtime/numeric_rl_feasibility_20260930/probe-long-tis/receipt.json)
- [実更新・BF16 actor接続監査](/home/kabatan/work/solver/qwen/.runtime/numeric_rl_feasibility_20260930/technical-audit.json)、[FP16比較](/home/kabatan/work/solver/qwen/.runtime/numeric_rl_feasibility_20260930/precision-comparison.json)、[追加actor4回答の全文評定](/home/kabatan/work/solver/qwen/.runtime/numeric_rl_feasibility_20260930/actor-math-review.json)
- [時間外挿とtoken正規化](/home/kabatan/work/solver/qwen/.runtime/numeric_rl_feasibility_20260930/cost-projection.json)、[旧RL再集計](/home/kabatan/work/solver/qwen/.runtime/numeric_rl_feasibility_20260930/historical-rl-audit.json)、[最終監査](/home/kabatan/work/solver/qwen/.runtime/numeric_rl_feasibility_20260930/final-audit.json)
