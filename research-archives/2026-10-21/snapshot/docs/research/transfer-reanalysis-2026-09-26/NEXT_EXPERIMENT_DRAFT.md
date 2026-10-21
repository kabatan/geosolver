# 次の最小実験案：数値SFTの新seed再現とラベル対応対照

**次のGPU実験:** 未実行。採用用教材・configはまだ作成していない。下記のCPU検査だけを一時ファイルで実施した。

**実施済みCPU検査:** target値のsource別重複、決定的derangement、trainer/tokenizerによる32/128設定のpreflightを一時ファイルで確認した。GPUとmodel weightは使わず、一時dataset/config/receiptは削除済み。hash・値分布・token数・検査範囲は [`NEXT_EXPERIMENT_CPU_CHECK.json`](NEXT_EXPERIMENT_CPU_CHECK.json) に記録した。

## 根拠と問い

現在のextended数値評価はbase 11/24、OPD 11/24、code128 11/24、numeric128 16/24。32kではnumeric128 14/24、base 12/24。数値SFTはjob単位で6勝1敗、構図単位で5改善・1悪化。形式監査による主数値正答数の変化はない。保持問題は4/4で保たれた。導出監査では「数値正答かつvalid core」がbase 3/24、OPD 5/24、code128 6/24、numeric128 6/24で、数値SFTの境界例2件を許容すると8/24になる。これは弱い記述的な兆候だが、学習seedは各1、12構図につき数値instanceは1つ、各instanceの推論seedは2つである。したがって24 jobを24独立問題とみなせず、導出判定の境界感度も残る。完了した証明副評価はbase 5/6、追加学習の3条件は保守判定4/6（OPD・数値SFTは境界許容で5/6）。コード128の再生成は通常1/7、結果を見た後のgreedy診断でも2/7だった。現レシピでのOPD・コードSFT拡大より、数値SFTの再現確認を優先する根拠とする。詳細は [最終報告](FOLLOWUP_REPORT.md) に記録した。

次は数値のみのSFTに限り、次の二点を小さく確かめる。

1. 新しい学習seedでも、既存の数値SFTと同方向のheld-out数値結果が出るか。
2. 同じ問題と同じ周辺回答分布を保ったとき、各問題に正しく対応した数値ラベルの方が、対応を崩したラベルより役立つか。

コードSFTは13例・7構図でtargetが長く、数値SFTは56例・7構図、unique target token 1,056と短い。更新数をそろえても教師量・形式が異なるため、codeとの比較から表現学習の差を切り分ける実験にはしない。

## 二つの学習arm

| arm | 56件の入力 | 比較が示し得ること |
|---|---|---|
| `numeric_match_seed2` | 現行の凍結済み56件。各問題の数値targetを維持 | 新seedでのレシピ再現性 |
| `numeric_deranged_seed2` | 同じ56件、同じprompt/ID/source_id。target文字列だけを同じsource_id内で完全derangement | 問題とtargetの対応が必要だったか |

両armは同じ新seed（提案値 `2026092801`）、同一のQwen3.5-9B revision `c202236235762e1c871ad0ccb60c8ee5ba337b9a`、同一LoRA/optimizer/学習順序規則、128 updatesで実行する。現行レシピどおり各armをbase modelから新規開始し、各自の32-update checkpointとoptimizerだけを自armの128-update continuationに使う。旧numeric32/128 adapterからは開始しない。これで二armの初期化seedと提示順を意図的にそろえ、教師ラベル対応を主な差にする。

CPUで `source_id` と数値targetだけを数えたところ、7 sourceは各8行で、全sourceの8 target値がすべて異なった。したがって現データでは全7 source・56行を完全にvalue-derangeでき、定数target sourceの除外は不要である。固定したshuffle seed `2026092802`、source_idの昇順、Python RNGでsource内のtarget列を並べ替え、全行で元targetと異なるまで引き直す。**これは行を並べ替えるだけではなく**、IDとpromptの対応を固定したままtarget文字列を別問題に割り当てる操作である。`messages`、ID、source_id、行順、sourceごとのtarget multisetは変えない。この検査で使った正確なderangement規則とhashは隣接CPU receiptに記録した。

実trainerの `tokenize_rows` と `data_order`、凍結snapshotのtokenizerをCPUで使い、提案する学習seed `2026092801` と上記derangementで両armのpreflightを試した。unique target tokensはmatch/shuffleとも1,056で一致。一方、128-update・512提示の `planned_target_tokens` はmatch 9,655、shuffle 9,656（shuffle−match = +1）。32-update初回区間も2,414対2,413だった。512は56行の9完全cycleに8行の末尾部分cycleを加えるため、全sourceでmultisetを維持してもpromptごとのtoken長と末尾順により実露出token総数は一致しない。この1 token差（約0.01%）は変形を選び直して消さず、実receiptとmanifestに記録する。したがって実験はupdate/example-count matchedであり、厳密なtotal-token matchedとは表現しない。もし実config/dataset hashで再実行するpreflight値がここから変わったら、その値をfreezeし直すまでGPUを開始しない。

