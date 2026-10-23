"""Read saved HMMT booklets and record answer-line provenance; no solving."""
from pathlib import Path
import hashlib
import json
import re

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
SOURCES=Path('/home/kabatan/work/solver-research-assets/corpus97-sources')

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def section(path,n):
    text=path.read_text()
    # Form-feed can immediately precede a problem number in pdftotext output.
    pattern=r'(?m)(?:^|\f)[ \t]*'+str(n)+r'\. '
    m=re.search(pattern,text)
    assert m, (path,n)
    start=m.start()
    if text[start:start+1]=='\f':
        start+=1
    next_start=re.search(r'(?m)(?:^|\f)[ \t]*'+str(n+1)+r'\. ',text[m.end():])
    end=m.end()+next_start.start() if next_start else len(text)
    return text[start:end].strip(), text[:start].count('\n')+1, start, text

def main():
    answers={r['id']:r for r in map(json.loads,(BASE/'official_answers.jsonl').read_text().splitlines())}
    old_manifest=json.loads((BASE/'revisions/v2-before-aime/manifest.json').read_text())
    old_hashes={s['path']:s['sha256'] for s in old_manifest['sources']}
    out=[]
    page_map={(2016,1):([1],1),(2022,7):([1],3),(2022,8):([1,2],4),(2023,6):([1],3)}
    for (year,n),(problem_pages,answer_page) in page_map.items():
        cid=f'HMMT-{year}-FEB-GEO-{n:02}'
        problem=SOURCES/f'hmmt-{year}-geo-problems.txt'
        solution=SOURCES/f'hmmt-{year}-geo-solutions.txt'
        ptext,pline,_,_=section(problem,n)
        stext,_,sstart,full=section(solution,n)
        a=re.search(r'Answer:[ \t]*([^\n]+)',stext)
        assert a
        answer_text=a.group(1).strip()
        numbers=[int(s) for s in re.findall(r'\d+',answer_text)]
        answer=numbers if len(numbers)>1 else numbers[0]
        assert answer==answers[cid]['official_answer']
        line=next(i for i,s in enumerate(full.split('\n'),1) if i>full[:sstart].count('\n') and 'Answer:' in s)
        assert sha(problem)==old_hashes[str(problem)]
        files={}
        for p in (problem,solution,problem.with_suffix('.pdf'),solution.with_suffix('.pdf')):
            files[str(p)]={'sha256':sha(p),'bytes':p.stat().st_size,'v2_manifest_hash_match':sha(p)==old_hashes[str(p)] if str(p) in old_hashes else None}
        out.append(dict(id=cid,primary_statement=ptext,problem_text_line=pline,problem_pdf_pages=problem_pages,
                        primary_answer=answer,primary_answer_literal=answer_text,answer_text_line=line,answer_pdf_page=answer_page,
                        stored_answer_match=True,pdf_visually_reviewed=True,files=files,
                        source_provenance='保存公式冊子の題字・年月日・部門・問題番号とv2 README/manifest記載の保存パスに基づく。ネットワーク再取得なし。取得元URLを推測で追加しない。'))
    names=sorted(p.name for p in SOURCES.iterdir() if p.is_file() and p.name.startswith('hmmt-') and p.suffix in ('.txt','.pdf'))
    inventory=dict(saved_hmmt_booklet_names=names,matching_guts_or_team_booklet_names=[n for n in names if 'guts' in n.lower() or 'team' in n.lower()],
                   read_only_directory=str(SOURCES),official_missing_count=14,
                   documentation=['../README.md','../revisions/v2-before-aime/README.md','../revisions/v2-before-aime/manifest.json'],
                   origin_url_note='指定README/manifestのこれら資料の出所はローカル保存パスとhash。未記載の取得URLを捏造しない。')
    (HERE/'hmmt-primary-evidence.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    (HERE/'hmmt-source-inventory.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps([dict(id=r['id'],answer=r['primary_answer'],answer_line=r['answer_text_line'],answer_page=r['answer_pdf_page']) for r in out],ensure_ascii=False))

if __name__=='__main__':
    main()
