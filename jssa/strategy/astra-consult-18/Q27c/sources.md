文献は今回オンラインで確認した。以下は説明に使える範囲であり、本研究の新規性や特定問題の機構を文献だけで認定しない。

| 一次資料 | 確認した範囲 | 本稿での使い方・限界 |
|---|---|---|
| R. Kannan, A. K. Lenstra, L. Lovász, “Polynomial Factorization and Nonrandomness of Bits of Algebraic and Some Transcendental Numbers”, Mathematics of Computation 50(181), 235–250 (1988)。[収録PDF](https://www.math.cmu.edu/users/af1p/Teaching/AdditiveCombinatorics/LLLL.pdf) | 誌面241の定理1.19で次数・高さ上界からの復元十分条件、誌面238の命題1.6で別多項式の非零値下界を確認。PDF内では13ページ目、10ページ目 | 格子法・分離理論の候補。真のd,Hを使う別アルゴリズムの保証で、本実装の閾値を直接予言しない |
| D. H. Bailey, J. M. Borwein, “PSLQ: An Algorithm to Discover Integer Relations”。[2020年5月14日付の著者版](https://www.davidhbailey.com/dhbpapers/pslq-comp-alg.pdf) | pp.1–2の関係長・係数桁数と多倍長精度の説明、単項式ベクトルの関係探索 | `(d+1)log10 H`の比較目安の背景。全数の厳密な必要桁数・本実装の十分条件とは扱わない。PDFの日付と初出出版年を混同しない |
| A. Leykin, J. Verschelde, A. Zhao, “Newton's method with deflation for isolated singularities of polynomial systems”。[著者arXiv版](https://arxiv.org/abs/math/0408419)、[出版元](https://www.sciencedirect.com/science/article/pii/S030439750600168X) | arXiv v2（2004）の要旨で孤立特異解の正則化・二次収束回復・重複度による段階数上界を確認。出版元の2006年、Theoretical Computer Science 359(1–3), 111–122も確認 | 特異点理論の候補。本データ18問の孤立性・重複度・反復次数は未確認。deflationを今回実装・検証したとは言わない |
| D. Goldberg, “What Every Computer Scientist Should Know About Floating-Point Arithmetic”, Computing Surveys, March 1991。[Oracle掲載の許諾再録](https://docs.oracle.com/cd/E19957-01/806-3568/ncg_goldberg.html) | 冒頭の書誌・再録許諾、丸め・精度・桁落ちの説明を確認 | 計算上の0と厳密な0の違い。δ=10^-120の例は本稿の説明で、原論文の実験ではない |

mpmath公式Web文書は今回の取得で403だったため、Web本文は未確認で引用根拠にしていない。実測はインストール済みmpmath 1.3.0を使用し、許容値規則はローカルの`polynomial_search.py`と`polynomial_search_helpers.py`から確認した。PSLQ原論文のAMS検索結果には1999年の書誌・要旨があるが、PDF直接取得は403だったため、全文にしかない主張は採用していない。

未確認：この幾何323問に固有のPSLQ普遍閾値を与える新理論、18問の停滞を一律に説明する重複度・Łojasiewicz指数、別seedでの精密化次数の普遍性。一般論から成立済みとはしない。
