## C01 sample 0

Solve the new problem with concise, justified steps. When using similarity, keep the vertex correspondence explicit. Check the assumptions of each theorem. Do not specialize a general figure without justifying that the requested quantity is preserved. Prefer a short geometric explanation when it is available; any valid method remains allowed. Finish once the proof is complete.

Here are four examples of the desired mathematical care; they are not hints to the new problem.

Example problem: Triangles ABC and DEF satisfy AB=6, AC=9, DE=10, DF=15 and angle BAC=EDF. Find BC/EF, with justification.
Example answer: AB/DE=AC/DF=3/5, and the included angles at A,D are equal. Thus SAS similarity gives A-D, B-E, C-F. In particular BC/EF=3/5.

Example problem: Distinct points A,B,C,D lie on a circle in that cyclic order. Given angle ABD=32 degrees, find angle ACD.
Example answer: B and C are on the same arc from A to D. The inscribed angles ABD and ACD therefore subtend the same opposite arc AD, so they are equal. Thus angle ACD=32 degrees.

Example problem: In triangle ABC, the perpendicular from A to BC meets the interior of BC at D. Given AB=13, BD=5 and DC=9, find AC.
Example answer: Triangle ADB is right at D, so AD^2=AB^2-BD^2=169-25=144. In right triangle ADC, AC^2=AD^2+DC^2=144+81=225. Therefore AC=15.

Example problem: A convex quadrilateral has diagonals which bisect each other. Must it be a rectangle? Give a proof or explicit counterexample.
Example answer: No. Take A=(0,0), B=(2,0), C=(3,1), D=(1,1). This is a convex parallelogram, and both diagonals have midpoint (3/2,1/2). But AB=(2,0) and AD=(1,1) have dot product 2, not 0. Thus angle BAD is not right and the quadrilateral is not a rectangle.

New problem:
In triangle ABC, AB=6, AC=9, and BC=10. The internal bisector of angle BAC meets BC at D. Through D draw the line parallel to AB, meeting AC at E. Find AE.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 8192; finish: length.

[No completed final answer; raw generation retained in the source JSON.]

Grade: {"valid": false, "method": "none", "note": "Output limit reached without completed final proof.", "repairable": false}

## C01 sample 1

Solve the new problem with concise, justified steps. When using similarity, keep the vertex correspondence explicit. Check the assumptions of each theorem. Do not specialize a general figure without justifying that the requested quantity is preserved. Prefer a short geometric explanation when it is available; any valid method remains allowed. Finish once the proof is complete.

Here are four examples of the desired mathematical care; they are not hints to the new problem.

Example problem: Triangles ABC and DEF satisfy AB=6, AC=9, DE=10, DF=15 and angle BAC=EDF. Find BC/EF, with justification.
Example answer: AB/DE=AC/DF=3/5, and the included angles at A,D are equal. Thus SAS similarity gives A-D, B-E, C-F. In particular BC/EF=3/5.

Example problem: Distinct points A,B,C,D lie on a circle in that cyclic order. Given angle ABD=32 degrees, find angle ACD.
Example answer: B and C are on the same arc from A to D. The inscribed angles ABD and ACD therefore subtend the same opposite arc AD, so they are equal. Thus angle ACD=32 degrees.

Example problem: In triangle ABC, the perpendicular from A to BC meets the interior of BC at D. Given AB=13, BD=5 and DC=9, find AC.
Example answer: Triangle ADB is right at D, so AD^2=AB^2-BD^2=169-25=144. In right triangle ADC, AC^2=AD^2+DC^2=144+81=225. Therefore AC=15.

Example problem: A convex quadrilateral has diagonals which bisect each other. Must it be a rectangle? Give a proof or explicit counterexample.
Example answer: No. Take A=(0,0), B=(2,0), C=(3,1), D=(1,1). This is a convex parallelogram, and both diagonals have midpoint (3/2,1/2). But AB=(2,0) and AD=(1,1) have dot product 2, not 0. Thus angle BAD is not right and the quadrilateral is not a rectangle.

New problem:
In triangle ABC, AB=6, AC=9, and BC=10. The internal bisector of angle BAC meets BC at D. Through D draw the line parallel to AB, meeting AC at E. Find AE.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 6654; finish: stop.



To solve the problem, we are given triangle $ ABC $ with side lengths $ AB = 6 $, $ AC = 9 $, and $ BC = 10 $. The internal angle bisector of $ \angle BAC $ intersects $ BC $ at point $ D $, and through $ D $, a line parallel to $ AB $ is drawn, intersecting $ AC $ at point $ E $. We are to find the length of $ AE $.

---

### Step 1: Apply the Angle Bisector Theorem

The **Angle Bisector Theorem** states that the angle bisector of an angle in a triangle divides the opposite side into segments proportional to the adjacent sides. That is:

$$
\frac{BD}{DC} = \frac{AB}{AC} = \frac{6}{9} = \frac{2}{3}
$$

Since $ BC = 10 $, let $ BD = 2x $ and $ DC = 3x $. Then:

$$
BD + DC = 10 \Rightarrow 2x + 3x = 10 \Rightarrow x = 2
$$

Thus:

$$
BD = 4, \quad DC = 6
$$

---

### Step 2: Use the Basic Proportionality Theorem (Thales' Theorem)

We are told that a line $ DE $ is drawn through $ D $, parallel to $ AB $, and intersects $ AC $ at $ E $. By the **Basic Proportionality Theorem**, if a line is drawn parallel to one side of a triangle, it divides the other two sides proportionally. In this case:

$$
\frac{AE}{EC} = \frac{BD}{DC} = \frac{4}{6} = \frac{2}{3}
$$

Let $ AE = 2k $ and $ EC = 3k $. Then:

$$
AE + EC = AC = 9 \Rightarrow 2k + 3k = 9 \Rightarrow k = \frac{3}{5}
$$

So:

$$
AE = 2k = 2 \cdot \frac{3}{5} = \frac{6}{5} \cdot 3 = \frac{18}{5}
$$

---

### Final Answer:

$$
\boxed{\frac{18}{5}}
$$<|im_end|>

Grade: {"valid": false, "method": "synthetic", "note": "5k=9 is incorrectly solved as k=3/5; ensuing multiplication also false although the final answer18/5 is right.", "repairable": true}

## C02 sample 0

Solve the new problem with concise, justified steps. When using similarity, keep the vertex correspondence explicit. Check the assumptions of each theorem. Do not specialize a general figure without justifying that the requested quantity is preserved. Prefer a short geometric explanation when it is available; any valid method remains allowed. Finish once the proof is complete.

Here are four examples of the desired mathematical care; they are not hints to the new problem.

Example problem: Triangles ABC and DEF satisfy AB=6, AC=9, DE=10, DF=15 and angle BAC=EDF. Find BC/EF, with justification.
Example answer: AB/DE=AC/DF=3/5, and the included angles at A,D are equal. Thus SAS similarity gives A-D, B-E, C-F. In particular BC/EF=3/5.

Example problem: Distinct points A,B,C,D lie on a circle in that cyclic order. Given angle ABD=32 degrees, find angle ACD.
Example answer: B and C are on the same arc from A to D. The inscribed angles ABD and ACD therefore subtend the same opposite arc AD, so they are equal. Thus angle ACD=32 degrees.

Example problem: In triangle ABC, the perpendicular from A to BC meets the interior of BC at D. Given AB=13, BD=5 and DC=9, find AC.
Example answer: Triangle ADB is right at D, so AD^2=AB^2-BD^2=169-25=144. In right triangle ADC, AC^2=AD^2+DC^2=144+81=225. Therefore AC=15.

Example problem: A convex quadrilateral has diagonals which bisect each other. Must it be a rectangle? Give a proof or explicit counterexample.
Example answer: No. Take A=(0,0), B=(2,0), C=(3,1), D=(1,1). This is a convex parallelogram, and both diagonals have midpoint (3/2,1/2). But AB=(2,0) and AD=(1,1) have dot product 2, not 0. Thus angle BAD is not right and the quadrilateral is not a rectangle.

New problem:
In triangle ABC, angle BAC=48 degrees. The internal bisectors of angles ABC and ACB meet at I. Find angle BIC.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 1746; finish: stop.



To determine the measure of angle $ \angle BIC $ in triangle $ ABC $, where $ I $ is the incenter, we use the geometric property that the incenter lies at the intersection of the internal angle bisectors of $ \angle ABC $ and $ \angle ACB $.

---

### Step 1: Use the Angle Bisector Property

Since $ I $ is the incenter, the angle bisectors $ BI $ and $ CI $ divide angles $ \angle ABC $ and $ \angle ACB $ into two equal parts. Thus:

- $ \angle IBC = \frac{1}{2} \angle ABC $
- $ \angle ICB = \frac{1}{2} \angle ACB $

---

### Step 2: Apply Triangle Angle Sum in $ \triangle BIC $

In triangle $ BIC $, the sum of the angles is $ 180^\circ $:

$$
\angle BIC = 180^\circ - \angle IBC - \angle ICB
$$

Substitute the expressions for the bisected angles:

$$
\angle BIC = 180^\circ - \left( \frac{1}{2} \angle ABC + \frac{1}{2} \angle ACB \right)
= 180^\circ - \frac{1}{2}(\angle ABC + \angle ACB)
$$

---

### Step 3: Use Triangle Angle Sum in $ \triangle ABC $

In triangle $ ABC $, the sum of the angles is $ 180^\circ $:

$$
\angle ABC + \angle ACB = 180^\circ - \angle BAC
$$

Given $ \angle BAC = 48^\circ $, we have:

$$
\angle ABC + \angle ACB = 180^\circ - 48^\circ = 132^\circ
$$

---

### Step 4: Compute $ \angle BIC $

Substitute into the expression for $ \angle BIC $:

$$
\angle BIC = 180^\circ - \frac{1}{2}(132^\circ) = 180^\circ - 66^\circ = 114^\circ
$$

---

### Final Answer:

$$
\boxed{114^\circ}
$$<|im_end|>

Grade: {"valid": true, "method": "synthetic", "note": "Correct triangle angle sums; sample1 verbally misnames angle vertices but equations are correct.", "repairable": false}

## C02 sample 1

Solve the new problem with concise, justified steps. When using similarity, keep the vertex correspondence explicit. Check the assumptions of each theorem. Do not specialize a general figure without justifying that the requested quantity is preserved. Prefer a short geometric explanation when it is available; any valid method remains allowed. Finish once the proof is complete.

Here are four examples of the desired mathematical care; they are not hints to the new problem.

Example problem: Triangles ABC and DEF satisfy AB=6, AC=9, DE=10, DF=15 and angle BAC=EDF. Find BC/EF, with justification.
Example answer: AB/DE=AC/DF=3/5, and the included angles at A,D are equal. Thus SAS similarity gives A-D, B-E, C-F. In particular BC/EF=3/5.

Example problem: Distinct points A,B,C,D lie on a circle in that cyclic order. Given angle ABD=32 degrees, find angle ACD.
Example answer: B and C are on the same arc from A to D. The inscribed angles ABD and ACD therefore subtend the same opposite arc AD, so they are equal. Thus angle ACD=32 degrees.

Example problem: In triangle ABC, the perpendicular from A to BC meets the interior of BC at D. Given AB=13, BD=5 and DC=9, find AC.
Example answer: Triangle ADB is right at D, so AD^2=AB^2-BD^2=169-25=144. In right triangle ADC, AC^2=AD^2+DC^2=144+81=225. Therefore AC=15.

Example problem: A convex quadrilateral has diagonals which bisect each other. Must it be a rectangle? Give a proof or explicit counterexample.
Example answer: No. Take A=(0,0), B=(2,0), C=(3,1), D=(1,1). This is a convex parallelogram, and both diagonals have midpoint (3/2,1/2). But AB=(2,0) and AD=(1,1) have dot product 2, not 0. Thus angle BAD is not right and the quadrilateral is not a rectangle.

New problem:
In triangle ABC, angle BAC=48 degrees. The internal bisectors of angles ABC and ACB meet at I. Find angle BIC.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 1864; finish: stop.



To find the measure of angle $ \angle BIC $ in triangle $ ABC $, where $ I $ is the incenter (intersection of angle bisectors of $ \angle ABC $ and $ \angle ACB $), we proceed as follows:

---

**Step 1: Use the incenter properties**  
The incenter $ I $ lies at the intersection of the internal angle bisectors of triangle $ ABC $. Therefore, the angles at $ I $ formed with the sides of the triangle are half the corresponding angles of the triangle.

Let $ \angle BAC = A = 48^\circ $. Then, since the sum of angles in triangle $ ABC $ is $ 180^\circ $, we have:

$$
\angle ABC + \angle ACB = 180^\circ - 48^\circ = 132^\circ
$$

Let $ \angle ABC = B $ and $ \angle ACB = C $. Then:

$$
B + C = 132^\circ
$$

---

**Step 2: Express $ \angle BIC $ in terms of $ B $ and $ C $**  
In triangle $ BIC $, the angles at $ I $ are:

- $ \angle IBC = \frac{1}{2}B $
- $ \angle ICB = \frac{1}{2}C $

Therefore, the third angle $ \angle BIC $ is:

$$
\angle BIC = 180^\circ - \left( \frac{1}{2}B + \frac{1}{2}C \right) = 180^\circ - \frac{1}{2}(B + C)
$$

Substituting $ B + C = 132^\circ $:

$$
\angle BIC = 180^\circ - \frac{1}{2}(132^\circ) = 180^\circ - 66^\circ = 114^\circ
$$

---

**Step 3: Confirm with known formula**  
This result is consistent with the known formula for the angle at the incenter:

$$
\angle BIC = 90^\circ + \frac{1}{2} \angle BAC
$$

Substituting $ \angle BAC = 48^\circ $:

$$
\angle BIC = 90^\circ + \frac{1}{2} \cdot 48^\circ = 90^\circ + 24^\circ = 114^\circ
$$

---

**Final Answer:**  
$$
\boxed{114^\circ}
$$<|im_end|>

Grade: {"valid": true, "method": "synthetic", "note": "Correct triangle angle sums; sample1 verbally misnames angle vertices but equations are correct.", "repairable": false}

## C03 sample 0

Solve the new problem with concise, justified steps. When using similarity, keep the vertex correspondence explicit. Check the assumptions of each theorem. Do not specialize a general figure without justifying that the requested quantity is preserved. Prefer a short geometric explanation when it is available; any valid method remains allowed. Finish once the proof is complete.

Here are four examples of the desired mathematical care; they are not hints to the new problem.

Example problem: Triangles ABC and DEF satisfy AB=6, AC=9, DE=10, DF=15 and angle BAC=EDF. Find BC/EF, with justification.
Example answer: AB/DE=AC/DF=3/5, and the included angles at A,D are equal. Thus SAS similarity gives A-D, B-E, C-F. In particular BC/EF=3/5.

Example problem: Distinct points A,B,C,D lie on a circle in that cyclic order. Given angle ABD=32 degrees, find angle ACD.
Example answer: B and C are on the same arc from A to D. The inscribed angles ABD and ACD therefore subtend the same opposite arc AD, so they are equal. Thus angle ACD=32 degrees.

