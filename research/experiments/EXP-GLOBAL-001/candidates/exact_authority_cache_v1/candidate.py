"""Disposable exact-authority cache policy.

The cache is populated only after exact source replay has accepted a target
identity.  A later ordinary proposal for that same exact identity may be
discarded because the target has already been emitted by an earlier source
configuration.  Failed confirmations are never cached.
"""

from __future__ import annotations

from threading import Lock
from typing import Hashable


class ConfirmedIdentityCache:
    def __init__(self) -> None:
        self._confirmed: set[Hashable] = set()
        self._lock = Lock()

    def already_confirmed(self, identity: Hashable | None) -> bool:
        if identity is None:
            return False
        with self._lock:
            return identity in self._confirmed

    def confirm(self, identity: Hashable | None) -> None:
        if identity is None:
            return
        with self._lock:
            self._confirmed.add(identity)

    def count(self) -> int:
        with self._lock:
            return len(self._confirmed)
