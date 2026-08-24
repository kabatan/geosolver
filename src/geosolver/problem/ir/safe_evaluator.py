"""Safe AST evaluator used by IR compiler."""

import ast
import operator
from typing import Dict, Any, Callable

from geosolver.problem.ir.errors import IRCompileError, IRSecurityError


class SafeEvaluator(ast.NodeVisitor):
    """
    安全なAST評価器

    許可されたノードのみを評価し、任意のコード実行を防ぐ。
    """

    BINARY_OPS: Dict[type, Callable] = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
    }

    UNARY_OPS: Dict[type, Callable] = {
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
        ast.Not: operator.not_,
    }

    COMPARE_OPS: Dict[type, Callable] = {
        ast.Eq: operator.eq,
        ast.NotEq: operator.ne,
        ast.Lt: operator.lt,
        ast.LtE: operator.le,
        ast.Gt: operator.gt,
        ast.GtE: operator.ge,
    }

    def __init__(self, context: Dict[str, Any]):
        self.context = context

    def visit_Expression(self, node: ast.Expression) -> Any:
        return self.visit(node.body)

    def visit_Constant(self, node: ast.Constant) -> Any:
        return node.value

    def visit_Num(self, node: ast.Num) -> Any:
        """Python 3.7互換"""
        return node.n

    def visit_Str(self, node: ast.Str) -> Any:
        """Python 3.7互換"""
        return node.s

    def visit_Name(self, node: ast.Name) -> Any:
        name = node.id
        if name not in self.context:
            raise IRCompileError(f"未定義の変数: {name!r}")
        return self.context[name]

    def visit_BinOp(self, node: ast.BinOp) -> Any:
        left = self.visit(node.left)
        right = self.visit(node.right)
        op_func = self.BINARY_OPS.get(type(node.op))
        if op_func is None:
            raise IRCompileError(f"未対応の二項演算子: {type(node.op).__name__}")
        return op_func(left, right)

    def visit_UnaryOp(self, node: ast.UnaryOp) -> Any:
        operand = self.visit(node.operand)
        op_func = self.UNARY_OPS.get(type(node.op))
        if op_func is None:
            raise IRCompileError(f"未対応の単項演算子: {type(node.op).__name__}")
        return op_func(operand)

    def visit_Compare(self, node: ast.Compare) -> Any:
        left = self.visit(node.left)
        for op, comparator in zip(node.ops, node.comparators):
            right = self.visit(comparator)
            op_func = self.COMPARE_OPS.get(type(op))
            if op_func is None:
                raise IRCompileError(f"未対応の比較演算子: {type(op).__name__}")
            if not op_func(left, right):
                return False
            left = right
        return True

    def visit_BoolOp(self, node: ast.BoolOp) -> Any:
        if isinstance(node.op, ast.And):
            result = True
            for value in node.values:
                result = result and self.visit(value)
                if not result:
                    return False
            return result
        if isinstance(node.op, ast.Or):
            for value in node.values:
                result = self.visit(value)
                if result:
                    return result
            return False
        raise IRCompileError(f"未対応のブール演算子: {type(node.op).__name__}")

    def visit_IfExp(self, node: ast.IfExp) -> Any:
        test = self.visit(node.test)
        if test:
            return self.visit(node.body)
        return self.visit(node.orelse)

    def visit_Call(self, node: ast.Call) -> Any:
        func = self.visit(node.func)
        if not callable(func):
            raise IRCompileError(f"呼び出し不可能なオブジェクト: {func!r}")

        args = [self.visit(arg) for arg in node.args]
        kwargs = {kw.arg: self.visit(kw.value) for kw in node.keywords}

        try:
            return func(*args, **kwargs)
        except Exception as e:
            raise IRCompileError(f"関数呼び出しエラー: {e}", cause=e) from e

    def visit_Attribute(self, node: ast.Attribute) -> Any:
        value = self.visit(node.value)
        attr = node.attr
        if attr.startswith("_"):
            raise IRSecurityError(f"プライベート属性へのアクセス禁止: {attr}")
        try:
            return getattr(value, attr)
        except AttributeError as e:
            raise IRCompileError(f"属性エラー: {e}", cause=e) from e

    def visit_Subscript(self, node: ast.Subscript) -> Any:
        value = self.visit(node.value)
        if isinstance(node.slice, ast.Index):
            index = self.visit(node.slice.value)
        else:
            index = self.visit(node.slice)
        try:
            return value[index]
        except (KeyError, IndexError, TypeError) as e:
            raise IRCompileError(f"添字アクセスエラー: {e}", cause=e) from e

    def visit_Tuple(self, node: ast.Tuple) -> tuple:
        return tuple(self.visit(elt) for elt in node.elts)

    def visit_List(self, node: ast.List) -> list:
        return [self.visit(elt) for elt in node.elts]

    def generic_visit(self, node: ast.AST) -> Any:
        raise IRCompileError(f"未対応のASTノード: {type(node).__name__}")
