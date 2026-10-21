# Qwen3-4B 環境

固定した `Qwen/Qwen3-4B` の取得・環境診断・単発推論と、数値監督による幾何学習実験。実験ではchat templateのthinkingを有効にする。solverの `.venv` とは別のPython環境を使う。

## 構成

- `models.json`：モデルID・immutable revision・全ファイルのSHA-256・検証済みsnapshotの場所を記録するロック。
- `models.py`：revisionの解決・snapshot取得・ファイルhash検証（`ensure_models` / `locked_models`）。
- `inference.py`：BF16・SDPAでのモデル読込と、chat template経由の単発生成。推論結果にはモデルrevision・生成設定・終了理由・入出力token数・所要時間・ピークメモリを記録する。
- `doctor.py`：重量ファイルのhash再検証、CUDA/BF16確認、KV 32768トークン負荷、実験課題と無関係な短文スモーク生成。
- `common.py`：JSON・hash・時刻の補助。
- `requirements.in` / `requirements.lock`：固定依存（torch 2.12.1+cu130、transformers 4.57.6 等、hash付き）。

## 環境構築

```bash
uv venv --python 3.12 qwen/.venv
uv pip sync --python qwen/.venv/bin/python --require-hashes \
  --extra-index-url https://download.pytorch.org/whl/cu130 \
  --index-strategy unsafe-best-match qwen/requirements.lock
```

依存を再解決する場合は `uv pip compile qwen/requirements.in --index-strategy unsafe-best-match --generate-hashes -o qwen/requirements.lock`。

## 使い方

```bash
# モデル取得（既に固定revisionがHFキャッシュにある場合はその検証）
qwen/.venv/bin/python -m qwen download

# 環境診断（GPU・重みhash・KV負荷・無関係スモーク）
qwen/.venv/bin/python -m qwen doctor --output qwen/doctor.json

# 任意テキストへの単発推論
qwen/.venv/bin/python -m qwen infer --prompt "What is 2 + 3?"
qwen/.venv/bin/python -m qwen infer --file problem.txt --output result.json
cat problem.txt | qwen/.venv/bin/python -m qwen infer
```

`infer` の主な引数：`--system`、`--seed`、`--max-new-tokens`、`--context-limit`、`--temperature`、`--top-p`、`--top-k`、`--wall-seconds`。`--prompt`・`--file`・標準入力の順で入力を解釈する。

モデルの重みはrepo外の共有HFキャッシュを参照する。`models.json` の `snapshot_path` が無効な環境では `download` を再実行して再固定する。

## vLLM診断環境（実験用・`.runtime` 内）

`diagnostics.py --engine vllm` は別環境（`qwen/.runtime/vllm-venv`、`uv pip install vllm`、vllm 0.29・torch 2.13・cu13で動作確認）で実行する。SM120（RTX 5090）では以下が必要：

- `VLLM_USE_FLASHINFER_SAMPLER=0`：sampler opのJITがCCCL版不一致で失敗するためtorchサンプラに落とす。
- FlashInfer系カーネル（fp8 KVのxqa decode等）をJITさせる場合は `CUDA_HOME=<venv>/lib/python3.12/site-packages/nvidia/cu13`、venv `bin`（ninja）を `PATH` に追加し、`FLASHINFER_EXTRA_CUDAFLAGS="-DCCCL_DISABLE_CTK_COMPATIBILITY_CHECK"`・`FLASHINFER_EXTRA_LDFLAGS="-L<cuda_home>/lib"` を付ける。pip配布nvcc（13.4）とcudartヘッダ（13.0）のマイナー不一致がCCCLの互換チェックを落とすため。`nvidia/cu13` には `lib64→lib` と `lib/libcudart.so→libcudart.so.13` のシンボリックリンクを作る。

実測（296回答・思考長回答）：bf16 `generate` ~242 tok/s、vLLM bf16 ~809 tok/s、**fp8 KV + FlashInfer ~1427 tok/s**。fp8は `--kv-cache-dtype fp8`、xqaは自動選択。`gpu_memory_utilization` は0.9が上限（0.93でプロファイルOOM）。EAGLE3推測decodeは飽和状態では逆効果（-9%）。nvfp4 KVはvllm 0.29ではSM120未対応。

長文生成の自然終了長（37配置×4回答・fp8+FI・上限32,512・`longctx_fp8.jsonl`）：平均19,870 tok、終了組はp50≒20k・p90=27,170・p95=29,152・max=32,449。打ち切りは7/148（4.7%）のみで全件不正解or未解析（32kまで達して正解に至った例なし）。16,384上限時は打ち切り69%・正答率22.6%だったのが、32,512では正答率45.9%に改善したため**評価・ロールアウトの上限は32,512（コンテキスト32,768−prompt分）を推奨**。コスト削減が必要なら28,672（自然終了の89%を収容、失う正解は全体の~2%）。注意：32GiBではKV pool 275k tokで同時実行~8-10系列まで（実効~932 tok/s）、chunked prefill中に一時的な活性化OOM警告が出ることがある（0.9 util・非致命的）。TRL GRPO colocateではvLLM sleepモード（rollout時のみKV確保・学習時に解放）が前提になる。

