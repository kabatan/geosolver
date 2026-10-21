# 採点確認用の答案抜粋

2026-09-23。全48答案を採点固定後にモデル対応を開示。このファイルは人手確認用であり、新しい教師データとして学習へ渡さない。

通常の座標計算を省略しても正しい一般式を明示したものは認める。核心の無根拠な公式引用・循環・特殊例だけの検証は認めない。局所的な説明・転記ミスは別集計。


## R0017 / N01 / trained sample 1

暫定採点：complete。H=(e,(d²−e²)/f), P=(d²e/(e²+f²),d²f/(e²+f²)), k=(d²−e²−f²)/(2f)を明示。Pの円への代入は一般に恒等的に成立する。

以下の命題を証明してください。必要な仮定と推論が追えるように説明してください。解法は問いません。通常の定理は用いてよいですが、この配置に固有の非自明な性質や、結論と実質的に同じ命題は、名称の引用だけで済ませず根拠を示してください。

鋭角三角形ABCでAB≠ACとする。Hを垂心、MをBCの中点、PをHから直線AMへ下ろした垂線の足とする。B,C,H,Pが同一円周上にあることを証明せよ。

**証明の概要：**

鋭角三角形ABCにおいて、Hは垂心、MはBCの中点、PはHから直線AMに下ろした垂線の足である。B, C, H, Pが同一円周上にあることを証明するためには、以下の手順を踏む。

---

### **1. 基本的な性質と定理の活用**
- **垂心H**：三角形ABCの三つの高線の交点。
- **中点M**：BCの中点であり、AMは中線。
- **垂線の足P**：HからAMに下ろした垂線の足。

**目標**：四点B, C, H, Pが同一円周上にあることを示す。

---

### **2. 坐標系による証明（代数的アプローチ）**
- **座標設定**：
  - B(-d, 0), C(d, 0), M(0, 0)（Mが原点）
  - A(e, f)（f ≠ 0）
- **垂心Hの座標**：
  - Hの座標は (e, (d² - e²)/f)
- **点Pの座標**：
  - PはHからAMに下ろした垂線の足。AMの式はy = (f/e)xで、Pの座標は ([d² e / (e² + f²)], [f d² / (e² + f²)] )

---

### **3. 円の存在の確認**
- **B, C, Hを通過する円の中心と半径**：
  - B(-d, 0), C(d, 0), H(e, (d² - e²)/f)を通過する円の中心は(0, k)（y軸上）。
  - k = [d² - e² - f²]/(2f)
  - 半径の平方は r² = d² + k²
- **点Pがこの円上にあるかの確認**：
  - Pの座標を代入し、中心からの距離を計算。
  - 計算により、Pの座標は円の半径と一致することが示される。

---

### **4. 例による検証**
- **例1**：d=2, e=1, f=1
  - H(1, 3), P(2, 2)
  - B(-2, 0), C(2, 0), H(1, 3), P(2, 2)が円周上にあることが確認。
- **例2**：d=2, e=1, f=2
  - H(1, 3/2), P(4/5, 8/5)
  - 同様に、Pが円周上にあることが確認。

---

### **5. 結論**
- 上記の代数的計算と例による検証から、四点B, C, H, Pが同一円周上にあることが証明される。
- この結果は、三角形ABCの性質と垂心、中点、垂線の関係に基づく一般の定理として成り立つ。

---

**結論**：  
鋭角三角形ABCでAB ≠ ACのとき、垂心H、BCの中点M、HからAMに下ろした垂線の足Pは、四点B, C, H, Pが同一円周上にある。この結果は、座標系による代数的証明と例による検証を通じて成り立つ。


## R0031 / N01 / trained sample 2

暫定採点：local_error。H・P・円の一般式は正しく共円性を検算できる。ただし「HはAMとBCの垂直線の交点」は誤りで、高線の説明の局所修正が必要。

以下の命題を証明してください。必要な仮定と推論が追えるように説明してください。解法は問いません。通常の定理は用いてよいですが、この配置に固有の非自明な性質や、結論と実質的に同じ命題は、名称の引用だけで済ませず根拠を示してください。

鋭角三角形ABCでAB≠ACとする。Hを垂心、MをBCの中点、PをHから直線AMへ下ろした垂線の足とする。B,C,H,Pが同一円周上にあることを証明せよ。

鋭角三角形ABCにおいて、AB ≠ ACと仮定し、Hを垂心、MをBCの中点、PをHから直線AMへ下ろした垂線の足とする。B, C, H, Pが同一円周上にあることを証明する。以下に証明の手順を示す。

---

### **1. 坐標系の設定**
- BCを水平軸に置き、B(-1, 0)、C(1, 0)、M(0, 0)と設定。このとき、MはBCの中点である。
- A(a, b)とし、三角形ABCは鋭角であり、AB ≠ ACを満たす。
- 垂心Hの座標を計算する。

---

### **2. 垂心Hの座標の求め方**
- BCの垂直線はAMに垂直であり、AMの傾きはb/a。したがって、HはAMとBCの垂直線の交点であり、Hの座標は(a, (1 - a²)/b)となる。

---

### **3. Pの座標の求め方**
- AMの式はy = (b/a)x。
- HPはAMに垂直な直線であり、H(a, (1 - a²)/b)からAMへ下ろした垂線の足Pの座標は、解くことで(a/(a² + b²), b/(a² + b²))と求められる。

---

### **4. 円の存在の確認**
- B(-1, 0)、C(1, 0)、H(a, (1 - a²)/b)が同一円周上にあることを確認する。
- BとCが対称な点であるため、円の中心はy軸上にあり、中心を(0, k)と置く。
- 円の式はx² + y² - 2ky - 1 = 0と表され、Hを代入することでk = (1 - a² - b²)/(2b)と求められる。
- P(a/(a² + b²), b/(a² + b²))をこの円の式に代入すると、0に等しくなることが確認される。

---

### **5. 結論**
- Pの座標を円の式に代入した結果、0に等しくなることから、B, C, H, Pは同一円周上にあることが示される。

**したがって、B, C, H, Pは同一円周上にある。**


## R0035 / N01 / trained sample 0

暫定採点：local_error。H,P,円の一般式は正しく代入で結論を得る。ただし「BCの傾きは0…BHは垂直」とする説明はACへの垂線との取り違え。表示したBHの式自体は正しい。

以下の命題を証明してください。必要な仮定と推論が追えるように説明してください。解法は問いません。通常の定理は用いてよいですが、この配置に固有の非自明な性質や、結論と実質的に同じ命題は、名称の引用だけで済ませず根拠を示してください。

鋭角三角形ABCでAB≠ACとする。Hを垂心、MをBCの中点、PをHから直線AMへ下ろした垂線の足とする。B,C,H,Pが同一円周上にあることを証明せよ。

鋭角三角形ABCでAB≠ACとする。Hを垂心、MをBCの中点、PをHから直線AMへ下ろした垂線の足とする。B,C,H,Pが同一円周上にあることを証明する。

---

### **証明の概要**
1. **座標系の設定**  
   BCをx軸に置き、B(0,0)、C(2c, 0)、M(c, 0)とし、A(d, e)と置く。このとき、AMはAからMへの線分であり、Hは垂心となる。

2. **垂心Hの座標**  
   ABCの垂心Hは、各辺の垂線の交点である。BCに垂直な垂線はx=d、BHとCHの交点を求めて、H(d, [d(2c - d)]/e)と求められる。

3. **点Pの座標**  
   HからAMに下ろした垂線の足Pは、AMとHP（AMに垂直）の交点である。AMの傾きをm_AM = -e/(c - d)とし、HPの傾きは(c - d)/e。HPの式を立て、AMとHPの交点を求めてPの座標を導く。

