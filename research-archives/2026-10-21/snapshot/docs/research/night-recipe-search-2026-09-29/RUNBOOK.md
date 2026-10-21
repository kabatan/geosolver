# Continue the authorized overnight experiment

## Current controlling amendment: complete the original plan

Read [COMPLETION_AMENDMENT.md](COMPLETION_AMENDMENT.md) first. The user's latest
instruction removes all wall-clock cutoffs and authorizes completion of the
original finite plan, including identical recovery of DX512/Base main/S128 main
after external-GPU interruptions. Old exhausted retry records below are history;
`completion-policy.json` controls those resource recoveries now. ComfyUI priority
and the sixty-second quiet check remain in force.

The restored launcher is `resume.py initial`, which reuses completed artifacts
and recovers the missing original jobs. Check `continuation.json` and live
processes before any launch. The old `evaluate_available.py` is retired. After
the full seven-arm screen, apply the original common-cap checks, blinded review,
and `decide.py` without bypass, then the originally prescribed branch A or B.
Only after that branch and final audit/report should the completion marker be
saved, sleep inhibition released, and the heartbeat paused. No new recipes.

All time limits and permanent missing-comparison statements in the historical
sections below are superseded by this completion amendment; scientific settings
and grading instructions remain applicable.

Repository: `/home/kabatan/work/solver`. This is an already authorized execution,
not a request to design a new study. Read `TIMING_AMENDMENT.md`, `PROTOCOL.md`, and the runtime
`qwen/.runtime/night_recipe_search_20260929/status.json` first. Preserve all
pre-existing repository changes. Do not spawn subagents without user instruction.

Start: 2026-09-28 17:30:45 UTC. The original cutoff/deadline in `clock.json`
are historical base values. The user subsequently authorized a modest extension
for GPU waiting and explicitly prohibited interrupting ComfyUI. `timing.py`
adds actual GPU waiting to both cutoffs, capped at two hours. Read its output or
`effective-timing.json` for the current limits. Latest possible final deadline:
2026-09-29 08:30:45 UTC (17:30:45 JST). The final 90-minute reserve is preserved.

## Live state as of 2026-09-28 18:20 UTC

- Data, all six fresh confirmation questions, and all configurations are frozen.
- All 560 original/generated shapes passed independent 60-digit reconstruction;
  maximum relative-or-unit discrepancy 5.46e-12. Original56 rows unchanged.
- S, X, and D training completed 32 -> 128 -> 512 updates. DX not started yet.
- No inference/evaluation has started yet.
- Initial launcher session 42349 ended after a prelaunch GPU guard refusal.
  This was not a model/training failure. Its log is preserved under
  `failed-attempts/prelaunch-DX32/guard-refusal.log`.
- `resume.py initial` is running as exec session 15939, waiting for the GPU.
  Check its actual process before launching anything else; never duplicate it.
  It automatically completes DX training, then all initial evaluation jobs.
- Another project's ComfyUI server PID 2088929 was holding GPU memory (6.6GB,
  then ~16GB). The priority question has now been answered: do not interrupt
  ComfyUI; wait for GPU availability. Do not ask this question again. Do not
  stop it or unload its models. `TIMING_AMENDMENT.md` supersedes the old deadline.
- New GNOME Settings PID 2085852 is a desktop C+G process. `resume.py` adds only
  identity-verified `/usr/bin/gnome-control-center` to the desktop inventory.
  It waits for other compute PIDs without terminating them. The original frozen
  campaign, guard, training and inference code/data are unchanged. See
  `operational-amendment-001.json` and `operational-amendment-002.json`.
- Temporary sleep inhibitor session 95442 runs `keep_awake.py`; it releases when
  `campaign-complete.json` appears or at the dynamically updated bounded deadline.
  It blocks sleep only. PIDs/session IDs above predate the timing amendment;
  inspect live processes and `continuation.json` for their replacement IDs.

Read live files/processes; these snapshot notes will become stale.

## Latest recovery at 2026-09-29 03:42 UTC

