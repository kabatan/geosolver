"""Continue unchanged numeric SFT recipe from update 128 to fixed update 512."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ORIGINAL=HERE.parent/'program-self-training-2026-09-26/train_sft.py'
EXPECTED='f525e7626bae22109753cd5a8deac47b94cd13f4bd4dcc13960543b4607b9857'


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--config',required=True);ap.add_argument('--out',required=True)
    ap.add_argument('--preflight',action='store_true');args=ap.parse_args()
    assert hashlib.sha256(ORIGINAL.read_bytes()).hexdigest()==EXPECTED
    sys.path.insert(0,str(ORIGINAL.parent))
    spec=importlib.util.spec_from_file_location('unchanged_sft_trainer',ORIGINAL)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    original_parameters=module.parameters
    def extended(config):
        assert config['updates']==512 and config['prior_checkpoint']
        prior=json.loads((Path(config['prior_checkpoint'])/'receipt.json').read_text())
        assert prior['global_updates']==128 and prior['status']=='complete'
        return original_parameters(dict(config,updates=32))
    module.parameters=extended
    module.run(args)


if __name__=='__main__':main()
