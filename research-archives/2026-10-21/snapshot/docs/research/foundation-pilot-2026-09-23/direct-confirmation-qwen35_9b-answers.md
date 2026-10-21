## C01 sample 0

In triangle ABC, AB=6, AC=9, and BC=10. The internal bisector of angle BAC meets BC at D. Through D draw the line parallel to AB, meeting AC at E. Find AE.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 649; finish: stop.

### Step-by-Step Deduction

**1. Analyze the Angle Bisector Theorem**
In $\triangle ABC$, $AD$ is the internal bisector of $\angle BAC$. According to the **Angle Bisector Theorem**, the ratio of the lengths of the two segments of the opposite side is equal to the ratio of the lengths of the other two sides of the triangle.
Given:
*   $AB = c = 6$
*   $AC = b = 9$
*   $BC = a = 10$

The theorem states:
$$ \frac{BD}{DC} = \frac{AB}{AC} = \frac{6}{9} = \frac{2}{3} $$

Since $D$ lies on $BC$, we have $BD + DC = BC = 10$. Let $BD = 2x$ and $DC = 3x$.
$$ 2x + 3x = 10 \implies 5x = 10 \implies x = 2 $$
Thus, $BD = 4$ and $DC = 6$. (Although finding the specific lengths isn't strictly necessary for the final answer, this confirms the ratio).

**2. Analyze the Parallel Line Construction**
We are given that line $DE$ is parallel to side $AB$ ($DE \parallel AB$), where $E$ lies on $AC$.

Because $DE \parallel AB$, we can apply the **Basic Proportionality Theorem** (also known as Thales's Theorem) to $\triangle ABC$. This theorem states that if a line parallel to one side of a triangle intersects the other two sides, then it divides the two sides proportionally.

Therefore:
$$ \frac{AE}{EC} = \frac{BD}{DC} $$

From Step 1, we know $\frac{BD}{DC} = \frac{2}{3}$. Consequently:
$$ \frac{AE}{EC} = \frac{2}{3} $$

**3. Calculate the Length of AE**
Let $AE = 2y$ and $EC = 3y$.
Since $E$ lies on $AC$, the sum of the segments equals the total length of side $AC$:
$$ AE + EC = AC $$
$$ 2y + 3y = 9 $$
$$ 5y = 9 $$
$$ y = \frac{9}{5} = 1.8 $$

Now, calculate $AE$:
$$ AE = 2y = 2 \times 1.8 = 3.6 $$

Alternatively, using the section formula directly:
$$ AE = \frac{BD}{BD+DC} \times AC $$
$$ AE = \frac{2}{2+3} \times 9 = \frac{2}{5} \times 9 = \frac{18}{5} = 3.6 $$

### Conclusion

The length of segment $AE$ is **3.6**.<|im_end|>

Grade: {"valid": true, "method": "synthetic", "repairable": false, "note": "Correct angle-bisector ratio followed by parallel-line similarity gives AE=18/5."}

## C01 sample 1

In triangle ABC, AB=6, AC=9, and BC=10. The internal bisector of angle BAC meets BC at D. Through D draw the line parallel to AB, meeting AC at E. Find AE.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 1121; finish: stop.

### Step-by-Step Deduction

**1. Analyze the Geometry and Given Values**
*   In $\triangle ABC$, the side lengths are $AB = c = 6$, $AC = b = 9$, and $BC = a = 10$.
*   $AD$ is the internal angle bisector of $\angle BAC$, intersecting $BC$ at $D$.
*   A line is drawn through $D$ parallel to $AB$ ($DE \parallel AB$), intersecting $AC$ at $E$.
*   We need to find the length of segment $AE$.

**2. Apply the Angle Bisector Theorem**
Since $AD$ bisects $\angle A$, by the **Angle Bisector Theorem**, the ratio of the sides adjacent to the angle is equal to the ratio of the segments into which the bisector divides the opposite side:
$$ \frac{BD}{DC} = \frac{AB}{AC} = \frac{6}{9} = \frac{2}{3} $$

From this ratio, we can express $BD$ and $DC$ in terms of the total length $BC = 10$:
Let $BD = 2k$ and $DC = 3k$.
Then $2k + 3k = BC = 10 \implies 5k = 10 \implies k = 2$.
Therefore:
$$ BD = 4, \quad DC = 6 $$

**3. Use Similar Triangles due to Parallel Lines**
We are given that $DE \parallel AB$.
Consider $\triangle CDE$ and $\triangle CBA$:
*   $\angle DCE = \angle BCA$ (Common angle).
*   $\angle CDE = \angle CBA$ (Corresponding angles since $DE \parallel AB$).
*   Therefore, $\triangle CDE \sim \triangle CBA$ by AA similarity.

Alternatively, consider the Thales's Basic Proportionality Theorem (Intercept Theorem) directly on the transversals $AC$ and $BC$ cut by parallel lines $DE$ and $AB$. This states that the segments cut on the transversal $BC$ are proportional to the segments cut on the transversal $AC$.

Specifically, looking at the configuration where $DE \parallel AB$:
$$ \frac{CE}{CA} = \frac{CD}{CB} $$
Wait, let's re-evaluate the proportion based on the similar triangles $\triangle CDE \sim \triangle CBA$. The correspondence is $C \leftrightarrow C$, $D \leftrightarrow B$, and $E \leftrightarrow A$.
Thus:
$$ \frac{CE}{CA} = \frac{CD}{CB} = \frac{DE}{BA} $$

Using the known lengths for the base ratio:
$$ \frac{CE}{9} = \frac{DC}{BC} = \frac{6}{10} = \frac{3}{5} $$

**4. Calculate CE and then AE**
Now solve for $CE$:
$$ CE = 9 \times \frac{3}{5} = \frac{27}{5} = 5.4 $$

Since point $E$ lies on $AC$, we have:
$$ AE = AC - CE $$
$$ AE = 9 - 5.4 = 3.6 $$

**Alternative Verification using Direct Ratio:**
By similar triangles $\triangle ADE$? No, $ADE$ is not necessarily similar to anything simple immediately without constructing more lines. Let's use the property derived from Thales' theorem on the "trapezoid-like" setup or simply the similarity ratio calculated above.

Let's double check the logic with the other proportion often used:
Since $DE \parallel AB$, in $\triangle ABC$, the line $DE$ creates $\triangle CDE \sim \triangle CBA$.
Ratio of similarity $r = \frac{CD}{CB} = \frac{6}{10} = 0.6$.
So $CE = r \cdot CA = 0.6 \cdot 9 = 5.4$.
$AE = 9 - 5.4 = 3.6$.

Is there another way?
Consider $\triangle ABD$. Since $DE \parallel AB$, $\angle ADE = \angle DAB$ (Alternate interior angles).
Also, since $AD$ is a bisector, $\angle DAB = \angle DAC$ (which is $\angle DAE$).
Therefore, $\angle ADE = \angle DAE$.
This implies $\triangle ADE$ is an isosceles triangle with $AE = DE$.

Now apply similarity again: $\triangle CDE \sim \triangle CBA$.
$$ \frac{DE}{AB} = \frac{CD}{CB} = \frac{6}{10} = 0.6 $$
$$ DE = 0.6 \times AB = 0.6 \times 6 = 3.6 $$
Since $AE = DE$, then $AE = 3.6$.

Both methods yield the same result.

### Final Conclusion

The length of $AE$ is **3.6**.<|im_end|>

Grade: {"valid": true, "method": "synthetic", "repairable": false, "note": "Correct angle-bisector ratio followed by parallel-line similarity gives AE=18/5."}

## C02 sample 0

In triangle ABC, angle BAC=48 degrees. The internal bisectors of angles ABC and ACB meet at I. Find angle BIC.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 626; finish: stop.

### Logical Deduction

**1. Define Variables and Properties**
Let the angles of $\triangle ABC$ be denoted as follows:
*   $\angle BAC = \angle A = 48^\circ$
*   $\angle ABC = \angle B$
*   $\angle ACB = \angle C$

The sum of internal angles in any triangle is $180^\circ$. Therefore:
$$A + B + C = 180^\circ$$
Substituting the known value of $A$:
$$48^\circ + B + C = 180^\circ$$
$$B + C = 132^\circ$$

**2. Analyze the Incenter and Angle Bisectors**
Point $I$ is the intersection of the internal angle bisectors of $\angle B$ and $\angle C$, making it the incenter of $\triangle ABC$. Consequently, the line segments $BI$ and $CI$ bisect angles $B$ and $C$ respectively.

Let:
*   $\angle IBC = \frac{1}{2}B$
*   $\angle ICB = \frac{1}{2}C$

**3. Calculate Angles in Triangle BIC**
Consider $\triangle BIC$. The sum of its internal angles must also be $180^\circ$:
$$\angle BIC + \angle IBC + \angle ICB = 180^\circ$$

Substitute the expressions for the bisected angles:
$$\angle BIC + \frac{1}{2}B + \frac{1}{2}C = 180^\circ$$
$$\angle BIC + \frac{1}{2}(B + C) = 180^\circ$$

**4. Substitute and Solve**
From Step 1, we know that $B + C = 132^\circ$. Substitute this value into the equation from Step 3:
$$\angle BIC + \frac{1}{2}(132^\circ) = 180^\circ$$
$$\angle BIC + 66^\circ = 180^\circ$$
$$\angle BIC = 180^\circ - 66^\circ$$
$$\angle BIC = 114^\circ$$

**Alternative Formula Verification:**
There exists a direct formula relating the angle at the incenter to the opposite vertex angle: $\angle BIC = 90^\circ + \frac{1}{2}\angle A$.
$$\angle BIC = 90^\circ + \frac{48^\circ}{2} = 90^\circ + 24^\circ = 114^\circ$$
Both methods yield the same result.

### Final Conclusion

The measure of angle **$\angle BIC$ is $114^\circ$**.<|im_end|>

Grade: {"valid": true, "method": "synthetic", "repairable": false, "note": "Correct angle sum in triangle BIC gives 114 degrees."}

## C02 sample 1

In triangle ABC, angle BAC=48 degrees. The internal bisectors of angles ABC and ACB meet at I. Find angle BIC.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 655; finish: stop.

### Logical Deduction

**1. Define Variables and Properties**
Let the angles of $\triangle ABC$ be denoted as:
*   $\angle BAC = A$
*   $\angle ABC = B$
*   $\angle ACB = C$

We are given $A = 48^\circ$.
Point $I$ is the intersection of the internal angle bisectors of $\angle B$ and $\angle C$. By definition, the point where all three internal angle bisectors intersect is the **incenter**. Therefore, $BI$ bisects $\angle B$, and $CI$ bisects $\angle C$.

This implies:
*   $\angle IBC = \frac{1}{2}B$
*   $\angle ICB = \frac{1}{2}C$

**2. Apply the Triangle Angle Sum Theorem to $\triangle ABC$**
The sum of angles in any triangle is $180^\circ$:
$$A + B + C = 180^\circ$$

Substituting the known value of $A$:
$$48^\circ + B + C = 180^\circ$$
$$B + C = 180^\circ - 48^\circ = 132^\circ$$

**3. Analyze Triangle $\triangle BIC$**
Consider the triangle formed by points $B$, $I$, and $C$. The sum of its internal angles must also be $180^\circ$:
$$\angle IBC + \angle ICB + \angle BIC = 180^\circ$$

Substitute the expressions from Step 1 into this equation:
$$\frac{1}{2}B + \frac{1}{2}C + \angle BIC = 180^\circ$$

Factor out $\frac{1}{2}$:
$$\frac{1}{2}(B + C) + \angle BIC = 180^\circ$$

**4. Calculate the Final Value**
Substitute the value of $(B + C)$ calculated in Step 2 ($132^\circ$):
$$\frac{1}{2}(132^\circ) + \angle BIC = 180^\circ$$
$$66^\circ + \angle BIC = 180^\circ$$
$$\angle BIC = 180^\circ - 66^\circ$$
$$\angle BIC = 114^\circ$$

*(Alternative General Formula Verification)*:
It is a well-known property that for the incenter $I$, $\angle BIC = 90^\circ + \frac{1}{2}\angle A$.
$$\angle BIC = 90^\circ + \frac{48^\circ}{2} = 90^\circ + 24^\circ = 114^\circ$$
Both methods yield the same result.

### Conclusion

The measure of angle $BIC$ is **114 degrees**.<|im_end|>

Grade: {"valid": true, "method": "synthetic", "repairable": false, "note": "Correct angle sum in triangle BIC gives 114 degrees."}

## C03 sample 0

ABCD is a convex quadrilateral with AB=BC and AD=DC. Prove that its diagonals AC and BD are perpendicular.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 470; finish: stop.

**Proof:**

1.  **Identify Congruent Triangles**:
    Consider $\triangle ABC$ and $\triangle ADC$. We are given:
    *   $AB = BC$ (Given) implies $\triangle ABC$ is isosceles? No, wait. The condition is $AB=BC$ and $AD=DC$.
    Let's re-evaluate the sides relative to the diagonal $BD$.
    
    Actually, let us look at $\triangle ABD$ and $\triangle CBD$:
    *   $AB = CB$ (Given)
    *   $AD = CD$ (Given)
    *   $BD = BD$ (Common side)
    
    By the SSS (Side-Side-Side) Congruence Postulate, $\triangle ABD \cong \triangle CBD$.

2.  **Analyze Corresponding Parts**:
    Since $\triangle ABD \cong \triangle CBD$, their corresponding angles are equal. Specifically:
    $$ \angle ADB = \angle CDB $$

3.  **Apply Isosceles Triangle Property**:
    Now consider $\triangle ADC$. We are given $AD = DC$, so $\triangle ADC$ is an isosceles triangle with base $AC$.
    Let the diagonals intersect at point $O$. Thus, $DO$ is the cevian from vertex $D$ to the base $AC$.
    
    From step 2, we know that line segment $BD$ bisects the angle $\angle ADC$ because $\angle ADB = \angle CDB$. Therefore, $DO$ is the angle bisector of the vertex angle in isosceles $\triangle ADC$.

4.  **Conclusion via Properties of Isosceles Triangles**:
    In an isosceles triangle ($AD=DC$), the angle bisector of the vertex angle coincides with the altitude and the median to the base.
    Therefore, $DO \perp AC$.
    
    Since $D, O, B$ are collinear (part of diagonal $BD$), it follows that:
    $$ BD \perp AC $$

**Final Conclusion:**
The diagonals $AC$ and $BD$ are perpendicular.<|im_end|>

Grade: {"valid": true, "method": "synthetic", "repairable": false, "note": "Valid SSS followed by isosceles altitude/bisector; second sample also gives the perpendicular-bisector argument."}

## C03 sample 1

ABCD is a convex quadrilateral with AB=BC and AD=DC. Prove that its diagonals AC and BD are perpendicular.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 660; finish: stop.

### Proof

**Given:**
1.  $ABCD$ is a convex quadrilateral.
2.  $AB = BC$.
3.  $AD = DC$.

Let the diagonals $AC$ and $BD$ intersect at point $O$. We aim to prove that $AC \perp BD$.

**Step-by-Step Deduction:**

1.  **Identify Congruent Triangles:**
    Consider $\triangle ABD$ and $\triangle CBD$.
    *   $AB = CB$ (Given)
    *   $AD = CD$ (Given)
    *   $BD = BD$ (Common side)
    
    By the Side-Side-Side (SSS) Congruence Postulate, $\triangle ABD \cong \triangle CBD$.

2.  **Establish Angle Equality:**
    Since the triangles are congruent, their corresponding angles are equal. Specifically:
    $$ \angle ADB = \angle CDB $$
    Let this angle measure be $\theta$. Thus, $DB$ bisects $\angle ADC$.

3.  **Apply Isosceles Triangle Properties:**
    Now consider $\triangle ADC$. It is an isosceles triangle because $AD = DC$.
    The segment $DO$ lies on the line of symmetry for this isosceles triangle because it bisects the vertex angle $\angle ADC$ (as established in Step 2).

4.  **Prove Perpendicularity:**
    In an isosceles triangle ($\triangle ADC$), the angle bisector of the vertex angle is also the altitude to the base and the perpendicular bisector of the base.
    Therefore, the line containing $DO$ (which is the diagonal $BD$) is perpendicular to the base $AC$.
    
    Alternatively, using $\triangle ABC$:
    *   $AB = BC$ implies $\triangle ABC$ is isosceles.
    *   From Step 1, $\triangle ABD \cong \triangle CBD$, so $\angle ABD = \angle CBD$.
    *   Thus, $BO$ (part of diagonal $BD$) is the angle bisector of the vertex angle $\angle ABC$ in the isosceles triangle $\triangle ABC$.
    *   By the same property of isosceles triangles, the angle bisector of the vertex is the altitude to the base $AC$.
    *   Hence, $BD \perp AC$.

**Alternative Approach (Perpendicular Bisector Theorem):**
*   Since $AB = BC$, point $B$ lies on the perpendicular bisector of segment $AC$.
*   Since $AD = DC$, point $D$ lies on the perpendicular bisector of segment $AC$.
*   Two distinct points ($B$ and $D$) determine a unique line. Therefore, the line $BD$ is the perpendicular bisector of $AC$.
*   Consequently, $BD \perp AC$.

**Conclusion:**
The diagonals $AC$ and $BD$ are perpendicular.

**Final Answer:**
$$ AC \perp BD $$<|im_end|>

Grade: {"valid": true, "method": "synthetic", "repairable": false, "note": "Valid SSS followed by isosceles altitude/bisector; second sample also gives the perpendicular-bisector argument."}

## C04 sample 0

ABCD is a nondegenerate parallelogram, E is the midpoint of AB, and lines DE and AC meet at F. Find AF/FC.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 515; finish: stop.

### Geometric Analysis

Let the vertices of the parallelogram $ABCD$ be represented in a coordinate system or via vectors. We will use similar triangles, as this is the most direct method for ratios involving intersecting lines in a parallelogram.

1.  **Identify Parallel Lines**:
    Since $ABCD$ is a parallelogram, side $AB$ is parallel to side $DC$ ($AB \parallel DC$). Consequently, the segment $AE$ (which lies on line $AB$) is parallel to $DC$.

2.  **Identify Similar Triangles**:
    Consider $\triangle AEF$ and $\triangle CDF$.
    *   $\angle EAF = \angle DCF$ (Alternate interior angles formed by transversal $AC$ cutting parallel lines $AB$ and $CD$).
    *   $\angle AFE = \angle CFD$ (Vertically opposite angles at intersection $F$).
    *   Therefore, $\triangle AEF \sim \triangle CDF$ by Angle-Angle (AA) similarity.

3.  **Establish Ratios**:
    Because the triangles are similar, the ratio of their corresponding sides is constant:
    $$ \frac{AF}{FC} = \frac{EF}{FD} = \frac{AE}{CD} $$

4.  **Apply Given Constraints**:
    *   We are given that $E$ is the midpoint of $AB$, so $AE = \frac{1}{2} AB$.
    *   In a parallelogram, opposite sides are equal in length, so $AB = CD$.
    *   Substituting these into the expression for $AE$:
        $$ AE = \frac{1}{2} CD $$
    *   Therefore, the ratio $\frac{AE}{CD}$ is:
        $$ \frac{AE}{CD} = \frac{\frac{1}{2} CD}{CD} = \frac{1}{2} $$

5.  **Calculate Final Ratio**:
    From step 3, we know $\frac{AF}{FC} = \frac{AE}{CD}$.
    Thus:
    $$ \frac{AF}{FC} = \frac{1}{2} $$

### Conclusion

The ratio of the lengths $AF$ to $FC$ is:

$$ \frac{AF}{FC} = \frac{1}{2} $$<|im_end|>

Grade: {"valid": true, "method": "synthetic", "repairable": false, "note": "Correct AA similarity AEF~CDF and AE/CD=1/2."}

## C04 sample 1

ABCD is a nondegenerate parallelogram, E is the midpoint of AB, and lines DE and AC meet at F. Find AF/FC.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 723; finish: stop.

### Logical Deduction

To find the ratio $AF/FC$, we will use **similar triangles** derived from the properties of the parallelogram and the given midpoint.

1.  **Identify Parallel Lines**:
    Since $ABCD$ is a parallelogram, by definition, opposite sides are parallel. Therefore:
    $$AB \parallel CD$$
    Since point $E$ lies on line $AB$, it follows that:
    $$AE \parallel CD$$

2.  **Establish Similarity**:
    Consider $\triangle AEF$ and $\triangle CDF$:
    *   $\angle EAF = \angle DCF$ (Alternate interior angles formed by transversal $AC$ intersecting parallel lines $AE$ and $CD$).
    *   $\angle AEF = \angle CDF$ (Alternate interior angles formed by transversal $DE$ intersecting parallel lines $AE$ and $CD$).
    *   $\angle AFE = \angle CFD$ (Vertically opposite angles at point $F$).

    By the Angle-Angle-Angle (AAA) criterion, the triangles are similar:
    $$\triangle AEF \sim \triangle CDF$$

3.  **Set Up Proportions**:
    Because the triangles are similar, the ratios of their corresponding sides are equal:
    $$\frac{AF}{FC} = \frac{AE}{CD} = \frac{EF}{FD}$$

4.  **Apply Given Conditions**:
    *   We are given that $E$ is the midpoint of $AB$. Therefore:
        $$AE = \frac{1}{2} AB \implies AE = \frac{AB}{2}$$
    *   In a parallelogram, opposite sides are equal in length, so $AB = CD$. Substituting this into the equation for $AE$:
        $$AE = \frac{CD}{2}$$
    *   Rearranging to find the ratio $\frac{AE}{CD}$:
        $$\frac{AE}{CD} = \frac{1}{2}$$

5.  **Calculate Final Ratio**:
    Substitute the value of the side ratio back into the similarity proportion:
    $$\frac{AF}{FC} = \frac{AE}{CD} = \frac{1}{2}$$

Alternatively, using **Mass Point Geometry**:
*   Assign a mass of $m(A) = 1$ and $m(B) = 1$. Since $E$ is the midpoint of $AB$, the mass at $E$ is $m(E) = m(A) + m(B) = 2$.
*   To balance the parallelogram along the diagonal $AC$, we treat $C$ as having mass such that the center of mass logic holds relative to the parallel lines. However, a simpler application involves the intercept theorem directly on the parallel lines $AE$ and $CD$. The intersection $F$ divides the transversal $AC$ inversely proportional to the lengths of the parallel segments it connects.
*   Ratio $= \frac{\text{Length}(AE)}{\text{Length}(CD)} = \frac{0.5 \cdot AB}{AB} = 0.5$.

Both methods yield the same result.

### Final Conclusion

$$ \frac{AF}{FC} = \frac{1}{2} $$<|im_end|>

Grade: {"valid": true, "method": "synthetic", "repairable": false, "note": "Correct AA similarity AEF~CDF and AE/CD=1/2."}

## C05 sample 0

AB is a diameter of a circle with center O. C is another point on the circle. The tangent at C meets the tangents at A and B at X and Y, respectively. Prove that angle XOY=90 degrees.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 821; finish: stop.

### Proof

**1. Geometric Setup and Properties**
Let the circle have center $O$ and radius $r$.
*   Since $AB$ is a diameter, $\angle AOB = 180^\circ$.
*   Let the tangent at $C$ intersect the line containing $AB$? No, the problem states the tangent at $C$ meets the *tangents* at $A$ and $B$ at points $X$ and $Y$.
    *   The line $AX$ is tangent to the circle at $A$, so $OA \perp AX$.
    *   The line $BY$ is tangent to the circle at $B$, so $OB \perp BY$.
    *   Therefore, $AX \parallel OB$ and $BY \parallel OA$. Since $A, O, B$ are collinear, lines $AX$ and $BY$ are perpendicular to the line $AB$ at points $A$ and $B$ respectively. Thus, $AX \parallel BY$ (both perpendicular to $AB$). Wait, if they are on opposite sides of the diameter, they form parallel lines perpendicular to the diameter. If $C$ is not $A$ or $B$, the tangent at $C$ cuts these two parallel lines.

**2. Analysis of Point X**
Consider the point $X$, which lies on the tangent at $A$.
*   $XA$ is tangent to the circle at $A$.
*   $XC$ is tangent to the circle at $C$.
*   From a point external to a circle, the two tangents segments to the points of contact are equal in length: $XA = XC$.
*   Consequently, triangle $\triangle OAX$ is congruent to triangle $\triangle OCX$ (SSS congruence: $OA=OC=r$, $OX$ is common, $XA=XC$).
*   Alternatively, by the property that the line joining the center to an external point bisects the angle between the tangents:
    $$ \angle AOX = \angle COX $$

**3. Analysis of Point Y**
Similarly, consider point $Y$ on the tangent at $B$.
*   $YB$ is tangent to the circle at $B$.
*   $YC$ is tangent to the circle at $C$.
*   By the same property ($YB=YC$):
    $$ \angle BOY = \angle COY $$

**4. Summing the Angles**
We know that $A, O, B$ lie on a straight line (since $AB$ is the diameter), so the angles around $O$ on one side sum to $180^\circ$:
$$ \angle AOX + \angle COX + \angle COY + \angle BOY = 180^\circ $$
*(Note: Depending on the position of C relative to AB, the rays $OX$ and $OY$ lie within the upper or lower half-plane defined by AB. Assuming standard configuration where X and Y are on the same side of AB as C, the four angles listed above partition the straight angle $\angle AOB$.)*

Substituting the equalities from steps 2 and 3:
$$ 2\angle COX + 2\angle COY = 180^\circ $$

Divide by 2:
$$ \angle COX + \angle COY = 90^\circ $$

**5. Conclusion**
The angle $\angle XOY$ is composed of adjacent angles $\angle COX$ and $\angle COY$:
$$ \angle XOY = \angle COX + \angle COY $$
Therefore:
$$ \angle XOY = 90^\circ $$

### Final Conclusion
$\angle XOY = 90^\circ$.<|im_end|>

Grade: {"valid": true, "method": "synthetic", "repairable": false, "note": "A complete independent equal-tangent/SSS/angle-sum proof is present. The introductory paragraph also falsely says AX parallel OB and BY parallel OA, unused by that proof. Count as proof present; exclude in conservative whole-answer sensitivity.", "ancillary_math_error": true, "whole_answer_conservative_valid": false}

## C05 sample 1

AB is a diameter of a circle with center O. C is another point on the circle. The tangent at C meets the tangents at A and B at X and Y, respectively. Prove that angle XOY=90 degrees.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 540; finish: stop.

### Proof

**1. Geometric Setup and Properties**
Let the circle have center $O$ and radius $r$.
*   Since $AB$ is a diameter, $\angle AOB = 180^\circ$.
*   Lines $XA$, $XY$, and $YB$ are tangents to the circle at points $A$, $C$, and $B$, respectively.
*   The tangent at $A$ is perpendicular to the radius $OA$, so $\angle OAX = 90^\circ$.
*   The tangent at $B$ is perpendicular to the radius $OB$, so $\angle OB Y = 90^\circ$.

**2. Tangent Segments Property**
From an external point, the two tangent segments to a circle are equal in length:
*   From point $X$: $XA = XC$. Thus, $\triangle OAX \cong \triangle OCX$ (SSS congruence: $OA=OC=r$, $XA=XC$, $OX$ common). Consequently, $\angle AOX = \angle COX$.
*   From point $Y$: $YC = YB$. Thus, $\triangle OCY \cong \triangle OBY$ (SSS congruence: $OC=OB=r$, $YC=YB$, $OY$ common). Consequently, $\angle COY = \angle BOY$.

**3. Angle Summation**
The angles around the center $O$ on one side of the diameter line sum to $180^\circ$ because $A, O, B$ are collinear. Specifically:
$$ \angle AOX + \angle XOC + \angle COY + \angle YO B = 180^\circ $$

Substituting the equalities derived from the tangent properties ($\angle AOX = \angle XOC$ and $\angle COY = \angle BOY$):
$$ 2\angle XOC + 2\angle COY = 180^\circ $$

Dividing by 2:
$$ \angle XOC + \angle COY = 90^\circ $$

**4. Conclusion**
Observe that $\angle XOY$ is composed of adjacent angles $\angle XOC$ and $\angle COY$:
$$ \angle XOY = \angle XOC + \angle COY $$
Therefore:
$$ \angle XOY = 90^\circ $$

***

**Final Conclusion:**
The angle $\angle XOY$ is **90 degrees**.<|im_end|>

Grade: {"valid": true, "method": "synthetic", "repairable": false, "note": "Correct independent congruence/central-angle-bisector proof."}

## C06 sample 0

ABC is an equilateral triangle of altitude h. P is strictly inside the triangle, and its perpendicular distances to lines AB, BC, CA are x,y,z. Prove that x+y+z=h.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 594; finish: stop.

### Mathematical Justification

Let the vertices of the equilateral triangle $ABC$ be $A$, $B$, and $C$. Let the side length of the triangle be denoted by $s$.
The area of an equilateral triangle can be expressed in two ways:
1.  Using the base $s$ and altitude $h$:
    $$ \text{Area}(\triangle ABC) = \frac{1}{2} s h $$

2.  By decomposing the triangle into three smaller triangles formed by connecting point $P$ to each vertex ($PAB$, $PBC$, $PCA$).
    *   For $\triangle PBC$, the base is $BC = s$ and the corresponding height (perpendicular distance from $P$ to $BC$) is $z$. Thus, $\text{Area}(PBC) = \frac{1}{2} s z$.
    *   For $\triangle PCA$, the base is $CA = s$ and the corresponding height (perpendicular distance from $P$ to $CA$) is $x$. Thus, $\text{Area}(PCA) = \frac{1}{2} s x$.
    *   For $\triangle PAB$, the base is $AB = s$ and the corresponding height (perpendicular distance from $P$ to $AB$) is $y$. Thus, $\text{Area}(PAB) = \frac{1}{2} s y$.

Since $P$ lies strictly inside the triangle, the sum of the areas of these three smaller triangles equals the total area of $\triangle ABC$:
$$ \text{Area}(\triangle ABC) = \text{Area}(PBC) + \text{Area}(PCA) + \text{Area}(PAB) $$

Substituting the expressions derived above:
$$ \frac{1}{2} s h = \frac{1}{2} s z + \frac{1}{2} s x + \frac{1}{2} s y $$

Since $s > 0$, we can divide both sides of the equation by $\frac{1}{2} s$:
$$ h = z + x + y $$

Rearranging the terms yields the required identity:
$$ x + y + z = h $$

*(Note: This result is a specific instance of Viviani's Theorem, which states that for any point inside an equilateral triangle, the sum of the perpendicular distances to the sides is equal to the altitude.)*

### Final Conclusion
For any point $P$ strictly inside an equilateral triangle with altitude $h$, if $x, y, z$ are the perpendicular distances from $P$ to the sides $AB, BC,$ and $CA$ respectively, then:
$$ x + y + z = h $$<|im_end|>

Grade: {"valid": true, "method": "area", "repairable": false, "note": "Correct partition into three equal-base area terms; minor relabeling of distances does not affect the sum."}

## C06 sample 1

ABC is an equilateral triangle of altitude h. P is strictly inside the triangle, and its perpendicular distances to lines AB, BC, CA are x,y,z. Prove that x+y+z=h.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 605; finish: stop.

### Proof using Area Addition

Let $ABC$ be an equilateral triangle with side length $s$ and altitude $h$. Let the area of $\triangle ABC$ be denoted by $\Delta$.
The formula for the area of a triangle is:
$$ \Delta = \frac{1}{2} \times \text{base} \times \text{height} $$
Since the base is $s$ and the altitude is $h$:
$$ \Delta = \frac{1}{2}sh \quad \text{--- (1)} $$

Let $P$ be a point strictly inside the triangle. We connect $P$ to the vertices $A$, $B$, and $C$, forming three smaller triangles: $\triangle PBC$, $\triangle PCA$, and $\triangle PAB$. The sum of the areas of these three triangles equals the total area $\Delta$.

Given the perpendicular distances from $P$ to the sides $BC$, $CA$, and $AB$ are $x$, $y$, and $z$ respectively:
1.  **Area of $\triangle PBC$**: Taking $BC$ as the base ($s$) and $x$ as the height:
    $$ \text{Area}(PBC) = \frac{1}{2}sx $$
2.  **Area of $\triangle PCA$**: Taking $CA$ as the base ($s$) and $y$ as the height:
    $$ \text{Area}(PCA) = \frac{1}{2}sy $$
3.  **Area of $\triangle PAB$**: Taking $AB$ as the base ($s$) and $z$ as the height:
    $$ \text{Area}(PAB) = \frac{1}{2}sz $$

Summing these areas:
$$ \text{Area}(ABC) = \text{Area}(PBC) + \text{Area}(PCA) + \text{Area}(PAB) $$
$$ \Delta = \frac{1}{2}sx + \frac{1}{2}sy + \frac{1}{2}sz $$
$$ \Delta = \frac{1}{2}s(x + y + z) \quad \text{--- (2)} $$

Equating expressions (1) and (2) for $\Delta$:
$$ \frac{1}{2}sh = \frac{1}{2}s(x + y + z) $$

Since the side length $s > 0$, we can divide both sides by $\frac{1}{2}s$:
$$ h = x + y + z $$

**Conclusion:**
For any point $P$ strictly inside an equilateral triangle of altitude $h$, the sum of its perpendicular distances to the three sides is equal to $h$. Thus, **$x + y + z = h$**.<|im_end|>

Grade: {"valid": true, "method": "area", "repairable": false, "note": "Correct partition into three equal-base area terms; minor relabeling of distances does not affect the sum."}

## C07 sample 0

Triangle ABC has AB=13, AC=14, BC=15. Its incircle touches BC at D. Find BD.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 940; finish: stop.

### Step-by-Step Deduction

**1. Identify Given Values**
We are given a triangle $ABC$ with side lengths:
*   $c = AB = 13$
*   $b = AC = 14$
*   $a = BC = 15$

**2. Recall the Tangent Segment Theorem**
Let the incircle of $\triangle ABC$ touch the sides $BC$, $AC$, and $AB$ at points $D$, $E$, and $F$ respectively.
According to the properties of tangent segments from an external point to a circle:
*   From vertex $A$: $AF = AE$
*   From vertex $B$: $BD = BF$
*   From vertex $C$: $CD = CE$

Let $x = BD$. Then $BF = x$.
Since $D$ lies on $BC$, we have $CD = BC - BD = 15 - x$.
Consequently, $CE = 15 - x$ and $AE = 14 - (15 - x) = x - 1$.
Also, $AF = x - 1$.

**3. Formulate the Equation**
The semi-perimeter $s$ of the triangle is defined as:
$$s = \frac{AB + BC + AC}{2}$$
Substituting the given values:
$$s = \frac{13 + 15 + 14}{2} = \frac{42}{2} = 21$$

There is a standard formula relating the distance from a vertex to the tangency point on an adjacent side to the semi-perimeter. Specifically for vertex $B$ and side $BC$:
$$BD = s - b$$
where $b$ is the length of the side opposite vertex $B$ (which is $AC$).

**4. Alternative Derivation (Verification)**
Using the algebraic approach established in Step 2:
Sum of sides: $AB + BC + CA = c + a + b$
$$AB + BD + CD + AC = c + x + (15-x) + 14 = c + a + b$$
Alternatively, summing the segments starting from vertices:
$AB = AF + FB = (x-1) + x = 2x - 1$? No, let's re-evaluate the expressions based on $s$.

Let $AF = AE = y$.
Let $BD = BF = z$.
Let $CD = CE = w$.
Then:
1. $y + z = 13$
2. $z + w = 15$
3. $w + y = 14$

Adding all three equations:
$2(y + z + w) = 13 + 15 + 14 = 42$
$y + z + w = 21$ (This is the semi-perimeter $s$)

We need to find $BD = z$.
From equation (1), $y = 13 - z$.
From equation (3), $w = 14 - y = 14 - (13 - z) = 1 + z$.
Substitute $y$ and $w$ into the sum ($y+z+w=21$):
$(13 - z) + z + (1 + z) = 21$
$14 + z = 21$
$z = 7$

Alternatively, using the direct relationship derived from $2s = y+z+w+y$:
No, simply subtracting the perimeter sum from twice the semi-perimeter logic directly yields:
$z = (z + w) - (w) ...$ easier to just use $z = s - b$.
$s = 21$.
$b = AC = 14$.
$BD = 21 - 14 = 7$.

Check with other formulas:
$BD = s - AC = 21 - 14 = 7$.
$CD = s - AB = 21 - 13 = 8$.
$BC = BD + CD = 7 + 8 = 15$. This matches the given $BC=15$.

### Final Conclusion

The length of segment $BD$ is **7**.<|im_end|>

Grade: {"valid": true, "method": "synthetic", "repairable": false, "note": "Correct equal-tangent segment equations and result 7."}

## C07 sample 1

Triangle ABC has AB=13, AC=14, BC=15. Its incircle touches BC at D. Find BD.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 1142; finish: stop.

### Step-by-Step Deduction

1.  **Identify the Given Values**:
    Let the side lengths of triangle $ABC$ be denoted as follows:
    *   $c = AB = 13$
    *   $b = AC = 14$
    *   $a = BC = 15$

2.  **Recall the Property of Tangent Segments**:
    A fundamental property of a triangle's incircle is that the two tangent segments from any vertex to the points of tangency on the adjacent sides are equal in length.
    *   Let the incircle touch side $BC$ at $D$, side $AC$ at $E$, and side $AB$ at $F$.
    *   Then, the following equalities hold:
        $$BD = BF$$
        $$CD = CE$$
        $$AE = AF$$

3.  **Formulate Equations based on Side Lengths**:
    The total length of each side is the sum of these tangent segments:
    *   $BC = BD + CD = a$
    *   $AC = CD + AE = b$
    *   $AB = BF + AF = c$

    Since $BD = BF$ and $CD = CE$ (let's call this length $x$ and $y$ respectively), we have:
    $$BD + CD = 15 \implies x + y = 15$$
    $$AC = CD + AE \implies y + AE = 14$$
    $$AB = BD + AF \implies x + AF = 13$$

    Also, from vertex $A$, we know $AE = AF$. Let this length be $z$.
    So, $y + z = 14$ and $x + z = 13$.

4.  **Derive the Semi-perimeter Formula**:
    Sum the expressions for sides $AB$ and $AC$:
    $$AB + AC = (AF + FB) + (AE + EC)$$
    Substituting the tangent properties ($AF=AE=z$, $FB=BD=x$, $EC=CD=y$):
    $$AB + AC = z + x + z + y = x + y + 2z$$
    
    We know $x + y = BC = a$. Therefore:
    $$AB + AC = BC + 2z$$
    $$c + b = a + 2z \implies 2z = b + c - a$$
    
    However, we need to find $BD$ (which is $x$). Let's look at the sum of all three sides ($Perimeter = P = a+b+c$):
    $$P = BC + AC + AB = (x+y) + (y+z) + (x+z) = 2x + 2y + 2z$$
    The semi-perimeter $s = \frac{P}{2} = x + y + z$.
    
    Since $x + y = a$, we can write:
    $$s = a + z \implies z = s - a$$
    Similarly, considering side $AC$:
    $$s = x + (y+z) = x + b \implies x = s - b$$
    
    Wait, let's re-verify the variable assignment carefully to avoid confusion.
    Let $BD = x$. Then $BF = x$.
    Since $BC = 15$, then $CD = 15 - x$. Consequently $CE = 15 - x$.
    Since $AC = 14$, then $AE = 14 - (15 - x) = x - 1$.
    Since $AB = 13$, then $AF = 13 - x$.
    
    Because the tangents from vertex $A$ must be equal ($AE = AF$):
    $$x - 1 = 13 - x$$
    $$2x = 14$$
    $$x = 7$$
    
    Alternatively, using the standard formula for the distance from a vertex to the points of tangency:
    For vertex $B$, the distance to the point of tangency on $BC$ (which is $D$) is given by:
    $$BD = \frac{AB + BC - AC}{2} = \frac{c + a - b}{2}$$
    This corresponds to deriving $x = s - b$ where $s = \frac{a+b+c}{2}$:
    $$BD = \frac{a+b+c}{2} - b = \frac{a+b+c - 2b}{2} = \frac{a+c-b}{2}$$

5.  **Calculate the Final Value**:
    Using the derived formula with $a=15$, $b=14$, $c=13$:
    $$BD = \frac{13 + 15 - 14}{2}$$
    $$BD = \frac{28 - 14}{2}$$
    $$BD = \frac{14}{2}$$
    $$BD = 7$$

### Final Conclusion

The length of segment $BD$ is **7**.<|im_end|>

Grade: {"valid": true, "method": "synthetic", "repairable": false, "note": "Correct equal-tangent segment equations and result 7."}

## C08 sample 0

In an isosceles triangle ABC with AB=AC, D is strictly inside AB and E is strictly inside AC, with BD=CE. Let F be the intersection of BE and CD. Prove BF=CF.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 760; finish: stop.

### Proof by Symmetry

**1. Establish Symmetry of the Configuration**
Consider the angle bisector of $\angle BAC$. Since $\triangle ABC$ is isosceles with $AB = AC$, this bisector is also the perpendicular bisector of the base $BC$ and acts as an axis of symmetry for the entire triangle.

Let this axis of symmetry be the line $L$. The reflection across $L$ maps:
*   Vertex $A$ to itself ($A \to A$).
*   Vertex $B$ to vertex $C$ ($B \to C$) because $AB=AC$.
*   Vertex $C$ to vertex $B$ ($C \to B$).

**2. Map Points D and E**
We are given that $D$ lies on segment $AB$, $E$ lies on segment $AC$, and $BD = CE$.
Under the reflection across $L$:
*   Segment $AB$ maps to segment $AC$.
*   Since $B$ maps to $C$ and lengths are preserved, a point $D$ on $AB$ such that $BD = x$ must map to a point $E'$ on $AC$ such that $CE' = x$.
*   We are given $CE = BD = x$. Therefore, the point $E$ coincides exactly with the image of $D$ under this reflection.
*   Thus, the reflection maps $D \to E$.

**3. Map Lines BE and CD**
Now consider the lines containing segments $BE$ and $CD$:
*   Line $BE$ connects points $B$ and $E$. Under reflection, $B \to C$ and $E \to D$. Therefore, line $BE$ maps to line $CD$.
*   Similarly, line $CD$ connects points $C$ and $D$. Under reflection, $C \to B$ and $D \to E$. Therefore, line $CD$ maps to line $BE$.

**4. Analyze the Intersection Point F**
Let $F$ be the intersection of $BE$ and $CD$ ($F = BE \cap CD$).
Since $F$ lies on both lines, its image under the reflection must lie on the images of both lines:
*   $F \in BE \implies \text{Ref}(F) \in \text{Ref}(BE) = CD$.
*   $F \in CD \implies \text{Ref}(F) \in \text{Ref}(CD) = BE$.
Therefore, $\text{Ref}(F)$ is the intersection of $CD$ and $BE$. Since the intersection of two distinct lines is unique, $\text{Ref}(F) = F$.
This implies that point $F$ lies on the axis of symmetry $L$.

**5. Conclusion regarding Lengths BF and CF**
Since $F$ lies on the axis of symmetry (the perpendicular bisector of $BC$), it is equidistant from the endpoints of the segment $BC$.
$$FB = FC$$

### Final Conclusion
The reflection symmetry of the isosceles triangle $\triangle ABC$ across the altitude from $A$ maps $B$ to $C$, $D$ to $E$, line $BE$ to line $CD$, and consequently their intersection point $F$ onto itself. Since $F$ lies on the perpendicular bisector of $BC$, the distances from $F$ to $B$ and $C$ are equal.

**Therefore, $BF = CF$.**<|im_end|>

Grade: {"valid": true, "method": "synthetic", "repairable": false, "note": "Correct reflection or SAS congruence giving equal base angles at B,C."}

## C08 sample 1

In an isosceles triangle ABC with AB=AC, D is strictly inside AB and E is strictly inside AC, with BD=CE. Let F be the intersection of BE and CD. Prove BF=CF.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 656; finish: stop.

### Logical Deduction

Let the triangle $ABC$ be isosceles with $AB = AC$.
We are given:
1.  $D$ lies on segment $AB$.
2.  $E$ lies on segment $AC$.
3.  $BD = CE$.
4.  $F$ is the intersection of segments $BE$ and $CD$.

**Step 1: Establish Congruence between $\triangle ABD'$ and $\triangle ACE'$ (using auxiliary points or direct side analysis)**
Actually, let's compare triangles $\triangle DBC$ and $\triangle ECB$.
*   $BC$ is a common side.
*   Since $AB = AC$, the base angles are equal: $\angle ABC = \angle ACB$. Let's denote this measure as $\beta$. So, $\angle DBC = \angle ECB = \beta$.
*   We are given $BD = CE$.

By the **Side-Angle-Side (SAS)** congruence criterion:
$$ \triangle DBC \cong \triangle ECB $$
*(Note: Side $BD$ corresponds to Side $CE$, Angle $\angle DBC$ corresponds to Angle $\angle ECB$, and Side $BC$ corresponds to Side $CB$.)*

**Step 2: Derive Equal Angles from Congruence**
From the congruence $\triangle DBC \cong \triangle ECB$, corresponding angles must be equal. Specifically:
$$ \angle BCD = \angle CBE $$
Let $\angle BCD = x$ and $\angle CBE = x$.

**Step 3: Analyze Triangle $BFC$**
Consider the triangle formed by points $B$, $C$, and their intersection $F$, which is $\triangle BFC$.
The angles at vertices $B$ and $C$ within this specific triangle are:
*   $\angle FBC$: This is exactly $\angle CBE$, which we found in Step 2 to be $x$.
*   $\angle FCB$: This is exactly $\angle BCD$, which we found in Step 2 to be $x$.

Thus, in $\triangle BFC$:
$$ \angle FBC = \angle FCB = x $$

**Step 4: Apply Isosceles Triangle Theorem Converse**
In any triangle, if two interior angles are equal, the sides opposite those angles are also equal.
Since $\angle FBC = \angle FCB$, the sides opposite these angles must be equal:
*   Side opposite $\angle FCB$ is $BF$.
*   Side opposite $\angle FBC$ is $CF$.

Therefore:
$$ BF = CF $$

***

### Final Conclusion

By proving that $\triangle DBC \cong \triangle ECB$ via SAS congruence, we established that $\angle BCD = \angle CBE$. Consequently, in $\triangle BFC$, the base angles $\angle FBC$ and $\angle FCB$ are equal, implying that $\triangle BFC$ is an isosceles triangle with equal legs **$BF = CF$**.<|im_end|>

Grade: {"valid": true, "method": "synthetic", "repairable": false, "note": "Correct reflection or SAS congruence giving equal base angles at B,C."}

## C09 sample 0

The diagonals of a convex quadrilateral ABCD are perpendicular. Prove AB^2+CD^2=BC^2+DA^2.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 524; finish: stop.

### Proof

Let the vertices of the convex quadrilateral be $A, B, C, D$.
Let the diagonals $AC$ and $BD$ intersect at point $O$.
We are given that the diagonals are perpendicular, so $\angle AOB = \angle BOC = \angle COD = \angle DOA = 90^\circ$.

Since the diagonals intersect perpendicularly, the four triangles $\triangle AOB$, $\triangle BOC$, $\triangle COD$, and $\triangle DOA$ are right-angled at $O$. We can apply the Pythagorean theorem to each triangle:

1.  In $\triangle AOB$:
    $$AB^2 = OA^2 + OB^2$$

2.  In $\triangle BOC$:
    $$BC^2 = OB^2 + OC^2$$

3.  In $\triangle COD$:
    $$CD^2 = OC^2 + OD^2$$

4.  In $\triangle DOA$:
    $$DA^2 = OD^2 + OA^2$$

Now, consider the sum of the squares of opposite sides $AB$ and $CD$:
$$AB^2 + CD^2 = (OA^2 + OB^2) + (OC^2 + OD^2)$$
$$AB^2 + CD^2 = OA^2 + OB^2 + OC^2 + OD^2$$

Next, consider the sum of the squares of the other pair of opposite sides $BC$ and $DA$:
$$BC^2 + DA^2 = (OB^2 + OC^2) + (OD^2 + OA^2)$$
$$BC^2 + DA^2 = OB^2 + OC^2 + OD^2 + OA^2$$

Comparing the two results:
$$AB^2 + CD^2 = OA^2 + OB^2 + OC^2 + OD^2$$
$$BC^2 + DA^2 = OA^2 + OB^2 + OC^2 + OD^2$$

Therefore:
$$AB^2 + CD^2 = BC^2 + DA^2$$

**Conclusion:**
For any convex quadrilateral with perpendicular diagonals, the sum of the squares of one pair of opposite sides equals the sum of the squares of the other pair. Thus, **$AB^2+CD^2=BC^2+DA^2$** is proven.<|im_end|>

Grade: {"valid": true, "method": "synthetic", "repairable": false, "note": "Correct four Pythagorean equations and their sums prove the identity."}

## C09 sample 1

The diagonals of a convex quadrilateral ABCD are perpendicular. Prove AB^2+CD^2=BC^2+DA^2.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 544; finish: stop.

### Proof

Let the diagonals of the convex quadrilateral $ABCD$ be $AC$ and $BD$. Let them intersect at point $O$.
Given that the diagonals are perpendicular, we have $\angle AOB = \angle BOC = \angle COD = \angle DOA = 90^\circ$.

Since the diagonals intersect at right angles, triangles $\triangle AOB$, $\triangle BOC$, $\triangle COD$, and $\triangle DOA$ are all right-angled triangles with the right angle at $O$. We can apply the Pythagorean theorem to each:

1.  In $\triangle AOB$: $AB^2 = OA^2 + OB^2$
2.  In $\triangle COD$: $CD^2 = OC^2 + OD^2$
3.  In $\triangle BOC$: $BC^2 = OB^2 + OC^2$
4.  In $\triangle DOA$: $DA^2 = OD^2 + OA^2$

Now, consider the sum of the squares of opposite sides $AB$ and $CD$:
$$AB^2 + CD^2 = (OA^2 + OB^2) + (OC^2 + OD^2)$$
Rearranging the terms on the right side:
$$AB^2 + CD^2 = (OB^2 + OC^2) + (OD^2 + OA^2)$$

Next, substitute the expressions for $BC^2$ and $DA^2$ derived earlier:
*   Since $BC^2 = OB^2 + OC^2$, we replace $(OB^2 + OC^2)$ with $BC^2$.
*   Since $DA^2 = OD^2 + OA^2$, we replace $(OD^2 + OA^2)$ with $DA^2$.

Thus:
$$AB^2 + CD^2 = BC^2 + DA^2$$

Alternatively, this result follows directly from **Apollonius' Theorem** (the law of cosines generalized for medians), which states that for any quadrilateral, if the diagonals are perpendicular, the sum of the squares of two opposite sides equals the sum of the squares of the other two opposite sides. Specifically, applying the Law of Cosines on $\triangle ABC$ and $\triangle ADC$ with $\theta = 90^\circ$ yields the same identity immediately.

### Final Conclusion
The property holds true:
$$AB^2 + CD^2 = BC^2 + DA^2$$<|im_end|>

Grade: {"valid": true, "method": "synthetic", "repairable": false, "note": "Complete correct Pythagorean proof precedes an unnecessary and erroneous/misnamed Apollonius alternative. Count as proof present; exclude in conservative whole-answer sensitivity.", "ancillary_math_error": true, "whole_answer_conservative_valid": false}

## C10 sample 0

ABC is a triangle with incenter I. D is the midpoint of the arc BC of its circumcircle that does not contain A. Prove DB=DC=DI.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 564; finish: stop.

### Proof

Let $\triangle ABC$ have incenter $I$ and circumcircle $\Gamma$. Let $D$ be the midpoint of the arc $BC$ not containing $A$. This implies two key properties:
1.  Since $D$ is the midpoint of arc $BC$, chords $DB$ and $DC$ are equal. Thus, **$DB = DC$**.
2.  The line segment $AD$ bisects $\angle BAC$. Consequently, points $B$ and $C$ subtend equal angles at any point on the circle relative to the arc $BD$ and $CD$. Specifically, let $\angle BAD = \angle CAD = \alpha$. Then $\angle DBC = \angle DAC = \alpha$ (angles subtended by the same arc $DC$), and $\angle DCB = \angle DAB = \alpha$ (angles subtended by the same arc $BD$). Therefore, $\triangle DBC$ is isosceles with base angles equal to $\alpha$.

**Step 1: Analyze angles related to the Incenter $I$**
Since $I$ is the incenter, $BI$ bisects $\angle ABC$. Let $\angle ABI = \angle CBI = \beta$.
Consider $\triangle IBD$. We calculate $\angle DBI$:
$$ \angle DBI = \angle DBC + \angle CBI = \alpha + \beta $$

Now consider $\triangle ABI$. The angle sum of $\triangle ABI$ gives us relations for angles involving $A$ and $B$. More directly, look at $\angle BID$ as an exterior angle to $\triangle ABI$:
$$ \angle BID = \angle IAB + \angle IBA $$
Since $AI$ bisects $\angle A$ (as established earlier, $A, I, D$ are collinear) and $BI$ bisects $\angle B$:
$$ \angle IAB = \alpha $$
$$ \angle IBA = \beta $$
Thus:
$$ \angle BID = \alpha + \beta $$

**Step 2: Compare $\triangle IBD$**
We have found that:
$$ \angle DBI = \alpha + \beta $$
$$ \angle BID = \alpha + \beta $$
Since $\angle DBI = \angle BID$, $\triangle IBD$ is an isosceles triangle with sides opposite these angles being equal. Therefore:
$$ DB = DI $$

**Conclusion**
From Step 1, we know $DB = DC$. From Step 2, we proved $DB = DI$. By transitivity:
$$ DB = DC = DI $$

Q.E.D.<|im_end|>

Grade: {"valid": true, "method": "synthetic", "repairable": false, "note": "Correct arc midpoint gives DB=DC and AI,D collinear; exterior-angle proof DBI=BID proves DI=DB."}

## C10 sample 1

ABC is a triangle with incenter I. D is the midpoint of the arc BC of its circumcircle that does not contain A. Prove DB=DC=DI.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 931; finish: stop.

### Proof

Let $R$ be the circumradius of $\triangle ABC$, and let $\angle BAC = A$, $\angle ABC = B$, and $\angle ACB = C$.

**Step 1: Calculate $\angle DBC$ and $\angle DCB$**
Since $D$ is the midpoint of the arc $BC$ not containing $A$:
1.  The arc lengths $BD$ and $DC$ are equal, which implies the chords are equal:
    $$DB = DC$$
2.  By the Inscribed Angle Theorem, angles subtended by equal arcs at the circumference are equal. Thus, the angle subtended by arc $BD$ at vertex $A$ (which is part of $\angle BAD$) relates to the angle subtended by arc $CD$ at vertex $A$. More directly, consider the angles subtended by these arcs at any point on the remaining part of the circle.
    Specifically, $\angle DBC$ subtends arc $DC$, and $\angle DCB$ subtends arc $BD$. Since arc $BD =$ arc $DC$:
    $$\angle DBC = \angle DCB = \frac{1}{2} \text{m}(\widehat{DC}) = \frac{1}{2} \text{m}(\widehat{BD})$$
    Since the measure of arc $BC$ (not containing $A$) corresponds to the central angle $2A$, the arcs $BD$ and $DC$ each measure $A$. Therefore:
    $$\angle DBC = \angle DCB = \frac{1}{2} A$$
    *(Note: Alternatively, using cyclic quadrilateral properties or simply noting that $\angle DBC = \angle DAC$ because they subtend the same arc $DC$. Since $AD$ bisects $\angle A$, $\angle DAC = A/2$.)*

**Step 2: Express $\angle DBI$**
Point $I$ is the incenter, so $BI$ is the internal angle bisector of $\angle ABC$. Thus:
$$\angle CBI = \frac{1}{2} B$$
Now consider $\angle DBI$. Since $D$ lies on the extension of this geometry relative to side $BC$:
$$\angle DBI = \angle DBC + \angle CBI$$
Substituting the values derived above:
$$\angle DBI = \frac{A}{2} + \frac{B}{2}$$

**Step 3: Express $\angle BID$**
Consider $\triangle ABI$. The exterior angle at $I$, which is $\angle BID$ (since $A, I, D$ are collinear), is equal to the sum of the two opposite interior angles.
First, verify that $A, I, D$ are collinear. Since $D$ is the midpoint of arc $BC$, $AD$ is the angle bisector of $\angle BAC$. By definition, the incenter $I$ lies on the angle bisectors of the triangle. Therefore, $D$ lies on the line segment $AI$ extended.
Thus, $\angle BID$ is an exterior angle to $\triangle ABI$:
$$\angle BID = \angle IAB + \angle IBA$$
We know $\angle IAB = \frac{A}{2}$ (as $AD$ bisects $A$) and $\angle IBA = \frac{B}{2}$ (as $BI$ bisects $B$).
Therefore:
$$\angle BID = \frac{A}{2} + \frac{B}{2}$$

**Step 4: Conclude Isosceles Triangle**
Comparing the results from Step 2 and Step 3:
$$\angle DBI = \frac{A+B}{2}$$
$$\angle BID = \frac{A+B}{2}$$
Since $\angle DBI = \angle BID$, the triangle $\triangle DBI$ is isosceles with sides opposite these angles being equal:
$$DB = DI$$

**Final Conclusion**
From Step 1, we established $DB = DC$. From Step 4, we established $DB = DI$.
By transitivity:
$$DB = DC = DI$$
This point $D$ is known as the **circumcenter of $\triangle BIC$**.<|im_end|>

Grade: {"valid": true, "method": "synthetic", "repairable": false, "note": "Correct arc midpoint gives DB=DC and AI,D collinear; exterior-angle proof DBI=BID proves DI=DB."}

## C11 sample 0

Triangle ABC is right-angled at A. D is the midpoint of BC. The perpendicular from D to AC meets AC at E. Prove AE=EC and DE=AB/2.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 858; finish: stop.

### **Problem Analysis and Geometric Construction**

We are given a right-angled triangle $ABC$ ($\angle BAC = 90^\circ$).
1.  **Point D**: Midpoint of the hypotenuse $BC$.
2.  **Line DE**: Perpendicular from $D$ to $AC$, meeting $AC$ at $E$ (i.e., $DE \perp AC$).

We need to prove:
1.  $AE = EC$ (Point $E$ is the midpoint of $AC$).
2.  $DE = \frac{AB}{2}$.

---

### **Step-by-Step Deduction**

#### **Part 1: Proving Parallelism between AB and DE**
*   Since $\triangle ABC$ is right-angled at $A$, we have $AB \perp AC$.
*   By construction, $DE \perp AC$.
*   In Euclidean geometry, two lines perpendicular to the same line are parallel. Therefore:
    $$AB \parallel DE$$

#### **Part 2: Proving E is the Midpoint of AC (AE = EC)**
*   Consider $\triangle ABC$. We have identified that $D$ is the midpoint of side $BC$ (given) and that the line segment $DE$ passes through $D$ and is parallel to the side $AB$.
*   According to the **Triangle Midpoint Theorem** (specifically its converse or intercept theorem): If a line drawn through the midpoint of one side of a triangle is parallel to another side, it bisects the third side.
*   Applying this to $\triangle ABC$: Since $D$ is the midpoint of $BC$ and $DE \parallel AB$, the point $E$ must be the midpoint of $AC$.
*   Therefore:
    $$AE = EC$$

*(Alternatively, using similar triangles: Since $DE \parallel AB$, $\triangle CDE \sim \triangle CBA$. The ratio of similarity is $CD/CB = 1/2$. Thus, $CE/CA = 1/2$, implying $E$ is the midpoint.)*

#### **Part 3: Proving the Length of DE**
*   Returning to the similarity established above ($\triangle CDE \sim \triangle CBA$ with scale factor $1/2$):
    $$\frac{DE}{AB} = \frac{CD}{CB} = \frac{1}{2}$$
*   Solving for $DE$:
    $$DE = \frac{1}{2} AB$$

*(Alternatively, since $D$ and $E$ are midpoints, $DE$ is the **midline** (or median) of the triangle corresponding to side $AB$. A property of the midline is that it is parallel to the base and half its length.)*

---

### **Formal Proof Summary**

1.  Given $AB \perp AC$ and $DE \perp AC$, it follows that $AB \parallel DE$.
2.  In $\triangle ABC$, $D$ is the midpoint of $BC$ and $DE \parallel AB$. By the converse of the Triangle Midpoint Theorem, $DE$ intersects $AC$ at its midpoint $E$. Hence, **$AE = EC$**.
3.  Since $DE$ connects the midpoints of sides $BC$ and $AC$, it is the midline of $\triangle ABC$ relative to base $AB$. By the properties of the midline, **$DE = \frac{1}{2}AB$**.

---

### **Final Conclusion**

In right-angled triangle $ABC$ where $D$ is the midpoint of $BC$ and $DE \perp AC$:
1.  **$AE = EC$**: Point $E$ is the midpoint of side $AC$.
2.  **$DE = \frac{AB}{2}$**: The segment $DE$ is half the length of side $AB$.<|im_end|>

Grade: {"valid": true, "method": "synthetic", "repairable": false, "note": "Correct perpendicular-to-parallel implication and midpoint similarity."}

## C11 sample 1

Triangle ABC is right-angled at A. D is the midpoint of BC. The perpendicular from D to AC meets AC at E. Prove AE=EC and DE=AB/2.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 629; finish: stop.

### Step-by-Step Deduction

**1. Establish Parallelism and Similarity**
*   Since $\triangle ABC$ is right-angled at $A$, we have $AB \perp AC$.
*   By the given condition, $DE$ is perpendicular to $AC$ ($DE \perp AC$).
*   Since two lines perpendicular to the same line are parallel, it follows that $AB \parallel DE$.

**2. Apply Properties of the Midpoint**
*   We are given that $D$ is the midpoint of the hypotenuse $BC$, so $BD = DC$.
*   Consider $\triangle ABC$ with the transversal line segment $DE$.
*   Since $DE \parallel AB$ and $D$ bisects side $BC$, by the **Intercept Theorem (Thales's Theorem)** or the properties of similar triangles:
    $$ \triangle CDE \sim \triangle CBA $$
    Specifically, the ratio of corresponding sides is determined by the position of $D$ on $BC$:
    $$ \frac{CE}{CA} = \frac{CD}{CB} = \frac{DE}{AB} $$

**3. Prove $AE = EC$**
*   Since $D$ is the midpoint of $BC$, $\frac{CD}{CB} = \frac{1}{2}$.
*   Substituting this into the similarity ratio:
    $$ \frac{CE}{CA} = \frac{1}{2} \implies CE = \frac{1}{2} CA $$
*   This implies that $E$ is the midpoint of $AC$. Therefore:
    $$ AE = EC = \frac{1}{2} AC $$

**4. Prove $DE = \frac{AB}{2}$**
*   Using the same similarity ratio established above:
    $$ \frac{DE}{AB} = \frac{CD}{CB} = \frac{1}{2} $$
*   Solving for $DE$:
    $$ DE = \frac{1}{2} AB $$

*(Note: This result can also be viewed through the **Midpoint Theorem**, which states that the segment connecting the midpoints of two sides of a triangle is parallel to the third side and half its length. While $D$ is explicitly the midpoint of $BC$, proving $E$ is the midpoint of $AC$ via the parallel construction allows us to apply the theorem directly to $\triangle ABC$ with midpoints $D$ and $E$.)*

### Final Conclusion

Based on the geometric properties derived:
1.  **$AE = EC$**: Point $E$ is the midpoint of leg $AC$.
2.  **$DE = \frac{AB}{2}$**: Segment $DE$ is the median to the hypotenuse relative to the right angle vertex in the sub-triangle context, effectively being half the length of the other leg $AB$.<|im_end|>

Grade: {"valid": true, "method": "synthetic", "repairable": false, "note": "Correct perpendicular-to-parallel implication and midpoint similarity."}

## C12 sample 0

Two distinct circles intersect at A and B. The point diametrically opposite A on the first circle is C, and the point diametrically opposite A on the second is D. Assume C,D are different from B. Prove B,C,D are collinear.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 1149; finish: stop.

### Proof by Angle Analysis

**1. Geometric Setup and Given Conditions**
Let the two circles be $\Gamma_1$ and $\Gamma_2$, intersecting at points $A$ and $B$.
- Point $C$ lies on $\Gamma_1$ such that $AC$ is a diameter of $\Gamma_1$.
- Point $D$ lies on $\Gamma_2$ such that $AD$ is a diameter of $\Gamma_2$.
- We are given $C \neq B$ and $D \neq B$. Since $AC$ and $AD$ are diameters, $A, C, D$ cannot be collinear unless the circles are tangent or degenerate, which implies distinctness leads to specific angle properties.

**2. Properties of Diameters in Circles**
Consider triangle $\triangle ABC$ inscribed in circle $\Gamma_1$. Since $AC$ is the diameter of $\Gamma_1$:
$$ \angle ABC = 90^\circ $$
(Since the angle subtended by a diameter at any point on the circumference is a right angle).

Similarly, consider triangle $\triangle ABD$ inscribed in circle $\Gamma_2$. Since $AD$ is the diameter of $\Gamma_2$:
$$ \angle ABD = 90^\circ $$

**3. Analyzing Angles at Point B**
We examine the angles formed at point $B$ with respect to the line segment $AC$ and $AD$.
- From the first condition: The vector (or ray) $BA$ is perpendicular to the vector (or ray) $BC$. Thus, $BC \perp AB$.
- From the second condition: The vector (or ray) $BA$ is perpendicular to the vector (or ray) $BD$. Thus, $BD \perp AB$.

**4. Collinearity Argument**
We have established that both lines $BC$ and $BD$ pass through point $B$ and are both perpendicular to the same line $AB$.
In Euclidean geometry, if two distinct lines passing through a common point are both perpendicular to a third line, they must coincide.
Therefore, the points $C$, $B$, and $D$ lie on the same straight line.

*(Note: Even though there are four possible rays originating from $B$ perpendicular to $AB$ in non-Euclidean contexts, in standard plane geometry, the line perpendicular to a given line at a given point is unique. The direction depends on whether $C$ and $D$ lie on opposite sides of $AB$ or the same side. However, since $AC$ and $AD$ are diameters of different circles intersecting at $A$, geometric constraints ensure $C$ and $D$ align linearly with $B$. Specifically, $\angle CBD = |\angle ABC - \angle ABD|$ or $|\angle ABC + \angle ABD|$. Since $\angle ABC = 90^\circ$ and $\angle ABD = 90^\circ$, the angle between $BC$ and $BD$ relative to $BA$ sums to $180^\circ$ if they are on opposite sides, or $0^\circ$ if on the same side? Let's refine the orientation).*

**Refined Orientation Check:**
Let line $AB$ be vertical.
- In $\Gamma_1$, $AC \perp BC$. If $A$ is "top" and $B$ is "bottom-right", then $C$ must be such that $BC \perp AB$. Actually, simpler: Vector $\vec{BA} \cdot \vec{BC} = 0$ and $\vec{BA} \cdot \vec{BD} = 0$.
- This means $\vec{BC}$ and $\vec{BD}$ are both orthogonal to $\vec{BA}$.
- Therefore, $\vec{BC}$ and $\vec{BD}$ are parallel vectors along the same line passing through $B$.
- Are they pointing in the same direction or opposite?
  Consider the quadrilateral $ACBD$ (if convex) or the configuration of arcs.
  Actually, we don't need to determine if they point in the same or opposite direction; being parallel and sharing a point $B$ is sufficient for collinearity.
  
  Wait, strictly speaking, two lines are collinear if they form a single straight line ($180^\circ$) or are identical ($0^\circ$). Both cases represent the points lying on one line.
  Specifically:
  $\angle CBA = 90^\circ$ and $\angle DBA = 90^\circ$.
  Thus, $\angle CBD = \angle CBA + \angle DBA = 180^\circ$ (if $C$ and $D$ are on opposite sides of $AB$) OR $\angle CBD = 0^\circ$ (if they are on the same side).
  Regardless of the sum being $180^\circ$ or the rays coinciding ($0^\circ$), the points $B, C, D$ lie on the unique line passing through $B$ perpendicular to $AB$.

**Conclusion**
Since $BC \perp AB$ and $BD \perp AB$, the points $B$, $C$, and $D$ are collinear.

**Final Conclusion**
The points **$B, C, D$ are collinear**.<|im_end|>

Grade: {"valid": true, "method": "synthetic", "repairable": false, "note": "Correct final diameter angles at B, hence BC and BD lie on the unique perpendicular through B. Earlier mistaken descriptions are corrected."}

## C12 sample 1

Two distinct circles intersect at A and B. The point diametrically opposite A on the first circle is C, and the point diametrically opposite A on the second is D. Assume C,D are different from B. Prove B,C,D are collinear.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 911; finish: stop.

### Mathematical Justification

Let the two circles be $\omega_1$ and $\omega_2$. Let $O_1$ and $R_1$ be the center and radius of $\omega_1$, respectively. Similarly, let $O_2$ and $R_2$ be the center and radius of $\omega_2$.

**Step 1: Analyze properties within $\omega_1$**
Points $A$, $B$, and $C$ lie on circle $\omega_1$.
By definition, $C$ is diametrically opposite to $A$ on $\omega_1$. Therefore, the segment $AC$ passes through the center $O_1$ and is a diameter of $\omega_1$.
Since $B$ lies on $\omega_1$, the angle subtended by the diameter at point $B$ is a right angle.
$$ \angle ABC = 90^\circ $$

**Step 2: Analyze properties within $\omega_2$**
Points $A$, $B$, and $D$ lie on circle $\omega_2$.
By definition, $D$ is diametrically opposite to $A$ on $\omega_2$. Therefore, the segment $AD$ passes through the center $O_2$ and is a diameter of $\omega_2$.
Since $B$ lies on $\omega_2$, the angle subtended by the diameter at point $B$ is a right angle.
$$ \angle ABD = 90^\circ $$

**Step 3: Establish Collinearity**
Consider the angles formed at point $B$ relative to the lines passing through it.
We have established that line segment $BC$ is perpendicular to $AC$ ($\angle ABC = 90^\circ$) and line segment $BD$ is perpendicular to $AD$ ($\angle ABD = 90^\circ$).

Note that points $A, C, D$ are distinct (since $C \neq B$, $D \neq B$, and generally the circles are distinct with different diameters unless symmetric in a way that merges them, but even then, $C$ and $D$ define directions from $A$). More rigorously, consider the line $ACD$? No, $A, C, D$ are not necessarily collinear. However, we look at the angles sharing vertex $B$.

The angles $\angle ABC$ and $\angle ABD$ share the vertex $B$ and the common side $AB$.
*   $AC \perp BC$ implies the line containing $C$ and $B$ is perpendicular to $AC$.
*   $AD \perp BD$ implies the line containing $D$ and $B$ is perpendicular to $AD$.

Wait, a simpler geometric argument uses the angles relative to the transversal $AB$:
Actually, let's reconsider the configuration. The claim "$\angle ABC = 90^\circ$" means $CB \perp AB$? **No.**
It means the angle *inside the triangle* $ABC$ at vertex $B$ is $90^\circ$. So $CB \perp AB$ is incorrect; rather, $CB \perp AC$ is false too.
Correct interpretation: In $\triangle ABC$, since $AC$ is the diameter, the angle at $B$, which is $\angle CBA$ or simply $\angle B$ in $\triangle ABC$, is $90^\circ$. Thus, $CB \perp AB$.
Similarly, in $\triangle ABD$, since $AD$ is the diameter, $\angle DBA = 90^\circ$. Thus, $DB \perp AB$.

So:
1.  Line $BC$ is perpendicular to line $AB$.
2.  Line $BD$ is perpendicular to line $AB$.

Through any given point $B$ (where $B \neq A$), there exists exactly one line perpendicular to a given line $AB$. Since both line $BC$ and line $BD$ pass through $B$ and are perpendicular to $AB$, they must be the same line.

Therefore, points $C$, $B$, and $D$ lie on the same straight line.

### Conclusion
**B, C, and D are collinear.**<|im_end|>

Grade: {"valid": true, "method": "synthetic", "repairable": false, "note": "Correct final diameter angles at B, hence BC and BD lie on the unique perpendicular through B. Earlier mistaken descriptions are corrected."}

## C13 sample 0

D and E are the midpoints of BC and CA in triangle ABC. The medians AD and BE meet at G. Prove AG=2GD.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 822; finish: stop.

### Proof using Vector Geometry

**1. Define Position Vectors**
Let the origin be an arbitrary point $O$. Let the position vectors of vertices $A$, $B$, and $C$ be $\mathbf{a}$, $\mathbf{b}$, and $\mathbf{c}$ respectively.

**2. Express the Centroid $G$**
The centroid $G$ of a triangle is the average of the position vectors of its vertices. Therefore:
$$ \mathbf{g} = \frac{\mathbf{a} + \mathbf{b} + \mathbf{c}}{3} $$

**3. Express Point $D$ on Median $AD$**
Since $D$ is the midpoint of side $BC$:
$$ \mathbf{d} = \frac{\mathbf{b} + \mathbf{c}}{2} $$

**4. Formulate the Vector Relationship**
We calculate the vector difference $\vec{AG} = \mathbf{g} - \mathbf{a}$ and compare it to $\vec{GD} = \mathbf{d} - \mathbf{g}$.

First, compute $\vec{AG}$:
$$ \vec{AG} = \frac{\mathbf{a} + \mathbf{b} + \mathbf{c}}{3} - \mathbf{a} = \frac{\mathbf{b} + \mathbf{c} - 2\mathbf{a}}{3} $$

Next, compute $\vec{GD}$:
$$ \vec{GD} = \frac{\mathbf{b} + \mathbf{c}}{2} - \frac{\mathbf{a} + \mathbf{b} + \mathbf{c}}{3} $$
To subtract these fractions, find a common denominator (6):
$$ \vec{GD} = \frac{3(\mathbf{b} + \mathbf{c}) - 2(\mathbf{a} + \mathbf{b} + \mathbf{c})}{6} $$
$$ \vec{GD} = \frac{3\mathbf{b} + 3\mathbf{c} - 2\mathbf{a} - 2\mathbf{b} - 2\mathbf{c}}{6} $$
$$ \vec{GD} = \frac{\mathbf{b} + \mathbf{c} - 2\mathbf{a}}{6} $$

**5. Compare Lengths and Direction**
Observing the results from Step 4:
$$ \vec{AG} = \frac{\mathbf{b} + \mathbf{c} - 2\mathbf{a}}{3} = 2 \left( \frac{\mathbf{b} + \mathbf{c} - 2\mathbf{a}}{6} \right) = 2\vec{GD} $$

Since $\vec{AG} = 2\vec{GD}$, the vectors are collinear (they lie on the same line segment $AD$) and point in the same direction. Consequently, their magnitudes satisfy:
$$ |\vec{AG}| = 2|\vec{GD}| $$

*(Note: While the problem statement mentions median $BE$ meeting $AD$ at $G$, only the property of $D$ being the midpoint of $BC$ is required for this specific ratio on $AD$. The intersection at $G$ confirms $G$ lies on both medians, which is consistent with the definition of the centroid.)*

### Conclusion
Based on the vector derivation showing that $\vec{AG} = 2\vec{GD}$, we conclude:
$$ AG = 2GD $$<|im_end|>

Grade: {"valid": false, "method": "analytic", "repairable": true, "note": "Assumes the median intersection has vector (a+b+c)/3 without deriving that from the two medians. This effectively imports the core centroid relation asked to prove; repair by showing that vector lies on both medians."}

## C13 sample 1

D and E are the midpoints of BC and CA in triangle ABC. The medians AD and BE meet at G. Prove AG=2GD.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 795; finish: stop.

### Logical Deduction

**1. Definitions and Setup**
Let $\triangle ABC$ be the given triangle.
*   $D$ is the midpoint of side $BC$.
*   $E$ is the midpoint of side $CA$.
*   $AD$ and $BE$ are medians intersecting at point $G$.

**2. Geometric Construction**
Draw a line through vertex $C$ parallel to median $BE$, extending median $AD$ to meet this line at point $F$.
Now consider $\triangle BGD$ and $\triangle CFD$:
*   $\angle BDG = \angle CDF$ (Vertically opposite angles).
*   Since $CF \parallel BE$, $\angle DBG = \angle DCF$ (Alternate interior angles with transversal $BC$) and $\angle DGB = \angle DFC$ (Alternate interior angles with transversal $AF$).
*   We know $BD = DC$ because $D$ is the midpoint of $BC$.

By the **ASA Congruence Criterion**, $\triangle BGD \cong \triangle CFD$.

**3. Deriving Relationships from Congruence**
From the congruence $\triangle BGD \cong \triangle CFD$:
*   Corresponding sides are equal: $BG = CF$.
*   Corresponding sides are equal: $GD = DF$. Thus, $GF = GD + DF = 2GD$.

**4. Analyzing Triangle ACF**
Now consider $\triangle ACF$:
*   We established $CF \parallel BE$, which implies $CF \parallel EG$.
*   $E$ is the midpoint of $AC$ (Given).
*   By the **Midpoint Theorem Converse** (or properties of parallel lines cutting proportional segments): Since a line ($EG$) drawn through the midpoint of one side ($AC$) of a triangle ($\triangle ACF$) is parallel to another side ($CF$), it must bisect the third side ($AF$).

Therefore, $G$ is the midpoint of $AF$.
This gives us the relationship:
$$AG = GF$$

**5. Final Calculation**
Substitute $GF = 2GD$ into the equation for $AG$:
$$AG = 2GD$$

---

### Alternative Method: Mass Point Geometry
Assign masses to the vertices to balance the center of mass system.
1.  Assign mass $m_A = 1$ to $A$.
2.  To balance the side $AC$ at midpoint $E$, assign mass $m_C = 1$ to $C$. The total mass at $E$ is $1+1=2$.
3.  To balance the side $BC$ at midpoint $D$, since $m_C=1$, we must assign $m_B = 1$ to $B$. The total mass at $D$ is $1+1=2$.
4.  The intersection $G$ is the centroid balancing the entire triangle.
    *   Balancing along line $AD$: The system acts as two masses at endpoints. Mass at $A$ is $1$. Mass at $D$ (representing $B+C$) is $1+1=2$.
    *   For the center of mass $G$ on segment $AD$:
        $$m_A \cdot AG = m_D \cdot GD$$
        $$1 \cdot AG = 2 \cdot GD \implies AG = 2GD$$

---

### Conclusion

In any triangle, the medians intersect at the centroid, which divides each median in a ratio of $2:1$, measuring from the vertex to the midpoint.

**Final Conclusion:**
$$AG = 2GD$$<|im_end|>

Grade: {"valid": true, "method": "synthetic", "repairable": false, "note": "Constructs through C a parallel to BE, uses congruence across D and the midpoint theorem to prove AG=2GD."}

## C14 sample 0

A convex quadrilateral has equal diagonals. Must its four vertices lie on a circle? Prove the assertion or give an explicit counterexample.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 5814; finish: stop.

### Conclusion
**No**, a convex quadrilateral with equal diagonals does not necessarily have its four vertices lying on a circle.

While every rectangle (which is cyclic) has equal diagonals, there exist non-cyclic convex quadrilaterals (such as an **isosceles trapezoid**) that also satisfy this condition. In fact, the statement "equal diagonals $\implies$ cyclic" is false even for a specific subclass: the **isosceles trapezoid**. Wait, an isosceles trapezoid *is* cyclic. Let me re-evaluate.

Actually, the standard counterexample for "Equal Diagonals $\implies$ Cyclic" is an **Isosceles Trapezoid**? No, an isosceles trapezoid *is* cyclic.
Let's reconsider the properties.
- Rectangles: Equal diagonals, cyclic.
- Isosceles Trapezoids: Equal diagonals, cyclic.
- Kites? Only if square/rectangle.
- What about a generic quadrilateral with $AC = BD$?

Let's test the converse: If a quadrilateral is cyclic, must its diagonals be equal? No (a general rectangle is, but a scalene cyclic quadrilateral like $1, 2, 3, 4$ sides usually doesn't have equal diagonals).
The question asks: If $AC = BD$, must it be cyclic?

Let's construct a counterexample. Consider a **"right kite"** or a specific configuration.
Actually, the classic counterexample is an **isosceles trapezoid**? No, that works.
What if we take two congruent right triangles joined at their hypotenuses such that they are not symmetric in a way that forms a rectangle?
Consider a quadrilateral formed by points $(0,0), (2,1), (0,2), (-1,1)$? No, check convexity and lengths.

Let's use a coordinate geometry approach to build a rigorous counterexample.
We need a convex quadrilateral $ABCD$ such that $AC = BD$, but $A,B,C,D$ are not concyclic.
Condition for concyclicity: The perpendicular bisectors of the sides meet at one point, or Ptolemy's theorem holds ($AC \cdot BD = AB \cdot CD + BC \cdot DA$ only if cyclic? No, Ptolemy is equality for cyclic. For general, $AC \cdot BD \geq \dots$).
Alternative condition: Opposite angles sum to $180^\circ$. Or, using coordinates, the power of a point.

**Counterexample Construction:**
Let the vertices be:
$A = (-1, 0)$
$B = (0, 1)$
$C = (1, 0)$
$D = (0, -2)$ -- This is a kite? $DA=\sqrt{1+4}=\sqrt{5}$, $DC=\sqrt{1+4}=\sqrt{5}$. $BA=\sqrt{1+1}=\sqrt{2}$, $BC=\sqrt{2}$.
Diagonals: $AC$ lies on x-axis, length $= 2$. $BD$ lies on y-axis, length $= 1 - (-2) = 3$. Not equal.

Try again. We need $AC = BD$.
Let's try a specific shape known to fail: A quadrilateral with symmetry but not rotational symmetry of order 2 or reflection across diagonals.
Actually, the set of quadrilaterals with equal diagonals includes **isosceles trapezoids** (cyclic) and **some others**.
Are there non-cyclic ones?
Yes. Consider the quadrilateral formed by removing the center of a rectangle? No.

Let's define coordinates explicitly:
$A = (-2, 0)$
$B = (1, 2)$
$C = (2, 0)$
$D = (0, 1)$
Check convexity: Plot roughly. A left, B up-right, C right, D up-center.
Order A-B-C-D?
Vectors: $AB=(3,2)$, $BC=(1,-2)$, $CD=(-2, -1)$, $DA=(-2, -1)$? No $D-A = (2, 1)$.
Wait, let's order them carefully to be convex.
Let's place vertices on a grid.
$A = (0, 0)$
$B = (4, 1)$
$C = (3, 3)$
$D = (1, 3)$ -> Rectangle-ish?
$AC = \sqrt{3^2+3^2} = \sqrt{18}$.
$BD = \sqrt{(4-1)^2 + (1-3)^2} = \sqrt{9+4} = \sqrt{13}$. Not equal.

**Correct Counterexample Strategy:**
We know that for a cyclic quadrilateral, $AC^2 + BD^2 = \text{something involving sides}$? No.
There is a known class called **"Equidiagonal Quadrilaterals"**.
It is a known result that an equidiagonal quadrilateral is cyclic **IF AND ONLY IF** it is a **kite**? No.
Actually, the statement "An equidiagonal quadrilateral is cyclic" is **FALSE**.
A standard counterexample is an **isosceles trapezoid**? No, that is cyclic.
Is there any other equidiagonal convex quad?
Yes. Take a rectangle and deform it slightly while keeping diagonals equal?
If you shear a rectangle, diagonals change length differently?
In a parallelogram, diagonals are equal iff it is a rectangle (which is cyclic).
So the counterexample cannot be a parallelogram.

Let's try a non-symmetric construction.
Let $A=(-1, 0)$, $C=(1, 0)$. So $AC=2$. Midpoint origin.
We need $BD=2$. Let $B=(0, 1)$? Then $D$ must be such that distance from $(0,1)$ to $D$ is... wait, $B$ and $D$ are opposite.
Let diagonal $AC$ be on x-axis from $(-1,0)$ to $(1,0)$. Length 2.
We need $B(x_1, y_1)$ and $D(x_2, y_2)$ such that distance $BD = 2$.
And we need $A, B, C, D$ to form a convex quadrilateral.
Order $A, B, C, D$.
Convexity implies $B$ and $D$ are on opposite sides of $AC$.
Let $B = (x, h)$. Since $BD=2$, $D$ can be anywhere on a circle centered at $B$ with radius 2? No, $D$ is a vertex.
Let's fix $B$ and determine $D$.
To avoid being cyclic, the points should not lie on a single circle.
The circumcircle of $ABC$ must not contain $D$.
Circle through $A(-1,0), B(x,h), C(1,0)$.
Since $A$ and $C$ are symmetric around y-axis, the center of this circle lies on the y-axis, say $(0, k)$.
Radius squared $R^2 = 1^2 + k^2$.
Equation: $x^2 + (y-k)^2 = 1+k^2$.
We need $D(x_D, y_D)$ to NOT satisfy this equation.
Also constraint: Convex hull is $ABCD$. So $B$ has $y>0$, $D$ has $y<0$.
And $AC$ intersects nothing inside? Just ensure order.

Let's pick numbers:
$A = (-1, 0)$
$C = (1, 0)$
$B = (0, 2)$. (Top vertex)
Now choose $D$ such that $BD = AC = 2$.
$B=(0,2)$. Circle for $D$: $x^2 + (y-2)^2 = 4$.
We need $D$ in lower half plane ($y<0$) for convexity.
Let's pick $D = (\sqrt{3}, -1)$.
Check if on circle: $(\sqrt{3})^2 + (-1-2)^2 = 3 + 9 = 12 \neq 4$.
Wait, I need to solve for $D$ on the locus where $BD=2$.
$x^2 + (y-2)^2 = 4$.
Let's pick $x=0$. Then $(y-2)^2 = 4 \implies y-2 = \pm 2 \implies y=4$ or $y=0$.
If $y=0$, $D$ is on line $AC$. Degenerate.
Pick $x=1$. $1 + (y-2)^2 = 4 \implies (y-2)^2 = 3 \implies y = 2 \pm \sqrt{3}$.
Lower branch: $y = 2 - \sqrt{3} \approx 0.26 > 0$. Still upper half.
Need $y < 0$. Max distance down from $B(0,2)$ with radius 2 is $y=0$.
So if $B=(0,2)$ and $AC$ is on axis $y=0$, no $D$ exists with $y<0$ and $BD=2$ unless $D$ touches $y=0$.
This means $B$ must be closer to $AC$ than 2 units away vertically? No, $B$ is height. If height is 2, max reach down is 0.
So let's make $B$ lower.
$A=(-1,0), C=(1,0)$.
Let $B = (0, 1)$.
Then $BD=2$. Center $(0,1)$, radius 2.
Circle equation: $x^2 + (y-1)^2 = 4$.
Intersection with $y<0$:
Let $y = -1$. $x^2 + (-2)^2 = 4 \implies x^2 = 0 \implies x=0$.
$D=(0,-1)$. This gives a Rhombus/Square? $A(-1,0), B(0,1), C(1,0), D(0,-1)$. Square. Cyclic.
Let's shift $B$ horizontally.
$A=(-1,0), C=(1,0)$.
$B = (0.5, 1)$.
$BD = 2$.
Center $(0.5, 1)$. Radius 2.
We need $D(x,y)$ with $y < 0$.
Let's try to find a point $D$ on the circle $x^2 + (y-1)^2 = 4$ with $y=-1$?
$x^2 + (-2)^2 = 4 \implies x=0$.
So $D=(0, -1)$.
Vertices: $A(-1,0), B(0.5, 1), C(1,0), D(0, -1)$.
Check convexity:
Plot: A left, B mid-top, C right, D mid-bottom.
Edges: $AB, BC, CD, DA$.
Does $AC$ intersect interior? Yes.
Is it convex? Angles?
Vector $AB = (1.5, 1)$. $BC = (0.5, -1)$. Cross prod $z = -1.5 - 0.5 = -2$. Right turn?
Depends on orientation. Assume CCW.
Let's just assume convex visually (kite-like but skewed).
Now check if cyclic.
Calculate circumcircle of $A, B, C$.
Perpendicular bisector of $AC$ ($y$-axis, $x=0$).
Perpendicular bisector of $AB$. Midpoint $M_{AB} = (-0.25, 0.5)$.
Slope $AB = 1/1.5 = 2/3$. Perp slope $-3/2$.
Eq: $y - 0.5 = -1.5 (x + 0.25)$.
Intersect with $x=0$: $y = 0.5 - 1.5(0.25) = 0.5 - 0.375 = 0.125$.
Center $O(0, 0.125)$.
Radius to $A(-1,0)$: $r^2 = (-1)^2 + (-0.125)^2 = 1 + 0.015625 = 1.015625$.
Distance from $O$ to $D(0, -1)$:
$d^2 = (0-0)^2 + (-1 - 0.125)^2 = 1.125^2 = 1.265625$.
$r^2 \neq d^2$.
Thus $D$ does not lie on the circumcircle of $ABC$.
**Conclusion**: This quadrilateral is convex, has equal diagonals ($AC=2$, $BD=\sqrt{(0.5-0)^2 + (1-(-1))^2} = \sqrt{0.25+4} = \sqrt{4.25}$? Wait.)
My calculation of $BD$ was wrong.
$B=(0.5, 1)$, $D=(0, -1)$.
$BD^2 = (0.5-0)^2 + (1 - (-1))^2 = 0.25 + 4 = 4.25$.
But $AC^2 = 2^2 = 4$.
They are not equal! My construction failed to satisfy $BD=AC$.

I need to solve: Find $B, D$ such that $dist(B,D) = dist(A,C)$ and $D$ is not on circle $ABC$.
Let $AC$ be fixed horizontal segment length $L$.
Let $B$ be arbitrary. $D$ must be on a circle of radius $L$ centered at $B$.
We just need to ensure $D$ lands outside the circumcircle of $ABC$.
Since the circumcircle of $ABC$ passes through $A$ and $C$, and $AC=L$, the chord length is $L$.
For a circle of radius $L$ (centered at $B$), does it intersect the circumcircle of $ABC$ in exactly two points ($A$ and $C$)? No, $B$ is not related to that yet.
Generally, a circle centered at $B$ with radius $L$ will intersect the line $AC$ at some points? Not necessarily.
But we can always rotate $D$ around $B$ until it is not concyclic.
Is it possible that ALL points $D$ on the circle $|BD|=L$ that form a convex quad lie on the circumcircle?
That would imply the intersection of the circle $(B, L)$ and the circumcircle of $ABC$ contains all valid $D$. Impossible, two circles intersect at most at 2 points.
Therefore, unless the circle $(B,L)$ coincides with the circumcircle (impossible as centers differ usually), there are infinitely many choices for $D$. Most will not be concyclic.

**Explicit Counterexample Verification:**
Let $A = (-1, 0)$, $C = (1, 0)$. $AC = 2$.
Let $B = (0, 1)$.
Circumcircle of $ABC$:
Midpoint $AC$: $(0,0)$. Perpendicular bisector: $x=0$.
Midpoint $AB$: $(-0.5, 0.5)$. Slope $AB$: $1$. Perp slope: $-1$.
Line: $y - 0.5 = -1(x + 0.5) \implies y = -x$.
Intersect $x=0 \implies y=0$.
Center is $(0,0)$. Radius $1$.
Circle eq: $x^2+y^2=1$.
Points $A, B, C$ are on unit circle.
We need $D$ such that $BD = AC = 2$.
Circle centered at $B(0,1)$ with radius 2: $x^2 + (y-1)^2 = 4$.
We need a point $D$ on this circle such that $ABCD$ is convex and $D$ is NOT on $x^2+y^2=1$.
Let's pick $D = (-2, 1)$.
Check if on $BD$ circle: $(-2-0)^2 + (1-1)^2 = 4$. Yes.
Check convexity: $A(-1,0), B(0,1), C(1,0), D(-2,1)$.
Plot:
B(0,1) top center.
D(-2,1) top left.
A(-1,0) bottom left.
C(1,0) bottom right.
Order $A, B, C, D$?
Angles:
At $B$: Vector $BA=(-1,-1)$, $BC=(1,-1)$. Angle 90.
At $C$: $CB=(-1,1)$, $CD=(-3,1)$.
At $D$: $DC=(3,-1)$, $DA=(1,-1)$.
At $A$: $AD=(-2,2)$? No $D-A = (-1, 1)$. $AB=(1,1)$.
Is it convex?
Draw polygon $A \to B \to C \to D \to A$.
$A(-1,0) \to B(0,1)$ (Up Right)
$B(0,1) \to C(1,0)$ (Down Right)
$C(1,0) \to D(-2,1)$ (Far Left Up)
$D(-2,1) \to A(-1,0)$ (Down Right)
This shape self-intersects? Segment $BC$ crosses $DA$?
Line $BC$: $y-0 = \frac{1-0}{0-1}(x-1) \implies y = -x+1 \implies x+y=1$.
Line $DA$: $D(-2,1), A(-1,0)$. Slope $\frac{-1}{1} = -1$. Eq: $y = -x-1$.
Parallel lines. No intersection between segments.
However, look at the sequence. $A, B, C, D$.
Visually, $B$ and $C$ are close. $D$ is far left.
Angle at $C$: Interior angle.
Vector $CB = (-1, 1)$. Vector $CD = (-3, 1)$.
Cross product $z = (-1)(1) - (1)(-3) = -1 + 3 = 2 > 0$. Left turn.
Angle at $D$: $DC = (3, -1)$. $DA = (1, -1)$.
Cross $z = (3)(-1) - (-1)(1) = -3 + 1 = -2 < 0$. Right turn.
Not convex. The order $A,B,C,D$ creates a concave shape or self-intersecting if we don't pick the right order.
We need the convex hull to be $A,B,C,D$.
The convex hull of these points is likely $D, B, C, A$ or something else.
Hull vertices sorted angularly:
Center approx (-0.5, 0.5).
$D(-2,1)$ angle ~160.
$A(-1,0)$ angle ~200.
$C(1,0)$ angle ~340.
$B(0,1)$ angle ~45.
Order: $D \to B \to C \to A \to D$.
Quadrilateral $DBCA$.
Check diagonals of $DBCA$: $DC$ and $BA$.
$DC = \sqrt{(1-(-2))^2 + (0-1)^2} = \sqrt{9+1} = \sqrt{10}$.
$BA = 2$. Not equal.
We defined $AC=2$ and wanted $BD=2$.
In quad $DBCA$, the diagonals are $DC$ and $BA$. We needed the diagonals of the final quadrilateral to be equal.
So we must arrange vertices such that the pair $(AC, BD)$ are the diagonals.
This implies the order is $A, B, C, D$.
My previous check showed $A,B,C,D$ wasn't convex.
Let's adjust $D$.
We need $D$ such that $ABCD$ is convex.
Conditions for convexity of $A(-1,0), B(0,1), C(1,0), D(x,y)$:
$D$ must be in the region making $ABCD$ convex.
Usually $D$ needs to be below $AC$? Or above?
If $B$ is above, $D$ should be below.
Earlier, $B(0,1)$ led to $D$ needing $y<0$.
Let's retry $B(0, 0.5)$.
$A(-1,0), C(1,0)$. $AC=2$.
$B(0, 0.5)$.
Circle for $D$: Center $(0, 0.5)$, radius 2.
$x^2 + (y-0.5)^2 = 4$.
We want $y < 0$ (below $AC$) for convexity (assuming $B$ is above).
Max $y$ downwards: $y = 0.5 - 2 = -1.5$.
Pick $y = -1$.
$x^2 + (-1.5)^2 = 4 \implies x^2 + 2.25 = 4 \implies x^2 = 1.75 \implies x = \sqrt{1.75} \approx 1.32$.
Let $D = (1.32, -1)$.
Vertices: $A(-1,0), B(0, 0.5), C(1,0), D(1.32, -1)$.
Check convexity:
$A \to B$ (Up Right)
$B \to C$ (Down Right)
$C \to D$ (Down Right? $1.32 > 1, -1 < 0$. Yes)
$D \to A$ (Up Left)
Looks convex.
Check Concyclicity:
Circumcircle of $ABC$.
$A(-1,0), C(1,0), B(0, 0.5)$.
Perp bisector $AC$: $x=0$.
Perp bisector $AB$: $A(-1,0), B(0, 0.5)$. Mid $(-0.5, 0.25)$. Slope $AB = 0.5/1 = 0.5$. Perp slope $-2$.
$y - 0.25 = -2(x + 0.5)$.
At $x=0$: $y = 0.25 - 1 = -0.75$.
Center $O(0, -0.75)$.
Radius to $A$: $1^2 + 0.75^2 = 1 + 0.5625 = 1.5625$.
Dist to $D(1.32, -1)$:
$dx = 1.32, dy = -1 - (-0.75) = -0.25$.
$d^2 = 1.32^2 + 0.25^2 = 1.7424 + 0.0625 = 1.8049$.
$1.8049 \neq 1.5625$.
So $D$ is not on the circle.
Diagonals: $AC = 2$. $BD = 2$ (by construction).
Result: Equidiagonal, convex, not cyclic.

### Final Proof Steps
1.  **Assertion**: The assertion is **false**.
2.  **Counterexample**: Construct coordinates $A(-1, 0)$, $B(0, 0.5)$, $C(1, 0)$, and $D(\sqrt{1.75}, -1)$.
3.  **Verification**:
    *   **Equal Diagonals**: $AC = 2$. $B=(0, 0.5)$, $D \approx (1.32, -1)$. Distance $BD = \sqrt{1.75 + (-1.5)^2} = \sqrt{1.75+2.25} = \sqrt{4} = 2$. Thus $AC=BD$.
    *   **Convexity**: The vertices appear in counter-clockwise (or clockwise) order without internal angles $> 180^\circ$ based on geometric arrangement (one above axis, three spanning below/right/left). Specifically, the y-coordinates alternate relative to the edges forming the hull.
    *   **Non-Cyclic**: The circumradius of $\triangle ABC$ is $\sqrt{1.5625} = 1.25$. The distance from the circumcenter to $D$ is $\sqrt{1.8049} \approx 1.34 \neq 1.25$. Hence, $D$ lies outside the circle passing through $A, B, C$.

### Statement of Conclusion
A convex quadrilateral with equal diagonals does **not** have to be cyclic. A concrete counterexample exists in Euclidean geometry (as demonstrated by the coordinate construction above).<|im_end|>

Grade: {"valid": true, "method": "analytic", "repairable": false, "note": "Correct final explicit convex counterexample with equal diagonals and unequal powers/distances from circumcenter; abandoned failed examples are not used."}

## C14 sample 1

A convex quadrilateral has equal diagonals. Must its four vertices lie on a circle? Prove the assertion or give an explicit counterexample.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 3671; finish: stop.

### Conclusion
**No**, a convex quadrilateral with equal diagonals does **not** necessarily have its four vertices lying on a circle. In other words, the property of having equal diagonals is neither necessary nor sufficient for a quadrilateral to be cyclic.

Below is the proof via an explicit counterexample.

---

### Counterexample Construction

Consider an **isosceles trapezoid**. By definition, an isosceles trapezoid is a trapezoid where the non-parallel legs are congruent. A known theorem states that every isosceles trapezoid is a cyclic quadrilateral (its vertices lie on a circle) and its diagonals are equal. This shows that "cyclic $\implies$ equal diagonals."

However, we need the converse: "equal diagonals $\implies$ cyclic". To disprove this, we construct a specific convex quadrilateral with equal diagonals that is **not** cyclic.

Let us define a quadrilateral $ABCD$ in the Cartesian plane with the following vertices:
$$A = (0, 0), \quad B = (2, 1), \quad C = (4, 0), \quad D = (3, 2)$$

#### Step 1: Verify Convexity
Plotting these points or checking cross products of adjacent edge vectors confirms that the interior angles are all less than $180^\circ$. The shape is a convex kite-like figure (though not a perfect kite due to side lengths).

#### Step 2: Calculate Diagonal Lengths
Calculate the squared lengths of the diagonals $AC$ and $BD$ using the distance formula $d^2 = (x_2-x_1)^2 + (y_2-y_1)^2$.

1.  **Diagonal $AC$**: Connects $(0,0)$ and $(4,0)$.
    $$|AC|^2 = (4 - 0)^2 + (0 - 0)^2 = 16 + 0 = 16$$
    $$|AC| = 4$$

2.  **Diagonal $BD$**: Connects $(2,1)$ and $(3,2)$.
    $$|BD|^2 = (3 - 2)^2 + (2 - 1)^2 = 1^2 + 1^2 = 2$$
    $$|BD| = \sqrt{2}$$

Wait, in the example above, $|AC| \neq |BD|$. Let me re-calculate carefully to ensure the counterexample satisfies the condition $|AC| = |BD|$.

**Corrected Counterexample Attempt:**

Let's try a simpler approach based on the intersection of two line segments.
We need a quadrilateral where the diagonals intersect at right angles but the sides are arranged such that it cannot be inscribed in a circle. Actually, any quadrilateral with perpendicular diagonals has area $S = \frac{1}{2} d_1 d_2$. If $d_1=d_2$, area is fixed by length. That doesn't guarantee non-cyclic.

Let's use the property of **bimedians** or specific coordinates.
Let the vertices be $A(0,0)$, $B(a, b)$, $C(c, 0)$, and $D(d, e)$.
This is getting algebraically messy. Let's look at the geometric construction directly.

**Geometric Construction of a Counterexample:**
Start with a rectangle (which is cyclic and has equal diagonals). Now, move one vertex slightly off the circumcircle while adjusting another to keep diagonal lengths equal? No, moving a vertex changes the other diagonal usually.

Let's try a **right trapezoid** variant or simply calculate specific integer coordinates.
Let the diagonals intersect at the origin $O(0,0)$ along the axes for symmetry, but the segments must form a closed loop.
Let diagonal $AC$ lie on the x-axis: $A=(-u, 0)$, $C=(v, 0)$ with $u,v > 0$.
Let diagonal $BD$ lie on the y-axis: $B=(0, w)$, $D=(0, z)$ with $w,z > 0$ (assuming convexity implies they are on opposite sides of the intersection).
For the quadrilateral to close, the order of vertices must be $A, B, C, D$.
Lengths:
$d_1 = |AC| = u + v$
$d_2 = |BD| = w + z$

Condition: Equal diagonals $\implies u + v = w + z$. Let this sum be $L$.
Vertices: $A(-u, 0), B(0, w), C(v, 0), D(0, z)$.
Are these concyclic?
The general equation of a circle is $x^2 + y^2 + Dx + Ey + F = 0$.
Substitute $A$: $u^2 - Du + F = 0 \implies F = Du - u^2$.
Substitute $C$: $v^2 + Dv + F = 0 \implies F = -Dv - v^2$.
Equating $F$: $Du - u^2 = -Dv - v^2 \implies D(u+v) = u^2 - v^2 = (u-v)(u+v)$.
Since $u+v = L \neq 0$, we get $D = u - v$.
Then $F = (u-v)u - u^2 = u^2 - uv - u^2 = -uv$.
So far, circle eq: $x^2 + y^2 + (u-v)x + Ey - uv = 0$.

Now check points $B(0, w)$ and $D(0, z)$.
Substitute $B$: $w^2 + Ew - uv = 0 \implies E = \frac{uv - w^2}{w}$.
Substitute $D$: $z^2 + Ez - uv = 0 \implies E = \frac{uv - z^2}{z}$.
For them to be on the same circle, the calculated $E$ must match:
$$\frac{uv - w^2}{w} = \frac{uv - z^2}{z}$$
$$z(uv - w^2) = w(uv - z^2)$$
$$uzv - zw^2 = wuv - wz^2$$
$$uv(z-w) - wz(w-z) = 0$$
$$uv(z-w) + wz(z-w) = 0$$
$$(z-w)(uv + wz) = 0$$
Since $u,v,w,z > 0$, the term $uv+wz$ is strictly positive. Therefore, we must have $z - w = 0$, i.e., $z = w$.

**Interpretation:**
If the diagonals are perpendicular (aligned with axes as done here) and have equal total lengths ($u+v = w+z$), the vertices are concyclic **if and only if** the diagonals cut each other into equal halves (i.e., $u=v$ and $w=z$, making it a rectangle) OR if the specific product balance holds. Wait, my derivation showed $z=w$ is required given the constraint $uv+wz \neq 0$.
Actually, let's re-evaluate. The condition derived was $(z-w)(uv+wz)=0$. Since $uv+wz > 0$, we must have $z=w$.
But we also know $u+v = w+z$. If $z=w$, then $u+v = 2w$.
Does this force a rectangle? Not necessarily. We just need $z=w$.
If $z=w$, the y-intercepts are symmetric. The x-intercepts satisfy $u+v=2w$.
Let's pick numbers:
Let $w = 2$, so $z = 2$. Then $u+v = 4$.
Let $u = 1$, so $v = 3$.
Vertices:
$A = (-1, 0)$
$B = (0, 2)$
$C = (3, 0)$
$D = (0, 2)$ -> Wait, $B$ and $D$ coincide! That's degenerate.
Ah, $B$ and $D$ must be on *opposite* sides of the intersection for a convex quad if the diagonals are segments connecting opposite vertices.
In my setup: $A, C$ on x-axis, $B, D$ on y-axis.
For convexity $ABCD$, $A$ and $C$ are opposite, $B$ and $D$ are opposite.
Usually, we place intersection at origin.
$A = (-u, 0)$, $C = (v, 0)$ ($u,v>0$).
$B = (0, w)$, $D = (0, -z)$ ($w,z>0$). Note the sign change for $D$ to make it a proper crossing.
Re-run the circle check with $D = (0, -z)$.

Circle through $A(-u,0)$ and $C(v,0)$: Same $D_{coeff} = u-v$, $F = -uv$. Eq: $x^2+y^2+(u-v)x+Ey-uv=0$.
Point $B(0, w)$: $w^2 + Ew - uv = 0 \implies E = (uv-w^2)/w$.
Point $D(0, -z)$: $(-z)^2 + E(-z) - uv = 0 \implies z^2 - Ez - uv = 0 \implies Ez = z^2 - uv \implies E = (z^2-uv)/z$.
Equate $E$:
$$\frac{uv-w^2}{w} = \frac{z^2-uv}{z}$$
$$z(uv-w^2) = w(z^2-uv)$$
$$uzv - zw^2 = wz^2 - wuv$$
$$uv(z+w) - zw(w+z) = 0$$
$$(z+w)(uv - zw) = 0$$
Since $z,w > 0$, $z+w \neq 0$. Thus, $uv = zw$.

**Condition for Concyclicity with Perpendicular Diagonals:**
For a quadrilateral with perpendicular diagonals intersecting at origin with segments $u,v$ on x-axis and $w,z$ on y-axis:
1. Equal diagonals: $u+v = w+z$.
2. Concyclic: $uv = wz$.

Can we find positive real numbers $u,v,w,z$ satisfying both equations but not forming a rectangle ($u \neq v$)?
Yes.
Let $u+v = S$ and $uv = P$. $u,v$ are roots of $t^2 - St + P = 0$. Discriminant $\Delta = S^2 - 4P \ge 0$.
Similarly for $w,z$: sum $S$, product $P$.
So if we choose $S=4$ and $P=3$:
Roots for $\{u,v\}$ are $1, 3$. So $u=1, v=3$ (or vice versa). Sum=4, Prod=3.
Roots for $\{w,z\}$ are $1, 3$. So $w=1, z=3$ (or vice versa). Sum=4, Prod=3.
Check equality: $u+v = 4$, $w+z = 4$. (Equal diagonals).
Check concyclicity condition: $uv = 1\times3 = 3$, $wz = 1\times3 = 3$. (Concyclic!).
It seems if sums and products are equal, the sets are identical. So $u,v$ is the set $\{1,3\}$ and $w,z$ is $\{1,3\}$.
Is it possible to have different distributions?
We need $u+v = w+z$ AND $uv = wz$.
This implies $\{u,v\} = \{w,z\}$ as sets.
So either ($u=w, v=z$) or ($u=z, v=w$).
Case 1: $u=w, v=z$. Vertices: $(-u,0), (0,u), (v,0), (0,-v)$.
Diagonals lengths $u+v$ and $u+v$. Equal.
Is it cyclic? Yes, $uv=wz$ holds.
Case 2: $u=z, v=w$. Vertices: $(-u,0), (0,v), (v,0), (0,-u)$.
Symmetric swap. Still cyclic.

**Conclusion from Perpendicular Case:**
If diagonals are perpendicular, equal diagonals $\implies$ cyclic?
My math says: $u+v = w+z$ AND $uv=wz$ is required for cyclic.
But the problem statement only gives $u+v=w+z$.
If I choose $u+v = w+z$ but $uv \neq wz$, it is NOT cyclic.
Example:
Let sum $S = 5$.
Set 1: $u=1, v=4$. Product $P_1 = 4$.
Set 2: Need $w+z=5$ but $wz \neq 4$. Let $w=2, z=3$. Product $P_2 = 6$.
Check conditions:
- Diagonals: $u+v = 5$, $w+z = 5$. **Equal**.
- Concyclicity condition: $uv = 4$, $wz = 6$. **Not Equal**.
Thus, this quadrilateral has equal diagonals but is **not** cyclic.

**Final Explicit Coordinates:**
Intersection at $(0,0)$. Diagonals along axes.
$A = (-1, 0)$
$C = (4, 0)$
$B = (0, 2)$
$D = (0, -3)$

**Verification:**
1.  **Convexity**: Vertices in order $A, B, C, D$ form a convex quadrilateral (a dart/kite shape but stretched).
2.  **Diagonal Lengths**:
    -   $AC = |-1 - 4| = 5$.
    -   $BD = |2 - (-3)| = 5$.
    -   $AC = BD$. Condition met.
3.  **Cyclic Check**:
    -   Power of point $O(0,0)$ wrt potential circle passing through $A,B,C$.
    -   If cyclic, $OA \cdot OC = OB \cdot OD$ (but note directions). For chords intersecting inside, $OA \cdot OC = OB \cdot OD$.
    -   Here, lengths from center: $OA=1, OC=4 \implies OA \cdot OC = 4$.
    -   $OB=2, OD=3 \implies OB \cdot OD = 6$.
    -   Since $4 \neq 6$, point $D$ does not lie on the circle defined by $A, B, C$.
    -   Therefore, not cyclic.

### Final Proof Summary

**Assertion:** False. A convex quadrilateral with equal diagonals does not necessarily have its vertices on a circle.

**Counterexample:**
Consider the quadrilateral $ABCD$ with vertices $A(-1, 0)$, $B(0, 2)$, $C(4, 0)$, and $D(0, -3)$.
1.  **Convexity**: The vertices form a convex polygon.
2.  **Equal Diagonals**:
    -   Length of $AC = \sqrt{(4 - (-1))^2 + 0} = 5$.
    -   Length of $BD = \sqrt{0 + (-3 - 2)^2} = 5$.
    -   Thus, $AC = BD$.
3.  **Non-Cyclic**:
    -   If $ABCD$ were cyclic, the intersecting chords theorem would require the product of the segment lengths of the diagonals to be equal: $OA \cdot OC = OB \cdot OD$, where $O$ is the intersection $(0,0)$.
    -   $OA \cdot OC = 1 \cdot 4 = 4$.
    -   $OB \cdot OD = 2 \cdot 3 = 6$.
    -   Since $4 \neq 6$, the points are not concyclic.

**Answer:** No, the assertion is false.<|im_end|>

Grade: {"valid": true, "method": "analytic", "repairable": false, "note": "Correct final explicit convex counterexample with equal diagonals and unequal powers/distances from circumcenter; abandoned failed examples are not used."}

## C15 sample 0

A,B are distinct points. C,D are distinct points off line AB, and triangles ABC and ABD have equal (unsigned) areas. Must CD be parallel to AB? Prove the assertion or give an explicit counterexample.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 1015; finish: stop.

### Logical Deduction

**1. Formulation using the Area Formula**
Let the line containing points $A$ and $B$ be denoted as $L$. Since $C$ and $D$ are not on $L$, let $h_C$ and $h_D$ represent the perpendicular distances from $C$ and $D$ to the line $AB$, respectively.
The area of a triangle with base length $b$ and height $h$ is given by $\text{Area} = \frac{1}{2}bh$.

For triangles $\triangle ABC$ and $\triangle ABD$:
- Both share the same base segment $AB$. Let the length of this base be $c = |AB|$.
- The problem states that their unsigned areas are equal:
  $$ \text{Area}(\triangle ABC) = \text{Area}(\triangle ABD) $$
  $$ \frac{1}{2} c \cdot h_C = \frac{1}{2} c \cdot h_D $$

Since $A$ and $B$ are distinct, $c > 0$. Dividing both sides by $\frac{1}{2}c$, we obtain:
$$ h_C = h_D $$

**2. Geometric Interpretation of Equal Heights**
The condition $h_C = h_D$ implies that points $C$ and $D$ lie on a line parallel to $AB$ **on the same side** of $AB$, OR on lines equidistant from $AB$ but on **opposite sides**.

In coordinate geometry terms, if we set $A = (0,0)$ and $B = (c, 0)$, then the $y$-coordinate of any point determines its signed distance from the line $AB$.
- If $y_C = k$ and $y_D = k$ for some $k \neq 0$, then $C$ and $D$ lie on the line $y=k$, which is parallel to the x-axis ($AB$).
- However, if $y_C = k$ and $y_D = -k$ for some $k \neq 0$, then the perpendicular distances are $|k|$ and $|-k|$, which are equal. In this case, $C$ and $D$ lie on different parallel lines separated by the axis $AB$. Neither $C$ nor $D$ lies on a single line passing through both that is parallel to $AB$.

**3. Constructing a Counterexample**
To disprove the assertion "Must $CD$ be parallel to $AB$", we construct a specific case where $h_C = h_D$ but the segment $CD$ intersects the line $AB$ (or is not horizontal).

*Setup:*
- Let $A = (-1, 0)$ and $B = (1, 0)$. Line $AB$ is the x-axis ($y=0$).
- Let point $C$ be at $(0, 1)$. Its distance to $AB$ is $1$.
- Let point $D$ be at $(0, -1)$. Its distance to $AB$ is $1$.
- Check distinctness: $C \neq D$, $C \notin AB$, $D \notin AB$.

*Verification of Areas:*
- Base $AB$ has length $2$.
- Height of $\triangle ABC$ is $1$. Area $= \frac{1}{2} \times 2 \times 1 = 1$.
- Height of $\triangle ABD$ is $1$. Area $= \frac{1}{2} \times 2 \times 1 = 1$.
- The areas are equal.

*Analysis of Segment CD:*
- Points $C(0, 1)$ and $D(0, -1)$.
- The slope of the line connecting $C$ and $D$ is $\frac{-1 - 1}{0 - 0}$, which is undefined (a vertical line $x=0$).
- The line $AB$ is horizontal ($y=0$).
- A vertical line is not parallel to a horizontal line; they intersect at $(0,0)$.

Thus, $CD$ is not parallel to $AB$.

### Conclusion

No, $CD$ does not necessarily have to be parallel to $AB$.

While $C$ and $D$ must be equidistant from the line $AB$, they can lie on opposite sides of the line $AB$. In such cases, the segment $CD$ will intersect the line $AB$ (unless $C$ and $D$ coincide, which is ruled out by the problem statement), and therefore cannot be parallel to $AB$.

**Final Answer:** False.<|im_end|>

Grade: {"valid": true, "method": "area", "repairable": false, "note": "Correct opposite-side equal-altitude counterexample, explicitly verified."}

## C15 sample 1

A,B are distinct points. C,D are distinct points off line AB, and triangles ABC and ABD have equal (unsigned) areas. Must CD be parallel to AB? Prove the assertion or give an explicit counterexample.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 1006; finish: stop.

### Logical Deduction

Let the line containing points $A$ and $B$ be denoted as $L$.
The area of a triangle with vertices $X, Y, Z$ is given by $\frac{1}{2} \times \text{base} \times \text{height}$, where the base lies on one side and the height is the perpendicular distance from the third vertex to the line containing the base.

1.  **Define Parameters**:
    *   Let the length of segment $AB$ be $b = |AB|$. Since $A$ and $B$ are distinct, $b > 0$.
    *   Let $h_C$ be the perpendicular distance from point $C$ to the line $AB$.
    *   Let $h_D$ be the perpendicular distance from point $D$ to the line $AB$.

2.  **Calculate Areas**:
    The problem states that triangles $ABC$ and $ABD$ have equal unsigned areas:
    $$ \text{Area}(ABC) = \text{Area}(ABD) $$
    Substituting the base-height formula (with common base $AB$):
    $$ \frac{1}{2} b h_C = \frac{1}{2} b h_D $$
    Since $b > 0$, we can divide both sides by $\frac{1}{2}b$:
    $$ h_C = h_D $$

3.  **Analyze the Geometric Implication**:
    *   Points $C$ and $D$ lie "off line $AB$", meaning their signed distances to the line are non-zero.
    *   We found that the absolute values of their distances to line $AB$ are equal ($|d(C, L)| = |d(D, L)|$).
    *   There are two possible scenarios for points with equal perpendicular distance to a line:
        *   **Case 1**: Both points lie on the same side of line $AB$. If so, they must lie on the same line parallel to $AB$ at distance $h_C$. Thus, $CD \parallel AB$.
        *   **Case 2**: The points lie on opposite sides of line $AB$. In this scenario, the lines connecting these points to the line $AB$ intersect, forming a 'bowtie' or trapezoid configuration where $CD$ is not parallel to $AB$.

4.  **Construct a Counterexample**:
    To prove that $CD$ does *not* necessarily have to be parallel to $AB$, we construct an explicit case where $C$ and $D$ are on opposite sides.
    
    *   Set coordinates: Let $A = (0, 0)$ and $B = (1, 0)$. Line $AB$ is the x-axis ($y=0$).
    *   Choose point $C$ at $(0, 1)$. Distance to x-axis is $1$.
    *   Choose point $D$ at $(1, -1)$. Distance to x-axis is $|-1| = 1$.
    *   **Check Areas**:
        *   $\text{Area}(ABC) = \frac{1}{2} \times |1-0| \times |1| = 0.5$.
        *   $\text{Area}(ABD) = \frac{1}{2} \times |1-0| \times |-1| = 0.5$.
        *   Areas are equal.
    *   **Check Parallelism**:
        *   Slope of $AB = 0$.
        *   Slope of $CD = \frac{-1 - 1}{1 - 0} = -2$.
        *   Since $-2 \neq 0$, $CD$ is **not** parallel to $AB$.
    *   **Verify Constraints**:
        *   $A, B$ are distinct? Yes.
        *   $C, D$ are distinct? Yes ($(0,1) \neq (1,-1)$).
        *   $C, D$ off line $AB$? Yes ($y \neq 0$).

### Conclusion

No, $CD$ does not necessarily have to be parallel to $AB$.

While equal areas imply that $C$ and $D$ are equidistant from the line $AB$, they may lie on **opposite sides** of that line. In such cases, the segment $CD$ intersects the line $AB$ (or its extension) and is therefore not parallel to it.

**Final Answer:** The assertion is false; $CD$ is not necessarily parallel to $AB$.<|im_end|>

Grade: {"valid": true, "method": "area", "repairable": false, "note": "Correct opposite-side equal-altitude counterexample, explicitly verified."}

## C16 sample 0

In an acute triangle ABC, the perpendicular from B to AC has the same length as the perpendicular from C to AB. Prove AB=AC.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 402; finish: stop.

### Mathematical Justification

Let $h_b$ be the length of the perpendicular from vertex $B$ to side $AC$, and let $h_c$ be the length of the perpendicular from vertex $C$ to side $AB$.
By definition, these lengths represent the altitudes of $\triangle ABC$ corresponding to sides $b$ ($AC$) and $c$ ($AB$), respectively. Thus:
$$h_b = b \sin A$$
$$h_c = c \sin A$$

We are given that $h_b = h_c$. Substituting the expressions above:
$$b \sin A = c \sin A$$

Since $\triangle ABC$ is an acute triangle, angle $A$ is strictly between $0^\circ$ and $90^\circ$. Therefore, $\sin A > 0$, allowing us to divide both sides by $\sin A$:
$$b = c$$

In terms of the side lengths opposite the vertices, this means:
$$AC = AB$$

*(Alternative Geometric Proof via Right Triangles)*:
Consider right-angled triangles formed by the altitudes: $\triangle ABD$ (where $D$ is on $AC$) and $\triangle ACE$ (where $E$ is on $AB$).
1. In $\triangle ABD$ and $\triangle ACE$:
   - $\angle ADB = \angle AEC = 90^\circ$ (by construction of altitudes).
   - $\angle DAB = \angle EAC$ (common angle $A$).
   - Given $BD = CE$ (equal altitudes).
2. By the AAS (Angle-Angle-Side) congruence criterion, $\triangle ABD \cong \triangle ACE$.
3. Corresponding parts of congruent triangles are equal; therefore, hypotenuse $AB = AC$.

### Final Conclusion
$$AB = AC$$<|im_end|>

Grade: {"valid": true, "method": "synthetic", "repairable": false, "note": "Initial altitude-sine assignments interchange b and c. An independent complete correct AAS proof follows. Count as proof present; exclude in conservative whole-answer sensitivity.", "ancillary_math_error": true, "whole_answer_conservative_valid": false}

## C16 sample 1

In an acute triangle ABC, the perpendicular from B to AC has the same length as the perpendicular from C to AB. Prove AB=AC.
Give a complete, concise mathematical justification. Any correct method is allowed. State your final conclusion clearly.

Tokens: 379; finish: stop.

### Mathematical Justification

Let the side lengths of triangle $ABC$ be denoted as $a$, $b$, and $c$, corresponding to sides opposite vertices $A$, $B$, and $C$ respectively.
Let $h_b$ be the length of the perpendicular from vertex $B$ to side $AC$.
Let $h_c$ be the length of the perpendicular from vertex $C$ to side $AB$.

The area of triangle $ABC$ can be expressed in two ways using these altitudes:
$$ \text{Area} = \frac{1}{2} b h_b $$
$$ \text{Area} = \frac{1}{2} c h_c $$

Equating the two expressions for the area:
$$ \frac{1}{2} b h_b = \frac{1}{2} c h_c $$
$$ b h_b = c h_c \quad \dots (1) $$

We are given that the lengths of the perpendiculars are equal, so:
$$ h_b = h_c \quad \dots (2) $$

Substituting equation (2) into equation (1):
$$ b(h_b) = c(h_b) $$

Since $\triangle ABC$ is a non-degenerate triangle, its altitude $h_b > 0$. Therefore, we can divide both sides by $h_b$:
$$ b = c $$

By definition, $b = AC$ and $c = AB$. Thus:
$$ AC = AB $$

*(Note: Since $AB = AC$, the base angles are equal ($\angle B = \angle C$), confirming the triangle is acute if the vertex angle $A < 90^\circ$, which is consistent with the problem statement.)*

### Final Conclusion

**AB = AC**<|im_end|>

Grade: {"valid": true, "method": "area", "repairable": false, "note": "Correct area argument or an independent correct right-triangle AAS argument."}
