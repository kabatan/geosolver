"""Build researcher review and solution-free evaluation exports.

Only this directory is written. Approved training files are hashed, never edited.
"""
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TRAIN = ROOT.parent / 'humpty_configurations_v2' / 'training_problems.jsonl'
APPROVED_TRAIN_SHA256 = 'b7fb1929a90bc4f5440825cdd47d238d2ead410c811be3d4037ed54066c79fc7'
ROLES = {
    'transfer_main': '別配置・別関係への転移',
    'same_configuration': '同配置の証明への転移',
}
INSTRUCTION = ('以下の命題を証明してください。必要な仮定と推論が追えるように説明してください。解法は問いません。'
               '通常の定理は用いてよいですが、この配置に固有の非自明な性質や、結論と実質的に同じ命題は、'
               '名称の引用だけで済ませず根拠を示してください。')


def seq(value):
    return value if isinstance(value, list) else [value] if value else []


def load_cards():
    cards = []
    for name in ['ev02.json', 'orthic_bridge.json', 'simple_dumpty.json', 'aops_candidate.json', 'same_configuration_basics.json']:
        path = ROOT / 'authoring' / name
        if not path.exists():
            raise ValueError(f'Awaiting {path.name}')
        for card in json.loads(path.read_text()):
            card['authoring_file'] = str(path.relative_to(ROOT))
            cards.append(card)
    amendments_path = ROOT / 'authoring' / 'curation.json'
    amendments = json.loads(amendments_path.read_text()) if amendments_path.exists() else {}
    for card in cards:
        card.update(amendments.get(card['id'], {}))
        for key in ['overlap_audit_ja', 'verification_ja', 'scoring_ja', 'domain_ja']:
            card[key] = seq(card.get(key))
        for key in ['key_lemma_ja', 'after_discovery_ja']:
            if isinstance(card.get(key), list):
                card[key] = '\n'.join(card[key])
    return sorted(cards, key=lambda c: (list(ROLES).index(c['role']), c['id'] != 'EV02', c['id']))


def validate(cards, train_ids):
    assert len({c['id'] for c in cards}) == len(cards), 'duplicate IDs'
    for card in cards:
        for field in ['id', 'role', 'family_id', 'title_ja', 'problem_ja', 'solution_ja',
                      'transfer_target_ja', 'overlap_audit_ja', 'scoring_ja', 'verification_ja',
                      'short_route_ja', 'after_discovery_ja', 'key_lemma_ja', 'overlap_level_ja']:
            assert card.get(field), (card['id'], field)
        assert card['role'] in ROLES
        assert set(card.get('training_overlap_ids', [])) <= train_ids, card['id']
        assert not re.search(r'Humpty|Dumpty|ハンプティ|ダンプティ|Sharky', card['problem_ja'], re.I)
        assert card['id'] not in train_ids, 'evaluation ID appears in training'
        for src in card.get('source', []):
            assert src.get('url') is None or src['url'].startswith('https://')


def catalogue(cards, stats):
    out = ['# 数値学習から証明への転移：評価候補 v2', '',
           '問題と完全解答を確認するための資料。学習には使わない。採点・測定方針は [README](README.md) を参照。', '',
           f"承認済みの主学習37配置と照合。証明問題は{len(cards)}題。役割別の成績を分け、総合正解数で混ぜない。", '',
           '| ID | 題材 | 役割 |', '|---|---|---|']
    for c in cards:
        out.append(f"| [{c['id']}](#{c['id'].lower()}) | {c['title_ja']} | {ROLES[c['role']]} |")
    for c in cards:
        out += ['', f"## {c['id']}", '', f"**{c['title_ja']} — {ROLES[c['role']]}**", '',
                '### 問題', '', c['problem_ja'], '', '### 評価する転移', '', c['transfer_target_ja'], '',
                '**補助構成：** ' + c.get('key_auxiliary_ja', '—'), '',
                '**共通する証明の核：** ' + c['family_id'], '', '### 学習との重なり', '']
        out += ['- ' + s for s in c['overlap_audit_ja']]
        out += ['', '**関連する主学習ID：** ' + ', '.join(c.get('training_overlap_ids', [])), '',
                '### 補助点を導入した後の短い筋', '']
        out += [f'{i}. {s}' for i, s in enumerate(c['short_route_ja'], 1)]
        out += ['', '**残る処理：** ' + c['after_discovery_ja'], '', '**核心の根拠：** ' + c['key_lemma_ja'], '', '### 完全解答', '']
        out += [f'{i}. {s}' for i, s in enumerate(c['solution_ja'], 1)]
        for alt in c.get('alternative_solutions_ja', []):
            out += ['', '### 別解：' + alt.get('code', ''), '']
            out += [f'{i}. {s}' for i, s in enumerate(alt['steps'], 1)]
        for heading, field in [('条件・枝', 'domain_ja'), ('採点', 'scoring_ja'), ('数学的な検証', 'verification_ja')]:
            out += ['', '### ' + heading, ''] + ['- ' + s for s in c[field]]
        out += ['', '**新規性の扱い：** ' + c.get('novelty_status', '原著性・事前学習での未見性は主張しない。'), '', '### 出典・背景資料', '']
        out += ["- " + (f"[{s['title']}]({s['url']})" if s.get('url') else s['title']) + f" — {s.get('locator', '')}" for s in c.get('source', [])]
    return '\n'.join(out) + '\n'


