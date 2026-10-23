"""Static comparison only; no development solver reruns and no repair attribution."""
from common import *
import ast
import collections
import csv
import statistics

def features(dsl):
    conditions = dsl['conditions']
    sources = [c['expression'] for c in dsl['constructions']]+[dsl['target']]
    for c in conditions:
        sources.extend(str(c[k]) for k in ('left','right','expression','predicate') if k in c)
    calls = collections.Counter(n.func.id for s in sources for n in ast.walk(ast.parse(s,mode='eval'))
                               if isinstance(n,ast.Call) and isinstance(n.func,ast.Name))
    return dict(id=dsl['id'], variables=len(dsl['variables']), constructions=len(dsl['constructions']),
        point_constructions=sum(ast.parse(c['expression'],mode='eval').body.__class__ is ast.Call
            and isinstance(ast.parse(c['expression'],mode='eval').body.func,ast.Name)
            and ast.parse(c['expression'],mode='eval').body.func.id=='Point' for c in dsl['constructions']),
        conditions=len(conditions), equalities=sum(c.get('operator')=='=' for c in conditions),
        inequalities=sum(c.get('operator') in ('>','>=','<','<=','!=') for c in conditions),
        predicates=sum('expression' in c or 'predicate' in c for c in conditions),
        integer_calls=calls['IsInteger'], angle_calls=calls['Angle'], oncircle_calls=calls['OnCircle'],
        sqrt_calls=calls['sqrt'], calls=dict(calls))

def main():
    dev = [json.loads(l) for l in (ROOT/'benchmarks/cases.jsonl').read_text().splitlines()]
    assert len(dev)==323
    for r in dev:
        assert r['dsl']==json.loads((ROOT/'benchmarks'/r['dsl_path']).read_text())
    rows = [dict(group='development',**features(r['dsl'])) for r in dev]
    rows += [dict(group='Q29a',**features(problem(cid).model_dump())) for cid in IDS]
    keys = [k for k in rows[0] if k!='calls']
    with (HERE/'structure.csv').open('w',newline='') as f:
        writer = csv.DictWriter(f,fieldnames=keys)
        writer.writeheader()
        writer.writerows({k:r[k] for k in keys} for r in rows)
    dr = rows[:323]
    fields = ['variables','constructions','conditions','equalities','inequalities','predicates','integer_calls','angle_calls']
    summary = dict(development_n=323, development_cases_sha256=sha(ROOT/'benchmarks/cases.jsonl'),
        development_summary={k:dict(min=min(r[k] for r in dr),median=statistics.median(r[k] for r in dr),
            max=max(r[k] for r in dr),mean=statistics.mean(r[k] for r in dr),
            nonzero=sum(r[k]>0 for r in dr)) for k in fields},
        Q29a=[{**r,'development_count_greater_or_equal':{k:sum(d[k]>=r[k] for d in dr) for k in fields}}
              for r in rows[323:]],
        development_integer_cases=[r for r in dr if r['integer_calls']],
        limitation='Static features only; number of eliminated coordinates is not inferable from DSL alone; repair history is outside Q29a.')
    save(HERE/'structure-summary.json',summary)
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
