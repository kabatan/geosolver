"""Render measured data with system Python/matplotlib, never the solver env."""
from __future__ import annotations

import ast
import gzip
import json
import os
import sys

import coordinates as C

os.environ['MPLCONFIGDIR']=str(C.EXTERNAL/'mpl-cache')
os.environ['MPLBACKEND']='Agg'
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap, BoundaryNorm

plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'savefig.facecolor':'white'})


def load(path):return json.loads(path.read_text())


def plots(stage):
    summary=load(C.BASE/f'{stage}-summary.json');inputs=load(C.BASE/'inputs.json')
    probs={p['id']:p for p in summary['problems']}
    order=[v['name'] for v in C.variants() if v['name'] in probs[inputs[0]['id']]['counts_by_variant']]
    matrix=np.asarray([[probs[p['id']]['counts_by_variant'][v] for v in order] for p in inputs])
    labels=[v.replace('scale_','').replace('translate_1000000','shift 1e6').replace('translate_1000','shift 1e3').replace('translate_1','shift 1').replace('leaf_centroid','centroid').replace('last_leaf','last point').replace('identity_rewrite','identity') for v in order]
    fig,ax=plt.subplots(figsize=(max(9,len(order)*.43+4),10))
    cm=ListedColormap(['#eee6e2','#e9ad46','#257867']);norm=BoundaryNorm([-.5,.5,1.5,2.5],cm.N)
    ax.imshow(matrix,cmap=cm,norm=norm,aspect='auto')
    ax.set_xticks(range(len(order)),labels,rotation=60,ha='right')
    ax.set_yticks(range(len(inputs)),[p['id'] for p in inputs],fontsize=8)
    ax.axhline(11.5,color='#263238',lw=1.3)
    for y in range(matrix.shape[0]):
        for x in range(matrix.shape[1]):ax.text(x,y,str(matrix[y,x]),ha='center',va='center',fontsize=8,color='white' if matrix[y,x]==2 else '#333333')
    ax.set_title(f'Q43a — exact answer set recovered in 0 / 1 / 2 seeds\n{stage}: {summary["jobs"]} runs; all failures retained',loc='left',pad=16)
    ax.set_xlabel('Scale columns: k in 10^k. Other columns: geometric coordinate frame.')
    fig.tight_layout();fig.savefig(C.BASE/f'{stage}-matrix.png',dpi=160);fig.savefig(C.BASE/f'{stage}-matrix.svg');plt.close(fig)
    scales=[g for g in summary['groups'] if g['group']=='all' and g['variant'].startswith('scale_')]
    if len(scales)==13:
        scales.sort(key=lambda r:int(r['variant'].split('_')[1]))
        fig,axs=plt.subplots(1,2,figsize=(11,4.3));seeds=list(scales[0]['by_seed'])
        for i,s in enumerate(seeds):
            axs[0].plot(range(-6,7),[r['by_seed'][s]['correct'] for r in scales],marker='o',lw=1.8,label=f'seed {s}',alpha=.85)
        axs[0].set(ylim=(0,24.8),yticks=range(0,25,4),xticks=range(-6,7),xlabel='k: geometry scaled by 10^k',ylabel='Correct answer sets / 24 problems')
        axs[0].legend(frameon=False,fontsize=9);axs[0].grid(axis='y',alpha=.2)
        axs[1].plot(range(-6,7),[r['restricted_mean_cost'] for r in scales],color='#775293',marker='o')
        axs[1].set(xticks=range(-6,7),xlabel='k: geometry scaled by 10^k',ylabel='Restricted mean cost (seconds)')
        axs[1].grid(axis='y',alpha=.2)
        fig.suptitle('Same mathematical problem; answer units and scalar parameters held fixed',ha='left',x=.04)
        fig.text(.04,.01,'Cost = observed elapsed time for a correct set; full time budget for every unsuccessful run.',fontsize=9,color='#555555')
        fig.tight_layout(rect=(0,.05,1,.94));fig.savefig(C.BASE/f'{stage}-scale-response.png',dpi=160);fig.savefig(C.BASE/f'{stage}-scale-response.svg');plt.close(fig)


def diagram_examples():
    choices=load(C.BASE/'figure-examples.json');inputs={i['id']:i for i in load(C.BASE/'inputs.json')}
    figs={}
    for stage in {c['stage'] for c in choices}:
        with gzip.open(C.EXTERNAL/stage/'figures.json.gz','rt') as f:figs[stage]=json.load(f)
    fig,axs=plt.subplots(1,len(choices),figsize=(5*len(choices),5),squeeze=False)
    for ax,c in zip(axs[0],choices,strict=True):
        found=next(r for r in figs[c['stage']] if all(r[k]==v for k,v in c.items() if k not in ('caption','stage')))
        points=found['points'];inp=inputs[found['id']]
        polygons=[]
        for cond in inp['dsl']['conditions']:
            if 'predicate' not in cond:continue
            n=ast.parse(cond['predicate'],mode='eval').body
            if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in ('ConvexPolygon','SimplePolygon') and isinstance(n.args[0],ast.List):
                names=[p.id for p in n.args[0].elts if isinstance(p,ast.Name)]
                if names and all(p in points for p in names):polygons.append(names)
        for poly in polygons:
            xy=np.asarray([points[p] for p in poly+[poly[0]]]);ax.plot(xy[:,0],xy[:,1],color='#a4b8b1',lw=1.2,zorder=1)
        xy=np.asarray(list(points.values()));ax.scatter(xy[:,0],xy[:,1],color='#257867',s=20,zorder=3)
        for name,(x,y) in points.items():ax.annotate(name,(x,y),xytext=(4,5),textcoords='offset points',fontsize=8)
        ax.set_aspect('equal',adjustable='datalim');ax.margins(.17);ax.grid(alpha=.16)
        ax.set_title(c.get('caption',found['variant'])+f'\nanswer = {found["answer"]:.9g}',fontsize=11)
        ax.set_xlabel('Original length units');ax.set_ylabel('Original length units')
    fig.suptitle(choices[0]['id']+' — accepted figures, mapped back to the original frame',fontsize=13)
    fig.tight_layout();fig.savefig(C.BASE/'found-figures.png',dpi=170);fig.savefig(C.BASE/'found-figures.svg');plt.close(fig)


if __name__=='__main__':
    if sys.argv[1]=='figures':diagram_examples()
    else:plots(sys.argv[1])
