# Q2対応カード集 v3

AIME補充は二次資料・公式冊子未照合。旧HMMT18問はv2のまま保持。

# AIME-1983-04 原文→入力対応カード

状態: **二次資料・公式冊子未照合・数値検証未実施**。

- 資料: `jssa/difficulty/unseen-1983/source-evidence/aime-1983-1999/aime-1983-1999.jsonl` / line 4
- 原文SHA-256: `456ccfc7d33963783249ea126eaf34743fbe53441baac56efdece969ad9276b2`
- 入力SHA-256: `f3604f59255096023114b8a5890e59d9541a16a59d673017d123c0a519874c2e`
- 座標固定・同値性: 直角の二辺AB,BCを座標軸に固定。長さ6,2は原文。合同移動・鏡映だけ。
- 答えは `official_answers.jsonl` へ入力固定後に分離。選定・入力には未使用。

## 手元の原文（二次資料のQuestionをそのまま保存）

A machine-shop cutting tool has the shape of a notched circle, as shown. The radius of the circle is $\sqrt{50}$ cm, the length of $AB$ is $6$ cm and that of $BC$ is $2$ cm. The angle $ABC$ is a right angle. Find the square of the distance (in centimeters) from $B$ to the center of the circle. [asy] size(150); defaultpen(linewidth(0.6)+fontsize(11)); real r=10; pair O=(0,0), A=r*dir(45),B=(A.x,A.y-r); path P=circle(O,r); pair C=intersectionpoint(B--(B.x+r,B.y),P); // Drawing arc instead of full circle //draw(P); draw(arc(O, r, degrees(A), degrees(C))); draw(C--B--A--B); dot(A); dot(B); dot(C); label("$A$",A,NE); label("$B$",B,S); label("$C$",C,SE); [/asy]

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| right angle ABC / 直角頂点を原点 | `constructions[0]` | `B = Point(0, 0)` |
| AB=6 | `constructions[1]` | `A = Point(0, 6)` |
| BC=2 | `constructions[2]` | `C = Point(2, 0)` |
| 円の中心は未知 | `constructions[3]` | `O = Point(x, y)` |
| circle radius sqrt(50) | `constructions[4]` | `omega = Circle(O, sqrt(50))` |
| 図の円周上の端点A | `conditions[0]` | `OnCircle(A, omega) = 0` |
| 図の円周上の端点C | `conditions[1]` | `OnCircle(C, omega) = 0` |
| notched circle / Bは元の円盤の内部 | `conditions[2]` | `sqrt(50) > Distance(O, B)` |
| square of distance from B to center | `target` | `Distance(B, O)**2` |

## 残る制約

asyはA,Cが円周上、Bが内部という接続情報にのみ使用。描画用座標は制約に転記しない。

分枝・内部・非退化は表のguardで明示。根番号で解を選ばない。AST合格は幾何同値性・実行可能性・目標の一意性を保証しない。


---

# AIME-1983-12 原文→入力対応カード

状態: **二次資料・公式冊子未照合・数値検証未実施**。

- 資料: `jssa/difficulty/unseen-1983/source-evidence/aime-1983-1999/aime-1983-1999.jsonl` / line 12
- 原文SHA-256: `30df8527621872aafa0c38e7e0cd63e39f0de470ceb7a671bfe7ab66872e32a5`
- 入力SHA-256: `b6ebcb828da4aa856c94f583431e96d46d171a2c344225bcf3e7e0f9127e3c12`
- 座標固定・同値性: O原点、ABをx軸。OHの正側は鏡映で固定。
- 答えは `official_answers.jsonl` へ入力固定後に分離。選定・入力には未使用。

## 手元の原文（二次資料のQuestionをそのまま保存）

Diameter $AB$ of a circle has length a $2$ -digit integer (base ten). Reversing the digits gives the length of the perpendicular chord $CD$ . The distance from their intersection point $H$ to the center $O$ is a positive rational number. Determine the length of $AB$ . Pdfresizer.com-pdf-convert-aimeq12.png

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| circle center | `constructions[0]` | `O = Point(0, 0)` |
| diameter AB has two-digit length 10a+b | `constructions[1]` | `A = Point(-(10*a+b)/2, 0)` |
| diameter AB | `constructions[2]` | `B = Point((10*a+b)/2, 0)` |
| perpendicular diameter/chord intersection | `constructions[3]` | `H = Point(h, 0)` |
| reversed-digit chord CD, perpendicular to AB | `constructions[4]` | `C = Point(h, (10*b+a)/2)` |
| CD / 円の中心からの垂線が弦を二等分 | `constructions[5]` | `D = Point(h, -(10*b+a)/2)` |
| circle with diameter AB | `constructions[6]` | `omega = Circle(O, (10*a+b)/2)` |
| decimal digits / rational witnesses | `conditions[0]` | `IsInteger(a) = 0` |
| decimal digits / rational witnesses | `conditions[1]` | `IsInteger(b) = 0` |
| decimal digits / rational witnesses | `conditions[2]` | `IsInteger(p) = 0` |
| decimal digits / rational witnesses | `conditions[3]` | `IsInteger(q) = 0` |
| 十の位 | `conditions[4]` | `a >= 1` |
| 十の位 | `conditions[5]` | `a <= 9` |
| 一の位（反転後の先頭0を排除しない） | `conditions[6]` | `b >= 0` |
| 一の位 | `conditions[7]` | `b <= 9` |
| positive distance OH / 鏡映でHを右側 | `conditions[8]` | `h > 0` |
| positive rational numerator witness | `conditions[9]` | `p > 0` |
| positive rational denominator witness | `conditions[10]` | `q > 0` |
| OH is rational（既約性の指定はない） | `conditions[11]` | `h = p/q` |
| C on circle | `conditions[12]` | `OnCircle(C, omega) = 0` |
| D on circle | `conditions[13]` | `OnCircle(D, omega) = 0` |
| determine AB | `target` | `Distance(A, B)` |

## 残る制約

画像は欠落しているが、径・垂直弦・交点・全数値は本文だけで定義できる。

分枝・内部・非退化は表のguardで明示。根番号で解を選ばない。AST合格は幾何同値性・実行可能性・目標の一意性を保証しない。


---

# AIME-1983-14 原文→入力対応カード

状態: **二次資料・公式冊子未照合・数値検証未実施**。

- 資料: `jssa/difficulty/unseen-1983/source-evidence/aime-1983-1999/aime-1983-1999.jsonl` / line 14
- 原文SHA-256: `1370fd798fd1704f5af4e9cc243e14563344ae8dd7a83b5141a063ca1dd89461`
- 入力SHA-256: `1c650b81b9da5ef8710901c41f08bd46b3167ed28cf8ae407e09701751172a24`
- 座標固定・同値性: 中心間をx軸に固定、鏡映でP.y>0。
- 答えは `official_answers.jsonl` へ入力固定後に分離。選定・入力には未使用。

## 手元の原文（二次資料のQuestionをそのまま保存）

In the adjoining figure, two circles with radii $8$ and $6$ are drawn with their centers $12$ units apart. At $P$ , one of the points of intersection, a line is drawn in such a way that the chords $QP$ and $PR$ have equal length. Find the square of the length of $QP$ . [asy]size(160); defaultpen(linewidth(.8pt)+fontsize(11pt)); dotfactor=3; pair O1=(0,0), O2=(12,0); path C1=Circle(O1,8), C2=Circle(O2,6); pair P=intersectionpoints(C1,C2)[0]; path C3=Circle(P,sqrt(130)); pair Q=intersectionpoints(C3,C1)[0]; pair R=intersectionpoints(C3,C2)[1]; draw(C1); draw(C2); draw(O2--O1); dot(O1); dot(O2); draw(Q--R); label("$Q$",Q,NW); label("$P$",P,1.5*dir(80)); label("$R$",R,NE); label("12",waypoint(O1--O2,0.4),S);[/asy]

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| center of radius-8 circle | `constructions[0]` | `O1 = Point(0, 0)` |
| centers 12 apart | `constructions[1]` | `O2 = Point(12, 0)` |
| radius 8 | `constructions[2]` | `c1 = Circle(O1, 8)` |
| radius 6 | `constructions[3]` | `c2 = Circle(O2, 6)` |
| one intersection P | `constructions[4]` | `P = Point(px, py)` |
| other endpoint Q of chord QP | `constructions[5]` | `Q = Point(qx, qy)` |
| other endpoint R of chord PR | `constructions[6]` | `R = Point(rx, ry)` |
| 鏡映で上側交点 | `conditions[0]` | `py > 0` |
| P on first circle | `conditions[1]` | `OnCircle(P,c1) = 0` |
| P on second circle | `conditions[2]` | `OnCircle(P,c2) = 0` |
| Q on first circle | `conditions[3]` | `OnCircle(Q,c1) = 0` |
| R on second circle | `conditions[4]` | `OnCircle(R,c2) = 0` |
| straight line QPR | `conditions[5]` | `OnLine(R,Line(Q,P)) = 0` |
| equal chords | `conditions[6]` | `Distance(Q,P) = Distance(P,R)` |
| distinct chord endpoints | `conditions[7]` | `Distance(Q,P) > 0` |
| 図のPはQ,Rの間（反対方向の二弦） | `conditions[8]` | `0 > ((Q.x-P.x)*(R.x-P.x)+(Q.y-P.y)*(R.y-P.y))` |
| square of QP | `target` | `Distance(Q,P)**2` |

## 残る制約

asy内の描画補助円の半径sqrt(130)は答えを埋め込んだ値かもしれないため一切使用しない。使用する図情報はQ-P-Rの順序だけ。

分枝・内部・非退化は表のguardで明示。根番号で解を選ばない。AST合格は幾何同値性・実行可能性・目標の一意性を保証しない。


---

# AIME-1984-03 原文→入力対応カード

状態: **二次資料・公式冊子未照合・数値検証未実施**。

- 資料: `jssa/difficulty/unseen-1983/source-evidence/aime-1983-1999/aime-1983-1999.jsonl` / line 18
- 原文SHA-256: `11ee2b0577d208e44bcf990b13c3d734b9d2b34cd187566b4da9cd7b80493f19`
- 入力SHA-256: `aa9d451654881d05e52066b736cfee0579e03b61009221c561a6f018394552af`
- 座標固定・同値性: A原点、ABをx軸、Cを上側。尺度は固定しない。
- 答えは `official_answers.jsonl` へ入力固定後に分離。選定・入力には未使用。

## 手元の原文（二次資料のQuestionをそのまま保存）

A point $P$ is chosen in the interior of $\triangle ABC$ such that when lines are drawn through $P$ parallel to the sides of $\triangle ABC$ , the resulting smaller triangles $t_{1}$ , $t_{2}$ , and $t_{3}$ in the figure, have areas $4$ , $9$ , and $49$ , respectively. Find the area of $\triangle ABC$ . [asy] size(200); pathpen=black+linewidth(0.65);pointpen=black; pair A=(0,0),B=(12,0),C=(4,5); D(A--B--C--cycle); D(A+(B-A)*3/4--A+(C-A)*3/4); D(B+(C-B)*5/6--B+(A-B)*5/6);D(C+(B-C)*5/12--C+(A-C)*5/12); MP("A",C,N);MP("B",A,SW);MP("C",B,SE); /* sorry mixed up points according to resources diagram. */ MP("t_3",(A+B+(B-A)*3/4+(A-B)*5/6)/2+(-1,0.8),N); MP("t_2",(B+C+(B-C)*5/12+(C-B)*5/6)/2+(-0.3,0.1),WSW); MP("t_1",(A+C+(C-A)*3/4+(A-C)*5/12)/2+(0,0.15),ESE); [/asy]

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| triangle ABC | `constructions[0]` | `A = Point(0, 0)` |
| AB horizontal | `constructions[1]` | `B = Point(b, 0)` |
| unknown C | `constructions[2]` | `C = Point(cx, cy)` |
| interior point P | `constructions[3]` | `P = Point(px, py)` |
| Pを通りBCに平行な方向点 | `constructions[4]` | `WA = Point(P.x+C.x-B.x, P.y+C.y-B.y)` |
| Pを通る辺BCの平行線 | `constructions[5]` | `LA = Line(P, WA)` |
| 平行線と辺の交点 | `constructions[6]` | `EA = Intersect(LA, Line(A, B))` |
| 平行線と辺の交点 | `constructions[7]` | `FA = Intersect(LA, Line(A, C))` |
| Pを通りCAに平行な方向点 | `constructions[8]` | `WB = Point(P.x+A.x-C.x, P.y+A.y-C.y)` |
| Pを通る辺CAの平行線 | `constructions[9]` | `LB = Line(P, WB)` |
| 平行線と辺の交点 | `constructions[10]` | `EB = Intersect(LB, Line(B, C))` |
| 平行線と辺の交点 | `constructions[11]` | `FB = Intersect(LB, Line(B, A))` |
| Pを通りABに平行な方向点 | `constructions[12]` | `WC = Point(P.x+B.x-A.x, P.y+B.y-A.y)` |
| Pを通る辺ABの平行線 | `constructions[13]` | `LC = Line(P, WC)` |
| 平行線と辺の交点 | `constructions[14]` | `EC = Intersect(LC, Line(C, A))` |
| 平行線と辺の交点 | `constructions[15]` | `FC = Intersect(LC, Line(C, B))` |
| AB positive | `conditions[0]` | `b > 0` |
| 鏡映でCを上側 | `conditions[1]` | `cy > 0` |
| P strictly inside ABC / 各辺の内側 | `conditions[2]` | `((B.x-A.x)*(P.y-A.y)-(B.y-A.y)*(P.x-A.x)) > 0` |
| P strictly inside ABC / 各辺の内側 | `conditions[3]` | `((C.x-B.x)*(P.y-B.y)-(C.y-B.y)*(P.x-B.x)) > 0` |
| P strictly inside ABC / 各辺の内側 | `conditions[4]` | `((A.x-C.x)*(P.y-C.y)-(A.y-C.y)*(P.x-C.x)) > 0` |
| t1: Pと辺AB上の二交点の小三角形 | `conditions[5]` | `Area(P, EA, FB) = 4` |
| t2: Pと辺AC上の二交点の小三角形 | `conditions[6]` | `Area(P, FA, EC) = 9` |
| t3: Pと辺BC上の二交点の小三角形 | `conditions[7]` | `Area(P, EB, FC) = 49` |
| area of ABC | `target` | `Area(A,B,C)` |

## 残る制約

本文とasyの接続から三平行線を記述。asyの頂点ラベルはコードの変数名と異なるため表示ラベルA,B,Cを使用。描画座標・分割率は使わない。

分枝・内部・非退化は表のguardで明示。根番号で解を選ばない。AST合格は幾何同値性・実行可能性・目標の一意性を保証しない。


---

# AIME-1984-06 原文→入力対応カード

状態: **二次資料・公式冊子未照合・数値検証未実施**。

- 資料: `jssa/difficulty/unseen-1983/source-evidence/aime-1983-1999/aime-1983-1999.jsonl` / line 21
- 原文SHA-256: `e002af6c30c399e113b8ebb206f63d91901d828b19312bc6dc45caf4a0c2a372`
- 入力SHA-256: `d9ab59d29bd6d6e317d77e830123c358228c9e8ac6d6ef955a0bac67fb9a69bb`
- 座標固定・同値性: 原文の座標・半径3をそのまま保持。
- 答えは `official_answers.jsonl` へ入力固定後に分離。選定・入力には未使用。

## 手元の原文（二次資料のQuestionをそのまま保存）

Three circles, each of radius $3$ , are drawn with centers at $(14, 92)$ , $(17, 76)$ , and $(19, 84)$ . A line passing through $(17,76)$ is such that the total area of the parts of the three circles to one side of the line is equal to the total area of the parts of the three circles to the other side of it. What is the absolute value of the slope of this line?

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| first circle center | `constructions[0]` | `A = Point(14, 92)` |
| second circle center / line passes through B | `constructions[1]` | `B = Point(17, 76)` |
| third circle center | `constructions[2]` | `C = Point(19, 84)` |
| line direction perpendicular to unit normal (nx,ny) | `constructions[3]` | `W = Point(17-ny, 76+nx)` |
| unknown bisecting line | `constructions[4]` | `ell = Line(B,W)` |
| normal normalization removes only representation scale | `conditions[0]` | `nx**2+ny**2 = 1` |
| 法線の符号を固定 / 有限傾き | `conditions[1]` | `ny > 0` |
| 三円盤の同じ側の部分の面積和が全体の半分 | `conditions[2]` | `(9*acos(-(max([-3,min([3,-3*nx+16*ny])]))/3)+(max([-3,min([3,-3*nx+16*ny])]))*sqrt(9-(max([-3,min([3,-3*nx+16*ny])]))**2))+9*pi/2+(9*acos(-(max([-3,min([3,2*nx+8*ny])]))/3)+(max([-3,min([3,2*nx+8*ny])]))*sqrt(9-(max([-3,min([3,2*nx+8*ny])]))**2)) = 27*pi/2` |
| absolute value of line slope | `target` | `abs(nx/ny)` |

## 残る制約

符号付き中心距離dに対する半平面円盤面積はr² acos(-d/r)+d sqrt(r²-d²)。dを[-r,r]にclampする。未知の配置での有限3円の切片面積を直接記述し、二等分線の解は求めない。

分枝・内部・非退化は表のguardで明示。根番号で解を選ばない。AST合格は幾何同値性・実行可能性・目標の一意性を保証しない。


---

# AIME-1985-09 原文→入力対応カード

状態: **二次資料・公式冊子未照合・数値検証未実施**。

- 資料: `jssa/difficulty/unseen-1983/source-evidence/aime-1983-1999/aime-1983-1999.jsonl` / line 38
- 原文SHA-256: `49c76147e5e12551babf5bf9f97086fd8e371a983b3ccf79195eda879b19b766`
- 入力SHA-256: `c25e7b6d3c57b5e4cfb1e1039caf3627f2dc2f8eba095903ab7f42bee4a707ac`
- 座標固定・同値性: O原点、三弦を水平。弦中点をy軸上に置くのは円の定義から。上下の分枝は残す。
- 答えは `official_answers.jsonl` へ入力固定後に分離。選定・入力には未使用。

## 手元の原文（二次資料のQuestionをそのまま保存）

In a circle, parallel chords of lengths $2$ , $3$ , and $4$ determine central angles of $\alpha$ , $\beta$ , and $\alpha + \beta$ radians, respectively, where $\alpha + \beta < \pi$ . If $\cos \alpha$ , which is a positive rational number, is expressed as a fraction in lowest terms, what is the sum of its numerator and denominator?

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| circle center | `constructions[0]` | `O = Point(0, 0)` |
| unknown radius | `constructions[1]` | `omega = Circle(O,r)` |
| horizontal chord of length 2 | `constructions[2]` | `A = Point(-2/2, y2)` |
| horizontal chord of length 2 | `constructions[3]` | `B = Point(2/2, y2)` |
| horizontal chord of length 3 | `constructions[4]` | `C = Point(-3/2, y3)` |
| horizontal chord of length 3 | `constructions[5]` | `D = Point(3/2, y3)` |
| horizontal chord of length 4 | `constructions[6]` | `E = Point(-4/2, y4)` |
| horizontal chord of length 4 | `constructions[7]` | `F = Point(4/2, y4)` |
| circle positive radius | `conditions[0]` | `r > 0` |
| parallel chord endpoints on circle | `conditions[1]` | `OnCircle(A,omega) = 0` |
| parallel chord endpoints on circle | `conditions[2]` | `OnCircle(B,omega) = 0` |
| parallel chord endpoints on circle | `conditions[3]` | `OnCircle(C,omega) = 0` |
| parallel chord endpoints on circle | `conditions[4]` | `OnCircle(D,omega) = 0` |
| parallel chord endpoints on circle | `conditions[5]` | `OnCircle(E,omega) = 0` |
| parallel chord endpoints on circle | `conditions[6]` | `OnCircle(F,omega) = 0` |
| length2 chord central angle alpha | `conditions[7]` | `Angle(A,O,B) = alpha` |
| length3 chord central angle beta | `conditions[8]` | `Angle(C,O,D) = beta` |
| length4 chord central angle alpha+beta | `conditions[9]` | `Angle(E,O,F) = alpha+beta` |
| positive central angle | `conditions[10]` | `alpha > 0` |
| positive central angle | `conditions[11]` | `beta > 0` |
| alpha+beta < pi | `conditions[12]` | `pi > alpha+beta` |
| positive rational cos alpha | `conditions[13]` | `cos(alpha) > 0` |
| cos alpha = reduced rational | `conditions[14]` | `cos(alpha) = m/n` |
| 既約分数の整数分子分母・Bezout整数証人 | `conditions[15]` | `IsInteger(m) = 0` |
| 既約分数の整数分子分母・Bezout整数証人 | `conditions[16]` | `IsInteger(n) = 0` |
| 既約分数の整数分子分母・Bezout整数証人 | `conditions[17]` | `IsInteger(u) = 0` |
| 既約分数の整数分子分母・Bezout整数証人 | `conditions[18]` | `IsInteger(v) = 0` |
| 分母は正 | `conditions[19]` | `n > 0` |
| 互いに素の定義的同値条件（Bezout） | `conditions[20]` | `u*m+v*n = 1` |
| 分子は正 | `conditions[21]` | `m > 0` |
| sum of numerator and denominator | `target` | `m+n` |

## 残る制約

公式冊子照合と独立の意味監査は未了。

分枝・内部・非退化は表のguardで明示。根番号で解を選ばない。AST合格は幾何同値性・実行可能性・目標の一意性を保証しない。


---

# AIME-1985-11 原文→入力対応カード

状態: **二次資料・公式冊子未照合・数値検証未実施**。

- 資料: `jssa/difficulty/unseen-1983/source-evidence/aime-1983-1999/aime-1983-1999.jsonl` / line 40
- 原文SHA-256: `d0d603d0a1fce8dfcbd9d39014d0380142c5bfbc99ea7f23e5c75758c91fc098`
- 入力SHA-256: `b03635c60b7fdfee52deb646fb857176c4955637a2b49ea2796d06f0a2c43fcc`
- 座標固定・同値性: 指定座標を保持。接点も長軸長も未知変数。
- 答えは `official_answers.jsonl` へ入力固定後に分離。選定・入力には未使用。

## 手元の原文（二次資料のQuestionをそのまま保存）

An ellipse has foci at $(9, 20)$ and $(49, 55)$ in the $xy$ -plane and is tangent to the $x$ -axis. What is the length of its major axis?

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| ellipse first focus | `constructions[0]` | `F1 = Point(9, 20)` |
| ellipse second focus | `constructions[1]` | `F2 = Point(49, 55)` |
| tangency point on x-axis | `constructions[2]` | `T = Point(t, 0)` |
| ellipse definition / major axis length L | `conditions[0]` | `Distance(T,F1)+Distance(T,F2) = L` |
| x-axis tangency: ellipse defining distance sum has zero x derivative at T | `conditions[1]` | `(t-9)/Distance(T,F1)+(t-49)/Distance(T,F2) = 0` |
| nondegenerate ellipse | `conditions[2]` | `L > Distance(F1,F2)` |
| length of major axis | `target` | `L` |

## 残る制約

両焦点はx軸の上側。距離和の水平微分0が接線水平を表す定義条件。最小値自体を事前計算しない。

分枝・内部・非退化は表のguardで明示。根番号で解を選ばない。AST合格は幾何同値性・実行可能性・目標の一意性を保証しない。


---

# AIME-1986-09 原文→入力対応カード

状態: **二次資料・公式冊子未照合・数値検証未実施**。

- 資料: `jssa/difficulty/unseen-1983/source-evidence/aime-1983-1999/aime-1983-1999.jsonl` / line 52
- 原文SHA-256: `32127ea86a8b982ca838f2913453b55afaec07885cf8362abd6b15b983d791c2`
- 入力SHA-256: `56e6d24e071e76c80761cbc23f53c0b32c2fb3c92cdb642782d9c4df3d759e46`
- 座標固定・同値性: A原点、ABをx軸、鏡映でC.y>0。長さは原文通り。
- 答えは `official_answers.jsonl` へ入力固定後に分離。選定・入力には未使用。

## 手元の原文（二次資料のQuestionをそのまま保存）

In $\triangle ABC$ , $AB= 425$ , $BC=450$ , and $AC=510$ . An interior point $P$ is then drawn, and segments are drawn through $P$ parallel to the sides of the triangle. If these three segments are of an equal length $d$ , find $d$ .

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| triangle ABC | `constructions[0]` | `A = Point(0, 0)` |
| AB=425 | `constructions[1]` | `B = Point(425, 0)` |
| unknown C | `constructions[2]` | `C = Point(cx, cy)` |
| interior P | `constructions[3]` | `P = Point(px, py)` |
| Pを通りBCに平行な方向点 | `constructions[4]` | `WA = Point(P.x+C.x-B.x, P.y+C.y-B.y)` |
| Pを通る辺BCの平行線 | `constructions[5]` | `LA = Line(P, WA)` |
| 平行線と辺の交点 | `constructions[6]` | `EA = Intersect(LA, Line(A, B))` |
| 平行線と辺の交点 | `constructions[7]` | `FA = Intersect(LA, Line(A, C))` |
| Pを通りCAに平行な方向点 | `constructions[8]` | `WB = Point(P.x+A.x-C.x, P.y+A.y-C.y)` |
| Pを通る辺CAの平行線 | `constructions[9]` | `LB = Line(P, WB)` |
| 平行線と辺の交点 | `constructions[10]` | `EB = Intersect(LB, Line(B, C))` |
| 平行線と辺の交点 | `constructions[11]` | `FB = Intersect(LB, Line(B, A))` |
| Pを通りABに平行な方向点 | `constructions[12]` | `WC = Point(P.x+B.x-A.x, P.y+B.y-A.y)` |
| Pを通る辺ABの平行線 | `constructions[13]` | `LC = Line(P, WC)` |
| 平行線と辺の交点 | `constructions[14]` | `EC = Intersect(LC, Line(C, A))` |
| 平行線と辺の交点 | `constructions[15]` | `FC = Intersect(LC, Line(C, B))` |
| 鏡映でCを上側 | `conditions[0]` | `cy > 0` |
| BC=450 | `conditions[1]` | `Distance(B,C) = 450` |
| AC=510 | `conditions[2]` | `Distance(A,C) = 510` |
| P strictly inside ABC / 各辺の内側 | `conditions[3]` | `((B.x-A.x)*(P.y-A.y)-(B.y-A.y)*(P.x-A.x)) > 0` |
| P strictly inside ABC / 各辺の内側 | `conditions[4]` | `((C.x-B.x)*(P.y-B.y)-(C.y-B.y)*(P.x-B.x)) > 0` |
| P strictly inside ABC / 各辺の内側 | `conditions[5]` | `((A.x-C.x)*(P.y-C.y)-(A.y-C.y)*(P.x-C.x)) > 0` |
| positive common segment length | `conditions[6]` | `d > 0` |
| Pを通る三本の平行切片は同長d | `conditions[7]` | `Distance(EA,FA) = d` |
| Pを通る三本の平行切片は同長d | `conditions[8]` | `Distance(EB,FB) = d` |
| Pを通る三本の平行切片は同長d | `conditions[9]` | `Distance(EC,FC) = d` |
| common length d | `target` | `d` |

## 残る制約

公式冊子照合と独立の意味監査は未了。

分枝・内部・非退化は表のguardで明示。根番号で解を選ばない。AST合格は幾何同値性・実行可能性・目標の一意性を保証しない。


---

# AIME-1986-15 原文→入力対応カード

状態: **二次資料・公式冊子未照合・数値検証未実施**。

- 資料: `jssa/difficulty/unseen-1983/source-evidence/aime-1983-1999/aime-1983-1999.jsonl` / line 58
- 原文SHA-256: `cc3f0bb7614536f5412af59694e91948c8b2485448a51400705b83c187b175f1`
- 入力SHA-256: `9b076391befdc6d07689ab6a89f2daec0b8f528ffc7ed7962f7fff8c7d56eda9`
- 座標固定・同値性: 指定された二直線が絶対座標を決めるので座標の正規化なし。
- 答えは `official_answers.jsonl` へ入力固定後に分離。選定・入力には未使用。

## 手元の原文（二次資料のQuestionをそのまま保存）

Let triangle $ABC$ be a right triangle in the $xy$ -plane with a right angle at $C_{}$ . Given that the length of the hypotenuse $AB$ is $60$ , and that the medians through $A$ and $B$ lie along the lines $y=x+3$ and $y=2x+4$ respectively, find the area of triangle $ABC$ .

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| vertex A | `constructions[0]` | `A = Point(ax, ay)` |
| vertex B | `constructions[1]` | `B = Point(bx, by)` |
| right vertex C | `constructions[2]` | `C = Point(cx, cy)` |
| median through A | `constructions[3]` | `M = Midpoint(B,C)` |
| median through B | `constructions[4]` | `N = Midpoint(A,C)` |
| hypotenuse AB=60 | `conditions[0]` | `Distance(A,B) = 60` |
| right angle C | `conditions[1]` | `((A.x-C.x)*(B.x-C.x)+(A.y-C.y)*(B.y-C.y)) = 0` |
| nondegenerate triangle | `conditions[2]` | `Area(A,B,C) > 0` |
| A on its median line y=x+3 | `conditions[3]` | `A.y = A.x+3` |
| BC midpoint on same median | `conditions[4]` | `M.y = M.x+3` |
| B on its median line y=2x+4 | `conditions[5]` | `B.y = 2*B.x+4` |
| AC midpoint on same median | `conditions[6]` | `N.y = 2*N.x+4` |
| area of ABC | `target` | `Area(A,B,C)` |

## 残る制約

公式冊子照合と独立の意味監査は未了。

分枝・内部・非退化は表のguardで明示。根番号で解を選ばない。AST合格は幾何同値性・実行可能性・目標の一意性を保証しない。


---

# AIME-1987-09 原文→入力対応カード

状態: **二次資料・公式冊子未照合・数値検証未実施**。

- 資料: `jssa/difficulty/unseen-1983/source-evidence/aime-1983-1999/aime-1983-1999.jsonl` / line 67
- 原文SHA-256: `3e798caf7f1f206f4b57a8a22e7f079619be6a5d086f8b1ce97c384e8ec14062`
- 入力SHA-256: `6b4e8d418c7fe5c79e3c6dd616ff21c4606f2e9766b1570239f2559a81cf79aa`
- 座標固定・同値性: B原点、二直角辺を正x軸・正y軸。合同移動・鏡映だけ。
- 答えは `official_answers.jsonl` へ入力固定後に分離。選定・入力には未使用。

## 手元の原文（二次資料のQuestionをそのまま保存）

Triangle $ABC$ has right angle at $B$ , and contains a point $P$ for which $PA = 10$ , $PB = 6$ , and $\angle APB = \angle BPC = \angle CPA$ .  Find $PC$ . AIME 1987 Problem 9.png

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| right vertex B | `constructions[0]` | `B = Point(0, 0)` |
| leg BA | `constructions[1]` | `A = Point(a, 0)` |
| leg BC | `constructions[2]` | `C = Point(0, c)` |
| interior P | `constructions[3]` | `P = Point(x, y)` |
| positive leg BA | `conditions[0]` | `a > 0` |
| positive leg BC | `conditions[1]` | `c > 0` |
| interior P | `conditions[2]` | `x > 0` |
| interior P | `conditions[3]` | `y > 0` |
| P below hypotenuse | `conditions[4]` | `1 > x/a+y/c` |
| PA=10 | `conditions[5]` | `Distance(P,A) = 10` |
| PB=6 | `conditions[6]` | `Distance(P,B) = 6` |
| angle APB = BPC | `conditions[7]` | `Angle(A,P,B) = Angle(B,P,C)` |
| angle BPC = CPA | `conditions[8]` | `Angle(B,P,C) = Angle(C,P,A)` |
| PC | `target` | `Distance(P,C)` |

## 残る制約

欠落画像を使わず本文で全条件を表現できる。角の値を解いて入力へ追加しない。

分枝・内部・非退化は表のguardで明示。根番号で解を選ばない。AST合格は幾何同値性・実行可能性・目標の一意性を保証しない。


---

# AIME-1988-07 原文→入力対応カード

状態: **二次資料・公式冊子未照合・数値検証未実施**。

- 資料: `jssa/difficulty/unseen-1983/source-evidence/aime-1983-1999/aime-1983-1999.jsonl` / line 76
- 原文SHA-256: `5b13a4618b340f9879cd5d3e4649289ce5b8713efbc87d307698c683c7e69108`
- 入力SHA-256: `05945ea140756eb257a5a078a116506f66763a5a2a7008f2ec45e625640cdbfb`
- 座標固定・同値性: B,C交換で足から3の側をBとする。角Aと面積は交換に不変。長さ保持。
- 答えは `official_answers.jsonl` へ入力固定後に分離。選定・入力には未使用。

## 手元の原文（二次資料のQuestionをそのまま保存）

In triangle $ABC$ , $\tan \angle CAB = 22/7$ , and the altitude from $A$ divides $BC$ into segments of length $3$ and $17$ . What is the area of triangle $ABC$ ?

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| one base endpoint | `constructions[0]` | `B = Point(0, 0)` |
| altitude divides BC into 3 and17 | `constructions[1]` | `C = Point(3+17, 0)` |
| altitude foot between B,C | `constructions[2]` | `H = Point(3, 0)` |
| altitude AH | `constructions[3]` | `A = Point(3, h)` |
| 鏡映でAを上側 | `conditions[0]` | `h > 0` |
| tan angle CAB=22/7 | `conditions[1]` | `tan(Angle(C,A,B)) = 22/7` |
| tan is positive for an interior triangle angle | `conditions[2]` | `pi/2 > Angle(C,A,B)` |
| area of ABC | `target` | `Area(A,B,C)` |

## 残る制約

公式冊子照合と独立の意味監査は未了。

分枝・内部・非退化は表のguardで明示。根番号で解を選ばない。AST合格は幾何同値性・実行可能性・目標の一意性を保証しない。


---

# AIME-1988-14 原文→入力対応カード

状態: **二次資料・公式冊子未照合・数値検証未実施**。

