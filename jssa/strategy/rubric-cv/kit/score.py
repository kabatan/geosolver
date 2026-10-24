import csv,json,sys,itertools,os
from collections import defaultdict
keys=json.load(open(os.path.join(os.path.dirname(__file__),'keys.json')))
T={'A':1,'B':2,'C':3,'D':4,'E':5}
def spearman(x,y):
    def rk(v):
        s=sorted(range(len(v)),key=lambda i:v[i]); r=[0]*len(v); i=0
        while i<len(v):
            j=i
            while j+1<len(v) and v[s[j+1]]==v[s[i]]: j+=1
            for k in range(i,j+1): r[s[k]]=(i+j)/2+1
            i=j+1
        return r
    a,b=rk(x),rk(y); n=len(a); ma,mb=sum(a)/n,sum(b)/n
    num=sum((p-ma)*(q-mb) for p,q in zip(a,b)); den=(sum((p-ma)**2 for p in a)*sum((q-mb)**2 for q in b))**.5
    return num/den if den else float('nan')
runs=defaultdict(dict)
for r in csv.DictReader(open(sys.argv[1])):
    runs[(r['fold'],r['run'])][int(r['no'])]=(r['tier'].strip().upper(),int(r['rank']))
out=[];accs=[];rhos=[];am=[]
for (f,ru),v in sorted(runs.items()):
    k={e['no']:e for e in keys['fold'+f]}
    nos=sorted(k); hit=sum(v[n][0]==k[n]['tier'] for n in nos)/len(nos)
    rho=spearman([v[n][1] for n in nos],[T[k[n]['tier']] for n in nos])
    bias=sum(T[v[n][0]]-T[k[n]['tier']] for n in nos)/len(nos)
    fin=sum((T[v[n][0]]<=3)==(T[k[n]['tier']]<=3) for n in nos)/len(nos)
    amn=[n for n in nos if k[n]['field']=='応用数学']; amh=sum(v[n][0]==k[n]['tier'] for n in amn)/len(amn)
    accs.append(hit);rhos.append(rho);am.append(amh)
    out.append(f'| fold{f} | {ru} | {hit:.0%} | {rho:.2f} | {bias:+.2f} | {fin:.0%} | {amh:.0%} |')
cons=[]
for f in '123':
    a,b=runs.get((f,'a')),runs.get((f,'b'))
    if a and b: cons.append(f'fold{f}: {sum(a[n][0]==b[n][0] for n in a)/len(a):.0%}')
print('| fold | 回 | 段階一致 | 順位相関 | ずれ(+は辛い) | 最終審査進出の判別 | 応用数学のみ一致 |\n|---|---|---|---|---|---|---|')
print('\n'.join(out))
print(f'\n平均：段階一致 {sum(accs)/len(accs):.0%}、順位相関 {sum(rhos)/len(rhos):.2f}、応用数学のみ {sum(am)/len(am):.0%}')
print('同じfoldの2回の一致：'+'、'.join(cons))
print('合格基準：段階一致の平均50%以上、順位相関の平均0.5以上、同じfold2回の一致70%以上')
