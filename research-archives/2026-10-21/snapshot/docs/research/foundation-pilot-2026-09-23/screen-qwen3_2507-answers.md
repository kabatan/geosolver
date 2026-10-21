## F01 sample 0

A point S outside a circle has a tangent ST. A secant meets the circle at U,V in the order S,U,V, with SU=3 and UV=9. Find ST. Establish the product identity you use from similar triangles instead of citing the power-of-a-point theorem.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 8192; finish: length.

[No completed final answer; raw generation retained in the source JSON.]

Grade: {"valid": false, "method": "none", "note": "Token limit reached without a complete final proof.", "repairable": false}

## F01 sample 1

A point S outside a circle has a tangent ST. A secant meets the circle at U,V in the order S,U,V, with SU=3 and UV=9. Find ST. Establish the product identity you use from similar triangles instead of citing the power-of-a-point theorem.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 6152; finish: stop.



To find the length of the tangent $ ST $ from an external point $ S $ to a circle, where a secant intersects the circle at points $ U $ and $ V $ in the order $ S, U, V $ with $ SU = 3 $ and $ UV = 9 $, we use **similar triangles** instead of directly invoking the power-of-a-point theorem.

---

### Step 1: Understand the Geometry

- Point $ S $ lies outside the circle.
- A **tangent** $ ST $ touches the circle at point $ T $.
- A **secant** passes through the circle, intersecting it at two points $ U $ and $ V $, such that $ S $ is outside and the order along the line is $ S \rightarrow U \rightarrow V $.
- Given:
  - $ SU = 3 $
  - $ UV = 9 $
  - Therefore, $ SV = SU + UV = 3 + 9 = 12 $

We are to find the length $ ST $ using **similar triangles**, not the power-of-a-point theorem.

---

### Step 2: Apply the Alternate Segment Theorem

The **Alternate Segment Theorem** states:

> The angle between a tangent and a chord through the point of contact is equal to the angle in the alternate segment (i.e., the angle subtended by the chord in the opposite segment of the circle).

In this case:
- Tangent at $ T $: $ ST $
- Chord from $ T $ to $ U $: $ TU $
- So, $ \angle STU = \angle TVU $

This is because $ \angle TVU $ is the angle subtended by chord $ TU $ in the **alternate segment** of the circle.

---

### Step 3: Identify Similar Triangles

Now consider triangles $ \triangle STU $ and $ \triangle SVT $:

- $ \angle TSU $ is common to both triangles (angle at $ S $).
- From the Alternate Segment Theorem: $ \angle STU = \angle TVS $ (since $ \angle TVU = \angle TVS $ due to the collinearity of $ S, U, V $).

Thus, by **AA similarity** (two corresponding angles equal), we have:

$$
\triangle STU \sim \triangle SVT
$$

---

### Step 4: Use the Proportion from Similar Triangles

From the similarity $ \triangle STU \sim \triangle SVT $, the ratio of corresponding sides gives:

$$
\frac{SU}{ST} = \frac{ST}{SV}
$$

Cross-multiplying:

$$
ST^2 = SU \cdot SV
$$

Substitute known values:

- $ SU = 3 $
- $ SV = 12 $

$$
ST^2 = 3 \cdot 12 = 36 \quad \Rightarrow \quad ST = \sqrt{36} = 6
$$

---

### Final Answer

$$
\boxed{6}
$$

This result was derived using **similar triangles** based on the **Alternate Segment Theorem**, without invoking the power-of-a-point theorem. The key was identifying the correct pair of equal angles to establish triangle similarity and then applying the proportionality of corresponding sides.<|im_end|>

Grade: {"valid": true, "method": "synthetic", "note": "Correct tangent-chord correspondence and ST²=SU*SV.", "repairable": false}

## F02 sample 0

Two chords AC and BD of a circle meet at an interior point P. PA=3, PC=8, PB=4. Find PD. Derive the needed product relation from angles and similar triangles instead of quoting the intersecting-chords theorem.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 8169; finish: stop.



To solve the problem of finding $ PD $ given that chords $ AC $ and $ BD $ intersect at an interior point $ P $ with segment lengths $ PA = 3 $, $ PC = 8 $, and $ PB = 4 $, we derive the necessary product relation using **angles and similar triangles**, without invoking the intersecting chords theorem directly.

---

### Step 1: Identify Equal Angles via Inscribed Angles

Since points $ A, B, C, D $ lie on a circle and chords $ AC $ and $ BD $ intersect at an interior point $ P $, we can apply the **Inscribed Angle Theorem** to identify equal angles:

- **Angle $ \angle PAB $** (at vertex $ A $) subtends arc $ BC $
- **Angle $ \angle PDC $** (at vertex $ D $) also subtends arc $ BC $

Therefore, by the Inscribed Angle Theorem:
$$
\angle PAB = \angle PDC
$$

Similarly:
- **Angle $ \angle PBA $** (at vertex $ B $) subtends arc $ AD $
- **Angle $ \angle PCD $** (at vertex $ C $) also subtends arc $ AD $

So:
$$
\angle PBA = \angle PCD
$$

---

### Step 2: Establish Triangle Similarity

From the above, in triangles $ \triangle APB $ and $ \triangle DPC $, we have:

- $ \angle PAB = \angle PDC $
- $ \angle PBA = \angle PCD $

By the **AA Similarity Criterion**, these two triangles are similar:
$$
\triangle APB \sim \triangle DPC
$$

This similarity is crucial because it allows us to write proportional side relationships between corresponding sides.

---

### Step 3: Use Proportions from Similar Triangles