- 資料: `jssa/difficulty/unseen-1983/source-evidence/aime-1983-1999/aime-1983-1999.jsonl` / line 81
- 原文SHA-256: `6cdc2ea623f4b70baefdee5f575dca762e7acdb477d0f5f5148361590282075e`
- 入力SHA-256: `3366dde319cf1965e899c07947ff6337f1f0121f071a9b3f24a66e0abc96a632`
- 座標固定・同値性: 指定座標・鏡映軸を保持。
- 答えは `official_answers.jsonl` へ入力固定後に分離。選定・入力には未使用。

## 手元の原文（二次資料のQuestionをそのまま保存）

Let $C$ be the graph of $xy = 1$ , and denote by $C^*$ the reflection of $C$ in the line $y = 2x$ . Let the equation of $C^*$ be written in the form \[12x^2 + bxy + cy^2 + d = 0.\] Find the product $bc$ .

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| origin | `constructions[0]` | `O = Point(0, 0)` |
| reflection axis y=2x | `constructions[1]` | `W = Point(1, 2)` |
| axis | `constructions[2]` | `ell = Line(O,W)` |
| coordinate basis | `constructions[3]` | `E1 = Point(1, 0)` |
| coordinate basis | `constructions[4]` | `E2 = Point(0, 1)` |
| reflection of first basis vector | `constructions[5]` | `U = Reflect(E1,ell)` |
| reflection of second basis vector | `constructions[6]` | `V = Reflect(E2,ell)` |
| reflected xy=1 equation: x² coefficient is 12 | `conditions[0]` | `k*U.x*U.y = 12` |
| xy coefficient | `conditions[1]` | `k*(U.x*V.y+V.x*U.y) = b` |
| y² coefficient | `conditions[2]` | `k*V.x*V.y = c` |
| constant coefficient | `conditions[3]` | `-k = d` |
| nonzero equation multiplier | `conditions[4]` | `k != 0` |
| product bc | `target` | `b*c` |

## 残る制約

鏡映は線形かつ逆写像が同じ。逆写像(x,y)=(U.x*x+V.x*y,U.y*x+V.y*y)をxy=1へ代入し、指定二次式と係数比較する定義的翻訳。係数値は求めない。

分枝・内部・非退化は表のguardで明示。根番号で解を選ばない。AST合格は幾何同値性・実行可能性・目標の一意性を保証しない。


---

# AIME-1990-07 原文→入力対応カード

状態: **二次資料・公式冊子未照合・数値検証未実施**。

- 資料: `jssa/difficulty/unseen-1983/source-evidence/aime-1983-1999/aime-1983-1999.jsonl` / line 97
- 原文SHA-256: `a5dd59938dcf14e25988170d229a313e093fce7469040f766786b1433d987816`
- 入力SHA-256: `a61bcf002e60671d69c5206276c3d1f07cf7883365a9b662f08577f859999df8`
- 座標固定・同値性: 原文の絶対座標を保持。内心は内角二等分線の定義。
- 答えは `official_answers.jsonl` へ入力固定後に分離。選定・入力には未使用。

## 手元の原文（二次資料のQuestionをそのまま保存）

A triangle has vertices $P_{}^{}=(-8,5)$ , $Q_{}^{}=(-15,-19)$ , and $R_{}^{}=(1,-7)$ . The equation of the bisector of $\angle P$ can be written in the form $ax+2y+c=0_{}^{}$ . Find $a+c_{}^{}$ .

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| P=(-8,5) | `constructions[0]` | `P = Point(-8, 5)` |
| Q=(-15,-19) | `constructions[1]` | `Q = Point(-15, -19)` |
| R=(1,-7) | `constructions[2]` | `R = Point(1, -7)` |
| 内角二等分線上の内心 | `constructions[3]` | `I = Incenter(P,Q,R)` |
| bisector equation at P | `conditions[0]` | `a*P.x+2*P.y+c = 0` |
| bisector equation at incenter | `conditions[1]` | `a*I.x+2*I.y+c = 0` |
| a+c | `target` | `a+c` |

## 残る制約

公式冊子照合と独立の意味監査は未了。

分枝・内部・非退化は表のguardで明示。根番号で解を選ばない。AST合格は幾何同値性・実行可能性・目標の一意性を保証しない。


---

# AIME-1991-02 原文→入力対応カード

状態: **二次資料・公式冊子未照合・数値検証未実施**。

- 資料: `jssa/difficulty/unseen-1983/source-evidence/aime-1983-1999/aime-1983-1999.jsonl` / line 105
- 原文SHA-256: `6d08c44ad9d08f3e602d37975c7799d83422f358161e7064fdaf196693d8bf60`
- 入力SHA-256: `99ada126dc065aac5d43f33d1da86f0f56c0edc2b0550ba4d158166e3efe5af0`
- 座標固定・同値性: A原点、AB水平、AD垂直、辺長4,3を保持。
- 答えは `official_answers.jsonl` へ入力固定後に分離。選定・入力には未使用。

## 手元の原文（二次資料のQuestionをそのまま保存）

