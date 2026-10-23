Q22a 文献・一次資料の確認記録（2026-10-23）

以下は実際に検索・閲覧して確認した範囲である。文献に書かれた機能と、この課題の121問で同等に動くことを区別する。後者のGeoGebra／GMB／DD+AR実行比較は未実施。

**[1] 数値図からの関係列挙。** Zoltán Kovács and Jonathan H. Yu, *Automated Discovery of Geometrical Theorems in GeoGebra*, arXiv:2202.04627v1, 2022. 本文§1、§4.1–4.2を確認。GeoGebra Discovery研究系のDiscoverは、共線・共円・等長などを数値的に探索し、記号的な確認、作図から明らかな関係への対処、関係のまとめ上げを扱う。「全点組を調べる」だけでは新規性にならない。現行の標準GeoGebra全版での提供状態、今回と同じ相似・接触候補の全自動列挙率、今回のDSLへの対応は未確認。[著者論文](https://arxiv.org/html/2202.04627v1)

**[2] 指定した関係の数値・記号的確認。** *Relation Command*, GeoGebra公式マニュアル。最大4対象、共線・共円・直線と円錐曲線の接触など、および対応する場合の記号的確認を確認した。手作業で対象を選ぶ代替があることを支持する。公式解答で重要な関係を自動選択する機能とは書かれていない。[公式マニュアル](https://geogebra.github.io/docs/manual/en/commands/Relation/)

**[3] 演繹閉包と証明依存。** Trieu H. Trinh, Yuhuai Wu, Quoc V. Le, He He and Thang Luong, *Solving olympiad geometry without human demonstrations*, Nature **625**, 476–482, 2024. 本文のSynthetic theorems and proofs generation、Fig. 3、MethodsのDDとtracebackを確認。DD+ARが得る命題と依存辺のDAG、前提への遡及、補助点の役割は本案に最も近い比較対象。数値的真偽の集合はこの依存DAGを与えない。論文の最小化処理を「あらゆる証明の厳密な最短性」とは解釈しない。共線・共円の遡及には貪欲法を用いる記述もある。本件では実行していない。[Nature本文](https://www.nature.com/articles/s41586-023-06747-5)

**[4] 解法を与えず数値図を作る代替。** Ryan Krueger, Jesse Michael Han and Daniel Selsam, *Automatically Building Diagrams for Olympiad Geometry Problems*, arXiv:2012.02590v2, 2021（初版2020）。書誌・要旨を確認。GMBのDSLはパラメータ化、直接作図、微分可能な損失を区別し、数値最適化で図を得る。「一般的な最適化では図を作れない」という反論はできない。今回は本文の全実装・本データへの適用を再検証していない。[著者論文](https://arxiv.org/abs/2012.02590)

**[5] 人間の幾何的まとまり認識。** Kenneth R. Koedinger and John R. Anderson, *Abstract Planning and Perceptual Chunks: Elements of Expertise in Geometry*, Cognitive Science **14**(4), 511–550, 1990, DOI:10.1207/s15516709cog1404_2。出版社ページの書誌・要旨を確認。熟達者がまとまりを認識し細かな証明段階を省ける、という点が、作図段数・機械の規則適用数をそのまま人間難度にしない理由になる。著者配布PDFは取得に失敗し、本文の実験方法・参加者数・全結果は未確認。[出版社ページ](https://doi.org/10.1207/s15516709cog1404_2)

**[6] 図の複雑さと推論段数。** Hui-Yu Hsu and Edward A. Silver, *Cognitive complexity of geometric proof and geometric calculation: a problem-solving perspective*, Educational Studies in Mathematics **121**, 29–50, 2026（オンライン公開2025-11-17）, DOI:10.1007/s10649-025-10434-9。本文・要旨を確認。台湾の中学相当915人を対象に図の複雑さと2段階／3段階の推論を操作し、単純な図・少ない段数の方が良い成績だった。「段数が多ければ難しい」だけの主張には既知研究がある。競技熟達者・AIME/HMMTのpとの関係には一般化できない。[出版社本文](https://link.springer.com/article/10.1007/s10649-025-10434-9)

**[7] 人間難度のデータ。** Mucong Ding et al., *Easy2Hard-Bench: Standardized Difficulty Labels for Profiling LLM Performance and Generalization*, NeurIPS 2024 Datasets and Benchmarks, arXiv:2409.18433（閲覧版v2、2025-06-09）。書誌・要旨を確認。成績データからIRTやGlicko-2などで難度を推定するデータ群である。本件はローカルのhuman列をそのまま用いた。今回、新規の参加者実験・解答中の思考過程・補助線発見時間は測定していない。ローカル131問の元データ照合記録は既存Jのhuman-source-join.csvとanswer.mdを参照した。[著者論文](https://arxiv.org/abs/2409.18433)、[既存の照合説明](../../astra-consult-17/J/answer.md)

**[8] AIMEの内容監査。** Mathematical Association of America, *2012 AIME I Solutions Pamphlet*, Problem 12, printed p. 5。MAAの表紙・著作権表示と該当解答を確認。角の二等分線から得る比の等式を用いる。配布元は第三者ミラーであり、現行MAAサーバーから取得した資料とは称さない。解答の一例であり、その関係が全ての解法で不可欠だとは主張しない。[MAA冊子のミラー](https://www.isinj.com/mt-aime/2012AIME-ISolutions.pdf)

**[9] HMMTの内容監査。** HMMT, *February 2019 Geometry Solutions*, Problem 10, PDF pp. 5–6。大会公式アーカイブが指すPDFを確認。9個の正方形、S1の台形関係、S2の補助点B7と三角形の合同・相似を確認した。B7を加えた数値確認は公式解答に教えられた事後診断で、自動発見ではない。[公式アーカイブ](https://www.hmmt.org/www/archive/222)、[公式解答](https://hmmt-archive.s3.amazonaws.com/tournaments/2019/feb/geo/solutions.pdf)

**既存作業との差分。** 指定されたtasks末尾・session要約、相談16/17、report/supplement v10、G–L、所在を確認できたQ3–Q12、Q20/Q21の既存answerを参照した。Jの作図深さは既知なので主対照B_Dに含めた。Q20eの同じ前提・違う目標、Q22bの最小対を新しい実験として重ねなかった。壁・偽のゴール・認証・事前の探索難度診断は候補から外した。Q3はdifficulty/wall-diagnostic、Q4はdifficulty/multiplicity、Q11はdifficulty/certify-allの所在も確認した。Q5の指定先full-solver-nohardは見つからず、当該answerは未確認。Q20/Q21/Q22bの文書は同時更新中であり、参照時点の内容で判断した。

**相談5の0.80/0.70について。** 指定資料、ローカルの相談5要約、関連コード・文書を検索したが、この二値を生成した元コード、対象の分母、特徴、前処理の組を特定できなかった。外部ノートの参照先も作業環境では見つからなかった。従って再現は未確認。本件B_Dの数値を「相談5の再現値」と呼ばず、0.80/0.70超えは依頼記載値に対する参考判定に留めた。原手順を推測して数字を合わせる操作はしていない。

**文献探索の限界。** 上記の近接研究が存在することは確認したが、文献全体を網羅して「この組合せは世界初」と判断できる調査ではない。GeoGebra Discoveryと本件の完全な機能差、公式解答の最短性、各人の知識差を考慮した推論深さ、pとの機構的独立性はいずれも未確認。
