/**
 * A deliberately small, non-executable interpreter for the drawable subset of
 * the GeoSolver construction language.  This module never evaluates JavaScript and
 * treats unsupported expressions as data, reported through Scene.warnings.
 */

export type Vec2 = Readonly<{ x: number; y: number }>;

export type Viewport = Readonly<{
  width: number;
  height: number;
  center: Vec2;
  pixelsPerUnit: number;
}>;

export type ConstructionInput = Readonly<{ name: string; expr: string }>;
export type ConstraintInput = Readonly<{ def: string; value: number | string }>;

type SceneItemBase = Readonly<{ name: string; source: string }>;

export type ScenePoint = SceneItemBase & Readonly<{
  kind: "point";
  position: Vec2;
}>;

export type SceneLine = SceneItemBase & Readonly<{
  kind: "line";
  anchor: Vec2;
  direction: Vec2;
  /** Normal coefficient orientation used by GeoSolver Line(a,b,c). */
  normal: Vec2;
}>;

export type SceneSegment = SceneItemBase & Readonly<{
  kind: "segment";
  start: Vec2;
  end: Vec2;
}>;

export type SceneRay = SceneItemBase & Readonly<{
  kind: "ray";
  start: Vec2;
  direction: Vec2;
}>;

export type SceneVector = SceneItemBase & Readonly<{
  kind: "vector";
  start: Vec2;
  end: Vec2;
}>;

export type SceneCircle = SceneItemBase & Readonly<{
  kind: "circle";
  center: Vec2;
  radius: number;
}>;

export type SceneArc = SceneItemBase & Readonly<{
  kind: "arc"; center: Vec2; radius: number; startAngle: number; endAngle: number; counterclockwise: boolean;
}>;

export type ScenePolygon = SceneItemBase & Readonly<{
  kind: "polygon";
  vertices: readonly Vec2[];
}>;

export type SceneItem =
  | ScenePoint
  | SceneLine
  | SceneSegment
  | SceneRay
  | SceneVector
  | SceneCircle
  | SceneArc
  | ScenePolygon;

export type SceneWarning = Readonly<{
  name: string;
  expression: string;
  message: string;
}>;

export type Scene = Readonly<{
  items: readonly SceneItem[];
  byName: ReadonlyMap<string, SceneItem>;
  warnings: readonly SceneWarning[];
}>;

export type IntersectionCandidate = Readonly<{
  first: string;
  second: string;
  position: Vec2;
  distance: number;
  /** Every geometrically valid branch for this pair, in deterministic order. */
  alternatives: readonly Vec2[];
}>;

/** @deprecated Use IntersectionCandidate. Kept for source compatibility. */
export type LineIntersectionCandidate = IntersectionCandidate;

export type KeywordArgument = Readonly<{ name: string; value: ExpressionNode }>;

export type ExpressionNode =
  | Readonly<{ type: "number"; value: number }>
  | Readonly<{ type: "string"; value: string }>
  | Readonly<{ type: "identifier"; name: string }>
  | Readonly<{ type: "list"; items: readonly ExpressionNode[] }>
  | Readonly<{
      type: "call";
      name: string;
      arguments: readonly ExpressionNode[];
      keywordArguments: readonly KeywordArgument[];
    }>
  | Readonly<{ type: "unary"; operator: "+" | "-"; argument: ExpressionNode }>
  | Readonly<{
      type: "binary";
      operator: "+" | "-" | "*" | "/" | "^" | "**";
      left: ExpressionNode;
      right: ExpressionNode;
    }>;

class ParseFailure extends Error {}

class Parser {
  private index = 0;

  constructor(private readonly input: string) {}

  parse(): ExpressionNode {
    const node = this.parseSum();
    this.skipWhitespace();
    if (this.index !== this.input.length) this.fail("式の末尾に解釈できない文字があります");
    return node;
  }

  private parseSum(): ExpressionNode {
    let left = this.parseProduct();
    while (true) {
      const operator = this.takeOneOf(["+", "-"] as const);
      if (!operator) return left;
      left = { type: "binary", operator, left, right: this.parseProduct() };
    }
  }

  private parseProduct(): ExpressionNode {
    let left = this.parsePower();
    while (true) {
      this.skipWhitespace();
      if (this.input.startsWith("**", this.index)) return left;
      const operator = this.takeOneOf(["*", "/"] as const);
      if (!operator) return left;
      left = { type: "binary", operator, left, right: this.parsePower() };
    }
  }

  private parsePower(): ExpressionNode {
    const left = this.parseUnary();
    const operator = this.takeOneOf(["**", "^"] as const);
    return operator
      ? { type: "binary", operator, left, right: this.parsePower() }
      : left;
  }

  private parseUnary(): ExpressionNode {
    const operator = this.takeOneOf(["+", "-"] as const);
    return operator
      ? { type: "unary", operator, argument: this.parseUnary() }
      : this.parsePrimary();
  }

  private parsePrimary(): ExpressionNode {
    this.skipWhitespace();
    if (this.take("[")) {
      const items: ExpressionNode[] = [];
      if (!this.peek("]")) {
        do items.push(this.parseSum());
        while (this.take(","));
      }
      if (!this.take("]")) this.fail("リストの閉じ角括弧がありません");
      return { type: "list", items };
    }
    if (this.take("(")) {
      const node = this.parseSum();
      if (!this.take(")")) this.fail("閉じ括弧がありません");
      return node;
    }

    const quoted = this.readString();
    if (quoted !== undefined) return { type: "string", value: quoted };
    const number = this.readNumber();
    if (number !== undefined) return { type: "number", value: number };

    const identifier = this.readIdentifier();
    if (!identifier) this.fail("数値、識別子、または関数呼び出しが必要です");
    if (!this.take("(")) return { type: "identifier", name: identifier };

    const args: ExpressionNode[] = [];
    const keywordArguments: KeywordArgument[] = [];
    if (!this.peek(")")) {
      do {
        const savedIndex = this.index;
        const keyword = this.readIdentifier();
        if (keyword && this.take("=")) {
          if (keywordArguments.some((argument) => argument.name === keyword)) {
            this.fail(`keyword ${keyword} が重複しています`);
          }
          keywordArguments.push({ name: keyword, value: this.parseSum() });
        } else {
          this.index = savedIndex;
          if (keywordArguments.length > 0) this.fail("keyword引数の後に位置引数は置けません");
          args.push(this.parseSum());
        }
      }
      while (this.take(","));
    }
    if (!this.take(")")) this.fail("関数呼び出しの閉じ括弧がありません");
    return { type: "call", name: identifier, arguments: args, keywordArguments };
  }

  private readString(): string | undefined {
    this.skipWhitespace();
    const quote = this.input[this.index];
    if (quote !== "'" && quote !== '"') return undefined;
    const end = this.input.indexOf(quote, this.index + 1);
    if (end < 0) this.fail("文字列の閉じ引用符がありません");
    const value = this.input.slice(this.index + 1, end);
    this.index = end + 1;
    return value;
  }

  private readNumber(): number | undefined {
    this.skipWhitespace();
    const match = /^(?:(?:\d+(?:\.\d*)?)|(?:\.\d+))(?:[eE][+-]?\d+)?/.exec(this.input.slice(this.index));
    if (!match) return undefined;
    this.index += match[0].length;
    const value = Number(match[0]);
    if (!Number.isFinite(value)) this.fail("有限な数値だけを使用できます");
    return value;
  }

  private readIdentifier(): string | undefined {
    this.skipWhitespace();
    const match = /^[A-Za-z_][A-Za-z0-9_]*/.exec(this.input.slice(this.index));
    if (!match) return undefined;
    this.index += match[0].length;
    return match[0];
  }

  private take(value: string): boolean {
    this.skipWhitespace();
    if (!this.input.startsWith(value, this.index)) return false;
    this.index += value.length;
    return true;
  }

  private peek(value: string): boolean {
    this.skipWhitespace();
    return this.input.startsWith(value, this.index);
  }

