"""Driver-owned SEARCH_MODE bridge. Does not modify frozen source or identity defaults."""
import os

def install(worker, mode):
    if mode is None:
        return
    if mode != 'mads':
        raise ValueError('unsupported SEARCH_MODE')
    original=worker.ExternalPipelineConfig
    class ConfigBridge:
        @staticmethod
        def production_baseline_tier(**kwargs):
            # The public factory sets BOTH global_search_mode and the primary
            # BaselineSearchPolicy attempt; changing only the former is ineffective.
            return original.production_baseline_tier(**dict(kwargs,global_search_mode=mode))
    worker.ExternalPipelineConfig=ConfigBridge

if __name__=='__main__':
    from geosolver.runtime import worker
    install(worker,os.environ.get('SEARCH_MODE'))
    raise SystemExit(worker.main())
