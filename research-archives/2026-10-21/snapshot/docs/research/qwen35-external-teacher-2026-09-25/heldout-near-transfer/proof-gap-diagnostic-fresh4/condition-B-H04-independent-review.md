# Independent review: condition B, H04

I reviewed only the two B-condition H04 `final_text` outputs, the frozen B prompts/key, and the grading rubrics. I did not open the primary B-H04 grades before forming this assessment.

## Mathematical core shared by both answers

The final vector argument in each answer is sound. Put `M=(0,0)`, `B=(-c,0)`, `C=(c,0)`, `A=(x,y)`, where `c=BC/2` and `s=MA^2`. Since `P` is explicitly defined as the foot of `H` on `AM`, the supplied projection lemma gives `MP·MA=c^2`, hence `P=(c^2/s)A`. The perpendicular-bisector condition is `TA=TP`. For `T=(t,0)`, expanding squared distances and canceling the common factor `s-c^2` yields `2tx=s+c^2`; this factor is nonzero because `s-c^2=AB·AC·cos(A)>0` for acute `A`. Therefore

`AT^2=s+t^2-2tx=t^2-c^2=MT^2-(BC/2)^2`.

The stated order `T-B-C` gives `t<-c`, `MT=BT+c`, and `TC=BT+2c=BT+BC`, so `AT^2=BT·TC`. This sign/branch and both exact substitutions are correct.

## Item review

| Job | Exact | Relation/use | Strict proof recommendation | Decisive note |
|---|---:|---:|---:|---|
| H04 instance 1 (`...H04-fresh4-0`) | Pass: `√2198/11` | Pass | **Fail under the strict whole-answer rule** | The final coordinate derivation and exterior-branch arithmetic are valid. However, the answer leaves false proof-side assertions uncorrected: its opening conditions say the isosceles case would give `P=H=M`, and its abandoned similarity route states the false product `DH·DC=BD·BH`. The subsequent coordinate proof supersedes that route but never explicitly retracts those claims. If grading only the final decisive derivation, proof could pass; strict unresolved-claim grading should withhold proof credit. |
| H04 instance 2 (`...H04-fresh4-1`) | Pass: `√305/4` | Pass | **Fail under the strict whole-answer rule** | Its final derivation, explicit correction of the erroneous first cancellation, positive branch, and arithmetic are valid. But the answer opens by asserting that `AT⊥BC` must hold and proposes `BT=|BM−AT|`; it never explicitly retracts these claims. `AT⊥BC` is impossible here: for acute `ABC`, the altitude foot from `A` lies inside `BC`, while `T-B-C` puts `T` outside `BC`. The final valid argument drops this assertion without resolving the contradiction. |

Both prompts already give the projection definition of `P`; record mapping as `given_in_original_problem`, not as a model-discovered mapping or a separately proved construction fact. The supplied lemma is used correctly in the final derivations. Both answers naturally stop (4,991 and 7,339 completion tokens, respectively).

### Strict-credit caveat

If the grading convention treats the mathematically correct final derivation as dispositive and regards every earlier wrong route as discarded, both answers pass proof as well as exact/relation/use. Under the frozen rubric's instruction not to excuse unresolved contradictions, I recommend withholding proof credit as above: neither response explicitly resolves all of its false preliminary claims. The numeric answers and the final `AT²=BT·TC` derivations themselves are correct.
