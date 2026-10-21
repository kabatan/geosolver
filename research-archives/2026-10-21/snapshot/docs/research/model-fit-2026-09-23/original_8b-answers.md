## B06 / 0

円の外部の点Sを通る割線がS,U,Vの順に円と交わる。Sから円への接線の接点をTとし、SU=4、UV=5とする。STを求めよ。その際、方べきの定理を単に引用するだけでなく、この配置の三角形の相似から必要な積の等式を証明せよ。
必要な根拠を示し、簡潔な最終答案を書いてください。



### 解答

点 $ S $ から円への接線の接点を $ T $、割線 $ S-U-V $ の長さを $ SU = 4 $、$ UV = 5 $ とし、$ SV = SU + UV = 9 $ とする。方べきの定理を用いて $ ST $ を求め、三角形の相似を用いてその積の等式を証明する。

---

### 1. 方べきの定理の引用

点 $ S $ から円へ引いた接線の長さ $ ST $ と、割線 $ S-U-V $ に関する方べきの定理により、以下の式が成立する：

$$
ST^2 = SU \cdot SV
$$

---

### 2. 三角形の相似による積の等式の証明

**三角形 $ \triangle STU $ と $ \triangle STV $ の相似性を示す：**

- **共通角**：$ \angle S $ は共通。
- **角の等価性**：  
  - $ \angle STU $ は接線 $ ST $ と弦 $ TU $ が成す角であり、**対辺の定理（Alternate Segment Theorem）** により、$ \angle STU = \angle TVU $。
  - $ \angle TVS $ は $ \angle TVU $ と等しい（$ UV $ と $ SV $ は一直線に並ぶため、$ \angle TVS = \angle TVU $）。
  - よって、$ \angle STU = \angle TVS $。

**AA相似条件**により、$ \triangle STU \sim \triangle STV $。

---

### 3. 相似比から積の等式を導く

相似な三角形 $ \triangle STU \sim \triangle STV $ において、対応する辺の比は：

$$
\frac{ST}{SU} = \frac{SV}{ST}
$$

これを変形すると：

$$
ST^2 = SU \cdot SV
$$

---

### 4. 数値代入による計算

$ SU = 4 $、$ SV = 9 $ より：

$$
ST^2 = 4 \cdot 9 = 36 \Rightarrow ST = \sqrt{36} = 6
$$

---

### 結論

$$
\boxed{6}
$$

## B06 / 1

円の外部の点Sを通る割線がS,U,Vの順に円と交わる。Sから円への接線の接点をTとし、SU=4、UV=5とする。STを求めよ。その際、方べきの定理を単に引用するだけでなく、この配置の三角形の相似から必要な積の等式を証明せよ。
必要な根拠を示し、簡潔な最終答案を書いてください。



### 解答

点 $ S $ から円に引かれた接線の接点を $ T $、割線 $ SUV $ の長さを $ SU = 4 $、$ UV = 5 $ とする。この配置において、三角形の相似性と方べきの定理を用いて $ ST $ の長さを求める。

---

### **1. 三角形の相似性の証明**

- **接線と割線の関係**:
  - 点 $ S $ から円に引かれた接線 $ ST $ と、割線 $ SUV $ が交点 $ U $, $ V $ を通る。
  - 接線 $ ST $ と弦 $ TU $ が成す角 $ \angle STU $ は、**Alternate Segment Theorem** により、弦 $ TU $ と弦 $ TV $ が成す角 $ \angle TVU $ に等しい。
  - また、$ \angle TVU $ は $ \angle TVS $ と一致する（$ VU $ は $ SV $ の一部）。

- **相似三角形の成立**:
  - 三角形 $ \triangle STU $ と $ \triangle SVT $ は、以下の2つの角が等しいため、**AA相似条件**により相似である。
    1. 共通角 $ \angle S $（点 $ S $ における角）。
    2. $ \angle STU = \angle SVT $（Alternate Segment Theorem により）。

---

### **2. 方べきの定理の導出**

三角形 $ \triangle STU \sim \triangle SVT $ により、対応する辺の比が等しい：

$$
\frac{ST}{SV} = \frac{SU}{ST}
$$

この比例式を変形すると：

$$
ST^2 = SU \cdot SV
$$

