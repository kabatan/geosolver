"""Static research figure from completed offline scores, no additional search."""
import csv
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
OUT=Path(__file__).resolve().parent

def main():
    summary=json.loads((OUT/'summary.json').read_text()); assert summary['complete']
    rows=list(csv.DictReader((OUT/'success-matrix.csv').open()))
    ARMS=list(rows[0])[4:]
    data=np.array([[float(r[a]) for a in ARMS] for r in rows])
    fig,ax=plt.subplots(figsize=(12,10.5),layout='constrained')
    im=ax.imshow(data,vmin=0,vmax=1,cmap='Blues',aspect='auto')
    ax.set_xticks(range(len(ARMS)),ARMS); ax.xaxis.tick_top()
    ax.set_yticks(range(len(rows)),[r['id'] for r in rows],fontsize=8)
    for i in range(len(rows)):
        for j in range(len(ARMS)):
            ax.text(j,i,str(round(data[i,j]*16)),ha='center',va='center',fontsize=8,color='white' if data[i,j]>.55 else '#153451')
    ax.axhline(20.5,color='#b34a35',lw=2)
    ax.set_title('Standalone methods and interventions: successful starts out of 16\n21 historical zero-hit cases (top) and 7 controls (bottom)',pad=28,fontsize=12)
    fig.colorbar(im,ax=ax,shrink=.6,label='Success probability estimate')
    fig.savefig(OUT/'success-matrix.png',dpi=170)
    fig.savefig(OUT/'success-matrix.svg')
    plt.close(fig)
    groups=json.loads((OUT/'group-summary.json').read_text())
    fig,axs=plt.subplots(1,2,figsize=(12,4),layout='constrained',sharey=True)
    for ax,group in zip(axs,['hard','control']):
        g={r['arm']:r for r in groups if r['group']==group and r['seed']==0}
        x=np.arange(len(ARMS)); ax.bar(x-.18,[g[a]['p'] for a in ARMS],.36,label='Strict hit + answer check',color='#24659e')
        ax.bar(x+.18,[g[a]['coarse']/g[a]['n'] for a in ARMS],.36,label='Feasible residual <= 1e-4',color='#e6a24c')
        ax.set_xticks(x,ARMS,rotation=45,ha='right'); ax.set_ylim(0,1); ax.set_title('Historical zero-hit (21)' if group=='hard' else 'Controls (7)'); ax.grid(axis='y',alpha=.2)
    axs[0].set_ylabel('Fraction of starts')
    handles,labels=axs[1].get_legend_handles_labels()
    fig.legend(handles,labels,loc='outside upper center',ncol=2,fontsize=8)
    fig.savefig(OUT/'strict-and-coarse.png',dpi=170); plt.close(fig)
    print('figures saved')

if __name__=='__main__': main()
