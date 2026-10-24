"""Build S10 B switches from the read-only BASE1; never run a solver."""
import ast
import csv
import difflib
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

OUT = Path(__file__).resolve().parent
REPO = OUT.parents[5]
BASE = Path('/tmp/mechanism-7b-lkdjle5l/final')
FROZEN = Path('/tmp/mechanism-S1-1m9aomj8/frozen')
EXPECTED = 'sha256:03a44bfbb743b972d95306c63a14c04b78c7d12b96a1ba83d147c56eea7f86a3'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def inventory(root):
    return {str(p.relative_to(root)): sha(p) for p in sorted(root.rglob('*'))
            if p.is_file() and '__pycache__' not in p.parts}


def source_hash(root):
    digest = hashlib.sha256()
    package = root / 'src/geosolver'
    for p in sorted(package.rglob('*')):
        rel = p.relative_to(package)
        if (p.is_file() and p.suffix in {'.py', '.json', '.toml'}
                and p.name != 'engine-lock.json'
                and not {'frontend', '__pycache__'}.intersection(rel.parts)):
            digest.update(str(rel).encode() + b'\0' + p.read_bytes().replace(b'\r\n', b'\n') + b'\0')
    return 'sha256:' + digest.hexdigest()


def main():
    assert not (OUT / 'source-hashes.json').exists(), 'Do not replace frozen preparation'
    before = inventory(BASE)
    assert source_hash(BASE) == EXPECTED
    work = Path(tempfile.mkdtemp(prefix='mechanism-S10-'))
    final = work / 'final'
    shutil.copytree(BASE, final, ignore=shutil.ignore_patterns('__pycache__'))

    def edit(rel, old, new):
        p = final / 'src/geosolver' / rel
        text = p.read_text()
        assert text.count(old) == 1, (rel, old)
        p.write_text(text.replace(old, new))

    flags = ['NO_FLOAT_MARGIN_FLOOR', 'NO_NOMAD_GUARD_PENALTY',
             'NO_SEARCH_BOX_INFERENCE', 'NO_GUARD_BOUND_INFERENCE',
             'NO_SEARCH_BOX_SCALING', 'NO_HIDDEN_CONSTRAINT_MODE']
    edit('runtime/ablation.py', 'ABLATIONS = (',
         'ABLATIONS = (\n' + ''.join(f'    "{f}",\n' for f in flags).rstrip('\n'))
    core = 'engine/standard/evaluation/_hard_feasibility_core.py'
    edit(core, 'from geosolver.runtime.deadline import check_deadline',
         'from geosolver.runtime.ablation import ablated\nfrom geosolver.runtime.deadline import check_deadline')
    for kind in ('LINE', 'TRIANGLE', 'INTERSECTION'):
        edit(core, f'    threshold = {kind}_MARGIN_MIN if allow_float else mp.mpf("0")',
             f'    threshold = {kind}_MARGIN_MIN if allow_float else mp.mpf("0")\n'
             '    if allow_float and ablated("NO_FLOAT_MARGIN_FLOOR"):\n'
             '        threshold = mp.mpf("0")')
    adapter = 'engine/standard/search/nomad_blackbox_adapter.py'
    edit(adapter, 'from geosolver.runtime.deadline import deadline_scope, expired',
         'from geosolver.runtime.ablation import ablated\nfrom geosolver.runtime.deadline import deadline_scope, expired')
    edit(adapter, '            return 0\n        evaluation = evaluate_search_point(',
         '            if ablated("NO_HIDDEN_CONSTRAINT_MODE"):\n'
         '                # Keep the failure record; only NOMAD sees a valid finite penalty.\n'
         '                point.setBBO(str(NON_FINITE_SCORE_PENALTY).encode("utf-8"))\n'
         '                return 1\n'
         '            return 0\n        evaluation = evaluate_search_point(')
    edit(adapter, '        point.setBBO(str(score).encode("utf-8"))',
         '        if ablated("NO_NOMAD_GUARD_PENALTY"):\n'
         '            # nomad-wall mode N: preserve record.score and eligibility.\n'
         '            point.setBBO(str(scaled_norm_sq).encode("utf-8"))\n'
         '        else:\n'
         '            point.setBBO(str(score).encode("utf-8"))')
    cfg = 'engine/standard/search/nomad_config.py'
    edit(cfg, 'from math import ceil', 'from math import ceil\n\nfrom geosolver.runtime.ablation import ablated')
    edit(cfg, 'f"DISCO_MADS_HID_CONST {str(DISCO_MADS_HID_CONST).lower()}"',
         'f"DISCO_MADS_HID_CONST {str(False if ablated(\"NO_HIDDEN_CONSTRAINT_MODE\") else DISCO_MADS_HID_CONST).lower()}"')
    domain = 'problem/domain_bounds.py'
    edit(domain, 'from dataclasses import dataclass', 'from dataclasses import dataclass, replace')
    edit(domain, 'from geosolver.problem.expression_source import source_expression',
         'from geosolver.runtime.ablation import ablated\nfrom geosolver.problem.expression_source import source_expression')
    edit(domain, 'def search_bounds(spec) -> list[tuple[float, float]]:',
         'def search_box_domains(spec) -> dict[str, AxisDomain]:\n'
         '    """Search-only inference; mathematical_bounds remains authoritative."""\n'
         '    if ablated("NO_SEARCH_BOX_INFERENCE") or ablated("NO_GUARD_BOUND_INFERENCE"):\n'
         '        # Explicit bounds and construction parameter domains still apply.\n'
         '        return mathematical_bounds(replace(spec, guards=[]))\n'
         '    return mathematical_bounds(spec)\n\n\n'
         'def search_bounds(spec) -> list[tuple[float, float]]:')
    p = final / 'src/geosolver' / domain
    txt = p.read_text()
    start = txt.index('    for index, expr in enumerate(spec.constraints):', txt.index('def search_bounds('))
    end = txt.index('    domains = mathematical_bounds(spec)', start)
    block = txt[start:end]
    txt = txt[:start] + ('    if not (ablated("NO_SEARCH_BOX_INFERENCE") or ablated("NO_SEARCH_BOX_SCALING")):\n'
                         + ''.join('    ' + line if line.strip() else line for line in block.splitlines(True))) + txt[end:]
    txt = txt[:txt.index('def search_bounds(')] + txt[txt.index('def search_bounds('):].replace(
        'domains = mathematical_bounds(spec)', 'domains = search_box_domains(spec)', 1)
    p.write_text(txt)
    locks = 'engine/standard/interpreter/compile/infer_bounds.py'
    edit(locks, 'from geosolver.problem.domain_bounds import mathematical_bounds',
         'from geosolver.problem.domain_bounds import search_box_domains')
    edit(locks, 'domains = mathematical_bounds(spec)', 'domains = search_box_domains(spec)')
    after_hash = source_hash(final)
    lock = final / 'src/geosolver/engine-lock.json'
    lock.write_text(lock.read_text().replace(EXPECTED, after_hash))
    for p in final.rglob('*.py'):
        ast.parse(p.read_text(), filename=str(p))
    after = inventory(final)
    changed = [p for p in before if before[p] != after[p]]
    patch = ''.join(''.join(difflib.unified_diff((BASE / p).read_text().splitlines(True),
                        (final / p).read_text().splitlines(True), fromfile='a/' + p, tofile='b/' + p))
                    for p in changed)
    (OUT / 'switch-b.patch').write_text(patch)
    replay = work / 'replay'
    shutil.copytree(BASE, replay, ignore=shutil.ignore_patterns('__pycache__'))
    for args in (['--check'], []):
        subprocess.run(['git', 'apply', *args, str(OUT / 'switch-b.patch')], cwd=replay, check=True)
    assert inventory(replay) == after
    protected = [p for p in before if '/evaluation/verification_' in p or
                 p.endswith('/evaluation/final_verifier.py') or '/exact_assembly/' in p]
    frozen_inv = inventory(FROZEN)
    assert len(protected) == 12
    assert all(before[p] == after[p] == frozen_inv[p] for p in protected)
    assert inventory(BASE) == before
    provenance = REPO / 'jssa/difficulty/nomad-wall/patch/nomad_wall_patch.py'
    manifest = dict(base_source=str(BASE), patched_source=str(final), replay_source=str(replay),
                    frozen_source=str(FROZEN), base_source_hash=EXPECTED, patched_source_hash=after_hash,
                    frozen_source_hash=source_hash(FROZEN), base_files_sha256=before,
                    patched_files_sha256=after, frozen_files_sha256=frozen_inv,
                    changed_files=changed, protected_files={p: before[p] for p in protected},
                    replay_byte_identical=True, base_unmodified=True,
                    provenance=dict(path=str(provenance.relative_to(REPO)), sha256=sha(provenance)),
                    patch_sha256=sha(OUT / 'switch-b.patch'))
    (OUT / 'source-hashes.json').write_text(json.dumps(manifest, indent=2) + '\n')
    arms = {'B0': {}}
    for arm, flag in zip(('B014','B046','B005_006','B005','B006','B045'), flags):
        arms[arm] = {'GEOSOLVER_ABLATE_' + flag: '1'}
    arms['B014_046'] = {**arms['B014'], **arms['B046']}
    (OUT / 'configs.json').write_text(json.dumps(dict(arms=arms,
        thread_environment={k:'1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')},
        smoke=dict(max_parallel=1, outer_seconds=10, inner_seconds=3, seed=0,
                   full_process_arms=list(arms)[:-1], extra_composition_probe='B014_046')), indent=2) + '\n')
    # First ID in each pre-existing classification; do not read performance columns.
    with (REPO / 'jssa/difficulty/false-attractors/per-problem.csv').open() as f:
        classification = [(r['id'], r['main_cause']) for r in csv.DictReader(f)]
    ids = {cause: next(i for i,c in classification if c == cause) for cause in ('a','b')}
    inputs = []
    for line in (REPO / 'benchmarks/cases.jsonl').open():
        r = json.loads(line)
        if r['id'] in ids.values():
            path = (REPO / 'benchmarks' / r['dsl_path']).resolve()
            inputs.append(dict(case_id=r['id'], group=next(c for c,i in ids.items() if i==r['id']),
                               path=str(path), sha256=sha(path)))
    assert len(inputs) == 2
    inputs.sort(key=lambda r:r['group'])
    (OUT / 'inputs.json').write_text(json.dumps(inputs, indent=2) + '\n')
    print(json.dumps(dict(work=str(work), changed_files=changed, source_hash=after_hash, inputs=inputs), indent=2))


if __name__ == '__main__':
    main()
