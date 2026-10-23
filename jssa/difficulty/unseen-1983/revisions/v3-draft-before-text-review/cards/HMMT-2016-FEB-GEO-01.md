# HMMT-2016-FEB-GEO-01 原文→入力対応カード

状態: **暫定候補・公式番号/答え未照合・数値検証未実施**。

- 保存資料: `/home/kabatan/work/solver-research-assets/corpus97-sources/hmmt-2016-geo-problems.txt` / saved_pdf_text / row_idx=1
- 原文SHA-256: `dbd326627b84cf97821be42d5e03f5781a9aa49e9c42650d756453cddccbfaf6`
- 入力SHA-256（JSONファイルの全bytes）: `40f7619eabc820552c73d68a1a2220eb0e2ea3c4113561ee37cc32db6ebba736`
- 座標固定・同値性: Q=(0,0), W=(2,0)。合同移動だけ。隣接辺の直交から全辺が軸平行。鏡映・凹凸の枝は残す。
- 分枝・非退化: 下表のguardと構成の定義域を使用。根番号による選択なし。
- 公式答え: 本カードには含めず、`official_answers.jsonl` の状態を参照。採否と入力に答えを使用していない。

## 手元の原文（保存資料）

Dodecagon QW ART ZSP HIN X has all side lengths equal to 2, is not self-intersecting (in particular,
    the twelve vertices are all distinct), and moreover each interior angle is either 90◦ or 270◦ . What are
    all possible values of the area of 4SIX?

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| all side lengths 2 / 座標原点 | `constructions[0]` | `Q = Point(0, 0)` |
| QW = 2 | `constructions[1]` | `W = Point(2, 0)` |
| dodecagon QWARTZSPHINX / 未知頂点 | `constructions[2]` | `A = Point(ax, ay)` |
| dodecagon QWARTZSPHINX / 未知頂点 | `constructions[3]` | `R = Point(rx, ry)` |
| dodecagon QWARTZSPHINX / 未知頂点 | `constructions[4]` | `T = Point(tx, ty)` |
| dodecagon QWARTZSPHINX / 未知頂点 | `constructions[5]` | `Z = Point(zx, zy)` |
| dodecagon QWARTZSPHINX / 未知頂点 | `constructions[6]` | `S = Point(sx, sy)` |
| dodecagon QWARTZSPHINX / 未知頂点 | `constructions[7]` | `P = Point(px, py)` |
| dodecagon QWARTZSPHINX / 未知頂点 | `constructions[8]` | `H = Point(hx, hy)` |
| dodecagon QWARTZSPHINX / 未知頂点 | `constructions[9]` | `I = Point(ix, iy)` |
| dodecagon QWARTZSPHINX / 未知頂点 | `constructions[10]` | `N = Point(nx, ny)` |
| dodecagon QWARTZSPHINX / 未知頂点 | `constructions[11]` | `X = Point(xx, xy)` |
| each interior angle 90 or 270 degrees / 隣接辺は直交し、単純性と併用 | `conditions[0]` | `Perpendicular(Line(Q, W), Line(W, A)) = 0` |
| all twelve side lengths equal 2 | `conditions[1]` | `Distance(W, A) = 2` |
| each interior angle 90 or 270 degrees / 隣接辺は直交し、単純性と併用 | `conditions[2]` | `Perpendicular(Line(W, A), Line(A, R)) = 0` |
| all twelve side lengths equal 2 | `conditions[3]` | `Distance(A, R) = 2` |
| each interior angle 90 or 270 degrees / 隣接辺は直交し、単純性と併用 | `conditions[4]` | `Perpendicular(Line(A, R), Line(R, T)) = 0` |
| all twelve side lengths equal 2 | `conditions[5]` | `Distance(R, T) = 2` |
| each interior angle 90 or 270 degrees / 隣接辺は直交し、単純性と併用 | `conditions[6]` | `Perpendicular(Line(R, T), Line(T, Z)) = 0` |
| all twelve side lengths equal 2 | `conditions[7]` | `Distance(T, Z) = 2` |
| each interior angle 90 or 270 degrees / 隣接辺は直交し、単純性と併用 | `conditions[8]` | `Perpendicular(Line(T, Z), Line(Z, S)) = 0` |
| all twelve side lengths equal 2 | `conditions[9]` | `Distance(Z, S) = 2` |
| each interior angle 90 or 270 degrees / 隣接辺は直交し、単純性と併用 | `conditions[10]` | `Perpendicular(Line(Z, S), Line(S, P)) = 0` |
| all twelve side lengths equal 2 | `conditions[11]` | `Distance(S, P) = 2` |
| each interior angle 90 or 270 degrees / 隣接辺は直交し、単純性と併用 | `conditions[12]` | `Perpendicular(Line(S, P), Line(P, H)) = 0` |
| all twelve side lengths equal 2 | `conditions[13]` | `Distance(P, H) = 2` |
| each interior angle 90 or 270 degrees / 隣接辺は直交し、単純性と併用 | `conditions[14]` | `Perpendicular(Line(P, H), Line(H, I)) = 0` |
| all twelve side lengths equal 2 | `conditions[15]` | `Distance(H, I) = 2` |
| each interior angle 90 or 270 degrees / 隣接辺は直交し、単純性と併用 | `conditions[16]` | `Perpendicular(Line(H, I), Line(I, N)) = 0` |
| all twelve side lengths equal 2 | `conditions[17]` | `Distance(I, N) = 2` |
| each interior angle 90 or 270 degrees / 隣接辺は直交し、単純性と併用 | `conditions[18]` | `Perpendicular(Line(I, N), Line(N, X)) = 0` |
| all twelve side lengths equal 2 | `conditions[19]` | `Distance(N, X) = 2` |
| each interior angle 90 or 270 degrees / 隣接辺は直交し、単純性と併用 | `conditions[20]` | `Perpendicular(Line(N, X), Line(X, Q)) = 0` |
| all twelve side lengths equal 2 | `conditions[21]` | `Distance(X, Q) = 2` |
| each interior angle 90 or 270 degrees / 隣接辺は直交し、単純性と併用 | `conditions[22]` | `Perpendicular(Line(X, Q), Line(Q, W)) = 0` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[23]` | `(max(Q.x,W.x)<min(A.x,R.x)) or (max(A.x,R.x)<min(Q.x,W.x)) or (max(Q.y,W.y)<min(A.y,R.y)) or (max(A.y,R.y)<min(Q.y,W.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[24]` | `(max(Q.x,W.x)<min(R.x,T.x)) or (max(R.x,T.x)<min(Q.x,W.x)) or (max(Q.y,W.y)<min(R.y,T.y)) or (max(R.y,T.y)<min(Q.y,W.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[25]` | `(max(Q.x,W.x)<min(T.x,Z.x)) or (max(T.x,Z.x)<min(Q.x,W.x)) or (max(Q.y,W.y)<min(T.y,Z.y)) or (max(T.y,Z.y)<min(Q.y,W.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[26]` | `(max(Q.x,W.x)<min(Z.x,S.x)) or (max(Z.x,S.x)<min(Q.x,W.x)) or (max(Q.y,W.y)<min(Z.y,S.y)) or (max(Z.y,S.y)<min(Q.y,W.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[27]` | `(max(Q.x,W.x)<min(S.x,P.x)) or (max(S.x,P.x)<min(Q.x,W.x)) or (max(Q.y,W.y)<min(S.y,P.y)) or (max(S.y,P.y)<min(Q.y,W.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[28]` | `(max(Q.x,W.x)<min(P.x,H.x)) or (max(P.x,H.x)<min(Q.x,W.x)) or (max(Q.y,W.y)<min(P.y,H.y)) or (max(P.y,H.y)<min(Q.y,W.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[29]` | `(max(Q.x,W.x)<min(H.x,I.x)) or (max(H.x,I.x)<min(Q.x,W.x)) or (max(Q.y,W.y)<min(H.y,I.y)) or (max(H.y,I.y)<min(Q.y,W.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[30]` | `(max(Q.x,W.x)<min(I.x,N.x)) or (max(I.x,N.x)<min(Q.x,W.x)) or (max(Q.y,W.y)<min(I.y,N.y)) or (max(I.y,N.y)<min(Q.y,W.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[31]` | `(max(Q.x,W.x)<min(N.x,X.x)) or (max(N.x,X.x)<min(Q.x,W.x)) or (max(Q.y,W.y)<min(N.y,X.y)) or (max(N.y,X.y)<min(Q.y,W.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[32]` | `(max(W.x,A.x)<min(R.x,T.x)) or (max(R.x,T.x)<min(W.x,A.x)) or (max(W.y,A.y)<min(R.y,T.y)) or (max(R.y,T.y)<min(W.y,A.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[33]` | `(max(W.x,A.x)<min(T.x,Z.x)) or (max(T.x,Z.x)<min(W.x,A.x)) or (max(W.y,A.y)<min(T.y,Z.y)) or (max(T.y,Z.y)<min(W.y,A.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[34]` | `(max(W.x,A.x)<min(Z.x,S.x)) or (max(Z.x,S.x)<min(W.x,A.x)) or (max(W.y,A.y)<min(Z.y,S.y)) or (max(Z.y,S.y)<min(W.y,A.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[35]` | `(max(W.x,A.x)<min(S.x,P.x)) or (max(S.x,P.x)<min(W.x,A.x)) or (max(W.y,A.y)<min(S.y,P.y)) or (max(S.y,P.y)<min(W.y,A.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[36]` | `(max(W.x,A.x)<min(P.x,H.x)) or (max(P.x,H.x)<min(W.x,A.x)) or (max(W.y,A.y)<min(P.y,H.y)) or (max(P.y,H.y)<min(W.y,A.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[37]` | `(max(W.x,A.x)<min(H.x,I.x)) or (max(H.x,I.x)<min(W.x,A.x)) or (max(W.y,A.y)<min(H.y,I.y)) or (max(H.y,I.y)<min(W.y,A.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[38]` | `(max(W.x,A.x)<min(I.x,N.x)) or (max(I.x,N.x)<min(W.x,A.x)) or (max(W.y,A.y)<min(I.y,N.y)) or (max(I.y,N.y)<min(W.y,A.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[39]` | `(max(W.x,A.x)<min(N.x,X.x)) or (max(N.x,X.x)<min(W.x,A.x)) or (max(W.y,A.y)<min(N.y,X.y)) or (max(N.y,X.y)<min(W.y,A.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[40]` | `(max(W.x,A.x)<min(X.x,Q.x)) or (max(X.x,Q.x)<min(W.x,A.x)) or (max(W.y,A.y)<min(X.y,Q.y)) or (max(X.y,Q.y)<min(W.y,A.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[41]` | `(max(A.x,R.x)<min(T.x,Z.x)) or (max(T.x,Z.x)<min(A.x,R.x)) or (max(A.y,R.y)<min(T.y,Z.y)) or (max(T.y,Z.y)<min(A.y,R.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[42]` | `(max(A.x,R.x)<min(Z.x,S.x)) or (max(Z.x,S.x)<min(A.x,R.x)) or (max(A.y,R.y)<min(Z.y,S.y)) or (max(Z.y,S.y)<min(A.y,R.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[43]` | `(max(A.x,R.x)<min(S.x,P.x)) or (max(S.x,P.x)<min(A.x,R.x)) or (max(A.y,R.y)<min(S.y,P.y)) or (max(S.y,P.y)<min(A.y,R.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[44]` | `(max(A.x,R.x)<min(P.x,H.x)) or (max(P.x,H.x)<min(A.x,R.x)) or (max(A.y,R.y)<min(P.y,H.y)) or (max(P.y,H.y)<min(A.y,R.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[45]` | `(max(A.x,R.x)<min(H.x,I.x)) or (max(H.x,I.x)<min(A.x,R.x)) or (max(A.y,R.y)<min(H.y,I.y)) or (max(H.y,I.y)<min(A.y,R.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[46]` | `(max(A.x,R.x)<min(I.x,N.x)) or (max(I.x,N.x)<min(A.x,R.x)) or (max(A.y,R.y)<min(I.y,N.y)) or (max(I.y,N.y)<min(A.y,R.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[47]` | `(max(A.x,R.x)<min(N.x,X.x)) or (max(N.x,X.x)<min(A.x,R.x)) or (max(A.y,R.y)<min(N.y,X.y)) or (max(N.y,X.y)<min(A.y,R.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[48]` | `(max(A.x,R.x)<min(X.x,Q.x)) or (max(X.x,Q.x)<min(A.x,R.x)) or (max(A.y,R.y)<min(X.y,Q.y)) or (max(X.y,Q.y)<min(A.y,R.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[49]` | `(max(R.x,T.x)<min(Z.x,S.x)) or (max(Z.x,S.x)<min(R.x,T.x)) or (max(R.y,T.y)<min(Z.y,S.y)) or (max(Z.y,S.y)<min(R.y,T.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[50]` | `(max(R.x,T.x)<min(S.x,P.x)) or (max(S.x,P.x)<min(R.x,T.x)) or (max(R.y,T.y)<min(S.y,P.y)) or (max(S.y,P.y)<min(R.y,T.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[51]` | `(max(R.x,T.x)<min(P.x,H.x)) or (max(P.x,H.x)<min(R.x,T.x)) or (max(R.y,T.y)<min(P.y,H.y)) or (max(P.y,H.y)<min(R.y,T.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[52]` | `(max(R.x,T.x)<min(H.x,I.x)) or (max(H.x,I.x)<min(R.x,T.x)) or (max(R.y,T.y)<min(H.y,I.y)) or (max(H.y,I.y)<min(R.y,T.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[53]` | `(max(R.x,T.x)<min(I.x,N.x)) or (max(I.x,N.x)<min(R.x,T.x)) or (max(R.y,T.y)<min(I.y,N.y)) or (max(I.y,N.y)<min(R.y,T.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[54]` | `(max(R.x,T.x)<min(N.x,X.x)) or (max(N.x,X.x)<min(R.x,T.x)) or (max(R.y,T.y)<min(N.y,X.y)) or (max(N.y,X.y)<min(R.y,T.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[55]` | `(max(R.x,T.x)<min(X.x,Q.x)) or (max(X.x,Q.x)<min(R.x,T.x)) or (max(R.y,T.y)<min(X.y,Q.y)) or (max(X.y,Q.y)<min(R.y,T.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[56]` | `(max(T.x,Z.x)<min(S.x,P.x)) or (max(S.x,P.x)<min(T.x,Z.x)) or (max(T.y,Z.y)<min(S.y,P.y)) or (max(S.y,P.y)<min(T.y,Z.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[57]` | `(max(T.x,Z.x)<min(P.x,H.x)) or (max(P.x,H.x)<min(T.x,Z.x)) or (max(T.y,Z.y)<min(P.y,H.y)) or (max(P.y,H.y)<min(T.y,Z.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[58]` | `(max(T.x,Z.x)<min(H.x,I.x)) or (max(H.x,I.x)<min(T.x,Z.x)) or (max(T.y,Z.y)<min(H.y,I.y)) or (max(H.y,I.y)<min(T.y,Z.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[59]` | `(max(T.x,Z.x)<min(I.x,N.x)) or (max(I.x,N.x)<min(T.x,Z.x)) or (max(T.y,Z.y)<min(I.y,N.y)) or (max(I.y,N.y)<min(T.y,Z.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[60]` | `(max(T.x,Z.x)<min(N.x,X.x)) or (max(N.x,X.x)<min(T.x,Z.x)) or (max(T.y,Z.y)<min(N.y,X.y)) or (max(N.y,X.y)<min(T.y,Z.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[61]` | `(max(T.x,Z.x)<min(X.x,Q.x)) or (max(X.x,Q.x)<min(T.x,Z.x)) or (max(T.y,Z.y)<min(X.y,Q.y)) or (max(X.y,Q.y)<min(T.y,Z.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[62]` | `(max(Z.x,S.x)<min(P.x,H.x)) or (max(P.x,H.x)<min(Z.x,S.x)) or (max(Z.y,S.y)<min(P.y,H.y)) or (max(P.y,H.y)<min(Z.y,S.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[63]` | `(max(Z.x,S.x)<min(H.x,I.x)) or (max(H.x,I.x)<min(Z.x,S.x)) or (max(Z.y,S.y)<min(H.y,I.y)) or (max(H.y,I.y)<min(Z.y,S.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[64]` | `(max(Z.x,S.x)<min(I.x,N.x)) or (max(I.x,N.x)<min(Z.x,S.x)) or (max(Z.y,S.y)<min(I.y,N.y)) or (max(I.y,N.y)<min(Z.y,S.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[65]` | `(max(Z.x,S.x)<min(N.x,X.x)) or (max(N.x,X.x)<min(Z.x,S.x)) or (max(Z.y,S.y)<min(N.y,X.y)) or (max(N.y,X.y)<min(Z.y,S.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[66]` | `(max(Z.x,S.x)<min(X.x,Q.x)) or (max(X.x,Q.x)<min(Z.x,S.x)) or (max(Z.y,S.y)<min(X.y,Q.y)) or (max(X.y,Q.y)<min(Z.y,S.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[67]` | `(max(S.x,P.x)<min(H.x,I.x)) or (max(H.x,I.x)<min(S.x,P.x)) or (max(S.y,P.y)<min(H.y,I.y)) or (max(H.y,I.y)<min(S.y,P.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[68]` | `(max(S.x,P.x)<min(I.x,N.x)) or (max(I.x,N.x)<min(S.x,P.x)) or (max(S.y,P.y)<min(I.y,N.y)) or (max(I.y,N.y)<min(S.y,P.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[69]` | `(max(S.x,P.x)<min(N.x,X.x)) or (max(N.x,X.x)<min(S.x,P.x)) or (max(S.y,P.y)<min(N.y,X.y)) or (max(N.y,X.y)<min(S.y,P.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[70]` | `(max(S.x,P.x)<min(X.x,Q.x)) or (max(X.x,Q.x)<min(S.x,P.x)) or (max(S.y,P.y)<min(X.y,Q.y)) or (max(X.y,Q.y)<min(S.y,P.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[71]` | `(max(P.x,H.x)<min(I.x,N.x)) or (max(I.x,N.x)<min(P.x,H.x)) or (max(P.y,H.y)<min(I.y,N.y)) or (max(I.y,N.y)<min(P.y,H.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[72]` | `(max(P.x,H.x)<min(N.x,X.x)) or (max(N.x,X.x)<min(P.x,H.x)) or (max(P.y,H.y)<min(N.y,X.y)) or (max(N.y,X.y)<min(P.y,H.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[73]` | `(max(P.x,H.x)<min(X.x,Q.x)) or (max(X.x,Q.x)<min(P.x,H.x)) or (max(P.y,H.y)<min(X.y,Q.y)) or (max(X.y,Q.y)<min(P.y,H.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[74]` | `(max(H.x,I.x)<min(N.x,X.x)) or (max(N.x,X.x)<min(H.x,I.x)) or (max(H.y,I.y)<min(N.y,X.y)) or (max(N.y,X.y)<min(H.y,I.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[75]` | `(max(H.x,I.x)<min(X.x,Q.x)) or (max(X.x,Q.x)<min(H.x,I.x)) or (max(H.y,I.y)<min(X.y,Q.y)) or (max(X.y,Q.y)<min(H.y,I.y))` |
| not self-intersecting / 軸平行な非隣接2辺の閉包が交わらない | `conditions[76]` | `(max(I.x,N.x)<min(X.x,Q.x)) or (max(X.x,Q.x)<min(I.x,N.x)) or (max(I.y,N.y)<min(X.y,Q.y)) or (max(X.y,Q.y)<min(I.y,N.y))` |
| all possible areas of triangle SIX / DSLは各許容配置の面積を返す | `target` | `Area(S, I, X)` |

## 残る制約

原問は可能な面積の集合を問う。値の列挙はしていない。集合の完全な採点と網羅性は後続担当で設計が必要。非隣接辺の矩形分離は軸平行性の下で線分非交差と同値。

AST検査の合格は幾何条件の同値性・実行可能性・一意性を保証しない。