## exp01の修復・再評価（2026-09-22）

数値採点は `answer_check.py` の `exact-numeric-v2` を共用する。旧採点の値と混ぜない。
保存済み回答の再採点は `.venv/bin/python -m qwen.review_exp01` で実行でき、出力先は
`qwen/.runtime/exp01/review_v2/`。元回答・checkpointは変更しない。

[修復・再評価の完了報告](../docs/research/exp01-repair-completion-2026-09-22.md) と
[次の技術的較正の計画](../docs/research/exp02-technical-calibration-plan-2026-09-22.md) を参照。
exp01のrunner `grpo_segment.py` は正規化とBF16同期に問題があり、実行を停止した。
旧コードはexp01の退避先で参照できる。上記のBF16/fp8速度・旧採点の数値は歴史的な測定であり、
以下の修復後の精度・速度・正答率として流用しない。

## 段階的な学習と証明評価（exp03）

現在の手順は [段階実験プロトコル](../docs/research/exp03-staged-protocol-2026-09-22.md)。
`exp03_staged.json` と `staged_study.py` を使う。旧 `exp03_pilot.json`、
`exp03_budgeted.json` は履歴であり、新しい実験を開始する設定には使わない。

既存の `qwen/.runtime/vllm-venv`（torch 2.13.0、transformers 5.17.0、peft 0.18.0、vLLM 0.29.0）で実行する。
全依存・モデル・データ・コードは `qwen/.runtime/exp03_staged/study/training/manifest.json` に固定する。
上記の単発推論用requirements.lockとは別環境である。

- `fast_engine.py`：FP16 base/KVと未マージLoRAによる生成。
- `grpo_policy.py` / `grpo_loss.py`：FP16またはFP32 learner、token正規化、凍結LM headの省メモリ逆伝播。FP16経路は勾配スケーリングとtoken単位の生成確率補正を使う。
- `grpo_stage.py` / `grpo_run.py`：生成と更新を別processで実行し、raw回答・logprob・optimizerを保存して再開する。
- `experiment_budget.py`：準備・失敗試行・学習・前後評価を同じ台帳へ記録する。24〜40時間は目安。今回の無人実行には48時間の累積上限と8時間の後評価留保を置く。
- `staged_study.py`：前評価→37配置を網羅する10ラウンド→数値・証明評価→科学的分析→継続または終了→最終評価。今回の報酬は数値正誤Cのみ。
- `staged_readiness.py`：較正済みの数値処理が不変であること、新しい実行制御のCPU検証、準備費用の引継ぎを確認する。
- `grpo_evaluate.py` / `grpo_compare.py`：固定条件での前後比較と、採点完了後のモデル対応表開示。
- `fast_readiness.py`：短文・長文更新、生成側への反映、復元、32kメモリ、実測費用、テストの通過記録をまとめる。

repoのルートで実行する。

```bash
# 準備済み設定の検査のみ。GPU学習・評価を開始しない。
qwen/.runtime/vllm-venv/bin/python -m qwen.staged_study

# 本実験を開始、または同じ設定・出力先から再開する。
qwen/.runtime/vllm-venv/bin/python -m qwen.staged_study --run

# 全GPU workerが停止しているときの残り予算確認。
.venv/bin/python -m qwen.experiment_budget status \
  --ledger qwen/.runtime/exp03_staged/budget.json
```

実験中にコード・入力・モデル・環境を変更したまま再開することはできない。
未完了のworker記録があれば、実プロセスと計上時間を確認してから再開する。台帳を削除して時間をリセットしない。
証明の自動正誤判定は行わず、中間48答案・最終96答案の数学的採点を行う。
中間では学習答案48本も診断し、同配置の未指導証明を第一成果として継続を判断する。
採点・判断の保存と再開コマンドは上記プロトコルを参照。

[追加報酬の追試計画](../docs/research/exp03-reward-followup-plan-2026-09-22.md) は、
同じcheckpointからC継続・妥当性追加CV・説明価値追加CVGを比較する別実験の設計。
今回のrunnerはV/Gのjudgeや追加学習を自動起動しない。

## FP32の参照較正と過去の速度測定

[exp02報告](../docs/research/exp02-technical-results-2026-09-22.md) にFP32での目的関数・同期・復元の検証を保存している。
この経路は長文で約99 token/秒であり、全面採用すると旧評価規模では3〜4日を要する見積りだった。
[費用判断の修正](../docs/research/exp03-cost-revision-2026-09-22.md) を経て、上記の予算付きFP16経路へ切り替えた。
FP32較正は原因診断の参照として残し、低精度学習が不可能だという根拠には扱わない。
旧 `diagnostics.py` のBF16/fp8速度と旧採点値は履歴であり、現在の学習の所要時間・精度として流用しない。
