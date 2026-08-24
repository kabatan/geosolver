"""GeoSolver IR (Intermediate Representation) Module"""

from geosolver.problem.ir.errors import (
    IRError,
    IRValidationError,
    IRCompileError,
    IRSecurityError,
)
from geosolver.problem.ir.schema import (
    IRSpec,
    IRVariableSpec,
    IRConstruction,
    TaskKind,
)
from geosolver.problem.ir.compiler import (
    safe_eval_expr,
    extract_names,
    validate_expr_safety,
    ALLOWED_AST_NODES,
    BANNED_SUBSTRINGS,
)
from geosolver.problem.ir.parser import load_ir

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
