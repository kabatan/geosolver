import {
  directPointVariables,
  parameterizedPoint,
} from "./authoring";
import type { Construction, DslCatalog, Problem } from "./types";

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

export function isDslCatalog(value: unknown): value is DslCatalog {
  if (!value || typeof value !== "object") return false;
  const item = value as Partial<DslCatalog>;
  return (
    typeof item.version === "string" &&
    Array.isArray(item.categories) &&
    Array.isArray(item.tools)
  );
}