Given the correspondence of vertices:
$$
\triangle APB \sim \triangle DPC \quad \text{with } A \leftrightarrow D,\; P \leftrightarrow P,\; B \leftrightarrow C
$$

The corresponding sides are:
- $ AP \leftrightarrow DP $
- $ PB \leftrightarrow PC $

Thus, the ratio of corresponding sides gives:
$$
\frac{AP}{DP} = \frac{PB}{PC}
$$

Substitute the known values:
$$
\frac{3}{PD} = \frac{4}{8}
$$

Solve for $ PD $:
$$
PD = \frac{3 \cdot 8}{4} = \frac{24}{4} = 6
$$

---

### Final Justification

We derived the product relation $ PB \cdot PD = PA \cdot PC $ through **angle chasing using the Inscribed Angle Theorem** and **triangle similarity** (AA criterion), without relying on the intersecting chords theorem. This method is rigorous and fully justifies the result.

---

### Final Answer

$$
\boxed{6}
$$<|im_end|>

Grade: {"valid": true, "method": "synthetic", "note": "Correct subtended arcs and explicit APB-DPC correspondence; PD=6.", "repairable": false}

## F02 sample 1

Two chords AC and BD of a circle meet at an interior point P. PA=3, PC=8, PB=4. Find PD. Derive the needed product relation from angles and similar triangles instead of quoting the intersecting-chords theorem.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 8192; finish: length.

[No completed final answer; raw generation retained in the source JSON.]

Grade: {"valid": false, "method": "none", "note": "Token limit reached without a complete final proof.", "repairable": false}

## F03 sample 0

Triangle ABC is right-angled at A. The perpendicular from A to BC meets BC at D. Given BD=4 and DC=9, find AD and AB. Justify the relations rather than citing a special theorem about the altitude to a hypotenuse.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 5882; finish: stop.



To solve the problem, we begin by placing triangle $ ABC $ in a coordinate system that simplifies the geometry and leverages the given conditions.

---

### **Step 1: Coordinate Setup**

Let’s place point $ D $ (the foot of the perpendicular from $ A $ to $ BC $) at the origin:  
- $ D = (0, 0) $
- Since $ BD = 4 $, place $ B = (-4, 0) $
- Since $ DC = 9 $, place $ C = (9, 0) $

Because $ AD \perp BC $, and $ BC $ lies along the x-axis, the line $ AD $ must be vertical. Therefore, point $ A $ has coordinates $ (0, h) $ for some $ h > 0 $.

---

### **Step 2: Use of Right Angle at $ A $**

We are told that triangle $ ABC $ is right-angled at $ A $. This implies that vectors $ \vec{AB} $ and $ \vec{AC} $ are perpendicular. Let's compute these vectors:

- $ \vec{AB} = B - A = (-4 - 0, 0 - h) = (-4, -h) $
- $ \vec{AC} = C - A = (9 - 0, 0 - h) = (9, -h) $

The dot product of $ \vec{AB} $ and $ \vec{AC} $ must be zero because they are perpendicular:

$$
\vec{AB} \cdot \vec{AC} = (-4)(9) + (-h)(-h) = -36 + h^2 = 0
$$

Solving this equation:

$$
h^2 = 36 \quad \Rightarrow \quad h = 6 \quad (\text{since } h > 0)
$$

So, the length of $ AD = h = 6 $.

---

### **Step 3: Find Length of $ AB $**

Now that we know $ A = (0, 6) $ and $ B = (-4, 0) $, we can compute the distance $ AB $ using the distance formula:

$$
AB = \sqrt{(-4 - 0)^2 + (0 - 6)^2} = \sqrt{16 + 36} = \sqrt{52} = 2\sqrt{13}
$$

---

### **Final Answer**

- $ \boxed{AD = 6} $
- $ \boxed{AB = 2\sqrt{13}} $

---

### **Justification Summary**

This solution uses only basic coordinate geometry and vector properties. The key steps rely on:
- Placing the triangle in a convenient coordinate system,
- Using the fact that $ AD \perp BC $ to align $ A $ vertically above $ D $,
- Applying the condition of perpendicularity at $ A $ via the dot product (a consequence of the Pythagorean theorem),
- Computing distances directly from coordinates.

No special theorems about altitudes or similar triangles are cited; all relations are derived from fundamental geometric principles and the definition of perpendicular vectors.

This method is both concise and fully justified without invoking any special theorems beyond the standard Pythagorean theorem and vector dot product.<|im_end|>

Grade: {"valid": true, "method": "analytic", "note": "General right-triangle coordinates and dot product determine AD=6, AB=2sqrt(13).", "repairable": false}

## F03 sample 1

Triangle ABC is right-angled at A. The perpendicular from A to BC meets BC at D. Given BD=4 and DC=9, find AD and AB. Justify the relations rather than citing a special theorem about the altitude to a hypotenuse.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 4728; finish: stop.



To solve the problem, we are given a right triangle $ \triangle ABC $ with a right angle at $ A $, and the perpendicular from $ A $ to hypotenuse $ BC $ meets $ BC $ at point $ D $. We are told that $ BD = 4 $ and $ DC = 9 $, so the total length of the hypotenuse is:

$$
BC = BD + DC = 4 + 9 = 13
$$

We are to find the lengths of $ AD $ (the altitude from $ A $ to $ BC $) and $ AB $, **without citing any special theorems about the altitude to the hypotenuse**.

---

### Step 1: Use the Pythagorean Theorem in Sub-triangles

Let:
- $ h = AD $
- $ x = AB $
- $ y = AC $

