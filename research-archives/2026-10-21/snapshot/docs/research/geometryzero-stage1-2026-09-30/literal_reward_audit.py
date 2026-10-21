"""Run the actual upstream numeric function in isolated pinned math-verify deps."""
import ast,json,re,sys
from pathlib import Path
from prepare import HERE,RUN,write,sha
sys.path.insert(0,str(RUN/'reward-deps'))
from math_verify import ExprExtractionConfig,LatexExtractionConfig,StringExtractionConfig,parse,verify
def main():
 source=HERE/'upstream/workspace__reward__reward_utils.py';tree=ast.parse(source.read_text());tree.body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('extract_answer_with_tags','accuracy_reward_func')]
 ns=dict(re=re,parse=parse,verify=verify,ExprExtractionConfig=ExprExtractionConfig,LatexExtractionConfig=LatexExtractionConfig,StringExtractionConfig=StringExtractionConfig);exec(compile(tree,str(source),'exec'),ns)
 labels=json.loads((RUN/'labels.json').read_text());rows=json.loads((RUN/'scores.json').read_text());records=[]
 for r in rows:
  if r['censored']:continue
  gold=labels[r['problem_id']]['answer_exact'];literal=ns['accuracy_reward_func'](r['raw_text'],gold,relaxed=True);closed=re.findall(r'<answer>(.*?)</answer>',r['raw_text'],re.S);parsed=closed[-1].strip() if closed else None
  # Supplementary mathematical extraction on last closed answer. No fallback numbers.
  extracted=parse(parsed,extraction_config=[StringExtractionConfig(),LatexExtractionConfig(),ExprExtractionConfig()]) if parsed else []
  goldparsed=parse(gold);symbolic=int(bool(extracted) and bool(goldparsed) and verify(extracted,goldparsed))
  records.append(dict(id=r['id'],sample=r['sample'],literal=literal,adapted=r['relaxed'],strict=r['strict'],supplementary_symbolic=symbolic,closed_tags=len(closed),parsed_last=parsed))
 result=dict(source_sha256=sha(source),math_verify_version='0.9.0',scope='Actual upstream function under pinned parser dependency; upstream dependency version is not pinned in inspected training script; supplementary score does not change frozen training selection.',groups={g:dict(natural=sum(r['id'].endswith('-'+g) for r in records),literal_correct=sum(r['literal']==1 for r in records if r['id'].endswith('-'+g)),adapted_correct=sum(r['adapted']==1 for r in records if r['id'].endswith('-'+g)),supplementary_symbolic_correct=sum(r['supplementary_symbolic']==1 for r in records if r['id'].endswith('-'+g)),literal_only=sum(r['literal']==1 and r['adapted']==0 for r in records if r['id'].endswith('-'+g))) for g in ('main','with','without')},records=records)
 write(HERE/'literal-reward-audit.json',result);print(json.dumps(result['groups'],indent=2))
if __name__=='__main__':main()
