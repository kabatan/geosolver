# 候補の選び方と公式資料

2026-09-23。順位は実験後に決める。公開競技スコアは幾何証明の正しさを保証しない。

| 候補 | 今回調べる理由 | 主な確認点 | 公式資料 |
|---|---|---|---|
| Qwen3.5-4B | サイズを増やさず世代を変える | 有用な解法の出現、Gated DeltaNetを含むLoRA経路 | [モデル](https://huggingface.co/Qwen/Qwen3.5-4B) |
| Qwen3.5-9B | 同世代で容量を増やす比較 | 4Bより良い自己解法が費用に見合う頻度で出るか | [モデル](https://huggingface.co/Qwen/Qwen3.5-9B) |
| Phi-4-mini-reasoning | 小型で数学推論に重点を置いた別系列 | 英語での証明の完成度、長い推論の費用 | [モデル](https://huggingface.co/microsoft/Phi-4-mini-reasoning)、[論文](https://arxiv.org/abs/2504.21233) |
| MiMo-7B-RL | 推論を重視した事前・事後学習、別の学習履歴 | native MiMo実装での生成、幾何への適合性 | [モデル](https://huggingface.co/XiaomiMiMo/MiMo-7B-RL)、[論文](https://arxiv.org/abs/2505.07608) |
| Nemotron-Nano-9B-v2 | Mamba-Transformer型の別系列、推論効率も候補 | state精度、公式thinking制御、LoRA実装の負担 | [モデル](https://huggingface.co/nvidia/NVIDIA-Nemotron-Nano-9B-v2)、[論文](https://arxiv.org/abs/2508.14444) |
| Qwen3-4B-Thinking-2507 | 英語条件を揃える既存モデル対照 | 前回との差をモデル変更だけの効果と誤認しない | [モデル](https://huggingface.co/Qwen/Qwen3-4B-Thinking-2507) |

Phiの公式カードは対応言語をEnglishとし、推論例は温度0.8。初回pilot後の正式な一次診断では公式例の0.8を用いる（PROTOCOL.mdの改訂参照）。候補ごとの最適設定を総探索したものではない。MiMoは空systemを推奨、Nemotronは/thinkとfloat32のSSM stateを推奨しているため、その形式を守る。Qwen3.5には公式推奨より小さい32Kの実用枠を使用し、打切りを別に報告する。

調査した別候補には [DeepSeek-R1-0528-Qwen3-8B](https://huggingface.co/deepseek-ai/DeepSeek-R1-0528-Qwen3-8B)、[OpenMath-Nemotron-7B](https://huggingface.co/nvidia/OpenMath-Nemotron-7B) がある。前者はQwen3-8Bと同じ構造で別の事後学習、後者はQwen2.5-MathをOpenMathReasoningで学習したモデル。OpenMathReasoningはAoPS由来の問題を含むため、今回のオリンピック由来の配置との重なりを特に意識する必要がある。今回の初期5候補と対照で判断し、候補を無制限に増やさない。

どの公開モデルも、公開前の人間・別モデルの数学データの影響を排除できない。この点は以前のQwen3にもある。本研究の比較対象は同じ公開初期モデルから分岐する追加学習であり、『対象の正解解法を今回新しく与えない』ことを守る。事前学習の無汚染や、対象理論を完全に知らないことを保証するモデル選定ではない。

追加検索で[Qwen3.8-27B](https://huggingface.co/Qwen/Qwen3.8-27B)も確認した。27Bの言語部にvision encoderを持つ新しい候補だが、今回の5090上のBF16学習主体という条件からは外れる。量子化や大きいGPUが必要になるため、初期の5候補には含めていない。未実測のまま小型候補より適切とは判断しない。
