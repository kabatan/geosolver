# Repair A thin real connection

Decision: `HOLD_CONNECTION_NO_TYPED_REDUNDANT_HANDOFF`.

The exact common control was audited at entrypoint SHA-256
`e1405739201b0cb1d72e8f9ab6ca402b5e71918e569888993c4fdd13022c7301`.
Its champion-v0 reservoir delays every target until HP authority. Every
unstarted primary, failed-cluster alternate, and restoration attempt may
therefore produce a novel canonical descriptor. None is typed as a
descriptor-only reconfirmation.

A successful primary causes its same-cluster alternate to be skipped, but
that skipped alternate is not charged control work and may still contain a
different exact target. It cannot serve as Repair A's dominance-safe borrowed
handoff. Replacing any charged primary/alternate/restoration can lose control
output. Running only 75% of the common control before side work changes the
formal baseline. Running the full control and using leftover union is safe but
is the already-tested v4 mechanism, whose generated real side attempt had
novel descriptor activation zero.

No monkey patch can simultaneously establish the required typed redundancy,
immutable formal baseline, equal charged work, and
`control_union <= candidate_union`. The adapter and source smokes are therefore
stopped before code rather than weakening the Repair A contract.

Reopen only if an independently motivated runtime exposes both an independent
authority-block identifier and an unstarted work item whose public contract is
`can_generate_novel_descriptor = false`, or if a new snapshot-first
post-control mechanism is authorized as a lineage distinct from Repair A.
Threshold, route order, timeout, or baseline-fraction changes do not reopen
this connection.

No truth, scorer, case outcome, development score, validation, sealed, or
holdout input was read or executed.
