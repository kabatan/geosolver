"""Exploratory real S3 monodromy in a 26-link mechanism.

This is a discovery/verification pilot, not a call to the repository solver.
The rational map and component formulae are analytic. Numerical root matching,
constraint residuals and singular values are sampled, not interval certificates.
Run with .venv/bin/python research-directions-20261002/round2-fresh/rational_linkage.py
"""
from __future__ import annotations

import itertools
import json
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = Path(__file__).resolve().parent
POLES = np.array([-1., 0., 1.])
K = 5.
LONG = 9.
SHORT = np.sqrt(LONG**2-K)
ARM = 12.
W0 = 2.2j
RADIUS = .32
PERMS = list(itertools.permutations(range(3)))


def inverse_roots(w):
    q = np.conj(w)
    return np.roots([q, -3., -q, 1.])


HOME = np.array(sorted(inverse_roots(W0), key=lambda z: z.real))
CRIT_Z = 3**(-.25)*np.exp(1j*(np.pi/4+np.arange(4)*np.pi/2))
CRIT_W = np.conj((3*CRIT_Z**2-1)/(CRIT_Z**3-CRIT_Z))


def loop(b, n=900):
    start = b + RADIUS*(W0-b)/abs(W0-b)
    a = np.angle(start-b)
    m = n//9
    return np.r_[np.linspace(W0, start, m, endpoint=False),
                 b+RADIUS*np.exp(1j*np.linspace(a, a+2*np.pi, n-2*m, endpoint=False)),
                 np.linspace(start, W0, m+1)]


def track(path):
    z = HOME.copy()
    hist = [z.copy()]
    max_step = 0.
    for w in path[1:]:
        roots = inverse_roots(w)
        p = min(PERMS, key=lambda p: np.sum(abs(roots[list(p)]-z)**2))
        nxt = roots[list(p)]
        max_step = max(max_step, float(np.max(abs(nxt-z))))
        hist.append(nxt.copy())
        z = nxt
    perm = np.argmin(abs(z[:,None]-HOME[None,:]), axis=1)
    return np.array(hist), perm.tolist(), max_step


def points(z):
    """One assembly branch of three inversors and two weighted pantographs."""
    p = {"P": complex(z)}
    for j, c in enumerate(POLES):
        v = z-c
        q = K/np.conj(v)
        mid = (v+q)/2
        h = np.sqrt(LONG**2-abs(mid)**2)
        side = 1j*v/abs(v)*h
        p.update({f"O{j}": complex(c), f"Q{j}": complex(c+q),
                  f"A{j}": complex(c+mid+side), f"C{j}": complex(c+mid-side)})
    # A pantograph with alpha produces (1-alpha)*U+alpha*V.
    for j, u, v, alpha in [(0, "Q0", "Q1", .5), (1, "D0", "Q2", 1/3)]:
        U, V = p[u], p[v]
        d = abs(V-U)
        B = (U+V)/2 + 1j*(V-U)/d*np.sqrt(ARM**2-d*d/4)
        C = (1-alpha)*U+alpha*B
        E = (1-alpha)*B+alpha*V
        D = C+E-B
        p.update({f"B{j}": B, f"H{j}": C, f"E{j}": E, f"D{j}": D})
    return p


FIXED = [f"O{j}" for j in range(3)]
VARIABLES = [k for k in points(HOME[0]) if k not in FIXED]
INDEX = {k: 2*j for j,k in enumerate(VARIABLES)}


