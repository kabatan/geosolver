using Test
using HomotopyContinuation

@testset "pinned homotopy baseline" begin
    @polyvar x
    system = System([x^2 - 2])
    result = solve(
        system;
        start_system = :polyhedral,
        only_non_zero = false,
        seed = UInt32(0),
        show_progress = false,
        threading = false,
    )
    @test length(solutions(result)) == 2
    @test nfailed(result) == 0
    @test all(is_real(path) for path in result.path_results)
end