この対照は意図的に不適切な教師を与える比較である。matchがshuffleより良ければ、同じ数値分布を保った誤対応より正しい対応が役立つ証拠にはなる。一方、幾何の一般手順を獲得したこと、内部推論が改善したこと、自己生成経験の有効性、証明能力の向上は示さない。shuffle側の性能低下だけでも「正しい幾何を学んだ」とは言えない。

## CPU準備と実行手順

根拠にした実装は `program-self-training-2026-09-26/train_sft.py` と `program-self-training-followup-2026-09-26/train_continue.py`。前者は数値targetだけのassistant-only LoRA SFTで、32 updateまでを受け付ける。後者は元trainerのhashを固定し、保存済み32-update checkpointから128 updateまで延長する。現在の数値128 receiptは56例、128 global updates、512提示相当、unique target token 1,056、planned target token 9,656を記録する。現行数値32のconfig/receiptとselection receiptは読み取り専用で使う。

1. CPU準備用の新規成果物だけを作る。元のselection dataset、config、receiptは編集しない。matchは既存datasetをそのまま参照し、shuffleはderangementした複製datasetとそのhashを使う。4つの新config（各armの32/128）ではseed・dataset path/hash・prior checkpoint・出力先だけを適切に設定し、学習率 `5e-6`、grad accumulation `4`、LoRA rank/alpha `8/16`、module一覧、clip `1.0`、bf16、no-thinking等を凍結値にする。
2. system Pythonにはtorchがないため、`--cpu-check` と `--preflight` は必ず既存runtimeの `qwen/.runtime/vllm-venv/bin/python` で実行する。`CUDA_VISIBLE_DEVICES=''` とoffline環境変数を付ける。preflightはtokenizer・hash・target長・CE実装を検査し、モデル重みを読み込まない。preflightは出力dirを作成するため、GPU学習の出力先とは別の使い捨てdirを指定する。
3. 32-configのCPU preflight後、各armを `train_sft.py` で32 updateする。各32/finalが完成した後に、実checkpointをpriorにした128-configを `train_continue.py --preflight` でCPU検証し、その後に同wrapperで128 updateまで進める。128-configの `prior_checkpoint` は同armの新しい `.../32/final` を指し、seedと他の学習parameter・dataset hashは32-configと一致させる。continuationは96 updateを追加し、receipt上の累計128 updates / 512提示を検証する。
4. 4つのGPUコマンドは既存 `gpu_job.py` の排他lock・desktop PID検査・recovery library設定を通し、直列実行する。各コマンドreceiptにはconfig、dataset、trainer、metadataとprior checkpointのhashを残す。既存の32/128 config、checkpoint、optimizer、selection dataは上書きしない。

実行コマンドの形は次のとおり。`<arm>`ごとにmatch/shuffle用のconfigと新しいoutを指定し、各GPU呼び出しは同じguardで囲む。

```bash
CUDA_VISIBLE_DEVICES='' HF_HUB_OFFLINE=1 TOKENIZERS_PARALLELISM=false \
  qwen/.runtime/vllm-venv/bin/python \
  docs/research/program-self-training-2026-09-26/train_sft.py --cpu-check

CUDA_VISIBLE_DEVICES='' HF_HUB_OFFLINE=1 TOKENIZERS_PARALLELISM=false \
  qwen/.runtime/vllm-venv/bin/python \
  docs/research/program-self-training-2026-09-26/train_sft.py \
  --config <config-numeric-<arm>32.json> --out <cpu-preflight-<arm>32> --preflight

/usr/bin/python3 docs/research/program-self-training-2026-09-26/gpu_job.py \
  --runtime qwen/.runtime/program_self_training_20260926 \
  --label <numeric-<arm>32> \
  --recovery-libs qwen/.runtime/answer_opd_pilot_20260926/recovery-nvml59584/extracted/usr/lib/x86_64-linux-gnu \
  --desktop-inventory qwen/.runtime/program_self_training_20260926/gpu-guard-amendment/first-launch-blocked.json \
  --input <config-numeric-<arm>32.json> --input <arm-dataset.json> \
  --input docs/research/program-self-training-2026-09-26/train_sft.py -- \
  qwen/.runtime/vllm-venv/bin/python \
  docs/research/program-self-training-2026-09-26/train_sft.py \
  --config <config-numeric-<arm>32.json> --out <new-runtime>/<arm>32

# 32/final完成後は実priorを指す128-configをCPU preflightし、
# train_continue.pyを同じgpu_job.py guard経由で呼ぶ。
CUDA_VISIBLE_DEVICES='' HF_HUB_OFFLINE=1 TOKENIZERS_PARALLELISM=false \
  qwen/.runtime/vllm-venv/bin/python \
  docs/research/program-self-training-followup-2026-09-26/train_continue.py \
  --config <config-numeric-<arm>128.json> --out <cpu-preflight-<arm>128> --preflight
```

32と128のpreflight/実行をmatch、shuffleの順に依存関係どおり行う。shuffle 128をmatchのcheckpointから続ける、といった交差はしない。

## 評価の再利用と独立確認

