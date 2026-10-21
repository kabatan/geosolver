# 既成モデルで基礎FTを省けるか：候補調査

2026-09-23。論文・公式モデルカード・公開設定・一部の公開学習データを調査した。モデル重みのダウンロード、推論、GPU利用、学習、教材作成は行っていない。候補化は実験開始や採用の決定ではない。

## 結論

新規候補として先に検討するのは **deepseek-ai/DeepSeek-R1-0528-Qwen3-8B**。**nvidia/OpenMath-Nemotron-7B** は数学特化の予備候補として残す。どちらにも、今回の条件で基礎幾何証明が安定し、32k以内で数学的に有用な対象解法が出ると強く予測できる直接証拠はない。Qwen3/Qwen3.5の既存候補をこの調査だけで置き換えない。

自然言語証明への最も直接的な実績があった **lm-provers/QED-Nano** は、対象と関連する教材の実在と長い生成コストのため、現在のHumpty/Dumpty研究の主モデルには推薦しない。別題材の研究・能力比較用には意味があるが、そのために今回の題材を変更する提案はしない。

「そのまま使える」には、公開重みを動かせること、必要な基礎能力を持つこと、研究意図・追加学習費用に合うことの三つがある。公開重みと一般数学スコアだけで後二つを保証しない。文献だけで基礎FTが不要と判定できるモデルは、今回の調査では見つからなかった。

## 優先して残す候補

### DeepSeek-R1-0528-Qwen3-8B