4. **円の存在の確認**  
   B(0,0)、C(2c, 0)、H(d, h_y)を通る円の式を導き、P(x_p, y_p)がこの円上にあることを確認する。計算により、Pの座標が円の式を満たすことが示される。

---

### **詳細な証明**

**1. 座標系の設定とHの座標**  
- B(0,0)、C(2c, 0)、M(c, 0)、A(d, e)と置く。
- BCに垂直な垂線はx=dであり、A(d, e)から垂線はx=d。
- BHの式：BCの傾きは0（水平），BHは垂直に交わる。BHの式はy = [(2c - d)/e]x。
- Hはx=dとy = [(2c - d)/e]xの交点なので、H(d, [d(2c - d)]/e)。

**2. 点Pの座標**  
- AMの傾きm_AM = -e/(c - d)，方程式：y = [-e/(c - d)]x + [ec/(c - d)]。
- HPはAMに垂直，傾き(c - d)/e。H(d, h_y)を通る直線の式：y - h_y = [(c - d)/e](x - d)。
- AMとHPの交点Pを求める。解くと、Pの座標は：
  $$
  x_p = \frac{c(e^2 - dc + d^2)}{e^2 + (c - d)^2}, \quad y_p = \frac{ec^2}{e^2 + (c - d)^2}
  $$

**3. 円の存在の確認**  
- B(0,0)、C(2c, 0)、H(d, h_y)を通る円の式を導く：
  $$
  x^2 + y^2 - 2c x + \frac{(-d^2 - h_y^2 + 2c d)}{h_y} y = 0
  $$
- P(x_p, y_p)をこの円の式に代入し、計算により0に等しいことが示される。

---

### **結論**
点B、C、H、Pが同一円周上にあることが証明された。この結果は、座標系での計算と一般の円の性質に基づくものであり、図形の性質を深く理解するための重要な結果である。


## R0036 / N01 / base sample 0

暫定採点：local_error。H,P,kと円への代入は正しい一般式。一方「高線BHは y=(b²−p²)/q」は直線の式でなくHのy座標。ここを修正すれば完答。

以下の命題を証明してください。必要な仮定と推論が追えるように説明してください。解法は問いません。通常の定理は用いてよいですが、この配置に固有の非自明な性質や、結論と実質的に同じ命題は、名称の引用だけで済ませず根拠を示してください。

鋭角三角形ABCでAB≠ACとする。Hを垂心、MをBCの中点、PをHから直線AMへ下ろした垂線の足とする。B,C,H,Pが同一円周上にあることを証明せよ。

**証明**

鋭角三角形 $ ABC $ で $ AB \neq AC $ とする。垂心 $ H $、辺 $ BC $ の中点 $ M $、および $ H $ から線分 $ AM $ へ下ろした垂線の足 $ P $ が与えられる。目標は、点 $ B $、$ C $、$ H $、$ P $ が同一円周上にあることを証明する。

---

### **1. 坐標系の設定と点の座標の導出**

- 点 $ B $ を $ (-b, 0) $、点 $ C $ を $ (b, 0) $、中点 $ M $ を $ (0, 0) $ と置く。
- 点 $ A $ を $ (p, q) $ とし、$ AB \neq AC $ を満たすように $ p \neq 0 $ と設定する。
- 垂心 $ H $ の座標は、三角形の高線の交点として導出される。高線 $ AH $ は $ x = p $、高線 $ BH $ は $ y = \frac{b^2 - p^2}{q} $ なので、$ H $ の座標は $ (p, \frac{b^2 - p^2}{q}) $。
- 線分 $ AM $ の方程式は $ y = \frac{q}{p}x $。
- $ H $ から $ AM $ に下ろした垂線の足 $ P $ の座標は、点 $ H $ から $ AM $ への垂線の足を計算することで得られる。結果として、$ P $ の座標は $ \left( \frac{p b^2}{p^2 + q^2}, \frac{b^2 q}{p^2 + q^2} \right) $。

---

### **2. 円の存在の確認**

点 $ B $、$ C $、$ H $ が同一円周上にあることを確認し、$ P $ もその円上にあることを示す。

- 点 $ B(-b, 0) $、$ C(b, 0) $、$ H(p, \frac{b^2 - p^2}{q}) $ が円周上にある円の中心は、$ y $ 軸上に位置する。中心を $ (0, k) $、半径を $ r $ と置くと、以下の条件が成り立つ：
  $$
  b^2 + k^2 = r^2
  $$
  また、$ H $ がこの円上にあるため、以下の式が成り立つ：
  $$
  p^2 + \left( \frac{b^2 - p^2}{q} - k \right)^2 = r^2
  $$
  これを解くことで、$ k = \frac{b^2 - p^2 - q^2}{2q} $ と求められる。

- これにより、円の中心は $ (0, k) $、半径は $ r = \sqrt{b^2 + k^2} $ と定義される。

- 点 $ P $ の座標をこの円の式に代入し、以下の式が成り立つことを確認する：
  $$
  \left( \frac{p b^2}{p^2 + q^2} \right)^2 + \left( \frac{b^2 q}{p^2 + q^2} - k \right)^2 = b^2 + k^2
  $$
  この式を展開・整理することで、両辺が等しいことが示される。

---

### **3. 結論**

点 $ B $、$ C $、$ H $、$ P $ は、円の中心 $ (0, k) $ と半径 $ r $ で定義される円上に存在する。したがって、**点 $ B $、$ C $、$ H $、$ P $ は同一円周上にある**。

---

**補足：**  
この証明では、座標幾何を用いて直接的な計算により、点 $ P $ が円上にあることを確認した。また、円の中心と半径の導出過程で、三角形の性質や垂心の定義を活用した。このように、座標系の設定と計算により、問題の配置に固有の性質を明示的に示すことができた。


## R0012 / DU01 / trained sample 0

暫定採点：complete。B=(c,0),C=(b cosα,b sinα)に対してU,V,mUV,mAKの一般式を正しく明示。接線の連立計算は省略されているがmAK=c sinα/(b+c cosα)はその計算結果と一致し、積−1を証明する。計算省略の許容について要人手確認。

以下の命題を証明してください。必要な仮定と推論が追えるように説明してください。解法は問いません。通常の定理は用いてよいですが、この配置に固有の非自明な性質や、結論と実質的に同じ命題は、名称の引用だけで済ませず根拠を示してください。

鋭角三角形ABCでAB≠ACとし、その外接円をΓとする。ΓのB,Cにおける接線の交点をKとする。Bを通り直線ACにAで接する円の中心をU、Cを通り直線ABにAで接する円の中心をVとする。UV⊥AKであることを証明せよ。

鋭角三角形ABCにおいて、AB ≠ ACとし、外接円ΓのB,Cにおける接線の交点をKとする。Bを通り直線ACにAで接する円の中心をU、Cを通り直線ABにAで接する円の中心をVとする。UV ⊥ AKを証明する。

### 証明の概要
1. **点UとVの位置**:
   - Uは直線ACにAで接する円の中心であり、ACに垂直にAを通る直線（ACの垂直線）に位置する。また、UはABの垂直二等分線に位置する。したがって、UはACの垂直線とABの垂直二等分線の交点である。
   - 同様に、VはABの垂直線とACの垂直二等分線の交点である。

2. **座標系の設定**:
   - Aを原点(0,0)、ABをx軸、ACを任意の角度αで設定。このとき、ABの長さをc、ACの長さをbとし、座標をA(0,0)、B(c,0)、C(b cos α, b sin α)とする。

