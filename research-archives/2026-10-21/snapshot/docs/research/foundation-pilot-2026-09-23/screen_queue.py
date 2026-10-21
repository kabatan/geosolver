"""Continue the fixed screen sequentially after the already launched control."""
import json
import subprocess
import sys
import time
from pathlib import Path

D = Path(__file__).resolve().parent
R = Path('qwen/.runtime/foundation_pilot_20260923')
while True:
    receipt = json.loads((R / 'screen-qwen3_4b/receipt.json').read_text())
    if receipt['status'] != 'running':
        assert receipt['status'] == 'complete', receipt
        break
    time.sleep(10)
for key in ['qwen3_2507', 'qwen35_9b', 'r1_8b']:
    print('Starting ' + key, flush=True)
    subprocess.run([sys.executable, str(D / 'infer.py'), '--key', key], check=True)
print('All fixed screen jobs completed.', flush=True)
