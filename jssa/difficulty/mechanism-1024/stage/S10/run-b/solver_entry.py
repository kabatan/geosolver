"""S10 CLI entry: select the same adapter worker for all four arms. Main runs only when launched explicitly."""
import runpy

def install(runner_module):
    original=runner_module.EngineRunner.__init__
    def init(self, *, worker_module='s10_worker', memory_limit_bytes=None):
        return original(self,worker_module=worker_module,memory_limit_bytes=memory_limit_bytes)
    runner_module.EngineRunner.__init__=init

if __name__=='__main__':
    import geosolver.engine.runner as runner
    install(runner)
    runpy.run_module('geosolver.application.cli',run_name='__main__')
