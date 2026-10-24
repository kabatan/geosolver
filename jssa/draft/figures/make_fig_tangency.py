# 図2：接する条件を含む12問、同じ候補から精密化した目標値の正しい桁数（事前登録10、S3）
import csv, re, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
font_manager.fontManager.addfont('/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf')
plt.rcParams.update({'font.family':'IPAGothic','font.size':9,'figure.facecolor':'white','axes.facecolor':'white'})
rows=list(csv.DictReader(open('../../difficulty/mechanism-1024/stage/S3/run/per-problem.csv')))
def name(c):
    m=re.match(r'(?i)aime-(\d+)-(I+|\d)-(\d+)',c)
    if m:
        k={'1':'I','2':'II'}.get(m.group(2),m.group(2)); return f'AIME {m.group(1)} {k}-{int(m.group(3))}'
    m=re.match(r'HMMT-(\d+)-FEB-GEO-(\d+)',c)
    if m: return f'HMMT {m.group(1)} 幾何{int(m.group(2))}'
    m=re.match(r'JMO-(\d+)-PRE-(\d+)',c)
    return f'JMO {m.group(1)} 予選{int(m.group(2))}'
for r in rows:
    for k in 'T0','T1','T2': r[k]=max(0,float(r[k+'_best_error_digits']))
rows.sort(key=lambda r:(r['T2']-r['T0'],r['T2']))
fig,ax=plt.subplots(figsize=(6.4,4.1))
y=list(range(len(rows)))
for i,r in enumerate(rows):
    if 'HMMT-2022' not in r['case_id']: ax.plot([min(r['T0'],r['T1'],r['T2']),max(r['T0'],r['T1'],r['T2'])],[i,i],color='#d0d0d0',lw=2,zorder=1)
sty=[('T0','元の残差','#d95f02','o'),('T1','接点を使わない符号付き残差','#7a7a7a','s'),('T2','接点を使う残差（既定）','#1b6ca8','D')]
fail=lambda r:'HMMT-2022' in r['case_id']
for k,lab,c,m in sty:
    ax.scatter([r[k] if not fail(r) else float('nan') for r in rows],y,s=40,color=c,marker=m,label=lab,zorder=3 if k=='T2' else 2,edgecolor='white',linewidth=1.2)
ax.set_yticks(y); ax.set_yticklabels([name(r['case_id']) for r in rows])
ax.set_xlabel('目標値の正しい桁数（精密化直後の最良候補、90秒）'); ax.set_xlim(-10,520)
for s in ['top','right']: ax.spines[s].set_visible(False)
ax.grid(axis='x',color='#eeeeee'); ax.set_axisbelow(True)
ax.legend(loc='lower center',bbox_to_anchor=(0.42,1.0),ncol=3,frameon=False,fontsize=8,handletextpad=0.3,columnspacing=1.0)
i=[k for k,r in enumerate(rows) if 'HMMT-2022' in r['case_id']][0]
ax.text(5,i,'3通りとも候補が通らない（桁数なし）',va='center',fontsize=8,color='#555')
fig.tight_layout(); fig.savefig('fig2_tangency_digits.png',dpi=200)
