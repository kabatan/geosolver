# 原問題の条件を補ったGMB入力

この2ファイルは**未改変の公式GMB入力ではない**。
[geo-model-builder](https://github.com/rkruegs123/geo-model-builder) の
commit `f070afe18ed874b3a31db519ea6f593f40a1be00` にある公開入力をもとに、
数学の原問題で要求される条件だけを追加した研究比較用の入力である。

| 入力 | 追加した条件 |
| --- | --- |
| `IMO_2000_P1.smt2` | `distance(N,AB) > distance(M,AB)` |
| `IMO_2015_P3.smt2` | KとBが直線CAの反対側、QとBが直線KAの反対側 |

後者は、既存の共円・非退化条件の下でA,B,C,K,Qの指定順序と同値であり、鏡映も許す。
どちらも元の変数・構成・条件・結論を維持したまま追加した。
正式な構文・型の確認と、原問題およびGeoSolver入力との同値性の確認は
`../reviews/alignment/`、元・新hashと選択規則は `../input-adjustments.json` にある。

公式原本は `benchmarks/gmb/.runtime/source/problems/IMO/` に保存し、変更していない。
他の34問には公式入力を使う。過去の「公式GMBの再現結果」を、この補正版の結果として扱わない。
GMB本体の数値処理は変更しないため、端点の誤受理等は共通の配置検査器で確認する。

出典の著作権表示：Copyright 2020 Ryan Krueger。
原入力のApache License 2.0を `LICENSE` に同梱し、各修正ファイルにも変更を明記した。
