# 今回実行した小診断

2026-09-26。転移の有効性を実証する訓練実験ではない。候補手法の入力効果と実装可能性を調べた。

## 正解数値を見せると本人の導出が改善するか

Qwen3.5-9Bの未更新base、non-thinking、4構図×ヒントなし／数値ヒントあり×各1生成。条件ごとに同じseedとサンプリング設定。生成上限32768、context45056、2系列。過去に使った開発構図から事前にH04/H07/DA05/H14を選んだ。対象の一般式・完成解法はpromptに含まない。

| 構図 | ヒントなし：必要な導出 | 数値ヒントあり：必要な導出 | 観察 |
|---|---|---|---|
| H04 | 成立* | 成立* | 座標による核心の導出あり |
| H07 | 成立 | 不成立 | ヒント条件は座標の符号誤りを解消せず、答えから不足量を逆算 |
| DA05 | 不成立 | 不成立 | ヒント条件は正しい数値5を返すが、核心の積の関係を未証明の既知性質として扱う |
| H14 | 不成立 | 不成立 | 30から24へ数値は変わるが、必要な直角関係の証明はない |

必要な導出が完結した数は2/4対1/4。数値だけの正答は2/4対4/4。*H04双方には独立した余談の存在確認・検算に誤記があり、全文無誤謬という採点ではない。核心を含む必要な導出と、その余談の誤りを分けて記録した。採点の式と理由は [HINT_PROBE_GRADES.md](HINT_PROBE_GRADES.md) に残す。

全8回答は自然終了した。生成合計77742 tokens、モデルロード等を含むwall time689.22秒（約11.5分）。訓練更新はゼロ。1構図1sampleの小さい意図的選択なので、ヒントの平均的効果や統計的な悪化を推定しない。「答えさえ知れば妥当な自己教師答案が増える」という期待に対する局所的な反対材料であり、自己蒸留の重み学習効果を否定する実験でもない。

再現情報： [protocol](hint-probe-protocol.json)、[jobs](hint-probe-jobs.json)、[生出力](hint-probe-outputs.json)、[receipt](hint-probe-receipt.json)、[driver](hint_probe.py)。生出力archiveはtoken IDsを除く各recordと元record SHA-256を保存する。完全recordは `qwen/.runtime/learning_options_20260926/hint_probe/`。

## 数値ヒント付き自己教師から実際に更新できるか

H04のヒントなし生成をそのまま採点列に使用。凍結baseを教師とし、教師側だけに数値答え4を追加した。学生は同じbaseにr8 LoRAを付け、元入力を使う。回答tokenの対応をassertし、教師forward→教師logitsをCPUへ退避→学生forward/backward→optimizer updateの順で実行した。教師・学生ともnon-thinking。新しい生成はない。

| 確認条件 | peak allocated GPU | ロード込み秒 | 結果 |
|---|---:|---:|---|
| 同じ生成の先頭1024 tokens | 18.51 GiB | 4.41 | 1更新成功 |
| 自然終了した全5670 tokens | 26.16 GiB | 12.70 | 1更新成功 |

全語彙のforward KLをtoken chunkで計算した。CPU上で通常のdense計算と比較し、loss差1.19e-7、最大gradient差7.45e-9、同一分布KL=0を確認。実モデルではgradientは有限、両試験とも200/400のLoRA tensorが変化した。初期B=0の初回更新ではA側の勾配が0となるため、これはinactive adapterの兆候ではない。

全5670版はteacher forward2.04秒、student update7.22秒、teacher CPU logits2.62GiB。測ったのは1例・1更新で、全32k答案や長時間on-policy学習の完走を示さない。能力評価は行わず、adapterも保存していない。各試験は未更新baseから別々に開始した。

重要なのは、単GPUで全5.7k答案のdense自己蒸留更新まで既存環境のまま実行できたこと。学習ループへの統合は残るが、「教師モデルを別に9B載せる必要があり実行不能」という実装上の懸念は、この形では解消した。数値ヒントによる確率変化が正しい推論を強化するとの実証ではない。

実装：[distillation_probe.py](distillation_probe.py)。prefix版実行時のscriptも [distillation_probe_prefix_v1.py](distillation_probe_prefix_v1.py) に保全。詳細receiptと追加説明は [DISTILLATION_PROBE.md](DISTILLATION_PROBE.md) を参照。

## 推奨への反映

1. 無検査の正解ヒント答案を集めるSTaR/SFTは主投資先にしない。検査付き版は小さい比較候補として残す。
2. 数値ヒントから各tokenの分布を作る自己蒸留は、更新部の実装可能性を確認したため、次の小さい学習実験の第一候補にする。妥当性を保証する教師ではないことは維持する。
3. 数値RLの先行根拠はGeometryZeroに置き、今回のヒント生成診断と混同しない。
4. 複数入力に通用する自己生成プログラムの経路は今回未実装・未評価。文献と具体化した実装計画に基づく、より冒険的な別候補として提示する。