Rectangle $ABCD_{}^{}$ has sides $\overline {AB}$ of length 4 and $\overline {CB}$ of length 3. Divide $\overline {AB}$ into 168 congruent segments with points $A_{}^{}=P_0, P_1, \ldots, P_{168}=B$ , and divide $\overline {CB}$ into 168 congruent segments with points $C_{}^{}=Q_0, Q_1, \ldots, Q_{168}=B$ . For $1_{}^{} \le k \le 167$ , draw the segments $\overline {P_kQ_k}$ . Repeat this construction on the sides $\overline {AD}$ and $\overline {CD}$ , and then draw the diagonal $\overline {AC}$ . Find the sum of the lengths of the 335 parallel segments drawn.

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| rectangle vertex | `constructions[0]` | `A = Point(0, 0)` |
| AB=4 | `constructions[1]` | `B = Point(4, 0)` |
| CB=3 | `constructions[2]` | `C = Point(4, 3)` |
| rectangle vertex | `constructions[3]` | `D = Point(0, 3)` |
| ABを168等分する第1点（端点の順序は本文） | `constructions[4]` | `P1 = PointOnSegment(A,B,1/168)` |
| CBを168等分する第1点（端点の順序は本文） | `constructions[5]` | `Q1 = PointOnSegment(C,B,1/168)` |
| ADを168等分する第1点（端点の順序は本文） | `constructions[6]` | `U1 = PointOnSegment(A,D,1/168)` |
| CDを168等分する第1点（端点の順序は本文） | `constructions[7]` | `V1 = PointOnSegment(C,D,1/168)` |
| ABを168等分する第2点（端点の順序は本文） | `constructions[8]` | `P2 = PointOnSegment(A,B,2/168)` |
| CBを168等分する第2点（端点の順序は本文） | `constructions[9]` | `Q2 = PointOnSegment(C,B,2/168)` |
| ADを168等分する第2点（端点の順序は本文） | `constructions[10]` | `U2 = PointOnSegment(A,D,2/168)` |
| CDを168等分する第2点（端点の順序は本文） | `constructions[11]` | `V2 = PointOnSegment(C,D,2/168)` |
| ABを168等分する第3点（端点の順序は本文） | `constructions[12]` | `P3 = PointOnSegment(A,B,3/168)` |
| CBを168等分する第3点（端点の順序は本文） | `constructions[13]` | `Q3 = PointOnSegment(C,B,3/168)` |
| ADを168等分する第3点（端点の順序は本文） | `constructions[14]` | `U3 = PointOnSegment(A,D,3/168)` |
| CDを168等分する第3点（端点の順序は本文） | `constructions[15]` | `V3 = PointOnSegment(C,D,3/168)` |
| ABを168等分する第4点（端点の順序は本文） | `constructions[16]` | `P4 = PointOnSegment(A,B,4/168)` |
| CBを168等分する第4点（端点の順序は本文） | `constructions[17]` | `Q4 = PointOnSegment(C,B,4/168)` |
| ADを168等分する第4点（端点の順序は本文） | `constructions[18]` | `U4 = PointOnSegment(A,D,4/168)` |
| CDを168等分する第4点（端点の順序は本文） | `constructions[19]` | `V4 = PointOnSegment(C,D,4/168)` |
| ABを168等分する第5点（端点の順序は本文） | `constructions[20]` | `P5 = PointOnSegment(A,B,5/168)` |
| CBを168等分する第5点（端点の順序は本文） | `constructions[21]` | `Q5 = PointOnSegment(C,B,5/168)` |
| ADを168等分する第5点（端点の順序は本文） | `constructions[22]` | `U5 = PointOnSegment(A,D,5/168)` |
| CDを168等分する第5点（端点の順序は本文） | `constructions[23]` | `V5 = PointOnSegment(C,D,5/168)` |
| ABを168等分する第6点（端点の順序は本文） | `constructions[24]` | `P6 = PointOnSegment(A,B,6/168)` |
| CBを168等分する第6点（端点の順序は本文） | `constructions[25]` | `Q6 = PointOnSegment(C,B,6/168)` |
| ADを168等分する第6点（端点の順序は本文） | `constructions[26]` | `U6 = PointOnSegment(A,D,6/168)` |
| CDを168等分する第6点（端点の順序は本文） | `constructions[27]` | `V6 = PointOnSegment(C,D,6/168)` |
| ABを168等分する第7点（端点の順序は本文） | `constructions[28]` | `P7 = PointOnSegment(A,B,7/168)` |
| CBを168等分する第7点（端点の順序は本文） | `constructions[29]` | `Q7 = PointOnSegment(C,B,7/168)` |
| ADを168等分する第7点（端点の順序は本文） | `constructions[30]` | `U7 = PointOnSegment(A,D,7/168)` |
| CDを168等分する第7点（端点の順序は本文） | `constructions[31]` | `V7 = PointOnSegment(C,D,7/168)` |
| ABを168等分する第8点（端点の順序は本文） | `constructions[32]` | `P8 = PointOnSegment(A,B,8/168)` |
| CBを168等分する第8点（端点の順序は本文） | `constructions[33]` | `Q8 = PointOnSegment(C,B,8/168)` |
| ADを168等分する第8点（端点の順序は本文） | `constructions[34]` | `U8 = PointOnSegment(A,D,8/168)` |
| CDを168等分する第8点（端点の順序は本文） | `constructions[35]` | `V8 = PointOnSegment(C,D,8/168)` |
| ABを168等分する第9点（端点の順序は本文） | `constructions[36]` | `P9 = PointOnSegment(A,B,9/168)` |
| CBを168等分する第9点（端点の順序は本文） | `constructions[37]` | `Q9 = PointOnSegment(C,B,9/168)` |
| ADを168等分する第9点（端点の順序は本文） | `constructions[38]` | `U9 = PointOnSegment(A,D,9/168)` |
| CDを168等分する第9点（端点の順序は本文） | `constructions[39]` | `V9 = PointOnSegment(C,D,9/168)` |
| ABを168等分する第10点（端点の順序は本文） | `constructions[40]` | `P10 = PointOnSegment(A,B,10/168)` |
| CBを168等分する第10点（端点の順序は本文） | `constructions[41]` | `Q10 = PointOnSegment(C,B,10/168)` |
| ADを168等分する第10点（端点の順序は本文） | `constructions[42]` | `U10 = PointOnSegment(A,D,10/168)` |
| CDを168等分する第10点（端点の順序は本文） | `constructions[43]` | `V10 = PointOnSegment(C,D,10/168)` |
| ABを168等分する第11点（端点の順序は本文） | `constructions[44]` | `P11 = PointOnSegment(A,B,11/168)` |
| CBを168等分する第11点（端点の順序は本文） | `constructions[45]` | `Q11 = PointOnSegment(C,B,11/168)` |
| ADを168等分する第11点（端点の順序は本文） | `constructions[46]` | `U11 = PointOnSegment(A,D,11/168)` |
| CDを168等分する第11点（端点の順序は本文） | `constructions[47]` | `V11 = PointOnSegment(C,D,11/168)` |
| ABを168等分する第12点（端点の順序は本文） | `constructions[48]` | `P12 = PointOnSegment(A,B,12/168)` |
| CBを168等分する第12点（端点の順序は本文） | `constructions[49]` | `Q12 = PointOnSegment(C,B,12/168)` |
| ADを168等分する第12点（端点の順序は本文） | `constructions[50]` | `U12 = PointOnSegment(A,D,12/168)` |
| CDを168等分する第12点（端点の順序は本文） | `constructions[51]` | `V12 = PointOnSegment(C,D,12/168)` |
| ABを168等分する第13点（端点の順序は本文） | `constructions[52]` | `P13 = PointOnSegment(A,B,13/168)` |
| CBを168等分する第13点（端点の順序は本文） | `constructions[53]` | `Q13 = PointOnSegment(C,B,13/168)` |
| ADを168等分する第13点（端点の順序は本文） | `constructions[54]` | `U13 = PointOnSegment(A,D,13/168)` |
| CDを168等分する第13点（端点の順序は本文） | `constructions[55]` | `V13 = PointOnSegment(C,D,13/168)` |
| ABを168等分する第14点（端点の順序は本文） | `constructions[56]` | `P14 = PointOnSegment(A,B,14/168)` |
| CBを168等分する第14点（端点の順序は本文） | `constructions[57]` | `Q14 = PointOnSegment(C,B,14/168)` |
| ADを168等分する第14点（端点の順序は本文） | `constructions[58]` | `U14 = PointOnSegment(A,D,14/168)` |
| CDを168等分する第14点（端点の順序は本文） | `constructions[59]` | `V14 = PointOnSegment(C,D,14/168)` |
| ABを168等分する第15点（端点の順序は本文） | `constructions[60]` | `P15 = PointOnSegment(A,B,15/168)` |
| CBを168等分する第15点（端点の順序は本文） | `constructions[61]` | `Q15 = PointOnSegment(C,B,15/168)` |
| ADを168等分する第15点（端点の順序は本文） | `constructions[62]` | `U15 = PointOnSegment(A,D,15/168)` |
| CDを168等分する第15点（端点の順序は本文） | `constructions[63]` | `V15 = PointOnSegment(C,D,15/168)` |
| ABを168等分する第16点（端点の順序は本文） | `constructions[64]` | `P16 = PointOnSegment(A,B,16/168)` |
| CBを168等分する第16点（端点の順序は本文） | `constructions[65]` | `Q16 = PointOnSegment(C,B,16/168)` |
| ADを168等分する第16点（端点の順序は本文） | `constructions[66]` | `U16 = PointOnSegment(A,D,16/168)` |
| CDを168等分する第16点（端点の順序は本文） | `constructions[67]` | `V16 = PointOnSegment(C,D,16/168)` |
| ABを168等分する第17点（端点の順序は本文） | `constructions[68]` | `P17 = PointOnSegment(A,B,17/168)` |
| CBを168等分する第17点（端点の順序は本文） | `constructions[69]` | `Q17 = PointOnSegment(C,B,17/168)` |
| ADを168等分する第17点（端点の順序は本文） | `constructions[70]` | `U17 = PointOnSegment(A,D,17/168)` |
| CDを168等分する第17点（端点の順序は本文） | `constructions[71]` | `V17 = PointOnSegment(C,D,17/168)` |
| ABを168等分する第18点（端点の順序は本文） | `constructions[72]` | `P18 = PointOnSegment(A,B,18/168)` |
| CBを168等分する第18点（端点の順序は本文） | `constructions[73]` | `Q18 = PointOnSegment(C,B,18/168)` |
| ADを168等分する第18点（端点の順序は本文） | `constructions[74]` | `U18 = PointOnSegment(A,D,18/168)` |
| CDを168等分する第18点（端点の順序は本文） | `constructions[75]` | `V18 = PointOnSegment(C,D,18/168)` |
| ABを168等分する第19点（端点の順序は本文） | `constructions[76]` | `P19 = PointOnSegment(A,B,19/168)` |
| CBを168等分する第19点（端点の順序は本文） | `constructions[77]` | `Q19 = PointOnSegment(C,B,19/168)` |
| ADを168等分する第19点（端点の順序は本文） | `constructions[78]` | `U19 = PointOnSegment(A,D,19/168)` |
| CDを168等分する第19点（端点の順序は本文） | `constructions[79]` | `V19 = PointOnSegment(C,D,19/168)` |
| ABを168等分する第20点（端点の順序は本文） | `constructions[80]` | `P20 = PointOnSegment(A,B,20/168)` |
| CBを168等分する第20点（端点の順序は本文） | `constructions[81]` | `Q20 = PointOnSegment(C,B,20/168)` |
| ADを168等分する第20点（端点の順序は本文） | `constructions[82]` | `U20 = PointOnSegment(A,D,20/168)` |
| CDを168等分する第20点（端点の順序は本文） | `constructions[83]` | `V20 = PointOnSegment(C,D,20/168)` |
| ABを168等分する第21点（端点の順序は本文） | `constructions[84]` | `P21 = PointOnSegment(A,B,21/168)` |
| CBを168等分する第21点（端点の順序は本文） | `constructions[85]` | `Q21 = PointOnSegment(C,B,21/168)` |
| ADを168等分する第21点（端点の順序は本文） | `constructions[86]` | `U21 = PointOnSegment(A,D,21/168)` |
| CDを168等分する第21点（端点の順序は本文） | `constructions[87]` | `V21 = PointOnSegment(C,D,21/168)` |
| ABを168等分する第22点（端点の順序は本文） | `constructions[88]` | `P22 = PointOnSegment(A,B,22/168)` |
| CBを168等分する第22点（端点の順序は本文） | `constructions[89]` | `Q22 = PointOnSegment(C,B,22/168)` |
| ADを168等分する第22点（端点の順序は本文） | `constructions[90]` | `U22 = PointOnSegment(A,D,22/168)` |
| CDを168等分する第22点（端点の順序は本文） | `constructions[91]` | `V22 = PointOnSegment(C,D,22/168)` |
| ABを168等分する第23点（端点の順序は本文） | `constructions[92]` | `P23 = PointOnSegment(A,B,23/168)` |
| CBを168等分する第23点（端点の順序は本文） | `constructions[93]` | `Q23 = PointOnSegment(C,B,23/168)` |
| ADを168等分する第23点（端点の順序は本文） | `constructions[94]` | `U23 = PointOnSegment(A,D,23/168)` |
| CDを168等分する第23点（端点の順序は本文） | `constructions[95]` | `V23 = PointOnSegment(C,D,23/168)` |
| ABを168等分する第24点（端点の順序は本文） | `constructions[96]` | `P24 = PointOnSegment(A,B,24/168)` |
| CBを168等分する第24点（端点の順序は本文） | `constructions[97]` | `Q24 = PointOnSegment(C,B,24/168)` |
| ADを168等分する第24点（端点の順序は本文） | `constructions[98]` | `U24 = PointOnSegment(A,D,24/168)` |
| CDを168等分する第24点（端点の順序は本文） | `constructions[99]` | `V24 = PointOnSegment(C,D,24/168)` |
| ABを168等分する第25点（端点の順序は本文） | `constructions[100]` | `P25 = PointOnSegment(A,B,25/168)` |
| CBを168等分する第25点（端点の順序は本文） | `constructions[101]` | `Q25 = PointOnSegment(C,B,25/168)` |
| ADを168等分する第25点（端点の順序は本文） | `constructions[102]` | `U25 = PointOnSegment(A,D,25/168)` |
| CDを168等分する第25点（端点の順序は本文） | `constructions[103]` | `V25 = PointOnSegment(C,D,25/168)` |
| ABを168等分する第26点（端点の順序は本文） | `constructions[104]` | `P26 = PointOnSegment(A,B,26/168)` |
| CBを168等分する第26点（端点の順序は本文） | `constructions[105]` | `Q26 = PointOnSegment(C,B,26/168)` |
| ADを168等分する第26点（端点の順序は本文） | `constructions[106]` | `U26 = PointOnSegment(A,D,26/168)` |
| CDを168等分する第26点（端点の順序は本文） | `constructions[107]` | `V26 = PointOnSegment(C,D,26/168)` |
| ABを168等分する第27点（端点の順序は本文） | `constructions[108]` | `P27 = PointOnSegment(A,B,27/168)` |
| CBを168等分する第27点（端点の順序は本文） | `constructions[109]` | `Q27 = PointOnSegment(C,B,27/168)` |
| ADを168等分する第27点（端点の順序は本文） | `constructions[110]` | `U27 = PointOnSegment(A,D,27/168)` |
| CDを168等分する第27点（端点の順序は本文） | `constructions[111]` | `V27 = PointOnSegment(C,D,27/168)` |
| ABを168等分する第28点（端点の順序は本文） | `constructions[112]` | `P28 = PointOnSegment(A,B,28/168)` |
| CBを168等分する第28点（端点の順序は本文） | `constructions[113]` | `Q28 = PointOnSegment(C,B,28/168)` |
| ADを168等分する第28点（端点の順序は本文） | `constructions[114]` | `U28 = PointOnSegment(A,D,28/168)` |
| CDを168等分する第28点（端点の順序は本文） | `constructions[115]` | `V28 = PointOnSegment(C,D,28/168)` |
| ABを168等分する第29点（端点の順序は本文） | `constructions[116]` | `P29 = PointOnSegment(A,B,29/168)` |
| CBを168等分する第29点（端点の順序は本文） | `constructions[117]` | `Q29 = PointOnSegment(C,B,29/168)` |
| ADを168等分する第29点（端点の順序は本文） | `constructions[118]` | `U29 = PointOnSegment(A,D,29/168)` |
| CDを168等分する第29点（端点の順序は本文） | `constructions[119]` | `V29 = PointOnSegment(C,D,29/168)` |
| ABを168等分する第30点（端点の順序は本文） | `constructions[120]` | `P30 = PointOnSegment(A,B,30/168)` |
| CBを168等分する第30点（端点の順序は本文） | `constructions[121]` | `Q30 = PointOnSegment(C,B,30/168)` |
| ADを168等分する第30点（端点の順序は本文） | `constructions[122]` | `U30 = PointOnSegment(A,D,30/168)` |
| CDを168等分する第30点（端点の順序は本文） | `constructions[123]` | `V30 = PointOnSegment(C,D,30/168)` |
| ABを168等分する第31点（端点の順序は本文） | `constructions[124]` | `P31 = PointOnSegment(A,B,31/168)` |
| CBを168等分する第31点（端点の順序は本文） | `constructions[125]` | `Q31 = PointOnSegment(C,B,31/168)` |
| ADを168等分する第31点（端点の順序は本文） | `constructions[126]` | `U31 = PointOnSegment(A,D,31/168)` |
| CDを168等分する第31点（端点の順序は本文） | `constructions[127]` | `V31 = PointOnSegment(C,D,31/168)` |
| ABを168等分する第32点（端点の順序は本文） | `constructions[128]` | `P32 = PointOnSegment(A,B,32/168)` |
| CBを168等分する第32点（端点の順序は本文） | `constructions[129]` | `Q32 = PointOnSegment(C,B,32/168)` |
| ADを168等分する第32点（端点の順序は本文） | `constructions[130]` | `U32 = PointOnSegment(A,D,32/168)` |
| CDを168等分する第32点（端点の順序は本文） | `constructions[131]` | `V32 = PointOnSegment(C,D,32/168)` |
| ABを168等分する第33点（端点の順序は本文） | `constructions[132]` | `P33 = PointOnSegment(A,B,33/168)` |
| CBを168等分する第33点（端点の順序は本文） | `constructions[133]` | `Q33 = PointOnSegment(C,B,33/168)` |
| ADを168等分する第33点（端点の順序は本文） | `constructions[134]` | `U33 = PointOnSegment(A,D,33/168)` |
| CDを168等分する第33点（端点の順序は本文） | `constructions[135]` | `V33 = PointOnSegment(C,D,33/168)` |
| ABを168等分する第34点（端点の順序は本文） | `constructions[136]` | `P34 = PointOnSegment(A,B,34/168)` |
| CBを168等分する第34点（端点の順序は本文） | `constructions[137]` | `Q34 = PointOnSegment(C,B,34/168)` |
| ADを168等分する第34点（端点の順序は本文） | `constructions[138]` | `U34 = PointOnSegment(A,D,34/168)` |
| CDを168等分する第34点（端点の順序は本文） | `constructions[139]` | `V34 = PointOnSegment(C,D,34/168)` |
| ABを168等分する第35点（端点の順序は本文） | `constructions[140]` | `P35 = PointOnSegment(A,B,35/168)` |
| CBを168等分する第35点（端点の順序は本文） | `constructions[141]` | `Q35 = PointOnSegment(C,B,35/168)` |
| ADを168等分する第35点（端点の順序は本文） | `constructions[142]` | `U35 = PointOnSegment(A,D,35/168)` |
| CDを168等分する第35点（端点の順序は本文） | `constructions[143]` | `V35 = PointOnSegment(C,D,35/168)` |
| ABを168等分する第36点（端点の順序は本文） | `constructions[144]` | `P36 = PointOnSegment(A,B,36/168)` |
| CBを168等分する第36点（端点の順序は本文） | `constructions[145]` | `Q36 = PointOnSegment(C,B,36/168)` |
| ADを168等分する第36点（端点の順序は本文） | `constructions[146]` | `U36 = PointOnSegment(A,D,36/168)` |
| CDを168等分する第36点（端点の順序は本文） | `constructions[147]` | `V36 = PointOnSegment(C,D,36/168)` |
| ABを168等分する第37点（端点の順序は本文） | `constructions[148]` | `P37 = PointOnSegment(A,B,37/168)` |
| CBを168等分する第37点（端点の順序は本文） | `constructions[149]` | `Q37 = PointOnSegment(C,B,37/168)` |
| ADを168等分する第37点（端点の順序は本文） | `constructions[150]` | `U37 = PointOnSegment(A,D,37/168)` |
| CDを168等分する第37点（端点の順序は本文） | `constructions[151]` | `V37 = PointOnSegment(C,D,37/168)` |
| ABを168等分する第38点（端点の順序は本文） | `constructions[152]` | `P38 = PointOnSegment(A,B,38/168)` |
| CBを168等分する第38点（端点の順序は本文） | `constructions[153]` | `Q38 = PointOnSegment(C,B,38/168)` |
| ADを168等分する第38点（端点の順序は本文） | `constructions[154]` | `U38 = PointOnSegment(A,D,38/168)` |
| CDを168等分する第38点（端点の順序は本文） | `constructions[155]` | `V38 = PointOnSegment(C,D,38/168)` |
| ABを168等分する第39点（端点の順序は本文） | `constructions[156]` | `P39 = PointOnSegment(A,B,39/168)` |
| CBを168等分する第39点（端点の順序は本文） | `constructions[157]` | `Q39 = PointOnSegment(C,B,39/168)` |
| ADを168等分する第39点（端点の順序は本文） | `constructions[158]` | `U39 = PointOnSegment(A,D,39/168)` |
| CDを168等分する第39点（端点の順序は本文） | `constructions[159]` | `V39 = PointOnSegment(C,D,39/168)` |
| ABを168等分する第40点（端点の順序は本文） | `constructions[160]` | `P40 = PointOnSegment(A,B,40/168)` |
| CBを168等分する第40点（端点の順序は本文） | `constructions[161]` | `Q40 = PointOnSegment(C,B,40/168)` |
| ADを168等分する第40点（端点の順序は本文） | `constructions[162]` | `U40 = PointOnSegment(A,D,40/168)` |
| CDを168等分する第40点（端点の順序は本文） | `constructions[163]` | `V40 = PointOnSegment(C,D,40/168)` |
| ABを168等分する第41点（端点の順序は本文） | `constructions[164]` | `P41 = PointOnSegment(A,B,41/168)` |
| CBを168等分する第41点（端点の順序は本文） | `constructions[165]` | `Q41 = PointOnSegment(C,B,41/168)` |
| ADを168等分する第41点（端点の順序は本文） | `constructions[166]` | `U41 = PointOnSegment(A,D,41/168)` |
| CDを168等分する第41点（端点の順序は本文） | `constructions[167]` | `V41 = PointOnSegment(C,D,41/168)` |
| ABを168等分する第42点（端点の順序は本文） | `constructions[168]` | `P42 = PointOnSegment(A,B,42/168)` |
| CBを168等分する第42点（端点の順序は本文） | `constructions[169]` | `Q42 = PointOnSegment(C,B,42/168)` |
| ADを168等分する第42点（端点の順序は本文） | `constructions[170]` | `U42 = PointOnSegment(A,D,42/168)` |
| CDを168等分する第42点（端点の順序は本文） | `constructions[171]` | `V42 = PointOnSegment(C,D,42/168)` |
| ABを168等分する第43点（端点の順序は本文） | `constructions[172]` | `P43 = PointOnSegment(A,B,43/168)` |
| CBを168等分する第43点（端点の順序は本文） | `constructions[173]` | `Q43 = PointOnSegment(C,B,43/168)` |
| ADを168等分する第43点（端点の順序は本文） | `constructions[174]` | `U43 = PointOnSegment(A,D,43/168)` |
| CDを168等分する第43点（端点の順序は本文） | `constructions[175]` | `V43 = PointOnSegment(C,D,43/168)` |
| ABを168等分する第44点（端点の順序は本文） | `constructions[176]` | `P44 = PointOnSegment(A,B,44/168)` |
| CBを168等分する第44点（端点の順序は本文） | `constructions[177]` | `Q44 = PointOnSegment(C,B,44/168)` |
| ADを168等分する第44点（端点の順序は本文） | `constructions[178]` | `U44 = PointOnSegment(A,D,44/168)` |
| CDを168等分する第44点（端点の順序は本文） | `constructions[179]` | `V44 = PointOnSegment(C,D,44/168)` |
| ABを168等分する第45点（端点の順序は本文） | `constructions[180]` | `P45 = PointOnSegment(A,B,45/168)` |
| CBを168等分する第45点（端点の順序は本文） | `constructions[181]` | `Q45 = PointOnSegment(C,B,45/168)` |
| ADを168等分する第45点（端点の順序は本文） | `constructions[182]` | `U45 = PointOnSegment(A,D,45/168)` |
| CDを168等分する第45点（端点の順序は本文） | `constructions[183]` | `V45 = PointOnSegment(C,D,45/168)` |
| ABを168等分する第46点（端点の順序は本文） | `constructions[184]` | `P46 = PointOnSegment(A,B,46/168)` |
| CBを168等分する第46点（端点の順序は本文） | `constructions[185]` | `Q46 = PointOnSegment(C,B,46/168)` |
| ADを168等分する第46点（端点の順序は本文） | `constructions[186]` | `U46 = PointOnSegment(A,D,46/168)` |
| CDを168等分する第46点（端点の順序は本文） | `constructions[187]` | `V46 = PointOnSegment(C,D,46/168)` |
| ABを168等分する第47点（端点の順序は本文） | `constructions[188]` | `P47 = PointOnSegment(A,B,47/168)` |
| CBを168等分する第47点（端点の順序は本文） | `constructions[189]` | `Q47 = PointOnSegment(C,B,47/168)` |
| ADを168等分する第47点（端点の順序は本文） | `constructions[190]` | `U47 = PointOnSegment(A,D,47/168)` |
| CDを168等分する第47点（端点の順序は本文） | `constructions[191]` | `V47 = PointOnSegment(C,D,47/168)` |
| ABを168等分する第48点（端点の順序は本文） | `constructions[192]` | `P48 = PointOnSegment(A,B,48/168)` |
| CBを168等分する第48点（端点の順序は本文） | `constructions[193]` | `Q48 = PointOnSegment(C,B,48/168)` |
| ADを168等分する第48点（端点の順序は本文） | `constructions[194]` | `U48 = PointOnSegment(A,D,48/168)` |
| CDを168等分する第48点（端点の順序は本文） | `constructions[195]` | `V48 = PointOnSegment(C,D,48/168)` |
| ABを168等分する第49点（端点の順序は本文） | `constructions[196]` | `P49 = PointOnSegment(A,B,49/168)` |
| CBを168等分する第49点（端点の順序は本文） | `constructions[197]` | `Q49 = PointOnSegment(C,B,49/168)` |
| ADを168等分する第49点（端点の順序は本文） | `constructions[198]` | `U49 = PointOnSegment(A,D,49/168)` |
| CDを168等分する第49点（端点の順序は本文） | `constructions[199]` | `V49 = PointOnSegment(C,D,49/168)` |
| ABを168等分する第50点（端点の順序は本文） | `constructions[200]` | `P50 = PointOnSegment(A,B,50/168)` |
| CBを168等分する第50点（端点の順序は本文） | `constructions[201]` | `Q50 = PointOnSegment(C,B,50/168)` |
| ADを168等分する第50点（端点の順序は本文） | `constructions[202]` | `U50 = PointOnSegment(A,D,50/168)` |
| CDを168等分する第50点（端点の順序は本文） | `constructions[203]` | `V50 = PointOnSegment(C,D,50/168)` |
| ABを168等分する第51点（端点の順序は本文） | `constructions[204]` | `P51 = PointOnSegment(A,B,51/168)` |
| CBを168等分する第51点（端点の順序は本文） | `constructions[205]` | `Q51 = PointOnSegment(C,B,51/168)` |
| ADを168等分する第51点（端点の順序は本文） | `constructions[206]` | `U51 = PointOnSegment(A,D,51/168)` |
| CDを168等分する第51点（端点の順序は本文） | `constructions[207]` | `V51 = PointOnSegment(C,D,51/168)` |
| ABを168等分する第52点（端点の順序は本文） | `constructions[208]` | `P52 = PointOnSegment(A,B,52/168)` |
| CBを168等分する第52点（端点の順序は本文） | `constructions[209]` | `Q52 = PointOnSegment(C,B,52/168)` |
| ADを168等分する第52点（端点の順序は本文） | `constructions[210]` | `U52 = PointOnSegment(A,D,52/168)` |
| CDを168等分する第52点（端点の順序は本文） | `constructions[211]` | `V52 = PointOnSegment(C,D,52/168)` |
| ABを168等分する第53点（端点の順序は本文） | `constructions[212]` | `P53 = PointOnSegment(A,B,53/168)` |
| CBを168等分する第53点（端点の順序は本文） | `constructions[213]` | `Q53 = PointOnSegment(C,B,53/168)` |
| ADを168等分する第53点（端点の順序は本文） | `constructions[214]` | `U53 = PointOnSegment(A,D,53/168)` |
| CDを168等分する第53点（端点の順序は本文） | `constructions[215]` | `V53 = PointOnSegment(C,D,53/168)` |
| ABを168等分する第54点（端点の順序は本文） | `constructions[216]` | `P54 = PointOnSegment(A,B,54/168)` |
| CBを168等分する第54点（端点の順序は本文） | `constructions[217]` | `Q54 = PointOnSegment(C,B,54/168)` |
| ADを168等分する第54点（端点の順序は本文） | `constructions[218]` | `U54 = PointOnSegment(A,D,54/168)` |
| CDを168等分する第54点（端点の順序は本文） | `constructions[219]` | `V54 = PointOnSegment(C,D,54/168)` |
| ABを168等分する第55点（端点の順序は本文） | `constructions[220]` | `P55 = PointOnSegment(A,B,55/168)` |
| CBを168等分する第55点（端点の順序は本文） | `constructions[221]` | `Q55 = PointOnSegment(C,B,55/168)` |
| ADを168等分する第55点（端点の順序は本文） | `constructions[222]` | `U55 = PointOnSegment(A,D,55/168)` |
| CDを168等分する第55点（端点の順序は本文） | `constructions[223]` | `V55 = PointOnSegment(C,D,55/168)` |
| ABを168等分する第56点（端点の順序は本文） | `constructions[224]` | `P56 = PointOnSegment(A,B,56/168)` |
| CBを168等分する第56点（端点の順序は本文） | `constructions[225]` | `Q56 = PointOnSegment(C,B,56/168)` |
| ADを168等分する第56点（端点の順序は本文） | `constructions[226]` | `U56 = PointOnSegment(A,D,56/168)` |
| CDを168等分する第56点（端点の順序は本文） | `constructions[227]` | `V56 = PointOnSegment(C,D,56/168)` |
| ABを168等分する第57点（端点の順序は本文） | `constructions[228]` | `P57 = PointOnSegment(A,B,57/168)` |
| CBを168等分する第57点（端点の順序は本文） | `constructions[229]` | `Q57 = PointOnSegment(C,B,57/168)` |
| ADを168等分する第57点（端点の順序は本文） | `constructions[230]` | `U57 = PointOnSegment(A,D,57/168)` |
| CDを168等分する第57点（端点の順序は本文） | `constructions[231]` | `V57 = PointOnSegment(C,D,57/168)` |
| ABを168等分する第58点（端点の順序は本文） | `constructions[232]` | `P58 = PointOnSegment(A,B,58/168)` |
| CBを168等分する第58点（端点の順序は本文） | `constructions[233]` | `Q58 = PointOnSegment(C,B,58/168)` |
| ADを168等分する第58点（端点の順序は本文） | `constructions[234]` | `U58 = PointOnSegment(A,D,58/168)` |
| CDを168等分する第58点（端点の順序は本文） | `constructions[235]` | `V58 = PointOnSegment(C,D,58/168)` |
| ABを168等分する第59点（端点の順序は本文） | `constructions[236]` | `P59 = PointOnSegment(A,B,59/168)` |
| CBを168等分する第59点（端点の順序は本文） | `constructions[237]` | `Q59 = PointOnSegment(C,B,59/168)` |
| ADを168等分する第59点（端点の順序は本文） | `constructions[238]` | `U59 = PointOnSegment(A,D,59/168)` |
| CDを168等分する第59点（端点の順序は本文） | `constructions[239]` | `V59 = PointOnSegment(C,D,59/168)` |
| ABを168等分する第60点（端点の順序は本文） | `constructions[240]` | `P60 = PointOnSegment(A,B,60/168)` |
| CBを168等分する第60点（端点の順序は本文） | `constructions[241]` | `Q60 = PointOnSegment(C,B,60/168)` |
| ADを168等分する第60点（端点の順序は本文） | `constructions[242]` | `U60 = PointOnSegment(A,D,60/168)` |
| CDを168等分する第60点（端点の順序は本文） | `constructions[243]` | `V60 = PointOnSegment(C,D,60/168)` |
| ABを168等分する第61点（端点の順序は本文） | `constructions[244]` | `P61 = PointOnSegment(A,B,61/168)` |
| CBを168等分する第61点（端点の順序は本文） | `constructions[245]` | `Q61 = PointOnSegment(C,B,61/168)` |
| ADを168等分する第61点（端点の順序は本文） | `constructions[246]` | `U61 = PointOnSegment(A,D,61/168)` |
| CDを168等分する第61点（端点の順序は本文） | `constructions[247]` | `V61 = PointOnSegment(C,D,61/168)` |
| ABを168等分する第62点（端点の順序は本文） | `constructions[248]` | `P62 = PointOnSegment(A,B,62/168)` |
| CBを168等分する第62点（端点の順序は本文） | `constructions[249]` | `Q62 = PointOnSegment(C,B,62/168)` |
| ADを168等分する第62点（端点の順序は本文） | `constructions[250]` | `U62 = PointOnSegment(A,D,62/168)` |
| CDを168等分する第62点（端点の順序は本文） | `constructions[251]` | `V62 = PointOnSegment(C,D,62/168)` |
| ABを168等分する第63点（端点の順序は本文） | `constructions[252]` | `P63 = PointOnSegment(A,B,63/168)` |
| CBを168等分する第63点（端点の順序は本文） | `constructions[253]` | `Q63 = PointOnSegment(C,B,63/168)` |
| ADを168等分する第63点（端点の順序は本文） | `constructions[254]` | `U63 = PointOnSegment(A,D,63/168)` |
| CDを168等分する第63点（端点の順序は本文） | `constructions[255]` | `V63 = PointOnSegment(C,D,63/168)` |
| ABを168等分する第64点（端点の順序は本文） | `constructions[256]` | `P64 = PointOnSegment(A,B,64/168)` |
| CBを168等分する第64点（端点の順序は本文） | `constructions[257]` | `Q64 = PointOnSegment(C,B,64/168)` |
| ADを168等分する第64点（端点の順序は本文） | `constructions[258]` | `U64 = PointOnSegment(A,D,64/168)` |
| CDを168等分する第64点（端点の順序は本文） | `constructions[259]` | `V64 = PointOnSegment(C,D,64/168)` |
| ABを168等分する第65点（端点の順序は本文） | `constructions[260]` | `P65 = PointOnSegment(A,B,65/168)` |
| CBを168等分する第65点（端点の順序は本文） | `constructions[261]` | `Q65 = PointOnSegment(C,B,65/168)` |
| ADを168等分する第65点（端点の順序は本文） | `constructions[262]` | `U65 = PointOnSegment(A,D,65/168)` |
| CDを168等分する第65点（端点の順序は本文） | `constructions[263]` | `V65 = PointOnSegment(C,D,65/168)` |
| ABを168等分する第66点（端点の順序は本文） | `constructions[264]` | `P66 = PointOnSegment(A,B,66/168)` |
| CBを168等分する第66点（端点の順序は本文） | `constructions[265]` | `Q66 = PointOnSegment(C,B,66/168)` |
| ADを168等分する第66点（端点の順序は本文） | `constructions[266]` | `U66 = PointOnSegment(A,D,66/168)` |
| CDを168等分する第66点（端点の順序は本文） | `constructions[267]` | `V66 = PointOnSegment(C,D,66/168)` |
| ABを168等分する第67点（端点の順序は本文） | `constructions[268]` | `P67 = PointOnSegment(A,B,67/168)` |
| CBを168等分する第67点（端点の順序は本文） | `constructions[269]` | `Q67 = PointOnSegment(C,B,67/168)` |
| ADを168等分する第67点（端点の順序は本文） | `constructions[270]` | `U67 = PointOnSegment(A,D,67/168)` |
| CDを168等分する第67点（端点の順序は本文） | `constructions[271]` | `V67 = PointOnSegment(C,D,67/168)` |
| ABを168等分する第68点（端点の順序は本文） | `constructions[272]` | `P68 = PointOnSegment(A,B,68/168)` |
| CBを168等分する第68点（端点の順序は本文） | `constructions[273]` | `Q68 = PointOnSegment(C,B,68/168)` |
| ADを168等分する第68点（端点の順序は本文） | `constructions[274]` | `U68 = PointOnSegment(A,D,68/168)` |
| CDを168等分する第68点（端点の順序は本文） | `constructions[275]` | `V68 = PointOnSegment(C,D,68/168)` |
| ABを168等分する第69点（端点の順序は本文） | `constructions[276]` | `P69 = PointOnSegment(A,B,69/168)` |
| CBを168等分する第69点（端点の順序は本文） | `constructions[277]` | `Q69 = PointOnSegment(C,B,69/168)` |
| ADを168等分する第69点（端点の順序は本文） | `constructions[278]` | `U69 = PointOnSegment(A,D,69/168)` |
| CDを168等分する第69点（端点の順序は本文） | `constructions[279]` | `V69 = PointOnSegment(C,D,69/168)` |
| ABを168等分する第70点（端点の順序は本文） | `constructions[280]` | `P70 = PointOnSegment(A,B,70/168)` |
| CBを168等分する第70点（端点の順序は本文） | `constructions[281]` | `Q70 = PointOnSegment(C,B,70/168)` |
| ADを168等分する第70点（端点の順序は本文） | `constructions[282]` | `U70 = PointOnSegment(A,D,70/168)` |
| CDを168等分する第70点（端点の順序は本文） | `constructions[283]` | `V70 = PointOnSegment(C,D,70/168)` |
| ABを168等分する第71点（端点の順序は本文） | `constructions[284]` | `P71 = PointOnSegment(A,B,71/168)` |
| CBを168等分する第71点（端点の順序は本文） | `constructions[285]` | `Q71 = PointOnSegment(C,B,71/168)` |
| ADを168等分する第71点（端点の順序は本文） | `constructions[286]` | `U71 = PointOnSegment(A,D,71/168)` |
| CDを168等分する第71点（端点の順序は本文） | `constructions[287]` | `V71 = PointOnSegment(C,D,71/168)` |
| ABを168等分する第72点（端点の順序は本文） | `constructions[288]` | `P72 = PointOnSegment(A,B,72/168)` |
| CBを168等分する第72点（端点の順序は本文） | `constructions[289]` | `Q72 = PointOnSegment(C,B,72/168)` |
| ADを168等分する第72点（端点の順序は本文） | `constructions[290]` | `U72 = PointOnSegment(A,D,72/168)` |
| CDを168等分する第72点（端点の順序は本文） | `constructions[291]` | `V72 = PointOnSegment(C,D,72/168)` |
| ABを168等分する第73点（端点の順序は本文） | `constructions[292]` | `P73 = PointOnSegment(A,B,73/168)` |
| CBを168等分する第73点（端点の順序は本文） | `constructions[293]` | `Q73 = PointOnSegment(C,B,73/168)` |
| ADを168等分する第73点（端点の順序は本文） | `constructions[294]` | `U73 = PointOnSegment(A,D,73/168)` |
| CDを168等分する第73点（端点の順序は本文） | `constructions[295]` | `V73 = PointOnSegment(C,D,73/168)` |
| ABを168等分する第74点（端点の順序は本文） | `constructions[296]` | `P74 = PointOnSegment(A,B,74/168)` |
| CBを168等分する第74点（端点の順序は本文） | `constructions[297]` | `Q74 = PointOnSegment(C,B,74/168)` |
| ADを168等分する第74点（端点の順序は本文） | `constructions[298]` | `U74 = PointOnSegment(A,D,74/168)` |
| CDを168等分する第74点（端点の順序は本文） | `constructions[299]` | `V74 = PointOnSegment(C,D,74/168)` |
| ABを168等分する第75点（端点の順序は本文） | `constructions[300]` | `P75 = PointOnSegment(A,B,75/168)` |
| CBを168等分する第75点（端点の順序は本文） | `constructions[301]` | `Q75 = PointOnSegment(C,B,75/168)` |
| ADを168等分する第75点（端点の順序は本文） | `constructions[302]` | `U75 = PointOnSegment(A,D,75/168)` |
| CDを168等分する第75点（端点の順序は本文） | `constructions[303]` | `V75 = PointOnSegment(C,D,75/168)` |
| ABを168等分する第76点（端点の順序は本文） | `constructions[304]` | `P76 = PointOnSegment(A,B,76/168)` |
| CBを168等分する第76点（端点の順序は本文） | `constructions[305]` | `Q76 = PointOnSegment(C,B,76/168)` |
| ADを168等分する第76点（端点の順序は本文） | `constructions[306]` | `U76 = PointOnSegment(A,D,76/168)` |
| CDを168等分する第76点（端点の順序は本文） | `constructions[307]` | `V76 = PointOnSegment(C,D,76/168)` |
| ABを168等分する第77点（端点の順序は本文） | `constructions[308]` | `P77 = PointOnSegment(A,B,77/168)` |
| CBを168等分する第77点（端点の順序は本文） | `constructions[309]` | `Q77 = PointOnSegment(C,B,77/168)` |
| ADを168等分する第77点（端点の順序は本文） | `constructions[310]` | `U77 = PointOnSegment(A,D,77/168)` |
| CDを168等分する第77点（端点の順序は本文） | `constructions[311]` | `V77 = PointOnSegment(C,D,77/168)` |
| ABを168等分する第78点（端点の順序は本文） | `constructions[312]` | `P78 = PointOnSegment(A,B,78/168)` |
| CBを168等分する第78点（端点の順序は本文） | `constructions[313]` | `Q78 = PointOnSegment(C,B,78/168)` |
| ADを168等分する第78点（端点の順序は本文） | `constructions[314]` | `U78 = PointOnSegment(A,D,78/168)` |
| CDを168等分する第78点（端点の順序は本文） | `constructions[315]` | `V78 = PointOnSegment(C,D,78/168)` |
| ABを168等分する第79点（端点の順序は本文） | `constructions[316]` | `P79 = PointOnSegment(A,B,79/168)` |
| CBを168等分する第79点（端点の順序は本文） | `constructions[317]` | `Q79 = PointOnSegment(C,B,79/168)` |
| ADを168等分する第79点（端点の順序は本文） | `constructions[318]` | `U79 = PointOnSegment(A,D,79/168)` |
| CDを168等分する第79点（端点の順序は本文） | `constructions[319]` | `V79 = PointOnSegment(C,D,79/168)` |
| ABを168等分する第80点（端点の順序は本文） | `constructions[320]` | `P80 = PointOnSegment(A,B,80/168)` |
| CBを168等分する第80点（端点の順序は本文） | `constructions[321]` | `Q80 = PointOnSegment(C,B,80/168)` |
| ADを168等分する第80点（端点の順序は本文） | `constructions[322]` | `U80 = PointOnSegment(A,D,80/168)` |
| CDを168等分する第80点（端点の順序は本文） | `constructions[323]` | `V80 = PointOnSegment(C,D,80/168)` |
| ABを168等分する第81点（端点の順序は本文） | `constructions[324]` | `P81 = PointOnSegment(A,B,81/168)` |
| CBを168等分する第81点（端点の順序は本文） | `constructions[325]` | `Q81 = PointOnSegment(C,B,81/168)` |
| ADを168等分する第81点（端点の順序は本文） | `constructions[326]` | `U81 = PointOnSegment(A,D,81/168)` |
| CDを168等分する第81点（端点の順序は本文） | `constructions[327]` | `V81 = PointOnSegment(C,D,81/168)` |
| ABを168等分する第82点（端点の順序は本文） | `constructions[328]` | `P82 = PointOnSegment(A,B,82/168)` |
| CBを168等分する第82点（端点の順序は本文） | `constructions[329]` | `Q82 = PointOnSegment(C,B,82/168)` |
| ADを168等分する第82点（端点の順序は本文） | `constructions[330]` | `U82 = PointOnSegment(A,D,82/168)` |
| CDを168等分する第82点（端点の順序は本文） | `constructions[331]` | `V82 = PointOnSegment(C,D,82/168)` |
| ABを168等分する第83点（端点の順序は本文） | `constructions[332]` | `P83 = PointOnSegment(A,B,83/168)` |
| CBを168等分する第83点（端点の順序は本文） | `constructions[333]` | `Q83 = PointOnSegment(C,B,83/168)` |
| ADを168等分する第83点（端点の順序は本文） | `constructions[334]` | `U83 = PointOnSegment(A,D,83/168)` |
| CDを168等分する第83点（端点の順序は本文） | `constructions[335]` | `V83 = PointOnSegment(C,D,83/168)` |
| ABを168等分する第84点（端点の順序は本文） | `constructions[336]` | `P84 = PointOnSegment(A,B,84/168)` |
| CBを168等分する第84点（端点の順序は本文） | `constructions[337]` | `Q84 = PointOnSegment(C,B,84/168)` |
| ADを168等分する第84点（端点の順序は本文） | `constructions[338]` | `U84 = PointOnSegment(A,D,84/168)` |
| CDを168等分する第84点（端点の順序は本文） | `constructions[339]` | `V84 = PointOnSegment(C,D,84/168)` |
| ABを168等分する第85点（端点の順序は本文） | `constructions[340]` | `P85 = PointOnSegment(A,B,85/168)` |
| CBを168等分する第85点（端点の順序は本文） | `constructions[341]` | `Q85 = PointOnSegment(C,B,85/168)` |
| ADを168等分する第85点（端点の順序は本文） | `constructions[342]` | `U85 = PointOnSegment(A,D,85/168)` |
| CDを168等分する第85点（端点の順序は本文） | `constructions[343]` | `V85 = PointOnSegment(C,D,85/168)` |
| ABを168等分する第86点（端点の順序は本文） | `constructions[344]` | `P86 = PointOnSegment(A,B,86/168)` |
| CBを168等分する第86点（端点の順序は本文） | `constructions[345]` | `Q86 = PointOnSegment(C,B,86/168)` |
| ADを168等分する第86点（端点の順序は本文） | `constructions[346]` | `U86 = PointOnSegment(A,D,86/168)` |
| CDを168等分する第86点（端点の順序は本文） | `constructions[347]` | `V86 = PointOnSegment(C,D,86/168)` |
| ABを168等分する第87点（端点の順序は本文） | `constructions[348]` | `P87 = PointOnSegment(A,B,87/168)` |
| CBを168等分する第87点（端点の順序は本文） | `constructions[349]` | `Q87 = PointOnSegment(C,B,87/168)` |
| ADを168等分する第87点（端点の順序は本文） | `constructions[350]` | `U87 = PointOnSegment(A,D,87/168)` |
| CDを168等分する第87点（端点の順序は本文） | `constructions[351]` | `V87 = PointOnSegment(C,D,87/168)` |
| ABを168等分する第88点（端点の順序は本文） | `constructions[352]` | `P88 = PointOnSegment(A,B,88/168)` |
| CBを168等分する第88点（端点の順序は本文） | `constructions[353]` | `Q88 = PointOnSegment(C,B,88/168)` |
| ADを168等分する第88点（端点の順序は本文） | `constructions[354]` | `U88 = PointOnSegment(A,D,88/168)` |
| CDを168等分する第88点（端点の順序は本文） | `constructions[355]` | `V88 = PointOnSegment(C,D,88/168)` |
| ABを168等分する第89点（端点の順序は本文） | `constructions[356]` | `P89 = PointOnSegment(A,B,89/168)` |
| CBを168等分する第89点（端点の順序は本文） | `constructions[357]` | `Q89 = PointOnSegment(C,B,89/168)` |
| ADを168等分する第89点（端点の順序は本文） | `constructions[358]` | `U89 = PointOnSegment(A,D,89/168)` |
| CDを168等分する第89点（端点の順序は本文） | `constructions[359]` | `V89 = PointOnSegment(C,D,89/168)` |
| ABを168等分する第90点（端点の順序は本文） | `constructions[360]` | `P90 = PointOnSegment(A,B,90/168)` |
| CBを168等分する第90点（端点の順序は本文） | `constructions[361]` | `Q90 = PointOnSegment(C,B,90/168)` |
| ADを168等分する第90点（端点の順序は本文） | `constructions[362]` | `U90 = PointOnSegment(A,D,90/168)` |
| CDを168等分する第90点（端点の順序は本文） | `constructions[363]` | `V90 = PointOnSegment(C,D,90/168)` |
| ABを168等分する第91点（端点の順序は本文） | `constructions[364]` | `P91 = PointOnSegment(A,B,91/168)` |
| CBを168等分する第91点（端点の順序は本文） | `constructions[365]` | `Q91 = PointOnSegment(C,B,91/168)` |
| ADを168等分する第91点（端点の順序は本文） | `constructions[366]` | `U91 = PointOnSegment(A,D,91/168)` |
| CDを168等分する第91点（端点の順序は本文） | `constructions[367]` | `V91 = PointOnSegment(C,D,91/168)` |
| ABを168等分する第92点（端点の順序は本文） | `constructions[368]` | `P92 = PointOnSegment(A,B,92/168)` |
| CBを168等分する第92点（端点の順序は本文） | `constructions[369]` | `Q92 = PointOnSegment(C,B,92/168)` |
| ADを168等分する第92点（端点の順序は本文） | `constructions[370]` | `U92 = PointOnSegment(A,D,92/168)` |
| CDを168等分する第92点（端点の順序は本文） | `constructions[371]` | `V92 = PointOnSegment(C,D,92/168)` |
| ABを168等分する第93点（端点の順序は本文） | `constructions[372]` | `P93 = PointOnSegment(A,B,93/168)` |
| CBを168等分する第93点（端点の順序は本文） | `constructions[373]` | `Q93 = PointOnSegment(C,B,93/168)` |
| ADを168等分する第93点（端点の順序は本文） | `constructions[374]` | `U93 = PointOnSegment(A,D,93/168)` |
| CDを168等分する第93点（端点の順序は本文） | `constructions[375]` | `V93 = PointOnSegment(C,D,93/168)` |
| ABを168等分する第94点（端点の順序は本文） | `constructions[376]` | `P94 = PointOnSegment(A,B,94/168)` |
| CBを168等分する第94点（端点の順序は本文） | `constructions[377]` | `Q94 = PointOnSegment(C,B,94/168)` |
| ADを168等分する第94点（端点の順序は本文） | `constructions[378]` | `U94 = PointOnSegment(A,D,94/168)` |
| CDを168等分する第94点（端点の順序は本文） | `constructions[379]` | `V94 = PointOnSegment(C,D,94/168)` |
| ABを168等分する第95点（端点の順序は本文） | `constructions[380]` | `P95 = PointOnSegment(A,B,95/168)` |
| CBを168等分する第95点（端点の順序は本文） | `constructions[381]` | `Q95 = PointOnSegment(C,B,95/168)` |
| ADを168等分する第95点（端点の順序は本文） | `constructions[382]` | `U95 = PointOnSegment(A,D,95/168)` |
| CDを168等分する第95点（端点の順序は本文） | `constructions[383]` | `V95 = PointOnSegment(C,D,95/168)` |
| ABを168等分する第96点（端点の順序は本文） | `constructions[384]` | `P96 = PointOnSegment(A,B,96/168)` |
| CBを168等分する第96点（端点の順序は本文） | `constructions[385]` | `Q96 = PointOnSegment(C,B,96/168)` |
| ADを168等分する第96点（端点の順序は本文） | `constructions[386]` | `U96 = PointOnSegment(A,D,96/168)` |
| CDを168等分する第96点（端点の順序は本文） | `constructions[387]` | `V96 = PointOnSegment(C,D,96/168)` |
| ABを168等分する第97点（端点の順序は本文） | `constructions[388]` | `P97 = PointOnSegment(A,B,97/168)` |
| CBを168等分する第97点（端点の順序は本文） | `constructions[389]` | `Q97 = PointOnSegment(C,B,97/168)` |
| ADを168等分する第97点（端点の順序は本文） | `constructions[390]` | `U97 = PointOnSegment(A,D,97/168)` |
| CDを168等分する第97点（端点の順序は本文） | `constructions[391]` | `V97 = PointOnSegment(C,D,97/168)` |
| ABを168等分する第98点（端点の順序は本文） | `constructions[392]` | `P98 = PointOnSegment(A,B,98/168)` |
| CBを168等分する第98点（端点の順序は本文） | `constructions[393]` | `Q98 = PointOnSegment(C,B,98/168)` |
| ADを168等分する第98点（端点の順序は本文） | `constructions[394]` | `U98 = PointOnSegment(A,D,98/168)` |
| CDを168等分する第98点（端点の順序は本文） | `constructions[395]` | `V98 = PointOnSegment(C,D,98/168)` |
| ABを168等分する第99点（端点の順序は本文） | `constructions[396]` | `P99 = PointOnSegment(A,B,99/168)` |
| CBを168等分する第99点（端点の順序は本文） | `constructions[397]` | `Q99 = PointOnSegment(C,B,99/168)` |
| ADを168等分する第99点（端点の順序は本文） | `constructions[398]` | `U99 = PointOnSegment(A,D,99/168)` |
| CDを168等分する第99点（端点の順序は本文） | `constructions[399]` | `V99 = PointOnSegment(C,D,99/168)` |
| ABを168等分する第100点（端点の順序は本文） | `constructions[400]` | `P100 = PointOnSegment(A,B,100/168)` |
| CBを168等分する第100点（端点の順序は本文） | `constructions[401]` | `Q100 = PointOnSegment(C,B,100/168)` |
| ADを168等分する第100点（端点の順序は本文） | `constructions[402]` | `U100 = PointOnSegment(A,D,100/168)` |
| CDを168等分する第100点（端点の順序は本文） | `constructions[403]` | `V100 = PointOnSegment(C,D,100/168)` |
| ABを168等分する第101点（端点の順序は本文） | `constructions[404]` | `P101 = PointOnSegment(A,B,101/168)` |
| CBを168等分する第101点（端点の順序は本文） | `constructions[405]` | `Q101 = PointOnSegment(C,B,101/168)` |
| ADを168等分する第101点（端点の順序は本文） | `constructions[406]` | `U101 = PointOnSegment(A,D,101/168)` |
| CDを168等分する第101点（端点の順序は本文） | `constructions[407]` | `V101 = PointOnSegment(C,D,101/168)` |
| ABを168等分する第102点（端点の順序は本文） | `constructions[408]` | `P102 = PointOnSegment(A,B,102/168)` |
| CBを168等分する第102点（端点の順序は本文） | `constructions[409]` | `Q102 = PointOnSegment(C,B,102/168)` |
| ADを168等分する第102点（端点の順序は本文） | `constructions[410]` | `U102 = PointOnSegment(A,D,102/168)` |
| CDを168等分する第102点（端点の順序は本文） | `constructions[411]` | `V102 = PointOnSegment(C,D,102/168)` |
| ABを168等分する第103点（端点の順序は本文） | `constructions[412]` | `P103 = PointOnSegment(A,B,103/168)` |
| CBを168等分する第103点（端点の順序は本文） | `constructions[413]` | `Q103 = PointOnSegment(C,B,103/168)` |
| ADを168等分する第103点（端点の順序は本文） | `constructions[414]` | `U103 = PointOnSegment(A,D,103/168)` |
| CDを168等分する第103点（端点の順序は本文） | `constructions[415]` | `V103 = PointOnSegment(C,D,103/168)` |
| ABを168等分する第104点（端点の順序は本文） | `constructions[416]` | `P104 = PointOnSegment(A,B,104/168)` |
| CBを168等分する第104点（端点の順序は本文） | `constructions[417]` | `Q104 = PointOnSegment(C,B,104/168)` |
| ADを168等分する第104点（端点の順序は本文） | `constructions[418]` | `U104 = PointOnSegment(A,D,104/168)` |
| CDを168等分する第104点（端点の順序は本文） | `constructions[419]` | `V104 = PointOnSegment(C,D,104/168)` |
| ABを168等分する第105点（端点の順序は本文） | `constructions[420]` | `P105 = PointOnSegment(A,B,105/168)` |
| CBを168等分する第105点（端点の順序は本文） | `constructions[421]` | `Q105 = PointOnSegment(C,B,105/168)` |
| ADを168等分する第105点（端点の順序は本文） | `constructions[422]` | `U105 = PointOnSegment(A,D,105/168)` |
| CDを168等分する第105点（端点の順序は本文） | `constructions[423]` | `V105 = PointOnSegment(C,D,105/168)` |
| ABを168等分する第106点（端点の順序は本文） | `constructions[424]` | `P106 = PointOnSegment(A,B,106/168)` |
| CBを168等分する第106点（端点の順序は本文） | `constructions[425]` | `Q106 = PointOnSegment(C,B,106/168)` |
| ADを168等分する第106点（端点の順序は本文） | `constructions[426]` | `U106 = PointOnSegment(A,D,106/168)` |
| CDを168等分する第106点（端点の順序は本文） | `constructions[427]` | `V106 = PointOnSegment(C,D,106/168)` |
| ABを168等分する第107点（端点の順序は本文） | `constructions[428]` | `P107 = PointOnSegment(A,B,107/168)` |
| CBを168等分する第107点（端点の順序は本文） | `constructions[429]` | `Q107 = PointOnSegment(C,B,107/168)` |
| ADを168等分する第107点（端点の順序は本文） | `constructions[430]` | `U107 = PointOnSegment(A,D,107/168)` |
| CDを168等分する第107点（端点の順序は本文） | `constructions[431]` | `V107 = PointOnSegment(C,D,107/168)` |
| ABを168等分する第108点（端点の順序は本文） | `constructions[432]` | `P108 = PointOnSegment(A,B,108/168)` |
| CBを168等分する第108点（端点の順序は本文） | `constructions[433]` | `Q108 = PointOnSegment(C,B,108/168)` |
| ADを168等分する第108点（端点の順序は本文） | `constructions[434]` | `U108 = PointOnSegment(A,D,108/168)` |
| CDを168等分する第108点（端点の順序は本文） | `constructions[435]` | `V108 = PointOnSegment(C,D,108/168)` |
| ABを168等分する第109点（端点の順序は本文） | `constructions[436]` | `P109 = PointOnSegment(A,B,109/168)` |
| CBを168等分する第109点（端点の順序は本文） | `constructions[437]` | `Q109 = PointOnSegment(C,B,109/168)` |
| ADを168等分する第109点（端点の順序は本文） | `constructions[438]` | `U109 = PointOnSegment(A,D,109/168)` |
| CDを168等分する第109点（端点の順序は本文） | `constructions[439]` | `V109 = PointOnSegment(C,D,109/168)` |
| ABを168等分する第110点（端点の順序は本文） | `constructions[440]` | `P110 = PointOnSegment(A,B,110/168)` |
| CBを168等分する第110点（端点の順序は本文） | `constructions[441]` | `Q110 = PointOnSegment(C,B,110/168)` |
| ADを168等分する第110点（端点の順序は本文） | `constructions[442]` | `U110 = PointOnSegment(A,D,110/168)` |
| CDを168等分する第110点（端点の順序は本文） | `constructions[443]` | `V110 = PointOnSegment(C,D,110/168)` |
| ABを168等分する第111点（端点の順序は本文） | `constructions[444]` | `P111 = PointOnSegment(A,B,111/168)` |
| CBを168等分する第111点（端点の順序は本文） | `constructions[445]` | `Q111 = PointOnSegment(C,B,111/168)` |
| ADを168等分する第111点（端点の順序は本文） | `constructions[446]` | `U111 = PointOnSegment(A,D,111/168)` |
| CDを168等分する第111点（端点の順序は本文） | `constructions[447]` | `V111 = PointOnSegment(C,D,111/168)` |
| ABを168等分する第112点（端点の順序は本文） | `constructions[448]` | `P112 = PointOnSegment(A,B,112/168)` |
| CBを168等分する第112点（端点の順序は本文） | `constructions[449]` | `Q112 = PointOnSegment(C,B,112/168)` |
| ADを168等分する第112点（端点の順序は本文） | `constructions[450]` | `U112 = PointOnSegment(A,D,112/168)` |
| CDを168等分する第112点（端点の順序は本文） | `constructions[451]` | `V112 = PointOnSegment(C,D,112/168)` |
| ABを168等分する第113点（端点の順序は本文） | `constructions[452]` | `P113 = PointOnSegment(A,B,113/168)` |
| CBを168等分する第113点（端点の順序は本文） | `constructions[453]` | `Q113 = PointOnSegment(C,B,113/168)` |
| ADを168等分する第113点（端点の順序は本文） | `constructions[454]` | `U113 = PointOnSegment(A,D,113/168)` |
| CDを168等分する第113点（端点の順序は本文） | `constructions[455]` | `V113 = PointOnSegment(C,D,113/168)` |
| ABを168等分する第114点（端点の順序は本文） | `constructions[456]` | `P114 = PointOnSegment(A,B,114/168)` |
| CBを168等分する第114点（端点の順序は本文） | `constructions[457]` | `Q114 = PointOnSegment(C,B,114/168)` |
| ADを168等分する第114点（端点の順序は本文） | `constructions[458]` | `U114 = PointOnSegment(A,D,114/168)` |
| CDを168等分する第114点（端点の順序は本文） | `constructions[459]` | `V114 = PointOnSegment(C,D,114/168)` |
| ABを168等分する第115点（端点の順序は本文） | `constructions[460]` | `P115 = PointOnSegment(A,B,115/168)` |
| CBを168等分する第115点（端点の順序は本文） | `constructions[461]` | `Q115 = PointOnSegment(C,B,115/168)` |
| ADを168等分する第115点（端点の順序は本文） | `constructions[462]` | `U115 = PointOnSegment(A,D,115/168)` |
| CDを168等分する第115点（端点の順序は本文） | `constructions[463]` | `V115 = PointOnSegment(C,D,115/168)` |
| ABを168等分する第116点（端点の順序は本文） | `constructions[464]` | `P116 = PointOnSegment(A,B,116/168)` |
| CBを168等分する第116点（端点の順序は本文） | `constructions[465]` | `Q116 = PointOnSegment(C,B,116/168)` |
| ADを168等分する第116点（端点の順序は本文） | `constructions[466]` | `U116 = PointOnSegment(A,D,116/168)` |
| CDを168等分する第116点（端点の順序は本文） | `constructions[467]` | `V116 = PointOnSegment(C,D,116/168)` |
| ABを168等分する第117点（端点の順序は本文） | `constructions[468]` | `P117 = PointOnSegment(A,B,117/168)` |
| CBを168等分する第117点（端点の順序は本文） | `constructions[469]` | `Q117 = PointOnSegment(C,B,117/168)` |
| ADを168等分する第117点（端点の順序は本文） | `constructions[470]` | `U117 = PointOnSegment(A,D,117/168)` |
| CDを168等分する第117点（端点の順序は本文） | `constructions[471]` | `V117 = PointOnSegment(C,D,117/168)` |
| ABを168等分する第118点（端点の順序は本文） | `constructions[472]` | `P118 = PointOnSegment(A,B,118/168)` |
| CBを168等分する第118点（端点の順序は本文） | `constructions[473]` | `Q118 = PointOnSegment(C,B,118/168)` |
| ADを168等分する第118点（端点の順序は本文） | `constructions[474]` | `U118 = PointOnSegment(A,D,118/168)` |
| CDを168等分する第118点（端点の順序は本文） | `constructions[475]` | `V118 = PointOnSegment(C,D,118/168)` |
| ABを168等分する第119点（端点の順序は本文） | `constructions[476]` | `P119 = PointOnSegment(A,B,119/168)` |
| CBを168等分する第119点（端点の順序は本文） | `constructions[477]` | `Q119 = PointOnSegment(C,B,119/168)` |
| ADを168等分する第119点（端点の順序は本文） | `constructions[478]` | `U119 = PointOnSegment(A,D,119/168)` |
| CDを168等分する第119点（端点の順序は本文） | `constructions[479]` | `V119 = PointOnSegment(C,D,119/168)` |
| ABを168等分する第120点（端点の順序は本文） | `constructions[480]` | `P120 = PointOnSegment(A,B,120/168)` |
| CBを168等分する第120点（端点の順序は本文） | `constructions[481]` | `Q120 = PointOnSegment(C,B,120/168)` |
| ADを168等分する第120点（端点の順序は本文） | `constructions[482]` | `U120 = PointOnSegment(A,D,120/168)` |
| CDを168等分する第120点（端点の順序は本文） | `constructions[483]` | `V120 = PointOnSegment(C,D,120/168)` |
| ABを168等分する第121点（端点の順序は本文） | `constructions[484]` | `P121 = PointOnSegment(A,B,121/168)` |
| CBを168等分する第121点（端点の順序は本文） | `constructions[485]` | `Q121 = PointOnSegment(C,B,121/168)` |
| ADを168等分する第121点（端点の順序は本文） | `constructions[486]` | `U121 = PointOnSegment(A,D,121/168)` |
| CDを168等分する第121点（端点の順序は本文） | `constructions[487]` | `V121 = PointOnSegment(C,D,121/168)` |
| ABを168等分する第122点（端点の順序は本文） | `constructions[488]` | `P122 = PointOnSegment(A,B,122/168)` |
| CBを168等分する第122点（端点の順序は本文） | `constructions[489]` | `Q122 = PointOnSegment(C,B,122/168)` |
| ADを168等分する第122点（端点の順序は本文） | `constructions[490]` | `U122 = PointOnSegment(A,D,122/168)` |
| CDを168等分する第122点（端点の順序は本文） | `constructions[491]` | `V122 = PointOnSegment(C,D,122/168)` |
| ABを168等分する第123点（端点の順序は本文） | `constructions[492]` | `P123 = PointOnSegment(A,B,123/168)` |
| CBを168等分する第123点（端点の順序は本文） | `constructions[493]` | `Q123 = PointOnSegment(C,B,123/168)` |
| ADを168等分する第123点（端点の順序は本文） | `constructions[494]` | `U123 = PointOnSegment(A,D,123/168)` |
| CDを168等分する第123点（端点の順序は本文） | `constructions[495]` | `V123 = PointOnSegment(C,D,123/168)` |
| ABを168等分する第124点（端点の順序は本文） | `constructions[496]` | `P124 = PointOnSegment(A,B,124/168)` |
| CBを168等分する第124点（端点の順序は本文） | `constructions[497]` | `Q124 = PointOnSegment(C,B,124/168)` |
| ADを168等分する第124点（端点の順序は本文） | `constructions[498]` | `U124 = PointOnSegment(A,D,124/168)` |
| CDを168等分する第124点（端点の順序は本文） | `constructions[499]` | `V124 = PointOnSegment(C,D,124/168)` |
| ABを168等分する第125点（端点の順序は本文） | `constructions[500]` | `P125 = PointOnSegment(A,B,125/168)` |
| CBを168等分する第125点（端点の順序は本文） | `constructions[501]` | `Q125 = PointOnSegment(C,B,125/168)` |
| ADを168等分する第125点（端点の順序は本文） | `constructions[502]` | `U125 = PointOnSegment(A,D,125/168)` |
| CDを168等分する第125点（端点の順序は本文） | `constructions[503]` | `V125 = PointOnSegment(C,D,125/168)` |
| ABを168等分する第126点（端点の順序は本文） | `constructions[504]` | `P126 = PointOnSegment(A,B,126/168)` |
| CBを168等分する第126点（端点の順序は本文） | `constructions[505]` | `Q126 = PointOnSegment(C,B,126/168)` |
| ADを168等分する第126点（端点の順序は本文） | `constructions[506]` | `U126 = PointOnSegment(A,D,126/168)` |
| CDを168等分する第126点（端点の順序は本文） | `constructions[507]` | `V126 = PointOnSegment(C,D,126/168)` |
| ABを168等分する第127点（端点の順序は本文） | `constructions[508]` | `P127 = PointOnSegment(A,B,127/168)` |
| CBを168等分する第127点（端点の順序は本文） | `constructions[509]` | `Q127 = PointOnSegment(C,B,127/168)` |
| ADを168等分する第127点（端点の順序は本文） | `constructions[510]` | `U127 = PointOnSegment(A,D,127/168)` |
| CDを168等分する第127点（端点の順序は本文） | `constructions[511]` | `V127 = PointOnSegment(C,D,127/168)` |
| ABを168等分する第128点（端点の順序は本文） | `constructions[512]` | `P128 = PointOnSegment(A,B,128/168)` |
| CBを168等分する第128点（端点の順序は本文） | `constructions[513]` | `Q128 = PointOnSegment(C,B,128/168)` |
| ADを168等分する第128点（端点の順序は本文） | `constructions[514]` | `U128 = PointOnSegment(A,D,128/168)` |
| CDを168等分する第128点（端点の順序は本文） | `constructions[515]` | `V128 = PointOnSegment(C,D,128/168)` |
| ABを168等分する第129点（端点の順序は本文） | `constructions[516]` | `P129 = PointOnSegment(A,B,129/168)` |
| CBを168等分する第129点（端点の順序は本文） | `constructions[517]` | `Q129 = PointOnSegment(C,B,129/168)` |
| ADを168等分する第129点（端点の順序は本文） | `constructions[518]` | `U129 = PointOnSegment(A,D,129/168)` |
| CDを168等分する第129点（端点の順序は本文） | `constructions[519]` | `V129 = PointOnSegment(C,D,129/168)` |
| ABを168等分する第130点（端点の順序は本文） | `constructions[520]` | `P130 = PointOnSegment(A,B,130/168)` |
| CBを168等分する第130点（端点の順序は本文） | `constructions[521]` | `Q130 = PointOnSegment(C,B,130/168)` |
| ADを168等分する第130点（端点の順序は本文） | `constructions[522]` | `U130 = PointOnSegment(A,D,130/168)` |
| CDを168等分する第130点（端点の順序は本文） | `constructions[523]` | `V130 = PointOnSegment(C,D,130/168)` |
| ABを168等分する第131点（端点の順序は本文） | `constructions[524]` | `P131 = PointOnSegment(A,B,131/168)` |
| CBを168等分する第131点（端点の順序は本文） | `constructions[525]` | `Q131 = PointOnSegment(C,B,131/168)` |
| ADを168等分する第131点（端点の順序は本文） | `constructions[526]` | `U131 = PointOnSegment(A,D,131/168)` |
| CDを168等分する第131点（端点の順序は本文） | `constructions[527]` | `V131 = PointOnSegment(C,D,131/168)` |
| ABを168等分する第132点（端点の順序は本文） | `constructions[528]` | `P132 = PointOnSegment(A,B,132/168)` |
| CBを168等分する第132点（端点の順序は本文） | `constructions[529]` | `Q132 = PointOnSegment(C,B,132/168)` |
| ADを168等分する第132点（端点の順序は本文） | `constructions[530]` | `U132 = PointOnSegment(A,D,132/168)` |
| CDを168等分する第132点（端点の順序は本文） | `constructions[531]` | `V132 = PointOnSegment(C,D,132/168)` |
| ABを168等分する第133点（端点の順序は本文） | `constructions[532]` | `P133 = PointOnSegment(A,B,133/168)` |
| CBを168等分する第133点（端点の順序は本文） | `constructions[533]` | `Q133 = PointOnSegment(C,B,133/168)` |
| ADを168等分する第133点（端点の順序は本文） | `constructions[534]` | `U133 = PointOnSegment(A,D,133/168)` |
| CDを168等分する第133点（端点の順序は本文） | `constructions[535]` | `V133 = PointOnSegment(C,D,133/168)` |
| ABを168等分する第134点（端点の順序は本文） | `constructions[536]` | `P134 = PointOnSegment(A,B,134/168)` |
| CBを168等分する第134点（端点の順序は本文） | `constructions[537]` | `Q134 = PointOnSegment(C,B,134/168)` |
| ADを168等分する第134点（端点の順序は本文） | `constructions[538]` | `U134 = PointOnSegment(A,D,134/168)` |
| CDを168等分する第134点（端点の順序は本文） | `constructions[539]` | `V134 = PointOnSegment(C,D,134/168)` |
| ABを168等分する第135点（端点の順序は本文） | `constructions[540]` | `P135 = PointOnSegment(A,B,135/168)` |
| CBを168等分する第135点（端点の順序は本文） | `constructions[541]` | `Q135 = PointOnSegment(C,B,135/168)` |
| ADを168等分する第135点（端点の順序は本文） | `constructions[542]` | `U135 = PointOnSegment(A,D,135/168)` |
| CDを168等分する第135点（端点の順序は本文） | `constructions[543]` | `V135 = PointOnSegment(C,D,135/168)` |
| ABを168等分する第136点（端点の順序は本文） | `constructions[544]` | `P136 = PointOnSegment(A,B,136/168)` |
| CBを168等分する第136点（端点の順序は本文） | `constructions[545]` | `Q136 = PointOnSegment(C,B,136/168)` |
| ADを168等分する第136点（端点の順序は本文） | `constructions[546]` | `U136 = PointOnSegment(A,D,136/168)` |
| CDを168等分する第136点（端点の順序は本文） | `constructions[547]` | `V136 = PointOnSegment(C,D,136/168)` |
| ABを168等分する第137点（端点の順序は本文） | `constructions[548]` | `P137 = PointOnSegment(A,B,137/168)` |
| CBを168等分する第137点（端点の順序は本文） | `constructions[549]` | `Q137 = PointOnSegment(C,B,137/168)` |
| ADを168等分する第137点（端点の順序は本文） | `constructions[550]` | `U137 = PointOnSegment(A,D,137/168)` |
| CDを168等分する第137点（端点の順序は本文） | `constructions[551]` | `V137 = PointOnSegment(C,D,137/168)` |
| ABを168等分する第138点（端点の順序は本文） | `constructions[552]` | `P138 = PointOnSegment(A,B,138/168)` |
| CBを168等分する第138点（端点の順序は本文） | `constructions[553]` | `Q138 = PointOnSegment(C,B,138/168)` |
| ADを168等分する第138点（端点の順序は本文） | `constructions[554]` | `U138 = PointOnSegment(A,D,138/168)` |
| CDを168等分する第138点（端点の順序は本文） | `constructions[555]` | `V138 = PointOnSegment(C,D,138/168)` |
| ABを168等分する第139点（端点の順序は本文） | `constructions[556]` | `P139 = PointOnSegment(A,B,139/168)` |
| CBを168等分する第139点（端点の順序は本文） | `constructions[557]` | `Q139 = PointOnSegment(C,B,139/168)` |
| ADを168等分する第139点（端点の順序は本文） | `constructions[558]` | `U139 = PointOnSegment(A,D,139/168)` |
| CDを168等分する第139点（端点の順序は本文） | `constructions[559]` | `V139 = PointOnSegment(C,D,139/168)` |
| ABを168等分する第140点（端点の順序は本文） | `constructions[560]` | `P140 = PointOnSegment(A,B,140/168)` |
| CBを168等分する第140点（端点の順序は本文） | `constructions[561]` | `Q140 = PointOnSegment(C,B,140/168)` |
| ADを168等分する第140点（端点の順序は本文） | `constructions[562]` | `U140 = PointOnSegment(A,D,140/168)` |
| CDを168等分する第140点（端点の順序は本文） | `constructions[563]` | `V140 = PointOnSegment(C,D,140/168)` |
| ABを168等分する第141点（端点の順序は本文） | `constructions[564]` | `P141 = PointOnSegment(A,B,141/168)` |
| CBを168等分する第141点（端点の順序は本文） | `constructions[565]` | `Q141 = PointOnSegment(C,B,141/168)` |
| ADを168等分する第141点（端点の順序は本文） | `constructions[566]` | `U141 = PointOnSegment(A,D,141/168)` |
| CDを168等分する第141点（端点の順序は本文） | `constructions[567]` | `V141 = PointOnSegment(C,D,141/168)` |
| ABを168等分する第142点（端点の順序は本文） | `constructions[568]` | `P142 = PointOnSegment(A,B,142/168)` |
| CBを168等分する第142点（端点の順序は本文） | `constructions[569]` | `Q142 = PointOnSegment(C,B,142/168)` |
| ADを168等分する第142点（端点の順序は本文） | `constructions[570]` | `U142 = PointOnSegment(A,D,142/168)` |
| CDを168等分する第142点（端点の順序は本文） | `constructions[571]` | `V142 = PointOnSegment(C,D,142/168)` |
| ABを168等分する第143点（端点の順序は本文） | `constructions[572]` | `P143 = PointOnSegment(A,B,143/168)` |
| CBを168等分する第143点（端点の順序は本文） | `constructions[573]` | `Q143 = PointOnSegment(C,B,143/168)` |
| ADを168等分する第143点（端点の順序は本文） | `constructions[574]` | `U143 = PointOnSegment(A,D,143/168)` |
| CDを168等分する第143点（端点の順序は本文） | `constructions[575]` | `V143 = PointOnSegment(C,D,143/168)` |
| ABを168等分する第144点（端点の順序は本文） | `constructions[576]` | `P144 = PointOnSegment(A,B,144/168)` |
| CBを168等分する第144点（端点の順序は本文） | `constructions[577]` | `Q144 = PointOnSegment(C,B,144/168)` |
| ADを168等分する第144点（端点の順序は本文） | `constructions[578]` | `U144 = PointOnSegment(A,D,144/168)` |
| CDを168等分する第144点（端点の順序は本文） | `constructions[579]` | `V144 = PointOnSegment(C,D,144/168)` |
| ABを168等分する第145点（端点の順序は本文） | `constructions[580]` | `P145 = PointOnSegment(A,B,145/168)` |
| CBを168等分する第145点（端点の順序は本文） | `constructions[581]` | `Q145 = PointOnSegment(C,B,145/168)` |
| ADを168等分する第145点（端点の順序は本文） | `constructions[582]` | `U145 = PointOnSegment(A,D,145/168)` |
| CDを168等分する第145点（端点の順序は本文） | `constructions[583]` | `V145 = PointOnSegment(C,D,145/168)` |
| ABを168等分する第146点（端点の順序は本文） | `constructions[584]` | `P146 = PointOnSegment(A,B,146/168)` |
| CBを168等分する第146点（端点の順序は本文） | `constructions[585]` | `Q146 = PointOnSegment(C,B,146/168)` |
| ADを168等分する第146点（端点の順序は本文） | `constructions[586]` | `U146 = PointOnSegment(A,D,146/168)` |
| CDを168等分する第146点（端点の順序は本文） | `constructions[587]` | `V146 = PointOnSegment(C,D,146/168)` |
| ABを168等分する第147点（端点の順序は本文） | `constructions[588]` | `P147 = PointOnSegment(A,B,147/168)` |
| CBを168等分する第147点（端点の順序は本文） | `constructions[589]` | `Q147 = PointOnSegment(C,B,147/168)` |
| ADを168等分する第147点（端点の順序は本文） | `constructions[590]` | `U147 = PointOnSegment(A,D,147/168)` |
| CDを168等分する第147点（端点の順序は本文） | `constructions[591]` | `V147 = PointOnSegment(C,D,147/168)` |
| ABを168等分する第148点（端点の順序は本文） | `constructions[592]` | `P148 = PointOnSegment(A,B,148/168)` |
| CBを168等分する第148点（端点の順序は本文） | `constructions[593]` | `Q148 = PointOnSegment(C,B,148/168)` |
| ADを168等分する第148点（端点の順序は本文） | `constructions[594]` | `U148 = PointOnSegment(A,D,148/168)` |
| CDを168等分する第148点（端点の順序は本文） | `constructions[595]` | `V148 = PointOnSegment(C,D,148/168)` |
| ABを168等分する第149点（端点の順序は本文） | `constructions[596]` | `P149 = PointOnSegment(A,B,149/168)` |
| CBを168等分する第149点（端点の順序は本文） | `constructions[597]` | `Q149 = PointOnSegment(C,B,149/168)` |
| ADを168等分する第149点（端点の順序は本文） | `constructions[598]` | `U149 = PointOnSegment(A,D,149/168)` |
| CDを168等分する第149点（端点の順序は本文） | `constructions[599]` | `V149 = PointOnSegment(C,D,149/168)` |
| ABを168等分する第150点（端点の順序は本文） | `constructions[600]` | `P150 = PointOnSegment(A,B,150/168)` |
| CBを168等分する第150点（端点の順序は本文） | `constructions[601]` | `Q150 = PointOnSegment(C,B,150/168)` |
| ADを168等分する第150点（端点の順序は本文） | `constructions[602]` | `U150 = PointOnSegment(A,D,150/168)` |
| CDを168等分する第150点（端点の順序は本文） | `constructions[603]` | `V150 = PointOnSegment(C,D,150/168)` |
| ABを168等分する第151点（端点の順序は本文） | `constructions[604]` | `P151 = PointOnSegment(A,B,151/168)` |
| CBを168等分する第151点（端点の順序は本文） | `constructions[605]` | `Q151 = PointOnSegment(C,B,151/168)` |
| ADを168等分する第151点（端点の順序は本文） | `constructions[606]` | `U151 = PointOnSegment(A,D,151/168)` |
| CDを168等分する第151点（端点の順序は本文） | `constructions[607]` | `V151 = PointOnSegment(C,D,151/168)` |
| ABを168等分する第152点（端点の順序は本文） | `constructions[608]` | `P152 = PointOnSegment(A,B,152/168)` |
| CBを168等分する第152点（端点の順序は本文） | `constructions[609]` | `Q152 = PointOnSegment(C,B,152/168)` |
| ADを168等分する第152点（端点の順序は本文） | `constructions[610]` | `U152 = PointOnSegment(A,D,152/168)` |
| CDを168等分する第152点（端点の順序は本文） | `constructions[611]` | `V152 = PointOnSegment(C,D,152/168)` |
| ABを168等分する第153点（端点の順序は本文） | `constructions[612]` | `P153 = PointOnSegment(A,B,153/168)` |
| CBを168等分する第153点（端点の順序は本文） | `constructions[613]` | `Q153 = PointOnSegment(C,B,153/168)` |
| ADを168等分する第153点（端点の順序は本文） | `constructions[614]` | `U153 = PointOnSegment(A,D,153/168)` |
| CDを168等分する第153点（端点の順序は本文） | `constructions[615]` | `V153 = PointOnSegment(C,D,153/168)` |
| ABを168等分する第154点（端点の順序は本文） | `constructions[616]` | `P154 = PointOnSegment(A,B,154/168)` |
| CBを168等分する第154点（端点の順序は本文） | `constructions[617]` | `Q154 = PointOnSegment(C,B,154/168)` |
| ADを168等分する第154点（端点の順序は本文） | `constructions[618]` | `U154 = PointOnSegment(A,D,154/168)` |
| CDを168等分する第154点（端点の順序は本文） | `constructions[619]` | `V154 = PointOnSegment(C,D,154/168)` |
| ABを168等分する第155点（端点の順序は本文） | `constructions[620]` | `P155 = PointOnSegment(A,B,155/168)` |
| CBを168等分する第155点（端点の順序は本文） | `constructions[621]` | `Q155 = PointOnSegment(C,B,155/168)` |
| ADを168等分する第155点（端点の順序は本文） | `constructions[622]` | `U155 = PointOnSegment(A,D,155/168)` |
| CDを168等分する第155点（端点の順序は本文） | `constructions[623]` | `V155 = PointOnSegment(C,D,155/168)` |
| ABを168等分する第156点（端点の順序は本文） | `constructions[624]` | `P156 = PointOnSegment(A,B,156/168)` |
| CBを168等分する第156点（端点の順序は本文） | `constructions[625]` | `Q156 = PointOnSegment(C,B,156/168)` |
| ADを168等分する第156点（端点の順序は本文） | `constructions[626]` | `U156 = PointOnSegment(A,D,156/168)` |
| CDを168等分する第156点（端点の順序は本文） | `constructions[627]` | `V156 = PointOnSegment(C,D,156/168)` |
| ABを168等分する第157点（端点の順序は本文） | `constructions[628]` | `P157 = PointOnSegment(A,B,157/168)` |
| CBを168等分する第157点（端点の順序は本文） | `constructions[629]` | `Q157 = PointOnSegment(C,B,157/168)` |
| ADを168等分する第157点（端点の順序は本文） | `constructions[630]` | `U157 = PointOnSegment(A,D,157/168)` |
| CDを168等分する第157点（端点の順序は本文） | `constructions[631]` | `V157 = PointOnSegment(C,D,157/168)` |
| ABを168等分する第158点（端点の順序は本文） | `constructions[632]` | `P158 = PointOnSegment(A,B,158/168)` |
| CBを168等分する第158点（端点の順序は本文） | `constructions[633]` | `Q158 = PointOnSegment(C,B,158/168)` |
| ADを168等分する第158点（端点の順序は本文） | `constructions[634]` | `U158 = PointOnSegment(A,D,158/168)` |
| CDを168等分する第158点（端点の順序は本文） | `constructions[635]` | `V158 = PointOnSegment(C,D,158/168)` |
| ABを168等分する第159点（端点の順序は本文） | `constructions[636]` | `P159 = PointOnSegment(A,B,159/168)` |
| CBを168等分する第159点（端点の順序は本文） | `constructions[637]` | `Q159 = PointOnSegment(C,B,159/168)` |
| ADを168等分する第159点（端点の順序は本文） | `constructions[638]` | `U159 = PointOnSegment(A,D,159/168)` |
| CDを168等分する第159点（端点の順序は本文） | `constructions[639]` | `V159 = PointOnSegment(C,D,159/168)` |
| ABを168等分する第160点（端点の順序は本文） | `constructions[640]` | `P160 = PointOnSegment(A,B,160/168)` |
| CBを168等分する第160点（端点の順序は本文） | `constructions[641]` | `Q160 = PointOnSegment(C,B,160/168)` |
| ADを168等分する第160点（端点の順序は本文） | `constructions[642]` | `U160 = PointOnSegment(A,D,160/168)` |
| CDを168等分する第160点（端点の順序は本文） | `constructions[643]` | `V160 = PointOnSegment(C,D,160/168)` |
| ABを168等分する第161点（端点の順序は本文） | `constructions[644]` | `P161 = PointOnSegment(A,B,161/168)` |
| CBを168等分する第161点（端点の順序は本文） | `constructions[645]` | `Q161 = PointOnSegment(C,B,161/168)` |
| ADを168等分する第161点（端点の順序は本文） | `constructions[646]` | `U161 = PointOnSegment(A,D,161/168)` |
| CDを168等分する第161点（端点の順序は本文） | `constructions[647]` | `V161 = PointOnSegment(C,D,161/168)` |
| ABを168等分する第162点（端点の順序は本文） | `constructions[648]` | `P162 = PointOnSegment(A,B,162/168)` |
| CBを168等分する第162点（端点の順序は本文） | `constructions[649]` | `Q162 = PointOnSegment(C,B,162/168)` |
| ADを168等分する第162点（端点の順序は本文） | `constructions[650]` | `U162 = PointOnSegment(A,D,162/168)` |
| CDを168等分する第162点（端点の順序は本文） | `constructions[651]` | `V162 = PointOnSegment(C,D,162/168)` |
| ABを168等分する第163点（端点の順序は本文） | `constructions[652]` | `P163 = PointOnSegment(A,B,163/168)` |
| CBを168等分する第163点（端点の順序は本文） | `constructions[653]` | `Q163 = PointOnSegment(C,B,163/168)` |
| ADを168等分する第163点（端点の順序は本文） | `constructions[654]` | `U163 = PointOnSegment(A,D,163/168)` |
| CDを168等分する第163点（端点の順序は本文） | `constructions[655]` | `V163 = PointOnSegment(C,D,163/168)` |
| ABを168等分する第164点（端点の順序は本文） | `constructions[656]` | `P164 = PointOnSegment(A,B,164/168)` |
| CBを168等分する第164点（端点の順序は本文） | `constructions[657]` | `Q164 = PointOnSegment(C,B,164/168)` |
| ADを168等分する第164点（端点の順序は本文） | `constructions[658]` | `U164 = PointOnSegment(A,D,164/168)` |
| CDを168等分する第164点（端点の順序は本文） | `constructions[659]` | `V164 = PointOnSegment(C,D,164/168)` |
| ABを168等分する第165点（端点の順序は本文） | `constructions[660]` | `P165 = PointOnSegment(A,B,165/168)` |
| CBを168等分する第165点（端点の順序は本文） | `constructions[661]` | `Q165 = PointOnSegment(C,B,165/168)` |
| ADを168等分する第165点（端点の順序は本文） | `constructions[662]` | `U165 = PointOnSegment(A,D,165/168)` |
| CDを168等分する第165点（端点の順序は本文） | `constructions[663]` | `V165 = PointOnSegment(C,D,165/168)` |
| ABを168等分する第166点（端点の順序は本文） | `constructions[664]` | `P166 = PointOnSegment(A,B,166/168)` |
| CBを168等分する第166点（端点の順序は本文） | `constructions[665]` | `Q166 = PointOnSegment(C,B,166/168)` |
| ADを168等分する第166点（端点の順序は本文） | `constructions[666]` | `U166 = PointOnSegment(A,D,166/168)` |
| CDを168等分する第166点（端点の順序は本文） | `constructions[667]` | `V166 = PointOnSegment(C,D,166/168)` |
| ABを168等分する第167点（端点の順序は本文） | `constructions[668]` | `P167 = PointOnSegment(A,B,167/168)` |
| CBを168等分する第167点（端点の順序は本文） | `constructions[669]` | `Q167 = PointOnSegment(C,B,167/168)` |
| ADを168等分する第167点（端点の順序は本文） | `constructions[670]` | `U167 = PointOnSegment(A,D,167/168)` |
| CDを168等分する第167点（端点の順序は本文） | `constructions[671]` | `V167 = PointOnSegment(C,D,167/168)` |
| 335 segments: 167+167+diagonal ACの長さの和 | `target` | `Distance(A,C)+Distance(P1,Q1)+Distance(U1,V1)+Distance(P2,Q2)+Distance(U2,V2)+Distance(P3,Q3)+Distance(U3,V3)+Distance(P4,Q4)+Distance(U4,V4)+Distance(P5,Q5)+Distance(U5,V5)+Distance(P6,Q6)+Distance(U6,V6)+Distance(P7,Q7)+Distance(U7,V7)+Distance(P8,Q8)+Distance(U8,V8)+Distance(P9,Q9)+Distance(U9,V9)+Distance(P10,Q10)+Distance(U10,V10)+Distance(P11,Q11)+Distance(U11,V11)+Distance(P12,Q12)+Distance(U12,V12)+Distance(P13,Q13)+Distance(U13,V13)+Distance(P14,Q14)+Distance(U14,V14)+Distance(P15,Q15)+Distance(U15,V15)+Distance(P16,Q16)+Distance(U16,V16)+Distance(P17,Q17)+Distance(U17,V17)+Distance(P18,Q18)+Distance(U18,V18)+Distance(P19,Q19)+Distance(U19,V19)+Distance(P20,Q20)+Distance(U20,V20)+Distance(P21,Q21)+Distance(U21,V21)+Distance(P22,Q22)+Distance(U22,V22)+Distance(P23,Q23)+Distance(U23,V23)+Distance(P24,Q24)+Distance(U24,V24)+Distance(P25,Q25)+Distance(U25,V25)+Distance(P26,Q26)+Distance(U26,V26)+Distance(P27,Q27)+Distance(U27,V27)+Distance(P28,Q28)+Distance(U28,V28)+Distance(P29,Q29)+Distance(U29,V29)+Distance(P30,Q30)+Distance(U30,V30)+Distance(P31,Q31)+Distance(U31,V31)+Distance(P32,Q32)+Distance(U32,V32)+Distance(P33,Q33)+Distance(U33,V33)+Distance(P34,Q34)+Distance(U34,V34)+Distance(P35,Q35)+Distance(U35,V35)+Distance(P36,Q36)+Distance(U36,V36)+Distance(P37,Q37)+Distance(U37,V37)+Distance(P38,Q38)+Distance(U38,V38)+Distance(P39,Q39)+Distance(U39,V39)+Distance(P40,Q40)+Distance(U40,V40)+Distance(P41,Q41)+Distance(U41,V41)+Distance(P42,Q42)+Distance(U42,V42)+Distance(P43,Q43)+Distance(U43,V43)+Distance(P44,Q44)+Distance(U44,V44)+Distance(P45,Q45)+Distance(U45,V45)+Distance(P46,Q46)+Distance(U46,V46)+Distance(P47,Q47)+Distance(U47,V47)+Distance(P48,Q48)+Distance(U48,V48)+Distance(P49,Q49)+Distance(U49,V49)+Distance(P50,Q50)+Distance(U50,V50)+Distance(P51,Q51)+Distance(U51,V51)+Distance(P52,Q52)+Distance(U52,V52)+Distance(P53,Q53)+Distance(U53,V53)+Distance(P54,Q54)+Distance(U54,V54)+Distance(P55,Q55)+Distance(U55,V55)+Distance(P56,Q56)+Distance(U56,V56)+Distance(P57,Q57)+Distance(U57,V57)+Distance(P58,Q58)+Distance(U58,V58)+Distance(P59,Q59)+Distance(U59,V59)+Distance(P60,Q60)+Distance(U60,V60)+Distance(P61,Q61)+Distance(U61,V61)+Distance(P62,Q62)+Distance(U62,V62)+Distance(P63,Q63)+Distance(U63,V63)+Distance(P64,Q64)+Distance(U64,V64)+Distance(P65,Q65)+Distance(U65,V65)+Distance(P66,Q66)+Distance(U66,V66)+Distance(P67,Q67)+Distance(U67,V67)+Distance(P68,Q68)+Distance(U68,V68)+Distance(P69,Q69)+Distance(U69,V69)+Distance(P70,Q70)+Distance(U70,V70)+Distance(P71,Q71)+Distance(U71,V71)+Distance(P72,Q72)+Distance(U72,V72)+Distance(P73,Q73)+Distance(U73,V73)+Distance(P74,Q74)+Distance(U74,V74)+Distance(P75,Q75)+Distance(U75,V75)+Distance(P76,Q76)+Distance(U76,V76)+Distance(P77,Q77)+Distance(U77,V77)+Distance(P78,Q78)+Distance(U78,V78)+Distance(P79,Q79)+Distance(U79,V79)+Distance(P80,Q80)+Distance(U80,V80)+Distance(P81,Q81)+Distance(U81,V81)+Distance(P82,Q82)+Distance(U82,V82)+Distance(P83,Q83)+Distance(U83,V83)+Distance(P84,Q84)+Distance(U84,V84)+Distance(P85,Q85)+Distance(U85,V85)+Distance(P86,Q86)+Distance(U86,V86)+Distance(P87,Q87)+Distance(U87,V87)+Distance(P88,Q88)+Distance(U88,V88)+Distance(P89,Q89)+Distance(U89,V89)+Distance(P90,Q90)+Distance(U90,V90)+Distance(P91,Q91)+Distance(U91,V91)+Distance(P92,Q92)+Distance(U92,V92)+Distance(P93,Q93)+Distance(U93,V93)+Distance(P94,Q94)+Distance(U94,V94)+Distance(P95,Q95)+Distance(U95,V95)+Distance(P96,Q96)+Distance(U96,V96)+Distance(P97,Q97)+Distance(U97,V97)+Distance(P98,Q98)+Distance(U98,V98)+Distance(P99,Q99)+Distance(U99,V99)+Distance(P100,Q100)+Distance(U100,V100)+Distance(P101,Q101)+Distance(U101,V101)+Distance(P102,Q102)+Distance(U102,V102)+Distance(P103,Q103)+Distance(U103,V103)+Distance(P104,Q104)+Distance(U104,V104)+Distance(P105,Q105)+Distance(U105,V105)+Distance(P106,Q106)+Distance(U106,V106)+Distance(P107,Q107)+Distance(U107,V107)+Distance(P108,Q108)+Distance(U108,V108)+Distance(P109,Q109)+Distance(U109,V109)+Distance(P110,Q110)+Distance(U110,V110)+Distance(P111,Q111)+Distance(U111,V111)+Distance(P112,Q112)+Distance(U112,V112)+Distance(P113,Q113)+Distance(U113,V113)+Distance(P114,Q114)+Distance(U114,V114)+Distance(P115,Q115)+Distance(U115,V115)+Distance(P116,Q116)+Distance(U116,V116)+Distance(P117,Q117)+Distance(U117,V117)+Distance(P118,Q118)+Distance(U118,V118)+Distance(P119,Q119)+Distance(U119,V119)+Distance(P120,Q120)+Distance(U120,V120)+Distance(P121,Q121)+Distance(U121,V121)+Distance(P122,Q122)+Distance(U122,V122)+Distance(P123,Q123)+Distance(U123,V123)+Distance(P124,Q124)+Distance(U124,V124)+Distance(P125,Q125)+Distance(U125,V125)+Distance(P126,Q126)+Distance(U126,V126)+Distance(P127,Q127)+Distance(U127,V127)+Distance(P128,Q128)+Distance(U128,V128)+Distance(P129,Q129)+Distance(U129,V129)+Distance(P130,Q130)+Distance(U130,V130)+Distance(P131,Q131)+Distance(U131,V131)+Distance(P132,Q132)+Distance(U132,V132)+Distance(P133,Q133)+Distance(U133,V133)+Distance(P134,Q134)+Distance(U134,V134)+Distance(P135,Q135)+Distance(U135,V135)+Distance(P136,Q136)+Distance(U136,V136)+Distance(P137,Q137)+Distance(U137,V137)+Distance(P138,Q138)+Distance(U138,V138)+Distance(P139,Q139)+Distance(U139,V139)+Distance(P140,Q140)+Distance(U140,V140)+Distance(P141,Q141)+Distance(U141,V141)+Distance(P142,Q142)+Distance(U142,V142)+Distance(P143,Q143)+Distance(U143,V143)+Distance(P144,Q144)+Distance(U144,V144)+Distance(P145,Q145)+Distance(U145,V145)+Distance(P146,Q146)+Distance(U146,V146)+Distance(P147,Q147)+Distance(U147,V147)+Distance(P148,Q148)+Distance(U148,V148)+Distance(P149,Q149)+Distance(U149,V149)+Distance(P150,Q150)+Distance(U150,V150)+Distance(P151,Q151)+Distance(U151,V151)+Distance(P152,Q152)+Distance(U152,V152)+Distance(P153,Q153)+Distance(U153,V153)+Distance(P154,Q154)+Distance(U154,V154)+Distance(P155,Q155)+Distance(U155,V155)+Distance(P156,Q156)+Distance(U156,V156)+Distance(P157,Q157)+Distance(U157,V157)+Distance(P158,Q158)+Distance(U158,V158)+Distance(P159,Q159)+Distance(U159,V159)+Distance(P160,Q160)+Distance(U160,V160)+Distance(P161,Q161)+Distance(U161,V161)+Distance(P162,Q162)+Distance(U162,V162)+Distance(P163,Q163)+Distance(U163,V163)+Distance(P164,Q164)+Distance(U164,V164)+Distance(P165,Q165)+Distance(U165,V165)+Distance(P166,Q166)+Distance(U166,V166)+Distance(P167,Q167)+Distance(U167,V167)` |

