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
