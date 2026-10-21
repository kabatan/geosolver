# FT後の再読込検査と技術的再実行

最初の`train_foundation.py`は72更新を完了しadapterを保存したが、保存再読込後のlogit最大差0.5により検査で停止した。推論評価は始めていなかった。元のreceipt・重み・ログは`qwen/.runtime/foundation_pilot_20260923/sft-qwen3_4b/`に保持した。

調査するとPEFT 0.18.0の`load_adapter`は、新しいadapterをBF16のbaseと同じdtypeで作り、FP32の保存重みをコピーした後でFP32へ昇格していた。`diagnose_reload.py`で、最初の`PeftModel.from_pretrained`とdelete→load_adapter経路を比較。両方とも最終dtypeはFP32だが、後者は504tensor全部が丸められ、重みの最大差6.103515625e-05、logit最大差0.5を再現した。保存ファイルはFP32だった。

修正は再読込検査だけ。adapterを先に作り、コピー前にFP32に揃えてから公式load_adapterを使う。教師・学習率・seed・順序・更新数・評価を変えず、一度だけ同じレシピを再実行した。最初の試行も33.79秒、再実行も33.57秒の学習だった。新しい` sft-qwen3_4b-replay/`の504tensorが再読込前後で完全一致、logit最大差0を確認し、そのadapterだけを確認・対象評価へ進めた。

同じseedの再実行は最初の試行とのbitwise一致までは保証せず、実際の重みは最大差0.0008499959だった（technical-replay-comparison.json）。seed固定と完全決定性を混同しない。最初の試行の評価を見て良い方を選んだものではない。

vLLM推論時のLoRA演算はBF16であり、FP32 adapterによるHF学習時forwardと完全一致するという主張はしない。今回の検査は、保存自体の忠実性と、不意の二重丸めを分けるもの。モデル前後比較は同じvLLM driver・BF16設定で行う。

実行時間集計には最初の失敗receiptと成功した再実行receiptの両方を含む。このほか単発のreload診断が約4秒（ファイル時刻からの概算）あり、これはworker receipt合計とは別記する。