  private takeOneOf<const T extends readonly string[]>(values: T): T[number] | undefined {
    this.skipWhitespace();
    const found = values.find((value) => this.input.startsWith(value, this.index));
    if (!found) return undefined;
    this.index += found.length;
    return found;
  }

  private skipWhitespace(): void {
    while (/\s/.test(this.input[this.index] ?? "")) this.index += 1;
  }

  private fail(message: string): never {
    throw new ParseFailure(`${message}（${this.index + 1}文字目）`);
  }
}

/** Parse a GeoSolver-style expression without executing it. */
export function parseExpression(source: string): ExpressionNode {
  if (!source.trim()) throw new ParseFailure("式が空です");
  return new Parser(source).parse();
}

function scalar(node: ExpressionNode, variables: ReadonlyMap<string, number>): number | undefined {
  if (node.type === "number") return node.value;
  if (node.type === "identifier") {
    if (node.name === "pi" || node.name === "PI") return Math.PI;
    if (node.name === "e" || node.name === "E") return Math.E;
    return variables.get(node.name);
  }
  if (node.type === "unary") {
    const value = scalar(node.argument, variables);
    return value === undefined ? undefined : node.operator === "-" ? -value : value;
  }
  if (node.type !== "binary") return undefined;
  const left = scalar(node.left, variables);
  const right = scalar(node.right, variables);
  if (left === undefined || right === undefined) return undefined;
  let result: number;
  switch (node.operator) {
    case "+": result = left + right; break;
    case "-": result = left - right; break;
    case "*": result = left * right; break;
    case "/": result = left / right; break;
    case "^":
    case "**": result = left ** right; break;
  }
  return Number.isFinite(result) ? result : undefined;
}

const subtract = (a: Vec2, b: Vec2): Vec2 => ({ x: a.x - b.x, y: a.y - b.y });
const add = (a: Vec2, b: Vec2): Vec2 => ({ x: a.x + b.x, y: a.y + b.y });
const scale = (a: Vec2, factor: number): Vec2 => ({ x: a.x * factor, y: a.y * factor });
const cross = (a: Vec2, b: Vec2): number => a.x * b.y - a.y * b.x;
const length = (a: Vec2): number => Math.hypot(a.x, a.y);
const EPSILON = 1e-10;

function pointFrom(node: ExpressionNode, objects: ReadonlyMap<string, SceneItem>): Vec2 | undefined {
  if (node.type !== "identifier") return undefined;
  const item = objects.get(node.name);
  return item?.kind === "point" ? item.position : undefined;
}

function lineFrom(node: ExpressionNode, objects: ReadonlyMap<string, SceneItem>): Pick<SceneLine, "anchor" | "direction"> & Partial<Pick<SceneLine, "normal">> | undefined {
  if (node.type === "call" && node.name === "Line") {
    const points = twoPoints(node.arguments, objects);
    if (!points) return undefined;
    const direction = subtract(points[1], points[0]);
    if (length(direction) < EPSILON) return undefined;
    return { anchor: points[0], direction, normal: { x: -direction.y, y: direction.x } };
  }
  if (node.type !== "identifier") return undefined;
  const item = objects.get(node.name);
  if (!item) return undefined;
  if (item.kind === "line") return item;
  if (item.kind === "segment" || item.kind === "vector") return { anchor: item.start, direction: subtract(item.end, item.start) };
  if (item.kind === "ray") return { anchor: item.start, direction: item.direction };
  return undefined;
}

function circleFrom(node: ExpressionNode, objects: ReadonlyMap<string, SceneItem>): SceneCircle | SceneArc | undefined {
  if (node.type !== "identifier") return undefined;
  const item = objects.get(node.name);
  return item?.kind === "circle" || item?.kind === "arc" ? item : undefined;
}

function projection(point: Vec2, line: Pick<SceneLine, "anchor" | "direction">): Vec2 | undefined {
  const denominator = line.direction.x ** 2 + line.direction.y ** 2;
  if (denominator < EPSILON) return undefined;
  const parameter = ((point.x - line.anchor.x) * line.direction.x + (point.y - line.anchor.y) * line.direction.y) / denominator;
  return add(line.anchor, scale(line.direction, parameter));
}

function pointAndLine(
  args: readonly ExpressionNode[],
  objects: ReadonlyMap<string, SceneItem>,
  acceptLegacyReverse: boolean,
): { point: Vec2; line: Pick<SceneLine, "anchor" | "direction"> & Partial<Pick<SceneLine, "normal">> } | undefined {
  if (args.length !== 2) return undefined;
  const canonicalPoint = pointFrom(args[0], objects);
  const canonicalLine = lineFrom(args[1], objects);
  if (canonicalPoint && canonicalLine) return { point: canonicalPoint, line: canonicalLine };
  if (!acceptLegacyReverse) return undefined;
  const legacyPoint = pointFrom(args[1], objects);
  const legacyLine = lineFrom(args[0], objects);
  return legacyPoint && legacyLine ? { point: legacyPoint, line: legacyLine } : undefined;
}

function twoPoints(args: readonly ExpressionNode[], objects: ReadonlyMap<string, SceneItem>): readonly [Vec2, Vec2] | undefined {
  if (args.length !== 2) return undefined;
  const first = pointFrom(args[0], objects);
  const second = pointFrom(args[1], objects);
  return first && second ? [first, second] : undefined;
}

function circumcircle(a: Vec2, b: Vec2, c: Vec2): { center: Vec2; radius: number } | undefined {
  const denominator = 2 * (a.x * (b.y - c.y) + b.x * (c.y - a.y) + c.x * (a.y - b.y));
  if (Math.abs(denominator) < EPSILON) return undefined;
  const aa = a.x * a.x + a.y * a.y;
  const bb = b.x * b.x + b.y * b.y;
  const cc = c.x * c.x + c.y * c.y;
  const center = {
    x: (aa * (b.y - c.y) + bb * (c.y - a.y) + cc * (a.y - b.y)) / denominator,
    y: (aa * (c.x - b.x) + bb * (a.x - c.x) + cc * (b.x - a.x)) / denominator,
  };
  return { center, radius: length(subtract(center, a)) };
}

function trianglePoints(args: readonly ExpressionNode[], objects: ReadonlyMap<string, SceneItem>): readonly [Vec2, Vec2, Vec2] | undefined {
  if (args.length !== 3) return undefined;
  const points = args.map((argument) => pointFrom(argument, objects));
  return points[0] && points[1] && points[2] ? [points[0], points[1], points[2]] : undefined;
}

function normalized(vector: Vec2): Vec2 | undefined {
  const magnitude = length(vector);
  return magnitude > EPSILON ? scale(vector, 1 / magnitude) : undefined;
}