Since $ AD \perp BC $, triangles $ \triangle ABD $, $ \triangle ADC $, and $ \triangle ABC $ are all right-angled.

From the right triangle $ \triangle ABD $:
$$
x^2 = h^2 + BD^2 = h^2 + 16 \tag{1}
$$

From the right triangle $ \triangle ADC $:
$$
y^2 = h^2 + DC^2 = h^2 + 81 \tag{2}
$$

From the right triangle $ \triangle ABC $:
$$
x^2 + y^2 = BC^2 = 13^2 = 169 \tag{3}
$$

---

### Step 2: Substitute Equations (1) and (2) into Equation (3)

Substitute $ x^2 $ and $ y^2 $ from equations (1) and (2) into equation (3):

$$
(h^2 + 16) + (h^2 + 81) = 169
$$

Simplify:
$$
2h^2 + 97 = 169
$$

Solve for $ h^2 $:
$$
2h^2 = 72 \quad \Rightarrow \quad h^2 = 36 \quad \Rightarrow \quad h = 6
$$

So, $ AD = 6 $

---

### Step 3: Find $ AB $

Now substitute $ h = 6 $ back into equation (1):

$$
x^2 = h^2 + 16 = 36 + 16 = 52 \quad \Rightarrow \quad x = \sqrt{52} = 2\sqrt{13}
$$

Thus, $ AB = 2\sqrt{13} $

---

### Final Answer

$$
\boxed{AD = 6,\quad AB = 2\sqrt{13}}
$$

This solution uses only the **Pythagorean Theorem** on the right triangles formed by the perpendicular from $ A $ to $ BC $, without invoking any special theorems about the altitude to the hypotenuse. All steps are justified using basic geometric principles and algebraic manipulation.<|im_end|>

Grade: {"valid": true, "method": "analytic", "note": "Three Pythagorean equations eliminate AB and AC and give the correct lengths.", "repairable": false}

## F04 sample 0

ABC is an acute triangle. D is the foot of the perpendicular from B to AC, and E is the foot from C to AB. Prove that angle ADE equals angle ABC.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 8192; finish: length.

[No completed final answer; raw generation retained in the source JSON.]

Grade: {"valid": false, "method": "none", "note": "Token limit reached without a complete final proof.", "repairable": false}

## F04 sample 1

ABC is an acute triangle. D is the foot of the perpendicular from B to AC, and E is the foot from C to AB. Prove that angle ADE equals angle ABC.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 8192; finish: length.

[No completed final answer; raw generation retained in the source JSON.]

Grade: {"valid": false, "method": "none", "note": "Token limit reached without a complete final proof.", "repairable": false}

## F05 sample 0

ABCD is a convex trapezoid with AB parallel to CD, AB=6, CD=10. Diagonals AC and BD intersect at O. The line through O parallel to the bases meets AD at E and BC at F. Find EF.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 8192; finish: length.

[No completed final answer; raw generation retained in the source JSON.]

Grade: {"valid": false, "method": "none", "note": "Token limit reached without a complete final proof.", "repairable": false}

## F05 sample 1

ABCD is a convex trapezoid with AB parallel to CD, AB=6, CD=10. Diagonals AC and BD intersect at O. The line through O parallel to the bases meets AD at E and BC at F. Find EF.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 8192; finish: length.

[No completed final answer; raw generation retained in the source JSON.]

Grade: {"valid": false, "method": "none", "note": "Token limit reached without a complete final proof.", "repairable": false}

## F06 sample 0

In triangle ABC, D is inside AB and E is inside AC, with AD/DB=AE/EC=2/3. Lines BE and CD intersect at F. Find BF/FE.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 7661; finish: stop.



To determine the ratio $ \frac{BF}{FE} $ in triangle $ ABC $, where point $ D $ lies on segment $ AB $ and point $ E $ lies on segment $ AC $ such that:

$$
\frac{AD}{DB} = \frac{AE}{EC} = \frac{2}{3}
$$

and lines $ BE $ and $ CD $ intersect at point $ F $, we can apply **mass point geometry** as a concise and elegant method.

---

### Step 1: Assign Masses Based on Given Ratios

We are given that:

- $ \frac{AD}{DB} = \frac{2}{3} $ ⇒ $ AD : DB = 2 : 3 $
- $ \frac{AE}{EC} = \frac{2}{3} $ ⇒ $ AE : EC = 2 : 3 $

In mass point geometry, the masses assigned to vertices are inversely proportional to the segments they divide. That is:

- For segment $ AB $ with $ AD : DB = 2 : 3 $, assign mass $ m_A = 3 $, $ m_B = 2 $
- For segment $ AC $ with $ AE : EC = 2 : 3 $, assign mass $ m_A = 3 $, $ m_C = 2 $

This ensures consistency at vertex $ A $, since both ratios give $ m_A = 3 $.

So, the masses are:
- $ m_A = 3 $
- $ m_B = 2 $
- $ m_C = 2 $

---

### Step 2: Compute Masses at Points $ D $ and $ E $

- Point $ D $ lies on $ AB $, so its mass is $ m_D = m_A + m_B = 3 + 2 = 5 $
- Point $ E $ lies on $ AC $, so its mass is $ m_E = m_A + m_C = 3 + 2 = 5 $

---

### Step 3: Use Mass Point to Find $ \frac{BF}{FE} $

Now consider line $ BE $, which connects points $ B $ (mass 2) and $ E $ (mass 5). The key principle of mass point geometry is:

> The ratio of the segments created by an intersection point is **inversely proportional** to the masses at the endpoints.

Thus,

