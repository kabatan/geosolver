Q28aの文献確認記録（2026-10-23）。一次資料を検索し、以下の範囲を実際に確認した。文献にある定理と、answer.mdで行った適用可否の判断・三次式への代入を区別する。

| 資料 | 確認した範囲 | 今回の使い方・限界 |
|---|---|---|
| Jonathan D. Hauenstein and Frank Sottile, *alphaCertified: Certifying Solutions to Polynomial Systems*。[著者公開PDF](https://franksottile.github.io/research/pdf/alphaCertified.pdf) | PDF冒頭は2011-09-07、TOMS to appear。§1の定義、Theorem 2・4、係数ノルム、序論の過剰決定系の注意 | α判定は十分条件。Theorem 4の1/(20γ)を正則な厳密根に適用した。正方系の認証と過剰決定系の扱いは同じではない。今回alphaCertified自体は実行していない |
| Michael Shub, *Complexity of Bezout's Theorem VI: Geodesics in the Condition (number) metric*。[arXiv本文](https://arxiv.org/html/math/0702344) | 2007年の公開版、§2のμ_normの定義、Theorem 5 | 条件数で重み付けした解経路長とNewton継続ステップの上界。本solverのLM探索軌道へは未適用 |
| Peter Bürgisser, *Smoothed Analysis of Condition Numbers*。[著者公開ICM 2010稿](https://www3.math.tu-berlin.de/algebra/work/pbuerg-icm2010.pdf) | §4.1–4.2、Bombieri–Weylノルム、平均の確率空間、式(13)–(16) | 正規化μと局所十分半径、ホモトピーの前提の確認。323問の係数がこの確率モデルに従うことは未確認 |
| Peter Bürgisser and Felipe Cucker, *Condition: The Geometry of Numerical Algorithms*。[出版社ページ](https://link.springer.com/book/10.1007/978-3-642-38896-5) | 著者・2013年・Grundlehren 349・DOI・目次を確認 | 書籍全本文は未確認。具体的定理の証拠には上の公開本文を使用 |
| Peter Bürgisser and Felipe Cucker, *On a Problem Posed by Steve Smale*。[arXiv要旨](https://arxiv.org/abs/0909.2114) | 著者・要旨・投稿履歴（初稿2009、最終改訂2011） | 平均計算量と複素多項式系という対象を確認。全文・各定理の定数は未確認で、数値予言の根拠にしていない |

別の講義ノート https://jncf2017.lip6.fr/files/lecture-notes/jncf2017-buergisser.pdf は検索結果の要旨のみ取得でき、本文取得はタイムアウトした。本文は未確認とし、結論の根拠に使っていない。

α理論の非正方系・解析関数への拡張全体を網羅したわけではない。「この拡張は存在しない」とは主張しない。確認できた定理だけでは、このsolverの許容判定を含む有限予算の成功率や精密化時間の未知の予言に届かなかった、という限定した判定である。