Example problem: In triangle ABC, the perpendicular from A to BC meets the interior of BC at D. Given AB=13, BD=5 and DC=9, find AC.
Example answer: Triangle ADB is right at D, so AD^2=AB^2-BD^2=169-25=144. In right triangle ADC, AC^2=AD^2+DC^2=144+81=225. Therefore AC=15.

Example problem: A convex quadrilateral has diagonals which bisect each other. Must it be a rectangle? Give a proof or explicit counterexample.
Example answer: No. Take A=(0,0), B=(2,0), C=(3,1), D=(1,1). This is a convex parallelogram, and both diagonals have midpoint (3/2,1/2). But AB=(2,0) and AD=(1,1) have dot product 2, not 0. Thus angle BAD is not right and the quadrilateral is not a rectangle.

New problem:
ABCD is a convex quadrilateral with AB=BC and AD=DC. Prove that its diagonals AC and BD are perpendicular.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 2701; finish: stop.



To prove that the diagonals $ AC $ and $ BD $ of convex quadrilateral $ ABCD $ are perpendicular, we use the properties of isosceles triangles and symmetry.

**Step 1: Use Isosceles Triangle Properties**  
Given $ AB = BC $ and $ AD = DC $, triangles $ ABC $ and $ ADC $ are isosceles. In triangle $ ABC $, the equal sides are $ AB $ and $ BC $, so the **perpendicular bisector of $ AC $** also serves as the **altitude and angle bisector** from vertex $ B $. Similarly, in triangle $ ADC $, the equal sides are $ AD $ and $ DC $, so the **perpendicular bisector of $ AC $** also serves as the **altitude and angle bisector** from vertex $ D $.

**Step 2: Identify the Perpendicular Bisector**  
Since both points $ B $ and $ D $ lie on the **perpendicular bisector of $ AC $**, the line segment $ BD $ must lie along this perpendicular bisector. This implies that $ BD $ is **perpendicular to $ AC $**.

**Step 3: Conclude Perpendicularity of Diagonals**  
As $ BD $ lies on the perpendicular bisector of $ AC $, it is perpendicular to $ AC $. Therefore, the diagonals $ AC $ and $ BD $ are **perpendicular**.

**Final Answer:**  
The diagonals $ AC $ and $ BD $ are perpendicular because points $ B $ and $ D $ lie on the perpendicular bisector of $ AC $, making $ BD $ perpendicular to $ AC $. Thus, $ AC \perp BD $.<|im_end|>

Grade: {"valid": true, "method": "synthetic", "note": "Valid perpendicular-bisector / general vector proof. Sample1 reverses AC vector sign, immaterial to zero dot product.", "repairable": false}

## C03 sample 1

Solve the new problem with concise, justified steps. When using similarity, keep the vertex correspondence explicit. Check the assumptions of each theorem. Do not specialize a general figure without justifying that the requested quantity is preserved. Prefer a short geometric explanation when it is available; any valid method remains allowed. Finish once the proof is complete.

Here are four examples of the desired mathematical care; they are not hints to the new problem.

Example problem: Triangles ABC and DEF satisfy AB=6, AC=9, DE=10, DF=15 and angle BAC=EDF. Find BC/EF, with justification.
Example answer: AB/DE=AC/DF=3/5, and the included angles at A,D are equal. Thus SAS similarity gives A-D, B-E, C-F. In particular BC/EF=3/5.

Example problem: Distinct points A,B,C,D lie on a circle in that cyclic order. Given angle ABD=32 degrees, find angle ACD.
Example answer: B and C are on the same arc from A to D. The inscribed angles ABD and ACD therefore subtend the same opposite arc AD, so they are equal. Thus angle ACD=32 degrees.

Example problem: In triangle ABC, the perpendicular from A to BC meets the interior of BC at D. Given AB=13, BD=5 and DC=9, find AC.
Example answer: Triangle ADB is right at D, so AD^2=AB^2-BD^2=169-25=144. In right triangle ADC, AC^2=AD^2+DC^2=144+81=225. Therefore AC=15.

Example problem: A convex quadrilateral has diagonals which bisect each other. Must it be a rectangle? Give a proof or explicit counterexample.
Example answer: No. Take A=(0,0), B=(2,0), C=(3,1), D=(1,1). This is a convex parallelogram, and both diagonals have midpoint (3/2,1/2). But AB=(2,0) and AD=(1,1) have dot product 2, not 0. Thus angle BAD is not right and the quadrilateral is not a rectangle.

New problem:
ABCD is a convex quadrilateral with AB=BC and AD=DC. Prove that its diagonals AC and BD are perpendicular.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 6115; finish: stop.



To prove that the diagonals $ AC $ and $ BD $ of quadrilateral $ ABCD $ are perpendicular, we leverage vector properties and the given equalities $ AB = BC $ and $ AD = DC $.

---

### Step 1: Set Up Vectors
Let $ \vec{B} = \vec{0} $ (place $ B $ at the origin). Let $ \vec{A} = \vec{a} $, $ \vec{C} = \vec{c} $, and $ \vec{D} = \vec{d} $. The given conditions translate to:

- $ AB = BC \Rightarrow |\vec{a}| = |\vec{c}| $
- $ AD = DC \Rightarrow |\vec{d} - \vec{a}| = |\vec{c} - \vec{d}| $

---

### Step 2: Use the Given Equalities
From $ |\vec{d} - \vec{a}| = |\vec{c} - \vec{d}| $, square both sides:

$$
(\vec{d} - \vec{a}) \cdot (\vec{d} - \vec{a}) = (\vec{c} - \vec{d}) \cdot (\vec{c} - \vec{d})
$$

Expanding both sides:

$$
\vec{d} \cdot \vec{d} - 2\vec{a} \cdot \vec{d} + \vec{a} \cdot \vec{a} = \vec{c} \cdot \vec{c} - 2\vec{c} \cdot \vec{d} + \vec{d} \cdot \vec{d}
$$

Cancel $ \vec{d} \cdot \vec{d} $ from both sides and use $ |\vec{a}| = |\vec{c}| \Rightarrow \vec{a} \cdot \vec{a} = \vec{c} \cdot \vec{c} $:

$$
-2\vec{a} \cdot \vec{d} = -2\vec{c} \cdot \vec{d}
$$

Divide both sides by $ -2 $:

$$
\vec{a} \cdot \vec{d} = \vec{c} \cdot \vec{d}
$$

This implies:

$$
(\vec{a} - \vec{c}) \cdot \vec{d} = 0
$$

---

### Step 3: Interpret the Result
The vector $ \vec{a} - \vec{c} $ is the vector $ \vec{AC} $, and $ \vec{d} $ is the vector $ \vec{BD} $ (since $ \vec{B} = \vec{0} $). Therefore:

$$
\vec{AC} \cdot \vec{BD} = 0
$$

This shows that the diagonals $ AC $ and $ BD $ are **perpendicular**.

---

### Final Conclusion
The diagonals $ AC $ and $ BD $ of quadrilateral $ ABCD $, with $ AB = BC $ and $ AD = DC $, are **perpendicular**.

$$
\boxed{\text{Diagonals } AC \text{ and } BD \text{ are perpendicular.}}
$$<|im_end|>

Grade: {"valid": true, "method": "analytic", "note": "Valid perpendicular-bisector / general vector proof. Sample1 reverses AC vector sign, immaterial to zero dot product.", "repairable": false}

## C04 sample 0

Solve the new problem with concise, justified steps. When using similarity, keep the vertex correspondence explicit. Check the assumptions of each theorem. Do not specialize a general figure without justifying that the requested quantity is preserved. Prefer a short geometric explanation when it is available; any valid method remains allowed. Finish once the proof is complete.

Here are four examples of the desired mathematical care; they are not hints to the new problem.

Example problem: Triangles ABC and DEF satisfy AB=6, AC=9, DE=10, DF=15 and angle BAC=EDF. Find BC/EF, with justification.
Example answer: AB/DE=AC/DF=3/5, and the included angles at A,D are equal. Thus SAS similarity gives A-D, B-E, C-F. In particular BC/EF=3/5.

Example problem: Distinct points A,B,C,D lie on a circle in that cyclic order. Given angle ABD=32 degrees, find angle ACD.
Example answer: B and C are on the same arc from A to D. The inscribed angles ABD and ACD therefore subtend the same opposite arc AD, so they are equal. Thus angle ACD=32 degrees.

Example problem: In triangle ABC, the perpendicular from A to BC meets the interior of BC at D. Given AB=13, BD=5 and DC=9, find AC.
Example answer: Triangle ADB is right at D, so AD^2=AB^2-BD^2=169-25=144. In right triangle ADC, AC^2=AD^2+DC^2=144+81=225. Therefore AC=15.

Example problem: A convex quadrilateral has diagonals which bisect each other. Must it be a rectangle? Give a proof or explicit counterexample.
Example answer: No. Take A=(0,0), B=(2,0), C=(3,1), D=(1,1). This is a convex parallelogram, and both diagonals have midpoint (3/2,1/2). But AB=(2,0) and AD=(1,1) have dot product 2, not 0. Thus angle BAD is not right and the quadrilateral is not a rectangle.

New problem:
ABCD is a nondegenerate parallelogram, E is the midpoint of AB, and lines DE and AC meet at F. Find AF/FC.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 4133; finish: stop.



To determine the ratio $ \dfrac{AF}{FC} $ in the given configuration of a nondegenerate parallelogram $ABCD$, where $E$ is the midpoint of $AB$ and $F$ is the intersection of $DE$ and $AC$, we proceed with a general geometric argument using vector analysis.

---

### **Step 1: Assign Vectors to Points**

Let us assign vectors to the points in the parallelogram:

- Let point $A$ be the origin, so $ \vec{A} = \vec{0} $.
- Let $ \vec{AB} = \vec{b} $ and $ \vec{AD} = \vec{d} $, then:
  - $ \vec{B} = \vec{b} $
  - $ \vec{D} = \vec{d} $
  - $ \vec{C} = \vec{b} + \vec{d} $, since $ABCD$ is a parallelogram.

Since $E$ is the midpoint of $AB$, we have:
$$
\vec{E} = \frac{1}{2} \vec{b}
$$

---

### **Step 2: Parametrize the Lines**

- Line $DE$ goes from $D = \vec{d}$ to $E = \frac{1}{2} \vec{b}$. A parametric representation of this line is:
$$
\vec{r}_{DE}(t) = \vec{d} + t\left(\frac{1}{2} \vec{b} - \vec{d}\right), \quad t \in \mathbb{R}
$$

- Line $AC$ goes from $A = \vec{0}$ to $C = \vec{b} + \vec{d}$. A parametric representation of this line is:
$$
\vec{r}_{AC}(s) = s(\vec{b} + \vec{d}), \quad s \in \mathbb{R}
$$

---

### **Step 3: Find the Intersection Point $F$**

We find the point $F$ that lies on both lines, so we solve for $t$ and $s$ such that:
$$
\vec{d} + t\left(\frac{1}{2} \vec{b} - \vec{d}\right) = s(\vec{b} + \vec{d})
$$

Expanding both sides:
$$
\vec{d} + \frac{t}{2} \vec{b} - t \vec{d} = s \vec{b} + s \vec{d}
$$

Grouping terms by vector components:
$$
\left(\frac{t}{2} \vec{b}\right) + \left((1 - t) \vec{d}\right) = s \vec{b} + s \vec{d}
$$

Equating coefficients of $ \vec{b} $ and $ \vec{d} $:
- $ \frac{t}{2} = s $
- $ 1 - t = s $

Substitute $ s = \frac{t}{2} $ into the second equation:
$$
1 - t = \frac{t}{2} \Rightarrow 1 = \frac{3t}{2} \Rightarrow t = \frac{2}{3}
$$

Then:
$$
s = \frac{t}{2} = \frac{1}{3}
$$

---

### **Step 4: Compute the Ratio**

Since $F$ lies on $AC$ at parameter $s = \frac{1}{3}$, the point $F$ divides $AC$ in the ratio:
$$
AF : FC = s : (1 - s) = \frac{1}{3} : \frac{2}{3} = \frac{1}{2}
$$

---

### **Conclusion**

The ratio of $AF$ to $FC$ is:

$$
\boxed{\dfrac{1}{2}}
$$<|im_end|>

Grade: {"valid": true, "method": "analytic", "note": "General vectors / nonrectangular coordinates yield1/2.", "repairable": false}

## C04 sample 1

Solve the new problem with concise, justified steps. When using similarity, keep the vertex correspondence explicit. Check the assumptions of each theorem. Do not specialize a general figure without justifying that the requested quantity is preserved. Prefer a short geometric explanation when it is available; any valid method remains allowed. Finish once the proof is complete.

Here are four examples of the desired mathematical care; they are not hints to the new problem.

Example problem: Triangles ABC and DEF satisfy AB=6, AC=9, DE=10, DF=15 and angle BAC=EDF. Find BC/EF, with justification.
Example answer: AB/DE=AC/DF=3/5, and the included angles at A,D are equal. Thus SAS similarity gives A-D, B-E, C-F. In particular BC/EF=3/5.

Example problem: Distinct points A,B,C,D lie on a circle in that cyclic order. Given angle ABD=32 degrees, find angle ACD.
Example answer: B and C are on the same arc from A to D. The inscribed angles ABD and ACD therefore subtend the same opposite arc AD, so they are equal. Thus angle ACD=32 degrees.

Example problem: In triangle ABC, the perpendicular from A to BC meets the interior of BC at D. Given AB=13, BD=5 and DC=9, find AC.
Example answer: Triangle ADB is right at D, so AD^2=AB^2-BD^2=169-25=144. In right triangle ADC, AC^2=AD^2+DC^2=144+81=225. Therefore AC=15.

Example problem: A convex quadrilateral has diagonals which bisect each other. Must it be a rectangle? Give a proof or explicit counterexample.
Example answer: No. Take A=(0,0), B=(2,0), C=(3,1), D=(1,1). This is a convex parallelogram, and both diagonals have midpoint (3/2,1/2). But AB=(2,0) and AD=(1,1) have dot product 2, not 0. Thus angle BAD is not right and the quadrilateral is not a rectangle.

New problem:
ABCD is a nondegenerate parallelogram, E is the midpoint of AB, and lines DE and AC meet at F. Find AF/FC.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 4520; finish: stop.



To solve the problem, we are given a nondegenerate parallelogram $ABCD$, with $E$ as the midpoint of side $AB$, and lines $DE$ and $AC$ intersecting at point $F$. The goal is to find the ratio $ \dfrac{AF}{FC} $.

---

### Step 1: Assign Coordinates for Generality

We can assign coordinates to the points to make the problem more concrete. Let:
- $A = (0, 0)$
- $B = (2, 0)$
- $D = (a, b)$
- Then $C = B + D - A = (2 + a, b)$, since $ABCD$ is a parallelogram.

Since $E$ is the midpoint of $AB$, its coordinates are:
$$
E = \left(1, 0\right)
$$

---

### Step 2: Parametrize the Lines

**Line $AC$** (from $A = (0, 0)$ to $C = (2 + a, b)$):
$$
x = t(2 + a), \quad y = tb, \quad t \in [0, 1]
$$

