# PROPER_MORSE_POLAR_TARGET_IMAGE_CERTIFICATE_V1

- Status: `D0_PASS; HOLD_REAL_TYPED_LOWERABILITY_ZERO`.
- Hypothesis: a positive-dimensional source can still have a finite exact target
  image.  It is sound to enumerate proper-Morse critical target values only
  after proving `dT=0` on every smooth stratum and recursively covering the
  singular locus.  Merely finding finitely many critical values is unsound.
- Mechanism: verify an exact source-ideal intersection decomposition into the
  supported radical/equidimensional scope; encode each strict guard by
  `g*s^2-1` and each disequality by `h*u-1`; localize at every nonzero maximal
  Jacobian minor; reduce all target-augmented minors to zero; require a fixed
  source-independent proper rational-quadratic polar ideal to be zero
  dimensional; solve its real points exactly; recurse over a zero-dimensional
  singular locus; emit the union of square-free minpoly/ordinal/isolator
  descriptors.  Positive-dimensional singular recursion and undecided reality
  fail closed.
- D0 result: 13/13.  Exact images were recovered for plural lines `{-1,1}`,
  circle plus isolated point `{0,1}`, strict-positive chart `{7}`, disequality
  chart `{3}`, and a nodal curve with a zero-dimensional singular recursion
  `{0}`.  Component order was invariant.  Nonradical, nonpolynomial,
  incomplete strict/disequality chart and incomplete component cover inputs
  rejected.
- Mandatory adversary: the circle `x^2+y^2=1` with target `x` rejected as
  `TARGET_DIFFERENTIAL_NONZERO_ON_SMOOTH_STRATUM`, even though every proper
  Morse function has finitely many critical values there.  This is the central
  completeness guard, not a generated convenience case.
- Boundaries: proposal/certificate only; authority/release false; unchanged
  canonical source/guard/branch/raw-target replay remains mandatory.  No truth,
  outcome, case/family routing, real source, HP or formal benchmark was used.
- Real HOLD: Root's fixed anonymous85 has independently confirmed typed
  polynomial lowerability 0, so no source-bound proper-Morse panel exists.
  Reopen only when the unchanged current compiler yields at least 4 sources in
  2 structural signatures for which radical/equidimensional decomposition,
  finite compatible stratification and zero-dimensional critical ideals all
  verify.  Do not build a new compiler or tune generated polynomial examples.
- Candidate SHA-256:
  `fe5c7495c080a95d0743618a74dc3a0be2f48ac1283fa3ddd79e8cf48bbaddbb`.
