# Follow-up bridge blind-scoring protocol

This protocol applies to the frozen ten-job set in `eval_jobs.json`. It is a
CPU-only packet and scoring utility; it does not run inference. The base and
six rotation outputs must all use the same ten prompts, frozen seeds, and
sampling settings recorded in the evaluation protocol.

## Files and input contract

`blind_bridge_tools.py` consumes the native `generate.py` output directory for
each condition. Pass exactly seven repeated `--input CONDITION=DIR` options.
Each directory must contain `receipt.json` and exactly one `<job-id>-0.json`
per frozen job (plus any non-JSON logs the generator produced). The job record
uses the generator's native schema, including `id`, `source_id`, `seed`,
`messages`, `final_text`, `finish_reason`, `prompt_ids`, and
`completion_ids`. The packetizer checks the record's ID, source, seed, and
messages against the frozen job; it does not require fields the generator
doesn't emit.

Each receipt must be complete, point to the exact frozen jobs file by
`jobs_sha256`, and include generation metadata. The seven receipts must agree
on sample count, cap, context, temperature, top-p, top-k, presence penalty,
thinking setting, driver hash, and model metadata hash; the adapter field may
differ by condition. This bridge expects one sample. Each completion must end
with `finish_reason: "stop"` and `len(completion_ids) < receipt.cap`; each
prompt's recorded token length plus cap must fit within receipt context.
Missing/extra job files, truncated output, mismatched prompts/seeds, failed
receipts, or inconsistent settings reject packet creation. It verifies the
raw `eval_jobs.json` SHA-256 against `hashes.json`, the ten-job count and
source order, and expected source counts. Receipt hashes, per-job file hashes,
frozen case hashes, prompt hashes, and answer hashes are recorded in the
separate private vault.

The native generator's `finish_reason` must be `stop`; length caps, timeouts,
interruptions, or unknown finish states are not natural stops and must not be
normalized into one.

## Blinding and freeze order

Run `build-packet` once all seven output directories are complete. It writes a
shuffled 70-row packet and a separate private vault. The packet has
blind IDs, source IDs, prompts, and answers; it contains no condition labels,
job IDs, or vault hashes. Keep the vault outside the grader's access.
The shuffle seed is random by default; an explicit seed is useful only for a
reproducible synthetic test.

The grader returns one row per blind ID, with strict JSON booleans for
`exact`, `relation`, `proof`, `use`, and `uncertain`, plus a concise math note.
The grade file is a JSON list, for example:

```json
[
  {
    "blind_id": "B001",
    "exact": true,
    "relation": false,
    "proof": false,
    "use": true,
    "uncertain": false,
    "note": "Computes the value but does not derive the target relation."
  }
]
```

`freeze-grades` validates exact packet coverage and writes the frozen grade
artifact bound to the packet SHA-256. This step does not read the vault. Only
after that artifact is frozen should `join` be run with the private vault.
Join verifies packet, frozen-job, receipt, case, grade-row, and vault alignment
hashes.

## Scoring and reporting

For every answer, `complete = exact AND relation AND proof AND use`.
Uncertain grades remain visible, but are excluded from complete-rate
denominators until adjudicated. A frozen grade file or packet must not be
silently edited: the join rejects hash mismatches.

The frozen rotation order is rotation-1 omitting H03, rotation-2 omitting H04,
and rotation-3 omitting H14. For each rotation, the heldout slice contains
only that omitted ID's two fresh4 jobs; the same two base answers are reported
as the matched reference. The other four H03/H04/H14 fresh4 jobs are reported
as `seen_source`; the four H01/H02/H07/H13 fresh2 jobs are reported as
`retention`. No other fresh4 job enters that rotation's heldout count.

H04 is additionally reported in a separate `lower_bar_H04` slice for all
seven conditions. H04-only improvement is not evidence of hidden-relation
transfer; H03 and H14 require the construction-to-projection correspondence
to be proved. Results remain exploratory and test an external-teacher
lower-bound step, not discovery without external teachers.

## Commands

```sh
python3 blind_bridge_tools.py build-packet \
  --eval-jobs eval_jobs.json --frozen-hashes hashes.json \
  --input base=/secure/base \
  --input rotation-1-treatment=/secure/rotation-1-treatment \
  --input rotation-1-control=/secure/rotation-1-control \
  --input rotation-2-treatment=/secure/rotation-2-treatment \
  --input rotation-2-control=/secure/rotation-2-control \
  --input rotation-3-treatment=/secure/rotation-3-treatment \
  --input rotation-3-control=/secure/rotation-3-control \
  --packet-out /secure-for-grading/blind-packet.json \
  --vault-out /private/bridge-vault.json

python3 blind_bridge_tools.py freeze-grades \
  --packet /secure-for-grading/blind-packet.json \
  --grades /secure-for-grading/blind-grades.json \
  --frozen-out /private/frozen-grades.json

python3 blind_bridge_tools.py join \
  --packet /secure-for-grading/blind-packet.json \
  --vault /private/bridge-vault.json \
  --frozen-grades /private/frozen-grades.json \
  --eval-jobs eval_jobs.json --frozen-hashes hashes.json \
  --report-out /private/scored-report.json
```

The repository smoke test uses temporary synthetic records only:

```sh
python3 smoke_test_blind_bridge.py
```
