"""Q18: JSON/AST/name contracts and literal templates only. No DSL evaluation."""
from __future__ import annotations

import ast
from collections import Counter
import hashlib
import itertools
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
ROOT = BASE.parents[2]
sys.path.insert(0, str(ROOT/'src'))
from geosolver.problem.models import GeometryProblem
from geosolver.problem.validation import _expression_issues

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def read_rows(p):
    return [json.loads(s) for s in p.read_text().splitlines() if s.strip()]

def tree(s):
    return ast.dump(ast.parse(str(s), mode='eval'), include_attributes=False)

def eq(a,b):
    return tree(a) == tree(b)

def read_dsl(cid):
    return json.loads((BASE/'dsl'/f'{cid}.json').read_text())

def condition_signature(c):
    if 'predicate' in c:
        return ('predicate',tree(c['predicate']))
    return (c['operator'],tree(c['left']),tree(c['right']))

def cross(a,b,c):
    return f'(({b}.x-{a}.x)*({c}.y-{a}.y)-({b}.y-{a}.y)*({c}.x-{a}.x))'

def check_templates():
    checks=[]
    d=read_dsl('AIME-1991-02')
    assert len(d['constructions']) == 672
    assert d['variables'] == d['conditions'] == []
    expected=[]
    for k in range(1,168):
        for name,a,b in [('P','A','B'),('Q','C','B'),('U','A','D'),('V','C','D')]:
            expected.append((f'{name}{k}',f'PointOnSegment({a},{b},{k}/168)'))
    assert [(c['name'],tree(c['expression'])) for c in d['constructions'][4:]] == [(n,tree(e)) for n,e in expected]
    terms=['Distance(A,C)']
    for k in range(1,168):
        terms += [f'Distance(P{k},Q{k})',f'Distance(U{k},V{k})']
    assert eq(d['target'],'+'.join(terms))
    checks.append(dict(id=d['id'],check='全668等分点のASTと全335距離項の添字・順序',passed=True))

    d=read_dsl('AIME-1993-02')
    assert len(d['constructions']) == 41
    for k,c in enumerate(d['constructions'][1:],1):
        dx = f'{k}**2/2' if k%4==1 else f'-{k}**2/2' if k%4==3 else '0'
        dy = f'{k}**2/2' if k%4==2 else f'-{k}**2/2' if k%4==0 else '0'
        assert c['name']==f'P{k}' and eq(c['expression'],f'Point(P{k-1}.x+({dx}),P{k-1}.y+({dy}))')
    assert eq(d['target'],'Distance(P0,P40)')
    checks.append(dict(id=d['id'],check='全40移動のAST・方向周期・負の累乗の構文',passed=True))

    d=read_dsl('AIME-1999-02')
    root=ast.parse(d['conditions'][7]['predicate'],mode='eval').body
    assert isinstance(root,ast.BoolOp) and isinstance(root.op,ast.Or) and len(root.values)==8
    left=['X','V1','V2','Y']; right=['Y','V3','V0','X']
    branches=[]
    for order in [right,list(reversed(right))]:
        for shift in range(4):
            perm=order[shift:]+order[:shift]
            branch=' and '.join(f'Distance({left[i]},{left[j]}) == Distance({perm[i]},{perm[j]})' for i,j in itertools.combinations(range(4),2))
            branches.append(ast.dump(ast.parse(branch,mode='eval').body,include_attributes=False))
    assert Counter(branches)==Counter(ast.dump(n,include_attributes=False) for n in root.values)
    checks.append(dict(id=d['id'],check='合同四角形の8巡回/反転枝と各6距離等式の全数AST',passed=True))

    d=read_dsl('HMMT-2016-FEB-GEO-01')
    vertices=list('QWARTZSPHINX')
    assert len(vertices)==12 and [c['name'] for c in d['constructions']]==vertices
    expected=[]
    for i in range(12):
        a,b,c=vertices[i-1],vertices[i],vertices[(i+1)%12]
        expected.append(dict(left=f'Perpendicular(Line({a},{b}),Line({b},{c}))',operator='=',right=0))
        if i != 0:
            expected.append(dict(left=f'Distance({b},{c})',operator='=',right=2))
    # The source omits QW, already fixed to 2. Above i=0 is QW.
    for i,j in itertools.combinations(range(12),2):
        if j==i+1 or (i,j)==(0,11):
            continue
        a,b=vertices[i],vertices[(i+1)%12]
        c,e=vertices[j],vertices[(j+1)%12]
        pred=' or '.join([f'(max({a}.x,{b}.x)<min({c}.x,{e}.x))',f'(max({c}.x,{e}.x)<min({a}.x,{b}.x))',f'(max({a}.y,{b}.y)<min({c}.y,{e}.y))',f'(max({c}.y,{e}.y)<min({a}.y,{b}.y))'])
        expected.append(dict(predicate=pred))
    assert len(expected)==77
    assert Counter(map(condition_signature,d['conditions']))==Counter(map(condition_signature,expected))
    assert eq(d['target'],'Area(S,I,X)')
    checks.append(dict(id=d['id'],check='12直角・11未固定辺長・非隣接全54辺組の分離AST',passed=True))

    for cid,vertices in [('AIME-1991-14','ABCDEF'),('HMMT-2015-FEB-GUTS-02','ABCDE'),('HMMT-2017-FEB-GUTS-06','ABCD'),('HMMT-2023-FEB-GEO-06','ABCD')]:
        d=read_dsl(cid)
        expected=[]
        for i,a in enumerate(vertices):
            b=vertices[(i+1)%len(vertices)]
            for c in vertices:
                if c not in (a,b):
                    expected.append(condition_signature(dict(left=cross(a,b,c),operator='>',right=0)))
        actual=Counter(map(condition_signature,d['conditions']))
        assert all(actual[s]==1 for s in expected)
        checks.append(dict(id=cid,check=f'凸性の全{len(expected)}外積不等式の頂点/辺対応AST',passed=True))

    d=read_dsl('HMMT-2022-FEB-GEO-07')
    sides=['Distance(O1,O2)','Distance(O2,O3)','Distance(O3,O4)','Distance(O4,O1)']
    expression='max(['+', '.join(f'min({a},{b})' for a,b in itertools.combinations(sides,2))+'])**2'
    assert eq(d['conditions'][6]['left'],expression)
    checks.append(dict(id=d['id'],check='第2最大の全6ペアmin/max式のAST',passed=True))

    d=read_dsl('HMMT-2016-FEB-GUTS-03')
    for i,name in enumerate('PROBLEMZ'):
        c=d['constructions'][i]
        assert c['name']==name and eq(c['expression'],f'Point(cos({i}*pi/4),sin({i}*pi/4))')
    checks.append(dict(id=d['id'],check='正八角形全8頂点の順序/中心角AST',passed=True))
    return checks

