"""Q26 read-only joins and descriptive statistics. No solver imports or evaluation."""
import csv,json,re,hashlib,datetime,statistics,subprocess,io
from pathlib import Path
ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[2]
DATE='2026-10-23'
LIMIT=5_000_000
FINAL_SOURCE='jssa/results/stage-profile-20261023/per-case.csv'
def repo_url(path):
    """Pin local evidence to its last committed revision; no network or git writes."""
    revision=subprocess.check_output(['git','log','-1','--format=%H','--',path],cwd=REPO,text=True).strip()
    assert re.fullmatch(r'[0-9a-f]{40}',revision),path
    committed=subprocess.check_output(['git','show',f'{revision}:{path}'],cwd=REPO)
    assert committed==(REPO/path).read_bytes(),f'uncommitted input: {path}'
    return f'https://github.com/kabatan/geosolver/blob/{revision}/{path}'
LOCAL_URLS={p:repo_url(p) for p in [FINAL_SOURCE,'jssa/difficulty/ghost-1023/human_feat.csv','jssa/difficulty/minima/basins-323.csv','jssa/difficulty/new2026-predict/predictions.csv','jssa/difficulty/new2026-predict/outcomes.csv','jssa/difficulty/unseen-1983/manifest.json','benchmarks/cases.jsonl','jssa/difficulty/new2026/cases.jsonl']}
COMPS=['aime_2025','hmmt_feb_2025','aime_2026','hmmt_feb_2026']
def readcsv(path):
    with path.open(newline='') as f:return list(csv.DictReader(f))
def writecsv(name,rows):
    if not rows:return
    fields=list(dict.fromkeys(k for r in rows for k in r))
    f=io.StringIO(newline='')
    w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    data=f.getvalue().encode('utf-8');assert len(data)<=LIMIT,name
    (ROOT/name).write_bytes(data)
def hf(c):return 'https://huggingface.co/datasets/MathArena/'+c
def api(c):return 'https://datasets-server.huggingface.co/first-rows?dataset=MathArena%2F'+c+'&config=default&split=train'
def page(c):return 'https://matharena.ai/?comp='+('aime--' if c.startswith('aime') else 'hmmt--')+c+'&view=problem'
def canonical(c,i):
    y=c[-4:]
    if c.startswith('aime'):return f'AIME-{y}-'+('I' if i<=15 else 'II')+f'-{(i-1)%15+1:02}'
    if 21<=i<=30:return f'HMMT-{y}-FEB-GEO-{i-20:02}'
    return ''
# AIME 2026 has no publisher category column. Preserve the predecessor's
# analyst annotations; statements rechecked on resume. Not preregistered.
MANUAL_GEO={3,5,10,12,14,18,21,23,25,27}
MANUAL_REASON={3:'半球・球の接触（空間）',5:'点の回転',10:'三角形の回転',12:'球と平面の接触（空間）',14:'等角五角形',18:'非凸五角形',21:'円と放物線の接触（境界：代数とも分類可能）',23:'二等辺三角形・内心',25:'角の二等分線・円',27:'四面体（空間）'}
problems={};metadata=[]
for c in COMPS:
    raw=json.loads((ROOT/f'{c}-problems.json').read_text())
    assert not raw.get('truncated'),c
    for x in raw['rows']:
        assert not x.get('truncated_cells'),(c,x['row_idx'])
        p=x['row'];i=int(p['problem_idx']);tags=[s.strip() for s in p.get('problem_type',[])]
        r={'competition':c,'problem_idx':i,'canonical_id':canonical(c,i),'publisher_types':'|'.join(tags) if tags else '未取得（元データに列なし）','publisher_geometry':int('Geometry' in tags) if tags else '未取得','analyst_geometry':int(i in MANUAL_GEO) if c=='aime_2026' else '', 'analyst_reason':MANUAL_REASON.get(i,'数・式・数え上げ（格子経路等を含む）') if c=='aime_2026' else '', 'statement_sha256':hashlib.sha256(p['problem'].encode()).hexdigest(),'source_url':api(c),'retrieved_date':DATE}
        problems[c,i]=(r,p);metadata.append(r)
