## F01 sample 0

A point S outside a circle has a tangent ST. A secant meets the circle at U,V in the order S,U,V, with SU=3 and UV=9. Find ST. Establish the product identity you use from similar triangles instead of citing the power-of-a-point theorem.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 6012; finish: stop.



To find the length of the tangent segment $ST$, we establish the relationship between the tangent and the secant using the properties of similar triangles.

### 1. Geometric Setup and Similarity
Consider the two triangles $\triangle STU$ and $\triangle SVT$ formed within the figure:
*   $\triangle STU$ is formed by the tangent segment $ST$, the secant segment $SU$, and the chord $TU$.
*   $\triangle SVT$ is formed by the tangent segment $ST$, the entire secant segment $SV$, and the chord $TV$.

We analyze the angles of these triangles to determine if they are similar:
1.  **Common Angle:** Both triangles share the angle at vertex $S$ (denoted as $\angle S$ or $\angle TSU$).
2.  **Angle Equality:** Consider $\angle STU$ and $\angle SVT$.
    *   $\angle STU$ is the angle formed by the tangent line $ST$ and the chord $TU$.
    *   By the **Alternate Segment Theorem** (also known as the Tangent-Chord Theorem), the angle between a tangent and a chord through the point of contact is equal to the angle subtended by the chord in the alternate segment of the circle. Therefore, $\angle STU$ is equal to the angle subtended by chord $TU$ at point $V$ on the circle, which is $\angle TVU$.
    *   Since points $S$, $U$, and $V$ are collinear (with $U$ between $S$ and $V$), the angle $\angle TVU$ is geometrically identical to the angle $\angle SVT$ (the angle formed by secant $SV$ and chord $TV$ at vertex $V$).
    *   Thus, $\angle STU = \angle SVT$.

Since two angles are equal ($\angle S = \angle S$ and $\angle STU = \angle SVT$), the triangles are similar by the **AA (Angle-Angle) Similarity Criterion**:
$$ \triangle STU \sim \triangle SVT $$

### 2. Establishing the Product Identity
Because the triangles are similar, the ratio of their corresponding sides is constant. Matching vertices $S \leftrightarrow S$, $T \leftrightarrow V$, and $U \leftrightarrow T$, we write the proportions:
$$ \frac{ST}{SV} = \frac{SU}{ST} $$
Rearranging this proportion to isolate the squares yields the product identity:
$$ ST^2 = SU \cdot SV $$
*(This effectively derives the specific case of the Power of a Point theorem using similar triangles.)*

### 3. Calculation
We are given the following lengths:
*   $SU = 3$
*   $UV = 9$

First, we determine the total length of the secant segment $SV$. Since $U$ lies between $S$ and $V$:
$$ SV = SU + UV = 3 + 9 = 12 $$

Now, substitute the values into our derived identity:
$$ ST^2 = 3 \cdot 12 $$
$$ ST^2 = 36 $$

Taking the square root (as length must be positive):
$$ ST = 6 $$

### Final Result
$$ ST = 6 $$<|im_end|>

Grade: {"valid": true, "method": "synthetic", "note": "Correct tangent-chord angle and explicit STU-SVT correspondence derive ST=6.", "repairable": false}

## F01 sample 1

A point S outside a circle has a tangent ST. A secant meets the circle at U,V in the order S,U,V, with SU=3 and UV=9. Find ST. Establish the product identity you use from similar triangles instead of citing the power-of-a-point theorem.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 4453; finish: stop.



**Solution:**

**1. Geometric Setup and Construction**
Consider the circle containing points $U$ and $V$. Let us draw the chord $UT$ and the chord $VT$ to connect the points of intersection on the secant with the point of tangency. This creates two triangles: $\triangle STU$ and $\triangle SVT$.

**2. Proof of Similarity**
To establish the product identity, we demonstrate that these two triangles are similar using the Angle-Angle (AA) criterion.

*   **Common Angle:** Both triangles share the angle at vertex $S$.
    $$ \angle TSU = \angle VST $$
*   **Tangent-Chord Property:** According to the Tangent-Chord Theorem (also known as the Alternate Segment Theorem), the angle formed between a tangent and a chord through the point of contact is equal to the angle in the alternate segment. Here, the angle between the tangent $ST$ and the chord $TU$ is $\angle STU$. The angle in the alternate segment subtended by the chord $TU$ is $\angle SVT$ (the angle at $V$ on the circle).
    $$ \angle STU = \angle SVT $$

