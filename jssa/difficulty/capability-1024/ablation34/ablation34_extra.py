import json, glob, statistics as st, math, collections
BASE="/home/kabatan/work/jssa-ablation34/out/runs"
R={}
for p in glob.glob(BASE+"/*/*/*.json"):
    d=json.load(open(p)); R[(d["arm"],d["case_id"],d["seed"])]=d
w=lambda d: d["wall_seconds"] if d["wall_seconds"] is not None else d["elapsed_seconds"]
keys=sorted({(k[1],k[2]) for k in R})
for arm in ["NO_SECOND_ATTEMPT","NO_NOMAD","NO_ALGEBRAIC","NO_SCALE_CHART","NO_RESCUE","NO_ANALYTIC_JAC"]:
    both=[k for k in keys if R[(arm,)+k]["matched"] and R[("BASE",)+k]["matched"]]
    r=[w(R[(arm,)+k])/w(R[("BASE",)+k]) for k in both if w(R[("BASE",)+k])>0]
    tot=sum(w(R[(arm,)+k]) for k in both)/sum(w(R[("BASE",)+k]) for k in both)
    gm=math.exp(sum(math.log(x) for x in r)/len(r))
    big=[ (k,round(w(R[(arm,)+k])/w(R[("BASE",)+k]),2)) for k in both if w(R[("BASE",)+k])>0 and w(R[(arm,)+k])/w(R[("BASE",)+k])>1.5]
    hard=[k for k in both if w(R[("BASE",)+k])>=10]
    rh=[w(R[(arm,)+k])/w(R[("BASE",)+k]) for k in hard]
    print(arm,"median",round(st.median(r),3),"gmean",round(gm,3),"total-time ratio (both solved)",round(tot,3),"n>=1.5x:",len(big),"hard(base>=10s) n",len(hard),"median ratio hard",round(st.median(rh),3) if rh else None)
print("BASE wall median/mean over all:",round(st.median([w(R[("BASE",)+k]) for k in keys]),2),round(st.mean([w(R[("BASE",)+k]) for k in keys]),2))
pp=collections.Counter()
for k in keys:
    if R[("BASE",)+k]["matched"]: pp[k[0]]+=1
print("problems BASE>=2/3:",sum(1 for c in {x[0] for x in keys} if pp[c]>=2),"of",len({x[0] for x in keys}))
print("NO_NOMAD gained:",sorted(k for k in keys if R[("NO_NOMAD",)+k]["matched"] and not R[("BASE",)+k]["matched"]))
print("NO_SECOND lost:",sorted(k for k in keys if not R[("NO_SECOND_ATTEMPT",)+k]["matched"] and R[("BASE",)+k]["matched"]))
