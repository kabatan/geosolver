"""Scientific plots from saved CSV/JSON only; run with system Python/matplotlib."""
import csv
import json
import os
from pathlib import Path

OUT=Path(__file__).resolve().parent
os.environ['MPLCONFIGDIR']=str(OUT/'plot-cache')
os.environ['OPENBLAS_NUM_THREADS']='1'
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

rows=list(csv.DictReader((OUT/'uncertainty.csv').open()))
stats=json.loads((OUT/'local-summary.json').read_text())['problems']
plt.rcParams.update({'font.size':9,'axes.spines.top':False,'axes.spines.right':False,
                     'font.family':'DejaVu Sans','svg.fonttype':'none'})
fig,axes=plt.subplots(4,3,figsize=(12,11.5),sharex=True,sharey=True)
for ax,st in zip(axes.ravel(),stats):
    rs=[r for r in rows if r['id']==st['id']]
    x=np.array([float(r['epsilon']) for r in rs]); y=np.array([float(r['f']) for r in rs])
    root=np.array([float(r['f_root']) for r in rs]);low=np.array([float(r['wilson_low']) for r in rs]);high=np.array([float(r['wilson_high']) for r in rs])
    ax.set_xscale('log');ax.set_yscale('log')
    ax.axvspan(1e-15,1e-12,color='#eef1f5',zorder=0)
    ax.fill_between(x,np.maximum(low,1e-5),high,color='#3269a8',alpha=.14)
    ax.plot(x,np.where(y>0,y,np.nan),'o-',color='#3269a8',ms=3,lw=1.3,label='Any outcome change')
    ax.plot(x,np.where(root>0,root,np.nan),'s--',color='#cf6b27',ms=3,lw=1,label='Known root to root')
    ax.scatter(x[y==0],np.full(sum(y==0),.0016),marker='v',s=13,color='#3269a8',clip_on=False,label='Zero / 256')
    ax.set_title(st['id'],loc='left',fontsize=10,fontweight='bold')
    f=st['alpha_raw'];alpha='not identifiable' if f is None else f"{f['alpha']:.3f} (R²={f['r2']:.2f})"
    ax.text(.03,.94,'raw slope: '+alpha,transform=ax.transAxes,va='top',fontsize=8)
    ax.text(.03,.82,f"1-ulp changes: {st['ulp_changes']}/256",transform=ax.transAxes,va='top',fontsize=8)
    ax.grid(alpha=.15,which='major');ax.set_ylim(.0013,1.2);ax.set_xlim(8e-16,.014)
    ax.set_xticks([1e-15,1e-12,1e-9,1e-6,1e-3]);ax.set_yticks([.01,.1,1])
for ax in axes[-1]:ax.set_xlabel('Perturbation ε (normalized box-width coordinates)')
for ax in axes[:,0]:ax.set_ylabel('Fraction with different destination')
fig.suptitle('Q34 · Fixed-neighborhood uncertainty curves, frozen LM (K=80)',fontsize=16,x=.06,ha='left',y=.988)
handles,labels=axes[0,0].get_legend_handles_labels()
fig.legend(handles,labels,ncol=3,loc='upper center',bbox_to_anchor=(.51,.956),frameon=False)
fig.text(.06,.015,'256 paired starts / problem; shaded band: pointwise Wilson 95% interval. Triangles mark zero counts, not positive estimates.\nGray region is used to diagnose a numerical floor. Raw slopes are descriptive, not certified fractal dimensions.',fontsize=9)
fig.tight_layout(rect=(0,.055,1,.925),h_pad=2,w_pad=1.8)
fig.savefig(OUT/'uncertainty-curves.png',dpi=170)
fig.savefig(OUT/'uncertainty-curves.svg')
plt.close(fig)
