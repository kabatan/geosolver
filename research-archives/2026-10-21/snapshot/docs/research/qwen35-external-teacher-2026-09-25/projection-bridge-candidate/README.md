# Projection-bridge candidate arms

Status: **candidate / untrained**. These files are CPU-built training inputs,
not model results. No GPU, adapter, LOO output, or held-out evaluation answer
was used to construct them.

Each rotation starts from the same frozen 32-row common base and adds six rows
per arm. Its two permitted English v0 projection-family sources each contribute
three rows per arm. In treatment, rows 1 and 2 separately target the
construction relation and its proof; row 3 uses the exact standard problem
prompt and asks for a full, self-contained integrated solution, so it does not
rely on the other treatment rows being sampled together. Control has three
complete integrated solutions per source: one uses that same exact standard
prompt, and two use distinct paraphrases of the whole task.

| Rotation | Omitted target (audit metadata only) | Permitted v0 sources |
|---|---|---|
| rotation-1 | H03 | H04, H14 |
| rotation-2 | H04 | H03, H14 |
| rotation-3 | H14 | H03, H04 |

Every merged arm has 38 rows and 34 distinct source IDs. Each treatment and
control file preserves the base rows unchanged. The addition files contain
exactly six rows, balanced three per permitted source. The omitted target's
problem, answer, and source are absent from that rotation's training rows.

## Exploratory token-budget tolerance

Counts use the frozen 32-original Qwen tokenizer on assistant answer text plus
one EOS token per row. They do not count prompts or the chat wrapper. The
32-row base contributes 19,936 assistant-target tokens to both arms. This
exploratory comparison accepts at most a 2% relative mismatch in the merged
38-row answer-token totals, using the larger arm as the denominator. All three
rotations meet that predeclared tolerance; this is approximate matching, not
strict token equality.

| Rotation | Added treatment/control | Added mismatch | Merged treatment/control | Merged mismatch |
|---|---:|---:|---:|---:|
| rotation-1 | 1,424 / 1,623 | 199 (12.26%) | 21,360 / 21,559 | 199 (0.923%) |
| rotation-2 | 1,867 / 2,040 | 173 (8.48%) | 21,803 / 21,976 | 173 (0.787%) |
| rotation-3 | 1,467 / 1,389 | 78 (5.32%) | 21,403 / 21,325 | 78 (0.364%) |

The additions alone remain mismatched by 5.32–12.26%; the longer arm varies by
rotation. The merged-dataset tolerance therefore does not imply equal added
supervision or a strict dose-matched effect. No token padding or unrelated
text was added. Read [PROTOCOL.md](PROTOCOL.md) for the acceptance rule and
intended exploratory interpretation.

## Source integrity and math review

audit-manifest.json records exact source counts, source SHA-256 hashes,
accepted v0 audit fields, candidate-data hashes, and token-count details.
candidate-hashes.json additionally hashes the builder and documentation.
MATH_CAVEATS.md lists branch, nonzero, and construction conditions for an
independent review. The build script verifies the 32-row base, accepted audited
v0 status, source balance, unique source limits, omitted-ID absence, standard
integrated prompt alignment, and the merged-token tolerance before writing
each arm.

Rebuild with Python 3.12 and the tokenizers package:

    uv run --no-project --with tokenizers --python 3.12 python \
      docs/research/qwen35-external-teacher-2026-09-25/projection-bridge-candidate/build_candidate.py
