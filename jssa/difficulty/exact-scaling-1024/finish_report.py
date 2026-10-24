"""Append the completed supplement and a proposed, unexecuted timing design."""
from collections import defaultdict
import csv
import json
import os
from pathlib import Path

HERE=Path(__file__).resolve().parent
os.environ['MPLCONFIGDIR']='/tmp/exact-scaling-1024-matplotlib'
os.environ['OPENBLAS_NUM_THREADS']='1'
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    rows=list(csv.DictReader((HERE/'degrees.csv').open()))
    assert len(rows)==24
    groups=defaultdict(list)
    for r in rows: groups[r['family']].append(r)
    fig,ax=plt.subplots(figsize=(7,4),constrained_layout=True)
    styles={'circle_line':('o','#286491'),'angle_bisector':('x','#d77036'),'midpoint_control':('s','#248065')}
    for family,rr in groups.items():
        marker,color=styles[family]
        ax.plot([int(r['k']) for r in rr],[int(r['base_degree']) for r in rr],marker=marker,
                color=color,lw=1.5,label=family,markersize=6)
    ax.set_yscale('log',base=2)
    ax.set(xlabel='Construction depth k',ylabel='Ideal degree (log2 scale)',
           title='Three families: degree only, no timing benchmark')
    ax.legend();ax.grid(alpha=.2)
    ax.text(.02,.96,'Original = strong = proved minimal-polynomial degree',transform=ax.transAxes,
            va='top',fontsize=8)
    fig.savefig(HERE/'family-degrees.png',dpi=150)
    plt.close(fig)
    lines=['## 人工族（補強）','',
           '実問題表と骨子を2026-10-24 01:33:00 UTCに保存し、`progress.jsonl` に「実問題表完了」を記録した後に着手した。'
           '次数計算の実問題部分は約10分20秒、補強は約1分18秒（初回の比較検査の修正を含む）。'
           '3族×k=1〜8の24組を作成。生成スクリプト・DSL・日本語問題文・証明は [families/](families/README.md)、'
           '値は [degrees.csv](degrees.csv)。全て1個の自由スカラーtを最終座標に等置し、選択した実数の枝で答えは1個に決まる。','',
           '|族|k|選択したt|既存系次数|強化系次数|tの最小多項式次数|',
           '|---|---|---|---|---|---|',
           '|円と直線の交点の鎖|1〜8|2 cos(π/2^(k+1))|2^k|2^k|2^k|',
           '|角の二等分の鎖|1〜8|tan(π/2^(k+2))|2^k|2^k|2^k|',
           '|中点の鎖（対照）|1〜8|2^(−k)|1|1|1|','',
           '![人工族の次数](family-degrees.png)','',
           '2つの二次的な族では各kの次数は **2, 4, 8, 16, 32, 64, 128, 256**。'
           '中点の族は全て1。強化版の非零因子がどの共役でも消えない2族では、飽和しても次数が下がらない。'
           'この限定された族では2^kを確認できたが、実問題全体への一般化や時間の増加率はこの結果からは決まらない。','',
           '円の鎖は `y0=0, yi²=2+y(i−1)`。最小多項式を `P0(T)=T, Pi(T)=P(i−1)(T²−2)` と作り、'
           '素数2のEisenstein判定で既約性と次数2^iを確認した。全ての共役は−2と2の間にあり、円と交点は退化しない。',
           '二等分の鎖は `yi=y(i−1)/(1+sqrt(1+y(i−1)²))`。n=2^kとして `X^(2n)+1` の既約性と '
           '`Q(exp(iπ/(2n)))=Q(t,i)` からtの体次数nを導いた。中点の最小多項式は `2^k*T−1`。'
           '各族とも最後の座標から前段を逆に決められるので、全配置の有限性も確認できる。詳細は [証明](families/README.md)。','',
           '**角の二等分k=8では、既存・強化の次元0・次数256は計算済みだが、強化系の後続のT消去が30秒で停止した。**'
           'そのT最小多項式次数256は上の独立した厳密な導出による。消去との照合は未完として `ELIMINATION_TIMEOUT` を残した。'
           '残る23組はSingularの消去式の平方因子を除いたものと、証明した最小多項式が一致。'
           '計算秒は制限管理用に保存しただけで、時間比較には使わない。','',
           '今回の全24入力ではDSLの自由変数が常に1個で、最後の等式もtについて一次である。'
           '一般の多変数探索の難しさを再現する族ではない。完成solverの代数的前処理や定数評価が主役になる可能性もあり、'
           '段階2では採用された経路を併記する。初回の多項式照合はZZ/QQの表記差で停止したため、'
           '係数領域を揃えて保存済み出力から再開した。CASの再実行はない。','',
           '## 確認状況','',
           '`verify_artifacts.py` で全ID、出典のハッシュ、深さ、正解数・時間中央値、次数とSingular出力、'
           'ファイル上限、実問題→補強の順序を確認した。[verification.json](verification.json)。'
           '各系の入力 `.sing` と結果 `.log` / `.json` を保存。変換器・solver・元データは変更していない。'
           'git commit/push、新規solver実行、時間比較、システム導入、昇格コマンドは行っていない。','',
           '## 段階2（時間比較）の推奨設計案','',
           '以下は今後の実行案で、今回は実行していない。予測・成功基準・打切り規則は、依頼者が固定してから開始する。','',
           '|族|主比較のk|補足|',
           '|---|---|---|',
           '|円と直線の交点の鎖|1〜8|全段で次数とT消去が確認済み|',
           '|角の二等分の鎖|1〜7|k=8は消去30秒打切りの別枠として事前指定して含める|',
           '|中点の鎖|1〜8|次数を増やさず深さだけ増やす対照|','',
           '1. このDSL・変換器・BASE相当solver・採点器のハッシュを固定する。厳密な答えは最小多項式と実根の区別まで指定する。'
           '円の族は最大の実根、角の族は最小の正の実根、中点は有理数。共役全体を正解集合として採点しない。',
           '2. 同じ機械で、他の計算と重ならない期間を確保し、1実行1コア・最大4並列・メモリ上限を揃える。'
           '全体壁時間は例えば180秒、仮想メモリは2 GiB。各方式の変換・起動・候補生成・復元・検証を全てこの枠に含める。'
           '方法・k・反復の実行順は事前に乱数seedを固定して混ぜる。',
           '3. 既存msolve経路、強化Singular経路、完成solverの3方式を同じ入力・同じ採点で比較する。'
           'msolveは1スレッド、元のfresh変換を使用。決定的な厳密法は各3反復、solverは例えばseed0〜4。'
           '全配置を列挙する経路とTへ射影する経路を区別して記録し、単なる次数計算を求解時間に代用しない。',
           '4. 主指標は正しいtの同定・最終検証までの全体時間と成功率。別列に変換、代数計算、探索、精密化、同定、検証の時間と採用経路を残す。'
           '代数次数や係数長がsolverの既定の同定上限を超える場合は、そのまま理由を記録する。'
           '数値的な図の実現と厳密な答えの同定を分け、前者だけを「解けた」としない。',
           '5. 各kの全試行・失敗・打切りを残し、正解試行の中央値だけで線形/指数増加を主張しない。'
           '全体時間に加えて時間内成功率と打切り数を表示する。`秒=a+b k` と `log2(秒)=a+b k` は記述モデルとして並べ、'
           '起動時間の床、係数のビット長、必要精度、前処理の効果を確認する。次数2^kだけから時間2^kを仮定しない。','']
    text=(HERE/'answer.md').read_text().split('<!-- FAMILIES -->')[0]
    (HERE/'answer.md').write_text(text+'<!-- FAMILIES -->\n'+'\n'.join(lines))


if __name__=='__main__':
    main()
