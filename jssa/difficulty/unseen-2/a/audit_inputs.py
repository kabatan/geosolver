"""Static validation + independent fixed-coordinate substitution. NO SEARCH.

The evaluator below is independent of GeoSolver's numerical geometry evaluator.
Only GeometryProblem and the AST catalog validator are imported from its problem
layer; the exact descriptor scorer parses known reference expressions only.
"""
from __future__ import annotations
import ast
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import mpmath as mp

from geosolver.problem.models import GeometryProblem
from geosolver.problem.validation import _expression_issues
from collect_sources import answer_key, problem, validate
from hand_witnesses import witnesses
import score

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
LIMIT=5_000_000
mp.mp.dps=90
TOL=mp.mpf('1e-70')


def sha(data): return hashlib.sha256(data).hexdigest()
def read_rows(p): return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
def write_json(p,value):
    data=(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()
    assert len(data)<LIMIT
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_bytes(data)
def fmt(x): return mp.nstr(x,75)


@dataclass
class Pt:
    x: object
    y: object

@dataclass
class Ln:
    a: Pt
    b: Pt

@dataclass
class Circ:
    center: Pt
    radius: object


def sub(a,b): return Pt(a.x-b.x,a.y-b.y)
def dot(a,b): return a.x*b.x+a.y*b.y
def cross(a,b): return a.x*b.y-a.y*b.x
def dist(a,b):
    if isinstance(b,Ln):
        direction=sub(b.b,b.a)
        assert dot(direction,direction)>0
        return abs(cross(direction,sub(a,b.a)))/mp.sqrt(dot(direction,direction))
    v=sub(a,b)
    return mp.sqrt(dot(v,v))
def line(a,b):
    assert dist(a,b)>TOL
    return Ln(a,b)
def circle(o,r):
    assert r>0
    return Circ(o,r)
def area(*points):
    if len(points)==1 and isinstance(points[0],Circ): return mp.pi*points[0].radius**2
    assert len(points)>=3
    return abs(sum(cross(points[i],points[(i+1)%len(points)]) for i in range(len(points))))/2
def midpoint(a,b): return Pt((a.x+b.x)/2,(a.y+b.y)/2)
def point_on_segment(a,b,t):
    assert 0<=t<=1 and dist(a,b)>TOL
    return Pt(a.x+t*(b.x-a.x),a.y+t*(b.y-a.y))
def incenter(a,b,c):
    assert area(a,b,c)>TOL
    wa,wb,wc=dist(b,c),dist(a,c),dist(a,b)
    s=wa+wb+wc
    return Pt((wa*a.x+wb*b.x+wc*c.x)/s,(wa*a.y+wb*b.y+wc*c.y)/s)
def angle(a,b,c):
    u,v=sub(a,b),sub(c,b)
    assert dot(u,u)>TOL and dot(v,v)>TOL
    return mp.atan2(abs(cross(u,v)),dot(u,v))
def reflect(p,l):
    v=sub(l.b,l.a)
    t=dot(sub(p,l.a),v)/dot(v,v)
    foot=Pt(l.a.x+t*v.x,l.a.y+t*v.y)
    return Pt(2*foot.x-p.x,2*foot.y-p.y)
def convex(points):
    signs=[]
    for i,a in enumerate(points):
        b=points[(i+1)%len(points)]
        for j,p in enumerate(points):
            if j not in (i,(i+1)%len(points)):
                signs.append(cross(sub(b,a),sub(p,a)))
    return all(x>TOL for x in signs) or all(x<-TOL for x in signs)


FUNCTIONS=dict(Point=Pt,Line=line,Circle=circle,Distance=dist,Area=area,Midpoint=midpoint,
               PointOnSegment=point_on_segment,Incenter=incenter,Angle=angle,Reflect=reflect,
               ConvexPolygon=convex,Dot=dot,Vector=lambda a,b:sub(b,a),
               sqrt=mp.sqrt,cos=mp.cos,sin=mp.sin,abs=abs)


def evaluate(expression,scope):
    """Restricted AST interpreter; integer division never round-trips via float."""
    def visit(n):
        if isinstance(n,ast.Constant):
            assert isinstance(n.value,(int,float)) and not isinstance(n.value,bool)
            return mp.mpf(str(n.value))
        if isinstance(n,ast.Name): return mp.pi if n.id=='pi' else scope[n.id]
        if isinstance(n,ast.Attribute):
            assert n.attr in ('x','y')
            return getattr(visit(n.value),n.attr)
        if isinstance(n,ast.List): return [visit(x) for x in n.elts]
        if isinstance(n,ast.UnaryOp):
            a=visit(n.operand)
            return -a if isinstance(n.op,ast.USub) else a
        if isinstance(n,ast.BinOp):
            a,b=visit(n.left),visit(n.right)
            if isinstance(n.op,ast.Add): return a+b
            if isinstance(n.op,ast.Sub): return a-b
            if isinstance(n.op,ast.Mult): return a*b
            if isinstance(n.op,ast.Div): return a/b
            if isinstance(n.op,ast.Pow): return a**b
            raise AssertionError(type(n.op))
        if isinstance(n,ast.Call):
            assert isinstance(n.func,ast.Name) and not n.keywords
            return FUNCTIONS[n.func.id](*[visit(x) for x in n.args])
        raise AssertionError(type(n))
    return visit(ast.parse(str(expression),mode='eval').body)


def normalized_id(s):
    return '-'.join(str(int(t)) if t.isdigit() else {'I':'1','II':'2'}.get(t,t) for t in s.upper().split('-'))


def dsl_signature(d,alpha=False):
    if not alpha: return sha(json.dumps({k:v for k,v in d.items() if k!='id'},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode())
    names={v:f'v{i}' for i,v in enumerate(d['variables'])}
    names.update({c['name']:f'o{i}' for i,c in enumerate(d['constructions'])})
    class Rename(ast.NodeTransformer):
        def visit_Name(self,node): return ast.Name(id=names.get(node.id,node.id),ctx=node.ctx)
    def ex(s): return ast.dump(Rename().visit(ast.parse(str(s),mode='eval')),include_attributes=False)
    cond=[('predicate',ex(c['predicate'])) if 'predicate' in c else (c['operator'],ex(c['left']),ex(c['right'])) for c in d['conditions']]
    return sha(json.dumps([len(d['variables']),[ex(c['expression']) for c in d['constructions']],sorted(cond),ex(d['target'])]).encode())


def normalized_statement(s):
    s=re.sub(r'\[asy\].*?\[/asy\]','',s,flags=re.S)
    s=re.sub(r'\bSolution\b\s*$','',s)
    return re.sub(r'[^a-z0-9\u3000-\u9fff]','',s.lower())


def duplicate_audit(cases):
    groups=[('development323',ROOT/'benchmarks/cases.jsonl'),
            ('new2026',ROOT/'jssa/difficulty/new2026/cases.jsonl'),
            ('unseen1983',ROOT/'jssa/difficulty/unseen-1983/cases.jsonl')]
    other=HERE.parent/'b/cases.jsonl'
    if other.exists(): groups.append(('unseen2b_snapshot',other))
    def sig(c,k):
        if k=='normalized_id': return normalized_id(c['id'])
        if k=='dsl_without_id': return dsl_signature(c['dsl']) if c.get('dsl') else None
        if k=='alpha_ast': return dsl_signature(c['dsl'],True) if c.get('dsl') else None
        return normalized_statement(c['problem_statement']) if c.get('problem_statement') else None
    kinds=['normalized_id','dsl_without_id','alpha_ast','normalized_statement']
    overlaps=[]; coverage=[]
    for label,path in groups:
        rows=read_rows(path)
        coverage.append(dict(group=label,path=str(path.relative_to(ROOT)),sha256=sha(path.read_bytes()),
                             count=len(rows),with_statement=sum(bool(r.get('problem_statement')) for r in rows)))
        for kind in kinds:
            index=defaultdict(list)
            for r in rows:
                s=sig(r,kind)
                if s: index[s].append(r['id'])
            for c in cases:
                s=sig(c,kind)
                for cid in index.get(s,[]) if s else []:
                    overlaps.append(dict(group=label,kind=kind,new_id=c['id'],existing_id=cid))
    internal=[]
    for kind in kinds:
        index=defaultdict(list)
        for c in cases:
            s=sig(c,kind)
            if s: index[s].append(c['id'])
        internal.extend(dict(kind=kind,ids=ids) for ids in index.values() if len(ids)>1)
    assert [r['count'] for r in coverage[:3]]==[323,20,54]
    return dict(passed=not overlaps and not internal,coverage=coverage,methods=kinds,
                external_overlaps=overlaps,internal_overlaps=internal,
                limitations='数学的同値の網羅的証明ではない。翻訳・異なるモデルの同一問題は正規化IDで補う。new2026等の原文欠落分はIDとDSLで照合。bは取得時点のsnapshot。',
                solver_run=False)


def static(d):
    GeometryProblem.model_validate(d)
    assert set(d)=={'id','variables','constructions','conditions','target'}
    scope=set(d['variables']); errors=[]; count=0
    assert len(scope)==len(d['variables'])
    def inspect(where,expression):
        nonlocal count
        count+=1
        issues,tree=_expression_issues(where,str(expression),scope)
        errors.extend(dict(path=where,issue=x.model_dump()) for x in issues)
        assert isinstance(tree,ast.Expression)
        assert not any(isinstance(n,(ast.FloorDiv,ast.Mod)) for n in ast.walk(tree))
        assert not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in ('IsInteger','floor','ceil') for n in ast.walk(tree))
    for i,c in enumerate(d['constructions']):
        assert c['name'] not in scope
        inspect(f'constructions[{i}]',c['expression']); scope.add(c['name'])
    for i,c in enumerate(d['conditions']):
        for key in ['predicate'] if 'predicate' in c else ['left','right']: inspect(f'conditions[{i}].{key}',c[key])
    inspect('target',d['target'])
    assert not errors,errors
    return count


def substitute(d,values,reference):
    assert set(values)==set(d['variables'])
    scope={k:evaluate(v,{}) for k,v in values.items()}
    rows=[]; worst=mp.mpf('0'); margins=[]
    for c in d['constructions']: scope[c['name']]=evaluate(c['expression'],scope)
    for i,c in enumerate(d['conditions']):
        if 'predicate' in c:
            passed=bool(evaluate(c['predicate'],scope)); row=dict(index=i,predicate=c['predicate'],passed=passed)
        else:
            a,b=evaluate(c['left'],scope),evaluate(c['right'],scope)
            op=c['operator']; delta=a-b; scale=1+abs(a)+abs(b)
            if op=='=':
                norm=abs(delta)/scale; worst=max(worst,norm); passed=norm<TOL
                row=dict(index=i,operator=op,left=fmt(a),right=fmt(b),absolute_residual=fmt(abs(delta)),normalized_residual=fmt(norm),passed=passed)
            else:
                margin=delta if op in ('>','>=') else -delta if op in ('<','<=') else abs(delta)
                passed=margin>0 if op in ('>','<','!=') else margin>=-TOL*scale
                margins.append(margin)
                row=dict(index=i,operator=op,left=fmt(a),right=fmt(b),margin=fmt(margin),passed=passed)
        rows.append(row)
    target=evaluate(d['target'],scope); ref=evaluate(reference,{})
    target_res=abs(target-ref)/(1+abs(ref))
    extras=[]
    if d['id']=='AIME-2002-I-02':
        centers=[scope[f'{row}{i}'] for row,n in [('L',7),('M',6),('T',7)] for i in range(n)]
        clearance=min(dist(a,b)-2 for i,a in enumerate(centers) for b in centers[i+1:])
        extras.append(dict(check='all 190 pairs of circles do not overlap',margin=fmt(clearance),passed=clearance>=-TOL))
    if d['id']=='AIME-2014-II-10':
        z=mp.mpc(2014,0)
        for n in ['W1','W2']:
            w=mp.mpc(scope[n].x,scope[n].y)
            error=abs(1/(z+w)-1/z-1/w)
            extras.append(dict(check=f'original reciprocal equation for {n}',absolute_residual=fmt(error),passed=error<TOL))
    if d['id']=='AIME-2019-I-12':
        z=mp.mpc(scope['Z'].x,scope['Z'].y); f=z*z-19*z; g=f*f-19*f
        crossvalue=abs(mp.im((z-f)*mp.conj(g-f)))
        extras.append(dict(check='triangle of the three complex points is nondegenerate',twice_area=fmt(crossvalue),passed=crossvalue>0))
    return dict(passed=all(r['passed'] for r in rows+extras) and target_res<TOL,
                coordinates=values,conditions=rows,extra_checks=extras,
                maximum_normalized_equality_residual=fmt(worst),
                minimum_inequality_margin=fmt(min(margins)) if margins else None,
                target=fmt(target),reference=reference,reference_decimal=fmt(ref),
                normalized_target_residual=fmt(target_res),precision_decimal_digits=90)


def main():
    assert not (HERE/'prediction.lock.json').exists(),'prediction is locked'
    mappings=json.loads((HERE/'mapping.json').read_text())
    hand=witnesses(); assert {m['id'] for m in mappings}==set(hand)
    cases=[]; reports=[]; references={}; cards=[]; expressions=0
    imports={r['name']:r for r in json.loads((HERE/'source-evidence/import-log.json').read_text())}
    for m in mappings:
        cid=m['id']; dpath=HERE/'dsl'/f'{cid}.json'; d=json.loads(dpath.read_text())
        expressions+=static(d)
        _,year,part,num=cid.split('-'); number=int(num)
        pfile=f'{year}_AIME_{part}_Problems.html'; afile=f'{year}_AIME_{part}_Answer_Key.html'
        for filename in (pfile,afile):
            data=(HERE/'source-evidence'/filename).read_bytes()
            validate(filename,data)
            assert sha(data)==imports[filename]['sha256']
        section=problem((HERE/'source-evidence'/pfile).read_text(),number)
        official=answer_key((HERE/'source-evidence'/afile).read_text())[number-1]
        w=hand[cid]
        audits=[substitute(d,v,w['reference']) for v in [w['values']]+w.get('additional_values',[])]
        assert all(r['passed'] for r in audits),(cid,audits)
        assert str(score.convert(score.sp.sympify(w['reference']),w['conversion']))==str(int(official)),cid
        references[cid]=dict(geometric_value=w['reference'],output_conversion=w['conversion'],
                             official_output=str(int(official)),official_output_verbatim=official,
                             answer_key_file='source-evidence/'+afile,answer_key_sha256=imports[afile]['sha256'],
                             answer_key_list_position_one_based=number,
                             basis='AoPS Wiki Answer Key plus independent hand construction; no solution text or solver run')
        reports.append(dict(id=cid,passed=True,dsl_sha256=sha(dpath.read_bytes()),statement_sha256=sha(section['text'].encode()),
                            derivation=w['derivation'],target_uniqueness_reasoning=w['uniqueness'],
                            substitutions=audits,scope='fixed-coordinate existence/target checks plus textual branch reasoning; not exhaustive automated root search'))
        url=imports[pfile]['archive_url_from_html_identity']+'#Problem_'+str(number)
        case=dict(id=cid,dedupe_key=cid,dsl_path=f'dsl/{cid}.json',dsl=d,problem_statement=section['text'],
                  source=url,answer=[w['reference']],authoring_status='runnable',truth_status='verified',
                  truth_basis='geometric reference verified by hand construction and converted to primary answer key',
                  source_evidence=dict(problem_file='source-evidence/'+pfile,problem_sha256=imports[pfile]['sha256'],
                                       problem_section_line=section['line'],answer_file='source-evidence/'+afile,answer_sha256=imports[afile]['sha256']))
        cases.append(case)
        lines=[f'# {cid}',f'一次資料: [{pfile}]({url})、Problem {number}、保存HTML行{section["line"]}。',
               f'DSL SHA-256: `{sha(dpath.read_bytes())}`',f'問題節 SHA-256: `{sha(section["text"].encode())}`',
               '', '## 原文（保存HTMLから抽出）', '',section['text'],'','## 座標・条件との読み合わせ','',m['coordinate_choice'],'']
        for key in ('constructions','conditions'):
            assert len(m[key])==len(d[key])
            for i,(clause,why) in enumerate(zip(d[key],m[key])):
                lines.append(f'- `{key}[{i}]` `{json.dumps(clause,ensure_ascii=False)}` — {why}')
        lines += [f'- `target` `{d["target"]}` — {m["target"]}', '', '## 独立検算','',w['derivation'],'',w['uniqueness'],'',
                  f'幾何量参照値 `{w["reference"]}`、採点変換 `{w["conversion"]}`、Answer Key `{official}`。',
                  '90桁の独立評価器で全等式・不等式・構成の定義域を検査。詳細は `audit/substitution.json`。',
                  '解座標は監査専用で、DSL・初期点・探索箱には渡さない。solverおよび局所探索の実行なし。','']
        card='\n'.join(lines); cards.append(card)
        (HERE/'cards').mkdir(exist_ok=True)
        (HERE/'cards'/f'{cid}.md').write_text(card)
    dedup=duplicate_audit(cases); assert dedup['passed'],dedup
    write_json(HERE/'audit/duplicate-audit.json',dedup)
    write_json(HERE/'audit/substitution.json',dict(passed=True,solver_run=False,local_search_run=False,PSLQ_run=False,
               method='independent 90-digit arithmetic at hand-derived fixed diagrams, no equation solving',cases=reports))
    write_json(HERE/'references.json',references)
    payload=''.join(json.dumps(c,ensure_ascii=False)+'\n' for c in cases)
    assert len(payload.encode())<LIMIT
    (HERE/'cases.jsonl').write_text(payload)
    (HERE/'cards.md').write_text('\n'.join(cards))
    checks=score.check_contract(references)
    write_json(HERE/'audit/scoring-contract-check.json',checks)
    assert not any(k.startswith('geosolver.engine') for k in sys.modules)
    report=dict(passed=True,cases=len(cases),static_expressions=expressions,
                fixed_diagrams=sum(len(r['substitutions']) for r in reports),
                all_official_outputs_match=True,duplicate_overlaps=0,
                solver_run=False,local_search_run=False,PSLQ_run=False,
                imported_engine_modules=[],created_at_utc=datetime.now(timezone.utc).isoformat())
    write_json(HERE/'audit/validation.json',report)
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__': main()
