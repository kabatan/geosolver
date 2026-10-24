#!/usr/bin/env python3
"""既存11認証の記述的整理。逐次処理。求解・認証の再実行はしない。"""
import ast
import csv
import hashlib
import json
import math
from pathlib import Path

import sympy as sp

OUT = Path(__file__).resolve().parent
BASE = OUT.parents[1]
ROOT = BASE.parents[2]
T = sp.Symbol('T')


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sign_rule(target):
    # eval9b/run_9b.py の sign_rule と同じ文法。副作用のあるモジュールは import しない。
    def walk(n):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id in {'Distance', 'Length', 'Perimeter', 'Area', 'Radius', 'sqrt'}
                and n.args and not n.keywords):
            return True, True
        if isinstance(n, ast.Constant) and type(n.value) in (int, float):
            return math.isfinite(n.value) and n.value >= 0, False
        if isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Add, ast.Mult)):
            a, b = walk(n.left), walk(n.right)
            return a[0] and b[0], a[1] or b[1]
        return False, False
    tree = ast.parse(target, mode='eval')
    valid, atom = walk(tree.body)
    return valid and atom, ast.dump(tree, include_attributes=False)


def hp_entries(obj, path=()):
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == 'answer_hp' and isinstance(value, str):
                yield path + (key,), value
            else:
                yield from hp_entries(value, path + (key,))
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            yield from hp_entries(value, path + (i,))


def exact_witness(cid, tr):
    """明示した代数値の代入検算だけ。方程式系の solve / Groebner はしない。"""
    if cid == 'AIME-2005-I-07':
        a = sp.sqrt(141) - 9
        assert a.is_positive
        assert sp.simplify(a*a-18*a-60+36*a) == 0
        vals = [-a, sp.sqrt(3)/2, sp.Integer(12), a, a]
    elif cid == 'HMMT-2021-FEB-GUTS-14':
        a = sp.sqrt(73) + 3
        cx = sp.simplify((a*a - 28)/(2*a))
        cy = sp.sqrt(sp.simplify(36-cx*cx))
        assert sp.simplify(cy**2).is_positive
        cos_c = sp.simplify((100-a*a)/96)
        assert sp.simplify(cos_c-(3-sp.sqrt(73))/16) == 0
        assert cos_c.is_negative
        vals = [a, cx, cy, sp.Integer(6), sp.Integer(8), a*cy, a, a]
    elif cid == 'AIME-2019-I-12':
        a = 9 - sp.sqrt(221)
        assert a.is_negative
        rad = []
        for i, e in [(2, tr['equations'][1]), (3, tr['equations'][2])]:
            r = sp.simplify(-sp.sympify(e).subs({sp.Symbol('x1'): a, sp.Symbol(f'x{i}'): 0}))
            assert r.is_positive
            rad.append(r)
        vals = [a, sp.sqrt(rad[0]), sp.sqrt(rad[1]), a]
    else:
        return None
    sub = {sp.Symbol(f'x{i+1}'): v for i, v in enumerate(vals)}
    residuals = [sp.simplify(sp.sympify(e).subs(sub)) for e in tr['equations']]
    factors = [sp.simplify(sp.sympify(e).subs(sub)) for e in tr['saturation_factors']]
    assert all(r == 0 for r in residuals)
    assert all(f.is_zero is False for f in factors)
    return dict(assignment={str(k): str(v) for k, v in sub.items()},
                equation_residuals=list(map(str, residuals)),
                saturation_factor_values=list(map(str, factors)),
                all_factors_nonzero=True,
                scope='保存済みtranslationの等式・非零条件のみ。元の不等式・主値の充足とは別。')