function triangleCenter(name: string, points: readonly [Vec2, Vec2, Vec2]): Vec2 | undefined {
  const [a, b, c] = points;
  if (name === "Centroid") return scale(add(add(a, b), c), 1 / 3);
  const circum = circumcircle(a, b, c);
  if (name === "Circumcenter") return circum?.center;
  if (name === "Orthocenter" && circum) return subtract(add(add(a, b), c), scale(circum.center, 2));
  if (name === "NinePointCenter" && circum) {
    const orthocenter = subtract(add(add(a, b), c), scale(circum.center, 2));
    return scale(add(circum.center, orthocenter), 0.5);
  }
  if (name === "Incenter") {
    const wa = length(subtract(b, c));
    const wb = length(subtract(c, a));
    const wc = length(subtract(a, b));
    const sum = wa + wb + wc;
    return sum > EPSILON ? scale(add(add(scale(a, wa), scale(b, wb)), scale(c, wc)), 1 / sum) : undefined;
  }
  const sideA = length(subtract(b, c));
  const sideB = length(subtract(c, a));
  const sideC = length(subtract(a, b));
  const weighted = (wa: number, wb: number, wc: number) => {
    const sum = wa + wb + wc;
    return Math.abs(sum) > EPSILON ? scale(add(add(scale(a, wa), scale(b, wb)), scale(c, wc)), 1 / sum) : undefined;
  };
  if (name === "SymmedianPoint") return weighted(sideA ** 2, sideB ** 2, sideC ** 2);
  const semiperimeter = (sideA + sideB + sideC) / 2;
  if (name === "NagelPoint") return weighted(semiperimeter - sideA, semiperimeter - sideB, semiperimeter - sideC);
  if (name === "GergonnePoint") {
    const wa = semiperimeter - sideA; const wb = semiperimeter - sideB; const wc = semiperimeter - sideC;
    return wa > EPSILON && wb > EPSILON && wc > EPSILON ? weighted(1 / wa, 1 / wb, 1 / wc) : undefined;
  }
  if (name === "Mittenpunkt") return weighted(sideA * (semiperimeter - sideA), sideB * (semiperimeter - sideB), sideC * (semiperimeter - sideC));
  if (name === "SpiekerCenter") return weighted(sideB + sideC, sideC + sideA, sideA + sideB);
  if (name === "FeuerbachPoint") {
    if (sideA < EPSILON || sideB < EPSILON || sideC < EPSILON) return undefined;
    const cosineA = (sideB ** 2 + sideC ** 2 - sideA ** 2) / (2 * sideB * sideC);
    const cosineB = (sideC ** 2 + sideA ** 2 - sideB ** 2) / (2 * sideC * sideA);
    const cosineC = (sideA ** 2 + sideB ** 2 - sideC ** 2) / (2 * sideA * sideB);
    const sineA = Math.sqrt(Math.max(0, 1 - cosineA ** 2));
    const sineB = Math.sqrt(Math.max(0, 1 - cosineB ** 2));
    const sineC = Math.sqrt(Math.max(0, 1 - cosineC ** 2));
    return weighted(
      1 - (cosineB * cosineC + sineB * sineC),
      1 - (cosineC * cosineA + sineC * sineA),
      1 - (cosineA * cosineB + sineA * sineB),
    );
  }
  return undefined;
}

function keywordLiteral(node: ExpressionNode | undefined): string | undefined {
  return node?.type === "string" ? node.value : node?.type === "identifier" ? node.name : node?.type === "number" ? String(node.value) : undefined;
}

function trianglePairCenter(name: "FermatPoint" | "IsodynamicPoint", points: readonly [Vec2, Vec2, Vec2], first: boolean): Vec2 | undefined {
  const [aPoint, bPoint, cPoint] = points;
  const a = length(subtract(bPoint, cPoint)); const b = length(subtract(cPoint, aPoint)); const c = length(subtract(aPoint, bPoint));
  if (a < EPSILON || b < EPSILON || c < EPSILON) return undefined;
  const cosines = [(b * b + c * c - a * a) / (2 * b * c), (c * c + a * a - b * b) / (2 * c * a), (a * a + b * b - c * c) / (2 * a * b)];
  const sines = cosines.map((value) => Math.sqrt(Math.max(0, 1 - value * value)));
  const sign = first ? 1 : -1;
  const shifted = sines.map((value, index) => value * 0.5 + cosines[index] * sign * Math.sqrt(3) / 2);
  const weights = name === "FermatPoint"
    ? sines.map((value, index) => value * shifted[(index + 1) % 3] * shifted[(index + 2) % 3])
    : sines.map((value, index) => value * shifted[index]);
  const total = weights.reduce((sum, value) => sum + value, 0);
  return Math.abs(total) > EPSILON ? scale(add(add(scale(aPoint, weights[0]), scale(bPoint, weights[1])), scale(cPoint, weights[2])), 1 / total) : undefined;
}

function excenter(points: readonly [Vec2, Vec2, Vec2], vertex: string): Vec2 | undefined {
  const index = vertex === "B" || vertex === "1" ? 1 : vertex === "C" || vertex === "2" ? 2 : 0;
  const [a, b, c] = index === 1 ? [points[1], points[2], points[0]] : index === 2 ? [points[2], points[0], points[1]] : points;
  const wa = length(subtract(b, c)); const wb = length(subtract(c, a)); const wc = length(subtract(a, b)); const denominator = -wa + wb + wc;
  return Math.abs(denominator) > EPSILON ? scale(add(add(scale(a, -wa), scale(b, wb)), scale(c, wc)), 1 / denominator) : undefined;
}

