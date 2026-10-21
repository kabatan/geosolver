# Balanced true/false relation-QA comparison against exact repeats

The balanced QA dataset is a separate training arm: `train-38-balanced-qa.json` contains the shared 32-row base and six relation-check QAs from `candidate-qa.json`. It does not contain the integrated worked-answer rows in `train-38-direct-multi.json`. All six QA assistant targets now include the decisive proof and exact numerical application; the answer key remains unchanged at three true and three false. False symbolic claims remain in the user prompts and are not repeated in the corresponding assistant answers.

For H01, every answer uses M=(0,0), B=(-m,0), C=(m,0), A=(x,y), derives the orthocenter coordinate, A·H=m², the projection factor, and the acute-angle branch t²−m²>0 before computing AP and MP. For H07, every answer writes both circle equations, derives the common chord through O and lambda from its two radial roots, then constructs reflected E and computes P,Q, PQ, height, and area. SymPy exact checks are in `balanced-qa-audit.json`.

Both QA and repeat groups have 38 rows and 32 sources; H01 and H07 each have four presentations including the base row. Only QA answers were revised; repeat data and its protocol are unchanged.

| Arm | Assistant tokens including EOS | Maximum sequence tokens |
|---|---:|---:|
| Balanced QA | 22917 | 1238 |
| Exact repeat | 22645 | 1238 |

Token counts use the Qwen3.5-9B tokenizer at revision `c202236235762e1c871ad0ccb60c8ee5ba337b9a` with train.py's non-thinking chat template and assistant-through-EOS target logic. No GPU training, model output, or evaluation result was used or inspected.