**最初の新seed screening**には、凍結済み `eval-jobs-v2.json` の24 jobを再利用する。これは学習7 sourceとは重ならない12構図に各1数値instance、各2推論seedであり、24独立問題ではない。baseと旧numeric128の既存出力・採点を不変の比較対象として再利用し、新しい二adapterだけ同じjobs/settingsで生成する。`run_evaluations.py` は完了済みOPD receiptと4 armを前提にhardcodeしているため、この二arm追加にはそのまま使わない。既存 `generate_batch.py` を個別armのadapter pathで呼び、`score_numeric.py` と現在のgrade/aggregate手順へ渡す小さなdriverを新設する。元driver/packet/採点は編集しない。

生成条件は既存どおりbatch 4、sampling seedはjob固定、temperature 0.7、top_p 0.95、top_k 20、presence penalty 0.2、thinkingなし、32,768 cap/context 40,960。全armのcapped job IDのunionを固定し、unionに含まれるIDだけを各比較armでcap 81,920/context 98,304に再実行する。baseまたは旧numeric128の保存結果に新しいunion IDがなければ、そのIDだけ同条件で補う。uniformな各budgetディレクトリは既存 `score_numeric.py` で採点する。extended-policyの最終job表は、小さなCPU joinerで事前固定ルールに従い該当IDのextended出力を選び、`score_numeric.grade_numeric_text` と元ファイルhashを保存する（32k/extendedを混ぜたreceiptを捏造しない）。budgetごとの出力hashと、各jobに採用したbudgetをmanifestへ記録する。打切りが残るjobは未解決/censoredのまま残す。

主指標は最終数値回答のexact correctness。12構図をcluster単位で併記し、2推論seedを独立の問題数として水増ししない。parser/形式訂正は感度分析でありprimary auto-scoreを書き換えない。現行の手動形式監査で正答数は変わらなかったため、曖昧なmarkerや未解析回答が出たケースだけ追監査対象にする。導出valid coreは別副評価として報告し、境界判定の保守値・許容値を併記する。

既存12構図は訓練構図と独立だが、各構図1数値instanceだけなので、chance clean-numberや特定given値への依存を除けない。より強い数値転移を述べる前に、同じ12 held-out構図それぞれに対し、訓練・現在評価と異なる数値givens/答えを持つ**新規1 instanceずつ**（計12 instance）を作り、独立な構成計算とexact label監査で凍結する。これは新定理の探索ではなく既存構図の再数値化とする。このjobs/keyは、これから行う**新seed 2-arm screeningの生成結果を開く前**に凍結する。confirmationではbase/new-match/new-shuffleの3条件を同じ2推論seedで評価する。screeningを見てcheckpointやpromptを変えない。新規instanceを正しく生成・監査できない場合はこの強い確認を行わず、既存24 job上の再現screeningに主張を限定する。

## 事前の判定と費用

- **再現screeningを通過:** full-budgetのmatchedが既存baseより少なくとも3/24 job多く正答し、同じseedのshuffleより少なくとも2/24多いこと、かつ差が単一構図だけに偏らないことを次段階への実務ゲートとする。これは小標本のscreening基準で、統計的有意性ではない。次は凍結済み12新instanceの確認へ進み、正対応の優位が再現すれば「この数値SFT設定では問題とlabelの対応が重要らしい」という範囲で報告する。今回完了した証明・code副評価を、数値転移の代用にはしない。
- **棄却/保留:** matchedがbaseを上回らない、shuffleとの差がない、またはscreeningの上昇が新規数値instanceで消える場合、seed特異性または回答分布/評価再利用の説明を残し、一般的な数値推論改善は主張しない。checkpoint選択・教材修正・追加seed探索で陽性結果を作らない。これは数値SFTの次段階の判定であり、完了した第一案・第三案の結果を遡って変更しない。
- 現行receiptでは数値32から128への学習に約58秒+151秒、peak reserved memory約17.4 GiB。二armを同様に学習するGPU時間は約7分。評価は既存numeric128で24 jobの32k生成が約50分、capped subsetの81,920延長が約36分だったため、新二armは延長分を含め**約2.5–3.5 GPU時間**を見込む（出力長で変動）。screeningのbase/旧numeric128は既存24-job出力を再利用し、全面再生成しない。ただし新しいcapped unionに旧出力のないjobが入れば、そのcondition/jobのextensionだけを追加生成し、予算を上乗せする。独立12-instance確認はbase/new-match/new-shuffleの3条件で概ね**約2.5–3.5 GPU時間**を見込む。旧numeric128も新setで評価するならさらに約1–1.5時間を加える。CPUでのdataset derangement・hash/tokenization preflightはGPU予算に含めない。

根拠ファイル（いずれも読み取りのみ）：`docs/research/program-self-training-2026-09-26/PROTOCOL.md`、`train_sft.py`、`config-numeric.json`、`docs/research/program-self-training-followup-2026-09-26/PROTOCOL.md`、`train_continue.py`、`config-numeric128.json`、それぞれのruntime receipt、`docs/research/transfer-reanalysis-2026-09-26/manifest.json`、`execution-amendment.json`、`run_evaluations.py`、`generate_batch.py`、`score_numeric.py`。
