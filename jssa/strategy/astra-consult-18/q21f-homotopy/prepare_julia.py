"""Expose only already cached Julia packages; no Pkg operations or downloads."""
import json
import re
import tomllib
from pathlib import Path

OUT = Path(__file__).resolve().parent
CACHE = Path('/home/kabatan/.julia/packages')
DEST = OUT / 'runtime' / 'packages'
DEST.mkdir(parents=True, exist_ok=True)
for part in ['depot', 'tmp']:
    (OUT / 'runtime' / part).mkdir(exist_ok=True)

def ver(s):
    return tuple(int(x) for x in re.findall(r'\d+', s))

records = []
for folder in sorted(CACHE.iterdir()):
    choices = []
    for project in folder.glob('*/Project.toml'):
        try:
            data = tomllib.loads(project.read_text())
        except Exception:
            continue
        choices.append((ver(data.get('version', '0')), project.parent, data))
    if not choices:
        continue
    _, path, data = max(choices, key=lambda x: (x[0], str(x[1])))
    target = DEST / folder.name
    if not target.exists():
        target.symlink_to(path, target_is_directory=True)
    records.append({'name':folder.name, 'version':data.get('version'),
                    'uuid':data.get('uuid'), 'cached_source':str(path)})
(OUT / 'cached-julia-packages.json').write_text(json.dumps(records, indent=2)+'\n')
# Legacy TreeViews predates Project.toml. Supply loader metadata locally;
# its cached Julia source remains unchanged and is read through a symlink.
legacy = DEST / 'TreeViews'
legacy.mkdir(exist_ok=True)
(legacy / 'Project.toml').write_text('name = "TreeViews"\nuuid = "a2a6695c-b41b-5b7d-aed9-dbfdeacea5d7"\n')
if not (legacy / 'src').exists():
    (legacy / 'src').symlink_to(CACHE / 'TreeViews' / 'EdGaj' / 'src', target_is_directory=True)
print(json.dumps({'symlinks':len(records), 'load_path':str(DEST),
                  'packages_installed':0}))