$$
\frac{BF}{FE} = \frac{m_E}{m_B} = \frac{5}{2}
$$

---

### Final Answer

$$
\boxed{\dfrac{5}{2}}
$$<|im_end|>

Grade: {"valid": true, "method": "synthetic", "note": "Consistent mass assignments A=3,B=C=2, E=5; standard mass-point composition gives BF/FE=5/2.", "repairable": false}

## F06 sample 1

In triangle ABC, D is inside AB and E is inside AC, with AD/DB=AE/EC=2/3. Lines BE and CD intersect at F. Find BF/FE.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 4516; finish: stop.



To solve the problem, we are given triangle $ ABC $ with points $ D $ on $ AB $ and $ E $ on $ AC $ such that:

$$
\frac{AD}{DB} = \frac{AE}{EC} = \frac{2}{3}
$$

Lines $ BE $ and $ CD $ intersect at point $ F $. We are to find the ratio $ \frac{BF}{FE} $.

---

### **Step 1: Use Mass Point Geometry**

This is a classic setup for **mass point geometry**, which is particularly effective for problems involving ratios along segments in triangles.

- On segment $ AB $, since $ \frac{AD}{DB} = \frac{2}{3} $, assign mass $ m_A = 3 $, $ m_B = 2 $, so that the mass at $ D $ is $ m_D = m_A + m_B = 5 $.
- On segment $ AC $, since $ \frac{AE}{EC} = \frac{2}{3} $, assign mass $ m_A = 3 $, $ m_C = 2 $, so that the mass at $ E $ is $ m_E = m_A + m_C = 5 $.

Now consider the line $ BE $, where:
- Mass at $ B $ is $ m_B = 2 $
- Mass at $ E $ is $ m_E = 5 $

In mass point geometry, the ratio of segments created by an intersection point is **inversely proportional** to the masses at the endpoints. Therefore,

$$
\frac{BF}{FE} = \frac{m_E}{m_B} = \frac{5}{2}
$$

---

### **Step 2: Verification via Coordinate Geometry (Optional but Confirmatory)**

Let’s place triangle $ ABC $ in the coordinate plane for verification:

- Let $ A = (0, 0) $
- Let $ B = (5, 0) $, so $ AB $ lies along the x-axis
- Let $ C = (0, 5) $, so $ AC $ lies along the y-axis

Then:
- Point $ D $ divides $ AB $ in ratio $ 2:3 $, so $ D = \left( \frac{2}{5} \cdot 5, 0 \right) = (2, 0) $
- Point $ E $ divides $ AC $ in ratio $ 2:3 $, so $ E = \left( 0, \frac{2}{5} \cdot 5 \right) = (0, 2) $

Find equations of lines $ BE $ and $ CD $:

- Line $ BE $: from $ (5, 0) $ to $ (0, 2) $ → slope $ -\frac{2}{5} $, equation: $ y = -\frac{2}{5}x + 2 $
- Line $ CD $: from $ (0, 5) $ to $ (2, 0) $ → slope $ -\frac{5}{2} $, equation: $ y = -\frac{5}{2}x + 5 $

Solving for intersection $ F $:

$$
-\frac{2}{5}x + 2 = -\frac{5}{2}x + 5
\Rightarrow \text{Multiply both sides by 10: } -4x + 20 = -25x + 50
\Rightarrow 21x = 30 \Rightarrow x = \frac{10}{7}
$$

Substitute back to get $ y = \frac{10}{7} $, so $ F = \left( \frac{10}{7}, \frac{10}{7} \right) $

Now compute $ \frac{BF}{FE} $ using parameter $ t $ along segment $ BE $:

- Vector from $ B $ to $ E $: $ (-5, 2) $
- Parametrize $ BE $ as $ (5 - 5t, 2t) $
- Set $ 5 - 5t = \frac{10}{7} \Rightarrow t = \frac{5}{7} $

Thus, $ BF = \frac{5}{7} \cdot |BE| $, $ FE = \frac{2}{7} \cdot |BE| $, so:

$$
\frac{BF}{FE} = \frac{5/7}{2/7} = \frac{5}{2}
$$

---

### **Conclusion**

All methods—mass point geometry, coordinate geometry, and vector analysis—lead to the same result.

$$
\boxed{\frac{5}{2}}
$$<|im_end|>

Grade: {"valid": true, "method": "mixed", "note": "Valid mass-point proof plus explicitly optional numerical coordinate verification, not used as the only general proof.", "repairable": false}

## F07 sample 0

The two tangents from T touch a circle at A and B, and TA=7. A third tangent touches the minor arc AB at P and meets the segments TA and TB at X and Y. Assume P lies between X and Y, with T,X,A and T,Y,B in those respective orders. Find the perimeter of triangle TXY.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 6630; finish: stop.



To determine the **perimeter of triangle $ \triangle TXY $**, we analyze the geometric configuration involving a circle and tangents from an external point.

---

### **Key Setup and Given Information**

- Point $ T $ lies outside a circle.
- Two tangents from $ T $ touch the circle at points $ A $ and $ B $, so:
  $$
  TA = TB = 7
  $$
- A third tangent touches the **minor arc** $ AB $ at point $ P $, and intersects:
  - Segment $ TA $ at point $ X $ (with order $ T \rightarrow X \rightarrow A $)
  - Segment $ TB $ at point $ Y $ (with order $ T \rightarrow Y \rightarrow B $)
- Point $ P $ lies **between** $ X $ and $ Y $ on the tangent line $ XY $

We are to find the **perimeter** of triangle $ \triangle TXY $, i.e., 
$$
\text{Perimeter} = TX + XY + YT
$$

