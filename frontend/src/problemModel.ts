import {
  directPointVariables,
  parameterizedPoint,
} from "./authoring";
import type {
  Construction,
  DslCatalog,
  GeometryCondition,
  GeometryProblem,
  Problem,
} from "./types";

const RELATION_GUARDS = {
  AssumeNe: "!=",
  AssumeLt: "<",
  AssumeLe: "<=",
  AssumeGt: ">",
  AssumeGe: ">=",
} as const;

const PUBLIC_PREDICATES: Record<string, string> = {
  AssumeAcute: "AcuteTriangle",
  AssumeRight: "RightTriangle",
  AssumeObtuse: "ObtuseTriangle",
  AssumeConvex: "ConvexPolygon",
  AssumeNoSelfIntersecting: "SimplePolygon",
};

function splitArguments(source: string): string[] {
  const parts: string[] = [];
  let depth = 0;
  let start = 0;
  for (let index = 0; index < source.length; index += 1) {
    const character = source[index];
    if ("([{".includes(character)) depth += 1;
    else if (")]}".includes(character)) depth -= 1;
    else if (character === "," && depth === 0) {
      parts.push(source.slice(start, index).trim());
      start = index + 1;
    }
  }
  parts.push(source.slice(start).trim());
  return parts;
}

function publicCondition(guard: string): GeometryCondition {
  const call = guard.trim().match(/^([A-Za-z_][A-Za-z0-9_]*)\s*\((.*)\)$/s);
  if (!call) return { predicate: guard };
  const [, name, body] = call;
  if (name in RELATION_GUARDS) {
    const [left, right = ""] = splitArguments(body);
    const numeric = Number(right);
    return {
      left,
      operator: RELATION_GUARDS[name as keyof typeof RELATION_GUARDS],
      right: right.trim() !== "" && Number.isFinite(numeric) ? numeric : right,
    };
  }
  if (name === "Assume") return { predicate: body.trim() };
  return { predicate: `${PUBLIC_PREDICATES[name] ?? name}(${body})` };
}

export function toGeometryProblem(problem: Problem): GeometryProblem {
  return {
    id: problem.id,
    variables: [...problem.variables.names],
    constructions: problem.construction.map(({ name, expr }) => ({
      name,
      expression: expr,
    })),
    conditions: [
      ...problem.constraints.map(({ def, value }) => ({
        left: def,
        operator: "=" as const,
        right: value,
      })),
      ...problem.guards.map(publicCondition),
    ],
    target: problem.answer,
  };
}

function internalGuard(condition: GeometryCondition): string | undefined {
  if ("predicate" in condition) {
    if (!condition.predicate.trim()) return undefined;
    const match = condition.predicate.match(/^([A-Za-z_][A-Za-z0-9_]*)\s*\((.*)\)$/s);
    if (!match) return `Assume(${condition.predicate})`;
    const internal = Object.entries(PUBLIC_PREDICATES).find(
      ([, publicName]) => publicName === match[1],
    )?.[0];
    return internal ? `${internal}(${match[2]})` : `Assume(${condition.predicate})`;
  }
  if (condition.operator === "=") return undefined;
  const internal = Object.entries(RELATION_GUARDS).find(
    ([, operator]) => operator === condition.operator,
  )?.[0];
  const right = typeof condition.right === "string" ? condition.right : String(condition.right);
  return `${internal}(${condition.left}, ${right})`;
}

export function fromGeometryProblem(problem: GeometryProblem): Problem {
  return {
    task: "solve",
    id: problem.id,
    variables: { names: [...problem.variables] },
    construction: problem.constructions.map(({ name, expression }) => ({ name, expr: expression })),
    constraints: problem.conditions
      .filter(
        (condition): condition is Extract<GeometryCondition, { left: string }> =>
          "left" in condition && condition.operator === "=",
      )
      .map((condition) => ({ def: condition.left, value: condition.right })),
    guards: problem.conditions.map(internalGuard).filter((value): value is string => !!value),
    answer: problem.target,
    post_process: "",
  };
}

