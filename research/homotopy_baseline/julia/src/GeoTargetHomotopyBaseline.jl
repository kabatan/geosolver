module GeoTargetHomotopyBaseline

"""Research-only Julia worker implementation lives in `worker.jl`.

Keeping a tiny package module makes the pinned Julia project precompile cleanly
while allowing the command-line worker to be launched as a script.  No product
solver code is imported here.
"""

end