Since two corresponding angles are equal, the triangles are similar:
$$ \triangle STU \sim \triangle SVT $$

**3. Derivation of the Product Identity**
Because $\triangle STU \sim \triangle SVT$, the lengths of their corresponding sides are proportional. Mapping the vertices $S \to S$, $T \to V$, and $U \to T$, the ratio of the sides is:

$$ \frac{ST}{SV} = \frac{SU}{ST} $$

Cross-multiplying these terms establishes the required product identity:
$$ ST^2 = SU \cdot SV $$

**4. Calculation**
We are given:
*   $SU = 3$
*   $UV = 9$

Since the points lie in the order $S, U, V$, the total length of the secant segment $SV$ is the sum of $SU$ and $UV$:
$$ SV = SU + UV = 3 + 9 = 12 $$

Substitute the known values into the derived identity:
$$ ST^2 = 3 \cdot 12 $$
$$ ST^2 = 36 $$

Taking the square root (lengths must be positive):
$$ ST = 6 $$

**Final Result:**
The length of the tangent $ST$ is **6**.<|im_end|>

Grade: {"valid": true, "method": "synthetic", "note": "Correct tangent-chord angle and explicit STU-SVT correspondence derive ST=6.", "repairable": false}

## F02 sample 0

Two chords AC and BD of a circle meet at an interior point P. PA=3, PC=8, PB=4. Find PD. Derive the needed product relation from angles and similar triangles instead of quoting the intersecting-chords theorem.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 8192; finish: length.

[No completed final answer; raw generation retained in the source JSON.]

Grade: {"valid": false, "method": "none", "note": "Token limit reached without a complete final proof.", "repairable": false}

## F02 sample 1

Two chords AC and BD of a circle meet at an interior point P. PA=3, PC=8, PB=4. Find PD. Derive the needed product relation from angles and similar triangles instead of quoting the intersecting-chords theorem.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 8192; finish: length.

[No completed final answer; raw generation retained in the source JSON.]

Grade: {"valid": false, "method": "none", "note": "Token limit reached without a complete final proof.", "repairable": false}

## F03 sample 0

Triangle ABC is right-angled at A. The perpendicular from A to BC meets BC at D. Given BD=4 and DC=9, find AD and AB. Justify the relations rather than citing a special theorem about the altitude to a hypotenuse.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 7048; finish: stop.



Let $h$ denote the length of the altitude $AD$.
We define the lengths of the segments as follows: $BD = 4$, $DC = 9$, and thus the total length of the hypotenuse is $BC = BD + DC = 13$.

### Justification of Relations

We apply the Pythagorean Theorem ($x^2 + y^2 = z^2$) to the three right-angled triangles present in the figure: $\triangle ABD$, $\triangle ACD$, and $\triangle ABC$.

1.  **For $\triangle ABD$ (right-angled at $D$):**
    $$AB^2 = AD^2 + BD^2$$
    $$AB^2 = h^2 + 4^2$$
    $$AB^2 = h^2 + 16 \quad \text{--- (Equation 1)}$$

2.  **For $\triangle ACD$ (right-angled at $D$):**
    $$AC^2 = AD^2 + DC^2$$
    $$AC^2 = h^2 + 9^2$$
    $$AC^2 = h^2 + 81 \quad \text{--- (Equation 2)}$$

3.  **For $\triangle ABC$ (right-angled at $A$):**
    $$AB^2 + AC^2 = BC^2$$
    $$AB^2 + AC^2 = 13^2$$
    $$AB^2 + AC^2 = 169 \quad \text{--- (Equation 3)}$$

Substitute Equation 1 and Equation 2 into Equation 3:
$$(h^2 + 16) + (h^2 + 81) = 169$$

Combine like terms:
$$2h^2 + 97 = 169$$

Isolate $h^2$:
$$2h^2 = 169 - 97$$
$$2h^2 = 72$$
$$h^2 = 36$$
$$h = 6$$

This derivation proves that $AD^2 = BD \cdot DC$ without citing a special theorem (since $36 = 4 \cdot 9$).

### Calculation of Lengths

**Finding AD:**
From the derivation above:
$$AD = 6$$

