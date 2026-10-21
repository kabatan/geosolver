"""Independent translated/unit-scaled native-versus-bounded Newton grid.
Run only with PYTHONPATH pointing at an independently frozen review snapshot.
"""
import argparse
import json
import time
from pathlib import Path
from mpmath import mp
from geosolver.engine.standard.refinement.newton_line_search import findroot_least_squares
from geosolver.runtime.integrity import source_tree_hash

parser = argparse.ArgumentParser()
parser.add_argument('--output', required=True)
args = parser.parse_args()

families = [
    ('atan', ('1e6','1e15','1e25'), lambda t: mp.atan(t), lambda t: 1/(1+t*t)),
    ('tanh', ('10','50','100'), lambda t: mp.tanh(t), lambda t: 1/mp.cosh(t)**2),
    ('normalized_rational', ('1e3','1e8','1e15'), lambda t: t/mp.sqrt(1+t*t), lambda t: (1+t*t)**mp.mpf('-1.5')),
    ('expm1', ('-10','-50','-100'), lambda t: mp.expm1(t), lambda t: mp.exp(t)),
    ('cubic_control', ('0.01','0.1','10'), lambda t: t**3-1, lambda t: 3*t*t),
]
source = source_tree_hash()
with Path(args.output).open('w') as output:
    for dps in (120, 180):
        with mp.workdps(dps):
            tolerance = mp.mpf('1e-70')
            for family, starts, function, derivative in families:
                for start in starts:
                    for unit_string in ('1e-12','1','1e12'):
                        unit = mp.mpf(unit_string)
                        for shift_string in ('0','1e90'):
                            shift = mp.mpf(shift_string)*unit
                            initial = (shift+unit*mp.mpf(start), mp.mpf('0.25'))
                            def residual(x,y):
                                return (function((x-shift)/unit),y-1)
                            def jacobian(x,y):
                                return mp.matrix([[derivative((x-shift)/unit)/unit,0],[0,1]])
                            row = dict(source_hash=source, dps=dps, family=family, start=start, unit=unit_string, shift_in_units=shift_string)
                            for variant in ('native','candidate'):
                                calls = [0]
                                def counted(x,y):
                                    calls[0] += 1
                                    return residual(x,y)
                                began = time.perf_counter()
                                try:
                                    if variant == 'native':
                                        root = mp.findroot(counted, initial, J=jacobian, tol=tolerance, maxsteps=80)
                                    else:
                                        root = findroot_least_squares(counted, initial, J=jacobian, tol=tolerance, maxsteps=80)
                                    norm = mp.norm(residual(*root),2)
                                    row[variant] = {'success': bool(mp.isfinite(norm) and norm**2 <= tolerance), 'residual_norm':mp.nstr(norm,10),'root_in_units':mp.nstr((root[0]-shift)/unit,12)}
                                except Exception as error:
                                    row[variant] = {'success':False,'exception':type(error).__name__,'message':str(error)[:180]}
                                row[variant].update(calls=calls[0],seconds=time.perf_counter()-began)
                            output.write(json.dumps(row)+'\n');output.flush()