**Line $DE$** (from $D = (a, b)$ to $E = (1, 0)$):
$$
x = a + s(1 - a), \quad y = b - sb = b(1 - s), \quad s \in [0, 1]
$$

---

### Step 3: Find the Intersection Point $F$

Set the coordinates equal for the two parametric lines:

$$
t(2 + a) = a + s(1 - a) \quad \text{(1)}
$$
$$
tb = b(1 - s) \quad \text{(2)}
$$

From (2), assuming $b \ne 0$, we get:
$$
t = 1 - s
$$

Substitute into (1):
$$
(1 - s)(2 + a) = a + s(1 - a)
$$
$$
2 + a - s(2 + a) = a + s(1 - a)
$$
$$
2 + a - a - s(2 + a + 1 - a) = 0
$$
$$
2 - 3s = 0 \Rightarrow s = \dfrac{2}{3}
$$

Then $t = 1 - \dfrac{2}{3} = \dfrac{1}{3}$

---

### Step 4: Compute the Ratio $ \dfrac{AF}{FC} $

Since $F$ lies on $AC$ at parameter $t = \dfrac{1}{3}$, the point $F$ divides $AC$ in the ratio:
$$
AF : FC = t : (1 - t) = \dfrac{1}{3} : \dfrac{2}{3} = 1 : 2
$$

Thus,
$$
\dfrac{AF}{FC} = \dfrac{1}{2}
$$

---

### Conclusion

The ratio $ \dfrac{AF}{FC} $ is:

$$
\boxed{\dfrac{1}{2}}
$$<|im_end|>

Grade: {"valid": true, "method": "analytic", "note": "General vectors / nonrectangular coordinates yield1/2.", "repairable": false}

## C05 sample 0

Solve the new problem with concise, justified steps. When using similarity, keep the vertex correspondence explicit. Check the assumptions of each theorem. Do not specialize a general figure without justifying that the requested quantity is preserved. Prefer a short geometric explanation when it is available; any valid method remains allowed. Finish once the proof is complete.

Here are four examples of the desired mathematical care; they are not hints to the new problem.

Example problem: Triangles ABC and DEF satisfy AB=6, AC=9, DE=10, DF=15 and angle BAC=EDF. Find BC/EF, with justification.
Example answer: AB/DE=AC/DF=3/5, and the included angles at A,D are equal. Thus SAS similarity gives A-D, B-E, C-F. In particular BC/EF=3/5.

Example problem: Distinct points A,B,C,D lie on a circle in that cyclic order. Given angle ABD=32 degrees, find angle ACD.
Example answer: B and C are on the same arc from A to D. The inscribed angles ABD and ACD therefore subtend the same opposite arc AD, so they are equal. Thus angle ACD=32 degrees.

Example problem: In triangle ABC, the perpendicular from A to BC meets the interior of BC at D. Given AB=13, BD=5 and DC=9, find AC.
Example answer: Triangle ADB is right at D, so AD^2=AB^2-BD^2=169-25=144. In right triangle ADC, AC^2=AD^2+DC^2=144+81=225. Therefore AC=15.

Example problem: A convex quadrilateral has diagonals which bisect each other. Must it be a rectangle? Give a proof or explicit counterexample.
Example answer: No. Take A=(0,0), B=(2,0), C=(3,1), D=(1,1). This is a convex parallelogram, and both diagonals have midpoint (3/2,1/2). But AB=(2,0) and AD=(1,1) have dot product 2, not 0. Thus angle BAD is not right and the quadrilateral is not a rectangle.

New problem:
AB is a diameter of a circle with center O. C is another point on the circle. The tangent at C meets the tangents at A and B at X and Y, respectively. Prove that angle XOY=90 degrees.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 3314; finish: stop.



To prove that $\angle XOY = 90^\circ$, we analyze the geometric configuration and use coordinate geometry to verify perpendicularity.

---

### **Step 1: Coordinate Setup**

Place the circle with center $O$ at the origin $(0, 0)$ and diameter $AB$ along the x-axis. Let:
- $A = (-1, 0)$, $B = (1, 0)$, and $O = (0, 0)$.
- Let point $C$ lie on the circle at $(\cos\theta, \sin\theta)$, where $\theta$ is an angle parameter.

---

### **Step 2: Tangent Equations**

- The **tangent at $A$** is perpendicular to $OA$. Since $OA$ is horizontal, the tangent at $A$ is vertical:  
  $$
  x = -1
  $$

- The **tangent at $B$** is perpendicular to $OB$, also vertical:  
  $$
  x = 1
  $$

- The **tangent at $C$** is perpendicular to $OC$. The equation of the tangent at point $C = (\cos\theta, \sin\theta)$ on the unit circle is:  
  $$
  x\cos\theta + y\sin\theta = 1
  $$

---

### **Step 3: Find Points $X$ and $Y$**

- **Point $X$** is the intersection of the tangent at $C$ and the tangent at $A$ ($x = -1$):  
  Substitute $x = -1$ into the tangent at $C$:  
  $$
  -\cos\theta + y\sin\theta = 1 \Rightarrow y = \frac{1 + \cos\theta}{\sin\theta}
  $$  
  So, $X = \left(-1, \frac{1 + \cos\theta}{\sin\theta}\right)$

- **Point $Y$** is the intersection of the tangent at $C$ and the tangent at $B$ ($x = 1$):  
  Substitute $x = 1$ into the tangent at $C$:  
  $$
  \cos\theta + y\sin\theta = 1 \Rightarrow y = \frac{1 - \cos\theta}{\sin\theta}
  $$  
  So, $Y = \left(1, \frac{1 - \cos\theta}{\sin\theta}\right)$

---

### **Step 4: Verify Perpendicularity of Vectors $\vec{OX}$ and $\vec{OY}$**

- Vectors:
  $$
  \vec{OX} = \left(-1, \frac{1 + \cos\theta}{\sin\theta}\right), \quad \vec{OY} = \left(1, \frac{1 - \cos\theta}{\sin\theta}\right)
  $$

- Compute the **dot product**:
  $$
  \vec{OX} \cdot \vec{OY} = (-1)(1) + \left(\frac{1 + \cos\theta}{\sin\theta}\right)\left(\frac{1 - \cos\theta}{\sin\theta}\right)
  $$

- Simplify:
  $$
  = -1 + \frac{(1 - \cos^2\theta)}{\sin^2\theta} = -1 + \frac{\sin^2\theta}{\sin^2\theta} = -1 + 1 = 0
  $$

Since the dot product is zero, vectors $\vec{OX}$ and $\vec{OY}$ are **perpendicular**.

---

### **Conclusion**

The vectors $\vec{OX}$ and $\vec{OY}$ are perpendicular, so $\angle XOY = 90^\circ$. Therefore, we have shown that:

$$
\boxed{\angle XOY = 90^\circ}
$$<|im_end|>

Grade: {"valid": true, "method": "analytic", "note": "Valid general tangent-coordinate dot product proof.", "repairable": false}

## C05 sample 1

Solve the new problem with concise, justified steps. When using similarity, keep the vertex correspondence explicit. Check the assumptions of each theorem. Do not specialize a general figure without justifying that the requested quantity is preserved. Prefer a short geometric explanation when it is available; any valid method remains allowed. Finish once the proof is complete.

Here are four examples of the desired mathematical care; they are not hints to the new problem.

Example problem: Triangles ABC and DEF satisfy AB=6, AC=9, DE=10, DF=15 and angle BAC=EDF. Find BC/EF, with justification.
Example answer: AB/DE=AC/DF=3/5, and the included angles at A,D are equal. Thus SAS similarity gives A-D, B-E, C-F. In particular BC/EF=3/5.

Example problem: Distinct points A,B,C,D lie on a circle in that cyclic order. Given angle ABD=32 degrees, find angle ACD.
Example answer: B and C are on the same arc from A to D. The inscribed angles ABD and ACD therefore subtend the same opposite arc AD, so they are equal. Thus angle ACD=32 degrees.

Example problem: In triangle ABC, the perpendicular from A to BC meets the interior of BC at D. Given AB=13, BD=5 and DC=9, find AC.
Example answer: Triangle ADB is right at D, so AD^2=AB^2-BD^2=169-25=144. In right triangle ADC, AC^2=AD^2+DC^2=144+81=225. Therefore AC=15.

Example problem: A convex quadrilateral has diagonals which bisect each other. Must it be a rectangle? Give a proof or explicit counterexample.
Example answer: No. Take A=(0,0), B=(2,0), C=(3,1), D=(1,1). This is a convex parallelogram, and both diagonals have midpoint (3/2,1/2). But AB=(2,0) and AD=(1,1) have dot product 2, not 0. Thus angle BAD is not right and the quadrilateral is not a rectangle.

New problem:
AB is a diameter of a circle with center O. C is another point on the circle. The tangent at C meets the tangents at A and B at X and Y, respectively. Prove that angle XOY=90 degrees.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 3984; finish: stop.



To prove that $\angle XOY = 90^\circ$, we analyze the geometric configuration involving a circle with diameter $AB$, center $O$, and a point $C$ on the circle. The tangents at points $A$, $B$, and $C$ intersect at points $X$, $Y$, and $C$ respectively. We aim to show that the angle between the lines $OX$ and $OY$ is a right angle.

---

### Step 1: Coordinate Setup

Let the circle have center $O = (0, 0)$ and radius $1$. Place the diameter $AB$ along the x-axis:
- $A = (-1, 0)$, $B = (1, 0)$
- Let $C = (\cos\theta, \sin\theta)$ for some angle $\theta$.

The tangent line at point $C$ is perpendicular to the radius $OC$, and its equation is:
$$
x\cos\theta + y\sin\theta = 1
$$

---

### Step 2: Find Coordinates of Points $X$ and $Y$

- **Point $X$** is the intersection of the tangent at $C$ with the tangent at $A$. The tangent at $A$ is vertical: $x = -1$. Substituting into the tangent line equation:
  $$
  -\cos\theta + y\sin\theta = 1 \Rightarrow y = \frac{1 + \cos\theta}{\sin\theta}
  $$
  So, $X = (-1, \frac{1 + \cos\theta}{\sin\theta})$

- **Point $Y$** is the intersection of the tangent at $C$ with the tangent at $B$. The tangent at $B$ is vertical: $x = 1$. Substituting into the tangent line equation:
  $$
  \cos\theta + y\sin\theta = 1 \Rightarrow y = \frac{1 - \cos\theta}{\sin\theta}
  $$
  So, $Y = (1, \frac{1 - \cos\theta}{\sin\theta})$

---

### Step 3: Compute Vectors $OX$ and $OY$

- Vector $OX = (-1, \frac{1 + \cos\theta}{\sin\theta})$
- Vector $OY = (1, \frac{1 - \cos\theta}{\sin\theta})$

Compute the dot product:
$$
OX \cdot OY = (-1)(1) + \left(\frac{1 + \cos\theta}{\sin\theta}\right)\left(\frac{1 - \cos\theta}{\sin\theta}\right)
$$
$$
= -1 + \frac{(1 - \cos^2\theta)}{\sin^2\theta} = -1 + \frac{\sin^2\theta}{\sin^2\theta} = -1 + 1 = 0
$$

---

### Step 4: Conclusion

Since the dot product of vectors $OX$ and $OY$ is zero, the angle between them is $90^\circ$. Therefore:

$$
\boxed{\angle XOY = 90^\circ}
$$<|im_end|>

Grade: {"valid": true, "method": "analytic", "note": "Valid general tangent-coordinate dot product proof.", "repairable": false}

## C06 sample 0

Solve the new problem with concise, justified steps. When using similarity, keep the vertex correspondence explicit. Check the assumptions of each theorem. Do not specialize a general figure without justifying that the requested quantity is preserved. Prefer a short geometric explanation when it is available; any valid method remains allowed. Finish once the proof is complete.

Here are four examples of the desired mathematical care; they are not hints to the new problem.

Example problem: Triangles ABC and DEF satisfy AB=6, AC=9, DE=10, DF=15 and angle BAC=EDF. Find BC/EF, with justification.
Example answer: AB/DE=AC/DF=3/5, and the included angles at A,D are equal. Thus SAS similarity gives A-D, B-E, C-F. In particular BC/EF=3/5.

Example problem: Distinct points A,B,C,D lie on a circle in that cyclic order. Given angle ABD=32 degrees, find angle ACD.
Example answer: B and C are on the same arc from A to D. The inscribed angles ABD and ACD therefore subtend the same opposite arc AD, so they are equal. Thus angle ACD=32 degrees.

Example problem: In triangle ABC, the perpendicular from A to BC meets the interior of BC at D. Given AB=13, BD=5 and DC=9, find AC.
Example answer: Triangle ADB is right at D, so AD^2=AB^2-BD^2=169-25=144. In right triangle ADC, AC^2=AD^2+DC^2=144+81=225. Therefore AC=15.

Example problem: A convex quadrilateral has diagonals which bisect each other. Must it be a rectangle? Give a proof or explicit counterexample.
Example answer: No. Take A=(0,0), B=(2,0), C=(3,1), D=(1,1). This is a convex parallelogram, and both diagonals have midpoint (3/2,1/2). But AB=(2,0) and AD=(1,1) have dot product 2, not 0. Thus angle BAD is not right and the quadrilateral is not a rectangle.

New problem:
ABC is an equilateral triangle of altitude h. P is strictly inside the triangle, and its perpendicular distances to lines AB, BC, CA are x,y,z. Prove that x+y+z=h.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 3542; finish: stop.



To prove that the sum of the perpendicular distances from a point $ P $ inside an equilateral triangle $ ABC $ to its sides equals the altitude $ h $, we can rely on a geometric argument based on area decomposition.

---

### **Key Observations and Setup**

Let $ ABC $ be an equilateral triangle with altitude $ h $, and let $ P $ be a point strictly inside the triangle. Let $ x $, $ y $, and $ z $ be the perpendicular distances from $ P $ to the sides $ AB $, $ BC $, and $ CA $, respectively.

Since $ ABC $ is equilateral, all its sides are of equal length, say $ s $. The altitude $ h $ is related to the side length by the formula:

$$
h = \frac{\sqrt{3}}{2}s
$$

---

### **Geometric Argument via Area**

The triangle $ ABC $ is divided by the point $ P $ into three smaller triangles: $ \triangle PAB $, $ \triangle PBC $, and $ \triangle PCA $. These three smaller triangles, along with their respective perpendicular distances from $ P $ to the sides, form a partition of the original triangle $ ABC $.

The area of each smaller triangle can be expressed in terms of the base (a side of the triangle) and the corresponding height (the perpendicular distance from $ P $ to that side):

$$
\text{Area of } \triangle PAB = \frac{1}{2} s x \\
\text{Area of } \triangle PBC = \frac{1}{2} s y \\
\text{Area of } \triangle PCA = \frac{1}{2} s z
$$

Adding these areas gives the total area of triangle $ ABC $:

$$
\frac{1}{2} s x + \frac{1}{2} s y + \frac{1}{2} s z = \frac{1}{2} s (x + y + z)
$$

But the area of triangle $ ABC $ is also given by:

$$
\frac{1}{2} s h
$$

Equating the two expressions for the area:

$$
\frac{1}{2} s (x + y + z) = \frac{1}{2} s h
$$

Canceling $ \frac{1}{2} s $ from both sides (since $ s \neq 0 $):

$$
x + y + z = h
$$

---

### **Conclusion**

This proof is valid under the assumption that the point $ P $ lies strictly inside the triangle, and the perpendicular distances to the sides are well-defined. The key idea is that the total area of the triangle is preserved when decomposed into the three smaller triangles formed by the point $ P $, leading to the conclusion that the sum of the perpendicular distances from any interior point to the sides of an equilateral triangle equals the altitude.

$$
\boxed{h}
$$<|im_end|>

Grade: {"valid": true, "method": "area", "note": "Valid area decomposition.", "repairable": false}

## C06 sample 1

Solve the new problem with concise, justified steps. When using similarity, keep the vertex correspondence explicit. Check the assumptions of each theorem. Do not specialize a general figure without justifying that the requested quantity is preserved. Prefer a short geometric explanation when it is available; any valid method remains allowed. Finish once the proof is complete.

Here are four examples of the desired mathematical care; they are not hints to the new problem.

Example problem: Triangles ABC and DEF satisfy AB=6, AC=9, DE=10, DF=15 and angle BAC=EDF. Find BC/EF, with justification.
Example answer: AB/DE=AC/DF=3/5, and the included angles at A,D are equal. Thus SAS similarity gives A-D, B-E, C-F. In particular BC/EF=3/5.

Example problem: Distinct points A,B,C,D lie on a circle in that cyclic order. Given angle ABD=32 degrees, find angle ACD.
Example answer: B and C are on the same arc from A to D. The inscribed angles ABD and ACD therefore subtend the same opposite arc AD, so they are equal. Thus angle ACD=32 degrees.

Example problem: In triangle ABC, the perpendicular from A to BC meets the interior of BC at D. Given AB=13, BD=5 and DC=9, find AC.
Example answer: Triangle ADB is right at D, so AD^2=AB^2-BD^2=169-25=144. In right triangle ADC, AC^2=AD^2+DC^2=144+81=225. Therefore AC=15.

Example problem: A convex quadrilateral has diagonals which bisect each other. Must it be a rectangle? Give a proof or explicit counterexample.
Example answer: No. Take A=(0,0), B=(2,0), C=(3,1), D=(1,1). This is a convex parallelogram, and both diagonals have midpoint (3/2,1/2). But AB=(2,0) and AD=(1,1) have dot product 2, not 0. Thus angle BAD is not right and the quadrilateral is not a rectangle.

New problem:
ABC is an equilateral triangle of altitude h. P is strictly inside the triangle, and its perpendicular distances to lines AB, BC, CA are x,y,z. Prove that x+y+z=h.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 3615; finish: stop.



To prove that for any point $ P $ strictly inside an equilateral triangle $ ABC $ with altitude $ h $, the sum of the perpendicular distances from $ P $ to the sides $ AB $, $ BC $, and $ CA $ equals $ h $, we proceed as follows:

---

### Step 1: Area Decomposition

Let $ P $ be a point inside triangle $ ABC $. The triangle can be partitioned into three smaller triangles: $ \triangle PAB $, $ \triangle PBC $, and $ \triangle PCA $, each sharing a vertex at $ P $ and having a base on one of the sides of $ ABC $.

The total area of $ ABC $ is the sum of the areas of these three smaller triangles:
$$
\text{Area of } \triangle ABC = \text{Area of } \triangle PAB + \text{Area of } \triangle PBC + \text{Area of } \triangle PCA.
$$

---

### Step 2: Express Each Area Using Base and Height

Let the perpendicular distances from $ P $ to the sides $ AB $, $ BC $, and $ CA $ be $ x $, $ y $, and $ z $, respectively. Since the triangle is equilateral, all sides have the same length, say $ s $, and the area of $ ABC $ is:
$$
\text{Area of } \triangle ABC = \frac{1}{2} s h.
$$

Now, express the areas of the smaller triangles:
- $ \text{Area of } \triangle PAB = \frac{1}{2} s x $,
- $ \text{Area of } \triangle PBC = \frac{1}{2} s y $,
- $ \text{Area of } \triangle PCA = \frac{1}{2} s z $.

Summing these:
$$
\frac{1}{2} s x + \frac{1}{2} s y + \frac{1}{2} s z = \frac{1}{2} s h.
$$

---

### Step 3: Simplify and Conclude

Divide both sides of the equation by $ \frac{1}{2} s $:
$$
x + y + z = h.
$$

This equality holds for any point $ P $ strictly inside the triangle, as the areas are additive and the formula for the area of a triangle using base and height is valid in this context.

---

### Final Answer

$$
\boxed{x + y + z = h}
$$<|im_end|>

Grade: {"valid": true, "method": "area", "note": "Valid area decomposition.", "repairable": false}

## C07 sample 0

Solve the new problem with concise, justified steps. When using similarity, keep the vertex correspondence explicit. Check the assumptions of each theorem. Do not specialize a general figure without justifying that the requested quantity is preserved. Prefer a short geometric explanation when it is available; any valid method remains allowed. Finish once the proof is complete.

Here are four examples of the desired mathematical care; they are not hints to the new problem.

Example problem: Triangles ABC and DEF satisfy AB=6, AC=9, DE=10, DF=15 and angle BAC=EDF. Find BC/EF, with justification.
Example answer: AB/DE=AC/DF=3/5, and the included angles at A,D are equal. Thus SAS similarity gives A-D, B-E, C-F. In particular BC/EF=3/5.

Example problem: Distinct points A,B,C,D lie on a circle in that cyclic order. Given angle ABD=32 degrees, find angle ACD.
Example answer: B and C are on the same arc from A to D. The inscribed angles ABD and ACD therefore subtend the same opposite arc AD, so they are equal. Thus angle ACD=32 degrees.

Example problem: In triangle ABC, the perpendicular from A to BC meets the interior of BC at D. Given AB=13, BD=5 and DC=9, find AC.
Example answer: Triangle ADB is right at D, so AD^2=AB^2-BD^2=169-25=144. In right triangle ADC, AC^2=AD^2+DC^2=144+81=225. Therefore AC=15.

Example problem: A convex quadrilateral has diagonals which bisect each other. Must it be a rectangle? Give a proof or explicit counterexample.
Example answer: No. Take A=(0,0), B=(2,0), C=(3,1), D=(1,1). This is a convex parallelogram, and both diagonals have midpoint (3/2,1/2). But AB=(2,0) and AD=(1,1) have dot product 2, not 0. Thus angle BAD is not right and the quadrilateral is not a rectangle.

New problem:
Triangle ABC has AB=13, AC=14, BC=15. Its incircle touches BC at D. Find BD.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 1548; finish: stop.



To find the length of $ BD $ in triangle $ ABC $, where the incircle touches $ BC $ at $ D $, we use the standard geometric property related to the incircle and semiperimeter.

---

### Step 1: Use the Semiperimeter Formula

Given the triangle has side lengths:
- $ AB = 13 $
- $ AC = 14 $
- $ BC = 15 $

The **semiperimeter** $ s $ is:
$$
s = \frac{AB + AC + BC}{2} = \frac{13 + 14 + 15}{2} = 21
$$

In a triangle, the length from a vertex to the point where the incircle touches the opposite side is given by:
$$
BD = s - AC
$$
This formula is derived from the fact that the tangents from a point to a circle are equal in length.

---

### Step 2: Apply the Formula

Substitute the known values:
$$
BD = s - AC = 21 - 14 = 7
$$

---

### Final Answer

$$
\boxed{7}
$$<|im_end|>

Grade: {"valid": true, "method": "synthetic", "note": "Correct standard tangent-length formula; sample1 also checks equal tangent segments.", "repairable": false}

## C07 sample 1

Solve the new problem with concise, justified steps. When using similarity, keep the vertex correspondence explicit. Check the assumptions of each theorem. Do not specialize a general figure without justifying that the requested quantity is preserved. Prefer a short geometric explanation when it is available; any valid method remains allowed. Finish once the proof is complete.

Here are four examples of the desired mathematical care; they are not hints to the new problem.

Example problem: Triangles ABC and DEF satisfy AB=6, AC=9, DE=10, DF=15 and angle BAC=EDF. Find BC/EF, with justification.
Example answer: AB/DE=AC/DF=3/5, and the included angles at A,D are equal. Thus SAS similarity gives A-D, B-E, C-F. In particular BC/EF=3/5.

Example problem: Distinct points A,B,C,D lie on a circle in that cyclic order. Given angle ABD=32 degrees, find angle ACD.
Example answer: B and C are on the same arc from A to D. The inscribed angles ABD and ACD therefore subtend the same opposite arc AD, so they are equal. Thus angle ACD=32 degrees.

Example problem: In triangle ABC, the perpendicular from A to BC meets the interior of BC at D. Given AB=13, BD=5 and DC=9, find AC.
Example answer: Triangle ADB is right at D, so AD^2=AB^2-BD^2=169-25=144. In right triangle ADC, AC^2=AD^2+DC^2=144+81=225. Therefore AC=15.

Example problem: A convex quadrilateral has diagonals which bisect each other. Must it be a rectangle? Give a proof or explicit counterexample.
Example answer: No. Take A=(0,0), B=(2,0), C=(3,1), D=(1,1). This is a convex parallelogram, and both diagonals have midpoint (3/2,1/2). But AB=(2,0) and AD=(1,1) have dot product 2, not 0. Thus angle BAD is not right and the quadrilateral is not a rectangle.

New problem:
Triangle ABC has AB=13, AC=14, BC=15. Its incircle touches BC at D. Find BD.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 1785; finish: stop.



To find the length of $ BD $, where the incircle of triangle $ ABC $ touches side $ BC $ at point $ D $, we use a standard geometric result involving the semiperimeter of the triangle.

---

### Step 1: Compute the Semiperimeter

Given the side lengths:
- $ AB = 13 $
- $ AC = 14 $
- $ BC = 15 $

The semiperimeter $ s $ is:

$$
s = \frac{AB + AC + BC}{2} = \frac{13 + 14 + 15}{2} = \frac{42}{2} = 21
$$

---

### Step 2: Apply the Formula for the Tangent Lengths

In a triangle, the length of the tangent from a vertex to the point of tangency of the incircle with the opposite side is given by:

$$
BD = s - AC
$$

Substituting the known values:

$$
BD = 21 - 14 = 7
$$

---

### Step 3: Verification via Tangent Properties

Let’s verify this result by considering the tangents from each vertex to the incircle. Denote the points of tangency on sides $ AB $, $ BC $, and $ AC $ as $ F $, $ D $, and $ E $, respectively.

From the properties of tangents drawn from a single point to a circle, we know:

- $ BD = BF $
- $ DC = EC $
- $ AF = AE $

Let’s denote:
- $ BD = x $
- Then $ DC = 15 - x $

From the tangent lengths:
- $ BF = BD = x $
- $ AF = AE = s - BC = 21 - 15 = 6 $

Then, since $ AB = AF + BF $, we have:

$$
13 = 6 + x \Rightarrow x = 7
$$

This confirms that $ BD = 7 $.

---

### Final Conclusion

The length of $ BD $, the segment from vertex $ B $ to the point where the incircle touches side $ BC $, is:

$$
\boxed{7}
$$<|im_end|>

Grade: {"valid": true, "method": "synthetic", "note": "Correct standard tangent-length formula; sample1 also checks equal tangent segments.", "repairable": false}

## C08 sample 0

Solve the new problem with concise, justified steps. When using similarity, keep the vertex correspondence explicit. Check the assumptions of each theorem. Do not specialize a general figure without justifying that the requested quantity is preserved. Prefer a short geometric explanation when it is available; any valid method remains allowed. Finish once the proof is complete.

Here are four examples of the desired mathematical care; they are not hints to the new problem.

Example problem: Triangles ABC and DEF satisfy AB=6, AC=9, DE=10, DF=15 and angle BAC=EDF. Find BC/EF, with justification.
Example answer: AB/DE=AC/DF=3/5, and the included angles at A,D are equal. Thus SAS similarity gives A-D, B-E, C-F. In particular BC/EF=3/5.

Example problem: Distinct points A,B,C,D lie on a circle in that cyclic order. Given angle ABD=32 degrees, find angle ACD.
Example answer: B and C are on the same arc from A to D. The inscribed angles ABD and ACD therefore subtend the same opposite arc AD, so they are equal. Thus angle ACD=32 degrees.

Example problem: In triangle ABC, the perpendicular from A to BC meets the interior of BC at D. Given AB=13, BD=5 and DC=9, find AC.
Example answer: Triangle ADB is right at D, so AD^2=AB^2-BD^2=169-25=144. In right triangle ADC, AC^2=AD^2+DC^2=144+81=225. Therefore AC=15.

Example problem: A convex quadrilateral has diagonals which bisect each other. Must it be a rectangle? Give a proof or explicit counterexample.
Example answer: No. Take A=(0,0), B=(2,0), C=(3,1), D=(1,1). This is a convex parallelogram, and both diagonals have midpoint (3/2,1/2). But AB=(2,0) and AD=(1,1) have dot product 2, not 0. Thus angle BAD is not right and the quadrilateral is not a rectangle.

New problem:
In an isosceles triangle ABC with AB=AC, D is strictly inside AB and E is strictly inside AC, with BD=CE. Let F be the intersection of BE and CD. Prove BF=CF.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 2600; finish: stop.



To prove that $ BF = CF $ in the given isosceles triangle $ ABC $ with $ AB = AC $, where $ D $ lies strictly inside $ AB $, $ E $ lies strictly inside $ AC $, and $ BD = CE $, we proceed as follows:

---

### **Step 1: Establish Symmetry via Segment Lengths**

Given:
- $ AB = AC $ (isosceles triangle),
- $ BD = CE $,
- $ D \in AB $, $ E \in AC $.

Since $ AB = AC $, and $ BD = CE $, then:
$$
AD = AB - BD = AC - CE = AE.
$$
Thus, $ AD = AE $, meaning that $ D $ and $ E $ are symmetric with respect to the axis of symmetry of triangle $ ABC $, which is the altitude from $ A $ to $ BC $.

---

### **Step 2: Use Congruence of Triangles**

Because $ AB = AC $, $ BD = CE $, and $ AD = AE $, triangles $ ABD $ and $ ACE $ are congruent by the **SSS Congruence Theorem**.

This congruence implies that:
$$
\angle ABD = \angle ACE.
$$

---

### **Step 3: Apply Reflection Symmetry**

The triangle $ ABC $ is isosceles with $ AB = AC $, so the **altitude from $ A $** is also the **axis of symmetry**. Reflecting triangle $ ABC $ across this axis swaps points $ B $ and $ C $, and maps $ D $ to $ E $ (since $ AD = AE $).

Therefore, the line $ BE $ is the reflection of $ CD $ across the altitude. Their intersection point $ F $ must lie on the axis of symmetry (the altitude from $ A $) because the reflection maps $ BE $ to $ CD $, and the only point fixed under reflection is on the axis.

---

### **Step 4: Conclude $ BF = CF $**

