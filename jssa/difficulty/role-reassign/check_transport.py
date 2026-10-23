"""Two artificial CLI solves to verify the unchanged public pipeline/embedded audit."""
from common import *
from types import SimpleNamespace
import ast
import hashlib
import os
import tempfile
from benchmarks import research_runner as research
from transport import execute
from geosolver.exact import describe_exact

old = (HERE/"interrupted-attempt-2/implementation/role_patch.py").read_text()
new = (HERE/"hook/role_patch.py").read_text()
def nodes(text):
    return {n.name:ast.dump(n,include_attributes=False) for n in ast.walk(ast.parse(text))
            if isinstance(n,ast.FunctionDef)}
a,b = nodes(old),nodes(new)
names=("plans_for","bundle_plans","rewrite_float","hard","vector","smooth","search")
assert all(a[n]==b[n] for n in names)
dump(HERE/"numerical-code-identity.json",dict(utc=now(),all_equal=True,
    functions={n:hashlib.sha256(a[n].encode()).hexdigest() for n in names},
    compared_to="interrupted-attempt-2/implementation/role_patch.py"))
doc=dict(id="Q13-transport-artificial",variables=[],
         constructions=[dict(name="A",expression="Point(0,0)"),dict(name="B",expression="Point(3,0)")],
         conditions=[],target="Distance(A,B)")
dsl_path=HERE/"transport-smoke/input.json"
dump(dsl_path,doc)
record=SimpleNamespace(identifier=doc["id"],dsl_path=dsl_path,dsl=doc)
for mode in ("B","R"):
    directory=HERE/"transport-smoke"/mode
    directory.mkdir(parents=True,exist_ok=True)
    os.environ.update(research.THREAD_ENVIRONMENT)
    os.environ.update(ROLE_CONDITION=mode,ROLE_AUDIT_PATH=str(directory/"audit.jsonl"),
        PYTHONPATH=os.pathsep.join([str(HERE/"hook"),str(ROOT/"src"),str(ROOT)]),
        PYTHONDONTWRITEBYTECODE="1",TMPDIR=str(directory),TMP=str(directory),TEMP=str(directory))
    tempfile.tempdir=str(directory)
    raw=execute(record,research._independent_cpus()[0])
    dump(directory/"result.json",raw)
    audit=audit_summary(directory/"audit.jsonl",raw)
    assert not raw["execution_contract_issues"] and raw["solver_result"]["status"]=="solved"
    assert audit["source"]=="embedded_worker_artifact" and audit["verified"] and audit["condition"]==mode
    assert research._answer_keys(raw["solver_result"]) == [research._canonical_json(describe_exact("3").canonical_key())]
    print(json.dumps(dict(mode=mode,passed=True,audit=audit)))
dump(HERE/"transport-smoke/checks.json",dict(utc=now(),passed=True,artificial_solves=2,
                                          optimizer_calls=0,numerical_ast_unchanged=True))