3. **点UとVの座標**:
   - UはABの垂直二等分線（x = c/2）とACの垂直線（y = -cot α x）の交点であり、Uの座標は(c/2, -c cot α / 2)。
   - VはABの垂直線（x = 0）とACの垂直二等分線の交点であり、Vの座標は(0, b/(2 sin α))。

4. **UVの傾き**:
   - UVの傾きは、UとVの座標から計算し、m_UV = - (b + c cos α)/(c sin α)。

5. **AKの傾き**:
   - AKは外接円Γの接線の交点Kを通る直線。Kの座標を計算し、AKの傾きm_AK = (c sin α)/(b + c cos α)。

6. **垂直性の確認**:
   - UVの傾きm_UVとAKの傾きm_AKの積は -1 である。したがって、UV ⊥ AK。

### 結論
UVとAKは直交する。この結果は、座標系を用いた一般化された計算により導かれる。したがって、題意の命題は成立する。

**証明終わり**。


## R0027 / DU01 / base sample 3

暫定採点：core_gap。U,Vの座標と結論に必要なAK傾きは正しいが、核心であるsymmedianの傾きの公式を根拠なく「一般に」と引用。垂線を−tanθとする誤記も残る。

以下の命題を証明してください。必要な仮定と推論が追えるように説明してください。解法は問いません。通常の定理は用いてよいですが、この配置に固有の非自明な性質や、結論と実質的に同じ命題は、名称の引用だけで済ませず根拠を示してください。

鋭角三角形ABCでAB≠ACとし、その外接円をΓとする。ΓのB,Cにおける接線の交点をKとする。Bを通り直線ACにAで接する円の中心をU、Cを通り直線ABにAで接する円の中心をVとする。UV⊥AKであることを証明せよ。

**証明**

鋭角三角形ABCにおいて、AB ≠ ACとし、外接円ΓのB,Cにおける接線の交点をKとする。Bを通りACにAで接する円の中心をU、Cを通りABにAで接する円の中心をVとする。UV ⊥ AKを証明する。

---

### **1. 点UとVの位置の決定**

- **点U**は、ACにAで接する円の中心であり、以下の2つの条件を満たす：
  1. **ACに垂直**：ACの接線はAにおける接線であり、中心UはACに垂直な直線に位置する。
  2. **AとBを結ぶ円の中心**：円はAとBを通るため、UはAとBの垂直二等分線に位置する。

  因此、UはACに垂直な直線とABの垂直二等分線の交点である。

- **点V**は、ABにAで接する円の中心であり、以下の2つの条件を満たす：
  1. **ABに垂直**：ABの接線はAにおける接線であり、中心VはABに垂直な直線に位置する。
  2. **AとCを結ぶ円の中心**：円はAとCを通るため、VはAとCの垂直二等分線に位置する。

  因此、VはABに垂直な直線とACの垂直二等分線の交点である。

---

### **2. UVの傾きの導出**

座標系を設定し、一般の座標を用いてUVの傾きを計算する。

- A(0, 0), B(b, 0), C(x, y)とし、ACの傾きはy/x、ABの傾きは0。
- **U**はACに垂直な直線とABの垂直二等分線（x = b/2）の交点。ACに垂直な直線はy = -x tan(θ)（θはACとx軸の角）。
  - Uの座標は(x, y) = (b/2, - (b x)/(2y))。
- **V**はABに垂直な直線（x = 0）とACの垂直二等分線の交点。ACの垂直二等分線はy = -x tan(θ) + c（cは定数）。
  - Vの座標は(x, y) = (0, (x² + y²)/(2y))。

UVの傾きは：
$$
\text{Slope}_{UV} = \frac{\frac{x^2 + y^2}{2y} - \left(-\frac{b x}{2y}\right)}{0 - \frac{b}{2}} = -\frac{x^2 + y^2 + b x}{b y}
$$

---

### **3. AKの傾きの導出**

KはΓのB,Cにおける接線の交点。AKは三角形ABCの**対称軸**（symmedian）である。

- **symmedianの傾き**は、三角形の辺ABとACの傾きを用いて計算できる。
- 一般に、symmedianの傾きは：
  $$
  \text{Slope}_{AK} = \frac{b y}{x^2 + y^2 + b x}
  $$
  （これはUVの傾きの負の逆数）

---

### **4. UVとAKの垂直性の確認**

UVの傾きとAKの傾きの積が-1であることを確認する：
$$
\left(-\frac{x^2 + y^2 + b x}{b y}\right) \cdot \left(\frac{b y}{x^2 + y^2 + b x}\right) = -1
$$

これは、UVとAKが**垂直**であることを示す。

---

### **結論**

以上より、UV ⊥ AKが成り立つ。

**証明終了**。


## R0032 / N02 / base sample 0

暫定採点：complete。両円の中心、共通弦の直線、一般のT座標とAT²を明示しており、BT²CT²=(AT²)²を通常の代入で確認できる。具体例だけに依存していない。radical axisの訳「共通接線」は誤訳だが式は正しい。

以下の命題を証明してください。必要な仮定と推論が追えるように説明してください。解法は問いません。通常の定理は用いてよいですが、この配置に固有の非自明な性質や、結論と実質的に同じ命題は、名称の引用だけで済ませず根拠を示してください。

鋭角三角形ABCをとる。A,Bを通り直線ACにAで接する円と、A,Cを通り直線ABにAで接する円の、A以外の交点をTとする。Tは三角形ABCの内部にあるとする。AT²=BT·CTを証明せよ。

鋭角三角形ABCにおいて、A,Bを通り直線ACにAで接する円と、A,Cを通り直線ABにAで接する円の交点T（A以外）が三角形ABCの内部にあるとき、AT² = BT·CTを証明する。

---

### **証明の手順**

1. **円の中心と方程式の導出**  
   - **円1**（A,Bを通る、ACにAで接する円）の中心O₁は直線ACに垂直な直線（y軸）上にあり、A(0,0)とB(d,e)を通る。中心O₁の座標は(0, (d² + e²)/(2e))。
   - **円2**（A,Cを通る、ABにAで接する円）の中心O₂は直線ABに垂直な直線（y = -d/e x）上にあり、A(0,0)とC(c,0)を通る。中心O₂の座標は(c/2, -cd/(2e))。

2. **交点Tの座標の導出**  
   - 2つの円の方程式から、radical axis（共通接線）を求めると、線分ATの式y = [ce/(c d + d² + e²)]xが得られる。
   - この直線と円1の交点Tの座標を求める。結果として、Tの座標は(x_T, y_T) = [c(d² + e²)D/(D² + c²e²), c²e(d² + e²)/(D² + c²e²)]（D = c d + d² + e²）。

3. **AT²の計算**  
   - A(0,0)からTまでの距離の平方AT²は、x_T² + y_T²を計算して、  
     $$
     AT^2 = \frac{c^2(d^2 + e^2)^2}{D^2 + c^2e^2}
     $$
     と求められる。

4. **BT·CTの計算**  
   - Tの座標を用いて、点B(d,e)とC(c,0)との距離BTとCTを計算し、その積BT·CTを求める。
   - 具体的な座標（例：A(0,0), B(1,2), C(3,0)）を代入して、AT² = 9/4、BT·CT = 9/4と確認する。

5. **一般化**  
   - 上記の具体例ではAT² = BT·CTが成り立つことを確認した。一般の座標設定でも同様の計算により、AT² = BT·CTが導かれる。

---

### **結論**

三角形ABCの内部にある点Tは、2つの円の交点であり、AT² = BT·CTが成り立つ。この結果は、座標幾何学の計算や具体例の検証により確認され、一般的に成立する。

**証明終わり**。


## R0038 / OB01 / base sample 3

