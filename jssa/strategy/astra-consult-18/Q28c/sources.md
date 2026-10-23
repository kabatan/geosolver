# Q28c 文献確認記録

確認日：2026-10-23。検索結果の要約だけでなく、下記の一次資料を開いて確認した。書誌・確認した範囲と、今回の推論を分ける。

1. Jonathan D. Hauenstein, Jose Israel Rodriguez, Frank Sottile, **Numerical computation of Galois groups**, *Foundations of Computational Mathematics* **18** (2018), 867–890, DOI 10.1007/s10208-017-9356-x。
   - 書誌：著者自身の [業績一覧](https://franksottile.github.io/research/publications.html)で年・巻・頁・DOIを確認。
   - プレプリント：[arXiv:1605.07806](https://arxiv.org/abs/1605.07806)、2016-05-25投稿を確認。
   - 本文：[著者版PDF](https://franksottile.github.io/research/pdf/NGalois.pdf)（表紙にDraft, May 14, 2016）。Introduction、§2.2/Proposition 2.3、§3/Theorem 3.1・Algorithm 3.3、およびファイバー積法の説明を確認した。節番号はこの著者版のもの。出版版との逐語照合は未実施。
   - 群の生成元の計算と、ランダムなループだけでは真の部分群で停止を保証できないという区別を確認。少数のループから2群と断定する方法として引用しない。

2. J. S. Milne, **Fields and Galois Theory**, Kea Books, 2022。
   - [著者公開PDF](https://www.jmilne.org/math/Books/FT0.pdf)の書誌、Constructible numbers revisited（誌面52–54）、Theorem 3.24、Remark 3.27、Theorem 3.28を確認。
   - 二次拡大の塔、次数が2冪という必要条件、4次でも非作図の反例、根号可解性と群の可解性の区別の根拠に使った。

**文献の定理として引用していない事項。** 残差の重み付けによる目的関数の変化、答えの体と座標体を区別する `x³=2, τ=x³` の例、およびこのsolverへ群から成功率の方向を導けなかったという判断は、本監査の推論である。

**未確認。** 323問の完全な座標体・ガロア群、問題ごとの自然なパラメータ族、数値的群計算の完備性・認証、人間による作図可否の予測、GeoGebra等が元DSLを同じ労力で処理できるかは未確認。文献全体にこの種の予測定理が存在しないという網羅的主張はしない。
