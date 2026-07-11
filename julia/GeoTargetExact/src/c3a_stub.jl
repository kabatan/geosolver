"""Typed Phase-A result: Core/C3A graph replay is intentionally not connected yet."""
struct C3AReplayUnsupported
    detail::String
end

replay_c3a(::Any...; kwargs...) = C3AReplayUnsupported(
    "GeoTargetExact Phase A implements recognition and certificate reconstruction only; " *
    "Core C3A replay is added in Phase B",
)
