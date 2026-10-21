# Exploratory decision rules

Recorded on 2026-09-23 before the 16-question confirmation runs and before weight updates. These are practical follow-up rules, not significance tests or claims of complete mastery.

- A pretrained setting with at least 28/32 fully justified answers on the confirmation set, including valid treatment of the false-claim controls, is a candidate to use directly. Inspect failures and target-development outputs before recommending it as the common starting model. This small, authored set cannot establish general reliability or absence of target knowledge.
- For the one fixed original-4B FT intervention, an increase of at least 4/32 fully justified answers, or substantial generation-cost reduction without a decrease in valid answers, justifies a larger independent confirmation. Inspect new failures and changes in reasoning; do not count shorter output alone as learning more mathematics.
- If an untrained native mode or four-example prompt attains the same practical result, prefer that inexpensive option unless FT shows a useful additional benefit. Prompt and FT contain different amounts of information; they compare practical alternatives, not a controlled mechanism at equal information.
- A negative result from 24 training structures and one seed does not establish that foundation FT is ineffective. It does constrain the claim that a tiny, cheap recipe already solves the bottleneck.
- Target-development performance is a separate suitability check. Routine correct coordinate solutions remain weak mathematical-usefulness successes under the user's rubric. Foundation gains do not validate the research hypothesis.
- If one new pretrained setting looks promising in the screen, add the already frozen 16-question confirmation and the four target-development questions for that setting. Do not tune against these answers or train on them.
