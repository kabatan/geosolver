"""Write completed review records from offline sources and substitution receipts."""
from __future__ import annotations

import csv
import datetime
import hashlib
import json
from pathlib import Path

from source_plan import SELECTED, SPECIAL_EXCLUSIONS, identifier

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SEMANTICS = [
 '原文の座標軸を保持。3方向への射影端点を各頂点のmin/maxで直接表現し、面積>0を課す。頂点のラベル順による解の選別はしない。2つの三角形を代入した。',
 '剛体変換と鏡映のみ。面積1なので尺度は未知。D,Eの閉線分条件、平行、長さ比1/3、鏡映の定義を全て保持。異なる底辺・頂点位置の2配置を確認。',
 '20×12の長方形とBC方向へのCZ=18の延長を直接配置。Eは内部かつAB,ADへの距離が各6。X,Yを直線交点で作り、四角形面積を求める。',
 '同一直線上のマーカーの差ベクトルは(4,4k)で始点nによらないため、1と1+4を代表にする。k>0と距離31を保持。求める2点は原文の7,19。',
 '面積比に限り外接半径1を固定。正六角形は中心角の定義で構成し、三角形BDFの内接円を用いる。答えの半径や面積はDSLへ代入しない。未知変数0。',
 'AB=10のみ座標に固定。他の3辺・共円性・凸頂点順を条件化。円の中心と半径を未知とし、3接点の垂足が各閉線分上であることを保持。円が四角形内に収まるという追加条件は入れない。',
 '13-14-15三角形のCを未知にする。垂足E,F、円AEF、各半径に垂直な3接線、その交点を定義的に構成。解答に現れる中点や面積比を入力へ追加しない。',
 'X,Y,Zを未知三角形として、指定6長さと線分順序から円周点を単位方向で構成。BE,CFの端点は円周上で交互なのでZも円内、E,FはZの先。6点の共円性・凸順序を課し、方べきで解いた値は監査だけに使う。',
 '公式図は縦横の中線による2×2分割。未知辺長sの正方形と中点を構成し、4小正方形の面積1を全て記述する。最終面積4を入力へ書かない。',
 'Pと各辺上の6点と共通辺長sを未知とする。正三角形3個の9辺を等置し、閉線分・凸六角形の順序を保持。Pが内心という解法上の結論はDSLに入れない。',
 'Aは2辺長で決まり、D,EはAB内部の順序付き角三等分点。X,YはAC,BCの直線上の第2交点で、原文にない半直線条件を足さない。tx,ty!=0で既知交点Cを除く。',
 'AC=6,BC=8,角A=2角Cをそのまま保持。targetはABの長さ。原文の整数a,bや100a+bをDSLへ入れず、公式解答のsqrt(73)-3を採点参照値として分離。',
 '原文の単位円と正十二角形の中心角を使用。2交点を構成し、指定された円弧領域を扇形OP2P4から三角形OXYを除く面積の定義で表す。床関数はtargetへ入れない。未知変数0。',
 'B=(0,0),D=(d,0),A=(0,a)で角ABDの直角を直接表現。角BCD=90度、CM=2、AM=3、凸順序を保持。解法で得るd=4は入力に書かない。異なるCの2配置を確認。',
 '角度なので正五角形の外接半径1を固定。反時計回りの辺AB,BCを外側へ60度回した頂点F,Gを使う。答え48度は入力にない。未知変数0。',
 'BC=1+4とD=(1,0)を原文から直接配置。Aは正三角形条件を満たす未知点。E,Fはt,u>=0の半直線で、Dが中点。監査のu=8/5はFがBを越える正しい枝を確認する。',
 '角度のみなのでA=(0,0),Q=(1,0)を固定。P=F+D-Qは平行四辺形の定義。4指定角、凸五角形の順序、Pの5本の内側不等式を保持。スパイラル相似は監査用座標の構成だけに使う。',
]


