import { migrateLegacyUiEquationGuards } from "./mathFormat";
import { isProblem } from "./problemModel";
import type { Problem, ProjectEnvelope, ValidationIssue } from "./types";

export function validationIssueLocation(
  path: string,
  problem: Problem,
): string {
  let match = /^constraints\[(\d+)](?:\.(def|value))?$/.exec(path);
  if (match) return `条件 ${Number(match[1]) + 1}`;
  match = /^guards\[(\d+)]$/.exec(path);
  if (match)
    return `条件 ${problem.constraints.length + Number(match[1]) + 1}`;
  match = /^construction\[(\d+)]\.expr$/.exec(path);
  if (match) {
    const item = problem.construction[Number(match[1])];
    return item ? `オブジェクト「${item.name}」の定義` : "作図の定義";
  }
  if (path === "answer") return "ターゲット";
  if (path.startsWith("variables")) return "変数";
  return path;
}

export function validationIssueExpression(
  path: string,
  problem: Problem,
): string | undefined {
  let match = /^constraints\[(\d+)]\.(def|value)$/.exec(path);
  if (match) {
    const item = problem.constraints[Number(match[1])];
    return item ? String(item[match[2] as "def" | "value"]) : undefined;
  }
  match = /^guards\[(\d+)]$/.exec(path);
  if (match) return problem.guards[Number(match[1])];
  match = /^construction\[(\d+)]\.expr$/.exec(path);
  if (match) return problem.construction[Number(match[1])]?.expr;
  if (path === "answer") return problem.answer;
  return undefined;
}

export type { ValidationIssue };

export const PROJECT_FORMAT_VERSION = 2;

export function saveLastProject(envelope: ProjectEnvelope) {
  const request = indexedDB.open("geosolver", 2);
  request.onupgradeneeded = () => {
    if (!request.result.objectStoreNames.contains("projects"))
      request.result.createObjectStore("projects");
  };
  request.onsuccess = () =>
    request.result
      .transaction("projects", "readwrite")
      .objectStore("projects")
      .put(envelope, "__last__");
}

export function loadLastProject(onLoad: (value: ProjectEnvelope) => void) {
  const request = indexedDB.open("geosolver", 2);
  request.onupgradeneeded = () => {
    if (!request.result.objectStoreNames.contains("projects"))
      request.result.createObjectStore("projects");
  };
  request.onsuccess = () => {
    const read = request.result
      .transaction("projects")
      .objectStore("projects")
      .get("__last__");
    read.onsuccess = () => {
      if (read.result?.problem && isProblem(read.result.problem)) {
        const envelope = read.result as ProjectEnvelope;
        const migrated = migrateLegacyUiEquationGuards(envelope.problem);
        onLoad({
          ...envelope,
          formatVersion: PROJECT_FORMAT_VERSION,
          problem: migrated.problem,
        });
      }
    };
  };
}

export function extractWitnessPoints(
  value: unknown,
): Array<{ name: string; position: { x: number; y: number } }> {
  const found = new Map<string, { x: number; y: number }>();
  function visit(node: unknown) {
    if (!node || typeof node !== "object") return;
    if (Array.isArray(node)) {
      node.forEach(visit);
      return;
    }
    for (const [key, child] of Object.entries(
      node as Record<string, unknown>,
    )) {
      if (
        Array.isArray(child) &&
        child.length >= 2 &&
        typeof child[0] === "number" &&
        typeof child[1] === "number"
      )
        found.set(key, { x: child[0], y: child[1] });
      else if (
        child &&
        typeof child === "object" &&
        typeof (child as { x?: unknown }).x === "number" &&
        typeof (child as { y?: unknown }).y === "number"
      )
        found.set(key, {
          x: (child as { x: number }).x,
          y: (child as { y: number }).y,
        });
      else visit(child);
    }
  }
  visit(value);
  return [...found].map(([name, position]) => ({ name, position }));
}