---

### **Geometric Insight Using Tangent Segment Theorem**

A crucial property of circles is that **tangents drawn from a single external point to a circle have equal length**.

Let’s apply this theorem to points $ X $ and $ Y $:

- From point $ X $, there are two tangents to the circle:
  - One is segment $ XA $ (along line $ TA $)
  - The other is segment $ XP $ (along the third tangent)
  - Therefore, $ XA = XP $

- From point $ Y $, there are two tangents to the circle:
  - One is segment $ YB $ (along line $ TB $)
  - The other is segment $ YP $ (along the third tangent)
  - Therefore, $ YB = YP $

---

### **Expressing the Perimeter**

Using the above equalities:

$$
\begin{aligned}
\text{Perimeter} &= TX + XY + YT \\
&= TX + (XP + PY) + YT \\
&= (TX + XP) + (PY + YT)
\end{aligned}
$$

Now substitute the known equalities:

- $ TX + XP = TX + XA = TA = 7 $
- $ PY + YT = YP + YT = YB + YT = TB = 7 $

So the total perimeter becomes:

$$
\text{Perimeter} = TA + TB = 7 + 7 = 14
$$

---

### **Conclusion**

The perimeter of triangle $ \triangle TXY $ is **independent of the position of point $ P $** on the minor arc $ AB $, as long as the tangent line through $ P $ intersects segments $ TA $ and $ TB $ between $ T $ and $ A $, $ T $ and $ B $ respectively.

This result follows directly from the **Tangent Segment Theorem** and the given order of points.

---

### ✅ Final Answer:

$$
\boxed{14}
$$<|im_end|>

Grade: {"valid": true, "method": "synthetic", "note": "Equal tangents from X,Y and the stated point orders yield perimeter14.", "repairable": false}

## F07 sample 1

The two tangents from T touch a circle at A and B, and TA=7. A third tangent touches the minor arc AB at P and meets the segments TA and TB at X and Y. Assume P lies between X and Y, with T,X,A and T,Y,B in those respective orders. Find the perimeter of triangle TXY.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 8053; finish: stop.



To determine the perimeter of triangle $ \triangle TXY $, we begin by analyzing the geometric configuration described:

- Point $ T $ lies outside a circle.
- Two tangents from $ T $ touch the circle at points $ A $ and $ B $, with $ TA = TB = 7 $.
- A third tangent line touches the **minor arc** $ AB $ at point $ P $, and intersects segments $ TA $ and $ TB $ at points $ X $ and $ Y $, respectively.
- The order on the lines is: $ T, X, A $ along segment $ TA $, and $ T, Y, B $ along segment $ TB $.
- Point $ P $ lies **between** $ X $ and $ Y $ on the tangent line $ XY $.

---

### Step 1: Use Tangent Segment Theorem

From the **Tangent Segment Theorem**, for any external point to a circle, the lengths of the two tangent segments from that point to the circle are equal.

- From point $ X $ (on segment $ TA $), the two tangents to the circle are:
  - $ XA $ (along segment $ TA $)
  - $ XP $ (along the third tangent line $ XY $)
  So, $ XA = XP $

- Similarly, from point $ Y $ (on segment $ TB $), the two tangents to the circle are:
  - $ YB $ (along segment $ TB $)
  - $ YP $ (along the same tangent line $ XY $)
  So, $ YB = YP $

---

### Step 2: Express Perimeter of Triangle $ \triangle TXY $

Let’s denote:
- $ TX = a $
- $ TY = b $
- Then, since $ X $ lies between $ T $ and $ A $, we have $ XA = TA - TX = 7 - a $
- Similarly, $ YB = TB - TY = 7 - b $

From the tangent segment theorem:
- $ XP = XA = 7 - a $
- $ YP = YB = 7 - b $

Since $ P $ lies between $ X $ and $ Y $ on the line $ XY $, it follows that:
$$
XY = XP + PY = (7 - a) + (7 - b) = 14 - a - b
$$

Now compute the **perimeter** of triangle $ \triangle TXY $:
$$
\text{Perimeter} = TX + TY + XY = a + b + (14 - a - b) = 14
$$

---

### Step 3: Conclusion

The key insight is that all variable terms cancel out due to the symmetry and application of the tangent segment theorem. Regardless of where point $ P $ is located on the minor arc $ AB $ (as long as the tangent intersects segments $ TA $ and $ TB $), the perimeter of triangle $ \triangle TXY $ remains constant.

Thus, the **perimeter of triangle $ TXY $** is:

$$
\boxed{14}
$$<|im_end|>

Grade: {"valid": true, "method": "synthetic", "note": "Equal tangents from X,Y and the stated point orders yield perimeter14.", "repairable": false}

## F08 sample 0

A,B,C are distinct points on a circle. The line through C parallel to the tangent at A meets the ray AB at D, with A,B,D in that order. Prove AB*AD=AC^2.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 8192; finish: length.

[No completed final answer; raw generation retained in the source JSON.]

Grade: {"valid": false, "method": "none", "note": "Token limit reached without a complete final proof.", "repairable": false}

## F08 sample 1

A,B,C are distinct points on a circle. The line through C parallel to the tangent at A meets the ray AB at D, with A,B,D in that order. Prove AB*AD=AC^2.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 8192; finish: length.

[No completed final answer; raw generation retained in the source JSON.]

Grade: {"valid": false, "method": "none", "note": "Token limit reached without a complete final proof.", "repairable": false}

## F09 sample 0

