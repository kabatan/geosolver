"""Supplement only after real-problem table completion. No timing benchmark."""
import csv
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import sympy as sp

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'families'))
from generate import FAMILIES,write_one


def event(**obj):
    obj=dict(utc=datetime.now(timezone.utc).isoformat(),**obj)
    with (HERE/'family-progress.jsonl').open('a') as f:
        f.write(json.dumps(obj,ensure_ascii=False)+'\n')
    print(json.dumps(obj,ensure_ascii=False),flush=True)


def run(inp,mode,out,reuse=False):
    if out.exists():
        if not reuse:
            raise RuntimeError('No implicit rerun: '+str(out))
        return json.loads(out.read_text())
    cmd=[sys.executable,'-B',str(HERE/'degree_worker.py'),str(inp),mode,str(out)]
    if mode=='strong': cmd+=['--eliminate']
    p=subprocess.Popen(cmd,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,start_new_session=True)
    try:
        _,err=p.communicate(timeout=55)
    except subprocess.TimeoutExpired:
        os.killpg(p.pid,signal.SIGKILL)
        _,err=p.communicate()
    rec=json.loads(out.read_text()) if out.exists() else {}
    if rec.get('status') in (None,'PENDING','CAS_RUNNING'):
        rec.update(status='WORKER_LIMIT',reason=err.decode(errors='replace')[-500:])
        out.write_text(json.dumps(rec,ensure_ascii=False,indent=2)+'\n')
    return rec


def main():
    completed=[json.loads(l) for l in (HERE/'progress.jsonl').read_text().splitlines()
               if '実問題表完了' in l]
    assert completed and (HERE/'answer.md').exists() and (HERE/'real-problems.csv').exists()
    resume='--resume' in sys.argv
    assert resume or not (HERE/'family-progress.jsonl').exists(),'No implicit rerun'
    event(event='family_stage_resumed' if resume else 'family_stage_started',
          real_table_completed=completed[-1]['utc'],
          reason='Reuse saved CAS outputs; polynomial equality now normalizes coefficient domain' if resume else '')
    rows=[]
    T=sp.Symbol('T')
    for family in FAMILIES:
        for k in range(1,9):
            inp,cert,features=write_one(family,k,reuse=resume)
            row=dict(family=family,k=k,depth=features['depth'],point_depth=features['point_depth'],
                     dsl_variables=1,dsl_path=str(inp.relative_to(HERE)),
                     selected_real_target_count=1,finite_target_status='PROVED_EXACTLY',
                     t_minimal_polynomial_degree=cert['degree'],
                     t_minimal_polynomial_path=str(inp.with_name(f'k{k}-minpoly.json').relative_to(HERE)),
                     t_minimal_polynomial_method='exact_recurrence_and_field_degree_proof')
            elapsed=0
            stop=False
            for mode in ['base','strong']:
                out=HERE/'families'/family/f'k{k}.{mode}.json'
                rec=run(inp,mode,out,reuse=resume)
                for key in ['status','degree','degree_label','dimension','nvars','neqs','translation_wall_s','cas_wall_s','reason']:
                    row[mode+'_'+key]=rec.get(key,'次数不明' if key=='degree_label' else '')
                elapsed+=rec.get('cas_wall_s',0)
                if rec.get('degree') is not None:
                    assert rec['dimension']==0
                    assert rec['degree']==cert['relaxed_complex_configuration_count'],(family,k,mode,rec)
                if rec['status'] not in ['OK_ZERO_DIMENSIONAL']:
                    stop=True
                if mode=='strong':
                    row['t_elimination_check']=rec.get('elimination_status','NOT_AVAILABLE')
                    if rec.get('elimination_polynomials'):
                        variable=sp.Symbol(rec['target_singular_variable'])
                        polys=[sp.Poly(sp.sympify(s.replace('^','**'),locals={str(variable):variable}),variable)
                               for s in rec['elimination_polynomials'] if s!='0']
                        gcd=polys[0]
                        for poly in polys[1:]:gcd=sp.gcd(gcd,poly)
                        observed=sp.Poly(gcd.sqf_part().monic().as_expr().subs(variable,T),T)
                        expected=sp.Poly(sp.sympify(cert['minimal_polynomial'],locals={'T':T}),T).monic()
                        assert observed.set_domain(sp.QQ)==expected.set_domain(sp.QQ),(family,k,str(observed),str(expected))
                        row['t_elimination_check']='MATCHES_PROVED_MINIMAL_POLYNOMIAL'
                    if rec.get('elimination_status'):
                        stop=True
            row['combined_cas_budget_seconds']=elapsed
            row['continue_to_next_k']=not stop and elapsed<=30 and k<8
            row['stop_reason']='RESOURCE_OR_TRANSLATION_LIMIT' if stop else 'COMBINED_CAS_OVER_30S' if elapsed>30 else 'K_MAX_8' if k==8 else ''
            rows.append(row)
            with (HERE/'degrees.csv').open('w',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=list(rows[0]))
                writer.writeheader();writer.writerows(rows)
            event(event='family_k_complete',family=family,k=k,base=row['base_status'],strong=row['strong_status'],
                  target_degree=cert['degree'],elimination=row['t_elimination_check'],stop=row['stop_reason'])
            if stop or elapsed>30:
                break
    event(event='family_stage_complete',rows=len(rows))


if __name__=='__main__':
    main()
