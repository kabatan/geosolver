## B04 / 0

Let M=(0,0), A=(a,b), and H=(u,v), where a^2+b^2>0. Derive the coordinates of the foot P of the perpendicular from H to the line MA. Do not assume that P lies on the segment MA. Give the necessary justification and a concise final solution.



To find the coordinates of the foot \( P \) of the perpendicular from \( H \) to the line \( MA \), we start by parametrizing the line \( MA \). The line \( MA \) can be parametrized as \( (ta, tb) \) where \( t \) is a scalar parameter. 

The vector from \( H \) to \( P \) must be perpendicular to the direction vector of \( MA \). The direction vector of \( MA \) is \( (a, b) \). Therefore, the dot product of the vector \( HP \) and the direction vector \( (a, b) \) must be zero. 

Given \( H = (u, v) \) and \( P = (ta, tb) \), the vector \( HP \) is \( (ta - u, tb - v) \). Setting their dot product to zero:

\[
(ta - u)a + (tb - v)b = 0
\]

Expanding and combining like terms:

\[
ta^2 - ua + tb^2 - vb = 0 \implies t(a^2 + b^2) = ua + vb \implies t = \frac{ua + vb}{a^2 + b^2}
\]

Substituting \( t \) back into the parametric equations of line \( MA \), we get the coordinates of \( P \):

\[
P = \left( a \cdot \frac{ua + vb}{a^2 + b^2}, b \cdot \frac{ua + vb}{a^2 + b^2} \right)
\]

Simplifying, the coordinates of \( P \) are:

\[
P = \left( \frac{a(ua + vb)}{a^2 + b^2}, \frac{b(ua + vb)}{a^2 + b^2} \right)
\]

Thus, the coordinates of the foot \( P \) are:

\[
\boxed{\left( \dfrac{a(ua + vb)}{a^2 + b^2}, \dfrac{b(ua + vb)}{a^2 + b^2} \right)}
\]

## B04 / 1

Let M=(0,0), A=(a,b), and H=(u,v), where a^2+b^2>0. Derive the coordinates of the foot P of the perpendicular from H to the line MA. Do not assume that P lies on the segment MA. Give the necessary justification and a concise final solution.



To find the coordinates of the foot \( P \) of the perpendicular from \( H \) to the line \( MA \), we start by noting that the line \( MA \) passes through the origin \( M = (0,0) \) and \( A = (a, b) \). The parametric equation of line \( MA \) can be written as \( t(a, b) \) where \( t \) is a scalar parameter. 

The vector from \( H \) to \( P \) must be perpendicular to the direction vector of \( MA \). If \( P \) is on \( MA \), then \( P = t(a, b) \) for some \( t \). The vector \( HP \) is given by \( t(a, b) - (u, v) \). For \( HP \) to be perpendicular to \( (a, b) \), their dot product must be zero:

\[
(ta - u, tb - v) \cdot (a, b) = 0
\]

Expanding this dot product:

\[
ta \cdot a + tb \cdot b - u \cdot a - v \cdot b = 0
\]

Simplifying, we get:

\[
t(a^2 + b^2) - (ua + vb) = 0
\]

Solving for \( t \):

\[
t = \frac{ua + vb}{a^2 + b^2}
\]

Substituting \( t \) back into the parametric equation of line \( MA \), the coordinates of \( P \) are:

\[
P = \left( \frac{ua + vb}{a^2 + b^2} \cdot a, \frac{ua + vb}{a^2 + b^2} \cdot b \right)
\]

Thus, the coordinates of the foot \( P \) are:

\[
\boxed{\left( \dfrac{a(ua + vb)}{a^2 + b^2}, \dfrac{b(ua + vb)}{a^2 + b^2} \right)}
\]

## B06 / 0

A secant from a point S outside a circle meets the circle at U and V, in the order S,U,V. The tangent from S touches the circle at T. Given SU=4 and UV=5, find ST. Prove the product identity you use by similarity of triangles in this configuration, rather than merely citing the power-of-a-point theorem. Give the necessary justification and a concise final solution.



To find the length of \( ST \) given \( SU = 4 \) and \( UV = 5 \), we use the product identity proven by similarity of triangles. 

1. **Identify the given lengths**:
   - \( SU = 4 \)
   - \( UV = 5 \)
   - \( SV = SU + UV = 4 + 5 = 9 \)

