import type { SceneItem, Vec2 } from "./geometry";

export type FreedomKind = "free" | "fixed" | "derived";
export type SelectableKind = "point" | "line" | "segment" | "circle" | "vector" | "polygon" | "object" | "line-or-circle" | "point-or-line";

export type ConstructionLike = Readonly<{ name: string; expr: string }>;
export type GuidedSlot = Readonly<{ kind: SelectableKind; label: string; coerceLinearCarrier?: boolean }>;
export type GuidedParameter = Readonly<{ suffix: string; initial: number; boundUnit?: boolean }>;
export type GuidedChoice = Readonly<{
  name: string; label: string; defaultValue: string; positional?: boolean;
  options: readonly Readonly<{ value: string; label: string }>[];
}>;
export type GuidedOutput = "construction" | "measurement" | "constraint" | "guard";
export type GuidedSpec = Readonly<{ slots: readonly GuidedSlot[]; output?: GuidedOutput; expressionName?: string; parameters?: readonly GuidedParameter[]; choices?: readonly GuidedChoice[] }>;

const GUIDED_SPECS: Readonly<Record<string, GuidedSpec>> = {
  PointOnLine: { slots: [{ kind: "line", label: "載せる直線" }], parameters: [{ suffix: "t", initial: 0 }] },
  PointOnSegment: { slots: [{ kind: "point", label: "端点A" }, { kind: "point", label: "端点B" }], parameters: [{ suffix: "t", initial: 0.5, boundUnit: true }] },
  PointOnCircle: { slots: [{ kind: "circle", label: "載せる円" }], parameters: [{ suffix: "t", initial: 0 }] },
  Segment: { slots: [{ kind: "point", label: "始点" }, { kind: "point", label: "終点" }] },
  Line: { slots: [{ kind: "point", label: "1点目" }, { kind: "point", label: "2点目" }] },
  Ray: { slots: [{ kind: "point", label: "始点" }, { kind: "point", label: "通過点" }] },
  Vector: { slots: [{ kind: "point", label: "始点" }, { kind: "point", label: "終点" }] },
  Midpoint: { slots: [{ kind: "point", label: "1点目" }, { kind: "point", label: "2点目" }] },
  ClosestPoint: { slots: [{ kind: "point", label: "射影する点" }, { kind: "line", label: "載せる直線（線分等は支持直線）", coerceLinearCarrier: true }] },
  FootOfPerpendicular: { slots: [{ kind: "point", label: "垂線を下ろす点" }, { kind: "line", label: "基準の直線（線分等は支持直線）", coerceLinearCarrier: true }] },
  PerpendicularBisector: { slots: [{ kind: "point", label: "1点目" }, { kind: "point", label: "2点目" }] },
  CircleThroughPoint: { slots: [{ kind: "point", label: "中心" }, { kind: "point", label: "円周上の点" }] },
  CircleThroughThreePoints: { slots: [{ kind: "point", label: "1点目" }, { kind: "point", label: "2点目" }, { kind: "point", label: "3点目" }] },
  Arc: { slots: [{ kind: "circle", label: "基準の円" }, { kind: "point", label: "始点" }, { kind: "point", label: "終点" }, { kind: "point", label: "円弧が通る点" }] },
  ContactPoint: { slots: [{ kind: "circle", label: "円" }, { kind: "line", label: "接線（線分等は支持直線）", coerceLinearCarrier: true }] },
  TangentAtPoint: { expressionName: "Polar", slots: [{ kind: "point", label: "円周上の接点" }, { kind: "circle", label: "円" }] },
  RegularPolygon: { slots: [{ kind: "point", label: "1点目" }, { kind: "point", label: "隣の頂点" }], choices: [
    { name: "n", label: "頂点数", defaultValue: "3", positional: true, options: [3, 4, 5, 6, 7, 8, 9, 10, 12].map((value) => ({ value: String(value), label: String(value) })) },
    { name: "ccw", label: "向き", defaultValue: "True", options: [{ value: "True", label: "反時計回り" }, { value: "False", label: "時計回り" }] },
  ] },
  Intersect: { slots: [{ kind: "line", label: "1本目" }, { kind: "line", label: "2本目" }] },
  Intersection: { slots: [{ kind: "line", label: "1本目" }, { kind: "line", label: "2本目" }] },
  IntersectLines: { slots: [{ kind: "line", label: "1本目" }, { kind: "line", label: "2本目" }] },
  ParallelLine: { slots: [{ kind: "line", label: "基準の直線（線分等は支持直線）", coerceLinearCarrier: true }, { kind: "point", label: "通る点" }] },
  PerpendicularLine: { slots: [{ kind: "line", label: "基準の直線（線分等は支持直線）", coerceLinearCarrier: true }, { kind: "point", label: "通る点" }] },
  AngleBisector: { slots: [{ kind: "point", label: "辺上の点" }, { kind: "point", label: "頂点" }, { kind: "point", label: "辺上の点" }] },
  Reflect: { slots: [{ kind: "point", label: "反転する点" }, { kind: "point-or-line", label: "対称の中心・軸（線分等は支持直線）", coerceLinearCarrier: true }] },
  Centroid: { slots: triangleSlots() },
  Circumcenter: { slots: triangleSlots() },
  Incenter: { slots: triangleSlots() },
  Orthocenter: { slots: triangleSlots() },
  Excenter: { slots: triangleSlots(), choices: [triangleVertexChoice()] },
  NinePointCenter: { slots: triangleSlots() },
  Incircle: { slots: triangleSlots() },
  Circumcircle: { slots: triangleSlots() },
  NinePointCircle: { slots: triangleSlots() },
  SymmedianPoint: { slots: triangleSlots() },
  GergonnePoint: { slots: triangleSlots() },
  NagelPoint: { slots: triangleSlots() },
  FermatPoint: { slots: triangleSlots(), choices: [pairChoice()] },
  FeuerbachPoint: { slots: triangleSlots() },
  Mittenpunkt: { slots: triangleSlots() },
  SpiekerCenter: { slots: triangleSlots() },
  Excircle: { slots: triangleSlots(), choices: [triangleVertexChoice()] },
  IncircleContactPoint: { slots: triangleSlots(), choices: [{ name: "side", label: "接点を取る辺", defaultValue: "'BC'", options: ["BC", "CA", "AB"].map((side) => ({ value: `'${side}'`, label: side })) }] },
  IsodynamicPoint: { slots: triangleSlots(), choices: [pairChoice()] },
  RadicalAxis: { slots: [{ kind: "circle", label: "1つ目の円" }, { kind: "circle", label: "2つ目の円" }] },
  Polar: { slots: [{ kind: "point", label: "極点" }, { kind: "circle", label: "基準の円" }] },
  Pole: { slots: [{ kind: "line", label: "極線（線分等は支持直線）", coerceLinearCarrier: true }, { kind: "circle", label: "基準の円" }] },
  Distance: { output: "measurement", slots: [{ kind: "point", label: "1点目" }, { kind: "point", label: "2点目" }] },
  Ratio: { output: "measurement", slots: [{ kind: "point", label: "第1の長さの始点" }, { kind: "point", label: "第1の長さの終点" }, { kind: "point", label: "第2の長さの始点" }, { kind: "point", label: "第2の長さの終点" }] },
  Length: { output: "measurement", slots: [{ kind: "segment", label: "長さを測る線分" }] },
  Angle: { output: "measurement", slots: [{ kind: "point", label: "辺上の点" }, { kind: "point", label: "頂点" }, { kind: "point", label: "辺上の点" }] },
  Area: { output: "measurement", slots: [{ kind: "point", label: "1点目" }, { kind: "point", label: "2点目" }, { kind: "point", label: "3点目" }] },
  Radius: { output: "measurement", slots: [{ kind: "circle", label: "円" }] },
  Circumference: { output: "measurement", slots: [{ kind: "circle", label: "円" }] },
  Perimeter: { output: "measurement", slots: triangleSlots() },
  Dot: { output: "measurement", slots: [{ kind: "vector", label: "1つ目のベクトル" }, { kind: "vector", label: "2つ目のベクトル" }] },
  PowerOfPoint: { output: "measurement", slots: [{ kind: "point", label: "点" }, { kind: "circle", label: "円" }] },
  Center: { slots: [{ kind: "circle", label: "円" }] },
  OnLine: { output: "constraint", slots: [{ kind: "point", label: "点" }, { kind: "line", label: "直線" }] },
  OnSegment: { output: "constraint", slots: [{ kind: "point", label: "点" }, { kind: "point", label: "線分の始点" }, { kind: "point", label: "線分の終点" }] },
  OnCircle: { output: "constraint", slots: [{ kind: "point", label: "点" }, { kind: "circle", label: "円" }] },
  Collinear: { output: "constraint", slots: triangleSlots("点") },
  IsTangent: { output: "constraint", slots: [{ kind: "line-or-circle", label: "直線または1つ目の円" }, { kind: "circle", label: "円" }] },
  Parallel: { output: "constraint", slots: [{ kind: "line", label: "1本目の直線" }, { kind: "line", label: "2本目の直線" }] },
  Perpendicular: { output: "constraint", slots: [{ kind: "line", label: "1本目の直線" }, { kind: "line", label: "2本目の直線" }] },
  AssumeAcute: { output: "guard", slots: triangleSlots() },
  AssumeRight: { output: "guard", slots: triangleSlots() },
  AssumeObtuse: { output: "guard", slots: triangleSlots() },
};