Since $ F $ lies on the altitude from $ A $, which is the axis of symmetry of the triangle, the distances from $ F $ to $ B $ and $ C $ are equal. Thus:
$$
BF = CF.
$$

---

### **Final Answer**

$$
\boxed{BF = CF}
$$<|im_end|>

Grade: {"valid": false, "method": "synthetic", "note": "Correct reflection proof is accompanied by an unretracted SSS congruence assertion about the degenerate triples ABD and ACE.", "repairable": true}

## C08 sample 1

Solve the new problem with concise, justified steps. When using similarity, keep the vertex correspondence explicit. Check the assumptions of each theorem. Do not specialize a general figure without justifying that the requested quantity is preserved. Prefer a short geometric explanation when it is available; any valid method remains allowed. Finish once the proof is complete.

Here are four examples of the desired mathematical care; they are not hints to the new problem.

Example problem: Triangles ABC and DEF satisfy AB=6, AC=9, DE=10, DF=15 and angle BAC=EDF. Find BC/EF, with justification.
Example answer: AB/DE=AC/DF=3/5, and the included angles at A,D are equal. Thus SAS similarity gives A-D, B-E, C-F. In particular BC/EF=3/5.

Example problem: Distinct points A,B,C,D lie on a circle in that cyclic order. Given angle ABD=32 degrees, find angle ACD.
Example answer: B and C are on the same arc from A to D. The inscribed angles ABD and ACD therefore subtend the same opposite arc AD, so they are equal. Thus angle ACD=32 degrees.

Example problem: In triangle ABC, the perpendicular from A to BC meets the interior of BC at D. Given AB=13, BD=5 and DC=9, find AC.
Example answer: Triangle ADB is right at D, so AD^2=AB^2-BD^2=169-25=144. In right triangle ADC, AC^2=AD^2+DC^2=144+81=225. Therefore AC=15.

Example problem: A convex quadrilateral has diagonals which bisect each other. Must it be a rectangle? Give a proof or explicit counterexample.
Example answer: No. Take A=(0,0), B=(2,0), C=(3,1), D=(1,1). This is a convex parallelogram, and both diagonals have midpoint (3/2,1/2). But AB=(2,0) and AD=(1,1) have dot product 2, not 0. Thus angle BAD is not right and the quadrilateral is not a rectangle.

New problem:
In an isosceles triangle ABC with AB=AC, D is strictly inside AB and E is strictly inside AC, with BD=CE. Let F be the intersection of BE and CD. Prove BF=CF.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 3341; finish: stop.



To prove that $ BF = CF $ in the given isosceles triangle $ ABC $ with $ AB = AC $, where $ D $ lies strictly inside $ AB $, $ E $ strictly inside $ AC $, and $ BD = CE $, and $ F $ is the intersection of $ BE $ and $ CD $, we proceed with a geometric argument based on symmetry and congruence.

---

### Step 1: Establish Symmetry

Since $ AB = AC $, triangle $ ABC $ is isosceles, and the altitude from $ A $ to $ BC $ (say, $ AM $) is also the median and angle bisector. This line $ AM $ is the axis of symmetry of the triangle.

Let $ D $ lie on $ AB $ and $ E $ lie on $ AC $ such that $ BD = CE $. Then, since $ AB = AC $, we have:

$$
AD = AB - BD = AC - CE = AE
$$

Hence, $ AD = AE $, and triangle $ ADE $ is isosceles with $ AD = AE $.

---

### Step 2: Use Reflection Symmetry

The triangle is symmetric about the axis $ AM $, and since $ AD = AE $, the point $ D $ on $ AB $ is the reflection of $ E $ on $ AC $ across $ AM $. Thus, the line $ BE $ is the reflection of the line $ CD $ over the axis $ AM $.

Therefore, the intersection point $ F $ of lines $ BE $ and $ CD $ lies on the axis of symmetry $ AM $, because the reflection of a line over an axis intersects the axis at the same point.

---

### Step 3: Conclude $ BF = CF $

Since point $ F $ lies on the axis of symmetry $ AM $, and the triangle is symmetric about this line, the distances from $ F $ to $ B $ and $ C $ must be equal. Thus:

$$
BF = CF
$$

---

### Final Conclusion

$$
\boxed{BF = CF}
$$<|im_end|>

Grade: {"valid": true, "method": "synthetic", "note": "Correct reflection fixes F on perpendicular bisector.", "repairable": false}

## C09 sample 0

Solve the new problem with concise, justified steps. When using similarity, keep the vertex correspondence explicit. Check the assumptions of each theorem. Do not specialize a general figure without justifying that the requested quantity is preserved. Prefer a short geometric explanation when it is available; any valid method remains allowed. Finish once the proof is complete.

Here are four examples of the desired mathematical care; they are not hints to the new problem.

Example problem: Triangles ABC and DEF satisfy AB=6, AC=9, DE=10, DF=15 and angle BAC=EDF. Find BC/EF, with justification.
Example answer: AB/DE=AC/DF=3/5, and the included angles at A,D are equal. Thus SAS similarity gives A-D, B-E, C-F. In particular BC/EF=3/5.

Example problem: Distinct points A,B,C,D lie on a circle in that cyclic order. Given angle ABD=32 degrees, find angle ACD.
Example answer: B and C are on the same arc from A to D. The inscribed angles ABD and ACD therefore subtend the same opposite arc AD, so they are equal. Thus angle ACD=32 degrees.

Example problem: In triangle ABC, the perpendicular from A to BC meets the interior of BC at D. Given AB=13, BD=5 and DC=9, find AC.
Example answer: Triangle ADB is right at D, so AD^2=AB^2-BD^2=169-25=144. In right triangle ADC, AC^2=AD^2+DC^2=144+81=225. Therefore AC=15.

Example problem: A convex quadrilateral has diagonals which bisect each other. Must it be a rectangle? Give a proof or explicit counterexample.
Example answer: No. Take A=(0,0), B=(2,0), C=(3,1), D=(1,1). This is a convex parallelogram, and both diagonals have midpoint (3/2,1/2). But AB=(2,0) and AD=(1,1) have dot product 2, not 0. Thus angle BAD is not right and the quadrilateral is not a rectangle.

New problem:
The diagonals of a convex quadrilateral ABCD are perpendicular. Prove AB^2+CD^2=BC^2+DA^2.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 2086; finish: stop.



To prove that in a convex quadrilateral $ABCD$ with perpendicular diagonals, the equation $AB^2 + CD^2 = BC^2 + DA^2$ holds, we proceed as follows:

---

### **Step 1: Use the Right Triangles Formed by the Diagonals**

Let the diagonals $AC$ and $BD$ intersect at point $O$, which is inside the convex quadrilateral (a property of convex quadrilaterals). Since the diagonals are perpendicular, the four triangles $AOB$, $BOC$, $COD$, and $DOA$ are all right triangles.

---

### **Step 2: Apply the Pythagorean Theorem to Each Right Triangle**

We apply the Pythagorean Theorem to each triangle:

- In $\triangle AOB$:  
  $$
  AB^2 = AO^2 + BO^2
  $$

- In $\triangle BOC$:  
  $$
  BC^2 = BO^2 + CO^2
  $$

- In $\triangle COD$:  
  $$
  CD^2 = CO^2 + DO^2
  $$

- In $\triangle DOA$:  
  $$
  DA^2 = DO^2 + AO^2
  $$

---

### **Step 3: Add the Equations for Opposite Sides**

Now, consider the sum $AB^2 + CD^2$:

$$
AB^2 + CD^2 = (AO^2 + BO^2) + (CO^2 + DO^2)
$$

Similarly, consider the sum $BC^2 + DA^2$:

$$
BC^2 + DA^2 = (BO^2 + CO^2) + (DO^2 + AO^2)
$$

Both expressions are equal:

$$
AB^2 + CD^2 = BC^2 + DA^2 = AO^2 + BO^2 + CO^2 + DO^2
$$

---

### **Conclusion**

Since the diagonals are perpendicular, the right triangles formed at the intersection have their legs aligned with the segments of the diagonals, and the Pythagorean Theorem applies. The sum of the squares of the opposite sides is preserved and equal due to the symmetry in the decomposition of the square of the diagonals.

---

### **Final Answer**

$$
\boxed{AB^2 + CD^2 = BC^2 + DA^2}
$$<|im_end|>

Grade: {"valid": true, "method": "synthetic", "note": "Four correct Pythagorean identities.", "repairable": false}

## C09 sample 1

Solve the new problem with concise, justified steps. When using similarity, keep the vertex correspondence explicit. Check the assumptions of each theorem. Do not specialize a general figure without justifying that the requested quantity is preserved. Prefer a short geometric explanation when it is available; any valid method remains allowed. Finish once the proof is complete.

Here are four examples of the desired mathematical care; they are not hints to the new problem.

Example problem: Triangles ABC and DEF satisfy AB=6, AC=9, DE=10, DF=15 and angle BAC=EDF. Find BC/EF, with justification.
Example answer: AB/DE=AC/DF=3/5, and the included angles at A,D are equal. Thus SAS similarity gives A-D, B-E, C-F. In particular BC/EF=3/5.

Example problem: Distinct points A,B,C,D lie on a circle in that cyclic order. Given angle ABD=32 degrees, find angle ACD.
Example answer: B and C are on the same arc from A to D. The inscribed angles ABD and ACD therefore subtend the same opposite arc AD, so they are equal. Thus angle ACD=32 degrees.

Example problem: In triangle ABC, the perpendicular from A to BC meets the interior of BC at D. Given AB=13, BD=5 and DC=9, find AC.
Example answer: Triangle ADB is right at D, so AD^2=AB^2-BD^2=169-25=144. In right triangle ADC, AC^2=AD^2+DC^2=144+81=225. Therefore AC=15.

Example problem: A convex quadrilateral has diagonals which bisect each other. Must it be a rectangle? Give a proof or explicit counterexample.
Example answer: No. Take A=(0,0), B=(2,0), C=(3,1), D=(1,1). This is a convex parallelogram, and both diagonals have midpoint (3/2,1/2). But AB=(2,0) and AD=(1,1) have dot product 2, not 0. Thus angle BAD is not right and the quadrilateral is not a rectangle.

New problem:
The diagonals of a convex quadrilateral ABCD are perpendicular. Prove AB^2+CD^2=BC^2+DA^2.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 2355; finish: stop.



To prove that in a convex quadrilateral $ABCD$ with perpendicular diagonals, the equality $AB^2 + CD^2 = BC^2 + DA^2$ holds, we use the geometric decomposition of the quadrilateral into right triangles formed by the diagonals.

---

### **Step 1: Decompose the quadrilateral into right triangles**

Let the diagonals $AC$ and $BD$ intersect at point $O$, forming four right triangles:

- $\triangle AOB$ with right angle at $O$
- $\triangle BOC$ with right angle at $O$
- $\triangle COD$ with right angle at $O$
- $\triangle DOA$ with right angle at $O$

Since the diagonals are perpendicular, each of these triangles is a right triangle.

---

### **Step 2: Apply the Pythagorean Theorem**

Let the segments of the diagonals be:

- $AO = a$, $OC = c$, $BO = b$, $OD = d$

Using the Pythagorean Theorem in each triangle:

- $AB^2 = AO^2 + BO^2 = a^2 + b^2$
- $BC^2 = BO^2 + OC^2 = b^2 + c^2$
- $CD^2 = OC^2 + OD^2 = c^2 + d^2$
- $DA^2 = OD^2 + AO^2 = d^2 + a^2$

---

### **Step 3: Compute the sums of squares of opposite sides**

Now compute:

- $AB^2 + CD^2 = (a^2 + b^2) + (c^2 + d^2) = a^2 + b^2 + c^2 + d^2$
- $BC^2 + DA^2 = (b^2 + c^2) + (d^2 + a^2) = a^2 + b^2 + c^2 + d^2$

Thus, both expressions are equal.

---

### **Conclusion**

Since the diagonals are perpendicular, the decomposition into right triangles ensures that the sum of the squares of the sides $AB^2 + CD^2$ and $BC^2 + DA^2$ are both equal to the sum of the squares of all four diagonal segments. Therefore, the equality holds for any convex quadrilateral with perpendicular diagonals.

$$
\boxed{AB^2 + CD^2 = BC^2 + DA^2}
$$<|im_end|>

Grade: {"valid": true, "method": "synthetic", "note": "Four correct Pythagorean identities.", "repairable": false}

## C10 sample 0

Solve the new problem with concise, justified steps. When using similarity, keep the vertex correspondence explicit. Check the assumptions of each theorem. Do not specialize a general figure without justifying that the requested quantity is preserved. Prefer a short geometric explanation when it is available; any valid method remains allowed. Finish once the proof is complete.

Here are four examples of the desired mathematical care; they are not hints to the new problem.

Example problem: Triangles ABC and DEF satisfy AB=6, AC=9, DE=10, DF=15 and angle BAC=EDF. Find BC/EF, with justification.
Example answer: AB/DE=AC/DF=3/5, and the included angles at A,D are equal. Thus SAS similarity gives A-D, B-E, C-F. In particular BC/EF=3/5.

Example problem: Distinct points A,B,C,D lie on a circle in that cyclic order. Given angle ABD=32 degrees, find angle ACD.
Example answer: B and C are on the same arc from A to D. The inscribed angles ABD and ACD therefore subtend the same opposite arc AD, so they are equal. Thus angle ACD=32 degrees.

Example problem: In triangle ABC, the perpendicular from A to BC meets the interior of BC at D. Given AB=13, BD=5 and DC=9, find AC.
Example answer: Triangle ADB is right at D, so AD^2=AB^2-BD^2=169-25=144. In right triangle ADC, AC^2=AD^2+DC^2=144+81=225. Therefore AC=15.

Example problem: A convex quadrilateral has diagonals which bisect each other. Must it be a rectangle? Give a proof or explicit counterexample.
Example answer: No. Take A=(0,0), B=(2,0), C=(3,1), D=(1,1). This is a convex parallelogram, and both diagonals have midpoint (3/2,1/2). But AB=(2,0) and AD=(1,1) have dot product 2, not 0. Thus angle BAD is not right and the quadrilateral is not a rectangle.

New problem:
ABC is a triangle with incenter I. D is the midpoint of the arc BC of its circumcircle that does not contain A. Prove DB=DC=DI.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 8192; finish: length.

[No completed final answer; raw generation retained in the source JSON.]

Grade: {"valid": false, "method": "none", "note": "Output limit reached without completed final proof.", "repairable": false}

## C10 sample 1

Solve the new problem with concise, justified steps. When using similarity, keep the vertex correspondence explicit. Check the assumptions of each theorem. Do not specialize a general figure without justifying that the requested quantity is preserved. Prefer a short geometric explanation when it is available; any valid method remains allowed. Finish once the proof is complete.

Here are four examples of the desired mathematical care; they are not hints to the new problem.

Example problem: Triangles ABC and DEF satisfy AB=6, AC=9, DE=10, DF=15 and angle BAC=EDF. Find BC/EF, with justification.
Example answer: AB/DE=AC/DF=3/5, and the included angles at A,D are equal. Thus SAS similarity gives A-D, B-E, C-F. In particular BC/EF=3/5.

