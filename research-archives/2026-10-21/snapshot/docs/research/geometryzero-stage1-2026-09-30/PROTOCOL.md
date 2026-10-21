# GeometryZero型GCPO：第一段階の固定検査

2026-09-30。対象の性質・解法を学習に与えず、現在の数値教材からRLの信号と実行時間が得られるかを検査する。転移成功や原論文の完全再現を判定する本学習ではない。汎用解法判別器・模範証明を報酬に追加しない。

## 有限の範囲

- Qwen/Qwen2.5-3B-Instruct revision aa8e72537993ba99e69dfaafa59ed015b17504d1。公式GeometryZeroコードrevision 8a7350f1ad323cbadd6ae3d4558953d2e744bf64を保存する。
- 現在の承認済み37構図・148問のv0から、H系（HXを含む）、DA系、DB系を元ファイル順に各先頭8問、計24問選ぶ。成績で選び直さない。ラベルは既存検証済みanswer_exactを使い、問題・与件と分離保存する。
- 既存の英訳を与件と照合して使う。入力は与件だけの英文geometry specification。原論文のTikZ/Geometry3k DSLをそのまま移植したものではなく、幾何表現の適用差を明記する。解法・非自明な結論を追加しない。
- 3群×各8回答。withは補助作図を要求、withoutは公式コードに従い追加作図指示のない元prompt、mainは公式コードに倣ったcoin-flip選択の作図指示。withoutを実際には存在しない厳格な禁止条件と呼ばない。新たな点・線・円の仕様を <auxiliary> 内へ書く形式に適用する。
- temperature=1、top_p=1、top_k=-1。max prompt 2048、completion1024。24問全3群を生成し、全回答のraw text・token ids・sampling logps・終了理由・時間を保存する。最初から全体を2048へ延長しない。
- 1024のmainで8回答の半数以上が打切りとなる問題を、完了・未完了で選別せず3群すべて上限2048で新規生成する。これは事前規定の長さ診断で、原1024の記録を置き換えず、長さ重みの分母900も変更しない。最終打切りを不正解扱いしない。

## 報酬と信号

- 数値報酬は、独立に実数へ評価した既存正解と、最終 <answer> 内の数式または数値を比較する。原コードのrelaxed=Trueは2%相対誤差であるため、主診断にはこの許容差を固定する。同時に従来のabs1e-4 OR rel1e-5とexact数式一致を別記録する。
- 原コードは分数ラベルの最終分母や、答案に列挙した数値をfallbackで拾える。このデータ適用では単一の最終答案だけを採り、goldの分母を正解値と誤認しない。ここは明示したparser適用差で、literal upstream挙動も可能な範囲で別診断する。
- formatは原regexに一致したとき0.5。auxは閉じた <auxiliary> タグがあるとき0.5（構成の数学的正しさを保証しない）。lengthは0.5*min(decoded responseのQwen token数/900,1)。原コードの900を使い、論文本文の1024との違いを明記する。
- maskは8回答の数値報酬平均の差をepsilon=.05で比較し、+1/−1/0。mainだけに acc+format+mask*aux+length を使う。advantageは群内平均・sample標準偏差（torch.std default correction=1）で正規化し、epsilon1e-9。原コードのsequence平均lossを使い、従来の全token共通正規化と混同しない。
- 数値だけ、数値+format、全報酬の分散・非ゼロadvantageを分ける。3群の補助作図タグ頻度、遵守、打切り率、2%とstrictの違いも記録する。打切り群のmaskを確定的な能力差と解釈しない。
- 全自然終了mixed-main群から総completion tokensが最小・最大の群を固定して技術更新を検査する。数学評定で選ばない。十分な数値mixed群がなくても、全報酬mixed群の更新可能性を数値学習信号とは区別して検査する。

## 実更新と接続

- 同じ初期baseから独立に最小・最大の1更新。full parameter training、BF16 model、CPU上のFP32 master/momentsによるAdamW offload、lr3e-7、clip1、weight decay0、beta(.9,.999)、epsilon1e-8。全completion因果文脈と全vocabularyを保持する。非reentrant checkpointとchunk化headを使う。dropout0、KL0、fresh rollout1step、PPO clip.2。
- 最初にGPUメモリ・CPU RAM・勾配有限性を確認する。AdamWの実行、非ゼロweight delta、保存tensor値一致、optimizer step状態を照合する。full weightsなのでLoRAのmappingを持ち込まない。
- actor/learner raw token logpsの差と、同じbackendでの更新前後を測る。旧の厳格max=.2 gateを黙って緩めた成功とは呼ばない。数値差が大きい場合は学習実行と方策忠実性を別報告し、本学習可否を保留する。
- 各群4回答まで最大256token固定prefixを更新前後にteacher forcingする。接続診断専用で、学習系列のtruncationではない。更新済みfull weightsをvLLMへ再読込し、同一保存prefixを比較し、同じ問題への新しいmain8回答を生成する。これは転移・改善評価ではない。

## 時間と研究上の限界

予算上限は第一段階の実験GPU実行4時間。model取得・準備・CPU監査は別に記録する。初回1024screenを優先し、延長・技術検査が入らない場合は未測定と報告する。自動的に本学習を開始しない。校正結果で数値の正解／解法への転移や研究方針を否定しない。

実測から148問1周／4周について、3群生成、mainのみの学習、保存・actor再配置、打切り再試行を分けて外挿する。1問ずつ更新する測定と、原論文train batch32のバッチ運用を区別し、バッチ速度の未測定を明示する。原論文は4H100、こちらは1RTX5090である。

数値報酬1のmain回答および選択update群を優先して数学的品質を確認する。これは非盲検の親AI診断であり、独立人間査読や報酬教師ではない。レビュー対象件数と範囲を明示し、全回答を数学採点したと主張しない。
