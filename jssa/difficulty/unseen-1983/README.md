# Q2: 未使用問題のオフライン準備（未完成・18候補）

## 結論

**18問の候補DSL、原文対応カード、問題ID・入力hash・除外理由を固定したmanifestを作った。
依頼の24〜30問には6問不足し、完成した本検証用集合にはなっていない。**
AIME 1983〜1999の原文は手元で見つからず、AIMEの採用は0問。
HMMT Februaryの入手可能な原文から、結果を見ない順序と表現可能性の規則で18問を作成した。
ARMLの原文も見つからなかったため含めていない。

solver・局所探索・数値的な配置生成・残差評価・PSLQ・成績計測は**一度も実行していない**。
実行した検査はJSONモデルとDSL式のASTパース・静的検査だけで、18問548式が合格した。
実行可能性、条件の同値性、目標値の一意性や集合の網羅性は検証していない。

公式答えは入力と分離した `official_answers.jsonl` に置いた。
入力固定後に保存済み公式解答テキストのAnswer行から4問分を転記した。
残り14問は `official_answer: null` で、二次資料の参照答を別のキーに未評価のまま保存した。
参照答を公式照合済と扱ってはいない。答え転記の前後でDSLとmanifestのbytesが不変だった。
ネットワークで公式出典を再確認してはいない。

14問のコーパス由来IDは公式冊子の番号と未照合である。
重複の静的検査では既存343問と一致しなかったが、番号違い・言い換えまで含む意味上の
非重複や、あらゆる過去研究での未使用を証明したわけではない。
**本検証へ渡す前に、原本照合と意味監査、件数の補充が必要。**

## 根拠

### 規則と資料の探索

`jssa/strategy/codex-tasks-1023.md` 末尾のQ2を読んだ。
指定の `jssa/difficulty/new2026/authoring-rules.md` と `jssa/dsl-audit/cards.md` は
このcheckoutに存在しなかった。取得済みの別ブランチ
`origin/claude/project-thread-fos2rk` と `origin/claude/project-thread-ulho54` の
全ファイル名も調べたが、両ファイルはなかった。
`/mnt/project-files/jssa/new2026/authoring-rules.md` もなく、`/mnt/project-files` 自体が未配置だった。

そのため、既存new2026のREADME・DSL、公開DSL仕様、
`benchmarks/gmb_comparison/AUTHORING.md` の数学的変換方針から
**推定した**規則を [authoring-rules.md](authoring-rules.md) に明記した。
指定の対応カードの実物を読めたとは主張せず、原文の各条件・全構成・全guard・目標の
DSL位置を示す表を代替形式にした。

原文を探した範囲は次のとおり。ネットワーク・git fetchは使っていない。

- repo内の `benchmarks/cases.jsonl`、new2026、保存済み原文コーパス、取得済み別ブランチのファイル一覧。
- `jssa/strategy/astra-consult-14/E/e2h-rows.jsonl` の614行。
  2000年より前の行はなく、AIME 1983〜1999の原文は0行だった。
- `/home/kabatan/work/solver-research-assets/corpus97-sources/` の保存資料。
  AIME旧年代・ARMLのファイル名はなく、HMMTの問題冊子テキスト14冊分・160問を追加で読めた。
  2022 Geometryの分数・根号は保存済みPDFの両ページを画像で確認した。
- Hugging Faceのローカルキャッシュに対象データセットのスナップショットはなかった。
  `/tmp` の関連する名前の資料も調べたが原文コーパスは見つからなかった。

最初にコーパスだけで14問を固定し、その後、上記の保存冊子テキストを見つけて
母集団を追加した。v1の規則・manifest・検査記録は `revisions/` に保存した。
v1の14入力のhashはv2でもすべて保持している。
追加は原文の発見によるもので、solverの結果による選び直しではない。

### 選定と除外

AIMEは1983〜1999、各年1〜15の**全255スロット**をmanifestに保留として載せた。
原文がないので幾何かどうかも未判定であり、255問を「DSL非対応」とは数えていない。
原文hash・入力hashは `null` とし、架空の原文や答えは作らなかった。

補完対象のHMMTは、コーパスのFebruary全322行と保存問題冊子の160問を監査し、
同一IDの重複54件を統合した428行を、年・番号・部門名順に並べた。
予想成功率、実測結果、人間の難度、変数の数で間引いていない。
変数0の正八角形と変数20の直交十二角形も含めた。
コーパス自体は過去の研究で収集された部分集合なので、大会全体を網羅する標本ではない。