Example problem: Distinct points A,B,C,D lie on a circle in that cyclic order. Given angle ABD=32 degrees, find angle ACD.
Example answer: B and C are on the same arc from A to D. The inscribed angles ABD and ACD therefore subtend the same opposite arc AD, so they are equal. Thus angle ACD=32 degrees.

Example problem: In triangle ABC, the perpendicular from A to BC meets the interior of BC at D. Given AB=13, BD=5 and DC=9, find AC.
Example answer: Triangle ADB is right at D, so AD^2=AB^2-BD^2=169-25=144. In right triangle ADC, AC^2=AD^2+DC^2=144+81=225. Therefore AC=15.

Example problem: A convex quadrilateral has diagonals which bisect each other. Must it be a rectangle? Give a proof or explicit counterexample.
Example answer: No. Take A=(0,0), B=(2,0), C=(3,1), D=(1,1). This is a convex parallelogram, and both diagonals have midpoint (3/2,1/2). But AB=(2,0) and AD=(1,1) have dot product 2, not 0. Thus angle BAD is not right and the quadrilateral is not a rectangle.

New problem:
ABC is a triangle with incenter I. D is the midpoint of the arc BC of its circumcircle that does not contain A. Prove DB=DC=DI.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 8192; finish: length.

[No completed final answer; raw generation retained in the source JSON.]

Grade: {"valid": false, "method": "none", "note": "Output limit reached without completed final proof.", "repairable": false}

## C11 sample 0

Solve the new problem with concise, justified steps. When using similarity, keep the vertex correspondence explicit. Check the assumptions of each theorem. Do not specialize a general figure without justifying that the requested quantity is preserved. Prefer a short geometric explanation when it is available; any valid method remains allowed. Finish once the proof is complete.

Here are four examples of the desired mathematical care; they are not hints to the new problem.

Example problem: Triangles ABC and DEF satisfy AB=6, AC=9, DE=10, DF=15 and angle BAC=EDF. Find BC/EF, with justification.
Example answer: AB/DE=AC/DF=3/5, and the included angles at A,D are equal. Thus SAS similarity gives A-D, B-E, C-F. In particular BC/EF=3/5.

Example problem: Distinct points A,B,C,D lie on a circle in that cyclic order. Given angle ABD=32 degrees, find angle ACD.
Example answer: B and C are on the same arc from A to D. The inscribed angles ABD and ACD therefore subtend the same opposite arc AD, so they are equal. Thus angle ACD=32 degrees.

Example problem: In triangle ABC, the perpendicular from A to BC meets the interior of BC at D. Given AB=13, BD=5 and DC=9, find AC.
Example answer: Triangle ADB is right at D, so AD^2=AB^2-BD^2=169-25=144. In right triangle ADC, AC^2=AD^2+DC^2=144+81=225. Therefore AC=15.

Example problem: A convex quadrilateral has diagonals which bisect each other. Must it be a rectangle? Give a proof or explicit counterexample.
Example answer: No. Take A=(0,0), B=(2,0), C=(3,1), D=(1,1). This is a convex parallelogram, and both diagonals have midpoint (3/2,1/2). But AB=(2,0) and AD=(1,1) have dot product 2, not 0. Thus angle BAD is not right and the quadrilateral is not a rectangle.

New problem:
Triangle ABC is right-angled at A. D is the midpoint of BC. The perpendicular from D to AC meets AC at E. Prove AE=EC and DE=AB/2.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 3369; finish: stop.



To solve the problem, we analyze the geometric configuration and use known properties of triangles and midlines.

---

### Step 1: Define Key Points and Relationships

- Triangle $ ABC $ is right-angled at $ A $, so $ \angle A = 90^\circ $.
- $ D $ is the **midpoint** of $ BC $, so $ BD = DC $.
- A **perpendicular** is dropped from $ D $ to $ AC $, meeting $ AC $ at point $ E $.
- We are to prove:
  - $ AE = EC $
  - $ DE = \frac{AB}{2} $

---

### Step 2: Use the Midline Theorem

Let $ M $ be the **midpoint** of $ AC $. Then, the segment $ DM $ connects the midpoints of two sides of triangle $ ABC $: $ D $ (midpoint of $ BC $) and $ M $ (midpoint of $ AC $).

By the **Midline Theorem**:
- $ DM $ is **parallel** to $ AB $, and
- $ DM = \frac{1}{2} AB $

Since $ AB \perp AC $, and $ DM \parallel AB $, it follows that $ DM \perp AC $.

Therefore, the **perpendicular from $ D $ to $ AC $** must be the segment $ DM $, and the foot of this perpendicular is point $ M $, the midpoint of $ AC $.

Thus, $ E = M $, the midpoint of $ AC $, so:
- $ AE = EC $
- $ DE = DM = \frac{1}{2} AB $

---

### Step 3: Final Conclusion

- $ AE = EC $ because $ E $ is the midpoint of $ AC $.
- $ DE = \frac{AB}{2} $ because $ DE = DM $, and $ DM = \frac{1}{2} AB $ by the midline theorem.

---

### Final Answer

$$
\boxed{AE = EC} \quad \text{and} \quad \boxed{DE = \dfrac{AB}{2}}
$$<|im_end|>

Grade: {"valid": true, "method": "synthetic", "note": "Midpoint theorem and uniqueness of perpendicular / isosceles right-hypotenuse property plus Pythagoras.", "repairable": false}

## C11 sample 1

Solve the new problem with concise, justified steps. When using similarity, keep the vertex correspondence explicit. Check the assumptions of each theorem. Do not specialize a general figure without justifying that the requested quantity is preserved. Prefer a short geometric explanation when it is available; any valid method remains allowed. Finish once the proof is complete.

Here are four examples of the desired mathematical care; they are not hints to the new problem.

Example problem: Triangles ABC and DEF satisfy AB=6, AC=9, DE=10, DF=15 and angle BAC=EDF. Find BC/EF, with justification.
Example answer: AB/DE=AC/DF=3/5, and the included angles at A,D are equal. Thus SAS similarity gives A-D, B-E, C-F. In particular BC/EF=3/5.

Example problem: Distinct points A,B,C,D lie on a circle in that cyclic order. Given angle ABD=32 degrees, find angle ACD.
Example answer: B and C are on the same arc from A to D. The inscribed angles ABD and ACD therefore subtend the same opposite arc AD, so they are equal. Thus angle ACD=32 degrees.

Example problem: In triangle ABC, the perpendicular from A to BC meets the interior of BC at D. Given AB=13, BD=5 and DC=9, find AC.
Example answer: Triangle ADB is right at D, so AD^2=AB^2-BD^2=169-25=144. In right triangle ADC, AC^2=AD^2+DC^2=144+81=225. Therefore AC=15.

Example problem: A convex quadrilateral has diagonals which bisect each other. Must it be a rectangle? Give a proof or explicit counterexample.
Example answer: No. Take A=(0,0), B=(2,0), C=(3,1), D=(1,1). This is a convex parallelogram, and both diagonals have midpoint (3/2,1/2). But AB=(2,0) and AD=(1,1) have dot product 2, not 0. Thus angle BAD is not right and the quadrilateral is not a rectangle.

New problem:
Triangle ABC is right-angled at A. D is the midpoint of BC. The perpendicular from D to AC meets AC at E. Prove AE=EC and DE=AB/2.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 3943; finish: stop.



To solve the problem, we analyze the geometric configuration of triangle $ \triangle ABC $, which is right-angled at $ A $. Point $ D $ is the midpoint of hypotenuse $ BC $, and the perpendicular from $ D $ to $ AC $ meets $ AC $ at point $ E $. We are to prove that $ AE = EC $ and $ DE = \frac{AB}{2} $.

---

### Step 1: Use the property of medians in right triangles

In any right triangle, the median from the right angle to the hypotenuse is equal to half the hypotenuse. Since $ \triangle ABC $ is right-angled at $ A $, the median from $ A $ to hypotenuse $ BC $ is $ AD $, and we have:

$$
AD = \frac{BC}{2}
$$

But since $ D $ is the midpoint of $ BC $, we also have:

$$
BD = DC = \frac{BC}{2}
$$

Thus, $ AD = DC $, so triangle $ \triangle ADC $ is **isosceles** with $ AD = DC $.

---

### Step 2: Use isosceles triangle properties

Since triangle $ \triangle ADC $ is isosceles with $ AD = DC $, the **altitude** from $ D $ to base $ AC $ (i.e., the segment $ DE $) is also the **median** and **angle bisector** of $ \triangle ADC $. Therefore, $ E $ is the **midpoint** of $ AC $, so:

$$
AE = EC
$$

---

### Step 3: Compute $ DE $ using the Pythagorean Theorem

In right triangle $ \triangle ADE $, we have:

$$
AD^2 = AE^2 + DE^2
$$

We already know that:

- $ AD = \frac{BC}{2} $
- $ AE = \frac{AC}{2} $

Let $ AB = c $, $ AC = b $, and $ BC = \sqrt{b^2 + c^2} $. Then:

$$
AD = \frac{\sqrt{b^2 + c^2}}{2}, \quad AE = \frac{b}{2}
$$

Substitute into the Pythagorean equation:

$$
\left( \frac{\sqrt{b^2 + c^2}}{2} \right)^2 = \left( \frac{b}{2} \right)^2 + DE^2
$$

$$
\frac{b^2 + c^2}{4} = \frac{b^2}{4} + DE^2
$$

$$
DE^2 = \frac{c^2}{4} \Rightarrow DE = \frac{c}{2} = \frac{AB}{2}
$$

---

### Conclusion

We have shown that:

- $ E $ is the midpoint of $ AC $, so $ AE = EC $
- $ DE = \frac{AB}{2} $

Thus, the final result is:

$$
\boxed{AE = EC} \quad \text{and} \quad \boxed{DE = \dfrac{AB}{2}}
$$<|im_end|>

Grade: {"valid": true, "method": "synthetic", "note": "Midpoint theorem and uniqueness of perpendicular / isosceles right-hypotenuse property plus Pythagoras.", "repairable": false}

## C12 sample 0

Solve the new problem with concise, justified steps. When using similarity, keep the vertex correspondence explicit. Check the assumptions of each theorem. Do not specialize a general figure without justifying that the requested quantity is preserved. Prefer a short geometric explanation when it is available; any valid method remains allowed. Finish once the proof is complete.

Here are four examples of the desired mathematical care; they are not hints to the new problem.

Example problem: Triangles ABC and DEF satisfy AB=6, AC=9, DE=10, DF=15 and angle BAC=EDF. Find BC/EF, with justification.
Example answer: AB/DE=AC/DF=3/5, and the included angles at A,D are equal. Thus SAS similarity gives A-D, B-E, C-F. In particular BC/EF=3/5.

Example problem: Distinct points A,B,C,D lie on a circle in that cyclic order. Given angle ABD=32 degrees, find angle ACD.
Example answer: B and C are on the same arc from A to D. The inscribed angles ABD and ACD therefore subtend the same opposite arc AD, so they are equal. Thus angle ACD=32 degrees.

Example problem: In triangle ABC, the perpendicular from A to BC meets the interior of BC at D. Given AB=13, BD=5 and DC=9, find AC.
Example answer: Triangle ADB is right at D, so AD^2=AB^2-BD^2=169-25=144. In right triangle ADC, AC^2=AD^2+DC^2=144+81=225. Therefore AC=15.

Example problem: A convex quadrilateral has diagonals which bisect each other. Must it be a rectangle? Give a proof or explicit counterexample.
Example answer: No. Take A=(0,0), B=(2,0), C=(3,1), D=(1,1). This is a convex parallelogram, and both diagonals have midpoint (3/2,1/2). But AB=(2,0) and AD=(1,1) have dot product 2, not 0. Thus angle BAD is not right and the quadrilateral is not a rectangle.

New problem:
Two distinct circles intersect at A and B. The point diametrically opposite A on the first circle is C, and the point diametrically opposite A on the second is D. Assume C,D are different from B. Prove B,C,D are collinear.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 4688; finish: stop.



To prove that points $ B $, $ C $, and $ D $ are collinear, we begin by analyzing the geometric configuration of the two intersecting circles and the roles of points $ C $ and $ D $.

---

### Step 1: Use of Thales’ Theorem

- Point $ C $ is the **diametrically opposite** point to $ A $ on the **first circle**. That means $ AC $ is a **diameter** of the first circle.
- Similarly, point $ D $ is the **diametrically opposite** point to $ A $ on the **second circle**, so $ AD $ is a **diameter** of the second circle.

By **Thales’ Theorem**, any triangle inscribed in a circle with one side being a diameter will have a right angle at the third vertex. Since point $ B $ lies on both circles, it lies on the first circle and is not equal to $ A $ or $ C $, and similarly on the second circle and is not equal to $ A $ or $ D $.

- Therefore, in triangle $ ABC $, since $ AC $ is a diameter, $ \angle ABC = 90^\circ $.
- In triangle $ ABD $, since $ AD $ is a diameter, $ \angle ABD = 90^\circ $.

---

### Step 2: Perpendicularity Implies Collinearity

- From the above, both $ \angle ABC $ and $ \angle ABD $ are right angles.
- This implies that **line $ BC $** is perpendicular to $ AB $, and **line $ BD $** is also perpendicular to $ AB $.
- If two distinct lines are both perpendicular to the same line, they must be **parallel** to each other.
- However, since both $ C $ and $ D $ lie on the same side of $ AB $ (as the diametrically opposite points are on the opposite side of the circle from $ A $), and both $ BC $ and $ BD $ are perpendicular to $ AB $, they must be the **same line**.

Therefore, $ C $, $ B $, and $ D $ lie on the same line, and hence are **collinear**.

---

### Final Conclusion

By applying Thales’ Theorem and analyzing the geometric implications of perpendicularity, we conclude that the three points $ B $, $ C $, and $ D $ lie on a single straight line.

$$
\boxed{B, C, D \text{ are collinear}}
$$<|im_end|>

Grade: {"valid": false, "method": "synthetic", "note": "Correct perpendicular idea, but core conclusion also relies on the false claim that C and D must be on the same side of AB.", "repairable": true}

## C12 sample 1

Solve the new problem with concise, justified steps. When using similarity, keep the vertex correspondence explicit. Check the assumptions of each theorem. Do not specialize a general figure without justifying that the requested quantity is preserved. Prefer a short geometric explanation when it is available; any valid method remains allowed. Finish once the proof is complete.

Here are four examples of the desired mathematical care; they are not hints to the new problem.

Example problem: Triangles ABC and DEF satisfy AB=6, AC=9, DE=10, DF=15 and angle BAC=EDF. Find BC/EF, with justification.
Example answer: AB/DE=AC/DF=3/5, and the included angles at A,D are equal. Thus SAS similarity gives A-D, B-E, C-F. In particular BC/EF=3/5.

Example problem: Distinct points A,B,C,D lie on a circle in that cyclic order. Given angle ABD=32 degrees, find angle ACD.
Example answer: B and C are on the same arc from A to D. The inscribed angles ABD and ACD therefore subtend the same opposite arc AD, so they are equal. Thus angle ACD=32 degrees.

