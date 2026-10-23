"""Assemble Q18's manual findings and source receipts; no geometry computation."""
from pathlib import Path
from collections import Counter
import csv
import hashlib
import json
import re

HERE=Path(__file__).resolve().parent
BASE=HERE.parent

def rows(path):
    return [json.loads(s) for s in path.read_text().splitlines() if s.strip()]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def display(value):
    if value is None:
        return ''
    if isinstance(value,list):
        return '{'+', '.join(map(str,value))+'}'
    return str(value)

def esc(value):
    return str(value).replace('|','\\|').replace('\n',' ')

def ref(path,locator=''):
    if not path:
        return '未入手'
    return f'[{Path(path).name}]({path})'+(f'（{locator}）' if locator else '')

def main():
    cases=rows(BASE/'cases.jsonl')
    reviews={r['id']:r for r in rows(HERE/'reviews.jsonl')}
    evidence={r['id']:r for r in json.loads((HERE/'primary-extracts.json').read_text())}
    hmmt={r['id']:r for r in json.loads((HERE/'hmmt-primary-evidence.json').read_text())}
    static=json.loads((HERE/'static-checks.json').read_text())
    assert static['passed'] and static['case_count']==54 and not static['original_files_changed']
    ast_by_id={r['id']:r for r in static['per_case']}
    hfile=BASE/'source-evidence/aime-1983-1999/aime-1983-1999.jsonl'
    hf={(int(r['Year']),int(r['Problem Number'])):r for r in rows(hfile)}
    hsha=sha(hfile)
    assert hsha=='5b29347ce7c807ab1ce23951577ca8530c2c10b18e52c9da8099e3e443779012'
    ordered=[]
    for c in cases:
        cid=c['id']; review=reviews[cid]; e=evidence[cid]; a=e['stored_answer']
        base=dict(id=cid,verdict=review['status'],primary_statement_status='',primary_answer_status='',
                  primary_answer='',primary_statement_file='',primary_statement_locator='',primary_statement_sha256='',primary_statement_url='',
                  primary_answer_file='',primary_answer_locator='',primary_answer_sha256='',primary_answer_url='',
                  stored_official_answer=display(a.get('official_answer')),secondary_answer=display(a.get('secondary_answer',a.get('corpus_reference_answer'))),
                  secondary_source_file='',secondary_source_locator='',secondary_reference_check='',answer_comparison='',
                  condition_review=review['condition_review'],branch_review=review['branch_review'],target=c['dsl']['target'],
                  target_review=review['target_review'],reason=review['reason'],proposed_fix=review.get('proposed_fix',''),
                  dsl_file='../'+c['dsl_path'],dsl_sha256=e['dsl_sha256'],ast_ok=ast_by_id[cid]['ast_ok'],
                  solver_results_seen=False,solver_run=False)
        if cid.startswith('AIME-'):
            _,year,n=cid.split('-'); source=hf[(int(year),int(n))]
            assert source['Question']==c['problem_statement']
            assert str(source['Answer'])==a['secondary_answer']
            base.update(secondary_source_file='../source-evidence/aime-1983-1999/aime-1983-1999.jsonl',
                        secondary_source_locator=f"source_id={a['reference_source']['source_id']}; row_idx={a['reference_source']['row_idx']}; sha256={hsha}",
                        secondary_reference_check='HF原行のQuestion/Answerと保存本文/secondary_answerは一致。一次確認とは別。')
            ps=e['primary_statement']
            if ps:
                s=e['primary_problem_source']
                base.update(primary_statement_status='一次本文照合済み',primary_statement_file=f'primary/aops/{year}_AIME_Problems.html',
                            primary_statement_locator=f"Problem_{int(n)}; line {ps['line']}",primary_statement_sha256=s['sha256'],primary_statement_url=s['url'])
            else:
                base['primary_statement_status']='一次資料で照合不能(取得失敗)'
            if e['primary_answer'] is not None:
                s=e['primary_answer_source']
                base.update(primary_answer_status='一次解答照合済み',primary_answer=e['primary_answer'],
                            primary_answer_file=f'primary/aops/{year}_AIME_Answer_Key.html',primary_answer_locator=f'解答順序リスト第{int(n)}項',
                            primary_answer_sha256=s['sha256'],primary_answer_url=s['url'],answer_comparison='一致（一次答とHF secondary_answer。先頭0は整数表記の差）' if e['answer_match'] else '不一致')
            else:
                base.update(primary_answer_status='一次資料で照合不能(取得失敗)',answer_comparison='一次答未入手につき比較不能。HF参考値のみ')
        elif cid in hmmt:
            h=hmmt[cid]; year=cid.split('-')[1]; directory='/home/kabatan/work/solver-research-assets/corpus97-sources/'
            problem=directory+f'hmmt-{year}-geo-problems.pdf'; solution=directory+f'hmmt-{year}-geo-solutions.pdf'
            base.update(primary_statement_status='公式本文照合済み（保存テキスト＋PDF目視）',primary_answer_status='公式解答照合済み（保存テキスト＋PDF目視）',
                        primary_answer=display(h['primary_answer']),primary_statement_file=problem,
                        primary_statement_locator='PDF p'+','.join(map(str,h['problem_pdf_pages']))+f"; 同名.txt line {h['problem_text_line']}",
                        primary_statement_sha256=h['files'][problem]['sha256'],primary_answer_file=solution,
                        primary_answer_locator=f"PDF p{h['answer_pdf_page']}; 同名.txt Answer line {h['answer_text_line']}",primary_answer_sha256=h['files'][solution]['sha256'],
                        secondary_reference_check='この行にはHF二次答の保存値なし。既存official_answerを保存公式原資料へ再照合。',
                        answer_comparison='一致（保存公式答と既存official_answer）。HF二次答はこの行に存在せず比較対象なし')
        else:
            sr=a['reference_source']
            base.update(primary_statement_status='公式本文未入手（コーパス本文のみ）',primary_answer_status='公式答え未入手',
                        secondary_source_file='../official_answers.jsonl',secondary_source_locator=f"id={cid}; 原参照={sr['path']}:{sr['split']}/{sr['row_idx']}",
                        secondary_reference_check='保存コーパス本文とDSLを参考照合。corpus_reference_answerは転記のまま、独立した公式確認なし。公式番号はcorpus indexのため未確定。',
                        answer_comparison='公式答え未入手につき比較不能。コーパス参考値のみ')
        ordered.append(base)
    assert len(ordered)==54 and len(reviews)==54
    counts=Counter(r['verdict'] for r in ordered)
    assert dict(counts)=={'合格':26,'修正要':1,'除外候補':27}, counts
    with (HERE/'audit.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(ordered[0]));writer.writeheader();writer.writerows(ordered)
    excluded=[r for r in ordered if r['verdict']=='除外候補']
    with (HERE/'exclusions.csv').open('w',newline='',encoding='utf-8') as f:
        fields=['id','primary_statement_status','primary_answer_status','secondary_answer','reason']
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows({k:r[k] for k in fields} for r in excluded)

    md=[
      '# Q18 未使用54問の入力監査',
      '',
      '**結論：合格26問、修正要1問、除外候補27問。未判定0問。**',
      '修正要1問は **HMMT-2016-FEB-GEO-01の集合採点・出力契約**であり、幾何DSL式の誤りではない。今回の読み合わせで、幾何DSLの条件・枝・目標式を変更すべき明白な誤りは検出しなかった。一次照合できない27問を、二次資料の答えだけで合格にしていない。',
      '',
      '| 区分 | 合格 | 修正要 | 除外候補 | 合計 |',
      '|---|---:|---:|---:|---:|',
      '| AIME 1983〜1999 | 23 | 0 | 13 | 36 |',
      '| HMMT February | 3 | 1（集合採点仕様） | 14 | 18 |',
      '| 合計 | 26 | 1 | 27 | 54 |',
      '',
      '**選別はソルバーの結果を見ずに行った。対象54問のソルバー結果は見ていない。** solver・局所探索・pの推定・数値的な配置生成・DSL式の数値評価・残差評価・解の列挙は実施していない。既存の封印実行やその結果ファイルも参照していない。見た答えは、監査に必要な一次解答と入力作成時に分離保存された参考答だけである。',
      '',
      '## 判定の意味と範囲',
      '',
      '- **合格**：指定一次資料の本文と答えを照合でき、記号的な読み合わせで条件・枝・不等式・非退化・目標量に修正点を見つけなかった。探索で解けること、全実数解の存在・一意性、数値安定性を認証したという意味ではない。',
      '- **修正要**：一次照合は済んだが、本検証前に具体的に直すべき出力・採点仕様が残る。修正案を別ファイルへ保存した。',
      '- **除外候補**：指定一次資料が不足している。今回のオフライン監査では本検証へ入れる根拠がそろわず、27問すべてを理由付きで保留する。将来一次資料が得られれば再監査できる。難度・変数数・予想成功率を選別に使っていない。',
      '',
      'この監査は一担当による静的・記号的なレビューであり、独立した第二査読や形式的同値性証明ではない。整数証人、床関数、論理枝、三角関数の実行時挙動は検査範囲外である。原問の証明要求と数値答の一致も区別する。',
      '',
      '## 答えの照合結果',
      '',
      '**確認できた範囲で答えの不一致は0件。** AIMEのHF `secondary_answer`とAoPS Answer Keyを比較できた23件は全て一致した（026と26などの先頭0は整数表記の差）。残る13件は一次答えがないため、一致とも不一致とも判定していない。AIME36件すべてで、HF原JSONLのQuestion/Answerが保存本文/secondary_answerと一致することは別途確認した。',
      '',
      'HMMTの公式冊子がある4件は、既存`official_answer`と保存公式Answer行・PDF表示が一致した。これら4行の`corpus_reference_answer`はnullなので、HF二次答との一致を確認したとはいわない。GUTS/TEAMの14行はコーパス参考答しかなく、**公式答え未入手**である。',
      '',
      '| HMMT公式照合 | 公式答 | 問題PDF | 解答PDF |',
      '|---|---|---|---|',
      '| 2016 GEO-01 | {2, 6} | p1 | p1 / テキスト8行 |',
      '| 2022 GEO-07 | 16902 | p1 | p3 / テキスト148行 |',
      '| 2022 GEO-08 | 2402 | p1〜2 | p4 / テキスト187行 |',
      '| 2023 GEO-06 | 68 | p1 | p3 / テキスト110行 |',
      '',
      '### 注意すべき目標量・枝',
      '',
      '- **2016 GEO-01**：`Area(S,I,X)`の像の集合が原問の答え。公式値2または6の一方だけで合格にしてはならない。公開結果モデルにはanswersリストがあるため、スカラーtargetだから表現不能とは判断しない。既存READMEの集合採点未実装を受け、[全答集合との一致を要求する案](proposed-fixes/HMMT-2016-FEB-GEO-01.md)と[機械可読な契約案](proposed-fixes/HMMT-2016-FEB-GEO-01.answer-contract.json)を置いた。幾何DSLはそのままでよく、この案も実行系へは適用していない。',
      '- **2022 TEAM-03（除外候補）**：R=1のDSLはXY/Rを返す。原問の長さは係数にRを掛けて復元する。保存参考答sqrt(3)Rを、そのままスカラー目標へ渡すのは誤り。原問の証明要求も残る。',
      '- **2016 GUTS-10（除外候補）**：保存コーパスは外心Oを使う。似た公式2016 GEO-02は垂心Hを使い、答え14である。類似した本文という理由でその公式答えを転用しなかった。',
      '- **2022 GEO-07**：第2最大辺長の二乗が既約a/b、目標は100a+b。六つのペアのminをmaxでまとめる式を全数照合し、PDFでsqrt(a/b)を再確認した。',
      '- **AIMEの既約分数**：整数分子分母、正の分母、整数Bezout証人の式を確認。長さ・比そのものへ目標を差し替えず、原文のm+n等を保持している。整数化・平方根表現・floor・度数法の対応も各問に記録した。',
      '',
      '## 一次資料と不足',
      '',
      'AIMEは依頼に従い、保存AoPS Wikiを一次照合資料として扱った。MAAの大会原本を再取得したわけではない。[fetch-log.json](primary/aops/fetch-log.json)にある取得成功HTML27本のbytes/SHA-256を全て再照合し、問題本文はHTMLのProblem節・数式画像alt・asy記述から読み取った。HTMLの外部画像本体は新規取得していない。画像がない問題でも本文だけで条件が完結する場合は、その根拠を個別記録に書いた。asyの描画座標や解由来数値を修正入力へ転用していない。',
      '',
      '| AIME取得失敗 | 対象番号 | 件数 | 扱い |',
      '|---|---|---:|---|',
      '| 1992 Problems / Answer Key | 09, 14 | 2 | 一次資料で照合不能(取得失敗) |',
      '| 1993 Problems / Answer Key | 02, 12, 13, 15 | 4 | 同上 |',
      '| 1994 Answer Key | 02, 08, 10 | 3 | 問題本文は一次確認済み、答え未照合 |',
      '| 1999 Problems / Answer Key | 02, 09, 12, 14 | 4 | 一次資料で照合不能(取得失敗) |',
      '',
      'HF二次資料の出所は[既存README](../source-evidence/aime-1983-1999/README.md)のgneubig/aime-1983-2024。SHA-256は`'+hsha+'`。一次不足13問のHF照合は、CSVの`secondary_*`と各問の「二次参考」に分離した。',
      '',
      'HMMTは`/home/kabatan/work/solver-research-assets/corpus97-sources/`の保存公式問題・解答テキスト/PDFを使用し、[既存README](../README.md)、[v2 README](../revisions/v2-before-aime/README.md)、[v2 manifest](../revisions/v2-before-aime/manifest.json)にある出所と照合した。題字・日付・部門・公式問題番号、PDFの数式、解答欄を目視確認した。指定保存ディレクトリにGUTS/TEAM冊子はない。該当14問のIDはコーパスの暫定indexで、公式番号の保証もない。元の取得URLがこのREADME/manifestにない資料に、推測のURLを追加していない。',
      '',
      '出所・各PDF/テキストのhashは[hmmt-primary-evidence.json](hmmt-primary-evidence.json)、保存冊子の有無は[hmmt-source-inventory.json](hmmt-source-inventory.json)、目視したページは[pdf-review/](pdf-review/)に記録した。AoPSの抽出と答え対応は[primary-extracts.json](primary-extracts.json)、取得ログとの一致は[source-checks.json](source-checks.json)にある。',
      '',
      '## 全54問の判定一覧',
      '',
      '一次答と二次参考答は独立の列にしている。「未入手」を二次答で埋めない。詳細な根拠は後半の個別記録と[audit.csv](audit.csv)に固定した。',
      '',
      '| ID | 判定 | 一次答 | 二次参考答 | 要点 |',
      '|---|---|---|---|---|'
    ]
    for r in ordered:
        md.append('| '+' | '.join(esc(x) for x in [r['id'],r['verdict'],r['primary_answer'] or '未入手',r['secondary_answer'] or 'なし',r['reason']])+' |')
    md += ['', '## 除外候補27問（理由付き固定一覧）', '', '機械可読な同一一覧：[exclusions.csv](exclusions.csv)。', '', '| ID | 一次資料の不足と理由 |', '|---|---|']
    md += ['| '+r['id']+' | '+esc(r['reason'])+' |' for r in excluded]
    md += [
      '', '## 静的検査・保存範囲', '',
      f"[static-checks.json](static-checks.json)：54問・{static['ast_expressions']:,}式、JSONモデル/AST/関数名/引数/定義順エラー0件。手作業監査に加え、次の反復は添字と式のASTを全数確認した。", '',
      '- AIME 1991-02：668等分点と335本の距離和。',
      '- AIME 1993-02：40日分の方向周期と負号。',
      '- AIME 1999-02：合同四角形の8対応と各6距離等式。',
      '- HMMT 2016 GEO-01：12直角、固定辺以外の11辺長、非隣接54辺組の非交差条件。',
      '- 凸多角形4問：全辺と非隣接頂点の外積条件。HMMT 2016 GUTS-03：八角形全頂点の中心角。HMMT 2022 GEO-07：第2最大用の全6ペア。', '',
      f"[input-snapshot.json](input-snapshot.json)の元ファイル{static['original_files_checked']}本（primary/を含む）は監査開始時とSHA-256不変。元DSL・cases・manifest・公式答記録は変更していない。追加・更新はaudit/内のprimary/以外のみ。ネットワーク、git fetch、commit、push、環境変更、指定作業フォルダ外への書込みは行っていない。最大ファイルサイズも最後の[delivery-checks.json](delivery-checks.json)に記録する。", '',
      'AST検査スクリプトは`geosolver.engine`、`geosolver.geometry`、NumPy、SciPy、SymPyをimportしていないことも検査した。GeometryProblemのモデル検査とAST専用の_expression_issuesだけを使い、式を評価するvalidateやengine_documentは呼んでいない。これは禁止した実験の代替計測ではない。', '',
      '監査の再確認（書込み先は本監査フォルダのみ、ソルバーは動かさない）：', '',
      '```bash',
      '/home/kabatan/work/solver/.venv/bin/python -B jssa/difficulty/unseen-1983/audit/verify_audit_static.py',
      '/home/kabatan/work/solver/.venv/bin/python -B jssa/difficulty/unseen-1983/audit/collect_hmmt_evidence.py',
      '/home/kabatan/work/solver/.venv/bin/python -B jssa/difficulty/unseen-1983/audit/build_report.py',
      '```', '',
      '手作業判定の原記録は[reviews.jsonl](reviews.jsonl)。prepare_evidence.pyは監査開始時の抽出・hash記録用であり、既存input-snapshot.jsonを更新して基準を動かすために再実行しない。', '',
      '## 問題ごとの読み合わせ記録', ''
    ]
    for r in ordered:
        md += [f"### {r['id']} — {r['verdict']}",'',
               f"**判定理由：** {r['reason']}",'',
               f"- 原文（一次）：{ref(r['primary_statement_file'],r['primary_statement_locator'])}。{r['primary_statement_status']}。",
               f"- 答え（一次）：**{r['primary_answer'] or '未入手'}**。{ref(r['primary_answer_file'],r['primary_answer_locator'])}。{r['answer_comparison']}。",
               f"- 二次参考：`{r['secondary_answer'] or 'なし'}`。{r['secondary_reference_check']}",
               f"- 条件：{r['condition_review']}",
               f"- 枝・不等式・非退化：{r['branch_review']}",
               f"- 目標量：{r['target_review']}",
               f"- 入力：[元DSL]({r['dsl_file']})。SHA-256 `{r['dsl_sha256']}`。AST合格。" ]
        if r['proposed_fix']:
            md.append(f"- 提案：[修正案]({r['proposed_fix']})。未適用。")
        md.append('')
    (HERE/'audit.md').write_text('\n'.join(md)+'\n')
    summary=dict(verdict_counts=dict(counts),case_count=54,primary_answer_verified_count=27,
                 aime_secondary_vs_primary_compared=23,aime_secondary_vs_primary_mismatches=[],
                 aime_primary_unavailable=13,hmmt_official_compared=4,hmmt_official_unavailable=14,
                 geometry_dsl_fixes=0,evaluation_contract_fixes=1,solver_results_seen=False,solver_run=False)
    (HERE/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(summary,ensure_ascii=False))

if __name__=='__main__':
    main()
