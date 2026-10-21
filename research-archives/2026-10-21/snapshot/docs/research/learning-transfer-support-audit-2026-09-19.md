# 支持確認の監査と次の判断
> 注記（2026-09-20のrepo整理）: 本文書が参照する `benchmarks/learning_transfer*`・`benchmarks/solver_analysis`・`JSSA_2026_REPORT_AND_EXPERIMENT_PLAN.md` 等は削除済み。当時の記録として保持しており、実体はgit履歴または`experiment`ブランチを参照。

2026-09-19。Devinの「support insufficient」報告に対する保存成果物とコードの監査。新しいモデル生成、judge呼び出し、GPU処理、学習は行っていない。元の実験コード・結果・報告は変更していない。

## 判断

現プロトコルのA/V/G本学習を停止した判断は維持する。ただし、結果は「この4形状・2種類のプロンプト・計32生成では、正答かつ妥当な幾何的解法への追加報酬の支持を確認できなかった」と限定する。学習自体を実施していないため、「小規模reward実験には科学的意味がない」「Qwen3-4Bには強化対象が存在しない」は結論にできない。

現在の判定値では全件でCVG=0なので、観測した回答に対するR_GとR_Vは等しい。これはGの増分効果を現条件で調べにくい証拠であって、Aの数値正答報酬の学習可能性を否定する証拠ではない。私が設定した支持ゲートも、限られた予算でG比較に進むための運用上の判断基準であり、不可能性の検定ではない。

次は監査上の不備を直して今回を閉じ、別プロトコルでB（未学習）対A（R=C）の小規模パイロットに戻すことを勧める。幾何的手法を追加報酬で増やす仮説は保留する。一般的な幾何カリキュラム、教師解答によるSFT、途中の幾何推論への部分報酬はそれぞれ別の介入であり、今回の継続として混ぜない。

## 保存データから再確認した数値

| stage | 生成 | C=1 | judge判定済み | V=1 | V=0 | G>0 | Cが異なる回答を含む群 |
|---|---:|---:|---:|---:|---:|---:|---:|
| stage1 | 16 | 7 | 7 | 6 | 1 | 0 | 3/4 |
| stage2 | 16 | 5 | 5 | 5 | 0 | 0 | 3/4 |

各stageはEOS 15件、打切り1件。残り20件のC=0回答は規定に従いV/Gが未採点である。「32件すべてanalytic」という手法判定はしていない。引用された報告のstage1「9件」は保存データと一致しない。

[support_check.json](/home/kabatan/work/solver/benchmarks/local-evaluation/learning-transfer-rl-20260919/support_check.json)と各slotの生成テキストを照合し、固定パーサをprompt_open_thinking=Falseで再実行した。32件すべてで保存されたparse/Cと一致した。これは修正後の採点の再現性確認であり、修正前の不具合を新規生成で埋め合わせる必要はない。

「合成幾何を一度も試みなかった」という記述も削除する。[stage2-dev2/slot_1.json](/home/kabatan/work/solver/benchmarks/local-evaluation/learning-transfer-rl-20260919/support/stage2-dev2/slot_1.json)の生成過程には、AA′が直径であることから直角を使おうとする検討がある。これは成功した合成解法の証拠ではないが、「試み自体がない」とは区別すべきである。報酬対象は最終解答であり、生成過程への言及だけでGを正に変更してはならない。

## 校正・実装に残る問題

### 1. 不変性テストが元の解答を送っていない

[calibrate.py](/home/kabatan/work/solver/benchmarks/learning_transfer_rl/calibrate.py:130)のbase_rowsは、変更後itemのidだけをpair_ofに置換している。problem/solutionは変更後のままになる。

保存されたjudge_cacheのsolution_sha256でも、12/12ペアで「元の解答」として送信した内容が変更後の解答と同一で、実際の元解答とは異なることを確認した。現在のunchangedは表現変更への不変性の根拠にならない。CALIBRATIONをidで引き、元itemと変換itemを比較する必要がある。

### 2. 再採点一致率とgoldとの一致率が混同されている

[calibrate.py](/home/kabatan/work/solver/benchmarks/learning_transfer_rl/calibrate.py:151)のrecheckは、先のjudge出力との一致ではなくgoldとの一致を集計する。

同じrubric_sha256とsolution_sha256の初回・再採点キャッシュを比較すると、validityは7/8、methodは8/8一致。cal-15では初回valid、再採点invalidであり、規定のvalidity 8/8再現は満たしていない。異なるrubric版の初回記録はこの比較に混ぜていない。

### 3. 保存済みgoldと現行goldが異なる

保存されたholdout2.jsonではvalid_accept_method_match=9/12で、基準10/12を下回る。その後の現行build_items.pyではh2-v06/v07/v08のgold_methodが変更され、現在のgate_report()は再計算により12/12・pass=Trueになる。recheckも保存値6/8から現行goldによる8/8に変わる。

したがって「現在の関数がfailを返す」とは言えない。一方、[gold_review_sheet.json](/home/kabatan/work/solver/benchmarks/local-evaluation/learning-transfer-rl-20260919/judge_calibration/gold_review_sheet.json)はstatus=pendingである。gold訂正自体は正当であり得るが、変更前後・数学的理由・確認者・時刻を明示し、結果を見ていない検証と区別する必要がある。これに上記2件も重なるため、校正完了とは扱えない。

