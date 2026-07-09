# ADR-0001: Clean-slate repository and language boundary

Status: Accepted  
Date: 2026-07-10

## Decision

`C:\solver` is an independent repository with a clean history and no initial
remote. The old repository, its history and working state are not imported,
used as a dependency, or used as an answer fallback. If it remains runnable
without repair, it may be measured once as a read-only secondary baseline; all
legacy observations must be reproduced independently before promotion.

The numerical core is Julia 1.12.6. Python is a first-class builder and CLI
client but does not duplicate numerical semantics or execute callbacks in the
hot loop. JSON is the canonical interchange protocol. Production custom
primitives are Julia plugins.

## Consequences

There is no compatibility layer for the former API/IR. The project must create
neutral benchmarks and independent truth data. A remote, public license or
publication requires explicit owner approval.

