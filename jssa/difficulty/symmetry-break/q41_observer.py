"""Passive external observation of every frozen candidate-record constructor.

The sampled/search/refined/algebraic candidates all use these two contracts.
Copies and rejected candidates are deliberately retained; no count cap applies.
Optimizer finite-difference probes are not candidate records. See observer-audit.
"""
from __future__ import annotations
import functools
import json
import math
import os
import sys
import time
from pathlib import Path


def install(directory, t0, expected_dimension):
    from mpmath import mp
    from geosolver.engine.standard.contracts.candidate_record import FloatCandidate, RefinedCandidate
    import importlib
    directory=Path(directory)
    stream=(directory/'candidates.jsonl').open('a',buffering=1)
    metadata=(directory/'observer-events.jsonl').open('a',buffering=1)
    state={'candidates':0,'float':0,'refined':0,'observer_seconds':0.0,'errors':0}

    def emit_meta(item):
        metadata.write(json.dumps(item,separators=(',',':'))+'\n')

    def observe(candidate,kind,born,caller):
        begin=time.monotonic()
        try:
            values=candidate.x_float if kind=='float' else candidate.x_hp
            # Serialization must not call float(mpf) while the frozen HP guard
            # is active. Decimal strings cross that boundary without changing
            # any solver value or its arithmetic context.
            decimals=[format(float(mp.nstr(v,90)) if hasattr(v,'_mpf_') else float(v),'.17g') for v in values]
            if len(values)!=expected_dimension:
                state['errors']+=1
                emit_meta({'event':'dimension_mismatch','expected':expected_dimension,'actual':len(values),'t':born-t0})
            row={'index':state['candidates'],'kind':kind,'t':born-t0,
                 'x':decimals,'source':caller,'uid':candidate.candidate_uid}
            if kind=='refined':
                row.update(x_hp=[mp.nstr(v,max(90,candidate.coordinate_precision_dps+10)) for v in values],
                           precision=candidate.coordinate_precision_dps,status=candidate.refinement_status)
            else:
                row.update(phase=candidate.origin_phase,backend=candidate.origin_backend,
                           family=candidate.origin_family,
                           initial_point_decimal=list(candidate.initial_point_decimal))
            stream.write(json.dumps(row,separators=(',',':'))+'\n')
            state['candidates']+=1;state[kind]+=1
        except Exception as error:
            state['errors']+=1
            emit_meta({'event':'observer_error','error':f'{type(error).__name__}: {error}','t':time.monotonic()-t0})
        finally:state['observer_seconds']+=time.monotonic()-begin

    for cls,kind in ((FloatCandidate,'float'),(RefinedCandidate,'refined')):
        original=cls.__init__
        @functools.wraps(original)
        def wrapped(self,*a,_original=original,_kind=kind,**kw):
            born=time.monotonic()
            _original(self,*a,**kw)
            frame=sys._getframe(1)
            while frame is not None and frame.f_globals.get('__name__')=='dataclasses':frame=frame.f_back
            caller={'module':frame.f_globals.get('__name__'),'function':frame.f_code.co_name,'line':frame.f_lineno} if frame else None
            observe(self,_kind,born,caller)
        cls.__init__=wrapped

    # Observe the usual per-arm bounds and scaling without computing new ones.
    for module_name,function_name,event in (
        ('geosolver.engine.standard.problem.infer_problem_bounds','infer_problem_bounds','bounds'),
        ('geosolver.engine.standard.orchestration.run_initial_probe','_compute_constraint_scales','constraint_scales')):
        module=importlib.import_module(module_name);original=getattr(module,function_name)
        @functools.wraps(original)
        def wrapped(*a,_original=original,_event=event,**kw):
            result=_original(*a,**kw)
            start=time.monotonic()
            try:emit_meta({'event':_event,'value':result,'t':start-t0})
            except Exception as error:
                state['errors']+=1
                emit_meta({'event':'metadata_error','error':str(error)})
            state['observer_seconds']+=time.monotonic()-start
            return result
        # Cover aliases already loaded while importing the observer dependencies.
        for loaded in list(sys.modules.values()):
            if loaded is not None and getattr(loaded,'__name__','').startswith('geosolver.'):
                for name,value in list(vars(loaded).items()):
                    if value is original:setattr(loaded,name,wrapped)
        setattr(module,function_name,wrapped)
    emit_meta({'event':'installed','dimension':expected_dimension,'pid':os.getpid(),'t':time.monotonic()-t0})

    def finish():
        emit_meta({'event':'finished',**state,'t':time.monotonic()-t0})
        stream.close();metadata.close()
        return state.copy()
    return finish
