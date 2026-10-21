"""
IR (Intermediate Representation) エラー定義

IRの解析・コンパイル時に発生するエラーを定義。
"""


class IRError(Exception):
    """IR関連エラーの基底クラス"""

    pass


class IRValidationError(IRError):
    """IR検証エラー

    IRスキーマ違反、不正な値、未定義の参照など。
    """

    def __init__(self, message: str, field: str = None, cause: Exception = None):
        super().__init__(message)
        self.field = field
        self.cause = cause

    def __str__(self):
        msg = super().__str__()
        if self.field:
            msg = f"{self.field}: {msg}"
        return msg


class IRCompileError(IRError):
    """IRコンパイルエラー

    式の解析やコード生成に失敗した場合。
    """

    def __init__(self, message: str, expr: str = None, cause: Exception = None):
        super().__init__(message)
        self.expr = expr
        self.cause = cause

    def __str__(self):
        msg = super().__str__()
        if self.expr:
            msg = f"{msg} (expr: {self.expr!r})"
        return msg


class IRSecurityError(IRError):
    """IRセキュリティエラー

    危険なコードパターンが検出された場合。
    """

    def __init__(self, message: str, pattern: str = None):
        super().__init__(message)
        self.pattern = pattern
