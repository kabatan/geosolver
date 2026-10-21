"""Extract numerical commitments before exposing their reference answers."""
import hashlib
import argparse
import importlib.util
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'qwen/.runtime/proof_numeric_pilot_20260928'
sys.path.insert(0,str(ROOT))
from qwen.answer_check import extract_answer,final_text


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--folder',type=Path,default=OUT/'blind')
    parser.add_argument('--out',type=Path,default=OUT/'numeric-extractions.json')
    args=parser.parse_args()
    driver=ROOT/'docs/research/transfer-reanalysis-2026-09-26/score_numeric.py'
    spec=importlib.util.spec_from_file_location('existing_numeric_scorer',driver)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    rows=[]
    for index in json.loads((args.folder/'numeric-index.json').read_text()):
        path=Path(index['file']);r=json.loads(path.read_text());text=final_text(r['raw_text']) or ''
        commit=mod.last_committed_answer(r['raw_text'])
        if commit:
            parsed=commit['parsed'];method=commit['marker'];expression=commit['expression']
        else:
            parsed=extract_answer(text);method='whole_response_expression';expression=text
            if parsed is None and text:
                expression=text.splitlines()[-1].strip().strip('*` ')
                parsed=extract_answer(expression);method='last_line_expression'
        rows.append({'case_id':r['case_id'],'file_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                     'finish_reason':r['finish_reason'],'tokens':r['tokens'],'method':method,
                     'parsed_expression':parsed,'commit_excerpt':expression[-600:],
                     'final_excerpt':text[-1800:]})
    args.out.write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(rows,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
