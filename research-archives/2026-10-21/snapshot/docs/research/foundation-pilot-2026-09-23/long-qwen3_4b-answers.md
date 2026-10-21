## F02 sample 0

Two chords AC and BD of a circle meet at an interior point P. PA=3, PC=8, PB=4. Find PD. Derive the needed product relation from angles and similar triangles instead of quoting the intersecting-chords theorem.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 12746; finish: stop.



To find the length of segment $ PD $, we are given that two chords $ AC $ and $ BD $ intersect at an interior point $ P $ of a circle. The known lengths are:

- $ PA = 3 $
- $ PC = 8 $
- $ PB = 4 $

We are to determine the value of $ PD $, and the problem specifies that we should **derive the necessary product relation from angles and similar triangles**, rather than directly invoking the **intersecting chords theorem**.

---

### Step 1: Understand the Geometry

Let’s consider the cyclic quadrilateral $ ABCD $, formed by the four points on the circle. The chords $ AC $ and $ BD $ intersect at point $ P $, which lies **inside** the circle.

This setup allows us to use properties of **inscribed angles**, **vertical angles**, and **similar triangles** to relate the lengths of segments $ PA, PB, PC, $ and $ PD $.

---

### Step 2: Use Angle Relationships to Identify Similar Triangles

We consider triangles $ \triangle APB $ and $ \triangle DPC $.

- **Vertical angles**: $ \angle APB = \angle DPC $ (they are vertical angles).
- **Angle PAB and PDC**: These are inscribed angles that both subtend the same arc $ BD $ of the circle. Since the angles subtended by the same arc are equal, we have:
  $$
  \angle PAB = \angle PDC
  $$

Thus, by the **AA (Angle-Angle) similarity criterion**, triangles $ \triangle APB \sim \triangle DPC $.

---

### Step 3: Use the Similarity to Derive the Desired Relation

Since $ \triangle APB \sim \triangle DPC $, the corresponding sides are proportional. Therefore:

$$
\frac{PA}{DP} = \frac{PB}{PC}
$$

Cross-multiplying gives:

$$
PA \cdot PC = PB \cdot PD
$$

Substituting the known values:

$$
3 \cdot 8 = 4 \cdot PD \Rightarrow 24 = 4 \cdot PD
$$

Solving for $ PD $:

$$
PD = \frac{24}{4} = 6
$$

---

### Final Answer

$$
\boxed{6}
$$<|im_end|>

Grade: {"valid": true, "method": "synthetic", "note": "Correct AA correspondence and product. The common intercepted arc is CB, not BD as named; correct explicit angles make this a local label error.", "repairable": false}

## F02 sample 1

Two chords AC and BD of a circle meet at an interior point P. PA=3, PC=8, PB=4. Find PD. Derive the needed product relation from angles and similar triangles instead of quoting the intersecting-chords theorem.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 9309; finish: stop.



To solve the problem, we are given that two chords $ AC $ and $ BD $ intersect at an interior point $ P $ of a circle, and we are provided with the lengths $ PA = 3 $, $ PC = 8 $, and $ PB = 4 $. The goal is to determine the length of $ PD $, using only the geometric relationships between angles and similar triangles, without invoking the intersecting chords theorem directly.

---

### **Step 1: Understand the Configuration**

Let’s visualize the circle with chords $ AC $ and $ BD $ intersecting at point $ P $ inside the circle. The segments formed are:

- $ PA = 3 $, $ PC = 8 $, so $ AC = PA + PC = 11 $
- $ PB = 4 $, and we are to find $ PD $

Since the chords intersect inside the circle, the key geometric insight is that **angles formed by intersecting chords are related to the arcs they subtend**.

---

### **Step 2: Use Angle Relationships and Similar Triangles**

We will consider triangles $ \triangle APB $ and $ \triangle DPC $. The key observation is that:

- $ \angle APB = \angle DPC $ (they are vertical angles)
- $ \angle PAB = \angle PDC $ (both subtend the same arc $ BD $ of the circle)

This is justified by the **inscribed angle theorem**, which states that angles subtended by the same arc from the same side of the circle are equal. Since both $ \angle PAB $ and $ \angle PDC $ subtend arc $ BD $, they are equal.

