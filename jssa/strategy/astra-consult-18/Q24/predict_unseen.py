"""Apply the already frozen rule to Q18-pass DSL ASTs only.

No expression evaluation, numerical coordinates, solver, references, or results.
Audit fields retained are exactly id/verdict/dsl_file/dsl_sha256.
"""
import csv
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from static_features import features, predict

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]


def sha(b):return hashlib.sha256(b).hexdigest()


def main():
    lock=json.loads((OUT/'rule-lock.json').read_text())
    for name,info in lock['files'].items():
        assert sha((OUT/name).read_bytes())==info['sha256'], 'Frozen file changed: '+name
    assert lock['stage']=='before_reading_unseen_audit_or_DSL' and lock['rule']=='R1_mechanism'
    audit=ROOT/'jssa/difficulty/unseen-1983/audit/audit.csv'
    with audit.open() as f:
        selected=[{k:r[k] for k in ('id','verdict','dsl_file','dsl_sha256')}
                  for r in csv.DictReader(f) if r['verdict']=='合格']
    assert len(selected)==26 and len({r['id'] for r in selected})==26
    dev_ids={r['id'] for r in csv.DictReader((OUT/'development.csv').open())}
    assert not dev_ids.intersection(r['id'] for r in selected)
    input_dir=(ROOT/'jssa/difficulty/unseen-1983/dsl').resolve()
    rows=[];inputs=[]
    for r in sorted(selected,key=lambda r:r['id']):
        assert re.fullmatch(r'[A-Za-z0-9_-]+',r['id'])
        p=(audit.parent/r['dsl_file']).resolve()
        assert p.parent==input_dir and p.name==r['id']+'.json'
        b=p.read_bytes()
        assert sha(b)==r['dsl_sha256'], 'Q18 input changed: '+r['id']
        dsl=json.loads(b)
        assert set(dsl)<= {'id','variables','constructions','conditions','target'}
        assert dsl['id']==r['id']
        f=features(dsl); prediction=predict(f,'R1_mechanism')
        rows.append({'id':r['id'],**f,**prediction,
                     'full_solver_secondary':prediction['local'],
                     'dsl_sha256':sha(b)})
        inputs.append({'id':r['id'],'path':str(p.relative_to(ROOT)), 'bytes':len(b),'sha256':sha(b)})
    names=['unseen26-predictions.csv','unseen26-input-manifest.json','unseen26-summary.json','preregistration.md']
    assert not any((OUT/name).exists() for name in names),'Refuse to overwrite predictions.'
    with (OUT/names[0]).open('w',newline='') as f:
        w=csv.DictWriter(f,list(rows[0]));w.writeheader()
        w.writerows({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in r.items()} for r in rows)
    manifest={'utc':datetime.now(timezone.utc).isoformat(),
              'rule_lock_sha256':sha((OUT/'rule-lock.json').read_bytes()),
              'audit':{'path':str(audit.relative_to(ROOT)),'sha256':sha(audit.read_bytes()),'selected_columns':['id','verdict','dsl_file','dsl_sha256']},
              'selection':selected,'inputs':inputs,
              'operations':'JSON/CSV parsing, AST traversal, integer counts, support matching, categorical rule; no numeric evaluation',
              'results_accessed':False}
    (OUT/names[1]).write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    summary={key:dict(Counter(r[key] for r in rows)) for key in ('local','exact','direction','full_solver_secondary')}
    summary['n']=len(rows)
    (OUT/names[2]).write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    loc={'easy':'高成功','hard':'低成功','abstain':'保留','no_search':'探索不要'}
    ex={'fast':'軽い','costly':'重い','enumeration_mismatch':'列挙不適合','out_of_scope':'適用範囲外','abstain':'保留','no_search':'探索不要'}
    full={'easy':'軽い','hard':'困難','abstain':'保留','no_search':'探索不要'}
    direction={'none':'なし','exact_costly_local_easy':'厳密重・局所高','exact_fast_local_hard':'厳密軽・局所低','enumeration_mismatch_local_easy':'列挙不適合・局所高'}
    lines=['', '---', '', '## 8. 固定規則を入力だけへ適用した全26問の予告', '',
           '以下だけを規則固定後に追加した。結果を見て規則・閾値・対象を変更していない。入力のQ18ハッシュは全26問で一致。nLは非線形演算数、hLはその深さ、hHは危険演算の深さ、Tは変数依存の接条件数、uは等式依存マッチングで覆えない変数数。完成solver欄は本文の弱い移行仮説。', '',
           '|ID|d|nL|hL|hH|T|u|局所|厳密側|完成solver副予告|方向|',
           '|---|---:|---:|---:|---:|---:|---:|---|---|---|---|']
    for r in rows:
        lines.append('|'+ '|'.join(str(x) for x in [r['id'],r['d'],r['nonlinear_gates'],r['nonlinear_depth'],r['hazard_depth'],r['active_tangent'],r['unmatched_variables'],loc[r['local']],ex[r['exact']],full[r['full_solver_secondary']],direction[r['direction']]])+'|')
    lines += ['', '入力・計算した全構文特徴・SHA-256は `unseen26-input-manifest.json` と `unseen26-predictions.csv`。', '',
              '局所分類：'+ '、'.join(f'{loc[k]} {v}問' for k,v in summary['local'].items())+'。',
              '厳密側分類：'+ '、'.join(f'{ex[k]} {v}問' for k,v in summary['exact'].items())+'。',
              '方向分類：'+ '、'.join(f'{direction[k]} {v}問' for k,v in summary['direction'].items())+'。', '',
              'この表は予告であり検証結果ではない。各方向3問以上という固定基準を満たす予告が出なければ、当該26問だけで双方向の能力を示すことはできない。']
    core=(OUT/'preregistration-core.md').read_text()
    (OUT/'preregistration.md').write_text(core+'\n'.join(lines)+'\n')
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
