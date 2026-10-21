"""Audit saved token IDs against each model's published tokenizer pipeline."""
import hashlib,json,shutil
from pathlib import Path
from tokenizers import Tokenizer
from transformers import AutoTokenizer
D=Path(__file__).resolve().parent
R=Path('qwen/.runtime/foundation_pilot_20260923')
audit={}
for key in ['qwen3_4b','qwen3_2507','qwen35_9b','r1_8b']:
 meta=json.loads((D/(key+'-model.json')).read_text());p=Path(meta['snapshot'])
 raw=Tokenizer.from_file(str(p/'tokenizer.json'))
 auto=AutoTokenizer.from_pretrained(p,local_files_only=True)
 probes=[]
 for text in ['The triangle is right.','ABCの外心をOとする。','<think>\nA short proof.\n</think>']:
  ids=auto.encode(text,add_special_tokens=False)
  probes.append(dict(text=text,roundtrip=auto.decode(ids,skip_special_tokens=False),matches_published=ids==raw.encode(text,add_special_tokens=False).ids))
 saved=[]
 for f in sorted((R/('screen-'+key)).glob('group-*.json')):
  for row in json.loads(f.read_text()):
   saved.append(dict(id=row['id'],sample=row['sample'],input_matches_published=row['prompt_ids']==raw.encode(row['prompt_text'],add_special_tokens=False).ids,decode_matches_published=row['raw_text']==raw.decode(row['completion_ids'],skip_special_tokens=False)))
 audit[key]=dict(auto_class=type(auto).__name__,probes=probes,saved=saved)
 if key!='r1_8b':assert all(x['matches_published'] for x in probes) and all(x['input_matches_published'] and x['decode_matches_published'] for x in saved),key

meta=json.loads((D/'r1_8b-model.json').read_text());p=Path(meta['snapshot'])
fix=R/'r1-tokenizer-canonical';fix.mkdir(exist_ok=True)
config=json.loads((p/'tokenizer_config.json').read_text())
config['tokenizer_class']='PreTrainedTokenizerFast'
(fix/'tokenizer_config.json').write_text(json.dumps(config,ensure_ascii=False,indent=2)+'\n')
shutil.copyfile(p/'tokenizer.json',fix/'tokenizer.json')
tok=AutoTokenizer.from_pretrained(fix,local_files_only=True);raw=Tokenizer.from_file(str(p/'tokenizer.json'))
checks=[]
for name in ['screen-jobs.json','confirmation-jobs.json','target-dev-jobs.json']:
 for row in json.loads((D/name).read_text()):
  prompt=tok.apply_chat_template([{'role':'user','content':row['problem']}],tokenize=False,add_generation_prompt=True,enable_thinking=True)
  ids=tok.encode(prompt,add_special_tokens=False)
  assert ids==raw.encode(prompt,add_special_tokens=False).ids
  assert tok.decode(ids,skip_special_tokens=False)==prompt
  checks.append(name+':'+row['id'])
meta['tokenizer_override']=str(fix.resolve())
meta['tokenizer_repair']='Only tokenizer_class metadata corrected to PreTrainedTokenizerFast. The published tokenizer.json is copied byte-for-byte, retaining its ByteLevel BPE encoder/decoder and original chat template. Transformers5.17 Auto LlamaTokenizer otherwise replaces this pipeline.'
(D/'r1_8b-model.json').write_text(json.dumps(meta,indent=2)+'\n')
audit['repair']=dict(path=str(fix.resolve()),model_weights_unchanged=True,tokenizer_json_sha256=hashlib.sha256((fix/'tokenizer.json').read_bytes()).hexdigest(),config_sha256=hashlib.sha256((fix/'tokenizer_config.json').read_bytes()).hexdigest(),checked_prompts=checks,eos=tok.eos_token,eos_id=tok.eos_token_id)
audit['invalid_runs']=['screen-r1_8b']
(D/'tokenizer-audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:dict(class_name=v['auto_class'],probe_match=all(x['matches_published'] for x in v['probes']),saved_answers=len(v['saved']),saved_input_match=all(x['input_matches_published'] for x in v['saved'])) for k,v in audit.items() if isinstance(v,dict) and 'probes' in v},indent=2))
print('Canonical R1 tokenizer verified on '+str(len(checks))+' full prompts.')
