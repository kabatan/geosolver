using HomotopyContinuation
using LinearAlgebra
BLAS.set_num_threads(1)
@var x y
F = System([x^2 + y^2 - 1, x - y])
r = solve(F; start_system=:total_degree, threading=false, show_progress=false, seed=UInt32(211023))
println("HC_VERSION=", pkgversion(HomotopyContinuation))
println("THREADS=", Threads.nthreads())
show(stdout, MIME"text/plain"(), r)
println()
println("SOLUTIONS=", solutions(r))
