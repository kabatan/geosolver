"""Prepare concrete offline CAS inputs; never launches or installs a CAS."""
from pathlib import Path
import json,sys,csv
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'vendor'))
import sympy as sp
from run_exact import poly_str
out=HERE/'cas-inputs';out.mkdir(exist_ok=True)
manifest=[]
ids=json.loads((HERE/'registration-lock.json').read_text())['ids']
for cid in ids:
    d=json.loads((HERE/'runs'/f'{cid}__A/system.json').read_text())
    target=sp.Symbol(d['target']);vs=[sp.Symbol(v) for v in d['variables'] if v!=d['target']]+[target]
    ren={v:sp.Symbol(f'x{i}') for i,v in enumerate(vs)};names=[str(ren[v]) for v in vs]
    fs=[poly_str(sp.sympify(e).xreplace(ren)) for e in d['equations']]
    dest=out/cid;dest.mkdir(exist_ok=True)
    (dest/'input.ms').write_text(','.join(names)+'\n0\n'+',\n'.join(fs)+'\n')
    script=['option(redSB);',f"ring r=0,({','.join(names)}),dp;",'ideal I='+',\n'.join(fs)+';',
            'int startTime=rtimer;',f"ideal E=eliminate(I,{'*'.join(names[:-1])});",'print("ELIM");print(E);',
            'if (E[1]!=0) { matrix C=lift(I,E[1]); poly chk=E[1]; int i; for(i=1;i<=size(I);i++){chk=chk-C[i,1]*I[i];} print("CHECK");print(chk==0);print("COFACTORS");print(C); }',
            'print("TICKS");print(rtimer-startTime);quit;']
    (dest/'input.sing').write_text('\n'.join(script)+'\n')
    mapping=dict(id=cid,coordinate_variables_to_eliminate=len(vs)-1,target=names[-1],variables={str(ren[v]):str(v) for v in vs},
                 nondeg=d['nondeg'],source_system=str((HERE/'runs'/f'{cid}__A/system.json').relative_to(HERE)))
    (dest/'mapping.json').write_text(json.dumps(mapping,indent=2)+'\n')
    manifest.append(dict(id=cid,k=len(vs)-1,variables=len(vs),equations=len(fs),target=names[-1]))
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('Prepared 16 Singular and msolve input pairs; no CAS execution.')
