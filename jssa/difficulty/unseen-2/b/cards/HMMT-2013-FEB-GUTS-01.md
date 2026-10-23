# HMMT-2013-FEB-GUTS-01

状態: 採用（一次資料・意味・独立代入・静的監査PASS）。記録は ../AUDIT.md と ../audit/。

座標固定・同値性: 原文の座標を保持。差4の任意の2マーカーの差ベクトルは(4,4k)なのでn=1と1+4を代表として用いる。整数変数を導入しない。

## 原文（PDF照合用転記）

Arpon chooses a positive real number k. For each positive integer n, he places a marker at the point (n,nk) in the (x,y) plane. Suppose that two markers whose x coordinates differ by 4 have distance 31. What is the distance between the markers at (7,7k) and (19,19k)?

## 条件対応

| 原文の条件・定義 | DSL位置 | DSL |
|---|---|---|
| マーカー(n,nk)の定義 | `constructions[0]` | `Point(1, (1)*k)` |
| マーカー(n,nk)の定義 | `constructions[1]` | `Point(1+4, (1+4)*k)` |
| マーカー(n,nk)の定義 | `constructions[2]` | `Point(7, (7)*k)` |
| マーカー(n,nk)の定義 | `constructions[3]` | `Point(19, (19)*k)` |
| kは正の実数 | `conditions[0]` | `k > 0` |
| x座標差4のマーカー間距離31 | `conditions[1]` | `Distance(U,V) = 31` |
| (7,7k)と(19,19k)の距離 | `target` | `Distance(P,Q)` |

定数: 原文の数値、座標固定の0/1、正多角形の頂点番号・中心角、作図定義の2/3/piだけ。
解答・検算用座標はDSLに転記しない。幾何量の参照答と公式出力はsource-evidenceおよび監査に分離。