暫定採点：complete。方法1は正しい一般のE,F,中心,X座標と傾きの一致による完答。方法2の「NがAとXに挟まれ」は一般には誤りだが、独立に完結する方法1では使わない。

以下の命題を証明してください。必要な仮定と推論が追えるように説明してください。解法は問いません。通常の定理は用いてよいですが、この配置に固有の非自明な性質や、結論と実質的に同じ命題は、名称の引用だけで済ませず根拠を示してください。

鋭角三角形ABCでAB≠ACとする。BからACへの垂足をE、CからABへの垂足をF、BCの中点をNとする。A,Eを通り直線AFにAで接する円と、A,Fを通り直線AEにAで接する円の、Aでない交点をXとする。A,N,Xが一直線上にあることを証明せよ。

### 問題の概要

三角形 $ ABC $ が鋭角であり、$ AB \ne AC $ である。以下の点を定義する：
- $ E $: $ B $ から $ AC $ への垂線の足。
- $ F $: $ C $ から $ AB $ への垂線の足。
- $ N $: $ BC $ の中点。

さらに、以下の2つの円を定義する：
- Γ₁: $ A $ と $ E $ を通り、$ AF $ に $ A $ で接する円。
- Γ₂: $ A $ と $ F $ を通り、$ AE $ に $ A $ で接する円。

Γ₁ と Γ₂ の $ A $ 以外の交点を $ X $ とおく。このとき、$ A, N, X $ が一直線上にあることを証明せよ。

---

### 証明の概要

この問題は、幾何学的な構造と円の性質を組み合わせて、点 $ X $ が線分 $ AN $ 上にあることを示す問題である。以下に、証明の流れを整理して述べる。

---

### 1. 坐標系の設定と点の座標の計算

三角形 $ ABC $ を座標系に設定し、以下の座標を用いる：
- $ A = (0, 0) $
- $ B = (b, 0) $
- $ C = (c, d) $（$ d > 0 $ で三角形が鋭角である）

このとき、以下の点の座標が計算できる：
- $ E $: $ B $ から $ AC $ への垂線の足。$ E = \left( \dfrac{bc^2}{c^2 + d^2}, \dfrac{bcd}{c^2 + d^2} \right) $
- $ F $: $ C $ から $ AB $ への垂線の足。$ F = (c, 0) $
- $ N $: $ BC $ の中点。$ N = \left( \dfrac{b + c}{2}, \dfrac{d}{2} \right) $

---

### 2. 円 Γ₁ と Γ₂ の中心と方程式

- **Γ₁**: $ A $ と $ E $ を通り、$ AF $ に $ A $ で接する円。$ AF $ は $ x $ 軸に沿うため、円の中心 $ O_1 $ は $ y $ 軸上にあり、$ O_1 = (0, \dfrac{bc}{2d}) $。
- **Γ₂**: $ A $ と $ F $ を通り、$ AE $ に $ A $ で接する円。$ AE $ の傾きは $ d/c $、したがって円の中心 $ O_2 $ は $ y = -\dfrac{c}{d}x $ 上にあり、$ O_2 = \left( \dfrac{c}{2}, -\dfrac{c^2}{2d} \right) $

---

### 3. 円 Γ₁ と Γ₂ の交点 $ X $ の座標

Γ₁ と Γ₂ の交点 $ X $ を求めると、以下の座標が得られる：
- $ x = \dfrac{bc(b + c)}{(b + c)^2 + d^2} $
- $ y = \dfrac{bc d}{(b + c)^2 + d^2} $

---

### 4. $ A, N, X $ が一直線上にあるかの確認

点 $ A $、$ N $、$ X $ が一直線上にあるかを確認するには、以下の2つの方法が考えられる：

#### 方法1: 傍接線の傾きの一致

- $ AN $ の傾き：$ \dfrac{d/2}{(b + c)/2} = \dfrac{d}{b + c} $
- $ AX $ の傾き：$ \dfrac{y}{x} = \dfrac{ \dfrac{bc d}{(b + c)^2 + d^2} }{ \dfrac{bc(b + c)}{(b + c)^2 + d^2} } = \dfrac{d}{b + c} $

したがって、$ AN $ と $ AX $ の傾きは一致し、$ A, N, X $ は一直線上にある。

#### 方法2: パラメータ表示による確認

点 $ A $、$ N $、$ X $ をパラメータ表示し、$ N $ が $ A $ と $ X $ に挟まれた直線上にあるかを確認する。結果として、$ N $ は $ A $ と $ X $ に挟まれた直線上にあることが確認される。

---

### 5. 結論

上記の計算と確認により、点 $ A, N, X $ は一直線上にあることが示された。

---

### 結論

$$
\boxed{A, N, X \text{ are collinear}}
$$


## R0048 / EV02 / trained sample 0

暫定採点：core_gap。E,Fの座標は正しいが、T_x=ac/(a−c)をEFとの交点からでなく「HTとAMが垂直である条件から」求めており循環。正しい式の提示だけでは当該方向の推論を補えない。

以下の命題を証明してください。必要な仮定と推論が追えるように説明してください。解法は問いません。通常の定理は用いてよいですが、この配置に固有の非自明な性質や、結論と実質的に同じ命題は、名称の引用だけで済ませず根拠を示してください。

鋭角三角形ABCでAB≠ACとする。垂心をH、BCの中点をM、BからACへの垂足をE、CからABへの垂足をFとする。直線EFと直線BCの交点をTとする。HT⊥AMであることを証明せよ。

鋭角三角形ABCにおいて、AB ≠ ACとする。垂心をH、BCの中点をM、BからACへの垂足をE、CからABへの垂足をFとする。直線EFと直線BCの交点をTとする。HT ⊥ AMを証明する。

### 証明の概要
1. **座標設定**：Bを原点(0, 0)、Cを(2c, 0)、Aを(a, b)と設定し、MはBCの中点(c, 0)。
2. **垂心Hの座標**：2つの高線の交点としてHの座標を求めると、H(a, a(2c - a)/b)。
3. **EとFの座標**：EはBからACへの垂線とACの交点、FはCからABへの垂線とABの交点を計算。
4. **Tの座標**：EFとBCの交点Tのx座標tは、HTとAMが垂直である条件からt = a c / (a - c)と求められる。
5. **HTとAMの垂直性**：HTとAMのベクトルの内積を計算し、0に等しいことを示すことで、HT ⊥ AMが成立する。

### 詳細な証明
1. **座標系の設定**：
   - B(0, 0), C(2c, 0), A(a, b)とし、MはBCの中点(c, 0)。
   - 垂心Hは2つの高線の交点から求められる。

2. **垂心Hの座標**：
   - ACの傾きは -b/(2c - a) なので、垂線の傾きは (2c - a)/b。
   - ABの傾きは b/a なので、垂線の傾きは -a/b。
   - 2つの高線の交点Hの座標は (a, a(2c - a)/b)。

3. **EとFの座標**：
   - EはBからACへの垂線とACの交点。座標は (2c b²/D₁, 2c b(2c - a)/D₁) で、D₁ = (2c - a)² + b²。
   - FはCからABへの垂線とABの交点。座標は (2a²c/D₂, 2abc/D₂) で、D₂ = a² + b²。

4. **Tの座標**：
   - EFとBC（y=0）の交点Tのx座標tは、HTとAMが垂直である条件から t = a c / (a - c) と求められる。

5. **HTとAMの垂直性**：
   - HTのベクトルは (t - a, -a(2c - a)/b)。
   - AMのベクトルは (c - a, -b)。
   - 内積を計算すると、(t - a)(c - a) + a(2c - a) = 0 となり、t = a c / (a - c) が成立する。
   - これにより、HT ⊥ AMが証明される。

### 結論
以上により、HTとAMが垂直であることが示され、命題は成り立つ。


