# Root-owned applicability gate

The benchmark owner builds request rows privately from already frozen
development exact-outer artifacts. Candidate agents do not receive rows.

For each row the owner authenticates the original source/PLAN/RESULT and exact
fallback child, recomputes endpoint bits and id-stripped source bytes, and
constructs the existing source-bound refinement bridge from the same endpoint.
Rows retain only endpoint attempts whose current exact-outer child ran cleanly
to a non-authoritative rejection. Timeout, insufficient allocation,
lock/memory deferral, malformed output, and already-authoritative attempts are
excluded without replacement.

Selection is source-only and deterministic: sort eligible source/endpoint/atom
tuples by SHA-256 of their anonymous structural projection and endpoint bits,
cap at 12 requests, and execute each once. No target, descriptor, prior solve
outcome, case/family, or known count participates. Each request has a 30-second
hard wall, one native thread, CPU14 root custody, 500 MiB aggregate RSS, 1 GiB
address/data, 4 MiB output, no retry, and fresh atomic output.

Return only aggregate counts for source eligibility, clean exact-outer
rejection, bridge join, independent lanes, non-turn exact-coordinate readiness,
terminal activation, verified private hold, replay rejection, resource failure,
fallback identity, and activated anonymous structural signatures. Do not emit
sources, paths, endpoint vectors, atom bindings, descriptors, target values, or
individual reasons. Truth/scorer/validation/sealed data are not opened.