NOTES = {
    'AIME-2005-I-07': (
        '排除できない（緩和した等式・非零条件には厳密な実代入例あり）',
        '排除できる：a=sqrt(141)-9>0。b>0 と target=Distance(A,B) より b=a。'
        '元の Distance(C,D)=12 は b**2-18*b-60=0 を必要とするが、a での値は -36*a≠0。'
        '等式系の代入例は b=-a なので b>0 に反する。凸性の追加検査は不要。'),
    'HMMT-2021-FEB-GUTS-14': (
        '排除できない（緩和した等式・非零条件には厳密な実代入例あり）',
        '排除できる：a=3+sqrt(73)。b>0 より b=a。'
        'cos(Angle(B,C,A))=(6**2+8**2-a**2)/(2*6*8)=(3-sqrt(73))/16<0。'
        'cy>0 の三角形で C角はπ/2超、従って2*C角>π。A角の主値は(0,π)なので A角=2*C角 は不可能。'),
    'AIME-2019-I-12': (
        '負根は排除できない（緩和した等式・非零条件には厳密な実代入例あり）',
        '負根9-sqrt(221)は排除できる：構築Z=Point(x,11)で target=Z.x=x、元の条件x>0に反する。'
        'ただしsign-ruleは別名展開・条件からの符号推論をしないため非負形へ格上げしない。'),
}


