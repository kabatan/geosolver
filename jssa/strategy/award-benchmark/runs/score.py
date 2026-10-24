"""Score blind anchor runs against a key (04-blind-anchor-test.md / 05-applied-math.md 5-4).

usage: python score.py KEY.md PARSED.json [--only-prefix 6._HAM]
PARSED.json: {run_id: {"order": 1, "rank": {"01": 3, ...}, "grade": {"01": "C", ...}, "seen": ["02"], "search": false}}
Metrics use the scored set: every awarded work, or only codes matching --only-prefix (e.g. applied math 'HAM').
Prints markdown.
"""
import json, re, sys, statistics, pathlib, collections

G = {'A': 1, 'B': 2, 'C': 3, 'D': 4, 'E': 5}
NAMES = {'66_HIT026IT': '盲導杖', '64_HIT023IT': '点字翻訳', '69_HIT058IT': '空間認知', '69_HAM023AM': '音律',
         '66_HAM029AM': '割当問題', '66_HIT016IT': 'JasperNet', '65_HIT044IT': '楽器音分離', '68_HAM010AM': 'Boid',
         '68_HIT039IT': 'LUALCAD', '66_HIT033IT': '画像圧縮', '66_HAM035AM': '量子機械学習', '66_HAM020AM': '料理配達',
         '68_HIT028IT': 'Swap SQA', '64_HIT025IT': 'AmoebaSAT', '66_HIT017IT': '立体数独', '66_HIT028IT': 'フォント生成',
         '69_HAM018AM': '路面電車', '68_HAM017AM': 'GK位置', '65_HAM016AM': '創作展', '67_HAM025AM': 'スーパーブルーム',
         '65_HAM003AM': '正多角形回帰', '65_HAM015AM': 'エスカレーター', '69_HAM026AM': 'チョークポイント',
         '65_HAM005AM': '三角魔方陣', '66_HAM030AM': '選挙', '67_HAM017AM': '片付け', 'GEOSOLVER': 'geosolver'}

keyf, parsedf = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
only = sys.argv[sys.argv.index('--only-prefix') + 1] if '--only-prefix' in sys.argv else ''
key = {}
for line in keyf.read_text(encoding='utf-8').splitlines():
    m = re.match(r'\|\s*(\d)\s*\|\s*作品(\d\d)\s*\|\s*(\S+)\s*\|\s*(\S)\s*\|', line)
    if m: key[(int(m.group(1)), m.group(2))] = (m.group(3), m.group(4))
scored = lambda code: code != 'GEOSOLVER' and (not only or only in code)

def avg_ranks(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i]); r = [0.0] * len(xs); i = 0
    while i < len(xs):
        j = i
        while j + 1 < len(xs) and xs[order[j + 1]] == xs[order[i]]: j += 1
        for k in range(i, j + 1): r[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return r

def spearman(a, b):
    ra, rb = avg_ranks(a), avg_ranks(b)
    ma, mb = statistics.mean(ra), statistics.mean(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = (sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb)) ** 0.5
    return num / den if den else float('nan')

runs = json.loads(parsedf.read_text(encoding='utf-8'))

def metrics(r, drop_seen):
    o = r['order']; rows = []
    for (oo, no), (code, act) in key.items():
        if oo != o or not scored(code) or (drop_seen and no in r['seen']): continue
        rows.append((code, G[act], G[r['grade'][no]], r['rank'][no]))
    exact = sum(a == g for _, a, g, _ in rows) / len(rows)
    bias = statistics.mean(g - a for _, a, g, _ in rows)
    rho = spearman([x[3] for x in rows], [x[1] for x in rows])
    return len(rows), exact, bias, rho

out = ['| 回 | 検索 | 件数 | 段階一致率 | ずれの向き（＋＝辛い） | 順位相関ρ | 見覚えあり | 見覚え除外 一致率/ずれ/ρ | geosolver 段階・全体順位・採点対象内の順位 |',
       '|---|---|---|---|---|---|---|---|---|']
per_code = collections.defaultdict(list); geo = []; allm = []
for rid in sorted(runs):
    r = runs[rid]; o = r['order']
    n, ex, bi, rho = metrics(r, False)
    n2, ex2, bi2, rho2 = metrics(r, True)
    gno = next(nn for (oo, nn), (c, _) in key.items() if oo == o and c == 'GEOSOLVER')
    above = sum(1 for (oo, nn), (c, _) in key.items() if oo == o and scored(c) and r['rank'][nn] < r['rank'][gno])
    geo.append((r['grade'][gno], r['rank'][gno], above + 1))
    seen = ','.join(f"{s}({NAMES.get(key[(o, s)][0], key[(o, s)][0])})" for s in r['seen']) or 'なし'
    out.append(f"| {rid} | {'あり' if r.get('search') else 'なし'} | {n} | {ex:.0%} | {bi:+.2f} | {rho:.2f} | {seen} | {ex2:.0%} / {bi2:+.2f} / {rho2:.2f} (n={n2}) | {r['grade'][gno]} / {r['rank'][gno]}位 / {above + 1}位 |")
    for (oo, no), (code, act) in key.items():
        if oo == o: per_code[code].append((r['grade'][no], r['rank'][no], no in r['seen']))
    allm.append((ex, bi, rho))
out.append(f"| **平均** | | | {statistics.mean(x[0] for x in allm):.0%} | {statistics.mean(x[1] for x in allm):+.2f} | {statistics.mean(x[2] for x in allm):.2f} | | | |")
out += ['', '### 作品ごとの判定（全回）', '', '| 作品 | 実際 | 採点対象 | GPT-Pro 段階（各回） | 段階の平均（A=1…E=5） | 順位（各回） | 順位の中央値 |', '|---|---|---|---|---|---|---|']
actual = {c: a for (_, _), (c, a) in key.items()}
for code in sorted(per_code, key=lambda c: (G.get(actual[c], 0), statistics.median(x[1] for x in per_code[c]))):
    xs = per_code[code]
    out.append(f"| {NAMES.get(code, code)} ({code}) | {actual[code]} | {'○' if scored(code) else ''} | {''.join(x[0] + ('*' if x[2] else '') for x in xs)} | "
               f"{statistics.mean(G[x[0]] for x in xs):.2f} | {','.join(str(x[1]) for x in xs)} | {statistics.median(x[1] for x in xs)} |")
out.append('\n（* はその回で「見覚えあり」と答えた作品）\n')
c = collections.Counter(g for g, _, _ in geo)
out.append(f"### geosolver\n\n- 段階の分布: {', '.join(f'{k} {c[k]}回' for k in 'ABCDE' if c[k])}（{len(geo)}回）")
out.append(f"- 全体順位: {', '.join(str(x[1]) for x in geo)} → 中央値 {statistics.median(x[1] for x in geo)}")
out.append(f"- 採点対象作品の中での順位（1＝どの採点対象作品よりも上）: {', '.join(str(x[2]) for x in geo)} → 中央値 {statistics.median(x[2] for x in geo)}")
print('\n'.join(out))
