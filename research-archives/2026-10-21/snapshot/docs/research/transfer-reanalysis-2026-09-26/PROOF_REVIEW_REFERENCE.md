# Grader-only reference for the three secondary proof claims

These derivations are researcher-side review aids. They are not supplied to the
learned models, training prompts, numerical teachers, or generation jobs.
Accept other valid proofs. Use this reference to check substantive issues rather
than requiring the same notation or method.

## H01: AM times MP equals MB squared

Put M=(0,0), B=(-a,0), C=(a,0), A=(x,y), with a,y>0, and let r²=x²+y².
The altitude through A is vertical. The altitude through B is perpendicular to
AC, so H=(x,(a²-x²)/y). Thus H·A=a². The orthogonal projection of H onto
line MA is P=(a²/r²)A. Therefore MP=a²/r and AM·MP=a².

Acuteness at A gives (B-A)·(C-A)=r²-a²>0. Consequently 0<a²/r²<1:
M,P,A occur in that order. An additional assertion that an acute triangle need
not satisfy AM>BC/2 is false, even when a preceding coordinate proof is correct.
Record an unretracted false aside separately from the existence of a valid proof.

## H04: AT squared equals TB times TC

Continue the preceding coordinates and write T=(t,0), α=a²/r². As T is on the
perpendicular bisector, |A-T|²=|αA-T|². Subtracting and using α<1 yields
2tx=r²+a². Hence AT²=r²-2tx+t²=t²-a².
The specified order T,B,C means t<-a, so TB=-a-t and TC=a-t. Their product is
t²-a², proving the claim with positive ordinary lengths.

An equivalent synthetic proof uses the circle centered at T through A and P,
the power MA·MP=a², and MT²-TA²=a². Such a proof must establish the H01 identity
if it otherwise merely cites the very relation needed for this self-contained
proof. Standard facts such as power of a point need not themselves be reproved.

## DA01: AT times AM equals AB times AC divided by two

Let A=(0,0), B=(c,0), C=(b cosθ,b sinθ), with b,c>0 and 0<θ<π.
The two circles have equations

    F1 = x²+y²-cx+c cotθ y = 0,
    F2 = x²+y²-(b/sinθ)y = 0.

Their tangents at A have respectively the required directions AC and AB;
B belongs to F1 and C belongs to F2. The radical axis is

    -c x + ((b+c cosθ)/sinθ)y = 0.

Use its direction d=(b+c cosθ,c sinθ), without dividing by b+c cosθ.
Set D=|d|²=b²+c²+2bc cosθ>0. Substituting T=λd into F2 gives
λ(λD-bc)=0. The non-A intersection is therefore T=(bc/D)d, and
AT=bc/√D. Meanwhile M=(B+C)/2 gives AM=√D/2, so AT·AM=bc/2.

This proof covers obtuse triangles and b+c cosθ=0. If a different trigonometric
proof divides by a quantity that can vanish, inspect whether it subsequently
uses an undivided identity, explicitly handles the case, or supplies a valid
continuity argument. Do not reject a proof for a supposedly missing branch if
the answer actually establishes it elsewhere. If an interior-angle branch is
needed, the coordinate T above satisfies y_T>0 and
sinθ x_T-cosθ y_T=(bc/D)b sinθ>0, placing it between the two side rays.

## Reporting

Keep `contains_valid_complete_proof` and `has_unretracted_false_claim` separate.
Discarded exploratory mistakes do not invalidate a subsequent complete correct
proof. Conversely, a correct numerical substitution is not a universal proof.
When a gap or branch issue is uncertain, record its precise location for review.