Example problem: In triangle ABC, the perpendicular from A to BC meets the interior of BC at D. Given AB=13, BD=5 and DC=9, find AC.
Example answer: Triangle ADB is right at D, so AD^2=AB^2-BD^2=169-25=144. In right triangle ADC, AC^2=AD^2+DC^2=144+81=225. Therefore AC=15.

Example problem: A convex quadrilateral has diagonals which bisect each other. Must it be a rectangle? Give a proof or explicit counterexample.
Example answer: No. Take A=(0,0), B=(2,0), C=(3,1), D=(1,1). This is a convex parallelogram, and both diagonals have midpoint (3/2,1/2). But AB=(2,0) and AD=(1,1) have dot product 2, not 0. Thus angle BAD is not right and the quadrilateral is not a rectangle.

New problem:
Two distinct circles intersect at A and B. The point diametrically opposite A on the first circle is C, and the point diametrically opposite A on the second is D. Assume C,D are different from B. Prove B,C,D are collinear.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 1701; finish: stop.



To prove that points $ B, C, D $ are collinear, we proceed as follows:

---

### **Step 1: Use Thales' Theorem**

We are given two distinct circles intersecting at points $ A $ and $ B $. Let the first circle have center $ O_1 $, and the second have center $ O_2 $. Since point $ C $ is diametrically opposite $ A $ on the first circle, the line segment $ AC $ is a **diameter** of the first circle. Similarly, $ AD $ is a **diameter** of the second circle.

By **Thales' Theorem**, any triangle inscribed in a circle where one side is a diameter has a right angle at the third point. Therefore:

- In the first circle, since $ AC $ is a diameter and $ B $ lies on the circle, $ \angle ABC = 90^\circ $.
- In the second circle, since $ AD $ is a diameter and $ B $ lies on the circle, $ \angle ABD = 90^\circ $.

---

### **Step 2: Analyze the Geometry of the Angles**

We now have:

- $ \angle ABC = 90^\circ $, so $ BC \perp AB $.
- $ \angle ABD = 90^\circ $, so $ BD \perp AB $.

Thus, both $ BC $ and $ BD $ are **perpendicular to the same line** $ AB $, which implies that $ BC $ and $ BD $ are **collinear**.

---

### **Step 3: Conclude Collinearity of $ B, C, D $**

Since both $ C $ and $ D $ lie on the same line that is perpendicular to $ AB $ at point $ B $, and since $ B $ is the common point, it follows that:

- Points $ B $, $ C $, and $ D $ all lie on the same line.

---

### **Final Conclusion**

$$
\boxed{B, C, D \text{ are collinear}}
$$<|im_end|>

Grade: {"valid": true, "method": "synthetic", "note": "Correct diameter-angle and common perpendicular argument.", "repairable": false}

## C13 sample 0

Solve the new problem with concise, justified steps. When using similarity, keep the vertex correspondence explicit. Check the assumptions of each theorem. Do not specialize a general figure without justifying that the requested quantity is preserved. Prefer a short geometric explanation when it is available; any valid method remains allowed. Finish once the proof is complete.

Here are four examples of the desired mathematical care; they are not hints to the new problem.

Example problem: Triangles ABC and DEF satisfy AB=6, AC=9, DE=10, DF=15 and angle BAC=EDF. Find BC/EF, with justification.
Example answer: AB/DE=AC/DF=3/5, and the included angles at A,D are equal. Thus SAS similarity gives A-D, B-E, C-F. In particular BC/EF=3/5.

Example problem: Distinct points A,B,C,D lie on a circle in that cyclic order. Given angle ABD=32 degrees, find angle ACD.
Example answer: B and C are on the same arc from A to D. The inscribed angles ABD and ACD therefore subtend the same opposite arc AD, so they are equal. Thus angle ACD=32 degrees.

Example problem: In triangle ABC, the perpendicular from A to BC meets the interior of BC at D. Given AB=13, BD=5 and DC=9, find AC.
Example answer: Triangle ADB is right at D, so AD^2=AB^2-BD^2=169-25=144. In right triangle ADC, AC^2=AD^2+DC^2=144+81=225. Therefore AC=15.

Example problem: A convex quadrilateral has diagonals which bisect each other. Must it be a rectangle? Give a proof or explicit counterexample.
Example answer: No. Take A=(0,0), B=(2,0), C=(3,1), D=(1,1). This is a convex parallelogram, and both diagonals have midpoint (3/2,1/2). But AB=(2,0) and AD=(1,1) have dot product 2, not 0. Thus angle BAD is not right and the quadrilateral is not a rectangle.

New problem:
D and E are the midpoints of BC and CA in triangle ABC. The medians AD and BE meet at G. Prove AG=2GD.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 4102; finish: stop.



To prove that $ AG = 2GD $ in triangle $ ABC $, where $ D $ and $ E $ are midpoints of $ BC $ and $ CA $, and $ G $ is the intersection of medians $ AD $ and $ BE $, we proceed as follows:

---

### **Step 1: Establish Key Properties**
- Since $ D $ and $ E $ are midpoints, we have:
  $$
  BD = DC, \quad AE = EC
  $$
- The segment $ ED $ connects midpoints of $ AC $ and $ BC $, so by the **midline theorem**, $ ED \parallel AB $ and $ ED = \frac{1}{2}AB $.

---

### **Step 2: Apply Similarity via Corresponding Angles**
- Since $ ED \parallel AB $, the transversal $ GE $ creates corresponding angles:
  $$
  \angle GED = \angle GAB, \quad \angle GDE = \angle GBA
  $$
- Therefore, triangles $ \triangle GDE $ and $ \triangle GAB $ are similar by the **AA similarity criterion**:
  $$
  \triangle GDE \sim \triangle GAB
  $$

---

### **Step 3: Use the Ratio of Corresponding Sides**
- From the similarity, the ratio of corresponding sides is:
  $$
  \frac{GD}{GA} = \frac{ED}{AB} = \frac{1}{2}
  $$
- Solving for $ GA $, we find:
  $$
  GA = 2GD
  $$

---

### **Conclusion**
Thus, the centroid $ G $ divides the median $ AD $ in the ratio $ 2:1 $, i.e.,  
$$
\boxed{AG = 2GD}
$$<|im_end|>

Grade: {"valid": false, "method": "synthetic", "note": "Angle correspondences GED/GAB and GDE/GBA are reversed. Intended midpoint similarity and final ratio are repairable.", "repairable": true}

## C13 sample 1

Solve the new problem with concise, justified steps. When using similarity, keep the vertex correspondence explicit. Check the assumptions of each theorem. Do not specialize a general figure without justifying that the requested quantity is preserved. Prefer a short geometric explanation when it is available; any valid method remains allowed. Finish once the proof is complete.

Here are four examples of the desired mathematical care; they are not hints to the new problem.

Example problem: Triangles ABC and DEF satisfy AB=6, AC=9, DE=10, DF=15 and angle BAC=EDF. Find BC/EF, with justification.
Example answer: AB/DE=AC/DF=3/5, and the included angles at A,D are equal. Thus SAS similarity gives A-D, B-E, C-F. In particular BC/EF=3/5.

Example problem: Distinct points A,B,C,D lie on a circle in that cyclic order. Given angle ABD=32 degrees, find angle ACD.
Example answer: B and C are on the same arc from A to D. The inscribed angles ABD and ACD therefore subtend the same opposite arc AD, so they are equal. Thus angle ACD=32 degrees.

Example problem: In triangle ABC, the perpendicular from A to BC meets the interior of BC at D. Given AB=13, BD=5 and DC=9, find AC.
Example answer: Triangle ADB is right at D, so AD^2=AB^2-BD^2=169-25=144. In right triangle ADC, AC^2=AD^2+DC^2=144+81=225. Therefore AC=15.

Example problem: A convex quadrilateral has diagonals which bisect each other. Must it be a rectangle? Give a proof or explicit counterexample.
Example answer: No. Take A=(0,0), B=(2,0), C=(3,1), D=(1,1). This is a convex parallelogram, and both diagonals have midpoint (3/2,1/2). But AB=(2,0) and AD=(1,1) have dot product 2, not 0. Thus angle BAD is not right and the quadrilateral is not a rectangle.

New problem:
D and E are the midpoints of BC and CA in triangle ABC. The medians AD and BE meet at G. Prove AG=2GD.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 4303; finish: stop.



To prove that in triangle $ ABC $, where $ D $ and $ E $ are the midpoints of $ BC $ and $ AC $, respectively, and the medians $ AD $ and $ BE $ intersect at $ G $, it follows that $ AG = 2 \cdot GD $, we use geometric similarity.

---

### Step 1: Use the Midline Theorem

Since $ D $ and $ E $ are midpoints of $ BC $ and $ AC $, respectively, the segment $ DE $ is the **midline** of triangle $ ABC $. By the **Midline Theorem**, this segment is **parallel to** side $ AB $ and is **half its length**:

$$
DE \parallel AB \quad \text{and} \quad DE = \frac{1}{2} AB
$$

---

### Step 2: Identify Similar Triangles

Let $ G $ be the intersection of the medians $ AD $ and $ BE $. Consider triangles $ \triangle GDE $ and $ \triangle GAB $.

- Since $ DE \parallel AB $, the corresponding angles $ \angle GDE $ and $ \angle GAB $ are equal (corresponding angles).
- Similarly, $ \angle GED $ and $ \angle GBA $ are equal (corresponding angles).

Thus, by **AA similarity**, we conclude:

$$
\triangle GDE \sim \triangle GAB
$$

---

### Step 3: Use the Ratio of Similarity

From the similarity of $ \triangle GDE $ and $ \triangle GAB $, the ratio of corresponding sides is equal to the ratio of $ DE $ to $ AB $:

$$
\frac{GD}{GA} = \frac{DE}{AB} = \frac{1}{2}
$$

This implies:

$$
GD = \frac{1}{2} GA \quad \Rightarrow \quad AG = 2 \cdot GD
$$

---

### Final Conclusion

Thus, the centroid $ G $ of triangle $ ABC $ divides the median $ AD $ in the ratio $ 2:1 $, with $ AG = 2 \cdot GD $.

$$
\boxed{2}
$$<|im_end|>

Grade: {"valid": true, "method": "synthetic", "note": "Correct midpoint similarity givesGD/GA=1/2.", "repairable": false}

## C14 sample 0

Solve the new problem with concise, justified steps. When using similarity, keep the vertex correspondence explicit. Check the assumptions of each theorem. Do not specialize a general figure without justifying that the requested quantity is preserved. Prefer a short geometric explanation when it is available; any valid method remains allowed. Finish once the proof is complete.

Here are four examples of the desired mathematical care; they are not hints to the new problem.

Example problem: Triangles ABC and DEF satisfy AB=6, AC=9, DE=10, DF=15 and angle BAC=EDF. Find BC/EF, with justification.
Example answer: AB/DE=AC/DF=3/5, and the included angles at A,D are equal. Thus SAS similarity gives A-D, B-E, C-F. In particular BC/EF=3/5.

Example problem: Distinct points A,B,C,D lie on a circle in that cyclic order. Given angle ABD=32 degrees, find angle ACD.
Example answer: B and C are on the same arc from A to D. The inscribed angles ABD and ACD therefore subtend the same opposite arc AD, so they are equal. Thus angle ACD=32 degrees.

Example problem: In triangle ABC, the perpendicular from A to BC meets the interior of BC at D. Given AB=13, BD=5 and DC=9, find AC.
Example answer: Triangle ADB is right at D, so AD^2=AB^2-BD^2=169-25=144. In right triangle ADC, AC^2=AD^2+DC^2=144+81=225. Therefore AC=15.

Example problem: A convex quadrilateral has diagonals which bisect each other. Must it be a rectangle? Give a proof or explicit counterexample.
Example answer: No. Take A=(0,0), B=(2,0), C=(3,1), D=(1,1). This is a convex parallelogram, and both diagonals have midpoint (3/2,1/2). But AB=(2,0) and AD=(1,1) have dot product 2, not 0. Thus angle BAD is not right and the quadrilateral is not a rectangle.

New problem:
A convex quadrilateral has equal diagonals. Must its four vertices lie on a circle? Prove the assertion or give an explicit counterexample.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 7425; finish: stop.



A convex quadrilateral with equal diagonals does **not** necessarily have its four vertices on a circle. Here's a concise, justified proof with a counterexample:

**Counterexample:**  
Consider the convex quadrilateral with vertices $ A(0,0) $, $ B(2,0) $, $ C(2,1) $, and $ D(1,2) $.  
- **Diagonals:**  
  - $ AC $: From $ (0,0) $ to $ (2,1) $, length $ \sqrt{(2)^2 + (1)^2} = \sqrt{5} $.  
  - $ BD $: From $ (2,0) $ to $ (1,2) $, length $ \sqrt{(1)^2 + (2)^2} = \sqrt{5} $.  
  - Thus, the diagonals are equal.  

- **Cyclic Check:**  
  Assume the four points lie on a circle $ x^2 + y^2 + Dx + Ey + F = 0 $.  
  - For $ A(0,0) $: $ F = 0 $.  
  - For $ B(2,0) $: $ 4 + 2D = 0 \Rightarrow D = -2 $.  
  - For $ C(2,1) $: $ 4 + 1 - 4 + E = 0 \Rightarrow E = -1 $.  
  - For $ D(1,2) $: $ 1 + 4 - 2 - 2 = 1 \neq 0 $.  
  - Hence, $ D $ does not lie on the circle defined by $ A, B, C $, proving the quadrilateral is **not cyclic**.  

**Conclusion:**  
A convex quadrilateral with equal diagonals is not guaranteed to be cyclic. The provided example demonstrates this explicitly.  

**Final Answer:**  
No, a convex quadrilateral with equal diagonals is not necessarily cyclic. A counterexample is the quadrilateral with vertices at $ (0,0) $, $ (2,0) $, $ (2,1) $, and $ (1,2) $, which has equal diagonals but is not cyclic.<|im_end|>

Grade: {"valid": true, "method": "analytic", "note": "A00 B20 C21 D12 is convex, diagonals sqrt5, fourth point fails circle equation.", "repairable": false}

## C14 sample 1

Solve the new problem with concise, justified steps. When using similarity, keep the vertex correspondence explicit. Check the assumptions of each theorem. Do not specialize a general figure without justifying that the requested quantity is preserved. Prefer a short geometric explanation when it is available; any valid method remains allowed. Finish once the proof is complete.

Here are four examples of the desired mathematical care; they are not hints to the new problem.

Example problem: Triangles ABC and DEF satisfy AB=6, AC=9, DE=10, DF=15 and angle BAC=EDF. Find BC/EF, with justification.
Example answer: AB/DE=AC/DF=3/5, and the included angles at A,D are equal. Thus SAS similarity gives A-D, B-E, C-F. In particular BC/EF=3/5.

Example problem: Distinct points A,B,C,D lie on a circle in that cyclic order. Given angle ABD=32 degrees, find angle ACD.
Example answer: B and C are on the same arc from A to D. The inscribed angles ABD and ACD therefore subtend the same opposite arc AD, so they are equal. Thus angle ACD=32 degrees.

Example problem: In triangle ABC, the perpendicular from A to BC meets the interior of BC at D. Given AB=13, BD=5 and DC=9, find AC.
Example answer: Triangle ADB is right at D, so AD^2=AB^2-BD^2=169-25=144. In right triangle ADC, AC^2=AD^2+DC^2=144+81=225. Therefore AC=15.

