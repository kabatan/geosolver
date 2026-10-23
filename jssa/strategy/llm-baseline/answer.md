**Q26：LLMの公開成績との比較材料（調査完了）**

| 4基準 | 短い判定 |
| --- | --- |
| 直感に反するか | 不可。幾何の弱さは大会・モデル・分類で変わる。驚くべき一般法則とはいえない。 |
| 説明に深い理論が必要か | 不可。今回の記述集計から深い理論を要する機構は示せない。 |
| 再現性と広がり | 限定。保存済みの公開反復から再集計可能だが、重なりが小さく、独自のseed追試はしていない。 |
| solverならではか | 不可。公開LLM成績の集計自体はsolver固有の成果ではない。 |

**Aの分析の核としては不可。主軸（solverの凄さ）の比較材料としては限定的に使える。** 同一問題の既存成績は並べられるが、「現代のLLMが苦手な幾何をsolverが圧倒する」という主張は支えない。入力・予算・採点条件を揃えた直接対決でもない。

LLMデータ取得日：2026-10-23 JST。再開・照合・報告完了：2026-10-24 JST。前担当の取得済みファイルを継承し、不足分を取得した。solverの新規実行・APIでのLLM評価は行っていない。

**取得範囲と方法**

各大会について前担当が選んだGPT-5.2 (high)と、2025年はDeepSeek-R1、2026年はDeepSeek-v3.2 (Think)を継承した。最新モデル全体や全公開モデルを代表する標本ではない。年をまたぐDeepSeekの差にはモデル変更が含まれる。採点はMathArena公式の問題別トレース、問題番号・答え・分野はMathArena公式Hugging Faceを使う。