2. **Apply the Alternate Segment Theorem**:
   - The angle between the tangent \( ST \) and chord \( TV \) (i.e., \( \angle STV \)) is equal to the angle subtended by \( TV \) in the alternate segment, which is \( \angle TVU \).
   - Similarly, the angle between the tangent \( ST \) and chord \( TU \) (i.e., \( \angle STU \)) is equal to the angle subtended by \( TU \) in the alternate segment, which is \( \angle TUV \).

3. **Establish similarity of triangles**:
   - By the Alternate Segment Theorem, \( \angle STU = \angle TVU \) and \( \angle STV = \angle TVU \). Therefore, \( \angle STU = \angle STV \).
   - Triangles \( STU \) and \( SVT \) share the angle at \( T \), and the angles \( \angle STU \) and \( \angle STV \) are equal. This gives us two pairs of equal angles, leading to the similarity of triangles \( STU \) and \( SVT \) by AA similarity.

4. **Set up the proportion from similarity**:
   - Since triangles \( STU \) and \( SVT \) are similar, the sides are proportional:
     \[
     \frac{ST}{SV} = \frac{SU}{ST}
     \]
   - Cross-multiplying gives:
     \[
     ST^2 = SU \times SV
     \]
   - Substituting the known values:
     \[
     ST^2 = 4 \times 9 = 36
     \]
   - Therefore, \( ST = \sqrt{36} = 6 \).

The length of \( ST \) is \(\boxed{6}\).

## B06 / 1

A secant from a point S outside a circle meets the circle at U and V, in the order S,U,V. The tangent from S touches the circle at T. Given SU=4 and UV=5, find ST. Prove the product identity you use by similarity of triangles in this configuration, rather than merely citing the power-of-a-point theorem. Give the necessary justification and a concise final solution.



Given a point \( S \) outside a circle, a secant from \( S \) intersects the circle at points \( U \) and \( V \) (in the order \( S, U, V \)), and a tangent from \( S \) touches the circle at \( T \). We need to find the length of \( ST \) given \( SU = 4 \) and \( UV = 5 \). 

### Key Steps and Proof:

1. **Power of a Point Theorem**: The power of point \( S \) with respect to the circle is given by \( ST^2 = SU \cdot SV \). However, we need to prove this using similarity of triangles instead of directly citing the theorem.

2. **Alternate Segment Theorem**: The angle between the tangent \( ST \) and the chord \( TU \) is equal to the angle subtended by \( TU \) in the alternate segment. This gives us \( \angle STU = \angle TVU \).

3. **Similar Triangles**:
   - Consider triangles \( STU \) and \( TVU \).
   - By the Alternate Segment Theorem, \( \angle STU = \angle TVU \).
   - Both triangles share the angle \( \angle U \) (at point \( U \) for \( \triangle STU \) and at point \( V \) for \( \triangle TVU \), which are vertical angles and thus equal).

4. **AA Similarity**: Since triangles \( STU \) and \( TVU \) have two corresponding angles equal, they are similar by AA (Angle-Angle) similarity.

5. **Proportional Sides**: Using the similarity of triangles \( STU \) and \( TVU \), we set up the proportion:
   \[
   \frac{ST}{SU} = \frac{SU}{SV}
   \]
   This leads to the product identity:
   \[
   ST^2 = SU \cdot SV
   \]

6. **Calculating \( ST \)**:
   - Given \( SU = 4 \) and \( UV = 5 \), the length \( SV \) is \( SU + UV = 4 + 5 = 9 \).
   - Substituting into the product identity:
   \[
   ST^2 = SU \cdot SV = 4 \cdot 9 = 36
   \]
   - Therefore, \( ST = \sqrt{36} = 6 \).

### Final Answer:
The length of \( ST \) is \(\boxed{6}\).

## H01_unassisted / 0

Let ABC be an acute scalene triangle with orthocenter H, and let M be the midpoint of BC. Let P be the foot of the perpendicular from H to the line AM. Given BC=12 and AM=10, find AP.

Justify your answer from the definitions and given conditions. Prove the central relation in your solution; merely citing the name or properties of a special point is not sufficient. Coordinate solutions are allowed. Put the final numerical value in \boxed{...}.
Seek a geometrically or mathematically meaningful solution: identify and actually use a relation that simplifies the calculation or proof, a viewpoint that reduces the unknowns, or an argument that concisely explains why a property holds. Any method is allowed. Justify the relations you discover from the given conditions.



Given an acute scalene triangle \(ABC\) with orthocenter \(H\), midpoint \(M\) of \(BC\), and \(P\) as the foot of the perpendicular from \(H\) to \(AM\). We know \(BC = 12\) and \(AM = 10\). We need to find \(AP\).