**Finding AB:**
Using Equation 1 with the known value of $AD$:
$$AB^2 = 6^2 + 4^2$$
$$AB^2 = 36 + 16$$
$$AB^2 = 52$$
$$AB = \sqrt{52}$$
Simplifying the radical:
$$AB = \sqrt{4 \cdot 13} = 2\sqrt{13}$$

### Final Result
$$AD = 6$$
$$AB = 2\sqrt{13}$$<|im_end|>

Grade: {"valid": true, "method": "analytic", "note": "Three justified Pythagorean equations give the requested lengths.", "repairable": false}

## F03 sample 1

Triangle ABC is right-angled at A. The perpendicular from A to BC meets BC at D. Given BD=4 and DC=9, find AD and AB. Justify the relations rather than citing a special theorem about the altitude to a hypotenuse.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 7201; finish: stop.



Let $A$, $B$, and $C$ be the vertices of the triangle such that $\angle BAC = 90^\circ$. The line segment $AD$ is drawn perpendicular to $BC$, intersecting it at $D$. We are given $BD = 4$ and $DC = 9$.

### 1. Justification of the relation for $AD$

To find the length of the altitude $AD$, we first analyze the angles within the triangles.

Since $\triangle ABC$ is right-angled at $A$, we have:
$$ \angle BAD + \angle CAD = 90^\circ $$

Since $AD$ is perpendicular to $BC$, $\angle ADB = \angle ADC = 90^\circ$.
Considering the right-angled triangle $\triangle ABD$, the sum of angles is $180^\circ$:
$$ \angle B + \angle BAD + 90^\circ = 180^\circ \implies \angle B = 90^\circ - \angle BAD $$
From the equation $\angle BAD + \angle CAD = 90^\circ$, we have $\angle CAD = 90^\circ - \angle BAD$.
Therefore:
$$ \angle B = \angle CAD $$

Now compare $\triangle ABD$ and $\triangle CAD$:
1.  $\angle ADB = \angle CDA = 90^\circ$.
2.  $\angle B = \angle CAD$ (proved above).

By the Angle-Angle (AA) similarity criterion, $\triangle ABD \sim \triangle CAD$.

Because the triangles are similar, the ratio of their corresponding sides is constant. In particular, we compare the sides opposite the equal angles:
*   The side opposite $\angle B$ in $\triangle ABD$ is $AD$.
*   The side opposite $\angle CAD$ in $\triangle CAD$ is $CD$.
*   The side opposite $\angle BAD$ in $\triangle ABD$ is $BD$.
*   The side opposite $\angle C$ in $\triangle CAD$ is $AD$. (Note: $\angle C$ corresponds to $\angle BAD$).

Setting up the proportion of the legs opposite these matching angles:
$$ \frac{BD}{AD} = \frac{AD}{CD} $$

Cross-multiplying gives the relation:
$$ AD^2 = BD \cdot DC $$

### 2. Calculation of $AD$

Substitute the given values $BD = 4$ and $DC = 9$:
$$ AD^2 = 4 \cdot 9 $$
$$ AD^2 = 36 $$
$$ AD = 6 $$

### 3. Calculation of $AB$

We determine $AB$ using the Pythagorean Theorem on the right-angled triangle $\triangle ABD$ (where the right angle is at $D$):
$$ AB^2 = AD^2 + BD^2 $$

Substituting the known values:
$$ AB^2 = 6^2 + 4^2 $$
$$ AB^2 = 36 + 16 $$
$$ AB^2 = 52 $$

Taking the square root:
$$ AB = \sqrt{52} = \sqrt{4 \cdot 13} = 2\sqrt{13} $$

***

**Final Results:**
$$ AD = 6 $$
$$ AB = 2\sqrt{13} $$<|im_end|>

Grade: {"valid": true, "method": "synthetic", "note": "Correct AA similarity ABD-CAD gives AD²=BD*DC, then Pythagoras gives AB.", "repairable": false}

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

Tokens: 6115; finish: stop.



Let $a = AB = 6$ and $b = CD = 10$. Since $ABCD$ is a trapezoid with $AB \parallel CD$, the diagonals $AC$ and $BD$ intersect at $O$.

