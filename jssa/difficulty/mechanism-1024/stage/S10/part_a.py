"""事前登録17 部分A の集計（S8 の結果を見る前に固定）。

入力: S8 の問題×構成の表（CSV）。列 case_id, config, solved(0/1), mean_time。
solved と mean_time は S8 の定義（3 seed 中2回以上で集合一致、時間は正解 seed の平均）。
列名が違う場合は --map で対応させるだけにし、定義は変えない。
"""
import argparse, csv, re, statistics, collections

norm = lambda s: re.sub(r'[^a-z0-9]', '', s.lower())

ap = argparse.ArgumentParser()
ap.add_argument('s8_csv')
ap.add_argument('--causes', default='jssa/difficulty/false-attractors/per-problem.csv')
ap.add_argument('--map', default='', help='例: case_id=problem,solved=ok')
a = ap.parse_args()
m = dict(kv.split('=') for kv in a.map.split(',') if kv)
col = lambda k: m.get(k, k)

cause = {norm(r['id']): r['main_cause'] for r in csv.DictReader(open(a.causes))}
R = collections.defaultdict(dict)
for r in csv.DictReader(open(a.s8_csv)):
    R[r[col('case_id')]][r[col('config')]] = (int(r[col('solved')]), float(r[col('mean_time')] or 'nan'))

def grp(g):
    return [p for p in R if cause.get(norm(p)) == g]

def rate(ps, frm, to):
    base = [p for p in ps if R[p].get(frm, (1,))[0] == 0 and to in R[p]]
    if len(base) < 5:
        return None, len(base)
    return sum(R[p][to][0] for p in base) / len(base), len(base)

def tratio(ps):
    v = [R[p]['N'][1] / R[p]['C1'][1] for p in ps
         if 'N' in R[p] and 'C1' in R[p] and R[p]['N'][0] and R[p]['C1'][0] and R[p]['C1'][1] > 0]
    return (statistics.median(v) if len(v) >= 5 else None), len(v)

A, E = grp('a'), grp('e')
print('群の問題数', {g: len(grp(g)) for g in 'abce'})
h1a, h1e = rate(A, 'N', 'C1'), rate(E, 'N', 'C1')
h2a, h2e = rate(A, 'C1', 'C2'), rate(E, 'C1', 'C2')
h3a, h3e = tratio(A), tratio(E)
def judge(x, y):  # x>y を予測
    if x[0] is None or y[0] is None: return '判定不能'
    return '当たり' if x[0] > y[0] else '外れ'
print('H1 N→C1で救われる割合 a', h1a, 'e', h1e, judge(h1a, h1e))
print('H2 C1→C2で救われる割合 e', h2e, 'a', h2a, judge(h2e, h2a))
print('H3 時間比N/C1の中央値 a', h3a, 'e', h3e, judge(h3a, h3e))
for g in 'bc':
    ps = grp(g)
    print('記述', g, len(ps), {c: sum(R[p].get(c, (0,))[0] for p in ps) for c in ['N', 'C1', 'C2', 'BASE']})