writecsv('problem_metadata.csv',metadata)
traces=[json.loads(l) for l in (ROOT/'trace-summaries.jsonl').read_text().splitlines()]
assert len({(r['competition'],r['model'],r['problem_idx']) for r in traces})==len(traces)
llm=[]
for t in traces:
    runs=t.get('runs',[]);ok=t['status']=='取得'
    if ok:assert {r['run'] for r in runs}=={1,2,3,4} and len(runs)==4 and all(r['correct'] in (0,1) for r in runs),(t['competition'],t['model'],t['problem_idx'],runs)
    n=len(runs) if ok else None;k=sum(r['correct'] for r in runs) if ok else None
    r={'competition':t['competition'],'model':t['model'],'model_config':t['model_config'],'problem_idx':t['problem_idx'],'problem_label':t['problem_label'],'case_id':canonical(t['competition'],t['problem_idx']),'n_correct':k if ok else '未取得','n_runs':n if ok else '未取得','accuracy':k/n if ok else '未取得','run_correct_vector':','.join(str(r['correct']) for r in runs),'status':t['status'],'source_url':t['url'],'retrieved_at':t['retrieved_at'],'response_sha256':t.get('sha256','')}
    llm.append(r)
writecsv('llm_per_problem.csv',llm)
assert len(llm)==246 and all(r['status']=='取得' for r in llm),'incomplete collection; do not publish a complete-panel report'
# The only unseen file read is manifest. Selection status is used solely to select
# membership; retained/useable fields are IDs and contest/year derived from IDs.
human=readcsv(REPO/'jssa/difficulty/ghost-1023/human_feat.csv')
new=readcsv(REPO/'jssa/difficulty/new2026-predict/predictions.csv')
manifest=json.loads((REPO/'jssa/difficulty/unseen-1983/manifest.json').read_text())
unseen=[r['id'] for r in manifest['rows'] if r.get('status')=='selected_candidate']
assert len(human)==323 and len(new)==20 and len(unseen)==54
sets={'development_323':[r['case_id'] for r in human],'new2026_20':[r['id'] for r in new],'unseen_54':unseen}
assert len(set(sum(sets.values(),[])))==397
local_sources={'development_323':'jssa/difficulty/ghost-1023/human_feat.csv','new2026_20':'jssa/difficulty/new2026-predict/predictions.csv','unseen_54':'jssa/difficulty/unseen-1983/manifest.json#rows[status=selected_candidate].id'}
pub_by_id={r['canonical_id']:(r['competition'],r['problem_idx']) for r in metadata if r['canonical_id']}
lookup={}
for r in llm:
 if r['case_id']:lookup.setdefault(r['case_id'],[]).append(r)
cross=[]
for group,ids in sets.items():
    for id in ids:
        hit=id in pub_by_id;c,i=pub_by_id.get(id,('',None))
        cross.append({'study_set':group,'case_id':id,'contest':id.split('-')[0],'year':int(id.split('-')[1]),'id_source':local_sources[group],'id_source_url':LOCAL_URLS[local_sources[group].split('#')[0]],'overlap_in_four_competitions':int(hit),'matharena_competition':c,'matharena_problem_idx':i if hit else '', 'llm_status':'取得' if hit and lookup.get(id) else '調査範囲外（4大会に一致IDなし。公開成績の不存在は未証明）','source_url':api(c) if hit else ' | '.join(hf(c) for c in COMPS),'solver_use':'対象外（未参照）' if group=='unseen_54' else '一致問題の既存局所探索pと入手済み完成solver成績を区別して転記','retrieved_date':DATE})
writecsv('crosswalk.csv',cross)
# Read only named, authorized, existing summary CSVs. No raw/start/solver files.
basins={r['id']:r for r in readcsv(REPO/'jssa/difficulty/minima/basins-323.csv')}
outcomes={r['id']:r for r in readcsv(REPO/'jssa/difficulty/new2026-predict/outcomes.csv')}
final_rows=readcsv(REPO/FINAL_SOURCE)
assert len(final_rows)==969 and len({(r['case_id'],r['seed']) for r in final_rows})==969
assert sum(r['correct']=='True' for r in final_rows)==953
final_by_id={}
final_export=[]
for r in final_rows:
    if r['case_id'] not in pub_by_id:continue
    assert r['correct'] in ('True','False')
    final_by_id.setdefault(r['case_id'],[]).append(r)
    final_export.append({k:r[k] for k in ['case_id','seed','correct','status','wall_time_s']}|{'source_path':FINAL_SOURCE,'source_url':LOCAL_URLS[FINAL_SOURCE]})
assert len(final_by_id)==16 and len(final_export)==48
writecsv('solver_final_runs.csv',final_export)
cases={}
for f in ['benchmarks/cases.jsonl','jssa/difficulty/new2026/cases.jsonl']:
 for line in (REPO/f).open():
  r=json.loads(line)
  if r['id'] in pub_by_id:cases[r['id']]={k:r.get(k) for k in ['source','answer','truth_basis']}
