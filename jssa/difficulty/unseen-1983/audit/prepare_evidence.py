"""Offline text extraction/hash inventory only; no DSL execution or solver import."""
from pathlib import Path
from html.parser import HTMLParser
import hashlib
import json
import re

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
ASSETS = Path('/home/kabatan/work/solver-research-assets/corpus97-sources')

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def rows(p):
    return [json.loads(s) for s in p.read_text().splitlines() if s.strip()]

class Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.images = []
    def handle_data(self, data):
        self.parts.append(data)
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'img':
            self.parts.append(a.get('alt', '[image without alt]'))
            self.images.append(a)
        if tag in ('p', 'br', 'li', 'h2', 'h3'):
            self.parts.append('\n')
    def handle_endtag(self, tag):
        if tag in ('p', 'li', 'h2', 'h3'):
            self.parts.append('\n')
    def text(self):
        return re.sub(r'[ \t]+', ' ', ''.join(self.parts)).strip()

def extract(path, number):
    content = path.read_text()
    h = re.search(r'<h2[^>]*>\s*<span[^>]*id="Problem_' + str(number) + r'"[^>]*>.*?</h2>', content, re.S)
    assert h, (path, number)
    end = re.search(r'<h2\b', content[h.end():])
    section = content[h.end(): h.end()+end.start()] if end else content[h.end():]
    section = re.split(r'<p><a[^>]*title="[^\"]*Problem[^\"]*">Solution', section)[0]
    parser = Text()
    parser.feed(section)
    return dict(text=parser.text(), images=parser.images, line=content[:h.start()].count('\n')+1)

def main():
    if (HERE/'input-snapshot.json').exists():
        raise SystemExit('監査開始時のinput-snapshot.jsonは固定済みです。基準の上書きを拒否します。')
    log = json.loads((HERE/'primary/aops/fetch-log.json').read_text())
    sources = []
    by_name = {}
    for r in log:
        p = HERE/'primary/aops'/f"{r['name']}.html"
        if p.exists():
            assert sha(p) == r['sha256'], p
            assert p.stat().st_size == r['bytes'], p
            by_name[r['name']] = r
        sources.append(dict(r, exists=p.exists()))
    answers = {r['id']:r for r in rows(BASE/'official_answers.jsonl')}
    cases = rows(BASE/'cases.jsonl')
    out = []
    for c in cases:
        cid = c['id']
        dpath = BASE/c['dsl_path']
        assert json.loads(dpath.read_text()) == c['dsl']
        r = dict(id=cid, dsl_sha256=sha(dpath), secondary_statement=c['problem_statement'], stored_answer=answers[cid])
        if cid.startswith('AIME-'):
            _,year,n = cid.split('-')
            problem = HERE/'primary/aops'/f'{year}_AIME_Problems.html'
            key = HERE/'primary/aops'/f'{year}_AIME_Answer_Key.html'
            r['primary_statement'] = extract(problem,int(n)) if problem.exists() else None
            r['primary_problem_source'] = by_name.get(f'{year}_AIME_Problems')
            r['primary_answer_source'] = by_name.get(f'{year}_AIME_Answer_Key')
            if key.exists():
                html = key.read_text().split('mw-parser-output',1)[1]
                ordered = re.search(r'<ol>(.*?)</ol>', html, re.S).group(1)
                values = re.findall(r'<li>\s*(\d+)\s*</li>', ordered)
                assert len(values) == 15, (key, values)
                r['primary_answer'] = values[int(n)-1]
                r['answer_match'] = int(r['primary_answer']) == int(answers[cid]['secondary_answer'])
            else:
                r['primary_answer'] = None
                r['answer_match'] = None
        out.append(r)
    (HERE/'primary-extracts.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    (HERE/'source-checks.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2)+'\n')
    allowed_roots = {'dsl', 'cards', 'revisions', 'source-evidence'}
    allowed_files = {'README.md', 'authoring-rules.md', 'manifest.json', 'cases.jsonl', 'statements.jsonl',
                     'official_answers.jsonl', 'answer-provenance.json', 'duplicate-audit.json', 'validation.json',
                     'cards.md', 'build_cases.py', 'aime_definitions.py', 'aime_decisions.py', 'verify_static.py', 'seal_answers.py'}
    snapshot = {}
    for p in sorted(BASE.rglob('*')):
        rel=p.relative_to(BASE)
        permitted = rel.parts[0] in allowed_roots or str(rel) in allowed_files or (HERE/'primary') in p.parents
        if permitted and p.is_file():
            snapshot[str(rel)]=sha(p)
    (HERE/'input-snapshot.json').write_text(json.dumps(snapshot,ensure_ascii=False,indent=2)+'\n')
    for r in out:
        if r['id'].startswith('AIME'):
            print(r['id'], 'primary=',r['primary_answer'], 'secondary=',r['stored_answer']['secondary_answer'], 'match=',r['answer_match'])

if __name__ == '__main__':
    main()
