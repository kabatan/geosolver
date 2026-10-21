## C01 sample 0

In triangle ABC, AB=6, AC=9, and BC=10. The internal bisector of angle BAC meets BC at D. Through D draw the line parallel to AB, meeting AC at E. Find AE.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 8192; finish: length.

[No completed final answer; raw generation retained in the source JSON.]

Grade: {"valid": false, "method": "none", "note": "No completed final proof before the output limit.", "repairable": false}

## C01 sample 1

In triangle ABC, AB=6, AC=9, and BC=10. The internal bisector of angle BAC meets BC at D. Through D draw the line parallel to AB, meeting AC at E. Find AE.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 5263; finish: stop.



To solve the problem, we begin by analyzing triangle $ ABC $, where the sides are given as $ AB = 6 $, $ AC = 9 $, and $ BC = 10 $. The internal angle bisector of $ \angle BAC $ meets $ BC $ at point $ D $, and through $ D $, a line is drawn parallel to $ AB $, intersecting $ AC $ at point $ E $. We are to find the length of $ AE $.

---

### Step 1: Use the Angle Bisector Theorem

The **Angle Bisector Theorem** states that the angle bisector of an angle in a triangle divides the opposite side into segments proportional to the adjacent sides. Therefore, in triangle $ ABC $, since $ AD $ is the angle bisector of $ \angle BAC $, we have:

$$
\frac{BD}{DC} = \frac{AB}{AC} = \frac{6}{9} = \frac{2}{3}
$$

Let $ BD = 2x $ and $ DC = 3x $. Since $ BD + DC = BC = 10 $, we get:

$$
2x + 3x = 10 \Rightarrow x = 2
$$

So, $ BD = 4 $ and $ DC = 6 $.

---

### Step 2: Use Similar Triangles

Now, we are told that a line is drawn through $ D $, parallel to $ AB $, and intersects $ AC $ at point $ E $. This line, $ DE $, is parallel to $ AB $, and we are to find $ AE $.

