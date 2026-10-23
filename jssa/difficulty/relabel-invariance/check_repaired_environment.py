"""Import-only audit of the dedicated Q38 environment; never invokes a solver."""
from pathlib import Path
import datetime as dt
import hashlib
import json
import os
import subprocess
import tempfile

BASE = Path(__file__).resolve().parent
CLEAN = Path('/tmp/q38-58e3993-clean')
OLD = Path('/home/kabatan/work/solver/.venv')
NEW = Path('/tmp/q38-58e3993-venv')
ARCHIVE = BASE / 'execution-records/invalid-attempt-20261023T164136Z'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    plan = json.loads((BASE / 'execution-plan.json').read_text())
    code = (
        "import json,sys,geosolver;from importlib.metadata import version;"
        "from geosolver.runtime.integrity import source_tree_hash,installed_dependencies,verify_engine_lock;"
        "print(json.dumps({'import_file':geosolver.__file__,'source_hash':source_tree_hash(),"
        "'dependencies':installed_dependencies()|{'geosolver':version('geosolver')},"
        "'engine_lock':verify_engine_lock(),'executable':sys.executable,"
        "'prefix':sys.prefix,'sys_path':sys.path}))"
    )
    argv = [str(NEW / 'bin/python'), '-B', '-c', code]
    env = os.environ | plan['environment']
    parent = json.loads(subprocess.check_output(argv, cwd=CLEAN, env=env, text=True, timeout=30))
    with tempfile.TemporaryDirectory(prefix='q38-repaired-import-only-') as temporary:
        child = json.loads(subprocess.check_output(argv, cwd=temporary, env=env, text=True, timeout=30))
    for probe in (parent, child):
        assert Path(probe['import_file']).parent == CLEAN / 'src/geosolver'
        assert probe['source_hash'] == 'sha256:d8fd9bb8392ad2984276bab3386e033669246ee79586317917c322d31b4541f5'
        assert probe['engine_lock'][0]
        assert Path(probe['prefix']) == NEW
        assert '/home/kabatan/work/solver/src' not in probe['sys_path']
    previous = json.loads((ARCHIVE / 'execution-records/preflight.json').read_text())
    for name, version in previous['runtime_fingerprint']['runtime_dependencies'].items():
        assert child['dependencies'].get(name) == version, (name, version)
    differences, links, files = [], [], 0
    for path in sorted(OLD.rglob('*')):
        relative = path.relative_to(OLD)
        copy = NEW / relative
        if path.is_symlink():
            assert copy.is_symlink() and os.readlink(path) == os.readlink(copy)
            links.append({'relative_path': str(relative), 'target': os.readlink(copy)})
        elif path.is_file():
            files += 1
            assert path.stat().st_ino != copy.stat().st_ino
            if sha(path) != sha(copy):
                differences.append(str(relative))
    assert differences == ['lib/python3.12/site-packages/_editable_impl_geosolver.pth'], differences
    original = ARCHIVE / 'stage2.py'
    expected = original.read_text().replace(
        "EXTERNAL = Path('/tmp/q38-58e3993-execution')",
        "EXTERNAL = Path('/tmp/q38-58e3993-repaired-execution')",
    ).replace(
        "PYTHON = Path('/home/kabatan/work/solver/.venv/bin/python')",
        "PYTHON = Path('/tmp/q38-58e3993-venv/bin/python')",
    )
    assert (BASE / 'stage2.py').read_text() == expected
    record = {
        'at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'solver_calls': 0, 'status': 'passed',
        'operation': 'Imports, metadata and source-integrity checks only; no solver entrypoint. Child starts in fresh temporary cwd.',
        'old_venv': str(OLD), 'dedicated_venv': str(NEW),
        'clone_method': 'shutil.copytree; distinct regular-file inodes; original symlinks preserved',
        'regular_files_compared': files, 'clone_differences': differences, 'symlinks': links,
        'old_pth_content': (OLD / differences[0]).read_text(),
        'new_pth_content': (NEW / differences[0]).read_text(),
        'original_venv_modified': False, 'network_used': False,
        'argv': argv, 'environment': plan['environment'],
        'parent_cwd': str(CLEAN), 'parent_probe': parent,
        'child_cwd': temporary, 'child_probe': child,
        'stage2_changes': ['Python absolute path placeholder binding', 'external results directory placeholder binding'],
        'stage2_original_sha256': sha(original), 'stage2_repaired_sha256': sha(BASE / 'stage2.py'),
        'prediction_rules_selection_dsl_plan_solver_grader_runner_contract_changed': False,
        'invalid_first_four_disposition': '契約違反の無効実行（環境不備、再実行して置換）',
        'restart_reason': 'Environment repair only, explicitly authorized by user; no result-dependent selection. Restart all 840 runs at batch 0.',
        'audit_note': 'Initial auxiliary version assertion omitted the geosolver distribution itself from installed_dependencies(); corrected the import-only audit to query its package version explicitly. No solver call occurred.',
        'loadavg': os.getloadavg(),
    }
    (BASE / 'execution-records/environment-repair.json').write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + '\n'
    )
    print(json.dumps({'status': 'passed', 'solver_calls': 0,
                      'child_import_file': child['import_file'],
                      'regular_files_compared': files, 'clone_differences': differences}))


if __name__ == '__main__':
    main()
