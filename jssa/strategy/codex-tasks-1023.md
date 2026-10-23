# Codex への依頼（10/23）

前提：repo は kabatan/geosolver、branch `claude/project-thread-9bdbbg` を pull して使う。solver 本体（src/）は凍結（60db4b6）なので変更しない。新しいコードは jssa/ 以下に置く。結果は指定のフォルダに置いて同じ branch に push する。Python は repo の .venv（`uv sync` 済みでなければ `uv sync`）。

背景：研究の中心の問いは (1) 求値幾何の solver をどう実現したか、(2) solver にとっての難しさは人間の難しさとどう違うか。予備調査（jssa/difficulty/ghost-1023/README.md）で、外れた探索の約35%が「2点が重なった図」で止まることが分かった（当たりでは0%）。誤答なのに式を満たす終点の79%も、2点が重なった図だった。jssa/strategy/gpt-pro-consult-12-prompt.md も読むこと。

---

## sol-1（実装と実験）：退化した厳密解の有無を、探索の結果を使わずに測る

目的：問題ごとに「2点が重なった図で、条件の等式がすべて満たされるか」とその次元を測る。探索の終点の分類は使わない。

手順：
1. 対象は jssa/difficulty/minima/basins-323.csv の n_vars ≥ 1 の問題（292問）。問題の DSL は benchmarks/cases.jsonl の `dsl`。
2. 点の座標は jssa/difficulty/probe_basins.py の `construction_coordinates` で変数から計算できる。点の名前の取り方は jssa/difficulty/ghost_scan.py の `point_names` と同じにする。
3. 点の組 (P, Q) ごとに、元の等式の残差ベクトル F(u) に2行 (P(u) − Q(u)) を加えた系を、問題の探索箱（`infer_problem_bounds`）からの乱数出発点20個で LM 法（scipy の least_squares, method="lm"）で解く。乱数は `np.random.default_rng([0, i, j])`（i, j は点の番号）。
4. 残差が 1e-10 以下に収束した解があれば、その組は「退化した厳密解あり」。そのときの次元を、その解での拡張系のヤコビ行列（中心差分）の数値ランクから n − rank で求める（特異値が最大値の 1e-8 倍未満を0とする）。
5. ただし、当たりの図（minima/raw-323/<id>.json の records で cls=="hit" のもの）で常に重なる組は除く（答えの一部）。当たりが無い問題は、除外なしで計算し、そのことを列に記録する。
6. 出力：jssa/difficulty/ghost-exact/ に per-pair.csv（id, P, Q, found, best_res, dim）と per-problem.csv（id, n_vars, n_pairs, n_pairs_found, max_dim, has_hits）。コードは jssa/difficulty/ghost_exact.py。README.md に手順と所要時間を書く。

判定は事前登録（ghost-1023/preregistration.md）に従う。結果の解釈は書かなくてよい（数値だけでよい）。

## sol-2（実装と実験）：3点が一直線になる退化と、図の膨張についても同じことをする

sol-1 と同じ手順で、加える行を「P, Q, R の作る三角形の符号付き面積（2行ではなく1行）」にした版。対象の3点組は、当たりの図で常に一直線のものを除き、点が12個を超える問題では、ランダムに選んだ200組までに絞る（乱数 `default_rng([1, 問題番号])`）。出力は jssa/difficulty/ghost-exact/ の per-triple.csv と per-problem-triple.csv。

## astra-A（相談役、実験してよい）：相談12の問いに答える

jssa/strategy/gpt-pro-consult-12-prompt.md の「聞きたいこと」1〜5に答えてほしい。自分で実験してよい。データは jssa/difficulty/minima/（raw-323 は 323問×200出発点の終点）、jssa/difficulty/ghost-1023/（終点の図の形 endpoints_v1.csv、人間の難易度 human_feat.csv の human 列）、jssa/difficulty/stage-taxonomy/。回答と使ったコードを jssa/strategy/astra-consult-12/A/ に置く。

## astra-B（相談役、実験してよい）：仮説を与えずに「非自明な原理」を探す

