"""Build a geometry-first revision from the imported v1 selection metadata."""
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parent
META=ROOT/'authoring/v1_metadata.json'
DECISIONS={'main':'主学習候補','probe':'性質の確認用','defer':'再設計待ち','holdout':'評価留保','exclude':'不採用'}


def read_cards():
    old=json.loads(META.read_text())['cards']
    cards=[]
    for p in sorted((ROOT/'authoring').glob('*_revision.json')):
        rows=json.loads(p.read_text())
        for c in rows:
            prev=old[c['id']]
            c['source']=prev['source']
            c['legacy_structural_group']=prev['structural_group']
            c['previous']={k:prev.get(k) for k in ['title_ja','split_recommendation','problem_template_ja','numeric_queries','free_parameters']}
            c['authoring_file']=str(p.relative_to(ROOT))
            cards.append(c)
    amendments=ROOT/'authoring/curation.json'
    overrides=json.loads(amendments.read_text()) if amendments.exists() else {}
    for c in cards:c.update(overrides.get(c['id'],{}))
    def order(c):
        prefix=re.match(r'[A-Z]+',c['id']).group()
        return list(DECISIONS).index(c['decision']),{'H':0,'HX':1,'DA':2,'DB':3,'EV':4}[prefix],c['id']
    return sorted(cards,key=order),old


def validate(cards,old,allow_partial=False):
    errors=[]
    ids=[c['id'] for c in cards]
    if len(ids)!=len(set(ids)):errors.append('duplicate ID')
    missing=sorted(set(old)-set(ids))
    if missing and not allow_partial:errors.append('unreviewed IDs: '+','.join(missing))
    for c in cards:
        cid=c['id']
        for key in ['title_ja','diagnosis_ja','change_ja','why_geometry_helps_ja','shortcut_risk_ja','feasibility','review_notes_ja']:
            if key not in c:errors.append(f'{cid}: missing {key}')
        if c['decision'] not in DECISIONS:errors.append(f'{cid}: decision invalid')
        if c['decision'] in {'main','probe'}:
            for key in ['problem_ja','givens','query','answer_exact','geometry_solution_ja','arithmetic_ja','parameter_family_ja']:
                if not c.get(key):errors.append(f'{cid}: missing usable {key}')
            if c['feasibility']['status']!='verified':errors.append(f'{cid}: accepted without checked witness')
            if not c['feasibility'].get('witness'):errors.append(f'{cid}: accepted without witness data')
            if c['feasibility'].get('solution_status') in {None,'unverified'}:
                errors.append(f'{cid}: no stated basis for short solution')
            if re.search(r'Humpty|Dumpty|ハンプティ|ダンプティ|Sharky',c.get('problem_ja',''),re.I):
                errors.append(f'{cid}: target name in problem')
            if cid in {'H10','H11','EV01','EV02'}:errors.append(f'{cid}: reserved evaluation in learning')
    return errors,missing


def markdown(cards,stats):
    out=['# 幾何的な着想から設計し直した求値問題 v2','',
         '研究者レビュー用。解法欄は学習入力へ含めない。v1の全件について、与条件・問い・残る計算を見直した。','',
         '| ID | 改訂後の題材 | 判断 |','|---|---|---|']
    for c in cards:out.append(f"| [{c['id']}](#{c['id'].lower()}) | {c['title_ja']} | {DECISIONS[c['decision']]} |")
    for c in cards:
        out+=['',f"## {c['id']}",'',f"**{c['title_ja']}** — {DECISIONS[c['decision']]}",'',
              '**前版の問題点：** '+c['diagnosis_ja'],'','**変更：** '+c['change_ja']]
        if c.get('problem_ja'):
            out+=['','### 改訂問題','',c['problem_ja'],'',f"**答え：** {c['answer_exact']}",'','### 幾何的な解法','']
            out += [f'{i+1}. {x}' for i,x in enumerate(c['geometry_solution_ja'])]
            out+=['','### 着想後に残る計算','']+[f'- {x}' for x in c['arithmetic_ja']]
        out+=['','**省ける計算：** '+c['why_geometry_helps_ja'],'','**安易な正解への注意：** '+c['shortcut_risk_ja']]
        if c.get('parameter_family_ja'):out+=['','**数値を変える方針：** '+c['parameter_family_ja']]
        out+=['','**検証：** '+c['feasibility']['method_ja']]
        out += ['','### 確認事項','']+[f'- {x}' for x in c['review_notes_ja']]
        out+=['','### 出典','']+[f"- [{s['title']}]({s['url']}) — {s['locator']}" for s in c['source']]
    return '\n'.join(out)+'\n'


def main():
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('--allow-partial',action='store_true');args=ap.parse_args()
    cards,old=read_cards();errors,missing=validate(cards,old,args.allow_partial)
    if errors:raise SystemExit('\n'.join(errors))
    main_cards=[c for c in cards if c['decision']=='main']
    accepted=[c for c in cards if c['decision'] in {'main','probe'}]
    old_train={c['id'] for c in old.values() if c['split_recommendation']=='train'}
    stats={'total':len(cards),'decisions':dict(Counter(c['decision'] for c in cards)),
           'legacy_training_count':sum(c['split_recommendation']=='train' for c in old.values()),
           'all_legacy_training_configurations_revised':old_train=={c['id'] for c in accepted},
           'accepted_legacy_structural_groups':len({c['legacy_structural_group'] for c in accepted}),
           'main_legacy_structural_groups':len(set(c['legacy_structural_group'] for c in main_cards)),
           'published_relation_not_reproved':[c['id'] for c in cards
                 if c['decision'] in {'main','probe'} and c['feasibility']['solution_status']=='source_claim_only'],
           'missing_ids':missing}
    blob=json.dumps(cards,ensure_ascii=False,indent=2)+'\n'
    digest=hashlib.sha256(blob.encode()).hexdigest()
    (ROOT/'revisions.json').write_text(blob)
    for role,filename in [('main','training_problems.jsonl'),('probe','probe_problems.jsonl')]:
        rows=[{'id':c['id'],'problem':c['problem_ja'],'answer_exact':c['answer_exact']} for c in cards if c['decision']==role]
        (ROOT/filename).write_text(''.join(json.dumps(c,ensure_ascii=False)+'\n' for c in rows))
    (ROOT/'catalogue.md').write_text(markdown(cards,stats))
    with (ROOT/'review.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(['ID','題材','改訂判断','計算の軽さ','幾何の実益','採否','コメント'])
        for c in cards:w.writerow([c['id'],c['title_ja'],DECISIONS[c['decision']],'','','',''])
    report={'errors':errors,'stats':stats,'sha256':digest,
            'v1_sha256':json.loads(META.read_text())['provenance']['source_sha256'],
            'scope':'schema / full coverage / learner export; mathematical checks run separately'}
    (ROOT/'validation_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    template=ROOT/'review_template.html'
    if template.exists():
        data=json.dumps({'cards':cards,'stats':stats,'sha256':digest},ensure_ascii=False).replace('<','\\u003c')
        (ROOT/'review.html').write_text(template.read_text().replace('/*DATASET*/null',data))
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
