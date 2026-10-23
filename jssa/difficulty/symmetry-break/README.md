# Q41 段階1

solver・局所探索は未実行。Claudeのcommit・push確認と、別タスクでの実行許可を待つ。実行用ランナーは含めない。

- [prediction.md](prediction.md)：選択、操作、数値予言、反証条件、解析、不可の線、理論の限界。
- [measurement-plan.md](measurement-plan.md)：後続段階の測定仕様。
- [selection.csv](selection.csv)／[selected-problems.txt](selected-problems.txt)：固定40問。適用可23（等辺17、鏡映・点対称6）、不可17。不可も分母に残す。
- [census.json](census.json)：開発323問の全監査。候補45、抽出40。未検出は非対称の証明ではない。
- [selection.json](selection.json)／`dsl/`：全armの差分・可否・hash、生成した178個のDSL（元版40＋適用可23×6）。
- [static-notes.md](static-notes.md)：封印前の修正。数値予言の達成不能な閾値を静的点検後に修正した経緯も明記。
- [prediction.lock.json](prediction.lock.json)：UTCとSHA-256、関連成果物のhash。ローカル封印であり、commit・pushの証拠ではない。

**次の2コマンドは静的照合だけ**で、ファイルを書かず、solverをimportも実行もしない。

```sh
python3 jssa/difficulty/symmetry-break/prepare_static.py --check
python3 jssa/difficulty/symmetry-break/seal_stage1.py --check
```

静的検査はJSON・AST・名前参照・差分・hashまで。solverでの型検査・lowering、解の存在、実際の対称性の破れ、p・時間・特異値は未検証。`answer.md`は結果段階で作り、冒頭に指定の4基準と追加3判定を置く。