| 428行の扱い | 件数 | 根拠 |
|---|---:|---|
| 候補DSLを作成 | 18 | 原文を有限の構成・条件・目標へ直接翻訳できる |
| 既存343問と同じID | 101 | 大小文字、ゼロ埋め、AIME I/II等を正規化して照合 |
| 同一原問の別部門収録 | 13 | 2011 ALGGEO/COMBGEOを対応づけ、ALGGEOに一本化 |
| 別名の過去DSLあり | 3 | 未使用と扱う根拠がないため除外。成否は参照していない |
| 代数・整数・組合せ等 | 227 | 平面図の単一の求値の対象外 |
| その他の除外・保留 | 66 | 最適化、軌跡面積、期待値、個数、立体、欠落図等 |

各行の具体的理由は [manifest.json](manifest.json) の `reason_code` と
`exclusion_reason` に固定した。例えば、2009 Geometry-03は軌跡の面積、
2010 Guts-10は期待値、2018 Guts-01は分割図の欠落、2020 Guts-06は最小の整数頂点数、
2021 Geometry-10は全ての可能な値の和なので、解法で別の有限配置へ置換していない。

2011 ALGGEO-12/20は、それぞれ保存済みの
`HMMT-2011-equilateral-hexagon.json` / `HMMT-2011-two-circles-tangent-line.json` と同じ原問。
2013 Geometry-09も過去DSLが存在した。これら3問は今回の候補に含めなかった。

### 作成した18問

GUTS/TEAMの番号はコーパスの暫定index。公式番号が確定したという意味ではない。
Geometryの4問は保存冊子の問題番号を使った。全問の原文と入力hashはmanifestにある。

| 問題ID | 変数数 | 原問の目標・特徴 | 公式答えの状態 |
|---|---:|---|---|
| HMMT-2012-FEB-GUTS-01 | 2 | 正方形の外の点を含む五角形の最長対角線 | 未入手 |
| HMMT-2013-FEB-TEAM-03 | 3 | 外心を通る円の接条件と交点の長さ | 未入手 |
| HMMT-2014-FEB-TEAM-08 | 4 | 垂足・外心・平行垂直条件とBX | 未入手 |
| HMMT-2015-FEB-GUTS-02 | 6 | 凸五角形の直角と等辺長、AE | 未入手 |
| HMMT-2016-FEB-GEO-01 | 20 | 単純直交十二角形で三角形SIXの可能な面積集合 | 保存公式解答から転記 |
| HMMT-2016-FEB-GUTS-03 | 0 | 正八角形の対角線交点とLI | 未入手 |
| HMMT-2016-FEB-TEAM-03 | 2 | 内心・外心の直角と三角形面積 | 未入手 |
| HMMT-2016-FEB-GUTS-10 | 2 | 二つの三角形の外心間距離 | 未入手 |
| HMMT-2017-FEB-GUTS-06 | 4 | 凸四角形の中点間距離二乗の和 | 未入手 |
| HMMT-2020-FEB-GUTS-02 | 7 | 弧中点と接線、角ACB | 未入手 |
| HMMT-2021-FEB-GUTS-03 | 5 | 扇形の接円の半径rの床関数 | 未入手 |
| HMMT-2021-FEB-GUTS-09 | 4 | 共通中点を持つ3線分、六つの面積の和 | 未入手 |
| HMMT-2022-FEB-GUTS-01 | 1 | 正2022角形の面積の四捨五入 | 未入手 |
| HMMT-2022-FEB-TEAM-03 | 4 | 内接円に接する弧中点間線分、XY/R | 未入手 |
| HMMT-2022-FEB-GEO-07 | 6 | 外心四角形の辺長順序と既約分数、100a+b | 保存公式解答から転記 |
| HMMT-2022-FEB-GEO-08 | 5 | 楕円・放物線の焦点と準線、AH²+BH² | 保存公式解答から転記 |
| HMMT-2023-FEB-GEO-06 | 5 | 凸四角形の整数角n | 保存公式解答から転記 |
| HMMT-2024-FEB-GUTS-06 | 2 | 三等分点と中点の共円、三角形面積 | 未入手 |

2022 TEAM-03だけは、原問の「Rによる長さ表示」を相似正規化R=1で係数XY/Rにした。
元の長さは係数にRを掛けて復元する。2022 Geometry-07は既約分数を勝手に求値対象へ
変更せず、整数a,b,h,kとha+kb=1で互いに素を表し、目標100a+bを保った。
十二角形の可能値は列挙しておらず、全ての値を得たことを確認する採点も未実装。
床関数や整数条件の実行時挙動もパース以上の確認はしていない。

### 検査で分かった範囲

