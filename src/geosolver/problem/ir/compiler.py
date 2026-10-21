"""
安全なIRコンパイラ

eval()を使わず、ASTを解析して許可されたノードのみを評価する。
"""

import ast
import functools
import hashlib
from types import CodeType
from typing import Any

from geosolver.problem.evaluation_trace import runtime_call
from geosolver.problem.ir.compiler_validation import (
    collect_name_nodes,
    ensure_allowed_ast_nodes,
    parse_eval_tree,
)
from geosolver.problem.ir.errors import IRCompileError, IRSecurityError

__all__ = [
    "safe_eval_expr",
    "safe_eval_expr_hp",
    "extract_names",
    "validate_expr_safety",
    "ALLOWED_AST_NODES",
    "BANNED_SUBSTRINGS",
]


# 許可するASTノードタイプ
ALLOWED_AST_NODES: set[type] = {
    ast.Expression,
    ast.Module,
    ast.Expr,
    # 演算
    ast.BinOp,
    ast.UnaryOp,
    ast.BoolOp,
    ast.Compare,
    ast.IfExp,
    # 演算子
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.FloorDiv,
    ast.Mod,
    ast.Pow,
    ast.USub,
    ast.UAdd,
    ast.Not,
    ast.And,
    ast.Or,
    # 比較演算子
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    # 値
    ast.Constant,
    ast.Name,
    ast.Load,
    # 関数呼び出し
    ast.Call,
    ast.keyword,  # キーワード引数
    # コレクション
    ast.Tuple,
    ast.List,
    # 属性アクセス
    ast.Attribute,
    ast.Subscript,
    ast.Slice,
}

# 禁止するサブストリング（コードインジェクション対策）
BANNED_SUBSTRINGS: tuple = (
    "__",
    "import",
    "exec(",
    "eval(",
    "open(",
    "os.",
    "sys.",
    "subprocess",
    "pickle",
    "marshal",
    "globals(",
    "locals(",
    "compile(",
    "getattr(",
    "setattr(",
    "delattr(",
    "hasattr(",
    "vars(",
    "dir(",
    "type(",
    "input(",
    "breakpoint(",
)


class _FloatLiteralToMpfTransformer(ast.NodeTransformer):
    """AST Transformer: float/int リテラルを mpf('...') 呼び出しに変換する。

    HP モード下で IR 式を評価する際に適用する。
    例: ``1.0`` -> ``mpf('1.0')``, ``2`` -> ``mpf('2')``

    変換後の式は HP 評価コンテキスト内の ``mpf`` (= ensure_mpf) を参照する。

    Note:
        bool は int のサブクラスだが変換しない (True/False は比較に使用される)。
    """

    def __init__(self, source: str):
        self.source = source

    def visit_Constant(self, node: ast.Constant) -> ast.AST:
        """数値定数を mpf(str_repr) 呼び出しに変換する。"""
        if isinstance(node.value, bool):
            # bool は int のサブクラスなので先にチェック
            return node
        if isinstance(node.value, int | float):
            # mpf(str_repr) に変換: mpf は HP コンテキストで ensure_mpf にバインドされる
            str_repr = ast.get_source_segment(self.source, node) or repr(node.value)
            call_node = ast.Call(
                func=ast.Name(id="mpf", ctx=ast.Load()),
                args=[ast.Constant(value=str_repr)],
                keywords=[],
            )
            return ast.copy_location(call_node, node)
        return node


class _InstrumentCalls(ast.NodeTransformer):
    def __init__(self, source):
        self.source = source

    def visit_Call(self, node):
        self.generic_visit(node)
        if not isinstance(node.func, ast.Name):
            return node
        name = node.func.id
        site = hashlib.sha256(
            f"{self.source}\0{node.lineno}:{node.col_offset}".encode()
        ).hexdigest()[:24]
        call = ast.Call(
            func=ast.Name(id="_dsl_call", ctx=ast.Load()),
            args=[ast.Constant(site), ast.Constant(name), node.func, *node.args],
            keywords=node.keywords,
        )
        return ast.copy_location(call, node)