function evaluateItem(name: string, source: string, node: ExpressionNode, objects: ReadonlyMap<string, SceneItem>, variables: ReadonlyMap<string, number>): SceneItem | string {
  if (node.type !== "call") return "描画可能な構成関数ではありません";
  const args = node.arguments;
  const base = { name, source };

  if (node.name === "Point") {
    if (args.length !== 2) return "Pointには2個の座標が必要です";
    const x = scalar(args[0], variables);
    const y = scalar(args[1], variables);
    return x === undefined || y === undefined
      ? "Pointの座標を数値として評価できません"
      : { ...base, kind: "point", position: { x, y } };
  }

  if (node.name === "PointOnSegment") {
    if (args.length !== 3) return "PointOnSegmentには2点とparameterが必要です";
    const pair = twoPoints(args.slice(0, 2), objects);
    const parameter = scalar(args[2], variables);
    return !pair || parameter === undefined
      ? "PointOnSegmentには定義済みの2点と数値parameterが必要です"
      : { ...base, kind: "point", position: add(pair[0], scale(subtract(pair[1], pair[0]), parameter)) };
  }

  if (node.name === "PointOnLine") {
    if (args.length !== 2) return "PointOnLineには直線とparameterが必要です";
    const line = lineFrom(args[0], objects);
    const parameter = scalar(args[1], variables);
    const parameterDirection = line?.normal
      ? normalized({ x: -line.normal.y, y: line.normal.x })
      : line && normalized(scale(line.direction, -1));
    if (!line || parameter === undefined || !parameterDirection) return "PointOnLineには定義済みの直線と数値parameterが必要です";
    const basePoint = subtract(line.anchor, scale(parameterDirection, line.anchor.x * parameterDirection.x + line.anchor.y * parameterDirection.y));
    return { ...base, kind: "point", position: add(basePoint, scale(parameterDirection, parameter)) };
  }

  if (node.name === "PointOnCircle") {
    if (args.length !== 2 || args[0].type !== "identifier") return "PointOnCircleには円とparameterが必要です";
    const circle = objects.get(args[0].name);
    const parameter = scalar(args[1], variables);
    if (circle?.kind !== "circle" || parameter === undefined) return "PointOnCircleには定義済みの円と数値parameterが必要です";
    const angle = 2 * Math.PI * parameter;
    return { ...base, kind: "point", position: add(circle.center, { x: circle.radius * Math.cos(angle), y: circle.radius * Math.sin(angle) }) };
  }

  if (["Line", "Segment", "Ray", "Vector"].includes(node.name)) {
    const pair = twoPoints(args, objects);
    if (!pair) return `${node.name}には定義済みの2点が必要です`;
    const [start, end] = pair;
    if (length(subtract(end, start)) < EPSILON) return `${node.name}を同一座標の点から作ることはできません`;
    if (node.name === "Line") { const direction = subtract(end, start); return { ...base, kind: "line", anchor: start, direction, normal: { x: -direction.y, y: direction.x } }; }
    if (node.name === "Segment") return { ...base, kind: "segment", start, end };
    if (node.name === "Ray") return { ...base, kind: "ray", start, direction: subtract(end, start) };
    return { ...base, kind: "vector", start, end };
  }

  if (node.name === "Midpoint") {
    const pair = twoPoints(args, objects);
    if (!pair) return "Midpointには定義済みの2点が必要です";
    return { ...base, kind: "point", position: scale(add(pair[0], pair[1]), 0.5) };
  }

  if (node.name === "PerpendicularBisector") {
    const pair = twoPoints(args, objects);
    if (!pair) return "PerpendicularBisectorには定義済みの2点が必要です";
    const direction = subtract(pair[1], pair[0]);
    if (length(direction) < EPSILON) return "同一座標の2点には垂直二等分線を定義できません";
    return { ...base, kind: "line", anchor: scale(add(pair[0], pair[1]), 0.5), direction: { x: -direction.y, y: direction.x }, normal: direction };
  }

  if (node.name === "AngleBisector") {
    const points = trianglePoints(args, objects);
    if (!points) return "AngleBisectorには定義済みの3点が必要です";
    const [sideA, vertex, sideB] = points;
    const first = normalized(subtract(sideA, vertex));
    const second = normalized(subtract(sideB, vertex));
    const direction = first && second ? add(first, second) : undefined;
    if (!direction || length(direction) < EPSILON) return "角の二等分線を一意に描画できません";
    return { ...base, kind: "line", anchor: vertex, direction, normal: { x: -direction.y, y: direction.x } };
  }

  if (node.name === "ClosestPoint") {
    if (args.length !== 2) return "ClosestPointには点と直線・円が必要です";
    const canonicalPoint = pointFrom(args[0], objects); const legacyPoint = pointFrom(args[1], objects);
    const canonicalLine = lineFrom(args[1], objects); const legacyLine = lineFrom(args[0], objects);
    const canonicalCircle = circleFrom(args[1], objects); const legacyCircle = circleFrom(args[0], objects);
    const point = canonicalPoint ?? legacyPoint;
    const line = canonicalPoint ? canonicalLine : legacyLine;
    const circle = canonicalPoint ? canonicalCircle : legacyCircle;
    if (!point || (!line && !circle)) return "ClosestPointには定義済みの点と直線・円が必要です";
    const position = line ? projection(point, line) : (() => {
      const radial = subtract(point, circle!.center); const direction = normalized(radial);
      return direction ? add(circle!.center, scale(direction, circle!.radius)) : circle!.center;
    })();
    return position ? { ...base, kind: "point", position } : "ClosestPointを一意に描画できません";
  }

  if (node.name === "FootOfPerpendicular") {
    if (args.length !== 2) return `${node.name}には点と直線が必要です`;
    const resolved = pointAndLine(args, objects, true);
    const foot = resolved ? projection(resolved.point, resolved.line) : undefined;
    return foot ? { ...base, kind: "point", position: foot } : `${node.name}には定義済みの点と直線が必要です`;
  }

  if (node.name === "ContactPoint") {
    if (args.length !== 2) return "ContactPointには円と接線が必要です";
    const circle = circleFrom(args[0], objects); const line = lineFrom(args[1], objects);
    const point = circle && line ? projection(circle.center, line) : undefined;
    return point ? { ...base, kind: "point", position: point } : "ContactPointには定義済みの円と直線が必要です";
  }

  if (node.name === "Arc") {
    if (args.length !== 3) return "Arcには円・始点・終点が必要です";
    const circle = circleFrom(args[0], objects); const start = pointFrom(args[1], objects); const end = pointFrom(args[2], objects);
    const including = pointFrom(node.keywordArguments.find((item) => item.name === "including")?.value ?? { type: "identifier", name: "" }, objects);
    if (!circle || !start || !end || !including) return "Arcには定義済みの円・始点・終点・including点が必要です";
    const angle = (point: Vec2) => Math.atan2(point.y - circle.center.y, point.x - circle.center.x);
    const startAngle = angle(start); const endAngle = angle(end); const includingAngle = angle(including); const turn = (value: number) => (value % (2 * Math.PI) + 2 * Math.PI) % (2 * Math.PI);
    return { ...base, kind: "arc", center: circle.center, radius: circle.radius, startAngle, endAngle, counterclockwise: turn(includingAngle - startAngle) <= turn(endAngle - startAngle) };
  }

  if (node.name === "Reflect") {
    if (args.length !== 2) return "Reflectには反転する点と中心点・対称軸が必要です";
    const point = pointFrom(args[0], objects); const center = pointFrom(args[1], objects); const line = lineFrom(args[1], objects);
    if (!point || (!center && !line)) return "Reflectには定義済みの点と中心点・対称軸が必要です";
    if (center) return { ...base, kind: "point", position: subtract(scale(center, 2), point) };
    const foot = projection(point, line!);
    return foot ? { ...base, kind: "point", position: subtract(scale(foot, 2), point) } : "Reflectを一意に描画できません";
  }

  if (["Centroid", "Circumcenter", "Incenter", "Orthocenter", "NinePointCenter", "SymmedianPoint", "GergonnePoint", "NagelPoint", "FeuerbachPoint", "Mittenpunkt", "SpiekerCenter"].includes(node.name)) {
    const points = trianglePoints(args, objects);
    if (!points) return `${node.name}には定義済みの3点が必要です`;
    const position = triangleCenter(node.name, points);
    return position ? { ...base, kind: "point", position } : `${node.name}を一意に描画できません`;
  }

  if (node.name === "FermatPoint" || node.name === "IsodynamicPoint") {
    const points = trianglePoints(args, objects); if (!points) return `${node.name}には定義済みの3点が必要です`;
    const first = keywordLiteral(node.keywordArguments.find((item) => item.name === "first")?.value) !== "False";
    const position = trianglePairCenter(node.name, points, first);
    return position ? { ...base, kind: "point", position } : `${node.name}を一意に描画できません`;
  }

  if (node.name === "Excenter" || node.name === "Excircle" || node.name === "IncircleContactPoint") {
    const points = trianglePoints(args, objects); if (!points) return `${node.name}には定義済みの3点が必要です`;
    if (node.name === "IncircleContactPoint") {
      const center = triangleCenter("Incenter", points); const side = keywordLiteral(node.keywordArguments.find((item) => item.name === "side")?.value) ?? "BC";
      const pair = side === "CA" ? [points[2], points[0]] : side === "AB" ? [points[0], points[1]] : [points[1], points[2]];
      const position = center ? projection(center, { anchor: pair[0], direction: subtract(pair[1], pair[0]) }) : undefined;
      return position ? { ...base, kind: "point", position } : `${node.name}を一意に描画できません`;
    }
    const vertex = keywordLiteral(node.keywordArguments.find((item) => item.name === "vertex")?.value) ?? "A"; const center = excenter(points, vertex);
    if (!center) return `${node.name}を一意に描画できません`;
    if (node.name === "Excenter") return { ...base, kind: "point", position: center };
    const index = vertex === "B" ? 1 : vertex === "C" ? 2 : 0; const opposite = index === 0 ? [points[1], points[2]] : index === 1 ? [points[2], points[0]] : [points[0], points[1]];
    const foot = projection(center, { anchor: opposite[0], direction: subtract(opposite[1], opposite[0]) });
    return foot ? { ...base, kind: "circle", center, radius: length(subtract(center, foot)) } : `${node.name}を一意に描画できません`;
  }


  if (["Circumcircle", "Incircle", "NinePointCircle"].includes(node.name)) {
    const points = trianglePoints(args, objects);
    if (!points) return `${node.name}には定義済みの3点が必要です`;
    const circum = circumcircle(...points);
    if (!circum) return `${node.name}を一意に描画できません`;
    if (node.name === "Circumcircle") return { ...base, kind: "circle", ...circum };
    if (node.name === "NinePointCircle") { const center = triangleCenter("NinePointCenter", points); return center ? { ...base, kind: "circle", center, radius: circum.radius / 2 } : `${node.name}を一意に描画できません`; }
    const center = triangleCenter("Incenter", points);
    const side = { anchor: points[1], direction: subtract(points[2], points[1]) };
    const foot = center ? projection(center, side) : undefined;
    return center && foot ? { ...base, kind: "circle", center, radius: length(subtract(center, foot)) } : `${node.name}を一意に描画できません`;
  }

  if (node.name === "Circle" || node.name === "CircleThroughPoint") {
    if (args.length !== 2) return `${node.name}には中心と半径、または中心と円周上の点が必要です`;
    const center = pointFrom(args[0], objects);
    if (!center) return `${node.name}の中心は定義済みの点である必要があります`;
    const radiusValue = scalar(args[1], variables);
    const through = pointFrom(args[1], objects);
    const radius = through ? length(subtract(through, center)) : radiusValue;
    if (radius === undefined || radius <= EPSILON) return `${node.name}の半径を正の数値として評価できません`;
    return { ...base, kind: "circle", center, radius };
  }

  if (node.name === "CircleThroughThreePoints") {
    if (args.length !== 3) return "CircleThroughThreePointsには3点が必要です";
    const points = args.map((argument) => pointFrom(argument, objects));
    if (!points[0] || !points[1] || !points[2]) return "CircleThroughThreePointsには定義済みの3点が必要です";
    const circle = circumcircle(points[0], points[1], points[2]);
    return circle ? { ...base, kind: "circle", ...circle } : "3点が一直線上にあるため円を描画できません";
  }

  if (node.name === "Polygon") {
    const vertexNodes = args.length === 1 && args[0].type === "list" ? args[0].items : args;
    if (vertexNodes.length < 3) return "Polygonには3点以上が必要です";
    const vertices = vertexNodes.map((argument) => pointFrom(argument, objects));
    if (vertices.some((point) => point === undefined)) return "Polygonには定義済みの点だけを指定できます";
    return { ...base, kind: "polygon", vertices: vertices as Vec2[] };
  }

  if (node.name === "RegularPolygon") {
    const pair = twoPoints(args.slice(0, 2), objects); const count = args[2]?.type === "number" ? Math.trunc(args[2].value) : undefined;
    const ccw = keywordLiteral(node.keywordArguments.find((item) => item.name === "ccw")?.value) !== "False";
    if (!pair || !count || count < 3) return "RegularPolygonには2点と3以上の頂点数が必要です";
    const vertices: Vec2[] = [pair[0], pair[1]]; const step = (ccw ? 1 : -1) * 2 * Math.PI / count;
    while (vertices.length < count) { const edge = subtract(vertices.at(-1)!, vertices.at(-2)!); const rotated = { x: edge.x * Math.cos(step) - edge.y * Math.sin(step), y: edge.x * Math.sin(step) + edge.y * Math.cos(step) }; vertices.push(add(vertices.at(-1)!, rotated)); }
    return { ...base, kind: "polygon", vertices };
  }

  if (["Intersect", "IntersectLines", "Intersection"].includes(node.name)) {
    if (args.length !== 2) return `${node.name}には2個の幾何オブジェクトが必要です`;
    const first = intersectionObjectFromNode(args[0], objects);
    const second = intersectionObjectFromNode(args[1], objects);
    if (!first || !second) return `${node.name}には定義済みの直線・線分・半直線・円が必要です`;
    if (node.name === "IntersectLines" && (first.kind !== "carrier" || second.kind !== "carrier")) {
      return "IntersectLinesには定義済みの2本の直線が必要です";
    }
    const intersections = objectIntersections(first, second);
    if (intersections.length === 0) return "指定したオブジェクトに実交点がありません";

    const selectors = node.keywordArguments;
    const unsupported = selectors.find((argument) => !["exclude", "near", "far"].includes(argument.name));
    if (unsupported) return `未対応の交点selector ${unsupported.name} です`;
    if (selectors.length > 1) return "交点selectorはexclude、near、farのいずれか1個だけ指定できます";
    if (intersections.length === 1) {
      return selectors.length === 0
        ? { ...base, kind: "point", position: intersections[0] }
        : "交点が一意な場合はselectorを指定できません";
    }
    if (selectors.length === 0) return "複数の交点にはexclude、near、farのselectorが必要です";

    const selector = selectors[0];
    const reference = pointFrom(selector.value, objects);
    if (!reference) return `${selector.name}には定義済みの基準点が必要です`;
    const ranked = intersections
      .map((position, index) => ({ position, index, distance: length(subtract(position, reference)) }))
      .sort((left, right) => left.distance - right.distance || left.index - right.index);
    if (selector.name === "exclude") {
      const scaleHint = Math.max(1, ...intersections.map((position) => length(position)), length(reference));
      const excluded = ranked.filter((candidate) => candidate.distance <= 1e-7 * scaleHint);
      if (excluded.length !== 1) return "excludeの基準点が交点の1つと一致しません";
      return { ...base, kind: "point", position: ranked.find((candidate) => candidate !== excluded[0])!.position };
    }
    if (Math.abs(ranked[0].distance - ranked[ranked.length - 1].distance) <= 1e-9 * Math.max(1, ranked[ranked.length - 1].distance)) {
      return `${selector.name}の基準点から2交点までの距離が等しいため分岐を選べません`;
    }
    const selected = selector.name === "near" ? ranked[0] : ranked[ranked.length - 1];
    return { ...base, kind: "point", position: selected.position };
  }

  if (node.name === "ParallelLine" || node.name === "PerpendicularLine") {
    if (args.length !== 2) return `${node.name}には点と直線が必要です`;
    const resolved = pointAndLine(args, objects, true);
    if (!resolved) return `${node.name}には定義済みの点と直線が必要です`;
    const { point, line } = resolved;
    const direction = node.name === "PerpendicularLine"
      ? { x: -line.direction.y, y: line.direction.x }
      : line.direction;
    const inheritedNormal = line.normal ?? { x: -line.direction.y, y: line.direction.x };
    const normal = node.name === "PerpendicularLine" ? { x: inheritedNormal.y, y: -inheritedNormal.x } : inheritedNormal;
    return { ...base, kind: "line", anchor: point, direction, normal };
  }


  if (node.name === "RadicalAxis") {
    if (args.length !== 2) return "RadicalAxisには2円が必要です";
    const first = circleFrom(args[0], objects); const second = circleFrom(args[1], objects);
    if (!first || !second) return "RadicalAxisには定義済みの2円が必要です";
    const directionBetween = subtract(second.center, first.center); const distance = length(directionBetween);
    if (distance < EPSILON) return "同心円の根軸を一意に描画できません";
    const unit = scale(directionBetween, 1 / distance);
    const offset = (distance * distance + first.radius * first.radius - second.radius * second.radius) / (2 * distance);
    return { ...base, kind: "line", anchor: add(first.center, scale(unit, offset)), direction: { x: -unit.y, y: unit.x }, normal: directionBetween };
  }

  if (node.name === "Polar") {
    if (args.length !== 2) return "Polarには点と円が必要です";
    const point = pointFrom(args[0], objects); const circle = circleFrom(args[1], objects);
    if (!point || !circle) return "Polarには定義済みの点と円が必要です";
    const radial = subtract(point, circle.center); const squared = radial.x ** 2 + radial.y ** 2;
    if (squared < EPSILON) return "円の中心に対する極線は一意に描画できません";
    return { ...base, kind: "line", anchor: add(circle.center, scale(radial, circle.radius ** 2 / squared)), direction: { x: -radial.y, y: radial.x }, normal: radial };
  }

  if (node.name === "Pole") {
    if (args.length !== 2) return "Poleには直線と円が必要です";
    const line = lineFrom(args[0], objects); const circle = circleFrom(args[1], objects);
    if (!line || !circle) return "Poleには定義済みの直線と円が必要です";
    const foot = projection(circle.center, line); if (!foot) return "極点を一意に描画できません";
    const normal = subtract(foot, circle.center); const squared = normal.x ** 2 + normal.y ** 2;
    return squared > EPSILON ? { ...base, kind: "point", position: add(circle.center, scale(normal, circle.radius ** 2 / squared)) } : "円の中心を通る直線の極点は有限位置にありません";
  }

  if (node.name === "Center") {
    if (args.length !== 1) return "Centerには円が必要です";
    const circle = circleFrom(args[0], objects);
    return circle ? { ...base, kind: "point", position: circle.center } : "Centerには定義済みの円が必要です";
  }

  return `未対応の構成関数 ${node.name} は描画を省略しました`;
}