def rows(p, w, length_errors=None, ratio_errors=None):
    """36 residuals and their analytic 36x36 Jacobian, output held at k*w/3."""
    residual, jac = [], []
    length_index = 0
    def length(a,b,L):
        nonlocal length_index
        if length_errors is not None: L *= 1+length_errors[length_index]
        length_index += 1
        v = p[a]-p[b]
        row = np.zeros(2*len(VARIABLES))
        xy = np.array([v.real,v.imag])/L
        if a in INDEX: row[INDEX[a]:INDEX[a]+2] += xy
        if b in INDEX: row[INDEX[b]:INDEX[b]+2] -= xy
        residual.append((abs(v)**2-L*L)/(2*L)); jac.append(row)
    def linear(terms, target=0j):
        v = sum(coef*p[name] for name,coef in terms)-target
        for xy in range(2):
            row = np.zeros(2*len(VARIABLES))
            for name,coef in terms:
                if name in INDEX: row[INDEX[name]+xy] += coef
            residual.append(v.real if xy==0 else v.imag); jac.append(row)
    for j in range(3):
        for x in (f"A{j}",f"C{j}"):
            length(f"O{j}",x,LONG)
            length("P",x,SHORT)
            length(f"Q{j}",x,SHORT)
    for j,u,v,alpha in [(0,"Q0","Q1",.5),(1,"D0","Q2",1/3)]:
        alpha_u = alpha if ratio_errors is None else alpha+ratio_errors[2*j]
        alpha_v = alpha if ratio_errors is None else alpha+ratio_errors[2*j+1]
        length(u,f"B{j}",ARM)
        linear([(f"H{j}",1),(u,-(1-alpha_u)),(f"B{j}",-alpha_u)])
        length(f"B{j}",v,ARM)
        linear([(f"E{j}",1),(f"B{j}",-(1-alpha_v)),(v,-alpha_v)])
        length(f"H{j}",f"D{j}",alpha*ARM)
        length(f"E{j}",f"D{j}",(1-alpha)*ARM)
    linear([("D1",1)],K*w/3)
    return np.array(residual),np.array(jac)


def rods():
    r=[]
    for j in range(3):
        for x in [f"A{j}",f"C{j}"]:
            r.extend([[f"O{j}",x],["P",x],[f"Q{j}",x]])
    for j,u,v in [(0,"Q0","Q1"),(1,"D0","Q2")]:
        r.extend([[u,f"H{j}",f"B{j}"],[f"B{j}",f"E{j}",v],
                  [f"H{j}",f"D{j}"],[f"E{j}",f"D{j}"]])
    return r


def encode(p):
    return {name:[float(z.real),float(z.imag)] for name,z in p.items()}


