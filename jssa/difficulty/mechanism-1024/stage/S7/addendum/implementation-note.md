# 実装修正の記録

初回のrun.pyは30問を保存した後、AIME-2010-II-09の段階(1)の空行列 `[]` を `mp.matrix([])` として読み込む処理でIndexErrorとなった。HMMT-2013-FEB-GEO-08も同じ0行×1列の形状である。数値閾値・対象・幅・精度・残差定義は変更しない。

元のREADME.md、protocol.json、スクリプトとpre-run-hashes.jsonは変更せず保持する。worker-v2.pyは空の保存行列の列数を保持して `mp.matrix(0,n)` として読む。verify-v2.pyも同じ修正。run-v2.pyはworker-v2.pyを起動し、既存の完了結果は保持する。修正コードのhashは再開前のimplementation-amendment.jsonに固定する。

実際の再現コマンド：`/home/kabatan/work/solver/.venv/bin/python run-v2.py` → `report.py` → `verify-v2.py`。修正は数値結果を変えるものではなく空行列のシリアライズへの対応である。初回完了結果もすべて同一の数値整合性検証を受ける。
