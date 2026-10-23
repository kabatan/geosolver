import numpy as np, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from scipy.optimize import least_squares
font_manager.fontManager.addfont('/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf')
plt.rcParams.update({'font.family':'IPAGothic','font.size':9.5,'figure.facecolor':'#fcfcfb','axes.facecolor':'#fcfcfb'})
B_,O_,A_,GR='#2a78d6','#eb6834','#1baf7a','#8a8985'
A=np.array([0.,0]);B=np.array([4.,0])
def pts(v):
    C=np.array(v[:2]);D=np.array(v[2:]);return C,D
def circ(P,Q,R):
    ax,ay=P;bx,by=Q;cx,cy=R
    d=2*(ax*(by-cy)+bx*(cy-ay)+cx*(ay-by))
    ux=((ax**2+ay**2)*(by-cy)+(bx**2+by**2)*(cy-ay)+(cx**2+cy**2)*(ay-by))/d
    uy=((ax**2+ay**2)*(cx-bx)+(bx**2+by**2)*(ax-cx)+(cx**2+cy**2)*(bx-ax))/d
    return np.array([ux,uy])
def res(v):
    C,D=pts(v);O=circ(A,B,C)
    return [np.linalg.norm(C-B)-5,np.linalg.norm(D-C)-6,np.linalg.norm(A-D)-7,np.linalg.norm(D-O)-np.linalg.norm(A-O)]
v=least_squares(res,[6,4,1,6]).x;C,D=pts(v)
def foot(P,Q,R):
    d=R-Q;return Q+np.dot(P-Q,d)/np.dot(d,d)*d
A1=foot(A,B,D);C1=foot(C,B,D);B1=foot(B,A,C);D1=foot(D,A,C)
per=sum(np.linalg.norm(p-q) for p,q in [(A1,B1),(B1,C1),(C1,D1),(D1,A1)])
print(res(v),per,242/59)
fig=plt.figure(figsize=(9.6,3.4))
ax=fig.add_axes([0.0,0.02,0.30,0.72]);ax.set_aspect('equal');ax.axis('off')
O=circ(A,B,C);r=np.linalg.norm(A-O);t=np.linspace(0,2*np.pi,200)
ax.plot(O[0]+r*np.cos(t),O[1]+r*np.sin(t),color='#d9d8d4',lw=1)
Q=[A,B,C,D,A];ax.plot([p[0] for p in Q],[p[1] for p in Q],color='#52514e',lw=1.4)
ax.plot([A[0],C[0]],[A[1],C[1]],color=GR,lw=0.8,ls='--');ax.plot([B[0],D[0]],[B[1],D[1]],color=GR,lw=0.8,ls='--')
for P,F in [(A,A1),(C,C1),(B,B1),(D,D1)]: ax.plot([P[0],F[0]],[P[1],F[1]],color=GR,lw=0.7,ls=':')
F=[A1,B1,C1,D1,A1];ax.plot([p[0] for p in F],[p[1] for p in F],color=O_,lw=2)
for n,P,o in [('A',A,(-0.5,-0.4)),('B',B,(0.2,-0.4)),('C',C,(0.25,0)),('D',D,(-0.6,0.1))]: ax.text(P[0]+o[0],P[1]+o[1],n,fontsize=10)
fig.text(0.01,0.97,'① 問題：AIME 2021 I-11\n辺4,5,6,7の円に内接する四角形 ABCD。\n頂点から対角線への垂線の足が作る\n四角形（橙）の周は？',fontsize=8.6,va='top',linespacing=1.4)
ax2=fig.add_axes([0.33,0.02,0.36,0.9]);ax2.axis('off')
txt=('② 入力（作図と条件）\n\n'
 '探索変数  C = (cx, cy),  D = (dx, dy)   d = 4\n'
 '作図  A = (0,0),  B = (4,0)\n'
 '      A1, C1 = A, C から BD への垂線の足\n'
 '      B1, D1 = B, D から AC への垂線の足\n'
 '等式  BC = 5,  CD = 6,  DA = 7,\n'
 '      A, B, C, D が同一円上\n'
 '不等式  C, D は上側、ABCD は凸\n'
 '求める量  四角形 A1B1C1D1 の周')
ax2.text(0,0.98,txt,va='top',fontsize=8.6,family='IPAGothic',linespacing=1.5,bbox=dict(boxstyle='round,pad=0.6',fc='#f1f0ec',ec='#d9d8d4'))
ax3=fig.add_axes([0.72,0.02,0.28,0.9]);ax3.axis('off')
txt3=('③ solver の出力（12.9秒）\n\n'
 '探索：候補 20個（1.4秒）\n'
 '精密化：14個が収束、6個は偽\n'
 '値：4.10169491525423…\n'
 '同定（PSLQ）：59τ − 242 = 0\n'
 '確認：120桁以上で条件と枝\n\n'
 '答え  242/59')
ax3.text(0,0.98,txt3,va='top',fontsize=8.6,linespacing=1.5,bbox=dict(boxstyle='round,pad=0.6',fc='#eef4fc',ec='#bcd3f0'))
fig.text(0.29,0.62,'→',fontsize=20,color='#8a8985');fig.text(0.675,0.62,'→',fontsize=20,color='#8a8985')
fig.savefig('/mnt/project-files/jssa/draft/figures/fig0_pipeline_example.png',dpi=200)