ABC is an isosceles triangle with AB=AC. P is any point in the interior of BC. E and F are the perpendicular projections of P onto the lines AB and AC. Prove that PE+PF equals the perpendicular distance from B to line AC.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 8192; finish: length.



To address the problem, we interpret the phrase **"P is any point in the interior of BC"** as referring to **any point on the open segment $ BC $** (i.e., the interior of the line segment $ BC $, excluding endpoints). This interpretation aligns with the mathematical context and ensures the result holds for all such points $ P $.

---

### ✅ **Mathematical Justification**

Let $ \triangle ABC $ be an isosceles triangle with $ AB = AC $. Place the triangle in the coordinate plane for clarity:

- Let $ B = (-1, 0) $, $ C = (1, 0) $, so that $ BC $ lies along the x-axis.
- Let $ A = (0, h) $ with $ h > 0 $, ensuring $ AB = AC $.

Let $ P = (t, 0) $ where $ -1 < t < 1 $ (i.e., $ P $ lies strictly between $ B $ and $ C $).

#### Step 1: Compute $ PE $ and $ PF $

- Line $ AB $: passes through $ (-1, 0) $ and $ (0, h) $, so its

Grade: {"valid": false, "method": "none", "note": "Token limit reached without a complete final proof.", "repairable": false}

## F09 sample 1

ABC is an isosceles triangle with AB=AC. P is any point in the interior of BC. E and F are the perpendicular projections of P onto the lines AB and AC. Prove that PE+PF equals the perpendicular distance from B to line AC.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 7103; finish: stop.



To prove that for an isosceles triangle $ ABC $ with $ AB = AC $, and a point $ P $ in the interior of segment $ BC $, the sum of the perpendicular distances from $ P $ to lines $ AB $ and $ AC $ (denoted as $ PE $ and $ PF $) equals the perpendicular distance from $ B $ to line $ AC $, we proceed with a geometric and trigonometric argument.

---

### **Step 1: Define the Triangle and Angles**

Let triangle $ ABC $ be isosceles with $ AB = AC $. Let:
- $ \angle ABC = \angle ACB = \beta $
- Since $ AB = AC $, the base angles at $ B $ and $ C $ are equal.

Let $ P $ be any point on the open segment $ BC $ (i.e., in the interior of $ BC $).

---

### **Step 2: Use Right Triangles to Express Distances**

From point $ P $, drop perpendiculars:
- $ PE $ is the perpendicular from $ P $ to line $ AB $
- $ PF $ is the perpendicular from $ P $ to line $ AC $

These form right triangles:
- $ \triangle PEB $: right triangle with $ \angle EBP = \beta $, so $ PE = PB \cdot \sin \beta $
- $ \triangle PFC $: right triangle with $ \angle FCP = \beta $, so $ PF = PC \cdot \sin \beta $

Thus,
$$
PE + PF = (PB + PC) \cdot \sin \beta
$$

But since $ P $ lies on segment $ BC $, we have $ PB + PC = BC $, so:
$$
PE + PF = BC \cdot \sin \beta
$$

---

### **Step 3: Compute the Perpendicular Distance from $ B $ to Line $ AC $**

Let $ D $ be the foot of the perpendicular from $ B $ to line $ AC $. Then the length $ BD $ is the perpendicular distance from $ B $ to line $ AC $.

We compute this using the area of triangle $ ABC $:

- Area of $ \triangle ABC $ can be expressed as:
  $$
  \text{Area} = \frac{1}{2} \cdot AB \cdot BC \cdot \sin \beta
  $$

- Also, the area can be written as:
  $$
  \text{Area} = \frac{1}{2} \cdot AC \cdot BD
  $$

Since $ AB = AC $, equating the two expressions gives:
$$
\frac{1}{2} \cdot AB \cdot BC \cdot \sin \beta = \frac{1}{2} \cdot AB \cdot BD
\Rightarrow BD = BC \cdot \sin \beta
$$

---

### **Step 4: Conclude the Equality**

From Steps 2 and 3, we have:
$$
PE + PF = BC \cdot \sin \beta = BD
$$

Therefore, the sum of the perpendicular distances from $ P $ to lines $ AB $ and $ AC $ equals the perpendicular distance from $ B $ to line $ AC $.

---

### ✅ Final Result

$$
\boxed{PE + PF = \text{perpendicular distance from } B \text{ to line } AC}
$$

This result holds for **any** point $ P $ in the interior of segment $ BC $ in the isosceles triangle $ ABC $ with $ AB = AC $. The proof relies on basic trigonometry and the symmetry of the isosceles triangle.<|im_end|>

Grade: {"valid": true, "method": "mixed", "note": "Correct base-angle sine expressions and area calculation; valid for arbitrary isosceles apex angle.", "repairable": false}

## F10 sample 0

ABCD is a convex trapezoid with AB parallel to CD, AB>CD, and AD=BC. Prove that A,B,C,D lie on one circle.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 7477; finish: stop.



To prove that the vertices $A, B, C, D$ of a convex trapezoid $ABCD$ with $AB \parallel CD$, $AB > CD$, and $AD = BC$ lie on a single circle (i.e., the trapezoid is cyclic), we proceed as follows:

---

### **Step 1: Understand the Given Conditions**

- $AB \parallel CD$: This implies that $AB$ and $CD$ are the two parallel sides (bases) of the trapezoid.
- $AB > CD$: The longer base is $AB$, and the shorter base is $CD$.
- $AD = BC$: The non-parallel sides (legs) are equal in length. This makes the trapezoid **isosceles**.

---

### **Step 2: Use Properties of Isosceles Trapezoids**