## R0010 / OB01 / trained sample 1

暫定採点：local_error。E,F,両円の中心,Xの一般式と共線性は正しい。ただしEを「AFに垂直な条件から」導くという説明はBE⊥ACとの取り違え。

以下の命題を証明してください。必要な仮定と推論が追えるように説明してください。解法は問いません。通常の定理は用いてよいですが、この配置に固有の非自明な性質や、結論と実質的に同じ命題は、名称の引用だけで済ませず根拠を示してください。

鋭角三角形ABCでAB≠ACとする。BからACへの垂足をE、CからABへの垂足をF、BCの中点をNとする。A,Eを通り直線AFにAで接する円と、A,Fを通り直線AEにAで接する円の、Aでない交点をXとする。A,N,Xが一直線上にあることを証明せよ。

鋭角三角形ABCにおいて、AB≠ACとし、BからACへの垂足をE、CからABへの垂足をF、BCの中点をNとする。A,Eを通り直線AFにAで接する円と、A,Fを通り直線AEにAで接する円のAでない交点をXとする。このとき、A,N,Xが一直線上にあることを証明する。

### 証明の概要
1. **座標系の設定**:
   - Aを原点(0,0)、Bを(2b, 0)、Cを(2c, 2d)と設定する。これにより、AB≠ACを満たす。
   - EはBからACへの垂線の足、FはCからABへの垂線の足となる。

2. **EとFの座標の導出**:
   - EはAC上の点で、ベクトルの内積により求められる。
   - FはAB上の点で、ABに垂直な条件から直接求められる。

3. **円の中心の導出**:
   - 第1円（A,Eを通りAFにAで接）の中心O₁は、AFに垂直な直線（y軸）とAEの垂直二等分線の交点。
   - 第2円（A,Fを通りAEにAで接）の中心O₂は、AEに垂直な直線とAFの垂直二等分線の交点。

4. **Xの座標の導出**:
   - 2つの円の交点AとXの座標を求めるため、2つの円の式を連立して解く。
   - 得られたXの座標は、AとNを通る直線に一致する。

5. **A,N,Xの共線性の確認**:
   - Nの座標を計算し、AとNを結ぶ直線の式を導出。
   - Xの座標がこの直線に一致することを確認。

### 詳細な証明
1. **座標系の設定**:
   - A(0,0), B(2b, 0), C(2c, 2d)と設定。この座標系では、ABとACが異なる長さを保証する。

2. **EとFの座標**:
   - EはAC上の点で、AFに垂直な条件から座標を導出:
     $$
     E = \left( \frac{2b c^2}{c^2 + d^2}, \frac{2b c d}{c^2 + d^2} \right)
     $$
   - FはAB上の点で、CからABへの垂線の足:
     $$
     F = (2c, 0)
     $$

3. **円の中心の導出**:
   - 第1円の中心O₁は、AFに垂直なy軸とAEの垂直二等分線の交点:
     $$
     O_1 = (0, \frac{b c}{d})
     $$
   - 第2円の中心O₂は、AEに垂直な直線とAFの垂直二等分線の交点:
     $$
     O_2 = (c, -\frac{c^2}{d})
     $$

4. **Xの座標の導出**:
   - 2つの円の式を連立し、交点Xの座標を求める:
     $$
     X = \left( \frac{2b c (b + c)}{(b + c)^2 + d^2}, \frac{2b c d}{(b + c)^2 + d^2} \right)
     $$

5. **A,N,Xの共線性の確認**:
   - NはBCの中点:
     $$
     N = (b + c, d)
     $$
   - A(0,0)とN(b + c, d)を結ぶ直線の式は:
     $$
     x = t(b + c), \quad y = t d \quad (t \in \mathbb{R})
     $$
   - Xの座標はこの直線に一致するため、A,N,Xは一直線上にある。

### 結論
上述の座標系と計算により、A,N,Xが一直線上にあることが示された。したがって、命題は証明された。

**答え**: A, N, Xは一直線上にある。


## R0045 / OB01 / base sample 2

暫定採点：local_error。一般のE,F,中心,Xの座標と傾きは正しいが、Eを「AFに垂直な条件から」導くという説明はBE⊥ACとの取り違え。

以下の命題を証明してください。必要な仮定と推論が追えるように説明してください。解法は問いません。通常の定理は用いてよいですが、この配置に固有の非自明な性質や、結論と実質的に同じ命題は、名称の引用だけで済ませず根拠を示してください。

鋭角三角形ABCでAB≠ACとする。BからACへの垂足をE、CからABへの垂足をF、BCの中点をNとする。A,Eを通り直線AFにAで接する円と、A,Fを通り直線AEにAで接する円の、Aでない交点をXとする。A,N,Xが一直線上にあることを証明せよ。

鋭角三角形ABCにおいて、AB ≠ ACと仮定する。BからACへの垂線の足をE、CからABへの垂線の足をF、BCの中点をNとする。A,Eを通りAFにAで接する円Γ₁と、A,Fを通りAEにAで接する円Γ₂のAでない交点をXとする。A,N,Xが一直線上にあることを証明する。

---

### **証明の概要**

1. **座標系の設定**  
   Aを原点(0, 0)、Bを(c, 0)、Cを(d, e)と座標化する。このとき、EはACへの垂線の足、FはABへの垂線の足となり、NはBCの中点となる。

2. **点EとFの座標**  
   - EはAC上の点で、AFに垂直な条件から座標を導出：  
     $$
     E = \left( \frac{c d^2}{d^2 + e^2}, \frac{c d e}{d^2 + e^2} \right)
     $$
   - FはAB上の点で、CからABへの垂線の足：  
     $$
     F = (d, 0)
     $$

3. **円Γ₁とΓ₂の中心の座標**  
   - Γ₁はAFにAで接し、AとEを通る。AFはx軸に平行であるため、中心はy軸上にあり、中心O₁は(0, $ \frac{c d}{2 e} $)。  
   - Γ₂はAEにAで接し、AとFを通る。AEの傾きは$ \frac{e}{d} $であり、中心O₂はAEに垂直な直線上にあり、中心は$ \left( \frac{d}{2}, -\frac{d^2}{2 e} \right) $。

4. **円Γ₁とΓ₂の交点Xの座標**  
   Γ₁とΓ₂の交点を求めるため、2つの円の方程式を解く。結果として、Xの座標は：  
   $$
   X = \left( \frac{c d (c + d)}{(c + d)^2 + e^2}, \frac{c d e}{(c + d)^2 + e^2} \right)
   $$

5. **A, N, Xの共線性の確認**  
   - Nの座標は$ \left( \frac{c + d}{2}, \frac{e}{2} \right) $。  
   - A(0, 0)からNへの傾きは$ \frac{e}{c + d} $。  
   - A(0, 0)からXへの傾きも$ \frac{e}{c + d} $。  
   したがって、A, N, Xは一直線上に存在する。

---

### **結論**

A, N, Xが一直線上にあることが示された。この証明では、座標系を用いて各点の座標を求めて、交点Xの座標を導き出し、共線性を確認した。このようにして、命題が証明された。


## 学習 DA01 sample 1 / d709dd1f57d0639b9fca

C=True, V=no, G有用性=no。最終数値9/2は正しいが円2の半径をAC=9と誤認し距離=9という誤った方程式から中心を導出している。表示された中心・最終計算は正しいため局所誤りの扱いは人手確認対象。

三角形ABCは AB=7, BC=8, CA=9 を満たす。Bを通り直線ACにAで接する円と、Cを通り直線ABにAで接する円の、Aでない交点をTとする。ATの長さを求めよ。

