## B04 / 0

Let M=(0,0), A=(a,b), and H=(u,v), where a^2+b^2>0. Derive the coordinates of the foot P of the perpendicular from H to the line MA. Do not assume that P lies on the segment MA. Give the necessary justification and a concise final solution.



### Derivation and Solution

To derive the coordinates of the foot $P$ of the perpendicular from $H(u,v)$ to the line passing through $M(0,0)$ and $A(a,b)$, we utilize vector algebra.

**1. Coordinate Setup and Line Definition**
Let the position vector of a generic point on the line passing through $M$ and $A$ be denoted by $\mathbf{r}$.
Since the line passes through the origin $M(0,0)$ and the point $A(a,b)$, its direction vector is $\vec{d} = (a, b)$.
Any point $P$ lying on this infinite line can be represented as a scalar multiple of $\vec{d}$:
$$ P = (x, y) = k(a, b) = (ka, kb) $$
where $k$ is a real constant. Note that the condition $a^2 + b^2 > 0$ ensures that $A$ is not the origin, defining a valid unique line.

**2. Perpendicularity Condition**
The point $P$ is the foot of the perpendicular from $H(u,v)$ to line $MA$. This implies that the vector $\vec{HP}$ connecting $H$ to $P$ must be orthogonal to the direction vector of the line $\vec{MA} = (a, b)$.

First, determine the vector $\vec{HP}$:
$$ \vec{HP} = P - H = (ka - u, kb - v) $$

Next, set the dot product of $\vec{HP}$ and $\vec{MA}$ to zero:
$$ \vec{HP} \cdot \vec{MA} = 0 $$
$$ (ka - u)(a) + (kb - v)(b) = 0 $$

**3. Calculation of the Parameter $k$**
Expand the terms:
$$ ka^2 - ua + kb^2 - vb = 0 $$
Group the terms containing $k$:
$$ k(a^2 + b^2) - (au + vb) = 0 $$
Solve for $k$:
$$ k(a^2 + b^2) = au + vb $$
$$ k = \frac{au + vb}{a^2 + b^2} $$

Since $a^2 + b^2 \neq 0$, the value for $k$ is uniquely determined. This parameterization naturally handles points on the segment $MA$ (where $0 \le k \le 1$), the endpoint $A$ (where $k=1$), the origin $M$ (where $k=0$), and points on the line extensions beyond these bounds (where $|k|$ is outside these limits), satisfying the requirement not to assume $P$ lies strictly on the segment.

**4. Final Coordinates**
Substitute the value of $k$ back into the expressions for the coordinates of $P$:

$$ x_P = k a = a \left( \frac{au + vb}{a^2 + b^2} \right) = \frac{a(au + vb)}{a^2 + b^2} = \frac{a^2 u + ab v}{a^2 + b^2} $$

$$ y_P = k b = b \left( \frac{au + vb}{a^2 + b^2} \right) = \frac{b(au + vb)}{a^2 + b^2} = \frac{ab u + b^2 v}{a^2 + b^2} $$

***

### Final Solution

The coordinates of the foot of the perpendicular $P(x,y)$ are:

$$ P = \left( \frac{a(au + vb)}{a^2 + b^2}, \frac{b(au + vb)}{a^2 + b^2} \right) $$

Or, written with expanded numerators:

$$ P = \left( \frac{a^2u + abv}{a^2+b^2}, \frac{ab u + b^2v}{a^2+b^2} \right) $$

## B04 / 1

Let M=(0,0), A=(a,b), and H=(u,v), where a^2+b^2>0. Derive the coordinates of the foot P of the perpendicular from H to the line MA. Do not assume that P lies on the segment MA. Give the necessary justification and a concise final solution.



To derive the coordinates of the foot $P$ of the perpendicular from $H(u, v)$ to the line $MA$, we treat the problem using vector geometry. Let $M$ be the origin, so we can define the relevant position vectors.

### 1. Geometric Setup and Justification

Let the coordinates of point $P$ be $(x, y)$.
The line $MA$ passes through the origin $M(0,0)$ and the point $A(a, b)$. The direction vector of this line is $\vec{d} = \langle a, b \rangle$.

