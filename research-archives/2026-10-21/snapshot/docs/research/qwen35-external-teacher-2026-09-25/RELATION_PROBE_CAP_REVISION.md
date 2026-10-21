# Relation-only probe cap revision

The original relation-only diagnostic specified 512 new tokens. The base run finished, and while the 32-original run was in progress, its **length-only** log showed three of the first five responses hitting that cap. No relation-only answer text was opened or scored, and the main 32,768-token integrated comparison was already complete and masked for grading.

The 512-token runs are retained as pilot generation receipts but will not be compared as a relation-quality result. To reduce truncation as a confound, rerun the **same nine frozen relation-only jobs for all four conditions**, including base, with a uniform 2,048-token cap and unchanged model, seed, temperature, top-p, top-k, presence penalty, context, and non-thinking mode. Score the complete set without selecting responses or conditions. Any remaining length stops will be reported and graded conservatively. This is a result-informed exploratory diagnostic; it is not evidence for autonomous relation discovery.

After both pilot runs finished, the length-only counts were 3/9 at the 512-token cap for base and 6/9 for 32-original. Neither pilot answer text was inspected or scored before the uniform 2,048-token rerun began.