def main():
    cards = load_cards()
    train_rows = [json.loads(line) for line in TRAIN.read_text().splitlines() if line]
    train_ids = {r['id'] for r in train_rows}
    assert len(train_ids) == 37, 'Approved training set changed; repeat overlap audit'
    assert hashlib.sha256(TRAIN.read_bytes()).hexdigest() == APPROVED_TRAIN_SHA256, 'Training content changed; repeat overlap audit'
    validate(cards, train_ids)
    blob = json.dumps(cards, ensure_ascii=False, indent=2) + '\n'
    digest = hashlib.sha256(blob.encode()).hexdigest()
    stats = {'total': len(cards), 'roles': dict(Counter(c['role'] for c in cards)),
             'main_families': sorted({c['family_id'] for c in cards if c['role'] == 'transfer_main'})}
    manifest = {
        'version': 2, 'status': 'mathematically_checked_candidates_awaiting_user_review',
        'dataset_sha256': digest, 'stats': stats, 'training_count': len(train_ids),
        'training_file': str(TRAIN.relative_to(ROOT.parent)),
        'training_sha256': hashlib.sha256(TRAIN.read_bytes()).hexdigest(),
        'training_ids': sorted(train_ids),
        'never_add_to_training': ['EV01', 'EV02', 'H10', 'H11', 'DB09'],
        'scoring_policy': 'complete proof required; target property citation alone insufficient; all valid methods equal credit',
        'model_measurements_run': False,
        'training_DA15_retained': True,
        'user_requested_same_configuration_group': True,
        'group_scores_reported_separately': True,
        'retired_v1_primary_candidates': ['EV01', 'CE01', 'CE02', 'DE01', 'DE02'],
    }
    (ROOT / 'researcher_problems.json').write_text(blob)
    prompts = [{'id': c['id'], 'prompt': INSTRUCTION + '\n\n' + c['problem_ja']} for c in cards]
    (ROOT / 'evaluation_prompts.jsonl').write_text(''.join(json.dumps(p, ensure_ascii=False) + '\n' for p in prompts))
    manifest['evaluation_prompts_sha256'] = hashlib.sha256((ROOT / 'evaluation_prompts.jsonl').read_bytes()).hexdigest()
    (ROOT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    for role in ROLES:
        ids = {c['id'] for c in cards if c['role'] == role}
        (ROOT / (role + '_prompts.jsonl')).write_text(''.join(json.dumps(p, ensure_ascii=False) + '\n' for p in prompts if p['id'] in ids))
    hints = [{'id': c['id'], 'condition': 'auxiliary_hint', 'prompt': INSTRUCTION + '\n\n' + c['problem_ja'] + '\n\n補助点の指定：' + c['auxiliary_hint_ja']} for c in cards if c.get('auxiliary_hint_ja')]
    (ROOT / 'auxiliary_hint_prompts.jsonl').write_text(''.join(json.dumps(h, ensure_ascii=False) + '\n' for h in hints))
    manifest['hint_condition_count'] = len(hints)
    manifest['hints_are_not_independent_problems'] = True
    manifest['auxiliary_hint_prompts_sha256'] = hashlib.sha256((ROOT / 'auxiliary_hint_prompts.jsonl').read_bytes()).hexdigest()
    (ROOT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    (ROOT / 'catalogue.md').write_text(catalogue(cards, stats))
    problem_text = ['# 評価用証明問題 — 問題文のみ', '', INSTRUCTION, '']
    for card in cards:
        problem_text += ['## ' + card['id'], '', card['problem_ja'], '']
    (ROOT / 'problems_only.md').write_text('\n'.join(problem_text))
    payload = json.dumps({'cards': cards, 'manifest': manifest, 'roles': ROLES}, ensure_ascii=False).replace('</', '<\\/')
    template = (ROOT / 'review_template.html').read_text()
    (ROOT / 'review.html').write_text(template.replace('/*DATASET*/null', payload))
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
