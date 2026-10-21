"""Assemble an explicit, researcher-curated AP01 problem pack. No training."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SOURCE = ROOT / 'benchmarks/humpty_configurations_v2/authoring/da_revision.json'
DB_SOURCE = ROOT / 'benchmarks/humpty_configurations_v2/authoring/db_revision.json'
PROOF_SOURCE = ROOT / 'benchmarks/humpty_proof_evaluation_v2/problems_only.md'
SOURCE_PAPER = 'https://www.awesomemath.org/wp-pdf-files/math-reflections/mr-2021-04/mr_4_2021_midpoint_of_symmedian_chord.pdf'

# Titles describe constructions only; they do not disclose a hidden relation.
SELECTION = [
    ('DA01', '頂点で接する二円', '二つの接円の第2交点は、AP01のFと同じ点。中線と特殊な弦の長さを結ぶ。'),
    ('DA02', '120°の交点と重心を通る割線', '頂角60°の場合の120°点が同じ特殊点となる。重心・円の割線へ関係を移す。'),
    ('DA03', '接円と外心を通る円', '別の二円で得た同じ特殊点から外心を通る直線を作り、隠れた接線性と方べきを使う。'),
    ('DA04', '大きな円に内接する二円', '三角形を取り直すと同じ特殊点の構成になる。共通弦の中点という別の現れ方を扱う。'),
    ('DA06', '二つの接円と中線', '同じ特殊点と中線上の別の円交点を反射で関連付ける。AP01の円と外心の関係に近い。'),
    ('DA07', '外心側と垂心側に作る二組の円', '外心側の点はAP01のFと同じ特殊点。垂心側の点と組み合わせ、平行性・相似へつなぐ。'),
    ('DA08', '外心を通る円と平行四辺形', '平行四辺形の対角線と直線AQから同じ特殊点を構成する。円への所属が数値に現れる。'),
    ('DA11', '辺の中点で接する二円', '頂点ではなく二つの中点で接する円から同じ特殊点を得る。角の関係を新しい円の半径へ移す。'),
    ('DB02', '角指定と倍長で作る交点', '角を移した二本の線と倍長で、特殊な弦の端点を得る。その弦の中点がAP01のFに対応する。'),
    ('DB12', '平行線で作る二つの円', '異なる内分点から作る二円の共通点がAP01のFと同じ特殊点。円族の固定点という別の現れ方を扱う。'),
]
GUARD = '記載した円は非退化で、指定した交点は相異なり有限に存在するものとする。'


def dump(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')


def main():
    cards = {r['id']: r for p in [SOURCE, DB_SOURCE] for r in json.loads(p.read_text())}
    proof = PROOF_SOURCE.read_text().split('\n## AP01\n', 1)[1].split('\n## ', 1)[0].strip()
    (HERE/'proof_problem.md').write_text('# 評価に残す証明問題 AP01\n\n' + proof + '\n')
    public, key, notes = [], [], []
    for i, (source_id, title, connection) in enumerate(SELECTION, 1):
        cid = f'PN{i:02d}'
        card = cards[source_id]
        problem = card['problem_ja'] + '\n\n' + GUARD
        public.append({'id': cid, 'problem_ja': problem})
        key.append({'id': cid, 'source_id': source_id, 'answer_exact': card['answer_exact'],
                    'givens': card['givens'], 'query': card['query']})
        notes.append({'id': cid, 'source_id': source_id, 'title_ja': title,
                      'connection_to_AP01_ja': connection,
                      'source_solution_status': card['feasibility'].get('solution_status', 'see_source'),
                      'source_derivation_ja': card['geometry_solution_ja'],
                      'parameter_family_ja': card['parameter_family_ja'],
                      'review_notes_ja': card['review_notes_ja']})
    assert len(public) == len({r['problem_ja'] for r in public}) == 10
    assert all(set(r) == {'id', 'problem_ja'} for r in public)
    (HERE/'numeric_problems.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in public))
    # Keep only neutral construction titles alongside the learner-facing text.
    md = '# AP01に関連する求値問題10種類 — 問題文のみ\n\n各問は独立した問題であり、点名は問ごとに定義し直す。\n'
    for row, meta in zip(public, notes):
        md += f"\n## {row['id']}　{meta['title_ja']}\n\n{row['problem_ja']}\n"
    (HERE/'numeric_problems.md').write_text(md)
    dump(HERE/'answer_key.json', key)
    dump(HERE/'researcher_metadata.json', notes)
    answer_md = '# 解答とAP01への接続 — 研究者用\n\nこのファイルの解法・関係式は、数値のみを教師にする実験の学習入力には含めない。\n'
    for row, meta in zip(key, notes):
        answer_md += f"\n## {row['id']}　{meta['title_ja']}（元ID: {row['source_id']}）\n\n"
        answer_md += f"**答え：{row['answer_exact']}**\n\nAP01との関係：{meta['connection_to_AP01_ja']}\n\n"
        answer_md += '\n'.join(f'{i}. {step}' for i, step in enumerate(meta['source_derivation_ja'], 1)) + '\n'
        answer_md += f"\n数値を変える方向：{meta['parameter_family_ja']}\n"
    (HERE/'answer_key.md').write_text(answer_md)
    dump(HERE/'manifest.json', {
        'proof_id': 'AP01', 'numeric_problem_types': 10,
        'source_ids': [x[0] for x in SELECTION],
        'design': 'Human-curated related constructions; not an automatic theorem-to-problem-family generator.',
        'scope': '10 related task templates, not 10 independent mathematical laws or 10 disjoint geometry families.',
        'teacher_export': 'No SFT launched. Public JSONL contains questions only; solutions and answers are separate.',
        'source_paper': SOURCE_PAPER,
        'source_hashes': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in [SOURCE, DB_SOURCE, PROOF_SOURCE, Path(__file__)]},
        'artifacts': {name: hashlib.sha256((HERE/name).read_bytes()).hexdigest()
                      for name in ['proof_problem.md', 'numeric_problems.md', 'numeric_problems.jsonl',
                                   'answer_key.json', 'answer_key.md', 'researcher_metadata.json']},
    })
    print('Prepared AP01 and 10 distinct numerical problem statements; no training launched.')


if __name__ == '__main__':
    main()
