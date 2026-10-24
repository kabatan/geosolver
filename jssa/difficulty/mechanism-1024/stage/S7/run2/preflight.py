"""Read-only reference residual checks, never searches or refines a target."""
import json
import os
from pathlib import Path
import sys

OUT=Path(__file__).resolve().parent
M=json.loads((OUT/'pre-run-hashes.json').read_text())
os.environ.update(M['thread_environment'])
sys.path.insert(0,str(Path(M['scratch'])/'final/src'))
sys.path.insert(0,str(OUT.parent))
import helpers as h
from raw_switch import mapped_rows,t1
from mpmath import mp

rows=[]
for task in M['inputs']:
    item=json.loads(Path(task['stage1_input']).read_text())
    ref=json.loads(Path(task['reference_path']).read_text())
    details=json.loads(Path(task['sigma_details']).read_text())
    bundle=h.load_problem_bundle(h.GeometryProblem.model_validate(item['dsl']).engine_document())
    evaluator=h.build_ir_evaluator(bundle)
    mapping=mapped_rows(bundle,item,details['tangencies'])
    with mp.workdps(200),h.high_precision_mode():
        point=[mp.mpf(v) for v in ref['coordinates']]
        values=list(evaluator.evaluate_hp_residual(point,precision=200).residual_vector)
        assert len(values)==len(details['layouts']['raw'])
        for i,row in mapping.items():
            assert t1(bundle,point,row,200)==h.t1(bundle,point,row)
            values[i]=t1(bundle,point,row,200)
        assert all(mp.isfinite(v) for v in values)
    rows.append(dict(case_id=task['case_id'],raw_rows=len(values),t1_rows=sorted(mapping),
                     stage1_formula_match=True))
receipt=dict(status='passed',problems=len(rows),target_searches=0,target_refinements=0,rows=rows)
(OUT/'preflight.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
print('Read-only raw residual preflight passed:',len(rows),flush=True)