function triangleSlots(noun = "頂点"): readonly GuidedSlot[] {
  return [{ kind: "point", label: `${noun}A` }, { kind: "point", label: `${noun}B` }, { kind: "point", label: `${noun}C` }];
}

function triangleVertexChoice(): GuidedChoice {
  return { name: "vertex", label: "対応する頂点", defaultValue: "'A'", options: ["A", "B", "C"].map((vertex) => ({ value: `'${vertex}'`, label: vertex })) };
}

function pairChoice(): GuidedChoice {
  return { name: "first", label: "分岐", defaultValue: "True", options: [{ value: "True", label: "第1分岐" }, { value: "False", label: "第2分岐" }] };
}

export function guidedSpecFor(toolId: string): GuidedSpec | undefined {
  return GUIDED_SPECS[toolId];
}

export function acceptsSceneItem(slot: GuidedSlot, item: SceneItem): boolean {
  if (slot.kind === "object") return true;
  if (slot.kind === "point") return item.kind === "point";
  if (slot.kind === "circle") return item.kind === "circle" || item.kind === "arc";
  if (slot.kind === "segment") return item.kind === "segment";
  if (slot.kind === "vector") return item.kind === "vector";
  if (slot.kind === "polygon") return item.kind === "polygon";
  const coercedLinearCarrier = !!slot.coerceLinearCarrier && ["segment", "ray", "vector"].includes(item.kind);
  if (slot.kind === "line-or-circle") return item.kind === "circle" || item.kind === "line" || coercedLinearCarrier;
  if (slot.kind === "point-or-line") return item.kind === "point" || item.kind === "line" || coercedLinearCarrier;
  return item.kind === "line" || coercedLinearCarrier;
}