Example problem: A convex quadrilateral has diagonals which bisect each other. Must it be a rectangle? Give a proof or explicit counterexample.
Example answer: No. Take A=(0,0), B=(2,0), C=(3,1), D=(1,1). This is a convex parallelogram, and both diagonals have midpoint (3/2,1/2). But AB=(2,0) and AD=(1,1) have dot product 2, not 0. Thus angle BAD is not right and the quadrilateral is not a rectangle.

New problem:
A convex quadrilateral has equal diagonals. Must its four vertices lie on a circle? Prove the assertion or give an explicit counterexample.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 8192; finish: length.

[No completed final answer; raw generation retained in the source JSON.]

Grade: {"valid": false, "method": "none", "note": "Output limit reached without completed final proof.", "repairable": false}

## C15 sample 0

Solve the new problem with concise, justified steps. When using similarity, keep the vertex correspondence explicit. Check the assumptions of each theorem. Do not specialize a general figure without justifying that the requested quantity is preserved. Prefer a short geometric explanation when it is available; any valid method remains allowed. Finish once the proof is complete.

Here are four examples of the desired mathematical care; they are not hints to the new problem.

Example problem: Triangles ABC and DEF satisfy AB=6, AC=9, DE=10, DF=15 and angle BAC=EDF. Find BC/EF, with justification.
Example answer: AB/DE=AC/DF=3/5, and the included angles at A,D are equal. Thus SAS similarity gives A-D, B-E, C-F. In particular BC/EF=3/5.

Example problem: Distinct points A,B,C,D lie on a circle in that cyclic order. Given angle ABD=32 degrees, find angle ACD.
Example answer: B and C are on the same arc from A to D. The inscribed angles ABD and ACD therefore subtend the same opposite arc AD, so they are equal. Thus angle ACD=32 degrees.

Example problem: In triangle ABC, the perpendicular from A to BC meets the interior of BC at D. Given AB=13, BD=5 and DC=9, find AC.
Example answer: Triangle ADB is right at D, so AD^2=AB^2-BD^2=169-25=144. In right triangle ADC, AC^2=AD^2+DC^2=144+81=225. Therefore AC=15.

Example problem: A convex quadrilateral has diagonals which bisect each other. Must it be a rectangle? Give a proof or explicit counterexample.
Example answer: No. Take A=(0,0), B=(2,0), C=(3,1), D=(1,1). This is a convex parallelogram, and both diagonals have midpoint (3/2,1/2). But AB=(2,0) and AD=(1,1) have dot product 2, not 0. Thus angle BAD is not right and the quadrilateral is not a rectangle.

New problem:
A,B are distinct points. C,D are distinct points off line AB, and triangles ABC and ABD have equal (unsigned) areas. Must CD be parallel to AB? Prove the assertion or give an explicit counterexample.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 1492; finish: stop.



**Conclusion:** CD does not necessarily have to be parallel to AB. A counterexample is provided as follows:

**Counterexample:** Let AB be the x-axis from $ A = (0, 0) $ to $ B = (2, 0) $. Let $ C = (1, 1) $ and $ D = (1, -1) $. The areas of triangles $ ABC $ and $ ABD $ are both $ \frac{1}{2} \times 2 \times 1 = 1 $, satisfying the condition. However, line $ CD $ is vertical (from $ (1,1) $ to $ (1,-1) $), which is not parallel to the horizontal line $ AB $. Thus, CD is not parallel to AB.

**Final Answer:** No, CD is not necessarily parallel to AB. A counterexample exists where $ C $ and $ D $ are on opposite sides of $ AB $ at equal heights, making $ CD $ non-parallel to $ AB $.<|im_end|>

Grade: {"valid": true, "method": "analytic", "note": "Explicit correct opposite-side equal-area counterexample.", "repairable": false}

## C15 sample 1

Solve the new problem with concise, justified steps. When using similarity, keep the vertex correspondence explicit. Check the assumptions of each theorem. Do not specialize a general figure without justifying that the requested quantity is preserved. Prefer a short geometric explanation when it is available; any valid method remains allowed. Finish once the proof is complete.

Here are four examples of the desired mathematical care; they are not hints to the new problem.

Example problem: Triangles ABC and DEF satisfy AB=6, AC=9, DE=10, DF=15 and angle BAC=EDF. Find BC/EF, with justification.
Example answer: AB/DE=AC/DF=3/5, and the included angles at A,D are equal. Thus SAS similarity gives A-D, B-E, C-F. In particular BC/EF=3/5.

Example problem: Distinct points A,B,C,D lie on a circle in that cyclic order. Given angle ABD=32 degrees, find angle ACD.
Example answer: B and C are on the same arc from A to D. The inscribed angles ABD and ACD therefore subtend the same opposite arc AD, so they are equal. Thus angle ACD=32 degrees.

Example problem: In triangle ABC, the perpendicular from A to BC meets the interior of BC at D. Given AB=13, BD=5 and DC=9, find AC.
Example answer: Triangle ADB is right at D, so AD^2=AB^2-BD^2=169-25=144. In right triangle ADC, AC^2=AD^2+DC^2=144+81=225. Therefore AC=15.

Example problem: A convex quadrilateral has diagonals which bisect each other. Must it be a rectangle? Give a proof or explicit counterexample.
Example answer: No. Take A=(0,0), B=(2,0), C=(3,1), D=(1,1). This is a convex parallelogram, and both diagonals have midpoint (3/2,1/2). But AB=(2,0) and AD=(1,1) have dot product 2, not 0. Thus angle BAD is not right and the quadrilateral is not a rectangle.

New problem:
A,B are distinct points. C,D are distinct points off line AB, and triangles ABC and ABD have equal (unsigned) areas. Must CD be parallel to AB? Prove the assertion or give an explicit counterexample.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 2579; finish: stop.



To determine whether segment $ CD $ must be parallel to segment $ AB $, given that triangles $ ABC $ and $ ABD $ have equal (unsigned) areas, we proceed with the following structured analysis:

---

### **Key Geometric Insight: Area and Height**

The area of a triangle is given by:
$$
\text{Area} = \frac{1}{2} \cdot \text{base} \cdot \text{height}
$$
For triangles $ ABC $ and $ ABD $, the base is the common segment $ AB $. Since the areas are equal, the heights from points $ C $ and $ D $ to line $ AB $ must be equal in magnitude. That is, the perpendicular distances from $ C $ and $ D $ to $ AB $ are equal.

This implies that $ C $ and $ D $ lie on lines that are **parallel to** the line $ AB $, at the same distance from $ AB $, but not necessarily on the same side.

---

### **Counterexample Construction**

Let us construct a counterexample to show that $ CD $ does **not** have to be parallel to $ AB $:

- Let $ A = (0,0) $, $ B = (2,0) $, so that $ AB $ lies on the x-axis.
- Let $ C = (1,1) $ and $ D = (1,-1) $, so that both $ C $ and $ D $ are equidistant from $ AB $ (each at a vertical distance of 1 unit), but on opposite sides of $ AB $.

Now compute the areas of triangles $ ABC $ and $ ABD $:

- Area of $ ABC $: $ \frac{1}{2} \cdot 2 \cdot 1 = 1 $
- Area of $ ABD $: $ \frac{1}{2} \cdot 2 \cdot 1 = 1 $

So the areas are equal, but the segment $ CD $ connects $ (1,1) $ to $ (1,-1) $, which is a **vertical** line, not parallel to $ AB $, which is horizontal.

Thus, this counterexample shows that $ CD $ is **not necessarily parallel** to $ AB $.

---

### **Conclusion**

Since the equality of areas only guarantees that the heights from $ C $ and $ D $ to $ AB $ are equal in magnitude, but does not enforce that they lie on the same side of $ AB $, the segment $ CD $ can be non-parallel to $ AB $. Therefore, the assertion that $ CD $ must be parallel to $ AB $ is **false**.

$$
\boxed{No}
$$<|im_end|>

Grade: {"valid": true, "method": "analytic", "note": "Explicit correct opposite-side equal-area counterexample.", "repairable": false}

## C16 sample 0

Solve the new problem with concise, justified steps. When using similarity, keep the vertex correspondence explicit. Check the assumptions of each theorem. Do not specialize a general figure without justifying that the requested quantity is preserved. Prefer a short geometric explanation when it is available; any valid method remains allowed. Finish once the proof is complete.

Here are four examples of the desired mathematical care; they are not hints to the new problem.

Example problem: Triangles ABC and DEF satisfy AB=6, AC=9, DE=10, DF=15 and angle BAC=EDF. Find BC/EF, with justification.
Example answer: AB/DE=AC/DF=3/5, and the included angles at A,D are equal. Thus SAS similarity gives A-D, B-E, C-F. In particular BC/EF=3/5.

Example problem: Distinct points A,B,C,D lie on a circle in that cyclic order. Given angle ABD=32 degrees, find angle ACD.
Example answer: B and C are on the same arc from A to D. The inscribed angles ABD and ACD therefore subtend the same opposite arc AD, so they are equal. Thus angle ACD=32 degrees.

Example problem: In triangle ABC, the perpendicular from A to BC meets the interior of BC at D. Given AB=13, BD=5 and DC=9, find AC.
Example answer: Triangle ADB is right at D, so AD^2=AB^2-BD^2=169-25=144. In right triangle ADC, AC^2=AD^2+DC^2=144+81=225. Therefore AC=15.

Example problem: A convex quadrilateral has diagonals which bisect each other. Must it be a rectangle? Give a proof or explicit counterexample.
Example answer: No. Take A=(0,0), B=(2,0), C=(3,1), D=(1,1). This is a convex parallelogram, and both diagonals have midpoint (3/2,1/2). But AB=(2,0) and AD=(1,1) have dot product 2, not 0. Thus angle BAD is not right and the quadrilateral is not a rectangle.

New problem:
In an acute triangle ABC, the perpendicular from B to AC has the same length as the perpendicular from C to AB. Prove AB=AC.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 1842; finish: stop.



To prove that $ AB = AC $ in an acute triangle $ ABC $, where the perpendicular from $ B $ to $ AC $ has the same length as the perpendicular from $ C $ to $ AB $, we proceed as follows:

---

**Step 1: Use the area formula for a triangle.**  
The area of triangle $ ABC $ can be expressed in two ways:  
- Using base $ AC $ and height $ h_b $ (the perpendicular from $ B $ to $ AC $):  
  $$
  \text{Area} = \frac{1}{2} \cdot AC \cdot h_b
  $$
- Using base $ AB $ and height $ h_c $ (the perpendicular from $ C $ to $ AB $):  
  $$
  \text{Area} = \frac{1}{2} \cdot AB \cdot h_c
  $$

Since both expressions represent the same area, we equate them:
$$
\frac{1}{2} \cdot AC \cdot h_b = \frac{1}{2} \cdot AB \cdot h_c
$$

---

**Step 2: Simplify the equation.**  
Multiplying both sides by 2 and canceling the common factor $ \frac{1}{2} $, we get:
$$
AC \cdot h_b = AB \cdot h_c
$$

Given that $ h_b = h_c $ (from the problem statement), substitute this into the equation:
$$
AC \cdot h_b = AB \cdot h_b
$$

---

**Step 3: Conclude that $ AB = AC $.**  
Since $ h_b \neq 0 $ (the triangle is acute, so the altitudes are non-zero), we can divide both sides by $ h_b $:
$$
AC = AB
$$

---

**Conclusion:**  
The triangle $ ABC $ is isosceles with $ AB = AC $.

$$
\boxed{AB = AC}
$$<|im_end|>

Grade: {"valid": true, "method": "area", "note": "Correct base-altitude area comparison.", "repairable": false}

## C16 sample 1

Solve the new problem with concise, justified steps. When using similarity, keep the vertex correspondence explicit. Check the assumptions of each theorem. Do not specialize a general figure without justifying that the requested quantity is preserved. Prefer a short geometric explanation when it is available; any valid method remains allowed. Finish once the proof is complete.

Here are four examples of the desired mathematical care; they are not hints to the new problem.

Example problem: Triangles ABC and DEF satisfy AB=6, AC=9, DE=10, DF=15 and angle BAC=EDF. Find BC/EF, with justification.
Example answer: AB/DE=AC/DF=3/5, and the included angles at A,D are equal. Thus SAS similarity gives A-D, B-E, C-F. In particular BC/EF=3/5.

Example problem: Distinct points A,B,C,D lie on a circle in that cyclic order. Given angle ABD=32 degrees, find angle ACD.
Example answer: B and C are on the same arc from A to D. The inscribed angles ABD and ACD therefore subtend the same opposite arc AD, so they are equal. Thus angle ACD=32 degrees.

Example problem: In triangle ABC, the perpendicular from A to BC meets the interior of BC at D. Given AB=13, BD=5 and DC=9, find AC.
Example answer: Triangle ADB is right at D, so AD^2=AB^2-BD^2=169-25=144. In right triangle ADC, AC^2=AD^2+DC^2=144+81=225. Therefore AC=15.

Example problem: A convex quadrilateral has diagonals which bisect each other. Must it be a rectangle? Give a proof or explicit counterexample.
Example answer: No. Take A=(0,0), B=(2,0), C=(3,1), D=(1,1). This is a convex parallelogram, and both diagonals have midpoint (3/2,1/2). But AB=(2,0) and AD=(1,1) have dot product 2, not 0. Thus angle BAD is not right and the quadrilateral is not a rectangle.

New problem:
In an acute triangle ABC, the perpendicular from B to AC has the same length as the perpendicular from C to AB. Prove AB=AC.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 3114; finish: stop.



To prove that in an acute triangle $ ABC $, if the perpendicular from $ B $ to $ AC $ has the same length as the perpendicular from $ C $ to $ AB $, then $ AB = AC $, we proceed as follows:

---

**Step 1: Use the area formula for a triangle.**

The area of triangle $ ABC $ can be expressed in two ways:

$$
\text{Area} = \frac{1}{2} \cdot AC \cdot h_B = \frac{1}{2} \cdot AB \cdot h_C
$$

where $ h_B $ is the length of the perpendicular from $ B $ to $ AC $, and $ h_C $ is the length of the perpendicular from $ C $ to $ AB $. The problem states that $ h_B = h_C $.

---

**Step 2: Equating the two expressions for the area.**

Since $ h_B = h_C $, the two expressions for the area become:

$$
\frac{1}{2} \cdot AC \cdot h_B = \frac{1}{2} \cdot AB \cdot h_B
$$

Multiplying both sides by 2 and canceling $ h_B $ (which is non-zero because the triangle is acute and the perpendiculars lie inside the triangle), we get:

$$
AC = AB
$$

---

**Conclusion:**

The equality of the perpendiculars from $ B $ to $ AC $ and from $ C $ to $ AB $ implies that the triangle is such that the bases $ AB $ and $ AC $ must be equal for the areas to be equal under the given conditions. Therefore, we conclude:

$$
\boxed{AB = AC}
$$<|im_end|>

Grade: {"valid": true, "method": "area", "note": "Correct base-altitude area comparison.", "repairable": false}
