# Independent blinded grading — primary

Reviewed only the eight answer files `P001.md` through `P008.md` for model output. No runtime records, condition mapping, condition-specific output, or other reviewer files were opened. The grading rubric and the independent mathematical check were established before these answers were read. No condition identities are inferred here.

## Scoring interpretation

- **mapping_claim:** the answer states that R is the foot from H to AM, including the equivalent combination R on AM and HR perpendicular to AM. A claim only that angle ARH is a right angle is a correct weaker relation, but does not by itself receive this strict mapping-claim credit.
- **mapping_proof:** a self-contained decisive construction argument proves that foot identification, or proves another correct relation sufficient to solve the problem. A sound alternative proof is accepted; naming the projection is not required.
- **downstream_proof:** conditional on the correct projection/right angle at R, the answer correctly justifies and applies the right-triangle area calculation. Correct multiplication after assuming the false right angle at A does not pass this field.
- **exact_value:** the final adopted value is correct. A retracted or speculative intermediate answer does not pass.
- **branch_valid:** the construction proof justifies the selected ray intersections, the second common point, and any relevant signs/nonzero factors. Correctly taking the positive square root in the numerical tail alone does not establish this field.
- **complete:** a valid construction argument, valid necessary branches, and correct application. Unresolved contradictions preclude completeness. Explicitly withdrawn hypotheses or corrected arithmetic errors are not independently penalized.

## Results

| ID | mapping_claim | mapping_proof | downstream_proof | exact_value | complete | branch_valid |
|---|---|---|---|---|---|---|
| P001 | false | false | true | true | false | false |
| P002 | false | false | false | false | false | false |
| P003 | false | false | false | false | false | false |
| P004 | false | false | false | false | false | false |
| P005 | false | false | false | false | false | false |
| P006 | true | false | true | true | false | false |
| P007 | false | false | false | false | false | false |
| P008 | false | false | false | false | false | false |

All eight fail the construction-proof criterion. P001 and P006 pass the conditional downstream calculation and final exact value. The claim credit for P006 is narrow: it states the two ingredients of the projection claim, but also leaves incompatible claims in its discussion. That claim credit is not proof or completeness credit.

## Mathematical reference used for checking

With M=(0,0), B=(-m,0), C=(m,0), A=(u,v), v>0, set S=u²+v² and delta=S-m². Acuteness gives delta>0. The circumcircle and its reflection across BC have equations

    Omega:  x²+y²-(delta/v)y-m²=0
    Omega*: x²+y²+(delta/v)y-m²=0.

For U=(u+m)²+v² and W=A+t(B-A), the two decisive restrictions are

    |W-C|²-|A-C|² = t(Ut-2delta)
    Omega*(W) = (t-1)(Ut-2delta).

Thus the actual D lies on Omega*; likewise E. Inversion I(X)=m²X/|X|² sends Omega* to Omega, preserves positive rays, and M is inside Omega, so its images of D and E are exactly the designated P and Q. The images of the distinct lines AB and AC are the defining circles BPM and CQM, hence their non-M common point is

    R=I(A)=(m²/S)A, with 0<m²/S<1.

The altitude equations give H=(u,(m²-u²)/v). Consequently A·H=A·R=m² and HR is perpendicular to AM. The area is therefore

    (1/2) AR sqrt(AH²-AR²).

The two exact values are 507/200 (HR=13/5) and 289/39 (HR=17 sqrt(13)/13).

A concrete acute scalene, nondegenerate counterexample to the repeatedly asserted AR perpendicular to AH and R on Omega is

    B=(-1,0), C=(1,0), A=(1/2,3/2), H=(1/2,1/2),
    D=(-1/2,1/2), E=(11/10,-3/10),
    P=(-1,1), Q=(11/13,-3/13), R=(1/5,3/5).

Here AB²=9/2, AC²=5/2, BC²=4 are distinct and satisfy the acute-triangle inequalities. The defining circles are x²+y²+x-y=0 and x²+y²-x-y/3=0. Both contain the displayed R and M. The positive ray multipliers are P=2D and Q=(10/13)E. Meanwhile (H-A)·(R-A)=9/10, not zero. Omega is x²+y²-y-1=0, whose residual at R is -6/5, so R is not on Omega. These checks were computed independently; they are not model evidence.

## Evidence for each answer

### P001

The stated relation, “right-angled triangle with the right angle at R” (lines 14–16), is correct. There is no statement that R lies on AM, so the strict mapping claim is absent.

The central proof is missing. Lines 31–34 invoke a “known theorem,” an isosceles limit, and “The algebraic verification ... yields exactly the equation” without giving the calculation or a geometric argument connecting the constructed intersections to the right angle. Naming a Miquel point and a limit does not establish the general scalene result. The two proposed formulas followed by “No” at line 33 are explicitly discarded and are not scored as final claims.

The numerical tail is correct: lines 44–58 identify AH as the hypotenuse, take the positive HR=13/5, and compute 507/200. This passes downstream_proof and exact_value only. No construction branch is verified.

### P002

The answer repeatedly and finally retains “A, H, R, M are concyclic” (lines 13, 25, 305, 322), which is false: A,R,M are distinct collinear points in the real construction. Line 153 even concludes “R is not on AM.”

