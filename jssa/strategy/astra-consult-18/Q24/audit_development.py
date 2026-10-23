"""Small, read-only-on-input audit; writes only Q24 summaries. No solving."""
import ast
import copy
import csv
import hashlib
import io
import json
from collections import Counter
from pathlib import Path

from static_features import features, predict, RULE_NAMES

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]


def csvrows(p):
    return list(csv.DictReader(p.open()))


def write(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def full(r):
    all_ok = r['geo_matched'] == r['geo_runs']
    t = float(r['geo_median_s'])
    return 'easy' if all_ok and t <= 10 else ('hard' if not all_ok or t >= 60 else 'intermediate')


def main():
    h = ROOT / 'jssa/strategy/astra-consult-17/H/sources'
    a = (h / 'comparison-cases.csv').read_bytes()
    b = (OUT / 'source-msolve-cases.csv').read_bytes()
    provenance = json.loads((h / 'provenance.json').read_text())
    entry = next(e for e in provenance['files'] if e['local'] == 'comparison-cases.csv')
    blob = hashlib.sha1(b'blob ' + str(len(b)).encode() + b'\0' + b).hexdigest()
    semantic_equal = list(csv.DictReader(io.StringIO(a.decode()))) == list(csv.DictReader(io.StringIO(b.decode())))
    assert blob == entry['sha'] and semantic_equal and a == b + b'\n'
    rb = (OUT / 'source-msolve-README.md').read_bytes()
    re = next(e for e in provenance['files'] if e['local'] == 'comparison-README.md')
    rblob = hashlib.sha1(b'blob ' + str(len(rb)).encode() + b'\0' + rb).hexdigest()
    assert rblob == re['sha']
    assert rb.decode('utf-8-sig').rstrip() == (h/'comparison-README.md').read_text().rstrip()
    src = list(csv.DictReader(io.StringIO(b.decode())))
    nonmatch = [r for r in src if r['msolve_class'] != 'answer_set_matches']
    write('source-audit.json', {
        'source_url':entry['display_url'], 'source_commit':provenance['commit'],
        'retrieval':'GitHub connector read-only contents API; no git fetch',
        'local_source':'source-msolve-cases.csv', 'bytes':len(b),
        'source_sha256':hashlib.sha256(b).hexdigest(),
        'computed_git_blob_sha1':blob, 'recorded_git_blob_sha1':entry['sha'],
        'git_blob_matches':True, 'all_csv_rows_equal':semantic_equal,
        'H_copy_difference':'Exactly one additional LF at EOF; no field difference.',
        'README_verification':{'url':re['display_url'],'local':'source-msolve-README.md','sha256':hashlib.sha256(rb).hexdigest(),'computed_git_blob_sha1':rblob,'recorded_git_blob_sha1':re['sha'],'matches':True,'difference':'H copy omits original UTF-8 BOM and adds trailing LF; content agrees.'},
        'rows':len(src), 'msolve_nonmatch':len(nonmatch),
        'full_any_success':sum(int(r['geo_matched'])>0 for r in nonmatch),
        'full_all_success':sum(r['geo_matched']==r['geo_runs'] for r in nonmatch),
        'all_fail_ids':[r['id'] for r in nonmatch if int(r['geo_matched'])==0],
        'limitation':'Verifies archived aggregate and provenance, not fresh runs or a formal answer-set proof.'})
    rs = csvrows(OUT / 'development.csv')
    by_id = {r['id']:r for r in rs}
    ps = csvrows(OUT / 'development-predictions-all.csv')
    rules = {rule:{p['id']:p for p in ps if p['rule']==rule} for rule in RULE_NAMES}
    scores = {}
    for rule, p in rules.items():
        selected = [v for v in p.values() if v['local_judged']=='True']
        scores[rule] = {
            'classified':len(selected), 'correct':sum(v['local_correct']=='True' for v in selected),
            'observed_counts_on_classified':dict(Counter(v['observed_local'] for v in selected)),
            'full_transfer_confusion':{label:dict(Counter(full(by_id[v['id']]) for v in p.values() if v['local']==label)) for label in ('easy','hard','abstain')},
        }
    common = [id for id,p in rules['R1_mechanism'].items() if p['local_judged']=='True' and rules['R0_dimension'][id]['local_judged']=='True']
    same_coverage = [id for id,p in rules['R1_mechanism'].items() if p['local_judged']=='True']
    inversions = {}
    for ex,loc in [('costly','easy'),('fast','hard'),('enumeration_mismatch','easy')]:
        inversions[ex+'_'+loc] = [{'id':r['id'],'p':float(r['p']), 'exact_seconds':r['exact_total_seconds'], 'full_class':full(r),'full_median_seconds':float(r['geo_median_s']), 'R1':rules['R1_mechanism'][r['id']]['direction']} for r in rs if (r['observed_exact'],r['observed_local'])==(ex,loc)]
    cases = [json.loads(s) for s in (ROOT/'benchmarks/cases.jsonl').read_text().splitlines() if s.strip()]
    invariant_errors=[]
    for case in cases:
        dsl=case['dsl']; f=features(dsl); changed=copy.deepcopy(dsl)
        names={name:'Q24_VARIABLE_'+str(i) for i,name in enumerate(dsl['variables'])}
        class Rename(ast.NodeTransformer):
            def visit_Name(self,node):
                return ast.copy_location(ast.Name(id=names.get(node.id,node.id),ctx=node.ctx),node)
        def rename(expr):
            return ast.unparse(Rename().visit(ast.parse(str(expr),mode='eval')))
        if isinstance(dsl['variables'],dict):
            changed['variables']={names[n]:v for n,v in dsl['variables'].items()}
        else:
            changed['variables']=[names[n] for n in dsl['variables']]
        for c in changed.get('constructions',[]):c['expression']=rename(c['expression'])
        for c in changed.get('conditions',[]):
            for key in ('left','right','predicate'):
                if key in c:c[key]=rename(c[key])
        changed['target']=rename(changed['target'])
        g=features(changed)
        if any(predict(f,rule)!=predict(g,rule) for rule in RULE_NAMES):invariant_errors.append(case['id'])
    assert not invariant_errors
    write('development-audit.json',{
        'rules':scores, 'same_R1_coverage':{'n':len(same_coverage),**{rule:sum(rules[rule][id]['local_correct']=='True' for id in same_coverage) for rule in RULE_NAMES[:2]}},
        'both_classify':{'n':len(common),**{rule:sum(rules[rule][id]['local_correct']=='True' for id in common) for rule in RULE_NAMES[:2]}},
        'true_inversions':inversions,'AST_variable_renaming_cases':len(cases),'AST_variable_renaming_errors':invariant_errors,
        'full_transfer_definitions':{'easy':'all archived seeds match and median <=10s','hard':'any archived seed fails or median >=60s','intermediate':'otherwise'},
    })
    all_r1 = list(rules['R1_mechanism'].values())
    errors=[r for r in all_r1 if (r['local_judged']=='True' and r['local_correct']=='False') or (r['exact_judged']=='True' and r['exact_correct']=='False')]
    lines=['# R1 開発群の全誤予測', '', '中間への着地も外れ。未対応・error・not_run は費用の正誤を判定せず、末尾に別記。全候補R0–R2の外れは `development-errors-all.csv`、保留を含む全323問×3規則は `development-predictions-all.csv`。', '', '|ID|局所予告→観測|厳密側予告→観測|p|厳密側秒|', '|---|---|---|---:|---:|']
    for r in errors:
        lines.append(f"|{r['id']}|{r['local']} → {r['observed_local']}|{r['exact']} → {r['observed_exact']}|{r['p']}|{r['exact_total_seconds']}|")
    lines += ['', '## 費用分類を出したが、観測側を判定できない全件', '', '|ID|予告|観測側の状態|', '|---|---|---|']
    for r in all_r1:
        if r['exact'] in ('fast','costly','enumeration_mismatch') and r['exact_judged']=='False':
            lines.append(f"|{r['id']}|{r['exact']}|{r['observed_exact']}|")
    (OUT/'development-errors-R1.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'source121of122':True,'R1_error_rows':len(errors),'renaming_cases':len(cases),'renaming_errors':invariant_errors},ensure_ascii=False))


if __name__=='__main__':main()