**Step 1: Determine ratios on the diagonals.**
Since $AB \parallel CD$, the alternate interior angles are equal ($\angle OAB = \angle OCD$ and $\angle OBA = \angle ODC$). Consequently, triangle $OAB$ is similar to triangle $OCD$ ($\triangle OAB \sim \triangle OCD$).
The ratio of similarity is given by the lengths of the parallel bases:
$$ \frac{OA}{OC} = \frac{OB}{OD} = \frac{AB}{CD} = \frac{6}{10} = \frac{3}{5} $$
From this proportion, we can determine the ratios of the segments of the diagonal $AC$:
$$ \frac{OA}{AC} = \frac{OA}{OA + OC} = \frac{3}{3 + 5} = \frac{3}{8} $$
$$ \frac{OC}{AC} = \frac{OC}{OA + OC} = \frac{5}{5 + 3} = \frac{5}{8} $$

**Step 2: Calculate the length of segment $EO$.**
Consider $\triangle ADC$. We are given that $EF \parallel CD$, so $EO \parallel DC$. Since $E$ lies on $AD$ and $O$ lies on $AC$, $\triangle AEO$ is similar to $\triangle ADC$ ($\triangle AEO \sim \triangle ADC$).
Using the similarity ratio:
$$ \frac{EO}{CD} = \frac{AO}{AC} $$
Substituting the known values ($CD=10$ and $AO/AC = 3/8$):
$$ EO = 10 \cdot \frac{3}{8} = \frac{30}{8} = \frac{15}{4} $$

**Step 3: Calculate the length of segment $OF$.**
Consider $\triangle ABC$. Since $EF \parallel AB$, we have $OF \parallel AB$. With $F$ on $BC$ and $O$ on $AC$, $\triangle COF$ is similar to $\triangle CAB$ ($\triangle COF \sim \triangle CAB$).
Using the similarity ratio:
$$ \frac{OF}{AB} = \frac{CO}{AC} $$
Substituting the known values ($AB=6$ and $CO/AC = 5/8$):
$$ OF = 6 \cdot \frac{5}{8} = \frac{30}{8} = \frac{15}{4} $$

**Step 4: Calculate the total length $EF$.**
Since $O$ lies on the segment $EF$ within the trapezoid, $EF = EO + OF$.
$$ EF = \frac{15}{4} + \frac{15}{4} = \frac{30}{4} = \frac{15}{2} $$

Alternatively, using the harmonic mean formula derived above ($EF = \frac{2ab}{a+b}$):
$$ EF = \frac{2 \cdot 6 \cdot 10}{6 + 10} = \frac{120}{16} = 7.5 $$

Final Result:
The length of $EF$ is $\frac{15}{2}$ or $7.5$.<|im_end|>

Grade: {"valid": true, "method": "synthetic", "note": "Correct diagonal similarity plus two parallel-segment similarities derive EO and OF, then EF=15/2.", "repairable": false}

## F05 sample 1

ABCD is a convex trapezoid with AB parallel to CD, AB=6, CD=10. Diagonals AC and BD intersect at O. The line through O parallel to the bases meets AD at E and BC at F. Find EF.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 8192; finish: length.

[No completed final answer; raw generation retained in the source JSON.]

Grade: {"valid": false, "method": "none", "note": "Token limit reached without a complete final proof.", "repairable": false}

## F06 sample 0

In triangle ABC, D is inside AB and E is inside AC, with AD/DB=AE/EC=2/3. Lines BE and CD intersect at F. Find BF/FE.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 8192; finish: length.

[No completed final answer; raw generation retained in the source JSON.]

Grade: {"valid": false, "method": "none", "note": "Token limit reached without a complete final proof.", "repairable": false}

## F06 sample 1

In triangle ABC, D is inside AB and E is inside AC, with AD/DB=AE/EC=2/3. Lines BE and CD intersect at F. Find BF/FE.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 8192; finish: length.

[No completed final answer; raw generation retained in the source JSON.]

Grade: {"valid": false, "method": "none", "note": "Token limit reached without a complete final proof.", "repairable": false}

## F07 sample 0

The two tangents from T touch a circle at A and B, and TA=7. A third tangent touches the minor arc AB at P and meets the segments TA and TB at X and Y. Assume P lies between X and Y, with T,X,A and T,Y,B in those respective orders. Find the perimeter of triangle TXY.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 7721; finish: stop.



