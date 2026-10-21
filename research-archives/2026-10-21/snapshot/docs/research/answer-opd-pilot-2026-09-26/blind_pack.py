"""Create anonymous proof-only grading packets; keep identities separately."""
import argparse
import hashlib
import json
import random
from pathlib import Path


def parse_input(item):
    if '=' not in item:
        raise ValueError(f'Expected condition=directory, got {item!r}')
    condition, directory = item.split('=', 1)
    if not condition or not directory:
        raise ValueError(f'Expected non-empty condition and directory, got {item!r}')
    return condition, Path(directory).resolve()


def collect_proof_outputs(item, allow_partial=False):
    condition, directory = parse_input(item)
    receipt = json.loads((directory / 'receipt.json').read_text())
    assert receipt['status'] == 'complete' or allow_partial, directory
    records = []
    for file in sorted(directory.glob('*.json')):
        try:
            row = json.loads(file.read_text())
        except json.JSONDecodeError:
            if allow_partial:
                continue  # A concurrently written output has not finished yet.
            raise
        if not isinstance(row, dict) or 'final_text' not in row:
            continue
        if 'proof' not in row.get('evaluation_role', ''):
            continue
        records.append((condition, file, row))
    return records


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--inputs', nargs='+', required=True, help='condition=directory')
    ap.add_argument('--anchor-inputs', nargs='+', default=[],
                    help='Optional reference-only proof sources, as condition=directory')
    ap.add_argument('--anchors-per-condition', type=int, default=4,
                    help='Deterministically sample this many proof outputs per anchor condition (default: 4)')
    ap.add_argument('--out', required=True)
    ap.add_argument('--seed', type=int, default=2026092691)
    ap.add_argument('--partial-intersection', action='store_true',
                    help='Use only finished proof jobs present in every input, even while runs continue')
    ap.add_argument('--exclude-key', type=Path,
                    help='Exclude condition/job pairs already assigned in an earlier packet')
    ap.add_argument('--id-prefix', default='A')
    a = ap.parse_args()
    if a.anchors_per_condition < 0:
        ap.error('--anchors-per-condition must be non-negative')

    records = [(condition, file, row, False)
               for item in a.inputs
               for condition, file, row in collect_proof_outputs(
                   item, allow_partial=a.partial_intersection)]
    if a.partial_intersection:
        by_condition = {}
        for condition, _, row, _ in records:
            by_condition.setdefault(condition, set()).add(row['id'])
        expected_conditions = {item.split('=', 1)[0] for item in a.inputs}
        assert set(by_condition) == expected_conditions, 'Some input has no finished proof jobs'
        shared = set.intersection(*by_condition.values())
        records = [r for r in records if r[2]['id'] in shared]

    excluded = set()
    if a.exclude_key:
        excluded = {(r['condition'], r['job_id']) for r in json.loads(a.exclude_key.read_text())}
        records = [r for r in records if (r[0], r[2]['id']) not in excluded]
    assert records, 'No unassigned primary proof outputs'

    # Reference anchors are frozen calibration examples. They always come from
    # completed runs, and prior key rows exclude both primary jobs and anchors.
    anchors = []
    anchor_conditions = set()
    anchor_rng = random.Random(a.seed)
    for item in a.anchor_inputs:
        condition, _ = parse_input(item)
        if condition in anchor_conditions:
            ap.error(f'duplicate anchor condition: {condition}')
        anchor_conditions.add(condition)
        candidates = [r for r in collect_proof_outputs(item)
                      if (r[0], r[2]['id']) not in excluded]
        if len(candidates) < a.anchors_per_condition:
            ap.error(f'anchor condition {condition!r} has {len(candidates)} unassigned proof outputs; '
                     f'{a.anchors_per_condition} requested')
        chosen = anchor_rng.sample(candidates, a.anchors_per_condition)
        anchors.extend((*r, True) for r in chosen)

    records.extend(anchors)
    random.Random(a.seed).shuffle(records)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=False)
    packets = [[], []]
    key = []
    for index, (condition, file, row, reference_only) in enumerate(records):
        anon = f'{a.id_prefix}{index+1:03d}'
        packet = dict(anonymous_id=anon, prompt=row['messages'][0]['content'],
                      answer=row['final_text'], finish_reason=row['finish_reason'])
        packets[index % 2].append(packet)
        key.append(dict(anonymous_id=anon, condition=condition, job_id=row['id'],
                        source_id=row.get('source_id'), role=row['evaluation_role'],
                        sample=row['sample'], raw_file=str(file),
                        raw_sha256=hashlib.sha256(file.read_bytes()).hexdigest(),
                        reference_only=reference_only))
    for index, packet in enumerate(packets):
        (out / f'packet-{index+1}.json').write_text(json.dumps(packet, ensure_ascii=False, indent=2)+'\n')
    (out / 'private-unblinding.json').write_text(json.dumps(key, indent=2)+'\n')
    print(json.dumps(dict(proofs=len(records), primary_proofs=len(records)-len(anchors),
                          reference_anchors=len(anchors), packet_sizes=list(map(len, packets)),
                          out=str(out))))


if __name__ == '__main__':
    main()