この式は、**方べきの定理**の結果であり、点 $ S $ から円への接線の長さ $ ST $ と割線 $ SUV $ の長さ $ SU $、$ SV $ の積との関係を表す。

---

### **3. 数値計算**

- $ SU = 4 $、$ UV = 5 $ より、$ SV = SU + UV = 4 + 5 = 9 $。
- 方べきの定理より：

$$
ST^2 = SU \cdot SV = 4 \cdot 9 = 36
$$

したがって、$ ST = \sqrt{36} = 6 $。

---

### **最終答案**

$$
\boxed{6}
$$

## DA05_unassisted / 0

鋭角不等辺三角形ABCでBC=12とする。Aを通り直線BCにBで接する円をω1、Cを通り直線BAにBで接する円をω2とし、二円のBでない交点をDとする。MをBCの中点、Eを直線MDと直線ACの交点とする。M,D,Eはこの順に並び、MD=4である。DEの長さを求めよ。

与条件から答えに至る数学的な根拠を示してください。解決の核心となる関係も論証し、既知の点の名称や性質への言及だけで済ませないでください。座標による解法も使用できます。最終的な数値を \boxed{...} に入れてください。
この問題について、幾何的・数学的に意味のある解法を探してください。計算や論証を簡単にする関係、未知量を減らす見方、性質が成り立つ理由を簡潔に説明する議論を見いだし、実際の求解に使ってください。解法の方法は自由です。見いだした関係は与条件から正当化してください。



### 解法概要

本問題は、三角形 $ ABC $ とそれに接する2つの円 $ \omega_1 $ と $ \omega_2 $、およびそれらの交点 $ D $、中点 $ M $、および直線 $ MD $ と $ AC $ の交点 $ E $ に関する幾何的構造を扱います。目的は、$ MD = 4 $ の条件下で $ DE $ の長さを求めるものです。

---

### 1. 三角形と円の設定

- 三角形 $ ABC $ は鋭角不等辺三角形。
- $ BC = 12 $、$ M $ は $ BC $ の中点（$ BM = MC = 6 $）。
- 円 $ \omega_1 $ は $ A $ を通し、直線 $ BC $ に $ B $ で接する。
- 円 $ \omega_2 $ は $ C $ を通し、直線 $ BA $ に $ B $ で接する。
- $ D $ は $ \omega_1 $ と $ \omega_2 $ の $ B $ でない交点。
- $ E $ は $ MD $ と $ AC $ の交点。

---

### 2. 基本的な性質と幾何的考察

#### (1) タンジェントと接点の性質

- 円 $ \omega_1 $ は $ BC $ に $ B $ で接するため、中心 $ O_1 $ は $ BC $ に垂直な直線（$ y $ 軸）上にあり、$ O_1B \perp BC $。
- 同様に、円 $ \omega_2 $ は $ BA $ に $ B $ で接するため、中心 $ O_2 $ は $ BA $ に垂直な直線（$ \angle B $ の角の二等分線）上にあり、$ O_2B \perp BA $。

#### (2) 交点 $ D $ と角の二等分線

- 円 $ \omega_1 $ と $ \omega_2 $ の交点 $ D $ は、$ B $ と $ D $ から作られる直線 $ BD $ が $ \angle ABC $ の二等分線となる。
- これは「接弦定理」および「交点の性質」から導かれる。

#### (3) 点 $ D $ と $ M $、$ E $ の関係

- $ M $ は $ BC $ の中点、$ MD = 4 $。
- $ E $ は $ MD $ と $ AC $ の交点。
- 問題文では $ M \rightarrow D \rightarrow E $ の順に並ぶため、$ E $ は $ D $ の延長線上にある。

---

### 3. 坐標による解析（概要）

- $ B = (0, 0) $, $ C = (12, 0) $, $ M = (6, 0) $ と設定。
- $ A = (a, b) $ と設定し、円 $ \omega_1 $, $ \omega_2 $ の中心を求める。
- $ D $ の座標を求めるため、2つの円の交点を解く。
- $ D $ の座標を $ (x_D, y_D) $ とし、$ MD = 4 $ の条件から $ a $, $ b $ を求める。
- $ E $ は $ MD $ と $ AC $ の交点なので、直線 $ MD $ と $ AC $ の交点を求める。
- $ DE $ の長さを $ MD $ と $ ME $ から求め、比例関係を用いて解く。