export function guidedSpecs(): Readonly<Record<string, GuidedSpec>> {
  return GUIDED_SPECS;
}

export function guidedExpression(toolId: string, names: readonly string[], spec: GuidedSpec, parameters: readonly string[] = [], choices: Readonly<Record<string, string>> = {}): string {
  if (toolId === "Ratio" && names.length === 4) return `Distance(${names[0]}, ${names[1]}) / Distance(${names[2]}, ${names[3]})`;
  if (toolId === "Arc" && names.length === 4) return `Arc(${names[0]}, ${names[1]}, ${names[2]}, including=${names[3]})`;
  const choiceArguments = (spec.choices ?? []).map((choice) => {
    const value = choices[choice.name] ?? choice.defaultValue;
    return choice.positional ? value : `${choice.name}=${value}`;
  });
  return `${spec.expressionName ?? toolId}(${[...names, ...parameters, ...choiceArguments].join(", ")})`;
}

export type ParameterizedPoint = Readonly<{
  operation: "PointOnLine" | "PointOnSegment" | "PointOnCircle" | "PointOnAxis";
  carriers: readonly string[]; variable: string; axis?: "x" | "y";
}>;

export function parameterizedPoint(construction: ConstructionLike, variables: readonly string[]): ParameterizedPoint | undefined {
  const axis = /^\s*Point\(\s*([A-Za-z_][A-Za-z0-9_]*|[+-]?0(?:\.0*)?)\s*,\s*([A-Za-z_][A-Za-z0-9_]*|[+-]?0(?:\.0*)?)\s*\)\s*$/.exec(construction.expr);
  if (axis) {
    if (variables.includes(axis[1]) && /^[-+]?0(?:\.0*)?$/.test(axis[2])) return { operation: "PointOnAxis", carriers: [], variable: axis[1], axis: "x" };
    if (/^[-+]?0(?:\.0*)?$/.test(axis[1]) && variables.includes(axis[2])) return { operation: "PointOnAxis", carriers: [], variable: axis[2], axis: "y" };
  }
  const match = /^\s*(PointOnLine|PointOnSegment|PointOnCircle)\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*(?:,\s*([A-Za-z_][A-Za-z0-9_]*)\s*)?,\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)\s*$/.exec(construction.expr);
  if (!match || !variables.includes(match[4])) return undefined;
  if (match[1] === "PointOnSegment" && !match[3]) return undefined;
  return { operation: match[1] as ParameterizedPoint["operation"], carriers: match[3] ? [match[2], match[3]] : [match[2]], variable: match[4] };
}