S128 main's single identical retry started at 03:38:28 UTC and was interrupted
at 03:38:47 UTC when ComfyUI PID 2412289 appeared. It saved zero answers.
Both attempts are archived, and `retry-S128-main-32768.json` has zero retries
remaining. **No third S128 main attempt or higher-cap/seed substitute.** Its
first attempt's four archived partial answers remain separate and cannot be
merged into another run or treated as a completed 24-answer comparison.

`initial-unavailable.json` now excludes Base main and S128 main as well as DX512.
The same `evaluate_available.py` skips these jobs after checking exhausted retry
records. Base and S128 each retain complete short168 and retention4 outputs.
Remaining original evaluations are X128/S512/X512/D512. The paired S512/X512
comparison can still be reported if completed; 128-update transfer replication
and a new Base transfer comparison cannot be completed in this campaign.

`resume.py` now requires 60 consecutive seconds without competing compute before
each GPU job, resetting the timer if competition returns. This addresses the
observed brief gaps between external GPU jobs; it cannot guarantee no later
contention. The quiet period is excluded from contention wait credit. Original
GPU guard, live monitor, scientific settings, and retry limits remain unchanged.
CPU validation and backup are in `operational-amendment-006.json` and
`amendments/006-gpu-quiet-period`.

This supersedes earlier cap groups: main first12 = X128/S512/X512/D512;
main second12 = X128 only (standalone description, no replication comparison);
short and retention = Base/S128/X128/S512/X512/D512. Apply common-cap rules only
to completed available groups with the exact original ordered subsets. Do not
recover excluded main jobs through cap extensions or bypass `decide.py`.

## Latest recovery at 2026-09-29 03:20 UTC

The GPU became free at 03:00 UTC and S128 short168 and retention4 completed.
S128 main's first attempt was interrupted at 03:14:34 UTC when external compute
PID 2402907 appeared. Its first batch saved four answers (two natural stops,
two cap hits); all four and the logs are preserved under
`failed-attempts/eval-S128-2026093001-main-32768-attempt1` with verified hashes.
Its single identical full-job retry is queued in `retry-S128-main-32768.json`.
Do not merge those archived partial answers into the retry or choose between
attempts. S128 short and retention remain complete and are skipped by receipt.
The launcher remains `evaluate_available.py`; current identity is in
`continuation.json`. Base main and DX512 remain unavailable as described below.

## Current recovery at 2026-09-28 23:50 UTC

Base main's single identical retry was interrupted at 23:46:54 UTC when
ComfyUI PID 2285696 began using the GPU. The first four requests were in flight,
but no answers had been saved. Both attempts are archived; see
`retry-Base-main-32768.json`, which now has zero retries remaining. **Do not run
Base main a third time or use a different cap/seed to circumvent this limit.**

`evaluate_available.py` now explicitly skips the exhausted Base main job listed
in `initial-unavailable.json`, in addition to unavailable DX512. The remaining
original evaluations proceed unchanged. Its CPU call-plan validation and source
backup are in `operational-amendment-005.json` and `amendments/005-base-main-unavailable`.
Base short168 and retention4 are complete. Do not overwrite these outputs.

There can be no new comparison against Base on transfer, and no branch A/B.
S/X paired transfer comparisons and six-arm numeric diagnostics/retention may
still be reported, with the missing Base main and DX512 explicit. Historical
Base answers must not be substituted into this campaign.

This supersedes the six-arm cap command in the earlier recovery below: that
command will now correctly fail on missing Base main. When the remaining
evaluations finish, common-cap handling must use the explicit available groups:
main first12 = S128/X128/S512/X512/D512; main second12 = S128/X128;
retention and short = Base/S128/X128/S512/X512/D512. Preserve the original ordered
question subsets, per-job seeds, batching and bounds, and regenerate each needed
subset for every arm in its available group. Do not include S512 in the second
sample group by slicing a shortened arm list. Treat any further exhausted job as
missing evidence, not failure on its questions. Do not bypass `decide.py`.

## Current recovery at 2026-09-28 22:50 UTC

