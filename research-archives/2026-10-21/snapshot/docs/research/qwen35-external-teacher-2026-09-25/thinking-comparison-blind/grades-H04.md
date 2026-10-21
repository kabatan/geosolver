# H04 blind grading — fresh4

Scored answer text only under the frozen stage-localization rubric. The frozen H04 keys give
\(AT^2=BT\cdot CT=BT(BC+BT)\) for the exterior order \(T-B-C\), equivalently
\(AT^2=MT^2-(BC/2)^2\). Expected values are \(\sqrt{2198}/11\) for
\(BT=14/11,BC=13\), and \(\sqrt{305}/4\) for \(BT=5/4,BC=14\).

For every item, the mapping status is `given_in_original_problem`: the prompt already defines \(P\) as the foot from \(H\) to \(AM\), so no model-discovered mapping proof is scored.

| blind_id | BT, BC | Downstream relation and proof | Final exact value | Complete proof | Main issue |
|---|---|---|---|---|---|
| T001 | 5/4, 14 | Fail | 33/4 — wrong | No | Settles on unsupported \(AT=BC/2+BT\), contradicting its own earlier rejection of \(AT=|x_T|\). |
| T002 | 14/11, 13 | Pass | \(14\sqrt{157}/11\) — wrong | No | Correctly derives \(\sqrt{2198}/11\), then incorrectly simplifies it. |
| T007 | 14/11, 13 | Pass after self-correction | \(\sqrt{2198}/11\) — correct | Yes | Early reflection guess and sign confusion are explicitly corrected; final coordinate proof and branch are sound. |
| T008 | 5/4, 14 | Relation claimed; proof incomplete | \(\sqrt{305}/4\) — correct | No | Asserts the key coordinate for \(T\); later equal-distance algebra drops a denominator and does not repair the derivation. |
| T013 | 14/11, 13 | Pass | \(\sqrt{2198}/11\) — correct | Yes | Correct coordinate proof. The canceled factor is nonzero because \(S-c^2=(B-A)\cdot(C-A)=AB\,AC\cos A>0\) for acute \(A\); the answer leaves this implication implicit. |
| T014 | 5/4, 14 | Pass after self-correction | \(\sqrt{305}/4\) — correct | Yes | Replaces an incorrect initial vector path with a valid coordinate proof. |
| T018 | 14/11, 13 | Fail | \(\sqrt{2198}/11\) — numerically correct only | No | Derives \(DT^2=BT\cdot TC\) and \(AT^2=DT^2+AD^2\), then ignores the height term after recognizing the problem. |
| T019 | 5/4, 14 | Pass after self-correction | \(\sqrt{305}/4\) — correct | Yes | Final coordinate proof is complete; earlier false conjectures are corrected. |

## Counts

- Mapping claim status `given_in_original_problem`: **8/8** — T001, T002, T007, T008, T013, T014, T018, T019. Independent mapping proof is not scored because the prompt supplies the foot definition.
- Correct downstream relation claim settled in the answer: **6/8** — T002, T007, T008, T013, T014, T019.
- Correct downstream relation with a valid proof: **5/8** — T002, T007, T013, T014, T019.
- Correct written final exact value: **6/8** — T007, T008, T013, T014, T018, T019. T018 matches only by unsupported inference.
- Correct exact application (scored separately from proof): **5/8** — T007, T008, T013, T014, T019. T008 substitutes correctly into the true relation but does not complete its derivation.
- Complete proof through branch selection and exact application: **4/8** — T007, T013, T014, T019.

The eight items are two numeric probes repeated across four blind conditions, not eight independent geometry families. No arm labels were recovered. I used the blind packet, the frozen H04 answer key, and the frozen grading rubric; I did not open the mapping vault, original generation directories, or prior grades.
