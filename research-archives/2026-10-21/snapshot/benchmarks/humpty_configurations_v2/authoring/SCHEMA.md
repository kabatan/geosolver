# v2 authoring schema: geometry-first numeric tasks

Write JSON array, one record per assigned v1 ID (including deferred cards). Do not edit v1. root builder attaches v1 sources and original question for comparison. User explicitly authorizes natural internal lengths/angles as givens. No need to preserve all prior queries or adoption count. Only one well-designed primary question per configuration is required. Japanese.

```
{
 "id": "H01 / DA01 / DB01 ...",
 "decision": "main | probe | defer | holdout | exclude",
 "title_ja": "new concise title",
 "diagnosis_ja": "why v1 was computationally heavy or pedagogically weak",
 "change_ja": "exact change of givens/query and mathematical purpose",
 "problem_ja": "full self-contained concrete numerical problem; defines every object and branch; unnamed target points, no hidden relations/solution",
 "givens": [{"name":"AP", "value":"3", "meaning_ja":"..."}],
 "query": {"expression":"AX", "meaning_ja":"..."},
 "answer_exact": "sqrt(13) / 2",
 "geometry_solution_ja": ["First identify/prove useful relation, naming auxiliary construction if needed", "derive ...", "substitute ..."],
 "arithmetic_ja": ["actual small arithmetic remaining after the insight, not just 'easy'"],
 "why_geometry_helps_ja": "specific unknown coordinates/intersections/elimination no longer needed; do not invent runtime ratios",
 "shortcut_risk_ja": "does this reduce to one supplied equality? Can a problem-independent rule or unused construction bypass the intended geometry? Honest weakness",
 "parameter_family_ja": "general family of compatible givens with nice answers, allowing non-similar shapes if possible; exclusions. Do not count scaled copies as diversity",
 "feasibility": {
   "status": "verified | unverified | not_applicable",
   "method_ja":"original construction reproduced independently; all supplied values and answer checked; or explicit unverified reason",
   "witness": {"points":{"A":[0,3]}, "given_values":{"...":"..."}, "answer":"..."},
   "script":"verify_h_revision.py / verify_da_revision.py / verify_db_revision.py",
   "solution_status":"proved_here | source_proof_checked | source_claim_only | unverified"
 },
 "review_notes_ja": ["remaining concern / why this is not main, etc."]
}
```

For defer/holdout/exclude, problem/query/answer/witness may be null; never emit invented answers. Every assigned ID needs explicit reassessment, not silent omission. A main/probe problem must be fully specified and have an exact checked answer, an actual short geometric derivation, and a compatible nondegenerate example. The task need not determine the entire diagram uniquely if the target value is uniquely forced; explain this explicitly.

A desired main task has an identifiable geometric insight (point/line/circle recognition or auxiliary construction), followed by at least a little genuine inference and a few small calculations. A direct unknown-angle or length equality can be a useful probe but must be labeled probe instead of inflating the main set. Avoid setting every main question to 'given one side of the target identity, find the other'. Derive an intermediate using a second relation, choose a new endpoint, use a secant/power relation etc when mathematically natural.

Do not turn intended conclusions into input hypotheses. Do not hand learners a general formula that embodies the target theory. Researcher-only solution text stays outside the learner export. No requirement that a synthetic solution be shorter in character count than all possible coordinate solutions: the actual criterion is low remaining arithmetic and reusable geometry. Coordinate methods are legitimate, not penalized.

Small answers alone are insufficient: a lucky huge cancellation after elimination is still a bad main problem. Write the actual path a learner should be able to exploit. Verify every given value as well as the answer from original construction; sample existence is not general theorem proof. A symbolic/exact witness is preferred; numeric tolerance evidence may support geometry but does not by itself prove the exact answer. Scripts should output a concise pass report (or support --json for details), make no network requests, and validate your own records without writing them by default.

Existing H10/H11/EV01/EV02 stay outside training. Keep SD out. If direct Humpty/Dumpty use is absent or superficial, defer instead of retaining merely to reach a target count.
