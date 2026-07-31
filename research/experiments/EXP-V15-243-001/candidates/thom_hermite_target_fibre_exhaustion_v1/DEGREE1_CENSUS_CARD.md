# Degree-one raw-panel census wrapper

- Purpose: convert the frozen anonymous degree-one request panel into the
  already-frozen aggregate-only `static_census.py` feature contract.
- Mechanism: call the existing exact QQ source compiler; compile the raw answer
  with that compiler's semantic AST without adding auxiliaries; prove the
  degree-one relation by exact ideal reduction; require a finite lexicographic
  quotient and a complete ordered-predicate ledger.
- Blind boundary: `source_path`, endpoint, proposal coefficients, rational
  target value, source hash, polynomials, and per-record disposition never
  cross the process boundary. Output is counts and eligible signature count
  only. Unknown request fields and outcome/truth fields fail closed.
- Fixed caps: inherited verbatim from `static_census.py`; three seconds per raw
  record; no parameter tuning from panel results.
- Authority: false. Release: false. This is applicability evidence only.
- Frozen dependencies:
  - `source_compile.py`: `24d6cee020256043f6ad4657ffa84a8b4e9188ab9ff18bf3e9339672a3229349`
  - semantic `compiler.py`: `f127f7f1e2f93161e1353f07222e93ffacfa1c2dbd4e68e5b1fd23a8a3b10318`
- Execution: Root benchmark owner runs it later on exclusively pinned CPU14.