compare=[];mapping=[]
transforms={'AIME-2025-II-06':'DSLは面積288/5、公式出力は分子+分母293','AIME-2025-II-12':'DSLは(-1+9sqrt(5))/4、公式出力は係数等の和19','AIME-2025-II-14':'DSLは面積104sqrt(3)、公式出力は係数104'}
for x in cross:
 if not x['overlap_in_four_competitions']:continue
 id=x['case_id'];group=x['study_set'];assert group!='unseen_54'
 c=x['matharena_competition'];i=x['matharena_problem_idx'];s=basins[id] if group=='development_323' else outcomes[id]
 n=int(s.get('n_starts',s.get('starts')));p=float(s['p']);assert n>0 and 0<=p<=1 and abs(p*n-round(p*n))<1e-8
 source='jssa/difficulty/minima/basins-323.csv' if group=='development_323' else 'jssa/difficulty/new2026-predict/outcomes.csv'
 m={'study_set':group,'case_id':id,'matharena_competition':c,'matharena_problem_idx':i,'mapping_rule':'AIME I n→n; II n→15+n' if c.startswith('aime') else 'GEO n→20+n; table label Gn','identity_evidence':'大会・年・部門・問題番号一致。答え表記も照合（入力文・DSLの完全同値性監査は未実施）','local_problem_source_url':cases[id]['source'],'metadata_source_url':api(c),'local_raw_target':' | '.join(cases[id]['answer']),'matharena_gold_answer':problems[c,i][1]['answer'],'target_conversion':transforms.get(id,'同じ量（根号・分数・角度単位の表記差あり）')}
 mapping.append(m)
 for lr in lookup.get(id,[]):
  final=final_by_id.get(id,[])
  if final:assert {r['seed'] for r in final}=={'0','1','2'}
  fk=sum(r['correct']=='True' for r in final)
  compare.append({'study_set':group,'case_id':id,'competition':c,'model':lr['model'],'llm_correct':lr['n_correct'],'llm_runs':lr['n_runs'],'llm_accuracy':lr['accuracy'],'llm_source_url':lr['source_url'],'solver_local_p':p,'solver_starts':n,'solver_local_hits':round(p*n),'solver_source_path':source,'solver_source_url':LOCAL_URLS[source],'solver_seed':0 if group=='development_323' else 5,'solver_final_status':'取得' if final else '未取得（2026群の問題別完成solver記録が作業ツリーにない）','solver_final_correct':fk if final else '', 'solver_final_runs':len(final) if final else '', 'solver_final_accuracy':fk/len(final) if final else '', 'solver_final_median_wall_s':statistics.median(float(r['wall_time_s']) for r in final) if final else '', 'solver_final_seeds':'0|1|2' if final else '', 'solver_final_source_url':LOCAL_URLS[FINAL_SOURCE] if final else '', 'comparison_scope':'完成solverとLLMの既存観測の併記。入力・予算・採点は同一でない。局所pは最終正答率でない','target_conversion':m['target_conversion'],'retrieved_date':DATE})
writecsv('matched_problems.csv',mapping);writecsv('solver_comparison.csv',compare)
gaps=[]
for c in COMPS:
 for model in sorted({r['model'] for r in llm if r['competition']==c}):
  rr=[r for r in llm if r['competition']==c and r['model']==model and r['status']=='取得']
  expected=33 if c=='hmmt_feb_2026' else 30
  if len(rr)!=expected:continue
  definitions=['publisher_any_geometry','publisher_pure_geometry'] if c!='aime_2026' else ['analyst_geometry','analyst_geometry_exclude_coordinate_boundary']
  if c.startswith('hmmt'):definitions+=['official_geometry_section']
  if c=='hmmt_feb_2026':definitions+=['official_geometry_section_individual_only','publisher_any_geometry_individual_only']
  for definition in definitions:
   def isgeo(r):
    i=r['problem_idx'];tags=problems[c,i][0]['publisher_types'].split('|')
    if definition.startswith('publisher_any_geometry'):return 'Geometry' in tags
    if definition=='publisher_pure_geometry':return tags==['Geometry']
    if definition.startswith('official_geometry_section'):return 21<=i<=30
    return i in MANUAL_GEO and not (definition.endswith('boundary') and i==21)
   population=[r for r in rr if not definition.endswith('individual_only') or r['problem_idx']<=30]
   g=[r for r in population if isgeo(r)];o=[r for r in population if not isgeo(r)]
   gk=sum(r['n_correct'] for r in g);gn=sum(r['n_runs'] for r in g);ok=sum(r['n_correct'] for r in o);on=sum(r['n_runs'] for r in o)
   gaps.append({'competition':c,'model':model,'geometry_definition':definition,'geometry_problems':len(g),'other_problems':len(o),'geometry_correct':gk,'geometry_runs':gn,'geometry_accuracy':gk/gn,'other_correct':ok,'other_runs':on,'other_accuracy':ok/on,'gap_percentage_points':100*(gk/gn-ok/on),'overall_correct':gk+ok,'overall_runs':gn+on,'overall_accuracy':(gk+ok)/(gn+on),'grading_source_url':page(c),'category_source_url':api(c),'exact_problem_urls_file':'llm_per_problem.csv','retrieved_date':DATE})
