"""Platform capabilities required by optional symbolic proposal tests."""

import signal

import pytest

HAS_CPU_TIMER = hasattr(signal, "setitimer") and hasattr(signal, "ITIMER_PROF")
requires_cpu_timer = pytest.mark.skipif(
    not HAS_CPU_TIMER,
    reason="optional symbolic proposals require the ITIMER_PROF process CPU timer",
)
