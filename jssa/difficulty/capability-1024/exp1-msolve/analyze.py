"""Summarize fixed campaign and reuse Q30 tables without solver executions."""
import collections,csv,hashlib,json,pathlib,statistics,subprocess
OUT=pathlib.Path(__file__).resolve().parent
ROOT=OUT.parents[3]; RAW=pathlib.Path('/tmp/q6e1-run/raw')
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def med(xs):return statistics.median(xs) if xs else None
def classify(m,receipt,log):
 st=m.get('solve_status','')
 if m.get('status')=='unsupported':return '変換不能',m.get('reason','')
 if m.get('nvars')==0:return '変換不能','未知数0の入力を固定コードがmsolveへ渡し、msolveが異常終了（error:-11）'
 if 'timeout' in st or receipt.get('outer_timeout'):return '時間切れ',st or 'outer_timeout'
 if any(w in (m.get('log','')+log).lower() for w in ['out of memory','cannot allocate','memoryerror','bad_alloc','failed to allocate']):return 'メモリ不足',st
 if st=='positive_dimensional':return '有限でない','多項式緩和の解集合が有限でない。Singular消去は別欄'
 if m.get('answer_set_matches') is True and m.get('filter_status')=='ok':return '正しい答え集合',''
 if st.startswith('error:'):
  return '不正解','答えなし・異常終了（'+st+'）。原因未確定でメモリ不足とは断定しない'
 if st in ('ok','no_complex_solution'):return '不正解','固定の最終検証・集合照合で参照答え集合と一致しない'
 raise RuntimeError('Unclassified outcome; inspect before report: '+str((m,receipt,log[-1000:])))