The single DX512 retry began at 22:48:01 UTC. An unrelated SDXL training
process PID 2257275 appeared, and the live monitor stopped only the campaign's
owned process group at 22:48:33 UTC. The external process remained running.
Attempt 2 is preserved under `failed-attempts/train-DX-2026093001-512-attempt2`.
Raw receipts still saying `running` belong to that interrupted process and are
not completion evidence. Both its launcher and guard process group are gone.

**Do not restart `resume.py initial`: DX512 has zero retries remaining.**
The replacement waiting launcher is `evaluate_available.py`; its current PID
and session are in `continuation.json`. It executes only the original frozen
evaluations for Base/S128/X128/S512/X512/D512. DX512 remains unavailable, with
details in `initial-unavailable.json`. There are no new arms or settings.

After these six arms finish, the original cap procedure can be applied to those
available arms using the unchanged extension code with an explicit operational
arm subset:

```
PYTHONPATH=docs/research/night-recipe-search-2026-09-29 .venv/bin/python -c 'import sys,resume,extend; extend.ARMS=[a for a in extend.ARMS if a!="DX512"]; sys.argv=["extend","--execute"]; extend.main()'
```

Record this as a six-arm incomplete screen, not a completed seven-arm screen.
Then create the usual condition-hidden review packets and grade the full text.
The frozen `decide.py` correctly refuses an incomplete seven-arm comparison;
do not bypass its completeness check or start branch A/B. Report available
paired results with the missing matched control and incomplete gate explicit.
Run the applicable mechanical audits, preserving any missing-output findings.
Keep the original final deadline and the final audit/report reserve.

At 22:58 UTC Base short diagnostics completed all 168 jobs. Base retention was
interrupted during model startup when ComfyUI PID 2265097 appeared; it produced
no answers. Its first attempt is archived and its single identical retry is
recorded in `retry-Base-retention-32768.json`. Before any recovery inspect the
matching `retry-*.json` records so an exhausted retry is never repeated.

At 23:24 UTC the Base retention retry completed all four jobs. The immediately
following Base main evaluation was interrupted during startup when an external
SDXL training process PID 2276294 appeared; it produced no answers. That first
attempt is preserved under `failed-attempts/eval-Base-2026093001-main-32768-attempt1`.
Its single identical retry is queued in `retry-Base-main-32768.json`; Base short
and retention are complete and must not be regenerated. The replacement launcher
still uses `evaluate_available.py`; inspect `continuation.json` for its PID.

## Earlier recovery at 2026-09-28 22:11 UTC

DX32 and DX128 are complete. The first DX512 continuation failed at global
update 402 with a verified CUDA OOM after ComfyUI PID 2231386 appeared during
the run. All failed training files, driver logs, and guard receipts are preserved
in `failed-attempts/train-DX-2026093001-512-attempt1`, with original file hashes.
`retry-DX512.json` authorizes the protocol's single identical retry from the
completed DX128 adapter and optimizer; do not reuse the incomplete update-402
state and do not grant a second retry for this stage.

`resume.py` now also uses `gpu_priority.py` to observe new competing compute
processes during each job. It signals only its own launcher, whose unchanged
campaign cleanup releases its owned GPU process group. No external process is
signalled. A competition interruption stops the launcher for inspection; it does
not silently retry or merge partial results. The new monitor and CPU validation
are documented in `operational-amendment-003.json`. All frozen scientific inputs,
training commands, decoding settings, and the original GPU guard are unchanged.
Read `continuation.json` for the replacement launcher PID/session.

## Execution

CPU scientific Python: `.venv/bin/python`. GPU Python is selected by campaign.
If the initial process exited, inspect the actual error before one allowed
identical retry. Archive failed attempts; never silently overwrite or combine
partial outputs with new ones. The shared GPU guard must remain active.

The initial pipeline is:

```
.venv/bin/python -u docs/research/night-recipe-search-2026-09-29/resume.py initial
```

The original runner skips completed checkpoints only after verifying receipts.
It does not tolerate existing incomplete output directories; handle any such
failure explicitly and preserve evidence. Source files in frozen-manifest.json
must not be edited casually.

