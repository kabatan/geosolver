# 日本学生科学賞 2026：レポート構成・実験計画

**対象**：第70回日本学生科学賞・高校の部「応用数学」  
**目標**：最高賞（内閣総理大臣賞）を狙える、鋭く、再現可能で、過大主張のない研究作品  
**作成日**：2026-08-28  
**最終更新**：2026-08-29  
**文書の役割**：応募レポートそのものではなく、本文・実験・補助資料・口頭審査を一つの論理へ統合する実行設計書

---

## 0. 基本方針：この研究を何として提出するか

### 0.1 推奨題名

> **求値幾何の探索可能性**  
> ―DSL表現と有限時間探索の境界―

題名は原則15字以内という公式規定に合わせ、主題を10字に抑える。副題で研究対象を具体化する。

候補：

- 求値幾何の探索可能性（第一候補）
- 幾何求値の有限探索
- 求値幾何の計算地形

### 0.2 研究の中心命題

> 求値幾何の探索可能性は、問題だけの性質ではなく、**問題・DSL表現・計算予算**の組によって決まる。本研究は、大規模な自然問題群で観測した主要な失敗機構を、数学的定式化、一因子の制御実験、未観測自然問題での方向予測によって調べ、固定予算下の経験的適用範囲を測定する。

### 0.3 この研究の三層

| 層 | 内容 | レポートでの扱い |
|---|---|---|
| 発想の原点 | AIMOでLLMが苦手な求値幾何を専用solverへ委譲する | 動機と応用実験 |
| 技術的中核 | 配置の全解ではなく、配置から得られる有限な目的値集合を回収する | 数学的・アルゴリズム的中核 |
| 科学的中核 | 大規模な自然問題群で失敗を観測し、その機構を人工系で隔離して、未観測の自然問題で予測的に再現する | E0・E3・E2を貫く主線 |
| 主結果候補 | 意味的に同じ問題でもDSL表現が数値的探索空間を変え、固定予算下の可解性を変化させる | 機構、方向予測、自然問題への移行まで再現された場合に主張 |

### 0.4 主張する新規性・研究貢献

1. 本solverの対象を、「配置の全解」ではなく、配置集合から得られる**有限な目的値集合**の探索として具体化した。
2. 有限時間の多点数値探索、高精度化、代数的descriptor同定を、有限目的値集合の回収のために統合した。
3. exactnessとcompletenessを分離した出力契約を採用した。
4. 大規模canonical corpus上の失敗を全件調査し、意味欠落、吸引域未到達、悪条件、境界漏れ、精密化、値同定等の最初の破綻checkpointへ分解する。
5. 失敗分析から得た主要仮説を一因子の人工問題族で検証し、意味同値なDSL対を用いて未観測の自然問題へ移行できるかを調べる。
6. DSL表現差をノイズや弱点として隠さず、探索可能性を予測・改善するための研究対象として体系化する。

### 0.5 主張しないこと

- 全ての2次元幾何問題を解けること
- 数値探索だけで解の網羅性を証明したこと
- PSLQと高精度近似だけで数学的同一性を一般に証明したこと
- DSL＋数値最適化、LLM＋solver、求値幾何の計算機処理を初めて考案したこと
- AlphaGeometry、computer-aided designの幾何engine、Gröbner基底、ホモトピーより一律に優れていること
- 現在の約92.6%が未知問題への一般化率であること

### 0.6 研究内容と信頼性の配分

形式的な再現性は、研究の主題ではなく、主結果を安心して読んでもらうための土台とする。作業と本文の重心はおおむね次のように置く。

| 重心 | 目安 | 内容 |
|---|---:|---|
| 科学的中核 | 70% | 有限目的値像、DSL表現依存性、成功・失敗機構、その数理的説明 |
| 性能と比較 | 20% | 未知問題性能、ablation、同一taskでのbaseline比較 |
| 信頼性と応募実務 | 10% | 凍結、分母、raw log、AI利用開示、提出確認 |

本文に必要な信頼性情報は、原則として次の四点だけでよい。

1. 最終solverと計算条件を先に固定した。
2. 開発に使っていない評価集合を用いた。
3. unsupported・参照未確定・失敗を分母から隠していない。
4. case別結果とraw logを補助資料に保存した。

これらは方法欄の短いparagraphと評価funnel一図で示し、hash、seed全表、再実行規則、環境lock等は補助資料へ回す。指導教員にcustodianや全caseの再判定を依頼する必要はなく、数学的主張と分野適合のreviewをお願いする程度で十分である。各確認実験の直前に仮説、操作因子、対象選定規則、評価指標を1ページ以内のprotocolとしてcommitすれば足り、形式の厳密化によって失敗分析と機構実験の時間を削らない。

---

## 1. 日本学生科学賞の公式条件

### 1.1 応募上の重要事項

- 第70回の応募期間は**2026年8月31日～10月27日必着**。
- 「情報・技術」「応用数学」は地方審査を経ず、全国一括の事前審査へ応募する。
- 本研究は、数学的定式化、成功条件の命題化、DSL表現実験を中心にするため「応用数学」を第一候補とする。
- 2026年1月以降のデータを含める。継続研究では過年度部分と2026年の新規部分を明確に区別する。
- 同一研究をJSECへ重複応募できない。
- 最高賞の正式名称は「最優秀賞」ではなく**内閣総理大臣賞**。

研究時期は次のように記載する。

| 時期 | 位置づけ |
|---|---|
| 2025年12月 | AIMOを契機とした着想・初期試作 |
| 2026年1～4月 | 初期検討 |
| 2026年4～6月 | 中断 |
| 2026年7月10日以降 | 現repoで監査可能なclean-slate実装、実験、benchmark構築 |
| 2026年9～10月 | 新規評価集合、DSL感度、失敗機構等の応募用実験 |

2025年部分に日時付き資料が十分なければ、成果ではなく着想として簡潔に扱う。主要成果と主要データは2026年7月以降として提示する。

### 1.2 レポート規定

- A4・横書き。
- 本文は5,000～8,000字程度。参考文献、謝辞、図表クレジットは字数外。
- 題名は原則15字以内。長い場合は副題を用いる。
- 指定項目：題名、要旨・概要、問題提起・研究目的、研究方法、結果、考察、結論・課題、参考文献、謝辞、図表・画像。
- 図表には番号とcaptionを付け、本文から参照する。
- PDFは30 MB以内。
- アップロード版と紙提出版を一致させ、必ず最終版をアップロードする。一度アップロードすると変更できない。
- PDF file名は「整理番号・学校名」とする。
- form登録後に届くID/PASSを保管し、MyPageへPDFをuploadしてから、同じ最終版と出品票を郵送する。
- 紙はカラー両面印刷、左上1か所をクリップ留め。表紙追加、ホチキス、製本はしない。
- 補助論文、実験ノート、動画等はCD-RまたはUSBで提出できる。重要な主張は本文だけで理解可能にする。
- 直接持参は不可。レポートと記録媒体は返却されず、標本・装置・模型等の実物は送付しない。
- 生成AIを使った場合は、名称・version・有料/無料・使用箇所・方法を記載し、promptを保存する。
- 生成AIの利用開示は、指定どおりレポート末尾に置く。

情報・技術／応用数学の送付先：

> 〒100-8055 東京都千代田区大手町1-7-1  
> 読売新聞東京本社 社会貢献事業室 日本学生科学賞事務局

### 1.3 公式資料