## 残る制約

有限167回の定義的作図を全て展開した。和の公式への置換・長さの事前評価はしない。

分枝・内部・非退化は表のguardで明示。根番号で解を選ばない。AST合格は幾何同値性・実行可能性・目標の一意性を保証しない。


---

# AIME-1991-12 原文→入力対応カード

状態: **二次資料・公式冊子未照合・数値検証未実施**。

- 資料: `jssa/difficulty/unseen-1983/source-evidence/aime-1983-1999/aime-1983-1999.jsonl` / line 112
- 原文SHA-256: `8d704a699c8f5d378ea62f2178e09eeca0c6e052e532b00bf889e4d5561045c3`
- 入力SHA-256: `22894bbff4eb2193bffebea194058d78fc8d555e3ff71a5567fb5d5ee59ece02`
- 座標固定・同値性: 長方形を第一象限に合同固定。尺度は保持。
- 答えは `official_answers.jsonl` へ入力固定後に分離。選定・入力には未使用。

## 手元の原文（二次資料のQuestionをそのまま保存）

Rhombus $PQRS^{}_{}$ is inscribed in rectangle $ABCD^{}_{}$ so that vertices $P^{}_{}$ , $Q^{}_{}$ , $R^{}_{}$ , and $S^{}_{}$ are interior points on sides $\overline{AB}$ , $\overline{BC}$ , $\overline{CD}$ , and $\overline{DA}$ , respectively. It is given that $PB^{}_{}=15$ , $BQ^{}_{}=20$ , $PR^{}_{}=30$ , and $QS^{}_{}=40$ . Let $m/n^{}_{}$ , in lowest terms, denote the perimeter of $ABCD^{}_{}$ . Find $m+n^{}_{}$ .

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| rectangle | `constructions[0]` | `A = Point(0, 0)` |
| rectangle | `constructions[1]` | `B = Point(w, 0)` |
| rectangle | `constructions[2]` | `C = Point(w, h)` |
| rectangle | `constructions[3]` | `D = Point(0, h)` |
| P on AB, PB=15 | `constructions[4]` | `P = Point(w-15, 0)` |
| Q on BC, BQ=20 | `constructions[5]` | `Q = Point(w, 20)` |
| R on CD | `constructions[6]` | `R = Point(rx, h)` |
| S on DA | `constructions[7]` | `S = Point(0, sy)` |
| P interior of AB | `conditions[0]` | `w > 15` |
| Q interior of BC | `conditions[1]` | `h > 20` |
| R interior CD | `conditions[2]` | `rx > 0` |
| R interior CD | `conditions[3]` | `w > rx` |
| S interior DA | `conditions[4]` | `sy > 0` |
| S interior DA | `conditions[5]` | `h > sy` |
| rhombus equal sides | `conditions[6]` | `Distance(P,Q) = Distance(Q,R)` |
| rhombus equal sides | `conditions[7]` | `Distance(Q,R) = Distance(R,S)` |
| rhombus equal sides | `conditions[8]` | `Distance(R,S) = Distance(S,P)` |
| PR=30 | `conditions[9]` | `Distance(P,R) = 30` |
| QS=40 | `conditions[10]` | `Distance(Q,S) = 40` |
| rectangle perimeter in lowest terms | `conditions[11]` | `2*(w+h) = m/n` |
| 既約分数の整数分子分母・Bezout整数証人 | `conditions[12]` | `IsInteger(m) = 0` |
| 既約分数の整数分子分母・Bezout整数証人 | `conditions[13]` | `IsInteger(n) = 0` |
| 既約分数の整数分子分母・Bezout整数証人 | `conditions[14]` | `IsInteger(u) = 0` |
| 既約分数の整数分子分母・Bezout整数証人 | `conditions[15]` | `IsInteger(v) = 0` |
| 分母は正 | `conditions[16]` | `n > 0` |
| 互いに素の定義的同値条件（Bezout） | `conditions[17]` | `u*m+v*n = 1` |
| 分子は正 | `conditions[18]` | `m > 0` |
| sum numerator and denominator | `target` | `m+n` |

