"""CPU tests of exact CE, short-target masks/order and verified adapter export."""
import json
from pathlib import Path
import tempfile
import unittest

import torch
from safetensors.torch import save_file, load_file
from transformers import AutoTokenizer

import train_sft as t


class TrainerTests(unittest.TestCase):
    def test_exact_chunked_ce_values_and_gradients(self):
        self.assertEqual(t.cpu_check()['status'], 'pass')

    def test_deterministic_order_and_resume_prefix(self):
        rows=[{'id':str(i)} for i in range(7)]
        short=t.data_order(7,64,2026092701);long=t.data_order(7,128,2026092701)
        self.assertEqual(short,long[:64]);self.assertEqual(t.order_digest(short,rows,64),t.order_digest(long,rows,64))
        self.assertNotEqual(t.order_digest(long,rows,64),t.order_digest(long,rows,128))

    def test_real_tokenizer_short_numeric_and_code_targets(self):
        path=Path('docs/research/qwen35-self-materials-2026-09-23/model.json')
        meta=json.loads(path.read_text());tok=AutoTokenizer.from_pretrained(meta['snapshot'],local_files_only=True)
        fixed=t.parameters({'updates':32})
        raw=[{'id':'short','source_id':'toy','kind':'numeric','messages':[{'role':'user','content':'Return only the scalar answer.'}],'target':'3'},
             {'id':'code','source_id':'toy','kind':'code','messages':[{'role':'user','content':'Return one complete Python fence defining solve(givens).'}],'target':'```python\ndef solve(givens):\n    return givens[\'x\']\n```'}]
        rows=t.tokenize_rows(raw,tok,fixed)
        self.assertLess(len(rows[0]['target_ids']),20)
        self.assertGreaterEqual(len(rows[0]['target_ids']),2)
        for row in rows:
            self.assertEqual(row['target_ids'][-1],tok.eos_token_id)
            # User turns end in EOS inside the prompt; those positions are
            # deliberately outside the assistant-only logits/loss window.
            self.assertNotEqual(tok.eos_token_id,row['prompt_ids'][-1])
        with self.assertRaises(ValueError):t.tokenize_rows(raw,tok,dict(fixed,max_target_tokens=1))

    def test_mapping_preserves_all_tensor_values(self):
        _,export=t.mapping_helpers()
        parent=Path('qwen/.runtime/program_self_training_20260926/cpu-tests');parent.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='mapping-',dir=parent) as temp:
            source=Path(temp)/'source';source.mkdir();target=Path(temp)/'mapped'
            original={f'base_model.model.model.layers.{i//10}.test{i}.lora_A.weight':torch.tensor([[float(i)]]) for i in range(400)}
            save_file(original,str(source/'adapter_model.safetensors'))
            (source/'adapter_config.json').write_text('{}')
            result=export(source,target);loaded=load_file(str(target/'adapter_model.safetensors'))
            self.assertEqual(result['n_tensors'],400)
            for key,value in original.items():
                new=key.replace('base_model.model.model.layers.','base_model.model.model.language_model.layers.')
                self.assertTrue(torch.equal(value,loaded[new]))


if __name__=='__main__':unittest.main(verbosity=2)
