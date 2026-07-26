# EXP-V15-243-001 研究進行敵対的監査 Wave 5

監査cutoff: 2026-07-18T21:56:00+09:00

## 総合判定

**`GO_MINIMAL_SCIENTIFIC_REFREEZE_THEN_THREE_D0 / STOP_SECURITY_INFRA_EXPANSION / HOLD_REAL_AND_FORMAL`**

P0=0、P1=4、P2=5。

三候補のgenerated D0を決着させる方針自体は、現在もっとも速く汎用solverの改善へ進む経路である。
ただし、重複launch/OOMを防ぐために必要だった小さな安全策が、同一UIDの悪意あるprocess、`LD_PRELOAD`
によるtoken窃取、偽launcherの暗号学的排除まで拡張され、algorithm実験を止め始めている。

必要な安全核は次だけで十分である。

- rootだけがexecution tokenを持つ。
- plan-hash keyed `O_CREAT|O_EXCL` persistent leaseとno-clobber outputを使う。
- 全childをprocess-group RSS/AS/data/output/timeout/descendant cap内で動かす。
- native thread=1、launch/stop floor=24/16 GiB、generated D0は直列、HP/CASと重ねない。
- launch直前にpolicy/code/plan hash、artifact absence、memory、重複processを一度確認する。

これを越えるcandidate-private認証protocol、秘密FDの暗号学的導出、同一UID攻撃者対策、全import前の
多段closure attestationは、この研究の事故モデルに対して過剰である。以後の安全変更は止め、科学的比較に
必要な最小修正だけを入れて三D0を実行すべきである。

## 監査範囲

これはread-onlyのprocess auditである。candidate、shared runner、policy、datasetは編集せず、Python/test、
generated D0、real v15、HP/CAS、scorerを実行していない。validation/sealedの問題内容・truthは開いていない。
本監査が追加したのは本directory内のreportとpriority JSONだけである。

現在のpolicy SHA-256はWave 4から不変である。

| policy | SHA-256 |
|---|---|
| `AUTHORITY_POLICY.md` | `b6be9d59106ac46e9d14e0fd8f9d7777beaf171f66f4d3ad9ed83640b35dff38` |
| `EXECUTION_SAFETY_POLICY.md` | `1ee3089ef83b3fbc70f239b77110e0a64f78e72abd22b2a88691b46d41faa3fc` |
| `LINEAGE_PREFLIGHT_POLICY.md` | `639e9678dab6bc84030cf69ddb2e306b0aae0d6d5d995a1f4d97cf788f249193` |

cutoff時点のhostはMemAvailable約49 GiB、研究用generated/real/Julia/CAS processは0だった。一方swapは
8 GiBほぼ全量が使用済みである。cold page由来なら即時危険ではないが、並列度を上げる根拠には使えない。

## 質問への直接回答

### 1. 基盤・securityへ投資しすぎているか

**現在は投資しすぎている。** ただし全部が不要だったわけではない。

三候補のalgorithm kernelは合計1,490行であるのに対し、launcher/bootstrap/guard/aggregate/test系は
概算6,819行である。三候補はいずれもgenerated D0実行0件のまま、shared `safe_subprocess.py`とcandidate
closureが繰り返し変更され、freezeが失効している。事故後に必要だったのはprocess-group resource capと
machine-exclusive leaseであり、これらは残すべきである。悪意あるsame-UID processが自作lease/childを
起動することまで防ぐ認証protocolはsolver algorithm研究の要件ではない。

`safe_subprocess`へのbackward-compatibleな`inherit_environment=False`/`pass_fds`追加は、小さな一回限りの
安全変更として許容できる。しかしここでbytesを凍結し、candidateごとに別のsecurity frameworkを増やしては
ならない。clean environmentが必要ならrootの一つの起動contractで与えればよい。

### 2. 三候補D0は最速の経路か

**はい。** coarea、GS-Power、SRBF/RBFは互いに異なるmechanismで、既にalgorithm codeと180件の
cross-family generated panelがある。ここで第四候補を開くより、各1回のD0で三者を反証する方が速い。

ただし現在launch可能なfreezeは0件である。

- coarea planはその後のcandidate/runner/test/shared-helper編集より古い。
- RBF planもその後のrunner/test/helper編集より古い。
- GSはcorrective bytesを編集中で、final manifest/property statusがまだ無い。

