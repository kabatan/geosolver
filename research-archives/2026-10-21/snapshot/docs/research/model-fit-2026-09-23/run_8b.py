"""Additional three-item 8B diagnostic, only after the two 4B workers finish."""
import os
os.environ.setdefault('HF_HUB_OFFLINE','1')
os.environ.setdefault('TOKENIZERS_PARALLELISM','false')
os.environ.setdefault('VLLM_USE_FLASHINFER_SAMPLER','0')
os.environ.setdefault('PYTORCH_ALLOC_CONF','expandable_segments:True')
import json,sys,time
from pathlib import Path
from qwen.common import write_json,file_hash,now,stable_seed
from qwen.grpo_run import run_worker
D=Path(__file__).resolve().parent
R=Path('qwen/.runtime/model_fit_20260923_8b')
def worker():
 from transformers import AutoTokenizer
 from vllm import LLM,SamplingParams
 model=json.loads((D/'8b-model.json').read_text());assert model['status']=='complete'
 protocol=json.loads((D/'8b-protocol.json').read_text());assert file_hash(D/'8b-jobs.json')==protocol['jobs_sha256']
 t=AutoTokenizer.from_pretrained(model['snapshot'],local_files_only=True)
 llm=LLM(model=model['snapshot'],dtype='float16',kv_cache_dtype='auto',enable_lora=True,max_lora_rank=32,lora_dtype='float16',max_loras=1,max_model_len=32768,max_num_seqs=2,max_num_batched_tokens=1024,gpu_memory_utilization=.85,enforce_eager=True,enable_prefix_caching=False,seed=2026092304)
 for index,row in enumerate(json.loads((D/'8b-jobs.json').read_text())):
  prompt=t.apply_chat_template([{'role':'system','content':'You are a helpful assistant.'},{'role':'user','content':row['problem']}],tokenize=False,add_generation_prompt=True,enable_thinking=True)
  ids=t.encode(prompt,add_special_tokens=False);assert all(isinstance(i,int) for i in ids)
  cap=min(32512,32768-len(ids));seed=stable_seed(2026092304,{'id':row['id'],'problem':row['problem']})%(2**31)
  start=time.monotonic();result=llm.generate([{'prompt_token_ids':ids}],SamplingParams(n=2,temperature=.6,top_p=.95,top_k=20,max_tokens=cap,seed=seed))[0];elapsed=time.monotonic()-start
  records=[]
  for sample,c in enumerate(result.outputs):
   raw=t.decode(c.token_ids,skip_special_tokens=False)
   records.append({**row,'model':'original_8b','sample':sample,'raw_text':raw,'final_text':raw.split('</think>',1)[1] if '</think>' in raw else '', 'prompt_ids':ids,'completion_ids':list(c.token_ids),'tokens':len(c.token_ids),'finish_reason':c.finish_reason,'seed':seed,'completion_cap':cap,'elapsed_group_seconds':elapsed})
  write_json(R/f'group-{index:02}.json',records)
  print(json.dumps({'id':row['id'],'tokens':[r['tokens'] for r in records],'seconds':elapsed}),flush=True)
def main():
 if '--worker' in sys.argv:return worker()
 assert json.loads(Path('qwen/.runtime/model_fit_20260923_attempt04/receipt.json').read_text())['status']=='complete','Wait for existing GPU worker to exit'
 R.mkdir(parents=True,exist_ok=True);receipt=R/'receipt.json';assert not receipt.exists()
 rec={'status':'running','start_utc':now(),'driver_sha256':file_hash(__file__),'protocol_sha256':file_hash(D/'8b-protocol.json'),'updates':0};write_json(receipt,rec);start=time.monotonic()
 try:run_worker([sys.executable,str(Path(__file__).resolve()),'--worker'],R/'generate.log',2700);rec['status']='complete'
 except BaseException as e:rec['status']='failed';rec['error']=repr(e);raise
 finally:rec['elapsed_seconds']=time.monotonic()-start;rec['end_utc']=now();write_json(receipt,rec);print(json.dumps(rec),flush=True)
if __name__=='__main__':main()
