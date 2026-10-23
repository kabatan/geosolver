# Q28e：文献と確認範囲

このタスク中にweb検索を行い、以下の一次資料を確認した。検索結果に出たWikipedia等を根拠には使っていない。未確認の書誌・定理・適用可能性を補っていない。

| 文献 | 確認箇所 | 今回使う範囲 |
|---|---|---|
| T. Bogart, A. Jensen, D. Speyer, B. Sturmfels, R. Thomas, *Computing Tropical Varieties*, arXiv:math/0507563（2005） | [原稿PDF](https://arxiv.org/pdf/math/0507563)の冒頭・§1、初期形式、Newton多面体、prevarietyとtropical basisの区別 | 任意の生成多項式の面を列挙するだけでは理想のトロピカル化にならない。論文全体の証明を監査したわけではない |
| Anders Jensen, Anton Leykin, Josephine Yu, *Computing Tropical Curves via Homotopy Continuation*, arXiv:1408.3105（2014）；Experimental Mathematics 25(1), 83–93（2016） | [原稿PDF](https://arxiv.org/pdf/1408.3105)の§1–2、数値点からrayとmultiplicityを計算する流れ。[著者所属機関の出版記録](https://pure.au.dk/portal/en/publications/computing-tropical-curves-via-homotopy-continuation/)で誌名・年・巻頁・DOI 10.1080/10586458.2015.1037407を照合 | 複素代数曲線からトロピカル方向を数値計算する既存手段がある。元solverのLM経路に適用できる定理とはしていない |
| Cynthia Vinzant, *Real radical initial ideals*, Journal of Algebra 352(1), 392–407（2012）, DOI 10.1016/j.jalgebra.2011.11.028 | [著者の出版一覧](https://sites.math.washington.edu/~vinzant/research.html)と[出版社検索結果の抄録](https://www.sciencedirect.com/science/article/pii/S0021869311006971)。出版社本文のopenは403、本文未確認 | 実零点集合・半代数集合の対数極限と初期イデアルの関係を扱う文献として確認。正確な仮定と定理本文は未確認であり、answer.mdの導出根拠には使わない |

第1論文はmin、第2論文はmaxの約束を使う。answer.mdはε→0の付値でminを使っており、文献の方向ベクトルの符号をそのまま混ぜていない。

**未確認事項。** GeoSolverが使用する実枝・不連続なhard罰則・有限差分・適応減衰・停止条件を含め、実際に選ぶ逃避経路の指数を入力から決める既存定理は今回確認していない。存在しないと断言していない。有限な保存終点の対数方向が真のPuiseux付値を近似することも未検証。

**自分で導いた部分。** 残差の零点集合だけでは減衰指数が決まらない有理関数例、HMMT-2006-FEB-GEO-07の距離式と漸近式、HMMT-2020-FEB-GEO-09の有限なpでの分母の極はローカル入力からの直接計算で、上記論文の主張として引用していない。

**ローカル一次資料。** 方針は[codex-tasks-1023.md](../../codex-tasks-1023.md)末尾の10/23 23:25とQ28、面白さの基準は[セッション要約](../../codex-session-01a1171a-summary.md)。solverの役割と制約は[report-draft-v10.md](../../../draft/report-draft-v10.md)、[supplement-v10.md](../../../draft/supplement-v10.md)。Q15の集計・判定コード、Hの代数化器、元の等式残差評価器とLMの付加残差コードを読んだ。入力のハッシュは[audit.json](audit.json)に保存した。
