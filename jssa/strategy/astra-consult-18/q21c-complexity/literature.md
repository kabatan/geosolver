# Q21c 文献確認記録

2026-10-23に検索し、以下の本文・定理記述を確認した。「確認」は論文の記述を読んだという意味で、帰着の全細部を再証明したという意味ではない。公開されている本文に直接リンクし、原著を読めていない箇所は区別する。

| 文献 | 確認箇所・Q21cで使う範囲 | 使用しない推論 |
|---|---|---|
| Marcus Schaefer, Jean Cardinal, Tillmann Miltzow, *The Existential Theory of the Reals as a Complexity Class: A Compendium*, arXiv:2407.18006 (2024), [確認版v1](https://arxiv.org/html/2407.18006v1) | §CG1、order type実現可能性の∃ℝ完全性。単純なorder typeにも成立するとの整理 | 任意の平面幾何問題や、本solverのDSL全体が∃ℝ完全だとは言わない。平均的な競技問題への転用もしない |
| Saugata Basu, *Algorithms in Real Algebraic Geometry: A Survey*, arXiv:1409.1534 (2014), [本文](https://arxiv.org/pdf/1409.1534) | §2の量化子消去、Theorem 2.27周辺。変数数・多項式数・次数・係数ビット長を明示する必要 | 作図後のdだけを量化変数総数とみなさない。固定次元での多項式時間を、そのまま変数数に関するFPTと呼ばない |
| Daniel Perrucci, Juan Sabia, *Real roots of univariate polynomials and straight line programs*, **Journal of Discrete Algorithms 5(3), 471–478 (2007)**, [機関公開本文](https://bibliotecadigital.exactas.uba.ar/download/paper/paper_15708667_v5_n3_p471_Perrucci.pdf), [書誌](https://bibliotecadigital.exactas.uba.ar/collection/paperaa/document/paper_15708667_v5_n3_p471_Perrucci), [DOI](https://doi.org/10.1016/j.jda.2006.10.002) | Theorem 7：SLP入力の1変数実根存在のNP困難性。Theorem 8：区間制限。Theorem 9：根存在保証下で、指定精度の根近似に関する困難性 | 1変数だから容易とは限らない。一方、定数精度の数値探索や競技DSLへの困難性をこの論文だけで断定しない。掲載年は2007と確認 |
| Eric Allender, Peter Bürgisser, Johan Kjeldgaard-Pedersen, Peter Bro Miltersen, *On the Complexity of Numerical Analysis*, **SIAM Journal on Computing 38(5), 1987–2006 (2009)**, [著者公開本文](https://people.cs.rutgers.edu/~allender/papers/slp.pdf), [DOI](https://doi.org/10.1137/070697926) | Proposition 1.3周辺：整数算術回路の数値評価と符号判定の関係。算術演算数とビット計算量を区別する根拠 | 短い作図手順なら、必要精度・符号判定も自動で安いとはしない。PosSLPのNP困難性や非P性がこの論文で無条件に証明されたとは言わない |
| Jeff Erickson, Ivor van der Hoog, Tillmann Miltzow, *Smoothing the gap between NP and ER*, arXiv:1912.02278（初出2019）, [確認版v3](https://arxiv.org/html/1912.02278v3) | Theorems 4–5、Limitations。一定の算術的構造制限と証人の摂動の下で、認識問題の検証に必要な入力精度を抑える | 多項式時間探索・競技集団の平均計算量を示す定理ではない。共線性などを摂動が壊し得ることも本文で注意されている |

## 確認範囲の境界

- MnëvやShorの元の帰着論文は今回**未確認**。order typeについての記述は上記Compendiumの確認に基づく。帰着を自分で実装・再検証したとは書かない。
- Basu–Pollack–Royの1996年原著（[DOI](https://doi.org/10.1145/235809.235813)）は書誌を確認したが、今回原著全文は読んでいない。計算量の参照先はBasuのsurveyに限定した。
- Perrucci–SabiaのTheorem 9は、精度パラメータも入力に含む。帰着で用いられる小さい精度は多項式長のビット列で表せるが、固定の `10⁻⁸` 精度の難しさを意味しない。
- 固定全変数数の半代数判定を多項式時間と呼ぶには、次数の数値・係数長などを入力長に対して管理する。回路で指数次数を圧縮した入力に、明示入力向けの結論をそのまま適用しない。
- 本DSLの∃ℝ完全性、競技問題が属する一様なP部分族、幾何の条件を保った平滑化分布は、いずれも今回**未確認／未構成**。
- [theory-notes.md](theory-notes.md) のBoolean符号化とChebyshevの議論は、定義から書いた初等的な証明。新規性は主張しない。

## 既存報告との関係

v10の補足S2.10は、形式化への解法の混入や、作図を展開した際の変数・実行時間の変化を既に扱う。候補1の「圧縮された表現」という観察だけではそれを超えない。H・L・Q8・Q10・certify-allの認証系統、I・Q3の診断系統、G・Q6・Q7・Q12の条件・壁・終点の系統を、新しい計算量の名前で言い換えることもしない。

Q3・Q4・Q5・Q11の指定された `answer.md` はこの作業コピーに見つからなかった。Q4はmultiplicity側、Q11はcertify-all側の報告を参照し、Q3は既存まとめの結論までを参照した。欠けた原報告の本文を確認済みとはしない。
