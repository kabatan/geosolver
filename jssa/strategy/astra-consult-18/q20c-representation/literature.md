# Q20c：先行研究の確認範囲

確認日：2026-10-23。一次資料を優先した限定的な調査であり、網羅的レビューではない。本文でいう「未確認」は、非存在を意味しない。新規性の判断と今回の数値実験の合否は分けた。

| 資料 | 今回確認した範囲 | 本候補への意味 |
|---|---|---|
| Jan Albersmeyer, Moritz Diehl, **The Lifted Newton Method and Its Application in Optimization**, SIAM Journal on Optimization 20(3), 1655–1684, 2010. DOI:10.1137/080724885 | [著者側公開PDF](https://publications.syscop.de/Albersmeyer2010.pdf) の要旨・§1–2、および [出版社の書誌と要旨](https://epubs.siam.org/doi/abs/10.1137/080724885) | 中間変数の追加という原理と汎用化は既存。候補1の数値表は新しい解法の実証にならない |
| Ryan Krueger, Jesse Michael Han, Daniel Selsam, **Automatically Building Diagrams for Olympiad Geometry Problems**, CADE-28, 2021, arXiv:2012.02590v2 | [原論文](https://arxiv.org/html/2012.02590v2) の要旨・§1、§3のDSL・パラメータ化 | 競技幾何で作図と数値制約を分ける近接先行研究。単なる変数削減の独自性は主張できない |
| Meera Sitharam, Heping Gao, **Characterizing graphs with convex and connected Cayley configuration spaces**, arXiv:0809.3935v6 | [版情報](https://arxiv.org/abs/0809.3935)、[PDF](https://arxiv.org/pdf/0809.3935) の定義、Lemma 5.8、Theorem 5.11と関連説明 | 候補2の距離制約部分を支える既知理論。混合DSL全体への適用は本論文から自動的には導けない |
| M. Shpitalni, H. Lipson, **Automatic reasoning for design under geometric constraints**, CIRP Annals 46(1), 85–89, 1997 | [著者公開の書誌・要旨](https://www.mit.edu/~hlipson/papers/geo_cons.htm) のみ。本文・実装は未確認 | 補助幾何を自動生成して逐次構成へ変換する先例。「補助線の自動発見」だけでは新しくない |

検索した主題は lifted Newton/multiple shooting、中間変数の消去、geometric constraint solving/auxiliary constructions、Cayley configuration spaces。検索結果に出たレビューや百科事典を、技術的主張の根拠には使っていない。大きいPDFをローカルへ保存していない。

未確認のまま残した点：

- 候補1と同じ有限精度機構が、今回の自然な求値入力に広く生じるか。既存57問の表現比較では原因を切り分けられない。
- 候補2と同じ角・接・入射・作図分岐を含む範囲に対する先行実装と、自動変換の新規性。純距離制約の既知理論を超えたとは言っていない。
- どちらの候補でも、特定の補助線を与える介入の人間成績。既存human_featの難度ラベルからは代用できない。

ローカルな位置づけは [answer.md](answer.md) の末尾と [README.md](README.md) に記した。相談資料で引用されていた全ての論文を今回改めて精読したという意味ではない。