## 残る制約

公式冊子照合と独立の意味監査は未了。

分枝・内部・非退化は表のguardで明示。根番号で解を選ばない。AST合格は幾何同値性・実行可能性・目標の一意性を保証しない。


---

# AIME-1991-14 原文→入力対応カード

状態: **二次資料・公式冊子未照合・数値検証未実施**。

- 資料: `jssa/difficulty/unseen-1983/source-evidence/aime-1983-1999/aime-1983-1999.jsonl` / line 114
- 原文SHA-256: `f53c23181fd19027c73d75827cd05ad79b2a2b3fda9edfa39dec78eef601d96d`
- 入力SHA-256: `1eedb2130ca5e84f291b06ccf4b409bea117441e79b51776821ea96426968417`
- 座標固定・同値性: A原点、ABを正x軸、頂点を反時計回り。AB=31を保持。
- 答えは `official_answers.jsonl` へ入力固定後に分離。選定・入力には未使用。

## 手元の原文（二次資料のQuestionをそのまま保存）

A hexagon is inscribed in a circle. Five of the sides have length 81 and the sixth, denoted by $\overline{AB}$ , has length 31. Find the sum of the lengths of the three diagonals that can be drawn from $A_{}^{}$ .

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| hexagon AB C D E F | `constructions[0]` | `A = Point(0, 0)` |
| sixth side AB=31 | `constructions[1]` | `B = Point(31, 0)` |
| remaining vertices in cyclic order | `constructions[2]` | `C = Point(cx, cy)` |
| remaining vertices in cyclic order | `constructions[3]` | `D = Point(dx, dy)` |
| remaining vertices in cyclic order | `constructions[4]` | `E = Point(ex, ey)` |
| remaining vertices in cyclic order | `constructions[5]` | `F = Point(fx, fy)` |
| circumcircle of hexagon | `constructions[6]` | `omega = Circumcircle(A,B,C)` |
| 頂点順の狭義凸性 / 各辺の他の頂点はすべて左側 | `conditions[0]` | `((B.x-A.x)*(C.y-A.y)-(B.y-A.y)*(C.x-A.x)) > 0` |
| 頂点順の狭義凸性 / 各辺の他の頂点はすべて左側 | `conditions[1]` | `((B.x-A.x)*(D.y-A.y)-(B.y-A.y)*(D.x-A.x)) > 0` |
| 頂点順の狭義凸性 / 各辺の他の頂点はすべて左側 | `conditions[2]` | `((B.x-A.x)*(E.y-A.y)-(B.y-A.y)*(E.x-A.x)) > 0` |
| 頂点順の狭義凸性 / 各辺の他の頂点はすべて左側 | `conditions[3]` | `((B.x-A.x)*(F.y-A.y)-(B.y-A.y)*(F.x-A.x)) > 0` |
| 頂点順の狭義凸性 / 各辺の他の頂点はすべて左側 | `conditions[4]` | `((C.x-B.x)*(A.y-B.y)-(C.y-B.y)*(A.x-B.x)) > 0` |
| 頂点順の狭義凸性 / 各辺の他の頂点はすべて左側 | `conditions[5]` | `((C.x-B.x)*(D.y-B.y)-(C.y-B.y)*(D.x-B.x)) > 0` |
| 頂点順の狭義凸性 / 各辺の他の頂点はすべて左側 | `conditions[6]` | `((C.x-B.x)*(E.y-B.y)-(C.y-B.y)*(E.x-B.x)) > 0` |
| 頂点順の狭義凸性 / 各辺の他の頂点はすべて左側 | `conditions[7]` | `((C.x-B.x)*(F.y-B.y)-(C.y-B.y)*(F.x-B.x)) > 0` |
| 頂点順の狭義凸性 / 各辺の他の頂点はすべて左側 | `conditions[8]` | `((D.x-C.x)*(A.y-C.y)-(D.y-C.y)*(A.x-C.x)) > 0` |
| 頂点順の狭義凸性 / 各辺の他の頂点はすべて左側 | `conditions[9]` | `((D.x-C.x)*(B.y-C.y)-(D.y-C.y)*(B.x-C.x)) > 0` |
| 頂点順の狭義凸性 / 各辺の他の頂点はすべて左側 | `conditions[10]` | `((D.x-C.x)*(E.y-C.y)-(D.y-C.y)*(E.x-C.x)) > 0` |
| 頂点順の狭義凸性 / 各辺の他の頂点はすべて左側 | `conditions[11]` | `((D.x-C.x)*(F.y-C.y)-(D.y-C.y)*(F.x-C.x)) > 0` |
| 頂点順の狭義凸性 / 各辺の他の頂点はすべて左側 | `conditions[12]` | `((E.x-D.x)*(A.y-D.y)-(E.y-D.y)*(A.x-D.x)) > 0` |
| 頂点順の狭義凸性 / 各辺の他の頂点はすべて左側 | `conditions[13]` | `((E.x-D.x)*(B.y-D.y)-(E.y-D.y)*(B.x-D.x)) > 0` |
| 頂点順の狭義凸性 / 各辺の他の頂点はすべて左側 | `conditions[14]` | `((E.x-D.x)*(C.y-D.y)-(E.y-D.y)*(C.x-D.x)) > 0` |
| 頂点順の狭義凸性 / 各辺の他の頂点はすべて左側 | `conditions[15]` | `((E.x-D.x)*(F.y-D.y)-(E.y-D.y)*(F.x-D.x)) > 0` |
| 頂点順の狭義凸性 / 各辺の他の頂点はすべて左側 | `conditions[16]` | `((F.x-E.x)*(A.y-E.y)-(F.y-E.y)*(A.x-E.x)) > 0` |
| 頂点順の狭義凸性 / 各辺の他の頂点はすべて左側 | `conditions[17]` | `((F.x-E.x)*(B.y-E.y)-(F.y-E.y)*(B.x-E.x)) > 0` |
| 頂点順の狭義凸性 / 各辺の他の頂点はすべて左側 | `conditions[18]` | `((F.x-E.x)*(C.y-E.y)-(F.y-E.y)*(C.x-E.x)) > 0` |
| 頂点順の狭義凸性 / 各辺の他の頂点はすべて左側 | `conditions[19]` | `((F.x-E.x)*(D.y-E.y)-(F.y-E.y)*(D.x-E.x)) > 0` |
| 頂点順の狭義凸性 / 各辺の他の頂点はすべて左側 | `conditions[20]` | `((A.x-F.x)*(B.y-F.y)-(A.y-F.y)*(B.x-F.x)) > 0` |
| 頂点順の狭義凸性 / 各辺の他の頂点はすべて左側 | `conditions[21]` | `((A.x-F.x)*(C.y-F.y)-(A.y-F.y)*(C.x-F.x)) > 0` |
| 頂点順の狭義凸性 / 各辺の他の頂点はすべて左側 | `conditions[22]` | `((A.x-F.x)*(D.y-F.y)-(A.y-F.y)*(D.x-F.x)) > 0` |
| 頂点順の狭義凸性 / 各辺の他の頂点はすべて左側 | `conditions[23]` | `((A.x-F.x)*(E.y-F.y)-(A.y-F.y)*(E.x-F.x)) > 0` |
| five sides have length81 | `conditions[24]` | `Distance(B,C) = 81` |
| five sides have length81 | `conditions[25]` | `Distance(C,D) = 81` |
| five sides have length81 | `conditions[26]` | `Distance(D,E) = 81` |
| five sides have length81 | `conditions[27]` | `Distance(E,F) = 81` |
| five sides have length81 | `conditions[28]` | `Distance(F,A) = 81` |
| hexagon inscribed in one circle | `conditions[29]` | `OnCircle(D,omega) = 0` |
| hexagon inscribed in one circle | `conditions[30]` | `OnCircle(E,omega) = 0` |
| hexagon inscribed in one circle | `conditions[31]` | `OnCircle(F,omega) = 0` |
| three diagonals drawn from A | `target` | `Distance(A,C)+Distance(A,D)+Distance(A,E)` |

## 残る制約

公式冊子照合と独立の意味監査は未了。

分枝・内部・非退化は表のguardで明示。根番号で解を選ばない。AST合格は幾何同値性・実行可能性・目標の一意性を保証しない。


---

# AIME-1992-09 原文→入力対応カード

状態: **二次資料・公式冊子未照合・数値検証未実施**。

- 資料: `jssa/difficulty/unseen-1983/source-evidence/aime-1983-1999/aime-1983-1999.jsonl` / line 123
- 原文SHA-256: `69956a2c16fd348bda27b9b7a647d1f8a7ab2924fd6642616ab4af3ef1972f61`
- 入力SHA-256: `ee2cc903a768efe7bbc2964b6dc26374d0b48a8b5760f879d4544f5147e59a1e`
- 座標固定・同値性: ABを水平、台形を上側。4辺長は保持。
- 答えは `official_answers.jsonl` へ入力固定後に分離。選定・入力には未使用。

## 手元の原文（二次資料のQuestionをそのまま保存）

Trapezoid $ABCD^{}_{}$ has sides $AB=92^{}_{}$ , $BC=50^{}_{}$ , $CD=19^{}_{}$ , and $AD=70^{}_{}$ , with $AB^{}_{}$ parallel to $CD^{}_{}$ . A circle with center $P^{}_{}$ on $AB^{}_{}$ is drawn tangent to $BC^{}_{}$ and $AD^{}_{}$ . Given that $AP^{}_{}=\frac mn$ , where $m^{}_{}$ and $n^{}_{}$ are relatively prime positive integers, find $m+n^{}_{}$ .

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| AB=92 | `constructions[0]` | `A = Point(0, 0)` |
| AB=92 | `constructions[1]` | `B = Point(92, 0)` |
| parallel top side | `constructions[2]` | `D = Point(dx, h)` |
| CD=19 and AB parallel CD | `constructions[3]` | `C = Point(dx+19, h)` |
| circle center on AB | `constructions[4]` | `P = Point(p, 0)` |
| unknown radius | `constructions[5]` | `omega = Circle(P,r)` |
| tangency foot on BC | `constructions[6]` | `E = FootOfPerpendicular(P,Line(B,C))` |
| tangency foot on AD | `constructions[7]` | `F = FootOfPerpendicular(P,Line(A,D))` |
| positive trapezoid height | `conditions[0]` | `h > 0` |
| BC=50 | `conditions[1]` | `Distance(B,C) = 50` |
| AD=70 | `conditions[2]` | `Distance(A,D) = 70` |
| P on AB | `conditions[3]` | `p >= 0` |
| P on AB | `conditions[4]` | `p <= 92` |
| positive radius | `conditions[5]` | `r > 0` |
| circle tangent BC | `conditions[6]` | `Distance(P,E) = r` |
| circle tangent AD | `conditions[7]` | `Distance(P,F) = r` |
| contact on segment BC | `conditions[8]` | `Distance(B,E)+Distance(E,C) = Distance(B,C)` |
| contact on segment AD | `conditions[9]` | `Distance(A,F)+Distance(F,D) = Distance(A,D)` |
| AP in lowest terms | `conditions[10]` | `Distance(A,P) = m/n` |
| 既約分数の整数分子分母・Bezout整数証人 | `conditions[11]` | `IsInteger(m) = 0` |
| 既約分数の整数分子分母・Bezout整数証人 | `conditions[12]` | `IsInteger(n) = 0` |
| 既約分数の整数分子分母・Bezout整数証人 | `conditions[13]` | `IsInteger(u) = 0` |
| 既約分数の整数分子分母・Bezout整数証人 | `conditions[14]` | `IsInteger(v) = 0` |
| 分母は正 | `conditions[15]` | `n > 0` |
| 互いに素の定義的同値条件（Bezout） | `conditions[16]` | `u*m+v*n = 1` |
| 分子は正 | `conditions[17]` | `m > 0` |
| m+n | `target` | `m+n` |

## 残る制約

公式冊子照合と独立の意味監査は未了。

分枝・内部・非退化は表のguardで明示。根番号で解を選ばない。AST合格は幾何同値性・実行可能性・目標の一意性を保証しない。


---

# AIME-1992-14 原文→入力対応カード

状態: **二次資料・公式冊子未照合・数値検証未実施**。

- 資料: `jssa/difficulty/unseen-1983/source-evidence/aime-1983-1999/aime-1983-1999.jsonl` / line 128
- 原文SHA-256: `6fb91eb941f658d014b028add079ad3ff15aaf66d68d2acf35554312f2f9e979`
- 入力SHA-256: `0f56c79c096ce1439294fb1e2043308a689ffd1bc6fab965323e9cd0f1b5e41c`
- 座標固定・同値性: 相似不変の比だけなのでAB=1。Cの形状自由度は残す。
- 答えは `official_answers.jsonl` へ入力固定後に分離。選定・入力には未使用。

## 手元の原文（二次資料のQuestionをそのまま保存）

In triangle $ABC^{}_{}$ , $A'$ , $B'$ , and $C'$ are on the sides $BC$ , $AC^{}_{}$ , and $AB^{}_{}$ , respectively. Given that $AA'$ , $BB'$ , and $CC'$ are concurrent at the point $O^{}_{}$ , and that $\frac{AO^{}_{}}{OA'}+\frac{BO}{OB'}+\frac{CO}{OC'}=92$ , find $\frac{AO}{OA'}\cdot \frac{BO}{OB'}\cdot \frac{CO}{OC'}$ .

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| triangle | `constructions[0]` | `A = Point(0, 0)` |
| similarity scale AB=1 | `constructions[1]` | `B = Point(1, 0)` |
| unknown C | `constructions[2]` | `C = Point(cx, cy)` |
| A' on BC | `constructions[3]` | `Ap = PointOnSegment(B,C,t)` |
| B' on AC | `constructions[4]` | `Bp = PointOnSegment(A,C,s)` |
| C' on AB | `constructions[5]` | `Cp = PointOnSegment(A,B,q)` |
| concurrent point | `constructions[6]` | `O = Point(ox, oy)` |
| nondegenerate triangle / upper orientation | `conditions[0]` | `cy > 0` |
| A' strictly on BC / endpoint would make cevian ratios undefined | `conditions[1]` | `t > 0` |
| A' strictly on BC / endpoint would make cevian ratios undefined | `conditions[2]` | `1 > t` |
| B' strictly on AC | `conditions[3]` | `s > 0` |
| B' strictly on AC | `conditions[4]` | `1 > s` |
| C' strictly on AB | `conditions[5]` | `q > 0` |
| C' strictly on AB | `conditions[6]` | `1 > q` |
| O strictly inside ABC / 各辺の内側 | `conditions[7]` | `((B.x-A.x)*(O.y-A.y)-(B.y-A.y)*(O.x-A.x)) > 0` |
| O strictly inside ABC / 各辺の内側 | `conditions[8]` | `((C.x-B.x)*(O.y-B.y)-(C.y-B.y)*(O.x-B.x)) > 0` |
| O strictly inside ABC / 各辺の内側 | `conditions[9]` | `((A.x-C.x)*(O.y-C.y)-(A.y-C.y)*(O.x-C.x)) > 0` |
| three cevians concurrent | `conditions[10]` | `OnLine(O,Line(A,Ap)) = 0` |
| three cevians concurrent | `conditions[11]` | `OnLine(O,Line(B,Bp)) = 0` |
| three cevians concurrent | `conditions[12]` | `OnLine(O,Line(C,Cp)) = 0` |
| ratio denominator nonzero | `conditions[13]` | `Distance(O,Ap) > 0` |
| ratio denominator nonzero | `conditions[14]` | `Distance(O,Bp) > 0` |
| ratio denominator nonzero | `conditions[15]` | `Distance(O,Cp) > 0` |
| given sum of three ratios | `conditions[16]` | `Distance(A,O)/Distance(O,Ap)+Distance(B,O)/Distance(O,Bp)+Distance(C,O)/Distance(O,Cp) = 92` |
| product of three ratios | `target` | `(Distance(A,O)/Distance(O,Ap))*(Distance(B,O)/Distance(O,Bp))*(Distance(C,O)/Distance(O,Cp))` |

## 残る制約

公式冊子照合と独立の意味監査は未了。

分枝・内部・非退化は表のguardで明示。根番号で解を選ばない。AST合格は幾何同値性・実行可能性・目標の一意性を保証しない。


---

# AIME-1993-02 原文→入力対応カード

状態: **二次資料・公式冊子未照合・数値検証未実施**。

- 資料: `jssa/difficulty/unseen-1983/source-evidence/aime-1983-1999/aime-1983-1999.jsonl` / line 131
- 原文SHA-256: `05996f8cfe4905f5684a93ec6e20ceb73d05a6750ae0370aead563bc8e12d0ed`
- 入力SHA-256: `e10774b7008ae6ec98998e321a0904755771e66cd2626084805b3a0f3615156a`
- 座標固定・同値性: 出発点を原点、東x正、北y正。40日の移動定義をそのまま展開。
- 答えは `official_answers.jsonl` へ入力固定後に分離。選定・入力には未使用。

## 手元の原文（二次資料のQuestionをそのまま保存）

During a recent campaign for office, a candidate made a tour of a country which we assume lies in a plane. On the first day of the tour he went east, on the second day he went north, on the third day west, on the fourth day south, on the fifth day east, etc. If the candidate went $\frac{n^{2}}{2}$ miles on the $n^{\mbox{th}}_{}$ day of this tour, how many miles was he from his starting point at the end of the $40^{\mbox{th}}_{}$ day?

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| starting point | `constructions[0]` | `P0 = Point(0, 0)` |
| day 1: east,north,west,south cyclic; length day²/2 | `constructions[1]` | `P1 = Point(P0.x+(1**2/2), P0.y+(0))` |
| day 2: east,north,west,south cyclic; length day²/2 | `constructions[2]` | `P2 = Point(P1.x+(0), P1.y+(2**2/2))` |
| day 3: east,north,west,south cyclic; length day²/2 | `constructions[3]` | `P3 = Point(P2.x+(-3**2/2), P2.y+(0))` |
| day 4: east,north,west,south cyclic; length day²/2 | `constructions[4]` | `P4 = Point(P3.x+(0), P3.y+(-4**2/2))` |
| day 5: east,north,west,south cyclic; length day²/2 | `constructions[5]` | `P5 = Point(P4.x+(5**2/2), P4.y+(0))` |
| day 6: east,north,west,south cyclic; length day²/2 | `constructions[6]` | `P6 = Point(P5.x+(0), P5.y+(6**2/2))` |
| day 7: east,north,west,south cyclic; length day²/2 | `constructions[7]` | `P7 = Point(P6.x+(-7**2/2), P6.y+(0))` |
| day 8: east,north,west,south cyclic; length day²/2 | `constructions[8]` | `P8 = Point(P7.x+(0), P7.y+(-8**2/2))` |
| day 9: east,north,west,south cyclic; length day²/2 | `constructions[9]` | `P9 = Point(P8.x+(9**2/2), P8.y+(0))` |
| day 10: east,north,west,south cyclic; length day²/2 | `constructions[10]` | `P10 = Point(P9.x+(0), P9.y+(10**2/2))` |
| day 11: east,north,west,south cyclic; length day²/2 | `constructions[11]` | `P11 = Point(P10.x+(-11**2/2), P10.y+(0))` |
| day 12: east,north,west,south cyclic; length day²/2 | `constructions[12]` | `P12 = Point(P11.x+(0), P11.y+(-12**2/2))` |
| day 13: east,north,west,south cyclic; length day²/2 | `constructions[13]` | `P13 = Point(P12.x+(13**2/2), P12.y+(0))` |
| day 14: east,north,west,south cyclic; length day²/2 | `constructions[14]` | `P14 = Point(P13.x+(0), P13.y+(14**2/2))` |
| day 15: east,north,west,south cyclic; length day²/2 | `constructions[15]` | `P15 = Point(P14.x+(-15**2/2), P14.y+(0))` |
| day 16: east,north,west,south cyclic; length day²/2 | `constructions[16]` | `P16 = Point(P15.x+(0), P15.y+(-16**2/2))` |
| day 17: east,north,west,south cyclic; length day²/2 | `constructions[17]` | `P17 = Point(P16.x+(17**2/2), P16.y+(0))` |
| day 18: east,north,west,south cyclic; length day²/2 | `constructions[18]` | `P18 = Point(P17.x+(0), P17.y+(18**2/2))` |
| day 19: east,north,west,south cyclic; length day²/2 | `constructions[19]` | `P19 = Point(P18.x+(-19**2/2), P18.y+(0))` |
| day 20: east,north,west,south cyclic; length day²/2 | `constructions[20]` | `P20 = Point(P19.x+(0), P19.y+(-20**2/2))` |
| day 21: east,north,west,south cyclic; length day²/2 | `constructions[21]` | `P21 = Point(P20.x+(21**2/2), P20.y+(0))` |
| day 22: east,north,west,south cyclic; length day²/2 | `constructions[22]` | `P22 = Point(P21.x+(0), P21.y+(22**2/2))` |
| day 23: east,north,west,south cyclic; length day²/2 | `constructions[23]` | `P23 = Point(P22.x+(-23**2/2), P22.y+(0))` |
| day 24: east,north,west,south cyclic; length day²/2 | `constructions[24]` | `P24 = Point(P23.x+(0), P23.y+(-24**2/2))` |
| day 25: east,north,west,south cyclic; length day²/2 | `constructions[25]` | `P25 = Point(P24.x+(25**2/2), P24.y+(0))` |
| day 26: east,north,west,south cyclic; length day²/2 | `constructions[26]` | `P26 = Point(P25.x+(0), P25.y+(26**2/2))` |
| day 27: east,north,west,south cyclic; length day²/2 | `constructions[27]` | `P27 = Point(P26.x+(-27**2/2), P26.y+(0))` |
| day 28: east,north,west,south cyclic; length day²/2 | `constructions[28]` | `P28 = Point(P27.x+(0), P27.y+(-28**2/2))` |
| day 29: east,north,west,south cyclic; length day²/2 | `constructions[29]` | `P29 = Point(P28.x+(29**2/2), P28.y+(0))` |
| day 30: east,north,west,south cyclic; length day²/2 | `constructions[30]` | `P30 = Point(P29.x+(0), P29.y+(30**2/2))` |
| day 31: east,north,west,south cyclic; length day²/2 | `constructions[31]` | `P31 = Point(P30.x+(-31**2/2), P30.y+(0))` |
| day 32: east,north,west,south cyclic; length day²/2 | `constructions[32]` | `P32 = Point(P31.x+(0), P31.y+(-32**2/2))` |
| day 33: east,north,west,south cyclic; length day²/2 | `constructions[33]` | `P33 = Point(P32.x+(33**2/2), P32.y+(0))` |
| day 34: east,north,west,south cyclic; length day²/2 | `constructions[34]` | `P34 = Point(P33.x+(0), P33.y+(34**2/2))` |
| day 35: east,north,west,south cyclic; length day²/2 | `constructions[35]` | `P35 = Point(P34.x+(-35**2/2), P34.y+(0))` |
| day 36: east,north,west,south cyclic; length day²/2 | `constructions[36]` | `P36 = Point(P35.x+(0), P35.y+(-36**2/2))` |
| day 37: east,north,west,south cyclic; length day²/2 | `constructions[37]` | `P37 = Point(P36.x+(37**2/2), P36.y+(0))` |
| day 38: east,north,west,south cyclic; length day²/2 | `constructions[38]` | `P38 = Point(P37.x+(0), P37.y+(38**2/2))` |
| day 39: east,north,west,south cyclic; length day²/2 | `constructions[39]` | `P39 = Point(P38.x+(-39**2/2), P38.y+(0))` |
| day 40: east,north,west,south cyclic; length day²/2 | `constructions[40]` | `P40 = Point(P39.x+(0), P39.y+(-40**2/2))` |
| distance after day40 | `target` | `Distance(P0,P40)` |

## 残る制約

公式冊子照合と独立の意味監査は未了。

分枝・内部・非退化は表のguardで明示。根番号で解を選ばない。AST合格は幾何同値性・実行可能性・目標の一意性を保証しない。


---

# AIME-1993-12 原文→入力対応カード

状態: **二次資料・公式冊子未照合・数値検証未実施**。

- 資料: `jssa/difficulty/unseen-1983/source-evidence/aime-1983-1999/aime-1983-1999.jsonl` / line 140
- 原文SHA-256: `a9047778fb67b5f496e59880009a5b91deb6a1fb4376cca5cd2ee3e239096765`
- 入力SHA-256: `41851d9dd407a3d246dcb705db1ba49a0e28ed3855f208b3724086231eb0d72d`
- 座標固定・同値性: 原文座標を保持。有限6回の実現したラベル列も変数とdisjunctionで残す。
- 答えは `official_answers.jsonl` へ入力固定後に分離。選定・入力には未使用。

## 手元の原文（二次資料のQuestionをそのまま保存）

The vertices of $\triangle ABC$ are $A = (0,0)\,$ , $B = (0,420)\,$ , and $C = (560,0)\,$ .  The six faces of a die are labeled with two $A\,$ 's, two $B\,$ 's, and two $C\,$ 's.  Point $P_1 = (k,m)\,$ is chosen in the interior of $\triangle ABC$ , and points $P_2\,$ , $P_3\,$ , $P_4, \dots$ are generated by rolling the die repeatedly and applying the rule: If the die shows label $L\,$ , where $L \in \{A, B, C\}$ , and $P_n\,$ is the most recently obtained point, then $P_{n + 1}^{}$ is the midpoint of $\overline{P_n L}$ .  Given that $P_7 = (14,92)\,$ , what is $k + m\,$ ?

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| A | `constructions[0]` | `A = Point(0, 0)` |
| B | `constructions[1]` | `B = Point(0, 420)` |
| C | `constructions[2]` | `C = Point(560, 0)` |
| initial interior point | `constructions[3]` | `P1 = Point(k, m)` |
| die label A=0,B=1,C=2 | `constructions[4]` | `L1 = Point(560 if z1 == 2 else 0, 420 if z1 == 1 else 0)` |
| midpoint rule at step1 | `constructions[5]` | `P2 = Midpoint(P1,L1)` |
| die label A=0,B=1,C=2 | `constructions[6]` | `L2 = Point(560 if z2 == 2 else 0, 420 if z2 == 1 else 0)` |
| midpoint rule at step2 | `constructions[7]` | `P3 = Midpoint(P2,L2)` |
| die label A=0,B=1,C=2 | `constructions[8]` | `L3 = Point(560 if z3 == 2 else 0, 420 if z3 == 1 else 0)` |
| midpoint rule at step3 | `constructions[9]` | `P4 = Midpoint(P3,L3)` |
| die label A=0,B=1,C=2 | `constructions[10]` | `L4 = Point(560 if z4 == 2 else 0, 420 if z4 == 1 else 0)` |
| midpoint rule at step4 | `constructions[11]` | `P5 = Midpoint(P4,L4)` |
| die label A=0,B=1,C=2 | `constructions[12]` | `L5 = Point(560 if z5 == 2 else 0, 420 if z5 == 1 else 0)` |
| midpoint rule at step5 | `constructions[13]` | `P6 = Midpoint(P5,L5)` |
| die label A=0,B=1,C=2 | `constructions[14]` | `L6 = Point(560 if z6 == 2 else 0, 420 if z6 == 1 else 0)` |
| midpoint rule at step6 | `constructions[15]` | `P7 = Midpoint(P6,L6)` |
| P1 inside triangle | `conditions[0]` | `k > 0` |
| P1 inside triangle | `conditions[1]` | `m > 0` |
| inside hypotenuse | `conditions[2]` | `1 > k/560+m/420` |
| one of three die labels; no probability target | `conditions[3]` | `(z1 == 0) or (z1 == 1) or (z1 == 2)` |
| one of three die labels; no probability target | `conditions[4]` | `(z2 == 0) or (z2 == 1) or (z2 == 2)` |
| one of three die labels; no probability target | `conditions[5]` | `(z3 == 0) or (z3 == 1) or (z3 == 2)` |
| one of three die labels; no probability target | `conditions[6]` | `(z4 == 0) or (z4 == 1) or (z4 == 2)` |
| one of three die labels; no probability target | `conditions[7]` | `(z5 == 0) or (z5 == 1) or (z5 == 2)` |
| one of three die labels; no probability target | `conditions[8]` | `(z6 == 0) or (z6 == 1) or (z6 == 2)` |
| given terminal x | `conditions[9]` | `P7.x = 14` |
| given terminal y | `conditions[10]` | `P7.y = 92` |
| initial k+m | `target` | `k+m` |

## 残る制約

確率・期待値を求める問題ではない。終点条件を満たす有限配置をそのまま表現し、ラベル列の列挙や逆算をしない。

分枝・内部・非退化は表のguardで明示。根番号で解を選ばない。AST合格は幾何同値性・実行可能性・目標の一意性を保証しない。


---

# AIME-1993-13 原文→入力対応カード