Therefore, triangles $ \triangle APB $ and $ \triangle DPC $ are similar by **AA similarity**.

---

### **Step 3: Use Similarity to Derive the Length of $ PD $**

From the similarity of triangles $ \triangle APB \sim \triangle DPC $, we can write the proportionality of corresponding sides:

$$
\frac{PA}{PD} = \frac{PB}{PC}
$$

Substitute the known values:

$$
\frac{3}{PD} = \frac{4}{8} = \frac{1}{2}
$$

Solving for $ PD $:

$$
PD = 3 \times 2 = 6
$$

---

### **Final Result**

$$
\boxed{6}
$$<|im_end|>

Grade: {"valid": true, "method": "synthetic", "note": "Correct AA correspondence and product. Misnames intercepted arc BD instead of CB; explicit angle relation and side mapping correct.", "repairable": false}

## F08 sample 0

A,B,C are distinct points on a circle. The line through C parallel to the tangent at A meets the ray AB at D, with A,B,D in that order. Prove AB*AD=AC^2.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 16975; finish: stop.



To prove the identity $ AB \cdot AD = AC^2 $, we are given that points $ A, B, C $ lie on a circle, and a line through point $ C $ is drawn parallel to the tangent at $ A $, intersecting the ray $ AB $ at point $ D $, with the order $ A, B, D $ along the ray.

---

### **Key Geometric Observations and Theorem Application**

1. **Tangent and Chord Relationship:**
   The Alternate Segment Theorem states that the angle between a tangent at a point on a circle and a chord through that point is equal to the angle in the alternate segment.

   - Let $ t $ be the tangent at point $ A $.
   - Let $ AC $ be a chord of the circle through $ A $.
   - Then, the angle between $ t $ and $ AC $ is equal to the angle $ \angle ABC $, which lies in the alternate segment.

2. **Parallel Lines and Angle Equality:**
   Since the line through $ C $ is parallel to the tangent at $ A $, the angle between that line and $ AB $ is equal to the angle between the tangent and $ AB $. By the Alternate Segment Theorem, this is equal to $ \angle ABC $.

   Therefore, the angle between line $ CD $ and $ AB $ is equal to $ \angle ABC $.

3. **Angle Equality in Triangles:**
   - Let $ \angle CAB = \alpha $ (common to both triangles $ ABC $ and $ DAC $).
   - From above, $ \angle ADC = \angle ABC $.
   - Thus, triangle $ ABC $ and triangle $ DAC $ share angle $ \alpha $ at $ A $, and angle $ \angle ADC = \angle ABC $, which implies that the two triangles are **similar** by AA similarity.

---

### **Similar Triangles and Proportionality**

Since $ \triangle ABC \sim \triangle DAC $, the corresponding sides are proportional:

$$
\frac{AB}{AC} = \frac{AC}{AD}
$$

Cross-multiplying gives:

$$
AB \cdot AD = AC^2
$$

---

### **Conclusion**

This completes the proof that the product of the lengths $ AB $ and $ AD $ is equal to the square of the length $ AC $, under the given geometric configuration.

---

### **Final Answer**

$$
\boxed{AB \cdot AD = AC^2}
$$<|im_end|>

Grade: {"valid": false, "method": "synthetic", "note": "Core angle ADC=ABC is false; the needed equality is ACD=ABC. Incorrect similarity correspondence.", "repairable": false}

## F08 sample 1

A,B,C are distinct points on a circle. The line through C parallel to the tangent at A meets the ray AB at D, with A,B,D in that order. Prove AB*AD=AC^2.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 5450; finish: stop.



To prove that $ AB \cdot AD = AC^2 $, we are given that $ A, B, C $ are distinct points on a circle, and that the line through $ C $, parallel to the tangent at $ A $, intersects the ray $ AB $ at point $ D $, with $ A, B, D $ in that order.

---

### **Key Observations and Theoretical Tools**

- **Alternate Segment Theorem**: The angle between a tangent to a circle at a point and a chord through that point is equal to the angle in the alternate segment.
- **Parallel Lines and Angles**: If a line is parallel to another, corresponding angles formed by a transversal are equal.
- **Similar Triangles**: Two triangles are similar if they have two corresponding angles equal (AA similarity criterion).

