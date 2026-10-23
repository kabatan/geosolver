"""Post-hoc causal contrast: disable only the hard-penalty search row."""
from __future__ import annotations
import json
import time
from collections import Counter
import numpy as np
from scipy.stats import binomtest
from experiment import OUT, all_cases, context, dump, reference_values, solve


def main():
    cases=all_cases()
    results=[]
    summaries=[]
    for cid in ('AIME-2023-I-12','HMMT-2024-FEB-GEO-04'):
        data=json.loads((OUT/'replication'/f'{cid}.json').read_text())
        b,ev,box=context(cases[cid])
        refs=reference_values(cases[cid]['answer'])
        started=time.monotonic()
        rows=[]
        for original in data['rows']:
            rec=solve(b,ev,box,refs,np.array(original['start']),data['a'],'nohard',320,original['k'])
            rows.append({'k':original['k'],'start':original['start'],'base':original['base'],'nohard':rec})
        gain=sum(r['nohard']['cls']=='hit' and r['base']['cls']!='hit' for r in rows)
        loss=sum(r['nohard']['cls']!='hit' and r['base']['cls']=='hit' for r in rows)
        result={'id':cid,'rows':rows,'seconds':time.monotonic()-started}
        results.append(result)
        summary={'id':cid,'n':len(rows),'base_hits':sum(r['base']['cls']=='hit' for r in rows),
                 'nohard_hits':sum(r['nohard']['cls']=='hit' for r in rows),
                 'gain':gain,'loss':loss,'mcnemar_p':binomtest(gain,gain+loss,.5).pvalue if gain+loss else 1,
                 'nohard_classes':dict(Counter(r['nohard']['cls'] for r in rows)),
                 'seconds':result['seconds']}
        summaries.append(summary)
        print(summary,flush=True)
    dump(OUT/'hard-penalty-results.json',results)
    dump(OUT/'hard-penalty-summary.json',summaries)


if __name__=='__main__':
    main()
