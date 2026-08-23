"""JSON protocol helpers for the Julia kernel boundary."""

from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass(frozen=True)
class KernelError:
    """Structured kernel error envelope."""

    code: str
    message: str
    details: dict[str, object] = field(default_factory=dict)

    def to_data(self) -> dict[str, object]:
        return {
            "code": self.code,
            "message": self.message,
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class KernelResponse:
    """Parsed kernel response with elapsed diagnostics."""

    ok: bool
    data: dict[str, object] = field(default_factory=dict)
    error: KernelError | None = None
    metadata: dict[str, object] = field(default_factory=dict)
    elapsed_sec: float = 0.0

    def to_data(self) -> dict[str, object]:
        return {
            "ok": bool(self.ok),
            "data": dict(self.data),
            "error": None if self.error is None else self.error.to_data(),
            "metadata": dict(self.metadata),
            "elapsed_sec": float(self.elapsed_sec),
        }

    @classmethod
    def unavailable(
        cls,
        *,
        code: str,
        message: str,
        metadata: dict[str, object],
        elapsed_sec: float = 0.0,
    ) -> "KernelResponse":
        return cls(
            ok=False,
            error=KernelError(code=code, message=message),
            metadata=dict(metadata),
            elapsed_sec=float(elapsed_sec),
        )

    @classmethod
    def from_json(
        cls,
        raw: str,
        *,
        metadata: dict[str, object] | None = None,
        elapsed_sec: float = 0.0,
    ) -> "KernelResponse":
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            return cls(
                ok=False,
                error=KernelError(
                    code="KERNEL_INVALID_RESPONSE",
                    message=f"kernel returned invalid JSON: {exc}",
                ),
                metadata={} if metadata is None else dict(metadata),
                elapsed_sec=float(elapsed_sec),
            )
        if not isinstance(parsed, dict):
            return cls(
                ok=False,
                error=KernelError(
                    code="KERNEL_INVALID_RESPONSE",
                    message="kernel response must be a JSON object",
                ),
                metadata={} if metadata is None else dict(metadata),
                elapsed_sec=float(elapsed_sec),
            )
        error = None
        if isinstance(parsed.get("error"), dict):
            error_raw = parsed["error"]
            error = KernelError(
                code=str(error_raw.get("code", "KERNEL_ERROR")),
                message=str(error_raw.get("message", "")),
                details=(
                    dict(error_raw.get("details", {}))
                    if isinstance(error_raw.get("details"), dict)
                    else {}
                ),
            )
        data_raw = parsed.get("data", {})
        metadata_raw = parsed.get("metadata", {})
        merged_metadata = {} if metadata is None else dict(metadata)
        if isinstance(metadata_raw, dict):
            merged_metadata.update(metadata_raw)
        return cls(
            ok=bool(parsed.get("ok", False)),
            data=dict(data_raw) if isinstance(data_raw, dict) else {"value": data_raw},
            error=error,
            metadata=merged_metadata,
            elapsed_sec=float(elapsed_sec),
        )


def dumps_request(payload: dict[str, object]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
