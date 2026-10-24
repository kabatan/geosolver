# 12構成の短時間フルプロセス動作確認

固定した2問 AIME-2014-II-08 / HMMT-2008-FEB-GEO-09 を各構成1回、seed 601、20秒上限、1コア、最大6並列で実行した。EngineRunner→本物のworker→必要なsymbolic subprocessを使用。全24親プロセスreturncode=0、外側28秒timeout=0、全worker artifact受領。正誤・答えの集合・採点ラベルは保存していない。本計測は0回。

観測は observe/sitecustomize.py の sys.setprofile によりソースを書き換えず実施。実際の ablated() 戻り値、呼出元、通常NOMAD import成功/SciPy backend到達、ordered attempt数、残差選別、精密化平滑化・解析微分評価の到達を保存した。単に環境変数を設定しただけの確認とは区別する。

**スイッチ矛盾・停止漏れ：0件。** 各構成の未到達flagは下表およびJSONで明示。flagが0でも、対象外・早期返却・短い残時間でその機構が動かない場合がある。再試行・追加問・追加seedは行わない。

| 構成 | AIME / HMMTで実際に到達したbackend | 分岐未到達のスイッチ（2問合算） | 平滑化 / 解析J評価 / 救済（いずれか1回） |
|---|---|---|---|
| N | SciPy multistart / SciPy multistart | なし | no / no / no |
| N+2 | SciPy multistart / SciPy multistart | なし | no / no / no |
| N+3 | SciPy multistart / SciPy multistart | なし | no / no / no |
| N+4 | SciPy multistart / SciPy multistart | なし | yes / no / no |
| N+5 | algebraic prepass / SciPy multistart | なし | no / no / no |
| N+6 | SciPy multistart / SciPy multistart | なし | no / yes / no |
| C1 | NOMAD normal / NOMAD normal | なし | no / no / no |
| C2 | NOMAD normal / NOMAD normal | なし | no / no / no |
| C3 | NOMAD normal / NOMAD normal | なし | no / no / no |
| C4 | NOMAD normal / NOMAD normal | なし | yes / no / no |
| C5 | algebraic prepass / NOMAD normal | なし | yes / no / no |
| BASE | algebraic prepass / NOMAD normal | なし | yes / yes / no |

「no」は停止成功または有効だが未発火。各flagの設定値・実測分岐はsmoke-check.jsonを参照。残差書き換えと解析Jの停止時に呼出しがないこと、G3停止時の生残差選別、G2停止時のattempt数1を照合した。救済は残時間8秒以上かつ未完了等の条件付きなので、未発火をNO_RESCUE不動作とは判定しない。

診断生ログ：smoke/00〜23/{start.json,end.json,worker.json,trace/*.jsonl,stderr.log}。freeze.json に観測コードとsmoke計画の実行前hashを保存。プロファイルの負荷があるため時間を本計測や構成比較に転用しない。未発火機構の完全な動的検証までは主張しない。
