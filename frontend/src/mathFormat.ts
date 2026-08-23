import type { Constraint, Problem } from "./types";

const RELATION_TO_ASSUME: Readonly<Record<string, string>> = {
  "<": "AssumeLt",
  "≤": "AssumeLe",
  "<=": "AssumeLe",
  ">": "AssumeGt",
  "≥": "AssumeGe",
  ">=": "AssumeGe",
  "=": "AssumeEq",
  "==": "AssumeEq",
  "≠": "AssumeNe",
  "!=": "AssumeNe",
};
const ASSUME_TO_RELATION: Readonly<Record<string, string>> = {
  AssumeLt: "<",
  AssumeLe: "≤",
  AssumeGt: ">",
  AssumeGe: "≥",
  AssumeEq: "=",
  AssumeNe: "≠",
};
export const GUARD_TOOL_NOTATION: Readonly<Record<string, string>> = {
  Assume: "条件",
  AssumeLt: "<",
  AssumeLe: "≤",
  AssumeGt: ">",
  AssumeGe: "≥",
  AssumeEq: "=",
  AssumeNe: "≠",
  Bound: "a ≤ t ≤ b",
  AssumeAcute: "鋭角",
  AssumeRight: "直角",
  AssumeObtuse: "鈍角",
  AssumeConvex: "凸",
  AssumeNoSelfIntersecting: "非自己交差",
  AssumeOrder: "順序",
};

function splitTopLevelArguments(source: string): string[] | undefined {
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
    if (depth < 0) return undefined;
  }
  if (depth !== 0) return undefined;
  parts.push(source.slice(start).trim());
  return parts;
}

function parseCall(
  source: string,
): { name: string; args: string[] } | undefined {
  const match = /^([A-Za-z_][A-Za-z0-9_]*)\s*\(([\s\S]*)\)$/.exec(
    source.trim(),
  );
  if (!match) return undefined;
  const args = splitTopLevelArguments(match[2]);
  return args ? { name: match[1], args } : undefined;
}

export function displayMathConstants(source: string): string {
  return source.replace(/\bpi\b/g, "π");
}
export function internalMathConstants(source: string): string {
  return source.replace(/π/g, "pi");
}

const SCALAR_LANGUAGE_NAMES = new Set([
  "and",
  "or",
  "not",
  "if",
  "else",
  "True",
  "False",
  "None",
  "pi",
]);

/** Expand an unambiguous concatenation of two point IDs in scalar expressions. */
export function expandDistanceShorthand(
  source: string,
  pointNames: Iterable<string>,
  reservedNames?: Iterable<string>,
  expandTrailingToken = true,
): string {
  const pointList = [...pointNames];
  const points = new Set(pointList);
  const reserved = new Set(reservedNames ?? pointList);
  let result = "";
  let cursor = 0;
  while (cursor < source.length) {
    const character = source[cursor];
    if (character === "'" || character === '"') {
      const quote = character;
      const start = cursor;
      cursor += 1;
      while (cursor < source.length) {
        if (source[cursor] === "\\") cursor += 2;
        else if (source[cursor] === quote) {
          cursor += 1;
          break;
        } else cursor += 1;
      }
      result += source.slice(start, cursor);
      continue;
    }
    const previous = cursor > 0 ? source[cursor - 1] : "";
    if (
      /[A-Za-z_]/.test(character) &&
      (cursor === 0 || !/[A-Za-z0-9_]/.test(previous))
    ) {
      const start = cursor;
      cursor += 1;
      while (cursor < source.length && /[A-Za-z0-9_]/.test(source[cursor]))
        cursor += 1;
      const token = source.slice(start, cursor);
      let before = start - 1;
      while (before >= 0 && /\s/.test(source[before])) before -= 1;
      let after = cursor;
      while (after < source.length && /\s/.test(source[after])) after += 1;
      const isFunction = source[after] === "(";
      const isAttribute = before >= 0 && source[before] === ".";
      const isKeyword =
        (source[before] === "(" || source[before] === ",") &&
        source[after] === "=" &&
        source[after + 1] !== "=";
      const candidates: Array<readonly [string, string]> = [];
      if (
        (expandTrailingToken || cursor < source.length) &&
        !SCALAR_LANGUAGE_NAMES.has(token) &&
        !reserved.has(token) &&
        !isFunction &&
        !isAttribute &&
        !isKeyword
      ) {
        for (let index = 1; index < token.length; index += 1) {
          const left = token.slice(0, index);
          const right = token.slice(index);
          if (points.has(left) && points.has(right))
            candidates.push([left, right]);
        }
      }
      result +=
        candidates.length === 1
          ? `Distance(${candidates[0][0]}, ${candidates[0][1]})`
          : token;
      continue;
    }
    result += character;
    cursor += 1;
  }
  return result;
}