---

### **Step-by-Step Proof**

1. **Define the Tangent and Parallel Line**:
   - Let the tangent to the circle at point $ A $ be denoted as $ t $.
   - The line through point $ C $, which is parallel to $ t $, is denoted as $ CD $.

2. **Apply the Alternate Segment Theorem**:
   - The angle between the tangent at $ A $ and the chord $ AC $ is equal to the angle $ \angle ABC $ (the angle in the alternate segment).
   - Since $ CD $ is parallel to the tangent at $ A $, the angle between $ CD $ and $ AC $ is equal to the angle between the tangent and $ AC $, which is $ \angle ABC $.
   - Therefore, $ \angle ACD = \angle ABC $.

3. **Identify the Common Angle**:
   - The angle $ \angle CAB $ (at point $ A $) is common to both triangles $ ABC $ and $ ACD $.
   - Since $ D $ lies on the ray $ AB $, the angle $ \angle CAD $ is the same as $ \angle CAB $.

4. **Establish Similarity of Triangles**:
   - In triangle $ ABC $, we have $ \angle ABC = \angle ACD $.
   - In triangle $ ACD $, we have $ \angle CAD = \angle CAB $.
   - Therefore, triangles $ ABC $ and $ ACD $ are similar by the **AA similarity criterion**.

5. **Apply the Similarity Ratio**:
   - From the similarity of triangles $ ABC \sim ACD $, we have:
     $$
     \frac{AB}{AC} = \frac{AC}{AD}
     $$
   - Cross-multiplying gives:
     $$
     AB \cdot AD = AC^2
     $$

---

### **Conclusion**

Thus, we have shown that the product of the lengths $ AB $ and $ AD $ is equal to the square of the length $ AC $, as required.

$$
\boxed{AB \cdot AD = AC^2}
$$<|im_end|>

Grade: {"valid": true, "method": "synthetic", "note": "Correct tangent-chord angle ACD=ABC and AA correspondence.", "repairable": false}

## F11 sample 0

Four distinct points A,B,C,D have no three collinear. Suppose angle BAC equals angle BDC, where both angles are ordinary angles in (0,180 degrees). Must the four points lie on one circle? Prove the assertion or give an explicit counterexample.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 6338; finish: stop.



To determine whether four distinct points $ A, B, C, D $, with no three collinear, and with the condition that $ \angle BAC = \angle BDC $, must lie on a single circle, we can proceed using the **inscribed angle theorem** and properties of **circles**.

---

### **Key Observations and Theorem Application**

1. **Inscribed Angle Theorem**:  
   In a circle, an inscribed angle is equal to half the measure of the arc it subtends.  
   So, if $ \angle BAC = \theta $, then the arc $ BC $ subtended by this angle has measure $ 2\theta $.

2. **Given Condition**:  
   We are told that $ \angle BAC = \angle BDC = \theta $.  
   Therefore, both angles subtend the same arc $ BC $, and both are equal to $ \theta $, meaning the arc $ BC $ must be of measure $ 2\theta $.

3. **Locus of Point $ D $**:  
   The set of all points $ D $ such that $ \angle BDC = \theta $ is a **circular arc** passing through $ B $ and $ C $, with the arc subtending $ \angle BDC = \theta $.  
   Since $ \angle BAC = \angle BDC $, and both angles are subtended by the same arc $ BC $, the only way for both angles to be equal is if point $ D $ lies on the **same circle** as $ A, B, C $, because:

   - If $ D $ were on a **different circle** through $ B $ and $ C $, then $ \angle BDC $ would be subtended by the arc $ BC $ on that new circle, and its measure would depend on the arc length on that circle.
   - However, for $ \angle BDC = \angle BAC $, the arc length subtended by $ BC $ must be the same in both circles, which is only possible if the two circles are the **same circle**.

---

### **Conclusion**

Thus, for the angles $ \angle BAC $ and $ \angle BDC $ to be equal, point $ D $ must lie on the **circumcircle** of triangle $ ABC $. This ensures that all four points $ A, B, C, D $ lie on the same circle.

