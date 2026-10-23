"""Input-only census and pre-execution hash lock. Never calls an optimizer."""
from common import *
import os
import platform
from benchmarks import research_runner as research
from geosolver import GeometryProblem
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from role_patch import bundle_plans

if (HERE / "execution-lock.json").exists():
    raise SystemExit("already frozen")
cases = sorted(research._load_cases(), key=lambda c: c.identifier)
raw_ids = {p.stem for p in (ROOT / "jssa/difficulty/minima/raw-323").glob("*.json")}
assert len(cases) == 323 and {c.identifier for c in cases} == raw_ids
manifest = []
for i, c in enumerate(cases):
    assert c.runnable and c.truth_status == "verified"
    assert read(c.dsl_path) == c.dsl
    b = load_problem_bundle(GeometryProblem.model_validate(c.dsl).engine_document())
    plans = bundle_plans(b)
    manifest.append(dict(id=c.identifier, ordinal=i, path=str(c.dsl_path.relative_to(ROOT)),
                         dsl_sha256=sha(c.dsl_path), n_vars=len(b.var_names),
                         signed_applicable=bool(plans),
                         signed_plans={str(k): v for k, v in plans.items()},
                         guard_count=len(b.spec.guards), hard_count=len(b.hard_feasibility_checks),
                         first="B" if i % 2 == 0 else "R"))
dump(HERE / "manifest.json", manifest)
runtime = research.runtime_fingerprint()
assert not runtime["issues"]
files = [HERE / "preregistration.md", HERE / "manifest.json", ROOT / "benchmarks/cases.jsonl",
         ROOT / "benchmarks/research_runner.py", *HERE.glob("*.py"), *HERE.glob("hook/*.py"),
         *(c.dsl_path for c in cases)]
dump(HERE / "execution-lock.json", dict(
    utc=now(), python=sys.executable, platform=platform.platform(), runtime=runtime,
    files={str(p.relative_to(ROOT)): sha(p) for p in sorted(set(files))},
    cpus=research._independent_cpus()[:8], loadavg=os.getloadavg(),
    n_cases=len(cases), planned_runs=646, max_simultaneous_solves=8,
    actual_optimizer_calls_so_far=0,
))
print(json.dumps(dict(cases=len(cases), signed_cases=sum(r["signed_applicable"] for r in manifest),
                      zero_variable_cases=sum(r["n_vars"] == 0 for r in manifest),
                      runtime=runtime["source_hash"], prereg_sha256=sha(HERE / "preregistration.md"))))