After initial completion, inspect cap hits and run required common-cap
extensions. To retain the operational GPU wait wrapper for the extension script:

```
PYTHONPATH=docs/research/night-recipe-search-2026-09-29 .venv/bin/python -c 'import sys,resume,extend; sys.argv=["extend","--execute"]; extend.main()'
```

Then score and create a condition-hidden packet:

```
.venv/bin/python docs/research/night-recipe-search-2026-09-29/score.py --blind
```

Review `review/case-*.md` and `review/blind-packets.json` WITHOUT opening
`review/mapping.researcher-only.json` until grades are saved. Read complete
reasoning, not only final lines. `REVIEW.md` gives criteria. Correct applicable
specialized known properties are permitted in numeric solving without reproof;
guesses and false supporting derivations are not. The compact researcher-only
reference contains correct relations. The old reference's H08 witness was stale;
use the frozen question/key for actual numbers (H08 answer 27/2).

Save `review/grades.json` as a list with `review_id`, `verdict` (valid/invalid/
unclear), `lenient_valid` boolean, `rationale`, and decisive excerpts. Record
whether success is a self-contained coordinate derivation or use of a correct
specialized property. The reviewer is the executing assistant; do not claim
independent human or multi-agent review. Grades must cover every packet.

```
.venv/bin/python docs/research/night-recipe-search-2026-09-29/decide.py
```

This checks the frozen common12 gate. Do not select by numeric accuracy alone.
Base/S128/X128 also have 24 outputs for the original recipe replication.

## Branch A: an eligible recipe

Train selected family and matched control fresh with seed2026093002 to selected
128 or 512 updates, using `resume.py train --family S|X|D|DX --seed 2026093002
--target 128|512`. Evaluate Base and both selected arms with `resume.py generate
--arm Base|S128|X128|S512|X512|D512|DX512 --seed 2026093002 --kind confirmation
--jobs <absolute runtime>/jobs/confirmation18.json`. All18 questions and seeds
are already frozen. Apply common-cap policy to these three arms. Create a new
blind packet with `score.py --blind --kind confirmation --review-name
review-confirmation`, grade it independently of condition mapping, then compare.
Report old12 and fresh6 separately; the fresh6 target three historically improved
families and are not a random broad generalization sample.

## Branch B: no eligible completed initial recipe

Only if enough time remains for the complete bundle: train D6 and DX6 fresh
seed2026093001 to512 using `resume.py train --family D6|DX6`. Then generate each
with `resume.py generate --arm D6|DX6 --kind precision --jobs <runtime>/jobs/main12.json`.
Compare to the initial common12 Base/D512/DX512 at the same per-job cap.
If extensions are needed, regenerate the same subset for all five compared arms
using kind `precision` and the same batching. Keep this branch's cap decisions
separate from the already reviewed initial comparison. Existing initial outputs
can be reused only when their cap and batches agree. Create a new packet using
`score.py --blind --kind precision --review-name review-precision` after extensions.
Do not invent further recipes or choose checkpoints retrospectively.

## Finish

Run the mechanical audit (`audit.py`), check hashes/seed/batch consistency,
assemble primary valid+numeric counts, raw numeric counts, retention, trained56
and heldout112 diagnostics, paired wins/losses by family, tokens/caps/timing.
Do not treat correlated repeated answers as independent problems or claim
statistical confirmation from the exploratory gate. A stopped or incomplete
comparison is censored, not a negative result about the learning hypothesis.

Write `docs/research/night-recipe-search-2026-09-29/REPORT.md` with a candid
recommendation and concrete supporting examples. If blocked until time expires,
report exactly which training/evaluation completed and what remains untested.
Do not infer transfer from training loss. Preserve all weights and raw outputs.

When finished, write runtime `campaign-complete.json` with status and report path
to release the sleep inhibitor. Stop only campaign-owned processes if necessary
to respect the deadline, never unrelated jobs. Disable the continuation heartbeat
through automation_update and report the result in Japanese. Leave the user's
research task unarchived.