export function cloneProblem(problem: Problem): Problem {
  return structuredClone(problem);
}

export function allNames(problem: Problem): string[] {
  return [
    ...problem.variables.names,
    ...problem.construction.map((item) => item.name),
  ];
}

export function validIdentifier(value: string): boolean {
  return /^[A-Za-z_][A-Za-z0-9_]*$/.test(value);
}

export function referencesIdentifier(source: string, name: string): boolean {
  return new RegExp(
    `\\b${name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`,
  ).test(source);
}

export function replaceIdentifier(
  source: string,
  from: string,
  to: string,
): string {
  return source.replace(
    new RegExp(`\\b${from.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`, "g"),
    to,
  );
}

function ownedVariablesFor(
  construction: Construction,
  variables: readonly string[],
): readonly string[] {
  const direct = directPointVariables(construction, variables);
  if (direct) return direct;
  const parameter = parameterizedPoint(construction, variables);
  return parameter ? [parameter.variable] : [];
}

export function deletionClosure(
  problem: Problem,
  root: string,
): { names: Set<string>; variables: Set<string> } {
  const names = new Set([root]);
  const variables = new Set<string>();
  const absorbVariables = (construction: Construction) =>
    ownedVariablesFor(construction, problem.variables.names).forEach((name) =>
      variables.add(name),
    );
  const rootConstruction = problem.construction.find(
    (item) => item.name === root,
  );
  if (rootConstruction) absorbVariables(rootConstruction);
  let changed = true;
  while (changed) {
    changed = false;
    for (const construction of problem.construction) {
      if (names.has(construction.name)) continue;
      if (
        ![...names, ...variables].some((name) =>
          referencesIdentifier(construction.expr, name),
        )
      )
        continue;
      names.add(construction.name);
      absorbVariables(construction);
      changed = true;
    }
  }
  return { names, variables };
}

export function completeVariablePreview(
  problem: Problem,
  saved: Record<string, number> = {},
): Record<string, number> {
  const preview: Record<string, number> = {};
  problem.variables.names.forEach((name) => {
    if (Number.isFinite(saved[name])) preview[name] = saved[name];
  });
  problem.construction.forEach((construction, index) => {
    const pair = directPointVariables(construction, problem.variables.names);
    if (!pair) return;
    if (!Number.isFinite(preview[pair[0]]))
      preview[pair[0]] = (index % 4) * 2 - 3;
    if (!Number.isFinite(preview[pair[1]]))
      preview[pair[1]] = 2 - Math.floor(index / 4) * 2;
  });
  problem.variables.names.forEach((name) => {
    if (!Number.isFinite(preview[name])) preview[name] = 1;
  });
  return preview;
}

export function isProblem(value: unknown): value is Problem {
  if (!value || typeof value !== "object") return false;
  const item = value as Partial<Problem>;
  return (
    item.task === "solve" &&
    typeof item.id === "string" &&
    Array.isArray(item.construction) &&
    Array.isArray(item.constraints) &&
    Array.isArray(item.guards) &&
    typeof item.answer === "string" &&
    typeof item.post_process === "string" &&
    !!item.variables &&
    Array.isArray(item.variables.names)
  );
}

export function isGeometryProblem(value: unknown): value is GeometryProblem {
  if (!value || typeof value !== "object") return false;
  const item = value as Partial<GeometryProblem>;
  return (
    typeof item.id === "string" &&
    Array.isArray(item.variables) &&
    Array.isArray(item.constructions) &&
    Array.isArray(item.conditions) &&
    typeof item.target === "string"
  );
}

export function isDslCatalog(value: unknown): value is DslCatalog {
  if (!value || typeof value !== "object") return false;
  const item = value as Partial<DslCatalog>;
  return (
    item.schema_version === 1 &&
    Array.isArray(item.categories) &&
    Array.isArray(item.tools)
  );
}