Let the circle be denoted by $\mathcal{C}$. Let $T$ be the external point.
From the problem statement, $TA$ and $TB$ are tangents to $\mathcal{C}$ from $T$, touching the circle at $A$ and $B$ respectively. It is given that $TA = 7$. By the property of tangents drawn from an external point to a circle, their lengths are equal. Therefore:
$$TB = TA = 7$$

Consider the third tangent line to $\mathcal{C}$ at point $P$, which intersects the segment $TA$ at $X$ and the segment $TB$ at $Y$.

We analyze the properties of tangent segments for the points $X$ and $Y$:

1.  **Point $X$:** The point $X$ lies on the line segment $TA$. Since $TA$ is tangent to $\mathcal{C}$ at $A$, the segment $XA$ is a tangent segment starting at $X$ and ending at the point of tangency $A$.
    Additionally, the line $XY$ is tangent to $\mathcal{C}$ at $P$. Thus, the segment $XP$ is also a tangent segment starting at $X$ and ending at the point of tangency $P$.
    According to the theorem that tangent segments from an external point to a circle are congruent, we have:
    $$XP = XA$$

2.  **Point $Y$:** Similarly, the point $Y$ lies on the line segment $TB$. Since $TB$ is tangent to $\mathcal{C}$ at $B$, the segment $YB$ is a tangent segment from $Y$.
    Also, the segment $YP$ is part of the tangent line $XY$ touching at $P$.
    Applying the same tangent property for point $Y$, we have:
    $$YP = YB$$

We wish to find the perimeter of triangle $TXY$, denoted as $Perim(TXY)$.
$$Perim(TXY) = TX + XY + YT$$

Since $P$ lies between $X$ and $Y$, the length of segment $XY$ is the sum of segments $XP$ and $PY$:
$$XY = XP + PY$$

Substituting this into the perimeter expression:
$$Perim(TXY) = TX + (XP + PY) + YT$$
$$Perim(TXY) = TX + XP + PY + YT$$

Now, substitute the equalities derived from the tangent properties ($XP = XA$ and $PY = YB$):
$$Perim(TXY) = TX + XA + YB + YT$$

Group the terms associated with each original tangent segment $TA$ and $TB$:
$$Perim(TXY) = (TX + XA) + (YT + YB)$$

From the problem statement, $X$ lies on the segment $TA$ such that $T, X, A$ are in that order, which implies $TX + XA = TA$. Similarly, $Y$ lies on the segment $TB$ such that $T, Y, B$ are in that order, implying $YT + YB = TB$.

Thus:
$$Perim(TXY) = TA + TB$$

Given that $TA = 7$ and $TB = 7$:
$$Perim(TXY) = 7 + 7 = 14$$

**Final Result:**
The perimeter of triangle $TXY$ is 14.<|im_end|>

Grade: {"valid": true, "method": "synthetic", "note": "Equal tangents and point orders give perimeter14.", "repairable": false}

## F07 sample 1

The two tangents from T touch a circle at A and B, and TA=7. A third tangent touches the minor arc AB at P and meets the segments TA and TB at X and Y. Assume P lies between X and Y, with T,X,A and T,Y,B in those respective orders. Find the perimeter of triangle TXY.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 8192; finish: length.

[No completed final answer; raw generation retained in the source JSON.]

Grade: {"valid": false, "method": "none", "note": "Token limit reached without a complete final proof.", "repairable": false}

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

Tokens: 7805; finish: stop.



Let $D$ be the foot of the perpendicular dropped from vertex $B$ onto the line containing $AC$. The length of the segment $BD$ represents the perpendicular distance from $B$ to line $AC$. We aim to prove that $PE + PF = BD$.

**Justification:**

1.  **Area Calculation of $\triangle ABC$:**
    Consider $\triangle ABC$. Using the side $AC$ as the base, the corresponding altitude is the length $BD$. Thus, the area of $\triangle ABC$ is given by:
    $$ \text{Area}(\triangle ABC) = \frac{1}{2} \cdot AC \cdot BD $$

2.  **Decomposition of Area:**
    Since $P$ is a point on the segment $BC$, the triangle $\triangle ABC$ is composed of two smaller triangles: $\triangle PAB$ and $\triangle PAC$. These two triangles do not overlap in area except at the shared boundary $AP$. Therefore, the sum of their areas equals the area of $\triangle ABC$:
    $$ \text{Area}(\triangle PAB) + \text{Area}(\triangle PAC) = \text{Area}(\triangle ABC) $$

