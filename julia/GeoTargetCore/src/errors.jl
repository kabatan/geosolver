abstract type CoreError <: Exception end

struct RegistryError <: CoreError
    code::Symbol
    message::String
end

Base.showerror(io::IO, error::RegistryError) =
    print(io, "GeoTarget registry ", error.code, ": ", error.message)

struct ProblemValidationError <: CoreError
    issues::Tuple
end

function Base.showerror(io::IO, error::ProblemValidationError)
    print(io, "GeoTarget problem validation failed")
    for issue in error.issues
        print(io, "\n  - ", issue.code, ": ", issue.message)
    end
end

