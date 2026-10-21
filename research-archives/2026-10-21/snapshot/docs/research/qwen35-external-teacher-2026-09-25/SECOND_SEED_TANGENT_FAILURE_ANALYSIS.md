# Second-seed tangent/reflection failure analysis

Scope: the first-pass and repeat1 unblinded H08/H15 evaluation answers, plus the frozen `heldout-near-transfer/lemma_overlap.json` audit. H08 and H15 are separate probes.

## H08: tangent circles and reflection

The missing step is the acute-branch identity \(\angle CAP=\angle BAQ\), or an equivalent dot/cross-product relation derived from both tangent-circle equations and \(AP=AC\). Across the eight outputs, the model repeatedly substitutes a right angle, an unsupported sine value, or an angle claim that does not follow from tangent-chord angles. The resulting area claims vary (first pass: 17, 204/13, 17, 289; repeat1: 12, 17, 17, 12) and are not supported by a derivation of the required angle relation.

There is a valid partial relation in a repeat1 answer: reflection gives \(PC=PB\), and cosine rule with \(AP=AC\) yields \(PB=2\,AP\cos(\angle APC)\). That reduces the area to an expression in an angle, but the answer then asserts, without deriving it, that \(\sin(2\angle APC)=12/17\). Other answers correctly set up the tangent circles or their radical axis, but do not turn those equations into the target angle identity or verify the acute branch.

The frozen overlap audit reports method-level overlap from H07 and DA01/DA04/DA06/DA11/DA16/DB01, but no audited teacher answer contains this angle lemma. Thus the failures fit a missing decisive relation: available examples supply tangent-circle/reflection techniques, not the bridge from those techniques to the angle needed here.

## H15: three reflections and a midpoint

The decisive step is deriving that \(K\) is the midpoint of \(AD\), then applying Apollonius in \(\triangle ABD\). No first-pass or repeat1 answer derives that midpoint. Instead, answers assert unrelated locations such as \(K=D\), \(K=E\), an orthocenter, or a reflection of a center; others guess a similarity and substitute the given lengths. Their final claims vary (first pass: \(13\sqrt3/3\), 7, \(56\sqrt{97}/97\), \(28/3\); repeat1: \(21\sqrt{97}/97\), \(48/7\), 7, \(56\sqrt{97}/97\)).

Some answers do reach useful preliminary facts: the tangent intersection puts \(AX\) on the A-symmedian, and the corresponding chord ratio \(BD/CD=AB/AC\) is sometimes stated or used. This does not propagate through the three reflections to locate \(K\), so it is only partial progress. The frozen audit finds H07's single-reflection method and DA15's perpendicular-bisector method as weak overlaps; neither contains the three-reflection midpoint lemma.

## Fair positive-control diagnostic

Before another run, freeze two new, independently generated control IDs, one per family, with different wording, labels, and numerical parameters. Ask the external teacher for complete derivations: the H08 control must use both circle equations, derive the angle identity, and justify the acute branch; the H15 control must derive the three-reflection midpoint and then use Apollonius. Blind-grade the controls with the same relation/proof/use rubric. Keep the complete H08/H15 IDs, statements, parameters, and outputs out of teacher prompts, training examples, and tuning. If training is attempted, use separate fresh control IDs for training and evaluation. A teacher pass would establish that this pipeline can produce suitable supervision on independent instances; it would remain a lower-bound result, not evidence that the trained model has transferred the lemma to H08 or H15.
