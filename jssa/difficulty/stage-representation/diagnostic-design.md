# Q39 診断版の仕様（未実装・未実行）

`src`、DSL、`research_runner`は変更しない。段階1で実装したのは構文だけを読む`select_static.py`。以下の数値ラッパーは別タスクで実装し、その差分・hashを実行前に記録する。ここにない予算・選択・成功定義の変更は予測の改訂であり、黙って実行しない。

## 4条件と段の分離

25問×seed `39001,39002,39003`×8始点。前段は凍結NOMAD/DiscoMADSの単独探索、後段は凍結MpmathRefiner。A→A／A→B／B→A／B→Bを全て作る。前段A/Bは各1回だけ走らせ、同じ保存候補を後段A/Bへ複製する。後段別に候補を作り直さない。代数的前処理、救済、第2探索は入れない。完成solverの再現実験とは呼ばない。

1. 原DSLを通常のcompiler・bundleへ通す。lowering、変数の除去、全guard/hardは4条件で共通。静的分類と実際の書き換え行を照合し、不一致は`mapping_unverified`。問題を取り替えず、当該層の結論を保留する。
2. 通常の`infer_problem_bounds`の有限箱を共有する。25%の箱拡張は診断では無効。始点は次のhashで各座標を独立に作る：UTF-8の`Q39-start-v1|id|seed|start_index|coordinate_index`のSHA-256先頭8byteをbig-endian整数hとし、`u=((h>>11)+0.5)/2**53`、`x=lo+(hi-lo)*u`。添字は0始まり。拒否点の再抽選なし。float.hexで保存する。
3. 同じ規則の`Q39-scale-v1|id|probe_index|coordinate_index`から32点を準備。両残差の行／置換ブロックについて有限値の絶対値／2ノルムの中央値を取り、`s=max(1,median)`。有限値なしは1とし欠測を記録。答え・正解座標は使用しない。補助行にも独立の固定尺度を与える。
4. 各前段は同じ始点・NOMAD seed、最大1,200 callback・6秒。backend seedは`external_seed*100+start_index`。native設定を使い、`constraint_scales=None`。両armとも各callbackでAとBを計算して記録し、optimizerへ渡す残差だけ切り替える。Bだけに観測費用を負わせない。無効評価もcallbackに数える。
5. 共通候補品質`Q(x)=max(max_i |A_i|/sAi, max_g ||B_g||₂/sBg)`。通常の残差行は1行ブロック。両armとも、元guard/hard通過・箱内の有限点のうちQ最小を1点選ぶ。なければ箱内の有限点でQ最小、全てなければ欠測。tieは評価順。各arm自身の目的値で候補を選別しない。元Aだけ／Bだけの閾値率も補助で残す。
6. 各保存候補を同じbinary座標のままA/B各8秒で精密化。1候補ごとにdeadlineを分離。既定の50/100/120dps、closure 120/250/350/500dps、80 LM反復などは維持する。warm Newton・LM・closureの全てで同じ残差モードを守る。
7. 8始点から得た候補を条件別に集め、元evaluatorを渡した`assemble_exact_results`を各問・seed・条件20秒で呼ぶ。独立検証・厳密同定の前後を別記し、後段の桁測定はその**前**に行う。同定・検証での追加補正を後段Bの効果に混ぜない。

## 薄いラッパーの差分仕様

| 接続点 | 診断時だけの変更 |
|---|---|
| `EvaluatorPort`を委譲するsearch proxy | Aは元`evaluate_float_residual`。Bはその結果に凍結`_smooth_zero_constraint_residuals`を適用しfloat結果を組み立てる。Bの幾何計算も53bit（`dps=15`を実装時に確認）。guard/hard/answer/元HP評価は委譲のまま |
| `NomadBlackboxAdapter` | proxyを注入。共通Qの候補台帳を外側に置く。元の有限不許容罰則、評価不能時の扱いを維持 |
| `mpmath_refiner._smooth_zero_constraint_residuals` | 後段Aのみ、呼出しプロセス内でidentityへ一時置換。後段Bは凍結関数そのもの。`finally`で復元。プロセス間でモードを共有しない |
| `mpmath_refiner.derivative_plan` | **両後段でNone**。B用解析Jacobianの混入を防ぎ、差分法を共通化する。凍結既定の性能と同一とは称さない |
| `mpmath_refiner.compute_finite_difference_jacobian` | **両後段で`row_dependencies=None`**を明示して元関数へ委譲。Bの行数・依存関係変更へ元の色分けを流用しない。差分幅・片側fallbackは元設定 |
| 観測proxy／`_run_stage`／`_run_findroot_closure`外側 | 入力、各stage/closureの返却点、最終点を保存。試行点を採用反復と誤認しない。50/80桁の到達時間は保存時点での上界とする |
| 最終検証・採点 | 元Aのevaluatorへ戻す。ここに残差proxy、identity patch、診断用成功閾値を入れない |

