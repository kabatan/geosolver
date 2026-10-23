"""Static corpus/answer validation and duplicate audit. Never execute a solver."""
from __future__ import annotations

import ast
import difflib
import hashlib
import importlib.abc
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'benchmarks')]
sys.dont_write_bytecode = True


class NoSolverImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith(('geosolver.engine', 'geosolver.application', 'scipy', 'PyNomad')):
            raise RuntimeError(f'Solver/search import prohibited during authoring: {fullname}')


sys.meta_path.insert(0, NoSolverImports())
import research_runner as rr
from geosolver.exact import describe_exact
import sympy


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def canonical(x): return json.dumps(x, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
def load(path): return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]
def normid(cid): return re.sub(r'[^A-Z0-9]', '', cid.upper().replace('GEOMETRY','GEO'))


def normtext(text):
    text = re.sub(r'\[asy\].*?\[/asy\]', ' ', text, flags=re.S | re.I)
    text = text.replace('\\triangle', ' triangle ').replace('\\angle', ' angle ')
    text = text.replace('∠', ' angle ').replace('△', ' triangle ')
    return ' '.join(re.findall(r'[a-z]+|\d+', text.lower()))


def dslkey(dsl):
    names = {n:f'v{i}' for i,n in enumerate(dsl.get('variables',[]))}
    names |= {c['name']:f'p{i}' for i,c in enumerate(dsl.get('constructions',[]))}
    class Renamer(ast.NodeTransformer):
        def visit_Name(self, node): return ast.copy_location(ast.Name(id=names.get(node.id,node.id),ctx=node.ctx),node)
    def expr(v):
        try: return ast.dump(Renamer().visit(ast.parse(str(v), mode='eval')), include_attributes=False)
        except (SyntaxError, ValueError): return str(v)
    result = dict(nvars=len(dsl.get('variables',[])),
        constructions=[expr(c['expression']) for c in dsl.get('constructions',[])],
        conditions=sorted(canonical({k:expr(v) for k,v in c.items()}) for c in dsl.get('conditions',[])),
        target=expr(dsl.get('target','')))
    return hashlib.sha256(canonical(result).encode()).hexdigest()