3.  **Expressing Areas of Sub-triangles:**
    *   For $\triangle PAB$, we take the side $AB$ as the base. Since $E$ is the perpendicular projection of $P$ onto the line $AB$, the length $PE$ is the height of this triangle relative to base $AB$.
        $$ \text{Area}(\triangle PAB) = \frac{1}{2} \cdot AB \cdot PE $$
    *   For $\triangle PAC$, we take the side $AC$ as the base. Since $F$ is the perpendicular projection of $P$ onto the line $AC$, the length $PF$ is the height of this triangle relative to base $AC$.
        $$ \text{Area}(\triangle PAC) = \frac{1}{2} \cdot AC \cdot PF $$

4.  **Derivation:**
    Substitute the expressions from Step 3 into the equation from Step 2:
    $$ \left( \frac{1}{2} \cdot AB \cdot PE \right) + \left( \frac{1}{2} \cdot AC \cdot PF \right) = \frac{1}{2} \cdot AC \cdot BD $$

5.  **Application of Isosceles Property:**
    We are given that $\triangle ABC$ is isosceles with $AB = AC$. We can substitute $AC$ for $AB$ in the term related to $PE$:
    $$ \frac{1}{2} \cdot AC \cdot PE + \frac{1}{2} \cdot AC \cdot PF = \frac{1}{2} \cdot AC \cdot BD $$

6.  **Conclusion:**
    Since $AC$ is a non-zero length, we can divide the entire equation by $\frac{1}{2} \cdot AC$:
    $$ PE + PF = BD $$

Thus, the sum of the perpendicular projections of $P$ onto $AB$ and $AC$ equals the perpendicular distance from $B$ to line $AC$.

**Final Result:**
$$ PE + PF = \text{Perpendicular Distance from } B \text{ to line } AC $$<|im_end|>

Grade: {"valid": true, "method": "area", "note": "Correct area decomposition and equal-side cancellation, valid for arbitrary apex angle.", "repairable": false}

## F09 sample 1

ABC is an isosceles triangle with AB=AC. P is any point in the interior of BC. E and F are the perpendicular projections of P onto the lines AB and AC. Prove that PE+PF equals the perpendicular distance from B to line AC.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 4833; finish: stop.



Let $h$ denote the perpendicular distance from vertex $B$ to the line $AC$. By definition, $h$ corresponds to the length of the altitude drawn from $B$ to $AC$.

**Proof:**

1.  **Decomposition of Area:**
    Since $P$ lies on the segment $BC$ (the interior of $BC$), we can express the area of $\triangle ABC$ as the sum of the areas of $\triangle ABP$ and $\triangle APC$.
    $$ \text{Area}(\triangle ABC) = \text{Area}(\triangle ABP) + \text{Area}(\triangle APC) $$

2.  **Calculation of Individual Areas:**
    Using the formula $\text{Area} = \frac{1}{2} \times \text{base} \times \text{height}$:
    *   For $\triangle ABC$, taking $AC$ as the base, the corresponding height is $h$. Thus:
        $$ \text{Area}(\triangle ABC) = \frac{1}{2} \cdot AC \cdot h $$
    *   For $\triangle ABP$, taking $AB$ as the base, the corresponding height is the perpendicular projection $PE$. Thus:
        $$ \text{Area}(\triangle ABP) = \frac{1}{2} \cdot AB \cdot PE $$
    *   For $\triangle APC$, taking $AC$ as the base, the corresponding height is the perpendicular projection $PF$. Thus:
        $$ \text{Area}(\triangle APC) = \frac{1}{2} \cdot AC \cdot PF $$

3.  **Substitution and Simplification:**
    Substituting these area expressions into the decomposition equation:
    $$ \frac{1}{2} \cdot AC \cdot h = \frac{1}{2} \cdot AB \cdot PE + \frac{1}{2} \cdot AC \cdot PF $$
    
    Multiplying both sides by 2 gives:
    $$ AC \cdot h = AB \cdot PE + AC \cdot PF $$
    
    We are given that $\triangle ABC$ is isosceles with $AB = AC$. Substituting $AB$ with $AC$ in the second term (or vice versa):
    $$ AC \cdot h = AC \cdot PE + AC \cdot PF $$
    
    Factoring out $AC$:
    $$ AC \cdot h = AC \cdot (PE + PF) $$
    
    Since $AC$ is the length of a side of a non-degenerate triangle, $AC \neq 0$. Dividing both sides by $AC$ yields:
    $$ h = PE + PF $$