def main():
    rows, evidence, inputs = [], {}, {}
    for mode, csvpath in [('p', BASE/'eval/per-problem.csv'),
                          ('q', BASE/'eval9b/unseen/per-problem.csv')]:
        inputs[str(csvpath.relative_to(ROOT))] = sha(csvpath)
        selected = [r for r in csv.DictReader(csvpath.open()) if r['category_ja'] == '認証']
        assert len(selected) == (4 if mode == 'p' else 7)
        for r in selected:
            cid = r['id']
            work = csvpath.parent/'runs'/f'{cid}.work'
            receipt_path = csvpath.parent/'runs'/f'{cid}.json'
            receipt = read(receipt_path)
            assert receipt['status'] == 'member' and receipt['proof_verified'] is True
            source = ROOT/r['polynomial_source']
            assert source.name == '301.json' and sha(source) == r['polynomial_source_sha256']
            raw = read(source)
            assert raw['case_id'] == cid
            case = read(work/'input.json')
            tr = read(work/'translation.json')
            # 入力DSLが現在の既存ケースと同じことも確認する。
            group = 'a' if cid.startswith('AIME') else 'b'
            cases_path = BASE.parent/f'unseen-2/{group}/cases.jsonl'
            actual = next(json.loads(line) for line in cases_path.read_text().splitlines()
                          if json.loads(line)['id'] == cid)
            assert actual['dsl'] == case['dsl']
            target = case['dsl']['target']
            nonnegative, tree = sign_rule(target)
            if mode == 'q':
                assert nonnegative == receipt['candidate']['sign']['nonnegative_form']
            descriptor = raw['solver_result']['answers'][0]['value']
            p = sp.Poly.from_list(list(map(sp.Rational, descriptor['minimal_polynomial'])), T).as_expr()
            certified = sp.sympify(r['polynomial' if mode == 'p' else 'q_polynomial'])
            assert sp.expand(certified - (p if mode == 'p' else p*p.subs(T, -T))) == 0
            target_symbol = sp.Symbol(tr['target_variable'])
            assert sp.expand(sp.sympify(tr['polynomial']) - certified.subs(T, target_symbol)) == 0
            poly = sp.Poly(certified, T)
            # 厳密な実根分離。個数は重複を除く。近似求根によるカウントはしない。
            roots = sorted(set(poly.real_roots()), key=lambda z: float(z.evalf(20)))
            positive = [z for z in roots if z.is_positive]
            assert all(z.is_positive is not None for z in roots)
            assert poly.count_roots(0, sp.oo) == len(positive)  # 全11問とも0は根でない。
            assert poly.eval(0) != 0
            considered = positive if nonnegative else roots
            hp_path, hp = next((path, value) for path, value in hp_entries(raw)
                               if abs(sp.N(sp.Rational(value)-sp.Rational(descriptor['decimal']), 80)) < sp.Float('1e-40'))
            # 保存値の末尾より高い精度で差を取り、強い桁落ちによる表示上の0を避ける。
            distances = [sp.N(abs(sp.N(z, 650)-sp.N(sp.Rational(hp), 650)), 100)
                         for z in considered]
            order = sorted(range(len(considered)), key=lambda i: distances[i])
            idx = order[0]
            assert distances[idx] < sp.Float('1e-40')
            assert len(order) == 1 or distances[order[1]] > 100*distances[idx]
            other = [z for i, z in enumerate(considered) if i != idx]
            note_eq, note_full = NOTES.get(cid, ('対象なし（他の正根なし）', '対象なし（他の正根なし）'))
            decision = ('目標値が1つに決まる（許容な図があれば）' if nonnegative and len(positive) == 1
                        else '言えない（正の実根が複数）' if nonnegative
                        else '言えない（構文上は符号未確定形）')
            shape = ('非負形：Areaの直接呼出し（通常面積）' if target.startswith('Area(')
                     else '非負形：Distanceの直接呼出し' if target.startswith('Distance(') and not isinstance(ast.parse(target, mode='eval').body, ast.BinOp)
                     else '非負形：Distanceの和＋非負定数の積（2*200）' if nonnegative
                     else '符号未確定形：Attribute(Name(Z),x)。条件からの符号推論はしない')
            row = dict(id=cid, registration='9' if mode == 'p' else '9b',
                       certified_kind=mode, original_p=str(p), certified_polynomial=str(certified),
                       degree=poly.degree(), target=target, target_shape_ja=shape, target_ast=tree,
                       nonnegative_form=nonnegative, root_scope='T>0' if nonnegative else '全実根',
                       positive_real_root_count=len(positive), all_real_root_count=len(roots), zero_is_root=False,
                       counted_root_count=len(considered), roots_exact='; '.join(map(str, considered)),
                       roots_decimal_30d='; '.join(str(z.evalf(30)) for z in considered),
                       solver_root_index_1based=idx+1, solver_root_exact=str(considered[idx]),
                       solver_answer_hp=hp, solver_answer_hp_json_path=json.dumps(hp_path),
                       match_abs_error_100d=str(distances[idx]), match_tolerance='1e-40（数値的一致・証明ではない）',
                       other_roots_exact='; '.join(map(str, other)),
                       other_roots_decimal_30d='; '.join(str(z.evalf(30)) for z in other),
                       exclusion_equations_nonzero_ja=note_eq, exclusion_original_conditions_ja=note_full,
                       uniqueness_ja=decision, source_solver=str(source.relative_to(ROOT)),
                       source_solver_sha256=sha(source), source_result=str(receipt_path.relative_to(ROOT)),
                       source_translation=str((work/'translation.json').relative_to(ROOT)))
            rows.append(row)
            witness = exact_witness(cid, tr)
            if witness:
                evidence[cid] = witness
            for path in [source, receipt_path, work/'input.json', work/'translation.json', cases_path]:
                inputs[str(path.relative_to(ROOT))] = sha(path)
    assert len(rows) == len({r['id'] for r in rows}) == 11
    counts = dict(unique_conditional=sum(r['nonnegative_form'] and r['positive_real_root_count'] == 1 for r in rows),
                  multiple_positive=sum(r['positive_real_root_count'] > 1 for r in rows),
                  signed_form=sum(not r['nonnegative_form'] for r in rows), unconfirmed=0)
    assert counts == dict(unique_conditional=8, multiple_positive=2, signed_form=1, unconfirmed=0)
    with (OUT/'table.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    evidence_path = OUT/'evidence.json'
    evidence_path.write_text(json.dumps(dict(sympy_version=sp.__version__, parallelism=1,
        counts=counts, method='既存結果の読取、厳密実根分離、高精度保存値との比較、明示代入の検算のみ。新規求解なし。',
        input_sha256=inputs, witnesses=evidence), ensure_ascii=False, indent=2)+'\n')
    for path in [OUT/'table.csv', evidence_path, Path(__file__)]:
        assert path.stat().st_size <= 3_000_000
    print(json.dumps(counts, ensure_ascii=False))
    for r in rows:
        print(r['id'], r['positive_real_root_count'], r['root_scope'], r['roots_exact'],
              'solver#'+str(r['solver_root_index_1based']), r['match_abs_error_100d'])


if __name__ == '__main__':
    main()
