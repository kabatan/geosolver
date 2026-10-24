"""Fixed selection rule for the 72-problem mechanism set (prereg 7). Run once; output committed before any run."""
import csv, collections, hashlib, statistics as st, json, sys
ATTR = 'jssa/results/mechanism-attribution/attribution.csv'
MULTI = 'jssa/difficulty/capability-1024/posthoc-20/multivalue-problems.csv'
rows = list(csv.DictReader(open(ATTR)))
by = collections.defaultdict(list)
for r in rows: by[r['case_id']].append(r)
h = lambda c: hashlib.sha256(('mech1024:' + c).encode()).hexdigest()
multi = sorted(r['case_id'] for r in csv.DictReader(open(MULTI)))
assert len(multi) == 8 and all(m in by for m in multi)
def med(c): return st.median(float(x['wall_s']) for x in by[c])
hard_pool = [c for c in by if c not in multi and (
    med(c) >= 10 or any(x['matched'] != 'True' for x in by[c])
    or any(x['second_attempt_triggered'] == 'True' for x in by[c])
    or any(x['rescue_triggered'] == 'True' for x in by[c]))]
fast_pool = [c for c in by if c not in multi and c not in hard_pool]
alg = [c for c in fast_pool if all(x['answer_source_stage'] == 'algebraic_branch_discovery' for x in by[c])]
nonalg = [c for c in fast_pool if not any(x['answer_source_stage'] == 'algebraic_branch_discovery' for x in by[c])
          and not any(x['answer_source_stage'] == 'direct_constant_no_variables' for x in by[c])]
hard = sorted(hard_pool, key=h)[:48]
fast = sorted(alg, key=h)[:8] + sorted(nonalg, key=h)[:8]
out = {'rule': 'see README.md', 'pools': {'hard_pool': len(hard_pool), 'fast_alg_pool': len(alg), 'fast_nonalg_pool': len(nonalg)},
       'hard': hard, 'fast_algebraic': fast[:8], 'fast_search': fast[8:], 'multivalued': multi}
json.dump(out, open('jssa/difficulty/mechanism-1024/problem-set/problem-set.json', 'w'), indent=1)
print(out['pools'], len(hard), len(fast), len(multi))