三者を一度だけ再freezeし、共通auditorが一回ずつG1を確認する。過去のGOや古いplanを継承してはならない。

### 3. subagent運用は効率的か

algorithm breadthには十分使えている。現在の三者はcoareaという独自導出、GS-Powerという先行研究を
一般root探索へ移した候補、SRBF/RBFという別系統の既存研究である。これ以前にも独自selector portal、
minimum-mode、spectral、ARC等を独立agentが調べ、反例またはSTOPへ接続しており、単なるpaper列挙ではない。

cutoff時点で実働はおおむねroot、三candidate owner、security auditor、本process auditorの6名で、総数は妥当である。
非効率なのは、candidate ownerがcandidateごとに複数のsecurity/freeze auditorをspawnした点である。
現在走っている個別auditを最後にし、以後は一つのrotating auditorが三候補のpre/post auditを担当する。
不合格ownerは新classを開かずwinner改善へ移す。process adversaryは三D0完了後、またはP0/OOM/false/extra/
shared-core変更時に再実施する。

### 4. 進捗を最大化するstop/GOと次の3 action

1. **一回だけ科学的fairnessを直してfreezeする。** shared safety helperを今の一回で凍結し、coarea/GSへ
   arm総wall時間、exactly balanced arm order、全positiveをright-censorするTTFVを追加する。coareaの常時
   `control -> candidate`順と、GSのcommon-success-only TTFVは比較biasなので、この小修正だけはD0前に必要である。
   root-per-wallとp95 wallをpromotion判断へ含める。秘密認証・closure frameworkの追加はSTOPする。
2. **rootだけが三D0を直列に一回ずつ実行する。** 原則coarea → GS → RBFだが、minimal G1を先に通った候補を
   idleせず先行してよい。各child RSS 256 MiB、thread=1、HP/CASなし、launch前MemAvailable確認、result/status/
   lease absence確認を行う。candidate ownerは実行しない。
3. **各resultを独立再集計し、最大1 primary + 1 orthogonal reserveへ絞る。** false/replay/work/RNG、二family gain、
   family loss、全wall costを同じ基準で見る。落ちたlineageはparameter tuningせずSTOPし、ownerをprimaryの
   一般的correction、held-out transfer、counterexampleへ再配置する。fresh held-outとanonymous applicabilityを
   通るまでrealはHOLD、G2後も最大2 paired source-only real caseに限る。

## P1 finding

### P1-1: security infrastructureがalgorithm実験を支配し始めた

重複launch事故を閉じる`O_EXCL` leaseと、OOMを閉じるresource guardは必要である。一方、公開commitmentから
child capabilityを暗号学的に導出し、偽launcher、same-UID process、loader injectionまで防ぐことは、信頼された
local research codeの再現実験に対する必要条件ではない。これをP1として止めなければ、候補1件ごとに数千行の
bootstrap/test/closureが増え、ユーザーの「基盤10%以下・algorithm優先」要件を継続的に破る。

### P1-2: current freezeは三件とも実行authorityを持たない

cutoff時点の`safe_subprocess.py`はWave 4 hash `8bc185...`から変更され、coarea/RBF planが束縛するhelper bytesと
一致しない。両候補ではplan後にもrunner/test/cardが変更されている。GSはfinal freeze前である。したがって
古いGO、command、commitmentを使うlaunchは不正であり、現状はlaunch 0を維持する。

### P1-3: coarea/GSのD0 comparatorはwall-clock目的に対して不公平

- coareaは全180件でcontrolを先に、SVDを加えるcandidateを後に実行し、arm総wallを出さない。gateはcallback
  efficiencyだけで、追加SVD costを最終180秒solver目的へ反映しない。
- GSはcharged requestとactual evaluator callを正しく分けたが、arm総wallを出さず、TTFVを両armが成功した
  instanceだけで比較する。candidateだけ失敗した難例がTTFV統計から消える。
- RBFは6 arm-order permutation、roots/wall、p95 wall、censored TTFVを既に持ち、比較設計は三者中もっとも良い。

これはalgorithmではなく比較の最小修正で閉じる。結果を見た後にwall基準を追加してはならない。

### P1-4: search D0とformal exact成功が分離されたままである

三D0の`source-solved`はproposal/search evidenceで、`AUTHORITY_POLICY.md`のproof-bearing exact descriptorではない。
historical `131/145`もcurrent formal scoreではない。proof breadth seamは`HOLD_INFRA_BLOAT`、zero-dimensional current
bytesはsemantic P0でSTOPである。従ってD0成功を「231/243へ近づいたexact solved数」と表現してはならない。

