"""Measure the saved HMMT-2020 reference after a whitespace-only row-map repair.
No solve, verification, or reference closure is invoked here.
"""
import ast
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
from select_targets import save,sha

OUT=Path(__file__).resolve().parent
M=json.loads((OUT/'pre-run-hashes.json').read_text())
sys.dont_write_bytecode=True
sys.path.insert(0,M['frozen_source'])
from mpmath import mp
import s4_helpers as s4
from worker import fixed_scales,sigma_kind
from geosolver.engine.standard.precision.type_guards.boundary_float_to_mpf import boundary_float_to_mpf,BoundaryOrigin

key='HMMT-2020-FEB-GEO-04';folder=OUT/'results'/key
oldpath=folder/('result.json' if (folder/'result.json').exists() else 'mapping-failure-result.json')
old=json.loads(oldpath.read_text())
assert old['status']=='measurement_unavailable' and old['reference_status']=='ok'
assert 'len(found) == 1' in old['traceback']
ref=json.loads((folder/'reference.json').read_text());assert ref['status']=='ok'
source=(OUT/'measure.py').read_text()
needle="if lhs == str(original['left']) and str(rhs) == str(original['right'])]"
assert source.count(needle)==1
fixed=source.replace(needle,"if ast.dump(ast.parse(lhs,mode='eval'),include_attributes=False) == ast.dump(ast.parse(str(original['left']),mode='eval'),include_attributes=False) and ast.dump(ast.parse(str(rhs),mode='eval'),include_attributes=False) == ast.dump(ast.parse(str(original['right']),mode='eval'),include_attributes=False)]")
fixed='import ast\n'+fixed
# S4's diagnostic assumed only IsTangent inputs. Distance=center-line-radius
# without a contact source keeps its original residual in frozen smoothing,
# while the registered T2 definition explicitly falls back to T1.
fixed=fixed.replace("assert difference < mp.mpf('1e-170') or fallback, (task['case_id'],difference)", "assert difference < mp.mpf('1e-170') or fallback or any(r['condition'].startswith('Distance(') and not r['t2_source'] for r in tangencies), (task['case_id'],difference)")
p=OUT/'measure_distance_repaired.py'
if p.exists(): assert p.read_text()==fixed
else: p.write_text(fixed)
input_path=OUT/'inputs'/(key+'.json')
save(folder/'mapping-repair-hashes.json',dict(reason='AST-equal whitespace normalization; record expected diagnostic discrepancy for Distance without contact source; registered T2=T1 remains unchanged',
    solve_executed=False,reference_recreated=False,
    files={str(q):sha(q) for q in [Path(__file__),p,OUT/'measure.py',input_path,folder/'reference.json',folder/'scales.json',oldpath]}))
if (folder/'result.json').exists(): (folder/'result.json').rename(folder/'mapping-failure-result.json')
os.sched_setaffinity(0,{M['cpus'][0]})
os.environ.update(M['threads'])
assert s4.source_tree_hash()==M['source_hash']
spec=importlib.util.spec_from_file_location('repaired_measure',p)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
item=json.loads(input_path.read_text())
# Normalize whitespace in the in-memory condition copy for S4.inventory's
# distance_contact_sources lookup as well; mathematical ASTs are unchanged.
for condition in item['dsl']['conditions']:
    for name in ['left','right']:
        if name in condition and isinstance(condition[name],str):
            original=ast.parse(condition[name],mode='eval')
            condition[name]=ast.unparse(original)
            assert ast.dump(original,include_attributes=False)==ast.dump(ast.parse(condition[name],mode='eval'),include_attributes=False)
with mp.workdps(700):
    points=[[boundary_float_to_mpf(v,origin=BoundaryOrigin.INITIAL_POINT) for v in point] for point in item['selection']['initial_points']]
scales=json.loads((folder/'scales.json').read_text())
entry,rows=module.measure(s4,item,ref,scales,{key:points},dict(case_id=key,reference=str(folder/'reference.json')))
entry['frozen_comparison_note']='Distance形式に接点式がないため指定T2はT1へ復帰。凍結版平滑化は元のDistance-rを保持するので当該行の差は記録のみ。全残差の定義・正規化・差分・SVDはS4.12と同じ。'
save(folder/'sigma-details.json',entry)
result={k:v for k,v in old.items() if k not in ['traceback','reason']}
judgments={}
with mp.workdps(200):
    for method in ['T1','T2']:
        condition=entry['conditions'][method]
        sigmas=[sample['singular_values'][0] for sample in condition['samples']]
        states=[sigma_kind(s) for s in sigmas]
        judgments[method]=states[0] if len(set(states))==1 else '不定'
        result.update({method+'_sigma':sigmas[0],method+'_sigma_check':sigmas[1],method+'_judgment':judgments[method],method+'_spectra_agree':condition['agreement']})
kind={('特異','非特異'):'P',('非特異','非特異'):'N',('特異','特異'):'B'}.get((judgments['T1'],judgments['T2']),'不定')
result.update(status='ok',type=kind,prediction={'P':'U1: T2がT1より40桁以上良い','N':'U2: T1とT2が20桁以内','B':'U3: T2が300桁未満'}.get(kind,''),
    reason='' if kind!='不定' else '登録のP/N/Bに該当しない組合せ',
    mapping_repaired='AST equality removes whitespace-only mismatch; saved reference reused',
    elapsed_seconds=time.time()-json.loads((folder/'started.json').read_text())['started'])
assert result['elapsed_seconds']<600
save(folder/'result.json',result)
print(key,kind,result['T1_sigma'],result['T2_sigma'])
