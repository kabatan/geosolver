# DB08 anonymous consistency review

I read all eight full packets without opening the private arm mapping or earlier review05 grades. The [calibrated rubric](../../related-numeric-sft-2026-09-28/REVIEW_RUBRIC.md) permits citing the verified special result that, for this exact construction, `OP=PX` is tangent to `(KLX)` at `X`. Then `PZ=PY+YZ=12`, so power of a point gives `PX²=3·12=36` and `PX=6`. The [compact reference](../../related-numeric-sft-2026-09-28/numeric-review-reference-compact.json) was used to check that statement, not to fill an omitted premise. A claim that the answer must use tangency merely because the problem has a unique or neat numerical answer is false.

| Case | Final derivation | Permissive / strict | Final number | Where the bad explanation sits |
| --- | --- | --- | --- | --- |
| 00 | valid | valid / unclear | 6, correct | The false `A,O,P,X` cyclic statement at line 54 is ancillary; the exact tangency lemma is independently retained at lines 81, 87 and used at 129–132. |
| 01 | valid | valid / unclear | 6, correct | Speculative digressions are not the final premise. The specific tangency is stated at lines 150, 237 and applied at 231–239. |
| 02 | invalid | invalid / invalid | 3, wrong | The correct lemma at line 77 is expressly retracted at 109. The final answer assumes `U∈OP` and guesses `X=Y` (295–301). This is geometry error, not arithmetic error. |
| 03 | invalid | valid / invalid | 6, correct | A correct lemma appears at 56, but the numbered final deduction at 106–109 says uniqueness of the answer forces tangency; this is a false replacement for that lemma. A permissive reading can instead use 56 and 126. |
| 04 | invalid | valid / invalid | 6, correct | An unsupported `EF⊥OP`/symmetry mechanism at 87 and uniqueness argument at 135 are presented as reasons for tangency, while the correct lemma at 116 is left as an assumption. |
| 05 | invalid | valid / invalid | 6, correct | Lines 151–162 incorrectly put `A` on the circle with diameter `PX`; line 264 calls this false setup crucial to the final tangency. A correct specialized statement also appears at 254. |
| 06 | invalid | valid / invalid | 6, correct | Lines 215–218 infer `U∉OP` from asymmetry and tangency from a unique-number heuristic. The true special theorem is stated at 224, allowing a permissive extraction, but the false chain remains part of the final rationale. |
| 07 | invalid | valid / invalid | 6, correct | The early isosceles thought experiment is substantially withdrawn as singular (203). The decisive final rationale is still the uniqueness heuristic at 216, 252 despite correct theorem statements at 130–131. |

The numerical power computation is arithmetically correct in every packet that ends at 6; none of those has a separate arithmetic error. Case 02's final 3 comes from an invalid geometric identification. The packet-by-packet line quotes, uncertainty and full read coverage are in `consistency06.json`. No manifest or existing grade was changed.
