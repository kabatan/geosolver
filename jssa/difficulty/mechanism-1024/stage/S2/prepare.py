"""Read saved figures, freeze selection and all inputs; no numeric trials."""
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timezone

OUT = Path(__file__).resolve().parent
REPO = OUT.parents[4]
FROZEN = '60db4b679b04167175c51c479c87c22fa663fda0'
EXPECTED = 'sha256:d8fd9bb8392ad2984276bab3386e033669246ee79586317917c322d31b4541f5'


def read(p):
    return json.loads(Path(p).read_text())


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def save(p, v):
    s = json.dumps(v, ensure_ascii=False, indent=2) + '\n'
    assert len(s.encode()) < 3_000_000
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(s)


assert not (OUT / 'pre-run-hashes.json').exists(), 'Do not replace registered inputs'
scratch = Path(tempfile.mkdtemp(prefix='mechanism-s2-'))
archive = subprocess.check_output(['git', '-C', str(REPO), 'archive', FROZEN, 'src'])
with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
    tar.extractall(scratch, filter='data')
for rel in ['geosolver/engine/standard/refinement/mpmath_refiner.py',
            'geosolver/exact/polynomial_search.py']:
    assert (scratch / 'src' / rel).read_bytes() == (Path('/tmp/mech-inv-clean/src') / rel).read_bytes()
sys.path.insert(0, str(scratch / 'src'))
sys.dont_write_bytecode = True
from geosolver.runtime.integrity import source_tree_hash
assert source_tree_hash() == EXPECTED
shutil.copyfile(scratch / 'src/geosolver/exact/polynomial_search.py', OUT / 'frozen_polynomial_search.py')

files = set()
def source(rel):
    p = REPO / rel
    files.add(p)
    return read(p)

devpath = 'jssa/difficulty/certify-1024/dev-answers-seed0.json'
dev = source(devpath)
expath = REPO / 'jssa/difficulty/exact-strong-1024/dev5-ids.txt'
files.add(expath)
excluded = set(expath.read_text().splitlines()) | {'AIME-2014-II-10', 'AIME-2019-I-12'}
pool = [k for k, v in dev.items() if k not in excluded and any(a.get('minimal_polynomial') for a in v.get('answers', []))]
idhash = lambda k: hashlib.sha256(k.encode('utf-8')).hexdigest()
selected = sorted(pool, key=idhash)[:10]
selection = '\n'.join(f'| {i+1} | {k} | {idhash(k)} |' for i, k in enumerate(selected))
(OUT / 'selection.md').write_text(
    '# S2 実行前の対照選定\n\n'
    f'母集団：{devpath}に最小多項式のある問題。dev5と対象2問を除いた{len(pool)}問。'
    'UTF-8のID（表記を変えない）のsha256昇順で先頭10問を固定する。結果や図の精密化の成否による交換はしない。\n\n'
    '| 順位 | ID | sha256(ID) |\n|---|---|---|\n' + selection + '\n\n'
    '図：role-reassign/campaign/B/runs/<ID>/0.jsonの最初のverified記録を固定。'
    '当該BASEの保存済み記録を読み取り専用で使う。本計測の欠けた元JSONや未検証のminima図で代用しない。'
    '元記録と小さな図のコピーのハッシュはpre-run-hashes.jsonに保存。\n')

items = []
rolemanifest = {v['id']: v for v in source('jssa/difficulty/role-reassign/manifest.json')}
for k in selected:
    rawpath = f'jssa/difficulty/role-reassign/campaign/B/runs/{k}/0.json'
    raw = source(rawpath)
    assert raw['source_hash'] == EXPECTED
    dslpath = rolemanifest[k]['path']
    dsl = source(dslpath)
    assert sha(REPO / dslpath) == rolemanifest[k]['dsl_sha256']
    alt = source(f'jssa/difficulty/exact-scaling-1024/inputs/dev323/{k}.json')['dsl']
    assert dsl == alt
    summary = raw['solver_result']['diagnostics']['pipeline_summary']
    vi, witness = next((i, v) for i, v in enumerate(summary['verification_records']) if v.get('verified'))
    assert len(witness['values']) == len(dsl['variables'])
    items.append(dict(key=k, id=k, group='control', kind='original', dsl=dsl,
                      coordinates=witness['values'], saved_answer=witness['answer_hp'],
                      reference_polynomials=[a['minimal_polynomial'] for a in dev[k]['answers'] if a.get('minimal_polynomial')],
                      reference_source=devpath, figure_source=rawpath,
                      figure_pointer=f'solver_result.diagnostics.pipeline_summary.verification_records[{vi}]',
                      witness=witness))