1. **Coordinate System Setup**:
   - Place \(B\) at \((0, 0)\), \(C\) at \((12, 0)\), and \(M\) at \((6, 0)\).
   - Let \(A\) be \((x, y)\) such that \(AM = 10\). Thus, \((x - 6)^2 + y^2 = 100\).

2. **Orthocenter \(H\) Coordinates**:
   - The orthocenter \(H\) is found as the intersection of the altitudes.
   - The altitude from \(A\) to \(BC\) is vertical line \(x = x\).
   - The altitude from \(B\) to \(AC\) has slope \(\frac{12 - x}{y}\) and passes through \(B\). Solving for intersection, \(H\) is \((x, \frac{x(12 - x)}{y})\).

3. **Foot of Perpendicular from \(H\) to \(AM\)**:
   - Parametrize \(AM\) as \(X = x + t(6 - x)\) and \(Y = y - ty\).
   - Solve for parameter \(t\) such that the vector from \(H\) to \(P\) is perpendicular to \(AM\).
   - Using projection formula, \(t = \frac{y^2 - x(12 - x)}{100}\).

4. **Length \(AP\)**:
   - Since \(AM = 10\), \(AP = t \times 10\).
   - Substitute \(t\) into the expression for \(AP\):
     \[
     AP = 10 \times \frac{y^2 - x(12 - x)}{100} = \frac{y^2 - 12x + x^2}{10}
     \]
   - Using \((x - 6)^2 + y^2 = 100\), we get \(x^2 + y^2 = 64 + 12x\).
   - Substitute \(x^2 + y^2\) into \(AP\):
     \[
     AP = \frac{64 + 12x - 12x}{10} = \frac{64}{10} = \frac{32}{5}
     \]

Thus, the final answer is \(\boxed{\dfrac{32}{5}}\).

## H01_unassisted / 1

Let ABC be an acute scalene triangle with orthocenter H, and let M be the midpoint of BC. Let P be the foot of the perpendicular from H to the line AM. Given BC=12 and AM=10, find AP.

Justify your answer from the definitions and given conditions. Prove the central relation in your solution; merely citing the name or properties of a special point is not sufficient. Coordinate solutions are allowed. Put the final numerical value in \boxed{...}.
Seek a geometrically or mathematically meaningful solution: identify and actually use a relation that simplifies the calculation or proof, a viewpoint that reduces the unknowns, or an argument that concisely explains why a property holds. Any method is allowed. Justify the relations you discover from the given conditions.



Given an acute scalene triangle \(ABC\) with orthocenter \(H\), midpoint \(M\) of \(BC\), and \(AM = 10\) with \(BC = 12\), we need to find \(AP\) where \(P\) is the foot of the perpendicular from \(H\) to \(AM\).

1. **Coordinate Setup**:
   - Place \(B\) at \((-6, 0)\), \(C\) at \((6, 0)\), and midpoint \(M\) at \((0, 0)\).
   - Let \(A\) be at \((x, y)\) such that \(x^2 + y^2 = 100\) (since \(AM = 10\)).

2. **Orthocenter Calculation**:
   - The orthocenter \(H\) lies at the intersection of the altitudes.
   - The altitude from \(A\) is vertical (since \(BC\) is horizontal), giving the equation \(x = x\).
   - The altitude from \(B\) has the equation \(Y = \frac{-(x - 6)}{y}(X + 6)\).
   - Substituting \(x = x\) into this equation gives the \(y\)-coordinate of \(H\) as \(\frac{36 - x^2}{y}\).

3. **Projection of \(H\) onto \(AM\)**:
   - The line \(AM\) is parameterized as \((x - tx, y - ty)\) where \(t\) is a parameter.
   - The vector projection of \(H\) onto \(AM\) is calculated using the dot product and projection formula.
   - The coordinates of \(P\) are found to be \(\left(\frac{9x}{25}, \frac{9y}{25}\right)\).

4. **Distance Calculation**:
   - The distance \(AP\) is calculated using the coordinates of \(A\) and \(P\):
     \[
     AP = \sqrt{\left(x - \frac{9x}{25}\right)^2 + \left(y - \frac{9y}{25}\right)^2} = \sqrt{\left(\frac{16x}{25}\right)^2 + \left(\frac{16y}{25}\right)^2} = \frac{16}{25} \sqrt{x^2 + y^2}
     \]
   - Given \(x^2 + y^2 = 100\), this simplifies to:
     \[
     AP = \frac{16}{25} \times 10 = \frac{160}{25} = \frac{32}{5}
     \]

Thus, the length of \(AP\) is \(\boxed{\dfrac{32}{5}}\).

