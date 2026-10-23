"""Read project metadata, then use bounded rg searches; never dump full sessions."""
import json
import re
import subprocess
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = Path('/home/kabatan/.codex/sessions/2026')
DAYS = ('09/07', '09/08', '09/11', '10/11')
PATTERN = r'なぜか|予想外|unexpected|regress|同じソース|同一ソース|same source|悪化|丸め|hypot|500桁|250桁|再現しな|source.hash'
records = []
inventory = []
for day in DAYS:
    for path in sorted((ROOT / day).glob('*jsonl*')):
        if path.suffix == '.zst':
            proc = subprocess.Popen(['zstd', '-dc', str(path)], stdout=subprocess.PIPE,
                                    stderr=subprocess.DEVNULL)
            line = proc.stdout.readline()
            proc.stdout.close()
            proc.terminate()
            proc.wait()
        else:
            with path.open('rb') as stream:
                line = stream.readline()
        try:
            meta = json.loads(line).get('payload', {})
        except (ValueError, AttributeError):
            continue
        if 'solver' not in str(meta.get('cwd', '')):
            continue
        query = ['rg', '-z', '--threads', '1', '-n', '-i', '-m', '80',
                 '"type":\\s*"message".*(' + PATTERN + ')', str(path)]
        found = subprocess.run(query, capture_output=True, text=True, timeout=35)
        count = 0
        for raw in found.stdout.splitlines():
            num, payload = raw.split(':', 1)
            item = json.loads(payload)
            data = item.get('payload', {})
            if data.get('type') != 'message' or data.get('role') not in ('user', 'assistant'):
                continue
            message = '\n'.join(c.get('text', '') for c in data.get('content', []))
            for match in list(re.finditer(PATTERN, message, flags=re.I))[:3]:
                excerpt = message[max(0, match.start()-160):match.end()+640]
                records.append(dict(path=str(path), line=int(num), timestamp=item.get('timestamp'),
                                    role=data['role'], match=match.group(), excerpt=excerpt))
                count += 1
        inventory.append(dict(path=str(path), compressed_bytes=path.stat().st_size,
                              cwd=meta.get('cwd'), rg_returncode=found.returncode,
                              rg_message_limit=80, excerpts=count))
OUT.joinpath('session-index.json').write_text(json.dumps(inventory, ensure_ascii=False, indent=2)+'\n')
OUT.joinpath('session-excerpts.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in records))
print(json.dumps(dict(project_sessions=len(inventory), excerpts=len(records), pattern=PATTERN), ensure_ascii=False))
for row in records:
    print(Path(row['path']).name, row['line'], row['match'], row['excerpt'][:500].replace('\n', ' / '))
