"""Copy user-provided complete AoPS HTML. Offline only; no solver imports.

Run repeatedly while the user's download is in progress. Existing copies are
immutable. Incomplete/404 files are never admitted.
"""
from datetime import datetime, timezone
from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parents[4] / 'fetched/aime'
OUT = HERE / 'source-evidence'
LIMIT = 5_000_000

def sha(data):
    return hashlib.sha256(data).hexdigest()

class Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts, self.images = [], []
    def handle_data(self, data):
        self.parts.append(data)
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'img':
            self.parts.append(attrs.get('alt', '[image without alt]'))
            self.images.append(attrs)
        if tag in ('p', 'br', 'li', 'h2', 'h3'):
            self.parts.append('\n')
    def handle_endtag(self, tag):
        if tag in ('p', 'li', 'h2', 'h3'):
            self.parts.append('\n')
    def text(self):
        return re.sub(r'[ \t]+', ' ', ''.join(self.parts)).strip()

def problem(html, number):
    h = re.search(r'<h2[^>]*>\s*<span[^>]*id="Problem_' + str(number) + r'"[^>]*>.*?</h2>', html, re.S)
    assert h, ('missing problem', number)
    section = re.split(r'<h2\b', html[h.end():], maxsplit=1)[0]
    section = re.split(r'<p>\s*<a[^>]*>\s*Solution', section, maxsplit=1)[0]
    parser = Text()
    parser.feed(section)
    return dict(text=parser.text(), images=parser.images, line=html[:h.start()].count('\n')+1)

def answer_key(html):
    content = html.split('mw-parser-output', 1)[1]
    ordered = re.search(r'<ol[^>]*>(.*?)</ol>', content, re.S).group(1)
    values = re.findall(r'<li>\s*(\d+)\s*</li>', ordered)
    assert len(values) == 15, ('answer count', len(values))
    return values

def validate(name, data):
    assert 0 < len(data) < LIMIT, 'empty/oversized'
    html = data.decode('utf-8')
    assert 'mw-parser-output' in html and '</html>' in html.lower(), 'incomplete/non-wiki'
    assert name.removesuffix('.html') in html, 'wrong page identity'
    title = name.removesuffix('.html').replace('_', ' ') + ' - AoPS Wiki'
    assert title in re.findall(r'<title>(.*?)</title>', html, re.S), 'wrong wiki title'
    if name.endswith('Problems.html'):
        for n in range(1, 16):
            assert len(problem(html, n)['text']) > 20
    else:
        answer_key(html)
    return html

def main():
    assert not (HERE / 'prediction.lock.json').exists(), 'sources already locked'
    OUT.mkdir(parents=True, exist_ok=True)
    log_path = OUT / 'import-log.json'
    prior = json.loads(log_path.read_text()) if log_path.exists() else []
    by_name = {r['name']: r for r in prior}
    maximum_year = int(sys.argv[1]) if len(sys.argv) > 1 else 2005
    for path in sorted(SOURCE.glob('*.html')):
        if int(path.name[:4]) > maximum_year:
            continue
        stat = path.stat()
        if stat.st_size >= LIMIT:
            print(path.name, 'rejected: oversized')
            continue
        data = path.read_bytes()
        try:
            html = validate(path.name, data)
            assert stat.st_size == path.stat().st_size == len(data), 'changing source file'
        except (AssertionError, UnicodeError, IndexError, AttributeError) as error:
            print(path.name, 'not admitted:', str(error))
            continue
        destination = OUT / path.name
        if destination.exists():
            assert destination.read_bytes() == data, 'copied source changed; investigate explicitly'
            continue
        destination.write_bytes(data)
        stamp = re.search(r'web.archive.org/web/(\d{14})', html)
        by_name[path.name] = dict(
            name=path.name, local_source=str(path), bytes=len(data), sha256=sha(data),
            copied_at_utc=datetime.now(timezone.utc).isoformat(),
            source_mtime_utc=datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
            download_time_and_http_status='not observed; supplied by user',
            archive_timestamp_from_html=stamp.group(1) if stamp else None,
            archive_url_from_html_identity='https://web.archive.org/web/' + stamp.group(1) + '/https://artofproblemsolving.com/wiki/index.php/' + path.stem if stamp else None,
            validation='complete HTML; page identity; 15 problem sections or 15 numeric answers')
        print(path.name, len(data), sha(data))
    log_path.write_text(json.dumps(list(by_name.values()), ensure_ascii=False, indent=2)+'\n')
    statements = []
    for path in sorted(OUT.glob('*_Problems.html')):
        year, _, part, _ = path.stem.split('_')
        html = path.read_text()
        for n in range(1, 16):
            statements.append(dict(id=f'AIME-{year}-{part}-{n:02}', source_file=path.name,
                                   source_sha256=sha(path.read_bytes()), **problem(html,n)))
    (OUT / 'statements.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in statements))
    print('copied pages',len(by_name),'problem sections',len(statements))

if __name__ == '__main__':
    main()
