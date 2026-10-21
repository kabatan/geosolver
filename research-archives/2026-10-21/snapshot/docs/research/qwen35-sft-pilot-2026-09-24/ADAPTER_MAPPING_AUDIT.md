# Qwen3.5 LoRA 推論時の層名対応

6更新の PEFT adapter は Hugging Face のテキスト専用モデル `Qwen3_5ForCausalLM` で学習した。保存重み400 tensorのキーは `base_model.model.model.layers.*` から始まる。一方、同じ Qwen3.5-9B スナップショットを vLLM は `Qwen3_5ForConditionalGeneration` として読み、言語モデルを `language_model.model.layers.*` の下に置く。

初回の `proof-after-multiconfig/` は vLLM に元の adapter を渡して完了したが、有効な SFT 比較ではない。同一エンジン・同一入力での上位20 token の log probability は、LoRA要求の有無で**全て同値**だった（`vllm-adapter-effect-initial.json`）。一方、Hugging Face で元 adapter を適用すると、最大 logit 差は学習 H01 入力で0.542、評価 EV02 入力で0.250だった（`adapter-effect-initial.json`）。従って保存した学習重みは非ゼロだが、vLLM の元の層名では適用されていなかった。初回の生成・採点 `unmapped-after-grades.json` は失敗した推論経路の監査用に残し、改善の根拠に使わない。

`map_vllm_adapter.py` は数値 tensor を変更せず、全400キーに `model.language_model.` を挿入した推論用コピー `adapter-vllm/` を作った。元ファイルとコピーのハッシュ、変換規則は `adapter-vllm/mapping-receipt.json` に記録している。変換後、同じ vLLM の上位20 tokenで最大 log probability 差は H01 入力0.253、EV02入力0.128となり、LoRAの適用を確認した（`vllm-adapter-effect-mapped.json`）。以降の推論はこの変換済みコピーだけを使う。

この修正は学習をやり直すものではなく、モデル重みの数値もハイパーパラメータも変えない。評価の設定は元の固定6問×2、同じseed・sampling・出力上限を維持する。
