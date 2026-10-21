"""GeoSolver IR (Intermediate Representation) Module"""

from geosolver.problem.ir.compiler import (
    ALLOWED_AST_NODES,
    BANNED_SUBSTRINGS,
    extract_names,
    safe_eval_expr,
    validate_expr_safety,
)
from geosolver.problem.ir.errors import (
    IRCompileError,
    IRError,
    IRSecurityError,
    IRValidationError,
)
from geosolver.problem.ir.parser import load_ir
from geosolver.problem.ir.schema import (
    IRConstruction,
    IRSpec,
    IRVariableSpec,
    TaskKind,
)

__all__ = [
    # Errors
    "IRError",
    "IRValidationError",
    "IRCompileError",
    "IRSecurityError",
    # Schema
    "IRSpec",
    "IRVariableSpec",
    "IRConstruction",
    "TaskKind",
    # Compiler
    "safe_eval_expr",
    "extract_names",
    "validate_expr_safety",
    "ALLOWED_AST_NODES",
    "BANNED_SUBSTRINGS",
    # Parser
    "load_ir",
]