**Condition 1: Collinearity (Point P lies on the line)**
Since $P$ lies on the line $MA$, the vector $\vec{MP}$ must be parallel to the direction vector $\vec{d}$. Therefore, there exists a real scalar $k$ such that:
$$ \vec{MP} = k\vec{d} $$
In coordinates:
$$ x - 0 = ka \implies x = ka $$
$$ y - 0 = kb \implies y = kb $$
So, $P$ can be written generally as $(ka, kb)$. By choosing $k \in \mathbb{R}$ (any real number), we do not assume that $P$ lies on the segment $MA$; it covers the entire infinite line.

**Condition 2: Perpendicularity (HP is perpendicular to MA)**
Since $HP$ is perpendicular to the line $MA$, the vector $\vec{HP}$ must be orthogonal to the direction vector $\vec{d} = \langle a, b \rangle$.
First, determine vector $\vec{HP}$:
$$ \vec{HP} = P - H = \langle ka - u, kb - v \rangle $$

Now, apply the dot product condition for orthogonality ($\vec{HP} \cdot \vec{d} = 0$):
$$ a(ka - u) + b(kb - v) = 0 $$

### 2. Solving for $k$

Expand the dot product equation:
$$ a^2k - au + b^2k - bv = 0 $$

Group the terms containing $k$:
$$ k(a^2 + b^2) = au + bv $$

Solve for $k$. Since $a^2 + b^2 > 0$, division is valid:
$$ k = \frac{au + bv}{a^2 + b^2} $$

### 3. Calculating Coordinates of P

Substitute the value of $k$ back into the expressions for $x$ and $y$:

$$ x = ka = \frac{a(au + bv)}{a^2 + b^2} = \frac{a^2u + abv}{a^2 + b^2} $$
$$ y = kb = \frac{b(au + bv)}{a^2 + b^2} = \frac{ab u + b^2v}{a^2 + b^2} $$

### Final Solution

The coordinates of the foot $P$ are:

$$ P = \left( \frac{a^2u + abv}{a^2 + b^2}, \frac{ab u + b^2v}{a^2 + b^2} \right) $$

Or in compact vector notation:
$$ P = \frac{au + bv}{a^2 + b^2} (a, b) $$

## B06 / 0

A secant from a point S outside a circle meets the circle at U and V, in the order S,U,V. The tangent from S touches the circle at T. Given SU=4 and UV=5, find ST. Prove the product identity you use by similarity of triangles in this configuration, rather than merely citing the power-of-a-point theorem. Give the necessary justification and a concise final solution.



To find the length of the tangent segment $ST$, we can utilize the relationship between the secant and tangent lengths, which is typically known as the Power of a Point Theorem. However, as requested, we will derive this identity using the similarity of triangles.

### Proof of the Identity using Similarity

Let us define the relevant points and triangles:
*   $S$: The external point.
*   $U, V$: Points of intersection of the secant with the circle (order $S, U, V$).
*   $T$: Point of tangency.

We examine the two triangles formed by these points: $\triangle SUT$ and $\triangle SVT$.

