# 厳密解法との比較

DSLを座標の多項式系に自動変換し（`algebraize.py`）、msolve（または解集合が有限でないときはSingularの消去）で解きます。得られた実数解はGeoSolverの最終検証器で元のDSLに照らして絞り込みます（`run_exact.py`）。`lift_check.py`はGeoSolverの配置が多項式系を満たすことを確かめます。

```bash
sudo apt-get install msolve singular
python run_exact.py CASE_ID fresh msolve 300 out.json
./batch.sh OUTDIR fresh msolve 60 4 < ids.txt
python select_cases.py OUTDIR 10 > sample.txt
./run_geosolver.sh GSDIR 4 < sample.txt
```

`inline`モード（有理式のまま埋め込む表し方）は未完成です。