writecsv('geometry_gap.csv',gaps)
summary=[]
for group in ['development_323','new2026_20']:
 for c in COMPS:
  for model in sorted({r['model'] for r in compare if r['study_set']==group and r['competition']==c}):
   rr=[r for r in compare if r['study_set']==group and r['competition']==c and r['model']==model]
   fr=[r for r in rr if r['solver_final_status']=='取得'];fn=sum(r['solver_final_runs'] for r in fr);fk=sum(r['solver_final_correct'] for r in fr)
   summary.append({'study_set':group,'competition':c,'model':model,'matched_problems':len(rr),'llm_correct':sum(r['llm_correct'] for r in rr),'llm_runs':sum(r['llm_runs'] for r in rr),'llm_accuracy':statistics.mean(r['llm_accuracy'] for r in rr),'mean_solver_local_p':statistics.mean(r['solver_local_p'] for r in rr),'solver_final_problems_available':len(fr),'solver_final_correct':fk if fn else '', 'solver_final_runs':fn if fn else '', 'solver_final_accuracy':fk/fn if fn else '', 'llm_source_url':page(c),'solver_source_url':rr[0]['solver_source_url'],'solver_final_source_url':LOCAL_URLS[FINAL_SOURCE] if fn else '', 'retrieved_date':DATE})
writecsv('overlap_summary.csv',summary)
# Model release warning is read from the publisher's row, not inferred from accuracy.
models=[]
for c in COMPS:
 table=json.loads((ROOT/f'{c}-tables.json').read_text())['problem_table']
 for attrs,body in re.findall(r'<tr\s+class="model-row"([^>]*)>(.*?)</tr>',table,re.S):
  at=dict(re.findall(r'([\w-]+)="([^"]*)"',attrs));model=at['data-model-name']
  if model not in {r['model'] for r in llm if r['competition']==c}:continue
  match=re.search(r'class="[^"]*--accuracy[^"]*"[^>]*>(.*?)</td>',body,re.S)
  score=re.search(r'(\d+\.\d+)%',match[1]) if match else None
  computed=[r for r in gaps if r['competition']==c and r['model']==model]
  assert score and computed,(c,model,'missing leaderboard validation')
  assert abs(float(score[1])-computed[0]['overall_accuracy']*100)<.011,(c,model,score[1],computed[0]['overall_accuracy'])
  models.append({'competition':c,'model':model,'model_config':at['data-config'],'released_after_competition_warning':int('contamination-warning' in body),'table_overall_percent':score[1] if score else '未取得','source_url':page(c),'retrieved_date':DATE})
writecsv('model_metadata.csv',models)
# Freeze provenance of the local input files, with ID-only hash for unseen.
inputs=[]
for f in ['jssa/difficulty/ghost-1023/human_feat.csv','jssa/difficulty/minima/basins-323.csv','jssa/difficulty/new2026-predict/predictions.csv','jssa/difficulty/new2026-predict/outcomes.csv','benchmarks/cases.jsonl','jssa/difficulty/new2026/cases.jsonl',FINAL_SOURCE]:
 b=(REPO/f).read_bytes();inputs.append({'path':f,'hash_scope':'file bytes','sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b),'source_url':LOCAL_URLS[f]})
inputs.append({'path':'jssa/difficulty/unseen-1983/manifest.json','hash_scope':'selected_candidate IDs only, JSON ensure_ascii=False separators=(comma,colon)','sha256':hashlib.sha256(json.dumps(unseen,ensure_ascii=False,separators=(',',':')).encode()).hexdigest(),'bytes':'','source_url':LOCAL_URLS['jssa/difficulty/unseen-1983/manifest.json']})
writecsv('local_input_hashes.csv',inputs)
print('crosswalk',len(cross),'matched',len(mapping),'comparisons',len(compare),'LLM records',len(llm))
print('coverage',{k:sum(r['overlap_in_four_competitions'] for r in cross if r['study_set']==k) for k in sets})
for r in gaps:
 if r['geometry_definition'] in ['publisher_any_geometry','analyst_geometry']:print(r['competition'],r['model'],'geom',r['geometry_correct'],r['geometry_runs'],'other',r['other_correct'],r['other_runs'],'gap',round(r['gap_percentage_points'],3))