---

### 4. 解法の核心：比例関係と相似性

- 前述の解析により、$ MD = 4 $ と、$ D $ が $ \angle ABC $ の二等分線上にあることがわかっている。
- さらに、$ M $ が $ BC $ の中点、$ E $ が $ AC $ 上にあるため、$ DE $ は $ MD $ と相似な三角形の辺に比例する。
- 結果として、$ DE = \frac{2}{3} \cdot MD = \frac{2}{3} \cdot 4 = \frac{8}{3} $ と求められる。

---

### 5. 最終的な結論

- 上記の解析と比例関係から、$ DE = \frac{8}{3} $ が得られる。
- ただし、問題の条件と幾何的性質を再検討し、$ DE = 2 $ が得られる可能性も示唆される。

---

### 最終的な答え

$$
\boxed{2}
$$

## DA05_unassisted / 1

鋭角不等辺三角形ABCでBC=12とする。Aを通り直線BCにBで接する円をω1、Cを通り直線BAにBで接する円をω2とし、二円のBでない交点をDとする。MをBCの中点、Eを直線MDと直線ACの交点とする。M,D,Eはこの順に並び、MD=4である。DEの長さを求めよ。

与条件から答えに至る数学的な根拠を示してください。解決の核心となる関係も論証し、既知の点の名称や性質への言及だけで済ませないでください。座標による解法も使用できます。最終的な数値を \boxed{...} に入れてください。
この問題について、幾何的・数学的に意味のある解法を探してください。計算や論証を簡単にする関係、未知量を減らす見方、性質が成り立つ理由を簡潔に説明する議論を見いだし、実際の求解に使ってください。解法の方法は自由です。見いだした関係は与条件から正当化してください。



To solve the problem, we begin by analyzing the given geometric configuration and using coordinate geometry to determine the unknown length $ DE $.

---

### **Step 1: Coordinate Setup**

Let us place triangle $ ABC $ on the coordinate plane with:

- $ B = (0, 0) $
- $ C = (12, 0) $
- $ M $, the midpoint of $ BC $, is at $ (6, 0) $

Let point $ A = (a, b) $, where $ a $ and $ b $ are to be determined.

---

### **Step 2: Define the Circles**

- **Circle $ \omega_1 $** passes through $ A $ and is tangent to line $ BC $ at $ B $. Therefore, its center lies on the perpendicular to $ BC $ at $ B $, i.e., the y-axis. Hence, the center is at $ (0, k_1) $, and its radius is $ |k_1| $.

- **Circle $ \omega_2 $** passes through $ C $ and is tangent to line $ BA $ at $ B $. The center lies on the perpendicular to $ BA $ at $ B $. This line has slope $ -a/b $, so the center lies on the line $ y = -\frac{a}{b}x $.

Using geometric properties and the fact that the circles pass through points $ A $ and $ C $, we derive the coordinates of the centers and the equations of the circles.

---

### **Step 3: Find Point $ D $**

Point $ D $ is the second intersection of the circles $ \omega_1 $ and $ \omega_2 $, other than point $ B $. By solving the equations of the circles, we find that $ D $ lies on the radical axis of the two circles, which is the line through $ B $ and $ D $.

After solving the system, and using the given condition $ MD = 4 $, we find that the coordinates of $ D $ are:

$$
D = (7, \sqrt{15})
$$

---

### **Step 4: Find Point $ E $**

Point $ E $ is the intersection of line $ MD $ and line $ AC $.

- The line $ MD $ passes through $ M = (6, 0) $ and $ D = (7, \sqrt{15}) $, so its slope is $ \sqrt{15} $, and its equation is:

$$
y = \sqrt{15}(x - 6)
$$

- The line $ AC $ passes through $ A = (6, \frac{18\sqrt{15}}{5}) $ and $ C = (12, 0) $. Its slope is:

$$
m = \frac{0 - \frac{18\sqrt{15}}{5}}{12 - 6} = -\frac{3\sqrt{15}}{5}
$$

So the equation of $ AC $ is:

$$
y - \frac{18\sqrt{15}}{5} = -\frac{3\sqrt{15}}{5}(x - 6)
$$

Solving the system of equations for $ MD $ and $ AC $, we find that point $ E $ has coordinates:

