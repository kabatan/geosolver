# ADR-0002: Open-world graph and plugin ABI

Status: Accepted  
Date: 2026-07-10

## Decision

The stable graph has only Literal, Reference, plugin-qualified Call and Select
nodes. Calls are typed through immutable PluginSpec/PluginLock records. Built-in
geometry is an ordinary plugin and GeoTargetCore does not import it.

Multi-valued calls return Choice values with stable keys and validity margins.
Relations, guards, domains, branches and targets retain separate semantics.
Plugin capabilities are explicit and precision/validation loss is never silent.
Relation truth predicates are required by default. A relation whose exact
predicate is intentionally false at nonzero numerical approximations (for
example, an `iszero` predicate paired with a smooth equality residual) must
declare `RELATION_TRUTH_APPROXIMATE_ZERO`; this opt-in never excuses a false
predicate at an exactly zero residual.

## Consequences

Custom objects, loops, control flow and transcendental functions are legal
inside calls. Compiler optimizations cannot assume polynomial structure.
Registration metadata will generate protocol symbols, Python bindings, docs and
capability reports from one source.