/** Present GeoSolver guards as equations while keeping the champion-native JSON unchanged. */
export function guardToFormula(guard: string): string {
  const call = parseCall(guard);
  if (!call) return displayMathConstants(guard);
  const operator = ASSUME_TO_RELATION[call.name];
  if (operator && call.args.length === 2)
    return `${displayMathConstants(call.args[0])} ${operator} ${displayMathConstants(call.args[1])}`;
  if (call.name === "Assume" && call.args.length === 1)
    return displayMathConstants(call.args[0]);
  if (call.name === "Bound" && call.args.length === 2) {
    const interval = /^\(\s*([^,]+)\s*,\s*([^,]+)\s*\)$/.exec(call.args[1]);
    if (interval)
      return `${displayMathConstants(interval[1])} ≤ ${call.args[0]} ≤ ${displayMathConstants(interval[2])}`;
  }
  if (call.name.startsWith("Assume"))
    return displayMathConstants(
      `${call.name.slice("Assume".length)}(${call.args.join(", ")})`,
    );
  return displayMathConstants(guard);
}

function topLevelRelation(
  source: string,
): { lhs: string; operator: string; rhs: string } | undefined {
  let depth = 0;
  for (let index = 0; index < source.length; index += 1) {
    const character = source[index];
    if ("([{".includes(character)) {
      depth += 1;
      continue;
    }
    if (")]}".includes(character)) {
      depth -= 1;
      continue;
    }
    if (depth !== 0) continue;
    const operator = [
      "<=",
      ">=",
      "!=",
      "==",
      "≤",
      "≥",
      "≠",
      "<",
      ">",
      "=",
    ].find((candidate) => source.startsWith(candidate, index));
    if (!operator) continue;
    const lhs = source.slice(0, index).trim();
    const rhs = source.slice(index + operator.length).trim();
    if (lhs && rhs) return { lhs, operator, rhs };
  }
  return undefined;
}

