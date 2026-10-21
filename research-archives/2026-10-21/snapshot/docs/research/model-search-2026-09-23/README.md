# モデル探索・実測（2026-09-23）

実行中。最終的な推薦と採点は REPORT.md にまとめる。途中の集計を確定結果として扱わない。

- [比較条件・採点](PROTOCOL.md)
- [候補と公式資料](CANDIDATES.md)
- [実装上の確認](IMPLEMENTATION_NOTES.md)
- [一次課題](jobs.json)、[事前固定した追加確認](confirmation-jobs.json)
- [個別採点](grades.json)、[集計](summary.json)、[生成費用](costs.json)

保存先は `qwen/.runtime/model_search_20260923_v2/`。初期sampling pilotと使い捨てのLoRA技術確認は `qwen/.runtime/model_search_20260923/`。研究の学習用データや既存checkpointを変更しない。

集計の再生成:

```bash
python3 docs/research/model-search-2026-09-23/audit.py
python3 docs/research/model-search-2026-09-23/costs.py
```

推論driverは既存のreceiptを上書きしない。すでに実行したディレクトリへ再実行するためにreceiptを削除せず、独立したrunとして保存すること。

```bash
PYTHONPATH=. qwen/.runtime/vllm-venv/bin/python docs/research/model-search-2026-09-23/run_v2.py
```

モデルごとに単独プロセスを使い、GPU上で同時に複数モデルを動かさない。公式revision、chat template、問題全文、sampling、token列、終了理由を保存する。自動の数値一致だけで正解とは採点せず、最終答案の核心的な論証を読む。内部thinking全行の形式検証を実施したものではない。
