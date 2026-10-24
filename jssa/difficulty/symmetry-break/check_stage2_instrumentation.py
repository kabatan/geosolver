"""Known fixed-coordinate checker fixtures; no benchmark or optimizer runs."""
import json
from dataclasses import replace
from stage2_common import *

def main():
    from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
    from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
    doc={'task':'solve','id':'checker-fixture','variables':{'names':['x']},
         'construction':[{'name':'A','expr':'Point(0,0)'},{'name':'B','expr':'Point(x,0)'}],
         'constraints':[{'def':'Distance(A,B)','value':2}],
         'guards':['AssumeGt(x,0)'],'answer':'Distance(A,B)','post_process':''}
    e=build_ir_evaluator(load_problem_bundle(doc))
    cases=[([2],True),([-2],False),([2.000001],False),([float('nan')],False)]
    records=[]
    for x,expected in cases:
        got=check_point(e,x)
        assert got['success']==expected,(x,got)
        records.append(dict(x=x,expected=expected,actual=got))
    save(OUT/'execution/checker-fixtures.json',dict(utc=utc(),source_hash=assert_identity(),
             benchmark_trials=0,optimizer_calls=0,cases=records))
    print('4 fixed-coordinate checker fixtures passed; no search calls')

if __name__=='__main__':main()
