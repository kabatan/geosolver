from pathlib import Path
import os
HERE=Path(__file__).resolve().parent
os.environ['MPLCONFIGDIR']=str(HERE/'mpl-cache')
os.environ['OPENBLAS_NUM_THREADS']='1'
os.environ['OMP_NUM_THREADS']='1'
import csv,json,hashlib,importlib.util,subprocess
import numpy as np
spec=importlib.util.spec_from_file_location('q21experiment',HERE/'experiment.py');e=importlib.util.module_from_spec(spec);spec.loader.exec_module(e)
from geosolver import GeometryProblem
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
cases=[json.loads(l) for l in (HERE/'cases.jsonl').open()]
summary=json.loads((HERE/'summary.json').read_text())
freeze=json.loads((HERE/'freeze.json').read_text())
assert all(e.digest(HERE/name)==value for name,value in freeze['files'].items())
assert e.digest(e.ROOT/'src/geosolver/engine/standard/search/scipy_multistart_backend.py')==freeze['src_backend_sha256']
checks={'frozen_files_unchanged':True,'all_300_embedded_residuals_ok':True,'raw_count':len(list((HERE/'raw').glob('*.json'))),'case_order_and_starts_consistent':True,'stored_endpoint_residual_matches':True,'ranks_threshold_disagreement':0,'S_count':0,'R_count':0,'S_with_wrong_native_or_independent_residual':0,'candidate_out_of_bounds':0,'preflight_only_native_rechecks':[]}
starts={}; total_eval=0; secs=[]; ratios=[]; matched=0
for c in cases:
    r=json.loads((HERE/'raw'/f"{c['id']}.json").read_text())
    assert len(r['records'])==3
    checks['ranks_threshold_disagreement']+=int(len(set(c['ranks'].values()))>1)
    assert np.max(np.abs(e.independent(c,c['planted'])[0]))<1e-12
    for z in r['records']:
        key=(c['k'],c['base'],z['seed'])
        if key in starts: assert z['start']==starts[key]
        else:starts[key]=z['start']
        err=max(abs(e.independent(c,z['x'])[0]))
        assert np.isclose(err,z['independent_max_res'],atol=1e-15,rtol=1e-9)
        expected=int(err<=1e-8 and z['max_res']<=1e-8 and z['guard'] and z['hard'] and np.all(np.isfinite(z['x'])) and 'out_of_bounds' not in z['tags'])
        assert expected==z['S']
        checks['S_count']+=z['S'];checks['R_count']+=z['R'];total_eval+=z['nfev'];secs.append(z['sec'])
        checks['candidate_out_of_bounds']+=int('out_of_bounds' in z['tags'])
    # Native residual and finite-difference Jacobian cross-check, no new search.
    if c['base']==0 and c['alpha'] in [1,2]:
        bundle=load_problem_bundle(GeometryProblem.model_validate(c['dsl']).engine_document()); ev=build_ir_evaluator(bundle)
        z=r['records'][0]; out=[]
        for label,x in [('start',z['start']),('end',z['x']),('planted',c['planted'])]:
            mp=dict(zip(c['dsl']['variables'],x)); xx=[mp[n] for n in bundle.var_names]
            native=np.array(ev.evaluate_float_residual(xx).residual_vector); independent,_=e.independent(c,x)
            assert np.allclose(native,independent,atol=1e-10,rtol=1e-8),(c['id'],label)
            out.append({'at':label,'native_vs_independent_maxdiff':float(np.max(np.abs(native-independent)))})
        x=np.array(c['planted']); _,jac=e.independent(c,x); cols=[]
        for j in range(c['d']):
            dx=np.zeros(c['d']);dx[j]=1e-6
            cols.append((e.independent(c,x+dx)[0]-e.independent(c,x-dx)[0])/2e-6)
        jerr=float(np.max(np.abs(jac-np.array(cols).T)))
        assert jerr<1e-7
        checks['preflight_only_native_rechecks'].append({'id':c['id'],'points':out,'analytic_jacobian_maxdiff':jerr})
assert checks['S_count']==summary['successes'] and checks['R_count']==summary['recoveries']
checks.update(total_evaluations=total_eval,local_seconds_sum=float(sum(secs)),local_seconds_median=float(np.median(secs)),local_seconds_max=float(max(secs)),paired_start_keys=len(starts),all_checks_passed=True)
(HERE/'verification.json').write_text(json.dumps(checks,indent=2)+'\n')
# Counting discrepancy audit: preregistered feature column is kept unchanged.
cs=[json.loads(l) for l in (e.ROOT/'benchmarks/cases.jsonl').open()]
feats={r['case_id']:r for r in csv.DictReader((e.ROOT/'jssa/difficulty/ghost-1023/human_feat.csv').open())}
metadata=[]
for c in cs:
    cond=c['dsl']['conditions']; nf=int(feats[c['id']]['n_eq'])
    explicit=sum(x.get('operator')=='=' for x in cond); predicates=sum('predicate' in x for x in cond)
    metadata.append({'id':c['id'],'feature_n_eq':nf,'explicit_equals':explicit,'predicate_count':predicates,'matches_equals_plus_predicates':nf==explicit+predicates})
(HERE/'condition-count-audit.json').write_text(json.dumps({'interpretation':'post hoc audit; no substitution in registered census','all':len(metadata),'matches_equals_plus_predicates':sum(x['matches_equals_plus_predicates'] for x in metadata),'rows':metadata},indent=2)+'\n')
# Preserve the 88-case background from the existing Git object; no checkout/fetch.
archive={}
for filename in ['README.md','freeze.json','cases.jsonl','derivations.json']:
    blob=subprocess.check_output(['git','show',f'23ef40a:benchmarks/generated-88/{filename}'],cwd=e.ROOT)
    archive[filename]={'bytes':len(blob),'sha256':hashlib.sha256(blob).hexdigest()}
    if filename=='cases.jsonl':
        archived=[json.loads(l) for l in blob.decode().splitlines()]
    if filename=='derivations.json':
        der=json.loads(blob);archive['family_counts']={f:sum(x['family']==f for x in der) for f in sorted({x['family'] for x in der})}
    if filename in ['README.md','freeze.json']:(HERE/f'generated88-{filename}').write_bytes(blob)
archive.update(git_object='23ef40a',case_count=len(archived),original_generator_source_available=False,full_solver_264_of_264_recomputed=False)
(HERE/'generated88-audit.json').write_text(json.dumps(archive,indent=2)+'\n')
print(json.dumps({k:v for k,v in checks.items() if k!='preflight_only_native_rechecks'},indent=2))
print('Condition feature matches equals + predicate:',sum(x['matches_equals_plus_predicates'] for x in metadata),'/',len(metadata))
