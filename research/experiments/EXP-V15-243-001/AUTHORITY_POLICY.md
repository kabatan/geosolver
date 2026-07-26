# v15-243 exact success authority (frozen 2026-07-18)

## Operational success contract

The formal score uses **proof-bearing emitted targets**. A case succeeds only
when, within the 180-second fresh-process budget:

1. every emitted target has an exact source/guard/branch/raw-target link;
2. its normalized exact descriptor is a square-free minimal polynomial plus an
   independently attested zero-based real-root ordinal;
3. the offline scorer finds the complete emitted descriptor set identical to
   the frozen truth set; and
4. there is no missing, extra, duplicate, invalid, wrong-branch, timeout,
   crash, or unfinalized result.

Offline truth is scoring-only. It is unavailable to search, scheduling,
exactification, routing, and finalization. Runtime mathematical proof of
global completeness is not required; completeness is measured by the frozen
offline set comparison. Every value that *is* emitted must nevertheless have
proof-bearing source authority.

## Admitted proof routes

- Exact evaluation of a fully supported zero-declared-variable source AST.
- Exact-coordinate replay: independently refined coordinates are recognized
  exactly and all original equations, guards, branches, definedness, and the
  raw target link replay in the exact domain.
- A certified unique regular source root (for example interval/Krawczyk) plus
  an exact source-to-target link under a mechanically supported compiler.

Small residual, agreement at fixed numerical precisions, target-only PSLQ or
`algdep`, and approximate guard replay are proposal evidence only. Unsupported,
timed-out, singular-without-proof, or partially recognized attempts emit no
target.

## Historical score label

The previously reported `champion_v1 = 131/145` is frozen as the
**historical empirical target-set score under the old target-only terminal**.
It is not a proof-bearing exact score and is not a development promotion gate.
Its endpoints and telemetry may be used as truth-blind proposal evidence.

## Promotion gate

All future solved counts must name the authority used. Validation and sealed
sets remain closed until the development set reaches `138/145` with this
proof-bearing authority and zero final extra/false targets.