補助式があるのにB helperが入力listそのものを返した場合は例外fallbackを疑い、`rewrite_fallback`を記録する。無変更対照で同じlistが戻るのは正常。予想行数・元行→ブロック対応も検査する。Bを評価できない点を黙ってAへ置換し、Bの成功に数えてはいけない。円間接点式の同一円という余分な零点は、元AのQ・guard/hard・最終検証で排除し、出現数も報告する。

## 指標・分母

- **前段能力F**：候補が元guard/hardを通り、箱内で`Q<=1e-4`。24始点／問を分母とし欠測・timeoutも失敗。答えを参照しない「近似配置候補率」で、正答率ではない。
- **後段能力R**：同一の保存候補から50桁へ到達する割合。独立後処理で元残差・B・hardを180dpsで再評価し`Q<=1e-50`、かつtargetの参照値集合への相対誤差`min_v |t-v|/max(1,|v|)<=1e-50`を要求。これも段の診断値で、公式採点ではない。
- **桁の増分**：`d(t)=clip(-log10(min_v |t-v|/max(1,|v|)),0,100)`。誤差0は100、非有限／候補欠測は0。入力と同定前の最終点の差を記録し、B−Aのpaired差を集計する。座標全体の正しい桁数や証明を意味しない。元残差の桁、Qの桁、80桁到達も別記する。
- 数値参照も既存`research_runner.reference_expressions`の分解規則を使う。各参照式を180dpsで評価するだけで、出力形式の変換や正解の許容幅を新設しない。参照値を読むのは候補台帳を封印した後の採点側だけ。
- 後段の主比較は、前段AとBの両候補を足した共通台帳（48枠／問）上。前段の閾値合格例だけを残さず、前段由来別の差も出す。同じ座標でも由来を消さない。候補のない枠は両後段とも失敗・増分0とする。有限候補だけの条件付き率も分母付きで併記する。
- 率は問題を等重み。family、構造層、問題、seedごとのpaired差を出す。95%区間は問題単位bootstrap 10,000回・seed39099の記述区間で、閾値の後付け選択には用いない。完了例だけの速度比を主指標にしない。
- callback上限と時間上限を区別。200／800／1200 callback時のQも保存（自然終了なら最終点を持越し、timeoutなら未到達を明記）。200 callbackまたは自然終了まで両armが完了した組が90%未満なら、前段差の機構判定は不足とする。全枠の実用的な率からtimeoutを除かない。

## 重根・単位・混合の切分け（実行時に必須）

1. **線–円の重み対照L**：`tangency_line_gap`を持つ選択7問で、Bの当該行を`(s²-r²)/(abs(s)+r)=abs(s)-r`へ置換して4条件を再構成。他の行はそのまま。正半径なので分母は正。Aとの二乗和差だけを除き、元Qで選別・測定する。共通のA→Aと前段Aは再利用可。
2. **初等的正則化の後段対照R0**：選択21問の同じ前段候補へ追加する。2点距離は座標差、円間gapは符号付きgap、線円一般形はL、正半径は同じ因子除去を使う。接点行だけは`R0_i=sBi*sign1(B_i)*sqrt(abs(A_i)/sAi)`（`sign1(0)=+1`）で局所消失次数を戻す。これはBの枝符号を利用する診断であり独立solverではない。差分の`one_sided_at_cusp=True`を共通適用し、解析Jacobianは無効。Bとの差がないなら一般的な尖点／因子除去で十分という説明と整合する。
3. **混合層の分解**：HMMT-2016-FEB-GEO-10は線円gap・円間gap・正半径補助の3種が混在。各1種だけをBにする3追加比較（各4条件）を固定。他2種はA。1問を3命令の再現と数えない。
4. **消失次数**：各問の通常4条件が保存した、元検証に合格した点のうち`(seed,arm,start_index)`辞書順最初の1点を用いる。既存点がなければNA。方向3本は`Q39-order-v1|id|direction_index|coordinate_index`のhashを始点と同じuへ変換し、`v=2u-1`を2ノルム1へ正規化（全0なら第1軸）。添字0始まり。±`10^-2,...,10^-8`×各座標の箱幅でA/Bを評価し、guard通過／違反と局所log slopeを保存（最大10秒／問）。新しい根を探して補わない。`1.8<=order(A)<=2.2`、`0.8<=order(B)<=1.2`を重根解消の整合例とする。元の別等式から接点を証明する場合は、等式面を外れた方向の傾きも混ざるため、この数値だけで次数を証明しない。

R0やLで差が残っても、それだけで深い理論が必要とは結論しない。有限差分の尖点、行数・局所rank、残差の単位、枝の切替え、余分な零点の説明を先に検討する。
