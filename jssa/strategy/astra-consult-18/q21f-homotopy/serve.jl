using HomotopyContinuation, JSON3, LinearAlgebra
BLAS.set_num_threads(1)
const HC = HomotopyContinuation
safe(x::Number) = isfinite(x) ? x : nothing
cvec(x) = [[safe(real(v)),safe(imag(v))] for v in x]
emit(x) = (println(JSON3.write(x)); flush(stdout))

function make_system(data)
    vars = [Variable(String(v)) for v in data.variables]
    eqs = Expression[]
    for terms in data.polynomials
        p = Expression(0)
        for (c, powers) in terms
            s = split(String(c), '/')
            q = parse(BigInt,s[1]) // (length(s)==1 ? big(1) : parse(BigInt,s[2]))
            term = Expression(q)
            for j in eachindex(vars)
                term *= vars[j]^Int(powers[j])
            end
            p += term
        end
        push!(eqs,p)
    end
    System(eqs;variables=vars)
end

function compute(job)
    data = JSON3.read(read(String(job.input),String))
    F = make_system(data)
    t0 = time_ns()
    r = solve(F;start_system=Symbol(job.method),seed=UInt32(job.seed),
              threading=false,show_progress=false,
              tracker_options=TrackerOptions(max_steps=10000))
    elapsed = (time_ns()-t0)/1e9
    paths = [Dict("return_code"=>String(p.return_code),"solution"=>cvec(p.solution),
                  "t"=>safe(p.t),"accuracy"=>safe(p.accuracy),
                  "residual"=>safe(p.residual),"condition_jacobian"=>safe(p.condition_jacobian),
                  "singular"=>p.singular,"is_failed"=>HC.is_failed(p),
                  "accepted_steps"=>p.accepted_steps,"rejected_steps"=>p.rejected_steps,
                  "winding_number"=>p.winding_number,
                  "multiplicity"=>p.multiplicity) for p in path_results(r)]
    sols = solutions(r;only_nonsingular=false)
    Dict("status"=>"ok","id"=>String(data.id),"mode"=>String(data.mode),
         "method"=>String(job.method),"seed"=>Int(job.seed),
         "solve_seconds"=>elapsed,"tracked"=>HC.ntracked(r),
         "failed"=>HC.nfailed(r),"at_infinity"=>HC.nat_infinity(r),
         "excess"=>HC.nexcess_solutions(r),"solutions"=>map(cvec,sols),
         "n_distinct_solutions"=>length(sols),
         "n_distinct_real"=>length(real_solutions(r;only_nonsingular=false,atol=1e-7)),
         "paths"=>paths)
end

emit(Dict("event"=>"ready","julia_version"=>string(VERSION),
          "hc_version"=>string(pkgversion(HC)),"threads"=>Threads.nthreads()))
for line in eachline(stdin)
    job = JSON3.read(line)
    try
        result = if get(job,:event,"")=="warmup"
            @var x y
            F=System([x^2+y^2-1,x-y])
            counts=[HC.nsolutions(solve(F;start_system=m,threading=false,
                        show_progress=false,seed=UInt32(211023))) for m in [:total_degree,:polyhedral]]
            @assert counts == [2,2]
            Dict("event"=>"warmup_done","counts"=>counts)
        else
            compute(job)
        end
        emit(result)
    catch err
        emit(Dict("status"=>"error","error"=>sprint(showerror,err,catch_backtrace())))
    end
end