**1. Common Angle:**
In both triangles, the angle at vertex $S$ (let's call it $\angle TSV$ or $\angle USV$) is identical.
$$ \angle TSV = \angle TSV \quad (\text{Reflexive Property}) $$

**2. Tangent-Chord Angle Theorem (Alternate Segment Theorem):**
The theorem states that the angle between a tangent and a chord through the point of contact is equal to the angle in the alternate segment.
*   Consider the angle formed by the tangent $ST$ and the chord $TU$. This is $\angle STU$.
*   Consider the angle in the alternate segment subtended by the chord $TU$. Since $V$ is on the circle in the alternate segment, this angle is $\angle TVU$ (also denoted as $\angle SVT$).
Therefore:
$$ \angle STU = \angle SVT $$

**3. Conclusion on Similarity:**
Since two angles of $\triangle SUT$ are equal to two angles of $\triangle SVT$ (the common angle at $S$ and the angles $\angle STU$ and $\angle SVT$), the triangles are similar by the **AA (Angle-Angle) Similarity Criterion**.
$$ \triangle SUT \sim \triangle SVT $$

**4. Deriving the Length Formula:**
Because the triangles are similar, their corresponding sides are proportional. We determine the correspondence based on the ordered vertices identified above:
*   Vertex $S$ corresponds to Vertex $S$.
*   Vertex $T$ (with angle equal to $\angle STU$) corresponds to Vertex $V$ (with angle equal to $\angle SVT$).
*   Vertex $U$ corresponds to Vertex $T$ (remaining angle correspondence).

Setting up the ratios of corresponding sides:
$$ \frac{SU}{ST} = \frac{ST}{SV} $$

Cross-multiplying yields the Power of a Point identity for this configuration:
$$ ST^2 = SU \cdot SV $$

---

### Calculation

**1. Determine the lengths of the segments:**
*   We are given $SU = 4$.
*   We are given $UV = 5$.
*   Since $S, U, V$ lie in that order, the length of the entire secant segment $SV$ is the sum of its parts:
    $$ SV = SU + UV $$
    $$ SV = 4 + 5 = 9 $$

**2. Solve for $ST$:**
Using the identity derived above:
$$ ST^2 = SU \cdot SV $$
$$ ST^2 = 4 \cdot 9 $$
$$ ST^2 = 36 $$

Taking the square root (length must be positive):
$$ ST = 6 $$

**Final Answer:**
The length of the tangent segment $ST$ is **6**.

## B06 / 1

A secant from a point S outside a circle meets the circle at U and V, in the order S,U,V. The tangent from S touches the circle at T. Given SU=4 and UV=5, find ST. Prove the product identity you use by similarity of triangles in this configuration, rather than merely citing the power-of-a-point theorem. Give the necessary justification and a concise final solution.



Here is the step-by-step solution.

### 1. Given Information and Calculation
We are given a circle with an external point $S$. A secant line passes through $S$ intersecting the circle at points $U$ and $V$ in that order. A tangent from $S$ touches the circle at $T$.
*   $SU = 4$
*   $UV = 5$

First, we determine the length of the entire secant segment from $S$ to $V$ ($SV$):
$$SV = SU + UV$$
$$SV = 4 + 5 = 9$$

### 2. Proof of the Product Identity via Similarity
We aim to prove the relationship $ST^2 = SU \cdot SV$ using the properties of triangles formed by the secant and tangent.

Consider the two triangles $\triangle STU$ and $\triangle SVT$. We will demonstrate that they are similar.

**Justification of Similarity:**
1.  **Common Angle:** Both triangles share the angle at vertex $S$ ($\angle TSU$ is the same angle as $\angle VST$).
2.  **Alternate Segment Theorem:** The angle between a tangent ($ST$) and a chord ($UT$) drawn to the point of contact is equal to the angle in the alternate segment.
    *   The angle between tangent $ST$ and chord $UT$ is $\angle STU$.
    *   The angle in the alternate segment subtended by the chord $UT$ is the inscribed angle at point $V$, which is $\angle TVU$.
    *   Therefore, $\angle STU = \angle TVU$.
3.  **Collinearity:** Since points $S, U, V$ lie on the same line, the angle $\angle TVU$ in the circle is identical to the angle $\angle SVT$ within the triangle $\triangle SVT$.
    *   Thus, $\angle STU = \angle SVT$.

Since two angles are equal ($\angle S$ is common and $\angle STU = \angle SVT$), the triangles are similar by the AA (Angle-Angle) criterion:
$$ \triangle STU \sim \triangle SVT $$

**Deriving the Ratio:**
From the similarity $\triangle STU \sim \triangle SVT$, the ratio of corresponding sides is equal. Matching the vertices ($S \leftrightarrow S$, $T \leftrightarrow V$, $U \leftrightarrow T$):
$$ \frac{SU}{ST} = \frac{ST}{SV} = \frac{TU}{VT} $$

Focusing on the segments involving $S, T, U, V$:
$$ \frac{SU}{ST} = \frac{ST}{SV} $$

Cross-multiplying yields the required identity:
$$ ST^2 = SU \cdot SV $$

### 3. Final Solution
Now, substitute the known values into the identity:

1.  $ST^2 = SU \cdot SV$
2.  Substitute $SU = 4$ and $SV = 9$:
    $$ ST^2 = 4 \cdot 9 $$
    $$ ST^2 = 36 $$
3.  Taking the square root (lengths must be positive):
    $$ ST = 6 $$

**Answer:** 6

## H01_unassisted / 0

Let ABC be an acute scalene triangle with orthocenter H, and let M be the midpoint of BC. Let P be the foot of the perpendicular from H to the line AM. Given BC=12 and AM=10, find AP.

Justify your answer from the definitions and given conditions. Prove the central relation in your solution; merely citing the name or properties of a special point is not sufficient. Coordinate solutions are allowed. Put the final numerical value in \boxed{...}.
Seek a geometrically or mathematically meaningful solution: identify and actually use a relation that simplifies the calculation or proof, a viewpoint that reduces the unknowns, or an argument that concisely explains why a property holds. Any method is allowed. Justify the relations you discover from the given conditions.



Let us denote the vertices of the triangle as $A, B, C$ and the midpoint of $BC$ as $M$. We are given that $BC = 12$, so $BM = MC = 6$. Let us choose a Cartesian coordinate system or a vector system to analyze the configuration.

**Step 1: Setup and Coordinate Geometry**
Let $M$ be the origin $(0,0)$. Since $M$ is the midpoint of $BC$, we can place $B$ and $C$ symmetrically on the x-axis (or simply denote their position vectors). Let $\vec{M} = \mathbf{0}$.
Let $\vec{MB} = \mathbf{b}$ and $\vec{MC} = \mathbf{c}$. Since $M$ is the midpoint, $\mathbf{c} = -\mathbf{b}$. The length $|\mathbf{b}| = |\mathbf{c}| = 6$.
Let $\vec{MA} = \mathbf{a}$. We are given $|\mathbf{a}| = AM = 10$.
We need to locate the orthocenter $H$. Let its position vector be $\mathbf{h}$.
The orthocenter $H$ is the intersection of the altitudes.
1.  The altitude from $A$ is perpendicular to $BC$. The vector $\vec{BC} = \mathbf{c} - \mathbf{b} = \mathbf{c} - (-\mathbf{c}) = 2\mathbf{c}$.
    Since $\vec{AH} = \mathbf{h} - \mathbf{a}$ is perpendicular to $BC$, we have:
    $$(\mathbf{h} - \mathbf{a}) \cdot \mathbf{c} = 0 \implies \mathbf{h} \cdot \mathbf{c} = \mathbf{a} \cdot \mathbf{c}$$
2.  The altitude from $B$ is perpendicular to $AC$. The vector $\vec{AC} = \mathbf{c} - \mathbf{a}$.
    Since $\vec{BH} = \mathbf{h} - \mathbf{b} = \mathbf{h} + \mathbf{c}$ is perpendicular to $AC$, we have:
    $$(\mathbf{h} + \mathbf{c}) \cdot (\mathbf{c} - \mathbf{a}) = 0$$
    Expanding this:
    $$\mathbf{h} \cdot \mathbf{c} - \mathbf{h} \cdot \mathbf{a} + \mathbf{c} \cdot \mathbf{c} - \mathbf{c} \cdot \mathbf{a} = 0$$
    $$\mathbf{h} \cdot \mathbf{c} - \mathbf{h} \cdot \mathbf{a} + |\mathbf{c}|^2 - \mathbf{a} \cdot \mathbf{c} = 0$$
    Substituting $\mathbf{h} \cdot \mathbf{c} = \mathbf{a} \cdot \mathbf{c}$ from the first condition:
    $$(\mathbf{a} \cdot \mathbf{c}) - \mathbf{h} \cdot \mathbf{a} + |\mathbf{c}|^2 - \mathbf{a} \cdot \mathbf{c} = 0$$
    $$-\mathbf{h} \cdot \mathbf{a} + |\mathbf{c}|^2 = 0$$
    $$\mathbf{h} \cdot \mathbf{a} = |\mathbf{c}|^2$$

**Step 2: Central Relation**
We have derived the following crucial vector relation centered at $M$:
$$ \vec{MH} \cdot \vec{MA} = MC^2 $$
Substituting the known values: $|\vec{MA}| = 10$, $|\vec{MC}| = 6$.
$$ \vec{MH} \cdot \vec{MA} = 6^2 = 36 $$

**Step 3: Finding the Projection $MP$**
$P$ is the foot of the perpendicular from $H$ to the line $AM$. Thus, the vector $\vec{MP}$ is the orthogonal projection of $\vec{MH}$ onto the line containing $AM$ (which is along $\vec{MA}$).
The scalar length of this projection is given by:
$$ MP = \frac{\vec{MH} \cdot \vec{MA}}{|\vec{MA}|} $$
Using our derived relation:
$$ MP = \frac{36}{10} = 3.6 $$
Since the dot product $\vec{MH} \cdot \vec{MA} = 36$ is positive, the vector $\vec{MP}$ points in the same direction as $\vec{MA}$.
Furthermore, since $|\vec{MA}| = 10$ and $MP = 3.6$, the point $P$ lies on the segment $AM$ because $0 < 3.6 < 10$. (Note: For an acute triangle, $AM > MC$ is a necessary condition for the angle at $A$ to be acute, ensuring $MP < MA$).

**Step 4: Calculating $AP$**
Since $P$ lies on the segment $AM$, the distance $AP$ is the difference between the total length $AM$ and the distance $MP$ from the origin $M$.
$$ AP = AM - MP $$
$$ AP = 10 - 3.6 = 6.4 $$

Alternatively, using coordinate geometry directly confirms this result. Let $M=(0,0)$, $C=(6,0)$, $B=(-6,0)$, and $A=(u,v)$ with $u^2+v^2=100$.
Altitude from $A$ is $x=u$.
Altitude from $B$ intersects $AC$. Slope of $AC$ is $v/(u-6)$. Slope of altitude from $B$ is $(6-u)/v$.
Line: $y = \frac{6-u}{v}(x+6)$. At $x=u$, $y_H = \frac{6-u}{v}(u+6) = \frac{36-u^2}{v}$.
So $H = (u, \frac{36-u^2}{v})$.
Vector $\vec{MH} = (u, \frac{36-u^2}{v})$. Vector $\vec{MA} = (u,v)$.
Dot product $\vec{MH} \cdot \vec{MA} = u^2 + (36-u^2) = 36$.
Projection length $MP = 36/10 = 3.6$.
$AP = \sqrt{10^2 - (3.6)^2 + ...}$ no, $AP = |10 - 3.6| = 6.4$.

Final numerical value is 6.4.

\boxed{6.4}

## H01_unassisted / 1

Let ABC be an acute scalene triangle with orthocenter H, and let M be the midpoint of BC. Let P be the foot of the perpendicular from H to the line AM. Given BC=12 and AM=10, find AP.

Justify your answer from the definitions and given conditions. Prove the central relation in your solution; merely citing the name or properties of a special point is not sufficient. Coordinate solutions are allowed. Put the final numerical value in \boxed{...}.
Seek a geometrically or mathematically meaningful solution: identify and actually use a relation that simplifies the calculation or proof, a viewpoint that reduces the unknowns, or an argument that concisely explains why a property holds. Any method is allowed. Justify the relations you discover from the given conditions.



The problem asks us to find the length of the segment $AP$, where $P$ is the foot of the perpendicular from the orthocenter $H$ to the median $AM$. We are given $BC = 12$ and $AM = 10$.

**Geometric Setup and Definitions:**
Let us place the triangle $ABC$ in a Cartesian coordinate system.
To simplify calculations involving the midpoint $M$, we set $M$ as the origin $(0,0)$.
Since $M$ is the midpoint of $BC$, we align $BC$ along the x-axis.
Given $BC = 12$, the coordinates of the vertices are:
$$M = (0, 0)$$
$$B = (-6, 0)$$
$$C = (6, 0)$$
Let the coordinates of vertex $A$ be $(x_A, y_A)$.
Since $M$ is the midpoint and $AM = 10$, we have:
$$x_A^2 + y_A^2 = 10^2 = 100$$
Since the triangle is acute and scalene, $y_A \neq 0$ and $x_A \neq 0$ (though the solution should hold generally).

**Finding the Coordinates of the Orthocenter $H$:**
The orthocenter $H$ is the intersection of the altitudes.
1.  **Altitude from $A$:** Since $BC$ lies on the x-axis, the altitude from $A$ to $BC$ is a vertical line. Its equation is $x = x_A$. Thus, the x-coordinate of $H$ is $x_H = x_A$.
2.  **Altitude from $B$:** This altitude passes through $B(-6, 0)$ and is perpendicular to the side $AC$.
    The slope of the line segment $AC$ is given by:
    $$m_{AC} = \frac{y_A - 0}{x_A - 6} = \frac{y_A}{x_A - 6}$$
    The slope of the altitude from $B$ is the negative reciprocal of $m_{AC}$:
    $$m_{\text{alt}_B} = -\frac{1}{m_{AC}} = -\frac{x_A - 6}{y_A} = \frac{6 - x_A}{y_A}$$
    Using the point-slope form, the equation of the altitude from $B$ is:
    $$y - 0 = \frac{6 - x_A}{y_A} (x - (-6))$$
    To find the y-coordinate of $H$, we substitute $x = x_H = x_A$ into this equation:
    $$y_H = \frac{6 - x_A}{y_A} (x_A + 6) = \frac{36 - x_A^2}{y_A}$$
    Thus, the coordinates of $H$ are $\left(x_A, \frac{36 - x_A^2}{y_A}\right)$.

**Calculating the Position of $P$:**
Point $P$ is the foot of the perpendicular from $H$ to the line $AM$. Since $M$ is the origin and $A$ is $(x_A, y_A)$, the line $AM$ passes through the origin with direction vector $\vec{MA} = (x_A, y_A)$.
The position vector of $P$, denoted $\vec{MP}$, is the orthogonal projection of the position vector of $H$, denoted $\vec{MH}$, onto the direction of $\vec{MA}$.
Using the vector projection formula:
$$\vec{MP} = \left( \frac{\vec{MH} \cdot \vec{MA}}{|\vec{MA}|^2} \right) \vec{MA}$$
We calculate the dot product $\vec{MH} \cdot \vec{MA}$:
$$\vec{MH} = \langle x_A, y_H \rangle = \left\langle x_A, \frac{36 - x_A^2}{y_A} \right\rangle$$
$$\vec{MA} = \langle x_A, y_A \rangle$$
$$\vec{MH} \cdot \vec{MA} = x_A(x_A) + \left( \frac{36 - x_A^2}{y_A} \right) y_A = x_A^2 + 36 - x_A^2 = 36$$
Notice that the result depends solely on the coordinate system choice (specifically that $M$ is the midpoint of $BC=12$) and not on the specific location of $A$. This leads to the central relation:
$$\vec{MH} \cdot \vec{MA} = \left(\frac{BC}{2}\right)^2 = 6^2 = 36$$
Now, we find the length $MP$ (distance from $M$ to $P$):
$$|\vec{MP}| = \frac{|\vec{MH} \cdot \vec{MA}|}{|\vec{MA}|} = \frac{36}{10} = 3.6$$
Since the dot product was positive, $\vec{MP}$ points in the same direction as $\vec{MA}$.
Thus, $P$ lies on the segment $AM$ (or the ray $MA$).

**Determining $AP$:**
Since $P$ lies on the ray $MA$ at a distance of $3.6$ from $M$, and $A$ lies at a distance of $10$ from $M$ along the same ray, the distance $AP$ is the difference between these lengths:
$$AP = AM - MP = 10 - 3.6 = 6.4$$
Alternatively, in vector terms:
$$\vec{AP} = \vec{MP} - \vec{MA} = \frac{36}{100}\vec{MA} - \vec{MA} = -0.64 \vec{MA}$$
$$AP = |-0.64| |\vec{MA}| = 0.64 \times 10 = 6.4$$

\boxed{6.4}

## DA03_unassisted / 0

Let O be the circumcenter of an acute scalene triangle ABC. The circle through A and C tangent to the line AB at A meets the circle through B,O,C again at T, other than C. Let K be the intersection of the lines TO and BC. The points K,B,C are collinear in that order. Given BC=32 and BK=49, find AK.

Justify your answer from the definitions and given conditions. Prove the central relation in your solution; merely citing the name or properties of a special point is not sufficient. Coordinate solutions are allowed. Put the final numerical value in \boxed{...}.
Seek a geometrically or mathematically meaningful solution: identify and actually use a relation that simplifies the calculation or proof, a viewpoint that reduces the unknowns, or an argument that concisely explains why a property holds. Any method is allowed. Justify the relations you discover from the given conditions.



## DA03_unassisted / 1

Let O be the circumcenter of an acute scalene triangle ABC. The circle through A and C tangent to the line AB at A meets the circle through B,O,C again at T, other than C. Let K be the intersection of the lines TO and BC. The points K,B,C are collinear in that order. Given BC=32 and BK=49, find AK.

Justify your answer from the definitions and given conditions. Prove the central relation in your solution; merely citing the name or properties of a special point is not sufficient. Coordinate solutions are allowed. Put the final numerical value in \boxed{...}.
Seek a geometrically or mathematically meaningful solution: identify and actually use a relation that simplifies the calculation or proof, a viewpoint that reduces the unknowns, or an argument that concisely explains why a property holds. Any method is allowed. Justify the relations you discover from the given conditions.



## DA05_unassisted / 0

Let ABC be an acute scalene triangle with BC=12. Let omega1 be the circle through A tangent to the line BC at B, and omega2 the circle through C tangent to the line BA at B. The two circles meet again at D, other than B. Let M be the midpoint of BC, and E the intersection of the lines MD and AC. The points M,D,E lie in that order, and MD=4. Find DE.

Justify your answer from the definitions and given conditions. Prove the central relation in your solution; merely citing the name or properties of a special point is not sufficient. Coordinate solutions are allowed. Put the final numerical value in \boxed{...}.
Seek a geometrically or mathematically meaningful solution: identify and actually use a relation that simplifies the calculation or proof, a viewpoint that reduces the unknowns, or an argument that concisely explains why a property holds. Any method is allowed. Justify the relations you discover from the given conditions.



## DA05_unassisted / 1

Let ABC be an acute scalene triangle with BC=12. Let omega1 be the circle through A tangent to the line BC at B, and omega2 the circle through C tangent to the line BA at B. The two circles meet again at D, other than B. Let M be the midpoint of BC, and E the intersection of the lines MD and AC. The points M,D,E lie in that order, and MD=4. Find DE.

Justify your answer from the definitions and given conditions. Prove the central relation in your solution; merely citing the name or properties of a special point is not sufficient. Coordinate solutions are allowed. Put the final numerical value in \boxed{...}.
Seek a geometrically or mathematically meaningful solution: identify and actually use a relation that simplifies the calculation or proof, a viewpoint that reduces the unknowns, or an argument that concisely explains why a property holds. Any method is allowed. Justify the relations you discover from the given conditions.



## DA15_unassisted / 0

Let O be the circumcenter of an acute scalene triangle ABC, and M the midpoint of BC. The perpendicular bisectors of AB and AC meet the ray AM at D and E, respectively. Let F be the intersection of BD and CE, and suppose F lies inside triangle ABC. Given AO=13 and AF=12, find OF.

Justify your answer from the definitions and given conditions. Prove the central relation in your solution; merely citing the name or properties of a special point is not sufficient. Coordinate solutions are allowed. Put the final numerical value in \boxed{...}.
Seek a geometrically or mathematically meaningful solution: identify and actually use a relation that simplifies the calculation or proof, a viewpoint that reduces the unknowns, or an argument that concisely explains why a property holds. Any method is allowed. Justify the relations you discover from the given conditions.



## DA15_unassisted / 1

Let O be the circumcenter of an acute scalene triangle ABC, and M the midpoint of BC. The perpendicular bisectors of AB and AC meet the ray AM at D and E, respectively. Let F be the intersection of BD and CE, and suppose F lies inside triangle ABC. Given AO=13 and AF=12, find OF.

Justify your answer from the definitions and given conditions. Prove the central relation in your solution; merely citing the name or properties of a special point is not sufficient. Coordinate solutions are allowed. Put the final numerical value in \boxed{...}.
Seek a geometrically or mathematically meaningful solution: identify and actually use a relation that simplifies the calculation or proof, a viewpoint that reduces the unknowns, or an argument that concisely explains why a property holds. Any method is allowed. Justify the relations you discover from the given conditions.