def main():
    assert not (HERE/'prediction.lock.json').exists(), 'Prediction already locked'
    validation=rr.validate_corpus(HERE/'cases.jsonl')
    rows=load(HERE/'cases.jsonl')
    sources={r['id']:r for r in json.loads((HERE/'source-evidence/manifest.json').read_text())['records']}
    forbidden=[];refs=[];conversions=[]
    for r in rows:
        d=r['dsl']
        for e in [*(c['expression'] for c in d['constructions']),d['target'],
                  *(str(v) for c in d['conditions'] for v in c.values())]:
            if any(x in e for x in ['IsInteger','IsPrime','floor','//']): forbidden.append([r['id'],e])
        refs.append(dict(id=r['id'],reference=r['answer'],canonical_keys=sorted({
            rr._canonical_json(describe_exact(v).canonical_key())
            for answer in r['answer'] for v in rr.reference_expressions(answer)})))
        expression=sympy.sympify(r['answer'][0]); official=sources[r['id']]['official_output']
        if r['id']=='HMMT-2021-FEB-GUTS-14':
            assert sympy.simplify(expression-(sympy.sqrt(73)-3))==0
            converted=sympy.Integer(100*73+3); rule='sqrt(a)-b with a=73,b=3 -> 100*a+b'
        elif r['id']=='HMMT-2022-FEB-GUTS-11':
            converted=sympy.floor(120*expression);rule='floor(120*A), outside the DSL'
        else:
            converted=expression;rule='identity (official radians used for angles)'
        passed=sympy.simplify(converted-sympy.sympify(official))==0
        assert passed
        conversions.append(dict(id=r['id'],geometric_reference=str(expression),
            official_output=official,rule=rule,converted=str(converted),passed=bool(passed)))
    static=dict(validation=validation,forbidden_output_encoding=forbidden,
        geometric_references=refs, official_output_conversions=conversions, solver_executed=False,
        prohibited_solver_imports_enforced=True,
        imported_geosolver_modules=sorted(n for n in sys.modules if n.startswith('geosolver')))
    (HERE/'audit/static.json').write_text(json.dumps(static,ensure_ascii=False,indent=2)+'\n')
    assert validation['valid'] and not forbidden

    files=['benchmarks/cases.jsonl','jssa/difficulty/new2026/cases.jsonl',
           'jssa/difficulty/unseen-1983/cases.jsonl']
    supplements=load(ROOT/'jssa/difficulty/unseen-1983/statements.jsonl')
    statements={r['id']:r.get('problem_statement','') for r in supplements}
    statements['HMMT-2011-equilateral-hexagon']=statements.get('HMMT-2011-FEB-ALGGEO-12','')
    statements['HMMT-2011-two-circles-tangent-line']=statements.get('HMMT-2011-FEB-ALGGEO-20','')
    old=[];coverage=[]
    for f in files:
        group=load(ROOT/f)
        for r in group:
            old.append(dict(id=r['id'], corpus=f, dsl_key=dslkey(r.get('dsl') or {}),
                text=normtext(r.get('problem_statement') or statements.get(r['id'],''))))
        coverage.append(dict(path=f,sha256=sha(ROOT/f),count=len(group),
            native_statements=sum(bool(r.get('problem_statement')) for r in group),
            with_supplementary_statements=sum(bool(r.get('problem_statement') or statements.get(r['id'])) for r in group)))
    legacy=json.loads((ROOT/'jssa/difficulty/unseen-1983/manifest.json').read_text())
    prior=[r for r in legacy['rows'] if r.get('reason_code')=='prior_authored_input']
    for r in prior:
        old.append(dict(id=r['id'],corpus='prior_authored_input ledger',dsl_key='',text=normtext(statements.get(r['id'],''))))
    overlaps=[];matches=[]
    for r in rows:
        text=normtext(r['problem_statement']);key=dslkey(r['dsl'])
        closest=[]
        for o in old:
            reasons=[]
            if normid(r['id'])==normid(o['id']): reasons.append('normalized_id')
            if key==o['dsl_key']: reasons.append('alpha_ast_dsl')
            if text and text==o['text']: reasons.append('normalized_statement')
            if reasons: overlaps.append(dict(id=r['id'],other=o['id'],methods=reasons))
            if o['text']:
                score=difflib.SequenceMatcher(None,text,o['text'],autojunk=False).ratio()
                closest.append(dict(id=o['id'],corpus=o['corpus'],similarity=round(score,6)))
        matches.append(dict(id=r['id'],closest=sorted(closest,key=lambda x:-x['similarity'])[:3]))
    for i,r in enumerate(rows):
        for s in rows[i+1:]:
            if normid(r['id'])==normid(s['id']) or dslkey(r['dsl'])==dslkey(s['dsl']) or normtext(r['problem_statement'])==normtext(s['problem_statement']):
                overlaps.append(dict(id=r['id'],other=s['id'],methods=['internal']))
    dedupe=dict(passed=not overlaps,coverage=coverage,
        supplemental_source=dict(path='jssa/difficulty/unseen-1983/statements.jsonl',sha256=sha(ROOT/'jssa/difficulty/unseen-1983/statements.jsonl')),
        prior_authored_exclusions=[r['id'] for r in prior],overlaps=overlaps,closest_statements=matches,
        methods=['normalized ID','alpha-renamed DSL AST; condition order ignored','normalized statement','top-three text similarities for manual reading'],
        limitations='Missing native statements supplemented only when a saved statement exists under the same ID. New2026 has no statements in this checkout. Similarity is a review aid, not a proof of mathematical nonequivalence. IDs and DSLs cover all 323+20+54 records.',
        solver_executed=False)
    (HERE/'audit/duplicates.json').write_text(json.dumps(dedupe,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(static_valid=validation['valid'],reference_count=len(refs),
        duplicate_overlaps=overlaps,coverage=coverage,solver_executed=False),ensure_ascii=False))
    assert not overlaps


if __name__=='__main__':main()
