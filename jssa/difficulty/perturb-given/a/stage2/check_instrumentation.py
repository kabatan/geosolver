"""Numerical-contract tests on artificial functions, never on a selected problem."""
from common import *
import types
import numpy as np
from diagnose import jacobian, cluster
from analyze import bootstrap, correlations


def main():
    cid='TEST-00'
    bounds=[[-3,7],[2,4]]
    x=starts(cid,404001,bounds)
    assert x.shape==(200,2) and np.all(x[:,0]>-3) and np.all(x[:,0]<7)
    integer=int(hashlib.sha256(b'Q40|4040|start|404001|TEST-00|0|0').hexdigest()[:16],16)
    assert x[0,0]==-3+(((integer//4096)+.5)/4503599627370496)*10
    slots=list(schedule(cid)); assert len(slots)==3600 and len(set(slots))==3600
    for offset in range(0,len(slots),6):
        block=slots[offset:offset+6]
        assert len({(s,k) for s,k,v,p in block})==1
        assert set(v for s,k,v,p in block)==set(VARIANTS)
        assert [p for s,k,v,p in block]==list(range(6))

    class Evaluator:
        def __init__(self,matrix): self.matrix=np.array(matrix)
        def evaluate_float_residual(self,point):
            return types.SimpleNamespace(residual_vector=self.matrix@point)

    full=jacobian(Evaluator([[2,0],[0,3]]),[.3,.7],[[0,10],[0,2]],[2,3],2)
    assert full['valid'] and full['rank']==2
    assert np.allclose(full['raw_singular_values'][1],[3,2],rtol=1e-8)
    assert np.allclose(full['scaled_singular_values'][1],[10,2],rtol=1e-8)
    under=jacobian(Evaluator([[1,0]]),[.3,.7],[[0,1],[0,1]],[1],1)
    assert under['valid'] and under['sigma_min']==0 and under['rank']==1
    zero=jacobian(Evaluator([[0,0],[0,0]]),[.3,.7],[[0,1],[0,1]],[1,1],2)
    assert zero['valid'] and zero['scaled_ratio']==[0,0] and zero['rank']==0
    missing=jacobian(Evaluator([[1,0]]),[.3,.7],[[0,1],[0,1]],None,1)
    assert not missing['valid'] and 'raw_singular_values' in missing
    points=[{'z':[0.0]},{'z':[.00009]},{'z':[.00018]}]
    assert [len(g) for g in cluster(points,1e-4)]==[2,1], 'complete-link clusters, not single-link chains'
    assert len(cluster(points,1e-5))==3 and len(cluster(points,1e-3))==1
    selected=[{'canonical_id':str(k),'cohort':'development' if k<20 else 'unseen'} for k in range(40)]
    interval=bootstrap({str(k):.05 for k in range(40)},selected)
    assert interval==[.05,.05], 'exact boundary, without accumulated floating-point error'
    assert correlations([(i,i,0,2) for i in range(19)])['spearman'] is None
    assert correlations([(1,i,0,2) for i in range(20)])['spearman'] is None
    result={'passed':True,'at_utc':utc(),'tests':['start SHA256 and mapping','all 3600 unique per-case slots and hash order',
            'raw/scaled Jacobians','underdetermined zero padding','zero matrix ratio and rank','missing row scale',
            'complete-link branch clustering at three widths','stratified bootstrap constant control','correlation NA rules'],
            'selected_problem_evaluations':0,'local_search_calls':0}
    write(HERE/'instrumentation-checks.json',result)
    print(json.dumps(result))


if __name__=='__main__':
    main()
