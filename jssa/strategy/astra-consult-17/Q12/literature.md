# 文献との差と確認範囲

2026-10-23確認。Q7の最終稿・文献表・検索記録を読み、以下の一次資料の必要箇所をQ12でもブラウザ検索ツールで確認した。原論文の全証明を検算したという意味ではない。未発見を不存在の証明にしない。長い逐語引用はしていない。

## 幾何制約の分解

Boris van Sosin, Gershon Elber (2017), *Solving Piecewise Polynomial Constraint Systems with Decomposition and a Subdivision-Based Solver*, Computer-Aided Design 90, 37–47。[著者PDF](https://gershon.cs.technion.ac.il/papers/mv_solver_decomp2017.pdf)。Abstract、§3.3–3.5、Algorithm 5を確認。

小系へ分解して順に解を伝播し、必要な変数が利用可能になる段階に不等式も配置する。Q12の「どこで条件を使うか」は広く既知の設計問題に入る。一方、本文5.2の特定のE/Y/Z比較と局所モデル誤差をそのまま扱う論文ではない。Q12の導出は、この分解法を超える新原理や完全性保証ではない。

古典的なCAD分解研究全体やvariable projectionとの網羅比較は**未確認**。この1論文だけでそれらとの差を確定していない。

## Barrierと、評価可能な条件／選別条件の区別

Charles Audet, J. E. Dennis Jr. (2009), *A Progressive Barrier for Derivative-Free Nonlinear Programming*, SIAM Journal on Optimization 20(1), 445–472。出版情報は[所属機関の記録](https://www.gerad.ca/en/papers/G-2007-37)、本文は2007-06-26の[著者稿](https://www.researchgate.net/profile/J-Dennis/publication/228700465_A_mads_algorithm_with_a_progressive_barrier_for_derivative-free_nonlinear_programming/links/09e4150ca73980221b000000/A-mads-algorithm-with-a-progressive-barrier-for-derivative-free-nonlinear-programming.pdf)§1–2.1を確認。

評価前に守る領域と、違反を一時的に認める制約を分け、違反量の上限を更新する。したがってQ12の定義域／選別という区別も発想自体は新しくない。Nは制約違反を管理するPBではなく、Bの有限段差は厳密なEBではない。出版版との逐語的一致・実装の直接性能比較は**未確認**。

Ceres Solverの[2.2.0公式Modeling FAQ](https://raw.githubusercontent.com/ceres-solver/ceres-solver/2.2.0/docs/source/modeling_faqs.rst)、不等式の項も確認。評価失敗で不許容試行を防ぐ方法には早期収束の危険があるとする。Q1の有限段差とは実装が異なるが、試行拒否で探索が止まるという着想の先取性は主張できない。

log barrier、適切な制約付きLM、smooth penalty等に対するPの優越性は**未確認**。Q1のG2は一方式で、滑らかな罰則一般を代表しない。Q7が読んだ制約付きLMの各論文はQ12では再確認せず、詳しい定理の根拠をそこへ広げていない。

## LMの受理・停止

[MINPACK `lmder.f`の公開ソース](https://netlib.org/minpack/lmder.f)で、相対減少、予測減少、ratio、受理点更新、ftol/xtol/gtolと機械精度による停止を確認した。Q12のモデル誤差の恒等式は自分で展開した説明で、MINPACK固有の全分岐を同一式と主張しない。

実行されたSciPy nativeバイナリとの逐行対応、Gの内部fnorm/ratioの実測値は**未確認**。常時定数行については理想的な一歩、指定停止、機械精度、実際の軌道を区別する。Moré (1978)の本文全体はQ12では未確認で、書誌だけから独自な理論結果を帰属していない。

## Deflation

Anton Leykin, Jan Verschelde, Ailing Zhao, *Newton's Method with Deflation for Isolated Singularities of Polynomial Systems*, [arXiv:math/0408419v2](https://arxiv.org/html/math/0408419v2)（2004-10-13）。Abstract、§1–3、Theorem 3.1を確認。孤立特異根の正則化とNewton法の二次収束の回復、必要回数と重複度の関係を扱う。

Jonathan D. Hauenstein, Bernard Mourrain, Agnes Szanto, *On deflation and multiplicity structure*, [arXiv:1601.00611v1](https://arxiv.org/html/1601.00611)（2016）。Abstract、§1、§3の構成を確認。変数を追加しない方法もあり、isosingular decompositionも扱う。「汎用deflationは必ず変数を増やす／非孤立には一切使えない」とは書けない。

Q12の共有接点規則は幾何的な入射を入力から認識する特定の書き換えで、一般の重複度理論を上回らない。距離ゼロのベクトル化と非零半径因子の処理を、すべてdeflationと一括しない。汎用deflationを同じ入力・候補・予算で走らせた比較、費用上の優越性、完全な正則化保証は**未確認**。

## 最も近い自動幾何の先行例

Ryan Krueger, Jesse Michael Han, Daniel Selsam (2021), *Automatically Building Diagrams for Olympiad Geometry Problems*, [arXiv:2012.02590v2](https://arxiv.org/html/2012.02590v2)。§3.1–3.4を確認。

GMBLには `param`、`define`、`assert`、`eval` があり、パラメータ化、構成、損失としての条件、最終モデルの評価を区別する。根の選択と退化を避ける補助損失も扱う。これはQ12の「条件の役割」を新規な概念と呼びにくい直接的な先例である。ただしevalの主要な実験は導くべきゴールの最終評価で、元guardを探索から最終検査へ移すQ12と同一ではない。Q1のhard除去・停止対照やQ4の具体的な診断の再現をこの論文で確認したという意味でもない。

## 正直に残せる差

残り得る差は、競技幾何のこの実装について、表現を変えた対応実験・受理機構・精密化診断・採点監査をつなぎ、**入力だけの規則が未使用問題で費用込みの増分能力を生むかを反証可能にしたこと**である。後半は未実証。Q2の計画を書いただけで新能力を獲得したとはいわない。

今回、同一の規則・同一の機構対照・未使用問題検証まで一致する既報は確認できなかった。ただし検索範囲はQ7の資料を中心とする限定的な確認で、特許・全CAD実装・全最適化文献を網羅していない。世界初の主張は保留する。