## DA03_unassisted / 0

Let O be the circumcenter of an acute scalene triangle ABC. The circle through A and C tangent to the line AB at A meets the circle through B,O,C again at T, other than C. Let K be the intersection of the lines TO and BC. The points K,B,C are collinear in that order. Given BC=32 and BK=49, find AK.

Justify your answer from the definitions and given conditions. Prove the central relation in your solution; merely citing the name or properties of a special point is not sufficient. Coordinate solutions are allowed. Put the final numerical value in \boxed{...}.
Seek a geometrically or mathematically meaningful solution: identify and actually use a relation that simplifies the calculation or proof, a viewpoint that reduces the unknowns, or an argument that concisely explains why a property holds. Any method is allowed. Justify the relations you discover from the given conditions.



Given an acute scalene triangle \(ABC\) with circumcenter \(O\), we need to find the length of \(AK\) where \(K\) is the intersection of line \(TO\) and \(BC\). The points \(K, B, C\) are collinear in that order, \(BC = 32\), and \(BK = 49\).

1. **Coordinates Setup**:
   - Place \(B\) at \((0, 0)\), \(C\) at \((32, 0)\), and \(K\) at \((-49, 0)\) since \(BK = 49\) and \(K\) is on the extension of \(BC\) beyond \(B\).

2. **Key Properties and Relations**:
   - The circle through \(A\) and \(C\) tangent to \(AB\) at \(A\) (denoted as \(\Gamma\)) and the circumcircle of \(BOC\) intersect at \(T\).
   - \(T\) lies on both circles, and \(TA = TC\) because \(T\) is on the perpendicular bisector of \(AC\).

3. **Power of a Point**:
   - The power of point \(K\) with respect to the circumcircle of \(BOC\) is given by \(KB \cdot KC\).
   - The power of point \(K\) with respect to circle \(\Gamma\) is given by \(KA^2\) (since \(K\) lies on the radical axis and \(KA\) is the tangent from \(K\) to \(\Gamma\)).

4. **Equating Powers**:
   - Using the power of point \(K\) with respect to both circles, we have:
     \[
     KA^2 = KB \cdot KC
     \]
   - Substituting the given values \(KB = 49\) and \(KC = 81\) (since \(BC = 32\) and \(BK = 49\), \(KC = BK + BC = 49 + 32 = 81\)):
     \[
     KA^2 = 49 \cdot 81 = 3969
     \]
   - Therefore, \(KA = \sqrt{3969} = 63\).

The final answer is \(\boxed{63}\).

## DA03_unassisted / 1

Let O be the circumcenter of an acute scalene triangle ABC. The circle through A and C tangent to the line AB at A meets the circle through B,O,C again at T, other than C. Let K be the intersection of the lines TO and BC. The points K,B,C are collinear in that order. Given BC=32 and BK=49, find AK.

Justify your answer from the definitions and given conditions. Prove the central relation in your solution; merely citing the name or properties of a special point is not sufficient. Coordinate solutions are allowed. Put the final numerical value in \boxed{...}.
Seek a geometrically or mathematically meaningful solution: identify and actually use a relation that simplifies the calculation or proof, a viewpoint that reduces the unknowns, or an argument that concisely explains why a property holds. Any method is allowed. Justify the relations you discover from the given conditions.



Given an acute scalene triangle \(ABC\) with circumcenter \(O\). The circle through \(A\) and \(C\) tangent to \(AB\) at \(A\) intersects the circumcircle of \(BOC\) again at \(T\). The intersection of \(TO\) with \(BC\) is \(K\), with \(BK = 49\) and \(BC = 32\). We need to find \(AK\).

1. **Coordinate Setup**:
   - Place \(B\) at \((0, 0)\), \(C\) at \((32, 0)\), and \(K\) at \((-49, 0)\).
   - Let \(A\) be at \((a, b)\).

2. **Circumcenter \(O\)**:
   - The circumcenter \(O\) of \(\triangle ABC\) is found by intersecting the perpendicular bisectors of \(AB\) and \(BC\).
   - Midpoint of \(BC\) is \((16, 0)\), and the perpendicular bisector is \(x = 16\).
   - Midpoint of \(AB\) is \((\frac{a}{2}, \frac{b}{2})\), and the perpendicular bisector has slope \(-\frac{a}{b}\).

3. **Circle \(\Gamma_1\) (through \(A\) and \(C\), tangent to \(AB\) at \(A\))**:
   - The center \(S\) of \(\Gamma_1\) lies on the line perpendicular to \(AB\) at \(A\).
   - Using the condition