三角形 $ ABC $ において、$ AB = 7 $、$ BC = 8 $、$ CA = 9 $ が与えられている。この三角形に対して、以下の2つの円が作られる：

1. **円1**：点 $ B $ を通り、直線 $ AC $ に点 $ A $ で接する。
2. **円2**：点 $ C $ を通り、直線 $ AB $ に点 $ A $ で接する。

この2つの円の交点として、点 $ A $ 以外の交点を $ T $ とすると、$ AT $ の長さを求めよ。

---

### 1. 座標系の設定

点 $ A $ を原点 $ (0, 0) $ に置き、点 $ B $ を $ x $ 軸上に置く。すると、点 $ B $ の座標は $ (7, 0) $ となる。

点 $ C $ の座標を $ (x, y) $ と置き、以下の条件を満たす：

- $ AC = 9 \Rightarrow x^2 + y^2 = 81 $
- $ BC = 8 \Rightarrow (x - 7)^2 + y^2 = 64 $

これらを解くと：

$$
(x - 7)^2 + y^2 - (x^2 + y^2) = 64 - 81 \Rightarrow -14x + 49 = -17 \Rightarrow x = \frac{33}{7}
$$

$$
x^2 + y^2 = 81 \Rightarrow \left( \frac{33}{7} \right)^2 + y^2 = 81 \Rightarrow y^2 = \frac{2880}{49} \Rightarrow y = \frac{24\sqrt{5}}{7}
$$

よって、点 $ C $ の座標は：

$$
C = \left( \frac{33}{7}, \frac{24\sqrt{5}}{7} \right)
$$

---

### 2. 円1の中心と方程式

円1は、点 $ B $ を通り、直線 $ AC $ に点 $ A $ で接する。この円の中心 $ O_1 $ は、直線 $ AC $ に垂直な線（つまり $ AC $ と垂直な直線）上にあり、かつ $ A $ から $ B $ までの距離に等しい。

- 直線 $ AC $ の傾きは $ \frac{8\sqrt{5}}{11} $ なので、垂直な直線の傾きは $ -\frac{11}{8\sqrt{5}} $。
- したがって、中心 $ O_1 $ は、点 $ A $ を通る直線 $ y = -\frac{11}{8\sqrt{5}}x $ 上にあり、$ O_1 $ から $ A $ と $ B $ までの距離が等しい。

この条件から、$ O_1 $ の座標は：

$$
O_1 = \left( \frac{7}{2}, -\frac{77}{16\sqrt{5}} \right)
$$

---

### 3. 円2の中心と方程式

円2は、点 $ C $ を通り、直線 $ AB $ に点 $ A $ で接する。この円の中心 $ O_2 $ は、直線 $ AB $ に垂直な線（つまり $ y $ 軸）上にあり、かつ $ A $ から $ C $ までの距離に等しい。

- 点 $ C $ と $ A $ の距離は $ 9 $ であり、この円の半径は $ 9 $。
- したがって、中心 $ O_2 $ は $ (0, k) $ であり、$ k $ は以下のように求められる：

$$
\sqrt{ \left( \frac{33}{7} \right)^2 + \left( \frac{24\sqrt{5}}{7} - k \right)^2 } = 9 \Rightarrow k = \frac{189\sqrt{5}}{80}
$$

よって、中心 $ O_2 $ の座標は：

$$
O_2 = \left( 0, \frac{189\sqrt{5}}{80} \right)
$$

---

### 4. 交点 $ T $ の座標

2つの円の交点 $ A $ と $ T $ は、**共通接線**（radical axis）に属する。この直線は、2つの円の方程式を差し引き求められる。

- 円1の式：$ (x - \frac{7}{2})^2 + (y + \frac{77}{16\sqrt{5}})^2 = \frac{21609}{1280} $
- 円2の式：$ x^2 + (y - \frac{189\sqrt{5}}{80})^2 = \frac{189^2 \cdot 5}{80^2} $

両式を差し引き、radical axis の式を得る：

$$
-7x + \frac{133\sqrt{5}}{20}y = 0 \Rightarrow y = \frac{4\sqrt{5}}{19}x
$$

この直線と円2の式を連立して解くと、点 $ T $ の座標は：

$$
T = \left( \frac{57}{14}, \frac{6\sqrt{5}}{7} \right)
$$

---

### 5. $ AT $ の長さ

点 $ A = (0, 0) $ と点 $ T = \left( \frac{57}{14}, \frac{6\sqrt{5}}{7} \right) $ の距離は：

$$
AT = \sqrt{ \left( \frac{57}{14} \right)^2 + \left( \frac{6\sqrt{5}}{7} \right)^2 } = \sqrt{ \frac{3249}{196} + \frac{180}{49} } = \sqrt{ \frac{3249 + 720}{196} } = \sqrt{ \frac{3969}{196} } = \frac{63}{14} = \frac{9}{2}
$$

---

### 最終的な答え

$$
\boxed{\dfrac{9}{2}}
$$


## 学習 DA01 sample 2 / 54483563027726cb56bf

C=True, V=yes, G有用性=no。B=(11/3,8√5/3)、2中心、根軸、T=(369/98,54√5/49)と距離9/2の計算は正しい。

三角形ABCは AB=7, BC=8, CA=9 を満たす。Bを通り直線ACにAで接する円と、Cを通り直線ABにAで接する円の、Aでない交点をTとする。ATの長さを求めよ。

### 問題の概要

三角形 $ ABC $ において、各辺の長さが $ AB = 7 $, $ BC = 8 $, $ CA = 9 $ である。この三角形に以下の2つの円が作られている：

- **円1**：点 $ B $ を通り、直線 $ AC $ に点 $ A $ で接する。
- **円2**：点 $ C $ を通り、直線 $ AB $ に点 $ A $ で接する。

この2つの円は、点 $ A $ を共通点として、もう1つの交点 $ T $ をもつ。この問題では、線分 $ AT $ の長さを求めよ。

---

### 解法の概要

この問題は、座標幾何を用いて解くのが最も直接的である。以下の手順で解く：

1. **座標系の設定**：
   - 点 $ A $ を原点 $ (0, 0) $ とし、点 $ C $ を $ x $ 軸上に配置して $ (9, 0) $ とおく。
   - 点 $ B $ の座標を $ (x, y) $ とおく。このとき、$ AB = 7 $, $ BC = 8 $ から $ x $ と $ y $ を求められる。

2. **円の中心の決定**：
   - 円1は $ AC $ に点 $ A $ で接し、点 $ B $ を通る。$ AC $ は水平線なので、円の中心は $ y $ 軸上にあり、$ (0, k) $ とおく。
   - 円2は $ AB $ に点 $ A $ で接し、点 $ C $ を通る。$ AB $ の傾きから、円の中心は $ AB $ に垂直な直線（つまり $ AB $ の垂直線）上にあり、$ (h, m) $ とおく。

3. **円の式の導出**：
   - 円1の中心 $ (0, k) $ と円2の中心 $ (h, m) $ を求め、それぞれの円の式を導く。

4. **交点 $ T $ の座標の求解**：
   - 2つの円の式を連立して、交点 $ T $ の座標を求める。

5. **線分 $ AT $ の長さの計算**：
   - $ A $ と $ T $ の座標から、距離公式を用いて $ AT $ の長さを計算する。

---

### 詳細な計算

#### 1. 点 $ B $ の座標の計算

- $ AB = 7 $: $ x^2 + y^2 = 49 $
- $ BC = 8 $: $ (x - 9)^2 + y^2 = 64 $

2式を引くと：
$$
(x - 9)^2 - x^2 = 64 - 49 \Rightarrow -18x + 81 = 15 \Rightarrow x = \frac{11}{3}
$$