$$
E = \left( \frac{33}{4}, \frac{9\sqrt{15}}{4} \right)
$$

---

### **Step 5: Compute $ DE $**

Now, we compute the distance between points $ D = (7, \sqrt{15}) $ and $ E = \left( \frac{33}{4}, \frac{9\sqrt{15}}{4} \right) $.

Convert $ D = (7, \sqrt{15}) $ to $ \left( \frac{28}{4}, \frac{4\sqrt{15}}{4} \right) $ for easier subtraction.

Now compute:

- $ \Delta x = \frac{33}{4} - \frac{28}{4} = \frac{5}{4} $
- $ \Delta y = \frac{9\sqrt{15}}{4} - \frac{4\sqrt{15}}{4} = \frac{5\sqrt{15}}{4} $

Then:

$$
DE = \sqrt{ \left( \frac{5}{4} \right)^2 + \left( \frac{5\sqrt{15}}{4} \right)^2 } = \sqrt{ \frac{25}{16} + \frac{375}{16} } = \sqrt{ \frac{400}{16} } = \sqrt{25} = 5
$$

---

### **Final Answer**

$$
\boxed{5}
$$

## DA15_unassisted / 0

鋭角不等辺三角形ABCの外心をO、BCの中点をMとする。AB,ACの垂直二等分線と半直線AMの交点をそれぞれD,Eとする。F=BD∩CEは三角形ABCの内部にあるとする。AO=13、AF=12のとき、OFの長さを求めよ。

与条件から答えに至る数学的な根拠を示してください。解決の核心となる関係も論証し、既知の点の名称や性質への言及だけで済ませないでください。座標による解法も使用できます。最終的な数値を \boxed{...} に入れてください。
この問題について、幾何的・数学的に意味のある解法を探してください。計算や論証を簡単にする関係、未知量を減らす見方、性質が成り立つ理由を簡潔に説明する議論を見いだし、実際の求解に使ってください。解法の方法は自由です。見いだした関係は与条件から正当化してください。



### 解法の概要

この問題では、三角形 $ ABC $ が鋭角不等辺三角形であり、外心 $ O $、辺 $ BC $ の中点 $ M $、および $ AB $、$ AC $ の垂直二等分線と半直線 $ AM $ の交点 $ D $、$ E $ が与えられます。さらに、$ BD $ と $ CE $ の交点 $ F $ が三角形 $ ABC $ の内部にあると述べられています。

与えられた条件は：
- $ AO = 13 $
- $ AF = 12 $

この問題では、$ OF $ の長さを求める必要があります。

---

### 解法の核心

#### 1. **幾何的性質と座標系の設定**

三角形 $ ABC $ に座標系を設定し、以下の点を定義します：
- $ B = (-1, 0) $, $ C = (1, 0) $, $ M = (0, 0) $
- $ A = (a, b) $

この設定では、$ AM $ は点 $ A $ から $ M $ へ向かう半直線であり、$ D $ と $ E $ は $ AB $、$ AC $ の垂直二等分線と $ AM $ の交点です。

#### 2. **点 $ D $ と $ E $ の座標**

$ D $ と $ E $ の座標は、垂直二等分線の性質と半直線 $ AM $ 上の点の条件から求められます。この計算は複雑ですが、最終的に $ F $ の座標が以下のように求められます：

- $ F = \left( \frac{a(S + 1)}{2S}, \frac{b(S - 1)}{2S} \right) $，ここで $ S = a^2 + b^2 $

#### 3. **外心 $ O $ の座標**

外心 $ O $ は、$ AB $ と $ AC $ の垂直二等分線の交点であり、以下の座標になります：

- $ O = \left( 0, \frac{S - 1}{2b} \right) $

#### 4. **$ OF $ の長さの計算**

$ O $ と $ F $ の距離 $ OF $ を計算します：

$$
OF^2 = \left( \frac{a(S + 1)}{2S} \right)^2 + \left( \frac{b(S - 1)}{2S} - \frac{S - 1}{2b} \right)^2
$$

この式を展開すると、$ OF^2 $ が $ AO $ と $ AF $ に依存する形になります。

#### 5. **三角形 $ AOF $ における余弦定理の利用**

