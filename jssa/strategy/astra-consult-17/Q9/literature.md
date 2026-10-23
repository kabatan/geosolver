# Q9に関係する文献の確認範囲

確認日：2026-10-23。下記は一次資料で確認した範囲。探索結果を見る前から並行して調査した。網羅的な新規性調査ではない。

1. Greg Aloupis, John Iacono, Stefan Langerman, Özgür Özkan, **The Complexity of Order Type Isomorphism**, arXiv:1311.0928 (2013; SODA 2014予定版)。[著者原稿・要旨](https://arxiv.org/abs/1311.0928)

   点集合のorder typeを、各(d+1)点組の向きで記述する定義を要旨で確認した。三点の時計回り・反時計回りを特徴にすること自体は新しくない。Q9はラベルを固定し、三点組を最大256個に絞り、零判定閾値・欠測記号も使うので、厳密なorder type同型判定を実装したものではない。論文の計算量の定理を本実験へ流用しない。

2. A. H. G. Rinnooy Kan, G. T. Timmer, **Stochastic global optimization methods part I: Clustering methods**, Mathematical Programming 39, 27–56 (1987)。[出版社の書誌・要旨](https://link.springer.com/article/10.1007/BF02592070)

   無作為標本・クラスタリングから局所極小を探索する既存の系統を、出版社の要旨で確認した。本文全体・各方式の細部は未確認。「多点出発の重複を減らす」は新原理ではない。Q9は局所探索前の幾何的な符号列を距離として使う単純な選点であり、この論文の方式に対する優位を測っていない。

3. Rogier de Regt, Hilderick A. van der Meiden, Willem F. Bronsvoort, **A Workbench for Geometric Constraint Solving**, Computer-Aided Design & Applications 5(1–4), 471–482 (2008), DOI 10.3722/cadaps.2008.471-482。[出版社PDF](https://www.cad-journal.net/files/vol_5/CAD_5%281-4%29_2008_471-482.pdf)

   PDF第2節を確認した。三角形の構成・クラスタ結合で生じる複数の解から、利用者のprototypeを用いて意図した配置を選ぶ既存方式が説明されている（pp.473–475）。形や向きに関する情報を枝選択へ使う発想は既存である。Q9は利用者の正しいsketchを前提にせず、初期配置を多様にする点で目的が異なる。しかしそれだけでは新しい有効性の証拠にならない。

補足：van der Meiden & Bronsvoort (2005), *An efficient method to determine the intended solution for a system of geometric constraints* の書誌・DOIは [TU Delft](https://research.tudelft.nl/en/publications/an-efficient-method-to-determine-the-intended-solution-for-a-syst/) で確認できた。出版社本文と検索されたPDF本文の取得は失敗したため、個別の選択規則は未確認。2008年論文の説明を超えてこの2005年論文の細部を断定しない。

**今回確認できていないこと：** 「hard許容性と等式評価可能性のprefixを一致させ、符号列のmaximin選点を同じ箱の座標maximinと比較する」というQ9の全手順が既発表かどうか。この未確認を新規性の根拠にしてはいけない。未見自然問題への有効性、完成solverへの優位、本人の予測を上回るかも文献からは分からない。