状態: **二次資料・公式冊子未照合・数値検証未実施**。

- 資料: `jssa/difficulty/unseen-1983/source-evidence/aime-1983-1999/aime-1983-1999.jsonl` / line 141
- 原文SHA-256: `6d7da601b0421bfdcbd56332d841888ada46e4aafcc4f2f86b7c384bc1ec6d2b`
- 入力SHA-256: `42e0b4aad9580a5185a4cbc28625c8e8b4f374243703b6541506c2589e77ff78`
- 座標固定・同値性: 建物中心原点、進行方向をx正、経路をy=±100に合同固定。
- 答えは `official_answers.jsonl` へ入力固定後に分離。選定・入力には未使用。

## 手元の原文（二次資料のQuestionをそのまま保存）

Jenny and Kenny are walking in the same direction, Kenny at 3 feet per second and Jenny at 1 foot per second, on parallel paths that are 200 feet apart. A tall circular building 100 feet in diameter is centered midway between the paths. At the instant when the building first blocks the line of sight between Jenny and Kenny, they are 200 feet apart. Let $t\,$ be the amount of time, in seconds, before Jenny and Kenny can see each other again. If $t\,$ is written as a fraction in lowest terms, what is the sum of the numerator and denominator?

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| building center | `constructions[0]` | `O = Point(0, 0)` |
| Jenny path 100ft below center | `constructions[1]` | `J0 = Point(j, -100)` |
| Kenny path100ft above | `constructions[2]` | `K0 = Point(k, 100)` |
| Jenny speed1 same direction | `constructions[3]` | `J1 = Point(j+t, -100)` |
| Kenny speed3 | `constructions[4]` | `K1 = Point(k+3*t, 100)` |
| initial sightline contact | `constructions[5]` | `F0 = FootOfPerpendicular(O,Line(J0,K0))` |
| next sightline contact | `constructions[6]` | `F1 = FootOfPerpendicular(O,Line(J1,K1))` |
| initial separation200 | `conditions[0]` | `Distance(J0,K0) = 200` |
| first tangent to diameter100 building | `conditions[1]` | `Distance(O,F0) = 50` |
| next tangency / sight resumes | `conditions[2]` | `Distance(O,F1) = 50` |
| positive elapsed time | `conditions[3]` | `t > 0` |
| entry: initial tangent is on approaching (left) side as both move right | `conditions[4]` | `0 > j+k` |
| initial contact between people | `conditions[5]` | `Distance(J0,F0)+Distance(F0,K0) = Distance(J0,K0)` |
| final contact between people | `conditions[6]` | `Distance(J1,F1)+Distance(F1,K1) = Distance(J1,K1)` |
| time in lowest terms | `conditions[7]` | `t = m/n` |
| 既約分数の整数分子分母・Bezout整数証人 | `conditions[8]` | `IsInteger(m) = 0` |
| 既約分数の整数分子分母・Bezout整数証人 | `conditions[9]` | `IsInteger(n) = 0` |
| 既約分数の整数分子分母・Bezout整数証人 | `conditions[10]` | `IsInteger(u) = 0` |
| 既約分数の整数分子分母・Bezout整数証人 | `conditions[11]` | `IsInteger(v) = 0` |
| 分母は正 | `conditions[12]` | `n > 0` |
| 互いに素の定義的同値条件（Bezout） | `conditions[13]` | `u*m+v*n = 1` |
| 分子は正 | `conditions[14]` | `m > 0` |
| numerator+denominator of time | `target` | `m+n` |

## 残る制約

二つの接触時刻を未知配置のまま記述。接触点が視線の線分上にあることと入口側をguardに含む。

分枝・内部・非退化は表のguardで明示。根番号で解を選ばない。AST合格は幾何同値性・実行可能性・目標の一意性を保証しない。


---

# AIME-1993-15 原文→入力対応カード

状態: **二次資料・公式冊子未照合・数値検証未実施**。

- 資料: `jssa/difficulty/unseen-1983/source-evidence/aime-1983-1999/aime-1983-1999.jsonl` / line 143
- 原文SHA-256: `e8dcd1e6addf369b3d9b2207c93ac8bce8608ed5e78a871520c963326e93f08e`
- 入力SHA-256: `ea0eb84003d0660c4216f31177a735dbf55d79a0060560214d43031aba128788`
- 座標固定・同値性: A原点、ABをx軸、Cを上側。指定長さを保持。
- 答えは `official_answers.jsonl` へ入力固定後に分離。選定・入力には未使用。

## 手元の原文（二次資料のQuestionをそのまま保存）

Let $\overline{CH}$ be an altitude of $\triangle ABC$ . Let $R\,$ and $S\,$ be the points where the circles inscribed in the triangles $ACH\,$ and $BCH^{}_{}$ are tangent to $\overline{CH}$ . If $AB = 1995\,$ , $AC = 1994\,$ , and $BC = 1993\,$ , then $RS\,$ can be expressed as $m/n\,$ , where $m\,$ and $n\,$ are relatively prime integers. Find $m + n\,$ .

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| A | `constructions[0]` | `A = Point(0, 0)` |
| AB1995 | `constructions[1]` | `B = Point(1995, 0)` |
| C | `constructions[2]` | `C = Point(cx, cy)` |
| altitude CH | `constructions[3]` | `H = FootOfPerpendicular(C,Line(A,B))` |
| incircle of ACH | `constructions[4]` | `I1 = Incenter(A,C,H)` |
| incircle of BCH | `constructions[5]` | `I2 = Incenter(B,C,H)` |
| first incircle tangency to CH | `constructions[6]` | `R = FootOfPerpendicular(I1,Line(C,H))` |
| second incircle tangency to CH | `constructions[7]` | `S = FootOfPerpendicular(I2,Line(C,H))` |
| mirror / nondegenerate | `conditions[0]` | `cy > 0` |
| AC1994 | `conditions[1]` | `Distance(A,C) = 1994` |
| BC1993 | `conditions[2]` | `Distance(B,C) = 1993` |
| altitude foot strictly on AB | `conditions[3]` | `H.x > 0` |
| altitude foot strictly on AB | `conditions[4]` | `1995 > H.x` |
| RS in lowest terms | `conditions[5]` | `Distance(R,S) = m/n` |
| 既約分数の整数分子分母・Bezout整数証人 | `conditions[6]` | `IsInteger(m) = 0` |
| 既約分数の整数分子分母・Bezout整数証人 | `conditions[7]` | `IsInteger(n) = 0` |
| 既約分数の整数分子分母・Bezout整数証人 | `conditions[8]` | `IsInteger(u) = 0` |
| 既約分数の整数分子分母・Bezout整数証人 | `conditions[9]` | `IsInteger(v) = 0` |
| 分母は正 | `conditions[10]` | `n > 0` |
| 互いに素の定義的同値条件（Bezout） | `conditions[11]` | `u*m+v*n = 1` |
| 分子は正 | `conditions[12]` | `m > 0` |
| sum numerator denominator | `target` | `m+n` |

## 残る制約

公式冊子照合と独立の意味監査は未了。

分枝・内部・非退化は表のguardで明示。根番号で解を選ばない。AST合格は幾何同値性・実行可能性・目標の一意性を保証しない。


---

# AIME-1994-02 原文→入力対応カード

状態: **二次資料・公式冊子未照合・数値検証未実施**。

- 資料: `jssa/difficulty/unseen-1983/source-evidence/aime-1983-1999/aime-1983-1999.jsonl` / line 145
- 原文SHA-256: `9b8968ba02092d422586c2bf036cf1d94354eb3494ccca7664c66edcc9199f89`
- 入力SHA-256: `19168ed238ff33503e0406359c3591e7e3faba41457a15ed4d13ea44aa3bb837`
- 座標固定・同値性: 中心線PQをx軸、Pを左側に合同固定。CDの右に正方形を置き小円は外側。ABの縦位置は未知のまま。
- 答えは `official_answers.jsonl` へ入力固定後に分離。選定・入力には未使用。

## 手元の原文（二次資料のQuestionをそのまま保存）

A circle with diameter $\overline{PQ}\,$ of length 10 is internally tangent at $P^{}_{}$ to a circle of radius 20. Square $ABCD\,$ is constructed with $A\,$ and $B\,$ on the larger circle, $\overline{CD}\,$ tangent at $Q\,$ to the smaller circle, and the smaller circle outside $ABCD\,$ . The length of $\overline{AB}\,$ can be written in the form $m + \sqrt{n}\,$ , where $m\,$ and $n\,$ are integers. Find $m + n\,$ .

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| large center | `constructions[0]` | `O = Point(0, 0)` |
| internal tangency P | `constructions[1]` | `P = Point(-20, 0)` |
| PQ diameter10 | `constructions[2]` | `Q = Point(-20+10, 0)` |
| small circle center | `constructions[3]` | `U = Point(-20+10/2, 0)` |
| large radius20 | `constructions[4]` | `big = Circle(O,20)` |
| small diameter10 | `constructions[5]` | `small = Circle(U,10/2)` |
| square to right of tangent CD | `constructions[6]` | `A = Point(Q.x+s, y)` |
| square | `constructions[7]` | `B = Point(Q.x+s, y+s)` |
| CD tangent at Q | `constructions[8]` | `C = Point(Q.x, y+s)` |
| CD tangent at Q | `constructions[9]` | `D = Point(Q.x, y)` |
| positive square side | `conditions[0]` | `s > 0` |
| Q on CD | `conditions[1]` | `0 > y` |
| Q on CD | `conditions[2]` | `y+s > 0` |
| A on big circle | `conditions[3]` | `OnCircle(A,big) = 0` |
| B on big circle | `conditions[4]` | `OnCircle(B,big) = 0` |
| AB=m+sqrt(n) integers | `conditions[5]` | `s = m+sqrt(n)` |
| 原問の整数係数 | `conditions[6]` | `IsInteger(m) = 0` |
| 原問の整数係数 | `conditions[7]` | `IsInteger(n) = 0` |
| 平方根の定義域 | `conditions[8]` | `n >= 0` |
| m+n | `target` | `m+n` |

## 残る制約

公式冊子照合と独立の意味監査は未了。

分枝・内部・非退化は表のguardで明示。根番号で解を選ばない。AST合格は幾何同値性・実行可能性・目標の一意性を保証しない。


---

# AIME-1994-08 原文→入力対応カード

状態: **二次資料・公式冊子未照合・数値検証未実施**。

- 資料: `jssa/difficulty/unseen-1983/source-evidence/aime-1983-1999/aime-1983-1999.jsonl` / line 146
- 原文SHA-256: `757d3d887ffb8b13c141f5ab51937e8da802da3afe5b2b963d954c48a8db0910`
- 入力SHA-256: `ef3343be85707a0b7774990cf28a2922bee7c0482f78f3253d03d264e31af05e`
- 座標固定・同値性: 原文の絶対座標をそのまま保持。
- 答えは `official_answers.jsonl` へ入力固定後に分離。選定・入力には未使用。

## 手元の原文（二次資料のQuestionをそのまま保存）

The points $(0,0)\,$ , $(a,11)\,$ , and $(b,37)\,$ are the vertices of an equilateral triangle.  Find the value of $ab\,$ .

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| first vertex | `constructions[0]` | `O = Point(0, 0)` |
| second vertex | `constructions[1]` | `A = Point(a, 11)` |
| third vertex | `constructions[2]` | `B = Point(b, 37)` |
| equilateral | `conditions[0]` | `Distance(O,A) = Distance(A,B)` |
| equilateral | `conditions[1]` | `Distance(A,B) = Distance(B,O)` |
| nondegenerate equilateral triangle | `conditions[2]` | `Area(O,A,B) > 0` |
| ab | `target` | `a*b` |

## 残る制約

公式冊子照合と独立の意味監査は未了。

分枝・内部・非退化は表のguardで明示。根番号で解を選ばない。AST合格は幾何同値性・実行可能性・目標の一意性を保証しない。


---

# AIME-1994-10 原文→入力対応カード

状態: **二次資料・公式冊子未照合・数値検証未実施**。

- 資料: `jssa/difficulty/unseen-1983/source-evidence/aime-1983-1999/aime-1983-1999.jsonl` / line 148
- 原文SHA-256: `a7cedc3ab84ef001aa415d5ac994b78a95610324eb16f1aa809f8b0a6fe0215e`
- 入力SHA-256: `13eaa39b72e8bffc6d9e4ca60949e631c082d6f3fda21a678a11f52099c9d762`
- 座標固定・同値性: B原点、BCをx軸、Aを上側。未知の整数辺をそのまま保持。
- 答えは `official_answers.jsonl` へ入力固定後に分離。選定・入力には未使用。

## 手元の原文（二次資料のQuestionをそのまま保存）

In triangle $ABC,\,$ angle $C$ is a right angle and the altitude from $C\,$ meets $\overline{AB}\,$ at $D.\,$ The lengths of the sides of $\triangle ABC\,$ are integers, $BD=29^3,\,$ and $\cos B=m/n\,$ , where $m\,$ and $n\,$ are relatively prime positive integers.  Find $m+n.\,$

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| vertex B | `constructions[0]` | `B = Point(0, 0)` |
| right vertex C / BC=b | `constructions[1]` | `C = Point(b, 0)` |
| AC=a | `constructions[2]` | `A = Point(b, a)` |
| altitude CD | `constructions[3]` | `D = FootOfPerpendicular(C,Line(A,B))` |
| integer side lengths | `conditions[0]` | `IsInteger(a) = 0` |
| integer side lengths | `conditions[1]` | `IsInteger(b) = 0` |
| integer side lengths | `conditions[2]` | `IsInteger(c) = 0` |
| positive side length | `conditions[3]` | `a > 0` |
| positive side length | `conditions[4]` | `b > 0` |
| positive side length | `conditions[5]` | `c > 0` |
| hypotenuse integer c | `conditions[6]` | `Distance(A,B) = c` |
| BD=29³ | `conditions[7]` | `Distance(B,D) = 29**3` |
| cos B in lowest terms | `conditions[8]` | `cos(Angle(A,B,C)) = m/n` |
| 既約分数の整数分子分母・Bezout整数証人 | `conditions[9]` | `IsInteger(m) = 0` |
| 既約分数の整数分子分母・Bezout整数証人 | `conditions[10]` | `IsInteger(n) = 0` |
| 既約分数の整数分子分母・Bezout整数証人 | `conditions[11]` | `IsInteger(u) = 0` |
| 既約分数の整数分子分母・Bezout整数証人 | `conditions[12]` | `IsInteger(v) = 0` |
| 分母は正 | `conditions[13]` | `n > 0` |
| 互いに素の定義的同値条件（Bezout） | `conditions[14]` | `u*m+v*n = 1` |
| 分子は正 | `conditions[15]` | `m > 0` |
| m+n | `target` | `m+n` |

## 残る制約

公式冊子照合と独立の意味監査は未了。

分枝・内部・非退化は表のguardで明示。根番号で解を選ばない。AST合格は幾何同値性・実行可能性・目標の一意性を保証しない。


---

# AIME-1995-04 原文→入力対応カード

状態: **二次資料・公式冊子未照合・数値検証未実施**。

- 資料: `jssa/difficulty/unseen-1983/source-evidence/aime-1983-1999/aime-1983-1999.jsonl` / line 156
- 原文SHA-256: `72941f9a477ecd805371633f21cd553792dc45ebdbcccbe18b3e53531eda95b1`
- 入力SHA-256: `f56bf681d1128051135ccf4249ed6ed23078c3a02513e8e326cf89d749d576c8`
- 座標固定・同値性: 大円中心原点、半径3の中心を正x側。接する中心距離だけ定義から表す。
- 答えは `official_answers.jsonl` へ入力固定後に分離。選定・入力には未使用。

## 手元の原文（二次資料のQuestionをそのまま保存）

Circles of radius $3$ and $6$ are externally tangent to each other and are internally tangent to a circle of radius $9$ . The circle of radius $9$ has a chord that is a common external tangent of the other two circles. Find the square of the length of this chord.

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| radius9 center | `constructions[0]` | `O = Point(0, 0)` |
| radius3 internally tangent / center distance9-3 | `constructions[1]` | `U = Point(9-3, 0)` |
| radius6 center | `constructions[2]` | `V = Point(x, y)` |
| chord endpoint | `constructions[3]` | `A = Point(ax, ay)` |
| chord endpoint | `constructions[4]` | `B = Point(bx, by)` |
| outer circle | `constructions[5]` | `big = Circle(O,9)` |
| radius6 internally tangent | `conditions[0]` | `Distance(O,V) = 9-6` |
| small circles externally tangent | `conditions[1]` | `Distance(U,V) = 3+6` |
| unit line normal | `conditions[2]` | `nx**2+ny**2 = 1` |
| common external tangent / both centers same signed side | `conditions[3]` | `nx*U.x+ny*U.y-h = 3` |
| common external tangent | `conditions[4]` | `nx*V.x+ny*V.y-h = 6` |
| chord A on tangent line | `conditions[5]` | `nx*A.x+ny*A.y = h` |
| chord B on line | `conditions[6]` | `nx*B.x+ny*B.y = h` |
| A on big circle | `conditions[7]` | `OnCircle(A,big) = 0` |
| B on big circle | `conditions[8]` | `OnCircle(B,big) = 0` |
| distinct endpoints | `conditions[9]` | `Distance(A,B) > 0` |
| square of chord length | `target` | `Distance(A,B)**2` |

## 残る制約

公式冊子照合と独立の意味監査は未了。

分枝・内部・非退化は表のguardで明示。根番号で解を選ばない。AST合格は幾何同値性・実行可能性・目標の一意性を保証しない。


---

# AIME-1995-09 原文→入力対応カード

状態: **二次資料・公式冊子未照合・数値検証未実施**。

- 資料: `jssa/difficulty/unseen-1983/source-evidence/aime-1983-1999/aime-1983-1999.jsonl` / line 160
- 原文SHA-256: `097e691aefb53adfab6425b766c49816ce6a5225a63459d510fae2d0060672ee`
- 入力SHA-256: `39cfb4e30c3e10d5e2a02fde6c131f362551c644330715c91e84c7c41152787e`
- 座標固定・同値性: M原点、AMを縦軸、等辺性からB,Cを左右対称に表示。AMの長さ保持。
- 答えは `official_answers.jsonl` へ入力固定後に分離。選定・入力には未使用。

## 手元の原文（二次資料のQuestionをそのまま保存）

Triangle $ABC$ is isosceles, with $AB=AC$ and altitude $AM=11.$ Suppose that there is a point $D$ on $\overline{AM}$ with $AD=10$ and $\angle BDC=3\angle BAC.$ Then the perimeter of $\triangle ABC$ may be written in the form $a+\sqrt{b},$ where $a$ and $b$ are integers.  Find $a+b.$ AIME 1995 Problem 9.png

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| altitude foot | `constructions[0]` | `M = Point(0, 0)` |
| AM=11 | `constructions[1]` | `A = Point(0, 11)` |
| isosceles base endpoint | `constructions[2]` | `B = Point(-s, 0)` |
| isosceles base endpoint | `constructions[3]` | `C = Point(s, 0)` |
| D on AM, AD=10 | `constructions[4]` | `D = Point(0, 11-10)` |
| nondegenerate isosceles | `conditions[0]` | `s > 0` |
| angle BDC=3 BAC | `conditions[1]` | `Angle(B,D,C) = 3*Angle(B,A,C)` |
| perimeter a+sqrt(b) integers | `conditions[2]` | `Distance(A,B)+Distance(A,C)+Distance(B,C) = a+sqrt(b)` |
| 原問の整数係数 | `conditions[3]` | `IsInteger(a) = 0` |
| 原問の整数係数 | `conditions[4]` | `IsInteger(b) = 0` |
| 平方根の定義域 | `conditions[5]` | `b >= 0` |
| a+b | `target` | `a+b` |

## 残る制約

公式冊子照合と独立の意味監査は未了。

分枝・内部・非退化は表のguardで明示。根番号で解を選ばない。AST合格は幾何同値性・実行可能性・目標の一意性を保証しない。


---

# AIME-1996-13 原文→入力対応カード

状態: **二次資料・公式冊子未照合・数値検証未実施**。

- 資料: `jssa/difficulty/unseen-1983/source-evidence/aime-1983-1999/aime-1983-1999.jsonl` / line 178
- 原文SHA-256: `21b2779dd82d1d4af90411a6b2ba17905b89dc03bcb49a620788eee631f00882`
- 入力SHA-256: `26d32973acac9f90b467cc3c78198dd8ebafef2d4d1e37290e38856940514a07`
- 座標固定・同値性: A原点、AB水平、C上側。線分ADが中点Mを含むようt>=1。交点の根番号では選ばない。
- 答えは `official_answers.jsonl` へ入力固定後に分離。選定・入力には未使用。

## 手元の原文（二次資料のQuestionをそのまま保存）

In triangle $ABC$ , $AB=\sqrt{30}$ , $AC=\sqrt{6}$ , and $BC=\sqrt{15}$ . There is a point $D$ for which $\overline{AD}$ bisects $\overline{BC}$ , and $\angle ADB$ is a right angle. The ratio \[\dfrac{\text{Area}(\triangle ADB)}{\text{Area}(\triangle ABC)}\] can be written in the form $\dfrac{m}{n}$ , where $m$ and $n$ are relatively prime positive integers. Find $m+n$ .

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| A | `constructions[0]` | `A = Point(0, 0)` |
| AB=sqrt30 | `constructions[1]` | `B = Point(sqrt(30), 0)` |
| C | `constructions[2]` | `C = Point(cx, cy)` |
| AD bisects BC | `constructions[3]` | `M = Midpoint(B,C)` |
| D on ray AM / segment AD contains midpoint M | `constructions[4]` | `D = Point(A.x+t*(M.x-A.x), A.y+t*(M.y-A.y))` |
| upper nondegenerate triangle | `conditions[0]` | `cy > 0` |
| ACsqrt6 | `conditions[1]` | `Distance(A,C) = sqrt(6)` |
| BCsqrt15 | `conditions[2]` | `Distance(B,C) = sqrt(15)` |
| segment AD bisects BC / M lies on segment AD | `conditions[3]` | `t >= 1` |
| angle ADB defined | `conditions[4]` | `Distance(A,D) > 0` |
| angle ADB defined | `conditions[5]` | `Distance(B,D) > 0` |
| angle ADB=90° | `conditions[6]` | `((A.x-D.x)*(B.x-D.x)+(A.y-D.y)*(B.y-D.y)) = 0` |
| area ratio reduced | `conditions[7]` | `Area(A,D,B)/Area(A,B,C) = m/n` |
| 既約分数の整数分子分母・Bezout整数証人 | `conditions[8]` | `IsInteger(m) = 0` |
| 既約分数の整数分子分母・Bezout整数証人 | `conditions[9]` | `IsInteger(n) = 0` |
| 既約分数の整数分子分母・Bezout整数証人 | `conditions[10]` | `IsInteger(u) = 0` |
| 既約分数の整数分子分母・Bezout整数証人 | `conditions[11]` | `IsInteger(v) = 0` |
| 分母は正 | `conditions[12]` | `n > 0` |
| 互いに素の定義的同値条件（Bezout） | `conditions[13]` | `u*m+v*n = 1` |
| 分子は正 | `conditions[14]` | `m > 0` |
| m+n | `target` | `m+n` |

## 残る制約

公式冊子照合と独立の意味監査は未了。

分枝・内部・非退化は表のguardで明示。根番号で解を選ばない。AST合格は幾何同値性・実行可能性・目標の一意性を保証しない。


---

# AIME-1996-15 原文→入力対応カード

状態: **二次資料・公式冊子未照合・数値検証未実施**。

- 資料: `jssa/difficulty/unseen-1983/source-evidence/aime-1983-1999/aime-1983-1999.jsonl` / line 180
- 原文SHA-256: `517b7ea8776c993701c7d37740c64bd94720ecd22d05c612fd3a04aeb8c99839`
- 入力SHA-256: `6a6aae4721e04df587587ff6001a6c44ea2628241ab9164a2bee87887a8ad568`
- 座標固定・同値性: 角度比のみなのでAB=1で相似正規化。鏡映でdy>0。
- 答えは `official_answers.jsonl` へ入力固定後に分離。選定・入力には未使用。

## 手元の原文（二次資料のQuestionをそのまま保存）

In parallelogram $ABCD,$ let $O$ be the intersection of diagonals $\overline{AC}$ and $\overline{BD}$ . Angles $CAB$ and $DBC$ are each twice as large as angle $DBA,$ and angle $ACB$ is $r$ times as large as angle $AOB$ . Find the greatest integer that does not exceed $1000r$ .

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| parallelogram | `constructions[0]` | `A = Point(0, 0)` |
| similarity AB=1 | `constructions[1]` | `B = Point(1, 0)` |
| D | `constructions[2]` | `D = Point(dx, dy)` |
| C=B+D-A | `constructions[3]` | `C = Point(1+dx, dy)` |
| diagonals intersection | `constructions[4]` | `O = Midpoint(A,C)` |
| nondegenerate parallelogram / orientation | `conditions[0]` | `dy > 0` |
| CAB twice DBA | `conditions[1]` | `Angle(C,A,B) = 2*Angle(D,B,A)` |
| DBC twice DBA | `conditions[2]` | `Angle(D,B,C) = 2*Angle(D,B,A)` |
| ACB=r AOB | `conditions[3]` | `Angle(A,C,B) = r*Angle(A,O,B)` |
| positive angle ratio | `conditions[4]` | `r > 0` |
| greatest integer <=1000r | `target` | `(1000*r) // 1` |

## 残る制約

公式冊子照合と独立の意味監査は未了。

分枝・内部・非退化は表のguardで明示。根番号で解を選ばない。AST合格は幾何同値性・実行可能性・目標の一意性を保証しない。


---

# AIME-1997-04 原文→入力対応カード

状態: **二次資料・公式冊子未照合・数値検証未実施**。

- 資料: `jssa/difficulty/unseen-1983/source-evidence/aime-1983-1999/aime-1983-1999.jsonl` / line 184
- 原文SHA-256: `f5b413e7fa98d7ba4720b474d2eb5941d535b80d66aeaf00829f81e8326798af`
- 入力SHA-256: `a5d74a6a0925ee13cbaffe63227fefc600dd173fe1562796ff3b922a0c27bd43`
- 座標固定・同値性: 5,5の二中心を水平固定。Cだけ鏡映で上側。第4中心の分枝は残す。
- 答えは `official_answers.jsonl` へ入力固定後に分離。選定・入力には未使用。

## 手元の原文（二次資料のQuestionをそのまま保存）

Circles of radii 5, 5, 8, and $m/n$ are mutually externally tangent, where $m$ and $n$ are relatively prime positive integers.  Find $m + n.$

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| first radius5 center | `constructions[0]` | `A = Point(0, 0)` |
| second radius5 center | `constructions[1]` | `B = Point(5+5, 0)` |
| radius8 center | `constructions[2]` | `C = Point(cx, cy)` |
| radius r center | `constructions[3]` | `D = Point(dx, dy)` |
| mirror choice for center C | `conditions[0]` | `cy > 0` |
| positive fourth radius | `conditions[1]` | `r > 0` |
| external tangent | `conditions[2]` | `Distance(A,C) = 5+8` |
| external tangent | `conditions[3]` | `Distance(B,C) = 5+8` |
| external tangent | `conditions[4]` | `Distance(A,D) = 5+r` |
| external tangent | `conditions[5]` | `Distance(B,D) = 5+r` |
| external tangent | `conditions[6]` | `Distance(C,D) = 8+r` |
| fourth radius reduced | `conditions[7]` | `r = m/n` |
| 既約分数の整数分子分母・Bezout整数証人 | `conditions[8]` | `IsInteger(m) = 0` |
| 既約分数の整数分子分母・Bezout整数証人 | `conditions[9]` | `IsInteger(n) = 0` |
| 既約分数の整数分子分母・Bezout整数証人 | `conditions[10]` | `IsInteger(u) = 0` |
| 既約分数の整数分子分母・Bezout整数証人 | `conditions[11]` | `IsInteger(v) = 0` |
| 分母は正 | `conditions[12]` | `n > 0` |
| 互いに素の定義的同値条件（Bezout） | `conditions[13]` | `u*m+v*n = 1` |
| 分子は正 | `conditions[14]` | `m > 0` |
| m+n | `target` | `m+n` |

## 残る制約

公式冊子照合と独立の意味監査は未了。

分枝・内部・非退化は表のguardで明示。根番号で解を選ばない。AST合格は幾何同値性・実行可能性・目標の一意性を保証しない。


---

# AIME-1997-07 原文→入力対応カード

状態: **二次資料・公式冊子未照合・数値検証未実施**。

- 資料: `jssa/difficulty/unseen-1983/source-evidence/aime-1983-1999/aime-1983-1999.jsonl` / line 187
- 原文SHA-256: `b5ee21b974597946b52f7a70ebe335403b84d4635a5987b4de501ffe9c4f2c65`
- 入力SHA-256: `5b1706a435bde7cb7911dea329f41ce6d108e1fce5dc0f1ec51430fb274ac246`
- 座標固定・同値性: t0の車を原点、東x正・北y正。円の中心の運動を本文通りに記述。
- 答えは `official_answers.jsonl` へ入力固定後に分離。選定・入力には未使用。

## 手元の原文（二次資料のQuestionをそのまま保存）

A car travels due east at $\frac 23$ miles per minute on a long, straight road. At the same time, a circular storm, whose radius is $51$ miles, moves southeast at $\frac 12\sqrt{2}$ miles per minute. At time $t=0$ , the center of the storm is $110$ miles due north of the car. At time $t=t_1$ minutes, the car enters the storm circle, and at time $t=t_2$ minutes, the car leaves the storm circle. Find $\frac 12(t_1+t_2)$ .

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| car east speed2/3 at t1 | `constructions[0]` | `C1 = Point(2*t1/3, 0)` |
| storm southeast speed sqrt2/2 at t1 | `constructions[1]` | `S1 = Point(t1/2, 110-t1/2)` |
| car at t2 | `constructions[2]` | `C2 = Point(2*t2/3, 0)` |
| storm at t2 | `constructions[3]` | `S2 = Point(t2/2, 110-t2/2)` |
| entry after t0 | `conditions[0]` | `t1 > 0` |
| exit later than entry | `conditions[1]` | `t2 > t1` |
| entry boundary | `conditions[2]` | `Distance(C1,S1) = 51` |
| exit boundary | `conditions[3]` | `Distance(C2,S2) = 51` |
| half of entry+exit time | `target` | `(t1+t2)/2` |

## 残る制約

公式冊子照合と独立の意味監査は未了。

分枝・内部・非退化は表のguardで明示。根番号で解を選ばない。AST合格は幾何同値性・実行可能性・目標の一意性を保証しない。


---

# AIME-1998-06 原文→入力対応カード

状態: **二次資料・公式冊子未照合・数値検証未実施**。

- 資料: `jssa/difficulty/unseen-1983/source-evidence/aime-1983-1999/aime-1983-1999.jsonl` / line 200
- 原文SHA-256: `381040384b04efbcb1b5f7ce2ce4e6229b08e49a655882a2be21b07f09b0bd99`
- 入力SHA-256: `7865b7a85754ba34efa870093a01fed654709fb7345695952f24b03f28fa9690`
- 座標固定・同値性: A原点、AB水平、D上側。長さがあるため相似尺度は固定しない。
- 答えは `official_answers.jsonl` へ入力固定後に分離。選定・入力には未使用。

## 手元の原文（二次資料のQuestionをそのまま保存）

Let $ABCD$ be a parallelogram .  Extend $\overline{DA}$ through $A$ to a point $P,$ and let $\overline{PC}$ meet $\overline{AB}$ at $Q$ and $\overline{DB}$ at $R.$ Given that $PQ = 735$ and $QR = 112,$ find $RC.$

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| parallelogram | `constructions[0]` | `A = Point(0, 0)` |
| B | `constructions[1]` | `B = Point(b, 0)` |
| D | `constructions[2]` | `D = Point(dx, dy)` |
| C=B+D-A | `constructions[3]` | `C = Point(b+dx, dy)` |
| DA extended beyond A | `constructions[4]` | `P = Point(-t*dx, -t*dy)` |
| PC meets AB | `constructions[5]` | `Q = Intersect(Line(P,C),Line(A,B))` |
| PC meets DB | `constructions[6]` | `R = Intersect(Line(P,C),Line(D,B))` |
| AB positive | `conditions[0]` | `b > 0` |
| parallelogram nondegenerate / orientation | `conditions[1]` | `dy > 0` |
| P beyond A | `conditions[2]` | `t > 0` |
| PQ735 | `conditions[3]` | `Distance(P,Q) = 735` |
| QR112 | `conditions[4]` | `Distance(Q,R) = 112` |
| Q on segment AB | `conditions[5]` | `Distance(A,Q)+Distance(Q,B) = Distance(A,B)` |
| R on diagonal DB | `conditions[6]` | `Distance(D,R)+Distance(R,B) = Distance(D,B)` |
| order P-Q-R-C / segment intersections | `conditions[7]` | `Distance(P,Q)+Distance(Q,R)+Distance(R,C) = Distance(P,C)` |
| RC | `target` | `Distance(R,C)` |

## 残る制約

公式冊子照合と独立の意味監査は未了。

分枝・内部・非退化は表のguardで明示。根番号で解を選ばない。AST合格は幾何同値性・実行可能性・目標の一意性を保証しない。


---

# AIME-1999-02 原文→入力対応カード

状態: **二次資料・公式冊子未照合・数値検証未実施**。

- 資料: `jssa/difficulty/unseen-1983/source-evidence/aime-1983-1999/aime-1983-1999.jsonl` / line 211
- 原文SHA-256: `55dce185409741e48883c81f4fdd0af09d70d83a2dfd6ef1996fa09545d6efab`
- 入力SHA-256: `132bce8a265a34029130ccc90139234ef501a8731c4f693efb845477fc7d8c18`
- 座標固定・同値性: 絶対座標保持。中心を通ると解いて仮定せず、両切断片の合同を直接制約化。
- 答えは `official_answers.jsonl` へ入力固定後に分離。選定・入力には未使用。

## 手元の原文（二次資料のQuestionをそのまま保存）