def main():
    cases=read_rows(BASE/'cases.jsonl')
    manifest=json.loads((BASE/'manifest.json').read_text())
    selected={r['id']:r for r in manifest['rows'] if r['status']=='selected_candidate'}
    reviews=read_rows(HERE/'reviews.jsonl')
    assert len(cases)==len(reviews)==len({r['id'] for r in reviews})==54
    assert {r['id'] for r in reviews}==set(selected)=={c['id'] for c in cases}
    errors=[]; count=0; per_case=[]
    for c in cases:
        cid=c['id']; d=read_dsl(cid); GeometryProblem.model_validate(d)
        assert d==c['dsl']
        assert sha(BASE/'dsl'/f'{cid}.json')==selected[cid]['input_sha256']
        scope=set(d['variables']); assert len(scope)==len(d['variables'])
        expressions=[]
        for i,item in enumerate(d['constructions']):
            name=item['name']; assert name not in scope
            path=f'constructions[{i}].expression'
            issues,t=_expression_issues(path,item['expression'],scope)
            assert isinstance(t,ast.Expression)
            errors.extend(dict(id=cid,path=path,issue=x.model_dump()) for x in issues)
            scope.add(name); count+=1
        for i,item in enumerate(d['conditions']):
            for key in ('predicate',) if 'predicate' in item else ('left','right'):
                expressions.append((f'conditions[{i}].{key}',str(item[key])))
        expressions.append(('target',d['target']))
        for path,s in expressions:
            issues,t=_expression_issues(path,s,scope)
            assert isinstance(t,ast.Expression)
            errors.extend(dict(id=cid,path=path,issue=x.model_dump()) for x in issues)
            count+=1
        per_case.append(dict(id=cid,expressions=len(d['constructions'])+len(expressions),input_sha256=sha(BASE/'dsl'/f'{cid}.json'),ast_ok=not any(e['id']==cid for e in errors)))
    templates=check_templates()
    snapshot=json.loads((HERE/'input-snapshot.json').read_text())
    assert not any(name.startswith('sealed/') for name in snapshot), 'sealed outputs must not be inspected'
    changed=[name for name,h in snapshot.items() if sha(BASE/name)!=h]
    assert not changed, changed
    forbidden=[m for m in sys.modules if m.startswith(('geosolver.engine','geosolver.geometry','scipy','numpy','sympy'))]
    assert not forbidden, forbidden
    report=dict(passed=not errors,case_count=54,ast_expressions=count,errors=errors,per_case=per_case,
                template_checks=templates,original_files_checked=len(snapshot),original_files_changed=changed,
                forbidden_modules_imported=forbidden,solver_run=False,local_search_run=False,
                numerical_geometry_generation=False,dsl_evaluation=False,solver_results_seen=False,
                scope='JSONモデル、DSL式のAST/関数/引数/名前、手作業監査を補助する反復ASTテンプレート、入力hash。実行可能性や全解を計算しない。')
    (HERE/'static-checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('per_case','template_checks')},ensure_ascii=False))
    if errors:
        raise SystemExit(1)

if __name__=='__main__':
    main()