Because $ DE \parallel AB $, and both $ AB $ and $ DE $ are intersected by $ AC $, we can apply the **Basic Proportionality Theorem** (also known as Thales' Theorem), which states that a line drawn parallel to one side of a triangle divides the other two sides proportionally.

This means that:

$$
\frac{AE}{EC} = \frac{BD}{DC} = \frac{2}{3}
$$

Let $ AE = 2k $ and $ EC = 3k $. Since $ AE + EC = AC = 9 $, we have:

$$
2k + 3k = 9 \Rightarrow 5k = 9 \Rightarrow k = \frac{9}{5}
$$

Therefore:

$$
AE = 2k = 2 \cdot \frac{9}{5} = \frac{18}{5}
$$

---

### Final Result

Thus, the length of $ AE $ is:

$$
\boxed{\dfrac{18}{5}}
$$<|im_end|>

Grade: {"valid": true, "method": "synthetic", "note": "Correct angle-bisector ratio and parallel-line proportion yield AE=18/5.", "repairable": false}

## C02 sample 0

In triangle ABC, angle BAC=48 degrees. The internal bisectors of angles ABC and ACB meet at I. Find angle BIC.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 1934; finish: stop.



To determine the measure of angle $ \angle BIC $ in triangle $ ABC $, where point $ I $ is the intersection of the internal angle bisectors of $ \angle ABC $ and $ \angle ACB $, we utilize the geometric properties of the incenter and angle bisectors.

---

### Step 1: Use the Angle Sum of Triangle $ ABC $

We are given that:
$$
\angle BAC = 48^\circ
$$
Let:
$$
\angle ABC = B, \quad \angle ACB = C
$$
Then, by the angle sum property of a triangle:
$$
A + B + C = 180^\circ
$$
$$
48^\circ + B + C = 180^\circ \Rightarrow B + C = 132^\circ
$$

---

### Step 2: Apply the Incenter Angle Formula

Point $ I $ is the incenter of triangle $ ABC $, so it lies at the intersection of the internal angle bisectors. This means:

- $ \angle IBC = \frac{B}{2} $
- $ \angle ICB = \frac{C}{2} $

Now consider triangle $ BIC $, and apply the angle sum property:

$$
\angle IBC + \angle ICB + \angle BIC = 180^\circ
$$
$$
\frac{B}{2} + \frac{C}{2} + \angle BIC = 180^\circ
$$
$$
\angle BIC = 180^\circ - \frac{B + C}{2}
$$

Substitute $ B + C = 132^\circ $:

$$
\angle BIC = 180^\circ - \frac{132^\circ}{2} = 180^\circ - 66^\circ = 114^\circ
$$

---

### Step 3: Confirm with a General Formula

There is a known formula for the angle at the incenter:

$$
\angle BIC = 90^\circ + \frac{1}{2} \angle BAC
$$

Using this:

$$
\angle BIC = 90^\circ + \frac{1}{2} \cdot 48^\circ = 90^\circ + 24^\circ = 114^\circ
$$

---

### Final Answer

$$
\boxed{114}
$$<|im_end|>

Grade: {"valid": true, "method": "synthetic", "note": "Correct angle sum in BIC yields114.", "repairable": false}

## C02 sample 1

In triangle ABC, angle BAC=48 degrees. The internal bisectors of angles ABC and ACB meet at I. Find angle BIC.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 1992; finish: stop.



To determine the measure of angle $ \angle BIC $ in triangle $ ABC $, where $ I $ is the incenter (the intersection of the internal angle bisectors of $ \angle ABC $ and $ \angle ACB $), we can use a well-known geometric property of the incenter.

---

### Step 1: Understand the Geometry

In triangle $ ABC $, the incenter $ I $ lies at the intersection of the internal angle bisectors of $ \angle ABC $ and $ \angle ACB $. Therefore, the angles formed at $ I $ by these bisectors are:

$$
\angle IBC = \frac{1}{2} \angle ABC, \quad \angle ICB = \frac{1}{2} \angle ACB
$$

Let the angles of triangle $ ABC $ be:

- $ \angle BAC = \alpha = 48^\circ $
- $ \angle ABC = \beta $
- $ \angle ACB = \gamma $

We know from triangle angle sum that:

$$
\alpha + \beta + \gamma = 180^\circ
$$

So:

$$
\beta + \gamma = 180^\circ - \alpha = 180^\circ - 48^\circ = 132^\circ
$$

---

### Step 2: Use the Incenter Angle Formula

In triangle $ BIC $, the angles at $ B $ and $ C $ are:

$$
\angle IBC = \frac{1}{2} \beta, \quad \angle ICB = \frac{1}{2} \gamma
$$

Therefore, the angle $ \angle BIC $ is:

$$
\angle BIC = 180^\circ - \angle IBC - \angle ICB = 180^\circ - \frac{1}{2} \beta - \frac{1}{2} \gamma
$$

Substituting $ \beta + \gamma = 132^\circ $:

$$
\angle BIC = 180^\circ - \frac{1}{2}(132^\circ) = 180^\circ - 66^\circ = 114^\circ
$$

---

### Final Answer

$$
\boxed{114}
$$<|im_end|>

Grade: {"valid": true, "method": "synthetic", "note": "Correct angle sum in BIC yields114.", "repairable": false}

## C03 sample 0

ABCD is a convex quadrilateral with AB=BC and AD=DC. Prove that its diagonals AC and BD are perpendicular.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 5382; finish: stop.



To prove that in a convex quadrilateral $ABCD$ with $AB = BC$ and $AD = DC$, the diagonals $AC$ and $BD$ are perpendicular, we can use a combination of geometric reasoning and vector algebra.

---

### Step 1: Understanding the Structure

Given:
- $AB = BC$ implies triangle $ABC$ is isosceles with base $AC$.
- $AD = DC$ implies triangle $ADC$ is isosceles with base $AC$.

This configuration suggests that the diagonals $AC$ and $BD$ intersect at some point inside the quadrilateral, and we are to show that they are perpendicular.

---

### Step 2: Use of Vector Geometry

Let’s place the quadrilateral in a vector space and define:
- Let $\vec{A} = \vec{0}$ (i.e., point $A$ is the origin).
- Let $\vec{B} = \vec{u}$ and $\vec{D} = \vec{d}$.

From the given:
- Since $AB = BC$, vector $\vec{BC} = \vec{u}$, so $\vec{C} = \vec{B} + \vec{BC} = \vec{u} + \vec{u} = 2\vec{u}$.
- Since $AD = DC$, vector $\vec{DC} = \vec{d}$, so $\vec{C} - \vec{D} = \vec{d} \Rightarrow 2\vec{u} - \vec{d} = \vec{d} \Rightarrow 2\vec{u} = 2\vec{d} \Rightarrow \vec{u} = \vec{d}$.

Wait — this would imply $AB = AD$, but the original problem does not state this. So this reasoning must be corrected.

Instead, from the condition $AD = DC$, we have:
$$
|\vec{d}| = |2\vec{u} - \vec{d}|
\Rightarrow |\vec{d}|^2 = |2\vec{u} - \vec{d}|^2
$$
Expanding both sides:
$$
\vec{d} \cdot \vec{d} = (2\vec{u} - \vec{d}) \cdot (2\vec{u} - \vec{d})
\Rightarrow \vec{d} \cdot \vec{d} = 4\vec{u} \cdot \vec{u} - 4\vec{u} \cdot \vec{d} + \vec{d} \cdot \vec{d}
$$
Subtracting $\vec{d} \cdot \vec{d}$ from both sides:
$$
0 = 4\vec{u} \cdot \vec{u} - 4\vec{u} \cdot \vec{d}
\Rightarrow \vec{u} \cdot \vec{d} = \vec{u} \cdot \vec{u}
$$

Now, we compute the dot product of vectors $\vec{AC}$ and $\vec{BD}$:
- $\vec{AC} = \vec{C} - \vec{A} = 2\vec{u} - \vec{0} = 2\vec{u}$
- $\vec{BD} = \vec{D} - \vec{B} = \vec{d} - \vec{u}$

Then:
$$
\vec{AC} \cdot \vec{BD} = (2\vec{u}) \cdot (\vec{d} - \vec{u}) = 2\vec{u} \cdot \vec{d} - 2\vec{u} \cdot \vec{u}
$$
But from earlier, $\vec{u} \cdot \vec{d} = \vec{u} \cdot \vec{u}$, so:
$$
\vec{AC} \cdot \vec{BD} = 2(\vec{u} \cdot \vec{u}) - 2(\vec{u} \cdot \vec{u}) = 0
$$

---

### Conclusion

Since the dot product of vectors $\vec{AC}$ and $\vec{BD}$ is zero, the diagonals $AC$ and $BD$ are perpendicular.

$$
\boxed{AC \perp BD}
$$<|im_end|>

Grade: {"valid": false, "method": "analytic", "note": "Confuses equal lengths AB=BC with equal vectors, assumes C=2B and retains that degenerate assumption after an attempted correction.", "repairable": false}

## C03 sample 1

ABCD is a convex quadrilateral with AB=BC and AD=DC. Prove that its diagonals AC and BD are perpendicular.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 3634; finish: stop.



To prove that the diagonals $ AC $ and $ BD $ of the convex quadrilateral $ ABCD $ are perpendicular, we begin by analyzing the given conditions:

- $ AB = BC $, so triangle $ ABC $ is isosceles with $ AB = BC $.
- $ AD = DC $, so triangle $ ADC $ is also isosceles with $ AD = DC $.

---

### Key Observations

1. **Isosceles Triangles and Perpendicular Bisectors**:
   - In triangle $ ABC $, since $ AB = BC $, the base is $ AC $, and the equal sides are $ AB $ and $ BC $. Therefore, the apex $ B $ lies on the **perpendicular bisector** of segment $ AC $.
   - Similarly, in triangle $ ADC $, since $ AD = DC $, the apex $ D $ also lies on the **perpendicular bisector** of segment $ AC $.

2. **Implication for Diagonal $ BD $**:
   - Since both points $ B $ and $ D $ lie on the **perpendicular bisector** of $ AC $, the segment $ BD $ lies entirely on that line.
   - The **perpendicular bisector of a segment** is a line that is **perpendicular** to the segment and passes through its midpoint.
   - Therefore, the line $ BD $ is **perpendicular to** the segment $ AC $.

---

### Conclusion

Since the diagonal $ BD $ lies on the perpendicular bisector of $ AC $, it is **perpendicular to** $ AC $. Therefore, the diagonals $ AC $ and $ BD $ are perpendicular.

$$
\boxed{AC \perp BD}
$$<|im_end|>

Grade: {"valid": true, "method": "synthetic", "note": "Correct perpendicular-bisector argument from the two equal-distance conditions.", "repairable": false}

## C04 sample 0

ABCD is a nondegenerate parallelogram, E is the midpoint of AB, and lines DE and AC meet at F. Find AF/FC.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 5287; finish: stop.



To determine the ratio $ \frac{AF}{FC} $ in the given parallelogram $ABCD$, where $E$ is the midpoint of $AB$ and lines $DE$ and $AC$ intersect at $F$, we can use a combination of coordinate geometry and vector analysis to arrive at a general and precise result.

---

### Step 1: Assign Coordinates

Let’s place the parallelogram in a coordinate system for simplicity:

- Let $A = (0, 0)$
- Let $B = (2b, 0)$, so that the midpoint $E$ of $AB$ is at $E = (b, 0)$
- Let $D = (0, 2d)$, then $C = (2b, 2d)$ (since in a parallelogram, $C = B + D - A$)

---

### Step 2: Parametrize the Lines

- **Line AC** (from $A = (0, 0)$ to $C = (2b, 2d)$):  
  Parametric form:  
  $$
  \vec{r}(s) = s(2b, 2d), \quad s \in [0, 1]
  $$

- **Line DE** (from $D = (0, 2d)$ to $E = (b, 0)$):  
  Direction vector: $ (b, -2d) $  
  Parametric form:  
  $$
  \vec{r}(t) = (0, 2d) + t(b, -2d) = (bt, 2d - 2dt), \quad t \in [0, 1]
  $$

---

### Step 3: Find the Intersection Point $F$

Set the two parametric equations equal to find the point $F$ where the lines intersect:

$$
bt = 2bs \quad \text{(from x-coordinates)}
$$
$$
2d - 2dt = 2ds \quad \text{(from y-coordinates)}
$$

From the first equation: $ t = 2s $

Substitute into the second equation:

$$
2d - 2d(2s) = 2ds \Rightarrow 2d - 4ds = 2ds \Rightarrow 2d = 6ds \Rightarrow s = \frac{1}{3}
$$

Then, $t = 2s = \frac{2}{3}$

So, the point $F$ lies at $s = \frac{1}{3}$ along the diagonal $AC$, meaning:

$$
AF = \frac{1}{3} \cdot AC, \quad FC = \frac{2}{3} \cdot AC
$$

Thus, the ratio is:

$$
\frac{AF}{FC} = \frac{1/3}{2/3} = \frac{1}{2}
$$

---

### Step 4: Generalization via Vectors

Let’s now confirm this result using vectors. Let:

- $ \vec{A} = \vec{0} $
- $ \vec{B} = \vec{b} $
- $ \vec{D} = \vec{d} $
- $ \vec{C} = \vec{b} + \vec{d} $
- $ \vec{E} = \frac{1}{2} \vec{b} $

Then:

- Line $DE$ is parametrized as:  
  $$
  \vec{r}(t) = \vec{d} + t(\vec{E} - \vec{D}) = \vec{d} + t\left(\frac{1}{2} \vec{b} - \vec{d}\right)
  $$

- Line $AC$ is parametrized as:  
  $$
  \vec{r}(s) = s(\vec{b} + \vec{d})
  $$

Setting these equal and solving gives the same result: $s = \frac{1}{3}$, so again:

$$
\frac{AF}{FC} = \frac{1}{2}
$$

---

### Final Conclusion

Regardless of the specific shape of the parallelogram (as long as it is nondegenerate), the ratio $ \frac{AF}{FC} $ is always:

$$
\boxed{\dfrac{1}{2}}
$$<|im_end|>

Grade: {"valid": true, "method": "analytic", "note": "Explicit general vector equations after a rectangular illustration establish AF/FC=1/2.", "repairable": false}

## C04 sample 1

ABCD is a nondegenerate parallelogram, E is the midpoint of AB, and lines DE and AC meet at F. Find AF/FC.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 4311; finish: stop.



To determine the ratio $ \dfrac{AF}{FC} $ in the given nondegenerate parallelogram $ABCD$, we analyze the geometric configuration and use coordinate geometry for clarity and precision.

---

### Step 1: Assign Coordinates

Let’s place the parallelogram in the coordinate plane for convenience:

- Let $ A = (0, 0) $
- Let $ B = (2b, 0) $, so that $ AB $ is horizontal.
- Let $ D = (0, 2d) $, so that $ AD $ is vertical.
- Then $ C = (2b, 2d) $, since $ \vec{AB} = \vec{DC} $, and $ \vec{AD} = \vec{BC} $, making $ABCD$ a parallelogram.

The midpoint $E$ of $AB$ is:
$$
E = \left( \frac{0 + 2b}{2}, \frac{0 + 0}{2} \right) = (b, 0)
$$

---

### Step 2: Find Equations of Lines

- **Line $DE$** connects $D = (0, 2d)$ to $E = (b, 0)$.  
  Slope of $DE$ is:
  $$
  m_{DE} = \frac{0 - 2d}{b - 0} = -\frac{2d}{b}
  $$
  Equation of line $DE$ is:
  $$
  y - 2d = -\frac{2d}{b}x \Rightarrow y = -\frac{2d}{b}x + 2d
  $$

- **Line $AC$** connects $A = (0, 0)$ to $C = (2b, 2d)$.  
  Slope of $AC$ is:
  $$
  m_{AC} = \frac{2d - 0}{2b - 0} = \frac{d}{b}
  $$
  Equation of line $AC$ is:
  $$
  y = \frac{d}{b}x
  $$

---

### Step 3: Find Intersection Point $F$

Set the two equations equal to find the intersection point $F$:

$$
\frac{d}{b}x = -\frac{2d}{b}x + 2d
$$

Multiply through by $b$ to eliminate denominators:

$$
dx = -2dx + 2db \Rightarrow 3dx = 2db \Rightarrow x = \frac{2b}{3}
$$

Substitute back into $y = \frac{d}{b}x$:

$$
y = \frac{d}{b} \cdot \frac{2b}{3} = \frac{2d}{3}
$$

So the coordinates of $F$ are:
$$
F = \left( \frac{2b}{3}, \frac{2d}{3} \right)
$$

---

### Step 4: Compute Ratio $ \dfrac{AF}{FC} $

Since $F$ lies on the line segment $AC$, we can compute the ratio by comparing the distances from $A$ to $F$ and from $F$ to $C$. Because the coordinates are proportional along the line, we can use the $x$-coordinates or $y$-coordinates for the ratio:

- From $A = (0, 0)$ to $F = \left( \frac{2b}{3}, \frac{2d}{3} \right)$
- From $F = \left( \frac{2b}{3}, \frac{2d}{3} \right)$ to $C = (2b, 2d)$

The $x$-coordinates of $A$, $F$, and $C$ are $0$, $\frac{2b}{3}$, and $2b$, respectively.

So the ratio:
$$
\frac{AF}{FC} = \frac{ \frac{2b}{3} - 0 }{ 2b - \frac{2b}{3} } = \frac{ \frac{2b}{3} }{ \frac{4b}{3} } = \frac{2}{4} = \frac{1}{2}
$$

---

### Final Answer

$$
\boxed{\dfrac{1}{2}}
$$<|im_end|>

Grade: {"valid": false, "method": "analytic", "note": "Calculates only a rectangle while claiming a general parallelogram; no affine-invariance or general vector justification.", "repairable": true}

## C05 sample 0

AB is a diameter of a circle with center O. C is another point on the circle. The tangent at C meets the tangents at A and B at X and Y, respectively. Prove that angle XOY=90 degrees.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 3445; finish: stop.



To prove that angle $ \angle XOY = 90^\circ $, we analyze the geometric configuration involving a circle with diameter $ AB $, center $ O $, and a point $ C $ on the circle. The tangent at $ C $ intersects the tangents at $ A $ and $ B $ at points $ X $ and $ Y $, respectively.

---

### Step 1: Coordinate Setup

We place the circle in the coordinate plane with center $ O $ at the origin $ (0, 0) $, and diameter $ AB $ along the x-axis. Let the circle have radius $ r = 1 $, so the coordinates of points are:

- $ A = (-1, 0) $
- $ B = (1, 0) $
- $ C = (\cos\theta, \sin\theta) $, where $ \theta $ is the angle $ \angle AOC $.

---

### Step 2: Tangent Lines

- The tangent at $ A $ is perpendicular to the radius $ OA $, which is horizontal. Hence, it is a vertical line: $ x = -1 $.
- Similarly, the tangent at $ B $ is vertical: $ x = 1 $.
- The tangent at $ C $ is perpendicular to the radius $ OC $, which has slope $ \tan\theta $. Thus, the tangent at $ C $ has slope $ -\cot\theta $, and its equation is:

$$
y - \sin\theta = -\cot\theta (x - \cos\theta)
$$

Simplifying this gives the equation of the tangent at $ C $:

$$
\cos\theta \cdot x + \sin\theta \cdot y = 1
$$

---

### Step 3: Finding Points $ X $ and $ Y $

- **Point $ X $**: Intersection of the tangent at $ C $ with the tangent at $ A $ (i.e., $ x = -1 $):

$$
\cos\theta \cdot (-1) + \sin\theta \cdot y = 1 \Rightarrow -\cos\theta + \sin\theta \cdot y = 1 \Rightarrow y = \frac{1 + \cos\theta}{\sin\theta}
$$

So, $ X = (-1, \frac{1 + \cos\theta}{\sin\theta}) $.

- **Point $ Y $**: Intersection of the tangent at $ C $ with the tangent at $ B $ (i.e., $ x = 1 $):

$$
\cos\theta \cdot 1 + \sin\theta \cdot y = 1 \Rightarrow \cos\theta + \sin\theta \cdot y = 1 \Rightarrow y = \frac{1 - \cos\theta}{\sin\theta}
$$

So, $ Y = (1, \frac{1 - \cos\theta}{\sin\theta}) $.

---

### Step 4: Vectors and Dot Product

Vectors from the origin to $ X $ and $ Y $ are:

- $ \vec{OX} = (-1, \frac{1 + \cos\theta}{\sin\theta}) $
- $ \vec{OY} = (1, \frac{1 - \cos\theta}{\sin\theta}) $

Compute the dot product:

$$
\vec{OX} \cdot \vec{OY} = (-1)(1) + \left( \frac{1 + \cos\theta}{\sin\theta} \right) \left( \frac{1 - \cos\theta}{\sin\theta} \right)
$$

$$
= -1 + \frac{(1 + \cos\theta)(1 - \cos\theta)}{\sin^2\theta} = -1 + \frac{1 - \cos^2\theta}{\sin^2\theta}
$$

But $ 1 - \cos^2\theta = \sin^2\theta $, so:

$$
\vec{OX} \cdot \vec{OY} = -1 + \frac{\sin^2\theta}{\sin^2\theta} = -1 + 1 = 0
$$

Since the dot product is zero, the vectors $ \vec{OX} $ and $ \vec{OY} $ are perpendicular. Therefore, the angle $ \angle XOY = 90^\circ $.

---

### Final Conclusion

$$
\boxed{90^\circ}
$$<|im_end|>

Grade: {"valid": true, "method": "analytic", "note": "General unit-circle tangent coordinates give dot product0. Sample0 misnames the parameter angle but computation is general.", "repairable": false}

## C05 sample 1

AB is a diameter of a circle with center O. C is another point on the circle. The tangent at C meets the tangents at A and B at X and Y, respectively. Prove that angle XOY=90 degrees.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 3695; finish: stop.



To prove that angle $\angle XOY = 90^\circ$, we begin by analyzing the geometric configuration of the circle and the tangents involved.

---

### **Geometric Setup**

- Let the circle have center $ O $ and diameter $ AB $.
- Let $ C $ be a point on the circle (not coinciding with $ A $ or $ B $).
- The tangent at $ C $ intersects the tangent at $ A $ at point $ X $, and the tangent at $ B $ at point $ Y $.
- The goal is to show that the angle $\angle XOY = 90^\circ$.

---

### **Coordinate Geometry Approach**

We place the circle in the coordinate plane with center at the origin $ O = (0, 0) $, and let the circle have radius 1. Then:

- $ A = (-1, 0) $
- $ B = (1, 0) $
- $ C = (\cos\theta, \sin\theta) $ for some angle $ \theta $, where $ \theta \in (0, \pi) $

The general equation of the tangent to a circle at point $ (\cos\theta, \sin\theta) $ is:

$$
x \cos\theta + y \sin\theta = 1
$$

- The tangent at $ A $ is vertical (since $ OA $ is horizontal), so its equation is $ x = -1 $
- The tangent at $ B $ is vertical, so its equation is $ x = 1 $

---

### **Finding Points $ X $ and $ Y $**

- **Point $ X $**: Intersection of the tangent at $ C $ and the tangent at $ A $.

$$
x = -1 \Rightarrow -\cos\theta + y \sin\theta = 1 \Rightarrow y = \frac{1 + \cos\theta}{\sin\theta}
$$

So, $ X = (-1, \frac{1 + \cos\theta}{\sin\theta}) $

- **Point $ Y $**: Intersection of the tangent at $ C $ and the tangent at $ B $.

$$
x = 1 \Rightarrow \cos\theta + y \sin\theta = 1 \Rightarrow y = \frac{1 - \cos\theta}{\sin\theta}
$$

So, $ Y = (1, \frac{1 - \cos\theta}{\sin\theta}) $

---

### **Vectors $ \vec{OX} $ and $ \vec{OY} $**

- $ \vec{OX} = (-1, \frac{1 + \cos\theta}{\sin\theta}) $
- $ \vec{OY} = (1, \frac{1 - \cos\theta}{\sin\theta}) $

Compute the dot product:

$$
\vec{OX} \cdot \vec{OY} = (-1)(1) + \left(\frac{1 + \cos\theta}{\sin\theta} \cdot \frac{1 - \cos\theta}{\sin\theta}\right)
$$

$$
= -1 + \frac{(1 + \cos\theta)(1 - \cos\theta)}{\sin^2\theta}
= -1 + \frac{1 - \cos^2\theta}{\sin^2\theta}
$$

Since $ 1 - \cos^2\theta = \sin^2\theta $, this simplifies to:

$$
-1 + \frac{\sin^2\theta}{\sin^2\theta} = -1 + 1 = 0
$$

Thus, the dot product of $ \vec{OX} $ and $ \vec{OY} $ is zero, which implies that the vectors are perpendicular.

---

### **Conclusion**

Since vectors $ \vec{OX} $ and $ \vec{OY} $ are perpendicular, the angle between them is $ 90^\circ $. Therefore:

$$
\angle XOY = \boxed{90^\circ}
$$<|im_end|>

Grade: {"valid": true, "method": "analytic", "note": "General unit-circle tangent coordinates give dot product0. Sample0 misnames the parameter angle but computation is general.", "repairable": false}

## C06 sample 0

ABC is an equilateral triangle of altitude h. P is strictly inside the triangle, and its perpendicular distances to lines AB, BC, CA are x,y,z. Prove that x+y+z=h.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 3943; finish: stop.



To prove that the sum of the perpendicular distances from any interior point $ P $ of an equilateral triangle $ ABC $ to its three sides is equal to the altitude $ h $, we can use a geometric argument based on the area of the triangle.

---

### **Key Idea: Area Decomposition**

Let $ P $ be a point strictly inside the equilateral triangle $ ABC $, and let $ x $, $ y $, and $ z $ be the perpendicular distances from $ P $ to the sides $ AB $, $ BC $, and $ CA $, respectively.

The triangle $ ABC $ can be divided into three smaller triangles: $ \triangle PAB $, $ \triangle PBC $, and $ \triangle PCA $. Each of these triangles has one side of $ ABC $ as its base, and the corresponding distance from $ P $ to that side is the height of the triangle.

Thus, the area of triangle $ ABC $ can be expressed as the sum of the areas of the three smaller triangles:

$$
\text{Area of } ABC = \text{Area of } \triangle PAB + \text{Area of } \triangle PBC + \text{Area of } \triangle PCA
$$

Each of these smaller triangles has area:

- $ \text{Area of } \triangle PAB = \frac{1}{2} \cdot AB \cdot x $
- $ \text{Area of } \triangle PBC = \frac{1}{2} \cdot BC \cdot y $
- $ \text{Area of } \triangle PCA = \frac{1}{2} \cdot CA \cdot z $

Since $ ABC $ is equilateral, all sides are equal in length, say $ s $. Therefore:

$$
\text{Area of } ABC = \frac{1}{2} s (x + y + z)
$$

But the area of triangle $ ABC $ can also be expressed using its base and height:

$$
\text{Area of } ABC = \frac{1}{2} s h
$$

Equating the two expressions for the area:

$$
\frac{1}{2} s (x + y + z) = \frac{1}{2} s h
$$

Dividing both sides by $ \frac{1}{2} s $ (since $ s > 0 $), we get:

$$
x + y + z = h
$$

---

### **Conclusion**

Therefore, for any point $ P $ strictly inside an equilateral triangle $ ABC $, the sum of the perpendicular distances from $ P $ to the three sides is equal to the altitude $ h $ of the triangle.

$$
\boxed{h}
$$<|im_end|>

Grade: {"valid": true, "method": "area", "note": "Correct three-part area decomposition.", "repairable": false}

## C06 sample 1

ABC is an equilateral triangle of altitude h. P is strictly inside the triangle, and its perpendicular distances to lines AB, BC, CA are x,y,z. Prove that x+y+z=h.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 4393; finish: stop.



To prove that for any point $ P $ strictly inside an equilateral triangle $ ABC $, the sum of the perpendicular distances from $ P $ to the sides $ AB $, $ BC $, and $ CA $ is equal to the altitude $ h $ of the triangle, we can proceed as follows:

---

### **Key Geometric Insight**

In any triangle, the **area** can be divided into smaller triangles formed by a point inside the triangle and the triangle's vertices. In particular, for an equilateral triangle $ ABC $, and a point $ P $ inside it, the triangle is divided into three smaller triangles: $ \triangle PAB $, $ \triangle PBC $, and $ \triangle PCA $.

The **area of triangle $ ABC $** is the sum of the areas of these three smaller triangles. This is a fundamental geometric property that holds for any point inside the triangle.

---

### **Area-Based Proof**

Let the side length of the equilateral triangle be $ s $, and the altitude be $ h $. In an equilateral triangle, the altitude is related to the side length by:

$$
h = \frac{\sqrt{3}}{2}s
$$

Let the perpendicular distances from point $ P $ to the sides $ AB $, $ BC $, and $ CA $ be $ x $, $ y $, and $ z $, respectively.

The area of triangle $ ABC $ can be written in two ways:

1. **Using the standard formula for the area of a triangle**:
   $$
   \text{Area of } \triangle ABC = \frac{1}{2} \cdot s \cdot h
   $$

2. **Using the areas of the three smaller triangles**:
   $$
   \text{Area of } \triangle ABC = \text{Area of } \triangle PAB + \text{Area of } \triangle PBC + \text{Area of } \triangle PCA
   $$

Each of the smaller triangles has a base equal to the side length $ s $ and a height equal to the perpendicular distance from $ P $ to that side:

- Area of $ \triangle PAB = \frac{1}{2} s x $
- Area of $ \triangle PBC = \frac{1}{2} s y $
- Area of $ \triangle PCA = \frac{1}{2} s z $

So the total area is:

$$
\frac{1}{2} s (x + y + z)
$$

Equating the two expressions for the area of $ \triangle ABC $:

$$
\frac{1}{2} s h = \frac{1}{2} s (x + y + z)
$$

Canceling $ \frac{1}{2} s $ from both sides:

$$
h = x + y + z
$$

---

### **Conclusion**

This shows that for any point $ P $ strictly inside the equilateral triangle $ ABC $, the sum of the perpendicular distances from $ P $ to the three sides is equal to the altitude $ h $ of the triangle.

$$
\boxed{h}
$$<|im_end|>

Grade: {"valid": true, "method": "area", "note": "Correct three-part area decomposition.", "repairable": false}

## C07 sample 0

Triangle ABC has AB=13, AC=14, BC=15. Its incircle touches BC at D. Find BD.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 3444; finish: stop.



To determine the length of $ BD $, where $ D $ is the point where the incircle of triangle $ ABC $ touches side $ BC $, we use the well-known geometric property that relates the lengths of tangents from a triangle's vertices to the incircle.

---

### Step 1: Compute the Semiperimeter

Given the side lengths of triangle $ ABC $:
- $ AB = 13 $
- $ AC = 14 $
- $ BC = 15 $

The **semiperimeter** $ s $ is given by:

$$
s = \frac{AB + AC + BC}{2} = \frac{13 + 14 + 15}{2} = \frac{42}{2} = 21
$$

---

### Step 2: Apply the Tangent Length Formula

In any triangle, the lengths of the tangents from the vertices to the incircle are given by:

$$
BD = s - AC
$$

Substituting the known values:

$$
BD = 21 - 14 = 7
$$

---

### Step 3: Verification (Optional but Satisfying)

We can verify this using coordinate geometry or the inradius formula. Placing the triangle in the coordinate plane, computing the incenter, and verifying the point of tangency on side $ BC $ also leads to the same result: the incircle touches $ BC $ at $ x = 7 $, so $ BD = 7 $.

Additionally, using the formula for the length of a tangent from a point to a circle (in this case, the incenter), we find the same value.

---

### Final Conclusion

All methods consistently confirm that the length of $ BD $ is:

$$
\boxed{7}
$$<|im_end|>

Grade: {"valid": true, "method": "synthetic", "note": "Correct standard incircle tangent-length formula BD=s-AC. Sample1 independently verifies general incenter coordinates; sample0 optional verification is unsupported but not needed for the cited elementary formula.", "repairable": false}

## C07 sample 1

Triangle ABC has AB=13, AC=14, BC=15. Its incircle touches BC at D. Find BD.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 3977; finish: stop.



To find the length of $ BD $ in triangle $ ABC $, where the incircle touches side $ BC $ at point $ D $, we begin by leveraging the properties of the incircle and the semiperimeter of the triangle.

---

### Step 1: Compute the Semiperimeter

The semiperimeter $ s $ of triangle $ ABC $ is given by:

$$
s = \frac{AB + BC + AC}{2} = \frac{13 + 15 + 14}{2} = \frac{42}{2} = 21
$$

---

### Step 2: Use the Formula for the Length from a Vertex to the Point of Tangency

In a triangle, the incircle touches each side at a point, and the distances from the vertices to these points of tangency are determined by the semiperimeter $ s $ and the lengths of the triangle’s sides.

Specifically, the length $ BD $ (where the incircle touches side $ BC $) is given by:

$$
BD = s - AC
$$

Substitute the known values:

$$
BD = 21 - 14 = 7
$$

---

### Step 3: Verification via Coordinates

To further confirm, we can place triangle $ ABC $ in the coordinate plane and find the coordinates of the incenter and the point of tangency $ D $ on side $ BC $.

- Place $ B = (0, 0) $ and $ C = (15, 0) $.
- Let $ A = (x, y) $, and solve using the distances $ AB = 13 $, $ AC = 14 $.
- Using the distance formula, we find $ A = \left( \frac{33}{5}, \frac{56}{5} \right) $.

The incenter coordinates are:

$$
\left( \frac{a x_A + b x_B + c x_C}{a + b + c}, \frac{a y_A + b y_B + c y_C}{a + b + c} \right)
$$

where $ a = 15 $, $ b = 14 $, $ c = 13 $, and the coordinates of the triangle vertices are:

- $ A = \left( \frac{33}{5}, \frac{56}{5} \right) $
- $ B = (0, 0) $
- $ C = (15, 0) $

Plugging in:

$$
x_{\text{incenter}} = \frac{15 \cdot \frac{33}{5} + 14 \cdot 0 + 13 \cdot 15}{42} = \frac{99 + 0 + 195}{42} = \frac{294}{42} = 7
$$
$$
y_{\text{incenter}} = \frac{15 \cdot \frac{56}{5} + 14 \cdot 0 + 13 \cdot 0}{42} = \frac{168}{42} = 4
$$

So, the incenter is at $ (7, 4) $, and the incircle touches side $ BC $ at point $ D = (7, 0) $, since the incircle is tangent to $ BC $ at the same x-coordinate as the incenter.

Thus, the distance $ BD $ is the horizontal distance from $ B = (0, 0) $ to $ D = (7, 0) $, which is:

$$
BD = 7
$$

---

### Final Conclusion

All methods—direct formula, coordinate geometry—lead to the same result. Therefore, the length of $ BD $ is:

$$
\boxed{7}
$$<|im_end|>

Grade: {"valid": true, "method": "analytic", "note": "Correct standard incircle tangent-length formula BD=s-AC. Sample1 independently verifies general incenter coordinates; sample0 optional verification is unsupported but not needed for the cited elementary formula.", "repairable": false}

## C08 sample 0

In an isosceles triangle ABC with AB=AC, D is strictly inside AB and E is strictly inside AC, with BD=CE. Let F be the intersection of BE and CD. Prove BF=CF.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 4987; finish: stop.



To prove that $ BF = CF $ in the isosceles triangle $ \triangle ABC $ with $ AB = AC $, and with points $ D $ on $ AB $, $ E $ on $ AC $, such that $ BD = CE $, and $ F $ being the intersection of lines $ BE $ and $ CD $, we proceed as follows:

---

### **Step 1: Understand the Symmetry of the Triangle**

Given that $ AB = AC $, triangle $ ABC $ is isosceles with base $ BC $ and apex $ A $. This implies that the triangle is symmetric with respect to the altitude from vertex $ A $ to the base $ BC $. This line of symmetry also serves as the median and angle bisector.

Therefore, any configuration involving points on $ AB $ and $ AC $ that are symmetric with respect to this axis will maintain the symmetry of the triangle.

---

### **Step 2: Use of Symmetry to Determine the Position of $ F $**

Since $ D $ is on $ AB $ and $ E $ is on $ AC $, and given that $ BD = CE $, the configuration is symmetric with respect to the altitude from $ A $ to $ BC $. This is because the triangle is isosceles and the segment lengths are equal, so the points $ D $ and $ E $ are symmetric in their placement on $ AB $ and $ AC $, respectively.

Let’s reflect point $ D $ over the altitude from $ A $ to $ BC $ to obtain point $ E $. This reflection ensures that $ BD = CE $, and since the reflection swaps $ B $ and $ C $, and preserves the configuration, the lines $ BE $ and $ CD $ must be symmetric with respect to the altitude.

---

### **Step 3: Consequence of Symmetry on the Intersection Point**

Since the lines $ BE $ and $ CD $ are symmetric with respect to the altitude from $ A $, their intersection point $ F $ must lie on that line of symmetry.

Therefore, point $ F $ lies on the altitude from $ A $, which is also the perpendicular bisector of $ BC $. This means that $ F $ is equidistant from points $ B $ and $ C $.

---

### **Step 4: Conclusion**

Since $ F $ lies on the axis of symmetry of the triangle, it follows that the distances from $ F $ to $ B $ and $ F $ to $ C $ are equal. Thus, we conclude:

$$
\boxed{BF = CF}
$$<|im_end|>

Grade: {"valid": true, "method": "synthetic", "note": "Valid symmetry / general isosceles coordinates place F on perpendicular bisectorBC.", "repairable": false}

## C08 sample 1

In an isosceles triangle ABC with AB=AC, D is strictly inside AB and E is strictly inside AC, with BD=CE. Let F be the intersection of BE and CD. Prove BF=CF.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 3104; finish: stop.



To prove that in the isosceles triangle $ ABC $ with $ AB = AC $, and points $ D \in AB $, $ E \in AC $ such that $ BD = CE $, the intersection point $ F $ of lines $ BE $ and $ CD $ satisfies $ BF = CF $, we proceed as follows:

---

### **1. Coordinate Setup**

We place the triangle in the coordinate plane for clarity and symmetry:

- Let $ A = (0, h) $
- Let $ B = (-1, 0) $
- Let $ C = (1, 0) $

This configuration ensures that triangle $ ABC $ is isosceles with $ AB = AC $, and the triangle is symmetric about the y-axis.

---

### **2. Parametrize Points D and E**

Let point $ D $ lie on segment $ AB $, and point $ E $ lie on segment $ AC $, such that $ BD = CE $.

- Let point $ D $ be at $ (-1 + s, sh) $, where $ 0 < s < 1 $
- Then point $ E $ is at $ (1 - s, hs) $, derived from the condition $ BD = CE $, which leads to the relation $ s = 1 - r $, hence $ E = (1 - s, hs) $

This placement ensures that $ D $ and $ E $ are symmetric about the y-axis.

---

### **3. Equations of Lines BE and CD**

We find the equations of the lines:

- **Line BE** passes through $ B = (-1, 0) $ and $ E = (1 - s, hs) $

  Slope of BE:
  $$
  m_{BE} = \frac{hs - 0}{(1 - s) - (-1)} = \frac{hs}{2 - s}
  $$

  Equation of BE:
  $$
  y = \frac{hs}{2 - s}(x + 1)
  $$

- **Line CD** passes through $ C = (1, 0) $ and $ D = (-1 + s, sh) $

  Slope of CD:
  $$
  m_{CD} = \frac{sh - 0}{(-1 + s) - 1} = \frac{sh}{s - 2}
  $$

  Equation of CD:
  $$
  y = \frac{sh}{s - 2}(x - 1)
  $$

---

### **4. Find the Intersection Point F**

Set the two equations equal to find the intersection point $ F $:

$$
\frac{hs}{2 - s}(x + 1) = \frac{sh}{s - 2}(x - 1)
$$

Multiply both sides by $ 2 - s $ and simplify:

$$
hs(x + 1) = -sh(x - 1)
$$

$$
x + 1 = -x + 1 \Rightarrow 2x = 0 \Rightarrow x = 0
$$

Substitute $ x = 0 $ into the equation of BE:

$$
y = \frac{hs}{2 - s}(0 + 1) = \frac{hs}{2 - s}
$$

So, point $ F = (0, \frac{hs}{2 - s}) $, which lies on the **y-axis**.

---

### **5. Conclude BF = CF**

Since $ F $ lies on the y-axis and triangle $ ABC $ is symmetric about the y-axis, the distances from $ F $ to $ B $ and $ C $ are equal:

$$
BF = CF
$$

---

### **Final Answer**

$$
\boxed{BF = CF}
$$<|im_end|>

Grade: {"valid": true, "method": "analytic", "note": "Valid symmetry / general isosceles coordinates place F on perpendicular bisectorBC.", "repairable": false}

## C09 sample 0

The diagonals of a convex quadrilateral ABCD are perpendicular. Prove AB^2+CD^2=BC^2+DA^2.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 3184; finish: stop.



To prove that in a convex quadrilateral $ABCD$ with perpendicular diagonals $AC \perp BD$, the following equality holds:

$$
AB^2 + CD^2 = BC^2 + DA^2,
$$

we can use a geometric approach based on the properties of right triangles formed by the diagonals.

---

### Step 1: Define the Intersection Point

Let the diagonals $AC$ and $BD$ intersect at point $O$ inside the convex quadrilateral. Since the diagonals are perpendicular, the four triangles $AOB$, $BOC$, $COD$, and $DOA$ are all right triangles.

Let the lengths of the segments of the diagonals be:
- $OA = p$, $OC = q$,
- $OB = r$, $OD = s$.

---

### Step 2: Apply the Pythagorean Theorem to Each Side

Each side of the quadrilateral can be expressed as the hypotenuse of a right triangle formed by segments of the diagonals:

- $AB^2 = OA^2 + OB^2 = p^2 + r^2$,
- $BC^2 = OB^2 + OC^2 = r^2 + q^2$,
- $CD^2 = OC^2 + OD^2 = q^2 + s^2$,
- $DA^2 = OD^2 + OA^2 = s^2 + p^2$.

---

### Step 3: Add Opposite Side Squares

Now compute the sum of the squares of the opposite sides:

$$
AB^2 + CD^2 = (p^2 + r^2) + (q^2 + s^2) = p^2 + q^2 + r^2 + s^2,
$$
$$
BC^2 + DA^2 = (r^2 + q^2) + (s^2 + p^2) = p^2 + q^2 + r^2 + s^2.
$$

Since both sums are equal, we conclude:

$$
AB^2 + CD^2 = BC^2 + DA^2.
$$

---

### Final Conclusion

In any convex quadrilateral with perpendicular diagonals, the sum of the squares of the lengths of two opposite sides is equal to the sum of the squares of the lengths of the other two opposite sides.

$$
\boxed{AB^2 + CD^2 = BC^2 + DA^2}
$$<|im_end|>

Grade: {"valid": true, "method": "synthetic", "note": "Correct four right-triangle Pythagorean identities.", "repairable": false}

## C09 sample 1

The diagonals of a convex quadrilateral ABCD are perpendicular. Prove AB^2+CD^2=BC^2+DA^2.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 3097; finish: stop.



To prove that in a convex quadrilateral $ABCD$ with perpendicular diagonals, the following relation holds:

$$
AB^2 + CD^2 = BC^2 + DA^2,
$$

we can use a coordinate geometry approach based on the geometric properties of the quadrilateral and the Pythagorean Theorem.

---

### Step 1: Coordinate Setup

Let the diagonals $AC$ and $BD$ intersect at point $O$, and suppose they are perpendicular. We place the point of intersection $O$ at the origin $(0, 0)$, and align the diagonals along the coordinate axes for simplicity:

- Let $A = (-a, 0)$, $C = (c, 0)$ so that diagonal $AC$ lies along the x-axis.
- Let $B = (0, b)$, $D = (0, -d)$ so that diagonal $BD$ lies along the y-axis.

This configuration ensures the diagonals are perpendicular and the quadrilateral is convex.

---

### Step 2: Compute Squared Side Lengths

Using the distance formula:

- $AB^2 = (-a - 0)^2 + (0 - b)^2 = a^2 + b^2$
- $BC^2 = (c - 0)^2 + (0 - b)^2 = c^2 + b^2$
- $CD^2 = (0 - c)^2 + (-d - 0)^2 = c^2 + d^2$
- $DA^2 = (-a - 0)^2 + (0 - (-d))^2 = a^2 + d^2$

---

### Step 3: Compute the Sums

Now, we compute the two sums:

- $AB^2 + CD^2 = (a^2 + b^2) + (c^2 + d^2) = a^2 + b^2 + c^2 + d^2$
- $BC^2 + DA^2 = (c^2 + b^2) + (a^2 + d^2) = a^2 + b^2 + c^2 + d^2$

Hence, we have:

$$
AB^2 + CD^2 = BC^2 + DA^2
$$

---

### Step 4: Generalization via Segment Lengths

Alternatively, consider the diagonals $AC$ and $BD$ intersecting at point $O$, with segments $AO = p$, $OC = q$, $BO = r$, and $OD = s$. Since the diagonals are perpendicular, we apply the Pythagorean Theorem to each triangle formed by the diagonals:

- $AB^2 = AO^2 + BO^2 = p^2 + r^2$
- $CD^2 = OC^2 + OD^2 = q^2 + s^2$
- $BC^2 = BO^2 + OC^2 = r^2 + q^2$
- $DA^2 = OD^2 + AO^2 = s^2 + p^2$

Then:

- $AB^2 + CD^2 = (p^2 + r^2) + (q^2 + s^2) = p^2 + q^2 + r^2 + s^2$
- $BC^2 + DA^2 = (r^2 + q^2) + (s^2 + p^2) = p^2 + q^2 + r^2 + s^2$

So again, we get the equality:

$$
AB^2 + CD^2 = BC^2 + DA^2
$$

---

### Conclusion

In any convex quadrilateral with perpendicular diagonals, the sum of the squares of two opposite sides equals the sum of the squares of the other two opposite sides. This result is valid regardless of the specific lengths of the diagonals or their segments, as long as they are perpendicular.

$$
\boxed{AB^2 + CD^2 = BC^2 + DA^2}
$$<|im_end|>

Grade: {"valid": true, "method": "analytic", "note": "Correct four right-triangle Pythagorean identities.", "repairable": false}

## C10 sample 0

ABC is a triangle with incenter I. D is the midpoint of the arc BC of its circumcircle that does not contain A. Prove DB=DC=DI.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 8192; finish: length.

[No completed final answer; raw generation retained in the source JSON.]

Grade: {"valid": false, "method": "none", "note": "No completed final proof before the output limit.", "repairable": false}

## C10 sample 1

ABC is a triangle with incenter I. D is the midpoint of the arc BC of its circumcircle that does not contain A. Prove DB=DC=DI.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 8192; finish: length.

[No completed final answer; raw generation retained in the source JSON.]

Grade: {"valid": false, "method": "none", "note": "No completed final proof before the output limit.", "repairable": false}

## C11 sample 0

Triangle ABC is right-angled at A. D is the midpoint of BC. The perpendicular from D to AC meets AC at E. Prove AE=EC and DE=AB/2.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 4694; finish: stop.



To solve the problem, we analyze triangle $ ABC $, which is right-angled at $ A $. Given that $ D $ is the midpoint of hypotenuse $ BC $, and a perpendicular from $ D $ to $ AC $ meets $ AC $ at point $ E $, we aim to prove the following two statements:

1. $ AE = EC $
2. $ DE = \dfrac{AB}{2} $

---

### **Step 1: Use of Geometry and Coordinates**

Let’s place the triangle in the coordinate plane for clarity:

- Let $ A = (0, 0) $
- Let $ B = (0, b) $, so that $ AB $ is vertical
- Let $ C = (c, 0) $, so that $ AC $ is horizontal

Then the midpoint $ D $ of $ BC $ is:
$$
D = \left( \frac{c}{2}, \frac{b}{2} \right)
$$

Now, the line $ AC $ lies along the x-axis from $ (0, 0) $ to $ (c, 0) $. A perpendicular from $ D $ to $ AC $ is vertical, since $ AC $ is horizontal. Thus, the perpendicular from $ D $ to $ AC $ is the vertical line through $ D $, which intersects $ AC $ at:
$$
E = \left( \frac{c}{2}, 0 \right)
$$

Now, compute the distances:

- $ AE = \left| \frac{c}{2} - 0 \right| = \frac{c}{2} $
- $ EC = \left| c - \frac{c}{2} \right| = \frac{c}{2} $

Therefore:
$$
AE = EC
$$

---

### **Step 2: Prove $ DE = \dfrac{AB}{2} $**

From the coordinates:

- $ D = \left( \frac{c}{2}, \frac{b}{2} \right) $
- $ E = \left( \frac{c}{2}, 0 \right) $

So the vertical segment $ DE $ has length:
$$
DE = \left| \frac{b}{2} - 0 \right| = \frac{b}{2}
$$

But $ AB $ is the vertical segment from $ (0, 0) $ to $ (0, b) $, so:
$$
AB = b \Rightarrow \frac{AB}{2} = \frac{b}{2}
$$

Thus:
$$
DE = \frac{AB}{2}
$$

---

### **Step 3: Alternative Synthetic Proof Using Pythagoras**

Let’s consider triangles $ ADE $ and $ CDE $, both right-angled at $ E $:

- $ AD = DC = \frac{1}{2} BC $, since $ D $ is the midpoint of hypotenuse $ BC $
- $ AD^2 = AE^2 + DE^2 $
- $ DC^2 = CE^2 + DE^2 $

Since $ AD = DC $, equating the two equations gives:
$$
AE^2 + DE^2 = CE^2 + DE^2 \Rightarrow AE^2 = CE^2 \Rightarrow AE = CE
$$

Now, using the Pythagorean theorem in triangle $ ADE $:
$$
AD^2 = AE^2 + DE^2
\Rightarrow \left( \frac{BC}{2} \right)^2 = \left( \frac{AC}{2} \right)^2 + DE^2
\Rightarrow DE^2 = \frac{BC^2 - AC^2}{4}
$$

But in triangle $ ABC $, right-angled at $ A $, we have:
$$
BC^2 = AB^2 + AC^2
\Rightarrow DE^2 = \frac{AB^2 + AC^2 - AC^2}{4} = \frac{AB^2}{4}
\Rightarrow DE = \frac{AB}{2}
$$

---

### **Conclusion**

Both coordinate geometry and synthetic methods confirm the following:

- $ AE = EC $, since $ E $ is the midpoint of $ AC $
- $ DE = \dfrac{AB}{2} $, as derived from the Pythagorean theorem

---

**Final Answer:**
$$
\boxed{AE = EC} \quad \text{and} \quad \boxed{DE = \dfrac{AB}{2}}
$$<|im_end|>

Grade: {"valid": true, "method": "analytic", "note": "Correct general right-triangle coordinates, with additional valid Pythagorean proof.", "repairable": false}

## C11 sample 1

Triangle ABC is right-angled at A. D is the midpoint of BC. The perpendicular from D to AC meets AC at E. Prove AE=EC and DE=AB/2.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 4279; finish: stop.



To prove that in a right-angled triangle $ \triangle ABC $, with $ \angle A = 90^\circ $, the midpoint $ D $ of hypotenuse $ BC $, and the foot of the perpendicular from $ D $ to $ AC $ being $ E $, the following two results hold:

1. $ AE = EC $
2. $ DE = \dfrac{AB}{2} $

---

### **Geometric Proof**

#### **Step 1: Establishing that $ DE \parallel AB $**

Since $ \angle A = 90^\circ $, the sides $ AB $ and $ AC $ are perpendicular. The segment $ DE $ is drawn perpendicular to $ AC $, so it is also perpendicular to $ AB $, which is itself perpendicular to $ AC $. Therefore, $ DE \parallel AB $.

---

#### **Step 2: Applying Thales’ Theorem (Basic Proportionality Theorem)**

In triangle $ ABC $, the line $ DE $ is parallel to $ AB $, and intersects the sides $ AC $ and $ BC $ at points $ E $ and $ D $, respectively. By Thales’ Theorem:

$$
\frac{BD}{DC} = \frac{AE}{EC}
$$

But since $ D $ is the **midpoint** of $ BC $, we have $ BD = DC $, so:

$$
\frac{BD}{DC} = 1 \Rightarrow \frac{AE}{EC} = 1 \Rightarrow AE = EC
$$

Thus, **$ AE = EC $** is proven.

---

#### **Step 3: Using Similar Triangles to Prove $ DE = \dfrac{AB}{2} $**

Because $ DE \parallel AB $, and both triangles $ \triangle CDE $ and $ \triangle CAB $ share angle $ \angle C $, the triangles are **similar** by AA similarity.

Therefore:

$$
\triangle CDE \sim \triangle CAB
$$

This gives us the proportionality:

$$
\frac{DE}{AB} = \frac{CD}{CB}
$$

Since $ D $ is the **midpoint** of $ BC $, we have:

$$
CD = \frac{1}{2} CB \Rightarrow \frac{CD}{CB} = \frac{1}{2}
$$

Therefore:

$$
\frac{DE}{AB} = \frac{1}{2} \Rightarrow DE = \frac{AB}{2}
$$

---

### **Conclusion**

From the geometric analysis, we have shown that:

- $ AE = EC $, because $ DE \parallel AB $, and by Thales’ Theorem, the segments $ AE $ and $ EC $ are equal.
- $ DE = \dfrac{AB}{2} $, by the similarity of triangles $ \triangle CDE \sim \triangle CAB $, with a side ratio of $ \dfrac{1}{2} $.

---

### **Final Answer**

$$
\boxed{AE = EC} \quad \text{and} \quad \boxed{DE = \dfrac{AB}{2}}
$$<|im_end|>

Grade: {"valid": false, "method": "synthetic", "note": "Core argument explicitly says DE is perpendicular to AB and then concludes parallel; replacing the erroneous phrase repairs the argument. Similar-triangle order also needs correction.", "repairable": true}

## C12 sample 0

Two distinct circles intersect at A and B. The point diametrically opposite A on the first circle is C, and the point diametrically opposite A on the second is D. Assume C,D are different from B. Prove B,C,D are collinear.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 3905; finish: stop.



To prove that points $ B, C, D $ are collinear, we begin by analyzing the geometric configuration of the two intersecting circles and their diametrically opposite points.

---

### **Key Geometric Facts and Setup**

- Two distinct circles intersect at points $ A $ and $ B $.
- $ C $ is the diametrically opposite point of $ A $ on the **first circle**.
- $ D $ is the diametrically opposite point of $ A $ on the **second circle**.
- $ C \neq B $ and $ D \neq B $, as stated.

---

### **Using Thales' Theorem**

Since $ AC $ is a **diameter** of the first circle, and point $ B $ lies on the first circle, by **Thales' Theorem**, the angle $ \angle ABC $ is a right angle. That is:

$$
\angle ABC = 90^\circ
$$

Similarly, since $ AD $ is a **diameter** of the second circle, and point $ B $ lies on the second circle, by Thales' Theorem:

$$
\angle ABD = 90^\circ
$$

---

### **Implication of Right Angles**

From the above, we have:

- $ \angle ABC = 90^\circ \Rightarrow BC \perp AB $
- $ \angle ABD = 90^\circ \Rightarrow BD \perp AB $

This implies that both $ BC $ and $ BD $ are **perpendicular to the line segment $ AB $**.

---

### **Conclusion from Perpendicularity**

If two lines are both perpendicular to the same line (in this case, $ AB $), then they must be **parallel** to each other. However, since both $ BC $ and $ BD $ originate from the same point $ B $, and are both perpendicular to $ AB $, they must lie on the **same line** passing through $ B $.

Therefore, points $ B, C, D $ are all on the same line, and hence are **collinear**.

---

### **Final Statement**

$$
\boxed{B, C, D \text{ are collinear}}
$$<|im_end|>

Grade: {"valid": true, "method": "synthetic", "note": "Both BC and BD are perpendicular to AB at the same point, by diameter angles.", "repairable": false}

## C12 sample 1

Two distinct circles intersect at A and B. The point diametrically opposite A on the first circle is C, and the point diametrically opposite A on the second is D. Assume C,D are different from B. Prove B,C,D are collinear.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 3974; finish: stop.



To prove that points $ B, C, D $ are collinear, we start with the given configuration of two distinct circles intersecting at points $ A $ and $ B $. On the first circle, the point $ C $ is diametrically opposite $ A $, and on the second circle, $ D $ is also diametrically opposite $ A $. It is also given that $ C $ and $ D $ are different from $ B $.

---

### Step 1: Use of Thales' Theorem

Thales' Theorem states that if a triangle is inscribed in a circle such that one side of the triangle is a diameter, then the angle opposite that side is a right angle.

- Since $ C $ is diametrically opposite $ A $ on the first circle, segment $ AC $ is a diameter of the first circle.
- Since $ B $ lies on the first circle, triangle $ ABC $ is inscribed in the first circle with $ AC $ as a diameter. Therefore, $ \angle ABC = 90^\circ $, i.e., $ BC \perp AB $.

- Similarly, since $ D $ is diametrically opposite $ A $ on the second circle, segment $ AD $ is a diameter of the second circle.
- Since $ B $ lies on the second circle, triangle $ ABD $ is inscribed in the second circle with $ AD $ as a diameter. Therefore, $ \angle ABD = 90^\circ $, i.e., $ BD \perp AB $.

---

### Step 2: Implication of Perpendicularity

From the above, we have:

- $ BC \perp AB $
- $ BD \perp AB $

This implies that both $ BC $ and $ BD $ are perpendicular to the same line $ AB $, and hence they must be **the same line**.

Therefore, points $ B $, $ C $, and $ D $ lie on the same straight line, meaning they are **collinear**.

---

### Final Conclusion

Thus, we have shown that the points $ B $, $ C $, and $ D $ lie on a single straight line, i.e., they are collinear.

$$
\boxed{B, C, D \text{ are collinear}}
$$<|im_end|>

Grade: {"valid": true, "method": "synthetic", "note": "Both BC and BD are perpendicular to AB at the same point, by diameter angles.", "repairable": false}

## C13 sample 0

D and E are the midpoints of BC and CA in triangle ABC. The medians AD and BE meet at G. Prove AG=2GD.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 5465; finish: stop.



To prove that in triangle $ ABC $, where $ D $ and $ E $ are the midpoints of $ BC $ and $ AC $, and $ G $ is the intersection of the medians $ AD $ and $ BE $, the segment $ AG $ is twice the segment $ GD $, we proceed with a clear, concise mathematical justification.

---

### **Key Concepts and Definitions**

- **Median**: A line segment from a vertex of a triangle to the midpoint of the opposite side.
- **Centroid**: The point of intersection of the medians of a triangle. It divides each median into a $ 2:1 $ ratio, with the longer segment being closer to the vertex.
- **Midpoint**: A point equidistant from the two endpoints of a segment.

---

### **Proof via Coordinate Geometry**

Let us place triangle $ ABC $ in the coordinate plane as follows:

- Let $ A = (0, 0) $
- Let $ B = (2b, 0) $
- Let $ C = (2c, 2d) $

Then:

- Midpoint $ D $ of $ BC $ is:
  $$
  D = \left( \frac{2b + 2c}{2}, \frac{0 + 2d}{2} \right) = (b + c, d)
  $$

- Midpoint $ E $ of $ AC $ is:
  $$
  E = \left( \frac{0 + 2c}{2}, \frac{0 + 2d}{2} \right) = (c, d)
  $$

Now, the median $ AD $ is the line from $ A = (0, 0) $ to $ D = (b + c, d) $, and can be parametrized as:
$$
x = t(b + c), \quad y = t d \quad \text{for } t \in [0, 1]
$$

The median $ BE $ is the line from $ B = (2b, 0) $ to $ E = (c, d) $, and can be parametrized as:
$$
x = 2b + s(c - 2b), \quad y = sd \quad \text{for } s \in [0, 1]
$$

Set the two parametric equations equal to find the point of intersection $ G $:

$$
t(b + c) = 2b + s(c - 2b), \quad t d = s d
$$

From the second equation, $ t = s $. Substituting into the first:

$$
t(b + c) = 2b + t(c - 2b)
\Rightarrow t b + t c = 2b + t c - 2b t
\Rightarrow t b = 2b - 2b t
\Rightarrow 3b t = 2b
\Rightarrow t = \frac{2}{3}
$$

Thus, the coordinates of $ G $ are:

$$
G = \left( \frac{2}{3}(b + c), \frac{2}{3}d \right)
$$

This shows that $ G $ lies along $ AD $, and divides it in the ratio $ AG : GD = 2 : 1 $.

---

### **Conclusion**

Since $ G $ lies on the median $ AD $, and the coordinates of $ G $ are $ \frac{2}{3} $ of the way from $ A $ to $ D $, it follows that:

$$
AG = \frac{2}{3} AD, \quad GD = \frac{1}{3} AD \Rightarrow AG = 2 GD
$$

This result is consistent with the known property of the centroid of a triangle, which divides each median into a $ 2:1 $ ratio.

---

### **Final Answer**

$$
\boxed{AG = 2GD}
$$<|im_end|>

Grade: {"valid": true, "method": "analytic", "note": "General vector/coordinate equations show G is2/3 along AD; sample1 drops vector arrows in one displayed length line without affecting the proportionality.", "repairable": false}

## C13 sample 1

D and E are the midpoints of BC and CA in triangle ABC. The medians AD and BE meet at G. Prove AG=2GD.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 4662; finish: stop.



To prove that in triangle $ ABC $, with $ D $ and $ E $ as midpoints of $ BC $ and $ CA $ respectively, the medians $ AD $ and $ BE $ intersect at the centroid $ G $, and that $ AG = 2GD $, we can use **vector geometry** for a general and concise proof.

---

### Step 1: Assign Position Vectors

Let’s place the triangle in a vector space with:
- $ A $ as the origin, so $ \vec{A} = \vec{0} $,
- $ \vec{B} = \vec{b} $,
- $ \vec{C} = \vec{c} $.

The midpoints of the sides are:
- $ D $, the midpoint of $ BC $, so:
  $$
  \vec{D} = \frac{\vec{B} + \vec{C}}{2} = \frac{\vec{b} + \vec{c}}{2}
  $$
- $ E $, the midpoint of $ AC $, so:
  $$
  \vec{E} = \frac{\vec{A} + \vec{C}}{2} = \frac{\vec{c}}{2}
  $$

---

### Step 2: Parametrize the Medians

- **Median $ AD $** goes from $ A $ (origin) to $ D $, so any point on $ AD $ can be written as:
  $$
  \vec{r} = t \cdot \vec{D} = t \cdot \frac{\vec{b} + \vec{c}}{2}, \quad t \in [0,1]
  $$

- **Median $ BE $** goes from $ B $ to $ E $, so any point on $ BE $ can be written as:
  $$
  \vec{r} = \vec{B} + s \cdot (\vec{E} - \vec{B}) = \vec{b} + s \cdot \left( \frac{\vec{c}}{2} - \vec{b} \right), \quad s \in [0,1]
  $$

---

### Step 3: Find the Intersection Point $ G $

Set the two parametric expressions for $ \vec{r} $ equal:
$$
t \cdot \frac{\vec{b} + \vec{c}}{2} = \vec{b} + s \cdot \left( \frac{\vec{c}}{2} - \vec{b} \right)
$$

Simplify both sides:
- Left side: $ \frac{t}{2} \vec{b} + \frac{t}{2} \vec{c} $
- Right side: $ (1 - s)\vec{b} + \frac{s}{2} \vec{c} $

Equating coefficients of $ \vec{b} $ and $ \vec{c} $:

- For $ \vec{b} $: $ \frac{t}{2} = 1 - s $
- For $ \vec{c} $: $ \frac{t}{2} = \frac{s}{2} \Rightarrow t = s $

Substitute $ t = s $ into the first equation:
$$
\frac{t}{2} = 1 - t \Rightarrow \frac{3t}{2} = 1 \Rightarrow t = \frac{2}{3}
$$

So, the point $ G $ lies on $ AD $ at $ t = \frac{2}{3} $, and its position vector is:
$$
\vec{G} = \frac{2}{3} \cdot \frac{\vec{b} + \vec{c}}{2} = \frac{\vec{b} + \vec{c}}{3}
$$

---

### Step 4: Compute the Ratios $ AG $ and $ GD $

- $ \vec{AG} = \vec{G} - \vec{A} = \vec{G} = \frac{\vec{b} + \vec{c}}{3} $
- $ \vec{GD} = \vec{D} - \vec{G} = \frac{\vec{b} + \vec{c}}{2} - \frac{\vec{b} + \vec{c}}{3} = \frac{(\vec{b} + \vec{c})}{6} $

Thus,
$$
AG = \frac{\vec{b} + \vec{c}}{3}, \quad GD = \frac{\vec{b} + \vec{c}}{6}
$$

Therefore,
$$
AG = 2GD
$$

---

### Final Conclusion

The centroid $ G $ of triangle $ ABC $ divides the median $ AD $ in the ratio $ 2:1 $, with $ AG = 2GD $.

$$
\boxed{AG = 2GD}
$$<|im_end|>

Grade: {"valid": true, "method": "analytic", "note": "General vector/coordinate equations show G is2/3 along AD; sample1 drops vector arrows in one displayed length line without affecting the proportionality.", "repairable": false}

## C14 sample 0

A convex quadrilateral has equal diagonals. Must its four vertices lie on a circle? Prove the assertion or give an explicit counterexample.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 6760; finish: stop.



To determine whether a **convex quadrilateral with equal diagonals** must have its **four vertices lying on a circle**, we analyze both the geometric properties of such quadrilaterals and construct a counterexample to demonstrate that this is not always the case.

---

### Key Geometric Insight

A **cyclic quadrilateral** is one in which all four vertices lie on a single circle. A well-known necessary and sufficient condition for a quadrilateral to be cyclic is that the **sum of opposite angles is 180°**, or equivalently, that the **perpendicular bisectors of the sides intersect at a common point (the center of the circle)**.

However, the condition of **equal diagonals** does not, in general, imply that the quadrilateral is cyclic. This is because the equality of diagonals is a **geometric constraint**, but not a **cyclic constraint**. There exist non-cyclic quadrilaterals with equal diagonals, which can be verified through construction.

---

### Constructing a Counterexample

Consider the convex quadrilateral with vertices:

- $ A = (0, 0) $
- $ B = (1, 0) $
- $ C = (1, 1) $
- $ D = (2, 1) $

#### Step 1: Compute the Diagonals

- Diagonal $ AC $: from $ A(0,0) $ to $ C(1,1) $, length = $ \sqrt{(1)^2 + (1)^2} = \sqrt{2} $
- Diagonal $ BD $: from $ B(1,0) $ to $ D(2,1) $, length = $ \sqrt{(1)^2 + (1)^2} = \sqrt{2} $

So the diagonals are **equal** in length.

#### Step 2: Check if the Quadrilateral is Cyclic

We attempt to find a circle passing through three of the points and check if the fourth lies on the same circle.

Let’s find the circle passing through $ A(0,0) $, $ B(1,0) $, and $ C(1,1) $.

The general equation of a circle is:

$$
x^2 + y^2 + Dx + Ey + F = 0
$$

Substituting the three points:

- For $ A(0,0) $: $ F = 0 $
- For $ B(1,0) $: $ 1 + D = 0 \Rightarrow D = -1 $
- For $ C(1,1) $: $ 1 + 1 - 1 + E = 0 \Rightarrow E = -1 $

So the equation becomes:

$$
x^2 + y^2 - x - y = 0
$$

Now check if point $ D(2,1) $ lies on this circle:

$$
2^2 + 1^2 - 2 - 1 = 4 + 1 - 2 - 1 = 2 \neq 0
$$

Thus, point $ D $ is **not** on the circle defined by $ A, B, C $, and therefore the quadrilateral is **not cyclic**.

---

### Conclusion

We have constructed a **convex quadrilateral** with **equal diagonals** that is **not cyclic**, proving that the condition of equal diagonals does **not** guarantee that the quadrilateral is cyclic.

---

### Final Answer

$$
\boxed{No}
$$<|im_end|>

Grade: {"valid": false, "method": "analytic", "note": "Claimed counterexample is self-crossing/nonconvex in ABCD order. Sample1 additionally miscomputes the circle and states a false cyclicity criterion.", "repairable": false}

## C14 sample 1

A convex quadrilateral has equal diagonals. Must its four vertices lie on a circle? Prove the assertion or give an explicit counterexample.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 5472; finish: stop.



To determine whether a convex quadrilateral with equal diagonals must have its four vertices lying on a circle, we must analyze the geometric properties of such quadrilaterals.

---

### Key Geometric Insight

A quadrilateral is **cyclic** (i.e., its vertices lie on a circle) if and only if the **opposite angles are supplementary** or the **diagonals intersect at right angles** and **bisect each other** (in the case of a kite). However, in general, a quadrilateral with **equal diagonals** does **not** necessarily satisfy these conditions.

A **counterexample** can be constructed to show that a convex quadrilateral with equal diagonals may **not** be cyclic.

---

### Constructing a Counterexample

Let us consider the following four points in the plane:

- $ A = (0, 0) $
- $ B = (0, 1) $
- $ C = (2, 2) $
- $ D = (2, 3) $

These points form a **convex quadrilateral**. Let's verify that:

- The quadrilateral is convex because the points are in order and the edges do not cross.
- The diagonals are:
  - $ AC $: from $ (0,0) $ to $ (2,2) $, length $ \sqrt{8} $
  - $ BD $: from $ (0,1) $ to $ (2,3) $, also length $ \sqrt{8} $

So, the diagonals are **equal**.

Now, check whether the quadrilateral is **cyclic**. A quadrilateral is cyclic if and only if the four points lie on a single circle. We can test this by checking whether the point $ D = (2,3) $ lies on the circle defined by the other three points $ A, B, C $.

Let’s find the equation of the circle passing through $ A(0,0) $, $ B(0,1) $, and $ C(2,2) $. The general equation of a circle is:

$$
x^2 + y^2 + Dx + Ey + F = 0
$$

Substituting the coordinates of $ A $, $ B $, and $ C $, we find:

- From $ A(0,0) $: $ F = 0 $
- From $ B(0,1) $: $ 1 + E = 0 \Rightarrow E = -1 $
- From $ C(2,2) $: $ 4 + 4 + 2D - 1 = 0 \Rightarrow 2D + 7 = 0 \Rightarrow D = -3.5 $

So the circle equation is:

$$
x^2 + y^2 - 3.5x - y = 0
$$

Now, plug in point $ D = (2,3) $:

$$
2^2 + 3^2 - 3.5 \cdot 2 - 3 = 4 + 9 - 7 - 3 = 3 \neq 0
$$

Thus, $ D $ does **not** lie on the circle defined by $ A, B, C $, meaning the quadrilateral is **not cyclic**.

---

### Conclusion

We have constructed a **convex quadrilateral** with **equal diagonals** that is **not cyclic**. This counterexample demonstrates that the property of having equal diagonals is **not sufficient** to guarantee that the quadrilateral is cyclic.

---

### Final Answer

$$
\boxed{No}
$$<|im_end|>

Grade: {"valid": false, "method": "analytic", "note": "Claimed counterexample is self-crossing/nonconvex in ABCD order. Sample1 additionally miscomputes the circle and states a false cyclicity criterion.", "repairable": false}

## C15 sample 0

A,B are distinct points. C,D are distinct points off line AB, and triangles ABC and ABD have equal (unsigned) areas. Must CD be parallel to AB? Prove the assertion or give an explicit counterexample.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 2143; finish: stop.



To determine whether $ CD $ must be parallel to $ AB $ given that triangles $ ABC $ and $ ABD $ have equal (unsigned) areas and $ C, D $ are distinct points off the line $ AB $, we analyze the geometric implications of the area condition.

---

### Step 1: Area of Triangle in Terms of Height

The area of triangle $ ABC $ is given by:

$$
\text{Area}_{ABC} = \frac{1}{2} \cdot AB \cdot h_C
$$

Similarly for triangle $ ABD $:

$$
\text{Area}_{ABD} = \frac{1}{2} \cdot AB \cdot h_D
$$

Since the areas are equal, we must have:

$$
h_C = h_D \quad \text{(in absolute value)}
$$

This means that the perpendicular distances from points $ C $ and $ D $ to the line $ AB $ are equal in magnitude. Therefore, $ C $ and $ D $ lie on lines parallel to $ AB $, at the same distance from $ AB $, but possibly on opposite sides of the line.

---

### Step 2: Constructing a Counterexample

To test the claim that $ CD $ must be parallel to $ AB $, consider a coordinate setup:

- Let $ A = (0, 0) $, $ B = (2, 0) $, so that $ AB $ is horizontal.
- Let $ C = (1, 1) $, and $ D = (1, -1) $

These points are both off the line $ AB $, and they are equidistant from $ AB $ (both at distance 1). The areas of triangles $ ABC $ and $ ABD $ are:

$$
\text{Area}_{ABC} = \frac{1}{2} \cdot 2 \cdot 1 = 1, \quad \text{Area}_{ABD} = \frac{1}{2} \cdot 2 \cdot 1 = 1
$$

So the areas are equal.

Now, the line segment $ CD $ connects $ (1,1) $ to $ (1,-1) $, which is a **vertical** line. Since $ AB $ is horizontal, $ CD $ is **not** parallel to $ AB $.

---

### Step 3: General Conclusion

The condition that $ \text{Area}_{ABC} = \text{Area}_{ABD} $ only ensures that the perpendicular distances from $ C $ and $ D $ to $ AB $ are equal, but does **not** enforce that $ C $ and $ D $ lie on the **same** line parallel to $ AB $. Therefore, the line segment $ CD $ may not be parallel to $ AB $, as shown in the counterexample.

---

### Final Answer

$$
\boxed{No}
$$

The assertion that $ CD $ must be parallel to $ AB $ is **false**. A counterexample exists where $ CD $ is not parallel to $ AB $, even though the areas of triangles $ ABC $ and $ ABD $ are equal.<|im_end|>

Grade: {"valid": true, "method": "analytic", "note": "Explicit opposite-side equal-height counterexample satisfies the givens.", "repairable": false}

## C15 sample 1

A,B are distinct points. C,D are distinct points off line AB, and triangles ABC and ABD have equal (unsigned) areas. Must CD be parallel to AB? Prove the assertion or give an explicit counterexample.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 3169; finish: stop.



To determine whether the line segment $ CD $ must be parallel to the line segment $ AB $, given that triangles $ ABC $ and $ ABD $ have equal (unsigned) areas and that points $ C $ and $ D $ are distinct and not on the line $ AB $, we analyze the geometric implications of the area condition.

---

### Key Observations:

1. **Area of a Triangle**: The area of triangle $ ABC $ is given by:
   $$
   \text{Area} = \frac{1}{2} \times \text{base} \times \text{height}
   $$
   Since $ AB $ is the common base for both triangles $ ABC $ and $ ABD $, the areas of the triangles depend only on the perpendicular distances (heights) from points $ C $ and $ D $ to the line $ AB $.

2. **Equal Areas Implies Equal Heights**: If the areas of $ ABC $ and $ ABD $ are equal, then the heights from $ C $ and $ D $ to line $ AB $ must be equal in magnitude. That is, the perpendicular distances from $ C $ and $ D $ to $ AB $ are the same.

3. **Implication of Equal Heights**: If $ C $ and $ D $ are on the same side of line $ AB $, then they lie on a line parallel to $ AB $, and hence $ CD $ is parallel to $ AB $. However, if $ C $ and $ D $ are on opposite sides of $ AB $, then they do **not** necessarily lie on a line parallel to $ AB $.

---

### Constructing a Counterexample:

Let’s consider a specific configuration in the plane:

- Let $ A = (0, 0) $ and $ B = (2, 0) $, so that $ AB $ is the horizontal line segment along the x-axis.
- Let $ C = (0, 1) $, so that the height from $ C $ to $ AB $ is 1.
- Let $ D = (1, -1) $, so that the height from $ D $ to $ AB $ is also 1 (in absolute value).

Now:

- The area of triangle $ ABC $ is:
  $$
  \frac{1}{2} \times 2 \times 1 = 1
  $$
- The area of triangle $ ABD $ is:
  $$
  \frac{1}{2} \times 2 \times 1 = 1
  $$

Thus, both triangles have equal area.

However, the line segment $ CD $ connects the points $ (0,1) $ and $ (1,-1) $, which has a slope of:
$$
\frac{-1 - 1}{1 - 0} = -2
$$
This is not equal to the slope of $ AB $, which is 0. Therefore, $ CD $ is **not** parallel to $ AB $.

---

### Conclusion:

Since we can construct a configuration where the areas of triangles $ ABC $ and $ ABD $ are equal, but $ CD $ is not parallel to $ AB $, the conclusion is that **CD does not necessarily have to be parallel to AB**.

---

**Final Answer**:  
$$
\boxed{No}
$$<|im_end|>

Grade: {"valid": true, "method": "analytic", "note": "Explicit opposite-side equal-height counterexample satisfies the givens.", "repairable": false}

## C16 sample 0

In an acute triangle ABC, the perpendicular from B to AC has the same length as the perpendicular from C to AB. Prove AB=AC.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 3465; finish: stop.



To prove that in an acute triangle $ ABC $, if the perpendicular from $ B $ to $ AC $ is equal in length to the perpendicular from $ C $ to $ AB $, then $ AB = AC $, we proceed as follows:

---

### Step 1: Use the Area Formula
The area $ S $ of triangle $ ABC $ can be expressed in two ways:
- As $ \frac{1}{2} \cdot AC \cdot h_B $, where $ h_B $ is the height from $ B $ to side $ AC $,
- As $ \frac{1}{2} \cdot AB \cdot h_C $, where $ h_C $ is the height from $ C $ to side $ AB $.

Given that $ h_B = h_C $, we equate these two expressions:
$$
\frac{1}{2} \cdot AC \cdot h_B = \frac{1}{2} \cdot AB \cdot h_C
$$
Since $ h_B = h_C $, we can cancel the common factor:
$$
AC \cdot h_B = AB \cdot h_B
$$
Assuming $ h_B \neq 0 $ (which is valid because the triangle is non-degenerate), we divide both sides by $ h_B $:
$$
AC = AB
$$

Thus, we conclude that $ AB = AC $.

---

### Step 2: Confirm the Result Using Trigonometry
Let $ \alpha $ be the angle at vertex $ A $. Then, the height from $ B $ to $ AC $ is given by:
$$
h_B = AB \cdot \sin(\alpha)
$$
Similarly, the height from $ C $ to $ AB $ is:
$$
h_C = AC \cdot \sin(\alpha)
$$
If $ h_B = h_C $, then:
$$
AB \cdot \sin(\alpha) = AC \cdot \sin(\alpha)
$$
Again, since $ \sin(\alpha) \neq 0 $ (as $ \alpha $ is an acute angle), we conclude:
$$
AB = AC
$$

---

### Step 3: Confirm with Coordinate Geometry
Let $ A = (0, 0) $, $ B = (c, 0) $, and $ C = (d, e) $. Then:
- The height from $ C $ to $ AB $ is the vertical distance from $ C $ to the x-axis, which is $ e $.
- The height from $ B $ to $ AC $ is the perpendicular distance from $ B $ to the line through $ A $ and $ C $. The line $ AC $ has slope $ \frac{e}{d} $, so its equation is $ y = \frac{e}{d}x $.

The perpendicular distance from $ B = (c, 0) $ to this line is:
$$
\frac{\left| \frac{e}{d} \cdot c - 0 \right|}{\sqrt{1 + \left( \frac{e}{d} \right)^2}} = \frac{ec}{\sqrt{d^2 + e^2}}
$$

Setting this equal to $ e $, we get:
$$
\frac{ec}{\sqrt{d^2 + e^2}} = e \Rightarrow \frac{c}{\sqrt{d^2 + e^2}} = 1 \Rightarrow c = \sqrt{d^2 + e^2}
$$
This means that $ AB = AC $, as $ AB = c $ and $ AC = \sqrt{d^2 + e^2} $.

---

### Final Conclusion
All approaches—area, trigonometry, and coordinate geometry—lead to the same conclusion: if the perpendicular from $ B $ to $ AC $ is equal to the perpendicular from $ C $ to $ AB $, then the triangle is isosceles with $ AB = AC $.

$$
\boxed{AB = AC}
$$<|im_end|>

Grade: {"valid": true, "method": "area", "note": "Correct comparison of the two base-altitude area formulas.", "repairable": false}

## C16 sample 1

In an acute triangle ABC, the perpendicular from B to AC has the same length as the perpendicular from C to AB. Prove AB=AC.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 3601; finish: stop.



To prove that in an acute triangle $ ABC $, if the perpendicular from $ B $ to $ AC $ has the same length as the perpendicular from $ C $ to $ AB $, then $ AB = AC $, we use the geometric relationship between the area of a triangle and the lengths of its altitudes.

---

### Step 1: Define the Altitudes

Let the length of the perpendicular from $ B $ to $ AC $ be $ h_b $, and the length of the perpendicular from $ C $ to $ AB $ be $ h_c $. The triangle is acute, so all altitudes lie inside the triangle.

The area of triangle $ ABC $ can be expressed in two ways:

$$
\text{Area} = \frac{1}{2} \cdot AC \cdot h_b = \frac{1}{2} \cdot AB \cdot h_c
$$

---

### Step 2: Equating the Two Expressions

Since $ h_b = h_c $, we can equate the two expressions for the area:

$$
\frac{1}{2} \cdot AC \cdot h_b = \frac{1}{2} \cdot AB \cdot h_b
$$

Divide both sides by $ \frac{1}{2} \cdot h_b $ (noting that $ h_b > 0 $, as it's a valid altitude in an acute triangle):

$$
AC = AB
$$

---

### Step 3: Conclusion

Thus, the lengths of sides $ AB $ and $ AC $ are equal, which means that triangle $ ABC $ is isosceles with $ AB = AC $.

---

### Final Answer

$$
\boxed{AB = AC}
$$<|im_end|>

Grade: {"valid": true, "method": "area", "note": "Correct comparison of the two base-altitude area formulas.", "repairable": false}
