# 図2：接する条件を含む12問、同じ候補から精密化した目標値の正しい桁数（S1、事前登録7）
import csv, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
font_manager.fontManager.addfont('/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf')
plt.rcParams.update({'font.family':'IPAGothic','font.size':9,'figure.facecolor':'white','axes.facecolor':'white'})
rows=list(csv.DictReader(open('../../difficulty/mechanism-1024/stage/S1/per-problem.csv')))
import re
def name(c):
    m=re.match(r'(?i)aime-(\d+)-(I+|\d)-(\d+)',c)
    if m:
        k={'1':'I','2':'II'}.get(m.group(2),m.group(2)); return f'AIME {m.group(1)} {k}-{int(m.group(3))}'
    m=re.match(r'HMMT-(\d+)-FEB-GEO-(\d+)',c)
    if m: return f'HMMT {m.group(1)} 幾何{int(m.group(2))}'
    m=re.match(r'JMO-(\d+)-PRE-(\d+)',c)
    return f'JMO {m.group(1)} 予選{int(m.group(2))}'
for r in rows:
    r['a']=max(0,float(r['BASE_best_error_digits'])); r['n']=max(0,float(r['NO_RESIDUAL_REWRITE_best_error_digits']))
rows.sort(key=lambda r:(r['a']-r['n']))
fig,ax=plt.subplots(figsize=(6.4,3.9))
y=range(len(rows))
for i,r in enumerate(rows):
    ax.plot([r['n'],r['a']],[i,i],color='#c9c9c9',lw=2,zorder=1)
ax.scatter([r['n'] for r in rows],y,s=46,color='#d95f02',label='書き換えなし',zorder=2,edgecolor='white',linewidth=1.5)
ax.scatter([r['a'] for r in rows],y,s=46,color='#1b6ca8',label='書き換えあり（既定）',zorder=3,edgecolor='white',linewidth=1.5)
ax.set_yticks(list(y)); ax.set_yticklabels([name(r['case_id']) for r in rows])
ax.set_xlabel('目標値の正しい桁数（精密化直後の最良候補、90秒）'); ax.set_xlim(-10,520)
for s in ['top','right']: ax.spines[s].set_visible(False)
ax.grid(axis='x',color='#eeeeee'); ax.set_axisbelow(True)
ax.legend(loc='lower center',bbox_to_anchor=(0.45,1.0),ncol=2,frameon=False)
i=[k for k,r in enumerate(rows) if 'HMMT-2022' in r['case_id']][0]
ax.annotate('両方で候補が通らない',(0,i),xytext=(30,i),va='center',fontsize=8,color='#555')
fig.tight_layout(); fig.savefig('fig2_tangency_digits.png',dpi=200)