/**
 * Evaluate constructions in declaration order. Forward references and unknown
 * functions are retained as warnings; they never stop later valid items from
 * being drawn.
 */
export function evaluateScene(constructions: readonly ConstructionInput[], variableValues: Readonly<Record<string, number>> = {}): Scene {
  const byName = new Map<string, SceneItem>();
  const variables = new Map(Object.entries(variableValues).filter((entry): entry is [string, number] => Number.isFinite(entry[1])));
  const items: SceneItem[] = [];
  const warnings: SceneWarning[] = [];

  for (const construction of constructions) {
    try {
      const result = evaluateItem(construction.name, construction.expr, parseExpression(construction.expr), byName, variables);
      if (typeof result === "string") {
        warnings.push({ name: construction.name, expression: construction.expr, message: result });
        continue;
      }
      if (byName.has(construction.name)) {
        warnings.push({ name: construction.name, expression: construction.expr, message: "同名オブジェクトを後の定義で置き換えました" });
        const previousIndex = items.findIndex((item) => item.name === construction.name);
        if (previousIndex >= 0) items.splice(previousIndex, 1);
      }
      byName.set(construction.name, result);
      items.push(result);
    } catch (error) {
      warnings.push({
        name: construction.name,
        expression: construction.expr,
        message: error instanceof Error ? error.message : "式を解釈できません",
      });
    }
  }
  return { items, byName, warnings };
}