ident = source('jssa/difficulty/capability-1024/examples/evidence/identification.json')
ref14 = source('jssa/difficulty/sweep/c-swap-target/references/AIME-2014-II-10.json')
rawpath = 'jssa/difficulty/unseen-2/a/execution/runs/AIME-2014-II-10/301.json'
c = source(rawpath)['diagnostic_evidence']['candidate_records']['first_6'][0]
assert c['candidate_id'] == ident['saved_candidate_id']
dsl = source('jssa/difficulty/sweep/c-swap-target/inputs/AIME-2014-II-10/original.json')
items.insert(0, dict(key='AIME-2014-II-10__area', id=dsl['id'], group='target', kind='area',
                     dsl=dsl, coordinates=c['x_hp'], saved_answer=c['answer_hp'],
                     reference_expression=ref14['answer'][0], reference_polynomials=[[1, 0, -27763975108827]],
                     reference_source='jssa/difficulty/sweep/c-swap-target/references/AIME-2014-II-10.json',
                     figure_source=rawpath, figure_pointer='diagnostic_evidence.candidate_records.first_6[0]', witness=c))
saved = source('jssa/difficulty/sweep/c-swap-target/saved-figure-targets.json')
example = next(e for e in source('jssa/difficulty/sweep/c-swap-target/coefficient-examples.json')['examples'] if e['id'] == 'AIME-2019-I-12')
m = next(m for m in saved['measurements'] if m['id'] == 'AIME-2019-I-12' and m['kind'] == 'original')
rawpath = Path(f'/tmp/q43c-swap-target-clean-20261024/runs/{m["source_run"]:03d}/receipt.json')
files.add(rawpath)
raw = read(rawpath)
assert sha(rawpath) == m['source_receipt_sha256']
summary = raw['result']['diagnostics']['pipeline_summary']
vi, v = next((i, v) for i, v in enumerate(summary['verification_records']) if v.get('verified') and v['candidate_uid'] == m['source_candidate_uid'])
assert v['values'] == m['source_values']
for offset, kind in enumerate(['length', 'area'], 1):
    dsl = source(f'jssa/difficulty/sweep/c-swap-target/inputs/AIME-2019-I-12/{kind}.json')
    measure = next(a for a in saved['measurements'] if a['id'] == dsl['id'] and a['kind'] == kind and a['source_run'] == m['source_run'])
    ref = example['targets'][kind]
    items.insert(offset, dict(key=f'AIME-2019-I-12__{kind}', id=dsl['id'], group='target', kind=kind,
                             dsl=dsl, coordinates=v['values'], saved_answer=measure['target_on_saved_figure'],
                             reference_expression=ref['value'], reference_polynomials=[ref['minimal_polynomial']],
                             reference_source='jssa/difficulty/sweep/c-swap-target/coefficient-examples.json',
                             figure_source=str(rawpath), figure_pointer=f'result.diagnostics.pipeline_summary.verification_records[{vi}]', witness=v))

for item in items:
    save(OUT / 'inputs' / (item['key'] + '.json'), item)
    item['order_rotation'] = int(idhash(item['key']), 16) % 6
    item.pop('witness')
    item.pop('dsl')
    item.pop('coordinates')
save(OUT / 'schedule.json', items)
files.update([OUT.parent.parent / 'preregistration-7.md', OUT / 'selection.md', OUT / 'rules.md', OUT / 'schedule.json'])
files.update(OUT.glob('*.py'))
files.update((OUT / 'inputs').glob('*.json'))
source_files = {str(p.relative_to(scratch)): sha(p) for p in sorted((scratch / 'src').rglob('*')) if p.is_file()}
manifest = dict(created_utc=datetime.now(timezone.utc).isoformat(), source_commit=FROZEN,
                source_hash=source_tree_hash(), frozen_source=str(scratch / 'src'), source_files=source_files,
                files={str(p): sha(p) for p in sorted(files)}, parallelism=2, cpus=sorted(os.sched_getaffinity(0))[-2:],
                python=sys.executable, python_version=sys.version, platform=platform.platform(), host=platform.node(),
                threads={k: '1' for k in ['OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS']},
                problem_count=len(items), conditions_per_problem=6, retries=0,
                limits=dict(phase_seconds=180, outer_seconds=188, memory_bytes=3 << 30),
                figures='one immutable saved figure per item; 2019 length/area share a figure',
                reference_dps=700, refinement_dps=620, stored_significant_digits=620)
save(OUT / 'pre-run-hashes.json', manifest)
(OUT / 'progress.md').write_text('# S2 進捗\n\n' + manifest['created_utc'] + ' 入力・規則・選定・コード固定。実験未開始。13件、78条件、並列2。\n')
print(json.dumps(dict(source_hash=manifest['source_hash'], selected=selected, scratch=str(scratch))))
