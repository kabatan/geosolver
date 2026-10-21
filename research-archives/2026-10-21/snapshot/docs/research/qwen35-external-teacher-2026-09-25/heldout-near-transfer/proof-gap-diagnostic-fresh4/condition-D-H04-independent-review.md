# Independent review: condition D, H04

I reviewed the H04 condition-D prompt, frozen rubric/protocol, and the output's `final_text`. I did not open the primary D-H04 grade before forming this assessment.

## Conditional downstream derivation

The final coordinate derivation is valid. With `P=λA`, `λ=m²/ρ²`, `T=(t,0)`, the perpendicular-bisector condition `TA=TP` gives

`ρ²(1−λ²)=2tx(1−λ)`.

The prompt supplies `0<λ<1`, so canceling `1−λ` is valid. Substituting `λ=m²/ρ²` yields `2tx=ρ²+m²`, and hence `AT²=t²−m²`. The order `T-B-C` gives `t<−m`, `BT=−(t+m)`, and `CT=m−t`; therefore `BT·CT=t²−m²=AT²`. The answer applies `TC=BT+BC=157/11` and obtains the keyed exact value `AT=√2198/11`. The conditional relation, cancellation, exterior-branch signs, and numerical application are correct. The construction-to-foot relation and its branches were supplied in D and receive no independent proof credit.

## Strict whole-answer proof credit

The answer opens by asserting `AT²=AH·AP`. This is false in general and is neither proved nor explicitly withdrawn. The later heading “Corrected Target Relation” and the valid derivation of `AT²=BT·CT` implicitly replace the opening claim, but the answer never says the former relation is wrong. Under the frozen rubric's unresolved-contradiction rule, I recommend withholding strict whole-answer proof/completeness credit while recording the downstream conditional derivation itself as correct. The naturally stopped response used 6,628 completion tokens.