def main():
 pre=read(OUT/'preflight.json');execution=read(OUT/'execution.json')
 cases=[json.loads(s) for s in pathlib.Path('/tmp/q6e1-run/benchmarks/cases.jsonl').read_text().splitlines()]
 geo={};missing_total=0
 for g in 'ab':
  p=ROOT/'jssa/difficulty/unseen-2'/g/('per-run.csv' if g=='a' else 'results.csv')
  assert sha(p)==pre['input_sha256'][str(p.relative_to(ROOT))]
  for r in csv.DictReader(p.open()):geo.setdefault(r['case_id'],[]).append(r)
 rows=[]
 for c in cases:
  cid=c['id'];d=RAW/'msolve'/cid;m=read(d/'result.json');receipt=read(d/'receipt.json')
  assert receipt['result_present'];assert receipt['returncode']==0
  category,reason=classify(m,receipt,(d/'driver.log').read_text())
  gr=geo[cid];assert len(gr)==5;assert sorted(int(r['seed']) for r in gr)==list(range(301,306))
  missing=sum(r.get('record_missing',r.get('missing_record'))=='True' for r in gr);missing_total+=missing
  correct=[r for r in gr if r['matched']=='True' and r.get('record_missing',r.get('missing_record'))!='True']
  efile=RAW/'elim'/cid/'result.json';e=read(efile) if efile.exists() else {}
  if category=='有限でない':assert efile.exists(),cid
  solve=m.get('solve_seconds');elim=e.get('solve_seconds')
  rows.append({'case_id':cid,'group':'a' if cid.startswith('AIME') else 'b','msolve_category':category,'solve_seconds':None if solve is None else solve+(elim or 0),'msolve_solve_seconds':solve,'translate_seconds':m.get('translate_seconds'),'filter_seconds':m.get('filter_seconds'),'msolve_total_seconds':sum(m.get(k,0) for k in ['translate_seconds','solve_seconds','filter_seconds']) if solve is not None else None,'process_wall_seconds':receipt['process_wall_seconds'],'msolve_status':m.get('solve_status',m.get('status')),'msolve_answers':json.dumps(m.get('answers',[])),'reference':json.dumps(m.get('reference',[])),'dsl_vars':m.get('dsl_vars'),'polynomial_vars':m.get('nvars'),'polynomial_equations':m.get('neqs'),'peak_tree_rss_bytes':receipt['peak_tree_rss_bytes'],'singular_status':e.get('solve_status',e.get('status','')),'singular_reason':e.get('reason',''),'singular_solve_seconds':elim,'singular_candidates':json.dumps(e.get('candidate_values',[])),'singular_reference_among_candidates':e.get('reference_among_candidates','') if e.get('solve_status','').startswith('univariate:') else '','geosolver_correct_out_of_5':len(correct),'geosolver_missing_out_of_5':missing,'geosolver_correct_seconds_median':med([float(r['wall_seconds']) for r in correct]),'reason':reason})
 with (OUT/'per-problem.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 counts=collections.Counter(r['msolve_category'] for r in rows)
 both=[r for r in rows if r['msolve_category']=='正しい答え集合' and r['geosolver_correct_out_of_5']>0]
 noanswer={'時間切れ','メモリ不足','有限でない','変換不能'}
 e2=[r for r in rows if (r['msolve_category'] in noanswer or r['msolve_status'].startswith('error:')) and r['geosolver_correct_out_of_5']>=3]
 e2_core=[r for r in e2 if r['msolve_category']!='変換不能']
 sm=med([r['msolve_solve_seconds'] for r in both]);gm=med([r['geosolver_correct_seconds_median'] for r in both])
 loads=[json.loads(s) for s in (OUT/'load.jsonl').read_text().splitlines()]
 summary={'problems':len(rows),'category_counts':dict(counts),'geosolver_correct_runs':sum(r['geosolver_correct_out_of_5'] for r in rows),'geosolver_missing_runs':missing_total,'geosolver_at_least_3_of_5':sum(r['geosolver_correct_out_of_5']>=3 for r in rows),'E1':{'prediction':'correct answer sets <=26/34','observed':counts['正しい答え集合'],'met':counts['正しい答え集合']<=26},'E2':{'prediction':'no answer and GeoSolver >=3/5, >=6 problems','observed':len(e2),'met':len(e2)>=6,'case_ids':[r['case_id'] for r in e2],'excluding_conversion_failures':len(e2_core),'excluding_conversion_failure_case_ids':[r['case_id'] for r in e2_core]},'E3':{'prediction':'median msolve solve time < median GeoSolver correct time','intersection_problems':len(both),'msolve_solve_median_seconds':sm,'geosolver_per_problem_correct_median_seconds':gm,'met':sm<gm,'msolve_total_median_seconds':med([r['msolve_total_seconds'] for r in both]),'msolve_process_wall_median_seconds':med([r['process_wall_seconds'] for r in both]),'case_ids':[r['case_id'] for r in both]},'load_1min':{'min':min(x['load'][0] for x in loads),'max':max(x['load'][0] for x in loads),'median':med([x['load'][0] for x in loads]),'samples':len(loads)},'msolve_missing_records':34-len(rows),'singular_elimination_results':[{'case_id':r['case_id'],'status':r['singular_status'],'candidate_values':r['singular_candidates'],'reference_among_candidates':r['singular_reference_among_candidates']} for r in rows if r['singular_status']]}
 (OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
 # Audit immutability, execution limits and raw files without copying large logs.
 code=pathlib.Path('/tmp/q6e1-run/benchmarks/exact_comparison')
 for name,h in pre['exact_code_sha256'].items():assert sha(code/name)==h
 for rel,h in pre['input_sha256'].items():assert sha(ROOT/rel)==h
 assert not subprocess.check_output(['git','-C','/tmp/q6e1-clean','status','--porcelain']).strip()
 for d in RAW.glob('*/*'):
  if not d.is_dir():continue
  limits=d/'limits.txt'
  if limits.exists():assert '8589934592           8589934592' in limits.read_text()
 inventory=[]
 for p in sorted(RAW.rglob('*')):
  if p.is_file():inventory.append({'path':str(p),'bytes':p.stat().st_size,'sha256':sha(p)})
 (OUT/'raw-manifest.json').write_text(json.dumps({'external_raw_directory':str(RAW),'files':inventory,'over_5MB':[r for r in inventory if r['bytes']>5_000_000]},indent=2)+'\n')
 (OUT/'validation.json').write_text(json.dumps({'problems':34,'msolve_result_records':len(rows),'geosolver_runs':170,'geosolver_missing':missing_total,'source_and_checkout_rechecked':True,'converter_unchanged':True,'inputs_unchanged':True,'recorded_address_space_limit_bytes':8<<30,'automatic_retries':0,'max_repository_file_bytes':max(p.stat().st_size for p in OUT.rglob('*') if p.is_file())},indent=2)+'\n')
 print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
