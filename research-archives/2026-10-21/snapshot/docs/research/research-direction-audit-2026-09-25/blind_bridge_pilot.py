"""Create the full two-arm packet only after all eight outputs have completed."""
import hashlib
import json
from pathlib import Path
import random

D = Path(__file__).resolve().parent
ROOT = D.parents[2]
R = ROOT / 'qwen/.runtime/research_direction_audit_20260925'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    rows = []
    for arm in ['treatment', 'control']:
        p = R/f'eval-mapped-{arm}'
        receipt = json.loads((p/'receipt.json').read_text())
        assert receipt['status'] == 'complete'
        armrows = []
        for f in p.glob('*.json'):
            x = json.loads(f.read_text())
            if 'completion_ids' in x:
                assert x['source_id'] == 'H14'
                armrows.append((arm, f, x))
        assert len(armrows) == 4
        rows.extend(sorted(armrows, key=lambda row: row[2]['id']))
    random.Random(2026092581).shuffle(rows)
    target = D/'bridge-blind'
    target.mkdir(exist_ok=False)
    packet, mapping = [], []
    for i, (arm, path, x) in enumerate(rows, 1):
        identity = f'P{i:03d}'
        public = {'id':identity, 'problem':x['messages'],
                  'answer':x['final_text'], 'finish_reason':x['finish_reason'],
                  'tokens':len(x['completion_ids'])}
        packet.append(public)
        prompt = '\n\n'.join(m['content'] for m in x['messages'])
        (target/f'{identity}.md').write_text(f'# {identity}\n\n{prompt}\n\n## Answer\n\n{x["final_text"]}\n')
        mapping.append({'id':identity,'arm':arm,'job_id':x['id'],
                        'source_path':str(path),'source_sha256':sha(path)})
    (target/'packet.json').write_text(json.dumps(packet,indent=2,ensure_ascii=False)+'\n')
    (R/'blind-mapping.json').write_text(json.dumps(mapping,indent=2)+'\n')
    frozen = {'packet_sha256':sha(target/'packet.json'),
              'mapping_sha256':sha(R/'blind-mapping.json'),
              'scope':'all eight H14 outputs; independent graders must not open mapping'}
    (target/'packet-freeze.json').write_text(json.dumps(frozen,indent=2)+'\n')
    print(json.dumps({'status':'blinded','n':len(packet),'packet_sha256':frozen['packet_sha256']}))

if __name__ == '__main__':
    main()
