import katex from "katex";
import "katex/dist/katex.min.css";
import { memo, useMemo } from "react";

type Token = { kind: "id" | "number" | "op" | "punct"; value: string };
type Node =
  | { kind: "atom"; value: string; atom: "id" | "number" }
  | { kind: "call"; name: string; args: Node[] }
  | { kind: "tuple"; items: Node[] }
  | { kind: "unary"; op: string; value: Node }
  | { kind: "binary"; op: string; left: Node; right: Node };

const RELATION_TEX: Record<string, string> = {
  "=": "=",
  "==": "=",
  "!=": "\\ne",
  "≠": "\\ne",
  "<": "<",
  "<=": "\\le",
  "≤": "\\le",
  ">": ">",
  ">=": "\\ge",
  "≥": "\\ge",
};

const FUNCTION_TEX: Record<string, string> = {
  Sin: "\\sin",
  Cos: "\\cos",
  Tan: "\\tan",
  Asin: "\\arcsin",
  Acos: "\\arccos",
  Atan: "\\arctan",
  Exp: "\\exp",
  Log: "\\log",
  Ln: "\\ln",
};

function tokenize(source: string): Token[] {
  const tokens: Token[] = [];
  let index = 0;
  while (index < source.length) {
    const rest = source.slice(index);
    const space = /^\s+/.exec(rest);
    if (space) {
      index += space[0].length;
      continue;
    }
    const number = /^(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?/.exec(rest);
    if (number) {
      tokens.push({ kind: "number", value: number[0] });
      index += number[0].length;
      continue;
    }
    const id = /^[A-Za-z_][A-Za-z0-9_]*|^[π∞]/.exec(rest);
    if (id) {
      tokens.push({ kind: "id", value: id[0] });
      index += id[0].length;
      continue;
    }
    const op = /^(?:\*\*|<=|>=|==|!=|≤|≥|≠|[+\-*/^=<>])/.exec(rest);
    if (op) {
      tokens.push({ kind: "op", value: op[0] });
      index += op[0].length;
      continue;
    }
    if ("(),[]".includes(source[index])) {
      tokens.push({ kind: "punct", value: source[index] });
      index += 1;
      continue;
    }
    throw new Error(`Unsupported formula character: ${source[index]}`);
  }
  return tokens;
}

const PRECEDENCE: Record<string, number> = {
  "=": 1,
  "==": 1,
  "!=": 1,
  "≠": 1,
  "<": 1,
  "<=": 1,
  "≤": 1,
  ">": 1,
  ">=": 1,
  "≥": 1,
  "+": 2,
  "-": 2,
  "*": 3,
  "/": 3,
  "^": 4,
  "**": 4,
};

class Parser {
  private index = 0;

  constructor(private readonly tokens: Token[]) {}

  parse(): Node {
    const node = this.expression(0);
    if (this.index !== this.tokens.length) throw new Error("Trailing tokens");
    return node;
  }

  private expression(minPrecedence: number): Node {
    let left = this.prefix();
    while (true) {
      const token = this.tokens[this.index];
      const precedence = token?.kind === "op" ? PRECEDENCE[token.value] : 0;
      if (!precedence || precedence < minPrecedence) break;
      this.index += 1;
      const rightAssociative = token.value === "^" || token.value === "**";
      const right = this.expression(precedence + (rightAssociative ? 0 : 1));
      left = { kind: "binary", op: token.value, left, right };
    }
    return left;
  }

  private prefix(): Node {
    const token = this.tokens[this.index];
    if (!token) throw new Error("Expected expression");
    if (token.kind === "op" && ["+", "-"].includes(token.value)) {
      this.index += 1;
      return { kind: "unary", op: token.value, value: this.expression(4) };
    }
    if (token.kind === "number") {
      this.index += 1;
      return { kind: "atom", atom: "number", value: token.value };
    }
    if (token.kind === "id") {
      this.index += 1;
      if (this.tokens[this.index]?.value !== "(")
        return { kind: "atom", atom: "id", value: token.value };
      this.index += 1;
      return { kind: "call", name: token.value, args: this.list(")") };
    }
    if (token.value === "(" || token.value === "[") {
      this.index += 1;
      const close = token.value === "(" ? ")" : "]";
      const items = this.list(close);
      return items.length === 1 ? items[0] : { kind: "tuple", items };
    }
    throw new Error("Expected formula atom");
  }

  private list(close: string): Node[] {
    const items: Node[] = [];
    if (this.tokens[this.index]?.value === close) {
      this.index += 1;
      return items;
    }
    while (this.index < this.tokens.length) {
      items.push(this.expression(0));
      const token = this.tokens[this.index];
      if (token?.value === close) {
        this.index += 1;
        return items;
      }
      if (token?.value !== ",") throw new Error(`Expected ${close}`);
      this.index += 1;
    }
    throw new Error(`Expected ${close}`);
  }
}

function escapeTexText(value: string): string {
  return value.replace(/[\\{}$&#_%~^]/g, (character) => {
    const names: Record<string, string> = {
      "\\": "\\textbackslash{}",
      "{": "\\{",
      "}": "\\}",
      "$": "\\$",
      "&": "\\&",
      "#": "\\#",
      "_": "\\_",
      "%": "\\%",
      "~": "\\textasciitilde{}",
      "^": "\\textasciicircum{}",
    };
    return names[character];
  });
}

function identifier(value: string): string {
  if (value === "pi" || value === "π") return "\\pi";
  if (value === "inf" || value === "infinity" || value === "∞") return "\\infty";
  const greek: Record<string, string> = {
    alpha: "\\alpha",
    beta: "\\beta",
    gamma: "\\gamma",
    delta: "\\delta",
    epsilon: "\\varepsilon",
    theta: "\\theta",
    lambda: "\\lambda",
    mu: "\\mu",
    rho: "\\rho",
    sigma: "\\sigma",
    phi: "\\varphi",
    omega: "\\omega",
  };
  if (greek[value]) return greek[value];
  const namedSubscript = /^([A-Za-z][A-Za-z0-9]*)_([A-Za-z0-9]+)$/.exec(
    value,
  );
  if (namedSubscript)
    return `${identifier(namedSubscript[1])}_{${identifier(namedSubscript[2])}}`;
  const match = /^([A-Za-z]+)_?(\d+)$/.exec(value);
  if (match) return `${escapeTexText(match[1])}_{${match[2]}}`;
  return escapeTexText(value);
}

function simpleId(node: Node): string | undefined {
  return node.kind === "atom" && node.atom === "id"
    ? identifier(node.value)
    : undefined;
}

function joinedPointIds(args: Node[]): string | undefined {
  const ids = args.map(simpleId);
  return ids.every(Boolean) ? ids.join("") : undefined;
}

function renderCall(name: string, args: Node[]): string {
  const values = args.map((arg) => renderNode(arg));
  const points = joinedPointIds(args);
  if (name === "Distance" && args.length === 2 && points)
    return `\\left|${points}\\right|`;
  if (name === "Segment" && args.length === 2 && points)
    return `\\overline{${points}}`;
  if (name === "Line" && args.length === 2 && points)
    return `\\overleftrightarrow{${points}}`;
  if (name === "Ray" && args.length === 2 && points)
    return `\\overrightarrow{${points}}`;
  if (name === "Angle" && args.length === 3 && points)
    return `\\angle ${points}`;
  if (name === "Ratio" && args.length === 2)
    return `\\frac{${values[0]}}{${values[1]}}`;
  if (["Sqrt", "sqrt"].includes(name) && args.length === 1)
    return `\\sqrt{${values[0]}}`;
  if (["Abs", "abs"].includes(name) && args.length === 1)
    return `\\left|${values[0]}\\right|`;
  if (name === "Point" && args.length === 2)
    return `\\left(${values.join(",\\,")}\\right)`;
  if (name === "Vector" && args.length === 2 && points)
    return `\\overrightarrow{${points}}`;
  if (name === "Dot" && args.length === 2)
    return `\\left\langle ${values[0]}, ${values[1]} \\right\rangle`;
  if (name === "Intersection" && args.length === 2)
    return `${values[0]} \\cap ${values[1]}`;
  if (FUNCTION_TEX[name])
    return `${FUNCTION_TEX[name]}\\left(${values.join(",\\,")}\\right)`;
  const label = name.replace(/([a-z0-9])([A-Z])/g, "$1 $2");
  return `\\operatorname{${escapeTexText(label)}}\\left(${values.join(",\\,")}\\right)`;
}

function renderNode(node: Node, parentPrecedence = 0): string {
  if (node.kind === "atom")
    return node.atom === "id" ? identifier(node.value) : node.value;
  if (node.kind === "call") return renderCall(node.name, node.args);
  if (node.kind === "tuple")
    return `\\left(${node.items.map((item) => renderNode(item)).join(",\\,")}\\right)`;
  if (node.kind === "unary") return `${node.op}${renderNode(node.value, 4)}`;
  const precedence = PRECEDENCE[node.op] ?? 0;
  let result: string;
  if (node.op === "/")
    result = `\\frac{${renderNode(node.left)}}{${renderNode(node.right)}}`;
  else if (node.op === "^" || node.op === "**")
    result = `{${renderNode(node.left, precedence)}}^{${renderNode(node.right)}}`;
  else {
    const operator =
      RELATION_TEX[node.op] ??
      (node.op === "*" ? "\\,\\cdot\\," : node.op === "-" ? "\\,-\\," : "\\,+\\,");
    result = `${renderNode(node.left, precedence)} ${operator} ${renderNode(node.right, precedence + 1)}`;
  }
  return precedence < parentPrecedence ? `\\left(${result}\\right)` : result;
}

export function expressionToTex(source: string): string {
  const value = source.trim();
  if (!value) return "\\text{—}";
  try {
    return renderNode(new Parser(tokenize(value)).parse());
  } catch {
    return `\\mathtt{${escapeTexText(value)}}`;
  }
}

export function polynomialToTex(coefficients: Array<number | string>): string {
  const degree = coefficients.length - 1;
  if (degree < 0) return "\\text{—}";
  const terms = coefficients.flatMap((raw, index) => {
    const coefficient = String(raw);
    const power = degree - index;
    if (coefficient === "0" || coefficient === "0.0") return [];
    const sign = coefficient.startsWith("-") ? "-" : "+";
    const magnitude = sign === "-" ? coefficient.slice(1) : coefficient;
    const factor = power > 0 && magnitude === "1" ? "" : magnitude;
    const variable = power === 0 ? "" : power === 1 ? "x" : `x^{${power}}`;
    return [{ sign, value: `${factor}${factor && variable ? "\\," : ""}${variable}` }];
  });
  if (!terms.length) return "0";
  return terms
    .map((term, index) =>
      index === 0 && term.sign === "+"
        ? term.value
        : `${term.sign === "+" ? "+" : "-"}\\,${term.value}`,
    )
    .join("\\,");
}

type MathFormulaProps = {
  source: string;
  className?: string;
  display?: boolean;
  label?: string;
  tex?: string;
};

export const MathFormula = memo(function MathFormula({
  source,
  className = "",
  display = false,
  label,
  tex,
}: MathFormulaProps) {
  const formula = tex ?? expressionToTex(source);
  const html = useMemo(
    () =>
      katex.renderToString(formula, {
        displayMode: display,
        throwOnError: false,
        strict: "ignore",
        trust: false,
        maxExpand: 200,
        output: "html",
      }),
    [display, formula],
  );
  return (
    <span
      className={`math-formula${display ? " math-formula-display" : ""}${className ? ` ${className}` : ""}`}
      role="math"
      aria-label={label ?? source}
      title={source}
    >
      <span
        className="math-render"
        aria-hidden="true"
        dangerouslySetInnerHTML={{ __html: html }}
      />
      <span className="visually-hidden math-source">{source}</span>
    </span>
  );
});