Consider the parallelogram with vertices $(10,45),$ $(10,114),$ $(28,153),$ and $(28,84).$ A line through the origin cuts this figure into two congruent polygons.  The slope of the line is $m/n,$ where $m_{}$ and $n_{}$ are relatively prime positive integers.  Find $m+n.$

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| given vertex | `constructions[0]` | `A = Point(10, 45)` |
| given vertex | `constructions[1]` | `B = Point(10, 114)` |
| given vertex | `constructions[2]` | `C = Point(28, 153)` |
| given vertex | `constructions[3]` | `D = Point(28, 84)` |
| cut line through origin | `constructions[4]` | `O = Point(0, 0)` |
| choose either pair of opposite cut edges | `constructions[5]` | `V0 = A if e == 0 else B` |
| choose either pair of opposite cut edges | `constructions[6]` | `V1 = B if e == 0 else C` |
| choose either pair of opposite cut edges | `constructions[7]` | `V2 = C if e == 0 else D` |
| choose either pair of opposite cut edges | `constructions[8]` | `V3 = D if e == 0 else A` |
| first cut endpoint | `constructions[9]` | `X = PointOnSegment(V0,V1,p)` |
| opposite cut endpoint | `constructions[10]` | `Y = PointOnSegment(V2,V3,q)` |
| two possible pairs of opposite edges | `conditions[0]` | `(e == 0) or (e == 1)` |
| interior edge intersection | `conditions[1]` | `p > 0` |
| interior edge intersection | `conditions[2]` | `1 > p` |
| interior opposite intersection | `conditions[3]` | `q > 0` |
| interior opposite intersection | `conditions[4]` | `1 > q` |
| cut line y=(m/n)x through origin | `conditions[5]` | `X.y*n = X.x*m` |
| same cut line | `conditions[6]` | `Y.y*n = Y.x*m` |
| two quadrilateral pieces congruent / all pair distances under cyclic/reversed bijection | `conditions[7]` | `(Distance(X,V1) == Distance(Y,V3) and Distance(X,V2) == Distance(Y,V0) and Distance(X,Y) == Distance(Y,X) and Distance(V1,V2) == Distance(V3,V0) and Distance(V1,Y) == Distance(V3,X) and Distance(V2,Y) == Distance(V0,X)) or (Distance(X,V1) == Distance(V3,V0) and Distance(X,V2) == Distance(V3,X) and Distance(X,Y) == Distance(V3,Y) and Distance(V1,V2) == Distance(V0,X) and Distance(V1,Y) == Distance(V0,Y) and Distance(V2,Y) == Distance(X,Y)) or (Distance(X,V1) == Distance(V0,X) and Distance(X,V2) == Distance(V0,Y) and Distance(X,Y) == Distance(V0,V3) and Distance(V1,V2) == Distance(X,Y) and Distance(V1,Y) == Distance(X,V3) and Distance(V2,Y) == Distance(Y,V3)) or (Distance(X,V1) == Distance(X,Y) and Distance(X,V2) == Distance(X,V3) and Distance(X,Y) == Distance(X,V0) and Distance(V1,V2) == Distance(Y,V3) and Distance(V1,Y) == Distance(Y,V0) and Distance(V2,Y) == Distance(V3,V0)) or (Distance(X,V1) == Distance(Y,X) and Distance(X,V2) == Distance(Y,V0) and Distance(X,Y) == Distance(Y,V3) and Distance(V1,V2) == Distance(X,V0) and Distance(V1,Y) == Distance(X,V3) and Distance(V2,Y) == Distance(V0,V3)) or (Distance(X,V1) == Distance(V3,Y) and Distance(X,V2) == Distance(V3,X) and Distance(X,Y) == Distance(V3,V0) and Distance(V1,V2) == Distance(Y,X) and Distance(V1,Y) == Distance(Y,V0) and Distance(V2,Y) == Distance(X,V0)) or (Distance(X,V1) == Distance(V0,V3) and Distance(X,V2) == Distance(V0,Y) and Distance(X,Y) == Distance(V0,X) and Distance(V1,V2) == Distance(V3,Y) and Distance(V1,Y) == Distance(V3,X) and Distance(V2,Y) == Distance(Y,X)) or (Distance(X,V1) == Distance(X,V0) and Distance(X,V2) == Distance(X,V3) and Distance(X,Y) == Distance(X,Y) and Distance(V1,V2) == Distance(V0,V3) and Distance(V1,Y) == Distance(V0,Y) and Distance(V2,Y) == Distance(V3,Y))` |
| 既約分数の整数分子分母・Bezout整数証人 | `conditions[8]` | `IsInteger(m) = 0` |
| 既約分数の整数分子分母・Bezout整数証人 | `conditions[9]` | `IsInteger(n) = 0` |
| 既約分数の整数分子分母・Bezout整数証人 | `conditions[10]` | `IsInteger(u) = 0` |
| 既約分数の整数分子分母・Bezout整数証人 | `conditions[11]` | `IsInteger(v) = 0` |
| 分母は正 | `conditions[12]` | `n > 0` |
| 互いに素の定義的同値条件（Bezout） | `conditions[13]` | `u*m+v*n = 1` |
| 分子は正 | `conditions[14]` | `m > 0` |
| slope reduced numerator+denominator | `target` | `m+n` |

## 残る制約

凸四角形で合同な二片は頂点数も等しいため切断は対辺同士（隣辺だと三角形と五角形）。各片の頂点順と8通りの合同対応を全て残す。

分枝・内部・非退化は表のguardで明示。根番号で解を選ばない。AST合格は幾何同値性・実行可能性・目標の一意性を保証しない。


---

# AIME-1999-09 原文→入力対応カード

状態: **二次資料・公式冊子未照合・数値検証未実施**。

- 資料: `jssa/difficulty/unseen-1983/source-evidence/aime-1983-1999/aime-1983-1999.jsonl` / line 218
- 原文SHA-256: `1ad4f5e82e0b79377e3efc439871a20970882842533d253825335b0c334a37ac`
- 入力SHA-256: `ebc441e7a5d1608cf31a923f9600cd3fb6696cd47073f269f33c01704b5ca02a`
- 座標固定・同値性: 複素平面の指定原点と単位を保持。
- 答えは `official_answers.jsonl` へ入力固定後に分離。選定・入力には未使用。

## 手元の原文（二次資料のQuestionをそのまま保存）

A function $f$ is defined on the complex numbers by $f(z)=(a+bi)z,$ where $a_{}$ and $b_{}$ are positive numbers.  This function has the property that the image of each point in the complex plane is equidistant from that point and the origin.  Given that $|a+bi|=8$ and that $b^2=m/n,$ where $m_{}$ and $n_{}$ are relatively prime positive integers.  Find $m+n.$

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| origin | `constructions[0]` | `O = Point(0, 0)` |
| unit complex input | `constructions[1]` | `E = Point(1, 0)` |
| image of 1 under multiplication a+bi | `constructions[2]` | `W = Point(a, b)` |
| a positive | `conditions[0]` | `a > 0` |
| b positive | `conditions[1]` | `b > 0` |
| modulus a+bi=8 | `conditions[2]` | `Distance(O,W) = 8` |
| image equidistant from input and origin / homogeneity | `conditions[3]` | `Distance(W,E) = Distance(W,O)` |
| b² reduced | `conditions[4]` | `b**2 = m/n` |
| 既約分数の整数分子分母・Bezout整数証人 | `conditions[5]` | `IsInteger(m) = 0` |
| 既約分数の整数分子分母・Bezout整数証人 | `conditions[6]` | `IsInteger(n) = 0` |
| 既約分数の整数分子分母・Bezout整数証人 | `conditions[7]` | `IsInteger(u) = 0` |
| 既約分数の整数分子分母・Bezout整数証人 | `conditions[8]` | `IsInteger(v) = 0` |
| 分母は正 | `conditions[9]` | `n > 0` |
| 互いに素の定義的同値条件（Bezout） | `conditions[10]` | `u*m+v*n = 1` |
| 分子は正 | `conditions[11]` | `m > 0` |
| m+n | `target` | `m+n` |

## 残る制約

任意zに対する二距離は|z|倍の|(a+bi)-1|と|a+bi|。したがってz=1の等距離条件が全zの性質と定義的に同値。a,bの値を算出しない。

分枝・内部・非退化は表のguardで明示。根番号で解を選ばない。AST合格は幾何同値性・実行可能性・目標の一意性を保証しない。


---

# AIME-1999-12 原文→入力対応カード

状態: **二次資料・公式冊子未照合・数値検証未実施**。

- 資料: `jssa/difficulty/unseen-1983/source-evidence/aime-1983-1999/aime-1983-1999.jsonl` / line 221
- 原文SHA-256: `4b4a9c0028c653a7f763510cbd94fc8e50b134da13aa1f71dae73d239da0bc6c`
- 入力SHA-256: `64424fee99d9fb38475b505e85f337a0bc98811ced197bb35571c62e8303c563`
- 座標固定・同値性: A原点、AB水平、C上側。AP,PB,rを保持。
- 答えは `official_answers.jsonl` へ入力固定後に分離。選定・入力には未使用。

## 手元の原文（二次資料のQuestionをそのまま保存）

The inscribed circle of triangle $ABC$ is tangent to $\overline{AB}$ at $P_{},$ and its radius is 21.  Given that $AP=23$ and $PB=27,$ find the perimeter of the triangle.

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| A | `constructions[0]` | `A = Point(0, 0)` |
| AB=AP+PB | `constructions[1]` | `B = Point(23+27, 0)` |
| unknown C | `constructions[2]` | `C = Point(cx, cy)` |
| AP23 PB27 | `constructions[3]` | `P = Point(23, 0)` |
| incircle center | `constructions[4]` | `I = Incenter(A,B,C)` |
| incircle contact with AB | `constructions[5]` | `T = FootOfPerpendicular(I,Line(A,B))` |
| nondegenerate / mirror | `conditions[0]` | `cy > 0` |
| incircle tangent at P | `conditions[1]` | `T.x = P.x` |
| same contact | `conditions[2]` | `T.y = P.y` |
| inradius21 | `conditions[3]` | `Distance(I,T) = 21` |
| triangle perimeter | `target` | `Distance(A,B)+Distance(B,C)+Distance(C,A)` |

## 残る制約

公式冊子照合と独立の意味監査は未了。

分枝・内部・非退化は表のguardで明示。根番号で解を選ばない。AST合格は幾何同値性・実行可能性・目標の一意性を保証しない。


---

# AIME-1999-14 原文→入力対応カード

状態: **二次資料・公式冊子未照合・数値検証未実施**。

- 資料: `jssa/difficulty/unseen-1983/source-evidence/aime-1983-1999/aime-1983-1999.jsonl` / line 223
- 原文SHA-256: `82b7c063710fc6533b8c417bafb1b13870e3d0e6eb573f6ddaca417a1dd624df`
- 入力SHA-256: `03533e821553e1b9876e96c3f801cc1c7a27a223cca469600cc4956050e49814`
- 座標固定・同値性: A原点、AB正x、C上側。角値やP座標は未知のまま。
- 答えは `official_answers.jsonl` へ入力固定後に分離。選定・入力には未使用。

## 手元の原文（二次資料のQuestionをそのまま保存）

Point $P_{}$ is located inside triangle $ABC$ so that angles $PAB, PBC,$ and $PCA$ are all congruent.  The sides of the triangle have lengths $AB=13, BC=14,$ and $CA=15,$ and the tangent of angle $PAB$ is $m/n,$ where $m_{}$ and $n_{}$ are relatively prime positive integers.  Find $m+n.$

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| A | `constructions[0]` | `A = Point(0, 0)` |
| AB13 | `constructions[1]` | `B = Point(13, 0)` |
| C | `constructions[2]` | `C = Point(cx, cy)` |
| interior P | `constructions[3]` | `P = Point(px, py)` |
| mirror / nondegenerate | `conditions[0]` | `cy > 0` |
| BC14 | `conditions[1]` | `Distance(B,C) = 14` |
| CA15 | `conditions[2]` | `Distance(C,A) = 15` |
| P strictly inside ABC / 各辺の内側 | `conditions[3]` | `((B.x-A.x)*(P.y-A.y)-(B.y-A.y)*(P.x-A.x)) > 0` |
| P strictly inside ABC / 各辺の内側 | `conditions[4]` | `((C.x-B.x)*(P.y-B.y)-(C.y-B.y)*(P.x-B.x)) > 0` |
| P strictly inside ABC / 各辺の内側 | `conditions[5]` | `((A.x-C.x)*(P.y-C.y)-(A.y-C.y)*(P.x-C.x)) > 0` |
| angles PAB and PBC equal | `conditions[6]` | `Angle(P,A,B) = Angle(P,B,C)` |
| angles PBC and PCA equal | `conditions[7]` | `Angle(P,B,C) = Angle(P,C,A)` |
| tangent in lowest terms | `conditions[8]` | `tan(Angle(P,A,B)) = m/n` |
| 既約分数の整数分子分母・Bezout整数証人 | `conditions[9]` | `IsInteger(m) = 0` |
| 既約分数の整数分子分母・Bezout整数証人 | `conditions[10]` | `IsInteger(n) = 0` |
| 既約分数の整数分子分母・Bezout整数証人 | `conditions[11]` | `IsInteger(u) = 0` |
| 既約分数の整数分子分母・Bezout整数証人 | `conditions[12]` | `IsInteger(v) = 0` |
| 分母は正 | `conditions[13]` | `n > 0` |
| 互いに素の定義的同値条件（Bezout） | `conditions[14]` | `u*m+v*n = 1` |
| 分子は正 | `conditions[15]` | `m > 0` |
| m+n | `target` | `m+n` |

## 残る制約

公式冊子照合と独立の意味監査は未了。

分枝・内部・非退化は表のguardで明示。根番号で解を選ばない。AST合格は幾何同値性・実行可能性・目標の一意性を保証しない。


---

# Q2対応カード集（暫定）

指定cards.mdがないため条件別表を採用。各原文・全構成・全条件・目標を対応づけた。

# HMMT-2012-FEB-GUTS-01 原文→入力対応カード

状態: **暫定候補・公式番号/答え未照合・数値検証未実施**。

- 保存資料: `jssa/strategy/astra-consult-14/E/e2h-rows.jsonl` / eval / row_idx=354
- 原文SHA-256: `c7a5746a659875dcf675ed3dae29cc6009e6d890bb40f749435b5a50b939f3de`
- 入力SHA-256（JSONファイルの全bytes）: `313cfb118f2e6a515463eb234419a3c10a3ff79fadc9f812120e7bee9b40e227`
- 座標固定・同値性: Aを原点、ABを正のx軸、正方形を上側。平行移動・回転・鏡映だけ。尺度2を保持。
- 分枝・非退化: 下表のguardと構成の定義域を使用。根番号による選択なし。
- 公式答え: 本カードには含めず、`official_answers.jsonl` の状態を参照。採否と入力に答えを使用していない。

## 手元の原文（保存資料）

Square $A B C D$ has side length 2 , and $X$ is a point outside the square such that $A X=X B=\sqrt{2}$. What is the length of the longest diagonal of pentagon $A X B C D$ ?

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| square ABCD, side 2 / 座標原点 | `constructions[0]` | `A = Point(0, 0)` |
| square ABCD, side 2 | `constructions[1]` | `B = Point(2, 0)` |
| square ABCD, side 2 | `constructions[2]` | `C = Point(2, 2)` |
| square ABCD, side 2 | `constructions[3]` | `D = Point(0, 2)` |
| X is outside the square / 未知点 | `constructions[4]` | `X = Point(x, y)` |
| AX = sqrt(2) | `conditions[0]` | `Distance(A, X) = sqrt(2)` |
| XB = sqrt(2) | `conditions[1]` | `Distance(X, B) = sqrt(2)` |
| X outside square / 正方形の閉領域の外 | `conditions[2]` | `(x < 0) or (x > 2) or (y < 0) or (y > 2)` |
| longest diagonal of AXBCD / 頂点順から得る全5本の対角線の最大値 | `target` | `max([Distance(A, B), Distance(A, C), Distance(X, C), Distance(X, D), Distance(B, D)])` |

## 残る制約

公式原本との照合、独立の意味監査、数値的実行可能性・一意性の確認は未実施。

AST検査の合格は幾何条件の同値性・実行可能性・一意性を保証しない。


---

# HMMT-2013-FEB-TEAM-03 原文→入力対応カード

状態: **暫定候補・公式番号/答え未照合・数値検証未実施**。

- 保存資料: `jssa/strategy/astra-consult-14/E/e2h-rows.jsonl` / eval / row_idx=199
- 原文SHA-256: `d346676026e102ad900899d3d8f2c549128e3057081e7b34349d1051ac9a4267`
- 入力SHA-256（JSONファイルの全bytes）: `c20487e7f105b3f6ab9f1d7b1b78bbbbb4e0f3316b6c779bbe196566ddd4e69a`
- 座標固定・同値性: Bを原点、Cを正のx軸、Aを上半平面。合同移動のみ。
- 分枝・非退化: 下表のguardと構成の定義域を使用。根番号による選択なし。
- 公式答え: 本カードには含めず、`official_answers.jsonl` の状態を参照。採否と入力に答えを使用していない。

## 手元の原文（保存資料）

Let $A B C$ be a triangle with circumcenter $O$ such that $A C=7$. Suppose that the circumcircle of $A O C$ is tangent to $B C$ at $C$ and intersects the line $A B$ at $A$ and $F$. Let $F O$ intersect $B C$ at $E$. Compute $B E$.

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| triangle ABC / 座標原点 | `constructions[0]` | `B = Point(0, 0)` |
| triangle ABC / BCをx軸 | `constructions[1]` | `C = Point(c, 0)` |
| triangle ABC / 未知頂点 | `constructions[2]` | `A = Point(ax, ay)` |
| circumcenter O | `constructions[3]` | `O = Circumcenter(A, B, C)` |
| circumcircle of AOC | `constructions[4]` | `omega = Circumcircle(A, O, C)` |
| line AB meets circle AOC at A and F / A以外 | `constructions[5]` | `F = Intersect(Line(A, B), omega, exclude=A)` |
| FO intersects BC at E | `constructions[6]` | `E = Intersect(Line(F, O), Line(B, C))` |
| BCの長さは正 / 非退化三角形 | `conditions[0]` | `c > 0` |
| 鏡映による向き固定 | `conditions[1]` | `ay > 0` |
| AC = 7 | `conditions[2]` | `Distance(A, C) = 7` |
| circumcircle AOCが定義される | `conditions[3]` | `Area(A, O, C) > 0` |
| circle AOC is tangent to BC at C / Cは構成上円上 | `conditions[4]` | `IsTangent(Line(B, C), omega) = 0` |
| A and F are distinct intersections | `conditions[5]` | `Distance(A, F) > 0` |
| line FOが定義される | `conditions[6]` | `Distance(F, O) > 0` |
| Compute BE | `target` | `Distance(B, E)` |

## 残る制約

公式原本との照合、独立の意味監査、数値的実行可能性・一意性の確認は未実施。

AST検査の合格は幾何条件の同値性・実行可能性・一意性を保証しない。


---

# HMMT-2014-FEB-TEAM-08 原文→入力対応カード

状態: **暫定候補・公式番号/答え未照合・数値検証未実施**。

- 保存資料: `jssa/strategy/astra-consult-14/E/e2h-rows.jsonl` / eval / row_idx=148
- 原文SHA-256: `13784ca4fb5e7ceedbd9a8223bf05c1dbca2fbaddbeb14a2d19bda10817ecc2d`
- 入力SHA-256（JSONファイルの全bytes）: `f8cdba7960fd49d2b2a4075a569b812c06d24ace51ba1f6256477911b8b18e80`
- 座標固定・同値性: B=(0,0), C=(6,0), ay>0。合同移動のみ。
- 分枝・非退化: 下表のguardと構成の定義域を使用。根番号による選択なし。
- 公式答え: 本カードには含めず、`official_answers.jsonl` の状態を参照。採否と入力に答えを使用していない。

## 手元の原文（保存資料）

Let $A B C$ be an acute triangle with circumcenter $O$ such that $A B=4, A C=5$, and $B C=6$. Let $D$ be the foot of the altitude from $A$ to $B C$, and $E$ be the intersection of $A O$ with $B C$. Suppose that $X$ is on $B C$ between $D$ and $E$ such that there is a point $Y$ on $A D$ satisfying $X Y \| A O$ and $Y O \perp A X$. Determine the length of $B X$.

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| BC = 6 / 座標原点 | `constructions[0]` | `B = Point(0, 0)` |
| BC = 6 | `constructions[1]` | `C = Point(6, 0)` |
| triangle ABC / 未知頂点 | `constructions[2]` | `A = Point(ax, ay)` |
| circumcenter O | `constructions[3]` | `O = Circumcenter(A, B, C)` |
| D is the foot from A to BC | `constructions[4]` | `D = FootOfPerpendicular(A, Line(B, C))` |
| E = AO intersection BC | `constructions[5]` | `E = Intersect(Line(A, O), Line(B, C))` |
| X between D and E on BC | `constructions[6]` | `X = PointOnSegment(D, E, t)` |
| Y on AD | `constructions[7]` | `Y = PointOnSegment(A, D, s)` |
| 鏡映による向き固定 | `conditions[0]` | `ay > 0` |
| AB = 4 | `conditions[1]` | `Distance(A, B) = 4` |
| AC = 5 | `conditions[2]` | `Distance(A, C) = 5` |
| acute triangle / 鋭角三角形: 各頂点の内積が正 | `conditions[3]` | `((B.x-A.x)*(C.x-A.x)+(B.y-A.y)*(C.y-A.y)) > 0` |
| acute triangle / 鋭角三角形: 各頂点の内積が正 | `conditions[4]` | `((A.x-B.x)*(C.x-B.x)+(A.y-B.y)*(C.y-B.y)) > 0` |
| acute triangle / 鋭角三角形: 各頂点の内積が正 | `conditions[5]` | `((A.x-C.x)*(B.x-C.x)+(A.y-C.y)*(B.y-C.y)) > 0` |
| X strictly between D and E | `conditions[6]` | `t > 0` |
| X strictly between D and E | `conditions[7]` | `t < 1` |
| Y on segment AD | `conditions[8]` | `s >= 0` |
| Y on segment AD | `conditions[9]` | `s <= 1` |
| XY parallel AO | `conditions[10]` | `Parallel(Line(X, Y), Line(A, O)) = 0` |
| YO perpendicular AX | `conditions[11]` | `Perpendicular(Line(Y, O), Line(A, X)) = 0` |
| line AOが定義される | `conditions[12]` | `Distance(A, O) > 0` |
| between D and E / 区間非退化 | `conditions[13]` | `Distance(D, E) > 0` |
| line XYが定義される | `conditions[14]` | `Distance(X, Y) > 0` |
| line YOが定義される | `conditions[15]` | `Distance(Y, O) > 0` |
| Determine BX | `target` | `Distance(B, X)` |

## 残る制約

公式原本との照合、独立の意味監査、数値的実行可能性・一意性の確認は未実施。

AST検査の合格は幾何条件の同値性・実行可能性・一意性を保証しない。


---

# HMMT-2015-FEB-GUTS-02 原文→入力対応カード

状態: **暫定候補・公式番号/答え未照合・数値検証未実施**。

- 保存資料: `jssa/strategy/astra-consult-14/E/e2h-rows.jsonl` / eval / row_idx=2060
- 原文SHA-256: `f460d44625ecd7b7c1e51d241b61110efae41021eaa362a5069ea5766a52b463`
- 入力SHA-256（JSONファイルの全bytes）: `5ff4313c102fe91dbeafbf9e5df8d2554ac4a8a823c4ab435798a877a79c9778`
- 座標固定・同値性: A=(0,0), B=(1,0)。凸多角形の向きを鏡映で反時計回りにする。
- 分枝・非退化: 下表のguardと構成の定義域を使用。根番号による選択なし。
- 公式答え: 本カードには含めず、`official_answers.jsonl` の状態を参照。採否と入力に答えを使用していない。

## 手元の原文（保存資料）

