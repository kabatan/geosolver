# AIME-2001-I-05
一次資料: [2001_AIME_I_Problems.html](https://web.archive.org/web/20250619020424/https://artofproblemsolving.com/wiki/index.php/2001_AIME_I_Problems#Problem_5)、Problem 5、保存HTML行510。
DSL SHA-256: `5824188cc1cf796e9b204cc77f9440e7dee885d4aca560c52d9fc974172fc436`
問題節 SHA-256: `9215311fbe42ac674a8fc813a45291eee41ff88042962da41486dac278bd02f9`

## 原文（保存HTMLから抽出）

An equilateral triangle is inscribed in the ellipse whose equation is $x^2+4y^2=4$. One vertex of the triangle is $(0,1)$, one altitude is contained in the y-axis, and the length of each side is $\sqrt{\frac mn}$, where $m$ and $n$ are relatively prime positive integers. Find $m+n$.

## 座標・条件との読み合わせ

楕円の指定座標を保持。y軸上の高度に対して左右頂点を交換し、右側をBと呼ぶ。

- `constructions[0]` `{"name": "A", "expression": "Point(0, 1)"}` — 指定された頂点(0,1)。
- `constructions[1]` `{"name": "B", "expression": "Point(x, y)"}` — 残りの頂点。
- `constructions[2]` `{"name": "C", "expression": "Point(-x, y)"}` — y軸を含む高度は正三角形の対称軸。左右交換以外の枝を消さない。
- `conditions[0]` `{"left": "x**2 + 4*y**2", "operator": "=", "right": 4}` — Bが指定楕円上。Cの楕円条件は同じ式になる。
- `conditions[1]` `{"left": "Distance(A, B)", "operator": "=", "right": "Distance(B, C)"}` — 正三角形。AB=ACは構成で保証。
- `conditions[2]` `{"left": "x", "operator": ">", "right": 0}` — 左右の名付けと非退化。
- `conditions[3]` `{"left": "y", "operator": "<", "right": 1}` — A以外の頂点は楕円の最上点より下。
- `target` `Distance(B, C)` — 辺長そのもの。平方して分子分母を足すのは採点側。

## 独立検算

手計算: 正三角形より(1-y)^2=3x^2。楕円式へ代入すると13y^2-2y-11=0。退化y=1を除くとy=-11/13,x=8sqrt(3)/13。辺長の平方は768/169。

二次式の2根のうちy=1は三頂点が重なるため除外。残る左右交換で辺長は同じ。

幾何量参照値 `16*sqrt(3)/13`、採点変換 `square_fraction_sum`、Answer Key `937`。
90桁の独立評価器で全等式・不等式・構成の定義域を検査。詳細は `audit/substitution.json`。
解座標は監査専用で、DSL・初期点・探索箱には渡さない。solverおよび局所探索の実行なし。

# AIME-2001-I-07
一次資料: [2001_AIME_I_Problems.html](https://web.archive.org/web/20250619020424/https://artofproblemsolving.com/wiki/index.php/2001_AIME_I_Problems#Problem_7)、Problem 7、保存HTML行518。
DSL SHA-256: `157bad0c73d5e0f8907fbb26232fd03efa5cf1de8e77573e73204a056762a379`
問題節 SHA-256: `7ce34d591b38e83bb5b3efa629f980d41063324662ea83a7e296555d938ef4ba`

## 原文（保存HTMLから抽出）

Triangle $ABC$ has $AB=21$, $AC=22$ and $BC=20$. Points $D$ and $E$ are located on $\overline{AB}$ and $\overline{AC}$, respectively, such that $\overline{DE}$ is parallel to $\overline{BC}$ and contains the center of the inscribed circle of triangle $ABC$. Then $DE=\frac{m}{n}$, where $m$ and $n$ are relatively prime positive integers. Find $m+n$.

## 座標・条件との読み合わせ

B=(0,0), C=(20,0)、Aを上半平面に置く等長変換のみ。

- `constructions[0]` `{"name": "B", "expression": "Point(0, 0)"}` — 原点固定。
- `constructions[1]` `{"name": "C", "expression": "Point(20, 0)"}` — 原文BC=20。
- `constructions[2]` `{"name": "A", "expression": "Point(x, y)"}` — 第三頂点。
- `constructions[3]` `{"name": "I", "expression": "Incenter(A, B, C)"}` — 原文の内接円中心。
- `constructions[4]` `{"name": "D", "expression": "PointOnSegment(A, B, t)"}` — DはAB上。
- `constructions[5]` `{"name": "E", "expression": "PointOnSegment(A, C, u)"}` — EはAC上。
- `conditions[0]` `{"left": "Distance(A, B)", "operator": "=", "right": 21}` — 原文AB=21。
- `conditions[1]` `{"left": "Distance(A, C)", "operator": "=", "right": 22}` — 原文AC=22。
- `conditions[2]` `{"left": "y", "operator": ">", "right": 0}` — 非退化と鏡映固定。
- `conditions[3]` `{"left": "D.y", "operator": "=", "right": "E.y"}` — DEは水平なBCに平行。
- `conditions[4]` `{"left": "D.y", "operator": "=", "right": "I.y"}` — DEは内心を通る。
- `conditions[5]` `{"left": "t", "operator": ">", "right": 0}` — 内心を通る線が辺の内部と交わる。
- `conditions[6]` `{"left": "t", "operator": "<", "right": 1}` — 内心を通る線が辺の内部と交わる。
- `conditions[7]` `{"left": "u", "operator": ">", "right": 0}` — 内心を通る線が辺の内部と交わる。
- `conditions[8]` `{"left": "u", "operator": "<", "right": 1}` — 内心を通る線が辺の内部と交わる。
- `target` `Distance(D, E)` — 指定された長さDE。m+nは採点側。

## 独立検算

手計算: AB^2-AC^2からAのx座標357/40。y>0を選ぶ。内心の高さは(20/63)yなので、Aからの辺内分率は43/63。DE=(43/63)*20。

3辺で三角形は鏡像以外一意。内心を通る平行線と各辺の交点も一意。

幾何量参照値 `860/63`、採点変換 `fraction_sum`、Answer Key `923`。
90桁の独立評価器で全等式・不等式・構成の定義域を検査。詳細は `audit/substitution.json`。
解座標は監査専用で、DSL・初期点・探索箱には渡さない。solverおよび局所探索の実行なし。

# AIME-2001-II-04
一次資料: [2001_AIME_II_Problems.html](https://web.archive.org/web/20250819004621/https://artofproblemsolving.com/wiki/index.php/2001_AIME_II_Problems#Problem_4)、Problem 4、保存HTML行508。
DSL SHA-256: `2f8c1947de31affcda671e9b6848099f9b15a72ff3d048c11cfe5f174766075d`
問題節 SHA-256: `cfdebd3cf8cb36ecb699e9c96a7f739405d84fb5e80dfb2444b0e081d8db31f6`

## 原文（保存HTMLから抽出）

Let $R = (8,6)$. The lines whose equations are $8y = 15x$ and $10y = 3x$ contain points $P$ and $Q$, respectively, such that $R$ is the midpoint of $\overline{PQ}$. The length of $PQ$ equals $\frac {m}{n}$, where $m$ and $n$ are relatively prime positive integers. Find $m + n$.

## 座標・条件との読み合わせ

指定された直交座標系をそのまま使う。PとQのx座標を自由変数にする。

- `constructions[0]` `{"name": "P", "expression": "Point(p, 15*p/8)"}` — Pは8y=15x上。
- `constructions[1]` `{"name": "Q", "expression": "Point(q, 3*q/10)"}` — Qは10y=3x上。
- `constructions[2]` `{"name": "R", "expression": "Point(8, 6)"}` — 原文のR=(8,6)。
- `constructions[3]` `{"name": "M", "expression": "Midpoint(P, Q)"}` — 線分PQの中点の定義。
- `conditions[0]` `{"left": "M.x", "operator": "=", "right": "R.x"}` — RがPQの中点（x座標）。
- `conditions[1]` `{"left": "M.y", "operator": "=", "right": "R.y"}` — RがPQの中点（y座標）。
- `conditions[2]` `{"left": "Distance(P, Q)", "operator": ">", "right": 0}` — 非退化な線分PQ。
- `target` `Distance(P, Q)` — 線分PQの長さ。

## 独立検算

手計算: p+q=16,15p/8+3q/10=12を消去。P=(32/7,60/7), Q=(80/7,24/7)。PQ=60/7。

異なる傾きの二直線と中点条件の2元線形系の行列式は非零。

幾何量参照値 `60/7`、採点変換 `fraction_sum`、Answer Key `067`。
90桁の独立評価器で全等式・不等式・構成の定義域を検査。詳細は `audit/substitution.json`。
解座標は監査専用で、DSL・初期点・探索箱には渡さない。solverおよび局所探索の実行なし。

# AIME-2001-II-13
一次資料: [2001_AIME_II_Problems.html](https://web.archive.org/web/20250819004621/https://artofproblemsolving.com/wiki/index.php/2001_AIME_II_Problems#Problem_13)、Problem 13、保存HTML行544。
DSL SHA-256: `8303b7a3383fe26dc518f50bebc3fab75bee3ab76aedb1580b159f7db0022d6e`
問題節 SHA-256: `47a863dbd0908c880ecf8afb7c342704ae1c61258ce365865b863e13423ee233`

## 原文（保存HTMLから抽出）

In quadrilateral $ABCD$, $\angle{BAD}\cong\angle{ADC}$ and $\angle{ABD}\cong\angle{BCD}$, $AB = 8$, $BD = 10$, and $BC = 6$. The length $CD$ may be written in the form $\frac {m}{n}$, where $m$ and $n$ are relatively prime positive integers. Find $m + n$.

## 座標・条件との読み合わせ

B=(0,0),D=(10,0)、Aを上、Cを下に置く。原文の四角形の順序と対角線BDを保持。

- `constructions[0]` `{"name": "B", "expression": "Point(0, 0)"}` — 原点。
- `constructions[1]` `{"name": "D", "expression": "Point(10, 0)"}` — 原文BD=10。
- `constructions[2]` `{"name": "A", "expression": "Point(ax, ay)"}` — AはBDの上側。
- `constructions[3]` `{"name": "C", "expression": "Point(cx, cy)"}` — CはBDの反対側。
- `conditions[0]` `{"left": "Distance(A, B)", "operator": "=", "right": 8}` — 原文AB=8。
- `conditions[1]` `{"left": "Distance(B, C)", "operator": "=", "right": 6}` — 原文BC=6。
- `conditions[2]` `{"left": "Angle(B, A, D)", "operator": "=", "right": "Angle(A, D, C)"}` — 原文角BAD=角ADC。
- `conditions[3]` `{"left": "Angle(A, B, D)", "operator": "=", "right": "Angle(B, C, D)"}` — 原文角ABD=角BCD。
- `conditions[4]` `{"left": "ay", "operator": ">", "right": 0}` — 鏡映固定。
- `conditions[5]` `{"left": "cy", "operator": "<", "right": 0}` — 対角線BDの両側にA,C。
- `conditions[6]` `{"predicate": "ConvexPolygon([A, B, C, D])"}` — 通常の内角を指定した四角形の枝。内角A=Dと角C=角ABDの枝を保持。
- `target` `Distance(C, D)` — 辺長CD。

## 独立検算

手計算: beta=角ABD=角BCD, gamma=角ADBとする。角BAD=角ADCから角CBD=2gamma。正弦定理でsin(beta+gamma)=(5/4)sin(gamma), sin(beta+2gamma)=(3/5)sin(beta)。cot(gamma)=(5/4-cos(beta))/sin(beta)を代入してcos(beta)=13/20,cot(gamma)=12/sqrt(231)。CD=10 sin(2gamma)/sin(beta)=64/5。

原文の内角の等式ではA,Dはともに凹角にできず、C=角ABDも180度未満。対角線の角分割と正弦定理の正の三角形枝でcos(beta)=13/20が一意に決まる。

幾何量参照値 `64/5`、採点変換 `fraction_sum`、Answer Key `069`。
90桁の独立評価器で全等式・不等式・構成の定義域を検査。詳細は `audit/substitution.json`。
解座標は監査専用で、DSL・初期点・探索箱には渡さない。solverおよび局所探索の実行なし。

# AIME-2002-I-02
一次資料: [2002_AIME_I_Problems.html](https://web.archive.org/web/20250819012652/https://artofproblemsolving.com/wiki/index.php/2002_AIME_I_Problems#Problem_2)、Problem 2、保存HTML行498。
DSL SHA-256: `59438973ddf49ca54793a20cabc450d36087db42b4e0199e657a9247406fc872`
問題節 SHA-256: `6c3fe118770cd9c89268dcb3d1d787d753183c953eff137a8be2d9a3083caf4d`

## 原文（保存HTMLから抽出）

The diagram shows twenty congruent circles arranged in three rows and enclosed in a rectangle. The circles are tangent to one another and to the sides of the rectangle as shown in the diagram. The ratio of the longer dimension of the rectangle to the shorter dimension can be written as $\frac{1}{2}\left(\sqrt{p}-q\right)$, where $p$ and $q$ are positive integers. Find $p+q$.


[asy] size(250);real x=sqrt(3); int i; draw(origin--(14,0)--(14,2+2x)--(0,2+2x)--cycle); for(i=0; i<7; i=i+1) { draw(Circle((2*i+1,1), 1)^^Circle((2*i+1,1+2x), 1)); } for(i=0; i<6; i=i+1) { draw(Circle((2*i+2,1+x), 1)); } [/asy]

## 座標・条件との読み合わせ

比だけなので共通半径1。Asymptoteは接続・3行の7/6/7個の位相だけに使用し、sqrt(3)等の完成座標は入力しない。

- `constructions[0]` `{"name": "W", "expression": "2 + 6*s"}` — 横7個、左右端の円が左右辺に接する。半径の2は定義、6は7個の6間隔。
- `constructions[1]` `{"name": "H", "expression": "w + 1"}` — 上段中心の高さwに半径1を足した長方形高。
- `constructions[2]` `{"name": "L0", "expression": "Point(1 + 0*s, 1)"}` — 図のL段の1番目の中心。水平に並ぶ等半径の接円の中心間隔sを共通化。
- `constructions[3]` `{"name": "L1", "expression": "Point(1 + 1*s, 1)"}` — 図のL段の2番目の中心。水平に並ぶ等半径の接円の中心間隔sを共通化。
- `constructions[4]` `{"name": "L2", "expression": "Point(1 + 2*s, 1)"}` — 図のL段の3番目の中心。水平に並ぶ等半径の接円の中心間隔sを共通化。
- `constructions[5]` `{"name": "L3", "expression": "Point(1 + 3*s, 1)"}` — 図のL段の4番目の中心。水平に並ぶ等半径の接円の中心間隔sを共通化。
- `constructions[6]` `{"name": "L4", "expression": "Point(1 + 4*s, 1)"}` — 図のL段の5番目の中心。水平に並ぶ等半径の接円の中心間隔sを共通化。
- `constructions[7]` `{"name": "L5", "expression": "Point(1 + 5*s, 1)"}` — 図のL段の6番目の中心。水平に並ぶ等半径の接円の中心間隔sを共通化。
- `constructions[8]` `{"name": "L6", "expression": "Point(1 + 6*s, 1)"}` — 図のL段の7番目の中心。水平に並ぶ等半径の接円の中心間隔sを共通化。
- `constructions[9]` `{"name": "M0", "expression": "Point(u + 0*s, v)"}` — 図のM段の1番目の中心。水平に並ぶ等半径の接円の中心間隔sを共通化。
- `constructions[10]` `{"name": "M1", "expression": "Point(u + 1*s, v)"}` — 図のM段の2番目の中心。水平に並ぶ等半径の接円の中心間隔sを共通化。
- `constructions[11]` `{"name": "M2", "expression": "Point(u + 2*s, v)"}` — 図のM段の3番目の中心。水平に並ぶ等半径の接円の中心間隔sを共通化。
- `constructions[12]` `{"name": "M3", "expression": "Point(u + 3*s, v)"}` — 図のM段の4番目の中心。水平に並ぶ等半径の接円の中心間隔sを共通化。
- `constructions[13]` `{"name": "M4", "expression": "Point(u + 4*s, v)"}` — 図のM段の5番目の中心。水平に並ぶ等半径の接円の中心間隔sを共通化。
- `constructions[14]` `{"name": "M5", "expression": "Point(u + 5*s, v)"}` — 図のM段の6番目の中心。水平に並ぶ等半径の接円の中心間隔sを共通化。
- `constructions[15]` `{"name": "T0", "expression": "Point(1 + 0*s, w)"}` — 図のT段の1番目の中心。水平に並ぶ等半径の接円の中心間隔sを共通化。
- `constructions[16]` `{"name": "T1", "expression": "Point(1 + 1*s, w)"}` — 図のT段の2番目の中心。水平に並ぶ等半径の接円の中心間隔sを共通化。
- `constructions[17]` `{"name": "T2", "expression": "Point(1 + 2*s, w)"}` — 図のT段の3番目の中心。水平に並ぶ等半径の接円の中心間隔sを共通化。
- `constructions[18]` `{"name": "T3", "expression": "Point(1 + 3*s, w)"}` — 図のT段の4番目の中心。水平に並ぶ等半径の接円の中心間隔sを共通化。
- `constructions[19]` `{"name": "T4", "expression": "Point(1 + 4*s, w)"}` — 図のT段の5番目の中心。水平に並ぶ等半径の接円の中心間隔sを共通化。
- `constructions[20]` `{"name": "T5", "expression": "Point(1 + 5*s, w)"}` — 図のT段の6番目の中心。水平に並ぶ等半径の接円の中心間隔sを共通化。
- `constructions[21]` `{"name": "T6", "expression": "Point(1 + 6*s, w)"}` — 図のT段の7番目の中心。水平に並ぶ等半径の接円の中心間隔sを共通化。
- `conditions[0]` `{"left": "s", "operator": ">", "right": 0}` — 各行を左から右へ列挙。
- `conditions[1]` `{"left": "u", "operator": ">", "right": 1}` — 中段は下段の隙間に入る。
- `conditions[2]` `{"left": "u", "operator": "<", "right": "1+s"}` — 中段先頭は下段先頭と次の中心の間。
- `conditions[3]` `{"left": "v", "operator": ">", "right": 1}` — 中段は下段より上。
- `conditions[4]` `{"left": "w", "operator": ">", "right": "v"}` — 上段は中段より上。
- `conditions[5]` `{"left": "Distance(L0, L1)", "operator": "=", "right": 2}` — 図の同一行の隣接する単位円の外接。
- `conditions[6]` `{"left": "Distance(L1, L2)", "operator": "=", "right": 2}` — 図の同一行の隣接する単位円の外接。
- `conditions[7]` `{"left": "Distance(L2, L3)", "operator": "=", "right": 2}` — 図の同一行の隣接する単位円の外接。
- `conditions[8]` `{"left": "Distance(L3, L4)", "operator": "=", "right": 2}` — 図の同一行の隣接する単位円の外接。
- `conditions[9]` `{"left": "Distance(L4, L5)", "operator": "=", "right": 2}` — 図の同一行の隣接する単位円の外接。
- `conditions[10]` `{"left": "Distance(L5, L6)", "operator": "=", "right": 2}` — 図の同一行の隣接する単位円の外接。
- `conditions[11]` `{"left": "Distance(M0, M1)", "operator": "=", "right": 2}` — 図の同一行の隣接する単位円の外接。
- `conditions[12]` `{"left": "Distance(M1, M2)", "operator": "=", "right": 2}` — 図の同一行の隣接する単位円の外接。
- `conditions[13]` `{"left": "Distance(M2, M3)", "operator": "=", "right": 2}` — 図の同一行の隣接する単位円の外接。
- `conditions[14]` `{"left": "Distance(M3, M4)", "operator": "=", "right": 2}` — 図の同一行の隣接する単位円の外接。
- `conditions[15]` `{"left": "Distance(M4, M5)", "operator": "=", "right": 2}` — 図の同一行の隣接する単位円の外接。
- `conditions[16]` `{"left": "Distance(T0, T1)", "operator": "=", "right": 2}` — 図の同一行の隣接する単位円の外接。
- `conditions[17]` `{"left": "Distance(T1, T2)", "operator": "=", "right": 2}` — 図の同一行の隣接する単位円の外接。
- `conditions[18]` `{"left": "Distance(T2, T3)", "operator": "=", "right": 2}` — 図の同一行の隣接する単位円の外接。
- `conditions[19]` `{"left": "Distance(T3, T4)", "operator": "=", "right": 2}` — 図の同一行の隣接する単位円の外接。
- `conditions[20]` `{"left": "Distance(T4, T5)", "operator": "=", "right": 2}` — 図の同一行の隣接する単位円の外接。
- `conditions[21]` `{"left": "Distance(T5, T6)", "operator": "=", "right": 2}` — 図の同一行の隣接する単位円の外接。
- `conditions[22]` `{"left": "Distance(M0, L0)", "operator": "=", "right": 2}` — 図の上下段と中段の隣接円の外接。
- `conditions[23]` `{"left": "Distance(M0, L1)", "operator": "=", "right": 2}` — 図の上下段と中段の隣接円の外接。
- `conditions[24]` `{"left": "Distance(M0, T0)", "operator": "=", "right": 2}` — 図の上下段と中段の隣接円の外接。
- `conditions[25]` `{"left": "Distance(M0, T1)", "operator": "=", "right": 2}` — 図の上下段と中段の隣接円の外接。
- `conditions[26]` `{"left": "Distance(M1, L1)", "operator": "=", "right": 2}` — 図の上下段と中段の隣接円の外接。
- `conditions[27]` `{"left": "Distance(M1, L2)", "operator": "=", "right": 2}` — 図の上下段と中段の隣接円の外接。
- `conditions[28]` `{"left": "Distance(M1, T1)", "operator": "=", "right": 2}` — 図の上下段と中段の隣接円の外接。
- `conditions[29]` `{"left": "Distance(M1, T2)", "operator": "=", "right": 2}` — 図の上下段と中段の隣接円の外接。
- `conditions[30]` `{"left": "Distance(M2, L2)", "operator": "=", "right": 2}` — 図の上下段と中段の隣接円の外接。
- `conditions[31]` `{"left": "Distance(M2, L3)", "operator": "=", "right": 2}` — 図の上下段と中段の隣接円の外接。
- `conditions[32]` `{"left": "Distance(M2, T2)", "operator": "=", "right": 2}` — 図の上下段と中段の隣接円の外接。
- `conditions[33]` `{"left": "Distance(M2, T3)", "operator": "=", "right": 2}` — 図の上下段と中段の隣接円の外接。
- `conditions[34]` `{"left": "Distance(M3, L3)", "operator": "=", "right": 2}` — 図の上下段と中段の隣接円の外接。
- `conditions[35]` `{"left": "Distance(M3, L4)", "operator": "=", "right": 2}` — 図の上下段と中段の隣接円の外接。
- `conditions[36]` `{"left": "Distance(M3, T3)", "operator": "=", "right": 2}` — 図の上下段と中段の隣接円の外接。
- `conditions[37]` `{"left": "Distance(M3, T4)", "operator": "=", "right": 2}` — 図の上下段と中段の隣接円の外接。
- `conditions[38]` `{"left": "Distance(M4, L4)", "operator": "=", "right": 2}` — 図の上下段と中段の隣接円の外接。
- `conditions[39]` `{"left": "Distance(M4, L5)", "operator": "=", "right": 2}` — 図の上下段と中段の隣接円の外接。
- `conditions[40]` `{"left": "Distance(M4, T4)", "operator": "=", "right": 2}` — 図の上下段と中段の隣接円の外接。
- `conditions[41]` `{"left": "Distance(M4, T5)", "operator": "=", "right": 2}` — 図の上下段と中段の隣接円の外接。
- `conditions[42]` `{"left": "Distance(M5, L5)", "operator": "=", "right": 2}` — 図の上下段と中段の隣接円の外接。
- `conditions[43]` `{"left": "Distance(M5, L6)", "operator": "=", "right": 2}` — 図の上下段と中段の隣接円の外接。
- `conditions[44]` `{"left": "Distance(M5, T5)", "operator": "=", "right": 2}` — 図の上下段と中段の隣接円の外接。
- `conditions[45]` `{"left": "Distance(M5, T6)", "operator": "=", "right": 2}` — 図の上下段と中段の隣接円の外接。
- `conditions[46]` `{"left": "L0.x", "operator": ">=", "right": 1}` — 円が長方形の左辺より内側。
- `conditions[47]` `{"left": "L0.x", "operator": "<=", "right": "W-1"}` — 円が長方形の右辺より内側。
- `conditions[48]` `{"left": "L0.y", "operator": ">=", "right": 1}` — 円が下辺より内側。
- `conditions[49]` `{"left": "L0.y", "operator": "<=", "right": "H-1"}` — 円が上辺より内側。
- `conditions[50]` `{"left": "L1.x", "operator": ">=", "right": 1}` — 円が長方形の左辺より内側。
- `conditions[51]` `{"left": "L1.x", "operator": "<=", "right": "W-1"}` — 円が長方形の右辺より内側。
- `conditions[52]` `{"left": "L1.y", "operator": ">=", "right": 1}` — 円が下辺より内側。
- `conditions[53]` `{"left": "L1.y", "operator": "<=", "right": "H-1"}` — 円が上辺より内側。
- `conditions[54]` `{"left": "L2.x", "operator": ">=", "right": 1}` — 円が長方形の左辺より内側。
- `conditions[55]` `{"left": "L2.x", "operator": "<=", "right": "W-1"}` — 円が長方形の右辺より内側。
- `conditions[56]` `{"left": "L2.y", "operator": ">=", "right": 1}` — 円が下辺より内側。
- `conditions[57]` `{"left": "L2.y", "operator": "<=", "right": "H-1"}` — 円が上辺より内側。
- `conditions[58]` `{"left": "L3.x", "operator": ">=", "right": 1}` — 円が長方形の左辺より内側。
- `conditions[59]` `{"left": "L3.x", "operator": "<=", "right": "W-1"}` — 円が長方形の右辺より内側。
- `conditions[60]` `{"left": "L3.y", "operator": ">=", "right": 1}` — 円が下辺より内側。
- `conditions[61]` `{"left": "L3.y", "operator": "<=", "right": "H-1"}` — 円が上辺より内側。
- `conditions[62]` `{"left": "L4.x", "operator": ">=", "right": 1}` — 円が長方形の左辺より内側。
- `conditions[63]` `{"left": "L4.x", "operator": "<=", "right": "W-1"}` — 円が長方形の右辺より内側。
- `conditions[64]` `{"left": "L4.y", "operator": ">=", "right": 1}` — 円が下辺より内側。
- `conditions[65]` `{"left": "L4.y", "operator": "<=", "right": "H-1"}` — 円が上辺より内側。
- `conditions[66]` `{"left": "L5.x", "operator": ">=", "right": 1}` — 円が長方形の左辺より内側。
- `conditions[67]` `{"left": "L5.x", "operator": "<=", "right": "W-1"}` — 円が長方形の右辺より内側。
- `conditions[68]` `{"left": "L5.y", "operator": ">=", "right": 1}` — 円が下辺より内側。
- `conditions[69]` `{"left": "L5.y", "operator": "<=", "right": "H-1"}` — 円が上辺より内側。
- `conditions[70]` `{"left": "L6.x", "operator": ">=", "right": 1}` — 円が長方形の左辺より内側。
- `conditions[71]` `{"left": "L6.x", "operator": "<=", "right": "W-1"}` — 円が長方形の右辺より内側。
- `conditions[72]` `{"left": "L6.y", "operator": ">=", "right": 1}` — 円が下辺より内側。
- `conditions[73]` `{"left": "L6.y", "operator": "<=", "right": "H-1"}` — 円が上辺より内側。
- `conditions[74]` `{"left": "M0.x", "operator": ">=", "right": 1}` — 円が長方形の左辺より内側。
- `conditions[75]` `{"left": "M0.x", "operator": "<=", "right": "W-1"}` — 円が長方形の右辺より内側。
- `conditions[76]` `{"left": "M0.y", "operator": ">=", "right": 1}` — 円が下辺より内側。
- `conditions[77]` `{"left": "M0.y", "operator": "<=", "right": "H-1"}` — 円が上辺より内側。
- `conditions[78]` `{"left": "M1.x", "operator": ">=", "right": 1}` — 円が長方形の左辺より内側。
- `conditions[79]` `{"left": "M1.x", "operator": "<=", "right": "W-1"}` — 円が長方形の右辺より内側。
- `conditions[80]` `{"left": "M1.y", "operator": ">=", "right": 1}` — 円が下辺より内側。
- `conditions[81]` `{"left": "M1.y", "operator": "<=", "right": "H-1"}` — 円が上辺より内側。
- `conditions[82]` `{"left": "M2.x", "operator": ">=", "right": 1}` — 円が長方形の左辺より内側。
- `conditions[83]` `{"left": "M2.x", "operator": "<=", "right": "W-1"}` — 円が長方形の右辺より内側。
- `conditions[84]` `{"left": "M2.y", "operator": ">=", "right": 1}` — 円が下辺より内側。
- `conditions[85]` `{"left": "M2.y", "operator": "<=", "right": "H-1"}` — 円が上辺より内側。
- `conditions[86]` `{"left": "M3.x", "operator": ">=", "right": 1}` — 円が長方形の左辺より内側。
- `conditions[87]` `{"left": "M3.x", "operator": "<=", "right": "W-1"}` — 円が長方形の右辺より内側。
- `conditions[88]` `{"left": "M3.y", "operator": ">=", "right": 1}` — 円が下辺より内側。
- `conditions[89]` `{"left": "M3.y", "operator": "<=", "right": "H-1"}` — 円が上辺より内側。
- `conditions[90]` `{"left": "M4.x", "operator": ">=", "right": 1}` — 円が長方形の左辺より内側。
- `conditions[91]` `{"left": "M4.x", "operator": "<=", "right": "W-1"}` — 円が長方形の右辺より内側。
- `conditions[92]` `{"left": "M4.y", "operator": ">=", "right": 1}` — 円が下辺より内側。
- `conditions[93]` `{"left": "M4.y", "operator": "<=", "right": "H-1"}` — 円が上辺より内側。
- `conditions[94]` `{"left": "M5.x", "operator": ">=", "right": 1}` — 円が長方形の左辺より内側。
- `conditions[95]` `{"left": "M5.x", "operator": "<=", "right": "W-1"}` — 円が長方形の右辺より内側。
- `conditions[96]` `{"left": "M5.y", "operator": ">=", "right": 1}` — 円が下辺より内側。
- `conditions[97]` `{"left": "M5.y", "operator": "<=", "right": "H-1"}` — 円が上辺より内側。
- `conditions[98]` `{"left": "T0.x", "operator": ">=", "right": 1}` — 円が長方形の左辺より内側。
- `conditions[99]` `{"left": "T0.x", "operator": "<=", "right": "W-1"}` — 円が長方形の右辺より内側。
- `conditions[100]` `{"left": "T0.y", "operator": ">=", "right": 1}` — 円が下辺より内側。
- `conditions[101]` `{"left": "T0.y", "operator": "<=", "right": "H-1"}` — 円が上辺より内側。
- `conditions[102]` `{"left": "T1.x", "operator": ">=", "right": 1}` — 円が長方形の左辺より内側。
- `conditions[103]` `{"left": "T1.x", "operator": "<=", "right": "W-1"}` — 円が長方形の右辺より内側。
- `conditions[104]` `{"left": "T1.y", "operator": ">=", "right": 1}` — 円が下辺より内側。
- `conditions[105]` `{"left": "T1.y", "operator": "<=", "right": "H-1"}` — 円が上辺より内側。
- `conditions[106]` `{"left": "T2.x", "operator": ">=", "right": 1}` — 円が長方形の左辺より内側。
- `conditions[107]` `{"left": "T2.x", "operator": "<=", "right": "W-1"}` — 円が長方形の右辺より内側。
- `conditions[108]` `{"left": "T2.y", "operator": ">=", "right": 1}` — 円が下辺より内側。
- `conditions[109]` `{"left": "T2.y", "operator": "<=", "right": "H-1"}` — 円が上辺より内側。
- `conditions[110]` `{"left": "T3.x", "operator": ">=", "right": 1}` — 円が長方形の左辺より内側。
- `conditions[111]` `{"left": "T3.x", "operator": "<=", "right": "W-1"}` — 円が長方形の右辺より内側。
- `conditions[112]` `{"left": "T3.y", "operator": ">=", "right": 1}` — 円が下辺より内側。
- `conditions[113]` `{"left": "T3.y", "operator": "<=", "right": "H-1"}` — 円が上辺より内側。
- `conditions[114]` `{"left": "T4.x", "operator": ">=", "right": 1}` — 円が長方形の左辺より内側。
- `conditions[115]` `{"left": "T4.x", "operator": "<=", "right": "W-1"}` — 円が長方形の右辺より内側。
- `conditions[116]` `{"left": "T4.y", "operator": ">=", "right": 1}` — 円が下辺より内側。
- `conditions[117]` `{"left": "T4.y", "operator": "<=", "right": "H-1"}` — 円が上辺より内側。
- `conditions[118]` `{"left": "T5.x", "operator": ">=", "right": 1}` — 円が長方形の左辺より内側。
- `conditions[119]` `{"left": "T5.x", "operator": "<=", "right": "W-1"}` — 円が長方形の右辺より内側。
- `conditions[120]` `{"left": "T5.y", "operator": ">=", "right": 1}` — 円が下辺より内側。
- `conditions[121]` `{"left": "T5.y", "operator": "<=", "right": "H-1"}` — 円が上辺より内側。
- `conditions[122]` `{"left": "T6.x", "operator": ">=", "right": 1}` — 円が長方形の左辺より内側。
- `conditions[123]` `{"left": "T6.x", "operator": "<=", "right": "W-1"}` — 円が長方形の右辺より内側。
- `conditions[124]` `{"left": "T6.y", "operator": ">=", "right": 1}` — 円が下辺より内側。
- `conditions[125]` `{"left": "T6.y", "operator": "<=", "right": "H-1"}` — 円が上辺より内側。
- `conditions[126]` `{"left": "W", "operator": ">", "right": "H"}` — 長い辺/短い辺。図の横長の枝を表す。
- `target` `W/H` — 長辺/短辺の比。sqrt(p), qの抽出は採点側。

## 独立検算

手計算: 同じ行の接円からs=2。中段先頭が下段2中心から距離2なので横座標u=2、上側の高さv=1+sqrt(3)。同じ計算でw=1+2sqrt(3)。幅14、高さ2+2sqrt(3)。

3行の順序u>1, u<1+s,1<v<wにより上下の交点の枝が一意。全20円の包含と全ペア非重複を追加で検算する。

幾何量参照値 `(7*sqrt(3)-7)/2`、採点変換 `half_sqrt_minus_integer`、Answer Key `154`。
90桁の独立評価器で全等式・不等式・構成の定義域を検査。詳細は `audit/substitution.json`。
解座標は監査専用で、DSL・初期点・探索箱には渡さない。solverおよび局所探索の実行なし。

# AIME-2003-I-02
一次資料: [2003_AIME_I_Problems.html](https://web.archive.org/web/20250819014932/https://artofproblemsolving.com/wiki/index.php/2003_AIME_I_Problems#Problem_2)、Problem 2、保存HTML行501。
DSL SHA-256: `08db8e923c9422f89b62dd1363b2e3e4d22e530fe6143022a3364f7d71833ae2`
問題節 SHA-256: `97f4d2502944ec804e41d147730a5ae5497bb77a60d84b71dc3c48a3c3f26e67`

## 原文（保存HTMLから抽出）

One hundred concentric circles with radii $1, 2, 3, \dots, 100$ are drawn in a plane. The interior of the circle of radius 1 is colored red, and each region bounded by consecutive circles is colored either red or green, with no two adjacent regions the same color. The ratio of the total area of the green regions to the area of the circle of radius 100 can be expressed as $m/n,$ where $m$ and $n$ are relatively prime positive integers. Find $m + n.$

## 座標・条件との読み合わせ

全同心円の中心を原点へ移すだけ。自由な未知量のない有限配置も除外しない。

- `constructions[0]` `{"name": "O", "expression": "Point(0, 0)"}` — 同心円の共通中心。
- `constructions[1]` `{"name": "C1", "expression": "Circle(O, 1)"}` — 原文の半径列1,2,...,100の第1円。
- `constructions[2]` `{"name": "C2", "expression": "Circle(O, 2)"}` — 原文の半径列1,2,...,100の第2円。
- `constructions[3]` `{"name": "C3", "expression": "Circle(O, 3)"}` — 原文の半径列1,2,...,100の第3円。
- `constructions[4]` `{"name": "C4", "expression": "Circle(O, 4)"}` — 原文の半径列1,2,...,100の第4円。
- `constructions[5]` `{"name": "C5", "expression": "Circle(O, 5)"}` — 原文の半径列1,2,...,100の第5円。
- `constructions[6]` `{"name": "C6", "expression": "Circle(O, 6)"}` — 原文の半径列1,2,...,100の第6円。
- `constructions[7]` `{"name": "C7", "expression": "Circle(O, 7)"}` — 原文の半径列1,2,...,100の第7円。
- `constructions[8]` `{"name": "C8", "expression": "Circle(O, 8)"}` — 原文の半径列1,2,...,100の第8円。
- `constructions[9]` `{"name": "C9", "expression": "Circle(O, 9)"}` — 原文の半径列1,2,...,100の第9円。
- `constructions[10]` `{"name": "C10", "expression": "Circle(O, 10)"}` — 原文の半径列1,2,...,100の第10円。
- `constructions[11]` `{"name": "C11", "expression": "Circle(O, 11)"}` — 原文の半径列1,2,...,100の第11円。
- `constructions[12]` `{"name": "C12", "expression": "Circle(O, 12)"}` — 原文の半径列1,2,...,100の第12円。
- `constructions[13]` `{"name": "C13", "expression": "Circle(O, 13)"}` — 原文の半径列1,2,...,100の第13円。
- `constructions[14]` `{"name": "C14", "expression": "Circle(O, 14)"}` — 原文の半径列1,2,...,100の第14円。
- `constructions[15]` `{"name": "C15", "expression": "Circle(O, 15)"}` — 原文の半径列1,2,...,100の第15円。
- `constructions[16]` `{"name": "C16", "expression": "Circle(O, 16)"}` — 原文の半径列1,2,...,100の第16円。
- `constructions[17]` `{"name": "C17", "expression": "Circle(O, 17)"}` — 原文の半径列1,2,...,100の第17円。
- `constructions[18]` `{"name": "C18", "expression": "Circle(O, 18)"}` — 原文の半径列1,2,...,100の第18円。
- `constructions[19]` `{"name": "C19", "expression": "Circle(O, 19)"}` — 原文の半径列1,2,...,100の第19円。
- `constructions[20]` `{"name": "C20", "expression": "Circle(O, 20)"}` — 原文の半径列1,2,...,100の第20円。
- `constructions[21]` `{"name": "C21", "expression": "Circle(O, 21)"}` — 原文の半径列1,2,...,100の第21円。
- `constructions[22]` `{"name": "C22", "expression": "Circle(O, 22)"}` — 原文の半径列1,2,...,100の第22円。
- `constructions[23]` `{"name": "C23", "expression": "Circle(O, 23)"}` — 原文の半径列1,2,...,100の第23円。
- `constructions[24]` `{"name": "C24", "expression": "Circle(O, 24)"}` — 原文の半径列1,2,...,100の第24円。
- `constructions[25]` `{"name": "C25", "expression": "Circle(O, 25)"}` — 原文の半径列1,2,...,100の第25円。
- `constructions[26]` `{"name": "C26", "expression": "Circle(O, 26)"}` — 原文の半径列1,2,...,100の第26円。
- `constructions[27]` `{"name": "C27", "expression": "Circle(O, 27)"}` — 原文の半径列1,2,...,100の第27円。
- `constructions[28]` `{"name": "C28", "expression": "Circle(O, 28)"}` — 原文の半径列1,2,...,100の第28円。
- `constructions[29]` `{"name": "C29", "expression": "Circle(O, 29)"}` — 原文の半径列1,2,...,100の第29円。
- `constructions[30]` `{"name": "C30", "expression": "Circle(O, 30)"}` — 原文の半径列1,2,...,100の第30円。
- `constructions[31]` `{"name": "C31", "expression": "Circle(O, 31)"}` — 原文の半径列1,2,...,100の第31円。
- `constructions[32]` `{"name": "C32", "expression": "Circle(O, 32)"}` — 原文の半径列1,2,...,100の第32円。
- `constructions[33]` `{"name": "C33", "expression": "Circle(O, 33)"}` — 原文の半径列1,2,...,100の第33円。
- `constructions[34]` `{"name": "C34", "expression": "Circle(O, 34)"}` — 原文の半径列1,2,...,100の第34円。
- `constructions[35]` `{"name": "C35", "expression": "Circle(O, 35)"}` — 原文の半径列1,2,...,100の第35円。
- `constructions[36]` `{"name": "C36", "expression": "Circle(O, 36)"}` — 原文の半径列1,2,...,100の第36円。
- `constructions[37]` `{"name": "C37", "expression": "Circle(O, 37)"}` — 原文の半径列1,2,...,100の第37円。
- `constructions[38]` `{"name": "C38", "expression": "Circle(O, 38)"}` — 原文の半径列1,2,...,100の第38円。
- `constructions[39]` `{"name": "C39", "expression": "Circle(O, 39)"}` — 原文の半径列1,2,...,100の第39円。
- `constructions[40]` `{"name": "C40", "expression": "Circle(O, 40)"}` — 原文の半径列1,2,...,100の第40円。
- `constructions[41]` `{"name": "C41", "expression": "Circle(O, 41)"}` — 原文の半径列1,2,...,100の第41円。
- `constructions[42]` `{"name": "C42", "expression": "Circle(O, 42)"}` — 原文の半径列1,2,...,100の第42円。
- `constructions[43]` `{"name": "C43", "expression": "Circle(O, 43)"}` — 原文の半径列1,2,...,100の第43円。
- `constructions[44]` `{"name": "C44", "expression": "Circle(O, 44)"}` — 原文の半径列1,2,...,100の第44円。
- `constructions[45]` `{"name": "C45", "expression": "Circle(O, 45)"}` — 原文の半径列1,2,...,100の第45円。
- `constructions[46]` `{"name": "C46", "expression": "Circle(O, 46)"}` — 原文の半径列1,2,...,100の第46円。
- `constructions[47]` `{"name": "C47", "expression": "Circle(O, 47)"}` — 原文の半径列1,2,...,100の第47円。
- `constructions[48]` `{"name": "C48", "expression": "Circle(O, 48)"}` — 原文の半径列1,2,...,100の第48円。
- `constructions[49]` `{"name": "C49", "expression": "Circle(O, 49)"}` — 原文の半径列1,2,...,100の第49円。
- `constructions[50]` `{"name": "C50", "expression": "Circle(O, 50)"}` — 原文の半径列1,2,...,100の第50円。
- `constructions[51]` `{"name": "C51", "expression": "Circle(O, 51)"}` — 原文の半径列1,2,...,100の第51円。
- `constructions[52]` `{"name": "C52", "expression": "Circle(O, 52)"}` — 原文の半径列1,2,...,100の第52円。
- `constructions[53]` `{"name": "C53", "expression": "Circle(O, 53)"}` — 原文の半径列1,2,...,100の第53円。
- `constructions[54]` `{"name": "C54", "expression": "Circle(O, 54)"}` — 原文の半径列1,2,...,100の第54円。
- `constructions[55]` `{"name": "C55", "expression": "Circle(O, 55)"}` — 原文の半径列1,2,...,100の第55円。
- `constructions[56]` `{"name": "C56", "expression": "Circle(O, 56)"}` — 原文の半径列1,2,...,100の第56円。
- `constructions[57]` `{"name": "C57", "expression": "Circle(O, 57)"}` — 原文の半径列1,2,...,100の第57円。
- `constructions[58]` `{"name": "C58", "expression": "Circle(O, 58)"}` — 原文の半径列1,2,...,100の第58円。
- `constructions[59]` `{"name": "C59", "expression": "Circle(O, 59)"}` — 原文の半径列1,2,...,100の第59円。
- `constructions[60]` `{"name": "C60", "expression": "Circle(O, 60)"}` — 原文の半径列1,2,...,100の第60円。
- `constructions[61]` `{"name": "C61", "expression": "Circle(O, 61)"}` — 原文の半径列1,2,...,100の第61円。
- `constructions[62]` `{"name": "C62", "expression": "Circle(O, 62)"}` — 原文の半径列1,2,...,100の第62円。
- `constructions[63]` `{"name": "C63", "expression": "Circle(O, 63)"}` — 原文の半径列1,2,...,100の第63円。
- `constructions[64]` `{"name": "C64", "expression": "Circle(O, 64)"}` — 原文の半径列1,2,...,100の第64円。
- `constructions[65]` `{"name": "C65", "expression": "Circle(O, 65)"}` — 原文の半径列1,2,...,100の第65円。
- `constructions[66]` `{"name": "C66", "expression": "Circle(O, 66)"}` — 原文の半径列1,2,...,100の第66円。
- `constructions[67]` `{"name": "C67", "expression": "Circle(O, 67)"}` — 原文の半径列1,2,...,100の第67円。
- `constructions[68]` `{"name": "C68", "expression": "Circle(O, 68)"}` — 原文の半径列1,2,...,100の第68円。
- `constructions[69]` `{"name": "C69", "expression": "Circle(O, 69)"}` — 原文の半径列1,2,...,100の第69円。
- `constructions[70]` `{"name": "C70", "expression": "Circle(O, 70)"}` — 原文の半径列1,2,...,100の第70円。
- `constructions[71]` `{"name": "C71", "expression": "Circle(O, 71)"}` — 原文の半径列1,2,...,100の第71円。
- `constructions[72]` `{"name": "C72", "expression": "Circle(O, 72)"}` — 原文の半径列1,2,...,100の第72円。
- `constructions[73]` `{"name": "C73", "expression": "Circle(O, 73)"}` — 原文の半径列1,2,...,100の第73円。
- `constructions[74]` `{"name": "C74", "expression": "Circle(O, 74)"}` — 原文の半径列1,2,...,100の第74円。
- `constructions[75]` `{"name": "C75", "expression": "Circle(O, 75)"}` — 原文の半径列1,2,...,100の第75円。
- `constructions[76]` `{"name": "C76", "expression": "Circle(O, 76)"}` — 原文の半径列1,2,...,100の第76円。
- `constructions[77]` `{"name": "C77", "expression": "Circle(O, 77)"}` — 原文の半径列1,2,...,100の第77円。
- `constructions[78]` `{"name": "C78", "expression": "Circle(O, 78)"}` — 原文の半径列1,2,...,100の第78円。
- `constructions[79]` `{"name": "C79", "expression": "Circle(O, 79)"}` — 原文の半径列1,2,...,100の第79円。
- `constructions[80]` `{"name": "C80", "expression": "Circle(O, 80)"}` — 原文の半径列1,2,...,100の第80円。
- `constructions[81]` `{"name": "C81", "expression": "Circle(O, 81)"}` — 原文の半径列1,2,...,100の第81円。
- `constructions[82]` `{"name": "C82", "expression": "Circle(O, 82)"}` — 原文の半径列1,2,...,100の第82円。
- `constructions[83]` `{"name": "C83", "expression": "Circle(O, 83)"}` — 原文の半径列1,2,...,100の第83円。
- `constructions[84]` `{"name": "C84", "expression": "Circle(O, 84)"}` — 原文の半径列1,2,...,100の第84円。
- `constructions[85]` `{"name": "C85", "expression": "Circle(O, 85)"}` — 原文の半径列1,2,...,100の第85円。
- `constructions[86]` `{"name": "C86", "expression": "Circle(O, 86)"}` — 原文の半径列1,2,...,100の第86円。
- `constructions[87]` `{"name": "C87", "expression": "Circle(O, 87)"}` — 原文の半径列1,2,...,100の第87円。
- `constructions[88]` `{"name": "C88", "expression": "Circle(O, 88)"}` — 原文の半径列1,2,...,100の第88円。
- `constructions[89]` `{"name": "C89", "expression": "Circle(O, 89)"}` — 原文の半径列1,2,...,100の第89円。
- `constructions[90]` `{"name": "C90", "expression": "Circle(O, 90)"}` — 原文の半径列1,2,...,100の第90円。
- `constructions[91]` `{"name": "C91", "expression": "Circle(O, 91)"}` — 原文の半径列1,2,...,100の第91円。
- `constructions[92]` `{"name": "C92", "expression": "Circle(O, 92)"}` — 原文の半径列1,2,...,100の第92円。
- `constructions[93]` `{"name": "C93", "expression": "Circle(O, 93)"}` — 原文の半径列1,2,...,100の第93円。
- `constructions[94]` `{"name": "C94", "expression": "Circle(O, 94)"}` — 原文の半径列1,2,...,100の第94円。
- `constructions[95]` `{"name": "C95", "expression": "Circle(O, 95)"}` — 原文の半径列1,2,...,100の第95円。
- `constructions[96]` `{"name": "C96", "expression": "Circle(O, 96)"}` — 原文の半径列1,2,...,100の第96円。
- `constructions[97]` `{"name": "C97", "expression": "Circle(O, 97)"}` — 原文の半径列1,2,...,100の第97円。
- `constructions[98]` `{"name": "C98", "expression": "Circle(O, 98)"}` — 原文の半径列1,2,...,100の第98円。
- `constructions[99]` `{"name": "C99", "expression": "Circle(O, 99)"}` — 原文の半径列1,2,...,100の第99円。
- `constructions[100]` `{"name": "C100", "expression": "Circle(O, 100)"}` — 原文の半径列1,2,...,100の第100円。
- `target` `((Area(C2) - Area(C1)) + (Area(C4) - Area(C3)) + (Area(C6) - Area(C5)) + (Area(C8) - Area(C7)) + (Area(C10) - Area(C9)) + (Area(C12) - Area(C11)) + (Area(C14) - Area(C13)) + (Area(C16) - Area(C15)) + (Area(C18) - Area(C17)) + (Area(C20) - Area(C19)) + (Area(C22) - Area(C21)) + (Area(C24) - Area(C23)) + (Area(C26) - Area(C25)) + (Area(C28) - Area(C27)) + (Area(C30) - Area(C29)) + (Area(C32) - Area(C31)) + (Area(C34) - Area(C33)) + (Area(C36) - Area(C35)) + (Area(C38) - Area(C37)) + (Area(C40) - Area(C39)) + (Area(C42) - Area(C41)) + (Area(C44) - Area(C43)) + (Area(C46) - Area(C45)) + (Area(C48) - Area(C47)) + (Area(C50) - Area(C49)) + (Area(C52) - Area(C51)) + (Area(C54) - Area(C53)) + (Area(C56) - Area(C55)) + (Area(C58) - Area(C57)) + (Area(C60) - Area(C59)) + (Area(C62) - Area(C61)) + (Area(C64) - Area(C63)) + (Area(C66) - Area(C65)) + (Area(C68) - Area(C67)) + (Area(C70) - Area(C69)) + (Area(C72) - Area(C71)) + (Area(C74) - Area(C73)) + (Area(C76) - Area(C75)) + (Area(C78) - Area(C77)) + (Area(C80) - Area(C79)) + (Area(C82) - Area(C81)) + (Area(C84) - Area(C83)) + (Area(C86) - Area(C85)) + (Area(C88) - Area(C87)) + (Area(C90) - Area(C89)) + (Area(C92) - Area(C91)) + (Area(C94) - Area(C93)) + (Area(C96) - Area(C95)) + (Area(C98) - Area(C97)) + (Area(C100) - Area(C99)))/Area(C100)` — 内側が赤で交互なので、偶数の外半径の50環が緑。各環の面積の定義による有限和/全体。和の計算結果は入力しない。

## 独立検算

手計算: 緑環の面積/piはsum_{k=1}^{50}[(2k)^2-(2k-1)^2]=sum(4k-1)=5050。全体の面積/pi=10000なので101/200。

原文に半径・色・個数がすべて指定された配置。自由変数なし。

幾何量参照値 `101/200`、採点変換 `fraction_sum`、Answer Key `301`。
90桁の独立評価器で全等式・不等式・構成の定義域を検査。詳細は `audit/substitution.json`。
解座標は監査専用で、DSL・初期点・探索箱には渡さない。solverおよび局所探索の実行なし。

# AIME-2004-II-07
一次資料: [2004_AIME_II_Problems.html](https://web.archive.org/web/20240725074532/https://artofproblemsolving.com/wiki/index.php/2004_AIME_II_Problems#Problem_7)、Problem 7、保存HTML行523。
DSL SHA-256: `6b4a15e17a8a379428bfd7b05634949bc442581aa45b2205a4dab7ca00e398d2`
問題節 SHA-256: `d7ba77245f89bc298387e6f2ebb9646c987dc0eccfeb799629f54742372473eb`

## 原文（保存HTMLから抽出）

$ABCD$ is a rectangular sheet of paper that has been folded so that corner $B$ is matched with point $B'$ on edge $AD.$ The crease is $EF,$ where $E$ is on $AB$ and $F$ is on $CD.$ The dimensions $AE=8, BE=17,$ and $CF=3$ are given. The perimeter of rectangle $ABCD$ is $m/n,$ where $m$ and $n$ are relatively prime positive integers. Find $m+n.$


[asy] size(200); defaultpen(linewidth(0.7)+fontsize(10)); pair A=origin, B=(25,0), C=(25,70/3), D=(0,70/3), E=(8,0), F=(22,70/3), Bp=reflect(E,F)*B, Cp=reflect(E,F)*C; draw(F--D--A--E); draw(E--B--C--F, linetype("4 4")); filldraw(E--F--Cp--Bp--cycle, white, black); pair point=( 12.5, 35/3 ); label("$A$", A, dir(point--A)); label("$B$", B, dir(point--B)); label("$C$", C, dir(point--C)); label("$D$", D, dir(point--D)); label("$E$", E, dir(point--E)); label("$F$", F, dir(point--F)); label("$B^\prime$", Bp, dir(point--Bp)); label("$C^\prime$", Cp, dir(point--Cp));[/asy]

## 座標・条件との読み合わせ

Aを原点、ABをx軸とする。図の完成高さ70/3は使わない。

- `constructions[0]` `{"name": "A", "expression": "Point(0, 0)"}` — 原点。
- `constructions[1]` `{"name": "B", "expression": "Point(8+17, 0)"}` — AB=AE+EB、原文の8と17の和。
- `constructions[2]` `{"name": "C", "expression": "Point(8+17, h)"}` — 長方形の未知高さ。
- `constructions[3]` `{"name": "D", "expression": "Point(0, h)"}` — 長方形。
- `constructions[4]` `{"name": "E", "expression": "Point(8, 0)"}` — AE=8。
- `constructions[5]` `{"name": "F", "expression": "Point(8+17-3, h)"}` — CF=3。
- `constructions[6]` `{"name": "Bp", "expression": "Reflect(B, Line(E, F))"}` — 折り目EFに関する鏡映が折ったB。
- `conditions[0]` `{"left": "h", "operator": ">", "right": 0}` — 長方形の非退化。
- `conditions[1]` `{"left": "Bp.x", "operator": "=", "right": 0}` — B'はAD上。
- `conditions[2]` `{"left": "Bp.y", "operator": ">=", "right": 0}` — B'は線分ADから外れない。
- `conditions[3]` `{"left": "Bp.y", "operator": "<=", "right": "h"}` — B'は線分ADから外れない。
- `target` `2*(Distance(A, B)+Distance(A, D))` — 長方形の周長。

## 独立検算

手計算: EB'=EB=17,AE=8からB'=(0,15)。FB=FB'より3^2+h^2=22^2+(h-15)^2、従ってh=70/3。周長=2(25+70/3)。図コードの完成高さをDSLへ入れていない。

B'がAD上なので正の平方根15。Fからの等距離で高さが一意。

幾何量参照値 `290/3`、採点変換 `fraction_sum`、Answer Key `293`。
90桁の独立評価器で全等式・不等式・構成の定義域を検査。詳細は `audit/substitution.json`。
解座標は監査専用で、DSL・初期点・探索箱には渡さない。solverおよび局所探索の実行なし。

# AIME-2005-I-01
一次資料: [2005_AIME_I_Problems.html](https://web.archive.org/web/20250819010808/https://artofproblemsolving.com/wiki/index.php/2005_AIME_I_Problems#Problem_1)、Problem 1、保存HTML行494。
DSL SHA-256: `ca5bfe6138022e1179fec24fafebf80a8b5e6a4b3696ee1baec71da2516b85a6`
問題節 SHA-256: `5b2a8b6d164257b271be4220da4d5662268d4d83f9d7f6dfcbedfccaff8d292f`

## 原文（保存HTMLから抽出）

Six congruent circles form a ring with each circle externally tangent to two circles adjacent to it. All circles are internally tangent to a circle $C$ with radius 30. Let $K$ be the area of the region inside circle $C$ and outside of the six circles in the ring. Find $\lfloor K \rfloor.$

## 座標・条件との読み合わせ

外円中心Oを原点、最初の内円中心P0を正のx軸に置く。正六角形の解法由来の角度や半径は入れない。

- `constructions[0]` `{"name": "O", "expression": "Point(0, 0)"}` — 外円中心。
- `constructions[1]` `{"name": "Outer", "expression": "Circle(O, 30)"}` — 原文の外円半径30。
- `constructions[2]` `{"name": "P0", "expression": "Point(30-r, 0)"}` — 半径rの内円が外円に内接する距離30-rと回転固定。
- `constructions[3]` `{"name": "P1", "expression": "Point(x1, y1)"}` — 第2内円の中心。
- `constructions[4]` `{"name": "P2", "expression": "Point(x2, y2)"}` — 第3内円の中心。
- `constructions[5]` `{"name": "P3", "expression": "Point(x3, y3)"}` — 第4内円の中心。
- `constructions[6]` `{"name": "P4", "expression": "Point(x4, y4)"}` — 第5内円の中心。
- `constructions[7]` `{"name": "P5", "expression": "Point(x5, y5)"}` — 第6内円の中心。
- `constructions[8]` `{"name": "C0", "expression": "Circle(P0, r)"}` — 6円は共通半径r。
- `constructions[9]` `{"name": "C1", "expression": "Circle(P1, r)"}` — 6円は共通半径r。
- `constructions[10]` `{"name": "C2", "expression": "Circle(P2, r)"}` — 6円は共通半径r。
- `constructions[11]` `{"name": "C3", "expression": "Circle(P3, r)"}` — 6円は共通半径r。
- `constructions[12]` `{"name": "C4", "expression": "Circle(P4, r)"}` — 6円は共通半径r。
- `constructions[13]` `{"name": "C5", "expression": "Circle(P5, r)"}` — 6円は共通半径r。
- `conditions[0]` `{"left": "r", "operator": ">", "right": 0}` — 円の非退化。
- `conditions[1]` `{"left": "r", "operator": "<", "right": 30}` — 内円が外円より小さい。
- `conditions[2]` `{"left": "Distance(O, P1)", "operator": "=", "right": "30-r"}` — 外円への内接。
- `conditions[3]` `{"left": "Distance(O, P2)", "operator": "=", "right": "30-r"}` — 外円への内接。
- `conditions[4]` `{"left": "Distance(O, P3)", "operator": "=", "right": "30-r"}` — 外円への内接。
- `conditions[5]` `{"left": "Distance(O, P4)", "operator": "=", "right": "30-r"}` — 外円への内接。
- `conditions[6]` `{"left": "Distance(O, P5)", "operator": "=", "right": "30-r"}` — 外円への内接。
- `conditions[7]` `{"left": "Distance(P0, P1)", "operator": "=", "right": "2*r"}` — 輪の隣接する2円への外接。
- `conditions[8]` `{"left": "Distance(P1, P2)", "operator": "=", "right": "2*r"}` — 輪の隣接する2円への外接。
- `conditions[9]` `{"left": "Distance(P2, P3)", "operator": "=", "right": "2*r"}` — 輪の隣接する2円への外接。
- `conditions[10]` `{"left": "Distance(P3, P4)", "operator": "=", "right": "2*r"}` — 輪の隣接する2円への外接。
- `conditions[11]` `{"left": "Distance(P4, P5)", "operator": "=", "right": "2*r"}` — 輪の隣接する2円への外接。
- `conditions[12]` `{"left": "Distance(P5, P0)", "operator": "=", "right": "2*r"}` — 輪の隣接する2円への外接。
- `conditions[13]` `{"predicate": "ConvexPolygon([P0, P1, P2, P3, P4, P5])"}` — 交差せず円周順の輪。
- `conditions[14]` `{"left": "y1", "operator": ">", "right": 0}` — 鏡映固定。
- `conditions[15]` `{"left": "Distance(P0, P2)", "operator": ">", "right": "2*r"}` — 隣接2円以外とは接触・重なりのない輪。
- `conditions[16]` `{"left": "Distance(P0, P3)", "operator": ">", "right": "2*r"}` — 隣接2円以外とは接触・重なりのない輪。
- `conditions[17]` `{"left": "Distance(P0, P4)", "operator": ">", "right": "2*r"}` — 隣接2円以外とは接触・重なりのない輪。
- `conditions[18]` `{"left": "Distance(P1, P3)", "operator": ">", "right": "2*r"}` — 隣接2円以外とは接触・重なりのない輪。
- `conditions[19]` `{"left": "Distance(P1, P4)", "operator": ">", "right": "2*r"}` — 隣接2円以外とは接触・重なりのない輪。
- `conditions[20]` `{"left": "Distance(P1, P5)", "operator": ">", "right": "2*r"}` — 隣接2円以外とは接触・重なりのない輪。
- `conditions[21]` `{"left": "Distance(P2, P4)", "operator": ">", "right": "2*r"}` — 隣接2円以外とは接触・重なりのない輪。
- `conditions[22]` `{"left": "Distance(P2, P5)", "operator": ">", "right": "2*r"}` — 隣接2円以外とは接触・重なりのない輪。
- `conditions[23]` `{"left": "Distance(P3, P5)", "operator": ">", "right": "2*r"}` — 隣接2円以外とは接触・重なりのない輪。
- `target` `Area(Outer) - Area(C0) - Area(C1) - Area(C2) - Area(C3) - Area(C4) - Area(C5)` — 外円の内側で6円の外側の面積K。floorは採点側。

## 独立検算

手計算: 円周順の6中心は共通半径30-rの円にある。隣接弦がすべて2rなので小さい中心角は等しい。大弧を1個含めても角の和を満たせず、6角は60度。2r=30-rからr=10。面積は(900-6*100)pi。

正の半径、凸で重ならない輪、6つの同長弦と一周条件により通常の正六角形枝のみ。鏡映・回転で面積不変。

幾何量参照値 `300*pi`、採点変換 `floor`、Answer Key `942`。
90桁の独立評価器で全等式・不等式・構成の定義域を検査。詳細は `audit/substitution.json`。
解座標は監査専用で、DSL・初期点・探索箱には渡さない。solverおよび局所探索の実行なし。

# AIME-2005-I-07
一次資料: [2005_AIME_I_Problems.html](https://web.archive.org/web/20250819010808/https://artofproblemsolving.com/wiki/index.php/2005_AIME_I_Problems#Problem_7)、Problem 7、保存HTML行518。
DSL SHA-256: `558afc3b8db9ce81912b04a34a1a06fe0d06844d269d7bcde6953691db72cc3e`
問題節 SHA-256: `42f774f134d4a4459aa840f61cfde39bd0c983a8cdb09a219d79bb56fe0c3aa7`

## 原文（保存HTMLから抽出）

In quadrilateral $ABCD, BC=8, CD=12, AD=10,$ and $m\angle A= m\angle B = 60^\circ.$ Given that $AB = p + \sqrt{q},$ where $p$ and $q$ are positive integers, find $p+q.$

## 座標・条件との読み合わせ

Aを原点、B=(b,0)、四角形を上半平面に置く。角A,B=60度の辺方向を原文の数値で構成。

- `constructions[0]` `{"name": "A", "expression": "Point(0, 0)"}` — 原点。
- `constructions[1]` `{"name": "B", "expression": "Point(b, 0)"}` — 未知の辺AB。
- `constructions[2]` `{"name": "D", "expression": "Point(10*cos(pi/3), 10*sin(pi/3))"}` — AD=10、角A=60度。
- `constructions[3]` `{"name": "C", "expression": "Point(b-8*cos(pi/3), 8*sin(pi/3))"}` — BC=8、角B=60度。
- `conditions[0]` `{"left": "b", "operator": ">", "right": 0}` — 辺ABの正値。
- `conditions[1]` `{"left": "Distance(C, D)", "operator": "=", "right": 12}` — 原文CD=12。
- `conditions[2]` `{"predicate": "ConvexPolygon([A, B, C, D])"}` — A,Bが60度の通常の単純四角形の内角配置。凹角の別解を追加しない。
- `target` `Distance(A, B)` — 辺長AB。p+qは採点側。

## 独立検算

手計算: D=(5,5sqrt(3)), C=(b-4,4sqrt(3))よりCD^2=(b-9)^2+3=144。b=9±sqrt(141)のうち正の根だけ。

負の根はb<0。正の根で4頂点は凸。

幾何量参照値 `9+sqrt(141)`、採点変換 `integer_plus_sqrt`、Answer Key `150`。
90桁の独立評価器で全等式・不等式・構成の定義域を検査。詳細は `audit/substitution.json`。
解座標は監査専用で、DSL・初期点・探索箱には渡さない。solverおよび局所探索の実行なし。

# AIME-2005-II-08
一次資料: [2005_AIME_II_Problems.html](https://web.archive.org/web/20241111195137/https://artofproblemsolving.com/wiki/index.php/2005_AIME_II_Problems#Problem_8)、Problem 8、保存HTML行539。
DSL SHA-256: `e654479bbbda6fec393b4fb1b25dd0cdd1504a5ad24eaf2889c4d368226db78d`
問題節 SHA-256: `ed63946e06d0633d14a9580bbe6cac08a47ba70e13eaf7e2133aa2b948dcbf52`

## 原文（保存HTMLから抽出）

Circles $C_1$ and $C_2$ are externally tangent, and they are both internally tangent to circle $C_3.$ The radii of $C_1$ and $C_2$ are 4 and 10, respectively, and the centers of the three circles are all collinear. A chord of $C_3$ is also a common external tangent of $C_1$ and $C_2.$ Given that the length of the chord is $\frac{m\sqrt{n}}p$ where $m,n,$ and $p$ are positive integers, $m$ and $p$ are relatively prime, and $n$ is not divisible by the square of any prime, find $m+n+p.$

## 座標・条件との読み合わせ

内円中心をO1=(0,0), O2=(4+10,0)に置く。外円中心は同じ軸上のO3=(z,0)。接線は上側を選ぶ鏡映固定。

- `constructions[0]` `{"name": "O1", "expression": "Point(0, 0)"}` — 第1円の中心。
- `constructions[1]` `{"name": "O2", "expression": "Point(4+10, 0)"}` — 2内円の外接による中心間距離、原文半径の和。
- `constructions[2]` `{"name": "O3", "expression": "Point(z, 0)"}` — 3中心が共線。
- `constructions[3]` `{"name": "L", "expression": "Line(Point(0, b), Point(1, a+b))"}` — 共通外接線y=ax+b。非鉛直なのは2中心が水平で半径が異なるため。
- `conditions[0]` `{"left": "R", "operator": ">", "right": 10}` — 2内円を含む外円の半径。
- `conditions[1]` `{"left": "Distance(O3, O1)", "operator": "=", "right": "R-4"}` — 第1円と第3円の内接。
- `conditions[2]` `{"left": "Distance(O3, O2)", "operator": "=", "right": "R-10"}` — 第2円と第3円の内接。
- `conditions[3]` `{"left": "Distance(O1, L)", "operator": "=", "right": 4}` — 第1円に接する。
- `conditions[4]` `{"left": "Distance(O2, L)", "operator": "=", "right": 10}` — 第2円に接する。
- `conditions[5]` `{"left": "b", "operator": ">", "right": 0}` — 上側外接線を選ぶ。
- `conditions[6]` `{"left": "a*(4+10)+b", "operator": ">", "right": 0}` — 両中心が接線の同じ側。内接線を排除。
- `conditions[7]` `{"left": "Distance(O3, L)", "operator": "<", "right": "R"}` — 外円を横切る弦。
- `target` `2*sqrt(R**2-Distance(O3, L)**2)` — 円中心から弦への垂線で二分した弦長の定義式。外円半径の解は入力しない。

## 独立検算

手計算: |z|=R-4,|z-14|=R-10の有効な内接枝はz=10,R=14。共通外接線はb=4sqrt(1+a^2),14a+b=10sqrt(1+a^2)からa=3/(2sqrt(10)),b=14/sqrt(10)。O3から線まで58/7、弦長=2sqrt(14^2-(58/7)^2)。

z<=0,z>=14の枝は半径差6と中心距離14が矛盾。上側接線は一意で下側は鏡像。

幾何量参照値 `8*sqrt(390)/7`、採点変換 `radical_fraction_sum`、Answer Key `405`。
90桁の独立評価器で全等式・不等式・構成の定義域を検査。詳細は `audit/substitution.json`。
解座標は監査専用で、DSL・初期点・探索箱には渡さない。solverおよび局所探索の実行なし。

# AIME-2005-II-12
一次資料: [2005_AIME_II_Problems.html](https://web.archive.org/web/20241111195137/https://artofproblemsolving.com/wiki/index.php/2005_AIME_II_Problems#Problem_12)、Problem 12、保存HTML行555。
DSL SHA-256: `d3f82c1cb08c74ece1555b2af01818d5a82e69590b7ed16aab546c48128b8e91`
問題節 SHA-256: `d49c5274698bb68f6ab18489a94df2452d97e35aebf5a66e551aecc453ce456f`

## 原文（保存HTMLから抽出）

Square $ABCD$ has center $O, AB=900, E$ and $F$ are on $AB$ with $AE<BF$ and $E$ between $A$ and $F, m\angle EOF =45^\circ,$ and $EF=400.$ Given that $BF=p+q\sqrt{r},$ where $p,q,$ and $r$ are positive integers and $r$ is not divisible by the square of any prime, find $p+q+r.$

## 座標・条件との読み合わせ

正方形A=(0,0),B=(900,0),C=(900,900),D=(0,900)。尺度変更なし。

- `constructions[0]` `{"name": "A", "expression": "Point(0, 0)"}` — 正方形の原点。
- `constructions[1]` `{"name": "B", "expression": "Point(900, 0)"}` — 原文AB=900。
- `constructions[2]` `{"name": "C", "expression": "Point(900, 900)"}` — 正方形。
- `constructions[3]` `{"name": "D", "expression": "Point(0, 900)"}` — 正方形。
- `constructions[4]` `{"name": "O", "expression": "Midpoint(A, C)"}` — 正方形の中心。
- `constructions[5]` `{"name": "E", "expression": "Point(e, 0)"}` — EはAB上。
- `constructions[6]` `{"name": "F", "expression": "Point(f, 0)"}` — FはAB上。
- `conditions[0]` `{"left": "e", "operator": ">=", "right": 0}` — Eは線分AB上。
- `conditions[1]` `{"left": "f", "operator": "<=", "right": 900}` — Fは線分AB上。
- `conditions[2]` `{"left": "e", "operator": "<", "right": "f"}` — EはAとFの間。
- `conditions[3]` `{"left": "Distance(A, E)", "operator": "<", "right": "Distance(B, F)"}` — 原文AE<BF。
- `conditions[4]` `{"left": "Distance(E, F)", "operator": "=", "right": 400}` — 原文EF=400。
- `conditions[5]` `{"left": "Angle(E, O, F)", "operator": "=", "right": "pi/4"}` — 原文角EOF=45度。
- `target` `Distance(B, F)` — 長さBF。p+q+rは採点側。

## 独立検算

手計算: f=e+400。角45度のdot=|cross|から(450-e)^2-400(450-e)+22500=0。AE<BFからe<250なのでe=250-50sqrt(7)。

二次式の2根は左右鏡像。AE<BFの厳密不等式が1根を選ぶ。

幾何量参照値 `250+50*sqrt(7)`、採点変換 `integer_plus_radical_sum`、Answer Key `307`。
90桁の独立評価器で全等式・不等式・構成の定義域を検査。詳細は `audit/substitution.json`。
解座標は監査専用で、DSL・初期点・探索箱には渡さない。solverおよび局所探索の実行なし。

# AIME-2005-II-14
一次資料: [2005_AIME_II_Problems.html](https://web.archive.org/web/20241111195137/https://artofproblemsolving.com/wiki/index.php/2005_AIME_II_Problems#Problem_14)、Problem 14、保存HTML行563。
DSL SHA-256: `a0b4a9b3669f5586e8aa0105fd5e47b15fe650384841e4cee85cef01638cace7`
問題節 SHA-256: `15dbeeeac0d95bef15691a64315374845c5b8022635dc04dff8e9158aa95b670`

## 原文（保存HTMLから抽出）

In triangle $ABC, AB=13, BC=15,$ and $CA = 14.$ Point $D$ is on $\overline{BC}$ with $CD=6.$ Point $E$ is on $\overline{BC}$ such that $\angle BAE\cong \angle CAD.$ Given that $BE=\frac pq$ where $p$ and $q$ are relatively prime positive integers, find $q.$

## 座標・条件との読み合わせ

B=(0,0), C=(15,0)、Aを上半平面へ。原文の尺度を保持。

- `constructions[0]` `{"name": "B", "expression": "Point(0, 0)"}` — 原点。
- `constructions[1]` `{"name": "C", "expression": "Point(15, 0)"}` — 原文BC=15。
- `constructions[2]` `{"name": "A", "expression": "Point(x, y)"}` — 頂点A。
- `constructions[3]` `{"name": "D", "expression": "Point(15-6, 0)"}` — CD=6。
- `constructions[4]` `{"name": "E", "expression": "PointOnSegment(B, C, t)"}` — EはBC上。
- `conditions[0]` `{"left": "Distance(A, B)", "operator": "=", "right": 13}` — 原文AB=13。
- `conditions[1]` `{"left": "Distance(A, C)", "operator": "=", "right": 14}` — 原文CA=14。
- `conditions[2]` `{"left": "y", "operator": ">", "right": 0}` — 非退化と鏡映固定。
- `conditions[3]` `{"left": "t", "operator": ">", "right": 0}` — 角の一致からEはBと異なる。
- `conditions[4]` `{"left": "t", "operator": "<", "right": 1}` — 角の一致からEはCと異なる。
- `conditions[5]` `{"left": "Angle(B, A, E)", "operator": "=", "right": "Angle(C, A, D)"}` — 原文の角BAE=角CAD。
- `target` `Distance(B, E)` — 長さBE。既約分母qは採点側。

## 独立検算

手計算: 辺長13,14,15からA=(33/5,56/5)。ADとAEは等角線なので(BD/DC)(BE/EC)=(AB/AC)^2。BD/DC=9/6よりBE/EC=169/294、従ってBE=2535/463。

三角形の固定後、ABからACに向かって角BAEは線分BC上で単調。指定角の解は一つ。

幾何量参照値 `2535/463`、採点変換 `denominator`、Answer Key `463`。
90桁の独立評価器で全等式・不等式・構成の定義域を検査。詳細は `audit/substitution.json`。
解座標は監査専用で、DSL・初期点・探索箱には渡さない。solverおよび局所探索の実行なし。

# AIME-2012-I-14
一次資料: [2012_AIME_I_Problems.html](https://web.archive.org/web/20250819010921/https://artofproblemsolving.com/wiki/index.php/2012_AIME_I_Problems#Problem_14)、Problem 14、保存HTML行552。
DSL SHA-256: `529ac0e06eac5ad188d45ee4ea6b005dd9be10652d02731418acb91a07fa45c0`
問題節 SHA-256: `a84d5908cf2bc5e3e18f8d873322bfdd81eddf56dbbc2f07aa800495a8be43cc`

## 原文（保存HTMLから抽出）

Complex numbers $a,$ $b,$ and $c$ are zeros of a polynomial $P(z) = z^3 + qz + r,$ and $|a|^2 + |b|^2 + |c|^2 = 250.$ The points corresponding to $a,$ $b,$ and $c$ in the complex plane are the vertices of a right triangle with hypotenuse $h.$ Find $h^2.$

## 座標・条件との読み合わせ

根a,b,cを直角がaになるよう名前交換。回転でabを水平、acを垂直にする。原点は動かさない。複素係数q,rに他の制限はない。

- `constructions[0]` `{"name": "A", "expression": "Point(x, y)"}` — 複素根a。
- `constructions[1]` `{"name": "B", "expression": "Point(u, y)"}` — 直角の1辺を水平にする回転固定。
- `constructions[2]` `{"name": "C", "expression": "Point(x, v)"}` — Aが直角のため他辺は垂直。
- `conditions[0]` `{"left": "2*x+u", "operator": "=", "right": 0}` — z^2係数0はVietaの恒等式a+b+c=0（実部）。解から求めた値ではない。
- `conditions[1]` `{"left": "2*y+v", "operator": "=", "right": 0}` — a+b+c=0（虚部）。
- `conditions[2]` `{"left": "x**2+y**2+u**2+y**2+x**2+v**2", "operator": "=", "right": 250}` — 原文の|a|^2+|b|^2+|c|^2=250。
- `conditions[3]` `{"left": "u", "operator": ">", "right": "x"}` — 直角の第1辺の正値。
- `conditions[4]` `{"left": "v", "operator": ">", "right": "y"}` — 直角の第2辺、鏡映固定。
- `target` `Distance(B, C)**2` — 指定された斜辺の平方h^2。

## 独立検算

手計算: a+b+c=0より辺の平方和=3(|a|^2+|b|^2+|c|^2)=750。直角三角形では辺の平方和=2h^2なのでh^2=375。配置は一意でない。異なる2形状を代入。

配置は連続族だが上の恒等式で目標値は常に375。q=ab+bc+ca, r=-abcが存在し、3点は必ず原文の形の三次式の根になる。

幾何量参照値 `375`、採点変換 `identity`、Answer Key `375`。
90桁の独立評価器で全等式・不等式・構成の定義域を検査。詳細は `audit/substitution.json`。
解座標は監査専用で、DSL・初期点・探索箱には渡さない。solverおよび局所探索の実行なし。

# AIME-2014-I-01
一次資料: [2014_AIME_I_Problems.html](https://web.archive.org/web/20240713184355/https://artofproblemsolving.com/wiki/index.php/2014_AIME_I_Problems#Problem_1)、Problem 1、保存HTML行498。
DSL SHA-256: `52f0a7787af21abca4eea3bfc884f3100c80c4f2bbcf9bcff6e05ac8e0b6c6c4`
問題節 SHA-256: `382709ddd0b278b8ab6ee94c98f5e79dc0ed4f31e8aef322d1a0554a7e0877f2`

## 原文（保存HTMLから抽出）

The 8 eyelets for the lace of a sneaker all lie on a rectangle, four equally spaced on each of the longer sides. The rectangle has a width of 50 mm and a length of 80 mm. There is one eyelet at each vertex of the rectangle. The lace itself must pass between the vertex eyelets along a width side of the rectangle and then crisscross between successive eyelets until it reaches the two eyelets at the other width side of the rectangle as shown. After passing through these final eyelets, each of the ends of the lace must extend at least 200 mm farther to allow a knot to be tied. Find the minimum length of the lace in millimeters. 


[asy] size(200); defaultpen(linewidth(0.7)); path laceL=(-20,-30)..tension 0.75 ..(-90,-135)..(-102,-147)..(-152,-150)..tension 2 ..(-155,-140)..(-135,-40)..(-50,-4)..tension 0.8 ..origin; path laceR=reflect((75,0),(75,-240))*laceL; draw(origin--(0,-240)--(150,-240)--(150,0)--cycle,gray); for(int i=0;i<=3;i=i+1) { path circ1=circle((0,-80*i),5),circ2=circle((150,-80*i),5); unfill(circ1); draw(circ1); unfill(circ2); draw(circ2); } draw(laceL--(150,-80)--(0,-160)--(150,-240)--(0,-240)--(150,-160)--(0,-80)--(150,0)^^laceR,linewidth(1));[/asy]
Solution

## 座標・条件との読み合わせ

長方形の指定幅50、長さ80を保つ。原文の経路は図の固定6斜線と始点側1横線。各自由端の最短余長200を加える。

- `constructions[0]` `{"name": "L0", "expression": "Point(0, 0*80/3)"}` — 長辺上の等間隔の4穴。3区間で全長80。
- `constructions[1]` `{"name": "R0", "expression": "Point(50, 0*80/3)"}` — 対辺上の4穴、幅50。
- `constructions[2]` `{"name": "L1", "expression": "Point(0, 1*80/3)"}` — 長辺上の等間隔の4穴。3区間で全長80。
- `constructions[3]` `{"name": "R1", "expression": "Point(50, 1*80/3)"}` — 対辺上の4穴、幅50。
- `constructions[4]` `{"name": "L2", "expression": "Point(0, 2*80/3)"}` — 長辺上の等間隔の4穴。3区間で全長80。
- `constructions[5]` `{"name": "R2", "expression": "Point(50, 2*80/3)"}` — 対辺上の4穴、幅50。
- `constructions[6]` `{"name": "L3", "expression": "Point(0, 3*80/3)"}` — 長辺上の等間隔の4穴。3区間で全長80。
- `constructions[7]` `{"name": "R3", "expression": "Point(50, 3*80/3)"}` — 対辺上の4穴、幅50。
- `target` `Distance(L0, R0) + Distance(L0, R1) + Distance(R0, L1) + Distance(L1, R2) + Distance(R1, L2) + Distance(L2, R3) + Distance(R2, L3) + 2*200` — 固定された靴紐経路の長さ+両端それぞれ最低200。全配置の最適化はなく余長の下限を足すだけ。

## 独立検算

手計算: 隣り合う高さ差80/3、各斜線sqrt(50^2+(80/3)^2)=170/3。6斜線+幅50+両端400=790。

指定された固定経路。両端の長さをそれぞれ原文の下限200にすれば最短になる。

幾何量参照値 `790`、採点変換 `identity`、Answer Key `790`。
90桁の独立評価器で全等式・不等式・構成の定義域を検査。詳細は `audit/substitution.json`。
解座標は監査専用で、DSL・初期点・探索箱には渡さない。solverおよび局所探索の実行なし。

# AIME-2014-I-10
一次資料: [2014_AIME_I_Problems.html](https://web.archive.org/web/20240713184355/https://artofproblemsolving.com/wiki/index.php/2014_AIME_I_Problems#Problem_10)、Problem 10、保存HTML行535。
DSL SHA-256: `8aa61a3686e59b15e12f3ac8571ea858c0b1a9d9260f3edf88b38185300bb1c7`
問題節 SHA-256: `5487d82854b8fc18a48fc2464e22ac4f05e60c01fe21e99e75621bb7f17123d7`

## 原文（保存HTMLから抽出）

A disk with radius $1$ is externally tangent to a disk with radius $5$. Let $A$ be the point where the disks are tangent, $C$ be the center of the smaller disk, and $E$ be the center of the larger disk. While the larger disk remains fixed, the smaller disk is allowed to roll along the outside of the larger disk until the smaller disk has turned through an angle of $360^\circ$. That is, if the center of the smaller disk has moved to the point $D$, and the point on the smaller disk that began at $A$ has now moved to point $B$, then $\overline{AC}$ is parallel to $\overline{BD}$. Then $\sin^2(\angle BEA)=\tfrac{m}{n}$, where $m$ and $n$ are relatively prime positive integers. Find $m+n$.

## 座標・条件との読み合わせ

大円中心E=(0,0)、最初の接点A=(5,0)、小円中心C=(5+1,0)。転がり方向は反時計回りを選ぶ。

- `constructions[0]` `{"name": "E", "expression": "Point(0, 0)"}` — 大円中心。
- `constructions[1]` `{"name": "A", "expression": "Point(5, 0)"}` — 原文の大円半径5の接点。
- `constructions[2]` `{"name": "C", "expression": "Point(5+1, 0)"}` — 小円半径1、外接。
- `constructions[3]` `{"name": "D", "expression": "Point((5+1)*cos(theta), (5+1)*sin(theta))"}` — 転がった小円中心は距離5+1の円周上。
- `constructions[4]` `{"name": "B", "expression": "Point(D.x-1, D.y)"}` — 小円が正確に1回転し、初期の中心から接点への半径(-1,0)が戻る。
- `conditions[0]` `{"left": "(5+1)*theta", "operator": "=", "right": "2*pi*1"}` — 滑りなしの転がり。接触に対する相対回転は5*theta/1、中心の向きthetaを加えた絶対回転が2*pi。解角度は入力しない。
- `conditions[1]` `{"left": "theta", "operator": ">", "right": 0}` — 正方向で最初の1回転。
- `conditions[2]` `{"left": "theta", "operator": "<", "right": "2*pi"}` — 1回転に対応する中心の移動範囲。
- `target` `sin(Angle(B, E, A))**2` — 原文のsin^2角BEAそのもの。

## 独立検算

手計算: 外転がりの小円の絶対回転は(5+1)theta/1。360度回転なのでtheta=pi/3。D=(3,3sqrt(3)),B=(2,3sqrt(3))、sin^2角BEA=27/(4+27)。

滑りのない正方向で最初の一回転を選ぶ。逆方向は鏡像で同じsin^2。

幾何量参照値 `27/31`、採点変換 `fraction_sum`、Answer Key `058`。
90桁の独立評価器で全等式・不等式・構成の定義域を検査。詳細は `audit/substitution.json`。
解座標は監査専用で、DSL・初期点・探索箱には渡さない。solverおよび局所探索の実行なし。

# AIME-2014-II-10
一次資料: [2014_AIME_II_Problems.html](https://web.archive.org/web/20250819010455/https://artofproblemsolving.com/wiki/index.php/2014_AIME_II_Problems#Problem_10)、Problem 10、保存HTML行538。
DSL SHA-256: `0914d8cbfb290985413a18d1afd155a4c93c0320be0b3733d53fd9e23ba6a4e4`
問題節 SHA-256: `279363b9a2cdc94a0cb6e8d108d28f9ea57cf3de856f24e3a9ad9026f28532e6`

## 原文（保存HTMLから抽出）

Let $z$ be a complex number with $|z|=2014$. Let $P$ be the polygon in the complex plane whose vertices are $z$ and every $w$ such that $\frac{1}{z+w}=\frac{1}{z}+\frac{1}{w}$. Then the area enclosed by $P$ can be written in the form $n\sqrt{3}$, where $n$ is an integer. Find the remainder when $n$ is divided by $1000$. 




Solution

## 座標・条件との読み合わせ

複素平面全体を回転しzを正実数2014へ。1/(z+w)=1/z+1/wの分母は非零。共役や根の値は決め打ちしない。

- `constructions[0]` `{"name": "Z", "expression": "Point(2014, 0)"}` — |z|=2014と回転固定。
- `constructions[1]` `{"name": "W1", "expression": "Point(x, y)"}` — 第1のw。
- `constructions[2]` `{"name": "W2", "expression": "Point(u, v)"}` — 第2のw。
- `conditions[0]` `{"left": "x**2-y**2+2014*x+2014**2", "operator": "=", "right": 0}` — 分母を払った恒等式w^2+zw+z^2=0の実部。
- `conditions[1]` `{"left": "2*x*y+2014*y", "operator": "=", "right": 0}` — 同じ式の虚部。
- `conditions[2]` `{"left": "x**2+y**2", "operator": ">", "right": 0}` — w!=0、元の分母条件。
- `conditions[3]` `{"left": "(x+2014)**2+y**2", "operator": ">", "right": 0}` — z+w!=0、元の分母条件。
- `conditions[4]` `{"left": "u**2-v**2+2014*u+2014**2", "operator": "=", "right": 0}` — 分母を払った恒等式w^2+zw+z^2=0の実部。
- `conditions[5]` `{"left": "2*u*v+2014*v", "operator": "=", "right": 0}` — 同じ式の虚部。
- `conditions[6]` `{"left": "u**2+v**2", "operator": ">", "right": 0}` — w!=0、元の分母条件。
- `conditions[7]` `{"left": "(u+2014)**2+v**2", "operator": ">", "right": 0}` — z+w!=0、元の分母条件。
- `conditions[8]` `{"left": "y", "operator": ">", "right": 0}` — 根の名前交換で上側をW1。実根は実二次式が正なので存在しない。
- `conditions[9]` `{"left": "v", "operator": "<", "right": 0}` — W2を下側。実係数二次式の非実根は共役対なのでこの2点が全根。
- `target` `Area(Z, W1, W2)` — 原文の多角形の面積。sqrt(3)の係数と剰余は採点側。

## 独立検算

手計算: z=2014と回転固定。w^2+2014w+2014^2=0の二次公式よりw=-1007±1007sqrt(3)i。三角形面積=(2014+1007)*(2*1007sqrt(3))/2=3042147sqrt(3)。

二次式の根は非実共役の2個。z,w,z+wの非零条件も満たし、元の逆数方程式と同値。

幾何量参照値 `3042147*sqrt(3)`、採点変換 `sqrt3_coefficient_mod1000`、Answer Key `147`。
90桁の独立評価器で全等式・不等式・構成の定義域を検査。詳細は `audit/substitution.json`。
解座標は監査専用で、DSL・初期点・探索箱には渡さない。solverおよび局所探索の実行なし。

# AIME-2019-I-12
一次資料: [2019_AIME_I_Problems.html](https://web.archive.org/web/20250819011031/https://artofproblemsolving.com/wiki/index.php/2019_AIME_I_Problems#Problem_12)、Problem 12、保存HTML行543。
DSL SHA-256: `c01fc8c6c540407f8fc5a9af08749f451656126255f0f05aaa4204e55bc12a02`
問題節 SHA-256: `4cc669d576f9e5afe8606844c1f13dfc4ff51a709c6ac76889fe0f386a6f5d33`

## 原文（保存HTMLから抽出）

Given $f(z) = z^2-19z$, there are complex numbers $z$ with the property that $z$, $f(z)$, and $f(f(z))$ are the vertices of a right triangle in the complex plane with a right angle at $f(z)$. There are positive integers $m$ and $n$ such that one such value of $z$ is $m+\sqrt{n}+11i$. Find $m+n$.

## 座標・条件との読み合わせ

原文の複素座標系を保持。zの虚部11と正の実部だけを使い、出力形式のm,nは変数にしない。

- `constructions[0]` `{"name": "Z", "expression": "Point(x, 11)"}` — 原文z=m+sqrt(n)+11iの虚部。m,n>0より実部は正。
- `constructions[1]` `{"name": "F", "expression": "Point(x**2-11**2-19*x, 2*11*x-19*11)"}` — 原文f(z)=z^2-19zを実部・虚部で直接評価。
- `constructions[2]` `{"name": "G", "expression": "Point(F.x**2-F.y**2-19*F.x, 2*F.x*F.y-19*F.y)"}` — 原文のf(f(z))を同じ定義で評価。
- `conditions[0]` `{"left": "Dot(Vector(Z, F), Vector(F, G))", "operator": "=", "right": 0}` — 頂点f(z)で直角。内積の符号は0条件に影響しない。
- `conditions[1]` `{"left": "Distance(Z, F)", "operator": ">", "right": 0}` — 直角三角形の第1辺が非退化。
- `conditions[2]` `{"left": "Distance(F, G)", "operator": ">", "right": 0}` — 直角三角形の第2辺が非退化。
- `conditions[3]` `{"left": "x", "operator": ">", "right": 0}` — 原文m,n>0に対応する実部の正の枝。整数性は出力形式なので入力しない。
- `target` `Z.x` — 点zの実座標そのもの。m+nは採点側で抽出。

## 独立検算

手計算: f(z)-z=z(z-20), f(f(z))-f(z)=z(z-19)(z-20)(z+1)。2辺が直交する条件はRe[(z-19)(z+1)]=0。Im(z)=11よりx^2-18x-140=0、x=9±sqrt(221)。

原文m,n>0の実部正の枝は9+sqrt(221)だけ。虚部11のためz=0,20の退化はなく、他の2辺も非零。

幾何量参照値 `9+sqrt(221)`、採点変換 `integer_plus_sqrt`、Answer Key `230`。
90桁の独立評価器で全等式・不等式・構成の定義域を検査。詳細は `audit/substitution.json`。
解座標は監査専用で、DSL・初期点・探索箱には渡さない。solverおよび局所探索の実行なし。