The attempted coordinate derivation is not sound. At line 74 it obtains H=(u,-k(u+k)/v), whereas the correct altitude calculation is H=(u,(k²-u²)/v). At lines 93–94 it puts D in the A-to-BA positive direction instead of using D=A+2(S-k²)(B-A)/|AB|². No later valid P,Q,R construction repairs this.

The final relation used for the area is AH perpendicular to AR (lines 307, 323, 331). The inference that a unique numerical answer forces that particular right angle is invalid. The final value 289 sqrt(13)/117 (line 329) is not 289/39. Multiplication under its false assumed angle is arithmetically correct, but it is not a downstream proof from the correct relation.

### P003

The final solution asserts AR parallel to BC and a right angle at A (lines 240–242). It merely says that “it can be shown” that y_R=v (line 255), followed by an undisplayed “Detailed expansion” (line 256). In fact y_R=m²v/S<v for the acute triangle. The suggested reflection across y=v does not preserve the defining construction in the asserted way.

The genuine right-angle-at-R possibility appears only among earlier questions; it is not adopted in the final solution. The final calculation treats AH and AR as legs and produces 507/160 (lines 264–270), instead of 507/200. No valid alternative construction proof or branch determination is present.

### P004

The coordinate setup simultaneously puts M at the origin, B and C at ±a, and A on the y-axis (lines 26–28). This makes AB=AC and cannot represent the required scalene triangle. The claim of order A-B-D (lines 76–80) also confuses CB with a when its own coordinates give CB=2a.

The initial reflection-of-H claim is expressly withdrawn at lines 197–199, so it is not treated as the final adopted relation. The replacement is still incorrect: AR parallel to BC, or AH perpendicular to AR, is justified only by guessing from uniqueness. The putative similarity at line 282 literally ends with “triangle ???”.

The final retained value is 289 sqrt(13)/117 (lines 291, 297), based on the wrong vertex for the right angle. Neither the correct downstream calculation nor the exact value is obtained.

### P005

The coordinate attempt changes the construction: lines 102–113 take AE=AB and AD=AC, whereas the given equalities are BE=BA and CD=CA. Consequently its attempted points are not the prescribed intersections. It never supplies a valid determination of R.

The answer eventually adopts AH perpendicular to AR and 507/160 (lines 386–388). “Coordinate geometry showing dot product vanishes” names work to be done; no such proof is actually given. The earlier conflict with this angle at line 192 is not resolved mathematically: line 319 says it will proceed with the assumption despite that concern.

The arithmetic error 13/4=6.5 is explicitly repaired at lines 369–380 and is not itself a reason to reject the final arithmetic. The final assumed right angle and final exact value remain wrong. There is no valid branch analysis.

### P006

This answer earns mapping_claim narrowly. Lines 11 and 22 assert R lies on segment AM / A,R,M are collinear. The final adopted relation at line 322 is AR perpendicular to RH. Their combination states exactly the foot condition, even though the answer does not coherently prove it.

Its correct calculation that the midpoint reflection of H lies on Omega (lines 79–105) concerns a different point. It does not prove that this point is the actual second intersection of BPM and CQM. The final construction argument says only that the proof “relies on the fact” that the Miquel point satisfies the right angle (line 308), which assumes the essential result. The later claim that R is on Omega (lines 263–265) is not withdrawn and conflicts with its segment-AM claim; the displayed counterexample also refutes it. The midpoint-reflection speculation is questioned at line 257, but that does not repair the later Omega assertion.

The decimal error is explicitly corrected at lines 291–297. The final numerical argument (lines 313–318) correctly uses the right angle at R, obtains HR=13/5, and computes 507/200. That conditional downstream proof and exact value pass. Construction proof, selected intersections, and completeness fail.

### P007

The answer ends with AH perpendicular to AR (lines 282–283, 299) and continues to use the false cyclicity of A,H,R,M in its proof summary (line 290). Earlier it identifies the radical axis of BPM and CQM as PQ (line 143), rather than their common chord MR.

The restarted quadratic for D (lines 119–127) is a valid beginning, but line 134 says “Let's skip the heavy algebraic derivation” before it identifies the second root or connects D to P and R. The final angle-chasing outline is a chain of unproved instructions, not an established result.

The correct right-angle-at-R possibility is considered and then rejected at lines 260–266 using faulty arithmetic: AH² is 48841/1521, not the 50222/1521 written at line 256. Its final retained value is 289 sqrt(13)/117 (line 306), not 289/39. There is no valid branch analysis or alternative proof.

### P008

The opening states both R on Omega and AR perpendicular to AH (line 14), both false for the defined R. The standard fact about reflecting H across BC (line 24) does not identify the circle-intersection point R.

The purported decisive step assumes a chord AR parallel to BC and then asks “Does this R lie on (BPM)? In this symmetric case, yes” (line 36). It supplies no construction-based membership proof for either defining circle and no selected-ray argument. This is circular.

The calculation at lines 45–50 assumes the wrong right angle at A. Despite reservations about the answer at lines 52–58, the final sentence retains 289 sqrt(13)/117 (line 61), not 289/39. There is no passing mapping claim, construction proof, correct conditional downstream proof, or branch check.
