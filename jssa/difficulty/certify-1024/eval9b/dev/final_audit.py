#!/usr/bin/env python3
"""Saved-output audit and evidence-backed wording only. Never run certification."""
import ast
import collections
import csv
import hashlib
import json
from pathlib import Path
import sys
import sympy as sp
sys.dont_write_bytecode=True
E=Path(__file__).resolve().parent

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,obj):
    data=json.dumps(obj,ensure_ascii=False,indent=2)+'\n'
    assert len(data.encode())<=2_900_000
    p.write_text(data)

def audit():
    manifest=json.loads((E/'pre-run-hashes.json').read_text())
    for p,h in manifest['hashes'].items():assert sha(Path(p))==h,p
    complete=json.loads((E/'completion.json').read_text())
    rows=list(csv.DictReader((E/'per-problem.csv').open()))
    records={cid:json.loads((E/'runs'/(cid+'.json')).read_text()) for cid in manifest['order']}
    assert len(rows)==len(records)==163 and {r['id'] for r in rows}==set(records)
    assert set(complete['completed'])==set(records)
    assert list(csv.DictReader((E.parent/'unseen/per-problem.csv').open()).fieldnames)==list(rows[0])
    summary=json.loads((E/'summary.json').read_text())
    bycategory=collections.Counter(r['category_ja'] for r in rows)
    assert all(summary['counts'][k]==v for k,v in bycategory.items())
    starts=sorted((r['start_receipt'] for r in records.values()),key=lambda x:x['start_unix'])
    if not complete['interruptions_not_results']:assert [s['id'] for s in starts]==manifest['order']
    cpus=collections.defaultdict(list);events=[];resources={};T=sp.Symbol('T');invariant_cert=[]
    row_by_id={r['id']:r for r in rows}
    for cid,r in records.items():
        assert r['supervisor_finalized'] and r['attempts']==1
        start=r['start_receipt']['start_unix'];end=start+r['wall_seconds'];cpu=r['start_receipt']['cpu']
        cpus[cpu].append((start,end,cid));events.extend([(start,1),(end,-1)])
        if row_by_id[cid]['category_ja']=='認証':
            assert r['unit_ideal'] is False and r['rabinowitsch']['status']=='member' and r['proof_verified'] is True
            assert r['power']['status'] in ('member','inconclusive_m_le_4')
            assert any(r[k].get('independent_verification')=='verified' for k in ('power','rabinowitsch'))
            p=sp.Poly(manifest['records'][cid]['original_polynomial'],T)
            q=sp.Poly(manifest['records'][cid]['polynomial'],T)
            if p.sqf_part().monic()==q.sqf_part().monic():invariant_cert.append(cid)
        if r['status']=='resource_limit':
            w=E/'runs'/(cid+'.work');log=w/'singular.log'
            if r.get('singular_returncode')==-25 or r.get('supervisor_returncode')==-25:
                cause='出力ファイル上限（SIGXFSZ、2,900,000 byte）'
                assert any(p.stat().st_size==2_900_000 for p in w.iterdir() if p.is_file())
            elif r.get('reason_code')=='MEMORY_LIMIT':
                cause='プロセス群メモリ8 GiB上限'
                assert r['peak_tree_rss_bytes']>=8<<30
            elif r.get('reason_code')=='MemoryError':cause='アドレス空間上限（MemoryError）'
            else:cause='資源上限・詳細未確定'
            resources[cid]=dict(cause=cause,reason_code=r.get('reason_code'),singular_returncode=r.get('singular_returncode'),
                supervisor_returncode=r.get('supervisor_returncode'),peak_tree_rss_bytes=r['peak_tree_rss_bytes'],
                last_algebra_event=r.get('last_algebra_event'),singular_log_bytes=log.stat().st_size if log.exists() else None,
                result_sha256=sha(E/'runs'/(cid+'.json')))
    # Same radical root set cannot turn a genuine original nonmember into a member.
    assert not invariant_cert,('ORIGINAL_NONMEMBERSHIP_CONTRADICTION',invariant_cert)
    for cpu,items in cpus.items():
        items.sort()
        for a,b in zip(items,items[1:]):assert a[1]<=b[0],('CPU_OVERLAP',cpu,a,b)
    active=peak=0
    for _,change in sorted(events):active+=change;peak=max(peak,active)
    assert peak<=4
    cert=sum(r['category_ja']=='認証' for r in rows)
    nn=sum(r['category_ja']=='認証' and r['sign_category_ja']=='非負形で正の根' for r in rows)
    expected={'C6':(cert,163,60),'C7':(nn,cert,70),'C8':(65+cert,254,50)}
    combined={'C6':(cert+7,179,60),'C7':(nn+7,cert+7,70),'C8':(65+cert+11,275,50)}
    for data,values in [(summary,expected),(summary['combined'],combined)]:
        for k,(a,b,t) in values.items():
            assert (data[k]['numerator'],data[k]['denominator'])==(a,b)
            assert data[k]['judgment']==(('的中' if 100*a>=t*b else '外れ') if b else '未判定')
    resource_counts=dict(collections.Counter(v['cause'] for v in resources.values()))
    write(E/'resource-limit-analysis.json',dict(method='保存された終了コード・ログサイズ・監視RSSのみ。再実行・再分類なし。',counts=resource_counts,details=resources))
    # The frozen reporter retains raw exception labels. Explain those labels using receipts.
    answer=(E/'answer.md').read_text()
    count_lines='、'.join(f'{k} {n}問' for k,n in resource_counts.items())
    note=f'資源上限の具体的な内訳は、{count_lines}。上表のRuntimeErrorはSingularのSIGXFSZ終了を受けた例外で、保存した終了コード−25と上限に達したログを確認した。メモリ上限は監視したプロセス群RSSによる。[資源上限の根拠](resource-limit-analysis.json)。'
    if '資源上限の具体的な内訳は、' not in answer:
        answer=answer.replace('偶多項式ではq=p²なので',note+'\n\n偶多項式ではq=p²なので')
    (E/'answer.md').write_text(answer)
    write(E/'supplementary-audit.json',dict(all_frozen_hashes_match=True,completed=163,counts=dict(bycategory),
        simultaneous_attempts_peak=peak,cpu_assignments=sorted(cpus),no_overlap_per_cpu=True,
        unchanged_root_set_certifications=invariant_cert,source_vs_q_consistent=True,resource_limit_causes=resource_counts,
        csv_sha256=sha(E/'per-problem.csv'),answer_sha256=sha(E/'answer.md'),audit_script_sha256=sha(Path(__file__)),
        original_categories_unchanged=True,no_new_certification_attempts=True))
    inventory=[dict(path=str(p.relative_to(E)),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(E.rglob('*'))
        if p.is_file() and p.name!='artifact-hashes.jsonl']
    assert all(r['bytes']<=2_900_000 for r in inventory)
    data=''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in inventory)
    assert len(data.encode())<=2_900_000
    (E/'artifact-hashes.jsonl').write_text(data)
    print(json.dumps(dict(completed=163,counts=dict(bycategory),resource_limit_causes=resource_counts,
        simultaneous_peak=peak,no_overlap_per_cpu=True,all_frozen_hashes_match=True),ensure_ascii=False,indent=2))

if __name__=='__main__':audit()
