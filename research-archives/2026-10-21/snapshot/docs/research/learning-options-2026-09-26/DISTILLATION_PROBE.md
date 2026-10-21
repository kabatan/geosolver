# 数値答えを知る同モデルからの自己蒸留：単GPU技術確認

2026-09-26。Qwen3.5-9B、RTX 5090 32GB、既存環境を使用。新しい学習案が実装可能かを限定して確認した。**学習後の能力・転移・仮説の支持は測っていない。**

## 実行したこと

既存の数値ヒント対応比較で生成されたH04のno-hint答案を使用。学生は元の問題文だけ、教師は同じ問題文に数値答え `4` だけを加えた入力を受ける。教師と学生は同じbaseを共有し、教師forward時はLoRAを無効にする。両者non-thinking。

異なる長さの入力に同じ出力token列を連結し、各出力tokenの直前位置の分布を対応させる。教師の全語彙logitsはCPUへ退避し、学生のfull-vocabulary forward KLを64-token chunk単位で計算する。custom autogradでsoftmaxをbackward時に再計算し、大きなsoftmax graphを保持しない。r8/alpha16、学習率1e-5のLoRAを1更新する。モデル・LoRA target・読み込み方は既存の9B SFT実績から流用。

1024-token prefixと、自然終了した5670-token全答案を別々に実行した。各実行は同じ未学習baseから初期化し、1更新後にadapterを保存せず終了した。新しいrolloutは生成していない。

## 結果

| 項目 | 1024-token prefix | 5670-token全答案 |
|---|---:|---:|
| 学生prompt tokens | 131 | 131 |
| 教師prompt tokens | 174 | 174 |
| Peak allocated | 18.51 GiB | 26.16 GiB |
| Peak reserved | 19.32 GiB | 26.53 GiB |
| 教師forward | 0.83秒 | 2.04秒 |
| 学生forward/backward/update等 | 0.87秒 | 7.22秒 |
| load等を含む全体 | 4.41秒 | 12.70秒 |
| 平均forward KL | 0.003715 | 0.002958 |
| finite gradients | true | true |
| 変化したLoRA tensors | 200/400 | 200/400 |

初回はゼロ初期化LoRA側のみ主に変化するため、200/400を失敗とは扱わない。chunked KLはGPU実行前にCPUの小tensorでdense実装と比較し、値の差1.19e-7、最大勾配差7.45e-9。同一分布ではKLと勾配がゼロ。

## 意味すること・意味しないこと

- 同じ5090で、教師9Bをもう一つ載せずに、数値答えによる分布差から実際にLoRAを更新できる。今回の実装では自然終了した5.7k答案の全体まで動いた。
- 1kのprefix蒸留から始める必要しかないわけではない。長さに応じて1k prefixと自然終了答案を別条件にする実装余地がある。
- この1更新を、学習済みモデルの改善と呼ばない。重み変化が望ましい方向かは測定していない。出力token上のteacher/student差が非ゼロでも、その差が誤った推論を適切に罰しているとは限らない。
- teacher non-thinking、KL成分clampなし。最新のanswer-only OPSD論文のteacher thinking・成分clampあり条件を再現していない。
- 長い答案を繰り返し生成する時間は含まない。on-policy再生成、複数更新の安定性、32k評価、複数seedは未実行。最大32k系列がメモリに収まるとも主張しない。

## 再現資料

- [実行driver](distillation_probe.py)
- [prefix実行時のdriver保存版](distillation_probe_prefix_v1.py)
- [CPUの同値確認](distillation-probe-cpu-check.json)
- [prefix receipt](distillation-probe-prefix-receipt.json)
- [全答案 receipt](distillation-probe-full-receipt.json)

実行コマンド（新しい出力directory名が必要）:

```bash
qwen/.runtime/vllm-venv/bin/python docs/research/learning-options-2026-09-26/distillation_probe.py --run --tokens 5670 --output-name distillation_probe_full
```

既存receiptや結果を上書きしない。今回、依存ライブラリの追加・更新は行っていない。
