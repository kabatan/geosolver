# Prior-overlap card

## Decision

This is a new mechanism implementation, not a rerun of an implemented arm.

- Archived candidate 04 (`ca47b12d...d1df8a`) and candidate 05
  (`4f5c267c...c4bdf`) are literature proposals. Neither contains an
  implementation or generated evidence.
- The existing certified-polynomial lane (`93c8d8bb...74edd7`) first isolates
  and Krawczyk-certifies every coordinate box, then hands a target interval to
  elimination. This D0 instead proves existential target feasibility directly
  from the finite quotient algebra and strict Tarski queries. No coordinate is
  reconstructed or exactified.
- The exact target exporter (`b44ef826...b55f2`) is a possible upstream
  frontend only. It is not copied here, and its output is not authority.

## Reopen gate satisfied

The prior cards asked for a minimum Hermite prototype and warned about missing
roots, nonradical ideals, positive-dimensional ideals, and unencoded semantic
inequalities. D0 closes those prototype gaps as follows:

- the exact Groebner quotient is used, so there is no incomplete approximate
  root list;
- a nonradical family activates with a singular Hermite form;
- an overall positive-dimensional system activates when the proposed target
  constraint makes its fibre zero-dimensional, while a positive-dimensional
  target fibre is rejected;
- strict guards and both open interval inequalities are counted by exact
  Tarski queries;
- an independent verifier checks the regular representation, generator
  identities, Hermite matrices, inertia, and conjunction count without
  recomputing the Groebner basis.

This is only a D0 reopen. It does not claim source-corpus recall or production
integration.