export function formulaToGuard(formula: string): string {
  const source = internalMathConstants(formula.trim());
  if (!source) return source;
  if (/^(?:Assume[A-Za-z]*|Bound)\s*\(/.test(source)) return source;
  const bounded =
    /^(.+?)\s*(?:<=|≤)\s*([A-Za-z_][A-Za-z0-9_]*)\s*(?:<=|≤)\s*(.+)$/.exec(
      source,
    );
  if (bounded)
    return `Bound(${bounded[2]}, (${bounded[1].trim()}, ${bounded[3].trim()}))`;
  const relation = topLevelRelation(source);
  if (relation)
    return `${RELATION_TO_ASSUME[relation.operator]}(${relation.lhs}, ${relation.rhs})`;
  const call = parseCall(source);
  const namedAssumption =
    call &&
    [
      "Acute",
      "Right",
      "Obtuse",
      "Convex",
      "NoSelfIntersecting",
      "Order",
    ].includes(call.name);
  if (call && namedAssumption)
    return `Assume${call.name}(${call.args.join(", ")})`;
  if (call) return source;
  return `Assume(${source})`;
}

export function constraintToFormula(constraint: Constraint): string {
  return `${displayMathConstants(constraint.def)} = ${displayMathConstants(String(constraint.value))}`;
}

function formulaToConstraint(formula: string): Constraint {
  const source = internalMathConstants(formula.trim());
  const relation = topLevelRelation(source);
  if (!relation || !["=", "=="].includes(relation.operator))
    return { def: source, value: 0 };
  const value = /^-?(?:\d+(?:\.\d*)?|\.\d+)$/.test(relation.rhs)
    ? Number(relation.rhs)
    : relation.rhs;
  return { def: relation.lhs, value };
}

export function conditionFromFormula(
  formula: string,
): { kind: "constraint"; value: Constraint } | { kind: "guard"; value: string } | undefined {
  const source = formula.trim();
  if (!source) return undefined;
  const relation = topLevelRelation(internalMathConstants(source));
  return relation && ["=", "=="].includes(relation.operator)
    ? { kind: "constraint", value: formulaToConstraint(source) }
    : { kind: "guard", value: formulaToGuard(source) };
}

export function conditionDraftIssue(source: string): string | undefined {
  const expectedClose: Readonly<Record<string, string>> = {
    "(": ")",
    "[": "]",
  };
  const opening = new Set(Object.keys(expectedClose));
  const closing = new Set(Object.values(expectedClose));
  const stack: Array<{ character: string; index: number }> = [];
  let quote = "";
  for (let index = 0; index < source.length; index += 1) {
    const character = source[index];
    if (quote) {
      if (character === quote && source[index - 1] !== "\\") quote = "";
      continue;
    }
    if (character === '"' || character === "'") {
      quote = character;
      continue;
    }
    if (opening.has(character)) {
      stack.push({ character, index });
      continue;
    }
    if (!closing.has(character)) continue;
    const latest = stack.pop();
    if (!latest || expectedClose[latest.character] !== character)
      return `${index + 1}文字目の「${character}」に対応する開き括弧がありません。式を入力し直してください。`;
  }
  if (quote)
    return `文字列を閉じる「${quote}」がありません。式を入力し直してください。`;
  if (stack.length) {
    const latest = stack[stack.length - 1];
    return `${latest.index + 1}文字目の「${latest.character}」が閉じられていません。「${expectedClose[latest.character]}」を補うか、式を入力し直してください。`;
  }
  return undefined;
}

/**
 * Upgrade projects written by the former visual condition editor.
 *
 * That editor serialized every `=` as AssumeEq, which is a hard admissibility
 * guard in GeoSolver rather than a numerical equation.  The migration is deliberately
 * syntax-generic: every two-argument AssumeEq produced by the UI becomes the
 * equivalent constraint, regardless of the functions used on either side.
 * Raw GeoSolver documents are not passed through this project migration.
 */
export function migrateLegacyUiEquationGuards(problem: Problem): {
  problem: Problem;
  migratedCount: number;
} {
  const constraints = [...problem.constraints];
  const guards: string[] = [];
  let migratedCount = 0;
  for (const guard of problem.guards) {
    const call = parseCall(guard);
    if (call?.name !== "AssumeEq" || call.args.length !== 2) {
      guards.push(guard);
      continue;
    }
    const constraint = formulaToConstraint(`${call.args[0]} = ${call.args[1]}`);
    const duplicate = constraints.some(
      (item) =>
        item.def === constraint.def && String(item.value) === String(constraint.value),
    );
    if (!duplicate) constraints.push(constraint);
    migratedCount += 1;
  }
  return {
    problem:
      migratedCount === 0
        ? problem
        : { ...problem, constraints, guards },
    migratedCount,
  };
}

export function appendUiCondition(problem: Problem, expression: string): Problem {
  const parsed = conditionFromFormula(guardToFormula(expression));
  if (!parsed) return problem;
  return parsed.kind === "constraint"
    ? { ...problem, constraints: [...problem.constraints, parsed.value] }
    : { ...problem, guards: [...problem.guards, parsed.value] };
}

export function formatConditionDraft(formula: string): string {
  let depth = 0;
  let quote = "";
  let result = "";
  for (let index = 0; index < formula.length; index += 1) {
    const character = formula[index];
    if (quote) {
      result += character;
      if (character === quote && formula[index - 1] !== "\\") quote = "";
      continue;
    }
    if (character === '"' || character === "'") {
      quote = character;
      result += character;
      continue;
    }
    if (["(", "[", "{"].includes(character)) depth += 1;
    if (")]}".includes(character)) depth -= 1;
    const operator =
      depth === 0
        ? ["<=", ">=", "!=", "==", "≤", "≥", "≠", "<", ">", "="].find(
            (candidate) => formula.startsWith(candidate, index),
          )
        : undefined;
    if (!operator) {
      result += character;
      continue;
    }
    if (!formula.slice(index + operator.length).trim()) {
      result += operator;
      index += operator.length - 1;
      continue;
    }
    result = result.trimEnd();
    result += ` ${displayMathConstants(operator)} `;
    index += operator.length - 1;
    while (/\s/.test(formula[index + 1] ?? "")) index += 1;
  }
  return result;
}

export function withoutBlankExpressions(problem: Problem): Problem {
  return {
    ...problem,
    constraints: problem.constraints.filter(
      (item) => item.def.trim() && String(item.value).trim(),
    ),
    guards: problem.guards.filter((item) => item.trim()),
  };
}

export function replaceCondition(
  problem: Problem,
  sourceKind: "constraint" | "guard",
  sourceIndex: number,
  formula: string,
): Problem {
  const next: Problem = {
    ...problem,
    constraints:
      sourceKind === "constraint"
        ? problem.constraints.filter((_, index) => index !== sourceIndex)
        : [...problem.constraints],
    guards:
      sourceKind === "guard"
        ? problem.guards.filter((_, index) => index !== sourceIndex)
        : [...problem.guards],
  };
  const parsed = conditionFromFormula(formula);
  if (!parsed) return next;
  if (parsed.kind === "constraint") next.constraints.push(parsed.value);
  else next.guards.push(parsed.value);
  return next;
}
