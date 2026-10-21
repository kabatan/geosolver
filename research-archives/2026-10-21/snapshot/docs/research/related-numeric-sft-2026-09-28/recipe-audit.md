# 数値SFTレシピ監査

2026-09-28。過去の数値SFT陽性例、9/28のAP01 pilot、今回凍結済みの10構図データと設定を読み取り専用で照合した。GPU処理は実行していない。この文書以外のファイルは変更していない。

## 判断

今回の設定は、LoRA、optimizer、学習率、累積勾配、更新数、モデルrevisionについて、過去の数値SFTとAP01 pilotに揃っている。再現性のある差は教師データの大きさ・prompt・答えの精度・各例の反復数である。今回の `.17g` 数値のみpromptは過去の陽性例へ戻している。80例を128更新する場合の提示回数は512、平均6.4回/例で、過去の56例を128更新した9.14回/例より少ない。両seedの結果を別々に報告し、学習成立が見えなければ、最初に凍結protocolの指定どおり教師と**完全に同じnumeric-only prompt**で習得診断する。

## 過去の陽性レシピ

[初回設定](../program-self-training-2026-09-26/config-numeric.json)は32更新で、[継続設定](../program-self-training-followup-2026-09-26/config-numeric128.json)が保存済み32更新から128更新まで延長する。実データはruntimeの `qwen/.runtime/program_self_training_20260926/selection/train-numeric.json`（56行、SHA-256 `75997401673246bca334de4e173c0e7553cdc3c56d486952463873ae7c99eba2`）。7構図（H01, H04, H07, H13, H15, DA01, DA05）各8例で、各行は1つの英語user promptと説明なしの小数targetから成る。promptは “Give only the requested numerical value, with at least 10 significant digits when appropriate. Do not give a proof or explanation.” と指示し、入力数値とtargetは17桁精度で記録されている。

固定学習設定はQwen3.5-9B revision `c202236235762e1c871ad0ccb60c8ee5ba337b9a`、BF16、LoRA r=8 / alpha=16 / dropout=0、10個のattention・linear-attention・MLP projection、AdamW learning rate `5e-6` / weight decay 0、gradient accumulation 4、gradient clip 1.0、non-thinking、全語彙のassistant-target cross entropyである。学習可能なのはLoRA parameterのみ。対象はassistantの数値文字列とEOSで、各例は完全にtokenizeできなければ失敗し、切り詰めない。`max_target_tokens=4096`、`max_sequence_tokens=8192`、CE token chunk 64。

32更新＋96更新の継続で、旧runtime receiptは全体128更新を記録する。更新ごとに4例、全512例提示であり、optimizer step min/maxも128。56例の各行は約9回、残りが10回提示された。旧転移評価はbase 11/24に対し数値SFT 16/24（32k時点では12/24対14/24）。単一学習seedの探索的陽性である。構図別の既存採点を今回残す8構図に絞ると、H02, H03, H08, H12, DA15, DB01, DB08, DB16でbase 6/16、数値SFT 9/16。今回trainへ含まれるDA03, DA06, DA07, DA11の8評価jobは除く。

旧評価は訓練と同じnumeric-only promptではなく、英語の導出と `Answer: <exact numerical expression>` を要求した。最終採点は最後の明示Answer行またはboxed式だけを読み、回答中の別の数値を拾わない。[旧prompt・生成設定・回答抽出](../transfer-reanalysis-2026-09-26/FOLLOWUP_REPORT.md)を維持する評価と、教師promptに合わせる数値診断は別に扱う。

## AP01 pilotとの差

AP01 pilotは同じQwen revision・128実更新・LoRA/optimizer設定を使ったが、64個のAP01三角形×4距離query、計256例を学習した。promptにはAP01前提と整数辺を含め、targetは小数6桁に丸めた値。512提示は256例をちょうど2巡した。recipe監査に記録された差と最終数値診断は[recipe-comparison.md](../proof-numeric-pilot-2026-09-28/review/recipe-comparison.md)と[REPORT.md](../proof-numeric-pilot-2026-09-28/REPORT.md)にある。

AP01のproof評価はbase 0/8、SFT 0/8で、全回答が32k以内に自然終了した。numeric-only評価はheldout 8問でbase 4/8、SFT 0/8。初回32kでbaseの1問が上限に達したが、baseとSFT双方を共通81k条件で再生成し、最終評価ではその問も自然終了した。従ってproof失敗は打ち切りで説明されない一方、AP01数値評価の過大な基数差は共通延長で扱われた。pilotはtarget桁数、提示回数、構図数、学習seed、評価promptが同時に異なるため、この差だけで陰性の原因を一つに特定しない。