予備調査の仮説（退化した図）にとらわれずに考えてほしい。問いは「この solver（多点出発の局所探索＋高精度化＋厳密同定）にとっての難しさと、人間（Easy2Hard の難易度、AIME/HMMT の正答率）の難しさのずれを、一つの原理で説明・予測できるか。できるならそれは何か」。直感に反する予測、本人（IMO 金メダリスト）も事前に当てられない予測を一つ以上出し、手元のデータで予備的に確かめてほしい。データは astra-A と同じ。jssa/draft/report-draft-v7.md と jssa/draft/supplement-v7.md も読むこと。回答とコードを jssa/strategy/astra-consult-12/B/ に置く。

## astra-C（相談役、実験してよい）：変数を増やすと良くなる問題

作図で消していた点を自由点に戻す（変数を増やす）と、たいていは当たる確率が下がる。しかし AIME 2020 II-15 では 0.03 → 0.53 に上がった（他に HMMT 2017 FEB GEO-10、HMMT 2021 FEB GEO-04 でも少し上がった）。元の系の失敗は、図が数百〜10万倍に膨らみ、垂線の足が頂点に重なる、というものだった（ghost-1023/README.md）。なぜ上がるのか、どの問題で上がるかを事前に予測できる規則は何かを考え、確かめてほしい。DSL は jssa/difficulty/holdout-1023/（k0 が元の系、k2 が自由点の系）に無ければ jssa/difficulty/expand_k.py で作れる（`--kmax 2 --min-eligible 2 --max-vars 6`）。実験の道具は jssa/difficulty/probe_common.py。回答とコードを jssa/strategy/astra-consult-12/C/ に置く。

---

# 追加（10/23 15:30）

## astra-D, astra-E（相談役、実験してよい、互いに独立）：中心成果の別の候補を出す

背景：本人の要求は「最高賞レベル。自明な予測と自明な結論は不可」。中心の問いは固定（(1) solver をどう実現したか、(2) solver の難しさは人間の難しさとどう違うか）。いまの候補は「出発点の図が問題の不等式（形の条件）を破るかどうかが当たり外れを大きく左右し、人間の難易度とは無関係」（jssa/difficulty/start-feasibility-1023/README.md、jssa/strategy/astra-consult-12/B/）。本人は「面白いが、最高賞の中心を担えるかは検証が要る。安易に決めない」と言っている。

依頼：この候補とは別の、中心成果の候補を一つ以上出し、手元のデータで予備的に確かめてほしい。各候補について (a) 主張を一文で、(b) 誰も事前に当てられない予測、(c) 2日以内・4〜16コアで実行できる検証の設計、(d) 外れたら何が言えるか、(e) 既知の文献との関係、を書くこと。候補を選ぶ基準は「人間と solver の難しさのずれを、一つの機構から予測できるか」。

- astra-D：solver の内部（局所探索の軌道、精密化の収束、厳密同定）から攻める。データ：jssa/difficulty/minima/（raw-323 と raw-323-seed1 は 323問×200出発点の終点・出発点）、jssa/difficulty/stage-taxonomy/、jssa/results/stage-profile-20261023/。
- astra-E：人間の側から攻める。人間の難易度は ghost-1023/human_feat.csv の human 列（Easy2Hard）と、問題文（benchmarks/cases.jsonl）。本人は IMO 2025 金メダリストで、その感覚も一次資料になりうる（本人に聞きたいことがあれば質問として書く）。

出力：jssa/strategy/astra-consult-14/D/、E/ に answer.md とコード。

## astra-F（批判役）：今の候補の弱点を突く

jssa/strategy/gpt-pro-consult-13-prompt.md を読み、候補の主張（図の形の正しさ）を、審査員として最も厳しく批判してほしい。特に「罰則の設計が悪いだけでは」「φ は変数の数や不等式の数の言い換えでは」「人間の難易度との無相関は、何も示していないのでは」に、データで答えること（反証を試みる実験をしてよい）。出力は jssa/strategy/astra-consult-14/F/。

---

# 追加2（10/23 16:00）

## sol-3（実装と実験）：未使用の20問での予測
jssa/difficulty/ghost-1023/preregistration-2.md の A に従う。DSL は jssa/difficulty/new2026/cases.jsonl（benchmarks/cases.jsonl にはない。probe_basins.py の load_case は benchmarks しか読まないので、ケースファイルを差し替えられるように jssa 側だけを直す）。G は jssa/difficulty/ghost_exact.py を流用。手順の (1)〜(3) を終えて predictions.csv を commit してから (4) の集計をすること。出力：jssa/difficulty/new2026-predict/。

