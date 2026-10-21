"""Join blinded grades by immutable response content; never by matching problem ID alone."""
from pathlib import Path
import hashlib, json

P = Path(__file__).resolve().parent
O = P.parents[2] / 'qwen/.runtime/related_numeric_sft_20260928'

def read(p): return json.loads(p.read_text())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def content_hash(response):
    content = {k: response[k] for k in ['messages', 'raw_text', 'finish_reason']}
    return hashlib.sha256(json.dumps(content, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

def main():
    manifest = read(P/'review/review-manifest.json')
    bank = {}
    for entry in manifest:
        grade_file = P/'review'/entry['file']
        grades = read(grade_file)
        if isinstance(grades, dict): grades = grades['cases']
        mapping = read(O/f"private-{entry['kind']}-{entry['label']}.json")
        for grade in grades:
            source = mapping[grade['case_id']]
            source_path = Path(source['file'])
            assert sha(source_path) == source['file_sha256']
            response = read(source_path)
            key = content_hash(response)
            normalized = dict(grade)
            if 'calibrated_status' in grade:
                normalized['derivation_status'] = grade['calibrated_status']
            bank[key] = {'kind': entry['kind'], 'grade': normalized,
                         'grade_file': str(grade_file), 'grade_file_sha256': sha(grade_file),
                         'original_source': source, 'content_sha256': key}
    output = {'reviewed_contents': len(bank), 'bank': bank,
              'matching_rule': 'Identical messages, entire raw text, and finish reason; source file integrity checked against blind packet mapping.'}
    if (O/'numeric-scores.json').exists():
        scores = read(O/'numeric-scores.json')
        need = scores['proof'] + [r for r in scores['numeric'] if r['split']=='untrained_configuration' and (r['numeric_correct'] is True or r['numeric_correct'] is None)]
        final = []
        for row in need:
            source = Path(row['file'])
            assert sha(source) == row['file_sha256']
            key = content_hash(read(source))
            final.append({'arm':row['arm'], 'job_id':row['job_id'], 'source_id':row['source_id'],
                          'finish_reason':row['finish_reason'], 'file':row['file'],
                          'content_sha256':key, 'review':bank.get(key)})
        output['final_required'] = final
        output['final_missing'] = [dict(arm=x['arm'], job_id=x['job_id'], file=x['file']) for x in final if x['review'] is None]
    (O/'review-bank.json').write_text(json.dumps(output, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'reviewed_contents':len(bank), 'final_missing':output.get('final_missing')}, ensure_ascii=False))

if __name__ == '__main__': main()