In an **isosceles trapezoid**, the following properties hold:
- The base angles adjacent to each leg are equal.
- The diagonals are equal in length.
- The trapezoid has an axis of symmetry through the midpoints of the bases.

Let us denote:
- $\angle DAB = \angle ABC = \alpha$
- $\angle ADC = \angle BCD = \beta$

Because $AB \parallel CD$, the consecutive interior angles formed by transversal $AD$ are supplementary:
$$
\angle DAB + \angle ADC = 180^\circ \Rightarrow \alpha + \beta = 180^\circ
$$

Similarly, for transversal $BC$:
$$
\angle ABC + \angle BCD = 180^\circ \Rightarrow \alpha + \beta = 180^\circ
$$

Thus, the sum of opposite angles in quadrilateral $ABCD$ satisfies:
$$
\angle DAB + \angle BCD = \alpha + \beta = 180^\circ
$$

---

### **Step 3: Apply the Cyclic Quadrilateral Theorem**

A quadrilateral is **cyclic** if and only if the sum of one pair of opposite angles equals $180^\circ$. Since we have shown:
$$
\angle DAB + \angle BCD = 180^\circ
$$
it follows that $ABCD$ is a **cyclic quadrilateral**.

Hence, the points $A, B, C, D$ lie on a single circle.

---

### **Final Result**

$$
\boxed{A, B, C, D \text{ lie on one circle}}
$$<|im_end|>

Grade: {"valid": true, "method": "synthetic", "note": "Correct formal equal-base-angle identities and supplementary opposite angles. Sample0 has loose wording about angles adjacent to a leg, resolved by its explicit formulas.", "repairable": false}

## F10 sample 1

ABCD is a convex trapezoid with AB parallel to CD, AB>CD, and AD=BC. Prove that A,B,C,D lie on one circle.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 5614; finish: stop.



To prove that the convex trapezoid $ABCD$ with $AB \parallel CD$, $AB > CD$, and $AD = BC$ lies on a single circle, we proceed as follows:

---

### **Step 1: Understand the Geometry**

Given:
- $AB \parallel CD$
- $AB > CD$
- $AD = BC$

This makes $ABCD$ an **isosceles trapezoid**, since it has one pair of parallel sides and the non-parallel sides (the legs) are equal in length.

In any trapezoid with $AB \parallel CD$, the **consecutive interior angles** formed by a transversal are supplementary. That is:
$$
\angle DAB + \angle CDA = 180^\circ \quad \text{and} \quad \angle ABC + \angle BCD = 180^\circ
$$

---

### **Step 2: Use Isosceles Property to Establish Angle Equality**

Because $AD = BC$, the trapezoid is isosceles. In such a trapezoid, the **base angles adjacent to each base are equal**. Specifically:
$$
\angle DAB = \angle ABC \quad \text{and} \quad \angle CDA = \angle BCD
$$

Let:
- $\angle DAB = \angle ABC = \alpha$
- $\angle CDA = \angle BCD = \beta$

From the parallel lines $AB \parallel CD$, we know:
$$
\angle DAB + \angle CDA = 180^\circ \Rightarrow \alpha + \beta = 180^\circ
$$

---

### **Step 3: Apply Cyclic Quadrilateral Criterion**

A quadrilateral is cyclic if and only if **one pair of opposite angles sums to $180^\circ$**.

Here, consider the opposite angles:
- $\angle DAB = \alpha$
- $\angle BCD = \beta$

So:
$$
\angle DAB + \angle BCD = \alpha + \beta = 180^\circ
$$

Thus, **one pair of opposite angles in quadrilateral $ABCD$ sums to $180^\circ$**.

By the **cyclic quadrilateral theorem**, this implies that all four points $A$, $B$, $C$, and $D$ lie on a single circle.

---

### **Final Result**

$$
\boxed{A, B, C, D \text{ lie on one circle}}
$$

This completes the proof without assuming the conclusion. The key steps rely on the properties of isosceles trapezoids and the standard geometric criterion for cyclic quadrilaterals.<|im_end|>

Grade: {"valid": true, "method": "synthetic", "note": "Correct formal equal-base-angle identities and supplementary opposite angles. Sample0 has loose wording about angles adjacent to a leg, resolved by its explicit formulas.", "repairable": false}

## F11 sample 0

Four distinct points A,B,C,D have no three collinear. Suppose angle BAC equals angle BDC, where both angles are ordinary angles in (0,180 degrees). Must the four points lie on one circle? Prove the assertion or give an explicit counterexample.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 8192; finish: length.

[No completed final answer; raw generation retained in the source JSON.]

Grade: {"valid": false, "method": "none", "note": "Token limit reached without a complete final proof.", "repairable": false}

## F11 sample 1

Four distinct points A,B,C,D have no three collinear. Suppose angle BAC equals angle BDC, where both angles are ordinary angles in (0,180 degrees). Must the four points lie on one circle? Prove the assertion or give an explicit counterexample.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 8192; finish: length.

[No completed final answer; raw generation retained in the source JSON.]

Grade: {"valid": false, "method": "none", "note": "Token limit reached without a complete final proof.", "repairable": false}

## F12 sample 0

Two nondegenerate triangles ABC and DEF satisfy AB/DE=AC/DF and angle ABC=angle DEF. Must the triangles be similar with correspondence A-D, B-E, C-F? Prove it or give an explicit counterexample.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 7720; finish: stop.



To determine whether two nondegenerate triangles $ \triangle ABC $ and $ \triangle DEF $ with the conditions:

- $ \frac{AB}{DE} = \frac{AC}{DF} $
- $ \angle ABC = \angle DEF $