今proof compilerを再開すると再び基盤がalgorithmを止めるため、三D0とwinner transferまではHOLDが正しい。
winnerがreal source-only transferした時点で、raw-source-bound proof routeを別scopeで閉じるか、formal 95%の
feasibility未確認を明示するmajor decisionが必要である。

## P2 finding

### P2-1: generated gainはgeneralizationでもprevalenceでもない

三panelは全てcandidate mechanismが作用するpositiveを構成している。family label/truthはscorer側に隔離され、
case heuristicは見つからなかったが、`2/3 family gain`だけでは未知v15への転移を示さない。D0後のfresh held-out
structure/leave-one-family-outとanonymous applicabilityは必須である。

### P2-2: coareaは一般的だが狭いregular/full-rank仮定を持つ

case名・図形名には依存せず、明白な偽装heuristicは無い。一方、normal-Jacobian補正は`m>=n`、regular isolated
root、identity residual-row metricの局所近似である。singular/multiple rootやrow representation変更へは転移保証が
ない。D0通過後も全v15主力にせず、anonymous full-rank applicabilityとrow sensitivityを先に測る。

### P2-3: GS-Powerの固有効果と表現不変性は限定的

`q_N=(q_1)^N`なので固有効果はantithetic pair間のrelative weightingだけであり、`mean(log1p(r_i^2))`はrow scaling/
basisに依存する。N=1 armを残し、D0後にN/sigma/stepを同panelへ合わせない。source hashはroutingではなく固定乱数key
にだけ使われており、現状のcandidate interfaceにcase分岐は見つからない。

### P2-4: RBFは比較が良い一方、negative priorとtail distortionが強い

SRBFは独立classだが、compact open-cube metricがphysical tailを圧縮し、過去のglobal coverage系は実problemで負例が
多い。DYCORSは低次元2--6では独立ablationに留め、SRBFを上回らなければ削除する。六shardのresultを一つのseedの
強い証拠として扱い、六replicationとは数えない。

### P2-5: OOMはcontainされたがswap-fullなので並列拡大は早い

現在MemAvailableは十分で研究childも0なので、256 MiB D0を一件ずつ実行するriskは低い。swapがほぼ満杯であるため、
32 threadを理由に今すぐ並列度を上げない。将来の145-case runはcase単位processを守りつつ、measured RSSと
MemAvailableを見て2→4→8と段階的に上げる。HP/CASは直列のままとする。

## terminal/HOLDの維持

| track | decision |
|---|---|
| ARC GN/full-Hessian | `STOP_TERMINAL`。同じgenerated panelのtuning/rerun禁止 |
| spectral branch explorer | `STOP_TERMINAL`。二waveでcross-family gate失敗 |
| minimum-mode saddle portal | `STOP_PREVALENCE_CURRENT_WAVE` |
| selector-trace portal | `HOLD_PREVALENCE_NO_EXECUTION` |
| mixed-precision JFNK / HP rungs | `PAUSE_APPLICABILITY_0 / STOP_AUTHORITY` |
| dependency-sliced FD | `PAUSED_PROMISING_STATIC_ONLY`。三D0後の次候補 |
| proof breadth seam | `HOLD_INFRA_BLOAT` |
| zero-dimensional current bytes | `STOP_SEMANTIC_P0` |
| strict-guard certificate join | `HOLD_INTEGRATION / REUSE_ONLY` |

新classを開かず、この表を維持する。三D0が全滅した場合の次順位は、135/144で静的適用可能性を示した
dependency-sliced FD evaluatorである。これはsolver throughputへ直接効き、case-specific geometry ruleではないが、
semantic bit-parityと実測speedupをまだ持たないため、今は実装再開しない。

## audit cadence

- 三候補のpreexec/postresultは一つのrotating auditorが担当する。
- process adversaryは三D0完了後とwinner held-out wave後に実施する。
- false/extra、OOM/descendant、duplicate launch、shared-core/policy変更時は即時臨時監査。
- full145、independent60、validation、sealedの前には必ずmajor auditを置く。

このcadenceなら、ユーザーが求めた定期的な敵対監査を維持しつつ、監査そのものがalgorithm実験を上回ることを防げる。