type PreviewPointDriver =
  | Readonly<{ kind: "coordinates"; x: string; y: string }>
  | Readonly<{
      kind: "parameter";
      variable: string;
      carrier: ExpressionNode;
      operation: "PointOnLine" | "PointOnSegment" | "PointOnCircle";
    }>;

function zeroConstraint(value: number | string): boolean {
  return typeof value === "number"
    ? Math.abs(value) <= EPSILON
    : /^\s*[+-]?0(?:\.0*)?\s*$/.test(value);
}

function incidenceCarrier(
  node: ExpressionNode,
  pointName: string,
): ExpressionNode | undefined {
  if (node.type !== "call" || node.arguments[0]?.type !== "identifier" || node.arguments[0].name !== pointName)
    return undefined;
  if ((node.name === "OnLine" || node.name === "OnCircle") && node.arguments.length === 2)
    return node.arguments[1];
  if (node.name === "OnSegment" && node.arguments.length === 3)
    return { type: "call", name: "Segment", arguments: node.arguments.slice(1), keywordArguments: [] };
  return undefined;
}

function previewPointDriver(
  node: ExpressionNode,
  variables: ReadonlySet<string>,
): PreviewPointDriver | undefined {
  if (node.type !== "call") return undefined;
  if (
    node.name === "Point" &&
    node.arguments.length === 2 &&
    node.arguments[0].type === "identifier" &&
    node.arguments[1].type === "identifier" &&
    variables.has(node.arguments[0].name) &&
    variables.has(node.arguments[1].name)
  )
    return { kind: "coordinates", x: node.arguments[0].name, y: node.arguments[1].name };
  if (
    !["PointOnLine", "PointOnSegment", "PointOnCircle"].includes(node.name) ||
    node.arguments.at(-1)?.type !== "identifier" ||
    !variables.has((node.arguments.at(-1) as { type: "identifier"; name: string }).name)
  )
    return undefined;
  const operation = node.name as "PointOnLine" | "PointOnSegment" | "PointOnCircle";
  const carrier = node.name === "PointOnSegment"
    ? { type: "call" as const, name: "Segment", arguments: node.arguments.slice(0, 2), keywordArguments: [] }
    : node.arguments[0];
  return {
    kind: "parameter",
    variable: (node.arguments.at(-1) as { type: "identifier"; name: string }).name,
    carrier,
    operation,
  };
}

function closestPointOnObject(object: IntersectionObject, point: Vec2): Vec2 | undefined {
  if (object.kind === "circle") {
    const radial = subtract(point, object.value.center);
    const direction = normalized(radial) ?? { x: 1, y: 0 };
    return add(object.value.center, scale(direction, object.value.radius));
  }
  const carrier = object.value;
  const squared = carrier.direction.x ** 2 + carrier.direction.y ** 2;
  if (squared < EPSILON) return undefined;
  let parameter = (
    (point.x - carrier.anchor.x) * carrier.direction.x +
    (point.y - carrier.anchor.y) * carrier.direction.y
  ) / squared;
  if (carrier.domain === "segment") parameter = Math.max(0, Math.min(1, parameter));
  else if (carrier.domain === "ray") parameter = Math.max(0, parameter);
  return add(carrier.anchor, scale(carrier.direction, parameter));
}

function closestCandidate(candidates: readonly Vec2[], reference: Vec2): Vec2 | undefined {
  return candidates
    .map((position, index) => ({ position, index, distance: length(subtract(position, reference)) }))
    .sort((left, right) => left.distance - right.distance || left.index - right.index)[0]?.position;
}

function allPairIntersections(objects: readonly IntersectionObject[]): Vec2[] {
  const candidates: Vec2[] = [];
  for (let first = 0; first < objects.length; first += 1)
    for (let second = first + 1; second < objects.length; second += 1)
      candidates.push(...objectIntersections(objects[first], objects[second]));
  return candidates;
}

function parameterForPoint(
  driver: Extract<PreviewPointDriver, { kind: "parameter" }>,
  point: Vec2,
  objects: ReadonlyMap<string, SceneItem>,
): number | undefined {
  if (driver.operation === "PointOnCircle") {
    const circle = circleFrom(driver.carrier, objects);
    return circle
      ? Math.atan2(point.y - circle.center.y, point.x - circle.center.x) / (2 * Math.PI)
      : undefined;
  }
  if (driver.operation === "PointOnSegment") {
    const object = intersectionObjectFromNode(driver.carrier, objects);
    if (object?.kind !== "carrier") return undefined;
    const vector = object.value.direction;
    const squared = vector.x ** 2 + vector.y ** 2;
    return squared < EPSILON
      ? undefined
      : Math.max(0, Math.min(1, (
          (point.x - object.value.anchor.x) * vector.x +
          (point.y - object.value.anchor.y) * vector.y
        ) / squared));
  }
  const line = lineFrom(driver.carrier, objects);
  const direction = line?.normal
    ? normalized({ x: -line.normal.y, y: line.normal.x })
    : line && normalized(scale(line.direction, -1));
  if (!line || !direction) return undefined;
  const base = subtract(line.anchor, scale(direction, line.anchor.x * direction.x + line.anchor.y * direction.y));
  return (point.x - base.x) * direction.x + (point.y - base.y) * direction.y;
}

/**
 * Evaluate the visual construction while honoring incidence constraints that
 * the GeoSolver solver treats as equations.  This keeps authored one-degree-of-
 * freedom points and relational intersections attached when their upstream
 * geometry moves; it never changes the canonical problem sent to the solver.
 */
export function evaluateConstrainedScene(
  constructions: readonly ConstructionInput[],
  constraints: readonly ConstraintInput[],
  variableNames: readonly string[],
  variableValues: Readonly<Record<string, number>> = {},
): Scene {
  const variables = new Set(variableNames);
  const working: Record<string, number> = { ...variableValues };
  const relations = constructions.flatMap((construction) => {
    try {
      const driver = previewPointDriver(parseExpression(construction.expr), variables);
      if (!driver) return [];
      const carriers = constraints.flatMap((constraint) => {
        if (!zeroConstraint(constraint.value)) return [];
        try {
          const carrier = incidenceCarrier(parseExpression(constraint.def), construction.name);
          return carrier ? [carrier] : [];
        } catch {
          return [];
        }
      });
      return carriers.length ? [{ construction, driver, carriers }] : [];
    } catch {
      return [];
    }
  });
  if (!relations.length) return evaluateScene(constructions, working);

  let scene = evaluateScene(constructions, working);
  const maxPasses = Math.min(12, Math.max(2, relations.length * 2));
  for (let pass = 0; pass < maxPasses; pass += 1) {
    let changed = false;
    for (const relation of relations) {
      const current = scene.byName.get(relation.construction.name);
      if (current?.kind !== "point") continue;
      const objects = relation.carriers
        .map((carrier) => intersectionObjectFromNode(carrier, scene.byName))
        .filter((object): object is IntersectionObject => !!object);
      let target: Vec2 | undefined;
      if (relation.driver.kind === "coordinates") {
        if (objects.length >= 2)
          target = closestCandidate(allPairIntersections(objects), current.position);
        else if (objects.length === 1)
          target = closestPointOnObject(objects[0], current.position);
      } else {
        const driverObject = intersectionObjectFromNode(relation.driver.carrier, scene.byName);
        const other = objects.find((object) => {
          if (!driverObject) return false;
          const intersections = objectIntersections(driverObject, object);
          return intersections.length > 0;
        });
        if (driverObject && other)
          target = closestCandidate(objectIntersections(driverObject, other), current.position);
      }
      if (!target) continue;
      if (relation.driver.kind === "coordinates") {
        const dx = Math.abs((working[relation.driver.x] ?? 0) - target.x);
        const dy = Math.abs((working[relation.driver.y] ?? 0) - target.y);
        if (Math.max(dx, dy) <= 1e-10) continue;
        working[relation.driver.x] = target.x;
        working[relation.driver.y] = target.y;
      } else {
        const parameter = parameterForPoint(relation.driver, target, scene.byName);
        if (parameter === undefined || Math.abs((working[relation.driver.variable] ?? 0) - parameter) <= 1e-10)
          continue;
        working[relation.driver.variable] = parameter;
      }
      changed = true;
      scene = evaluateScene(constructions, working);
    }
    if (!changed) break;
  }
  return scene;
}