| 大会 | 問題 | モデル | 問題×モデル | 採点回数 | 一次資料URL |
| --- | --- | --- | --- | --- | --- |
| AIME 2025 | 30 | 2 | 60 | 240 | [採点](https://matharena.ai/?comp=aime--aime_2025&view=problem) / [問題・分類](https://huggingface.co/datasets/MathArena/aime_2025) |
| HMMT 2月 2025 | 30 | 2 | 60 | 240 | [採点](https://matharena.ai/?comp=hmmt--hmmt_feb_2025&view=problem) / [問題・分類](https://huggingface.co/datasets/MathArena/hmmt_feb_2025) |
| AIME 2026 | 30 | 2 | 60 | 240 | [採点](https://matharena.ai/?comp=aime--aime_2026&view=problem) / [問題・分類](https://huggingface.co/datasets/MathArena/aime_2026) |
| HMMT 2月 2026 | 33 | 2 | 66 | 264 | [採点](https://matharena.ai/?comp=hmmt--hmmt_feb_2026&view=problem) / [問題・分類](https://huggingface.co/datasets/MathArena/hmmt_feb_2026) |

合計は123問・246組・984回。全組で4回の正誤を取得し、モデル×大会の全8集計が公式順位表の丸め値と一致した。各問の正答率は正解回数/4、集合の正答率は正解回数合計/試行数合計。全問の反復数が同じなので問題ごとの正答率の単純平均とも一致する。「4回のうち一度でも正解する率」ではない。数値の直接URL・正誤ベクトル・取得応答のSHA-256は[llm_per_problem.csv](llm_per_problem.csv)、採点タブの抜粋は[trace-summaries.jsonl](trace-summaries.jsonl)に残した（集計元は上表の一次資料）。

MathArenaは各問題を反復評価し、最終答えを採点する。現行の説明ではSymPyによる答えの照合、形式の修正要求、採点の不一致の人手確認を用いる。ここでは公開済みの最終採点を採用し、推論全文や採点判断の独自再審査はしていない。個別モデルのtemperature・トークン上限・プロンプトの完全な履歴は取得していない。[公式の評価・採点手順（Appendix A.1–A.2）](https://arxiv.org/html/2605.00674v1)

**幾何と幾何以外の正答率差**

差は「幾何 − 幾何以外」のパーセントポイント（pp）。負ならこの集合では幾何の成績が低い。公開分類がある大会はGeometryタグを含む問題を幾何とし、複数タグでも1問として一度だけ数えた。その他はその補集合。AIME 2026は取得した公式データに分野列がなく、問題文による手分類を使った（下記）。

| 大会 | モデル | 幾何/他の問題数 | 幾何：正解/試行 | 他：正解/試行 | 差 pp | 採点・分類URL |
| --- | --- | --- | --- | --- | --- | --- |
| AIME 2025 | DeepSeek-R1 | 8/22 | 27/32（84.38%） | 57/88（64.77%） | +19.60 | [採点](https://matharena.ai/?comp=aime--aime_2025&view=problem) / [分類元](https://datasets-server.huggingface.co/first-rows?dataset=MathArena%2Faime_2025&config=default&split=train) |
| AIME 2025 | GPT-5.2 (high) | 8/22 | 32/32（100.00%） | 88/88（100.00%） | +0.00 | [採点](https://matharena.ai/?comp=aime--aime_2025&view=problem) / [分類元](https://datasets-server.huggingface.co/first-rows?dataset=MathArena%2Faime_2025&config=default&split=train) |
| HMMT 2月 2025 | DeepSeek-R1 | 11/19 | 22/44（50.00%） | 28/76（36.84%） | +13.16 | [採点](https://matharena.ai/?comp=hmmt--hmmt_feb_2025&view=problem) / [分類元](https://datasets-server.huggingface.co/first-rows?dataset=MathArena%2Fhmmt_feb_2025&config=default&split=train) |
| HMMT 2月 2025 | GPT-5.2 (high) | 11/19 | 42/44（95.45%） | 76/76（100.00%） | -4.55 | [採点](https://matharena.ai/?comp=hmmt--hmmt_feb_2025&view=problem) / [分類元](https://datasets-server.huggingface.co/first-rows?dataset=MathArena%2Fhmmt_feb_2025&config=default&split=train) |
| AIME 2026 | DeepSeek-v3.2 (Think) | 10/20 | 39/40（97.50%） | 74/80（92.50%） | +5.00 | [採点](https://matharena.ai/?comp=aime--aime_2026&view=problem) / [分類元](https://datasets-server.huggingface.co/first-rows?dataset=MathArena%2Faime_2026&config=default&split=train) |
| AIME 2026 | GPT-5.2 (high) | 10/20 | 39/40（97.50%） | 79/80（98.75%） | -1.25 | [採点](https://matharena.ai/?comp=aime--aime_2026&view=problem) / [分類元](https://datasets-server.huggingface.co/first-rows?dataset=MathArena%2Faime_2026&config=default&split=train) |
| HMMT 2月 2026 | DeepSeek-v3.2 (Think) | 12/21 | 38/48（79.17%） | 73/84（86.90%） | -7.74 | [採点](https://matharena.ai/?comp=hmmt--hmmt_feb_2026&view=problem) / [分類元](https://datasets-server.huggingface.co/first-rows?dataset=MathArena%2Fhmmt_feb_2026&config=default&split=train) |
| HMMT 2月 2026 | GPT-5.2 (high) | 12/21 | 47/48（97.92%） | 81/84（96.43%） | +1.49 | [採点](https://matharena.ai/?comp=hmmt--hmmt_feb_2026&view=problem) / [分類元](https://datasets-server.huggingface.co/first-rows?dataset=MathArena%2Fhmmt_feb_2026&config=default&split=train) |

**この標本では「LLM一般が幾何で弱い」とはいえない。** 2025年のDeepSeek-R1は両大会とも幾何側の正答率が高い。GPT-5.2の差は小さく、正負が大会によって変わる。問題難度・分野構成を統制していないため、分野そのものの因果効果でもない。各問の反復を別々の独立問題とみなした有意差検定はしていない（上表の一次資料と[geometry_gap.csv](geometry_gap.csv)）。

分類への依存を確認するため、HMMTは大会のGeometry部門でも集計した。MathArenaの2026年版には個人戦に加えTeamの数値回答用改題が含まれるので、個人戦だけの比較も併記する。元の[Geometry部門](https://hmmt-archive.s3.amazonaws.com/tournaments/2026/feb/geo/problems.pdf)と[Team部門](https://hmmt-archive.s3.amazonaws.com/tournaments/2026/feb/team/problems.pdf)は大会公式資料。

| 大会 | モデル | 分け方 | 幾何：正解/試行 | 他：正解/試行 | 差 pp | 一次資料URL |
| --- | --- | --- | --- | --- | --- | --- |
| HMMT 2月 2025 | DeepSeek-R1 | Geometry部門 / 公開セットの他全問 | 22/40（55.00%） | 28/80（35.00%） | +20.00 | [MathArena](https://matharena.ai/?comp=hmmt--hmmt_feb_2025&view=problem) |
| HMMT 2月 2025 | GPT-5.2 (high) | Geometry部門 / 公開セットの他全問 | 38/40（95.00%） | 80/80（100.00%） | -5.00 | [MathArena](https://matharena.ai/?comp=hmmt--hmmt_feb_2025&view=problem) |
| HMMT 2月 2026 | DeepSeek-v3.2 (Think) | Geometry部門 / 公開セットの他全問 | 37/40（92.50%） | 74/92（80.43%） | +12.07 | [MathArena](https://matharena.ai/?comp=hmmt--hmmt_feb_2026&view=problem) |
| HMMT 2月 2026 | DeepSeek-v3.2 (Think) | Geometry部門 / AN・C部門のみ | 37/40（92.50%） | 65/80（81.25%） | +11.25 | [MathArena](https://matharena.ai/?comp=hmmt--hmmt_feb_2026&view=problem) |
| HMMT 2月 2026 | DeepSeek-v3.2 (Think) | Geometryタグあり / タグなし（個人戦のみ） | 38/48（79.17%） | 64/72（88.89%） | -9.72 | [MathArena](https://matharena.ai/?comp=hmmt--hmmt_feb_2026&view=problem) |
| HMMT 2月 2026 | GPT-5.2 (high) | Geometry部門 / 公開セットの他全問 | 40/40（100.00%） | 88/92（95.65%） | +4.35 | [MathArena](https://matharena.ai/?comp=hmmt--hmmt_feb_2026&view=problem) |
| HMMT 2月 2026 | GPT-5.2 (high) | Geometry部門 / AN・C部門のみ | 40/40（100.00%） | 76/80（95.00%） | +5.00 | [MathArena](https://matharena.ai/?comp=hmmt--hmmt_feb_2026&view=problem) |
| HMMT 2月 2026 | GPT-5.2 (high) | Geometryタグあり / タグなし（個人戦のみ） | 47/48（97.92%） | 69/72（95.83%） | +2.08 | [MathArena](https://matharena.ai/?comp=hmmt--hmmt_feb_2026&view=problem) |

HMMT 2026のDeepSeek-v3.2では、Geometryタグを含むC7・C8が合計1/8回正解で、Geometry部門の37/40回正解と大きく異なる。全公開問題での差はタグ分類だと−7.74 pp、部門分類だと+12.07 pp。個人戦だけでもそれぞれ−9.72 pp、+11.25 ppとなり、符号の逆転はTeamの追加だけでは説明できない。[C7の採点](https://matharena.ai/trace?comp=hmmt--hmmt_feb_2026&model=DeepSeek-v3.2+%28Think%29&problem_index=16&run=1&problem_name=C7&model_name=DeepSeek-v3.2+%28Think%29)、[C8の採点](https://matharena.ai/trace?comp=hmmt--hmmt_feb_2026&model=DeepSeek-v3.2+%28Think%29&problem_index=17&run=1&problem_name=C8&model_name=DeepSeek-v3.2+%28Think%29)、[大会別表](https://matharena.ai/?comp=hmmt--hmmt_feb_2026&view=problem)

AIME 2026の手分類はI-3・5・10・12・14、II-3・6・8・10・12を幾何とした。長さ・角・接触・図形の面積を本質とするものを含め、球・四面体の空間幾何も含む。格子上の数え上げは組合せとして除外した。境界例のII-6（円と放物線）を幾何から外しても、DeepSeek-v3.2の差は+4.37 pp、GPT-5.2は−1.59 ppで、主な読み取りは変わらない。前担当の分類を継承し、再開時に問題文を読み確認した事後的な分類であり、事前登録ではない。[問題文](https://huggingface.co/datasets/MathArena/aime_2026)、[採点](https://matharena.ai/?comp=aime--aime_2026&view=problem)、全件の分類理由は[problem_metadata.csv](problem_metadata.csv)。

過去のMathArena論文は、より広い大会集合で強いモデルの幾何の成績が低いと報告している。例としてGPT-5 (high)は幾何81.1%、代数100.0%、組合せ91.3%、整数94.0%。これは別のモデル・大会構成・複数タグ別平均であり、今回の「幾何対その補集合」と同じ指標ではない。この先行報告を今回の一致問題の成績として流用できない。[MathArena 2025論文、Table 8](https://arxiv.org/html/2505.23281v2)

**本研究との重なり**

集合は既存manifest/CSVのIDから固定した。AIME Iの第n問をMathArenaのn、IIの第n問を15+nに対応させた。HMMT Geometryの第n問は20+n、公開表のG1〜G10とも照合した。番号だけを横断して結合せず、大会・年・部門を含める。

| 研究集合 | 全問 | AIME 2025 | HMMT 2月 2025 | AIME 2026 | HMMT 2月 2026 | 一致合計 | 研究側出典URL |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 開発群 | 323 | 7 | 9 | 0 | 0 | 16 | [集合ID](https://github.com/kabatan/geosolver/blob/d87b987c84fec2f5278cf7ab609700ff9ff43d11/jssa/difficulty/ghost-1023/human_feat.csv) |
| 2026年群 | 20 | 0 | 0 | 0 | 10 | 10 | [集合ID](https://github.com/kabatan/geosolver/blob/8930f5d00bbd50b1a6b80bdb0d1630fea001cb3c/jssa/difficulty/new2026-predict/predictions.csv) |
| 未使用群（選定済み） | 54 | 0 | 0 | 0 | 0 | 0 | [集合ID](https://github.com/kabatan/geosolver/blob/2b76ab7dfaa09a364c26236d3924fc28ed05f8a8/jssa/difficulty/unseen-1983/manifest.json) |

重なりの相手は上の4大会の[公式問題データ](https://huggingface.co/MathArena)。全IDと一致・不一致は[crosswalk.csv](crosswalk.csv)、一致問題の番号・答え・出力変換は[matched_problems.csv](matched_problems.csv)。2026年群にはAIMEが含まれず、不一致分はHMMT GutsとJMO。未使用群のIDの年は今回の4大会と重ならない。この0件は「調べた4大会との一致がない」という意味で、他の公開資料にLLM成績が一切ないことを意味しない。未使用群はmanifestの所属IDだけを利用し、solver結果・封印データは参照していない。

**一致問題でのsolverとの比較**

完成solverの成績を確認できたのは開発群の一致問題。凍結版の本計測の既存記録を使い、問題ごとのseed 0・1・2を集計した。2026年群について、この作業ツリーで得られた問題別の数値は局所探索のpで、完成solverの対応する問題別記録は未取得。本文にある20問全体の成績を一致10問へ割り当ててはいない。

| 研究集合・大会 | 一致問題 | モデル | LLM 正解/試行 | 完成solver 正解/試行 | 出典URL |
| --- | --- | --- | --- | --- | --- |
| 開発群・AIME 2025 | 7 | DeepSeek-R1 | 27/28（96.43%） | 21/21（100.00%） | [LLM](https://matharena.ai/?comp=aime--aime_2025&view=problem) / [solver](https://github.com/kabatan/geosolver/blob/cdea8f35661968d32034d68a910d946ec91966e9/jssa/results/stage-profile-20261023/per-case.csv) |
| 開発群・AIME 2025 | 7 | GPT-5.2 (high) | 28/28（100.00%） | 21/21（100.00%） | [LLM](https://matharena.ai/?comp=aime--aime_2025&view=problem) / [solver](https://github.com/kabatan/geosolver/blob/cdea8f35661968d32034d68a910d946ec91966e9/jssa/results/stage-profile-20261023/per-case.csv) |
| 開発群・HMMT 2月 2025 | 9 | DeepSeek-R1 | 22/36（61.11%） | 27/27（100.00%） | [LLM](https://matharena.ai/?comp=hmmt--hmmt_feb_2025&view=problem) / [solver](https://github.com/kabatan/geosolver/blob/cdea8f35661968d32034d68a910d946ec91966e9/jssa/results/stage-profile-20261023/per-case.csv) |
| 開発群・HMMT 2月 2025 | 9 | GPT-5.2 (high) | 35/36（97.22%） | 27/27（100.00%） | [LLM](https://matharena.ai/?comp=hmmt--hmmt_feb_2025&view=problem) / [solver](https://github.com/kabatan/geosolver/blob/cdea8f35661968d32034d68a910d946ec91966e9/jssa/results/stage-profile-20261023/per-case.csv) |
| 2026年群・HMMT 2月 2026 | 10 | DeepSeek-v3.2 (Think) | 37/40（92.50%） | 未取得 | [LLM](https://matharena.ai/?comp=hmmt--hmmt_feb_2026&view=problem) |
| 2026年群・HMMT 2月 2026 | 10 | GPT-5.2 (high) | 40/40（100.00%） | 未取得 | [LLM](https://matharena.ai/?comp=hmmt--hmmt_feb_2026&view=problem) |

開発群の一致16問をまとめると、完成solverは48/48回（100.00%）、GPT-5.2は63/64回（98.44%）、DeepSeek-R1は49/64回（76.56%）。solverが旧モデルの不正解例を解けることは示せるが、GPT-5.2との差は全反復を合わせても1件で、優位性の強い証拠にはならない。[solverの既存記録](https://github.com/kabatan/geosolver/blob/cdea8f35661968d32034d68a910d946ec91966e9/jssa/results/stage-profile-20261023/per-case.csv)、[AIME採点](https://matharena.ai/?comp=aime--aime_2025&view=problem)、[HMMT採点](https://matharena.ai/?comp=hmmt--hmmt_feb_2025&view=problem)

以下は一致全問題。LLM欄は正解/4回。DeepSeek欄は2025年がR1、2026年がv3.2 (Think)。局所探索欄は既存実験のhits/実際のstartsで、完成solverの正答率とは別の量である。開発群は時間上限等でstartsが200未満の問題や、探索変数がない別経路もあるため、一律に200としない。各数値はセルのリンク先が出典。

| 問題（問題文URL） | GPT-5.2 | DeepSeek | 完成solver | 局所探索（参考） |
| --- | --- | --- | --- | --- |
| [AIME-2025-I-02](https://artofproblemsolving.com/wiki/index.php/2025_AIME_I_Problems/Problem_2) | [4/4](https://matharena.ai/trace?comp=aime--aime_2025&model=GPT-5.2+%28high%29&problem_index=1&run=1&problem_name=2&model_name=GPT-5.2+%28high%29) | [4/4](https://matharena.ai/trace?comp=aime--aime_2025&model=DeepSeek-R1&problem_index=1&run=1&problem_name=2&model_name=DeepSeek-R1) | [3/3](https://github.com/kabatan/geosolver/blob/cdea8f35661968d32034d68a910d946ec91966e9/jssa/results/stage-profile-20261023/per-case.csv) | [200/200](https://github.com/kabatan/geosolver/blob/d87b987c84fec2f5278cf7ab609700ff9ff43d11/jssa/difficulty/minima/basins-323.csv) |
| [AIME-2025-I-06](https://artofproblemsolving.com/wiki/index.php/2025_AIME_I_Problems/Problem_6) | [4/4](https://matharena.ai/trace?comp=aime--aime_2025&model=GPT-5.2+%28high%29&problem_index=5&run=1&problem_name=6&model_name=GPT-5.2+%28high%29) | [4/4](https://matharena.ai/trace?comp=aime--aime_2025&model=DeepSeek-R1&problem_index=5&run=1&problem_name=6&model_name=DeepSeek-R1) | [3/3](https://github.com/kabatan/geosolver/blob/cdea8f35661968d32034d68a910d946ec91966e9/jssa/results/stage-profile-20261023/per-case.csv) | [53/200](https://github.com/kabatan/geosolver/blob/d87b987c84fec2f5278cf7ab609700ff9ff43d11/jssa/difficulty/minima/basins-323.csv) |
| [AIME-2025-II-01](https://artofproblemsolving.com/wiki/index.php/2025_AIME_II_Problems/Problem_1) | [4/4](https://matharena.ai/trace?comp=aime--aime_2025&model=GPT-5.2+%28high%29&problem_index=15&run=1&problem_name=16&model_name=GPT-5.2+%28high%29) | [4/4](https://matharena.ai/trace?comp=aime--aime_2025&model=DeepSeek-R1&problem_index=15&run=1&problem_name=16&model_name=DeepSeek-R1) | [3/3](https://github.com/kabatan/geosolver/blob/cdea8f35661968d32034d68a910d946ec91966e9/jssa/results/stage-profile-20261023/per-case.csv) | [11/200](https://github.com/kabatan/geosolver/blob/d87b987c84fec2f5278cf7ab609700ff9ff43d11/jssa/difficulty/minima/basins-323.csv) |
| [AIME-2025-II-05](https://artofproblemsolving.com/wiki/index.php/2025_AIME_II_Problems/Problem_5) | [4/4](https://matharena.ai/trace?comp=aime--aime_2025&model=GPT-5.2+%28high%29&problem_index=19&run=1&problem_name=20&model_name=GPT-5.2+%28high%29) | [3/4](https://matharena.ai/trace?comp=aime--aime_2025&model=DeepSeek-R1&problem_index=19&run=1&problem_name=20&model_name=DeepSeek-R1) | [3/3](https://github.com/kabatan/geosolver/blob/cdea8f35661968d32034d68a910d946ec91966e9/jssa/results/stage-profile-20261023/per-case.csv) | [196/200](https://github.com/kabatan/geosolver/blob/d87b987c84fec2f5278cf7ab609700ff9ff43d11/jssa/difficulty/minima/basins-323.csv) |
| [AIME-2025-II-06](https://artofproblemsolving.com/wiki/index.php/2025_AIME_II_Problems/Problem_6) | [4/4](https://matharena.ai/trace?comp=aime--aime_2025&model=GPT-5.2+%28high%29&problem_index=20&run=1&problem_name=21&model_name=GPT-5.2+%28high%29) | [4/4](https://matharena.ai/trace?comp=aime--aime_2025&model=DeepSeek-R1&problem_index=20&run=1&problem_name=21&model_name=DeepSeek-R1) | [3/3](https://github.com/kabatan/geosolver/blob/cdea8f35661968d32034d68a910d946ec91966e9/jssa/results/stage-profile-20261023/per-case.csv) | [193/200](https://github.com/kabatan/geosolver/blob/d87b987c84fec2f5278cf7ab609700ff9ff43d11/jssa/difficulty/minima/basins-323.csv) |
| [AIME-2025-II-12](https://artofproblemsolving.com/wiki/index.php/2025_AIME_II_Problems/Problem_12) | [4/4](https://matharena.ai/trace?comp=aime--aime_2025&model=GPT-5.2+%28high%29&problem_index=26&run=1&problem_name=27&model_name=GPT-5.2+%28high%29) | [4/4](https://matharena.ai/trace?comp=aime--aime_2025&model=DeepSeek-R1&problem_index=26&run=1&problem_name=27&model_name=DeepSeek-R1) | [3/3](https://github.com/kabatan/geosolver/blob/cdea8f35661968d32034d68a910d946ec91966e9/jssa/results/stage-profile-20261023/per-case.csv) | [200/200](https://github.com/kabatan/geosolver/blob/d87b987c84fec2f5278cf7ab609700ff9ff43d11/jssa/difficulty/minima/basins-323.csv) |
| [AIME-2025-II-14](https://artofproblemsolving.com/wiki/index.php/2025_AIME_II_Problems/Problem_14) | [4/4](https://matharena.ai/trace?comp=aime--aime_2025&model=GPT-5.2+%28high%29&problem_index=28&run=1&problem_name=29&model_name=GPT-5.2+%28high%29) | [4/4](https://matharena.ai/trace?comp=aime--aime_2025&model=DeepSeek-R1&problem_index=28&run=1&problem_name=29&model_name=DeepSeek-R1) | [3/3](https://github.com/kabatan/geosolver/blob/cdea8f35661968d32034d68a910d946ec91966e9/jssa/results/stage-profile-20261023/per-case.csv) | [72/200](https://github.com/kabatan/geosolver/blob/d87b987c84fec2f5278cf7ab609700ff9ff43d11/jssa/difficulty/minima/basins-323.csv) |
| [HMMT-2025-FEB-GEO-01](https://hmmt-archive.s3.amazonaws.com/tournaments/2025/feb/geo/problems.pdf) | [4/4](https://matharena.ai/trace?comp=hmmt--hmmt_feb_2025&model=GPT-5.2+%28high%29&problem_index=20&run=1&problem_name=G1&model_name=GPT-5.2+%28high%29) | [4/4](https://matharena.ai/trace?comp=hmmt--hmmt_feb_2025&model=DeepSeek-R1&problem_index=20&run=1&problem_name=G1&model_name=DeepSeek-R1) | [3/3](https://github.com/kabatan/geosolver/blob/cdea8f35661968d32034d68a910d946ec91966e9/jssa/results/stage-profile-20261023/per-case.csv) | [0/200](https://github.com/kabatan/geosolver/blob/d87b987c84fec2f5278cf7ab609700ff9ff43d11/jssa/difficulty/minima/basins-323.csv) |
| [HMMT-2025-FEB-GEO-02](https://hmmt-archive.s3.amazonaws.com/tournaments/2025/feb/geo/problems.pdf) | [4/4](https://matharena.ai/trace?comp=hmmt--hmmt_feb_2025&model=GPT-5.2+%28high%29&problem_index=21&run=1&problem_name=G2&model_name=GPT-5.2+%28high%29) | [4/4](https://matharena.ai/trace?comp=hmmt--hmmt_feb_2025&model=DeepSeek-R1&problem_index=21&run=1&problem_name=G2&model_name=DeepSeek-R1) | [3/3](https://github.com/kabatan/geosolver/blob/cdea8f35661968d32034d68a910d946ec91966e9/jssa/results/stage-profile-20261023/per-case.csv) | [67/68](https://github.com/kabatan/geosolver/blob/d87b987c84fec2f5278cf7ab609700ff9ff43d11/jssa/difficulty/minima/basins-323.csv) |
| [HMMT-2025-FEB-GEO-03](https://hmmt-archive.s3.amazonaws.com/tournaments/2025/feb/geo/problems.pdf) | [4/4](https://matharena.ai/trace?comp=hmmt--hmmt_feb_2025&model=GPT-5.2+%28high%29&problem_index=22&run=1&problem_name=G3&model_name=GPT-5.2+%28high%29) | [4/4](https://matharena.ai/trace?comp=hmmt--hmmt_feb_2025&model=DeepSeek-R1&problem_index=22&run=1&problem_name=G3&model_name=DeepSeek-R1) | [3/3](https://github.com/kabatan/geosolver/blob/cdea8f35661968d32034d68a910d946ec91966e9/jssa/results/stage-profile-20261023/per-case.csv) | [20/200](https://github.com/kabatan/geosolver/blob/d87b987c84fec2f5278cf7ab609700ff9ff43d11/jssa/difficulty/minima/basins-323.csv) |
| [HMMT-2025-FEB-GEO-04](https://hmmt-archive.s3.amazonaws.com/tournaments/2025/feb/geo/problems.pdf) | [4/4](https://matharena.ai/trace?comp=hmmt--hmmt_feb_2025&model=GPT-5.2+%28high%29&problem_index=23&run=1&problem_name=G4&model_name=GPT-5.2+%28high%29) | [0/4](https://matharena.ai/trace?comp=hmmt--hmmt_feb_2025&model=DeepSeek-R1&problem_index=23&run=1&problem_name=G4&model_name=DeepSeek-R1) | [3/3](https://github.com/kabatan/geosolver/blob/cdea8f35661968d32034d68a910d946ec91966e9/jssa/results/stage-profile-20261023/per-case.csv) | [133/200](https://github.com/kabatan/geosolver/blob/d87b987c84fec2f5278cf7ab609700ff9ff43d11/jssa/difficulty/minima/basins-323.csv) |
| [HMMT-2025-FEB-GEO-05](https://hmmt-archive.s3.amazonaws.com/tournaments/2025/feb/geo/problems.pdf) | [3/4](https://matharena.ai/trace?comp=hmmt--hmmt_feb_2025&model=GPT-5.2+%28high%29&problem_index=24&run=1&problem_name=G5&model_name=GPT-5.2+%28high%29) | [0/4](https://matharena.ai/trace?comp=hmmt--hmmt_feb_2025&model=DeepSeek-R1&problem_index=24&run=1&problem_name=G5&model_name=DeepSeek-R1) | [3/3](https://github.com/kabatan/geosolver/blob/cdea8f35661968d32034d68a910d946ec91966e9/jssa/results/stage-profile-20261023/per-case.csv) | [109/200](https://github.com/kabatan/geosolver/blob/d87b987c84fec2f5278cf7ab609700ff9ff43d11/jssa/difficulty/minima/basins-323.csv) |
| [HMMT-2025-FEB-GEO-06](https://hmmt-archive.s3.amazonaws.com/tournaments/2025/feb/geo/problems.pdf) | [4/4](https://matharena.ai/trace?comp=hmmt--hmmt_feb_2025&model=GPT-5.2+%28high%29&problem_index=25&run=1&problem_name=G6&model_name=GPT-5.2+%28high%29) | [4/4](https://matharena.ai/trace?comp=hmmt--hmmt_feb_2025&model=DeepSeek-R1&problem_index=25&run=1&problem_name=G6&model_name=DeepSeek-R1) | [3/3](https://github.com/kabatan/geosolver/blob/cdea8f35661968d32034d68a910d946ec91966e9/jssa/results/stage-profile-20261023/per-case.csv) | [198/200](https://github.com/kabatan/geosolver/blob/d87b987c84fec2f5278cf7ab609700ff9ff43d11/jssa/difficulty/minima/basins-323.csv) |
| [HMMT-2025-FEB-GEO-07](https://hmmt-archive.s3.amazonaws.com/tournaments/2025/feb/geo/problems.pdf) | [4/4](https://matharena.ai/trace?comp=hmmt--hmmt_feb_2025&model=GPT-5.2+%28high%29&problem_index=26&run=1&problem_name=G7&model_name=GPT-5.2+%28high%29) | [3/4](https://matharena.ai/trace?comp=hmmt--hmmt_feb_2025&model=DeepSeek-R1&problem_index=26&run=1&problem_name=G7&model_name=DeepSeek-R1) | [3/3](https://github.com/kabatan/geosolver/blob/cdea8f35661968d32034d68a910d946ec91966e9/jssa/results/stage-profile-20261023/per-case.csv) | [128/200](https://github.com/kabatan/geosolver/blob/d87b987c84fec2f5278cf7ab609700ff9ff43d11/jssa/difficulty/minima/basins-323.csv) |
| [HMMT-2025-FEB-GEO-08](https://hmmt-archive.s3.amazonaws.com/tournaments/2025/feb/geo/problems.pdf) | [4/4](https://matharena.ai/trace?comp=hmmt--hmmt_feb_2025&model=GPT-5.2+%28high%29&problem_index=27&run=1&problem_name=G8&model_name=GPT-5.2+%28high%29) | [3/4](https://matharena.ai/trace?comp=hmmt--hmmt_feb_2025&model=DeepSeek-R1&problem_index=27&run=1&problem_name=G8&model_name=DeepSeek-R1) | [3/3](https://github.com/kabatan/geosolver/blob/cdea8f35661968d32034d68a910d946ec91966e9/jssa/results/stage-profile-20261023/per-case.csv) | [89/200](https://github.com/kabatan/geosolver/blob/d87b987c84fec2f5278cf7ab609700ff9ff43d11/jssa/difficulty/minima/basins-323.csv) |
| [HMMT-2025-FEB-GEO-09](https://hmmt-archive.s3.amazonaws.com/tournaments/2025/feb/geo/problems.pdf) | [4/4](https://matharena.ai/trace?comp=hmmt--hmmt_feb_2025&model=GPT-5.2+%28high%29&problem_index=28&run=1&problem_name=G9&model_name=GPT-5.2+%28high%29) | [0/4](https://matharena.ai/trace?comp=hmmt--hmmt_feb_2025&model=DeepSeek-R1&problem_index=28&run=1&problem_name=G9&model_name=DeepSeek-R1) | [3/3](https://github.com/kabatan/geosolver/blob/cdea8f35661968d32034d68a910d946ec91966e9/jssa/results/stage-profile-20261023/per-case.csv) | [174/200](https://github.com/kabatan/geosolver/blob/d87b987c84fec2f5278cf7ab609700ff9ff43d11/jssa/difficulty/minima/basins-323.csv) |
| [HMMT-2026-FEB-GEO-01](https://hmmt-archive.s3.amazonaws.com/tournaments/2026/feb/geo/problems.pdf) | [4/4](https://matharena.ai/trace?comp=hmmt--hmmt_feb_2026&model=GPT-5.2+%28high%29&problem_index=20&run=1&problem_name=G1&model_name=GPT-5.2+%28high%29) | [4/4](https://matharena.ai/trace?comp=hmmt--hmmt_feb_2026&model=DeepSeek-v3.2+%28Think%29&problem_index=20&run=1&problem_name=G1&model_name=DeepSeek-v3.2+%28Think%29) | 未取得 | [70/200](https://github.com/kabatan/geosolver/blob/c645032f51fad973d1641f11261b3f1e101a971b/jssa/difficulty/new2026-predict/outcomes.csv) |
| [HMMT-2026-FEB-GEO-02](https://hmmt-archive.s3.amazonaws.com/tournaments/2026/feb/geo/problems.pdf) | [4/4](https://matharena.ai/trace?comp=hmmt--hmmt_feb_2026&model=GPT-5.2+%28high%29&problem_index=21&run=1&problem_name=G2&model_name=GPT-5.2+%28high%29) | [4/4](https://matharena.ai/trace?comp=hmmt--hmmt_feb_2026&model=DeepSeek-v3.2+%28Think%29&problem_index=21&run=1&problem_name=G2&model_name=DeepSeek-v3.2+%28Think%29) | 未取得 | [47/200](https://github.com/kabatan/geosolver/blob/c645032f51fad973d1641f11261b3f1e101a971b/jssa/difficulty/new2026-predict/outcomes.csv) |
| [HMMT-2026-FEB-GEO-03](https://hmmt-archive.s3.amazonaws.com/tournaments/2026/feb/geo/problems.pdf) | [4/4](https://matharena.ai/trace?comp=hmmt--hmmt_feb_2026&model=GPT-5.2+%28high%29&problem_index=22&run=1&problem_name=G3&model_name=GPT-5.2+%28high%29) | [4/4](https://matharena.ai/trace?comp=hmmt--hmmt_feb_2026&model=DeepSeek-v3.2+%28Think%29&problem_index=22&run=1&problem_name=G3&model_name=DeepSeek-v3.2+%28Think%29) | 未取得 | [175/200](https://github.com/kabatan/geosolver/blob/c645032f51fad973d1641f11261b3f1e101a971b/jssa/difficulty/new2026-predict/outcomes.csv) |
| [HMMT-2026-FEB-GEO-04](https://hmmt-archive.s3.amazonaws.com/tournaments/2026/feb/geo/problems.pdf) | [4/4](https://matharena.ai/trace?comp=hmmt--hmmt_feb_2026&model=GPT-5.2+%28high%29&problem_index=23&run=1&problem_name=G4&model_name=GPT-5.2+%28high%29) | [4/4](https://matharena.ai/trace?comp=hmmt--hmmt_feb_2026&model=DeepSeek-v3.2+%28Think%29&problem_index=23&run=1&problem_name=G4&model_name=DeepSeek-v3.2+%28Think%29) | 未取得 | [198/200](https://github.com/kabatan/geosolver/blob/c645032f51fad973d1641f11261b3f1e101a971b/jssa/difficulty/new2026-predict/outcomes.csv) |
| [HMMT-2026-FEB-GEO-05](https://hmmt-archive.s3.amazonaws.com/tournaments/2026/feb/geo/problems.pdf) | [4/4](https://matharena.ai/trace?comp=hmmt--hmmt_feb_2026&model=GPT-5.2+%28high%29&problem_index=24&run=1&problem_name=G5&model_name=GPT-5.2+%28high%29) | [4/4](https://matharena.ai/trace?comp=hmmt--hmmt_feb_2026&model=DeepSeek-v3.2+%28Think%29&problem_index=24&run=1&problem_name=G5&model_name=DeepSeek-v3.2+%28Think%29) | 未取得 | [3/200](https://github.com/kabatan/geosolver/blob/c645032f51fad973d1641f11261b3f1e101a971b/jssa/difficulty/new2026-predict/outcomes.csv) |
| [HMMT-2026-FEB-GEO-06](https://hmmt-archive.s3.amazonaws.com/tournaments/2026/feb/geo/problems.pdf) | [4/4](https://matharena.ai/trace?comp=hmmt--hmmt_feb_2026&model=GPT-5.2+%28high%29&problem_index=25&run=1&problem_name=G6&model_name=GPT-5.2+%28high%29) | [3/4](https://matharena.ai/trace?comp=hmmt--hmmt_feb_2026&model=DeepSeek-v3.2+%28Think%29&problem_index=25&run=1&problem_name=G6&model_name=DeepSeek-v3.2+%28Think%29) | 未取得 | [195/200](https://github.com/kabatan/geosolver/blob/c645032f51fad973d1641f11261b3f1e101a971b/jssa/difficulty/new2026-predict/outcomes.csv) |
| [HMMT-2026-FEB-GEO-07](https://hmmt-archive.s3.amazonaws.com/tournaments/2026/feb/geo/problems.pdf) | [4/4](https://matharena.ai/trace?comp=hmmt--hmmt_feb_2026&model=GPT-5.2+%28high%29&problem_index=26&run=1&problem_name=G7&model_name=GPT-5.2+%28high%29) | [4/4](https://matharena.ai/trace?comp=hmmt--hmmt_feb_2026&model=DeepSeek-v3.2+%28Think%29&problem_index=26&run=1&problem_name=G7&model_name=DeepSeek-v3.2+%28Think%29) | 未取得 | [1/200](https://github.com/kabatan/geosolver/blob/c645032f51fad973d1641f11261b3f1e101a971b/jssa/difficulty/new2026-predict/outcomes.csv) |
| [HMMT-2026-FEB-GEO-08](https://hmmt-archive.s3.amazonaws.com/tournaments/2026/feb/geo/problems.pdf) | [4/4](https://matharena.ai/trace?comp=hmmt--hmmt_feb_2026&model=GPT-5.2+%28high%29&problem_index=27&run=1&problem_name=G8&model_name=GPT-5.2+%28high%29) | [4/4](https://matharena.ai/trace?comp=hmmt--hmmt_feb_2026&model=DeepSeek-v3.2+%28Think%29&problem_index=27&run=1&problem_name=G8&model_name=DeepSeek-v3.2+%28Think%29) | 未取得 | [195/200](https://github.com/kabatan/geosolver/blob/c645032f51fad973d1641f11261b3f1e101a971b/jssa/difficulty/new2026-predict/outcomes.csv) |
| [HMMT-2026-FEB-GEO-09](https://hmmt-archive.s3.amazonaws.com/tournaments/2026/feb/geo/problems.pdf) | [4/4](https://matharena.ai/trace?comp=hmmt--hmmt_feb_2026&model=GPT-5.2+%28high%29&problem_index=28&run=1&problem_name=G9&model_name=GPT-5.2+%28high%29) | [2/4](https://matharena.ai/trace?comp=hmmt--hmmt_feb_2026&model=DeepSeek-v3.2+%28Think%29&problem_index=28&run=1&problem_name=G9&model_name=DeepSeek-v3.2+%28Think%29) | 未取得 | [47/200](https://github.com/kabatan/geosolver/blob/c645032f51fad973d1641f11261b3f1e101a971b/jssa/difficulty/new2026-predict/outcomes.csv) |
| [HMMT-2026-FEB-GEO-10](https://hmmt-archive.s3.amazonaws.com/tournaments/2026/feb/geo/problems.pdf) | [4/4](https://matharena.ai/trace?comp=hmmt--hmmt_feb_2026&model=GPT-5.2+%28high%29&problem_index=29&run=1&problem_name=G10&model_name=GPT-5.2+%28high%29) | [4/4](https://matharena.ai/trace?comp=hmmt--hmmt_feb_2026&model=DeepSeek-v3.2+%28Think%29&problem_index=29&run=1&problem_name=G10&model_name=DeepSeek-v3.2+%28Think%29) | 未取得 | [89/200](https://github.com/kabatan/geosolver/blob/c645032f51fad973d1641f11261b3f1e101a971b/jssa/difficulty/new2026-predict/outcomes.csv) |

例えばHMMT 2025のG4・G5・G9はR1がいずれも0/4回、完成solverがいずれも3/3回。しかしGPT-5.2はそれぞれ4/4・3/4・4/4回。現代のLLM全般が解けない問題という扱いにはしない（上表の問題別URL）。

**比較の条件と、主軸に使える範囲**

| 論点 | 今回確認できること・制約 |
| --- | --- |
| 問題の同一性 | 大会・年・部門・番号と答えの表記を照合。入力文からDSLへの完全な意味同値性監査は今回行っていない。 |
| 入力 | LLMは自然言語、solverは作図と条件に整理済みのDSL。DSLを作る作業・時間は完成solverの実行時間に含まれない。 |
| 採点対象 | LLMは大会の指定した最終出力。solverは幾何量の式または値の集合。AIMEの出力形式の変換が必要なものがある。 |
| 実行予算 | 完成solverの本計測は1コア・各180秒上限・3 seed。LLMは公開設定の4反復。計算機・時間・トークン・費用を揃えていない。LLMの対応問題の実時間も未取得なので速度優位を主張しない。 |
| 開発・学習の影響 | 開発群はsolverの開発に使用済み。GPT-5.2の2025年大会成績にはMathArenaの「大会後リリース」警告がある。警告なしも学習汚染の完全否定ではない。 |
| 統計的な意味 | 小さい一致集合の記述比較。少数の反復で観測した満点を普遍的な成功確率とみなさず、差の有意性や一般化は主張しない。 |

solverの実行条件は[本計測の説明](../../results/stage-profile-20261023/per-case-README.md)と[補足S2.2](../../draft/supplement-v10.md)、モデルの警告は下表の一次資料で確認した。個々のLLM実行設定は完全には回収できていない。

| 大会 | モデル | 大会後リリース警告 | 公式全体正答率 | 一次資料URL |
| --- | --- | --- | --- | --- |
| AIME 2025 | GPT-5.2 (high) | あり | 100.00% | [公式表](https://matharena.ai/?comp=aime--aime_2025&view=problem) |
| AIME 2025 | DeepSeek-R1 | なし | 70.00% | [公式表](https://matharena.ai/?comp=aime--aime_2025&view=problem) |
| HMMT 2月 2025 | GPT-5.2 (high) | あり | 98.33% | [公式表](https://matharena.ai/?comp=hmmt--hmmt_feb_2025&view=problem) |
| HMMT 2月 2025 | DeepSeek-R1 | なし | 41.67% | [公式表](https://matharena.ai/?comp=hmmt--hmmt_feb_2025&view=problem) |
| AIME 2026 | GPT-5.2 (high) | なし | 98.33% | [公式表](https://matharena.ai/?comp=aime--aime_2026&view=problem) |
| AIME 2026 | DeepSeek-v3.2 (Think) | なし | 94.17% | [公式表](https://matharena.ai/?comp=aime--aime_2026&view=problem) |
| HMMT 2月 2026 | GPT-5.2 (high) | なし | 96.97% | [公式表](https://matharena.ai/?comp=hmmt--hmmt_feb_2026&view=problem) |
| HMMT 2月 2026 | DeepSeek-v3.2 (Think) | なし | 84.09% | [公式表](https://matharena.ai/?comp=hmmt--hmmt_feb_2026&view=problem) |

答えの形式が異なる一致問題は、AIME 2025 II-6が面積288/5から293、II-12が(−1+9√5)/4から19、II-14が面積104√3から104。根号・分数表記や角度単位の差も対応表に残した。solverが返す幾何量の正しさと、大会の指定出力の作成までを同一視しない。[II-6](https://artofproblemsolving.com/wiki/index.php/2025_AIME_II_Problems/Problem_6)、[II-12](https://artofproblemsolving.com/wiki/index.php/2025_AIME_II_Problems/Problem_12)、[II-14](https://artofproblemsolving.com/wiki/index.php/2025_AIME_II_Problems/Problem_14)、[MathArena公式の参照答](https://huggingface.co/datasets/MathArena/aime_2025)、[研究側との対応表](matched_problems.csv)

本文に使うなら、「公開LLM評価と重なる開発問題で、既存の完成solverの成績を併記した。旧モデルが誤る問題も解けたが、より強いモデルは同じ問題をほぼ全て正解しており、一般的なLLM優位・劣位を結論しない」まで。主軸は、明示した入力と計算条件で多様な求値問題を解く実装・検証・費用に置くのが正直である。

**未取得・取得できなかったもの**

| 項目 | 状況と報告への影響 | 出典・対象URL |
| --- | --- | --- |
| Hugging Faceのモデル指定出力抽出 | 前担当の保存応答はindex loading。タイムアウトの記述も前担当のメモにあるが、HTTPログは残っていない。モデル別出力の一括取得は完了していない。今回は公式トレースから必要な全採点を補完済み。 | [AIME出力](https://huggingface.co/datasets/MathArena/aime_2025_outputs)、[保存されたエラー](aime_2025-r1-0.json) |
| 最初のurllibアクセス | 保存ログにDNS解決失敗。後のcurl経路で公式サイト・残りの採点を取得できたため、主表の欠測にはなっていない。 | [公式サイト](https://matharena.ai/)、[fetch-log.jsonl](fetch-log.jsonl) |
| AIME 2026の公開分野ラベル | 取得したdataset schemaに列がない。手分類と境界例を外した集計を明示した。 | [公式問題データ](https://huggingface.co/datasets/MathArena/aime_2026) |
| 一致する2026年問題の完成solver成績 | 作業ツリーとREADME記載の本体側パスに、対応する問題別本計測ファイルを確認できなかった。局所pは取得済みだが代用しない。新しい実行もしていない。 | [研究集合の説明](../../difficulty/new2026/README.md)、[局所p](../../difficulty/new2026-predict/outcomes.csv) |
| 不一致問題・他モデル・他サイトのLLM個票 | 今回の大会・モデルに範囲を限定。未使用群を含め、全公開ベンチマークを網羅した探索は未実施。未取得を0%と扱わない。 | [公式データ一覧](https://huggingface.co/MathArena)、[全ID照合](crosswalk.csv) |

**保存物と再計算**

| ファイル | 内容 |
| --- | --- |
| [llm_per_problem.csv](llm_per_problem.csv) | 問題×モデルの正解数・反復数・正答率・正誤ベクトル・直接URL |
| [problem_metadata.csv](problem_metadata.csv) | 分野ラベル、手分類理由、問題文ハッシュ |
| [crosswalk.csv](crosswalk.csv)、[matched_problems.csv](matched_problems.csv) | 研究集合の全ID照合、一致問題の答えと変換 |
| [geometry_gap.csv](geometry_gap.csv) | 主分類と代替分類の正答率差、分子・分母 |
| [solver_comparison.csv](solver_comparison.csv)、[overlap_summary.csv](overlap_summary.csv) | 一致問題のLLM・完成solver・局所pを区別した比較 |
| [solver_final_runs.csv](solver_final_runs.csv) | 一致する開発問題の既存完成solver記録の抜粋 |
| [model_metadata.csv](model_metadata.csv) | モデル設定ID、大会後リリース警告、公式全体率 |
| [source_manifest.csv](source_manifest.csv)、[local_input_hashes.csv](local_input_hashes.csv) | 一次資料URL・保存ファイルのSHA-256、研究側入力の固定commit URL |
| [validation.json](validation.json) | 採点タブ・集計・ID対応・既存solver記録・リンク・サイズの照合結果 |

ネットワークなしで再集計できる。作業ツリーの.venvはないため、既存の本体repoのPython環境を使用した。追加パッケージは不要。

```bash
/home/kabatan/work/solver/.venv/bin/python jssa/strategy/llm-baseline/analyze.py
/home/kabatan/work/solver/.venv/bin/python jssa/strategy/llm-baseline/report.py
/home/kabatan/work/solver/.venv/bin/python jssa/strategy/llm-baseline/validate.py
```

analyze.pyは元データのID一意性、4反復の完全性、公式全体率との一致、研究入力と固定commitの一致を検査する。validate.pyでは保存された採点タブから正解数を別に読み直し、各分類の差、結合、完成solverの転記、保存ハッシュ、相対リンク、サイズを確認した。collect_traces.pyは公開HTMLの正誤タブだけを要約し、同じバッチを再処理しても重複行を作らない。既存trace-summaries.jsonlのretrieved_atは厳密には要約抽出時刻であり、HTTP取得時刻・LLM評価実行日時とは区別する。応答本文全体は一部のprobe以外保持せず、採点部分と元応答ハッシュを残した。

変更・生成物はこの調査フォルダ内。solver本体・実験結果・未使用問題の内容は変更していない。単一ファイル5,000,000 bytes以下を生成前・完了時に確認する。
