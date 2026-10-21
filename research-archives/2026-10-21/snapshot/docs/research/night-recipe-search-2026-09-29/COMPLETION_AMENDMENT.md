# Complete the original plan — user amendment, 2026-09-29

The user, after receiving the report of approximately eleven hours of GPU
contention and the missing comparisons, instructed:

> 実験を打ち切る必要はないので、もともと計画していた実験を完了できるまで進めてください

This supersedes the original thirteen-hour deadline, the assistant's two-hour
extension cap, and the resulting 07:00/08:30 UTC stopping schedule. There is now
no wall-clock cutoff. The workload is still the original finite experiment;
no extra recipe search is authorized. The frozen protocol and clock are retained
as historical evidence, with this amendment disclosed in the final report.

ComfyUI and other projects retain priority. Do not terminate, interrupt, unload,
or otherwise control them. Continue requiring sixty consecutive seconds without
competing GPU compute, counting memory residency as occupied. The exclusive
guard and live contention monitor remain active and stop only research processes.

## Recover the missing planned comparisons

The new completion instruction permits additional identical attempts for
verified external-GPU interruptions, including the already archived DX512,
Base main, and S128 main failures. Their old exhausted retry records are kept
unchanged as historical evidence; they no longer prohibit recovery under this
amendment. This is an operational recovery change, not a new scientific recipe.

Before every recovery, verify the old launcher and its GPU process group are
gone. Preserve the failed output directory, wrapper log, shared guard receipts,
priority event, and hashes in a newly numbered attempt archive. Never overwrite
or merge partial attempts. Do not choose among attempts based on answer quality.
Resume DX512 from the fully completed DX128 adapter and optimizer, never the
interrupted update-402 state. Repeat missing evaluation jobs with exactly their
original jobs, seeds, order, batch four, cap, and context.

Unexpected code/model errors still require investigation. This amendment does
not authorize repeatedly retrying arbitrary failures or changing scientific
settings to make a run succeed. Retain the original single identical transient
retry rule for failures not caused by verified external resource contention.

## Execution and scientific gate

The old `evaluate_available.py` was stopped while idle between completed X128
retention and not-yet-started X128 main. No active GPU job was interrupted for
the handoff. Six completed evaluation directories (Base/S128/X128 short and
retention) and all completed training stages are reused by receipt and hash.

Use `resume.py initial` for the restored full original initial pipeline. Its
operational runner now has no deadline timeout when `timing-policy.json` uses
`complete_original_plan`; the frozen campaign implementation, training and
generation drivers, inputs, and exclusive GPU guard remain unchanged.
Check `continuation.json` and actual processes first; never launch a duplicate.

After all seven arms finish, use the original seven-arm common-cap procedure
in `extend.py`, then the original blinded full-text review and `decide.py` gate.
Do not apply a gate while evidence is missing. Only then perform the originally
specified branch A (fresh training seed confirmation) or B (D6/DX6 comparison).
Retain all original branch criteria and generation-bound rules. The lack of a
deadline removes the old time-remaining prerequisite, not the scientific gate.

Finally run audits, write `REPORT.md`, save `campaign-complete.json`, release
the sleep inhibitor, and pause automation-2. No final result is implied by this
operational amendment. Primary success remains numerical correctness AND valid
reasoning; training loss, guessed numerical matches, and missing outputs are
not success or hypothesis-failure evidence.

Authoritative machine-readable policy: runtime `completion-policy.json` and
`timing-policy.json`. Backups and CPU validation:
`amendments/007-complete-original-plan/`.

## Launcher supervision repair, 2026-09-29 10:31 UTC

At the 10:29 UTC check, launcher PID 2563012 had exited with code 143 while its
S512 main GPU guard PID 2638015 continued running. This is consistent with
SIGTERM; the sender and exact time are not established. No matching contention
event was found. The interval without live priority monitoring is an operational
limitation to disclose; current GPU snapshots cannot prove continuous absence
of external work during that interval.

`adopt_guard.py` verified the original guard identity and restored the same
priority monitor around the live attempt, without restarting generation or
mixing answers. The guard and generation receipts subsequently completed, and
the new supervisor continued the original `resume.py initial` sequence. Consult
`continuation.json` for its actual PID and command before launching anything.
`resume.py` now routes SIGTERM and SIGHUP through its owned-process cleanup.
CPU-only signal tests verified child cleanup and the frozen manifest still
passes. Evidence, previous operational files, hashes, and validation are in
runtime `incidents/launcher-2563012-sigterm/`; `adoption.json` records the completed
attempt. No scientific setting, result selection, retry count, or scope changed.

## Initial generation completed, 2026-09-29 16:12 UTC

DX512 main identical attempt 3 completed with 12 outputs (11 natural stops and
one cap hit). All seven arms now have their original short168, retention4, and
main outputs. `initial-generation-validation.json` verifies all 1,324 outputs,
input/adapter/receipt hashes, job messages, seeds, and batch positions. Earlier
interrupted attempts remain separate and excluded. No primary scores yet.

The original unmodified `extend.py --execute` is now running via the `resume`
GPU-priority wrapper with shutdown handlers installed. Consult current
`continuation.json` and `extension-launch.json` for its process. Do not restart
`resume.py initial`. Main common12 extensions apply to all seven arms for
DA11-s1 and DB01-s1; replication extensions apply to Base/S128/X128 for H12-s2
and DB16-s2. Follow the original cap ladder and exact ordered subsets.