def main():
    paths = {"A":loop(CRIT_W[1]),"B":loop(CRIT_W[0])}
    results={}; tracks={}; payload={}
    for name,path in paths.items():
        hist,perm,maxstep=track(path); tracks[name]=hist
        smins=[]; maxres=0.; outputerr=0.; rows_evaluated=0
        for i in range(0,len(path),3):
            for j in range(3):
                p=points(hist[i,j]); residual,J=rows(p,path[i]); rows_evaluated+=1
                maxres=max(maxres,float(np.max(abs(residual))))
                smins.append(float(np.linalg.svd(J,compute_uv=False)[-1]))
                outputerr=max(outputerr,float(abs(p['D1']-K*path[i]/3)))
        pole_dist=abs(hist[:,:,None]-POLES)
        derivative=abs(np.sum(-1/(hist[:,:,None]-POLES)**2,axis=2))
        results[name]={"permutation_zero_based":perm,"steps":len(path)-1,
             "max_matched_step":maxstep,
             "min_state_separation":float(min(np.min(abs(hist[:,i]-hist[:,j])) for i,j in itertools.combinations(range(3),2))),
             "min_pole_distance":float(np.min(pole_dist)),"max_pole_distance":float(np.max(pole_dist)),
             "min_rational_derivative_abs":float(np.min(derivative)),
             "sampled_full_jacobian_min_sigma":min(smins),
             "jacobian_configurations_checked":rows_evaluated,
             "max_normalized_bar_residual":maxres,"max_output_error":outputerr}
        payload[name]={"perm":perm,"frames":[{"w":[float(path[i].real),float(path[i].imag)],
             "states":[encode(points(hist[i,j])) for j in range(3)]} for i in range(0,len(path),6)]}
    a,b=np.array(results['A']['permutation_zero_based']),np.array(results['B']['permutation_zero_based'])
    report={"map":"w = sum(1/(conj(z)-c) for c in [-1,0,1]); physical output D1=5*w/3",
            "home_state":[[float(z.real),float(z.imag)] for z in HOME],
            "home_control":[W0.real,W0.imag],"critical_controls":[[float(z.real),float(z.imag)] for z in CRIT_W],
            "links":26,"joints":21,"fixed_joints":3,"moving_joints":18,
            "loops":results,"A_then_B":b[a].tolist(),"B_then_A":a[b].tolist(),
            "limitations":["Sampled numerical checks; no interval certificate.",
                "No physical fabrication or rod collision/layer-routing validation.",
                "This script uses an analytic discovery model, not the repository solver.",
                "S3 acts on three reachable states in one initialized component; many other inverse-cell assemblies exist."]}
    (OUT/'rational_linkage_result.json').write_text(json.dumps(report,indent=2)+'\n')
    (OUT/'rational_linkage_animation.json').write_text(json.dumps({"rods":rods(),"fixed":FIXED,"data":payload}))
    (OUT/'rational_linkage_graph.json').write_text(json.dumps({"rods":rods(),"fixed":FIXED,"variables":VARIABLES,
               "inversor_long":LONG,"inversor_short":float(SHORT),"inversion_constant":K,"pantograph_arms":ARM,
               "home_configurations":[encode(points(z)) for z in HOME]},indent=2)+'\n')
    fig,axes=plt.subplots(1,2,figsize=(11,5))
    colors=['#e76f51','#2a9d8f','#457b9d']
    for name,path in paths.items():
        axes[0].plot(path.real,path.imag,label=f'Loop {name}',lw=2)
        for j in range(3):
            z=tracks[name][:,j]
            axes[1].plot(z.real,z.imag,c=colors[j],alpha=.7,ls='-' if name=='A' else '--')
    axes[0].scatter(CRIT_W[:2].real,CRIT_W[:2].imag,c='black',marker='x',s=60,label='Branch values')
    axes[0].scatter([W0.real],[W0.imag],c='black',s=30,label='Home')
    axes[0].set_title('Same control returns home');axes[0].legend()
    for j,z in enumerate(HOME):
        axes[1].scatter([z.real],[z.imag],c=[colors[j]],s=60)
        axes[1].annotate(str(j+1),(z.real,z.imag),xytext=(5,5),textcoords='offset points')
    axes[1].scatter(POLES,np.zeros(3),c='black',marker='x')
    axes[1].set_title('Three real planar states exchange continuously')
    for ax in axes: ax.set_aspect('equal');ax.grid(alpha=.15);ax.set_xlabel('x');ax.set_ylabel('y')
    fig.tight_layout();fig.savefig(OUT/'monodromy_paths.png',dpi=180);plt.close(fig)
    fig,axes=plt.subplots(1,3,figsize=(15,5))
    for j,(ax,z) in enumerate(zip(axes,HOME)):
        p=points(z)
        for nr,rod in enumerate(rods()):
            xy=np.array([p[n] for n in rod]);ax.plot(xy.real,xy.imag,c=colors[nr//6] if nr<18 else '#89929b',lw=1.3)
        ax.scatter([p[n].real for n in FIXED],[p[n].imag for n in FIXED],c='black',marker='s',s=30)
        ax.scatter([z.real],[z.imag],c='red',s=40,zorder=5,label='Memory joint P')
        ax.scatter([p['D1'].real],[p['D1'].imag],c='black',s=40,zorder=5,label='Control D1')
        ax.set_title(f'State {j+1}: identical control position');ax.set_aspect('equal');ax.set_xlim(-23,24);ax.set_ylim(-10,30)
    axes[0].legend(loc='upper left',fontsize=7);fig.tight_layout();fig.savefig(OUT/'mechanism_home_states.png',dpi=180);plt.close(fig)
    print(json.dumps(report,indent=2))


if __name__=='__main__': main()
