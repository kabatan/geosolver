"""Import S4 expression helpers without running S4 or reading S3 outcomes."""
import importlib.util
from pathlib import Path
p=Path(__file__).resolve().parent.parent/'S4/worker.py'
spec=importlib.util.spec_from_file_location('s4_original_worker',p)
s4=importlib.util.module_from_spec(spec)
spec.loader.exec_module(s4)
for k,v in vars(s4).items():
    if not k.startswith('__'): globals()[k]=v