**Final Result:**
$$ PE + PF = \text{perpendicular distance from } B \text{ to line } AC $$<|im_end|>

Grade: {"valid": true, "method": "area", "note": "Correct area decomposition and equal-side cancellation, valid for arbitrary apex angle.", "repairable": false}

## F10 sample 0

ABCD is a convex trapezoid with AB parallel to CD, AB>CD, and AD=BC. Prove that A,B,C,D lie on one circle.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 8192; finish: length.

[No completed final answer; raw generation retained in the source JSON.]

Grade: {"valid": false, "method": "none", "note": "Token limit reached without a complete final proof.", "repairable": false}

## F10 sample 1

ABCD is a convex trapezoid with AB parallel to CD, AB>CD, and AD=BC. Prove that A,B,C,D lie on one circle.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 5380; finish: stop.



**Proof:**

Let $h$ be the distance between the parallel lines $AB$ and $CD$. Since $AB \parallel CD$, the perpendicular distance from any point on $CD$ to the line containing $AB$ is equal to $h$.

Let us drop perpendiculars from points $D$ and $C$ to the line $AB$. Let $P$ be the foot of the perpendicular from $D$ onto $AB$, and $Q$ be the foot of the perpendicular from $C$ onto $AB$.

Thus, we have two right-angled triangles, $\triangle APD$ and $\triangle BQC$, satisfying the following conditions:
1.  $\angle DPA = \angle CQB = 90^\circ$.
2.  $DP = h$ and $CQ = h$ (since both represent the distance between the parallel lines).
3.  $AD = BC$ (given in the problem statement).

By the Hypotenuse-Leg (HL) theorem for congruent right-angled triangles, since the hypotenuses ($AD = BC$) are equal and the legs ($DP = CQ$) are equal, we conclude that:
$$ \triangle APD \cong \triangle BQC $$

Since the triangles are congruent, their corresponding acute angles are equal. Specifically:
$$ \angle DAP = \angle CBQ $$
Note that since $ABCD$ is a convex quadrilateral with $AB$ as the base, $\angle DAP$ corresponds to $\angle DAB$ and $\angle CBQ$ corresponds to $\angle CBA$. Therefore, the base angles of the trapezoid are equal:
$$ \angle DAB = \angle CBA $$

Because $ABCD$ is a trapezoid with $AB \parallel CD$, the consecutive interior angles along a transversal (the legs $AD$ and $BC$) are supplementary. Therefore:
$$ \angle DAB + \angle ADC = 180^\circ $$
$$ \angle CBA + \angle BCD = 180^\circ $$

Substituting the previously established fact that $\angle DAB = \angle CBA$ into the second equation, we get:
$$ \angle DAB + \angle BCD = 180^\circ $$

We have demonstrated that the sum of a pair of opposite angles ($\angle DAB$ and $\angle BCD$) is $180^\circ$. According to the converse of the property of cyclic quadrilaterals (where a quadrilateral is cyclic if and only if the sum of its opposite angles is $180^\circ$), the vertices $A, B, C,$ and $D$ must lie on a single circle.

**Conclusion:**
The vertices $A, B, C, D$ are concyclic.<|im_end|>

Grade: {"valid": true, "method": "synthetic", "note": "Equal-height right-triangle congruence gives equal base angles, then cyclicity. The feet lie on the longer base under the full given conditions; this positional detail is implicit, not a counterexample to the proof.", "repairable": false}

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

Tokens: 8192; finish: length.

[No completed final answer; raw generation retained in the source JSON.]

Grade: {"valid": false, "method": "none", "note": "Token limit reached without a complete final proof.", "repairable": false}

## F12 sample 1

Two nondegenerate triangles ABC and DEF satisfy AB/DE=AC/DF and angle ABC=angle DEF. Must the triangles be similar with correspondence A-D, B-E, C-F? Prove it or give an explicit counterexample.
Give a complete, concise mathematical justification. Do not assume the conclusion. Any correct method is allowed. Clearly state your final result.

Tokens: 8192; finish: length.

[No completed final answer; raw generation retained in the source JSON.]

Grade: {"valid": false, "method": "none", "note": "Token limit reached without a complete final proof.", "repairable": false}