must be similar with correspondence $ A \leftrightarrow D $, $ B \leftrightarrow E $, $ C \leftrightarrow F $, we analyze the geometric implications of these conditions.

---

### Step 1: Understanding the Given Conditions

Let’s denote:

- In triangle $ ABC $: sides $ AB = c $, $ AC = b $, $ BC = a $
- In triangle $ DEF $: sides $ DE = d $, $ DF = f $, $ EF = e $

Given:
$$
\frac{c}{d} = \frac{b}{f} \quad \text{and} \quad \angle ABC = \angle DEF
$$

This implies that the ratio of the lengths of two sides from vertex $ A $ (i.e., $ AB $ and $ AC $) is equal to the ratio of corresponding sides from vertex $ D $ (i.e., $ DE $ and $ DF $), and the angle at $ B $ in triangle $ ABC $ equals the angle at $ E $ in triangle $ DEF $.

However, **the angle $ \angle ABC $** is formed between sides $ AB $ and $ BC $, not $ AB $ and $ AC $. Therefore, this angle is **not** the included angle for the sides $ AB $ and $ AC $, which are the ones that are proportional.

This is crucial because **SAS similarity** requires the **included angle** between the two proportional sides to be equal. Here, the given angle is **not** the included angle for the proportional sides — it's an angle at a different vertex.

---

### Step 2: Constructing a Counterexample

We construct a specific example where the above conditions hold, but the triangles are **not** similar with the proposed correspondence.

#### Example:

Let’s define triangle $ ABC $ as a right triangle with:
- $ \angle A = 90^\circ $
- $ \angle B = 30^\circ $
- $ \angle C = 60^\circ $

Using standard 30°–60°–90° triangle ratios:
- Let $ AC = 1 $ (opposite $ \angle B = 30^\circ $)
- Then $ AB = \sqrt{3} $ (opposite $ \angle C = 60^\circ $)
- And $ BC = 2 $ (hypotenuse)

So:
- $ AB = \sqrt{3} $
- $ AC = 1 $
- $ BC = 2 $

Now consider triangle $ DEF $ such that:
- $ \angle E = 30^\circ $ (same as $ \angle B $)
- $ \frac{AB}{DE} = \frac{AC}{DF} = 1 $ ⇒ $ DE = AB = \sqrt{3} $, $ DF = AC = 1 $

Apply the Law of Sines in triangle $ DEF $:
$$
\frac{DE}{\sin(\angle F)} = \frac{DF}{\sin(\angle E)} \Rightarrow \frac{\sqrt{3}}{\sin(\angle F)} = \frac{1}{\sin(30^\circ)} = 2
\Rightarrow \sin(\angle F) = \frac{\sqrt{3}}{2}
\Rightarrow \angle F = 60^\circ \text{ or } 120^\circ
$$

Case 1: $ \angle F = 60^\circ $  
Then $ \angle D = 180^\circ - 30^\circ - 60^\circ = 90^\circ $, so triangle $ DEF $ has angles $ 90^\circ, 30^\circ, 60^\circ $, matching triangle $ ABC $ exactly. So they are **similar** with correspondence $ A \leftrightarrow D $, $ B \leftrightarrow E $, $ C \leftrightarrow F $.

Case 2: $ \angle F = 120^\circ $  
Then $ \angle D = 180^\circ - 30^\circ - 120^\circ = 30^\circ $

So triangle $ DEF $ has angles $ 30^\circ, 30^\circ, 120^\circ $, while triangle $ ABC $ has angles $ 90^\circ, 30^\circ, 60^\circ $.

Thus, **the triangles are not similar** with the correspondence $ A \leftrightarrow D $, $ B \leftrightarrow E $, $ C \leftrightarrow F $.

Moreover, triangle $ DEF $ is **nondegenerate**:
- Sides: $ DE = \sqrt{3} $, $ DF = 1 $, $ EF = 1 $
- Check triangle inequality: $ 1 + 1 > \sqrt{3} $, which holds since $ \sqrt{3} \approx 1.732 < 2 $

Hence, this is a **valid counterexample**.

---

### Final Conclusion

The given conditions do **not** guarantee that the triangles are similar with the correspondence $ A \leftrightarrow D $, $ B \leftrightarrow E $, $ C \leftrightarrow F $, because the angle $ \angle ABC $ is **not** the included angle for the proportional sides $ AB $ and $ AC $. This violates the requirement for SAS similarity.

A concrete counterexample exists where all conditions are satisfied, yet the triangles are **not** similar under the proposed correspondence.

---

### ✅ Final Answer:

**No**, the triangles do **not** necessarily have to be similar with correspondence $ A \leftrightarrow D $, $ B \leftrightarrow E $, $ C \leftrightarrow F $. A counterexample exists where the given conditions hold but the triangles are not similar under this correspondence.

$$
\boxed{\text{No}}
$$<|im_end|>

Grade: {"valid": true, "method": "mixed", "note": "Valid explicit SSA counterexample: ABC angles90,30,60 and sides sqrt3,1,2; DEF angles30,30,120 and sides sqrt3,1,1.", "repairable": false}

## F12 sample 1

Two nondegenerate triangles ABC and DEF satisfy AB/DE=AC/DF and angle ABC=angle DEF. Must the triangles be similar with correspondence A-D, B-E, C-F? Prove it or give an explicit counterexample.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 8192; finish: length.

[No completed final answer; raw generation retained in the source JSON.]

Grade: {"valid": false, "method": "none", "note": "Token limit reached without a complete final proof.", "repairable": false}