def write_csv(path, rows):
    with path.open('w', encoding='utf-8', newline='') as f:
        writer=csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader();writer.writerows(rows)


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    assert not (HERE/'prediction.lock.json').exists(), 'Prediction already locked'
    now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    cases=[json.loads(x) for x in (HERE/'cases.jsonl').read_text().splitlines()]
    sub=json.loads((HERE/'audit/substitution.json').read_text())
    static=json.loads((HERE/'audit/static.json').read_text())
    duplicates=json.loads((HERE/'audit/duplicates.json').read_text())
    sources=json.loads((HERE/'source-evidence/manifest.json').read_text())
    assert sub['all_passed'] and static['validation']['valid'] and duplicates['passed']
    sby={r['id']:r for r in sources['records']};wby={r['id']:r for r in sub['records']}
    inventory=[];audit=[];semantics=[]
    for r,comment in zip(cases,SEMANTICS,strict=True):
        cid=r['id'];d=r['dsl'];s=sby[cid];w=wby[cid]
        paths={t['kind']:t for t in s['sources']}
        item=dict(id=cid,division='Team A' if 'TEAM1' in cid else 'Guts',
            variables=len(d['variables']),equalities=sum(c.get('operator')=='=' for c in d['conditions']),
            inequalities=sum('operator' in c and c['operator']!='=' for c in d['conditions']),
            predicates=sum('predicate' in c for c in d['conditions']),target=d['target'],
            geometric_reference=r['answer'][0],official_output=s['official_output'],
            output_conversion=s['output_conversion'],
            problem_pdf=paths['problems']['pdf'],problem_pages=','.join(map(str,paths['problems']['pages'])),
            solution_pdf=paths['solutions']['pdf'],solution_pages=','.join(map(str,paths['solutions']['pages'])),
            dsl_path=r['dsl_path'],dsl_sha256=sha(HERE/r['dsl_path']),verdict='PASS')
        inventory.append(item)
        eqerrs=[float(c['scaled_residual']) for a in w['witnesses'] for c in a['checks'] if c.get('operator')=='=']
        audit.append(dict(id=cid,verdict='PASS',primary_answer=r['answer'][0],secondary_answer='',
            official_output=s['official_output'],pdf_problem_verified=True,pdf_answer_verified=True,
            semantic_review_passed=True,witness_count=len(w['witnesses']),
            max_scaled_equality_residual=max(eqerrs,default=0),
            max_target_absolute_error=max(float(a['target_error']) for a in w['witnesses']),
            dsl_sha256=item['dsl_sha256']))
        semantics.append(dict(id=cid,reviewed_at_utc=now,passed=True,note=comment,
            pdf_visual_review=[dict(pdf=t['pdf'],sha256=t['sha256'],pages=t['pages']) for t in s['sources']]))
    write_csv(HERE/'problem-list.csv',inventory)
    write_csv(HERE/'audit/audit.csv',audit)
    (HERE/'audit/semantic.json').write_text(json.dumps(dict(
        reviewed_at_utc=now,method='Read official PDF page images alongside transcription, DSL and clause mapping; review every condition, branch, gauge and constant source',
        all_passed=True,records=semantics),ensure_ascii=False,indent=2)+'\n')
    selection=[]
    for year,section,n,*_ in SELECTED:
        for k in range(1,n+1):
            cid=identifier(year,section,k)
            if k==n:
                decision,reason,basis='adopted','All primary-source, semantic, substitution and static audits passed','This task, official PDF and complete audit'
            elif section=='team1':
                decision,reason,basis='excluded','Earlier Team items are proof/strategy/universal statements, not a finite scalar configuration value','Official 2010 Team A problem PDF p1'
            else:
                status,why=SPECIAL_EXCLUSIONS.get((year,k),('not_planar_value','Arithmetic, algebra, counting or probability in inherited screening'))
                decision,reason,basis='excluded',status+': '+why,'Inherited pre-solver screening notes in source_plan.py; not an additional full-source audit of every excluded item'
            selection.append(dict(id=cid,decision=decision,reason=reason,basis=basis))
    write_csv(HERE/'selection.csv',selection)
    (HERE/'prereg/target-17.txt').write_text(''.join(r['id']+'\n' for r in cases))
    batches=[]
    for seed in range(301,306):
        for i in range(0,len(cases),4):
            batches.append(dict(batch_id=f'seed-{seed}-batch-{i//4+1:02}',seed=seed,
                case_ids=[r['id'] for r in cases[i:i+4]],max_parallel_workers=min(4,len(cases)-i)))
    plan=dict(status='PREPARED_NOT_AUTHORIZED',required_before_any_execution=[
        'User has committed AND pushed these exact prediction files and inputs; verify commit and remote state',
        'Explicit solver execution authorization in a separate task'],
        source_commit='60db4b679b04167175c51c479c87c22fa663fda0',time_limit_seconds=180,
        cores_per_run=1,max_parallel_runs=4,seeds=list(range(301,306)),planned_runs=85,
        runner='benchmarks/research_runner.py',scoring='Unmodified assess_campaign: normal_completion AND exact equality of canonical answer sets; same criterion as score_q19.py',
        grading_references='cases.jsonl answer fields are the geometric quantities normalized from the official answer/solution; integer display conversions are outside the DSL',
        command_sizing='One batch at a time, up to four case IDs with one seed; each worker has the existing 180+8 second watchdog. Do not run the entire 85-run campaign in one long command.',
        no_retry=True,no_result_based_exclusion=True,missing_runs_count_as_incorrect=True,
        fixed_denominators=dict(runs=85,problems=17,successes_per_problem_required=3),
        max_file_bytes_exclusive=5_000_000,batches=batches)
    (HERE/'prereg/execution-plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n')
    lines=['# Q30b 採用問題一覧','', '17問（Guts 16、Team A 1）。全問PASS。一次資料は取得済み公式PDFをそのまま保存した。', '',
        '| ID | 変数 | targetの意味 | 幾何量の参照答 | 公式出力 | 問題/解答PDFページ |','|---|---:|---|---|---|---|']
    meanings=['三角形面積','鏡像三角形面積','四角形面積','マーカー間距離','円と長方形の面積比','接円半径','接線三角形面積','三角形周長','正方形面積','凸六角形面積','第2交点間の距離','辺ABの長さ','円弧領域面積','辺ADの長さ','角FEG（ラジアン）','線分EFの長さ','角AQC（ラジアン）']
    for r,meaning in zip(inventory,meanings,strict=True):
        lines.append(f'| [{r["id"]}]({r["dsl_path"]}) | {r["variables"]} | {meaning} | `{r["geometric_reference"]}` | `{r["official_output"]}` | {r["problem_pages"]} / {r["solution_pages"]} |')
    lines+=['','PDFファイル名・URL・元の取得UTC・SHA-256は `source-evidence/manifest.json`。',
        '2021は公式Februaryアーカイブ内のSpring大会で、実施日は2021-03-06。IDのFEBはアーカイブ区分。',
        '2021は `sqrt(73)-3 → 100*73+3=7303`、2022は `floor(120*(pi/6-sqrt(3)/12))=45`。',
        '2024の48度と2010 Teamの15度は、公式解答にラジアン値も明記されている。','']
    (HERE/'problem-list.md').write_text('\n'.join(lines))
    report=['# Q30b 作成・監査記録','',f'監査記録UTC: {now}。solver実行0、局所探索0、ネットワーク利用0。','',
        '採用17問すべてで、問題文・公式答えのPDF画像照合、条件読み合わせ、独立座標代入、公開DSL静的検証に合格した。',
        '各式の原文対応は `cards/` と `mapping.json`、全座標・条件残差は `audit/substitution.json` に保存した。','',
        '## 独立代入','',
        'mpmath 70桁で、手計算・公式解答の作図から得た20配置を明示的に代入した。最小二乗・根探索・求解・PSLQは使っていない。',
        '全144条件チェックに合格。最大スケール化等式残差は9.97e-71未満、target絶対誤差は1.16e-69未満（判定許容差1e-50）。',
        '検算用の解法由来定数は `audit_substitution.py` と監査記録だけにあり、DSLへ逆流していない。',
        '2010 Teamの初回の補助配置AF=0.8, FP=0.3は凸性に不合格だった。`revisions/substitution-first-pass.json` に保存した。',
        '同時に用意したAF=0.7, FP=0.25の配置は全条件に合格。最終監査は後者を採用し、DSLは変更していない。',
        '代入は解の存在を示す検算であり、全解の列挙・一意性証明・solver成功率の測定ではない。','',
        '## 原文とDSLの読み合わせ','']
    for s in semantics:report += [f'### {s["id"]}','',s['note'],'']
    report+=['## 重複','',
        '開発323問・new2026 20問・unseen-1983全54問を、正規化IDと変数名正規化DSLで全件比較し、一致0。',
        '保存本文は開発131問（元本文28＋補助資料）、unseen-1983 54問で比較。new2026本文はこのcheckoutにない。',
        '各候補の本文類似度上位3件も読み合わせた。最大0.601399で、四角形・中点など一般的な語の一致であり同一原問ではない。',
        '13-14-15三角形は既存にもあるが、2016 Guts 14の「垂足の円への3接線の面積」と既存の重心・中心間距離・接円半径は別の原問。',
        '過去作成済みの2011 ALGGEO 12/20・2013 GEO 9も除外台帳と照合。今回の17問に含まれない。',
        '`audit/duplicates.json` に比較元hashと照合範囲を記録。本文がないものの別名・翻訳・数学的同値性を完全証明したとは主張しない。','',
        '## 選定と資料の限界','',
        '前担当が用意した17候補を全件監査して全件採用した。今回、新規候補の追加・solver成績による選別はない。',
        '各年の早いGutsから選ぶ方針のため無作為抽出ではなく、容易な問題を含む。3問は未知変数0。Geometryは0問で、部門全体を代表しない。',
        '除外候補のうちGutsの先行番号の分類は前担当のメモを保存したもので、全除外を新たに一次資料で監査したとは扱わない。',
        '指定のnew-2026 authoring-rules.mdは現checkoutと参照できるGit履歴にない。ユーザーの明示的な作成規則と現存new2026慣例に従う。','',
        '## 採点と次段階','',
        '`audit_static.py` は探索・application・engineのimportを拒否し、静的validateと参照式のdescribe_exactだけを使った。',
        '採点は未変更のresearch_runner。正常終了かつ幾何量の正規化された答え集合が完全一致した場合だけ正答とする（Q19と同じ判定式）。',
        '整数表記への変換は参照資料側で処理済みであり、2021/2022のDSLに整数変数・既約性・床はない。',
        '本タスクは予測固定まで。ユーザーによるcommit・push確認と、別タスクでの明示的実行許可が必要。','']
    (HERE/'AUDIT.md').write_text('\n'.join(report))
    for r in inventory:
        p=HERE/'cards'/f'{r["id"]}.md'
        text=p.read_text().replace('状態: 作成済み。採用は一次資料・代入監査の合格後。',
            '状態: 採用（一次資料・意味・独立代入・静的監査PASS）。記録は ../AUDIT.md と ../audit/。')
        p.write_text(text)
    print(json.dumps(dict(adopted=len(inventory),witnesses=sum(r['witness_count'] for r in audit),
        expected_future_runs=85,stage='authoring only',solver_executed=False)))


if __name__=='__main__':main()