def validate_expr_safety(expr: str, *, where: str = "expr") -> None:
    """
    式の安全性を検証

    Args:
        expr: 検証する式
        where: エラーメッセージ用のコンテキスト

    Raises:
        IRSecurityError: 危険なパターンが検出された場合
    """
    lowered = expr.lower()
    for banned in BANNED_SUBSTRINGS:
        if banned in lowered:
            raise IRSecurityError(f"{where}: forbidden pattern {banned!r} detected", pattern=banned)


def extract_names(expr: str) -> list[str]:
    """
    式から変数名を抽出

    Args:
        expr: Python式

    Returns:
        式中のName識別子のリスト

    Raises:
        IRCompileError: 構文エラーまたは禁止されたノードがある場合
    """
    validate_expr_safety(expr)
    tree = parse_eval_tree(expr)
    ensure_allowed_ast_nodes(tree, expr=expr, allowed_nodes=ALLOWED_AST_NODES)
    return collect_name_nodes(tree)


@functools.lru_cache(maxsize=1024)
def _compile_expr_safe_cached(expr: str) -> CodeType:
    validate_expr_safety(expr)
    tree = parse_eval_tree(expr)
    ensure_allowed_ast_nodes(tree, expr=expr, allowed_nodes=ALLOWED_AST_NODES)
    tree = _InstrumentCalls(expr.replace("^", "**")).visit(tree)
    ast.fix_missing_locations(tree)
    return compile(tree, filename="<ir_expr>", mode="eval")


@functools.lru_cache(maxsize=1024)
def _compile_expr_hp_cached(expr: str) -> CodeType:
    """HP モード用: float/int リテラルを mpf('...') に変換してコンパイル。"""
    expr = expr.replace("^", "**")
    validate_expr_safety(expr)
    tree = parse_eval_tree(expr)
    ensure_allowed_ast_nodes(tree, expr=expr, allowed_nodes=ALLOWED_AST_NODES)
    transformer = _FloatLiteralToMpfTransformer(expr)
    tree = _InstrumentCalls(expr).visit(tree)
    transformed = transformer.visit(tree)
    ast.fix_missing_locations(transformed)
    return compile(transformed, filename="<ir_expr_hp>", mode="eval")


def safe_eval_expr(expr: str, context: dict[str, Any]) -> Any:
    """
    制限されたPython式を安全に評価

    Args:
        expr: 評価するPython式
        context: 変数と関数を含む評価コンテキスト

    Returns:
        式の評価結果

    Raises:
        IRCompileError: 構文エラーまたは評価エラー
        IRSecurityError: 危険なパターンが検出された場合

    Examples:
        >>> safe_eval_expr("1 + 2", {})
        3
        >>> safe_eval_expr("Distance(A, B)", {"Distance": distance_func, "A": p1, "B": p2})
    """
    try:
        code = _compile_expr_safe_cached(expr)
        return eval(code, {"__builtins__": {}, "_dsl_call": runtime_call}, context)
    except (IRCompileError, IRSecurityError, TimeoutError):
        raise
    except Exception as e:
        raise IRCompileError(f"評価エラー: {e}", expr=expr, cause=e) from e


def safe_eval_expr_hp(expr: str, context: dict[str, Any]) -> Any:
    """HP モード用: float/int リテラルを mpf('...') に変換してから評価する。

    ``safe_eval_expr`` と同一のセキュリティ制約を持つが、数値リテラルを
    自動的に mpf 呼び出しに変換するため、HP モード内での float 混入を防ぐ。

    Args:
        expr: 評価するPython式
        context: 変数・関数を含む評価コンテキスト。``mpf`` キーを含む必要がある。

    Returns:
        式の評価結果 (数値リテラルは mpf として評価される)

    Raises:
        IRCompileError: 構文エラーまたは評価エラー
        IRSecurityError: 危険なパターンが検出された場合
    """
    try:
        code = _compile_expr_hp_cached(expr)
        return eval(code, {"__builtins__": {}, "_dsl_call": runtime_call}, context)
    except (IRCompileError, IRSecurityError, TimeoutError):
        raise
    except Exception as e:
        raise IRCompileError(f"評価エラー (HP モード): {e}", expr=expr, cause=e) from e
