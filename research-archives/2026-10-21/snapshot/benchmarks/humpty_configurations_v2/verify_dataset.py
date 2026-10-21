"""Run the independent construction checks and bind receipts to this dataset."""
import hashlib
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def check_script(name):
    path = ROOT / 'authoring' / name
    started = time.monotonic()
    result = subprocess.run([sys.executable, str(path)], cwd=ROOT,
                            text=True, capture_output=True, timeout=180)
    return {'script': name, 'exit_code': result.returncode,
            'seconds': round(time.monotonic() - started, 3),
            'stdout': result.stdout.strip(), 'stderr': result.stderr.strip(),
            'script_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    blob = (ROOT / 'revisions.json').read_bytes()
    cards = json.loads(blob)
    accepted = [c for c in cards if c['decision'] in {'main', 'probe'}]
    scripts = sorted({c['feasibility']['script'] for c in accepted}
                     | {c['feasibility']['general_relation_script'] for c in accepted
                        if c['feasibility'].get('general_relation_script')})
    with ThreadPoolExecutor(max_workers=3) as pool:
        checks = list(pool.map(check_script, scripts))
    errors = [c['script'] for c in checks if c['exit_code']]
    # Check the data the learner actually receives, separately from researcher notes.
    for role, filename in [('main', 'training_problems.jsonl'), ('probe', 'probe_problems.jsonl')]:
        exported = [json.loads(s) for s in (ROOT / filename).read_text().splitlines()]
        expected = [{'id': c['id'], 'problem': c['problem_ja'], 'answer_exact': c['answer_exact']}
                    for c in cards if c['decision'] == role]
        if exported != expected:
            errors.append(filename + ': mismatch with source records')
    report = {
        'checked_at_utc': datetime.now(UTC).isoformat(),
        'dataset_sha256': hashlib.sha256(blob).hexdigest(),
        'accepted_numeric_examples': len(accepted),
        'scope': 'Original constructions, supplied numeric values and target values; '
                 'general relations have the separate evidence stated on each card. '
                 'This is not a repo-solver run or a training experiment.',
        'checks': checks,
        'errors': errors,
    }
    (ROOT / 'verification_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(bool(errors))


if __name__ == '__main__':
    main()