## sol-4（実装と実験）：退化解を消す介入
jssa/difficulty/ghost-1023/preregistration-2.md の B に従う。退化解の見つかった組は jssa/difficulty/ghost-exact/per-pair.csv。出発点は jssa/difficulty/minima/raw-323/<id>.json の records の start（seed 0）をそのまま使う。局所探索は probe_basins.py と同じ smb._collect_local_start_record の経路を使い、残差だけを拡張する（src/ は変更しない。jssa 側でラップする）。出力：jssa/difficulty/ghost-intervention/（per-start.csv、per-problem.csv、README.md、score.md）。

---

# 追加3（10/23 16:40）

## sol-5（実験）：誤差の単調変換が効くのは形の誤った出発点だけか
jssa/difficulty/ghost-1023/preregistration-3.md に従う。変換と a の決め方は jssa/strategy/astra-consult-12/B/experiment.py をそのまま使う（新しく書くなら、2問 AIME 2023 I-12・HMMT 2024 FEB GEO-04 で astra-B の再現結果と一致することを先に確認）。出力：jssa/difficulty/transform-check/（per-start.csv に出発時の hard feasibility も記録、per-problem.csv、score.md）。

## sol-6（解析のみ）：失敗は、G が示した点の組に近づいているか
GPT-Pro 相談13の6.2。G あり（jssa/difficulty/ghost-exact/per-pair.csv で found=1 の組がある）問題について、minima/raw-323 の全出発点の終点を「成功」「found=1 の組のどれかが重なって失敗（coinc < 1e-4、ghost_scan.py と同じ尺度）」「それ以外の失敗」に分ける。G なしの問題では「どれかの組が重なって失敗」と「それ以外」に分ける。両群の内訳を変数の数の層ごとに表にする。出力：jssa/difficulty/ghost-pairs-match/。

---

# 追加4（10/23 17:20）

## sol-7（実装と実験、スーパーPC の計算資源で）：完成した solver での費用の比較
jssa/difficulty/start-feasibility-1023/preregistration-4.md に従う。src/ は変更しない。jssa 側のランナーで `geosolver.engine.standard.search.scipy_multistart_backend._build_local_start_sequence_with_kinds` を差し替える（monkeypatch）。差し替え後の出発点が実際に使われたことを、各実行の記録（選び直しの回数、形の条件を満たした割合）で確認すること。本番の実行経路・採点は既存の本計測（jssa-main-j6-20261022 で使ったランナー）と同じにする。両条件は同じ計算機で交互に、同じ並列数で走らせる。出力：jssa/difficulty/full-solver-redraw/（per-run.csv、per-problem.csv、README.md、score.md）。所要時間の見込みを最初に知らせること。

---

# 追加5（10/23 19:30）：Aを狙う中心成果の探索（astra を並列で）

背景（全員共通）：GPT-Pro の辛口判定（jssa/strategy/gpt-pro-consult-16-answer.md）は C（Bに近い）。最大の弱点は「この研究で、従来できなかった何ができるようになったのか／従来知られていなかった何を十分な広がりで明らかにしたのか」。本人は「Aを狙って新しい中心成果を探す」を選んだ。中心の問いは固定：(1) solver をどう実現したか、(2) solver の難しさは人間の難しさとどう違うか。自明な予測・自明な結論は不可。現行の本文は jssa/draft/report-draft-v10.md、補足は supplement-v10.md。候補の一覧は jssa/strategy/gpt-pro-consult-17-prompt.md。src/ は凍結（変更しない）。改変は jssa/ 以下で monkeypatch。

全員への依頼：(a) 主張を一文で、(b) 誰も事前に当てられない予測、(c) 予備的な検証の結果（手元のデータで、実際に計算して）、(d) 1日以内・16コアで実行できる事前登録用の本検証の設計、(e) 外れたら何が言えるか、(f) 既知の文献との関係、を answer.md に書く。コードと中間データも同じフォルダに置き、push する。候補として弱いと判断したら、そう結論してよい（それも価値がある）。

## astra-G：許容条件は「壁」か「近道」か（候補1の機構）

