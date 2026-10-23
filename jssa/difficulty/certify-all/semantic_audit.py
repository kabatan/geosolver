"""Structural checks for translator corner cases found by source inspection.

This does not replace the algebraic certificate check. It checks sensitive
line-parameter orientation and the straight-angle branch of AngleBisector.
The original measured results are preserved; an unresolved issue is reported.
"""
import ast
import json
from pathlib import Path
import sys
import sympy as sp

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from bounds import Bounds, parse, key, rational
from result_paths import results


def nodes(dsl):
    texts=[c["expression"] for c in dsl["constructions"]]+[dsl["target"]]
    for c in dsl["conditions"]:
        texts.extend(str(v) for k,v in c.items() if k in ("left","right","predicate"))
    return [n for s in texts for n in ast.walk(parse(s))]


def call(n,name):
    return isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id==name


def safe_line(n,b):
    n=b.expand(n)
    if call(n,"Line") and len(n.args)==2: return True
    if call(n,"ParallelLine") and len(n.args)==2: return any(safe_line(a,b) for a in n.args)
    return False


def coordinate(n,b):
    n=b.expand(n)
    if call(n,"Point") and len(n.args)==2:
        vals=[]
        for a in n.args:
            # Pure rational coordinate expressions only.
            if any(isinstance(q,(ast.Call,ast.Attribute)) for q in ast.walk(a)): return None
            vals.append(sp.sympify(ast.unparse(a),locals={s:sp.Symbol(s) for s in b.dsl["variables"]},rational=True))
        return vals
    if call(n,"Midpoint") and len(n.args)==2:
        a,c=[coordinate(v,b) for v in n.args]
        if a is not None and c is not None:return [(x+y)/2 for x,y in zip(a,c)]
    return None


def nonzero_factor(f,b):
    if not f.free_symbols:return bool(f!=0),{"constant":str(f)}
    n=b.expand(parse(str(f)))
    lo,hi=b.scalar(n)
    elo,ehi,lop,hip=b.explicit.get(key(n),(-sp.oo,sp.oo,False,False))
    ok=lo>0 or hi<0 or lo==0 and elo==0 and lop or hi==0 and ehi==0 and hip
    return bool(ok),{"factor":str(f),"bounds":[str(lo),str(hi)],"strict_lower":bool(lop and lo==elo),"strict_upper":bool(hip and hi==ehi)}


def triangle_noncollinear(args,b):
    pts=[coordinate(n,b) for n in args]
    if all(p is not None for p in pts):
        a,c,d=pts
        cross=sp.factor((c[0]-a[0])*(d[1]-a[1])-(c[1]-a[1])*(d[0]-a[0]))
        num,den=sp.fraction(cross)
        if num!=0:
            evidence=[];good=True
            for expr in (num,den):
                if not expr.free_symbols:
                    good &= expr!=0
                    continue
                const,fs=sp.factor_list(expr)
                for f,power in fs:
                    ok,ev=nonzero_factor(f,b);good &= ok;evidence.append(ev)
            if good:return {"proved":True,"method":"exact_cross_product_nonzero","cross":str(cross),"factors":evidence}
    target_keys={key(b.expand(a)) for a in args}
    lengths={}
    for i,c in enumerate(b.dsl["conditions"]):
        if not all(k in c for k in ("left","right","operator")):continue
        n=b.expand(parse(c["left"]));v=rational(parse(c["right"]))
        if call(n,"Area") and {key(x) for x in n.args}==target_keys and v is not None:
            if (c["operator"] in ("=",">=",">") and v>0) or (c["operator"]==">" and v==0):
                return {"proved":True,"method":"positive_area_condition","condition_index":i}
        if call(n,"Distance") and c["operator"]=="=" and len(n.args)==2 and v is not None:
            pair=frozenset(key(x) for x in n.args)
            if pair<target_keys:lengths[pair]=v
    if len(lengths)==3:
        sides=list(lengths.values())
        if all(s>0 and sum(sides)-s>s for s in sides):
            return {"proved":True,"method":"strict_triangle_inequality","rational_sides":list(map(str,sides))}
    return {"proved":False,"method":"noncollinearity_not_established_by_this_audit"}


def audit(dsl):
    b=Bounds(dsl);checks=[]
    for n in nodes(dsl):
        if call(n,"PointOnLine"):
            checks.append({"expression":ast.unparse(n),"kind":"line_parameter_orientation","proved":safe_line(n.args[0],b)})
        elif isinstance(n,ast.Attribute) and n.attr in ("a","b","c"):
            checks.append({"expression":ast.unparse(n),"kind":"line_coefficient_orientation","proved":safe_line(n.value,b)})
        elif call(n,"AngleBisector"):
            checks.append({"expression":ast.unparse(n),"kind":"exclude_straight_angle_fallback",**triangle_noncollinear(n.args,b)})
        elif call(n,"Tangent") or call(n,"TangentLine"):
            checks.append({"expression":ast.unparse(n),"kind":"tangent_lift_needs_manual_check","proved":False})
    return {"checks":checks,"pass":all(c["proved"] for c in checks)}


def main():
    rows=[]
    for rp in results():
        r=json.loads(rp.read_text())
        if r["status"]!="certified_saved_endpoint_set":continue
        d=json.loads((HERE/"inputs"/(r["id"]+".json")).read_text())["dsl"]
        rows.append({"id":r["id"],**audit(d)})
    payload={"scope":"Structural audit of known normalization/degenerate-construction hazards, not a formally verified DSL compiler.","cases":rows,"all_pass":all(r["pass"] for r in rows),"unresolved_ids":[r["id"] for r in rows if not r["pass"]]}
    (HERE/"semantic-audit.json").write_text(json.dumps(payload,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({"certified_cases_checked":len(rows),"unresolved_ids":payload["unresolved_ids"]}))


if __name__=="__main__":main()