## 今回の実データと設定の照合

読み取った学習データは `qwen/.runtime/related_numeric_sft_20260928/train.json`。80行、10 source各8例、全行 `kind=numeric`、各行のfieldsは `id, source_id, kind, messages, target`。sourceはDA01, DA02, DA03, DA04, DA06, DA07, DA08, DA11, DB02, DB12。英語promptは過去の陽性例と同じnumeric-only指示で、全targetは有限な小数文字列かつ`.17g` round-tripに一致する（6桁固定ではない）。凍結receiptはteacherを「numeric only .17g; original construction oracle」と記録する。120構築図形は各種類8 train、次の2 heldout、最後の2 reserveに分けられている。固定診断20 jobは各種類から1つの学習済み例（variant-01）と1つの新形状例（variant-09）を採り、variant-10は今回のjobには含めない。AP01の目標共円性、証明、座標、解法はassistant targetに入っていない。

`train.json` SHA-256は `778b87cfce6ea7271e971f8c727a5663468b783d21e7d21199bae7ccf46e26c9`。4設定すべてがこのhashと同一model-metadata hash、model revisionを指す。seed Aは `2026092701`、seed Bは `2026092901`。各32-update設定はprior checkpointなしで開始し、各128-update設定は対応する同seedの `sft-*-train32/final` を参照する。学習率、LoRA、accumulation、clip、chunk、target/sequence上限、thinking設定も4設定で一致している。seed Aは過去の学習seedを再利用しているが、32-update設定はprior adapterを持たないため重みとoptimizerはfresh baseから始まる。

提示量は `128 × 4 = 512` 例。80例なら6 full shuffle passと32例の追加pass、平均6.4提示/例になる。これは過去の陽性設定より少なく、AP01 256例の2巡より多い。現行 `train_sft.py` の直接updates guardは16/32のみ許可する。今回の32→128段階実行は適切であり、128設定をtrainerへ直接渡さないこと。継続wrapperは固定trainer hash、32-update prior、データhash、deterministic orderを確認する。各final receiptで `status=complete`, `global_updates=128`, `optimizer_step_min=optimizer_step_max=128` を確認し、32段階の更新を足した全体stepであることを確かめる。

学習データ形式の代表行は次のとおり。全targetを `format(value, '.17g')` の小数文字列にし、assistantメッセージへ説明・式・EOS以外の補助文を混ぜない。

```json
{
  "id": "DA01-variant-01",
  "source_id": "DA01",
  "kind": "numeric",
  "messages": [{"role": "user", "content": "Solve the following numerical geometry problem. Give only the requested numerical value, with at least 10 significant digits when appropriate. Do not give a proof or explanation.\n\n... fixed English construction, givens, and query ..."}],
  "target": "8.769021875963313"
}
```

trainerのCPU preflightはこの80例を同じpinned tokenizerで完全tokenizeし、target・sequence上限超過とchat-template/EOS不整合を拒否する。未検査の例をGPU学習へ流さない。GPU runは逐次実行し、既存 `gpu_job.py` のexclusive lockと `nvidia-smi` process guardを通す。今回の `run_pipeline.py` はpreflight、32→128継続、generationを順番に呼び、同じGPU guardを使う。

## 最小比較と判定上の注意

今回凍結された `main-jobs.json` は、旧評価のうち未学習の8構図×2seed（16 job）、AP01 proofの4推論seed、易しい保持問題4問で計24 job/条件。旧8構図のpromptとanswer keyは保ち、推論seedは3条件間で共通に新規割当されている。別ファイルの `diagnostic-jobs.json` は各10構図について学習済み第1例と新しい第9例を一つずつ、計20 job/条件で含む。baseと2つのSFT seedで計44回答/条件、132回答である。易問保持4問は主要転移の一部として数えず別集計する。

AP01 proofは1つの設定に4サンプルであり、独立した4問題ではない。16のheldout numeric jobは過去の陽性レシピが別問題で示した信号の追試、AP01 proofは同じ対象配置における数値経験から証明への転移、20 diagnosticはtraining fitと同構図別形状の習得チェックである。これらを一つの成功率にまとめない。答えはgeneration jobsへ含めず、正答と導出の妥当性を分ける。

