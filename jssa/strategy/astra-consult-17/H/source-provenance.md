# 入力と実行条件

- 開始時の作業ツリー HEAD: `e11b5c8a`。最終点検時は別作業により `86c06e1234bbfba71151f8e3621c5ab8bc6deb0e`。
  両者間で `src/`, `benchmarks/cases.jsonl`, `jssa/difficulty/probe_basins.py` に差分がないことを確認した。
  本担当はgitの変更操作を行っていない。問題DSLはこの作業ツリーの `benchmarks/cases.jsonl`。
- 比較CSV等: branch `claude/project-thread-nycxfb`, commit `c0bd76dba24b808866ca6f8b96bffda742d08320` の `jssa/results/exact-comparison-pc-20261022/`。
  詳細なファイルURLとblob SHAは `sources/provenance.json`。
- 旧証明書の説明・集計・診断: branch `claude/project-thread-ulho54`, commit `d5c9614c629d259ea13e1e45156e4692fa0a85c1` の `jssa/theory/posdim-identities/`。
  `README.md`, `certify.py`, `components.py`, `gauge.py`, `tabulate.py` と、`out/batch-summary.csv`, `out/components.json`, `out/gauge.json` を小さい読み取り用コピーとして保存した。
- 多項式変換コード: branch `claude/project-thread-fos2rk`, commit `b0575a09e19c40bbe4b0e542278a6aceeea78c59` の `benchmarks/exact_comparison/{algebraize.py,run_exact.py}`。
- リモートの読み取りは GitHub connector 経由。git の fetch/checkout/commit/push は行っていない。
- 局所探索の保存済終点は `jssa/difficulty/minima/{raw-323,raw-323-seed1}/`。
  事後診断では `jssa/difficulty/start-feasibility-1023/{seed2-plain,seed2-feasible}/` の保存済hitも使用。
  個々の入力の出所と試行番号は各JSONに残した。
- Python: `/home/kabatan/work/solver/.venv/bin/python -B`。追加インストールなし。
  凍結srcを読み取り専用で import。新規成果物と小さいコピーは全て H/ 内。
  数値診断は2プロセス、BLAS各1スレッド。証明書検算は1プロセス。
- Singular/msolve の実行ファイルは今回の環境では見つからなかった。旧結果の再集計と
  SymPyによる簡約系の厳密恒等式検算を行い、両ソフトの新規一括実験はしていない。
- コピー・問題DSL等の SHA256 は `input-hashes.json`。旧巨大証明書は取得・再生成していない。

再実行（リポジトリルートから、上から順に。各コマンドはH/内だけへ書く）：

```bash
/home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-17/H/measure.py --workers 2
/home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-17/H/diagnose.py --workers 2
/home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-17/H/new_certificates.py
/home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-17/H/analytic_audit.py
/home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-17/H/build_report_data.py
/home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-17/H/verify.py
```

`measure.py` は初回基準、`diagnose.py` は結果を見た後の追加診断であり、後者を前者の成功に取り替えない。
再実行は各段階のファイルを上書きするので、比較する場合はこの成果物を保存してから行う。