Therefore, the condition that $ \angle BAC = \angle BDC $ **implies** that the four points are concyclic.

---

### **Final Answer**

$$
\boxed{Yes}
$$<|im_end|>

Grade: {"valid": false, "method": "none", "note": "Incorrectly asserts equal unsigned angles force one circle; opposite-side case missed.", "repairable": false}

## F11 sample 1

Four distinct points A,B,C,D have no three collinear. Suppose angle BAC equals angle BDC, where both angles are ordinary angles in (0,180 degrees). Must the four points lie on one circle? Prove the assertion or give an explicit counterexample.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 7929; finish: stop.



To determine whether four distinct points $ A, B, C, D $, with no three collinear, and satisfying the condition that $ \angle BAC = \angle BDC $, must lie on a single circle, we analyze the geometric implications of this angle equality.

---

### Key Geometric Insight

In a circle, if two points $ A $ and $ D $ subtend the same angle $ \theta $ with a fixed chord $ BC $, then both $ A $ and $ D $ must lie on the same circle. This is due to the **Inscribed Angle Theorem**, which states that angles subtended by the same chord from the same side of the chord are equal if and only if the points lie on the same circle.

However, this theorem only applies when the angles are **on the same side** of the chord $ BC $. If the points $ A $ and $ D $ are on **opposite sides** of the chord $ BC $, then the angles subtended by $ BC $ at $ A $ and $ D $ can still be equal, but this does **not** imply that $ A, B, C, D $ lie on the same circle.

---

### Constructing a Counterexample

Let us construct a specific example where $ \angle BAC = \angle BDC $, but the four points do **not** lie on a single circle.

1. Let the chord $ BC $ be horizontal, with endpoints at:
   $$
   B = (0, 0), \quad C = (2, 0)
   $$
2. Let point $ A $ lie on the **upper** circle passing through $ B $ and $ C $ such that the angle $ \angle BAC = 60^\circ $. This circle has:
   - Center at $ (1, \frac{1}{\sqrt{3}}) $
   - Radius $ \frac{2}{\sqrt{3}} $
3. Let point $ D $ lie on the **lower** circle passing through $ B $ and $ C $, such that $ \angle BDC = 60^\circ $. This circle has:
   - Center at $ (1, -\frac{1}{\sqrt{3}}) $
   - Radius $ \frac{2}{\sqrt{3}} $

4. Choose a specific point $ A = (1, \sqrt{3}) $ on the upper circle, and $ D = (1, -\sqrt{3}) $ on the lower circle. Both points are at a distance $ \frac{2}{\sqrt{3}} $ from the center, and the angles $ \angle BAC $ and $ \angle BDC $ are both $ 60^\circ $.

5. Now, check whether all four points lie on a single circle. The general equation of a circle is:
   $$
   x^2 + y^2 + Dx + Ey + F = 0
   $$
   Plugging in $ B = (0, 0) $, $ C = (2, 0) $, and $ A = (1, \sqrt{3}) $, we find that the circle passing through these three points has center $ (1, \frac{1}{\sqrt{3}}) $ and radius $ \frac{2}{\sqrt{3}} $. However, the point $ D = (1, -\sqrt{3}) $ is not on this circle, as the distance from the center to $ D $ is:
   $$
   \sqrt{(1 - 1)^2 + \left(-\sqrt{3} - \frac{1}{\sqrt{3}}\right)^2} = \sqrt{0 + \left(-\frac{4}{\sqrt{3}}\right)^2} = \frac{4}{\sqrt{3}} \neq \frac{2}{\sqrt{3}}
   $$
   Thus, $ D $ is **not** on the circle passing through $ A, B, C $, and therefore, the four points do **not** lie on a single circle.

---

### Final Conclusion

The condition $ \angle BAC = \angle BDC $ does **not** guarantee that the four points lie on a single circle. A counterexample exists where the points satisfy the angle condition but are not concyclic.

$$
\boxed{No}
$$<|im_end|>

Grade: {"valid": true, "method": "analytic", "note": "Explicit reflected equilateral vertices give equal 60-degree angles and different circles.", "repairable": false}
