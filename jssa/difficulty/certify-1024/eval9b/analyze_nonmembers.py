#!/usr/bin/env python3
"""Post-run inspection: exact substitutions in saved ORIGINAL equations.

No Singular, Groebner computation, new certify attempt, or result reclassification.
Witnesses may be complex and do not claim an admissible geometric figure.
"""
import json
from pathlib import Path
import sys
import sympy as sp

E = Path(__file__).resolve().parent
sys.path.insert(0, str(E.parent))
import certify as c


def analyze():
    m = json.loads((E/'pre-run-hashes.json').read_text())
    rt = sp.sqrt
    f = 250+50*rt(7)
    t_alt = sp.Rational(507,53)
    t_param = (1285245-24539*t_alt**2)/1505790
    vals = {
        'AIME-2005-II-12': [f+400,f,rt(2)/2,-rt(2)/2,f+400,900-f,400,180000,900-f],
        'AIME-2001-II-13': [sp.Rational(26,5),2*rt(231)/5,sp.Rational(111,20),-3*rt(231)/20,
                             8,-3*rt(231)/2,5,6,4*rt(231),5*rt(231)/2,5],
        'AIME-2005-II-08': [0,3*rt(sp.Rational(98,5))/28,rt(sp.Rational(98,5)),4,-4,-10,4,10,
                             sp.Rational(40,7),40*sp.I/7,80*sp.I/7],
        'HMMT-2020-FEB-GUTS-13': [0,4*rt(3),-sp.Rational(16,33),-sp.Rational(16,33),sp.Rational(4,3),
                                  sp.Rational(12,11),-32*rt(3)/33,-16*rt(3)/3,4*rt(3)/11,
                                  sp.Rational(56,33),sp.Rational(56,33),sp.Rational(56,33),
                                  sp.Rational(112,33),7,4*rt(3),rt(3),32*rt(3)/33,sp.Rational(112,33)],
        'AIME-2002-I-02': [2,2,1+rt(3),1,2,2,2,2,2,7],
        'AIME-2005-II-14': [t_param,sp.Rational(33,5),sp.Rational(56,5),13,14,sp.Rational(336,5),
                             (845-495*t_param)*sp.Rational(336,5)/728,t_alt,t_alt],
        'AIME-2004-II-07': [sp.Rational(70,3),0,15,-sp.Rational(70,3),sp.Rational(10,3)],
        'HMMT-2012-FEB-GUTS-06': [-6,-6,-sp.Rational(5,3),7,6,6,32,32],
    }
    witnesses = {}
    for cid, values in vals.items():
        work = E/'unseen/runs'/(cid+'.work')
        model = json.loads((work/'translation.json').read_text())
        names = list(model['variable_mapping'])
        assert len(names) == len(values)
        symbols = {n:sp.Symbol(n) for n in names}
        subs = {symbols[n]:sp.sympify(v) for n,v in zip(names,values)}
        def value(expr):
            return sp.simplify(sp.sympify(expr.replace('^','**'),locals=symbols).subs(subs))
        equations = [value(e) for e in model['equations']]
        guards = [value(e) for e in model['saturation_factors']]
        q = value(model['polynomial'])
        passed = all(v==0 for v in equations) and all(v.is_zero is False for v in guards) and q.is_zero is False
        if not passed:
            raise AssertionError((cid,equations,guards,q))
        witnesses[cid] = dict(verified=True, variables={n:str(v) for n,v in zip(names,values)},
                              variable_mapping=model['variable_mapping'], target_value=str(subs[symbols[model['target_variable']]]),
                              equation_residuals=list(map(str,equations)), guard_values=list(map(str,guards)),
                              q_value=str(q), model_sha256=c.sha(work/'translation.json'),
                              method='exact SymPy substitution in pre-Singular original equations and nonzero guards',
                              geometric_existence_claim=False, singular_called=False)
    details = {}
    T = sp.Symbol('T')
    for cid in m['order']:
        path = E/'unseen/runs'/(cid+'.json')
        if not path.exists():
            continue
        result = json.loads(path.read_text())
        if result['status'] != 'nonmember':
            continue
        cand = m['records'][cid]
        p = sp.sympify(cand['original_polynomial'])
        even = sp.expand(p.subs(T,-T)-p)==0
        work = E/'unseen/runs'/(cid+'.work')
        blocks = json.loads((work/'algebra-output.json').read_text())
        details[cid] = dict(original_polynomial=str(p), q=cand['polynomial'],
                           even_p_so_q_equals_p_squared=even, target=cand['sign']['target'],
                           q_normal_form=blocks['NF1'], original_equation_counterexample=cid in witnesses,
                           category='pが既に偶多項式、根集合は増えない' if even else '目標の±以外の枝（元等式への反例あり）')
    assert len(details) == 9
    assert all(v['even_p_so_q_equals_p_squared'] or v['original_equation_counterexample'] for v in details.values())
    output = dict(scope='post-run explanation only; no new certification attempts',
                  script_sha256=c.sha(__file__), details=details, witnesses=witnesses,
                  caveat='反例は元の代数化等式と非零条件に対するもの。実図や元DSLの不等式・主値を満たすとは限らない。',
                  saturation_removed_q_branch='本分析では断定しない。少なくとも7問は目標の±以外の枝を元等式への代入で確認。')
    c.write_json(E/'unseen/nonmembership-analysis.json', output)
    print('exact original-equation witnesses verified',len(witnesses))


if __name__ == '__main__':
    analyze()