/** Evaluate the preview value of a scalar measurement without executing code. */
export function evaluateScalarExpression(source: string, scene: Scene, variableValues: Readonly<Record<string, number>> = {}): number | undefined {
  const variables = new Map(Object.entries(variableValues).filter((entry): entry is [string, number] => Number.isFinite(entry[1])));
  const evaluate = (node: ExpressionNode): number | undefined => {
    if (node.type === "number") return node.value;
    if (node.type === "identifier") {
      if (node.name === "pi" || node.name === "PI") return Math.PI;
      if (node.name === "e" || node.name === "E") return Math.E;
      return variables.get(node.name);
    }
    if (node.type === "unary") { const value = evaluate(node.argument); return value === undefined ? undefined : node.operator === "-" ? -value : value; }
    if (node.type === "binary") {
      const left = evaluate(node.left); const right = evaluate(node.right); if (left === undefined || right === undefined) return undefined;
      const value = node.operator === "+" ? left + right : node.operator === "-" ? left - right : node.operator === "*" ? left * right : node.operator === "/" ? left / right : left ** right;
      return Number.isFinite(value) ? value : undefined;
    }
    if (node.type !== "call") return undefined;
    const point = (index: number) => pointFrom(node.arguments[index], scene.byName);
    if (node.name === "Distance" && node.arguments.length === 2) {
      const first = point(0); const second = point(1);
      if (first && second) return length(subtract(first, second));
      const pointValue = first ?? second; const line = first ? lineFrom(node.arguments[1], scene.byName) : lineFrom(node.arguments[0], scene.byName);
      const foot = pointValue && line ? projection(pointValue, line) : undefined;
      return pointValue && foot ? length(subtract(pointValue, foot)) : undefined;
    }
    if (node.name === "Length" && node.arguments.length === 1 && node.arguments[0].type === "identifier") {
      const item = scene.byName.get(node.arguments[0].name); return item?.kind === "segment" || item?.kind === "vector" ? length(subtract(item.end, item.start)) : undefined;
    }
    if (node.name === "Angle" && node.arguments.length === 3) {
      const a = point(0); const b = point(1); const c = point(2); if (!a || !b || !c) return undefined;
      const first = normalized(subtract(a, b)); const second = normalized(subtract(c, b));
      return first && second ? Math.acos(Math.max(-1, Math.min(1, first.x * second.x + first.y * second.y))) : undefined;
    }
    if (node.name === "Area" && node.arguments.length === 3) {
      const a = point(0); const b = point(1); const c = point(2); return a && b && c ? Math.abs(cross(subtract(b, a), subtract(c, a))) / 2 : undefined;
    }
    if (["Radius", "Circumference"].includes(node.name) && node.arguments.length === 1) {
      const circle = circleFrom(node.arguments[0], scene.byName); return circle ? (node.name === "Radius" ? circle.radius : 2 * Math.PI * circle.radius) : undefined;
    }
    if (node.name === "Perimeter" && node.arguments.length >= 3) {
      const points = node.arguments.map((_, index) => point(index)); if (points.some((item) => !item)) return undefined;
      return points.reduce((total, item, index) => total + length(subtract(item!, points[(index + 1) % points.length]!)), 0);
    }
    if (node.name === "PowerOfPoint" && node.arguments.length === 2) {
      const p = point(0); const circle = circleFrom(node.arguments[1], scene.byName);
      return p && circle ? (p.x - circle.center.x) ** 2 + (p.y - circle.center.y) ** 2 - circle.radius ** 2 : undefined;
    }
    if (node.name === "Dot" && node.arguments.length === 2) {
      const vector = (index: number): Vec2 | undefined => {
        const argument = node.arguments[index];
        if (argument.type === "identifier") {
          const item = scene.byName.get(argument.name);
          if (item?.kind === "vector" || item?.kind === "segment") return subtract(item.end, item.start);
          if (item?.kind === "line" || item?.kind === "ray") return item.direction;
        }
        if (argument.type === "call" && argument.name === "Vector") {
          const pair = twoPoints(argument.arguments, scene.byName); return pair ? subtract(pair[1], pair[0]) : undefined;
        }
        return undefined;
      };
      const first = vector(0); const second = vector(1);
      return first && second ? first.x * second.x + first.y * second.y : undefined;
    }
    return undefined;
  };
  try { return evaluate(parseExpression(source)); } catch { return undefined; }
}

/** Convert mathematical coordinates (positive y upward) to SVG pixels. */
export function worldToScreen(point: Vec2, viewport: Viewport): Vec2 {
  return {
    x: viewport.width / 2 + (point.x - viewport.center.x) * viewport.pixelsPerUnit,
    y: viewport.height / 2 - (point.y - viewport.center.y) * viewport.pixelsPerUnit,
  };
}

/** Convert SVG pixels to mathematical coordinates (positive y upward). */
export function screenToWorld(point: Vec2, viewport: Viewport): Vec2 {
  if (!(viewport.pixelsPerUnit > 0) || !Number.isFinite(viewport.pixelsPerUnit)) {
    throw new RangeError("pixelsPerUnit must be a positive finite number");
  }
  return {
    x: viewport.center.x + (point.x - viewport.width / 2) / viewport.pixelsPerUnit,
    y: viewport.center.y - (point.y - viewport.height / 2) / viewport.pixelsPerUnit,
  };
}

type IntersectionCarrier = Readonly<{
  name: string;
  anchor: Vec2;
  direction: Vec2;
  domain: "line" | "ray" | "segment";
}>;

type IntersectionCircle = Readonly<{
  name: string;
  center: Vec2;
  radius: number;
}>;

type IntersectionObject =
  | Readonly<{ kind: "carrier"; value: IntersectionCarrier }>
  | Readonly<{ kind: "circle"; value: IntersectionCircle }>;

function intersectionCarrier(item: SceneItem): IntersectionCarrier | undefined {
  if (item.kind === "line") return { name: item.name, anchor: item.anchor, direction: item.direction, domain: "line" };
  if (item.kind === "ray") return { name: item.name, anchor: item.start, direction: item.direction, domain: "ray" };
  if (item.kind === "segment") return { name: item.name, anchor: item.start, direction: subtract(item.end, item.start), domain: "segment" };
  return undefined;
}

function parameterInDomain(value: number, domain: IntersectionCarrier["domain"]): boolean {
  if (domain === "line") return true;
  if (domain === "ray") return value >= -EPSILON;
  return value >= -EPSILON && value <= 1 + EPSILON;
}

function intersectionObject(item: SceneItem): IntersectionObject | undefined {
  const carrier = intersectionCarrier(item);
  if (carrier) return { kind: "carrier", value: carrier };
  if (item.kind === "circle") return { kind: "circle", value: item };
  return undefined;
}