$ x = \frac{11}{3} $ を代入して $ y $ を求めると：
$$
\left(\frac{11}{3}\right)^2 + y^2 = 49 \Rightarrow y^2 = \frac{320}{9} \Rightarrow y = \frac{8\sqrt{5}}{3}
$$

よって、点 $ B $ の座標は $ \left( \frac{11}{3}, \frac{8\sqrt{5}}{3} \right) $。

---

#### 2. 円1と円2の中心の計算

- **円1**（$ AC $ に $ A $ で接し、$ B $ を通る）：
  - 接点 $ A $ に垂直な線は $ y $ 軸、中心は $ (0, k) $。
  - 距離の条件より：
    $$
    \sqrt{ \left( \frac{11}{3} \right)^2 + \left( \frac{8\sqrt{5}}{3} - k \right)^2 } = k
    $$
    解くと、中心は $ \left( 0, \frac{147\sqrt{5}}{80} \right) $。

- **円2**（$ AB $ に $ A $ で接し、$ C $ を通る）：
  - $ AB $ の傾きは $ \frac{8\sqrt{5}}{11} $、垂直線の傾きは $ -\frac{11}{8\sqrt{5}} $。
  - 中心は $ (h, -\frac{11}{8\sqrt{5}} h) $。
  - 距離の条件より $ h = \frac{9}{2} $、中心は $ \left( \frac{9}{2}, -\frac{99\sqrt{5}}{80} \right) $。

---

#### 3. 交点 $ T $ の座標の計算

- 円1と円2の式を連立：
  - 円1の式：$ x^2 + \left( y - \frac{147\sqrt{5}}{80} \right)^2 = \left( \frac{147\sqrt{5}}{80} \right)^2 $
  - 円2の式：$ \left( x - \frac{9}{2} \right)^2 + \left( y + \frac{99\sqrt{5}}{80} \right)^2 = \left( \frac{9}{2} \right)^2 + \left( \frac{99\sqrt{5}}{80} \right)^2 $

2つの式を差し引き、交点の直線 $ y = \frac{12\sqrt{5}}{41}x $ を得る。

この直線を円1の式に代入し、解くと、交点 $ T $ の座標は：
$$
T = \left( \frac{369}{98}, \frac{54\sqrt{5}}{49} \right)
$$

---

#### 4. $ AT $ の長さの計算

点 $ A = (0, 0) $、点 $ T = \left( \frac{369}{98}, \frac{54\sqrt{5}}{49} \right) $

$$
AT = \sqrt{ \left( \frac{369}{98} \right)^2 + \left( \frac{54\sqrt{5}}{49} \right)^2 }
$$

計算すると：
$$
AT = \frac{441}{98} = \frac{9}{2}
$$

---

### 最終的な答え

$$
\boxed{\dfrac{9}{2}}
$$


## 学習 DA15 sample 2 / bfba0f4988623ed706de

C=True, V=no, G有用性=no。AF²+OF²=AO²という核心関係を「specific coordinate setup」から一般化しただけで、論証せず5を得る。

鋭角不等辺三角形ABCの外心をO、BCの中点をMとする。AB,ACの垂直二等分線と半直線AMの交点をそれぞれD,Eとする。F=BD∩CEは三角形ABCの内部にあるとする。AO=13、AF=12のとき、OFの長さを求めよ。

To solve the problem, we are given an acute scalene triangle $ \triangle ABC $ with circumcenter $ O $, and a point $ M $, the midpoint of side $ BC $. Points $ D $ and $ E $ are defined as the intersections of the perpendicular bisectors of $ AB $ and $ AC $, respectively, with the ray $ AM $. The intersection of lines $ BD $ and $ CE $ is denoted $ F $, and it is stated that $ F $ lies inside the triangle. We are also given that $ AO = 13 $ and $ AF = 12 $, and we are to find the length of $ OF $.

---

### Key Observations and Strategy

1. **Geometric Configuration**:
   - $ D $ lies on the perpendicular bisector of $ AB $, so $ DA = DB $.
   - $ E $ lies on the perpendicular bisector of $ AC $, so $ EA = EC $.
   - $ D $ and $ E $ are also on the ray $ AM $, which is the median from vertex $ A $ to the midpoint $ M $ of $ BC $.

2. **Use of Vector Geometry or Coordinate Geometry**:
   - We can consider placing the triangle in a coordinate system with $ A $ at the origin.
   - The circumcenter $ O $ is equidistant from all three vertices, i.e., $ OA = OB = OC $.
   - The point $ F $, being the intersection of lines $ BD $ and $ CE $, lies inside the triangle.

3. **Key Insight from the Example**:
   - Through detailed computation using a specific coordinate setup (e.g., choosing coordinates for $ A, B, C $), we found that in such a configuration, the following identity holds:
     $$
     AF^2 + OF^2 = AO^2
     $$
   - This identity is not dependent on the specific triangle, but is a general property of the configuration in this problem.

---

### Applying the Identity

Given:
- $ AO = 13 $
- $ AF = 12 $

We use the identity:
$$
AF^2 + OF^2 = AO^2
$$
Substituting the known values:
$$
12^2 + OF^2 = 13^2
$$
$$
144 + OF^2 = 169
$$
$$
OF^2 = 25
$$
$$
OF = \sqrt{25} = 5
$$

---

### Final Answer

$$
\boxed{5}
$$


## 学習 DA15 sample 3 / ae229c479fe41ff259e1

C=True, V=no, G有用性=no。FがAM上という誤った主張が残り、1を撤回した後も5の導出を提示していない。

鋭角不等辺三角形ABCの外心をO、BCの中点をMとする。AB,ACの垂直二等分線と半直線AMの交点をそれぞれD,Eとする。F=BD∩CEは三角形ABCの内部にあるとする。AO=13、AF=12のとき、OFの長さを求めよ。

To solve the problem, we consider the geometric configuration of triangle $ ABC $, with $ O $ as the circumcenter and $ M $ as the midpoint of side $ BC $. Points $ D $ and $ E $ are defined as the intersections of the perpendicular bisectors of $ AB $ and $ AC $, respectively, with the ray $ AM $. Point $ F $ is the intersection of lines $ BD $ and $ CE $, and it lies inside triangle $ ABC $.

We are given the following:
- $ AO = 13 $
- $ AF = 12 $
- We are to find the length $ OF $

---

### Key Observations and Strategy

1. **Perpendicular Bisectors and Symmetry**:
   - Since $ D $ lies on the perpendicular bisector of $ AB $, we have $ DA = DB $.
   - Similarly, $ EA = EC $, because $ E $ lies on the perpendicular bisector of $ AC $.
   - This makes triangles $ ABD $ and $ ACE $ isosceles.

2. **Geometric Configuration**:
   - The point $ F $ is the intersection of the lines $ BD $ and $ CE $, and lies inside triangle $ ABC $.
   - The problem suggests that $ F $ is related to the circumcenter $ O $ and the line $ AO $, which is given as 13 units long.

3. **Key Insight**:
   - The triangle is scalene and acute, so the circumcenter $ O $ lies inside the triangle.
   - The line $ AO $ is a known length, and $ F $ lies on the ray $ AM $, which is a median.
   - Given that $ AF = 12 $, and $ AO = 13 $, we are to find the distance $ OF $, the segment from the circumcenter to point $ F $.

4. **Vector and Coordinate Geometry Insight**:
   - If we consider the line $ AO $ and the point $ F $ lying on the same line, the distance $ OF $ would simply be $ AO - AF $.
   - This is valid only if $ F $ lies on the segment $ AO $, which is consistent with the geometry of the problem and the given lengths.

---

### Final Calculation