現在の評価出力上限は32,768/context40,960。いずれかのarmがlength終了したjobは同じseed/promptをbase・両SFTで81,920/context98,304へ再生成し、残る場合は全armで131,072/context147,456まで揃える。延長前の出力も残す。`finish_reason=length` を誤答に混ぜず、未完数を報告する。旧AP01 proof群は32k以内で止まったが、数値promptではbaseに長い回答があったため、今回もreceiptで確認するまでは「打ち切りなし」とは言わない。

主比較は旧数値転移と同じ英語reasoning+Answer-line promptで厳密数値式を採点する。教師promptそのものを再現したnumeric-only診断はprotocolに定めた条件で追加し、主評価を置き換えない。最後の回答を明示的に抽出し、unparsed、length、numeric incorrectを分けて集計する。小標本の多数決ではなく、seedごとの方向、数値正答、答案導出のレビューを別々に報告する。

## 再現コマンド

固定一連の実行はrepo vLLM runtimeのPythonで行う。これはCPU preparationではなく、base生成・両学習seed・評価までを進めるGPU pipelineなので、freeze hashと事前承認を確認したoperatorが一度だけ呼ぶ。

```bash
qwen/.runtime/vllm-venv/bin/python docs/research/related-numeric-sft-2026-09-28/run_pipeline.py
```

段階実行する場合は、各seedごとに32-update `train_sft.py` fresh-base jobを完了させ、その `final` を同じseedの128-update `train_continue.py` configで続ける。直接128を `train_sft.py` に渡さない。GPU commandは独立に並列起動せず、`gpu_job.py` の共有lock・process guardを通す。設定と入力hashは[32-update設定A](config-sft-a-32.json)、[128-update設定A](config-sft-a-128.json)、[32-update設定B](config-sft-b-32.json)、[128-update設定B](config-sft-b-128.json)に固定済み。

## 後日追記：診断prompt amendmentと完了済み部分の整合性

2026-09-28。元の記録を保持し、後から入った変更を追記する。main評価のseed Aで最初の回答群が出た後、診断生成が始まる前に、[DIAGNOSTIC_PROMPT_AMENDMENT.md](DIAGNOSTIC_PROMPT_AMENDMENT.md)に従って診断20件のpromptを学習時と同じnumeric-only `TRAIN_PREFIX` に揃えた。変更前の診断jobs・answer key・freezeは `qwen/.runtime/related_numeric_sft_20260928/pre-diagnostic-prompt-amendment/` に保存され、旧freezeの12 hashも照合できた。main jobs/keyと `main-freeze.json` は変更されていない。変更後の `data-freeze.json` はamendment文書、適用script、改訂診断jobsをhash固定し、全14項目のhashが監査時点で一致した。

改訂diagnostic jobsは20件で、10件の `trained_example` は実学習行とmessagesが完全一致する。10件の `new_shape` は各種類の `variant-09` heldout例で、同じnumeric-only prefixを使う。new-shape IDは訓練IDに重複しない。訓練80件は10種類×8件、英語user promptと独立したnumeric `.17g` targetから成り、全targetが有限でprovenanceと一致した。対象revision、config・dataset hash、optimizer step、adapter/optimizer継続hash、および32更新orderが128設定のprefixであることを照合した。各seedはfresh baseから32更新、同seedのcheckpointとoptimizerを読み戻す96追加更新を経て128 global optimizer stepsとなり、512提示、各学習ID6〜7回を記録した。

main jobs 24件は学習sourceと異なり、8関連数値構図×2 seed、AP01 proof×4 seed、易問×4件である。answer keyは数値/易問20件に限り、4件のAP01 proofに数値answer keyはない。どの答えもgeneration jobsには入らず、`generate_batch.py` はanswer keyを読まず、各jobに `target`/`answer_exact` がないことをassertする。main jobs/keyのhashもfreezeと一致した。

診断prompt変更により、別freezeで既に用意されていた10件のconditional exact-prompt jobsは、診断のtrained-example 10件と完全に同じmessagesになった。protocolの条件が成立した場合も、重複jobを追加せず、改訂diagnosticからその10件の結果を使う。

2026-09-28 07:56 UTCの監査snapshotではtraining integrityは整合しているが、評価は未完了であり、成績の結論は出していない。base mainとseed A mainは各24/24の初回32k生成が完了し、`finish_reason=length` はそれぞれ1件と3件。seed B mainは24件中8件まで進行中で、確認できた8件のうち1件がlength終了。base/両seedの診断は未開始、main/diagnosticのlength延長も未開始で、`generation-complete.json` と `final-cap-by-job.json` はまだない。したがって残るseed B main、全diagnostic、必要な81k/131k延長、最終採点・匿名レビューはすべて未監査とする。
