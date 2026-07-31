# Root-owned canonical prejoin gate

Build a private JSON object with exactly five rows under `requests`. Each row
has only `source`, `source_sha256`, `endpoint`, and `endpoint_sha256`. The rows
must be the anonymous qreflect/sector sources covered by aggregate SHA prefix
`0fe92cf7`; no case/family label, target, truth, descriptor, prior outcome, or
expected count may enter the manifest.

Run `root_prejoin_gate.py` pinned to CPU14. The script acquires the supplied
global lock itself, verifies five distinct source hashes, runs the frozen
single-refinement union once per row, and applies the frozen exact authority
boundary. Raw terminals remain process-private. Only `AGGREGATE.json` may be
returned to candidate agents.

GO requires all of:

- `request_count=5` and `anonymous_source_count=5`;
- `canonical_ready_source_count=5`;
- at least one ledger-proven qreflect exact dispatch activation;
- at least one raw-replay-ledger-proven sector-angle activation, followed by
  a canonical-ready final terminal;
- `guarded_process_failure_count=0`;
- `truth_used=false` and `target_set_completeness_claim=false`;
- no per-row output.

STOP without tuning on any failure. This is a canonical prejoin, not a formal
score. Saved-endpoint timing/parity and recurring-loss gates remain separate,
root-owned prerequisites to formal execution.