### 4. 12文字アンカーは引用全体の裏付けにならない

[judge_client.py](/home/kabatan/work/solver/benchmarks/learning_transfer_rl/judge_client.py:54)のquote_in_solutionは、引用の一部が12文字一致すると、残りが生成物に存在しなくても受理する。CPUで次を確認した。

```python
quote_in_solution(
    "The circles have equal radii. Therefore all triangles are equilateral.",
    "The circles have equal radii. No further conclusion follows.",
)
# True（存在しない結論を含む引用が通る）

quote_in_solution("a+b/c", r"\frac{a+b}{c}")
# True（括弧を失い、意味が異なる数式も一致する）
```

省略を許す場合も、各断片全体が順序通りに存在する必要がある。数式の意味を変える正規化はしない。必要ならjudgeに短い原文引用と位置情報を返させる。保存されたsupportの69引用中3件は断片全体の正規化一致では通らず、アンカー処理に依存していた。これはその3件の数学判定が誤りという意味ではない。該当3件を原文で確認し、引用修正と数学判定を別々に扱う。

対象はsupport-stage1-dev0-s1、support-stage2-dev1-s3、support-stage2-dev3-s3。

### 5. 学習用log-prob計算の本体がCPUで失敗する

[grpo.py](/home/kabatan/work/solver/benchmarks/learning_transfer_rl/grpo.py:159)の_chunked_lm_head_logpsは、logitsが[1,T,V]、target_idsが[T]のとき、gatherに渡すindexが[T,1]となり次元数が一致しない。

実際の関数をCPUのLinear(4,7)、hidden=[1,3,4]、target_ids=[1,2,3]で呼び、次を再現した。モデル重みのロードやGPU使用はしていない。

```text
RuntimeError: Index tensor must have the same number of dimensions as input tensor
```

CPUテスト14件通過は、この経路の動作確認を代替しない。本体を呼ぶ小さな前向き・逆向き比較を追加し、修正後に既定の短いGPU技術試験で確認する。今回、学習に進まなかったため学習結果の汚染は起きていない。

## 次の実験の境界

1. 今回の記録はsupport不足による停止として保持する。報告件数・結論・校正状態を訂正し、元のキャッシュ・gold・結果を追跡可能に残す。
2. 実装のCPU修正・検証を先に行う。judgeの修理はG/Vの再開やその判定の確定に必要だが、Aのオンライン報酬にはjudgeを使わない。
3. 新しいrun IDと事前固定したプロトコルで、ヒントなしのB対Aを計画する。元の未使用train 16形状×4回答、最大16更新の範囲とする。支持確認の32回答はオフライン学習に再利用しない。1〜3群の技術試験は別のdevデータで実施する。
4. 未使用の固定評価をB/A双方で行う。各状態の数値32回答・Sなし証明8回答・Sあり診断4回答という既存枠を維持し、Sの教師解答やjudgeコメントをpolicyへ与えない。評価を見て打切り・課題選択・ハイパーパラメータ変更をしない。
5. これは1 seedの探索的パイロットである。数値正答率・実際の更新数・証明の正当性・補助点の合法な使用を分けて報告する。変化があれば、無関係課題対照や反復で追試する。数値正答の改善だけを幾何的思考や証明転移の改善とは呼ばない。

このメモは次の実行方針の提案であり、新しい学習を開始した記録ではない。

## Devinへの返答案

> プロトコルどおり本学習を止めた判断は了解しました。ただし、科学的結論と校正完了の扱いを修正してください。今回確認できたのは、指定した32生成において、正答かつ妥当な幾何的最終解答によるGの増分信号が観測されなかったことです。「小規模reward実験は科学的に無意味」「合成幾何を一度も試みない」「強化対象が存在しない」という一般化はできません。
>
> まず元の成果物を追跡可能に保持して監査を完了してください。stage1はC=1が7件、V=1が6件、V=0が1件です。stage2はC=1/V=1が5件です。不変性テストは変換後の解答を両側に送っており、recheckは初回出力との一致でなくgold一致を測っています。同一rubric・同一solutionの初回と再採点のvalidity一致は7/8です。gold変更の履歴・理由・人間確認状態も報告してください。12文字アンカーによる引用全体の受理と、括弧を失う分数正規化を修正し、影響した既存判定を区別してください。GPUでの追加生成は不要です。
>
> また、grpo.pyの_chunked_lm_head_logpsはCPUの小さな本体呼び出しでもgatherの次元不一致で失敗します。実装本体の前向き・逆向きテストを含めて修正してください。14件のテスト通過を学習経路の動作確認済みとは扱わないでください。
>
> 今回のA/V/G実験を成功扱いで再開することは求めません。次の候補として、新しいプロトコルでヒントなしのB対A（数値正答報酬のみ）、16形状×4回答・最大16更新のパイロットを準備してください。支持確認では各stageの4群中3群にCのばらつきがあり、こちらの学習可能性は未検証です。既定の技術試験と固定評価、生成・更新の再開契約は維持します。G/V、教師証明、追加seed、追加epochは混ぜないでください。まず監査訂正と修正検証、次プロトコルの具体案を返してください。旧focus analysisの要否確認だけで研究全体を終了しないでください。