export function directPointVariables(construction: ConstructionLike, variables: readonly string[]): readonly [string, string] | undefined {
  const match = /^\s*Point\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*,\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)\s*$/.exec(construction.expr);
  if (!match || !variables.includes(match[1]) || !variables.includes(match[2])) return undefined;
  return [match[1], match[2]];
}

export function isFixedPointDefinition(construction: ConstructionLike): boolean {
  return /^\s*Point\(\s*[+-]?(?:\d+(?:\.\d*)?|\.\d+)\s*,\s*[+-]?(?:\d+(?:\.\d*)?|\.\d+)\s*\)\s*$/.test(construction.expr);
}

export function freedomOf(construction: ConstructionLike, variables: readonly string[]): FreedomKind {
  if (directPointVariables(construction, variables)) return "free";
  const usesVariable = variables.some((name) => new RegExp(`\\b${escapeRegExp(name)}\\b`).test(construction.expr));
  if (usesVariable) return "free";
  return isFixedPointDefinition(construction)
    ? "fixed"
    : "derived";
}

export function freePointDefinition(name: string, point: Vec2, usedVariables: readonly string[]) {
  const x = uniqueIdentifier(usedVariables, `${name}x`);
  const y = uniqueIdentifier([...usedVariables, x], `${name}y`);
  return { variables: [x, y] as const, expression: `Point(${x}, ${y})`, preview: { [x]: point.x, [y]: point.y } };
}

export function uniqueIdentifier(existing: Iterable<string>, preferred: string): string {
  const names = new Set(existing);
  if (!names.has(preferred)) return preferred;
  let suffix = 2;
  while (names.has(`${preferred}${suffix}`)) suffix += 1;
  return `${preferred}${suffix}`;
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
