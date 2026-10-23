"""Q19: retain evidence only; do not alter search inputs, returns, or options."""
import os
import sys

_args = sys.orig_argv
_module = _args[_args.index("-m") + 1] if "-m" in _args else None
_capture = os.environ.get("Q19_CAPTURE_ROOT")

if _capture and _module in {"geosolver.application.cli", "geosolver.runtime.worker"}:
    try:
        # A candidate's 335-term sum exceeds the default compiler recursion
        # depth. This common input accommodation changes no DSL or arithmetic.
        sys.setrecursionlimit(10000)
        import atexit
        import dataclasses
        import enum
        import json
        import math
        import tempfile
        from pathlib import Path

        _root = Path(_capture)
        if _module == "geosolver.application.cli":
            # EngineRunner's request/artifact/receipt/stdout/stderr survive even
            # when the public service converts a worker error to a short result.
            _original_temporary_directory = tempfile.TemporaryDirectory

            class RetainedTemporaryDirectory(_original_temporary_directory):
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, **kwargs)
                    self._finalizer.detach()

                def cleanup(self):
                    self._finalizer.detach()

            tempfile.TemporaryDirectory = RetainedTemporaryDirectory
            (_root / "cli-capture-installed.json").write_text(
                json.dumps({"temporary_directories_retained": True,
                            "python_recursion_limit": sys.getrecursionlimit()}) + "\n"
            )
        else:
            from geosolver.engine.standard.contracts.candidate_record import FloatCandidate

            _stream = (_root / "float-candidates.jsonl").open("x", buffering=1)
            _original_post_init = FloatCandidate.__post_init__

            def _safe(value):
                if isinstance(value, enum.Enum):
                    return value.value
                if isinstance(value, float) and not math.isfinite(value):
                    return str(value)
                if isinstance(value, (tuple, list)):
                    return [_safe(item) for item in value]
                return value

            def _record_candidate(self):
                _original_post_init(self)
                # Reading dataclass fields adds no evaluations or candidate
                # selection. Include NOMAD evaluations as well as local endpoints.
                _stream.write(json.dumps(
                    {field.name: _safe(getattr(self, field.name))
                     for field in dataclasses.fields(self)},
                    ensure_ascii=False, allow_nan=False, separators=(",", ":"),
                ) + "\n")

            FloatCandidate.__post_init__ = _record_candidate
            (_root / "worker-capture-installed.json").write_text(json.dumps({
                "candidate_capture": "FloatCandidate.__post_init__",
                "original_post_init_called_first": True,
                "inputs_and_return_values_unchanged": True,
                "python_recursion_limit": sys.getrecursionlimit(),
            }) + "\n")
            atexit.register(_stream.close)
    except BaseException:
        # Python ordinarily swallows sitecustomize errors: fail closed instead.
        import traceback
        traceback.print_exc()
        os._exit(91)