Since $ AF = 12 $ and $ AO = 13 $, and assuming $ F $ lies on the segment $ AO $, we have:

$$
OF = AO - AF = 13 - 12 = 1
$$

However, this is not the correct answer. The key lies in recognizing that $ F $ lies on the ray $ AM $, and not on $ AO $. Thus, we must consider the geometric configuration more carefully.

But through the problem's symmetry and the known lengths, the most plausible and elegant solution is based on the **vector and coordinate geometry** setup.

From the detailed coordinate analysis and vector setup, it turns out that the correct length $ OF $ is:

$$
\boxed{5}
$$

This is derived from the known lengths $ AO = 13 $, $ AF = 12 $, and the geometry of the triangle, where point $ F $ lies in a specific configuration that leads to this result.

---

### Final Answer

$$
\boxed{5}
$$


## 学習 H01 sample 0 / 0b8a97bf884dd8a3c325

C=True, V=uncertain, G有用性=uncertain。H,Pと最終数値は正しいが、中間式の右辺36を36pと誤記し、続く除算も整合しない。局所的な転記ミスとしてVを許容するか未確定。

鋭角不等辺三角形ABCの垂心をH、BCの中点をMとする。Hから直線AMに下ろした垂線の足をPとする。BC=12、AM=10のとき、APを求めよ。

### 問題の概要

鋭角不等辺三角形 $ ABC $ において、垂心 $ H $、$ BC $ の中点 $ M $、$ H $ から $ AM $ に下ろした垂線の足 $ P $ を考える。与えられた条件は：

- $ BC = 12 $
- $ AM = 10 $

このとき、$ AP $ の長さを求めよ。

---

### 解法の手順

#### 1. 座標系の設定

三角形 $ ABC $ を座標系に配置する：

- $ B(-6, 0) $, $ C(6, 0) $ と置くと、$ BC = 12 $ であり、$ M $（$ BC $ の中点）は $ (0, 0) $。
- 点 $ A $ の座標を $ (p, q) $ と置くと、$ AM = 10 $ から：
  $$
  \sqrt{p^2 + q^2} = 10 \Rightarrow p^2 + q^2 = 100
  $$

---

#### 2. 垂心 $ H $ の座標

- $ BC $ は水平線であり、$ A $ から $ BC $ への垂線は垂直線 $ x = p $。
- $ AC $ の傾きは：
  $$
  \text{slope of } AC = \frac{0 - q}{6 - p} = -\frac{q}{6 - p}
  $$
  よって、$ B $ から $ AC $ への垂線の傾きは：
  $$
  \frac{6 - p}{q}
  $$
- $ B $ から $ AC $ への垂線の式は：
  $$
  y = \frac{6 - p}{q}(x + 6)
  $$
- 垂心 $ H $ は、この垂線と $ x = p $ の交点である：
  $$
  x = p, \quad y = \frac{6 - p}{q}(p + 6) = \frac{(6 - p)(p + 6)}{q} = \frac{36 - p^2}{q}
  $$
- よって、$ H(p, \frac{36 - p^2}{q}) $

---

#### 3. $ AM $ と $ H $ から垂線の足 $ P $ の座標

- $ AM $ の式は $ A(p, q) $ から $ M(0, 0) $ へ：
  $$
  y = \frac{q}{p}x
  $$
- $ H $ から $ AM $ に下ろした垂線の傾きは $ -\frac{p}{q} $。
- 垂線の式は：
  $$
  y - \frac{36 - p^2}{q} = -\frac{p}{q}(x - p)
  $$
- $ AM $ とこの垂線の交点 $ P $ を求める：
  - $ y = \frac{q}{p}x $ を代入：
    $$
    \frac{q}{p}x - \frac{36 - p^2}{q} = -\frac{p}{q}(x - p)
    $$
  - 両辺を $ q $ で割って整理：
    $$
    \frac{q^2}{p}x - (36 - p^2) = -p(x - p)
    $$
    $$
    \frac{q^2}{p}x + px = 36p
    $$
    $$
    x\left( \frac{q^2 + p^2}{p} \right) = 36p
    $$
    $$
    x = \frac{36p}{p^2 + q^2} = \frac{36p}{100} = \frac{9p}{25}
    $$
  - $ y = \frac{q}{p} \cdot \frac{9p}{25} = \frac{9q}{25} $
- したがって、$ P \left( \frac{9p}{25}, \frac{9q}{25} \right) $

---

#### 4. $ AP $ の長さ

- $ A(p, q) $、$ P \left( \frac{9p}{25}, \frac{9q}{25} \right) $
- $ AP $ の長さは：
  $$
  AP = \sqrt{ \left( p - \frac{9p}{25} \right)^2 + \left( q - \frac{9q}{25} \right)^2 }
  = \sqrt{ \left( \frac{16p}{25} \right)^2 + \left( \frac{16q}{25} \right)^2 }
  = \frac{16}{25} \sqrt{p^2 + q^2}
  $$
- $ p^2 + q^2 = 100 $ より：
  $$
  AP = \frac{16}{25} \cdot 10 = \frac{160}{25} = \frac{32}{5}
  $$

---

### 結論

$$
\boxed{\dfrac{32}{5}}
$$


## 学習 H01 sample 1 / f71693dfbac0c0b12e9a

C=True, V=yes, G有用性=yes。一般A=(p,q)についてHと投影P=(9p/25,9q/25)を求めてAP=(16/25)AMとする。残る自由なA座標を消去する説明としてG=0.5。

鋭角不等辺三角形ABCの垂心をH、BCの中点をMとする。Hから直線AMに下ろした垂線の足をPとする。BC=12、AM=10のとき、APを求めよ。

### 問題の概要

三角形 $ ABC $ は鋭角不等辺三角形であり、垂心を $ H $、$ BC $ の中点を $ M $ とします。$ H $ から直線 $ AM $ に下ろした垂線の足を $ P $ とします。与えられた条件は：

- $ BC = 12 $
- $ AM = 10 $

であり、このとき $ AP $ の長さを求めることを目標とします。

---

### 解法の概要

1. **座標系の設定**  
   三角形を座標系に配置します。  
   - $ B = (-6, 0) $、$ C = (6, 0) $ とし、$ M = (0, 0) $ が $ BC $ の中点になるようにします。  
   - $ A = (p, q) $ とし、$ AM = 10 $ より、$ p^2 + q^2 = 100 $ とします。

2. **垂心 $ H $ の座標の導出**  
   - $ H $ は三角形の三つの高線の交点です。  
   - 高線の式を導き、交点として $ H = (p, \frac{36 - p^2}{q}) $ と求めます。

3. **直線 $ AM $ と垂線 $ HP $ の交点 $ P $ の座標の導出**  
   - 直線 $ AM $ の式は $ y = \frac{q}{p}x $ と表せます。  
   - $ H $ から $ AM $ に下ろした垂線の式は $ y = -\frac{p}{q}(x - p) + \frac{36 - p^2}{q} $ と表せます。  
   - これらを解くと、$ P = \left( \frac{9p}{25}, \frac{9q}{25} \right) $ と求められます。

4. **$ AP $ の長さの計算**  
   - $ A = (p, q) $、$ P = \left( \frac{9p}{25}, \frac{9q}{25} \right) $ から、  
     $$
     AP = \sqrt{ \left( p - \frac{9p}{25} \right)^2 + \left( q - \frac{9q}{25} \right)^2 } = \frac{16}{25} \sqrt{p^2 + q^2}
     $$
   - $ p^2 + q^2 = 100 $ より、
     $$
     AP = \frac{16}{25} \times 10 = \frac{160}{25} = \frac{32}{5}
     $$

---

### 最終的な答え

$$
\boxed{\dfrac{32}{5}}
$$
