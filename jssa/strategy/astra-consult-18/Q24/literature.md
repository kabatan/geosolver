# Q24 文献確認

確認日：2026-10-23。検索後に一次資料を開いて確認した範囲を記す。文献が本solverのDSLから成功率を予測できることまで証明したとは扱わない。

|資料|確認できたこと|本稿での限界|
|---|---|---|
|P. J. Menck, J. Heitzig, N. Marwan, J. Kurths, “How basin stability complements the linear-stability paradigm”, *Nature Physics* 9(2), 89–92 (2013), DOI 10.1038/nphys2516。[出版社](https://www.nature.com/articles/nphys2516)、[著者所属機関の書誌](https://publications.pik-potsdam.de/pubman/faces/ViewItemFullPage.jsp?itemId=item_18411_3)|書誌と盆の体積による安定性評価という概要。書誌は機関リポジトリでも一致。|出版社本文の取得は失敗し、機関のPDFはPrivateだった。2013年本文の詳細な式・仮定は未確認。次の著者らの後続論文で測度の定義を直接確認した。|
|P. Schultz, P. J. Menck, J. Heitzig, J. Kurths, “Potentials and Limits to Basin Stability Estimation”, arXiv:1603.01844v1 (2016)。[書誌](https://arxiv.org/abs/1603.01844)、[本文](https://arxiv.org/html/1603.01844v1)|本文式(2)は開始分布μに対する盆の確率質量。Monte Carloの標本誤差に加え、有限精度・長い過渡・境界付近の誤分類が問題になる。|連続力学系の漸近盆を扱う。本稿の有限予算・答え照合付きの局所探索成功集合への置換は本稿の定義であり、論文の定理の直接適用ではない。HTMLの自動生成日付ではなくarXiv提出年を採用。|
|B. I. Epureanu, H. S. Greenside, “Fractal Basins of Attraction Associated with a Damped Newton's Method”, arXiv:chao-dyn/9612010 (1996)。[著者原稿・概要](https://arxiv.org/abs/chao-dyn/9612010)|z³−1でもNewtonの盆が入り組むこと、減衰との関係を調べる既存研究。著者・題名・arXiv提出年を確認。|本作業で詳細なフラクタル次元や本solverとの同型性を確認したわけではない。最終刊行の巻号・頁をこの書誌には採用していない。|
|M. Shub, “Complexity of Bezout’s Theorem VI: Geodesics in the Condition (number) metric”, arXiv:math/0702344v1 (2007)。[本文](https://arxiv.org/html/math/0702344)|概要・導入・Theorem 5：経路の条件数と速度の積分による長さが、経路を近似するNewtonステップ数の上界に関係する。|経路本数だけで実行時間は決まらないことの根拠。経路や解を知らずにDSLの文字数から条件長を出せるという結果ではない。|
|J. Berthomieu, C. Eder, M. Safey El Din, “msolve: A Library for Solving Polynomial Systems”, ISSAC 2021, DOI 10.1145/3452143.3465545。[著者原稿](https://arxiv.org/abs/2104.03572)|概要と書誌：零次元多項式系を対象とするGröbner基底・順序変換・実一変数求根の枠組み。|msolveの費用をホモトピー経路本数と同一視しない。正次元を含む全ての使い方が不可能という主張ではない。|
|[msolve公式README](https://github.com/algebraic-solving/msolve/blob/master/README.md)|有限複素解を持つ系の実根分離に加え、Gröbner基底と `-e k` によるブロック消去の機能を確認。|現行文書。開発群の実測版0.9.4・翻訳器・制限は別途元比較READMEで確認した。|
|HomotopyContinuation.jl [Total Degree Homotopy](https://www.juliahomotopycontinuation.org/guides/totaldegree/)、[公式solve文書](https://www.juliahomotopycontinuation.org/HomotopyContinuation.jl/stable/solve/)|total degreeの開始解数は各式次数の積。solveにはtotal_degree/polyhedralの選択と `stop_early_cb` がある。|「ホモトピーは常に全経路を完走するしかない」は誤り。一解で打ち切る比較も代替手段として残る。|

確認できなかったもの：このsolverの入力ASTだけから盆の大きさを定量保証する定理、全ての等価なDSLに不変な盆予測式、局所探索のpからNOMAD・精密化・PSLQを含む完成solverの費用を導く定理。これらが存在しないと証明したわけではないが、本作業では未確認であり、成果として主張しない。

上記は盆・Newton・ホモトピーの必要な概念を確認する限定的な検索である。網羅的な先行研究不存在の証明ではない。