function intersectionObjectFromNode(node: ExpressionNode, objects: ReadonlyMap<string, SceneItem>): IntersectionObject | undefined {
  if (node.type === "call" && ["Line", "Segment", "Ray"].includes(node.name)) {
    const pair = twoPoints(node.arguments, objects);
    if (!pair) return undefined;
    const direction = subtract(pair[1], pair[0]);
    if (length(direction) < EPSILON) return undefined;
    return {
      kind: "carrier",
      value: {
        name: "",
        anchor: pair[0],
        direction,
        domain: node.name === "Segment" ? "segment" : node.name === "Ray" ? "ray" : "line",
      },
    };
  }
  if (node.type !== "identifier") return undefined;
  const item = objects.get(node.name);
  return item ? intersectionObject(item) : undefined;
}

function carrierCarrierIntersections(first: IntersectionCarrier, second: IntersectionCarrier): Vec2[] {
  const denominator = cross(first.direction, second.direction);
  if (Math.abs(denominator) < EPSILON) return [];
  const between = subtract(second.anchor, first.anchor);
  const firstParameter = cross(between, second.direction) / denominator;
  const secondParameter = cross(between, first.direction) / denominator;
  if (!parameterInDomain(firstParameter, first.domain) || !parameterInDomain(secondParameter, second.domain)) return [];
  return [add(first.anchor, scale(first.direction, firstParameter))];
}

function carrierCircleIntersections(carrier: IntersectionCarrier, circle: IntersectionCircle): Vec2[] {
  const fromCenter = subtract(carrier.anchor, circle.center);
  const a = carrier.direction.x ** 2 + carrier.direction.y ** 2;
  if (a < EPSILON) return [];
  const b = 2 * (fromCenter.x * carrier.direction.x + fromCenter.y * carrier.direction.y);
  const c = fromCenter.x ** 2 + fromCenter.y ** 2 - circle.radius ** 2;
  const discriminant = b * b - 4 * a * c;
  const discriminantTolerance = EPSILON * Math.max(1, b * b, Math.abs(4 * a * c));
  if (discriminant < -discriminantTolerance) return [];
  const root = Math.sqrt(Math.max(0, discriminant));
  const parameters = root <= Math.sqrt(discriminantTolerance)
    ? [-b / (2 * a)]
    : [(-b - root) / (2 * a), (-b + root) / (2 * a)];
  return parameters
    .filter((parameter) => parameterInDomain(parameter, carrier.domain))
    .map((parameter) => add(carrier.anchor, scale(carrier.direction, parameter)));
}

function circleCircleIntersections(first: IntersectionCircle, second: IntersectionCircle): Vec2[] {
  const between = subtract(second.center, first.center);
  const distance = length(between);
  const tolerance = EPSILON * Math.max(1, first.radius, second.radius, distance);
  if (distance <= tolerance) return [];
  if (distance > first.radius + second.radius + tolerance) return [];
  if (distance < Math.abs(first.radius - second.radius) - tolerance) return [];

  const along = (first.radius ** 2 - second.radius ** 2 + distance ** 2) / (2 * distance);
  const heightSquared = first.radius ** 2 - along ** 2;
  if (heightSquared < -tolerance * Math.max(1, first.radius)) return [];
  const unit = scale(between, 1 / distance);
  const midpoint = add(first.center, scale(unit, along));
  const height = Math.sqrt(Math.max(0, heightSquared));
  if (height <= tolerance) return [midpoint];
  const perpendicular = { x: -unit.y * height, y: unit.x * height };
  return [add(midpoint, perpendicular), subtract(midpoint, perpendicular)];
}

function objectIntersections(first: IntersectionObject, second: IntersectionObject): Vec2[] {
  if (first.kind === "carrier" && second.kind === "carrier") {
    return carrierCarrierIntersections(first.value, second.value);
  }
  if (first.kind === "carrier" && second.kind === "circle") {
    return carrierCircleIntersections(first.value, second.value);
  }
  if (first.kind === "circle" && second.kind === "carrier") {
    return carrierCircleIntersections(second.value, first.value);
  }
  return circleCircleIntersections(
    (first as Readonly<{ kind: "circle"; value: IntersectionCircle }>).value,
    (second as Readonly<{ kind: "circle"; value: IntersectionCircle }>).value,
  );
}

/** Find the closest visible line/segment/ray/circle crossing near a world-space point. */
export function nearestIntersection(
  items: readonly SceneItem[],
  point: Vec2,
  tolerance: number,
): IntersectionCandidate | undefined {
  if (!Number.isFinite(tolerance) || tolerance < 0) return undefined;
  const objects = items
    .map((item) => ({ name: item.name, object: intersectionObject(item) }))
    .filter((entry): entry is { name: string; object: IntersectionObject } => !!entry.object);
  let nearest: IntersectionCandidate | undefined;
  for (let firstIndex = 0; firstIndex < objects.length; firstIndex += 1) {
    for (let secondIndex = firstIndex + 1; secondIndex < objects.length; secondIndex += 1) {
      const first = objects[firstIndex];
      const second = objects[secondIndex];
      const alternatives = objectIntersections(first.object, second.object);
      for (const position of alternatives) {
        const distance = length(subtract(position, point));
        if (distance <= tolerance && (!nearest || distance < nearest.distance)) {
          nearest = { first: first.name, second: second.name, position, distance, alternatives };
        }
      }
    }
  }
  return nearest;
}

/** Find the closest visible line/segment/ray crossing near a world-space point. */
export function nearestLineIntersection(
  items: readonly SceneItem[],
  point: Vec2,
  tolerance: number,
): LineIntersectionCandidate | undefined {
  const carriers = items.map(intersectionCarrier).filter((item): item is IntersectionCarrier => !!item);
  let nearest: LineIntersectionCandidate | undefined;
  for (let firstIndex = 0; firstIndex < carriers.length; firstIndex += 1) {
    for (let secondIndex = firstIndex + 1; secondIndex < carriers.length; secondIndex += 1) {
      const first = carriers[firstIndex]; const second = carriers[secondIndex];
      const denominator = cross(first.direction, second.direction);
      if (Math.abs(denominator) < EPSILON) continue;
      const between = subtract(second.anchor, first.anchor);
      const firstParameter = cross(between, second.direction) / denominator;
      const secondParameter = cross(between, first.direction) / denominator;
      if (!parameterInDomain(firstParameter, first.domain) || !parameterInDomain(secondParameter, second.domain)) continue;
      const position = add(first.anchor, scale(first.direction, firstParameter));
      const distance = length(subtract(position, point));
      if (distance <= tolerance && (!nearest || distance < nearest.distance)) {
        nearest = { first: first.name, second: second.name, position, distance, alternatives: [position] };
      }
    }
  }
  return nearest;
}

function cleanCoordinate(value: number, fractionDigits: number): string {
  if (!Number.isFinite(value)) throw new RangeError("Point coordinates must be finite");
  const rounded = Math.abs(value) < 10 ** (-fractionDigits) / 2 ? 0 : value;
  return rounded.toFixed(fractionDigits).replace(/(?:\.0+|(\.\d*?)0+)$/, "$1");
}

/** Format a dragged/free point back into the canonical drawable GeoSolver spelling. */
export function formatPointExpression(point: Vec2, fractionDigits = 6): string {
  if (!Number.isInteger(fractionDigits) || fractionDigits < 0 || fractionDigits > 12) {
    throw new RangeError("fractionDigits must be an integer between 0 and 12");
  }
  return `Point(${cleanCoordinate(point.x, fractionDigits)}, ${cleanCoordinate(point.y, fractionDigits)})`;
}

/** Return the first unused name in the sequence P, P2, P3... (or another prefix). */
export function uniqueName(existing: Iterable<string>, prefix = "P"): string {
  const names = new Set(existing);
  if (!names.has(prefix)) return prefix;
  let suffix = 2;
  while (names.has(`${prefix}${suffix}`)) suffix += 1;
  return `${prefix}${suffix}`;
}
