# solverの難しさの理論：作業メモ（2026-10-22 23時、研究方針スレッド）

## T1 二種類の難しさ（msolveが解けた201問、PC計測）
- 順位相関: ベズー数×探索変数数 0.12（ほぼ独立）。
- msolve時間: ベズー数 0.69 / 探索変数数 0.28（偏: 0.69 / 0.27）。
- solver時間: 探索変数数 0.57 / ベズー数 0.50（偏: 0.60 / 0.54）。
- 読み: 探索変数の数は厳密法にほぼ効かず、solverには効く。solverは代数的な大きさにも一部影響される（評価の重さ・局所解の数？）。
- 分析: scratchpad twoaxes.py（exact_cases.csv × probe_merged.csv）。

## T2 作図による変数消去 = シューア補行列、拡大系は条件が悪くなる
- 拡大系 S(u,y)=(r(u,y), y−h(u))、J_aug=[[r_u, r_y],[−Dh, I]]。縮約系 J_R=r_u+r_y·Dh。
- 実測（extra-variables 15問の正解点でのヤコビアン特異値、probe_extra first_hit）:
  条件数κの中央値 k=0:1.8 → k=1:82 → k=2:92 → k=3:159。
- 同じ問題の中で Δlog κ と Δp: 順位相関 −0.67（p=5e-5, 10問×3段=30組）。Δlog κ と Δlog(1回の時間): 0.52（p=0.003）。
- 例: AIME-2014-II-14 κ 1.6→160、p 1.00→0.29。例外: HMMT-2024-FEB-GEO-07 κ 1→310 でも p 0.8 前後。

## T3 当たる確率の模型（カントロビッチ型の下界）
- 解のまわりに半径 ρ≈c·σ_min/L の収束保証球 → p ≳ vol(B_ρ)/vol(box) ∝ (ρ/幅)^d。
- 323問（234問で条件数が有限）: log p を d だけで R²=0.16、d と log κ で R²=0.24。係数 d:−0.21、log κ:−0.07。
- 弱い。下界なので当然だが、d（指数）と κ（冪）の両方が効く向きは一致。

## T4 対照実験（初期位置を作図どおり）
- k=2: p 0.40→0.76、k=3: 0.39→0.42、AIME-2014-II-14 k=1: 0.29→0.06。
- 解釈候補: LMは拡大空間で y≠h(u) の方向へ出ていく（条件の悪い谷）。内側最小化 ψ(u)=min_y… は φ のなめらか版になりうるので、書き換えが p を上げる問題がある事実とも整合しうる → GPT-Pro相談6で確認中。

## T5 枝の等分配仮説
- 「正しい解の数/msolveの実解の数」と p の順位相関 0.26（偏 0.14、185問）→ 引き込み領域は解ごとに等しくない。

## 待ち
- GPT-Pro相談6（/mnt/project-files/jssa/strategy/gpt-pro-consult-06-prompt.md）。
- 局所解の数え上げ（Sonnetスレッド）→ /mnt/project-files/jssa/difficulty/minima/。

## T6 Link between the second search and p (10/23 01:50, cloud)
The 9 problems lost in the 1-seed NO_SECOND_ATTEMPT ablation (nycxfb ablation-20261022) had a median hit probability p of 0.12. The median over all 292 problems was 0.55 (Mann–Whitney p = 0.006). Four of the 9 had p = 0. So the second search is the mechanism that rescues problems whose first search hits only rarely. To be redone with the 3-seed ablation and the attribution data (PC, requested).

## T7 Where answers came from, and where time goes (10/23 02:00, 9bdbbg 9d25047 jssa/results/mechanism-attribution/)
- Source of the answer over 969 runs: algebraic preprocessing 292, zero-variable path 93, NOMAD 476, LM multistart (scipy) 74, rescue 25, other 9.
- The mechanisms line up by hit probability p (medians). Algebraic preprocessing: p 0.91, d=2. LM multistart: p 0.92, d=1. NOMAD: p 0.43, d=3. Rescue: p 0.05, d=5. Runs where the second search fired: p 0.04 (38 runs).
- Time breakdown (share of total wall time): search 18%, refinement 48%, exact identification and verification 27%, rescue 1%. Even for answers that came from NOMAD, search is 16% and refinement plus identification 78%. So the solver's time is spent mainly on making the answer exact, not on searching.

## T8 なぜ「ずれの座標」は元の系と同じ動きをし、「自由点の座標」は違うのか（10/23）

記号：元の系 E は u だけを変数にし、残差は R(u) = C(u, h(u))。自由点の系 Y は (u, y) を変数にし、残差は (C(u, y), y − h(u))。ずれの系 Z は (u, z) を変数にし、残差は (C(u, h(u)+z), z)。LM法は MINPACK の方式で、ステップは次の最小化で決まる。

  min |J δ + r|² + λ |D δ|²（D は各列のノルムから作る対角の尺度。SciPy 1.18 の既定）

**命題1（書き換えた点が等式に現れない場合、C_y = 0）。** z = 0 から出発すると、Z の LM の反復は E の反復と完全に一致し、z はずっと 0 のままである。
- 証明：Z のヤコビアンは [[J_R, 0], [0, I]]。u の列は E と同じなので、尺度 D_u も同じになる。z の部分の残差は 0 で、列は単位ベクトルである。よって最小化は u と z に分かれる。z の部分は min |δz|² + λ|δz|² で δz = 0。u の部分は E と同じ式になる。∎
- Y では、u の列が [J_R; −H] になる。尺度 D_u は H の大きさだけ膨らみ、u の動きに余分な減衰がかかる。さらに δy を通して、u の動きが作図の微分 H と結び付く。尺度を使わない場合（D = I）でも、δy を先に消すと u への減衰は λ(I + HᵀH/(1+λ)) になり、作図が敏感な方向ほど動きにくい。解の集合は同じでも、反復の道筋が変わる。

**命題2（一般の場合、C_y ≠ 0）。** Z の z の動きは、[C_y; I] の列に対する正則化された補正になる。z は |C_y| に比例して小さく保たれ、反復は E に近い。Y との違いは同じく、u の列に −H が入るかどうかである。

**予測と実測（同じ出発点 60 個、k = 3、共通の範囲で判定）。**
- 命題1が当てはまる問題では、Z の当たり・外れの内訳が E と一致するはず。
- Y は、H が大きい（交点・垂線の足・外心など）ほど E から離れるはず。中点だけの問題では差が小さいはず。

結果は jssa/difficulty/common-start/ を参照。