Before grading, an overbroad metadata display inadvertently exposed part of
one DX512 DA03 answer with its arm label. `review-exposure-note.json` records
this limitation. Do not claim perfect condition hiding for that answer or
independent review; still grade every complete condition-hidden packet before
opening mapping, and disclose the prior exposure in the final report. No
scientific setting, answer selection, or grading verdict was changed.

## Common-cap recovery, 2026-09-29 16:53 UTC

Base/S128/X128/S512 completed the original two-question common-cap subset at
81,920 tokens. X512 attempt 1 began at 16:42:52 UTC and was interrupted by
the priority monitor at 16:43:34 UTC after external GPU PID 3119927 appeared.
The PID was gone at inspection, so its application is unknown. No answers were
saved. Both owned process groups were confirmed absent, and all interrupted
files plus the guard, logs and priority event were archived with verified hashes
under `failed-attempts/eval-X512-2026093001-main-81920-common-attempt1`.
`retry-X512-main-81920-common.json` authorizes identical attempt 2 under the
completion policy. The same extension command has resumed, reusing the four
completed conditions; read `continuation.json` for its current process. This is
not an OOM or evidence against the learning hypothesis.

## User resume and parallel review, 2026-09-29 18:00 UTC

The user confirmed the 17:27 UTC pause was manual, then explicitly requested
resuming the original experiment and grading concurrently with subagents. The
user additionally instructed that newly appearing GPU processes should no
longer automatically stop research; the user will warn when competition needs
attention. This supersedes the earlier live interruption-on-appearance policy.
The operational policy is recorded in `gpu-priority-policy.json`; startup
admission and actual error handling remain in place. Unknown applications are
not silently labelled as image generation.

X512 common-cap attempt 2 was interrupted at 17:27 UTC after GPU PID 3190998
appeared. No answers were serialized; all files and the priority event were
archived with verified hashes in its attempt2 directory. Ptyxis activation
was logged two seconds earlier, but no contemporaneous PID-to-executable
snapshot was saved, so this is a candidate explanation, not a confirmed identity.

Parallel grading starts only on 100 original main outputs that are final under
the original common-cap rule: every job needing any extension is excluded across
its comparison. The frozen scorer builds 47 condition-hidden numeric-success
packets in `review-stable`; fresh-context AI subagents read every complete answer
using the unchanged rubric. This changes review staffing/timing, not the primary
metric, problem selection, output selection or branch criteria. Once all GPU
cap checks finish, canonical packets are created by `score.py --blind` and stable
grades are reused only by identical content hashes. All additional final packets
must be graded and the full grades file saved before condition mapping is opened
and the unchanged completeness gate is run. Do not claim independent human
review. The previously documented parent exposure of one labelled answer remains
a report limitation. See `parallel-review-policy.json` and review dispatch files.

### Resumption execution and monitor validation, 2026-09-29T18:07:12.871229+00:00

Operational amendment 008 passed 13 CPU tests, Python compilation, and frozen-manifest validation. The persisted live policy is `observe_only_user_notifies`: competitor appearance and monitor errors are recorded with process identity; detection alone sends no signal. Exact existing desktop executable classification was made dynamic. Startup shared exclusion and sixty continuous quiet seconds remain. No scientific settings changed. The user may notify this task of expected competition.

The identical X512 main/common 81920 third attempt started after the quiet period at 2026-09-29T18:06:23.638430+00:00, launcher PID 3260959/session 74697, owned guard PID 3264807. Completed Base/S128/X128/S512 receipts were reused. The sleep inhibitor and ten-minute continuation heartbeat were resumed under explicit user authorization. Stable condition-hidden grading is running concurrently; no condition mapping has been opened for that review.

### Stable-output parallel review completed, 2026-09-29T18:11:34.454899+00:00

The three fresh-context grading agents read all 47 condition-hidden numeric-success packets (912,107 characters) drawn from the 100 original main outputs unaffected by common-cap extension. A separate fresh-context AI reviewer read 14 borderline packets in full (289,234 characters), without prior grades or condition mapping. Five provisional verdicts/sensitivity flags were reconciled under the unchanged rubric, with the original readers agreeing before any condition unmasking. The parent additionally read case-046 in full and checked its uncorrected midpoint/center error using exact rational arithmetic; coincidentally correct final distance was not accepted as valid reasoning. Original shard grades and all audit passages remain preserved.

`review-stable/grades.json` now contains 47 complete grades, with 20 valid and 27 invalid in this pooled staging set. These are not condition comparisons, independent problem counts, or evidence of transfer. `grading-receipt.json` records hashes, full-text coverage, original-to-final adjudications, and limitations. No mapping was opened; no branch decision was made. The remaining cap-dependent answers will be reviewed only at the final prescribed common cap, after which stable grades will be bound by exact messages/full-text SHA256 to the canonical review.

### Finalized-group parallel grading, 2026-09-29T18:24:32.433901+00:00

The seven-arm common12 cap procedure completed with natural stops at 81,920 for the original ordered DA11-s1/DB01-s1 subset. While the original Base/S128/X128 second-sample extension continues, the operational helper `stage_review.py` verifies complete receipts, exact input/model/adapter hashes, full ordered subsets, pairing, duplicate rejection and the original shared-cap ladder before staging a group. Twenty-six CPU validation cases passed (`stage-review-validation.json`). This changes grading timing only; all original comparisons and the canonical completeness gate remain required. The common group contributes 14 final outputs and six condition-hidden numeric-success packets, dispatched to two fresh-context AI graders. Neither staging mappings nor canonical mappings have been opened.