[validation.json](validation.json) に全18問548式の結果を保存した。
JSONの公開モデル、式のAST、関数名・引数・名前のスコープ、カードの全条件対応、
原文・DSLのSHA-256、一つのDSLとcases内のDSLの一致を検査した。
`geosolver.engine` がimportされていないことも検査した。
式を数値評価する `validate()`、コンパイル後の実行、solverは呼んでいない。

既存323問+2026年20問に対し、正規化ID、同一DSL、正規化した原文の完全一致は0件だった。
これは言い換えや別名の問題を完全に検出する検査ではない。
別名の過去DSLは上記3問について手動で入力だけを確認し、除外した。
この限界から、ファイルの状態は `selected_candidate` / `incomplete_offline_candidates` とした。

### 成果物

| ファイル | 内容 |
|---|---|
| `cases.jsonl`, `dsl/` | 答え・難度・解説を含まない18入力 |
| `statements.jsonl` | 428行の保存原文・出所・hash。抽出が崩れた箇所のraw抜粋も保持 |
| `cards.md`, `cards/` | 原文→全構成・全条件・目標の対応、座標固定と残る制約 |
| `manifest.json` | 255保留+428監査行、ID・採否・理由・入力hash・資料hash |
| `authoring-rules.md` | 指定規則の欠落と推定方針、母集団・順序の規則 |
| `official_answers.jsonl` | 公式答え4問、公式未入手14問、二次資料の未評価の参照答 |
| `answer-provenance.json` | 入力固定後の答え転記、原資料hash、DSL/manifest不変の確認 |
| `validation.json`, `verify_static.py` | パース・静的検査の記録と再実行用コード |
| `build_cases.py` | 答え・成績を使わない原文抽出・DSL生成・manifest生成 |
| `seal_answers.py` | 入力固定後の公式Answer行の分離転記 |
| `source-evidence/` | 2022 Geometry原文PDFを確認したページ画像 |
| `revisions/` | 原文資料を追加する前のv1規則・manifest・検査記録 |

`input_sha256` は `dsl/<id>.json` の末尾LF込みの全UTF-8 bytesのSHA-256。
`statement_sha256` は保存した本文文字列だけのUTF-8 bytesのSHA-256。
未入手・除外でDSLがない行の入力hashはnull。
manifestの `official_answers_verified=0` は入力固定時点の状態で、答え転記後の状態は
`answer-provenance.json` に記録した。manifestは答えを見た後に変更していない。

指定Pythonでの再検査は次のとおり。外部ディレクトリは参照資料の読み取りだけ。
再生成は公式答えファイルを未照合状態に戻すため、3手順を順に実行する。

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/kabatan/work/solver/.venv/bin/python jssa/difficulty/unseen-1983/build_cases.py
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/kabatan/work/solver/.venv/bin/python jssa/difficulty/unseen-1983/verify_static.py
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/kabatan/work/solver/.venv/bin/python jssa/difficulty/unseen-1983/seal_answers.py
```

Python環境の変更、pip install、ネットワーク、git fetch、commit、pushはしていない。
今回の書き込み先はすべてこのディレクトリ内。処理は原則逐次、独立な読み取りのみ最大2並列。

### 完成に必要な未入手資料・作業

承認を待つネットワーク取得は行わず、必要な資料を具体的に残す。

1. **AIME 1983〜1999の全17年・各1〜15問の原文、参照図、公式答え一覧。**
   現在のmanifestは全255スロットが原文未入手。資料入手後に年・番号順で全件判定し、
   少なくとも6問を補充して24問以上へ。後日追加は別版で記録する。
2. **HMMT February Gutsの2012、2015、2016、2017、2020、2021、2022、2024年の
   公式問題冊子・答え一覧。** 10候補の暫定indexを実際の問題番号と照合し、答えと図を補う。
3. **HMMT February Teamの2013、2014、2016、2022年の公式問題冊子・答え一覧。**
   4候補の番号・原文・答えを照合する。2022年はRによる表示も保持して確認する。
4. 18問の原文と入力の独立した意味監査。特に弧・同側・準線、整数/床関数、
   十二角形の単純性と可能値集合の扱い。必要な修正は本版を上書きせず別版にする。
5. 完成版のID・入力hash・除外理由・採点方式を固定し、ユーザー側でcommitした後に
   本検証を始める。今回の担当ではsolverを実行しない。

ARMLを補充先にする場合には対象年・部門の**問題冊子全体、図、公式答え**が必要で、
特定の易しい問題だけの抜粋では「書けるもの全部」という選定規則を再現できない。