Let $A B C D E$ be a convex pentagon such that $\angle A B C=\angle A C D=\angle A D E=90^{\circ}$ and $A B=B C=$ $C D=D E=1$. Compute $A E$.

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| AB = 1 / 座標原点 | `constructions[0]` | `A = Point(0, 0)` |
| AB = 1 | `constructions[1]` | `B = Point(1, 0)` |
| convex pentagon ABCDE / 未知点 | `constructions[2]` | `C = Point(cx, cy)` |
| convex pentagon ABCDE / 未知点 | `constructions[3]` | `D = Point(dx, dy)` |
| convex pentagon ABCDE / 未知点 | `constructions[4]` | `E = Point(ex, ey)` |
| angle ABC = 90 degrees | `conditions[0]` | `Perpendicular(Line(A, B), Line(B, C)) = 0` |
| angle ACD = 90 degrees | `conditions[1]` | `Perpendicular(Line(A, C), Line(C, D)) = 0` |
| angle ADE = 90 degrees | `conditions[2]` | `Perpendicular(Line(A, D), Line(D, E)) = 0` |
| BC = 1 | `conditions[3]` | `Distance(B, C) = 1` |
| CD = 1 | `conditions[4]` | `Distance(C, D) = 1` |
| DE = 1 | `conditions[5]` | `Distance(D, E) = 1` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[6]` | `((B.x-A.x)*(C.y-A.y)-(B.y-A.y)*(C.x-A.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[7]` | `((B.x-A.x)*(D.y-A.y)-(B.y-A.y)*(D.x-A.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[8]` | `((B.x-A.x)*(E.y-A.y)-(B.y-A.y)*(E.x-A.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[9]` | `((C.x-B.x)*(A.y-B.y)-(C.y-B.y)*(A.x-B.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[10]` | `((C.x-B.x)*(D.y-B.y)-(C.y-B.y)*(D.x-B.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[11]` | `((C.x-B.x)*(E.y-B.y)-(C.y-B.y)*(E.x-B.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[12]` | `((D.x-C.x)*(A.y-C.y)-(D.y-C.y)*(A.x-C.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[13]` | `((D.x-C.x)*(B.y-C.y)-(D.y-C.y)*(B.x-C.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[14]` | `((D.x-C.x)*(E.y-C.y)-(D.y-C.y)*(E.x-C.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[15]` | `((E.x-D.x)*(A.y-D.y)-(E.y-D.y)*(A.x-D.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[16]` | `((E.x-D.x)*(B.y-D.y)-(E.y-D.y)*(B.x-D.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[17]` | `((E.x-D.x)*(C.y-D.y)-(E.y-D.y)*(C.x-D.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[18]` | `((A.x-E.x)*(B.y-E.y)-(A.y-E.y)*(B.x-E.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[19]` | `((A.x-E.x)*(C.y-E.y)-(A.y-E.y)*(C.x-E.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[20]` | `((A.x-E.x)*(D.y-E.y)-(A.y-E.y)*(D.x-E.x)) > 0` |
| Compute AE | `target` | `Distance(A, E)` |

## 残る制約

公式原本との照合、独立の意味監査、数値的実行可能性・一意性の確認は未実施。

AST検査の合格は幾何条件の同値性・実行可能性・一意性を保証しない。


---

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


---

# HMMT-2016-FEB-GUTS-03 原文→入力対応カード

状態: **暫定候補・公式番号/答え未照合・数値検証未実施**。

- 保存資料: `jssa/strategy/astra-consult-14/E/e2h-rows.jsonl` / eval / row_idx=317
- 原文SHA-256: `e1ec215f55fea15321ed2b0ac7b8cce58d47d08e665a49ab9ab06d85d42225dc`
- 入力SHA-256（JSONファイルの全bytes）: `d1fb9bf24c8b4e78a6942569cabce083a685e37b5d646c5b7478d8ebce09e0b7`
- 座標固定・同値性: 円の中心を原点、P=(1,0)。鏡映で頂点を反時計回り。半径1は原文。
- 分枝・非退化: 下表のguardと構成の定義域を使用。根番号による選択なし。
- 公式答え: 本カードには含めず、`official_answers.jsonl` の状態を参照。採否と入力に答えを使用していない。

## 手元の原文（保存資料）

Let $P R O B L E M Z$ be a regular octagon inscribed in a circle of unit radius. Diagonals $M R, O Z$ meet at $I$. Compute $L I$.

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| regular octagon PROBLEMZ on unit circle / 頂点順と中心角の定義 | `constructions[0]` | `P = Point(cos(0*pi/4), sin(0*pi/4))` |
| regular octagon PROBLEMZ on unit circle / 頂点順と中心角の定義 | `constructions[1]` | `R = Point(cos(1*pi/4), sin(1*pi/4))` |
| regular octagon PROBLEMZ on unit circle / 頂点順と中心角の定義 | `constructions[2]` | `O = Point(cos(2*pi/4), sin(2*pi/4))` |
| regular octagon PROBLEMZ on unit circle / 頂点順と中心角の定義 | `constructions[3]` | `B = Point(cos(3*pi/4), sin(3*pi/4))` |
| regular octagon PROBLEMZ on unit circle / 頂点順と中心角の定義 | `constructions[4]` | `L = Point(cos(4*pi/4), sin(4*pi/4))` |
| regular octagon PROBLEMZ on unit circle / 頂点順と中心角の定義 | `constructions[5]` | `E = Point(cos(5*pi/4), sin(5*pi/4))` |
| regular octagon PROBLEMZ on unit circle / 頂点順と中心角の定義 | `constructions[6]` | `M = Point(cos(6*pi/4), sin(6*pi/4))` |
| regular octagon PROBLEMZ on unit circle / 頂点順と中心角の定義 | `constructions[7]` | `Z = Point(cos(7*pi/4), sin(7*pi/4))` |
| diagonals MR and OZ meet at I | `constructions[8]` | `I = Intersect(Line(M, R), Line(O, Z))` |
| Compute LI | `target` | `Distance(L, I)` |

## 残る制約

変数0も選定から除かない。頂点は正八角形の定義であって、解答の座標ではない。文字Oは頂点。

AST検査の合格は幾何条件の同値性・実行可能性・一意性を保証しない。


---

# HMMT-2016-FEB-TEAM-03 原文→入力対応カード

状態: **暫定候補・公式番号/答え未照合・数値検証未実施**。

- 保存資料: `jssa/strategy/astra-consult-14/E/e2h-rows.jsonl` / train / row_idx=457
- 原文SHA-256: `769b42bd36650e9b2b05a915c6eaa28b2b9a06afa02369fe8fb32da04dfbd1e7`
- 入力SHA-256（JSONファイルの全bytes）: `951d79daa648bf6ccf00fbd7068152c0830a11584c6867208a1604a7d3aad7fe`
- 座標固定・同値性: B=(0,0), C=(144,0), ay>0。合同移動のみ。
- 分枝・非退化: 下表のguardと構成の定義域を使用。根番号による選択なし。
- 公式答え: 本カードには含めず、`official_answers.jsonl` の状態を参照。採否と入力に答えを使用していない。

## 手元の原文（保存資料）

Let $A B C$ be an acute triangle with incenter $I$ and circumcenter $O$. Assume that $\angle O I A=90^{\circ}$. Given that $A I=97$ and $B C=144$, compute the area of $\triangle A B C$.

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| BC = 144 / 座標原点 | `constructions[0]` | `B = Point(0, 0)` |
| BC = 144 | `constructions[1]` | `C = Point(144, 0)` |
| acute triangle ABC / 未知頂点 | `constructions[2]` | `A = Point(ax, ay)` |
| incenter I | `constructions[3]` | `I = Incenter(A, B, C)` |
| circumcenter O | `constructions[4]` | `O = Circumcenter(A, B, C)` |
| 鏡映による向き固定 | `conditions[0]` | `ay > 0` |
| acute triangle / 鋭角三角形: 各頂点の内積が正 | `conditions[1]` | `((B.x-A.x)*(C.x-A.x)+(B.y-A.y)*(C.y-A.y)) > 0` |
| acute triangle / 鋭角三角形: 各頂点の内積が正 | `conditions[2]` | `((A.x-B.x)*(C.x-B.x)+(A.y-B.y)*(C.y-B.y)) > 0` |
| acute triangle / 鋭角三角形: 各頂点の内積が正 | `conditions[3]` | `((A.x-C.x)*(B.x-C.x)+(A.y-C.y)*(B.y-C.y)) > 0` |
| AI = 97 | `conditions[4]` | `Distance(A, I) = 97` |
| angle OIA = 90 degrees | `conditions[5]` | `Perpendicular(Line(O, I), Line(A, I)) = 0` |
| angle OIAが定義される / OとIは相異なる | `conditions[6]` | `Distance(O, I) > 0` |
| Compute area ABC | `target` | `Area(A, B, C)` |

## 残る制約

公式原本との照合、独立の意味監査、数値的実行可能性・一意性の確認は未実施。

AST検査の合格は幾何条件の同値性・実行可能性・一意性を保証しない。


---

# HMMT-2016-FEB-GUTS-10 原文→入力対応カード

状態: **暫定候補・公式番号/答え未照合・数値検証未実施**。

- 保存資料: `jssa/strategy/astra-consult-14/E/e2h-rows.jsonl` / eval / row_idx=1486
- 原文SHA-256: `8ce9ea19008557446d595303bdc0a54bb39f7e8cdbd52bdaca29154975abfe62`
- 入力SHA-256（JSONファイルの全bytes）: `689c97d307e6a8f035ae7827493a0c4871d0f4b245094c4aea3ec1e01ca56ed7`
- 座標固定・同値性: B=(0,0), C=(14,0), ay>0。合同移動のみ。
- 分枝・非退化: 下表のguardと構成の定義域を使用。根番号による選択なし。
- 公式答え: 本カードには含めず、`official_answers.jsonl` の状態を参照。採否と入力に答えを使用していない。

## 手元の原文（保存資料）

Let $A B C$ be a triangle with $A B=13, B C=14, C A=15$. Let $O$ be the circumcenter of $A B C$. Find the distance between the circumcenters of triangles $A O B$ and $A O C$.

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| BC = 14 / 座標原点 | `constructions[0]` | `B = Point(0, 0)` |
| BC = 14 | `constructions[1]` | `C = Point(14, 0)` |
| triangle ABC / 未知頂点 | `constructions[2]` | `A = Point(ax, ay)` |
| circumcenter O of ABC | `constructions[3]` | `O = Circumcenter(A, B, C)` |
| circumcenter of AOB | `constructions[4]` | `U = Circumcenter(A, O, B)` |
| circumcenter of AOC | `constructions[5]` | `V = Circumcenter(A, O, C)` |
| 鏡映による向き固定 | `conditions[0]` | `ay > 0` |
| AB = 13 | `conditions[1]` | `Distance(A, B) = 13` |
| CA = 15 | `conditions[2]` | `Distance(A, C) = 15` |
| triangle AOB has a circumcenter | `conditions[3]` | `Area(A, O, B) > 0` |
| triangle AOC has a circumcenter | `conditions[4]` | `Area(A, O, C) > 0` |
| distance between the two circumcenters | `target` | `Distance(U, V)` |

## 残る制約

公式原本との照合、独立の意味監査、数値的実行可能性・一意性の確認は未実施。

AST検査の合格は幾何条件の同値性・実行可能性・一意性を保証しない。


---

# HMMT-2017-FEB-GUTS-06 原文→入力対応カード

状態: **暫定候補・公式番号/答え未照合・数値検証未実施**。

- 保存資料: `jssa/strategy/astra-consult-14/E/e2h-rows.jsonl` / eval / row_idx=144
- 原文SHA-256: `6088e1b39c35b300c4f34f2713d099a015008203c8b928aaa05a488848e601cd`
- 入力SHA-256（JSONファイルの全bytes）: `651c1227a28e07084cd971dbfe1b27f2d4ad4e290b1152c3465bd6ad2baafb32`
- 座標固定・同値性: A=(0,0), C=(7,0)。合同移動と鏡映による凸四角形の向き固定のみ。図の自由度は残す。
- 分枝・非退化: 下表のguardと構成の定義域を使用。根番号による選択なし。
- 公式答え: 本カードには含めず、`official_answers.jsonl` の状態を参照。採否と入力に答えを使用していない。

## 手元の原文（保存資料）

Let $A B C D$ be a convex quadrilateral with $A C=7$ and $B D=17$. Let $M, P, N, Q$ be the midpoints of sides $A B, B C, C D, D A$ respectively. Compute $M N^{2}+P Q^{2}$

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| AC = 7 / 座標原点 | `constructions[0]` | `A = Point(0, 0)` |
| AC = 7 | `constructions[1]` | `C = Point(7, 0)` |
| convex quadrilateral ABCD / 未知点 | `constructions[2]` | `B = Point(bx, by)` |
| convex quadrilateral ABCD / 未知点 | `constructions[3]` | `D = Point(dx, dy)` |
| M midpoint of AB | `constructions[4]` | `M = Midpoint(A, B)` |
| P midpoint of BC | `constructions[5]` | `P = Midpoint(B, C)` |
| N midpoint of CD | `constructions[6]` | `N = Midpoint(C, D)` |
| Q midpoint of DA | `constructions[7]` | `Q = Midpoint(D, A)` |
| BD = 17 | `conditions[0]` | `Distance(B, D) = 17` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[1]` | `((B.x-A.x)*(C.y-A.y)-(B.y-A.y)*(C.x-A.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[2]` | `((B.x-A.x)*(D.y-A.y)-(B.y-A.y)*(D.x-A.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[3]` | `((C.x-B.x)*(A.y-B.y)-(C.y-B.y)*(A.x-B.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[4]` | `((C.x-B.x)*(D.y-B.y)-(C.y-B.y)*(D.x-B.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[5]` | `((D.x-C.x)*(A.y-C.y)-(D.y-C.y)*(A.x-C.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[6]` | `((D.x-C.x)*(B.y-C.y)-(D.y-C.y)*(B.x-C.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[7]` | `((A.x-D.x)*(B.y-D.y)-(A.y-D.y)*(B.x-D.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[8]` | `((A.x-D.x)*(C.y-D.y)-(A.y-D.y)*(C.x-D.x)) > 0` |
| Compute MN^2 + PQ^2 | `target` | `Distance(M, N)**2 + Distance(P, Q)**2` |

## 残る制約

公式原本との照合、独立の意味監査、数値的実行可能性・一意性の確認は未実施。

AST検査の合格は幾何条件の同値性・実行可能性・一意性を保証しない。


---

# HMMT-2020-FEB-GUTS-02 原文→入力対応カード

状態: **暫定候補・公式番号/答え未照合・数値検証未実施**。

- 保存資料: `jssa/strategy/astra-consult-14/E/e2h-rows.jsonl` / eval / row_idx=2086
- 原文SHA-256: `51dcf0322958169634a8779ddd29cb3b9f63c1393827eb6bf335f6a3e566c017`
- 入力SHA-256（JSONファイルの全bytes）: `b712d9961fa8ad073e5c9aca81073ecb16f238b830b253f9a881a9f047d823d6`
- 座標固定・同値性: 絶対長の指定がなく目標は角度なので半径1に相似正規化。O原点、回転でM=(1,0)。鏡映枝は両方残す。
- 分枝・非退化: 下表のguardと構成の定義域を使用。根番号による選択なし。
- 公式答え: 本カードには含めず、`official_answers.jsonl` の状態を参照。採否と入力に答えを使用していない。

## 手元の原文（保存資料）

Let $A B C$ be a triangle and $\omega$ be its circumcircle. The point $M$ is the midpoint of arc $B C$ not containing $A$ on $\omega$ and $D$ is chosen so that $D M$ is tangent to $\omega$ and is on the same side of $A M$ as $C$. It is given that $A M=A C$ and $\angle D M C=38^{\circ}$. Find the measure of angle $\angle A C B$.

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| circumcircle / 中心を原点 | `constructions[0]` | `O = Point(0, 0)` |
| circumcircle / 相似正規化 | `constructions[1]` | `omega = Circle(O, 1)` |
| arc midpoint M / 回転でMを固定 | `constructions[2]` | `M = Point(1, 0)` |
| A on circumcircle | `constructions[3]` | `A = Point(ax, ay)` |
| B on circumcircle | `constructions[4]` | `B = Point(bx, by)` |
| C on circumcircle | `constructions[5]` | `C = Point(cx, cy)` |
| DM tangent at M / 単位円のMでの接線上の点 | `constructions[6]` | `D = Point(1, dy)` |
| A on circumcircle | `conditions[0]` | `OnCircle(A, omega) = 0` |
| B on circumcircle | `conditions[1]` | `OnCircle(B, omega) = 0` |
| C on circumcircle | `conditions[2]` | `OnCircle(C, omega) = 0` |
| M midpoint of arc BC / 両端への弦長が等しい | `conditions[3]` | `Distance(M, B) = Distance(M, C)` |
| arc BC not containing A / AとMは弦BCの反対側 | `conditions[4]` | `((C.x-B.x)*(A.y-B.y)-(C.y-B.y)*(A.x-B.x))*((C.x-B.x)*(M.y-B.y)-(C.y-B.y)*(M.x-B.x)) < 0` |
| AM = AC | `conditions[5]` | `Distance(A, M) = Distance(A, C)` |
| angle DMC = 38 degrees | `conditions[6]` | `Angle(D, M, C) = 38*pi/180` |
| D and C on same side of AM | `conditions[7]` | `((M.x-A.x)*(D.y-A.y)-(M.y-A.y)*(D.x-A.x))*((M.x-A.x)*(C.y-A.y)-(M.y-A.y)*(C.x-A.x)) > 0` |
| nondegenerate triangle ABC | `conditions[8]` | `Area(A, B, C) > 0` |
| line AMが定義される | `conditions[9]` | `Distance(A, M) > 0` |
| arc midpoint distinct from endpoints | `conditions[10]` | `Distance(B, M) > 0` |
| arc midpoint distinct from endpoints | `conditions[11]` | `Distance(C, M) > 0` |
| angle DMCが定義される | `conditions[12]` | `Distance(D, M) > 0` |
| measure angle ACB / 度単位 | `target` | `Degrees(Angle(A, C, B))` |

## 残る制約

公式原本との照合、独立の意味監査、数値的実行可能性・一意性の確認は未実施。

AST検査の合格は幾何条件の同値性・実行可能性・一意性を保証しない。


---

# HMMT-2021-FEB-GUTS-03 原文→入力対応カード

状態: **暫定候補・公式番号/答え未照合・数値検証未実施**。

- 保存資料: `jssa/strategy/astra-consult-14/E/e2h-rows.jsonl` / eval / row_idx=2382
- 原文SHA-256: `c98b18c4b323e70ab9011f2149c5b0ed95e7e7a108adc0cfcdb64cf52dfc18ee`
- 入力SHA-256（JSONファイルの全bytes）: `d3b5dc0fb2f2d5822e45c8fabb253d8041ced67d2c4bfc21d6811f28da15cd53`
- 座標固定・同値性: O原点、OAを正x軸、半円を鏡映で上側。半径2021は保持。
- 分枝・非退化: 下表のguardと構成の定義域を使用。根番号による選択なし。
- 公式答え: 本カードには含めず、`official_answers.jsonl` の状態を参照。採否と入力に答えを使用していない。

## 手元の原文（保存資料）

A semicircle with radius 2021 has diameter $A B$ and center $O$. Points $C$ and $D$ lie on the semicircle such that $\angle A O C<\angle A O D=90^{\circ}$. A circle of radius $r$ is inscribed in the sector bounded by $O A$ and $O C$ and is tangent to the semicircle at $E$. If $C D=C E$, compute $\lfloor r\rfloor$.

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| center O | `constructions[0]` | `O = Point(0, 0)` |
| radius 2021 / OAを正x軸 | `constructions[1]` | `A = Point(2021, 0)` |
| diameter AB | `constructions[2]` | `B = Point(-2021, 0)` |
| angle AOD = 90 degrees | `constructions[3]` | `D = Point(0, 2021)` |
| C on semicircle / 未知点 | `constructions[4]` | `C = Point(cx, cy)` |
| center of the inscribed circle / 補助未知点 | `constructions[5]` | `J = Point(jx, jy)` |
| circle of radius r inscribed in sector AOC | `constructions[6]` | `small = Circle(J, r)` |
| internal tangency E / 中心線OJ上の大円との接点 | `constructions[7]` | `E = Point(2021*jx/Distance(O, J), 2021*jy/Distance(O, J))` |
| C on semicircle radius 2021 | `conditions[0]` | `Distance(O, C) = 2021` |
| angle AOC < 90 degrees | `conditions[1]` | `cx > 0` |
| nondegenerate sector on chosen upper semicircle | `conditions[2]` | `cy > 0` |
| positive radius of inscribed circle | `conditions[3]` | `r > 0` |
| tangency to ray OA / 垂足が正の半直線上 | `conditions[4]` | `jx > 0` |
| tangent to OA from inside sector / 上半平面 | `conditions[5]` | `jy = r` |
| tangent to OC from sector interior / 内向き符号付き距離 | `conditions[6]` | `cy*jx-cx*jy = 2021*r` |
| internal tangency to semicircle | `conditions[7]` | `Distance(O, J) + r = 2021` |
| unique tangency point E is defined | `conditions[8]` | `Distance(O, J) > 0` |
| CD = CE | `conditions[9]` | `Distance(C, D) = Distance(C, E)` |
| Compute floor(r) | `target` | `r // 1` |

## 残る制約

接円の二つの線への接条件と内接接条件は原文の定義。rの解を導いていない。床関数は目標だけ。

AST検査の合格は幾何条件の同値性・実行可能性・一意性を保証しない。


---

# HMMT-2021-FEB-GUTS-09 原文→入力対応カード

状態: **暫定候補・公式番号/答え未照合・数値検証未実施**。

- 保存資料: `jssa/strategy/astra-consult-14/E/e2h-rows.jsonl` / eval / row_idx=2629
- 原文SHA-256: `db6fb259ac58205255ec7e064843f935513fb9c75bdbadfd226805e4341ea116`
- 入力SHA-256（JSONファイルの全bytes）: `78a43411f568b7c8ce022dae1c310b372d6b1b9598398b61abc7d39ab051e48c`
- 座標固定・同値性: 共通中点を原点、ADをx軸、Aを正側。合同移動だけ。B,Cの向きは条件で定め鏡映は残す。
- 分枝・非退化: 下表のguardと構成の定義域を使用。根番号による選択なし。
- 公式答え: 本カードには含めず、`official_answers.jsonl` の状態を参照。採否と入力に答えを使用していない。

## 手元の原文（保存資料）

Let $A D, B E$, and $C F$ be segments sharing a common midpoint, with $A B<A E$ and $B C<B F$. Suppose that each pair of segments forms a $60^{\circ}$ angle, and that $A D=7, B E=10$, and $C F=18$. Let $K$ denote the sum of the areas of the six triangles $\triangle A B C, \triangle B C D, \triangle C D E, \triangle D E F, \triangle E F A$, and $\triangle F A B$. Compute $K \sqrt{3}$.

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| common midpoint of AD, BE, CF | `constructions[0]` | `O = Point(0, 0)` |
| AD = 7 | `constructions[1]` | `A = Point(7/2, 0)` |
| AD = 7 and midpoint O | `constructions[2]` | `D = Point(-7/2, 0)` |
| BE = 10 / 未知端点 | `constructions[3]` | `B = Point(bx, by)` |
| BE midpoint O | `constructions[4]` | `E = Point(-bx, -by)` |
| CF = 18 / 未知端点 | `constructions[5]` | `C = Point(cx, cy)` |
| CF midpoint O | `constructions[6]` | `F = Point(-cx, -cy)` |
| BE = 10 | `conditions[0]` | `Distance(B, E) = 10` |
| CF = 18 | `conditions[1]` | `Distance(C, F) = 18` |
| AD and BE form 60 degrees / 無向直線のcos^2=1/4 | `conditions[2]` | `4*bx**2 = bx**2+by**2` |
| AD and CF form 60 degrees / 無向直線のcos^2=1/4 | `conditions[3]` | `4*cx**2 = cx**2+cy**2` |
| BE and CF form 60 degrees | `conditions[4]` | `4*(bx*cx+by*cy)**2 = (bx**2+by**2)*(cx**2+cy**2)` |
| AB < AE | `conditions[5]` | `Distance(A, B) < Distance(A, E)` |
| BC < BF | `conditions[6]` | `Distance(B, C) < Distance(B, F)` |
| K is the sum of the six stated triangle areas; compute K*sqrt(3) | `target` | `sqrt(3)*(Area(A, B, C)+Area(B, C, D)+Area(C, D, E)+Area(D, E, F)+Area(E, F, A)+Area(F, A, B))` |

## 残る制約

公式原本との照合、独立の意味監査、数値的実行可能性・一意性の確認は未実施。

AST検査の合格は幾何条件の同値性・実行可能性・一意性を保証しない。


---

# HMMT-2022-FEB-GUTS-01 原文→入力対応カード

状態: **暫定候補・公式番号/答え未照合・数値検証未実施**。

- 保存資料: `jssa/strategy/astra-consult-14/E/e2h-rows.jsonl` / eval / row_idx=1167
- 原文SHA-256: `51f385517d2f1f8955901a22faa1d8bc1024ed5ff6cac93de531bde2c52f98a2`
- 入力SHA-256（JSONファイルの全bytes）: `245ebd5d0cb564e7a429242f303e3ad0f92a8fc4b1da4ddb0d16cd6b6c37faba`
- 座標固定・同値性: 中心原点、Pを正x軸。鏡映で隣頂点を上側。絶対周長6.28は有理数157/25で保持。
- 分枝・非退化: 下表のguardと構成の定義域を使用。根番号による選択なし。
- 公式答え: 本カードには含めず、`official_answers.jsonl` の状態を参照。採否と入力に答えを使用していない。

## 手元の原文（保存資料）

A regular 2022-gon has perimeter 6.28. To the nearest positive integer, compute the area of the 2022-gon.

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| regular 2022-gon / 中心 | `constructions[0]` | `O = Point(0, 0)` |
| regular 2022-gon / 一頂点 | `constructions[1]` | `P = Point(r, 0)` |
| regular 2022-gon / 隣の頂点、中心角の定義 | `constructions[2]` | `Q = Point(r*cos(2*pi/2022), r*sin(2*pi/2022))` |
| positive circumradius | `conditions[0]` | `r > 0` |
| perimeter 6.28 / 同長の2022辺の和 | `conditions[1]` | `2022*Distance(P, Q) = 157/25` |
| area to nearest positive integer / 中心から2022枚に分割して面積を加算 | `target` | `(2022*Area(O, P, Q)+1/2) // 1` |

## 残る制約

2022個の等しい中心三角形という正多角形の定義的分割。最適化や解答由来の式は使わない。

AST検査の合格は幾何条件の同値性・実行可能性・一意性を保証しない。


---

# HMMT-2022-FEB-TEAM-03 原文→入力対応カード

状態: **暫定候補・公式番号/答え未照合・数値検証未実施**。

- 保存資料: `jssa/strategy/astra-consult-14/E/e2h-rows.jsonl` / eval / row_idx=31
- 原文SHA-256: `de69cda4c071d7be5bcb638aaed3e3e2d1ef480d3dd791da493bef6cdd50c4b1`
- 入力SHA-256（JSONファイルの全bytes）: `cbebab77bf813e4d823a774e9aa54262871a1aede013a8997ace0557c51058c8`
- 座標固定・同値性: 原問の長さはRのみで全条件が相似不変。半径を1、O原点、A=(1,0)。鏡映は残す。
- 分枝・非退化: 下表のguardと構成の定義域を使用。根番号による選択なし。
- 公式答え: 本カードには含めず、`official_answers.jsonl` の状態を参照。採否と入力に答えを使用していない。

## 手元の原文（保存資料）

Let triangle $A B C$ be an acute triangle with circumcircle $\Gamma$. Let $X$ and $Y$ be the midpoints of minor arcs $\widehat{A B}$ and $\widehat{A C}$ of $\Gamma$, respectively. If line $X Y$ is tangent to the incircle of triangle $A B C$ and the radius of $\Gamma$ is $R$, find, with proof, the value of $X Y$ in terms of $R$.

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| circumcircle center / 相似正規化 | `constructions[0]` | `O = Point(0, 0)` |
| circumradius R=1 | `constructions[1]` | `Gamma = Circle(O, 1)` |
| A on Gamma / 回転固定 | `constructions[2]` | `A = Point(1, 0)` |
| B on Gamma | `constructions[3]` | `B = Point(bx, by)` |
| C on Gamma | `constructions[4]` | `C = Point(cx, cy)` |
| minor arc AB midpoint / 弦中点の方向 | `constructions[5]` | `U = Midpoint(A, B)` |
| minor arc AC midpoint / 弦中点の方向 | `constructions[6]` | `V = Midpoint(A, C)` |
| X midpoint of minor arc AB / 弦中点方向を円へ延長 | `constructions[7]` | `X = Point(U.x/Distance(O, U), U.y/Distance(O, U))` |
| Y midpoint of minor arc AC | `constructions[8]` | `Y = Point(V.x/Distance(O, V), V.y/Distance(O, V))` |
| incircle of ABC | `constructions[9]` | `omega = Incircle(A, B, C)` |
| B on circumcircle | `conditions[0]` | `OnCircle(B, Gamma) = 0` |
| C on circumcircle | `conditions[1]` | `OnCircle(C, Gamma) = 0` |
| nondegenerate triangle ABC | `conditions[2]` | `Area(A, B, C) > 0` |
| acute triangle / 鋭角三角形: 各頂点の内積が正 | `conditions[3]` | `((B.x-A.x)*(C.x-A.x)+(B.y-A.y)*(C.y-A.y)) > 0` |
| acute triangle / 鋭角三角形: 各頂点の内積が正 | `conditions[4]` | `((A.x-B.x)*(C.x-B.x)+(A.y-B.y)*(C.y-B.y)) > 0` |
| acute triangle / 鋭角三角形: 各頂点の内積が正 | `conditions[5]` | `((A.x-C.x)*(B.x-C.x)+(A.y-C.y)*(B.y-C.y)) > 0` |
| minor arc midpoint defined / AB not a diameter | `conditions[6]` | `Distance(O, U) > 0` |
| minor arc midpoint defined / AC not a diameter | `conditions[7]` | `Distance(O, V) > 0` |
| line XY is defined | `conditions[8]` | `Distance(X, Y) > 0` |
| XY tangent to incircle | `conditions[9]` | `IsTangent(Line(X, Y), omega) = 0` |
| XY in terms of R / R=1で係数XY/Rを問う | `target` | `Distance(X, Y)` |

## 残る制約

係数から原問の長さはR倍で復元する。公式答えの係数変換は未実施。

AST検査の合格は幾何条件の同値性・実行可能性・一意性を保証しない。


---

# HMMT-2022-FEB-GEO-07 原文→入力対応カード

状態: **暫定候補・公式番号/答え未照合・数値検証未実施**。

- 保存資料: `/home/kabatan/work/solver-research-assets/corpus97-sources/hmmt-2022-geo-problems.txt` / saved_pdf_text / row_idx=7
- 原文表記: PDF第1ページ画像を目視し、抽出で崩れた根号・分数をASCII表記で転記。raw_excerptも保持。
- 原文SHA-256: `d8a8dfbf740166536807bb3f2ce312ea5f842342c76827ae21c56062f885394c`
- 入力SHA-256（JSONファイルの全bytes）: `243b7dec3e96f2a9eed6ba61a8246b4ed9cec9257a71c9bce2a20e42da15ac84`
- 座標固定・同値性: A=(0,0), B=(10,0), 正方形を上側。合同移動のみ。
- 分枝・非退化: 下表のguardと構成の定義域を使用。根番号による選択なし。
- 公式答え: 本カードには含めず、`official_answers.jsonl` の状態を参照。採否と入力に答えを使用していない。

## 手元の原文（保存資料）

Point P is located inside a square ABCD of side length 10. Let O1, O2, O3, O4 be the circumcenters of PAB, PBC, PCD, and PDA, respectively. Given that PA + PB + PC + PD = 23 sqrt(2) and the area of O1O2O3O4 is 50, the second largest of the lengths O1O2, O2O3, O3O4, O4O1 can be written as sqrt(a/b), where a and b are relatively prime positive integers. Compute 100a + b.

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| square ABCD of side 10 | `constructions[0]` | `A = Point(0, 0)` |
| square ABCD of side 10 | `constructions[1]` | `B = Point(10, 0)` |
| square ABCD of side 10 | `constructions[2]` | `C = Point(10, 10)` |
| square ABCD of side 10 | `constructions[3]` | `D = Point(0, 10)` |
| P inside square | `constructions[4]` | `P = Point(x, y)` |
| circumcenter of PAB | `constructions[5]` | `O1 = Circumcenter(P, A, B)` |
| circumcenter of PBC | `constructions[6]` | `O2 = Circumcenter(P, B, C)` |
| circumcenter of PCD | `constructions[7]` | `O3 = Circumcenter(P, C, D)` |
| circumcenter of PDA | `constructions[8]` | `O4 = Circumcenter(P, D, A)` |
| P strictly inside square | `conditions[0]` | `x > 0` |
| P strictly inside square | `conditions[1]` | `x < 10` |
| P strictly inside square | `conditions[2]` | `y > 0` |
| P strictly inside square | `conditions[3]` | `y < 10` |
| PA+PB+PC+PD = 23 sqrt(2) | `conditions[4]` | `Distance(P,A)+Distance(P,B)+Distance(P,C)+Distance(P,D) = 23*sqrt(2)` |
| area O1O2O3O4 = 50 | `conditions[5]` | `Area(O1, O2, O3, O4) = 50` |
| second largest length is sqrt(a/b) / 全6組のminのmaxが2番目に大きい値 | `conditions[6]` | `(max([min(Distance(O1, O2), Distance(O2, O3)), min(Distance(O1, O2), Distance(O3, O4)), min(Distance(O1, O2), Distance(O4, O1)), min(Distance(O2, O3), Distance(O3, O4)), min(Distance(O2, O3), Distance(O4, O1)), min(Distance(O3, O4), Distance(O4, O1))]))**2 = a/b` |
| a,bは正整数、h,kは既約性の整数証人 | `conditions[7]` | `IsInteger(a) = 0` |
| a,bは正整数、h,kは既約性の整数証人 | `conditions[8]` | `IsInteger(b) = 0` |
| a,bは正整数、h,kは既約性の整数証人 | `conditions[9]` | `IsInteger(h) = 0` |
| a,bは正整数、h,kは既約性の整数証人 | `conditions[10]` | `IsInteger(k) = 0` |
| positive integer numerator | `conditions[11]` | `a > 0` |
| positive integer denominator | `conditions[12]` | `b > 0` |
| a,b are relatively prime / Bezoutの同値な定義的条件 | `conditions[13]` | `h*a+k*b = 1` |
| Compute 100a+b | `target` | `100*a+b` |

## 残る制約

整数補助変数は既約分数という原問の出力指定を保持するため。探索しやすさでは採否を決めない。PDF画像で根号と分数を確認。

AST検査の合格は幾何条件の同値性・実行可能性・一意性を保証しない。


---

# HMMT-2022-FEB-GEO-08 原文→入力対応カード

状態: **暫定候補・公式番号/答え未照合・数値検証未実施**。

- 保存資料: `/home/kabatan/work/solver-research-assets/corpus97-sources/hmmt-2022-geo-problems.txt` / saved_pdf_text / row_idx=8
- 原文SHA-256: `9239d35d4984e1860bd60e38ec3cf8eecf2093151d5f70ade74e5b48e290ad4a`
- 入力SHA-256（JSONファイルの全bytes）: `044153464a2f3a8ac6eb0310f7b741815cee84f0f026b672229f7f07d804e078`
- 座標固定・同値性: 楕円の中心を原点、長軸をx軸、Aを負側。合同移動と鏡映のみ。長短軸の指定50,14を保持。
- 分枝・非退化: 下表のguardと構成の定義域を使用。根番号による選択なし。
- 公式答え: 本カードには含めず、`official_answers.jsonl` の状態を参照。採否と入力に答えを使用していない。

## 手元の原文（保存資料）

Let E be an ellipse with foci A and B. Suppose there exists a parabola P such that
      • P passes through A and B,
      • the focus F of P lies on E,
      • the orthocenter H of △F AB lies on the directrix of P.
    If the major and minor axes of E have lengths 50 and 14, respectively, compute AH 2 + BH 2 .

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| ellipse focus A / 対称中心を原点 | `constructions[0]` | `A = Point(-f, 0)` |
| ellipse focus B | `constructions[1]` | `B = Point(f, 0)` |
| minor axis length 14 / 短軸端点を定義 | `constructions[2]` | `T = Point(0, 7)` |
| focus F of parabola lies on ellipse | `constructions[3]` | `F = Point(fx, fy)` |
| orthocenter H of FAB | `constructions[4]` | `H = Orthocenter(F, A, B)` |
| directrix through H / 未知方向 | `constructions[5]` | `W = Point(H.x+dx, H.y+dy)` |
| H lies on the directrix | `constructions[6]` | `line_d = Line(H, W)` |
| distance from A to directrix | `constructions[7]` | `U = FootOfPerpendicular(A, line_d)` |
| distance from B to directrix | `constructions[8]` | `V = FootOfPerpendicular(B, line_d)` |
| nondegenerate parabola / focus not on directrix | `constructions[9]` | `K = FootOfPerpendicular(F, line_d)` |
| ellipse with major 50 and minor 14 has distinct foci | `conditions[0]` | `f > 0` |
| ellipse definition: distances from short-axis endpoint sum to major-axis length | `conditions[1]` | `Distance(T, A)+Distance(T, B) = 50` |
| F lies on ellipse with foci A,B and major axis 50 | `conditions[2]` | `Distance(F, A)+Distance(F, B) = 50` |
| triangle FAB nondegenerate / 鏡映でFを上側 | `conditions[3]` | `fy > 0` |
| directrix direction is normalized / 表示だけの冗長な尺度を除く | `conditions[4]` | `dx**2+dy**2 = 1` |
| parabola passes through A / 焦点と準線への等距離という定義 | `conditions[5]` | `Distance(A, F) = Distance(A, U)` |
| parabola passes through B | `conditions[6]` | `Distance(B, F) = Distance(B, V)` |
| focus is not on directrix / proper parabola | `conditions[7]` | `Distance(F, K) > 0` |
| Compute AH^2+BH^2 | `target` | `Distance(A, H)**2+Distance(B, H)**2` |

## 残る制約

楕円・放物線の焦点/準線の定義で記述し、解答由来の焦点距離やF,Hの座標は使わない。PDF両ページで原文確認。

AST検査の合格は幾何条件の同値性・実行可能性・一意性を保証しない。


---

# HMMT-2023-FEB-GEO-06 原文→入力対応カード

状態: **暫定候補・公式番号/答え未照合・数値検証未実施**。

- 保存資料: `/home/kabatan/work/solver-research-assets/corpus97-sources/hmmt-2023-geo-problems.txt` / saved_pdf_text / row_idx=6
- 原文SHA-256: `23a1336c0aefdd57ecf374165ad56c3cf0fef07a99b0d33c0e3f3576408469b3`
- 入力SHA-256（JSONファイルの全bytes）: `b878de21b4753343976d47a908b007e1af0de8bcd0a1974bba8f5a88c42aa76b`
- 座標固定・同値性: 絶対長の指定がなく目標が角度なのでAB=1に相似正規化。凸四角形を反時計回りに鏡映。
- 分枝・非退化: 下表のguardと構成の定義域を使用。根番号による選択なし。
- 公式答え: 本カードには含めず、`official_answers.jsonl` の状態を参照。採否と入力に答えを使用していない。

## 手元の原文（保存資料）

Convex quadrilateral ABCD satisfies ∠CAB = ∠ADB = 30◦ , ∠ABD = 77◦ , BC = CD, and
    ∠BCD = n◦ for some positive integer n. Compute n.

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| convex quadrilateral ABCD / 座標原点 | `constructions[0]` | `A = Point(0, 0)` |
| ABを相似正規化 | `constructions[1]` | `B = Point(1, 0)` |
| convex quadrilateral ABCD / 未知点 | `constructions[2]` | `C = Point(cx, cy)` |
| convex quadrilateral ABCD / 未知点 | `constructions[3]` | `D = Point(dx, dy)` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[0]` | `((B.x-A.x)*(C.y-A.y)-(B.y-A.y)*(C.x-A.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[1]` | `((B.x-A.x)*(D.y-A.y)-(B.y-A.y)*(D.x-A.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[2]` | `((C.x-B.x)*(A.y-B.y)-(C.y-B.y)*(A.x-B.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[3]` | `((C.x-B.x)*(D.y-B.y)-(C.y-B.y)*(D.x-B.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[4]` | `((D.x-C.x)*(A.y-C.y)-(D.y-C.y)*(A.x-C.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[5]` | `((D.x-C.x)*(B.y-C.y)-(D.y-C.y)*(B.x-C.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[6]` | `((A.x-D.x)*(B.y-D.y)-(A.y-D.y)*(B.x-D.x)) > 0` |
| convex / 狭義凸: 各辺の他の頂点はすべて内側 | `conditions[7]` | `((A.x-D.x)*(C.y-D.y)-(A.y-D.y)*(C.x-D.x)) > 0` |
| angle CAB = 30 degrees | `conditions[8]` | `Angle(C, A, B) = 30*pi/180` |
| angle ADB = 30 degrees | `conditions[9]` | `Angle(A, D, B) = 30*pi/180` |
| angle ABD = 77 degrees | `conditions[10]` | `Angle(A, B, D) = 77*pi/180` |
| BC = CD | `conditions[11]` | `Distance(B, C) = Distance(C, D)` |
| angle BCD = n degrees | `conditions[12]` | `Angle(B, C, D) = n*pi/180` |
| n is an integer | `conditions[13]` | `IsInteger(n) = 0` |
| n is positive | `conditions[14]` | `n > 0` |
| Compute n | `target` | `n` |

## 残る制約

公式原本との照合、独立の意味監査、数値的実行可能性・一意性の確認は未実施。

AST検査の合格は幾何条件の同値性・実行可能性・一意性を保証しない。


---

# HMMT-2024-FEB-GUTS-06 原文→入力対応カード

状態: **暫定候補・公式番号/答え未照合・数値検証未実施**。

- 保存資料: `jssa/strategy/astra-consult-14/E/e2h-rows.jsonl` / eval / row_idx=1769
- 原文SHA-256: `a1625b938644e95009e53e9c9b7429371c99258859bdbc0f8e1c35f32d13ed11`
- 入力SHA-256（JSONファイルの全bytes）: `b1835a5e644475fabe725fe842dfccbf589f3aa53ee0efaf4b0153004ee35e6a`
- 座標固定・同値性: B=(0,0), C=(1,0), ay>0。P,Qの交換で条件は変わらない。
- 分枝・非退化: 下表のguardと構成の定義域を使用。根番号による選択なし。
- 公式答え: 本カードには含めず、`official_answers.jsonl` の状態を参照。採否と入力に答えを使用していない。

## 手元の原文（保存資料）

In triangle $A B C$, points $M$ and $N$ are the midpoints of $A B$ and $A C$, respectively, and points $P$ and $Q$ trisect $B C$. Given that $A, M, N, P$, and $Q$ lie on a circle and $B C=1$, compute the area of triangle $A B C$.

## 対応

| 原文の条件・定義 | DSL位置 | 入力 |
|---|---|---|
| BC = 1 / 座標原点 | `constructions[0]` | `B = Point(0, 0)` |
| BC = 1 | `constructions[1]` | `C = Point(1, 0)` |
| triangle ABC / 未知頂点 | `constructions[2]` | `A = Point(ax, ay)` |
| M midpoint of AB | `constructions[3]` | `M = Midpoint(A, B)` |
| N midpoint of AC | `constructions[4]` | `N = Midpoint(A, C)` |
| P,Q trisect BC / Bから1/3 | `constructions[5]` | `P = PointOnSegment(B, C, 1/3)` |
| P,Q trisect BC / Bから2/3 | `constructions[6]` | `Q = PointOnSegment(B, C, 2/3)` |
| A,M,N,P,Q lie on a circle / A,P,Qで定義 | `constructions[7]` | `omega = Circumcircle(A, P, Q)` |
| 鏡映による向き固定 / 三角形非退化 | `conditions[0]` | `ay > 0` |
| M on same circle as A,P,Q | `conditions[1]` | `OnCircle(M, omega) = 0` |
| N on same circle as A,P,Q | `conditions[2]` | `OnCircle(N, omega) = 0` |
| Compute area ABC | `target` | `Area(A, B, C)` |

## 残る制約

公式原本との照合、独立の意味監査、数値的実行可能性・一意性の確認は未実施。

AST検査の合格は幾何条件の同値性・実行可能性・一意性を保証しない。