観察（Claude、seed 0）：AIME 2010 II-14 では、許容判定を満たす出発点116個のうち104個が「stuck」で、終点も許容のまま。許容しない出発点84個は76個が当たり。実装では、許容判定を破ると残差ベクトルの最後の成分が一定値 10⁴ になる（scipy_multistart_backend._evaluate_augmented_residual_vector）。許容しない領域ではこの成分の勾配が0なので LM は元の等式だけで動くが、許容領域の中からは境界を越える一歩が大きく残差を増やし、拒否される。仮説：許容領域の境界が「壁」になり、解へ向かう道をふさぐ問題では p_F < p_I になる。ただし HMMT 2007年2月 幾何4（wrong_answer が多い）や JMO 2017 予選1（left_box が多い）は別の型に見える。
依頼：(1) 292問で、許容出発点からの失敗の終点が「境界に張り付いている」か（終点から解の方向・ランダム方向への小さな一歩で許容判定が変わるか、LM の最後の数歩が拒否されているか）を測り、p_F < p_I を説明できるか。(2) 入力の構造（不等式の種類と数、枝の選び方、解が許容境界にどれだけ近いか＝当たりの図での guard の余裕など）から、p_I > p_F の問題を事前に予測できるか。(3) 介入：罰則の扱いだけを変える（例：許容判定の罰則を収束後の判定にだけ使う、または境界までの距離に比例する傾きのある罰則にする）と、「壁」型の問題でだけ p_F が上がり、他は変わらない、という予測を立てて予備的に確かめる。データ：jssa/difficulty/minima/raw-323（start・x・cls）、start-feasibility-1023/。出力：jssa/strategy/astra-consult-17/G/。

## astra-H：図が一つに決まらない問題で値を返す（候補2）

msolve で答えの集合が一致しなかった122問のうち68問は座標の解集合が正次元（supplement-v10.md S1.4、S2.8、データはブランチ nycxfb の jssa/results/exact-comparison-pc-20261022/）。solver はほぼ全部で正解する。依頼：(1) この68問を「図が実際に動く（実数の解が無数で値は一定）」「固定漏れなど見かけの正次元」に全部分類する（S1.4 は10問だけ調べた）。(2) 図が実際に動く問題について、solver の出した解の周りで解集合の次元と、値が一定であることを数値的に確かめる。(3) 値が一定であることの証明書（s^N·P(τ) = Σ C_i F_i）を作れる問題を増やせるか（今は63問中24問）。(4) 既存の方法（Gröbner 基底、msolve、Wu の方法、GMB、AlphaGeometry2）でこれらが本当にできないのかを文献で確かめ、「新しくできるようになったこと」と言える範囲を正直に書く。出力：jssa/strategy/astra-consult-17/H/。

## astra-I：solver が自分の難しさを事前に診断し、構成を選ぶ（候補3）

φ、変数の数、短い予備探索（例えば出発点20個）から、問題ごとに「出発点の方策（許容点を優先する／しない）」や「探索の構成」を選ぶ規則を作り、一律の方策より良いかを予備的に確かめる。予備探索の費用も含めて評価すること。完成 solver の費用比較（jssa/difficulty/full-solver-redraw-cloud/、事前登録 start-feasibility-1023/preregistration-4.md）の途中結果が out/A にある（読むだけ。書き換えない）。出力：jssa/strategy/astra-consult-17/I/。

## astra-J：自由に探す（上の候補にとらわれない）

上の候補を見ずに考えてよい。手元の全データ（jssa/difficulty/、jssa/results/、Easy2Hard の人間の難度 ghost-1023/human_feat.csv）から、「人間と solver の難しさのずれ」について、本人（IMO 金メダリスト）にも事前に当てられない、広がりのある主張を一つ探し、予備的に確かめる。出力：jssa/strategy/astra-consult-17/J/。

## astra-K：審査員として候補を潰しにかかる

jssa/strategy/gpt-pro-consult-16-answer.md の観点（特に過去の受賞作「割当問題の拡張と解法」との比較、新規性、本人の寄与）で、候補1〜3それぞれを最も厳しく批判し、どの候補なら A に届きうるか、届かせるには何が必要かを書く。必要ならデータで反証を試みてよい。出力：jssa/strategy/astra-consult-17/K/。