- [公式モデル](https://huggingface.co/deepseek-ai/DeepSeek-R1-0528-Qwen3-8B)、[公式ファイル一覧](https://huggingface.co/deepseek-ai/DeepSeek-R1-0528-Qwen3-8B/tree/main)。Qwen3-8B BaseにR1-0528の推論を蒸留。通常のQwen3-8Bと同じモデルではない。
- 公式の同表比較でQwen3-8Bより数値数学が改善。ただし最大64k生成の評価であり、今回の32k内の証明品質を示してはいない。
- [Prover Agent](https://arxiv.org/html/2506.19923v2)で、自然言語の証明・補題を提案する役に実採用されている。整数解答以外での利用実績という補助根拠はある。ただし別のLean prover・検証・多数試行を含むシステムの成績を、この8B単体の能力とみなさない。
- Qwen3系の標準構造、BF16重み約16.4GB。サイズと実装の面では候補にできるが、長系列LoRA/RLが32GBに収まることや速度は未測定。
- 対象教材の無混入は未確認。学習元が完全には監査できないことを、公開データで重なりが見つかったモデルより安全な証拠とみなさない。

推薦の確信度：**追加候補としては中程度**。通常のQwen3-8Bと異なる事後学習と論証用途の実績が理由。基礎FT不要、幾何的な見方が得意、対象を知らない、という確信はない。

### OpenMath-Nemotron-7B

- [公式モデル](https://huggingface.co/nvidia/OpenMath-Nemotron-7B)、[AIMO2論文](https://arxiv.org/html/2504.16891v1)。Qwen2.5-Math-7B由来の数学特化SFT。純CoTでも動き、コード実行は必須ではない。AIMO2の実際の優勝提出は14B系であり、この7Bを優勝モデルそのものとは呼ばない。
- 論文の純CoT評価は最大32,768出力token。公式カードの4,096tokenは使用例であり成績の条件ではない。
- 標準Qwen2構造で学習資料も公開され、独自アーキテクチャへの移行負担は比較的小さいと推測できる。推論/更新の実測はない。
- 数値数学の強さは確認できるが、初等幾何の完全な証明や有用な簡略化に関する直接的な優位は未確認。
- [現行データカード](https://huggingface.co/datasets/nvidia/OpenMathReasoning)は問題数を306Kに訂正し、137Kの証明由来問題が処理バグで欠落していたことも記す。証明を数値化した学習であり、「証明を大量に習ったから証明が得意」とは推薦しない。
- AoPS由来データの対象重複を、サーバ全文検索・problem列検索で狭く照合したが、500エラー/timeoutで完遂できなかった。Web索引にも一致を確認できなかったが、不在の根拠にはしない。対象重なりは未確認。

推薦の確信度：**数学特化の予備候補として中程度、今回の証明課題への適合は弱い根拠に留まる**。前者より先に選ぶ決定的証拠はない。

## QED-Nanoを主候補にしない理由

[公式カード](https://huggingface.co/lm-provers/QED-Nano)で4Bの公開BF16重み、Qwen3-4B-Thinking-2507由来、自然言語証明向けSFT/RLを確認。Leanや画像入力は不要。この点では今回の不足能力に最も直接的な候補だった。

[論文](https://arxiv.org/html/2604.04898v1)のIMO-ProofBench平均採点は元モデル20.4→40.0。ただし正答率ではない。単発生成でも平均93,690tokenを使用し、著者の数学監査では幾何における計算偏重が弱点とされる。したがって短い生成枠・有用な幾何的簡略化への優位は未確認。SFT版も公開されるが、長文化の問題が報告されており、安価な代用品とみなさない。

[公開評価設定](https://github.com/CMU-AIRe/QED-Nano/blob/main/eval/configs/models/vllm/vllm-lm-provers-qed-nano.yaml)のmax_tokensは229376。モデルカードの32k使用例を、上の成績の測定条件として引用しない。

さらに今回、公開FineProofsの対象関連行を確認した。

| 公開集合 | 0始まりrow | 確認できた関係 |
|---|---:|---|
| [FineProofs-RL](https://huggingface.co/datasets/lm-provers/FineProofs-RL/viewer/default/train?row=2349) | 2349 | Humptyの名称、HからAMへの射影、BHCの円上という性質を採点に用いる |
| [FineProofs-RL](https://huggingface.co/datasets/lm-provers/FineProofs-RL/viewer/default/train?row=2662) | 2662 | AEFの円とAMの交点の問題で、Humptyに関する接円性を採点に用いる |
| [FineProofs-SFT](https://huggingface.co/datasets/lm-provers/FineProofs-SFT/viewer/default/train?row=1763) | 1763 | RL2349と同文の配置。教師の座標解答が関連する長さ比を導く |
| [FineProofs-SFT](https://huggingface.co/datasets/lm-provers/FineProofs-SFT/viewer/default/train?row=2074) | 2074 | RL2662と同文の配置。教師解答がHumpty配置の点を導いて平行関係を証明 |

RLではHumptyという文字列はrow2177/2349/2656/2662、Dumptyは2177/4823の採点基準に見つかった。SFTの対象2行は座標解法であり、Humptyという名称や純幾何的解法を直接教えているとまでは確認していない。RLの採点基準は採点器側の入力であり、学習者に同文が直接表示されることとも区別する。

公開教材に対象配置と教師解答があることは確認できたが、各行が最終モデルのどの更新で使われ、何を実際に獲得したかまでは証明していない。それでも、対象への学習済み度合いが不明な一般モデルとは異なり、今回の性質を強化する具体的な学習経路が公開されている。「基礎だけ整えたモデル」の代替として採用するには不向きと判断する。

調査時dataset revision：FineProofs-SFT `73661e62811cf2940a0d3f82788a4f4332204c2f`、FineProofs-RL `61c9ade2e04ab4ee7e257434e0826cb9b737f63e`。RL全5227行、SFT default4281行の問題等の列を調べ、SFTの教師解答は対象2行だけ確認した。全面的な混入監査ではない。

## 今回追加しないモデル

| 候補 | 理由・一次資料 |
|---|---|
| LIMO | [公式公開品](https://huggingface.co/GAIR/LIMO)は32B。単一32GBでの継続学習へ移すには量子化/offload等の追加検討が必要で、今回固有の幾何証明上の優位も未確認 |
| s1.1-7B | [公式カード](https://huggingface.co/simplescaling/s1.1-7B)自身が未評価と記し32Bを推奨。32Bの実績を7Bに流用できない |
| LIMR、DeepScaleR-1.5B | [LIMR](https://huggingface.co/GAIR/LIMR)、[DeepScaleR](https://huggingface.co/agentica-org/DeepScaleR-1.5B-Preview)は関連手法として意味があるが、今回不足する証明の安定性に関する優位の根拠がない |
| NuminaMath-7B-CoT/TIR | [公式CoTカード](https://huggingface.co/AI-MO/NuminaMath-7B-CoT)が幾何と難問答案の妥当性の弱さを明記。TIRはツール利用も伴う |
| OpenReasoning-Nemotron-7B | [公式カード](https://huggingface.co/nvidia/OpenReasoning-Nemotron-7B)では64k生成で数値数学等が強い。OpenMathから改善した証明性能や32k内の効率を示す資料は未確認。両方を自動追加しない |
| AceReason-Nemotron-1.1-7B | [公式カード](https://huggingface.co/nvidia/AceReason-Nemotron-1.1-7B)の数学・コード改善だけでは今回固有の追加候補化の根拠が弱い |
| Phi-4-reasoning系14B | [公式カード](https://huggingface.co/microsoft/Phi-4-reasoning)に広い数学能力の根拠はある。既に試したminiとは別モデルだが、BF16重みだけで約30GB級となり、長文生成と追加学習の余裕が小さい。今回この実装・費用変更を優先するほどの証明上の根拠は不足 |
| FM-Pochi-32B-IMO26 | [公式カード](https://huggingface.co/fieldsmodelorg/FM-Pochi-32B-IMO26)で証明用の公開重みは確認。32Bと専用推論系の負担、synthetic geometryの弱さから今回の直接代替にはしない |
| GeometryZero、GeoFM | 論文の手法・結果は参考になるが、今回確認した公式資料から利用できるモデル重みを特定できなかった。論文の存在を配布済みモデルと混同しない |

## 今後の判断への反映

新候補を既存4モデルへすべて加えた一括実験は提案しない。文献調査だけでは採用を確定できず、将来実験を許可された場合にも、追加候補はまず一つに限定する考え方を維持する。上記二候補ならDeepSeek-R1-0528-Qwen3-8Bを先に検討し、OpenMath7Bは予備にする。

QED-Nanoの調査は、小型モデルでも証明能力を改善できることを支持する一方、長い教師解答をSFTすれば安価で幾何的に有用なモデルができる、という推論を支持しない。対象教材の混入と生成長を制御する基礎FT案には依然役割があるが、既成モデルの不適合が確定したわけでもない。

対象を事前に一切知らないことは、どの公開モデルにも保証できない。今回追加した学習の効果を測ることと、基礎モデルが何を教えられていたかの限界を分けて記述する。データが非公開で重なりを調べられないことを、クリーンな証拠にはしない。
