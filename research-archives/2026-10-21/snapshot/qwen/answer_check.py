"""Conservative, CPU-only parsing of committed exact numerical answers.

Unknown syntax is unparsed, never silently deleted. In particular, nested
fractions are parsed structurally and intermediate thinking is not an answer.
"""

from __future__ import annotations

import re

import sympy as s

PARSER_VERSION = "exact-numeric-v2"


class AnswerSyntaxError(ValueError):
    """The response is not an unambiguous supported numerical expression."""


_TOKEN = re.compile(
    r"\s*(?:(?P<number>(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)"
    r"|(?P<command>\\[A-Za-z]+)|(?P<name>[A-Za-z]+)"
    r"|(?P<operator>\*\*|[+\-*/^(){}\[\]|√π]))"
)


def _tokens(text: str) -> list[str]:
    if len(text) > 4096:
        raise AnswerSyntaxError("expression too long")
    text = text.translate(
        str.maketrans({"−": "-", "–": "-", "×": "*", "÷": "/", "²": "^2", "³": "^3"})
    )
    text = re.sub(r"\\(?:left|right|big|Big)\b", "", text)
    text = re.sub(r"\\(?:,|!|;|:| )", " ", text)
    text = text.replace("$", "").strip()
    result = []
    pos = 0
    while pos < len(text):
        match = _TOKEN.match(text, pos)
        if not match:
            raise AnswerSyntaxError(f"unsupported syntax at {text[pos : pos + 20]!r}")
        token = match.group(match.lastgroup)
        result.append(token)
        pos = match.end()
        if len(result) > 512:
            raise AnswerSyntaxError("too many tokens")
    return result


class _Parser:
    def __init__(self, text: str):
        self.tokens = _tokens(text)
        self.pos = 0

    def peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def take(self, expected=None):
        token = self.peek()
        if token is None or (expected is not None and token != expected):
            raise AnswerSyntaxError(f"expected {expected!r}, got {token!r}")
        self.pos += 1
        return token

    def group(self, left="{", right="}"):
        self.take(left)
        value = self.sum()
        self.take(right)
        return value

    def sum(self):
        value = self.product()
        while self.peek() in ("+", "-"):
            op = self.take()
            other = self.product()
            value = value + other if op == "+" else value - other
        return value

    def product(self):
        value = self.unary()
        while True:
            token = self.peek()
            if token in ("*", "/", r"\cdot", r"\times", r"\div"):
                self.take()
                other = self.unary()
                value = value / other if token in ("/", r"\div") else value * other
            elif token is not None and (
                token[0].isdigit()
                or token[0] == "."
                or token
                in (
                    "(",
                    "{",
                    "sqrt",
                    r"\sqrt",
                    "√",
                    "pi",
                    r"\pi",
                    "π",
                    r"\frac",
                    r"\dfrac",
                    r"\tfrac",
                    "abs",
                )
            ):
                value *= self.unary()
            else:
                return value

    def unary(self):
        if self.peek() in ("+", "-"):
            sign = self.take()
            value = self.unary()
            return value if sign == "+" else -value
        value = self.atom()
        if self.peek() in ("^", "**"):
            self.take()
            exponent = self.unary()
            if not exponent.is_Rational or abs(exponent) > 64:
                raise AnswerSyntaxError("unsupported exponent")
            value **= exponent
        return value

    def atom(self):
        token = self.peek()
        if token in ("(", "{"):
            return self.group(token, ")" if token == "(" else "}")
        if token in (r"\frac", r"\dfrac", r"\tfrac"):
            self.take()
            numerator = self.group()
            denominator = self.group()
            return numerator / denominator
        if token in ("sqrt", r"\sqrt", "√"):
            self.take()
            index = s.Integer(2)
            if self.peek() == "[":
                index = self.group("[", "]")
                if not index.is_Integer or not 2 <= index <= 32:
                    raise AnswerSyntaxError("unsupported root index")
            return self.atom() ** (1 / index)
        if token == "abs":
            self.take()
            return s.Abs(self.group("(", ")"))
        if token in ("pi", r"\pi", "π"):
            self.take()
            return s.pi
        if token is not None and re.fullmatch(r"(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", token):
            self.take()
            if len(token) > 128:
                raise AnswerSyntaxError("number too long")
            if "e" in token.lower() and abs(int(token.lower().split("e")[1])) > 128:
                raise AnswerSyntaxError("decimal exponent too large")
            return s.Rational(token)
        raise AnswerSyntaxError(f"unsupported atom {token!r}")


def parse_numeric(text: str):
    parser = _Parser(text)
    value = parser.sum()
    if parser.peek() is not None:
        raise AnswerSyntaxError("trailing syntax")
    if value.free_symbols or value.is_real is not True or value.is_finite is not True:
        raise AnswerSyntaxError("answer must be a finite real constant")
    return value


def _to_expr(text: str) -> str | None:
    try:
        return s.sstr(parse_numeric(text))
    except (AnswerSyntaxError, ValueError, TypeError, ZeroDivisionError, RecursionError):
        return None


def final_text(raw_text: str) -> str | None:
    if "<think>" in raw_text and "</think>" not in raw_text:
        return None
    text = raw_text.rsplit("</think>", 1)[-1]
    return text.replace("<|im_end|>", "").replace("<|endoftext|>", "").strip()


def extract_answer(raw_text: str) -> str | None:
    """Read the last committed box, explicit answer line, or bare expression.

    Do not search for an arbitrary number or equation in an unfinished proof.
    An invalid final box never falls back to an earlier, convenient answer.
    """
    text = final_text(raw_text)
    if not text:
        return None
    boxes = list(re.finditer(r"\\boxed\s*\{", text))
    if boxes:
        start = boxes[-1].end()
        depth, end = 1, start
        while end < len(text) and depth:
            depth += text[end] == "{"
            depth -= text[end] == "}"
            end += 1
        return _to_expr(text[start : end - 1]) if depth == 0 else None
    explicit = list(
        re.finditer(
            r"(?:答えは|答え[：:]|(?:Final\s+)?Answer\s*(?:is|:))\s*([^\n]+)",
            text,
            flags=re.IGNORECASE,
        )
    )
    candidate = explicit[-1].group(1).strip() if explicit else text
    candidate = re.sub(r"(?:である|です)?[。.]$", "", candidate.strip())
    candidate = candidate.removeprefix(r"\(").removesuffix(r"\)")
    candidate = candidate.removeprefix(r"\[").removesuffix(r"\]")
    return _to_expr(candidate)


def answers_equal(got: str | None, expected: str) -> bool | None:
    """Exact equality, without a floating tolerance that accepts near misses."""
    want = parse_numeric(expected)  # Invalid labels are dataset errors.
    if got is None:
        return None
    try:
        have = parse_numeric(got)
    except (AnswerSyntaxError, ValueError, TypeError, ZeroDivisionError):
        return None
    return s.simplify(have - want) == 0
