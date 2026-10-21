# 3配置の自己生成 SFT 実行記録

2026-09-24。固定した教師は `train-multiconfig.json` の H01、DA04、DA15 各1件。学習前に SHA256 `a119f0f8acbeb9bb2b2e1a1f6fbd5921472e679b4d8ca056915085ebb1cd3bdf` を `sft-multiconfig-protocol.json` に記録した。原文の学習節・採否は `candidate-h01-fresh1-provenance.json`、`candidate-thinking-provenance.json`、`fresh-grades.json`、`thinking-grades.json` を参照。思考モードの内部思考と検証者の証明は教師に入れていない。

最初の `sft-multiconfig/` は更新0回で終了した。Qwen3.5の会話テンプレートが `<|im_end|>` の後に改行を付けており、終了トークンを最後の教師 token とする事前検査に失敗した。教師文・ハイパーパラメータは変えず、`train.py` でテンプレートの区切り改行だけを除いてから token 化した。失敗時の receipt は保持し、別出力 `sft-multiconfig-v2/` に再実行した。

再実行では 3例×2 epoch の6更新が完了した。assistant の回答だけに損失をかけ、prompt token 数は H01=207、DA04=246、DA15=226、回答と終了 token 数はそれぞれ1578、584、739。学習可能な LoRA パラメータは20,054,016、変化した tensor は400、最大確保 GPU メモリは24.00 GiB。保存後に400 tensor 全てが同一値で再読込され、比較した最終 token の logit 最大絶対差は0。adapter SHA256は `28df1051d5c010cc3abf00c50b7780518d19eaa467f4512bf3a23227e23d2833`。各更新の損失・勾配 norm・所要時間と完全な receipt は runtime 出力に保存した。

この loss の低下は教師3例への当てはまりの指標であり、未見の証明・発見能力の改善とはみなさない。固定した6問×2回答を未更新と更新後で比較して判断する。

## 追加の用量探索

同じ3教師、同じ rank 8 を使う30更新（10 epoch、学習率 `1e-4`）を、`sft-dose-probe-protocol.json` で先に固定してから実行した。元の3例のままなので、データ多様性を増やした実験ではない。`sft-dose-probe/receipt.json` によれば30更新が完了し、学習可能パラメータ20,054,016、変化した tensor 400、GPU最大確保23.997 GiB、再読込時に400 tensor一致・logit最大差0だった。元 adapter SHA256は `ee9c4dce603a41bce1719ff489a67265b105f4934aaa858346d93705cc3ffa29`。初回3更新の平均 loss は約0.6045、最後3更新は約0.0177。教師への強い適合を示すが、評価の正しさを保証しない。

用量探索でも推論用に数値を変えず層名だけ写像した `sft-dose-probe/adapter-vllm/` を使用した。写像済み adapter SHA256は `d21734b8a65803c3a02b92f68e3db1e6d4f292f262833d43901f909f321998dd`（変換元との対応は `mapping-receipt.json`）。同一 vLLM エンジン内の上位20 token の log probability 差は H01 8.18、EV02 4.38 natであり、更新が実効適用されている。固定証明評価 `proof-after-dose-mapped/receipt.json` は12出力を記録し、12件とも `dose-grades.json` で手監査した。発見評価も同じ写像済みadapterと固定jobで8回答を生成し、`discovery-after-dose-mapped-grades.json`に手監査した。