- [第70回応募要項](https://event.yomiuri.co.jp/jssa/assets/pdf/about/jssa2026.pdf?20260520)
- [応募方法](https://event.yomiuri.co.jp/jssa/how)
- [研究レポート規定](https://event.yomiuri.co.jp/jssa/assets/pdf/how/research-report-regulations.pdf?20260603)
- [FAQ](https://event.yomiuri.co.jp/jssa/qa)
- [研究作品のまとめ方](https://event.yomiuri.co.jp/jssa/arrange)
- [生成AI使用ルール](https://event.yomiuri.co.jp/jssa/assets/pdf/how/Generative_AI_Rules_Japan_Student_Science_Award.pdf?20260603)

数値化された公式採点rubricは公開されていない。以下の受賞戦略は、公式の「研究作品のまとめ方」と公開受賞概要からの推定であり、非公開の配点を推測したものではない。

---

## 2. 過去受賞作から抽出する設計原則

公開されているものは主に1ページの受賞概要であり、提出レポート全文ではない。この制約を明記した上で、研究の論理構造を分析する。

| 作品 | 受賞 | 強み | 本研究への翻訳 |
|---|---|---|---|
| [深層学習を用いた肺の異常検知](https://event.yomiuri.co.jp/jssa/voice/voice62) | 2018・内閣総理大臣賞 | 明確な社会課題、大規模データ、学習/評価分離 | 開発集合と未知評価集合を分ける |
| [点字を墨字に翻訳するアプリ](https://event.yomiuri.co.jp/jssa/storage/archives/64/HIT023IT.pdf) | 2020・内閣総理大臣賞 | 見落とされた利用者課題、複数手法比較、動く実装 | LLMが苦手な求値幾何という具体的gapを示す |
| [割当問題の拡張と解法について](https://event.yomiuri.co.jp/jssa/storage/archives/66/HAM029AM.pdf) | 2022・読売新聞社賞 | 古典問題の拡張、特殊/一般解法、既存solver比較、限界 | 「有限値射影」という問題クラスを定義する |
| [LUALCAD](https://event.yomiuri.co.jp/jssa/storage/archives/68/HIT039IT.pdf) | 2024・入選1等 | 現場のbottleneck、独自algorithm、実装、実物検証 | solverを動くartifactとして示し、実問題で検証する |
| [数学的視点による音律の再評価](https://event.yomiuri.co.jp/jssa/storage/archives/69/HAM023AM.pdf) | 2025・文部科学大臣賞 | 対象生成、定量指標、既存尺度との比較、限界から新尺度 | 「人間の幾何難度」と「探索難度」の新しい評価軸を作る |

選定した公開概要と公式「研究作品のまとめ方」から得る、本研究向けの設計仮説：

1. 「作ったもの」より先に、研究上の問いが一文で定義されている。
2. 既存手法の不足と独自工夫が一対一に対応している。
3. 工夫ごとに効果を測る比較・対照がある。
4. 本研究では、調整用データと評価用データを分離することが妥当である。
5. 成功例だけでなく、失敗、誤差、適用限界を説明している。
6. 理論、実装、実問題が一本の論理で接続されている。
7. 社会的意義を大きく列挙せず、具体的な利用場面で示している。
8. 専門外の審査員にも理解できる図と用語を用いている。
9. 研究者本人が採用しなかった案を含めて説明できる。

本研究にとって重要なのは、90%という一つの数字より、**なぜ解け、なぜ失敗し、意味的に同じ表現でなぜ結果が変わるか**を示すことである。

---

## 3. 先行研究に対する位置づけ

### 3.1 数学的な問題設定

DSL表現を \(R\)、探索領域を \(\Omega_R\)、等式残差を \(F_R\)、不等式・非退化条件を \(g_R\)、目的値を \(\tau_R\) とする。

\[
S_R=\{x\in\Omega_R\mid F_R(x)=0,\ g_R(x)>0\}
\]

\[
V_R=\{\tau_R(x)\mid x\in S_R\}
\]

本solverの対象として仮定するのは、答えの集合 \(V_R\) が有限であることである。配置集合 \(S_R\) 自体は正次元、すなわち無限個の配置を含んでもよい。像・射影そのものは数学上標準的な概念であり、その発明を主張しない。本研究ではこれを競技求値幾何へ具体化し、計算予算 \(B\) の下で高い経験的回収率を目指す手続きを研究する。

### 3.2 周辺分野との違い

| 分野・手法 | 主な目的 | 代表的出力 | 本研究との差 |
|---|---|---|---|
| AlphaGeometry、TongGeometry、GenesisGeo | 与えられた結論の証明 | 検証可能な証明 | 未知の目的値集合を発見する課題ではない |
| GMB/GMBL | 競技幾何の近似図生成 | 通常一つの配置 | 技術骨格は近いが全目的値回収が目的ではない |
| 幾何拘束solver（computer-aided design/GCS） | 意図したsketch配置の高速更新 | 初期配置近傍の一配置 | 冷スタートの複数目的値探索ではない |
| 拘束graph/DR法 | 幾何制約の分解と構成順序 | 配置または構成計画 | 分解可能性・認識規則に強く依存する |
| Gröbner基底/RUR | 主に零次元多項式系の消去・全解 | 条件を満たす範囲で厳密な代数解 | 保証と引き換えに適用条件・計算量の負担がある |
| 円筒代数分解（cylindrical algebraic decomposition） | 実多項式等式・不等式、量化消去 | cell分解と決定結果 | computer-aided design系GCSとは別概念。完全性と大きな計算負担を持つ比較軸 |
| 区間制約・branch-and-prune | box分割と区間評価による絞り込み | 認証boxまたは未決定box | 認証可能だが次元・分岐に伴う負担がある |
| numerical algebraic geometry | 多項式系の孤立根・正次元成分 | path、witness set、別途認証 | 不等式・幾何branch・target射影の扱いが異なる |
| GeoGebra Discovery | 手動構成した求値問題の記号解法 | 分数・根号等 | 求値問題の直接先例だが、少数の手動構成例 |
| 本研究 | 有限な目的値集合の予算付き探索 | algebraic/affine-π descriptor候補 | 完全性を原則unknownとして経験的回収率を狙う |

本文では曖昧な略称`CAD`を単独で使わず、computer-aided designとcylindrical algebraic decompositionを毎回区別する。

### 3.3 最も近い先行研究

1. Ryan Krueger, Jesse M. Han, Daniel Selsam, [Automatically Building Diagrams for Olympiad Geometry Problems](https://arxiv.org/abs/2012.02590), 2021。  
   DSL、parameterization、微分可能loss、多点初期化による最適化を既に実現している。したがって「競技幾何をDSLと数値最適化で扱うこと」は新規性にしない。差は、一つの近似図ではなく有限目的値集合を対象とすること、値同定、集合評価、表現頑健性、失敗機構に置く。

2. Amela Hota, Zoltán Kovács, Alexander Vujic, [Solving Some Geometry Problems of the Náboj 2023 Contest with Automated Deduction in GeoGebra Discovery](https://arxiv.org/html/2401.13703), 2024。  
   求値競技幾何を計算機で正確に解く直接的先例である。「求値幾何を初めて解いた」とは書かない。宣言的制約からの統一探索、広いcorpus、複数目的値、固定protocol評価を差とする。

3. Qiang Zou et al., [A review on geometric constraint solving](https://arxiv.org/abs/2202.13795), 2022。  
   computer-aided designにおけるGCSの全体像を示す主要survey。拘束graphを単純なtemplate集として否定せず、構造分解・対話的求解には強いが、本研究とは目的が違うと整理する。

4. AlphaGeometry、TongGeometry、[GenesisGeo](https://arxiv.org/abs/2509.21896)。  
   競技幾何AIの背景として触れるが、定理証明と求値探索を一つのleaderboardで比較しない。

### 3.4 安全な新規性文

> 調査した公開文献の範囲では、宣言的な2次元幾何DSLから、問題固有の定理templateを用いず、有限個の目的値を複数探索し、代数的descriptor候補へ復元して、広い競技問題集合上で目的値集合単位の評価を行った公開systemは確認できなかった。本研究は完全決定手続きではなく、固定計算資源下で高い回収率を目指す経験的solverである。

「世界初」とは断定せず、調査範囲と要件の組合せを明記する。

---

## 4. exactnessとcompletenessの契約

「厳密」と「全解」を曖昧にすると、審査で最も攻撃されやすい。以下を本文と口頭発表で統一する。

| Level | 意味 | 現状の到達点 |
|---|---|---|
| L1 数値候補 | 小さな残差を持つ配置を発見 | 実現 |
| L2 descriptor同定 | algebraicまたはaffine-πの記号候補を復元 | 実現 |
| L3 解の認証 | 元制約を満たし、そのdescriptorが真の値だと数学的に証明 | 一般には未実現 |
| L4 完全性 | 他の目的値が存在しないと証明 | 原則unknown |

本文で用いる表現：

> solverは代数的厳密形の候補を同定し、高精度数値整合性を確認する。評価では、根拠levelを記録したadjudicated reference setとの記号的一致を測る。数値探索による網羅性証明はなく、completenessは原則unknownとする。

避ける表現：

> 90%の問題ですべての解を厳密に発見した。

可能ならstretch goalとして、区間Newton/Krawczyk法、alpha-theory、記号代入等により、限定subsetでL3認証を追加する。ただし、主実験を遅らせてまで全問題へ一般化しない。

---

## 5. 現在ある証拠の正しい扱い

### 5.1 最新の閉じたcorpus上の結果

`experiment` branchの2026-08-22 full runは次の条件である。

- solver source：`32bd715c0b80bd10bbd551a56fe17dfb8f004bb2`
- full-run/report commit：`d93a132037d0b5ea1b1976217ff928b5bc1f81f1`
- 302 DSL files
- 実行可能285、reference-only 17
- repo上のtruth status：`verified` 205、`unresolved` 91、`not_executable` 6、合計302。この`verified`は数学的な完全性certificateを意味しない
- seed 7
- 180秒/case、1 core
- repoで手作業監査されたadjudicated reference setとの記号的集合一致：190/205 = 92.68%
- verified失敗：timeout 10、no_solution 3、success/mismatch 2

この302 filesは、truth、実行結果、aliasの三軸を混ぜずに扱う。truthと実行結果のcross tableは次の通りである。

| 実行結果 \ truth | verified | unresolved | not_executable | 合計 |
|---|---:|---:|---:|---:|
| success | 192 | 60 | 0 | 252 |
| no_solution | 3 | 9 | 0 | 12 |
| timeout | 10 | 11 | 0 | 21 |
| reference_only | 0 | 11 | 6 | 17 |
| **合計** | **205** | **91** | **6** | **302** |

3組のalias重複を問題単位で除くと、主値は**187/202 = 92.57%**である。190/205はfile単位の再現値として併記する。

### 5.2 この数字が意味しないこと

- 現行`research` HEADの性能値ではない。
- 未知問題に対する一般化率ではない。
- 302問すべての正答率ではない。
- truth status（205/91/6）、実行status（285/17）、unique/aliasは別の分類である。応募版では一つのcross tableへ閉じ、分母を混ぜない。
- solver自身が完全性を証明した割合ではない。
- 139/205から190/205への増加が単一algorithmの効果ではない。DSL修正、guard、runtime、高精度化、exactification等が混在する。

### 5.3 本文用の現時点で安全な記述

> 開発・監査に用いた競技幾何corpusでは、凍結した実装が180秒・1 coreの条件で、adjudicated reference setを用意した202独立問題中187問について、出力descriptor集合をその参照集合と一致させた。このcorpusはsolver改善にも使用したため、未知問題性能は新規評価集合で別途測定する。

### 5.4 応募前の技術的必須作業

- 提出対象runtimeを一つに決め、`submission-candidate` tagを付ける。
- 現行HEADと過去benchmark runtimeの差を解消する。
- engine integrity hash不一致を解消する。
- 180秒という外側hard timeoutと内部探索budgetの関係を明文化する。
- dependency lock、OS、CPU、Python/Julia/NOMAD/SciPy/mpmath等のversionを固定する。
- 最終tagで同じfull runをfresh processから再実行する。
- unique problem単位のdedupe表を確定する。
- raw artifactとSHA-256 manifestを保存する。

---

## 6. 研究質問と仮説

### RQ1：成功・失敗機構の発見

> 大規模なcanonical corpusで観測される失敗は、pipelineのどのcheckpointに集中し、どの測定可能な量から説明仮説を作れるか。

この段階は**探索的研究**と明記する。timeout/no_solution/mismatchを、意味層、探索層、精密化層、値同定層の最初の破綻checkpointへ全件分類し、対応する成功例と比較する。結果を見る前に個別原因を固定したことにはしない。

**H1候補の固定方法**：全失敗を調べた後、反復して現れ、理論的に一因子へ隔離でき、未観測問題で方向予測できる機構を原則1個選ぶ。選択理由、操作因子、予測方向、評価指標を、確認実験を走らせる前にversion化する。第一機構の証拠chainが閉じた場合だけ、第二機構へ進む。

### RQ2：機構とDSL表現依存性の確認

> 選定した失敗機構を人工問題族で一因子操作できるか。また、その機構が生じると事前予測した自然問題で、意味同値なDSL表現の変更が中間指標とsolver成否を予測方向へ変えるか。

**H2**：確認対象として選んだ主要機構について、DSL表現はvalid volume、Jacobianのrank/条件、sampling measure、guard margin等の中間量を変え、固定予算下の成功率・時間・失敗checkpointを変化させる。人工family内では因果的効果を、未観測の自然問題では予測との整合性と外的妥当性を評価する。

### RQ3：未知問題性能

> 凍結したsolverは、開発に使っていない求値競技幾何に対し、固定180秒・1 coreでどの程度target集合を回収できるか。

**H3**：source-faithfulなcanonical DSLが作成できた問題では、未知問題でも高い集合一致率を維持する。ただし開発corpusの92.57%より低下する可能性を認める。

### RQ4：構成要素の寄与

> 高精度化、rank-aware closure、scaling、candidate diversity、strict guard、exactificationは、成功率・安全性・時間へそれぞれどのように寄与するか。

**H4**：成功率を上げる構成要素と、誤受理を防ぐが正答数を増やさない安全構成要素が存在する。

### RQ5：LLMへの道具提供（副研究）

> LLM単独、LLM＋汎用Python、LLM＋GeoSolver、人間作成DSL＋GeoSolverのどこで正答率が変わるか。

**H5**：正しいDSLを条件とすればGeoSolverはLLM単独より安定するが、自然言語からDSLへの意味忠実な変換がend-to-end性能の主要bottleneckになる。

---

## 7. レポートの物語構造

### 7.1 一本の論理線

1. 求値幾何を有限目的値像の探索として定式化し、そのためのsolverを構築する。
2. 一つのcanonical規則で大規模な自然問題corpusを実行し、成功だけでなく全失敗を記録する。
3. 失敗がどのcheckpointに集中するかを調べ、対応する成功例と比較して原因仮説を作る。
4. 主要仮説を原則一つ選び、一因子の人工問題族で操作して中間量から成否を説明する。証拠chainを閉じられた場合だけ第二機構を追加する。
5. 結果を見ていない自然問題を静的signatureだけから選び、意味同値なDSL対で予測方向を確認する。
6. 小さな結果非依存panelで、表現依存性の頻度を機構の存在と分けて測る。
7. 最終的に凍結したsolverを未知問題で評価し、経験的な適用範囲を示す。
8. 公開難度proxyとの比較から、人間の幾何難度と異なる計算的難度がある可能性を考察する。
9. E6まで完了した場合だけ、LLM利用を応用例として示す。

研究史、AI史、機能一覧から始めない。中心は「高い成功率の報告」ではなく、**自然問題で発見した失敗を人工系で隔離し、再び自然問題へ戻して予測した**という往復に置く。同じ問題で成否が分かれるDSL対は強い導入例になるが、その一例から一般化せず、大規模調査の中で発見された現象として提示する。

### 7.2 冒頭文の型

> 多数の求値幾何問題を一つの規則で記述してsolverを実行すると、高い成功率の一方で、失敗は特定の処理段階に偏っていた。その原因を調べる過程で、意味的に同じ問題でもDSL表現により探索挙動が変わる例が見つかった。意味が同じなら、なぜ固定時間内の計算結果は同じにならないのか。本研究では、この差を生む数理的・計算的機構を調べた。

実測値が確定するまでは時間や問題名を入れない。最終版ではprospectiveに定めた代表例または再現可能なdevelopment例を使う。

### 7.3 IMO/JMO歴の使い方

応募者の実績：IMO 2025金メダル、JMO 2025銀賞・3位。

本文では権威付けに使わず、次のように研究動機へ変換する。

> 国際数学オリンピックを含む競技幾何に取り組む中で、人間にとって難しい補助線・定理発見と、求値問題に必要な計算処理とは異なる能力ではないかと考えた。

研究方法上の強み：

- source-faithfulなDSL規則の設計
- 点順、有向角、交点枝、退化等の反例設計
- 人間には難しいがsolverには易しい問題の解釈
- solverには難しいが人間には易しい問題の構造分析

同時に、「専門家がsolverに都合のよいDSLを書いた」という交絡を認め、canonical規則、複数表現、作成過程の記録によって分離する。

---

## 8. 本文構成案（約6,900字）

参考文献、謝辞、図表creditを除く本文目標を6,700～7,200字とし、上限8,000字ぎりぎりを避ける。

| 章 | 目安 | 役割 |
|---|---:|---|
| 1. 要旨・概要 | 450字 | 問い、方法、主要結果、限界を一段落で述べる |
| 2. 問題提起・研究目的 | 1,250字 | 有限値射影、先行研究との差、RQを示す |
| 3. 研究方法 | 1,650字 | DSL、solver、発見→確認→自然問題への移行 |
| 4. 結果 | 2,100字 | canonical調査、失敗仮説、人工系、自然問題、未知評価 |
| 5. 考察 | 950字 | 因果解釈、主張範囲、人間難度との差、応用 |
| 6. 結論・課題 | 500字 | 狭く強い結論、未証明部分、次の一手 |
| **合計** | **6,900字** | 余白約1,100字 |

この設計書ではrepo内の語との対応を保つため`solver`、`target`、`source`、`freeze`等を用いるが、提出本文では原則として「求解器」「目的値」「原問題」「固定」と書く。英語の専門語は初出で日本語定義を添え、code上の識別子が必要な図表にだけ残す。

### 8.1 要旨・概要

必ず含めるもの：

1. 対象：有限個の値を答えとする2次元求値幾何
2. gap：証明器、図生成、computer-aided design系GCS、完全代数法とは目的が異なる
3. 方法：DSL、有限時間数値探索、高精度化、descriptor同定
4. 主結果：canonical corpusで発見した失敗分布、主要機構、自然問題での方向予測
5. 性能結果：新規評価集合の参照集合一致率、参照集合coverage、95%区間
6. 限界：completenessは原則unknown

結果が出る前のtemplate：

> 答えが有限個となる2次元幾何問題を、配置集合の有限な目的値像を求める問題として定式化し、有限時間の数値探索、高精度化、代数的descriptor同定を組み合わせたsolverを構築した。canonical表現による大規模調査で観測した失敗を分類し、主要機構［M］を一因子の人工問題族で操作したところ、［中間指標］と成功率が予測方向へ変化した。さらに、静的特徴から事前選定した自然問題の意味同値なDSL対でも同方向の変化を確認した。solver凍結後の新規評価集合［U］問では、参照集合を事前確定できた［T］問中［C］問の出力集合が一致した。一方、数値探索による網羅性証明はなく、完全性は原則unknownである。

### 8.2 問題提起・研究目的

順序：

1. AIMOと競技幾何経験から生じた疑問
2. 証明問題と求値問題の違い
3. 完全代数法の保証と計算負担というtrade-off
4. \(S_R\) と \(V_R\) の定義
5. GMBL、GeoGebra Discovery、GCSとの差
6. RQ1～RQ4。本文ではRQ1→RQ2の「発見から確認」を主線とし、未知性能のRQ3は経験的範囲の確認、LLMは副RQとして短く置く

AI史を長く書かない。AlphaGeometry系は背景の一段落と位置づけ図に限定する。

### 8.3 研究方法

共通定義の後、実験ごとに同じ小見出しを用いる。

- 研究上の役割（探索、人工系での確認、自然問題への移行、頻度推定、未知性能）
- 対象集合
- 変更因子
- 固定条件
- primary endpoint
- secondary endpoint
- 除外規則
- 統計単位

solver説明は一枚図と一つの残差式に絞る。

> DSL → parameter/bounds推定 → 初期候補生成 → global/local探索 → hard feasibility → 高精度refinement → descriptor同定 → descriptor集合化

既存の最適化algorithmの数学的詳細は引用し、独自の組合せ、guard、rank-aware closure、exactify後dedup等を説明する。

### 8.4 結果

次の順序を固定する。実験番号順ではなく、科学的推論の順に並べる。

1. canonical corpusの全体結果と失敗checkpoint分布
2. 全失敗のforensicsと中心仮説
3. 人工問題族の一因子phase diagram
4. 未観測自然問題のpaired DSLと負の対照
5. 結果非依存panelでのrepresentation split rate
6. 最終solverの新規評価funnel、seed安定性、anytime curve
7. ablationと外部比較
8. LLM実験は紙幅があれば最後、詳細は補助資料

有利な成功例だけを図示しない。代表的な成功、境界例、未解決を一つずつ示す。

### 8.5 考察

事実と解釈を文法上も分ける。

- 事実：「L3 parameterizationで成功率がX点変化した」
- 解釈：「Jacobian条件とsampling measureの変化が一因と考えられる」
- 限界：「自然問題では問題難度との交絡が残る」

E0・E3・E2で対応する実測結果が得られた場合の中心結論：

> solverは幾何の難しさを消したのではない。公開難度proxyとsolverの成否が一致しない例、および制御実験の結果は、補助線・定理発見とは異なる、吸引域、条件数、guard margin、枝構造に由来する数値探索上の難度がある可能性を示す。

社会的価値は一つに絞る。第一候補は「LLMが形式化した後段を再現可能なsolverへ委譲すること」。作問支援は「曖昧性や複数値候補を発見する補助」とし、問題不備がないことを証明できるとは書かない。逆運動学は将来課題の一文に留める。

### 8.6 結論・課題

結論は三点以内：

1. 有限値射影としての求値幾何を定式化した。
2. canonical corpusから選んだ主要機構について、人工系で因果的証拠を得て、未観測自然問題で予測との整合性を確認した。
3. 凍結したsolverの未知問題評価で［結果］を得た。

課題：

- 一般の完全性証明
- descriptorの数学的認証
- source textからDSLへの自動形式化
- 表現を自動改善するcompiler

---

## 9. 必要な図表

本文は5図＋2表程度を目安とする。

### 図1：発見から自然問題へ戻る研究設計

`canonical corpus → 全失敗の分類 → 原因仮説 → 一因子の人工問題族 → 未観測自然問題のpaired DSL → 最終未知問題評価`

- 各矢印に「ここで結果を見たか」「次段階で何を固定したか」を短く示す。
- 探索的分析、人工系での確認、自然問題への移行、頻度推定を色分けする。
- 形式管理の図ではなく、各段階で何が新しく分かるかを示す。

### 図2：問題設定の地図

| 求めるもの | 代表分野 |
|---|---|
| 命題の証明 | AlphaGeometry系 |
| 配置を一つ | computer-aided design系GCS、GMBL |
| 配置の全孤立解 | Gröbner/RUR/Homotopy |
| 有限な目的値像 | 本研究 |

### 図3：solver pipelineと保証ladder

探索、精密化、値同定を横方向、L1～L4保証を縦方向に示す。どの段階で何を保証していないかを図に含める。

### 図4：canonical corpusのfailure census

- 全問題からcanonical success、seed不安定、stable failureへの分岐
- stable failureを最初の破綻checkpoint別に表示
- success側のmatched controlも同じ指標空間へ置く
- 開発corpus内の記述であり、未知問題性能ではないとcaptionに明記

### 図5：機構のcausal ladder

- 左：人工問題族の操作parameterと中間量
- 中：成功率、時間、failure checkpointのphase diagram
- 右：自然問題のcanonical／predicted-improve／predicted-worsenのpaired結果
- 人工系では因果的証拠、自然問題では予測との整合性であることを図内で区別

### 補助図：評価funnelと未知問題結果

`source U → source-faithful DSL D → adjudicated reference set T → reference-set match C`

unsupportedやtruth未確定を消さない。

### 補助図：代表E2のDSL表現heatmap

- 行：結果非依存に選んだ問題
- 列：canonicalと事前固定した3～4種類の広域適用variant
- 色：集合一致、timeout、no_solution、mismatch

本文ではproblem単位のrepresentation split rateを小さく示し、全heatmapとmechanism-targeted variantは補助資料へ回す。

### 表1：先行研究比較

入力、目的、出力、保証、比較可能subsetを示す。勝敗だけの表にしない。

### 表2：証拠の段階と主結果

E0、forensics、人工family、E2-M、E2-R、E1について、対象数、選定方法、primary endpoint、主要結果、許される主張を一行ずつ示す。ablationの成功率、false acceptance、activation件数は紙幅があれば小表、詳細は補助資料へ回す。

---

## 10. 共通評価規約

### 10.1 評価単位

- 統計単位はDSL fileではなく**unique source problem**。
- 同一問題のalias、数値変更、翻訳、図だけの差をfamilyとして管理する。
- seed、DSL variant、同じ問題の再実行を独立問題数へ数えない。

### 10.2 成功の定義

primary success：

> solverが返したcanonical descriptor集合と、事前に根拠levelを記録したadjudicated reference setが双方向に一致し、余分な値も不足する値もない。

単なる`status=success`、数値近似、表示用contest answerの一致はprimary successとしない。

### 10.3 計算条件

- 180秒/case
- 1 core/case
- fixed hardware、OS、dependency versions
- fresh subprocess/case
- networkなし
- hard timeout
- wall time、CPU time、peak RSS、評価回数を記録
- concurrent実行する場合も各caseを別coreへaffinity固定し、干渉を記録する

### 10.4 seed

- primaryは製品default、またはfinal tagから機械的に導く方法でholdout前に固定した1 seedとする。過去に繰り返し使用したseed 7はdevelopment比較だけに用いる。
- robustnessとして追加4 seedもprimary閲覧前に同じworkflowへ固定する。
- `pass@1`、全5 seed成功、`pass@5`を分ける。
- `pass@5`は5倍の計算予算を使った結果として表示する。
- 5 seedの平均single-run成功率とseed別rangeもsecondaryとして示す。5 seedを大きな確率母集団とみなした強い推測は行わない。

### 10.5 統計

- 無作為または明示した母集団から抽出したprimary固定seedの成功率にWilson 95% CIを付ける。連続年代の全数調査なら、区間は将来問題へのsuperpopulation modelに基づく参考値と明記する。
- variantを含む解析は、まず問題内でmacro平均し、problemをclusterとしたbootstrapを用いる。
- paired solver比較は問題単位の差とMcNemar検定またはpaired bootstrapを用いる。
- runtimeはtimeoutを除外した平均だけでなく、median、p90、success curve、PAR-2を示す。
- p値だけでなく、差の大きさと区間を示す。多数の副比較はexploratoryと表示するかHolm補正を用いる。
- E0のcanonical censusとE2-Rだけが、定義したcorpus/frame内の頻度を扱う。forensicsで原因候補が占めた割合と、E2-Mのtargeted case成功率を一般頻度へ外挿しない。
- forensicsは全caseの記述と仮説生成を目的とし、少数失敗に対する多数の有意差検定を行わない。
- 人工familyでは同じseedをparameter level間で対応させ、levelごとのseedを独立標本として水増ししない。dose-response、中間量、効果量を主に示す。
- E2-Mでは問題ごとの方向一致、paired差、負の対照との差を示す。問題数が少ない場合、単一のp値よりcase plotと予測の成否を重視する。

### 10.6 実験記録

各実験は次を一行または一JSON objectで保存する。

```text
experiment_id
hypothesis
control_commit / candidate_commit
changed_mechanism
dataset / partition role / manifest SHA
seed / budget / CPU / environment
primary metric / decision gate
result
decision
claim boundary
artifact SHA
reproduction command
```

### 10.7 逐次実験と主張境界

追加実験を最初から全て固定する必要はない。代わりに、**一つ前の段階で仮説を作り、次の未実行段階を走らせる前にそのprotocolを固定する**。これは研究の本題を圧迫しない最小限のpost-hoc対策とする。

| role | データを選ぶ時点 | 主な役割 | 主張してよいこと |
|---|---|---|---|
| `canonical_discovery` | source規則とcanonical manualを先に固定 | 現象の全体像、失敗分布 | このcorpus内で何が起きたか |
| `forensic` | canonical outcome後。全失敗＋matched success | 仮説生成 | 原因候補。一般的頻度や因果は未確定 |
| `synthetic_confirmatory` | 仮説、parameter grid、方向予測を実行前固定 | 一因子介入 | その人工family内の因果的効果と機構の存在 |
| `natural_transfer_reserve` | canonicalを含むsolver outcome未観測の自然問題を静的signatureで選定 | 外的妥当性 | 選定した自然問題で予測方向が再現したか |
| `representative_E2` | outcome非依存の層化・stable hash | 表現依存性の頻度 | 定義したsource frame内のrepresentation split rate |
| `prospective_E1` | 最終solver固定後 | 未知問題性能 | 定義したsource frameへの経験的一般化 |

共通規則：

- 一度結果を見たcaseを、後段の未観測確認集合へ昇格させない。
- `natural_transfer_reserve`の高い成功率を、一般問題における機構の頻度として報告しない。
- seed、parameter level、DSL variantを独立した問題数として数えない。
- 確認実験のprotocolには、仮説、方向予測、操作因子、対象選定、負の対照、primary endpoint、停止規則だけを1ページ以内で記録する。
- 予測に反した結果と`UNKNOWN`を残し、protocolを変えた再実験は新しいexperiment IDへ分ける。

E0の結果を見る前に、自然問題のeligible poolを相互排他的なroleへ分ける。

1. E2-Rを実施する場合は、source frame、層、件数、hash salt、広域適用variantを先に固定して代表panelを確保する。
2. E2-M用には、その残りからoutcome未観測のreserve poolを確保する。具体的な正例・負の対照はE3後に静的signatureから選んでよい。
3. E1はE2と重ならない別source frameに置き、final freezeまでcase IDを確定しない。

E2-M結果を見た後にE2-Rの層や抽出規則を変えない。凍結済みE2-Rを実行しない判断は可能だが、その場合は最終結論から表現依存性の頻度を削る。

既存の呼称との対応を保つためE1＝未知性能、E2＝表現依存性、E3＝失敗機構とするが、実行順は番号順ではない。

> **E0 canonical census → E3 forensics → E3人工確認 → E2-M自然問題への移行 → 必要ならE2-R頻度推定 → final freeze → E1未知問題評価**

提出本文ではE番号を前面に出さず、「現象発見」「仮説生成」「機構確認」「自然問題での確認」「未知性能」の順に記述する。

---

## 11. 実験E0：大規模canonical corpus調査

### 目的

まず自然な問題を一つの表現規則で広く実行し、solverが「何問解けたか」だけでなく、**どこで失敗したかを発見する母集団**を作る。同時に、提出候補runtimeについて環境・source・結果を閉じる。

既存302 DSL files全体は、solver調整に使われたため未知性能の評価には使えない。一方、失敗現象の発見と機構仮説の生成には最も情報量が多く、truth未確定や実行不能も含むsource inventory全体を残すことで、見栄えのよいcaseだけを選ぶ危険を減らせる。参照集合がある202 unique問題の性能評価と、全実行可能caseのpipeline挙動調査は分ける。

### corpusとcanonical表現

- cleanな自然問題corpusの規模は200～300 uniqueを目安とするが、件数を先に満たすための手選別はしない。連続した大会・年代等のsource frameに該当する全問題を採用した結果として件数を決める。期限内に全既存caseをmanual v1へ移植できない場合は、事前に決めた連続blockで切り、残りを都合よく抜き取らない。
- 原則として既存302 filesを全てinventoryへ入れ、source family単位でdedupeする。参照集合がある202 unique問題だけに母集団を縮めない。現行schemaへ未移植のcaseは、移植可否と理由をfunnelに残す。
- alias、数値だけを変えた同一family、翻訳重複を分離し、統計単位はunique source problemとする。
- 各問題はcanonical authoring manualに従った1表現をbaselineとする。
- 過去にsolver成否を見ながらDSLを修正したcaseは削除せず、`development_touched`と明示する。corpus内成功率は記述値であり、一般化率や表現感度の母集団推定には使わない。
- 既存DSLを単に`canonical`と改名しない。manual v1から結果を見ずに再構成できるものを`canonical_clean`、成否を見ながら修正した履歴があるものを`development_touched`とする。主なfailure分布は両方を示し、表現規則に関する数量的結論は`canonical_clean`または新規に作ったsource-complete subsetで確認する。
- `verified`、`reference_unresolved`、`not_executable`を別層として残す。参照集合一致率はverified unique問題で、candidate発見やfailure checkpointはtruth未確定を含む全実行可能unique問題で集計し、二つの分母を混ぜない。
- 新しい問題を追加する場合は、連続した大会・年代等のsource frameと収録規則を先に固定し、結果を見ずにcanonical DSLを全て作る。

### case作成と実行前freeze

1. source frame内の全問題を先にinventory化し、eligible／unsupported／重複をsolver結果なしで判定する。
2. 問題文の各clauseとDSLのconstruction、condition、guardの対応を短いledgerへ記録する。
3. solverを走らせず、parser、type、scope、未使用変数、次元等のstatic checkだけで全DSLを整える。
4. reference setは公式資料と独立な数学的導出・検算から作り、solver出力をtruth作成に使わない。
5. source、DSL、reference、manual versionを一括manifestへ固定してからprimary runを開始する。
6. 実行後にsemantic bugを発見した場合、元caseを消さず`semantic_error`として残し、修正版は新versionで再実行する。修正版だけを最初からのcanonical結果として扱わない。

E0は仮説を発見する開発調査なので、実行後にcaseを修正・追加すること自体は禁止しない。ただし、最初の一括runと後続修正版を分け、後から追加したcaseを元の母集団へ遡って混ぜない。

### 実行手順

1. current runtimeのintegrity、budget、descriptor contractを修正・確認する。
2. `discovery-candidate-YYYYMMDD` tag、dependency lock、machine profileを保存する。
3. canonical primary seedを全実行可能問題で実行し、robustness用の追加2 seedも同じmanifestに固定する。
4. 各runについて中間checkpoint、candidate数、valid proposal率、時間、評価回数、guard rejection、refinement、exactification、enumerationを保存する。
5. verified問題では集合一致に基づき、3 seed全て成功を`stable success`、全て失敗を`stable failure`、結果が割れたものを`seed-sensitive`とする。truth未確定問題では`candidate-returning`、`no-candidate`、`timeout`等の観測statusだけを用い、正解・不正解と呼ばない。これは便宜的な層別であり、真の成功確率の断定ではない。
6. stable failureとseed-sensitive caseは、E3のforensicsで追加traceまたは追加seedを用いて調べる。追加実行でE0の元結果を上書きしない。
7. 過去`32bd715c`との差をcase単位で表示し、退行例を隠さない。

180秒×3 seedが実務上重すぎる場合は、primary 1 seedを全数実行し、stable failure候補、境界例、結果非依存に抽出した成功例だけを追加4 seedで再実行する。この軽量版を採る場合、1 seedの失敗率と再実行後の安定性を別表にし、後から失敗caseだけへ有利な判定規則を適用しない。

### 出力

- verified層のcanonical success／seed-sensitive／stable failureと、truth未確定層の観測status分布
- pipeline checkpoint別のfailure census
- 全失敗caseへの一意なcase card
- matched successを選ぶための結果非依存な静的特徴表
- seed stability、anytime curve、過去runtimeからの改善・退行表
- SHA付きraw artifact

### 主張境界

E0から言えるのは、**この開発corpus内で観測された失敗の頻度と分布**である。ここから直接、未知問題性能、失敗原因の因果、一般の求値幾何における表現依存性の頻度を主張しない。本文では新規評価より後へ追いやらず、研究上の現象発見として結果の最初に示す。

---

## 12. 実験E1：solver-freeze後の新規評価集合

### 目的

開発に使っていない問題に対する一般化性能を測る。E0の失敗分析、E3の人工実験、E2の自然問題への移行、そこから得た一般的な改良を全て終えた後にfinal solverを固定し、最後に実行する。第三者custodianや暗号封印までは求めず、Git上のprotocol、solver freeze、raw保存による軽量なprospective評価を行う。これは第三者によるsealed evaluationではないことも明記する。

E1は失敗機構を発見・確認するためのデータとして使わない。E1後のcase分析は補助資料で`post-hoc E1 forensics`と表示し、その結果を使ってsolverを修正した場合、その版に対するE1のprospective性は失われる。

### 規模

- 既定：50 unique source problems
- stretch：60 problems。中心機構のE0→E3→E2-M chain、意味監査、参照集合が予定どおり完了した場合だけ増やす
- protocol pilot：別manifestの15～20 problems。pilotはheadline分母へ入れない。

成功率が約90%の場合、50問の95%区間は概ね±9 percentage points、60問なら±8 points程度である。件数を増やして意味監査と参照集合の質を落とすより、連続したsource blockを完全に処理することを優先する。

headline件数はholdoutを見る前の2026-09-20に、pilotの作業量とP0の進捗だけから50または60へ固定する。pilot 15問以上をT2相当まで完了でき、応募者による原文・意味監査の中央値が30分/case以下で、E2-Mまでのartifactが完成している場合だけ60問、それ以外は50問とする。coding agentの待ち時間ではなく、応募者が意味を確認する実作業時間を測る。freeze後に参照品質を守れないcaseが出てもheadline分母から除かず、(D)または(T)へ到達しなかったものとしてfunnelに残す。

### source frame

結果を見る前に、次を固定する。source inventoryはsolver freeze前に作ってよいが、headline対象のcase IDはfinal solver tagの後に、全数採用または事前に決めた機械的抽出で確定する。

- 対象大会・年代
- 2次元幾何か
- 答えが有限個のscalarか
- 図だけで条件が与えられていないか
- 外部知識や単位変換の扱い
- 同一familyの除外規則
- reference-only、unsupportedの定義

「解けそうな問題を選ぶ」のではなく、指定した大会・年代で条件に合う全問題をinventoryへ入れる。

### DSL作成

1. development corpusでcanonical authoring manualを完成させる。
2. development実験とpilotを全て終え、final solver tagを作る。
3. その後にheadline case IDを確定し、solver resultを見ずにDSLを作る。
4. parser、type checker、scope、unused-variable等のstatic checkは許可する。
5. 原文の各clauseとDSL construction/condition/guardの対応表を作る。
6. coding agentによる原文照合を補助的に使う。
7. headline caseでsolverを事前実行して意味をdebugしない。誤って実行したcaseを事後に除外・pilot移動しない。caseを分母に残すか、prospective labelを破棄して評価全体をsecondaryへ降格する。

### reference setのauthority level

「正解」の根拠を一つのbooleanにせず、次のlevelで記録する。

| Level | 根拠 |
|---|---|
| T0 | 公式のcontest final answerのみ |
| T1 | source targetについて独立した数学的導出がある |
| T2 | 各targetについてexact expressionと、元制約を満たす配置witnessまたは独立な高精度検算がある |
| T3 | DSL semanticsが許す全target集合について、記号・区間・数学的議論による網羅性certificateがある |

- primaryの参照集合は原則T2以上とし、T3でないものは「厳密に完全性を証明したtruth」ではなく**adjudicated reference set**と呼ぶ。
- 公式answerがpost-process後の単一値である場合、それだけでsource target集合を確定しない。
- AI間の一致や高精度近似だけでT3にしない。
- 確定できないcaseは`reference_unresolved`とし、件数をfunnelに残す。

### 指標

\[
Q=|D|/|U|\quad\text{（表現可能率）}
\]

\[
R=|T|/|D|\quad\text{（参照集合coverage）}
\]

\[
A=|C|/|T|\quad\text{（参照集合がある問題での集合一致率）}
\]

\[
E=|C|/|U|\quad\text{（verified end-to-end yield）}
\]

ここで、\(U\) はeligible source problems、\(D\subseteq U\) はsource-faithful executable DSL、\(T\subseteq D\) は事前にadjudicated reference setを確定した問題、\(C\subseteq T\) は出力集合が一致した問題である。未確定問題がある限り、\(E\)を「end-to-end正答率」とは呼ばない。

### one-shot規則

- solver tag、protocol、DSL、truth、manifestを先にcommitする。
- primary run後に元artifactを上書きしない。
- runtimeにはtruth、公式answer、scoring labelを渡さず、offline scorerだけが参照集合を見る。
- hash mismatch、worker未起動、machine outage等、事前定義したinfrastructure failureのみinvalid runとする。元logを保存し、該当するpaired block全体を再実行する。
- timeout、solver exception、non-finite、no_solutionはsolver outcomeなので再実行しない。
- DSL/reference/scorerの誤りを発見しても、headlineは事前版の結果を残す。
- 修正版はpost-hoc sensitivity analysisとして別表示する。
- solverを修正した場合、その評価集合は以後development扱いにする。

機構研究から、実行前に適用できるDSL診断または自動rewrite policyが完成した場合は、canonical入力をprimary、E1前に凍結した自動policyをsecondaryのpaired armとして同時に登録してよい。E1の結果を見てcaseごとに表現を選ばない。

「独立第三者監査済み」「完全にsealed」とは書かず、「solver freeze後のprospective evaluation」と表現する。

---

## 13. 実験E2：自然問題におけるDSL表現依存性

### 目的と二つのpanel

E2は、E0で先にvariantを大量展開する実験ではない。E0の失敗分析とE3の人工問題族から得た機構を自然問題へ戻す**mechanism panel（E2-M）**を主とし、表現依存性の頻度を測る小さな**representative panel（E2-R）**を分ける。

| panel | 問い | 選び方 | 主張できること |
|---|---|---|---|
| E2-M | 人工系で確認した機構が自然問題でも働くか | 機構signatureを持つ未観測問題と負の対照を意図的に選ぶ | 自然問題への移行、機構の存在、方向予測 |
| E2-R | 表現によりpass/failが割れる問題はどの程度あるか | outcome非依存の層化＋stable hash | 定義したsource frame内のrepresentation split rate |

E2-Mの高いsplit率を一般的頻度として報告しない。頻度を主張しないならE2-Rは省略または補助資料化できるが、「DSLを選べば90%を操作できるのではないか」という問いへ数量的に答えるため、16～20問の小規模panelを推奨する。精密な母集団率ではなく、明示したframe内の粗いsplit率推定と位置づける。

### 13.1 E2-M：mechanism-targeted natural transfer

E3で支持された各主要機構について、目安として次を用意する。

- E0前に確保するoutcome未観測reserve pool：目安24～30問。問題文とcanonical DSLの静的特徴だけを準備し、solverは実行しない
- 機構が生じると予測する自然問題：4～6問
- 機構が生じないと予測するmatched negative control：4～6問
- 各問題の表現：`canonical`、`predicted-improve`、`predicted-worsen`の3個
- primaryは同じfixed seedを各表現へ対応させた3 seed、最大180秒。意味監査が完了し時間が残れば、事前固定した追加2 seedをsecondaryとして実行

対象はcanonicalを含むsolver結果を一度も見ていないreserveから選ぶ。選定にはsolver outcomeではなく、sourceとcanonical DSLから計算できる静的signatureだけを使い、その規則を先に固定する。例えば変数・制約数、構成family、予測される自由度、guard構造、parameterization候補等である。target参照集合はvariant実行前に独立な解法・検算から確定し、solver出力を見てtruthを作らない。E0の失敗caseを再利用する場合は説明例に留め、確認標本には数えない。既に作成・調整したAIME 2000～2005等のcaseはrun historyを確認し、一度でもsolver outcomeを見ていればreserveではなくdevelopmentへ置く。

各表現は、結果を実行する前に全て作る。成功／失敗が反転するまで手で調整してはならない。primaryは、事前に予測した中間量とsolver outcomeの方向がcase単位で一致したかである。secondaryはpairedな成功率差、time-to-first-valid、time-to-first-solution、target-set Jaccard、failure checkpointの移動とする。

### 13.2 E2-R：representative representation panel

- 目標16～20 unique problems。contest、年代、target型、source上の条件種別で層化し、各層内をcase IDのstable hash順に採用する。層、抽出数、hash saltはcase IDを並べる前にcommitする。
- 可能ならE0と別のoutcome未観測source frameから採る。既知のdevelopment corpusから抽出する場合もselection自体はoutcome非依存にするが、結論は「このdevelopment corpus内の表現感度」に限定する。
- canonicalに加え、広く安全に適用できる事前固定の3変換程度を用いる。全問題へ9種類を機械的に掛ける設計にはしない。
- 3 fixed seeds、最大180秒。variant数やseed数を独立問題数へ数えない。
- primaryは、固定panel内でpass/failが割れたunique problemの割合（representation split rate）。problem単位でmacro集計し、source frameと適用可能分母を併記する。
- canonical成功問題だけに限定しない。canonical失敗→variant成功も、canonical成功→variant失敗も同じsplitとして記録する。
- 一部variantが適用不能でも問題自体をpanelから除かず、変換ごとのeligible denominatorを示す。全variant適用可能問題だけへ事後的に絞った率はsecondaryとする。
- 手作業の複雑なparameterization variantは8～12問程度のchallenge subsetとしてsecondaryに置き、代表頻度の分母へ混ぜない。

E2-Rを頻度の根拠として使うなら、source frame、抽出、variant panelはE0 outcomeを見る前に固定する。E3後に決めてよいのは実行・本文採用の可否だけであり、抽出規則やvariantを機構結果に合わせて変更しない。

### 13.3 表現層と使い分け

| Level | 変換候補 | E2での扱い |
|---|---|---|
| L0 構文 | variable rename、独立DAG順序、condition順序 | semantic graphは不変。差が出れば通常の感度でなくrelease-blocking defectとして別調査 |
| L1 幾何 | 平行移動、回転、条件付き鏡映、有理scale | E2-R候補。exact target mapとapplicability条件がある場合だけ採用 |
| L2 方程式 | 正のresidual scaling、安全な冗長制約、whitelist済みrewrite | E2-Rまたは機構がconditioningならE2-Mに使用 |
| L3 parameterization | Cartesian/polar、free＋constraint/explicit construction、branch表現 | 主にE2-M。configuration setまたはtarget imageの同値性を個別に示す |

E2-Mでは仮説に関係する変換だけを用い、E2-Rでは広く適用できる固定変換だけを用いる。複数の機構を同時に変えるvariantは説明例には使えても、機構確認のprimaryには使わない。

### 13.4 variant作成と意味同値性

- 可能な変換は自動generatorで作り、applicability predicate、target写像、orientation/domain/guard保存条件を持たせる。
- 鏡映は有向角・arc・orientation guardを保存または正しく写像できるcaseに限定する。
- scaleはlength/area/angleごとのtarget次元とbounds/toleranceの扱いを明記する。
- 二乗、分母除去、非単射なpolar変換等は余分な解やdomain欠落を生み得るため、証明なしでsafe variantへ入れない。
- 人手variantには「configuration set同値」か「target image同値」かを区別したequivalence ledgerを付ける。
- `best-of-k`はoracle ceilingとして別表示し、ensembleならk倍予算として報告する。best-performing variantだけを主指標にしない。

### 13.5 主張境界

- E2-Mは「選定した自然問題で、機構に基づく事前予測と整合する差が出た」と記述する。全問題における発生割合へ外挿しない。
- E2-Rだけが表現依存性の頻度を扱う。ただし開発corpusから抽出した場合は、そのcorpus内の頻度に限定する。
- 意味同値性の監査と数値的挙動の不変性は別である。結果が異なること自体をsemantic mismatchの証拠にしない。
- 自然問題のpaired比較は外的妥当性の証拠であり、人工familyで隔離した因果効果と同一の強さではない。

---

## 14. 実験E3：失敗forensicsと機構の制御実験

### 14.1 failure taxonomy

1. **SEMANTIC**：DSLが原問題の条件・枝・点順を保存していない
2. **DOMAIN**：valid領域が極端に小さい、guard境界へ吸着する
3. **DISCOVERY**：正解basinに初期点が入らない
4. **CONDITIONING**：Jacobianがrank欠損または悪条件
5. **REFINEMENT**：候補はあるが高精度閉包に失敗
6. **EXACTIFICATION**：数値値はあるがdescriptorを同定・検証できない
7. **ENUMERATION**：一部のtarget branchのみ発見
8. **RESOURCE**：timeout、memory等
9. **UNKNOWN**：証拠不足で機構を確定できない

timeoutは原因ではなく観測結果なので、可能な範囲で最初の破綻checkpointへ掘り下げる。

#### 全件調査とmatched success

- verified層ではE0のstable failureとseed-sensitive caseを全件対象にする。truth未確定層でも、timeout、no-candidate、exception等の観測failure statusは全件traceし、正答・不正答やcomplete failureとは呼ばず補助的証拠にする。not executableとsemantic errorも全件理由を記録する。説明しやすいcaseだけを選ばない。
- 各失敗に、contest、年代、target型、変数・制約数、構成family等の**結果より前に決まる特徴**が近いstable successを原則1件、余力があれば2件対応させる。
- source/DSL意味不備とsolver failureを混ぜない。SEMANTICは重要な結果だが、数値探索機構の分母からは別表にする。
- trace、候補配置、hard feasibility、Jacobian、guard、refinement、exactificationをcase cardへまとめ、複数原因が考えられる場合は主因を無理に一つへ決めない。
- `UNKNOWN`を正式な分類として残す。仮説に合わないcaseを除外しない。

このforensicsはoutcomeを見て対象を選ぶ**探索的分析**である。本文で「全失敗」と呼ぶのは、上記の層別規則に従って記録した全観測failure statusを指し、truth未確定caseをsolverの誤答数へ数えない。ここで得た「失敗のうちX%は原因M」「特徴量Mが失敗を引き起こした」という数値を、確認なしで一般化しない。

### 14.2 数理的な予測量

- valid volume：明示した探索領域・parameterization・proposal distributionの下で、sampleがhard feasibilityを満たす経験的割合。固有の幾何量とは呼ばない
- branch capture mass \(p_j\)
- scaled Jacobianの最小非零特異値
- condition number
- guard margin
- root separation
- target branch数
- algebraic degree/height
- residual scale imbalance
- effective DoF

独立初期値を仮定できる探索laneでは、branch \(j\) を \(N\) startで逃す確率を

\[
P(\mathrm{miss}\ j)\approx(1-p_j)^N
\]

とモデル化する。この式を全pipelineへ無条件に適用せず、独立乱数startの部分に限定する。

正則な等式制約多様体の内部点でtargetが局所一定なら、必要条件として

\[
\nabla\tau\in\operatorname{rowspan}(DF)
\]

を用い、正次元配置集合でもtargetが有限となる構造を説明する。特異点やactive inequalityではそのまま適用しない。

変数変換 \(x=\phi(z)\) では

\[
D(F\circ\phi)=DF\,D\phi
\]

となるため、意味的に等価でもconditioningとsampling measureが変化し得る。

### 14.3 機構の選定とprotocol freeze

人工問題族を失敗観察前に4種類へ固定しない。E0と14.1のforensics後、次の条件で本文の中心機構を**原則1個**選ぶ。第二機構は第一機構について人工系から自然問題までの証拠chainが閉じ、意味監査の時間が残った場合だけ追加する。

1. 複数の自然failureで同じsignatureが観測された。
2. 対応するsuccess controlとの差を測定できる。
3. 一因子だけを連続的または段階的に操作できる。
4. 数学的に方向予測を導ける。
5. 結果を見ていない自然問題を静的signatureから選べる。
6. 診断または表現改善へつながる可能性がある。

「最もきれいな結果が出た機構」ではなく、確認実験前に上の選択理由を記録する。選定後、人工familyの式、parameter grid、common seed、primary中間量、成功判定、方向予測、除外・停止規則を1ページのprotocolへ固定してから実行する。

同時に`mechanism-study` solver tagを固定し、人工familyからE2-Mまで同じ版を用いる。途中の結果を受けたbug fixやalgorithm変更は別tag・別experiment IDとし、元artifactを残す。機構研究から考案したrewriteは同じE2-Mで「改善確認済み」とせず、E1の事前登録secondary armまたは別の未観測reserveで初評価する。

候補bank：

- tangent circle-line：単純根から接する重根へ近づける
- near-rank-deficient：scaled Jacobianの最小非零特異値を小さくする
- multiroot capture：解間距離または各branchのcapture massを変える
- strict-guard boundary：真の解と除外境界の距離を変える
- valid-volume ladder：proposal distribution下のvalid領域を変える
- scale ladder：座標または残差scaleを変える
- redundant overdetermined：zero setを保った冗長制約数を変える
- exactification ladder：代数次数、係数高、affine-π難度を変える

この一覧は選択肢であり、全てを実施する義務ではない。positive-dimensional finite-targetは問題設定を説明する好例だが、failure mechanismでなければ独立した主実験にしない。

### 14.4 人工問題族の実行

各主要機構について、目安として7～10 parameter level、各level 10 common seedsを用いる。計算量が大きい場合でも7 level×8 seeds程度は確保する。seedはlevel間で対応させ、parameter以外の生成規則、solver、予算、verifierを固定する。

成功率だけでなく、仮説が予測する中間量を先に評価する。例えばvalid-volume仮説なら、

\[
\text{parameter}\rightarrow\text{valid proposal率}\rightarrow\text{time-to-first-valid}\rightarrow\text{target回収率}
\]

を同じ図で示す。これにより、単なる難易度調整ではなく、提案した機構を通じて結果が変化したかを判断する。

### 14.5 分析と自然問題への接続

- forensics：仮説生成。因果や一般頻度を主張しない。
- 人工問題族：一因子介入による、そのfamily内での因果的証拠。
- E2-M自然問題：関連、方向予測、外的妥当性。人工系と同じ強さの因果とは断定しない。
- E2-R：定義したsource frameにおける表現依存性の頻度。機構別の頻度とは限らない。
- 主証拠は人工familyの一因子phase diagramと、E2-Mにおける事前方向予測の二段構成とする。
- failure eventが50以上集まった場合に限り、透明な多変量logistic modelを探索的に用いる。約10件の失敗から多数predictorを推定しない。
- conditionやroot separationが正解witnessを必要とする場合、独立referenceから測る。solverが見つけた解だけで失敗caseの説明変数を埋めない。
- 説明できない失敗を`UNKNOWN`として残す

結論は「失敗原因を完全に証明した」ではなく、次の強さに揃える。

> canonical corpusから生成した仮説Mについて、人工familyではMだけを操作したとき予測どおり中間量と成功率が変化した。さらに、Mのsignatureから事前選定した自然問題でも、意味同値なDSL変更による同方向の変化を確認した。

### 14.6 診断・改善への還元

機構の存在を示すだけで終えず、可能なら次のいずれか一つを実装する。

- 実行前に失敗riskを警告する診断指標
- 意味同値な候補表現から選択する規則
- 機構を弱める自動normalizationまたはrewrite

開発corpusとE2-Mで規則を作り、E1前に固定する。E1ではcanonicalをprimary、固定した自動介入をsecondaryとしてpaired評価できる。手作業でcaseごとに最良表現を選ぶ方法は、実用的policyの成績として扱わない。

---

## 15. 実験E4：ablation

### 目的

既存部品を並べただけという批判に対し、各設計が有限目的値回収のどの失敗を防ぐかを示す。

### 比較候補

一初期値、random multistart、low-discrepancy multistartはone-component removalではないためE5のalgorithm baselineへ移す。E4は研究史からactivationが確認できる主要3～4機構へ絞る。

**探索・精密化ablation（同じ最終verifierを使用）**

1. auto scalingまたはbounds推定なし
2. candidate diversityなし
3. rescueなし
4. rank-aware closureなし
5. 必要なら高精度refinementなし

candidate diversityとrescueを一つのpackageとして外す場合は、個別因果効果ではなくpackage効果と呼ぶ。

**安全性ablation（別endpoint）**

- exactify前の近似dedup
- strict guardなし
- full-source replayなし

安全性機構を外すと最終descriptor endpointの意味自体が変わるため、同じ最終集合一致率ではなく、数値candidate回収、false acceptance、false rejectionを評価する。

### 固定条件

- 同じfinal DSL
- primaryは同じwall budget 180秒
- secondaryは可能な範囲で同じevaluator workまたはcallback数
- wall、start数、evaluation数を同時に同一と主張しない
- 探索ablationは同じ最終verifierとreference set
- 同じseed
- case-specific tuning禁止

### 報告項目

- 参照集合一致率の差
- false acceptance差
- activation件数。各機構について「介入前のfull runで、そのcode pathが実行されたcase」と機械的に定義する
- その機構が実際に救った/落としたcase
- wall timeとevaluation overhead
- safety fixは正答数が増えなくても誤受理防止を成果とする

### optional：過去改善の2×2寄与分解

時間があれば、結果を見ていない固定subset上で旧／最終solverと旧／最終DSLを交差させる。

|  | 旧DSL | 最終DSL |
|---|---|---|
| 旧solver | A | B |
| 最終solver | C | D |

これは139→190の歴史的改善がalgorithm、DSL修復、相互作用のどこから来たかを分ける補助分析であり、E2の主線には置かない。旧DSLがsemantic bugを含む場合は同一task比較にならないため、そのcellを性能比較から除き、修正件数として別報告する。

---

## 16. 実験E5：他手法との公平比較

### 16.1 task level

| 比較level | 成功条件 |
|---|---|
| K1 | 有効な配置を一つ得る |
| K2 | 正しい数値targetを一つ得る |
| K3 | 全参照targetを余分なくdescriptorで得る |
| K4 | 解の存在とtarget集合の完全性を認証する |

異なる比較levelのsystemを一つの総合勝率で順位付けしない。

### 16.2 比較の優先順位

**必須：同一残差上のalgorithm比較**

- 一初期値SciPy least-squares
- random/low-discrepancy multistart
- frozen full GeoSolver

入力compiler、residual、guard、verifierを共有し、candidate generatorだけを変える。最も公平で、独自工夫の寄与を示しやすい。

**主比較に加える候補：既に動くhomotopyとの共通subset比較**

- HomotopyContinuation.jl：既存実装が安定している場合のみ、polynomializableかつsquare/regularなsubset
- 不等式とbranchは共通post-filterで確認

subsetは結果を見る前の静的admission ruleで決める。source→多項式系への変換・前処理時間も総時間へ含め、全eligible問題に対するcoverage、admitted subset内の条件付き成功率、総時間、保証levelを分けて報告する。homotopyが優れる小規模caseを隠さない。

**余力がある場合だけ：追加のexact/complete系**

- msolve/Singular：零次元・有理係数へ安全に変換できるsubset
- 円筒代数分解または区間branch-and-prune：ごく小さな認証可能subset

短期間に入力変換だけを大量に作る比較は行わない。これらが安定しなければ、性能表へ無理に入れず、保証・coverage・目的の概念比較に留める。

**工学的対照：computer-aided design系GCS**

- SolveSpace/libslvs等の再現可能なopen solverを候補とする。
- intended-useのwarm startと、boundsのみのcold startを分ける。
- K1の配置発見とK3の全値回収を混同しない。
- 商用CAD engineは内部条件が不明なので、主定量比較より目的差の説明に用いる。

**技術的近縁：GMBL**

- common expressible subsetでK1を比較。
- 実装互換性や再現性が確保できなければ、公開結果との概念比較に留める。

### 16.3 公平性表

各手法について必ず示す。

- sourceから入力へ変換した人手
- 初期配置の有無
- 対応可能問題数/全問題数
- 一配置か全targetか
- 数値結果か認証付きか
- CPU/GPU、core、wall time、memory
- seedとretry
- unsupportedの扱い

主本文で必須なのは「同一残差上の三baseline」と、安定して実行できた場合のhomotopy比較までである。computer-aided design系GCS、GMBL、追加CASは補助資料または概念比較で十分であり、比較数の多さを成果にしない。

---

## 17. 実験E6：LLM＋GeoSolver（副研究）

### 位置づけ

本研究の原点と社会的応用を示すが、応用数学としての主成果にしない。自然言語→DSLは現時点でほぼ未実装なので、主実験完了後に薄いagent harnessを実装する。

### 条件

| 条件 | 内容 | 分解できる要因 |
|---|---|---|
| C0 | LLM単独（外部toolなし） | model自身の数学能力 |
| C1 | LLM＋generic Python/SymPy | 一般計算toolの効果 |
| C2 | LLM＋generic Python/SymPy＋GeoSolver | 専用solverを追加する効果 |
| C3 | canonical human DSL＋GeoSolver | 正しい形式化を仮定したdiagnostic ceiling |

C0～C2だけを同一LLMのpaired comparisonとし、C3はLLM条件と混ぜて順位付けしない。全条件に同じ問題文、最終contest-answer task、答えの正規化規則を用いる。

### harness

1. C0には問題文だけ、C1には問題文とgeneric Python/SymPy環境を渡す。
2. C2だけに凍結DSL manual/catalogとGeoSolverを追加し、JSON DSLを出力させる。
3. C2ではstatic validator errorを最大1回だけ返して修正させ、人間修正なしでsolverへ渡す。
4. C3は同じ問題のcanonical human DSLを直接GeoSolverへ渡す。
5. 全条件のfinal answer、prompt、tool call、時間、tokenを保存し、C2/C3ではDSLとsolver logも保存する。

model ID、local modelならquantization、system/user prompt、temperature等のsampling設定、利用可能なら推論seed、最大token、最大roundを固定する。推論が非決定的なら最低3 trialを行い、trial単位と問題単位を混同しない。wall time、LLM token、GeoSolver/PythonのCPU timeも分けて記録する。

### dataset

- 目標30～40問。pilotは別の10～15問。
- 可能なら公開日がmodel cutoff後の問題または新規作問。
- 既知のAIME等だけを使わず、training contaminationを主要limitationにしない。
- GeoSolverのprospective headline setと分ける。

### primary/secondary metrics

primary：最終target集合一致率。

secondary：

- JSON parse率
- DSL source fidelity率
- 正しいDSLを条件としたsolver成功率
- timeout、token、wall time、tool calls
- 人手介入回数

DSL source fidelityはsolver成否を見ず、原文clause checklistだけで先に判定する。これにより「solverが正答したからDSLも正しい」とする循環を避ける。

### decision gate

- 2026-09-20までにthin harnessと10～15問pilotが安定しなければ、本文から外して補助資料または今後の課題へ移す。
- 主実験を遅らせてまで実施しない。

### 人間実験

今回は原則実施しない。少人数の友人比較は証拠として弱く、人を対象とする研究の事前承認・同意・匿名化が必要になる。行う場合は別protocolとし、本文の主張に依存させない。

---

## 18. 人間の幾何難度とsolver難度

IMO/JMO経験を問題設計とcase解釈に活かす、探索的な補助分析である。人間参加実験を行わない限り、solverと人間の能力を一般的に比較する主結果にはしない。

|  | solverには易しい | solverには難しい |
|---|---|---|
| 人間には易しい | 基本的control | 数値表現・境界・条件数の弱点 |
| 人間には難しい | solverの価値が最も見える | 両者に共通する構造的難所 |

人間難度を応募者一人の主観だけで数値化しない。次の順で使う。

1. contest problem number、公開正答率、公式難度区分等の外部proxy
2. 公開解法の主要lemma数、補助構成数等の事前定義した構造proxy
3. 応募者による専門的case interpretation

主結果は相関係数一つではなく、対照的な4～6ケースを詳しく説明する。公開proxyが得られる範囲に限定し、目的は「solverが人間より優秀」と主張することではなく、難度軸の不一致という仮説を提示することである。

---

## 19. 実験史の見せ方

364 commitsや多数のbranchを時系列に並べない。次の因果chainを示す。

> failure checkpointの発見 → 原因仮説 → 一般修正 → 反例/対照 → full replay → 採否

本文候補：

1. **rank-aware closure**：rank欠損を局所chartで処理し、最後に全source residualを再確認。対象とcontrolで回復。
2. **repeated-factor exactification**：正答数の増加はなくても誤受理防止として採用。
3. **表現不変性による棄却**：一表現で成功したsingular対策が等価な直交表現で失敗し、不採用。

補助資料候補：

- sparse Jacobianはoracle workを減らしたがend-to-end overheadで不採用
- adaptive searchのdevelopment改善がholdoutへ十分一般化しなかった例
- strict boundary、DSL修復、affine-π等のcase cards

実験記録は成功数順ではなく、研究上の問いと採否理由で並べる。

---

## 20. coding agent・生成AIの利用規約

### 20.1 積極的に使う作業

- experiment runner、manifest、variant generatorの実装
- test、static analysis、集計、可視化
- DSLと原文のclause対応check
- CAS検算のscaffold
- failure logの仮分類
- 文献探索の候補出し
- レポートの反対尋問、文章校正

### 20.2 研究者が最終責任を持つ作業

- 研究質問と仮説
- source selection規則
- DSL semanticsとtruth
- 採否基準
- 数学的証明・解釈
- 結果から何を主張できるか
- 最終文章と口頭回答

### 20.3 記録

最低限保存する。

- service/model/versionまたはmodel ID
- mode、reasoning設定、date
- 有料/無料
- promptと入力file
- 生成物と人間が修正した箇所
- 研究のどの段階で使ったか

「AIが独立第三者として正しさを保証した」とは書かない。clean contextの別agentによる確認は「情報分離した反復確認」と呼ぶ。

本文用の開示例：

> 生成AIを、実験codeのscaffold、DSL原文照合、文献候補探索、文章校正に用いた。研究質問、評価protocol、数学的判断、結果解釈、最終記述は応募者が決定し、AIの出力はtestまたは原資料との照合後に採用した。全promptと使用記録を補助資料に保存した。

この相談自体も、構成検討・文献調査補助としてAI利用台帳へ含める。

提出時は総称の「GPT」「coding agent」で済ませず、実際に使ったものを次の一表へ閉じ、レポート末尾に置く。

| service/model | version・設定 | 有料/無料 | 使用時期・箇所 | 入力と方法 | 採否確認 |
|---|---|---|---|---|---|
| ［例：Codex / model ID］ | ［reasoning等］ | ［区分］ | 計画、実験code、校正等 | prompt/file | test、原資料照合、本人判断 |

利用していないmodel名や曖昧な推測versionは記載せず、service側でversionが表示されない場合は、その旨と利用日を記録する。

---

## 21. 補助資料

本文を単独で理解可能にした上で、USB/CD-Rに次を収録する。

### A. 数学・algorithm補足

- residual定義
- hard feasibilityとguard
- bounds/scaling
- global/local search
- high-precision refinement
- rank-aware chart
- descriptorとexactification
- 保証level

### B. DSL specification

- grammar/catalog
- canonical authoring manual
- 点順、交点枝、有向角、非退化等の注意
- source clause ledger template

### C. corpus audit

- source inventory
- inclusion/exclusion理由
- dedupe/family表
- truth status
- source/DSL/truth hashes
- 問題文・公式解答の再配布条件を確認し、原則としてproblem ID、出典link、必要最小限の引用、自作図を収録する。出典全文や公式解答を無断でcorpusへ同梱しない

### D. 全結果

- case-level result table
- raw JSON/JSONL
- seed、時間、memory、checkpoint
- timeout/no_solution/mismatchを含む

### E. DSL representation atlas

- E2-M：機構ごとのcanonical／predicted-improve／predicted-worsen
- E2-R：結果非依存panelの固定variant全集
- equivalence ledgerとapplicability predicate
- E2-MとE2-Rを混ぜないheatmap
- best-of-kと実行前policy、canonicalの分離

### F. failure atlas

- E0のcanonical failure全件とseed-sensitive case
- 各failureに対応するmatched success
- checkpoint、trace、原因候補、反証候補を含むcase card
- 仮説を選んだ時点と選択理由
- `forensic証拠 → 人工family → 未観測自然case`を機構ごとにつないだ索引
- negative control、予測に反したcase、unknown cases

### G. ablation・外部比較

- admission criteria
- conversion effort
- 全表と統計

### H. experiment cards

- 代表8～12件
- negative results
- 採用/棄却理由
- discovery／confirmatory／transferのroleとprotocol commit

### I. reproduction capsule

- submission tag
- dependency lock/container
- one-command runner
- expected small smoke output
- artifact SHA-256 manifest
- README index

### J. AI use ledger

- model/service/date
- prompt archive
- outputと修正記録
- 用途一覧

### K. 解説動画

2～3分程度を自主目安とする。

1. 問題
2. DSL
3. residual landscapeの2次元slice
4. multiple starts
5. local descent
6. high-precision replay
7. descriptor candidate
8. boundary failure例

字幕を付け、「2次元sliceであり高次元地形全体ではない」「動画は完全性証明ではない」と明記する。重要な数値は本文にも掲載する。

---

## 22. 実施優先順位

### P0：受賞可能性の中核

1. 中心命題とclaim boundaryの固定
2. submission runtimeの再現性
3. E0：大規模canonical censusと全失敗forensics
4. E3：主要1機構の理論と一因子人工実験。第二機構はstretch goal
5. E2-M：未観測自然問題のpaired DSL＋負の対照
6. E2-R：16～20問の事前抽出panel。表現依存性の頻度を本文で述べる場合だけ実行
7. E1：最終solverの新規評価集合

### P1：強い補強

8. 機構に基づく診断または自動rewrite一つ
9. 主要ablation E4
10. 同一残差baseline＋可能ならhomotopyのcommon-subset比較E5
11. 実験史case cards
12. reproduction capsule

### P2：余力があれば

13. LLM＋GeoSolver E6
14. 限定subsetの数学的certificate
15. GCS engineのwarm/cold比較
16. 解説動画

### 原則行わない

- 少人数の非正式な人間実験
- 全experiment branchの網羅的時系列説明
- 多数の外部solverを浅く比較すること
- 逆運動学等、未検証の応用を本文中心へ広げること

coding agentで実装量を増やせても、問題選定、truth、意味監査、結果解釈がbottleneckである。比較数や人工family数を増やすより、E0からE2-Mまでの証拠chainをまず一機構について閉じる。

P0の標準規模は次を既定値とする。

| 段階 | 標準規模 | 180秒全timeout時の概算CPU時間 |
|---|---:|---:|
| E0 | 実行可能約285問×3 seed | 約43時間 |
| E3 | 1機構×8 level×10 seed | 約4時間 |
| E2-M | 正例5＋負例5、3表現×3 seed | 約4.5時間 |
| E2-R | 18問×4表現×3 seed | 約11時間 |
| E1 | 50問×5 seed | 約12.5時間 |

合計は約75 CPU時間であり、core並列化できる。実際のbottleneckはrun時間より、E0の意味監査、E2-Mの30表現の同値性、E1の50 reference setである。第二機構、追加seed、60問E1は、これらの品質を落とさず標準規模が閉じた後だけ行う。

---

## 23. 日程

### 8月29日～9月3日

- この計画の確定
- main claim、RQ、用語、exactness/completeness規約を暫定固定
- canonical DSL manual v1
- manifest roleを`canonical_discovery`、`forensic`、`synthetic_confirmatory`、`natural_transfer_reserve`、`representative_E2`、`prospective_E1`へ分ける
- E0のsource inventoryとdedupeを確定する
- outcome未観測のnatural poolについて、E2-Rのsource frame・層・16～20 case・hash salt・固定variantを先に確保し、残りをE2-M reserveとする。E1は別source frameへ置く
- E1のsource frameと機械的抽出規則だけを決定する。headline case IDはまだ確定しない
- submission runtimeの技術blocker一覧
- 本文の安定部分を書き始める
- 8月31日以降、応募formは早めに登録し、ID/PASSを保管する

### 9月4日～12日

- 9月4～6日：current runtimeのintegrity/budget/reproduction修正、E0 canonical full run開始
- 9月7～9日：E0のprimary＋robustness run、checkpoint集計、全stable failure／seed-sensitive caseの確定
- 9月9～11日：全failureのforensicsとmatched success比較。`UNKNOWN`を含むcase cardを作る
- 9月11～12日：本文で扱う中心機構を一つ選び、人工familyの式、parameter grid、方向予測、endpointをprotocolへ固定する
- 9月12日：`mechanism-study-YYYYMMDD` solver tagを固定する。E3人工family、E2-M、実行する場合のE2-Rは原則として同一tagを使う
- 並行して、headlineと別manifestのE1 pilot 15～20問でDSL/reference workflowだけを確認する。E1 pilotを機構確認の証拠へ再利用しない
- E4候補のactivation確認は自動集計だけ進め、P0を遅らせない

### 9月13日～20日

- 9月13～16日：E3の中心人工familyを実行し、一因子phase diagramと中間量を解析する。第二機構はこのchainが閉じた場合だけ追加する
- 9月16日：支持された機構ごとにE2-Mの静的selection rule、正例、負の対照、3表現、方向予測を固定する
- 9月17～19日：canonical outcomeを含め未観測の自然問題で、同じ`mechanism-study` tagによりE2-Mを実行する。反転するまでの手修正は禁止する
- 9月20日：9月3日までに抽出・variant固定したE2-Rを実行するか、頻度主張とともに削る。E2-M結果を見てpanelやvariantを変更しない
- 支持された機構から診断・自動rewriteを作る場合、この期間中に設計してE1前に固定する。同じE2-Mで改善効果を再評価せず、E1の事前登録secondary armまたは別の未観測reserveで初評価する
- mechanism-study中にruntime bugが見つかっても元tagのartifactを残す。修正版は新experiment IDとし、E3からE2-Mまでを同じ新tagで繰り返さない限り、主張は旧tagへ限定する
- 必要ならE0 development replay
- 本文「問題提起」「方法」draft
- E6はこの時点でgo/no-goを決める
- 9月20日にpilot作業量とP0の完成状況だけからE1 headline件数を50/60のいずれかへ固定

### 9月21日

- E0～E3～E2で得た一般改良を反映したfinal solver、canonical DSL manual、自動rewriteを使う場合はそのpolicy、source-frame protocolをfreeze/tag。`mechanism-study` tagと異なる場合は、機構証拠がどの版に対するものか明記する
- primary seedと追加4 seedを機械的に確定し、閲覧前にmanifestへ記録

### 9月22日～10月2日

- 凍結済み抽出規則でE1 headline case IDを初めて確定
- 50問、条件を満たしたstretch時のみ60問について、solverを実行せずcanonical DSLを作成
- source clause ledgerとadjudicated reference setを作成
- static validatorだけを実行し、case/DSL/reference manifestをcommit

### 10月3日～5日

- E1 primary one-shot run
- 事前固定した追加4 seedも、途中結果を見て打ち切らず同じworkflowで実行
- raw artifactを上書きせずSHA-256 manifestへ保存

### 10月6日～10日

- 統計解析
- E1のfailure checkpointはpost-hoc補助分析として確定し、E0/E3で作った機構の確認標本へ混ぜない
- 同一残差baselineと、安定していればhomotopy common-subset比較
- 発見→仮説→人工介入→自然問題への移行を示す図1～5の作成

### 10月11日～16日

- 6,700～7,200字の本文draft
- 補助資料A～J
- 可能なら非専門家に論理線だけを確認してもらう
- 指導教員に数学的主張と分野適合を確認してもらう

### 10月17日～19日

- adversarial oral review
- 余力があれば動画
- AI利用開示とprompt archive完成
- reproduction capsule fresh test
- 最終PDF render確認
- 図、caption、引用、字数、30 MB制限
- PDFと紙版の一致確認
- カラー両面印刷

### 10月20日～21日

- MyPageへ最終PDFをupload
- 同じ版と出品票を追跡可能な方法で郵送
- 送付先、整理番号・学校名のfile名、到着予定を確認

### 10月27日

- 情報・技術／応用数学の必着期限。ここを作業日・発送日にしない。

---

## 24. claim dictionary

| 避ける | 推奨 |
|---|---|
| 90%の幾何問題を解いた | 開発に用いた202独立問題中187問で参照target集合と一致した |
| 全解を厳密に発見した | 根拠levelを記録したadjudicated reference setと出力descriptor集合が一致した |
| solverが解なしと証明した | 制限時間内に答え候補を発見できなかった |
| PSLQで厳密解を証明した | 代数的descriptor候補を同定し、高精度整合性を確認した |
| DSLが同じ意味であることを証明した | 原文clause ledgerと定めた変換規則により意味同値性を監査した |
| 世界初の求値幾何solver | 調査した公開文献の範囲で、列挙した要件を同時に満たす公開systemを確認できなかった |
| Gröbner基底は非現実的 | 一般保証には厳しい最悪計算量があり、本corpusの共通subsetで実測比較した |
| 拘束graphは汎用性がない | 構造分解に強いが、本研究とは目的と適用条件が異なる |
| 幾何的難しさと無関係に解ける | 公開難度proxyとの比較では、人間の難度軸とsolverの難度軸が一致しない可能性がある |
| AIが第三者監査した | AIによる情報分離した反復確認を、人間が原資料と照合した |
| 失敗例を分析して原因Mを証明した | failure forensicsから原因仮説Mを生成した |
| 人工問題で成功率が下がったので自然問題の失敗原因もMである | 人工family内ではMの因果的効果を確認し、自然問題では事前方向予測との整合性を調べた |
| targeted E2の75%で表現差が出た | 機構signatureから事前選定した対象のうちX/Y問で予測方向の差が出た。一般頻度は代表E2で別に測った |
| DSL表現差が一般に頻繁に起きる | 結果非依存に選んだ代表panelのX/Y問でpass/failが分かれた。母集団と区間を併記する |

---

## 25. 口頭審査の想定質問

1. GMBLと何が違うのか。
2. GeoGebra Discoveryは既に求値問題を解いているのではないか。
3. なぜ「厳密」と言えるのか。PSLQの偶然一致ではないか。
4. completenessがunknownなのに「全target一致」をどう評価したのか。
5. DSLを書き換えれば成功率を操作できるのではないか。
6. IMO金メダリストが良い表現を書いた能力を測っているだけではないか。
7. 既存202問へ過適合していないか。
8. 91件のtruth未確定を分母から外すのは有利な選別ではないか。
9. 139から190への改善のうち、algorithmの寄与はどれだけか。
10. GCS engine、Homotopy、Gröbnerとの比較は同じtaskなのか。
11. 180秒、1 coreを選んだ理由は何か。
12. seedを変えると結果はどうなるか。
13. failure theoryは相関か因果か。
14. 失敗を見てから仮説を作ったのなら、都合のよい事後説明ではないか。
15. 機構が起きそうな問題を選んだE2から、一般的な頻度を主張していないか。
16. 人間に難しい問題とsolverに難しい問題はどう違うか。
17. LLM＋solverは既存のneuro-symbolic systemと何が違うか。
18. 研究者本人とcoding agentがそれぞれ何を行ったか。
19. 第三者が同じ結果を再現できるか。
20. 次に一つだけ改良するなら何か。

各問いについて、30秒版、2分版、証拠を示す図表を用意する。

---

## 26. 最終判定gate

### Gate A：研究の問い

- 「何を作ったか」ではなく「何を明らかにしたか」を一文で言えるか。
- finite target imageとrepresentation dependenceが一本につながっているか。

### Gate B：評価

- 開発集合と新規評価集合を分けたか。
- unsupported、truth未確定、失敗を消していないか。
- unique problemを分母にしたか。
- raw artifactから表を再生成できるか。

### Gate C：因果性

- 各独自工夫に対照があるか。
- DSL表現差を一因子ずつ操作したか。
- failure forensicsを仮説生成、人工問題族を確認として明示したか。
- 仮説生成に使ったcaseを未観測の確認caseとして再利用していないか。
- 自然問題をvariant outcomeではなく静的signatureから選び、負の対照を置いたか。
- 自然問題の相関を人工問題の因果実験と混同していないか。
- targeted panelの機構存在とrepresentative panelの発生頻度を混同していないか。

### Gate D：過大主張

- exactness、certification、completenessを区別したか。
- 「世界初」「すべて」「厳密」を限定なしで使っていないか。
- current tagと過去runtimeの結果を混ぜていないか。

### Gate E：読みやすさ

- 最初の1ページで問いと驚きが伝わるか。
- 各図が一つの主張だけを表すか。
- algorithm名の羅列になっていないか。
- 専門外の読者が動画なしで結論を理解できるか。

### Gate F：本人性

- coding agentの利用を正確に開示したか。
- 全ての数式、比較条件、失敗例を応募者が説明できるか。
- 採用しなかった主要案を説明できるか。

---

## 27. この計画の最終的な勝ち筋

この研究を「優秀なsolverの開発」で終わらせない。

> 大規模なcanonical corpusで観測した失敗を全件分類し、そこから選んだ主要機構について、一因子の人工問題族では因果的証拠を、静的特徴から事前選定した自然問題では方向予測と整合する証拠を得た。さらに、結果非依存の代表panelで表現依存性を別途調べ、最終的な新規問題集合でsolverの経験的適用範囲を測定した。

これはE0・E3・E2-M・必要ならE2-R・E1が計画どおり成立した場合の最終文である。「保証境界を明示した」「失敗を説明した」と広く言い切らず、実際に確認できた機構名、対象範囲、証拠の強さへ置き換える。未実施または再現しなかった部分は、結果に合わせて削る。

この結論を、

1. 数学的定式化
2. 動くsolver
3. canonical corpusでの現象発見と全失敗分析
4. 人工問題族での一因子介入
5. 未観測自然問題でのpaired DSLと負の対照
6. 表現依存性の頻度と未知問題性能を分けた評価
7. 完了した場合のみ、機構に基づく自動改善またはLLM利用という具体的応用

で支える。

最も重要な成果候補は92%という数字そのものではなく、**「意味同値な記述が、どの機構を通じて有限時間の探索可能性を変えるか」を、発見・介入・自然問題への移行によって検証したこと**である。未観測自然問題で事前方向予測が十分再現した場合に限り「予測可能な研究対象にした」と述べる。再現が限定的なら「どこまで予測できるかを調べ、適用限界を示した」とする。診断または自動rewriteまで未観測問題で成立すれば、「説明」から「制御」へ進んだ点を最終的な価値に置く。

---

## 参考文献・資料候補

### 日本学生科学賞

- 読売新聞社「第70回日本学生科学賞 応募要項」2026。
- 読売新聞社「研究レポートについて」2026。
- 読売新聞社「研究作品のまとめ方」。
- 読売新聞社「生成AIの使用について」2026。

### 競技幾何・AI

- Trieu H. Trinh et al., “Solving Olympiad Geometry without Human Demonstrations,” *Nature*, 2024.
- Ryan Krueger, Jesse M. Han, Daniel Selsam, “Automatically Building Diagrams for Olympiad Geometry Problems,” CADE 28, 2021.
- Amela Hota, Zoltán Kovács, Alexander Vujic, “Solving Some Geometry Problems of the Náboj 2023 Contest with Automated Deduction in GeoGebra Discovery,” EPTCS 398, 2024.
- Chi Zhang et al., “Proposing and Solving Olympiad Geometry with Guided Tree Search,” *Nature Machine Intelligence*, 2026.
- Minfeng Zhu et al., “GenesisGeo: Technical Report,” arXiv:2509.21896, 2025.

### 幾何拘束解法（GCS）

- Qiang Zou et al., “A Review on Geometric Constraint Solving,” arXiv:2202.13795, 2022.
- Jian-Xin Ge, Shang-Ching Chou, Xiao-Shan Gao, “Geometric Constraint Satisfaction Using Optimization Methods,” *Computer-Aided Design*, 1999.
- William Bouma et al., “Geometric Constraint Solver,” *Computer-Aided Design*, 1995.

### 代数・数値解法

- Fabrice Rouillier, “Solving Zero-Dimensional Systems Through the Rational Univariate Representation,” 1999.
- George E. Collins, “Quantifier Elimination for Real Closed Fields by Cylindrical Algebraic Decomposition,” 1975.
- Alexander Morgan, Andrew Sommese, “Computing All Solutions to Polynomial Systems Using Homotopy Continuation,” 1987.
- Andrew J. Sommese, Charles W. Wampler, *The Numerical Solution of Systems of Polynomials Arising in Engineering and Science*, 2005.
- Luc Jaulin et al., *Applied Interval Analysis*, 2001.
- Jonathan Hauenstein, Frank Sottile, “Algorithm 921: alphaCertified,” *ACM TOMS*, 2012.
- Helaman Ferguson, David Bailey, Steve Arno, “Analysis of PSLQ, an Integer Relation Finding Algorithm,” *Mathematics of Computation*, 1999.
- Charles Audet, J. E. Dennis, “Mesh Adaptive Direct Search Algorithms for Constrained Optimization,” *SIAM Journal on Optimization*, 2006.

最終レポートでは、実際に参照した一次文献だけを残し、URL、DOI、閲覧日、引用箇所を統一形式にする。
