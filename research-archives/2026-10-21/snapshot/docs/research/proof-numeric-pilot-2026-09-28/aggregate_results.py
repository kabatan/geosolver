"""Aggregate audited outcomes, separating primary and post-hoc diagnostics."""
import hashlib
import json
from pathlib import Path
import statistics
import sys

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
OUT=ROOT/'qwen/.runtime/proof_numeric_pilot_20260928'
sys.path.insert(0,str(ROOT))
from qwen.answer_check import parse_numeric


def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def cases(obj):return obj if isinstance(obj,list) else obj['cases']


def proof_rows(paths,folder,private):
    grades=[r for p in paths for r in cases(read(p))]
    assert len({r['case_id'] for r in grades})==len(grades)==len(private)
    output=[]
    for r in grades:
        cid=r['case_id'];path=folder/f'{cid}.json';raw=read(path);key=private[cid]
        assert r['file_sha256']==sha(path) and r['reviewed_full_response'] is True
        assert bool(r['complete'])==(r['score']==4)
        quote=r.get('evidence_quote',r.get('evidence'))
        if quote:assert quote in raw['raw_text'],(cid,'quote missing')
        output.append(dict(r,arm=key['arm'],job_id=key['job_id'],cap=key['cap'],
                           finish_reason=raw['finish_reason'],tokens=raw['tokens']))
    return output


def summarize_proof(rows):
    return {arm:{'complete':sum(r['complete'] and r['finish_reason']=='stop' for r in rows if r['arm']==arm),
                 'attempts':sum(r['arm']==arm for r in rows),
                 'censored':sum(r['finish_reason']=='length' for r in rows if r['arm']==arm),
                 'scores':[r['score'] for r in rows if r['arm']==arm]}
            for arm in ['base','sft']}


def main():
    assert read(OUT/'integrity-audit.json')['status']=='pass'
    all_key=read(OUT/'blind-private-key.json');pk={cid:r for cid,r in all_key.items() if r['split']=='proof'}
    proofs=proof_rows([HERE/'review/grades-sol.json',HERE/'review/grades-luna.json'],OUT/'blind',pk)
    for r in proofs:assert sha(OUT/'proof-review'/f"{r['case_id']}.json")==sha(OUT/'blind'/f"{r['case_id']}.json")
    extracted=read(OUT/'numeric-extractions.json');audit=read(OUT/'numeric-answer-audit.json')
    assert set(audit)=={r['case_id'] for r in extracted}
    expected={r['id']:r for r in read(OUT/'data/numeric-private-key.json')}
    numeric=[]
    for r in extracted:
        cid=r['case_id'];k=all_key[cid];a=audit[cid];raw=read(OUT/'blind'/f'{cid}.json')
        assert a['reviewed_final_commitment'] is True
        assert r['file_sha256']==sha(OUT/'blind'/f'{cid}.json')
        expr=a['parsed_expression'];want=float(expected[k['job_id']]['solver_value'])
        value=float(parse_numeric(expr)) if expr is not None else None
        err=abs(value-want) if value is not None else None
        rel=err/abs(want) if err is not None else None
        correct=err<=max(1e-4,abs(want)*1e-5) if err is not None else None
        censored=raw['finish_reason']=='length'
        numeric.append({'case_id':cid,'arm':k['arm'],'job_id':k['job_id'],'split':k['split'],
                        'expected':want,'committed_expression':expr,'value':value,'absolute_error':err,'relative_error':rel,
                        'numeric_correct':correct if not censored else None,'censored':censored,
                        'within_1_percent':(rel<=.01) if rel is not None and not censored else None,
                        'finish_reason':raw['finish_reason'],'tokens':raw['tokens'],'cap':k['cap'],
                        'answer_audit':a})
    summary={}
    for split in ['heldout','train_probe']:
        summary[split]={}
        for arm in ['base','sft']:
            rows=[r for r in numeric if r['arm']==arm and r['split']==split]
            rel=[r['relative_error'] for r in rows if r['relative_error'] is not None and not r['censored']]
            summary[split][arm]={'correct':sum(r['numeric_correct'] is True for r in rows),'n':len(rows),
                'censored':sum(r['censored'] for r in rows),'unparsed':sum(r['value'] is None and not r['censored'] for r in rows),
                'within_1_percent':sum(r['within_1_percent'] is True for r in rows),
                'median_relative_error_parsed_natural':statistics.median(rel) if rel else None}
    result={'primary_proof':summarize_proof(proofs),'numeric':summary,'proof_cases':proofs,'numeric_cases':numeric,
            'scope':'one AP01 configuration, one training seed; heldout numeric shapes are not unseen configurations',
            'exploratory_numeric_metric':'within 1 percent and median relative error are supplementary error diagnostics'}
    coordinate_grades=HERE/'review/grades-coordinate.json'
    if coordinate_grades.exists():
        rows=proof_rows([coordinate_grades],OUT/'coordinate-review',read(OUT/'coordinate-private-key.json'))
        result.update(coordinate_diagnostic=summarize_proof(rows),coordinate_cases=rows)
    (OUT/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if not k.endswith('_cases')},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