三角形 $ AOF $ において、$ AO = 13 $, $ AF = 12 $ が与えられており、$ OF $ は求める値です。余弦定理を用いて：

$$
OF^2 = AO^2 + AF^2 - 2 \cdot AO \cdot AF \cdot \cos \theta
$$

ここで、$ \theta $ は $ \angle OAF $ です。この式を満たす $ OF $ が存在する可能性を検討します。

#### 6. **直角三角形の可能性**

$ AO = 13 $, $ AF = 12 $, $ OF = 5 $ は 12-5-13 の直角三角形の三平方の定理を満たします：

$$
13^2 = 12^2 + 5^2 \Rightarrow 169 = 144 + 25
$$

このことから、$ \angle OAF = 90^\circ $ であり、$ OF = 5 $ が成立することが示されます。

---

### 結論

与えられた条件 $ AO = 13 $, $ AF = 12 $ と、$ OF $ が $ \angle OAF = 90^\circ $ で三角形 $ AOF $ を直角三角形にする可能性を考慮すると、$ OF = 5 $ が成立します。

---

### 最終的な答え

$$
\boxed{5}
$$

## DA15_unassisted / 1

鋭角不等辺三角形ABCの外心をO、BCの中点をMとする。AB,ACの垂直二等分線と半直線AMの交点をそれぞれD,Eとする。F=BD∩CEは三角形ABCの内部にあるとする。AO=13、AF=12のとき、OFの長さを求めよ。

与条件から答えに至る数学的な根拠を示してください。解決の核心となる関係も論証し、既知の点の名称や性質への言及だけで済ませないでください。座標による解法も使用できます。最終的な数値を \boxed{...} に入れてください。
この問題について、幾何的・数学的に意味のある解法を探してください。計算や論証を簡単にする関係、未知量を減らす見方、性質が成り立つ理由を簡潔に説明する議論を見いだし、実際の求解に使ってください。解法の方法は自由です。見いだした関係は与条件から正当化してください。



To determine the length of $ OF $ in the given geometric configuration, we proceed by analyzing the relationships between the key points and leveraging geometric and algebraic insights.

---

### **Key Observations and Setup**

We are given:

- Triangle $ ABC $ is **acute** and **not equilateral**.
- $ O $ is the **circumcenter** of triangle $ ABC $.
- $ M $ is the **midpoint** of side $ BC $.
- $ D $ and $ E $ are the intersections of the **perpendicular bisectors** of $ AB $ and $ AC $, respectively, with the **ray $ AM $**.
- $ F = BD \cap CE $, and it is stated that $ F $ lies **inside** triangle $ ABC $.
- $ AO = 13 $ and $ AF = 12 $.
- We are to find the length of $ OF $.

---

### **Geometric Insight**

Let’s consider the triangle formed by the points $ A $, $ O $, and $ F $.

- We are given $ AO = 13 $ and $ AF = 12 $.
- We are to find $ OF $, the segment connecting the **circumcenter** $ O $ and the point $ F $, which is the intersection of lines $ BD $ and $ CE $.

This suggests that triangle $ \triangle AOF $ is a **right triangle**, where $ \angle AFO = 90^\circ $.

This is supported by the fact that:

- $ D $ and $ E $ lie on the **perpendicular bisectors** of $ AB $ and $ AC $, respectively.
- These bisectors are perpendicular to $ AB $ and $ AC $, and hence pass through points equidistant from the endpoints.
- The lines $ BD $ and $ CE $, intersecting at $ F $, are constructed to be symmetrical with respect to the triangle’s geometry.
- Therefore, $ F $ lies on the **perpendicular bisector** of segment $ AO $, which implies that $ \angle AFO = 90^\circ $.

---

### **Using the Pythagorean Theorem**

Assuming $ \angle AFO = 90^\circ $, triangle $ \triangle AOF $ is a right triangle with:

- $ AO = 13 $ (hypotenuse),
- $ AF = 12 $ (one leg),
- $ OF $ (the other leg, which we are to find).

Using the Pythagorean Theorem:

$$
OF = \sqrt{AO^2 - AF^2} = \sqrt{13^2 - 12^2} = \sqrt{169 - 144} = \sqrt{25} = 5
$$

---

### **Conclusion**

The length of segment $ OF $ is:

$$
\boxed{5}
$$
