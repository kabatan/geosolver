# FT後の悪化に対する実装照合

2026-09-23。追加の重み更新は行っていない。32回答の悪化を見て選んだ診断であり、新しい独立性能評価ではない。

同じ保存済みadapterを、学習時と同じHugging FaceモデルにFP32 LoRAで読み込み、さらにLoRAだけをBF16へ変えた場合、vLLMで読み込んだ場合を照合した。baseはBF16。学習例3問（T04/T09/T20）と確認例3問（C03/C04/C16）、greedy、最大512token。プロンプトはnative chat templateで一致させた。

- 学習例3問では、3経路とも教師の数学的方針と正しい証明を再現し、生成token列も経路間で完全一致した。
- 未学習C03では、3経路とも条件を満たさないSSSや誤った角の和から垂直を導く。FP32 HFとvLLMでは、誤った回答のtoken列まで一致した。
- 未学習C04では、3経路とも誤った直線のパラメータ表示から間違った比を導いた。
- C16はHFの両精度で正しい面積の証明。vLLMでも面積を使うが、高さと底辺の表記を取り違えた説明となった。この診断で全回答の完全一致を主張しない。

したがって、今回の大幅な悪化を「vLLMへの移行だけ」「LoRAのBF16化だけ」で説明することはできない。学習例の再現と、条件の異なる問題での誤適用が併存している。ただし、極短の教師、24構造という範囲、3epoch反復、学習率等の寄与を分けるablationは行っていない。暗記・出力の短文化と整合的な観測であって、単独の原因の確定ではない。

初回はtransformers 5のtokenize戻り値の扱いで停止。再実行ではHF診断が完了した後、vLLM起動時に既存推論driverの`VLLM_USE_FLASHINFER_SAMPLER=0`を引き継いでいないことによるnvcc未検出エラーで停止した。同じ設定を補い、HF結果を再利用してvLLM部分だけを再実行し完了した。診断用の失敗を主実験のモデル失敗率に混ぜない。全実行時間は費用へ含めた。

再現資料：

- [診断コード](check_ft_fidelity.py)、[経路間の比較](ft-fidelity-comparison.json)
- HFとvLLMの生回答：`qwen/.runtime/foundation_pilot_20260923/ft-fidelity-retry/{hf,vllm}.json`
- 診断receipt：`ft-fidelity/`、`ft-fidelity-retry/`、成功したvLLM追加実行`ft-fidelity-vllm-recovery/`
- 再読込精度の別問題：[RELOAD_INCIDENT.md](RELOAD_INCIDENT.md)。本診断は再読込検査を通過した最終adapterで実行した。
