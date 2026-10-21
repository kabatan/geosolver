"""Freeze stage-one self-generated-relation probe. No solutions in model input."""
import json
from pathlib import Path
from qwen.common import write_json,file_hash,now,stable_seed
D=Path(__file__).resolve().parent
F=D.parent/'foundation-pilot-2026-09-23'
configurations={
'H01':'鋭角不等辺三角形ABCの垂心をH、BCの中点をMとする。Hから直線AMに下ろした垂線の足をPとする。',
'DA05':'鋭角不等辺三角形ABCを考える。Aを通り直線BCにBで接する円をω1、Cを通り直線BAにBで接する円をω2とし、二円のBでない交点をDとする。MをBCの中点、Eを直線MDと直線ACの交点とする。M,D,Eはこの順に並ぶとする。',
'DA15':'鋭角不等辺三角形ABCの外心をO、BCの中点をMとする。AB,ACの垂直二等分線と半直線AMの交点をそれぞれD,Eとする。F=BD∩CEは三角形ABCの内部にあるとする。'
}
instruction='''この配置で成り立つ、数学的に意味のある関係を一つ見いだしてください。後でこの配置の長さ・角度などを求めたり、幾何的性質を説明したりするときに、未知量や計算・論証を実際に減らせる関係を目指してください。構成の定義の言い換えだけでは不十分です。補助点を導入する必要はありません。方法は自由で、座標・ベクトルも使えます。

次の順で回答してください。
1. 採用する関係を一つ、必要な条件とともに明確に述べる。
2. その関係を、与えられた構成と基本的な数学から論証する。既知の点・高度な補題の名前だけで核心を済ませない。
3. 何をどのように簡単にできるかを、式または短い具体的な利用例で示す。

三角形の数値は固定されていません。一つの特殊な三角形での一致を一般的な証明にしないでください。証明できなかった場合は、未証明の予想であると明記してください。'''
meta=json.loads((F/'qwen35_9b-model.json').read_text())
jobs=[]
for ident,cfg in configurations.items():
 for i in range(4):
  jobs.append(dict(id=f'{ident}-initial-{i}',source_id=ident,sample=i,messages=[dict(role='user',content=cfg+'\n\n'+instruction)],seed=stable_seed(2026092337,ident,i)%(2**31),stage='initial',training_eligible=False))
assert not (D/'protocol.json').exists(),'Frozen inputs already exist'
write_json(D/'jobs-initial.json',jobs)
write_json(D/'model.json',meta)
write_json(D/'protocol.json',dict(created_utc=now(),updates=0,model=meta['model_id'],revision=meta['revision'],dtype='bfloat16',kv_cache_dtype='auto',enable_thinking=False,max_output_tokens=32768,max_context=45056,max_num_seqs=2,max_num_batched_tokens=1024,gpu_memory_utilization=.85,sampling=dict(temperature=1.,top_p=.95,top_k=20,presence_penalty=1.5),initial_answers=12,initial_source_configurations=list(configurations),jobs_sha256=file_hash(D/'jobs-initial.json'),model_metadata_sha256=file_hash(D/'model.json'),max_followup_answers=4,max_feedback_pairs=2,feedback_policy='At most one pair each on DA05 and DA15: choose the first by sample order with a concretely refutable central claim. Same original answer; one continuation with only a counterexample/verdict for its own claim, one generic retry without verifier information. No correct target relation or proof supplied. If no suitable failure, skip. Exploratory matched retry, not powered causal study.',runtime_watchdog_seconds=3600,exclusions=['No final proof evaluation problems','No authoring references or target theorem supplied','No weight updates','No stronger-model solution repair'],verification='Freeze extracted claims before fresh numerical tests. Reconstruct from primitive definitions; check generic symbolic residuals where possible. Classify false, verified, and unresolved separately; model proof and utility separately.',decision='Proceed to collecting self-training material only if useful, algebraically verifiable model-proved material appears in at least two configurations; relation-only success supports a verifier-based search pilot, not whole-answer SFT. Twelve candidates do not establish enough diversity for training.'))
print('Frozen 12 prompts without numerical answers or target lemmas.')
