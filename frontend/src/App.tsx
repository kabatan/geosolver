import {
  Angle,
  ArrowArcRight,
  ArrowClockwise,
  ArrowCounterClockwise,
  ArrowLineRight,
  ArrowRight,
  ArrowsClockwise,
  ArrowsHorizontal,
  ArrowsLeftRight,
  ArrowsOut,
  Check,
  Circle,
  CircleDashed,
  CircleHalf,
  CircleNotch,
  CirclesThree,
  CloudArrowDown,
  CloudArrowUp,
  CompassTool,
  CrosshairSimple,
  Cursor,
  DotsThreeVertical,
  Eye,
  EyeSlash,
  FloppyDisk,
  GridFour,
  Hand,
  Intersect,
  IntersectSquare,
  IntersectThree,
  LineSegment,
  LineSegments,
  MagnifyingGlass,
  Minus,
  Pentagon,
  Play,
  Plus,
  Polygon,
  Ruler,
  Selection,
  Shapes,
  Stop,
  Target,
  Trash,
  Triangle,
  VectorTwo,
  Wrench,
  X,
} from "@phosphor-icons/react";
import {
  CSSProperties,
  ChangeEvent,
  KeyboardEvent as ReactKeyboardEvent,
  MouseEvent as ReactMouseEvent,
  PointerEvent as ReactPointerEvent,
  ReactNode,
  WheelEvent as ReactWheelEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  evaluateScalarExpression,
  evaluateConstrainedScene,
  evaluateScene,
  formatPointExpression,
  IntersectionCandidate,
  nearestIntersection,
  SceneItem,
  screenToWorld,
  uniqueName,
  Vec2,
  Viewport,
  worldToScreen,
} from "./geometry";
import {
  acceptsSceneItem,
  directPointVariables,
  freePointDefinition,
  freedomOf,
  guidedExpression,
  guidedSpecFor,
  GuidedSpec,
  isFixedPointDefinition,
  parameterizedPoint,
  uniqueIdentifier,
} from "./authoring";
import { MathKeyboard } from "./MathKeyboard";
import { expressionToTex, MathFormula, polynomialToTex } from "./MathFormula";
import {
  ExpressionAutocomplete,
  ExpressionSuggestion,
} from "./ExpressionAutocomplete";

type Construction = { name: string; expr: string };
type Constraint = { def: string; value: number | string };
type Problem = {
  task: "solve";
  id: string;
  variables: { names: string[] };
  construction: Construction[];
  constraints: Constraint[];
  guards: string[];
  answer: string;
  post_process: string;
};

type ConditionEditorProps = {
  formula: string;
  conditionIndex: number;
  suggestions: readonly ExpressionSuggestion[];
  normalizeDraft: (value: string) => string;
  mathKeyboardOpen: boolean;
  activeMathField: string;
  autoFocus?: boolean;
  registerMathTarget: (
    editor: HTMLInputElement | HTMLTextAreaElement,
    setter: (value: string) => void,
  ) => void;
  onCommit: (formula: string) => void;
  onDelete: () => void;
};

function ConditionEditorRow({
  formula,
  conditionIndex,
  suggestions,
  normalizeDraft,
  mathKeyboardOpen,
  activeMathField,
  autoFocus,
  registerMathTarget,
  onCommit,
  onDelete,
}: ConditionEditorProps) {
  const [draft, setDraft] = useState(formula);
  useEffect(() => setDraft(formula), [formula]);
  const field = `condition-${conditionIndex}`;
  return (
    <div className="guard-row">
      <div className="formula-editor formula-editor-compact">
        <ExpressionAutocomplete
          value={draft}
          onChange={(value) => setDraft(normalizeDraft(value))}
          onCommit={onCommit}
          suggestions={suggestions}
          ariaLabel={`条件 ${conditionIndex}`}
          ariaControls="math-keyboard"
          ariaDescribedBy={
            mathKeyboardOpen && activeMathField === field
              ? "math-keyboard-status"
              : undefined
          }
          dataMathField={field}
          autoFocus={autoFocus}
          onEditorFocus={(editor) =>
            registerMathTarget(editor, (value) =>
              setDraft(normalizeDraft(value)),
            )
          }
          onEditorClick={(editor) =>
            registerMathTarget(editor, (value) =>
              setDraft(normalizeDraft(value)),
            )
          }
        />
        <MathFormula
          className="formula-preview"
          source={draft}
          label={`条件 ${conditionIndex}の数式表示`}
        />
      </div>
      <button aria-label={`条件 ${conditionIndex}を削除`} onClick={onDelete}>
        <X />
      </button>
    </div>
  );
}
type ExactAnswer = {
  minimal_polynomial_high_to_low: Array<number | string>;
  selected_real_root_index: number;
  isolating_interval: string[];
  decimal: string;
  exact_authority_kind?: string | null;
  approximate_witness?: Record<string, unknown> | null;
};
type SolverMode = "adaptive" | "fixed" | "reference";
type SolverCores = "auto" | number;
type ResourceSummary = {
  max_time_seconds?: number;
  time_limit_seconds?: number;
  cores?: SolverCores;
  seed?: number;
};
type WorkCheckpointSummary = {
  plan_sha256?: string;
  completed_start_ordinals?: number[];
  pending_start_ordinals?: number[];
  extension_batch?: number;
  extension_batch_ordinal?: number;
  batch?: number;
  batch_ordinal?: number;
  window?: number;
  stability_count?: number;
  stable_batch_count?: number;
  extension_stability_count?: number;
};
type ApiResult = {
  status: string;
  elapsed_seconds: number;
  engine_id: string;
  engine_hash: string;
  engine_variant?: string;
  problem_sha256: string;
  requested_resources?: ResourceSummary;
  used_resources?: ResourceSummary;
  work_checkpoint?: WorkCheckpointSummary;
  termination_reason?: string | null;
  warnings: string[];
  answers: ExactAnswer[];
  detail?: string | null;
};
type RunProgress = {
  phase: string;
  completedStarts?: number;
  totalStarts?: number;
  batch?: number;
  stabilityCount?: number;
  usedCores?: number;
  elapsedSeconds: number;
  capSeconds: number;
  terminationReason?: string;
};

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === "object"
    ? (value as Record<string, unknown>)
    : {};
}

function firstFinite(...values: unknown[]): number | undefined {
  for (const value of values) {
    const number = typeof value === "number" ? value : Number.NaN;
    if (Number.isFinite(number)) return number;
  }
  return undefined;
}

function firstText(...values: unknown[]): string | undefined {
  return values.find(
    (value): value is string => typeof value === "string" && !!value.trim(),
  );
}

function progressFromPayload(
  payloadValue: unknown,
  fallback: RunProgress,
): RunProgress {
  const payload = record(payloadValue);
  const progress = record(payload.progress);
  const result = record(payload.result);
  const checkpoint = record(
    progress.work_checkpoint ??
      payload.work_checkpoint ??
      result.work_checkpoint,
  );
  const usedResources = record(
    progress.used_resources ?? payload.used_resources ?? result.used_resources,
  );
  const requestedResources = record(
    progress.requested_resources ??
      payload.requested_resources ??
      result.requested_resources,
  );
  const completedOrdinals = checkpoint.completed_start_ordinals;
  const pendingOrdinals = checkpoint.pending_start_ordinals;
  const completedStarts = Array.isArray(completedOrdinals)
    ? completedOrdinals.length
    : firstFinite(
        progress.completed_starts,
        progress.completed_start_count,
        payload.completed_starts,
        checkpoint.completed_starts,
      );
  const pendingStarts = Array.isArray(pendingOrdinals)
    ? pendingOrdinals.length
    : undefined;
  const totalStarts = firstFinite(
    progress.total_starts,
    payload.total_starts,
    checkpoint.total_starts,
    completedStarts !== undefined && pendingStarts !== undefined
      ? completedStarts + pendingStarts
      : undefined,
  );
  return {
    phase:
      firstText(
        progress.phase,
        payload.phase,
        payload.state,
        result.phase,
      ) ?? fallback.phase,
    completedStarts: completedStarts ?? fallback.completedStarts,
    totalStarts: totalStarts ?? fallback.totalStarts,
    batch:
      firstFinite(
        progress.extension_batch,
        progress.extension_batch_ordinal,
        progress.batch,
        progress.batch_ordinal,
        progress.extension_batches_completed,
        checkpoint.extension_batch,
        checkpoint.extension_batch_ordinal,
        checkpoint.batch,
        checkpoint.batch_ordinal,
        checkpoint.extension_batches_completed,
      ) ?? fallback.batch,
    stabilityCount:
      firstFinite(
        progress.stability_count,
        progress.stable_batch_count,
        progress.extension_stability_count,
        progress.consecutive_empty_extension_batches,
        checkpoint.stability_count,
        checkpoint.stable_batch_count,
        checkpoint.extension_stability_count,
        checkpoint.consecutive_empty_extension_batches,
      ) ?? fallback.stabilityCount,
    usedCores:
      firstFinite(progress.used_cores, payload.used_cores, usedResources.cores) ??
      fallback.usedCores,
    elapsedSeconds:
      firstFinite(
        progress.elapsed_seconds,
        payload.elapsed_seconds,
        result.elapsed_seconds,
      ) ?? fallback.elapsedSeconds,
    capSeconds:
      firstFinite(
        progress.max_time_seconds,
        progress.cap_seconds,
        payload.max_time_seconds,
        requestedResources.max_time_seconds,
        requestedResources.time_limit_seconds,
      ) ?? fallback.capSeconds,
    terminationReason:
      firstText(
        progress.termination_reason,
        payload.termination_reason,
        result.termination_reason,
      ) ?? fallback.terminationReason,
  };
}

const TERMINATION_LABELS: Readonly<Record<string, string>> = {
  initial_work_answered: "初期探索で解を確定",
  extension_stable: "追加探索が安定したため終了",
  safety_cap: "安全上限に到達",
  exact_complete: "厳密完全性を確認",
  cancelled: "ユーザーが中止",
  engine_error: "engine error",
};

function terminationLabel(reason?: string): string {
  if (!reason) return "—";
  return TERMINATION_LABELS[reason] ?? reason;
}

function runPhaseLabel(phase: string): string {
  const labels: Readonly<Record<string, string>> = {
    idle: "待機中",
    validating: "問題を検証中",
    queued: "実行待ち",
    running: "初期探索",
    initial_search: "初期探索",
    extension: "追加探索",
    exact_authority: "厳密判定",
    finalizing: "結果を整理中",
    completed: "完了",
    done: "完了",
    cancelled: "中止",
    error: "エラー",
  };
  return labels[phase] ?? phase;
}
type ValidationIssue = { path: string; code: string; message: string };
type ValidationReport = {
  valid: boolean;
  issues: ValidationIssue[];
  warnings?: ValidationIssue[];
};
type DslCategory = { id: string; label_ja: string; label_en: string };
type DslTool = {
  id: string;
  category: string;
  label_ja: string;
  signature: string;
  authoring_status?: "supported" | "advanced" | "legacy_read_only";
  notes_ja?: string;
};
export type DslCatalog = {
  version: string;
  categories: DslCategory[];
  tools: DslTool[];
};
type ToolMode =
  | "select"
  | "pan"
  | "free-point"
  | "fixed-point"
  | "point-on-object"
  | "segment"
  | "line"
  | "circle"
  | "polygon";
type ObjectStyle = {
  color?: string;
  lineWidth?: number;
  pointSize?: number;
  lineDash?: "solid" | "dashed" | "dotted";
  label?: "name" | "caption" | "hidden";
  caption?: string;
};
type ProjectEnvelope = {
  formatVersion?: number;
  problem: Problem;
  viewport?: { center?: Vec2; pixelsPerUnit?: number };
  style?: {
    grid?: boolean;
    snap?: boolean;
    witness?: boolean;
    hidden?: string[];
    objects?: Record<string, ObjectStyle>;
  };
  ui?: {
    selected?: string;
    variablePreview?: Record<string, number>;
    measurements?: Measurement[];
  };
};
type Measurement = { name: string; expr: string };
type HistoryState = {
  problem: Problem;
  variablePreview: Record<string, number>;
  objectStyles: Record<string, ObjectStyle>;
  hidden: string[];
  measurements: Measurement[];
};
type GuidedSelection = {
  tool: DslTool;
  spec: GuidedSpec;
  names: string[];
  outputName: string;
  choices?: Record<string, string>;
  repeatable?: boolean;
};
type PendingPoint = {
  name: string;
  variables: readonly [string, string];
  expression: string;
  position: Vec2;
};
type PaletteTool = {
  id: string;
  label: string;
  action: "mode" | "guided" | "catalog" | "hint";
  value: string;
  note?: string;
};
type PaletteGroup = { id: string; label: string; tools: PaletteTool[] };

const DEFAULT_POINT_SIZE = 3.5;
const MAX_POINT_SIZE = 8;
function renderedPointSize(style?: ObjectStyle): number {
  return Math.max(
    1.5,
    Math.min(MAX_POINT_SIZE, style?.pointSize ?? DEFAULT_POINT_SIZE),
  );
}

type CanvasLabelPlacement = Readonly<{
  x: number;
  y: number;
  width: number;
  height: number;
}>;

function canvasLabelAnchor(item: SceneItem, viewport: Viewport): Vec2 {
  if (item.kind === "point") return worldToScreen(item.position, viewport);
  if (item.kind === "circle") {
    const center = worldToScreen(item.center, viewport);
    return { x: center.x + item.radius * viewport.pixelsPerUnit, y: center.y };
  }
  if (item.kind === "arc")
    return worldToScreen(
      {
        x: item.center.x + item.radius * Math.cos(item.endAngle),
        y: item.center.y + item.radius * Math.sin(item.endAngle),
      },
      viewport,
    );
  if (item.kind === "polygon")
    return worldToScreen(item.vertices[0] ?? { x: 0, y: 0 }, viewport);
  if (item.kind === "segment" || item.kind === "vector")
    return worldToScreen(
      {
        x: (item.start.x + item.end.x) / 2,
        y: (item.start.y + item.end.y) / 2,
      },
      viewport,
    );
  if (item.kind === "ray")
    return worldToScreen(
      {
        x: item.start.x + item.direction.x,
        y: item.start.y + item.direction.y,
      },
      viewport,
    );
  return worldToScreen(item.anchor, viewport);
}

function canvasLabelLayout(
  items: readonly SceneItem[],
  viewport: Viewport,
  hidden: ReadonlySet<string>,
  styles: Readonly<Record<string, ObjectStyle>>,
): ReadonlyMap<string, CanvasLabelPlacement> {
  const placements = new Map<string, CanvasLabelPlacement>();
  const pointObstacles = items
    .filter((item) => item.kind === "point" && !hidden.has(item.name))
    .map((item) => {
      const point = canvasLabelAnchor(item, viewport);
      return { x: point.x - 7, y: point.y - 7, width: 14, height: 14 };
    });
  const occupied: CanvasLabelPlacement[] = [];
  const intersects = (a: CanvasLabelPlacement, b: CanvasLabelPlacement) =>
    a.x < b.x + b.width &&
    a.x + a.width > b.x &&
    a.y < b.y + b.height &&
    a.y + a.height > b.y;
  const ordered = [...items]
    .filter(
      (item) =>
        !hidden.has(item.name) && styles[item.name]?.label !== "hidden",
    )
    .sort((a, b) => Number(b.kind === "point") - Number(a.kind === "point"));
  for (const item of ordered) {
    const label =
      styles[item.name]?.label === "caption"
        ? styles[item.name]?.caption || item.name
        : item.name;
    const width = Math.min(150, Math.max(28, 16 + Array.from(label).length * 9));
    const height = 26;
    const anchor = canvasLabelAnchor(item, viewport);
    const candidates = [
      { x: anchor.x + 8, y: anchor.y - height - 5 },
      { x: anchor.x + 8, y: anchor.y + 5 },
      { x: anchor.x - width - 8, y: anchor.y - height - 5 },
      { x: anchor.x - width - 8, y: anchor.y + 5 },
      { x: anchor.x - width / 2, y: anchor.y - height - 11 },
      { x: anchor.x - width / 2, y: anchor.y + 11 },
    ];
    const fit = candidates
      .map((candidate) => ({ ...candidate, width, height }))
      .find(
        (candidate) =>
          candidate.x >= 2 &&
          candidate.y >= 2 &&
          candidate.x + candidate.width <= viewport.width - 2 &&
          candidate.y + candidate.height <= viewport.height - 2 &&
          !occupied.some((box) => intersects(candidate, box)) &&
          !pointObstacles.some((box) => intersects(candidate, box)),
      );
    const fallback = fit ?? {
      x: Math.max(2, Math.min(viewport.width - width - 2, anchor.x + 8)),
      y: Math.max(2, Math.min(viewport.height - height - 2, anchor.y - height - 5)),
      width,
      height,
    };
    placements.set(item.name, fallback);
    occupied.push(fallback);
  }
  return placements;
}

function CanvasMathLabel({
  source,
  placement,
  tex,
}: {
  source: string;
  placement: CanvasLabelPlacement;
  tex?: string;
}) {
  const isIdentifier = /^[A-Za-z_][A-Za-z0-9_]*$/.test(source);
  return (
    <foreignObject
      className="canvas-math-label"
      x={placement.x}
      y={placement.y}
      width={placement.width}
      height={placement.height}
      aria-hidden="true"
    >
      <div>
        {tex || isIdentifier ? (
          <MathFormula source={source} tex={tex} />
        ) : (
          <span className="canvas-plain-label">{source}</span>
        )}
      </div>
    </foreignObject>
  );
}

const INITIAL_PROBLEM: Problem = {
  task: "solve",
  id: "distance-3-4-5",
  variables: { names: [] },
  construction: [
    { name: "A", expr: "Point(0, 0)" },
    { name: "B", expr: "Point(3, 4)" },
  ],
  constraints: [],
  guards: [],
  answer: "Distance(A, B)",
  post_process: "",
};
const EMPTY_CATALOG: DslCatalog = { version: "V15", categories: [], tools: [] };
const CANVAS = { width: 1000, height: 700 };
const BASIC_PALETTE_GROUP: PaletteGroup = {
  id: "basic",
  label: "基本ツール",
  tools: [
    { id: "Move", label: "移動", action: "mode", value: "select" },
    {
      id: "Point",
      label: "点",
      action: "mode",
      value: "free-point",
      note: "空白・直線・円を自動判定",
    },
    { id: "Segment", label: "線分", action: "mode", value: "segment" },
    { id: "Line", label: "直線", action: "mode", value: "line" },
    { id: "Polygon", label: "多角形", action: "mode", value: "polygon" },
    {
      id: "CircleThroughPoint",
      label: "中心と1点で円",
      action: "mode",
      value: "circle",
    },
  ],
};
const EDIT_PALETTE_GROUP: PaletteGroup = {
  id: "edit",
  label: "編集",
  tools: [
    {
      id: "SelectObjects",
      label: "オブジェクトを選択",
      action: "mode",
      value: "select",
    },
    {
      id: "ShowHideObject",
      label: "表示／非表示",
      action: "hint",
      value: "オブジェクト一覧の色付き丸を押すと表示を切り替えられます",
    },
    {
      id: "Delete",
      label: "削除",
      action: "hint",
      value: "オブジェクトを選択し、設定パネルの削除を押してください",
    },
  ],
};
const DIRECT_TOOL_MODES: Readonly<Record<string, ToolMode>> = {
  Point: "free-point",
  Segment: "segment",
  Line: "line",
  Polygon: "polygon",
  CircleThroughPoint: "circle",
};

/** The full palette is derived from the canonical DSL catalog so functions cannot silently disappear from the UI. */
export function catalogPaletteGroups(catalog: DslCatalog): PaletteGroup[] {
  const groups = catalog.categories
    .map((category) => ({
      id: category.id,
      label: category.label_ja,
      tools: catalog.tools
        .filter(
          (tool) =>
            tool.category === category.id &&
            tool.authoring_status !== "legacy_read_only",
        )
        .map(
          (tool): PaletteTool => ({
            id: tool.id,
            label: tool.label_ja,
            action: DIRECT_TOOL_MODES[tool.id]
              ? "mode"
              : guidedSpecFor(tool.id)?.choices?.length
                ? "catalog"
                : guidedSpecFor(tool.id)
                  ? "guided"
                  : "catalog",
            value: DIRECT_TOOL_MODES[tool.id] ?? tool.id,
            note: tool.notes_ja,
          }),
        ),
    }))
    .filter((group) => group.tools.length > 0);
  return [EDIT_PALETTE_GROUP, ...groups];
}

function cloneProblem(problem: Problem): Problem {
  return structuredClone(problem);
}
function allNames(problem: Problem): string[] {
  return [
    ...problem.variables.names,
    ...problem.construction.map((item) => item.name),
  ];
}
function toolOutput(
  tool: DslTool,
): "construction" | "measurement" | "constraint" | "guard" {
  const contractOutput = guidedSpecFor(tool.id)?.output;
  if (contractOutput) return contractOutput;
  if (tool.category === "measurements") return "measurement";
  if (tool.category === "constraints") return "constraint";
  if (tool.category === "guards") return "guard";
  return "construction";
}

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
const GUARD_TOOL_NOTATION: Readonly<Record<string, string>> = {
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
function displayMathConstants(source: string): string {
  return source.replace(/\bpi\b/g, "π");
}
function internalMathConstants(source: string): string {
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

/** Present V15 guards as equations while keeping the champion-native JSON unchanged. */
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

function constraintToFormula(constraint: Constraint): string {
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

/**
 * Upgrade projects written by the former visual condition editor.
 *
 * That editor serialized every `=` as AssumeEq, which is a hard admissibility
 * guard in V15 rather than a numerical equation.  The migration is deliberately
 * syntax-generic: every two-argument AssumeEq produced by the UI becomes the
 * equivalent constraint, regardless of the functions used on either side.
 * Raw V15 documents are not passed through this project migration.
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

function appendUiCondition(problem: Problem, expression: string): Problem {
  const parsed = conditionFromFormula(guardToFormula(expression));
  if (!parsed) return problem;
  return parsed.kind === "constraint"
    ? { ...problem, constraints: [...problem.constraints, parsed.value] }
    : { ...problem, guards: [...problem.guards, parsed.value] };
}

function formatConditionDraft(formula: string): string {
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

function replaceCondition(
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

function guardFormulaForTool(tool: DslTool): string {
  return toolOutput(tool) === "guard"
    ? guardToFormula(tool.signature)
    : tool.signature;
}
function validIdentifier(value: string): boolean {
  return /^[A-Za-z_][A-Za-z0-9_]*$/.test(value);
}
function referencesIdentifier(source: string, name: string): boolean {
  return new RegExp(
    `\\b${name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`,
  ).test(source);
}
function replaceIdentifier(source: string, from: string, to: string): string {
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
function deletionClosure(
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
function completeVariablePreview(
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
function isProblem(value: unknown): value is Problem {
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
function isDslCatalog(value: unknown): value is DslCatalog {
  if (!value || typeof value !== "object") return false;
  const item = value as Partial<DslCatalog>;
  return (
    typeof item.version === "string" &&
    Array.isArray(item.categories) &&
    Array.isArray(item.tools)
  );
}
function polynomialText(coefficients: Array<number | string>): string {
  const degree = coefficients.length - 1;
  if (degree < 0) return "—";
  return (
    coefficients
      .map((raw, index) => {
        const coefficient = String(raw);
        const power = degree - index;
        if (coefficient === "0" || coefficient === "0.0") return "";
        const term = power === 0 ? "" : power === 1 ? "x" : `x^${power}`;
        if (!term) return coefficient;
        if (coefficient === "1") return term;
        if (coefficient === "-1") return `-${term}`;
        return `${coefficient}${term}`;
      })
      .filter(Boolean)
      .join(" + ")
      .replace(/\+ -/g, "− ") || "0"
  );
}
const FREEDOM_LABEL = { free: "自由", fixed: "固定", derived: "従属" } as const;
const PROJECT_FORMAT_VERSION = 2;
function saveLastProject(envelope: ProjectEnvelope) {
  const request = indexedDB.open("geotarget", 2);
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
function loadLastProject(onLoad: (value: ProjectEnvelope) => void) {
  const request = indexedDB.open("geotarget", 2);
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
function extractWitnessPoints(
  value: unknown,
): Array<{ name: string; position: Vec2 }> {
  const found = new Map<string, Vec2>();
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

function SceneShape({
  item,
  viewport,
  hidden,
  selected,
  freedom,
  objectStyle,
  labelPlacement,
  guidedCandidate,
  onPointDown,
  onPointMove,
  onPointUp,
  onPointClick,
}: {
  item: SceneItem;
  viewport: Viewport;
  hidden: boolean;
  selected: boolean;
  freedom: "free" | "fixed" | "derived";
  objectStyle?: ObjectStyle;
  labelPlacement?: CanvasLabelPlacement;
  guidedCandidate?: boolean;
  onPointDown: (event: ReactPointerEvent<SVGGElement>, name: string) => void;
  onPointMove: (event: ReactPointerEvent<SVGGElement>) => void;
  onPointUp: (event: ReactPointerEvent<SVGGElement>) => void;
  onPointClick: (event: ReactMouseEvent<SVGElement>, name: string) => void;
}) {
  if (hidden) return null;
  const cls = `geometry-object freedom-${freedom} ${selected ? "selected-object" : ""} ${guidedCandidate === true ? "guided-candidate" : guidedCandidate === false ? "guided-unavailable" : ""}`;
  const candidateLabel =
    guidedCandidate === true
      ? "、次の引数として選択可能"
      : guidedCandidate === false
        ? "、現在の引数には選択不可"
        : "";
  const dash =
    objectStyle?.lineDash === "dashed"
      ? "10 6"
      : objectStyle?.lineDash === "dotted"
        ? "2 5"
        : undefined;
  const label =
    objectStyle?.label === "hidden"
      ? ""
      : objectStyle?.label === "caption"
        ? objectStyle.caption || item.name
        : item.name;
  if (item.kind === "point") {
    const point = worldToScreen(item.position, viewport);
    const pointSize = renderedPointSize(objectStyle);
    return (
      <g
        className={`${cls} geometry-point ${freedom === "free" ? "draggable" : ""}`}
        data-object={item.name}
        data-freedom={freedom}
        role="button"
        tabIndex={0}
        aria-label={`${FREEDOM_LABEL[freedom]}点 ${item.name} (${item.position.x.toFixed(3)}, ${item.position.y.toFixed(3)})${candidateLabel}`}
        aria-disabled={guidedCandidate === false || undefined}
        onPointerDown={(event) => onPointDown(event, item.name)}
        onPointerMove={onPointMove}
        onPointerUp={onPointUp}
        onPointerCancel={onPointUp}
        onLostPointerCapture={onPointUp}
        onClick={(event) => onPointClick(event, item.name)}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            (event.currentTarget as SVGGElement).dispatchEvent(
              new MouseEvent("click", { bubbles: true }),
            );
          }
        }}
      >
        <circle
          className="point-hit"
          cx={point.x}
          cy={point.y}
          r="12"
          style={{ fill: "transparent", stroke: "transparent" }}
        />
        {selected && (
          <circle
            className="point-selection-ring"
            cx={point.x}
            cy={point.y}
            r={pointSize + 1.8}
          />
        )}
        <circle
          cx={point.x}
          cy={point.y}
          r={pointSize}
          style={{ fill: objectStyle?.color }}
        />
        {label && labelPlacement && (
          <CanvasMathLabel source={label} placement={labelPlacement} />
        )}
      </g>
    );
  }
  if (item.kind === "circle") {
    const center = worldToScreen(item.center, viewport);
    return (
      <g
        data-object={item.name}
        role="button"
        tabIndex={0}
        aria-label={`${FREEDOM_LABEL[freedom]}円 ${item.name}${candidateLabel}`}
        aria-disabled={guidedCandidate === false || undefined}
        onClick={(event) => onPointClick(event, item.name)}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            (event.currentTarget as SVGGElement).dispatchEvent(
              new MouseEvent("click", { bubbles: true }),
            );
          }
        }}
      >
        <circle
          className="geometry-object-hit"
          cx={center.x}
          cy={center.y}
          r={item.radius * viewport.pixelsPerUnit}
        />
        <circle
          className={cls}
          cx={center.x}
          cy={center.y}
          r={item.radius * viewport.pixelsPerUnit}
          style={{
            stroke: objectStyle?.color,
            strokeWidth: objectStyle?.lineWidth,
            strokeDasharray: dash,
          }}
        />
        {label && labelPlacement && (
          <CanvasMathLabel source={label} placement={labelPlacement} />
        )}
      </g>
    );
  }
  if (item.kind === "arc") {
    const start = worldToScreen(
      {
        x: item.center.x + item.radius * Math.cos(item.startAngle),
        y: item.center.y + item.radius * Math.sin(item.startAngle),
      },
      viewport,
    );
    const end = worldToScreen(
      {
        x: item.center.x + item.radius * Math.cos(item.endAngle),
        y: item.center.y + item.radius * Math.sin(item.endAngle),
      },
      viewport,
    );
    const turn = (value: number) =>
      ((value % (2 * Math.PI)) + 2 * Math.PI) % (2 * Math.PI);
    const span = item.counterclockwise
      ? turn(item.endAngle - item.startAngle)
      : turn(item.startAngle - item.endAngle);
    const path = `M ${start.x} ${start.y} A ${item.radius * viewport.pixelsPerUnit} ${item.radius * viewport.pixelsPerUnit} 0 ${span > Math.PI ? 1 : 0} ${item.counterclockwise ? 0 : 1} ${end.x} ${end.y}`;
    return (
      <g
        data-object={item.name}
        role="button"
        tabIndex={0}
        aria-label={`${FREEDOM_LABEL[freedom]}円弧 ${item.name}${candidateLabel}`}
        aria-disabled={guidedCandidate === false || undefined}
        onClick={(event) => onPointClick(event, item.name)}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            (event.currentTarget as SVGGElement).dispatchEvent(
              new MouseEvent("click", { bubbles: true }),
            );
          }
        }}
      >
        <path className="geometry-object-hit" d={path} fill="none" />
        <path
          className={cls}
          d={path}
          fill="none"
          style={{
            stroke: objectStyle?.color,
            strokeWidth: objectStyle?.lineWidth,
            strokeDasharray: dash,
          }}
        />
        {label && labelPlacement && (
          <CanvasMathLabel source={label} placement={labelPlacement} />
        )}
      </g>
    );
  }
  if (item.kind === "polygon") {
    const points = item.vertices
      .map((point) => {
        const p = worldToScreen(point, viewport);
        return `${p.x},${p.y}`;
      })
      .join(" ");
    return (
      <g>
        <polygon
          className={cls}
          data-object={item.name}
          role="button"
          tabIndex={0}
          aria-label={`${FREEDOM_LABEL[freedom]}多角形 ${item.name}${candidateLabel}`}
          aria-disabled={guidedCandidate === false || undefined}
          onClick={(event) => onPointClick(event, item.name)}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === " ") {
              event.preventDefault();
              (event.currentTarget as SVGPolygonElement).dispatchEvent(
                new MouseEvent("click", { bubbles: true }),
              );
            }
          }}
          style={{
            stroke: objectStyle?.color,
            strokeWidth: objectStyle?.lineWidth,
            strokeDasharray: dash,
          }}
          points={points}
        />
        {label && labelPlacement && (
          <CanvasMathLabel source={label} placement={labelPlacement} />
        )}
      </g>
    );
  }
  const start =
    item.kind === "segment" || item.kind === "vector"
      ? item.start
      : item.kind === "ray"
        ? item.start
        : item.anchor;
  const direction =
    item.kind === "segment" || item.kind === "vector"
      ? { x: item.end.x - item.start.x, y: item.end.y - item.start.y }
      : item.direction;
  const length = Math.hypot(direction.x, direction.y) || 1;
  const unit = { x: direction.x / length, y: direction.y / length };
  const from =
    item.kind === "segment" || item.kind === "vector"
      ? start
      : item.kind === "ray"
        ? start
        : { x: start.x - unit.x * 100, y: start.y - unit.y * 100 };
  const to =
    item.kind === "segment" || item.kind === "vector"
      ? item.end
      : { x: start.x + unit.x * 100, y: start.y + unit.y * 100 };
  const a = worldToScreen(from, viewport);
  const b = worldToScreen(to, viewport);
  return (
    <g
      data-object={item.name}
      role="button"
      tabIndex={0}
      aria-label={`${FREEDOM_LABEL[freedom]}${item.kind} ${item.name}${candidateLabel}`}
      aria-disabled={guidedCandidate === false || undefined}
      onClick={(event) => onPointClick(event, item.name)}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          (event.currentTarget as SVGGElement).dispatchEvent(
            new MouseEvent("click", { bubbles: true }),
          );
        }
      }}
    >
      <line
        className="geometry-object-hit"
        x1={a.x}
        y1={a.y}
        x2={b.x}
        y2={b.y}
      />
      <line
        className={cls}
        x1={a.x}
        y1={a.y}
        x2={b.x}
        y2={b.y}
        style={{
          stroke: objectStyle?.color,
          strokeWidth: objectStyle?.lineWidth,
          strokeDasharray: dash,
        }}
      />
      {label && labelPlacement && (
        <CanvasMathLabel source={label} placement={labelPlacement} />
      )}
    </g>
  );
}

function PaletteGlyph({ id }: { id: string }) {
  const editGlyphs: Record<string, ReactNode> = {
    Move: <Cursor />,
    SelectObjects: <Selection />,
    ShowHideObject: <Eye />,
    Delete: <Trash />,
  };
  return (
    editGlyphs[id] ?? (
      <svg
        className="palette-icon"
        viewBox="0 0 24 24"
        aria-hidden="true"
        focusable="false"
      >
        <use href={`/tool-icons.svg#tool-${id}`} />
      </svg>
    )
  );
}

type LayoutSizes = { left: number; right: number; bottom: number };
const DEFAULT_LAYOUT_SIZES: LayoutSizes = { left: 350, right: 330, bottom: 196 };
const LAYOUT_STORAGE_KEY = "geotarget.layout.v1";

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(maximum, Math.max(minimum, value));
}

function loadLayoutSizes(): LayoutSizes {
  if (typeof window === "undefined") return DEFAULT_LAYOUT_SIZES;
  try {
    const stored = JSON.parse(
      window.localStorage.getItem(LAYOUT_STORAGE_KEY) ?? "null",
    ) as Partial<LayoutSizes> | null;
    return {
      left: clamp(Number(stored?.left) || DEFAULT_LAYOUT_SIZES.left, 250, 520),
      right: clamp(Number(stored?.right) || DEFAULT_LAYOUT_SIZES.right, 270, 520),
      bottom: clamp(
        Number(stored?.bottom) || DEFAULT_LAYOUT_SIZES.bottom,
        150,
        420,
      ),
    };
  } catch {
    return DEFAULT_LAYOUT_SIZES;
  }
}

type PaneResizeHandleProps = {
  orientation: "vertical" | "horizontal";
  label: string;
  value: number;
  minimum: number;
  maximum: number;
  valuePerPixel: 1 | -1;
  defaultValue: number;
  onChange: (value: number) => void;
};

function PaneResizeHandle({
  orientation,
  label,
  value,
  minimum,
  maximum,
  valuePerPixel,
  defaultValue,
  onChange,
}: PaneResizeHandleProps) {
  const changeBy = (delta: number) =>
    onChange(clamp(value + delta * valuePerPixel, minimum, maximum));
  const beginResize = (event: ReactPointerEvent<HTMLDivElement>) => {
    event.preventDefault();
    const start = orientation === "vertical" ? event.clientX : event.clientY;
    const initial = value;
    const move = (moveEvent: PointerEvent) => {
      const current =
        orientation === "vertical" ? moveEvent.clientX : moveEvent.clientY;
      onChange(
        clamp(initial + (current - start) * valuePerPixel, minimum, maximum),
      );
    };
    const finish = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", finish);
      document.body.classList.remove("pane-resizing");
    };
    document.body.classList.add("pane-resizing");
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", finish, { once: true });
  };
  return (
    <div
      className={`pane-resizer pane-resizer-${orientation}`}
      role="separator"
      aria-label={label}
      aria-orientation={orientation}
      aria-valuemin={minimum}
      aria-valuemax={maximum}
      aria-valuenow={Math.round(value)}
      aria-valuetext={`${Math.round(value)}ピクセル`}
      tabIndex={0}
      title="ドラッグでサイズ変更・ダブルクリックで初期化"
      onPointerDown={beginResize}
      onDoubleClick={() => onChange(defaultValue)}
      onKeyDown={(event) => {
        const decreaseKey = orientation === "vertical" ? "ArrowLeft" : "ArrowUp";
        const increaseKey = orientation === "vertical" ? "ArrowRight" : "ArrowDown";
        if (event.key === decreaseKey || event.key === increaseKey) {
          event.preventDefault();
          changeBy(event.key === increaseKey ? 16 : -16);
        } else if (event.key === "Home" || event.key === "End") {
          event.preventDefault();
          onChange(event.key === "Home" ? minimum : maximum);
        }
      }}
    />
  );
}

export function App() {
  const [problem, setProblem] = useState<Problem>(INITIAL_PROBLEM);
  const [variablePreview, setVariablePreview] = useState<
    Record<string, number>
  >({});
  const [measurements, setMeasurements] = useState<Measurement[]>([]);
  const [history, setHistory] = useState<HistoryState[]>([]);
  const [future, setFuture] = useState<HistoryState[]>([]);
  const [selected, setSelected] = useState("A");
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [tool, setTool] = useState<ToolMode>("select");
  const [toolPoints, setToolPoints] = useState<string[]>([]);
  const [pendingPoints, setPendingPoints] = useState<PendingPoint[]>([]);
  const [leftMode, setLeftMode] = useState<"algebra" | "tools">("tools");
  const [layoutSizes, setLayoutSizes] = useState<LayoutSizes>(loadLayoutSizes);
  const [viewportWidth, setViewportWidth] = useState(() =>
    typeof window === "undefined" ? 1440 : window.innerWidth,
  );
  const [showAllTools, setShowAllTools] = useState(false);
  const [mathKeyboardOpen, setMathKeyboardOpen] = useState(false);
  const [activeMathField, setActiveMathField] = useState("");
  const [grid, setGrid] = useState(true);
  const [snap, setSnap] = useState(true);
  const [showWitness, setShowWitness] = useState(true);
  const [objectStyles, setObjectStyles] = useState<Record<string, ObjectStyle>>(
    {},
  );
  const [propertyTab, setPropertyTab] = useState<
    "basic" | "style" | "advanced"
  >("basic");
  const [camera, setCamera] = useState({
    center: { x: 0, y: 0 } as Vec2,
    pixelsPerUnit: 65,
  });
  const [keyboardPoint, setKeyboardPoint] = useState<Vec2>({ x: 1, y: 1 });
  const [intersectionHint, setIntersectionHint] =
    useState<IntersectionCandidate>();
  const [catalog, setCatalog] = useState<DslCatalog>(EMPTY_CATALOG);
  const [catalogStatus, setCatalogStatus] = useState<
    "loading" | "ready" | "error"
  >("loading");
  const [catalogOpen, setCatalogOpen] = useState(false);
  const [catalogSearch, setCatalogSearch] = useState("");
  const [catalogTool, setCatalogTool] = useState<DslTool>();
  const [guided, setGuided] = useState<GuidedSelection>();
  const [newName, setNewName] = useState("");
  const [newExpression, setNewExpression] = useState("");
  const [newConditionOpen, setNewConditionOpen] = useState(false);
  const [definitionDraft, setDefinitionDraft] = useState("");
  const [guidedChoices, setGuidedChoices] = useState<Record<string, string>>(
    {},
  );
  const [objectSearch, setObjectSearch] = useState("");
  const [editorTab, setEditorTab] = useState<"command" | "json" | "details">(
    "command",
  );
  const [command, setCommand] = useState(INITIAL_PROBLEM.answer);
  const [jsonDraft, setJsonDraft] = useState(
    JSON.stringify(INITIAL_PROBLEM, null, 2),
  );
  const [jsonDirty, setJsonDirty] = useState(false);
  const [uiError, setUiError] = useState("");
  const [validation, setValidation] = useState<ValidationReport>();
  const [doctor, setDoctor] = useState<{ ok: boolean; checks?: unknown }>();
  // Start fail-closed, then apply the backend qualification policy atomically.
  const [solverMode, setSolverMode] = useState<SolverMode>("reference");
  const [optimizedQualified, setOptimizedQualified] = useState(false);
  const [maxTime, setMaxTime] = useState(180);
  const [cores, setCores] = useState<SolverCores>(1);
  const [manualCores, setManualCores] = useState(1);
  const [seed, setSeed] = useState(0);
  const [phase, setPhase] = useState<
    | "idle"
    | "validating"
    | "queued"
    | "running"
    | "done"
    | "cancelled"
    | "error"
  >("idle");
  const [jobId, setJobId] = useState<string>();
  const [elapsed, setElapsed] = useState(0);
  const [runProgress, setRunProgress] = useState<RunProgress>({
    phase: "idle",
    elapsedSeconds: 0,
    capSeconds: 180,
  });
  const [result, setResult] = useState<ApiResult>();
  const [activeAnswer, setActiveAnswer] = useState(0);
  const importRef = useRef<HTMLInputElement>(null);
  const dialogInputRef = useRef<HTMLInputElement>(null);
  const mathTargetRef = useRef<HTMLInputElement | HTMLTextAreaElement | null>(
    null,
  );
  const mathSetterRef = useRef<(value: string) => void>(() => undefined);
  const suppressMathFocusRef = useRef(false);
  const canvasRef = useRef<SVGSVGElement>(null);
  const problemRef = useRef(problem);
  const dialogRef = useRef<HTMLElement | null>(null);
  const dialogTriggerRef = useRef<HTMLElement | null>(null);
  const runToken = useRef(0);
  const dragRef = useRef<
    | (
        | {
            name: string;
            kind: "coordinates";
            variables: readonly [string, string];
            beforePreview: Record<string, number>;
            moved: boolean;
          }
        | {
            name: string;
            kind: "parameter";
            variable: string;
            operation:
              | "PointOnLine"
              | "PointOnSegment"
              | "PointOnCircle"
              | "PointOnAxis";
            carriers: readonly string[];
            axis?: "x" | "y";
            beforePreview: Record<string, number>;
            moved: boolean;
          }
      )
    | undefined
  >(undefined);
  const panRef = useRef<{ point: Vec2; center: Vec2 } | undefined>(undefined);
  const dragFrameRef = useRef<number | undefined>(undefined);
  const pendingDragPointRef = useRef<Vec2 | undefined>(undefined);

  useEffect(() => {
    window.localStorage.setItem(
      LAYOUT_STORAGE_KEY,
      JSON.stringify(layoutSizes),
    );
  }, [layoutSizes]);

  useEffect(() => {
    const updateViewportWidth = () => setViewportWidth(window.innerWidth);
    window.addEventListener("resize", updateViewportWidth);
    return () => window.removeEventListener("resize", updateViewportWidth);
  }, []);

  useEffect(() => {
    if (viewportWidth <= 980) return;
    const panelBudget = Math.max(520, viewportWidth - 14 - 280);
    setLayoutSizes((current) => {
      let left = clamp(current.left, 250, 520);
      let right = clamp(current.right, 270, 520);
      const excess = left + right - panelBudget;
      if (excess > 0) {
        const reduceLeft = Math.min(excess, left - 250);
        left -= reduceLeft;
        right -= Math.min(excess - reduceLeft, right - 270);
      }
      return left === current.left && right === current.right
        ? current
        : { ...current, left, right };
    });
  }, [viewportWidth]);

  const leftPaneMaximum =
    viewportWidth > 980
      ? clamp(viewportWidth - layoutSizes.right - 14 - 280, 250, 520)
      : 520;
  const rightPaneMaximum =
    viewportWidth > 980
      ? clamp(viewportWidth - layoutSizes.left - 14 - 280, 270, 520)
      : 520;

  const scene = useMemo(
    () =>
      evaluateConstrainedScene(
        problem.construction,
        problem.constraints,
        problem.variables.names,
        variablePreview,
      ),
    [problem.construction, problem.constraints, problem.variables.names, variablePreview],
  );
  const pointNames = useMemo(
    () => scene.items.filter((item) => item.kind === "point").map((item) => item.name),
    [scene.items],
  );
  const viewport: Viewport = {
    ...CANVAS,
    center: camera.center,
    pixelsPerUnit: camera.pixelsPerUnit,
  };
  const canvasLabels = useMemo(
    () =>
      canvasLabelLayout(
        scene.items,
        {
          ...CANVAS,
          center: camera.center,
          pixelsPerUnit: camera.pixelsPerUnit,
        },
        hidden,
        objectStyles,
      ),
    [
      scene.items,
      camera.center.x,
      camera.center.y,
      camera.pixelsPerUnit,
      hidden,
      objectStyles,
    ],
  );
  const selectedConstruction = problem.construction.find(
    (item) => item.name === selected,
  );
  const selectedSceneItem = selectedConstruction
    ? scene.byName.get(selectedConstruction.name)
    : undefined;
  const selectedDirectVariables = selectedConstruction
    ? directPointVariables(selectedConstruction, problem.variables.names)
    : undefined;
  const selectedParameter = selectedConstruction
    ? parameterizedPoint(selectedConstruction, problem.variables.names)
    : undefined;
  const isUnselectedIntersection = (construction: Construction) =>
    /^\s*PointOn(?:Circle|Line|Segment)\(/.test(construction.expr) &&
    problem.constraints.some((constraint) =>
      new RegExp(
        `^\\s*On(?:Circle|Line|Segment)\\(\\s*${construction.name}\\b`,
      ).test(constraint.def),
    );
  const displayFreedom = (construction: Construction) =>
    isUnselectedIntersection(construction)
      ? ("derived" as const)
      : freedomOf(construction, problem.variables.names);
  const selectedStyle = selectedConstruction
    ? (objectStyles[selectedConstruction.name] ?? {})
    : {};
  const visibleObjects = useMemo(
    () =>
      problem.construction.filter((item) =>
        `${item.name} ${item.expr}`
          .toLowerCase()
          .includes(objectSearch.toLowerCase()),
      ),
    [problem.construction, objectSearch],
  );
  const treeTabStop = visibleObjects.some((item) => item.name === selected)
    ? selected
    : visibleObjects[0]?.name;
  const filteredCatalog = useMemo(
    () =>
      catalog.tools.filter((item) =>
        `${item.id} ${item.label_ja} ${item.signature}`
          .toLowerCase()
          .includes(catalogSearch.toLowerCase()),
      ),
    [catalog, catalogSearch],
  );
  const paletteGroups = useMemo(
    () =>
      showAllTools ? catalogPaletteGroups(catalog) : [BASIC_PALETTE_GROUP],
    [catalog, showAllTools],
  );
  const mathFunctionNames = useMemo(
    () =>
      catalog.tools
        .filter((item) => item.authoring_status !== "legacy_read_only")
        .map((item) => item.id),
    [catalog],
  );
  const expressionSuggestions = useMemo<ExpressionSuggestion[]>(() => {
    const favoriteTools = [
      "Distance",
      "Angle",
      "OnLine",
      "OnCircle",
      "Point",
      "Line",
      "Segment",
      "CircleThroughPoint",
      "Intersect",
    ];
    const favoriteRank = (id: string) => {
      const index = favoriteTools.indexOf(id);
      return index < 0 ? favoriteTools.length : index;
    };
    const objects = problem.construction.map((item) => ({
      id: `object-${item.name}`,
      label: item.name,
      detail: `作図オブジェクト · ${item.expr}`,
      insert: item.name,
      keywords: item.expr,
    }));
    const variables = problem.variables.names.map((name) => ({
      id: `variable-${name}`,
      label: name,
      detail: "自由変数",
      insert: name,
    }));
    const tools = catalog.tools
      .filter((item) => item.authoring_status !== "legacy_read_only")
      .sort(
        (a, b) =>
          favoriteRank(a.id) - favoriteRank(b.id) ||
          a.id.localeCompare(b.id),
      )
      .map((item) => ({
        id: `tool-${item.id}`,
        label: item.id,
        detail: `${item.label_ja} · ${item.signature}`,
        insert: `${item.id}(`,
        keywords: item.label_ja,
      }));
    return [
      ...objects,
      ...variables,
      ...tools,
      {
        id: "constant-pi",
        label: "π",
        detail: "円周率",
        insert: "π",
        keywords: "pi",
      },
    ];
  }, [catalog, problem.construction, problem.variables.names]);
  const witnessPoints = useMemo(
    () =>
      extractWitnessPoints(result?.answers[activeAnswer]?.approximate_witness),
    [result, activeAnswer],
  );

  useEffect(() => {
    loadLastProject((envelope) => {
      setProblem(envelope.problem);
      setCommand(envelope.problem.answer);
      setJsonDraft(JSON.stringify(envelope.problem, null, 2));
      setVariablePreview(
        completeVariablePreview(envelope.problem, envelope.ui?.variablePreview),
      );
      setMeasurements(envelope.ui?.measurements ?? []);
      if (envelope.viewport?.center && envelope.viewport.pixelsPerUnit)
        setCamera({
          center: envelope.viewport.center,
          pixelsPerUnit: envelope.viewport.pixelsPerUnit,
        });
      if (envelope.style) {
        setGrid(envelope.style.grid ?? true);
        setSnap(envelope.style.snap ?? true);
        setShowWitness(envelope.style.witness ?? true);
        setHidden(new Set(envelope.style.hidden ?? []));
        setObjectStyles(envelope.style.objects ?? {});
      }
      if (envelope.ui?.selected) setSelected(envelope.ui.selected);
    });
    fetch("/api/v1/dsl/catalog")
      .then(async (response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const payload: unknown = await response.json();
        if (!isDslCatalog(payload)) throw new Error("invalid catalog payload");
        return payload;
      })
      .then((payload) => {
        setCatalog(payload);
        setCatalogStatus("ready");
      })
      .catch(() => {
        setCatalogStatus("error");
        setUiError("DSLカタログを読み込めませんでした");
      });
    fetch("/api/v1/doctor")
      .then((response) => response.json())
      .then(setDoctor)
      .catch(() => setDoctor({ ok: false }));
    fetch("/api/v1/qualification")
      .then(async (response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const payload: unknown = await response.json();
        if (
          !payload ||
          typeof payload !== "object" ||
          !("default_engine" in payload) ||
          (payload.default_engine !== "reference" &&
            payload.default_engine !== "optimized")
        ) {
          throw new Error("invalid qualification payload");
        }
        return {
          defaultEngine: payload.default_engine,
          optimizedQualified:
            "promotion_status" in payload &&
            payload.promotion_status === "qualified",
        };
      })
      .then(({ defaultEngine, optimizedQualified: qualified }) => {
        setOptimizedQualified(qualified);
        if (defaultEngine === "optimized") {
          setSolverMode("adaptive");
          setMaxTime(900);
          setCores("auto");
          setManualCores(1);
        } else {
          setSolverMode("reference");
          setMaxTime(180);
          setCores(1);
          setManualCores(1);
        }
      })
      .catch(() => {
        // Fail closed: the initial state is the frozen reference tuple.
      });
  }, []);
  useEffect(() => {
    if (!jsonDirty) setJsonDraft(JSON.stringify(problem, null, 2));
    setCommand(problem.answer);
    setResult(undefined);
    setValidation(undefined);
  }, [problem, jsonDirty]);
  useEffect(() => {
    problemRef.current = problem;
  }, [problem]);
  useEffect(() => {
    setDefinitionDraft(selectedConstruction?.expr ?? "");
  }, [selectedConstruction?.name, selectedConstruction?.expr]);
  useEffect(
    () => () => {
      if (dragFrameRef.current !== undefined)
        window.cancelAnimationFrame(dragFrameRef.current);
    },
    [],
  );
  useEffect(() => {
    const envelope: ProjectEnvelope = {
      formatVersion: PROJECT_FORMAT_VERSION,
      problem,
      viewport: camera,
      style: {
        grid,
        snap,
        witness: showWitness,
        hidden: [...hidden],
        objects: objectStyles,
      },
      ui: { selected, variablePreview, measurements },
    };
    const timer = window.setTimeout(() => saveLastProject(envelope), 500);
    return () => window.clearTimeout(timer);
  }, [
    problem,
    camera,
    grid,
    snap,
    showWitness,
    hidden,
    objectStyles,
    selected,
    variablePreview,
    measurements,
  ]);
  useEffect(() => {
    if (!["queued", "running"].includes(phase)) return;
    const timer = window.setInterval(() => {
      setElapsed((value) => value + 1);
      setRunProgress((current) => ({
        ...current,
        elapsedSeconds: Math.min(
          current.capSeconds,
          current.elapsedSeconds + 1,
        ),
      }));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [phase]);
  useEffect(() => {
    if (!catalogOpen) return;
    dialogInputRef.current?.focus();
    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape") closeCatalog();
      if (event.key === "Tab" && dialogRef.current) {
        const focusable = [
          ...dialogRef.current.querySelectorAll<HTMLElement>(
            'button:not([disabled]), input:not([disabled]), textarea:not([disabled]), [tabindex="0"]',
          ),
        ].filter((item) => item.offsetParent !== null);
        if (!focusable.length) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [catalogOpen]);
  useEffect(() => {
    if (!catalogOpen || !dialogRef.current) return;
    const dialog = dialogRef.current;
    const activateMathInput = (event: FocusEvent) => {
      const target = event.target;
      if (
        target instanceof HTMLTextAreaElement &&
        ["条件式", "V15定義式"].includes(
          target.getAttribute("aria-label") ?? "",
        )
      )
        registerMathTarget(target, setNewExpression);
    };
    dialog.addEventListener("focusin", activateMathInput);
    return () => dialog.removeEventListener("focusin", activateMathInput);
  }, [catalogOpen]);
  useEffect(() => {
    if (!mathKeyboardOpen) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      if (
        event.target instanceof HTMLElement &&
        event.target.getAttribute("aria-expanded") === "true"
      )
        return;
      event.preventDefault();
      event.stopImmediatePropagation();
      closeMathKeyboard();
    };
    window.addEventListener("keydown", closeOnEscape, true);
    return () => window.removeEventListener("keydown", closeOnEscape, true);
  }, [mathKeyboardOpen]);
  useEffect(() => {
    if (mathKeyboardOpen && !mathTargetRef.current?.isConnected)
      closeMathKeyboard(false);
  });
  useEffect(() => {
    if (!mathKeyboardOpen) return;
    const movedOutsideMathEditor = (event: Event) => {
      const target = event.target;
      if (!(target instanceof Node)) return;
      if (target === mathTargetRef.current) return;
      if (document.getElementById("math-keyboard")?.contains(target)) return;
      closeMathKeyboard(false);
    };
    document.addEventListener("focusin", movedOutsideMathEditor, true);
    document.addEventListener("pointerdown", movedOutsideMathEditor, true);
    return () => {
      document.removeEventListener("focusin", movedOutsideMathEditor, true);
      document.removeEventListener("pointerdown", movedOutsideMathEditor, true);
    };
  }, [mathKeyboardOpen]);
  useEffect(() => {
    if (
      catalogOpen ||
      (!guided &&
        toolPoints.length === 0 &&
        (tool === "select" || tool === "pan"))
    )
      return;
    const cancel = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        setGuided(undefined);
        setToolPoints([]);
        setPendingPoints([]);
        setTool("select");
        window.setTimeout(() => canvasRef.current?.focus(), 0);
      }
    };
    window.addEventListener("keydown", cancel);
    return () => window.removeEventListener("keydown", cancel);
  }, [catalogOpen, guided, tool, toolPoints.length]);

  function snapshot(): HistoryState {
    return {
      problem: cloneProblem(problem),
      variablePreview: { ...variablePreview },
      objectStyles: structuredClone(objectStyles),
      hidden: [...hidden],
      measurements: structuredClone(measurements),
    };
  }
  function commit(
    next: Problem,
    nextPreview = completeVariablePreview(next, variablePreview),
  ) {
    setHistory((items) => [...items.slice(-79), snapshot()]);
    setFuture([]);
    problemRef.current = next;
    setProblem(next);
    setVariablePreview(nextPreview);
    setJsonDirty(false);
    setUiError("");
  }
  function cancelDraft(): boolean {
    if (!guided?.names.length && !toolPoints.length && !pendingPoints.length)
      return false;
    setGuided(undefined);
    setToolPoints([]);
    setPendingPoints([]);
    setTool("select");
    setUiError("");
    return true;
  }
  function undo() {
    if (cancelDraft()) return;
    const previous = history.at(-1);
    if (!previous) return;
    setFuture((items) => [snapshot(), ...items]);
    setHistory((items) => items.slice(0, -1));
    setProblem(previous.problem);
    setVariablePreview(previous.variablePreview);
    setObjectStyles(previous.objectStyles);
    setHidden(new Set(previous.hidden));
    setMeasurements(previous.measurements);
  }
  function redo() {
    if (cancelDraft()) return;
    const next = future[0];
    if (!next) return;
    setHistory((items) => [...items, snapshot()]);
    setFuture((items) => items.slice(1));
    setProblem(next.problem);
    setVariablePreview(next.variablePreview);
    setObjectStyles(next.objectStyles);
    setHidden(new Set(next.hidden));
    setMeasurements(next.measurements);
  }
  function svgPointFromClient(clientX: number, clientY: number): Vec2 {
    const svg = canvasRef.current;
    const box = svg?.getBoundingClientRect();
    if (!box || !box.width || !box.height) return { x: 0, y: 0 };
    const matrix = svg?.getScreenCTM?.();
    if (matrix && svg?.createSVGPoint) {
      const point = svg.createSVGPoint();
      point.x = clientX;
      point.y = clientY;
      const local = point.matrixTransform(matrix.inverse());
      return { x: local.x, y: local.y };
    }
    // Browser fallback for the default xMidYMid meet viewBox transform.
    const scale = Math.min(
      box.width / CANVAS.width,
      box.height / CANVAS.height,
    );
    const left = box.left + (box.width - CANVAS.width * scale) / 2;
    const top = box.top + (box.height - CANVAS.height * scale) / 2;
    return { x: (clientX - left) / scale, y: (clientY - top) / scale };
  }
  function worldPointFromClient(
    clientX: number,
    clientY: number,
    useSnap = snap,
  ) {
    const point = screenToWorld(svgPointFromClient(clientX, clientY), viewport);
    return useSnap
      ? { x: Math.round(point.x * 2) / 2, y: Math.round(point.y * 2) / 2 }
      : point;
  }
  function addPointAt(point: Vec2, freedom: "free" | "fixed") {
    const name = uniqueName(allNames(problem), "P");
    if (freedom === "fixed") {
      commit({
        ...problem,
        construction: [
          ...problem.construction,
          { name, expr: formatPointExpression(point, 3) },
        ],
      });
    } else {
      const definition = freePointDefinition(name, point, allNames(problem));
      const next = {
        ...problem,
        variables: {
          names: [...problem.variables.names, ...definition.variables],
        },
        construction: [
          ...problem.construction,
          { name, expr: definition.expression },
        ],
      };
      commit(next, {
        ...completeVariablePreview(next, variablePreview),
        ...definition.preview,
      });
    }
    setSelected(name);
    return name;
  }
  function axisPlacementNear(point: Vec2): "origin" | "x" | "y" | undefined {
    const tolerance = 12 / camera.pixelsPerUnit;
    if (Math.hypot(point.x, point.y) <= tolerance) return "origin";
    if (Math.abs(point.y) <= tolerance) return "x";
    if (Math.abs(point.x) <= tolerance) return "y";
    return undefined;
  }
  function createAxisPointNear(
    hitPoint: Vec2,
    placementPoint = hitPoint,
  ): boolean {
    const placement = axisPlacementNear(hitPoint);
    if (!placement) return false;
    if (placement === "origin") {
      const existing = scene.items.find(
        (item) =>
          item.kind === "point" &&
          Math.hypot(item.position.x, item.position.y) < 1e-10,
      );
      if (existing) setSelected(existing.name);
      else addPointAt({ x: 0, y: 0 }, "fixed");
      return true;
    }
    const name = uniqueName(allNames(problem), "P");
    const coordinate = uniqueIdentifier(
      allNames(problem),
      `${placement}${name}`,
    );
    const value = placement === "x" ? placementPoint.x : placementPoint.y;
    const expression =
      placement === "x" ? `Point(${coordinate}, 0)` : `Point(0, ${coordinate})`;
    const next = {
      ...problem,
      variables: { names: [...problem.variables.names, coordinate] },
      construction: [...problem.construction, { name, expr: expression }],
    };
    commit(next, {
      ...completeVariablePreview(next, variablePreview),
      [coordinate]: value,
    });
    setSelected(name);
    return true;
  }
  function makePendingPoint(point: Vec2, prior = pendingPoints): PendingPoint {
    const reserved = [
      ...allNames(problem),
      ...prior.flatMap((item) => [item.name, ...item.variables]),
    ];
    const name = uniqueName(reserved, "P");
    const definition = freePointDefinition(name, point, reserved);
    return {
      name,
      variables: definition.variables,
      expression: definition.expression,
      position: point,
    };
  }
  function finishObject(
    kind: "Segment" | "Line" | "CircleThroughPoint" | "Polygon",
    names: string[],
    drafts = pendingPoints,
  ) {
    const prefix =
      kind === "Segment"
        ? "s"
        : kind === "Line"
          ? "l"
          : kind === "CircleThroughPoint"
            ? "c"
            : "poly";
    const reserved = [
      ...allNames(problem),
      ...drafts.flatMap((item) => [item.name, ...item.variables]),
    ];
    const name = uniqueName(reserved, prefix);
    const expr =
      kind === "Polygon"
        ? `Polygon([${names.join(", ")}])`
        : `${kind}(${names.join(", ")})`;
    const next = {
      ...problem,
      variables: {
        names: [
          ...problem.variables.names,
          ...drafts.flatMap((item) => item.variables),
        ],
      },
      construction: [
        ...problem.construction,
        ...drafts.map((item) => ({ name: item.name, expr: item.expression })),
        { name, expr },
      ],
    };
    const preview = { ...completeVariablePreview(next, variablePreview) };
    drafts.forEach((item) => {
      preview[item.variables[0]] = item.position.x;
      preview[item.variables[1]] = item.position.y;
    });
    commit(next, preview);
    setSelected(name);
    setToolPoints([]);
    setPendingPoints([]);
  }
  function collectSimplePoint(name: string) {
    if (toolPoints[0] === name) {
      if (tool === "polygon" && toolPoints.length >= 3)
        finishObject("Polygon", toolPoints);
      else
        setUiError(
          tool === "polygon"
            ? "多角形には3点以上必要です"
            : "異なる2点を選択してください",
        );
      return;
    }
    if (toolPoints.includes(name)) {
      setUiError("同じ点は一度だけ選択してください");
      return;
    }
    const names = [...toolPoints, name];
    setToolPoints(names);
    if (tool === "segment" && names.length === 2)
      finishObject("Segment", names);
    else if (tool === "line" && names.length === 2) finishObject("Line", names);
    else if (tool === "circle" && names.length === 2)
      finishObject("CircleThroughPoint", names);
  }
  function collectBlankPoint(point: Vec2) {
    const existingPoint = scene.items.find(
      (item) =>
        item.kind === "point" &&
        Math.hypot(item.position.x - point.x, item.position.y - point.y) < 1e-8,
    );
    const existingDraft = pendingPoints.find(
      (item) =>
        Math.hypot(item.position.x - point.x, item.position.y - point.y) < 1e-8,
    );
    if (existingPoint) {
      collectSimplePoint(existingPoint.name);
      return;
    }
    if (existingDraft) {
      collectSimplePoint(existingDraft.name);
      return;
    }
    const draft = makePendingPoint(point);
    const drafts = [...pendingPoints, draft];
    const names = [...toolPoints, draft.name];
    setPendingPoints(drafts);
    setToolPoints(names);
    setSelected(draft.name);
    if (tool === "segment" && names.length === 2)
      finishObject("Segment", names, drafts);
    else if (tool === "line" && names.length === 2)
      finishObject("Line", names, drafts);
    else if (tool === "circle" && names.length === 2)
      finishObject("CircleThroughPoint", names, drafts);
  }
  function parameterAt(item: SceneItem, point: Vec2): number | undefined {
    if (item.kind === "circle")
      return (
        Math.atan2(point.y - item.center.y, point.x - item.center.x) /
        (2 * Math.PI)
      );
    if (!["line", "segment", "ray", "vector"].includes(item.kind))
      return undefined;
    const carrier = item as Extract<
      SceneItem,
      { kind: "line" | "segment" | "ray" | "vector" }
    >;
    const anchor = carrier.kind === "line" ? carrier.anchor : carrier.start;
    const vector =
      carrier.kind === "line"
        ? { x: -carrier.normal.y, y: carrier.normal.x }
        : carrier.kind === "ray"
          ? carrier.direction
          : {
              x: carrier.end.x - carrier.start.x,
              y: carrier.end.y - carrier.start.y,
            };
    const magnitude = Math.hypot(vector.x, vector.y);
    if (magnitude < 1e-12) return undefined;
    const direction = { x: vector.x / magnitude, y: vector.y / magnitude };
    if (carrier.kind === "segment")
      return Math.max(
        0,
        Math.min(
          1,
          ((point.x - anchor.x) * vector.x + (point.y - anchor.y) * vector.y) /
            (magnitude * magnitude),
        ),
      );
    const base = {
      x:
        anchor.x -
        direction.x * (anchor.x * direction.x + anchor.y * direction.y),
      y:
        anchor.y -
        direction.y * (anchor.x * direction.x + anchor.y * direction.y),
    };
    return (point.x - base.x) * direction.x + (point.y - base.y) * direction.y;
  }
  function addPointOnObject(name: string, point: Vec2) {
    const item = scene.byName.get(name);
    const construction = problem.construction.find(
      (entry) => entry.name === name,
    );
    if (!item || !construction) return;
    const outputName = uniqueName(allNames(problem), "P");
    const variable = uniqueIdentifier(allNames(problem), `t${outputName}`);
    let expression: string | undefined;
    let bound = false;
    if (item.kind === "circle")
      expression = `PointOnCircle(${name}, ${variable})`;
    else if (item.kind === "line")
      expression = `PointOnLine(${name}, ${variable})`;
    else if (item.kind === "segment") {
      const endpoints =
        /^\s*Segment\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*,\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)\s*$/.exec(
          construction.expr,
        );
      if (endpoints) {
        expression = `PointOnSegment(${endpoints[1]}, ${endpoints[2]}, ${variable})`;
        bound = true;
      }
    }
    const parameter = parameterAt(item, point);
    if (!expression || parameter === undefined) {
      setUiError("点は直線・線分・円の上に配置できます");
      return;
    }
    const next = {
      ...problem,
      variables: { names: [...problem.variables.names, variable] },
      construction: [
        ...problem.construction,
        { name: outputName, expr: expression },
      ],
      guards: bound
        ? [...problem.guards, `Bound(${variable}, (0, 1))`]
        : problem.guards,
    };
    commit(next, {
      ...completeVariablePreview(next, variablePreview),
      [variable]: parameter,
    });
    setSelected(outputName);
  }
  function defaultPointOnCarrier(item: SceneItem): Vec2 | undefined {
    if (item.kind === "circle")
      return { x: item.center.x + item.radius, y: item.center.y };
    if (item.kind === "segment")
      return {
        x: (item.start.x + item.end.x) / 2,
        y: (item.start.y + item.end.y) / 2,
      };
    if (item.kind === "line") return item.anchor;
    return undefined;
  }
  function guidedArgument(
    name: string,
    slot: GuidedSpec["slots"][number],
  ): string {
    if (!slot.coerceLinearCarrier) return name;
    const selected = scene.byName.get(name);
    if (!selected || !["segment", "ray", "vector"].includes(selected.kind))
      return name;
    const source =
      problem.construction.find((entry) => entry.name === name)?.expr ?? "";
    const endpoints =
      /^\s*(?:Segment|Ray|Vector)\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*,\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)\s*$/.exec(
        source,
      );
    return endpoints ? `Line(${endpoints[1]}, ${endpoints[2]})` : name;
  }
  function intersectionNear(point: Vec2) {
    return nearestIntersection(
      scene.items.filter((item) => !hidden.has(item.name)),
      point,
      14 / camera.pixelsPerUnit,
    );
  }
  function intersectionArguments(
    candidate: IntersectionCandidate,
  ): readonly [string, string] {
    const lineSlot = { kind: "line", label: "直線" } as const;
    return [
      guidedArgument(candidate.first, lineSlot),
      guidedArgument(candidate.second, lineSlot),
    ];
  }
  function addIntersection(candidate: IntersectionCandidate, selector = "") {
    const outputName = uniqueName(allNames(problem), "P");
    const [first, second] = intersectionArguments(candidate);
    const expression = `Intersect(${first}, ${second}${selector ? `, ${selector}` : ""})`;
    commit({
      ...problem,
      construction: [
        ...problem.construction,
        { name: outputName, expr: expression },
      ],
    });
    setSelected(outputName);
    setIntersectionHint(undefined);
  }
  function endpointNames(
    name: string,
    kind: "Segment" | "Ray",
  ): readonly [string, string] | undefined {
    const source =
      problem.construction.find((item) => item.name === name)?.expr ?? "";
    const match = new RegExp(
      `^\\s*${kind}\\(\\s*([A-Za-z_][A-Za-z0-9_]*)\\s*,\\s*([A-Za-z_][A-Za-z0-9_]*)\\s*\\)\\s*$`,
    ).exec(source);
    return match ? [match[1], match[2]] : undefined;
  }
  function explicitlyContainsPoint(
    objectName: string,
    pointName: string,
  ): boolean {
    const source =
      problem.construction.find((item) => item.name === objectName)?.expr ?? "";
    const call =
      /^\s*([A-Za-z_][A-Za-z0-9_]*)\(\s*([A-Za-z_][A-Za-z0-9_]*(?:\s*,\s*[A-Za-z_][A-Za-z0-9_]*)*)\s*\)\s*$/.exec(
        source,
      );
    if (call) {
      const args = call[2].split(",").map((item) => item.trim());
      if (
        ["Line", "Segment", "Ray", "Vector"].includes(call[1]) &&
        args.slice(0, 2).includes(pointName)
      )
        return true;
      if (
        ["CircleThroughPoint", "Circle"].includes(call[1]) &&
        args[1] === pointName
      )
        return true;
      if (
        ["CircleThroughThreePoints", "Circumcircle"].includes(call[1]) &&
        args.slice(0, 3).includes(pointName)
      )
        return true;
      if (
        ["ParallelLine", "PerpendicularLine"].includes(call[1]) &&
        args.includes(pointName)
      ) {
        const pointArgument = args.find(
          (name) => scene.byName.get(name)?.kind === "point",
        );
        if (pointArgument === pointName) return true;
      }
      if (call[1] === "AngleBisector" && args[1] === pointName) return true;
    }
    const segmentEndpoints = endpointNames(objectName, "Segment");
    return problem.constraints.some((constraint) => {
      const normalized = constraint.def.replace(/\s+/g, "");
      if (
        normalized === `OnCircle(${pointName},${objectName})` ||
        normalized === `OnLine(${pointName},${objectName})`
      )
        return true;
      return (
        !!segmentEndpoints &&
        normalized ===
          `OnSegment(${pointName},${segmentEndpoints[0]},${segmentEndpoints[1]})`
      );
    });
  }
  function pointIsProvenOnObject(
    pointName: string,
    objectName: string,
  ): boolean {
    if (explicitlyContainsPoint(objectName, pointName)) return true;
    const source =
      problem.construction.find((item) => item.name === pointName)?.expr ?? "";
    const direct =
      /^\s*PointOn(?:Circle|Line)\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*,/.exec(
        source,
      );
    if (direct?.[1] === objectName) return true;
    const segment =
      /^\s*PointOnSegment\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*,\s*([A-Za-z_][A-Za-z0-9_]*)\s*,/.exec(
        source,
      );
    const endpoints = endpointNames(objectName, "Segment");
    if (
      segment &&
      endpoints &&
      segment[1] === endpoints[0] &&
      segment[2] === endpoints[1]
    )
      return true;
    const intersection =
      /^\s*Intersect(?:ion)?\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*,\s*([A-Za-z_][A-Za-z0-9_]*)/.exec(
        source,
      );
    return (
      !!intersection &&
      (intersection[1] === objectName || intersection[2] === objectName)
    );
  }
  function provenSharedIntersection(
    candidate: IntersectionCandidate,
  ): string | undefined {
    if (candidate.alternatives.length < 2) return undefined;
    const sibling = candidate.alternatives.find(
      (position) =>
        Math.hypot(
          position.x - candidate.position.x,
          position.y - candidate.position.y,
        ) > 1e-8,
    );
    if (!sibling) return undefined;
    const tolerance =
      1e-7 * Math.max(1, Math.abs(sibling.x), Math.abs(sibling.y));
    return scene.items.find(
      (item) =>
        item.kind === "point" &&
        Math.hypot(item.position.x - sibling.x, item.position.y - sibling.y) <=
          tolerance &&
        pointIsProvenOnObject(item.name, candidate.first) &&
        pointIsProvenOnObject(item.name, candidate.second),
    )?.name;
  }
  function addRelationalIntersection(
    candidate: IntersectionCandidate,
    excludePoint?: string,
  ): boolean {
    const first = scene.byName.get(candidate.first);
    const second = scene.byName.get(candidate.second);
    if (!first || !second) {
      setUiError("交点を構成する図形を確認できません");
      return true;
    }
    const priority = (item: SceneItem) =>
      item.kind === "circle"
        ? 0
        : item.kind === "line"
          ? 1
          : item.kind === "segment"
            ? 2
            : item.kind === "ray"
              ? 3
              : 9;
    const driver = priority(first) <= priority(second) ? first : second;
    const other = driver === first ? second : first;
    const outputName = uniqueName(allNames(problem), "P");
    const variable = uniqueIdentifier(allNames(problem), `t${outputName}`);
    const parameter = parameterAt(driver, candidate.position);
    if (parameter === undefined) {
      setUiError("交点の初期表示位置を保存できませんでした");
      return true;
    }
    let expression: string | undefined;
    const addedGuards: string[] = [];
    if (driver.kind === "circle")
      expression = `PointOnCircle(${driver.name}, ${variable})`;
    else if (driver.kind === "line")
      expression = `PointOnLine(${driver.name}, ${variable})`;
    else if (driver.kind === "segment") {
      const endpoints = endpointNames(driver.name, "Segment");
      if (endpoints) {
        expression = `PointOnSegment(${endpoints[0]}, ${endpoints[1]}, ${variable})`;
        addedGuards.push(`Bound(${variable}, (0, 1))`);
      }
    } else if (driver.kind === "ray") {
      const endpoints = endpointNames(driver.name, "Ray");
      if (endpoints) {
        expression = `PointOnLine(Line(${endpoints[0]}, ${endpoints[1]}), ${variable})`;
        addedGuards.push(
          `AssumeGe(Dot(Vector(${endpoints[0]}, ${outputName}), Vector(${endpoints[0]}, ${endpoints[1]})), 0)`,
        );
      }
    }
    let membership: string | undefined;
    if (other.kind === "circle")
      membership = `OnCircle(${outputName}, ${other.name})`;
    else if (other.kind === "line")
      membership = `OnLine(${outputName}, ${other.name})`;
    else if (other.kind === "segment") {
      const endpoints = endpointNames(other.name, "Segment");
      if (endpoints)
        membership = `OnSegment(${outputName}, ${endpoints[0]}, ${endpoints[1]})`;
    } else if (other.kind === "ray") {
      const endpoints = endpointNames(other.name, "Ray");
      if (endpoints) {
        membership = `OnLine(${outputName}, Line(${endpoints[0]}, ${endpoints[1]}))`;
        addedGuards.push(
          `AssumeGe(Dot(Vector(${endpoints[0]}, ${outputName}), Vector(${endpoints[0]}, ${endpoints[1]})), 0)`,
        );
      }
    }
    if (!expression || !membership) {
      setUiError("この図形の交点所属をV15で表現できません");
      return true;
    }
    if (excludePoint)
      addedGuards.push(`AssumeNe(Distance(${outputName}, ${excludePoint}), 0)`);
    const next = {
      ...problem,
      variables: { names: [...problem.variables.names, variable] },
      construction: [
        ...problem.construction,
        { name: outputName, expr: expression },
      ],
      constraints: [...problem.constraints, { def: membership, value: 0 }],
      guards: [...problem.guards, ...addedGuards],
    };
    commit(next, {
      ...completeVariablePreview(next, variablePreview),
      [variable]: parameter,
    });
    setSelected(outputName);
    setIntersectionHint(undefined);
    return true;
  }
  function createIntersection(candidate: IntersectionCandidate): boolean {
    const exactExisting = scene.items.find(
      (item) =>
        item.kind === "point" &&
        /^\s*Intersect(?:ion)?\(/.test(
          problem.construction.find((entry) => entry.name === item.name)
            ?.expr ?? "",
        ) &&
        Math.hypot(
          item.position.x - candidate.position.x,
          item.position.y - candidate.position.y,
        ) < 1e-8,
    );
    if (exactExisting) {
      setSelected(exactExisting.name);
      setIntersectionHint(undefined);
      return true;
    }
    const first = scene.byName.get(candidate.first);
    const second = scene.byName.get(candidate.second);
    const finiteCarrier =
      first?.kind === "segment" ||
      first?.kind === "ray" ||
      second?.kind === "segment" ||
      second?.kind === "ray";
    const shared = provenSharedIntersection(candidate);
    if (shared && !finiteCarrier) {
      addIntersection(candidate, `exclude=${shared}`);
      return true;
    }
    if (shared) return addRelationalIntersection(candidate, shared);
    if (candidate.alternatives.length <= 1 && !finiteCarrier) {
      addIntersection(candidate);
      return true;
    }
    return addRelationalIntersection(candidate);
  }
  function createIntersectionNear(point: Vec2): boolean {
    const candidate = intersectionNear(point);
    return candidate ? createIntersection(candidate) : false;
  }
  function acceptsGuidedSelection(
    selection: GuidedSelection,
    item: SceneItem,
  ): boolean {
    const slot = selection.spec.slots[selection.names.length];
    if (!slot) return false;
    // PointOnLine owns a draggable point whose carrier must remain a named
    // line. The contextual Point tool is the natural route for segments.
    if (selection.tool.id === "PointOnLine" && slot.kind === "line")
      return item.kind === "line";
    return acceptsSceneItem(slot, item);
  }
  function addMeasurement(name: string, expr: string) {
    const reserved = new Set([
      ...allNames(problem),
      ...measurements.map((item) => item.name),
    ]);
    if (!validIdentifier(name)) {
      setUiError("測定値の名前は英字または_で始めてください");
      return false;
    }
    if (reserved.has(name)) {
      setUiError(`${name} は既に使われています`);
      return false;
    }
    setHistory((items) => [...items.slice(-79), snapshot()]);
    setFuture([]);
    setMeasurements((items) => [
      ...items,
      { name, expr: normalizeScalarInput(expr) },
    ]);
    setUiError("");
    setLeftMode("algebra");
    return true;
  }
  function revealConditions() {
    setLeftMode("algebra");
  }
  function normalizeScalarInput(
    source: string,
    expandTrailingToken = true,
  ): string {
    return internalMathConstants(
      expandDistanceShorthand(source, pointNames, [
        ...allNames(problem),
        ...measurements.map((item) => item.name),
      ], expandTrailingToken),
    );
  }
  function chooseObject(name: string, point?: Vec2) {
    if (mathTargetRef.current?.getAttribute("aria-label") === "定義")
      closeMathKeyboard(false);
    setSelected(name);
    if (tool === "free-point" || tool === "point-on-object") {
      const hit = scene.byName.get(name);
      if (hit?.kind === "point") return;
      if (tool === "free-point" && point && createIntersectionNear(point))
        return;
      const location = point ?? (hit ? defaultPointOnCarrier(hit) : undefined);
      if (!location) {
        setUiError("点は直線・線分・円の上に配置できます");
        return;
      }
      addPointOnObject(name, location);
      return;
    }
    if (guided) {
      const item = scene.byName.get(name);
      const slot = guided.spec.slots[guided.names.length];
      if (!item || !slot || !acceptsGuidedSelection(guided, item)) {
        setUiError(
          `${slot?.label ?? "引数"}には${guided.tool.id === "PointOnLine" ? "直線" : slot?.kind === "line" ? "直線・線分・半直線・ベクトル" : slot?.kind === "line-or-circle" ? "直線・線分・半直線・ベクトル・円" : slot?.kind === "point-or-line" ? "点・直線・線分・半直線・ベクトル" : slot?.kind === "segment" ? "線分" : slot?.kind === "point" ? "点" : "対応するオブジェクト"}を選択してください`,
        );
        return;
      }
      const names = [...guided.names, name];
      if (names.length === guided.spec.slots.length) {
        if (guided.tool.id === "TangentAtPoint") {
          const point = scene.byName.get(names[0]);
          const circle = scene.byName.get(names[1]);
          const distance =
            point?.kind === "point" && circle?.kind === "circle"
              ? Math.hypot(
                  point.position.x - circle.center.x,
                  point.position.y - circle.center.y,
                )
              : undefined;
          const tolerance =
            circle?.kind === "circle" ? 1e-7 * Math.max(1, circle.radius) : 0;
          if (
            distance === undefined ||
            circle?.kind !== "circle" ||
            Math.abs(distance - circle.radius) > tolerance
          ) {
            setUiError(
              "接線の接点には、選択した円の円周上にある点を指定してください",
            );
            setGuided({ ...guided, names: [] });
            return;
          }
        }
        const addedVariables: string[] = [];
        for (const parameter of guided.spec.parameters ?? [])
          addedVariables.push(
            uniqueIdentifier(
              [...allNames(problem), ...addedVariables],
              `${parameter.suffix}${guided.outputName}`,
            ),
          );
        const expression = guidedExpression(
          guided.tool.id,
          names.map((item, index) =>
            guidedArgument(item, guided.spec.slots[index]),
          ),
          guided.spec,
          addedVariables,
          guided.choices,
        );
        if (guided.spec.output === "constraint") {
          commit({
            ...problem,
            constraints: [
              ...problem.constraints,
              { def: expression, value: 0 },
            ],
          });
          revealConditions();
          if (guided.repeatable) setGuided({ ...guided, names: [] });
          else {
            setGuided(undefined);
            setTool("select");
          }
          return;
        }
        if (guided.spec.output === "guard") {
          commit(appendUiCondition(problem, expression));
          revealConditions();
          if (guided.repeatable) setGuided({ ...guided, names: [] });
          else {
            setGuided(undefined);
            setTool("select");
          }
          return;
        }
        if (guided.spec.output === "measurement") {
          if (
            evaluateScalarExpression(expression, scene, variablePreview) ===
            undefined
          ) {
            setUiError(`${guided.tool.label_ja}を現在の引数から計算できません`);
            return;
          }
          if (!addMeasurement(guided.outputName, expression)) return;
          if (guided.repeatable)
            setGuided({
              ...guided,
              names: [],
              outputName: uniqueName(
                [
                  ...allNames(problem),
                  ...measurements.map((item) => item.name),
                  guided.outputName,
                ],
                guided.tool.id.slice(0, 1).toLowerCase(),
              ),
            });
          else {
            setGuided(undefined);
            setTool("select");
          }
          return;
        }
        const next = {
          ...problem,
          variables: { names: [...problem.variables.names, ...addedVariables] },
          construction: [
            ...problem.construction,
            { name: guided.outputName, expr: expression },
          ],
          guards: [
            ...problem.guards,
            ...(guided.spec.parameters ?? []).flatMap((parameter, index) =>
              parameter.boundUnit
                ? [`Bound(${addedVariables[index]}, (0, 1))`]
                : [],
            ),
          ],
        };
        const preview = { ...completeVariablePreview(next, variablePreview) };
        (guided.spec.parameters ?? []).forEach((parameter, index) => {
          preview[addedVariables[index]] = parameter.initial;
        });
        const dryScene = evaluateScene(next.construction, preview);
        if (!dryScene.byName.has(guided.outputName)) {
          const issue = dryScene.warnings.find(
            (warning) => warning.name === guided.outputName,
          );
          setUiError(
            issue?.message ??
              `${guided.tool.label_ja}を現在の引数から作図できません`,
          );
          return;
        }
        commit(next, preview);
        setSelected(guided.outputName);
        if (guided.repeatable)
          setGuided({
            ...guided,
            names: [],
            outputName: uniqueName(
              allNames(next),
              guided.tool.id.slice(0, 1).toLowerCase(),
            ),
          });
        else {
          setGuided(undefined);
          setTool("select");
        }
      } else setGuided({ ...guided, names });
      return;
    }
    const sceneItem = scene.byName.get(name);
    if (sceneItem?.kind !== "point") return;
    if (["segment", "line", "circle", "polygon"].includes(tool))
      collectSimplePoint(name);
  }
  function canvasPointerDown(event: ReactPointerEvent<SVGSVGElement>) {
    if (event.button !== 0) return;
    if ((event.target as Element).closest("[data-object]")) return;
    if (tool === "free-point" || tool === "fixed-point") {
      const rawPoint = worldPointFromClient(
        event.clientX,
        event.clientY,
        false,
      );
      if (tool === "free-point" && createIntersectionNear(rawPoint)) return;
      const placementPoint = worldPointFromClient(event.clientX, event.clientY);
      if (
        tool === "free-point" &&
        createAxisPointNear(rawPoint, placementPoint)
      )
        return;
      addPointAt(placementPoint, tool === "free-point" ? "free" : "fixed");
      return;
    }
    if (tool === "point-on-object") {
      setUiError("直線・線分・円をクリックしてください");
      return;
    }
    if (["segment", "line", "circle", "polygon"].includes(tool)) {
      collectBlankPoint(worldPointFromClient(event.clientX, event.clientY));
      return;
    }
    if (tool === "pan" || tool === "select") {
      panRef.current = {
        point: svgPointFromClient(event.clientX, event.clientY),
        center: camera.center,
      };
      event.currentTarget.setPointerCapture(event.pointerId);
    }
  }
  function canvasKeyDown(event: ReactKeyboardEvent<SVGSVGElement>) {
    const coordinateTool =
      [
        "free-point",
        "fixed-point",
        "segment",
        "line",
        "circle",
        "polygon",
      ].includes(tool) && !guided;
    if (
      coordinateTool &&
      ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)
    ) {
      const step = snap ? 0.5 : 0.1;
      setKeyboardPoint((point) => {
        const next = {
          x:
            point.x +
            (event.key === "ArrowLeft"
              ? -step
              : event.key === "ArrowRight"
                ? step
                : 0),
          y:
            point.y +
            (event.key === "ArrowDown"
              ? -step
              : event.key === "ArrowUp"
                ? step
                : 0),
        };
        if (tool === "free-point") setIntersectionHint(intersectionNear(next));
        return next;
      });
      event.preventDefault();
      return;
    }
    if (coordinateTool && (event.key === "Enter" || event.key === " ")) {
      event.preventDefault();
      if (tool === "free-point" && createIntersectionNear(keyboardPoint))
        return;
      if (tool === "free-point" && createAxisPointNear(keyboardPoint)) return;
      if (tool === "free-point" || tool === "fixed-point")
        addPointAt(keyboardPoint, tool === "free-point" ? "free" : "fixed");
      else collectBlankPoint(keyboardPoint);
      return;
    }
    const step = 40 / camera.pixelsPerUnit;
    if (event.key === "ArrowLeft")
      setCamera((value) => ({
        ...value,
        center: { ...value.center, x: value.center.x - step },
      }));
    else if (event.key === "ArrowRight")
      setCamera((value) => ({
        ...value,
        center: { ...value.center, x: value.center.x + step },
      }));
    else if (event.key === "ArrowUp")
      setCamera((value) => ({
        ...value,
        center: { ...value.center, y: value.center.y + step },
      }));
    else if (event.key === "ArrowDown")
      setCamera((value) => ({
        ...value,
        center: { ...value.center, y: value.center.y - step },
      }));
    else if (event.key === "+")
      setCamera((value) => ({
        ...value,
        pixelsPerUnit: Math.min(180, value.pixelsPerUnit * 1.2),
      }));
    else if (event.key === "-")
      setCamera((value) => ({
        ...value,
        pixelsPerUnit: Math.max(20, value.pixelsPerUnit / 1.2),
      }));
    else return;
    event.preventDefault();
  }
  function pointPointerDown(
    event: ReactPointerEvent<SVGGElement>,
    name: string,
  ) {
    if (event.button !== 0) return;
    if (tool !== "select") return;
    const item = problem.construction.find(
      (candidate) => candidate.name === name,
    );
    if (item && isUnselectedIntersection(item)) return;
    const variables =
      item && directPointVariables(item, problem.variables.names);
    const parameter = item && parameterizedPoint(item, problem.variables.names);
    if (!item || (!variables && !parameter)) return;
    event.preventDefault();
    event.stopPropagation();
    setSelected(name);
    dragRef.current = variables
      ? {
          name,
          kind: "coordinates",
          variables,
          beforePreview: { ...variablePreview },
          moved: false,
        }
      : {
          name,
          kind: "parameter",
          ...parameter!,
          beforePreview: { ...variablePreview },
          moved: false,
        };
    event.currentTarget.setPointerCapture?.(event.pointerId);
  }
  function applyDragPoint(nextPoint: Vec2) {
    if (!dragRef.current) return;
    if (dragRef.current.kind === "coordinates") {
      const [x, y] = dragRef.current.variables;
      dragRef.current.moved = true;
      setVariablePreview((current) => ({
        ...current,
        [x]: nextPoint.x,
        [y]: nextPoint.y,
      }));
      return;
    }
    const drag = dragRef.current;
    let parameter: number | undefined;
    if (drag.operation === "PointOnAxis")
      parameter = drag.axis === "x" ? nextPoint.x : nextPoint.y;
    else if (drag.operation === "PointOnSegment") {
      const first = scene.byName.get(drag.carriers[0]);
      const second = scene.byName.get(drag.carriers[1]);
      if (first?.kind === "point" && second?.kind === "point")
        parameter = parameterAt(
          {
            kind: "segment",
            name: "",
            source: "",
            start: first.position,
            end: second.position,
          },
          nextPoint,
        );
    } else if (drag.operation === "PointOnCircle") {
      const circle = scene.byName.get(drag.carriers[0]);
      if (circle?.kind === "circle") parameter = parameterAt(circle, nextPoint);
    } else {
      const line = scene.byName.get(drag.carriers[0]);
      if (line && ["line", "segment", "ray", "vector"].includes(line.kind))
        parameter = parameterAt(line, nextPoint);
    }
    if (parameter !== undefined && Number.isFinite(parameter)) {
      drag.moved = true;
      setVariablePreview((current) => ({
        ...current,
        [drag.variable]: parameter!,
      }));
    }
  }
  function scheduleDragPoint(point: Vec2) {
    pendingDragPointRef.current = point;
    if (dragFrameRef.current !== undefined) return;
    dragFrameRef.current = window.requestAnimationFrame(() => {
      dragFrameRef.current = undefined;
      const pending = pendingDragPointRef.current;
      pendingDragPointRef.current = undefined;
      if (pending) applyDragPoint(pending);
    });
  }
  function updateIntersectionHint(point: Vec2) {
    const candidate =
      tool === "free-point" ? intersectionNear(point) : undefined;
    setIntersectionHint((current) =>
      current &&
      candidate &&
      current.first === candidate.first &&
      current.second === candidate.second &&
      current.position.x === candidate.position.x &&
      current.position.y === candidate.position.y
        ? current
        : candidate,
    );
  }
  function pointerMove(event: ReactPointerEvent<SVGSVGElement | SVGGElement>) {
    if (dragRef.current) {
      event.stopPropagation();
      scheduleDragPoint(
        worldPointFromClient(event.clientX, event.clientY, false),
      );
      return;
    }
    if (panRef.current) {
      const now = svgPointFromClient(event.clientX, event.clientY);
      const dx = (now.x - panRef.current.point.x) / camera.pixelsPerUnit;
      const dy = (now.y - panRef.current.point.y) / camera.pixelsPerUnit;
      setCamera((value) => ({
        ...value,
        center: {
          x: panRef.current!.center.x - dx,
          y: panRef.current!.center.y + dy,
        },
      }));
    } else
      updateIntersectionHint(
        worldPointFromClient(event.clientX, event.clientY, false),
      );
  }
  function pointerUp(event?: ReactPointerEvent<SVGSVGElement | SVGGElement>) {
    event?.stopPropagation();
    if (dragFrameRef.current !== undefined) {
      window.cancelAnimationFrame(dragFrameRef.current);
      dragFrameRef.current = undefined;
    }
    const pendingDrag = pendingDragPointRef.current;
    pendingDragPointRef.current = undefined;
    if (pendingDrag) applyDragPoint(pendingDrag);
    if (dragRef.current) {
      const completedDrag = dragRef.current;
      if (completedDrag.moved) {
        setHistory((items) => [
          ...items.slice(-79),
          {
            problem: cloneProblem(problem),
            variablePreview: completedDrag.beforePreview,
            objectStyles: structuredClone(objectStyles),
            hidden: [...hidden],
            measurements: structuredClone(measurements),
          },
        ]);
        setFuture([]);
      }
      dragRef.current = undefined;
    }
    panRef.current = undefined;
  }
  function setMode(mode: ToolMode) {
    setTool(mode);
    setToolPoints([]);
    setPendingPoints([]);
    setGuided(undefined);
    setIntersectionHint(undefined);
    setKeyboardPoint({ x: camera.center.x + 1, y: camera.center.y + 1 });
    setUiError("");
    window.setTimeout(() => canvasRef.current?.focus(), 0);
  }
  function registerMathTarget(
    target: HTMLInputElement | HTMLTextAreaElement,
    setter: (value: string) => void,
  ) {
    if (suppressMathFocusRef.current) return;
    mathTargetRef.current = target;
    mathSetterRef.current = setter;
    setActiveMathField(target.dataset.mathField ?? "");
    setMathKeyboardOpen(true);
  }
  function closeMathKeyboard(restoreFocus = true) {
    const target = mathTargetRef.current;
    setMathKeyboardOpen(false);
    setActiveMathField("");
    mathTargetRef.current = null;
    mathSetterRef.current = () => undefined;
    if (restoreFocus && target?.isConnected) {
      suppressMathFocusRef.current = true;
      window.requestAnimationFrame(() => {
        if (target.isConnected) target.focus();
        suppressMathFocusRef.current = false;
      });
    }
  }
  function insertMathText(text: string, caretBack = 0) {
    const target = mathTargetRef.current;
    if (!target?.isConnected) {
      closeMathKeyboard(false);
      return;
    }
    const start = target.selectionStart ?? target.value.length;
    const end = target.selectionEnd ?? start;
    const next = `${target.value.slice(0, start)}${text}${target.value.slice(end)}`;
    const caret = start + text.length - caretBack;
    const keepVirtualKeyFocus =
      document.activeElement instanceof HTMLElement &&
      document.activeElement.dataset.mathKey === "true";
    mathSetterRef.current(next);
    window.requestAnimationFrame(() => {
      if (!keepVirtualKeyFocus) target.focus();
      target.setSelectionRange(caret, caret);
    });
  }
  function mathBackspace() {
    const target = mathTargetRef.current;
    if (!target?.isConnected) {
      closeMathKeyboard(false);
      return;
    }
    const start = target.selectionStart ?? target.value.length;
    const end = target.selectionEnd ?? start;
    if (start === 0 && end === 0) return;
    const from = start === end ? start - 1 : start;
    const next = `${target.value.slice(0, from)}${target.value.slice(end)}`;
    const keepVirtualKeyFocus =
      document.activeElement instanceof HTMLElement &&
      document.activeElement.dataset.mathKey === "true";
    mathSetterRef.current(next);
    window.requestAnimationFrame(() => {
      if (!keepVirtualKeyFocus) target.focus();
      target.setSelectionRange(from, from);
    });
  }
  function moveMathCaret(direction: -1 | 1) {
    const target = mathTargetRef.current;
    if (!target?.isConnected) {
      closeMathKeyboard(false);
      return;
    }
    const position = target.selectionStart ?? target.value.length;
    const next = Math.max(
      0,
      Math.min(target.value.length, position + direction),
    );
    const keepKeyboardFocus = document
      .getElementById("math-keyboard")
      ?.contains(document.activeElement);
    if (!keepKeyboardFocus) target.focus();
    target.setSelectionRange(next, next);
  }
  function confirmMathInput() {
    const target = mathTargetRef.current;
    if (!target?.isConnected) {
      closeMathKeyboard(false);
      return;
    }
    target.dispatchEvent(
      new KeyboardEvent("keydown", {
        key: "Enter",
        ctrlKey: true,
        bubbles: true,
        cancelable: true,
      }),
    );
  }
  function activatePaletteTool(item: PaletteTool) {
    if (item.action === "mode") {
      setMode(item.value as ToolMode);
      return;
    }
    if (item.action === "guided") {
      activateGuidedTool(item.value, item.label);
      return;
    }
    if (item.action === "catalog") {
      const catalogItem = catalog.tools.find(
        (entry) => entry.id === item.value,
      );
      if (!catalogItem) {
        setUiError(
          catalogStatus === "ready"
            ? `${item.label}は現在のV15カタログにありません`
            : "作図カタログを読み込み中です",
        );
        return;
      }
      openCatalog(catalogItem);
      return;
    }
    setUiError(item.value);
  }
  function activateGuidedTool(id: string, label: string) {
    const spec = guidedSpecFor(id);
    if (!spec) {
      setUiError(`${label}は図上作図に未対応です`);
      return;
    }
    const measurementIds = new Set([
      "Angle",
      "Distance",
      "Ratio",
      "Length",
      "Area",
      "Radius",
      "Circumference",
    ]);
    const chosen = catalog.tools.find((entry) => entry.id === id) ?? {
      id,
      category: measurementIds.has(id) ? "measurements" : "construction",
      label_ja: label,
      signature: `${id}(…)`,
    };
    setGuided({
      tool: chosen,
      spec,
      names: [],
      outputName: uniqueName(
        [...allNames(problem), ...measurements.map((item) => item.name)],
        id.slice(0, 1).toLowerCase(),
      ),
      repeatable: true,
    });
    setTool("select");
    setToolPoints([]);
    setUiError("");
    window.setTimeout(() => canvasRef.current?.focus(), 0);
  }
  function openCatalog(item?: DslTool) {
    const chosen =
      item ??
      catalog.tools.find(
        (entry) => entry.authoring_status !== "legacy_read_only",
      ) ??
      catalog.tools[0];
    if (!chosen) {
      setUiError(
        catalogStatus === "error"
          ? "作図カタログを利用できません。サーバー状態を確認してください"
          : "作図カタログを読み込み中です。少し待ってから再度お試しください",
      );
      return;
    }
    closeMathKeyboard(false);
    setCatalogTool(chosen);
    setGuidedChoices(
      Object.fromEntries(
        (guidedSpecFor(chosen.id)?.choices ?? []).map((choice) => [
          choice.name,
          choice.defaultValue,
        ]),
      ),
    );
    setNewName(
      uniqueName(
        [...allNames(problem), ...measurements.map((entry) => entry.name)],
        chosen?.id.slice(0, 1).toLowerCase() || "o",
      ),
    );
    dialogTriggerRef.current = document.activeElement as HTMLElement | null;
    setNewExpression(chosen ? guardFormulaForTool(chosen) : "");
    setCatalogOpen(true);
  }
  function closeCatalog() {
    closeMathKeyboard(false);
    setCatalogOpen(false);
    window.setTimeout(() => dialogTriggerRef.current?.focus(), 0);
  }
  function startGuidedSelection() {
    if (!catalogTool) return;
    const spec = guidedSpecFor(catalogTool.id);
    if (!spec) return;
    const outputName =
      newName.trim() ||
      uniqueName(
        [...allNames(problem), ...measurements.map((item) => item.name)],
        catalogTool.id.slice(0, 1).toLowerCase(),
      );
    if (!validIdentifier(outputName)) {
      setUiError("IDは英字または_で始まる識別子にしてください");
      return;
    }
    if (
      [...allNames(problem), ...measurements.map((item) => item.name)].includes(
        outputName,
      )
    ) {
      setUiError(`ID ${outputName} は既に使われています`);
      return;
    }
    setGuided({
      tool: catalogTool,
      spec,
      names: [],
      outputName,
      choices: guidedChoices,
    });
    setTool("select");
    setToolPoints([]);
    closeCatalog();
  }
  function addCatalogObject() {
    if (!catalogTool || !newExpression.trim()) return;
    const output = toolOutput(catalogTool);
    const needsName = output === "construction" || output === "measurement";
    const expression = ["measurement", "constraint", "guard"].includes(output)
      ? normalizeScalarInput(newExpression.trim())
      : internalMathConstants(newExpression.trim());
    if (needsName && !newName.trim()) return;
    if (catalogTool.authoring_status === "legacy_read_only") {
      setUiError(
        "この関数は既存ファイルの表示専用です。新規作図には推奨される代替を使用してください。",
      );
      return;
    }
    if (output === "constraint") {
      commit({
        ...problem,
        constraints: [...problem.constraints, { def: expression, value: 0 }],
      });
      revealConditions();
      closeCatalog();
      return;
    }
    if (output === "guard") {
      commit(appendUiCondition(problem, expression));
      revealConditions();
      closeCatalog();
      return;
    }
    if (output === "measurement") {
      if (addMeasurement(newName.trim(), expression)) closeCatalog();
      return;
    }
    if (!validIdentifier(newName.trim())) {
      setUiError("IDは英字または_で始まる識別子にしてください");
      return;
    }
    if (allNames(problem).includes(newName.trim())) {
      setUiError(`ID ${newName.trim()} は既に使われています`);
      return;
    }
    commit({
      ...problem,
      construction: [
        ...problem.construction,
        { name: newName.trim(), expr: expression },
      ],
    });
    setSelected(newName.trim());
    closeCatalog();
  }
  async function validateCurrent(
    candidate: Problem = problem,
  ): Promise<ValidationReport | undefined> {
    setNewConditionOpen(false);
    const prepared = withoutBlankExpressions(candidate);
    if (JSON.stringify(prepared) !== JSON.stringify(candidate)) commit(prepared);
    try {
      await fetch("/api/v1/session", { credentials: "same-origin" });
      const response = await fetch("/api/v1/preview", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(prepared),
      });
      if (!response.ok) throw new Error(`検証API: HTTP ${response.status}`);
      const payload = (await response.json()) as {
        validation: ValidationReport;
      };
      setValidation(payload.validation);
      return payload.validation;
    } catch (error) {
      setUiError(
        error instanceof Error ? error.message : "検証できませんでした",
      );
      return undefined;
    }
  }
  async function startSolve() {
    const token = ++runToken.current;
    const prepared = withoutBlankExpressions(problem);
    if (JSON.stringify(prepared) !== JSON.stringify(problem)) commit(prepared);
    const submittedProblem = JSON.stringify(prepared);
    const requestedMaxTime =
      solverMode === "reference"
        ? 180
        : Math.min(900, Math.max(180, Math.round(maxTime)));
    const requestedCores: SolverCores =
      solverMode === "reference"
        ? 1
        : cores === "auto"
          ? "auto"
          : Math.max(1, Math.round(cores));
    const options = {
      engine: solverMode === "reference" ? "reference" : "optimized",
      run_mode: solverMode === "adaptive" ? "adaptive" : "fixed_time",
      max_time_seconds: requestedMaxTime,
      cores: requestedCores,
      seed,
    } as const;
    setPhase("validating");
    setElapsed(0);
    setRunProgress({
      phase: "validating",
      elapsedSeconds: 0,
      capSeconds: requestedMaxTime,
      usedCores:
        typeof requestedCores === "number" ? requestedCores : undefined,
    });
    setResult(undefined);
    setUiError("");
    const report = await validateCurrent(prepared);
    if (token !== runToken.current) return;
    if (!report?.valid) {
      setPhase("error");
      setRunProgress((currentProgress) => ({
        ...currentProgress,
        phase: "error",
      }));
      return;
    }
    try {
      const response = await fetch("/api/v1/solves", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          problem: prepared,
          options,
        }),
      });
      if (!response.ok)
        throw new Error(`solve request failed (HTTP ${response.status})`);
      const created = (await response.json()) as { job_id: string };
      if (token !== runToken.current) {
        await fetch(`/api/v1/solves/${created.job_id}`, {
          method: "DELETE",
          credentials: "same-origin",
        }).catch(() => undefined);
        return;
      }
      setJobId(created.job_id);
      setPhase("queued");
      setRunProgress((currentProgress) => ({
        ...currentProgress,
        phase: "queued",
      }));
      while (token === runToken.current) {
        await new Promise((resolve) => window.setTimeout(resolve, 700));
        const current = await fetch(`/api/v1/solves/${created.job_id}`, {
          credentials: "same-origin",
        });
        if (!current.ok)
          throw new Error(`job status failed (HTTP ${current.status})`);
        const payload = (await current.json()) as {
          state: string;
          result: ApiResult | null;
          progress?: unknown;
          [key: string]: unknown;
        };
        if (token !== runToken.current) return;
        setRunProgress((currentProgress) =>
          progressFromPayload(payload, currentProgress),
        );
        if (payload.state === "running") setPhase("running");
        if (payload.result) {
          if (
            JSON.stringify(withoutBlankExpressions(problemRef.current)) !==
            submittedProblem
          ) {
            setUiError(
              "計算中に問題が変更されたため、この結果は表示しません。もう一度実行してください",
            );
            setPhase("error");
            setRunProgress((currentProgress) => ({
              ...currentProgress,
              phase: "error",
            }));
            return;
          }
          setResult(payload.result);
          setRunProgress((currentProgress) => {
            const completed = progressFromPayload(payload, currentProgress);
            return {
              ...completed,
              phase:
                payload.result?.status === "cancelled"
                  ? "cancelled"
                  : payload.result?.status.endsWith("error")
                    ? "error"
                    : "done",
            };
          });
          setPhase(
            payload.result.status.endsWith("error")
              ? "error"
              : payload.result.status === "cancelled"
                ? "cancelled"
                : "done",
          );
          return;
        }
        if (payload.state === "cancelled") {
          setPhase("cancelled");
          setRunProgress((currentProgress) => ({
            ...currentProgress,
            phase: "cancelled",
            terminationReason: "cancelled",
          }));
          return;
        }
      }
    } catch (error) {
      if (token === runToken.current) {
        setUiError(
          error instanceof Error ? error.message : "solverに接続できません",
        );
        setPhase("error");
        setRunProgress((currentProgress) => ({
          ...currentProgress,
          phase: "error",
          terminationReason: "engine_error",
        }));
      }
    }
  }
  async function cancelSolve() {
    const id = jobId;
    ++runToken.current;
    setPhase("cancelled");
    setRunProgress((current) => ({
      ...current,
      phase: "cancelled",
      terminationReason: "cancelled",
    }));
    if (id)
      await fetch(`/api/v1/solves/${id}`, {
        method: "DELETE",
        credentials: "same-origin",
      }).catch(() => undefined);
  }
  function applyJson() {
    try {
      const parsed = JSON.parse(jsonDraft) as unknown;
      if (!isProblem(parsed))
        throw new Error("V15 problemの必須fieldが不足しています");
      commit(parsed);
      setJsonDirty(false);
    } catch (error) {
      setUiError(
        error instanceof Error ? error.message : "JSONを解釈できません",
      );
    }
  }
  function importProject(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    file.text().then((text) => {
      try {
        const parsed = JSON.parse(text) as Problem | ProjectEnvelope;
        const imported = "problem" in parsed ? parsed.problem : parsed;
        if (!isProblem(imported)) throw new Error("V15 problemではありません");
        const prepared =
          "problem" in parsed
            ? migrateLegacyUiEquationGuards(imported).problem
            : imported;
        const importedPreview = completeVariablePreview(
          prepared,
          "problem" in parsed ? parsed.ui?.variablePreview : undefined,
        );
        commit(prepared, importedPreview);
        setSelected(
          "problem" in parsed
            ? parsed.ui?.selected || prepared.construction[0]?.name || ""
            : prepared.construction[0]?.name || "",
        );
        setMeasurements(
          "problem" in parsed ? (parsed.ui?.measurements ?? []) : [],
        );
        if (
          "problem" in parsed &&
          parsed.viewport?.center &&
          parsed.viewport.pixelsPerUnit
        )
          setCamera({
            center: parsed.viewport.center,
            pixelsPerUnit: parsed.viewport.pixelsPerUnit,
          });
        if ("problem" in parsed && parsed.style) {
          setGrid(parsed.style.grid ?? true);
          setSnap(parsed.style.snap ?? true);
          setShowWitness(parsed.style.witness ?? true);
          setHidden(new Set(parsed.style.hidden ?? []));
          setObjectStyles(parsed.style.objects ?? {});
        }
      } catch (error) {
        setUiError(
          error instanceof Error ? error.message : "ファイルを読み込めません",
        );
      }
      event.target.value = "";
    });
  }
  function download(value: unknown, suffix: string) {
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }),
    );
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${problem.id}${suffix}`;
    anchor.click();
    URL.revokeObjectURL(url);
  }
  function toggleSelectedPointFreedom() {
    if (!selectedConstruction) return;
    const scenePoint = scene.byName.get(selectedConstruction.name);
    if (scenePoint?.kind !== "point") return;
    const variables = directPointVariables(
      selectedConstruction,
      problem.variables.names,
    );
    if (variables) {
      const sources = [
        ...problem.construction
          .filter((item) => item.name !== selectedConstruction.name)
          .map((item) => item.expr),
        ...problem.constraints.map((item) => item.def),
        ...problem.constraints.map((item) => String(item.value)),
        ...problem.guards,
        problem.answer,
        problem.post_process,
      ];
      if (
        variables.some((name) =>
          sources.some((source) => referencesIdentifier(source, name)),
        )
      ) {
        setUiError(
          "この自由点の変数は他の式から参照されています。先に参照を外してください。",
        );
        return;
      }
      const next = {
        ...problem,
        variables: {
          names: problem.variables.names.filter(
            (name) => !variables.includes(name),
          ),
        },
        construction: problem.construction.map((item) =>
          item.name === selectedConstruction.name
            ? { ...item, expr: formatPointExpression(scenePoint.position, 3) }
            : item,
        ),
      };
      const preview = { ...variablePreview };
      delete preview[variables[0]];
      delete preview[variables[1]];
      commit(next, preview);
    } else {
      const definition = freePointDefinition(
        selectedConstruction.name,
        scenePoint.position,
        allNames(problem),
      );
      const next = {
        ...problem,
        variables: {
          names: [...problem.variables.names, ...definition.variables],
        },
        construction: problem.construction.map((item) =>
          item.name === selectedConstruction.name
            ? { ...item, expr: definition.expression }
            : item,
        ),
      };
      commit(next, {
        ...completeVariablePreview(next, variablePreview),
        ...definition.preview,
      });
    }
  }
  function renameSelected(rawName: string): boolean {
    if (!selectedConstruction) return false;
    const previousName = selectedConstruction.name;
    const nextName = rawName.trim();
    if (nextName === previousName) return true;
    if (!validIdentifier(nextName)) {
      setUiError("名前は英字または_で始め、英数字と_だけを使ってください");
      return false;
    }
    if (
      allNames(problem).some(
        (name) => name !== previousName && name === nextName,
      ) ||
      measurements.some((item) => item.name === nextName)
    ) {
      setUiError(`${nextName} は既に使われています`);
      return false;
    }
    const replace = (source: string) =>
      replaceIdentifier(source, previousName, nextName);
    const next: Problem = {
      ...problem,
      construction: problem.construction.map((item) => ({
        name: item.name === previousName ? nextName : item.name,
        expr: replace(item.expr),
      })),
      constraints: problem.constraints.map((item) => ({
        def: replace(item.def),
        value:
          typeof item.value === "string" ? replace(item.value) : item.value,
      })),
      guards: problem.guards.map(replace),
      answer: replace(problem.answer),
      post_process: replace(problem.post_process),
    };
    commit(next);
    setMeasurements((items) =>
      items.map((item) => ({ ...item, expr: replace(item.expr) })),
    );
    setObjectStyles((current) => {
      if (!(previousName in current)) return current;
      const styles = { ...current, [nextName]: current[previousName] };
      delete styles[previousName];
      return styles;
    });
    setHidden((current) => {
      if (!current.has(previousName)) return current;
      const renamed = new Set(current);
      renamed.delete(previousName);
      renamed.add(nextName);
      return renamed;
    });
    setSelected(nextName);
    return true;
  }
  function updateSelectedDefinition(rawExpression: string): boolean {
    if (!selectedConstruction) return false;
    const expression = internalMathConstants(rawExpression.trim());
    if (!expression) {
      setUiError("定義を空にはできません");
      return false;
    }
    if (expression === selectedConstruction.expr) return true;
    commit({
      ...problem,
      construction: problem.construction.map((item) =>
        item.name === selectedConstruction.name
          ? { ...item, expr: expression }
          : item,
      ),
    });
    return true;
  }
  function removeSelected() {
    if (!selectedConstruction) return;
    closeMathKeyboard(false);
    const removed = deletionClosure(problem, selectedConstruction.name);
    const removedIdentifiers = [...removed.names, ...removed.variables];
    const referencesRemoved = (source: string) =>
      removedIdentifiers.some((name) => referencesIdentifier(source, name));
    const remainingConstruction = problem.construction.filter(
      (item) => !removed.names.has(item.name),
    );
    const next = {
      ...problem,
      construction: remainingConstruction,
      variables: {
        names: problem.variables.names.filter(
          (name) => !removed.variables.has(name),
        ),
      },
      constraints: problem.constraints.filter(
        (item) =>
          !referencesRemoved(item.def) &&
          !referencesRemoved(String(item.value)),
      ),
      guards: problem.guards.filter((guard) => !referencesRemoved(guard)),
      answer: referencesRemoved(problem.answer) ? "" : problem.answer,
      post_process: referencesRemoved(problem.post_process)
        ? ""
        : problem.post_process,
    };
    const preview = { ...variablePreview };
    removed.variables.forEach((name) => delete preview[name]);
    commit(next, preview);
    setMeasurements((items) =>
      items.filter(
        (measurement) =>
          ![...removed.names, ...removed.variables].some((name) =>
            referencesIdentifier(measurement.expr, name),
          ),
      ),
    );
    setObjectStyles((current) => {
      const styles = { ...current };
      removed.names.forEach((name) => delete styles[name]);
      return styles;
    });
    setHidden((current) => {
      const nextHidden = new Set(current);
      removed.names.forEach((name) => nextHidden.delete(name));
      return nextHidden;
    });
    setSelected(remainingConstruction[0]?.name ?? "");
  }
  function updateSelectedStyle(patch: Partial<ObjectStyle>) {
    if (!selectedConstruction) return;
    setHistory((items) => [...items.slice(-79), snapshot()]);
    setFuture([]);
    setObjectStyles((current) => ({
      ...current,
      [selectedConstruction.name]: {
        ...current[selectedConstruction.name],
        ...patch,
      },
    }));
  }
  function clearAll() {
    closeMathKeyboard(false);
    const hasContent =
      problem.construction.length ||
      problem.variables.names.length ||
      problem.constraints.length ||
      problem.guards.length ||
      problem.answer ||
      problem.post_process ||
      measurements.length;
    if (
      !hasContent ||
      !window.confirm(
        "すべてのオブジェクト・制約・ターゲットを消去します。元に戻すことができます。",
      )
    )
      return;
    const next: Problem = {
      ...problem,
      variables: { names: [] },
      construction: [],
      constraints: [],
      guards: [],
      answer: "",
      post_process: "",
    };
    commit(next, {});
    setMeasurements([]);
    setSelected("");
    setHidden(new Set());
    setObjectStyles({});
    setToolPoints([]);
    setPendingPoints([]);
    setGuided(undefined);
    setTool("select");
  }
  function fitAllObjects() {
    const points: Vec2[] = [];
    scene.items
      .filter((item) => !hidden.has(item.name))
      .forEach((item) => {
        if (item.kind === "point") points.push(item.position);
        else if (item.kind === "circle" || item.kind === "arc")
          points.push(
            { x: item.center.x - item.radius, y: item.center.y - item.radius },
            { x: item.center.x + item.radius, y: item.center.y + item.radius },
          );
        else if (item.kind === "segment" || item.kind === "vector")
          points.push(item.start, item.end);
        else if (item.kind === "ray") points.push(item.start);
        else if (item.kind === "line") points.push(item.anchor);
        else if (item.kind === "polygon") points.push(...item.vertices);
      });
    if (!points.length) {
      setCamera({ center: { x: 0, y: 0 }, pixelsPerUnit: 65 });
      return;
    }
    const minX = Math.min(...points.map((point) => point.x));
    const maxX = Math.max(...points.map((point) => point.x));
    const minY = Math.min(...points.map((point) => point.y));
    const maxY = Math.max(...points.map((point) => point.y));
    const width = Math.max(maxX - minX, 1);
    const height = Math.max(maxY - minY, 1);
    setCamera({
      center: { x: (minX + maxX) / 2, y: (minY + maxY) / 2 },
      pixelsPerUnit: Math.max(
        20,
        Math.min(
          180,
          (CANVAS.width - 120) / width,
          (CANVAS.height - 120) / height,
        ),
      ),
    });
  }
  const running = ["validating", "queued", "running"].includes(phase);
  const draftActive =
    !!guided?.names.length || !!toolPoints.length || !!pendingPoints.length;
  const keyboardIntersection =
    tool === "free-point" ? intersectionNear(keyboardPoint) : undefined;
  const keyboardAxisPlacement =
    tool === "free-point" && !keyboardIntersection
      ? axisPlacementNear(keyboardPoint)
      : undefined;
  const instruction = guided
    ? `${guided.tool.label_ja}: ${guided.spec.slots[guided.names.length]?.label}を図から選択（${guided.names.length}/${guided.spec.slots.length}）`
    : tool === "free-point"
      ? keyboardIntersection
        ? "交点候補。Enterで両branchを保持した交点を作成"
        : keyboardAxisPlacement === "origin"
          ? "原点に吸着。Enterで固定点を作成"
          : keyboardAxisPlacement
            ? `${keyboardAxisPlacement}軸に吸着。Enterで軸上を動く点を作成`
            : "位置または直線・線分・円・座標軸を選択してください"
      : tool === "fixed-point"
        ? "空白をクリックして固定点を配置（灰色）"
        : tool === "point-on-object"
          ? "直線・線分・円をクリックした位置に、1自由度の点を作成"
          : tool === "segment" || tool === "line" || tool === "circle"
            ? `点または空白を選択（${toolPoints.length}/2）`
            : tool === "polygon"
              ? `点または空白を選択。最初の点で閉じる（${toolPoints.length}点）`
              : tool === "pan"
                ? "ドラッグして表示範囲を移動"
                : "青い点をドラッグして移動。空白ドラッグでパン";

  return (
    <div className="app-shell">
      <header
        className="app-bar"
        inert={catalogOpen ? true : undefined}
        aria-hidden={catalogOpen || undefined}
      >
        <div className="brand">GeoTarget</div>
        <span className="project-name">{problem.id}.geotarget.json</span>
        <div className="app-actions">
          <input
            ref={importRef}
            className="visually-hidden"
            tabIndex={-1}
            type="file"
            accept=".json,.geotarget.json"
            onChange={importProject}
          />
          <button onClick={() => importRef.current?.click()}>
            <CloudArrowDown />
            読み込む
          </button>
          <button
            onClick={() =>
              download(
                {
                  formatVersion: PROJECT_FORMAT_VERSION,
                  problem,
                  viewport: camera,
                  style: {
                    grid,
                    snap,
                    witness: showWitness,
                    hidden: [...hidden],
                    objects: objectStyles,
                  },
                  ui: { selected, variablePreview, measurements },
                },
                ".geotarget.json",
              )
            }
          >
            <CloudArrowUp />
            プロジェクト
          </button>
          <button onClick={() => download(problem, ".json")}>
            <FloppyDisk />
            V15 JSON
          </button>
          <span
            className={`doctor-status ${doctor?.ok === false ? "bad" : ""}`}
          >
            {doctor?.ok ? (
              <Check weight="bold" />
            ) : doctor ? (
              <X weight="bold" />
            ) : null}
            {doctor
              ? `Doctor: ${doctor.ok ? "正常" : "要確認"}`
              : "Doctor: 確認中"}
          </span>
        </div>
      </header>
      <main
        className="workspace"
        style={
          {
            "--left-pane-width": `${layoutSizes.left}px`,
            "--right-pane-width": `${layoutSizes.right}px`,
          } as CSSProperties
        }
        inert={catalogOpen ? true : undefined}
        aria-hidden={catalogOpen || undefined}
      >
        <aside className="model-pane geogebra-pane" aria-label="作図サイドバー">
          <nav className="view-rail" aria-label="サイドバー表示">
            <button
              className={leftMode === "algebra" ? "active" : ""}
              aria-pressed={leftMode === "algebra"}
              onClick={() => setLeftMode("algebra")}
            >
              <Shapes />
              <span>代数</span>
            </button>
            <button
              className={leftMode === "tools" ? "active" : ""}
              aria-pressed={leftMode === "tools"}
              onClick={() => setLeftMode("tools")}
            >
              <Wrench />
              <span>ツール</span>
            </button>
          </nav>
          <div className="left-view">
            {leftMode === "tools" ? (
              <>
                <div className="geogebra-view-heading">
                  <h1>ツール</h1>
                  <button
                    aria-label="すべてのV15ツールを開く"
                    onClick={() => openCatalog()}
                  >
                    <Plus />
                  </button>
                </div>
                <div className="tool-gallery" aria-label="GeoGebra型作図ツール">
                  {paletteGroups.map((group) => (
                    <section
                      key={group.id}
                      aria-labelledby={`tool-group-${group.id}`}
                    >
                      <h2 id={`tool-group-${group.id}`}>{group.label}</h2>
                      <div className="tool-grid">
                        {group.tools.map((item) => {
                          const active =
                            (item.action === "mode" && tool === item.value) ||
                            guided?.tool.id === item.value;
                          return (
                            <button
                              key={`${group.id}-${item.id}`}
                              className={active ? "active" : ""}
                              aria-pressed={active}
                              aria-label={`作図ツール ${item.label}`}
                              title={item.note ?? item.label}
                              onClick={() => activatePaletteTool(item)}
                            >
                              <PaletteGlyph id={item.id} />
                              <span>{item.label}</span>
                            </button>
                          );
                        })}
                      </div>
                    </section>
                  ))}
                  <button
                    className="more-tools"
                    onClick={() => setShowAllTools((value) => !value)}
                  >
                    {showAllTools ? "基本ツールだけ表示" : "その他のツール"}
                  </button>
                </div>
              </>
            ) : (
              <>
                <div className="geogebra-view-heading">
                  <h1>代数</h1>
                  <span>{problem.construction.length}</span>
                </div>
                <label className="search-field">
                  <MagnifyingGlass />
                  <input
                    aria-label="オブジェクトを検索"
                    placeholder="オブジェクトを検索"
                    value={objectSearch}
                    onChange={(event) => setObjectSearch(event.target.value)}
                  />
                </label>
                <div
                  className="sequence-list algebra-list"
                  role="tree"
                  aria-label="作図オブジェクト"
                >
                  {visibleObjects.map((item) => {
                    const isHidden = hidden.has(item.name);
                    const freedom = displayFreedom(item);
                    return (
                      <div
                        className={`sequence-row freedom-${freedom} ${selected === item.name ? "selected" : ""}`}
                        role="treeitem"
                        aria-selected={selected === item.name}
                        tabIndex={treeTabStop === item.name ? 0 : -1}
                        key={item.name}
                        onClick={() => chooseObject(item.name)}
                        onKeyDown={(event) => {
                          if (event.target !== event.currentTarget) return;
                          if (event.key === "Enter" || event.key === " ") {
                            event.preventDefault();
                            chooseObject(item.name);
                          } else if (
                            ["ArrowDown", "ArrowUp", "Home", "End"].includes(
                              event.key,
                            )
                          ) {
                            event.preventDefault();
                            const current = visibleObjects.findIndex(
                              (candidate) => candidate.name === item.name,
                            );
                            const nextIndex =
                              event.key === "Home"
                                ? 0
                                : event.key === "End"
                                  ? visibleObjects.length - 1
                                  : Math.max(
                                      0,
                                      Math.min(
                                        visibleObjects.length - 1,
                                        current +
                                          (event.key === "ArrowDown" ? 1 : -1),
                                      ),
                                    );
                            setSelected(visibleObjects[nextIndex]?.name || "");
                            window.setTimeout(
                              () =>
                                document
                                  .querySelectorAll<HTMLElement>(
                                    '[role="treeitem"]',
                                  )
                                  [nextIndex]?.focus(),
                              0,
                            );
                          }
                        }}
                      >
                        <button
                          className={`visibility freedom-${freedom}`}
                          aria-label={`${item.name}を${isHidden ? "表示" : "非表示"}`}
                          onClick={(event) => {
                            event.stopPropagation();
                            setHidden((current) => {
                              const next = new Set(current);
                              isHidden
                                ? next.delete(item.name)
                                : next.add(item.name);
                              return next;
                            });
                          }}
                        >
                          {isHidden ? <EyeSlash /> : <i aria-hidden="true" />}
                        </button>
                        <div className="object-id">
                          <strong>{item.name}</strong>
                          <span>{FREEDOM_LABEL[freedom]}</span>
                        </div>
                        <MathFormula
                          className="object-formula"
                          source={item.expr}
                          label={`${item.name}の定義: ${item.expr}`}
                        />
                        <button
                          className="object-more"
                          aria-label={`${item.name}の設定`}
                          onClick={(event) => {
                            event.stopPropagation();
                            setSelected(item.name);
                          }}
                        >
                          <DotsThreeVertical />
                        </button>
                      </div>
                    );
                  })}
                </div>
                {measurements.length > 0 && (
                  <section className="measurement-section" aria-label="測定値">
                    <div className="measurement-heading">
                      <h2>測定値</h2>
                      <span>{measurements.length}</span>
                    </div>
                    {measurements.map((measurement) => {
                      const value = evaluateScalarExpression(
                        measurement.expr,
                        scene,
                        variablePreview,
                      );
                      const display =
                        value === undefined
                          ? "—"
                          : /^\s*Angle\(/.test(measurement.expr)
                            ? `${((value * 180) / Math.PI).toFixed(2)}°`
                            : Number(value.toPrecision(8)).toString();
                      return (
                        <div className="measurement-row" key={measurement.name}>
                          <div>
                            <strong>{measurement.name}</strong>
                            <MathFormula
                              className="measurement-formula"
                              source={measurement.expr}
                              label={`${measurement.name}の定義: ${measurement.expr}`}
                            />
                          </div>
                          <output aria-label={`${measurement.name}の値`}>
                            {display}
                          </output>
                          <button
                            title="ターゲットに設定"
                            aria-label={`${measurement.name}をターゲットに設定`}
                            onClick={() => {
                              commit({ ...problem, answer: measurement.expr });
                              setCommand(measurement.expr);
                            }}
                          >
                            <Target />
                          </button>
                          <button
                            title="測定値を削除"
                            aria-label={`${measurement.name}を削除`}
                            onClick={() => {
                              setHistory((items) => [
                                ...items.slice(-79),
                                snapshot(),
                              ]);
                              setFuture([]);
                              setMeasurements((items) =>
                                items.filter(
                                  (item) => item.name !== measurement.name,
                                ),
                              );
                            }}
                          >
                            <X />
                          </button>
                        </div>
                      );
                    })}
                  </section>
                )}
                <section className="advanced-model" aria-label="条件と変数">
                  <div className="conditions-heading">
                    <span>条件と変数</span>
                    <strong>
                      {problem.constraints.length + problem.guards.length}
                    </strong>
                  </div>
                  <section className="model-section condition-section">
                    <h2>
                      条件{" "}
                      <span>
                        {problem.constraints.length + problem.guards.length}
                      </span>
                    </h2>
                    <p className="condition-help">
                      等式・不等式をまとめて表示します。内部形式の違いを意識せず、数式のまま編集できます。
                    </p>
                    {problem.constraints.length + problem.guards.length ===
                      0 && (
                      <p className="empty-condition">条件はありません。</p>
                    )}
                    {[
                      ...problem.constraints.map((constraint, index) => (
                      <ConditionEditorRow
                        key={`condition-${index + 1}`}
                        formula={constraintToFormula(constraint)}
                        conditionIndex={index + 1}
                        suggestions={expressionSuggestions}
                        normalizeDraft={(value) =>
                          formatConditionDraft(normalizeScalarInput(value, false))
                        }
                        mathKeyboardOpen={mathKeyboardOpen}
                        activeMathField={activeMathField}
                        registerMathTarget={registerMathTarget}
                        onCommit={(formula) => {
                          closeMathKeyboard(false);
                          commit(
                            replaceCondition(
                              problemRef.current,
                              "constraint",
                              index,
                              normalizeScalarInput(formula),
                            ),
                          );
                        }}
                        onDelete={() => {
                          closeMathKeyboard(false);
                          commit(
                            replaceCondition(
                              problemRef.current,
                              "constraint",
                              index,
                              "",
                            ),
                          );
                        }}
                      />
                      )),
                      ...problem.guards.map((guard, index) => {
                      const conditionIndex =
                        problem.constraints.length + index + 1;
                      return (
                        <ConditionEditorRow
                          key={`condition-${conditionIndex}`}
                          formula={guardToFormula(guard)}
                          conditionIndex={conditionIndex}
                          suggestions={expressionSuggestions}
                          normalizeDraft={(value) =>
                            formatConditionDraft(normalizeScalarInput(value, false))
                          }
                          mathKeyboardOpen={mathKeyboardOpen}
                          activeMathField={activeMathField}
                          registerMathTarget={registerMathTarget}
                          onCommit={(formula) => {
                            closeMathKeyboard(false);
                            commit(
                              replaceCondition(
                                problemRef.current,
                                "guard",
                                index,
                                normalizeScalarInput(formula),
                              ),
                            );
                          }}
                          onDelete={() => {
                            closeMathKeyboard(false);
                            commit(
                              replaceCondition(
                                problemRef.current,
                                "guard",
                                index,
                                "",
                              ),
                            );
                          }}
                        />
                      );
                      }),
                      ...(newConditionOpen
                        ? [<ConditionEditorRow
                        key={`condition-${problem.constraints.length + problem.guards.length + 1}`}
                        formula=""
                        conditionIndex={
                          problem.constraints.length + problem.guards.length + 1
                        }
                        suggestions={expressionSuggestions}
                        normalizeDraft={(value) =>
                          formatConditionDraft(normalizeScalarInput(value, false))
                        }
                        mathKeyboardOpen={mathKeyboardOpen}
                        activeMathField={activeMathField}
                        registerMathTarget={registerMathTarget}
                        onCommit={(formula) => {
                          const parsed = conditionFromFormula(
                            normalizeScalarInput(formula),
                          );
                          setNewConditionOpen(false);
                          if (!parsed) return;
                          commit({
                            ...problemRef.current,
                            constraints:
                              parsed.kind === "constraint"
                                ? [
                                    ...problemRef.current.constraints,
                                    parsed.value,
                                  ]
                                : problemRef.current.constraints,
                            guards:
                              parsed.kind === "guard"
                                ? [...problemRef.current.guards, parsed.value]
                                : problemRef.current.guards,
                          });
                        }}
                        onDelete={() => {
                          closeMathKeyboard(false);
                          setNewConditionOpen(false);
                        }}
                          />]
                        : []),
                    ]}
                    <button
                      className="text-action"
                      disabled={newConditionOpen}
                      onClick={() => setNewConditionOpen(true)}
                    >
                      <Plus />
                      条件を追加
                    </button>
                  </section>
                  <section className="model-section">
                    <h2>
                      変数 <span>{problem.variables.names.length}</span>
                    </h2>
                    {problem.variables.names.map((name, index) => (
                      <div className="guard-row variable-row" key={index}>
                        <input
                          aria-label={`変数 ${index + 1}`}
                          value={name}
                          readOnly
                        />
                      </div>
                    ))}
                  </section>
                </section>
              </>
            )}
          </div>
        </aside>
        <PaneResizeHandle
          orientation="vertical"
          label="左パネルの幅を変更"
          value={layoutSizes.left}
          minimum={250}
          maximum={leftPaneMaximum}
          valuePerPixel={1}
          defaultValue={DEFAULT_LAYOUT_SIZES.left}
          onChange={(left) =>
            setLayoutSizes((current) => ({ ...current, left }))
          }
        />
        <section
          className="center-stage"
          style={
            { "--bottom-pane-height": `${layoutSizes.bottom}px` } as CSSProperties
          }
        >
          <div
            className="canvas-toolbar geogebra-canvas-bar"
            aria-label="作図操作"
          >
            <div className="tool-group compact">
              <button
                aria-label="元に戻す"
                disabled={!history.length && !draftActive}
                onClick={undo}
              >
                <ArrowCounterClockwise />
              </button>
              <button
                aria-label="やり直す"
                disabled={!future.length && !draftActive}
                onClick={redo}
              >
                <ArrowClockwise />
              </button>
            </div>
            <strong>
              {guided?.tool.label_ja ??
                paletteGroups
                  .flatMap((group) => group.tools)
                  .find((item) => item.action === "mode" && item.value === tool)
                  ?.label ??
                "移動"}
            </strong>
            <div className="tool-group compact">
              <button
                className={grid ? "active" : ""}
                aria-label="グリッド"
                aria-pressed={grid}
                onClick={() => setGrid(!grid)}
              >
                <GridFour />
              </button>
              <button
                className={snap ? "active" : ""}
                aria-label="スナップ"
                aria-pressed={snap}
                onClick={() => setSnap(!snap)}
              >
                <Target />
              </button>
              <button aria-label="表示を移動" onClick={() => setMode("pan")}>
                <Hand />
              </button>
              <button
                aria-label="すべてのオブジェクトを表示"
                title="すべて表示"
                disabled={!hidden.size}
                onClick={() => setHidden(new Set())}
              >
                <Eye />
              </button>
              <button
                aria-label="図全体に表示を合わせる"
                title="全体表示"
                disabled={!scene.items.length}
                onClick={fitAllObjects}
              >
                <ArrowsOut />
              </button>
              <button
                className="clear-all-button"
                aria-label="すべて消去"
                title="すべて消去"
                disabled={
                  !problem.construction.length &&
                  !problem.variables.names.length &&
                  !problem.constraints.length &&
                  !problem.guards.length &&
                  !problem.answer &&
                  !problem.post_process &&
                  !measurements.length
                }
                onClick={clearAll}
              >
                <Trash />
              </button>
            </div>
          </div>
          <div className="tool-instruction">
            <span className="instruction-copy" role="status">
              {instruction}
              {!guided &&
              [
                "free-point",
                "fixed-point",
                "segment",
                "line",
                "circle",
                "polygon",
              ].includes(tool)
                ? ` · キーボード位置 x ${keyboardPoint.x.toFixed(1)}, y ${keyboardPoint.y.toFixed(1)}。矢印キーで移動、Enterで確定`
                : ""}
            </span>
            <div>
              {scene.warnings.length ? (
                <span>{scene.warnings.length}件は描画プレビュー対象外</span>
              ) : null}
              {(guided ||
                toolPoints.length > 0 ||
                !["select", "pan"].includes(tool)) && (
                <button
                  onClick={() => {
                    setGuided(undefined);
                    setToolPoints([]);
                    setPendingPoints([]);
                    setTool("select");
                    window.setTimeout(() => canvasRef.current?.focus(), 0);
                  }}
                >
                  作図を中止
                </button>
              )}
            </div>
          </div>
          <div className={`canvas-wrap mode-${tool}`}>
            <svg
              ref={canvasRef}
              className="geometry-canvas"
              viewBox={`0 0 ${CANVAS.width} ${CANVAS.height}`}
              role="application"
              tabIndex={0}
              aria-label="幾何作図キャンバス。作図中は矢印キーで配置位置を動かしEnterで確定。通常は矢印キーで表示移動、プラスとマイナスで拡大縮小"
              onPointerDown={canvasPointerDown}
              onPointerMove={pointerMove}
              onPointerUp={pointerUp}
              onPointerCancel={pointerUp}
              onPointerLeave={() => {
                if (!dragRef.current) setIntersectionHint(undefined);
              }}
              onKeyDown={canvasKeyDown}
              onWheel={(event: ReactWheelEvent<SVGSVGElement>) => {
                event.preventDefault();
                setCamera((value) => ({
                  ...value,
                  pixelsPerUnit: Math.max(
                    20,
                    Math.min(
                      180,
                      value.pixelsPerUnit * (event.deltaY < 0 ? 1.1 : 0.9),
                    ),
                  ),
                }));
              }}
            >
              <defs>
                <pattern
                  id="minor-grid"
                  width={camera.pixelsPerUnit / 2}
                  height={camera.pixelsPerUnit / 2}
                  patternUnits="userSpaceOnUse"
                >
                  <path
                    d={`M ${camera.pixelsPerUnit / 2} 0 L 0 0 0 ${camera.pixelsPerUnit / 2}`}
                  />
                </pattern>
              </defs>
              <rect
                className="canvas-hit"
                width={CANVAS.width}
                height={CANVAS.height}
                fill={grid ? "url(#minor-grid)" : "#fff"}
              />
              {(() => {
                const origin = worldToScreen({ x: 0, y: 0 }, viewport);
                return (
                  <g className="axes">
                    <line
                      x1="0"
                      y1={origin.y}
                      x2={CANVAS.width}
                      y2={origin.y}
                    />
                    <line
                      x1={origin.x}
                      y1="0"
                      x2={origin.x}
                      y2={CANVAS.height}
                    />
                  </g>
                );
              })()}
              {!guided &&
                [
                  "free-point",
                  "fixed-point",
                  "segment",
                  "line",
                  "circle",
                  "polygon",
                ].includes(tool) &&
                (() => {
                  const point = worldToScreen(keyboardPoint, viewport);
                  return (
                    <g className="keyboard-cursor" aria-hidden="true">
                      <circle cx={point.x} cy={point.y} r="9" />
                      <line
                        x1={point.x - 14}
                        y1={point.y}
                        x2={point.x + 14}
                        y2={point.y}
                      />
                      <line
                        x1={point.x}
                        y1={point.y - 14}
                        x2={point.x}
                        y2={point.y + 14}
                      />
                    </g>
                  );
                })()}
              {scene.items
                .filter((item) => item.kind !== "point")
                .map((item) => {
                  const construction = problem.construction.find(
                    (entry) => entry.name === item.name,
                  )!;
                  const slot = guided?.spec.slots[guided.names.length];
                  const candidate =
                    guided && slot
                      ? acceptsGuidedSelection(guided, item)
                      : undefined;
                  return (
                    <SceneShape
                      key={item.name}
                      item={item}
                      viewport={viewport}
                      hidden={hidden.has(item.name)}
                      freedom={displayFreedom(construction)}
                      objectStyle={objectStyles[item.name]}
                      labelPlacement={canvasLabels.get(item.name)}
                      guidedCandidate={candidate}
                      selected={
                        selected === item.name ||
                        !!guided?.names.includes(item.name)
                      }
                      onPointDown={pointPointerDown}
                      onPointMove={pointerMove}
                      onPointUp={pointerUp}
                      onPointClick={(event, name) => {
                        event.stopPropagation();
                        const keyboard =
                          event.detail === 0 &&
                          event.clientX === 0 &&
                          event.clientY === 0;
                        chooseObject(
                          name,
                          keyboard
                            ? undefined
                            : worldPointFromClient(
                                event.clientX,
                                event.clientY,
                                false,
                              ),
                        );
                      }}
                    />
                  );
                })}
              {intersectionHint &&
                (() => {
                  const point = worldToScreen(
                    intersectionHint.position,
                    viewport,
                  );
                  return (
                    <g className="intersection-snap" aria-hidden="true">
                      <circle
                        className="intersection-snap-halo"
                        cx={point.x}
                        cy={point.y}
                        r="10"
                      />
                      <circle cx={point.x} cy={point.y} r="3" />
                      <text x={point.x + 10} y={point.y - 9}>
                        交点
                      </text>
                    </g>
                  );
                })()}
              {pendingPoints.map((item) => {
                const point = worldToScreen(item.position, viewport);
                return (
                  <g
                    className="geometry-point freedom-free pending-point"
                    data-pending-point={item.name}
                    role="button"
                    tabIndex={0}
                    aria-label={`作図中の自由点 ${item.name}`}
                    key={item.name}
                    onClick={(event) => {
                      event.stopPropagation();
                      collectSimplePoint(item.name);
                    }}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        event.stopPropagation();
                        collectSimplePoint(item.name);
                      }
                    }}
                  >
                    <circle
                      className="point-hit"
                      cx={point.x}
                      cy={point.y}
                      r="12"
                      style={{ fill: "transparent", stroke: "transparent" }}
                    />
                    <circle cx={point.x} cy={point.y} r={DEFAULT_POINT_SIZE} />
                    <CanvasMathLabel
                      source={item.name}
                      placement={{
                        x: point.x + 8,
                        y: point.y - 31,
                        width: 60,
                        height: 26,
                      }}
                    />
                  </g>
                );
              })}
              {scene.items
                .filter((item) => item.kind === "point")
                .map((item) => {
                  const construction = problem.construction.find(
                    (entry) => entry.name === item.name,
                  )!;
                  const slot = guided?.spec.slots[guided.names.length];
                  const candidate =
                    guided && slot
                      ? acceptsGuidedSelection(guided, item)
                      : tool === "point-on-object"
                        ? false
                        : undefined;
                  return (
                    <SceneShape
                      key={item.name}
                      item={item}
                      viewport={viewport}
                      hidden={hidden.has(item.name)}
                      freedom={displayFreedom(construction)}
                      objectStyle={objectStyles[item.name]}
                      labelPlacement={canvasLabels.get(item.name)}
                      guidedCandidate={candidate}
                      selected={
                        selected === item.name ||
                        toolPoints.includes(item.name) ||
                        !!guided?.names.includes(item.name)
                      }
                      onPointDown={pointPointerDown}
                      onPointMove={pointerMove}
                      onPointUp={pointerUp}
                      onPointClick={(event, name) => {
                        event.stopPropagation();
                        chooseObject(
                          name,
                          event.detail === 0
                            ? undefined
                            : worldPointFromClient(
                                event.clientX,
                                event.clientY,
                                false,
                              ),
                        );
                      }}
                    />
                  );
                })}
              {showWitness &&
                witnessPoints.map((item) => {
                  const point = worldToScreen(item.position, viewport);
                  return (
                    <g className="witness-point" key={`witness-${item.name}`}>
                      <circle cx={point.x} cy={point.y} r="4" />
                      <CanvasMathLabel
                        source={`${item.name}′`}
                        tex={`${expressionToTex(item.name)}^{\\prime}`}
                        placement={{
                          x: point.x + 8,
                          y: point.y + 5,
                          width: 64,
                          height: 26,
                        }}
                      />
                    </g>
                  );
                })}
            </svg>
            <div className="zoom-controls">
              <button
                aria-label="拡大"
                onClick={() =>
                  setCamera((value) => ({
                    ...value,
                    pixelsPerUnit: Math.min(180, value.pixelsPerUnit * 1.2),
                  }))
                }
              >
                <Plus />
              </button>
              <button
                aria-label="縮小"
                onClick={() =>
                  setCamera((value) => ({
                    ...value,
                    pixelsPerUnit: Math.max(20, value.pixelsPerUnit / 1.2),
                  }))
                }
              >
                <Minus />
              </button>
              <button
                aria-label="表示を中央に戻す"
                onClick={() =>
                  setCamera({ center: { x: 0, y: 0 }, pixelsPerUnit: 65 })
                }
              >
                <Target />
              </button>
            </div>
          </div>
          <PaneResizeHandle
            orientation="horizontal"
            label="下部エディターの高さを変更"
            value={layoutSizes.bottom}
            minimum={150}
            maximum={420}
            valuePerPixel={-1}
            defaultValue={DEFAULT_LAYOUT_SIZES.bottom}
            onChange={(bottom) =>
              setLayoutSizes((current) => ({ ...current, bottom }))
            }
          />
          <div className="editor-panel">
            <div
              className="editor-tabs"
              role="tablist"
              aria-label="問題エディター"
              onKeyDown={(event) => {
                if (
                  !["ArrowLeft", "ArrowRight", "Home", "End"].includes(
                    event.key,
                  )
                )
                  return;
                event.preventDefault();
                const tabs: Array<typeof editorTab> = [
                  "command",
                  "json",
                  "details",
                ];
                const index = tabs.indexOf(editorTab);
                const next =
                  event.key === "Home"
                    ? tabs[0]
                    : event.key === "End"
                      ? tabs[2]
                      : tabs[
                          (index + (event.key === "ArrowRight" ? 1 : 2)) % 3
                        ];
                setEditorTab(next);
                window.setTimeout(
                  () =>
                    document
                      .querySelector<HTMLElement>(
                        `[role="tab"][aria-selected="true"]`,
                      )
                      ?.focus(),
                  0,
                );
              }}
            >
              <button
                id="tab-command"
                role="tab"
                aria-controls="panel-command"
                aria-selected={editorTab === "command"}
                tabIndex={editorTab === "command" ? 0 : -1}
                onClick={() => setEditorTab("command")}
              >
                ターゲット
              </button>
              <button
                id="tab-json"
                role="tab"
                aria-controls="panel-json"
                aria-selected={editorTab === "json"}
                tabIndex={editorTab === "json" ? 0 : -1}
                onClick={() => setEditorTab("json")}
              >
                V15 JSON
              </button>
              <button
                id="tab-details"
                role="tab"
                aria-controls="panel-details"
                aria-selected={editorTab === "details"}
                tabIndex={editorTab === "details" ? 0 : -1}
                onClick={() => setEditorTab("details")}
              >
                描画ログ
              </button>
            </div>
            {editorTab === "command" && (
              <div
                id="panel-command"
                role="tabpanel"
                aria-labelledby="tab-command"
                className="command-area"
              >
                <div className="formula-editor command-formula-editor">
                  <input
                  aria-label="ターゲット式"
                  aria-controls="math-keyboard"
                  aria-describedby={
                    mathKeyboardOpen && activeMathField === "editor-target"
                      ? "math-keyboard-status"
                      : undefined
                  }
                  data-math-field="editor-target"
                  value={command}
                  onFocus={(event) =>
                    registerMathTarget(event.currentTarget, setCommand)
                  }
                  onClick={(event) =>
                    registerMathTarget(event.currentTarget, setCommand)
                  }
                  onChange={(event) => setCommand(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter")
                      commit({
                        ...problem,
                        answer: normalizeScalarInput(command),
                      });
                  }}
                  />
                  <MathFormula
                    className="formula-preview"
                    source={command}
                    label="ターゲット式の数式表示"
                  />
                </div>
                <button
                  className="primary-action"
                  onClick={() =>
                    commit({
                      ...problem,
                      answer: normalizeScalarInput(command),
                    })
                  }
                >
                  <Target />
                  ターゲットに設定
                </button>
                <span>例: AB または Distance(A, B)</span>
              </div>
            )}
            {editorTab === "json" && (
              <div
                id="panel-json"
                role="tabpanel"
                aria-labelledby="tab-json"
                className="json-editor"
              >
                <textarea
                  aria-label="V15 JSON"
                  value={jsonDraft}
                  onChange={(event) => {
                    setJsonDraft(event.target.value);
                    setJsonDirty(true);
                  }}
                  spellCheck={false}
                />
                <button
                  className="primary-action"
                  disabled={!jsonDirty}
                  onClick={applyJson}
                >
                  JSONを適用
                </button>
              </div>
            )}
            {editorTab === "details" && (
              <div
                id="panel-details"
                role="tabpanel"
                aria-labelledby="tab-details"
                className="scene-log"
              >
                {scene.warnings.length ? (
                  scene.warnings.map((warning) => (
                    <p key={`${warning.name}-${warning.message}`}>
                      <strong>{warning.name}</strong> {warning.message}
                    </p>
                  ))
                ) : (
                  <p>すべての構成を描画できました。</p>
                )}
              </div>
            )}
          </div>
        </section>
        <PaneResizeHandle
          orientation="vertical"
          label="右パネルの幅を変更"
          value={layoutSizes.right}
          minimum={270}
          maximum={rightPaneMaximum}
          valuePerPixel={-1}
          defaultValue={DEFAULT_LAYOUT_SIZES.right}
          onChange={(right) =>
            setLayoutSizes((current) => ({ ...current, right }))
          }
        />
        <aside className="solver-pane" aria-label="プロパティとsolver">
          <section className="inspector-section property-inspector">
            <h2>設定</h2>
            {selectedConstruction ? (
              <div className="property-form">
                <div
                  className="property-tabs"
                  role="tablist"
                  aria-label="オブジェクト設定"
                  onKeyDown={(event) => {
                    if (
                      !["ArrowLeft", "ArrowRight", "Home", "End"].includes(
                        event.key,
                      )
                    )
                      return;
                    event.preventDefault();
                    const tabs: Array<typeof propertyTab> = [
                      "basic",
                      "style",
                      "advanced",
                    ];
                    const index = tabs.indexOf(propertyTab);
                    const next =
                      event.key === "Home"
                        ? tabs[0]
                        : event.key === "End"
                          ? tabs[2]
                          : tabs[
                              (index + (event.key === "ArrowRight" ? 1 : 2)) % 3
                            ];
                    setPropertyTab(next);
                    window.setTimeout(
                      () =>
                        document
                          .querySelector<HTMLElement>(`#property-tab-${next}`)
                          ?.focus(),
                      0,
                    );
                  }}
                >
                  <button
                    id="property-tab-basic"
                    role="tab"
                    aria-controls="property-panel-basic"
                    aria-selected={propertyTab === "basic"}
                    tabIndex={propertyTab === "basic" ? 0 : -1}
                    onClick={() => setPropertyTab("basic")}
                  >
                    基本
                  </button>
                  <button
                    id="property-tab-style"
                    role="tab"
                    aria-controls="property-panel-style"
                    aria-selected={propertyTab === "style"}
                    tabIndex={propertyTab === "style" ? 0 : -1}
                    onClick={() => setPropertyTab("style")}
                  >
                    スタイル
                  </button>
                  <button
                    id="property-tab-advanced"
                    role="tab"
                    aria-controls="property-panel-advanced"
                    aria-selected={propertyTab === "advanced"}
                    tabIndex={propertyTab === "advanced" ? 0 : -1}
                    onClick={() => setPropertyTab("advanced")}
                  >
                    詳細
                  </button>
                </div>
                {propertyTab === "basic" && (
                  <div
                    id="property-panel-basic"
                    role="tabpanel"
                    aria-labelledby="property-tab-basic"
                  >
                    <div
                      className={`freedom-badge freedom-${freedomOf(selectedConstruction, problem.variables.names)}`}
                    >
                      <i />
                      {
                        FREEDOM_LABEL[
                          freedomOf(
                            selectedConstruction,
                            problem.variables.names,
                          )
                        ]
                      }
                    </div>
                    <label>
                      名前
                      <input
                        key={`name-${selectedConstruction.name}`}
                        aria-label="名前"
                        defaultValue={selectedConstruction.name}
                        onBlur={(event) => {
                          if (!renameSelected(event.currentTarget.value))
                            event.currentTarget.value =
                              selectedConstruction.name;
                        }}
                        onKeyDown={(event) => {
                          if (event.key === "Enter") {
                            event.preventDefault();
                            if (!renameSelected(event.currentTarget.value))
                              event.currentTarget.value =
                                selectedConstruction.name;
                          }
                          if (event.key === "Escape") {
                            event.currentTarget.value =
                              selectedConstruction.name;
                            event.currentTarget.blur();
                          }
                        }}
                      />
                    </label>
                    <label>
                      定義
                      <ExpressionAutocomplete
                        key={`definition-${selectedConstruction.name}-${selectedConstruction.expr}`}
                        multiline
                        value={definitionDraft}
                        onChange={setDefinitionDraft}
                        suggestions={expressionSuggestions}
                        ariaLabel="定義"
                        ariaControls="math-keyboard"
                        ariaDescribedBy={
                          mathKeyboardOpen &&
                          activeMathField === "property-definition"
                            ? "math-keyboard-status"
                            : undefined
                        }
                        dataMathField="property-definition"
                        onEditorFocus={(editor) =>
                          registerMathTarget(editor, setDefinitionDraft)
                        }
                        onEditorClick={(editor) =>
                          registerMathTarget(editor, setDefinitionDraft)
                        }
                        onCommit={(value) => {
                          if (!updateSelectedDefinition(value))
                            setDefinitionDraft(selectedConstruction.expr);
                        }}
                        onEscape={() =>
                          setDefinitionDraft(selectedConstruction.expr)
                        }
                      />
                    </label>
                    <p className="property-kind">
                      名前はEnter、定義はCtrl+Enterでも確定できます。参照している式も名前変更に追従します。
                    </p>
                    <label className="checkbox-row">
                      <input
                        type="checkbox"
                        checked={!hidden.has(selectedConstruction.name)}
                        onChange={() =>
                          setHidden((current) => {
                            const next = new Set(current);
                            next.has(selectedConstruction.name)
                              ? next.delete(selectedConstruction.name)
                              : next.add(selectedConstruction.name);
                            return next;
                          })
                        }
                      />
                      オブジェクトを表示
                    </label>
                    {selectedDirectVariables && (
                      <fieldset className="preview-controls">
                        <legend>自由点の位置</legend>
                        {selectedDirectVariables.map((name, index) => (
                          <label key={name}>
                            {index === 0 ? "x" : "y"} <span>{name}</span>
                            <input
                              aria-label={`${selectedConstruction.name}の${index === 0 ? "x" : "y"}表示位置`}
                              type="number"
                              step="0.1"
                              value={variablePreview[name] ?? 0}
                              onChange={(event) =>
                                setVariablePreview((current) => ({
                                  ...current,
                                  [name]: Number(event.target.value),
                                }))
                              }
                            />
                          </label>
                        ))}
                      </fieldset>
                    )}
                    {selectedParameter && (
                      <fieldset className="preview-controls">
                        <legend>
                          {selectedParameter.operation === "PointOnAxis"
                            ? `${selectedParameter.axis}軸上の位置`
                            : "オブジェクト上の位置"}
                        </legend>
                        <label>
                          {selectedParameter.operation === "PointOnAxis"
                            ? selectedParameter.axis
                            : "t"}{" "}
                          <span>{selectedParameter.variable}</span>
                          <input
                            aria-label={`${selectedConstruction.name}のparameter表示値`}
                            type="number"
                            step="0.05"
                            min={
                              selectedParameter.operation === "PointOnSegment"
                                ? 0
                                : undefined
                            }
                            max={
                              selectedParameter.operation === "PointOnSegment"
                                ? 1
                                : undefined
                            }
                            value={
                              variablePreview[selectedParameter.variable] ?? 0
                            }
                            onChange={(event) => {
                              const raw = Number(event.target.value);
                              const value =
                                selectedParameter.operation === "PointOnSegment"
                                  ? Math.max(0, Math.min(1, raw))
                                  : raw;
                              setVariablePreview((current) => ({
                                ...current,
                                [selectedParameter.variable]: value,
                              }));
                            }}
                          />
                        </label>
                      </fieldset>
                    )}
                    <p className="property-kind">
                      位置はprojectに保存され、solverへ渡すV15定義は変えません。
                    </p>
                    {selectedSceneItem?.kind === "point" &&
                      (selectedDirectVariables ||
                        isFixedPointDefinition(selectedConstruction)) && (
                        <button
                          className="secondary-action"
                          onClick={toggleSelectedPointFreedom}
                        >
                          {selectedDirectVariables
                            ? "点を固定"
                            : "点を自由にする"}
                        </button>
                      )}
                    <button className="danger-action" onClick={removeSelected}>
                      <Trash />
                      削除
                    </button>
                  </div>
                )}
                {propertyTab === "style" && (
                  <div
                    id="property-panel-style"
                    className="style-controls"
                    role="tabpanel"
                    aria-labelledby="property-tab-style"
                  >
                    <label>
                      色
                      <input
                        aria-label="オブジェクトの色"
                        type="color"
                        value={
                          selectedStyle.color ??
                          (freedomOf(
                            selectedConstruction,
                            problem.variables.names,
                          ) === "free"
                            ? "#3459d9"
                            : "#667085")
                        }
                        onChange={(event) =>
                          updateSelectedStyle({ color: event.target.value })
                        }
                      />
                    </label>
                    {selectedSceneItem?.kind === "point" ? (
                      <label>
                        点のサイズ
                        <input
                          type="range"
                          min="1.5"
                          max={MAX_POINT_SIZE}
                          step="0.5"
                          value={renderedPointSize(selectedStyle)}
                          onChange={(event) =>
                            updateSelectedStyle({
                              pointSize: Number(event.target.value),
                            })
                          }
                        />
                      </label>
                    ) : (
                      <>
                        <label>
                          線の太さ
                          <input
                            type="range"
                            min="1"
                            max="5"
                            step="0.5"
                            value={selectedStyle.lineWidth ?? 1.5}
                            onChange={(event) =>
                              updateSelectedStyle({
                                lineWidth: Number(event.target.value),
                              })
                            }
                          />
                        </label>
                        <label>
                          線種
                          <select
                            value={selectedStyle.lineDash ?? "solid"}
                            onChange={(event) =>
                              updateSelectedStyle({
                                lineDash: event.target
                                  .value as ObjectStyle["lineDash"],
                              })
                            }
                          >
                            <option value="solid">実線</option>
                            <option value="dashed">破線</option>
                            <option value="dotted">点線</option>
                          </select>
                        </label>
                      </>
                    )}
                    <label>
                      ラベル
                      <select
                        value={selectedStyle.label ?? "name"}
                        onChange={(event) =>
                          updateSelectedStyle({
                            label: event.target.value as ObjectStyle["label"],
                          })
                        }
                      >
                        <option value="name">名前</option>
                        <option value="caption">キャプション</option>
                        <option value="hidden">非表示</option>
                      </select>
                    </label>
                    {selectedStyle.label === "caption" && (
                      <label>
                        キャプション
                        <input
                          value={selectedStyle.caption ?? ""}
                          onChange={(event) =>
                            updateSelectedStyle({ caption: event.target.value })
                          }
                        />
                      </label>
                    )}
                    <p className="property-kind">
                      スタイルはproject
                      metadataに保存され、solver入力は変えません。
                    </p>
                  </div>
                )}
                {propertyTab === "advanced" && (
                  <div
                    id="property-panel-advanced"
                    role="tabpanel"
                    aria-labelledby="property-tab-advanced"
                  >
                    <p className="property-kind">
                      V15定義は厳密なsource of truthです。高度な式編集はV15
                      JSONタブで行えます。
                    </p>
                    <MathFormula
                      className="advanced-definition"
                      source={selectedConstruction.expr}
                      display
                      label={`${selectedConstruction.name}のV15定義`}
                    />
                  </div>
                )}
              </div>
            ) : (
              <p className="muted">オブジェクトを選択すると設定できます。</p>
            )}
          </section>
          <section className="inspector-section">
            <h2>Solver</h2>
            <label className="solver-target-field">
              ターゲット
              <input
                aria-label="ターゲット"
                aria-controls="math-keyboard"
                aria-describedby={
                  mathKeyboardOpen && activeMathField === "solver-target"
                    ? "math-keyboard-status"
                    : undefined
                }
                data-math-field="solver-target"
                value={displayMathConstants(problem.answer)}
                onFocus={(event) =>
                  registerMathTarget(event.currentTarget, (value) =>
                    setProblem((current) => ({
                      ...current,
                      answer: normalizeScalarInput(value, false),
                    })),
                  )
                }
                onClick={(event) =>
                  registerMathTarget(event.currentTarget, (value) =>
                    setProblem((current) => ({
                      ...current,
                      answer: normalizeScalarInput(value, false),
                    })),
                  )
                }
                onChange={(event) =>
                  setProblem({
                    ...problem,
                    answer: normalizeScalarInput(event.target.value, false),
                  })
                }
                onBlur={(event) => {
                  const value = event.currentTarget.value;
                  setProblem((current) => ({
                    ...current,
                    answer: normalizeScalarInput(value),
                  }));
                }}
              />
              <MathFormula
                className="formula-preview solver-target-preview"
                source={displayMathConstants(problem.answer)}
                label="solverターゲットの数式表示"
              />
            </label>
            <div className="solver-profile-summary" aria-live="polite">
              <strong>
                {solverMode === "adaptive"
                  ? optimizedQualified
                    ? "適応実行"
                    : "適応実行（未認定候補）"
                  : solverMode === "fixed"
                    ? optimizedQualified
                      ? "固定時間"
                      : "固定時間（未認定候補）"
                    : "参照版"}
              </strong>
              <span>
                {solverMode === "reference"
                  ? "凍結版 · 180秒 · 1コア"
                  : `${maxTime}秒まで · ${cores === "auto" ? "コア自動" : `${cores}コア`}`}
              </span>
            </div>
            <div className="resource-grid adaptive-resource-grid">
              <label>
                上限時間 (秒)
                <input
                  type="number"
                  min={180}
                  max={900}
                  disabled={solverMode === "reference"}
                  value={solverMode === "reference" ? 180 : maxTime}
                  onChange={(event) => setMaxTime(Number(event.target.value))}
                  onBlur={() =>
                    setMaxTime((value) =>
                      Math.min(900, Math.max(180, Math.round(value || 900))),
                    )
                  }
                />
              </label>
              <label>
                使用コア
                <select
                  aria-label="使用コア"
                  disabled={solverMode === "reference"}
                  value={
                    solverMode === "reference"
                      ? "manual"
                      : cores === "auto"
                        ? "auto"
                        : "manual"
                  }
                  onChange={(event) =>
                    setCores(
                      event.target.value === "auto" ? "auto" : manualCores,
                    )
                  }
                >
                  <option value="auto">自動</option>
                  <option value="manual">手動</option>
                </select>
              </label>
              {(cores !== "auto" || solverMode === "reference") && (
                <label>
                  コア数
                  <input
                    type="number"
                    min={1}
                    disabled={solverMode === "reference"}
                    value={solverMode === "reference" ? 1 : manualCores}
                    onChange={(event) => {
                      const value = Number(event.target.value);
                      setManualCores(value);
                      setCores(value);
                    }}
                    onBlur={() => {
                      const value = Math.max(1, Math.round(manualCores || 1));
                      setManualCores(value);
                      setCores(value);
                    }}
                  />
                </label>
              )}
            </div>
            <details className="solver-advanced">
              <summary>詳細設定</summary>
              <fieldset>
                <legend>実行方式</legend>
                <label>
                  <input
                    type="radio"
                    name="solver-mode"
                    value="adaptive"
                    checked={solverMode === "adaptive"}
                    onChange={() => {
                      setSolverMode("adaptive");
                      setMaxTime(900);
                      setCores("auto");
                    }}
                  />
                  <span>
                    <strong>適応</strong>
                    {!optimizedQualified && "未認定候補・実験用。"}
                    解が安定した時点で早く終了します
                  </span>
                </label>
                <label>
                  <input
                    type="radio"
                    name="solver-mode"
                    value="fixed"
                    checked={solverMode === "fixed"}
                    onChange={() => {
                      setSolverMode("fixed");
                      setMaxTime(900);
                      setCores("auto");
                    }}
                  />
                  <span>
                    <strong>固定時間</strong>
                    {!optimizedQualified && "未認定候補・実験用。"}
                    指定した上限まで固定workを続けます
                  </span>
                </label>
                <label>
                  <input
                    type="radio"
                    name="solver-mode"
                    value="reference"
                    checked={solverMode === "reference"}
                    onChange={() => setSolverMode("reference")}
                  />
                  <span>
                    <strong>参照版</strong>
                    凍結済みの1コア・180秒実行です
                  </span>
                </label>
              </fieldset>
              <label className="seed-control">
                Seed
                <input
                  type="number"
                  value={seed}
                  onChange={(event) => setSeed(Number(event.target.value))}
                />
              </label>
            </details>
            <div className="validation-line">
              <button onClick={() => void validateCurrent()}>問題を検証</button>
              {validation && (
                <span className={validation.valid ? "ok" : "bad"}>
                  {validation.valid
                    ? validation.warnings?.length
                      ? `有効・${validation.warnings.length}件の警告`
                      : "有効"
                    : `${validation.issues.length}件の問題`}
                </span>
              )}
            </div>
            {validation && !validation.valid && (
              <ul className="validation-errors">
                {validation.issues.map((issue) => (
                  <li key={`${issue.path}-${issue.code}`}>
                    <code>{issue.path}</code> {issue.message}
                  </li>
                ))}
              </ul>
            )}
            {validation?.warnings && validation.warnings.length > 0 && (
              <ul className="validation-errors validation-warnings">
                {validation.warnings.map((warning) => (
                  <li key={`${warning.path}-${warning.code}`}>
                    <code>{warning.path}</code> {warning.message}
                  </li>
                ))}
              </ul>
            )}
          </section>
          <section className="inspector-section execution-section">
            <div className="execution-heading">
              <h2>実行</h2>
              <span aria-live="polite">
                {phase === "idle"
                  ? "待機中"
                  : `${runPhaseLabel(
                      ["done", "cancelled", "error"].includes(phase)
                        ? phase
                        : runProgress.phase,
                    )} · ${Math.round(Math.max(elapsed, runProgress.elapsedSeconds))}秒`}
              </span>
            </div>
            {phase !== "idle" && (
              <div className="run-progress" aria-label="solver進捗">
                <div className="run-progress-line">
                  <strong>{runPhaseLabel(runProgress.phase)}</strong>
                  <span>
                    {Math.round(
                      Math.max(elapsed, runProgress.elapsedSeconds),
                    )}
                    /{Math.round(runProgress.capSeconds)}秒
                  </span>
                </div>
                <progress
                  aria-label="経過時間"
                  max={Math.max(1, runProgress.capSeconds)}
                  value={Math.min(
                    runProgress.capSeconds,
                    Math.max(elapsed, runProgress.elapsedSeconds),
                  )}
                />
                <dl className="run-progress-grid">
                  <div>
                    <dt>完了starts</dt>
                    <dd>
                      {runProgress.completedStarts ?? "—"}
                      {runProgress.totalStarts !== undefined &&
                        ` / ${runProgress.totalStarts}`}
                    </dd>
                  </div>
                  <div>
                    <dt>追加batch</dt>
                    <dd>
                      {runProgress.batch !== undefined
                        ? `#${runProgress.batch}`
                        : "—"}
                    </dd>
                  </div>
                  <div>
                    <dt>安定回数</dt>
                    <dd>{runProgress.stabilityCount ?? "—"}</dd>
                  </div>
                  <div>
                    <dt>使用コア</dt>
                    <dd>{runProgress.usedCores ?? "自動調整中"}</dd>
                  </div>
                </dl>
                {runProgress.terminationReason && (
                  <p className="termination-line">
                    終了理由: {terminationLabel(runProgress.terminationReason)}
                  </p>
                )}
              </div>
            )}
            <div className="solve-actions">
              <button
                className="primary-action"
                disabled={running}
                onClick={() => void startSolve()}
              >
                <Play weight="fill" />
                解く
              </button>
              <button
                className="cancel-action"
                disabled={!running}
                onClick={() => void cancelSolve()}
              >
                <Stop />
                中止
              </button>
            </div>
          </section>
          <section className="inspector-section result-section">
            <div className="result-heading">
              <h2>厳密解</h2>
              {result && <span>{result.answers.length} answers</span>}
            </div>
            {!result ? (
              <div className="empty-result">まだ実行していません。</div>
            ) : (
              <>
                <div className={`result-status status-${result.status}`}>
                  {result.status}
                </div>
                {result.warnings.map((warning) => (
                  <p className="warning-strip" key={warning}>
                    {warning}
                  </p>
                ))}
                {result.answers.map((answer, index) => (
                  <article
                    className={`answer-card ${activeAnswer === index ? "active-answer" : ""}`}
                    key={`${answer.decimal}-${index}`}
                  >
                    <div className="answer-number">
                      <span>#{index + 1}</span>
                      <strong>
                        <MathFormula source={answer.decimal} label={`近似値 ${answer.decimal}`} />
                      </strong>
                      {answer.approximate_witness && (
                        <button
                          onClick={() => {
                            if (activeAnswer === index && showWitness)
                              setShowWitness(false);
                            else {
                              setActiveAnswer(index);
                              setShowWitness(true);
                            }
                          }}
                        >
                          {activeAnswer === index && showWitness
                            ? "表示を隠す"
                            : "作図に表示"}
                        </button>
                      )}
                    </div>
                    <dl>
                      <div>
                        <dt>最小多項式</dt>
                        <dd className="exact-formula">
                          <MathFormula
                            source={polynomialText(
                              answer.minimal_polynomial_high_to_low,
                            )}
                            tex={polynomialToTex(
                              answer.minimal_polynomial_high_to_low,
                            )}
                            label={`最小多項式 ${polynomialText(answer.minimal_polynomial_high_to_low)}`}
                          />
                        </dd>
                      </div>
                      <div>
                        <dt>実根 index</dt>
                        <dd>{answer.selected_real_root_index}</dd>
                      </div>
                      <div>
                        <dt>隔離区間</dt>
                        <dd className="exact-formula">
                          <MathFormula
                            source={`[${answer.isolating_interval.join(", ")}]`}
                            tex={`\\left[${answer.isolating_interval.join(",\\,")}\\right]`}
                            label={`隔離区間 ${answer.isolating_interval.join(" から ")}`}
                          />
                        </dd>
                      </div>
                      {answer.exact_authority_kind && (
                        <div>
                          <dt>Authority</dt>
                          <dd>{answer.exact_authority_kind}</dd>
                        </div>
                      )}
                    </dl>
                    {answer.approximate_witness && (
                      <details open={activeAnswer === index && showWitness}>
                        <summary>近似配置 (witness)</summary>
                        <pre>
                          {JSON.stringify(answer.approximate_witness, null, 2)}
                        </pre>
                      </details>
                    )}
                  </article>
                ))}
                <dl className="result-meta">
                  <div>
                    <dt>Engine</dt>
                    <dd>
                      {result.engine_id}
                      {result.engine_variant && ` · ${result.engine_variant}`}
                    </dd>
                  </div>
                  <div>
                    <dt>Hash</dt>
                    <dd>
                      <code>{result.engine_hash}</code>
                    </dd>
                  </div>
                  <div>
                    <dt>Problem SHA</dt>
                    <dd>
                      <code>{result.problem_sha256}</code>
                    </dd>
                  </div>
                  <div>
                    <dt>Elapsed</dt>
                    <dd>
                      {result.elapsed_seconds.toFixed(3)}秒 / {Math.round(
                        runProgress.capSeconds,
                      )}
                      秒
                    </dd>
                  </div>
                  <div>
                    <dt>完了starts</dt>
                    <dd>
                      {runProgress.completedStarts ?? "—"}
                      {runProgress.totalStarts !== undefined &&
                        ` / ${runProgress.totalStarts}`}
                    </dd>
                  </div>
                  <div>
                    <dt>追加batch / 安定回数</dt>
                    <dd>
                      {runProgress.batch !== undefined
                        ? `#${runProgress.batch}`
                        : "—"}
                      {" / "}
                      {runProgress.stabilityCount ?? "—"}
                    </dd>
                  </div>
                  <div>
                    <dt>使用コア</dt>
                    <dd>
                      {runProgress.usedCores ??
                        (typeof result.used_resources?.cores === "number"
                          ? result.used_resources.cores
                          : "—")}
                    </dd>
                  </div>
                  <div>
                    <dt>終了理由</dt>
                    <dd>
                      {terminationLabel(
                        result.termination_reason ??
                          runProgress.terminationReason,
                      )}
                    </dd>
                  </div>
                </dl>
              </>
            )}
          </section>
        </aside>
      </main>
      {mathKeyboardOpen && !catalogOpen && (
        <>
          <span
            id="math-keyboard-status"
            className="visually-hidden"
            role="status"
          >
            数式キーボード表示中
          </span>
          <MathKeyboard
            functions={mathFunctionNames}
            onInsert={insertMathText}
            onBackspace={mathBackspace}
            onMove={moveMathCaret}
            onEnter={confirmMathInput}
            onClose={closeMathKeyboard}
          />
        </>
      )}
      {uiError && (
        <div className="toast" role="alert">
          <span>{uiError}</span>
          <button aria-label="閉じる" onClick={() => setUiError("")}>
            <X />
          </button>
        </div>
      )}
      {catalogOpen && catalogTool && (
        <div
          className="dialog-backdrop"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) closeCatalog();
          }}
        >
          <section
            ref={dialogRef}
            className="tool-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="tool-title"
          >
            <header>
              <div>
                <span>V15 {catalog.version}</span>
                <h2 id="tool-title">作図・条件カタログ</h2>
              </div>
              <button aria-label="閉じる" onClick={closeCatalog}>
                <X />
              </button>
            </header>
            <label className="catalog-search">
              <MagnifyingGlass />
              <input
                ref={dialogInputRef}
                placeholder="ツールを検索"
                value={catalogSearch}
                onChange={(event) => setCatalogSearch(event.target.value)}
              />
            </label>
            <div className="catalog-body">
              <nav aria-label="DSLツール一覧">
                {catalog.categories.map((category) => (
                  <section key={category.id}>
                    <h3>{category.label_ja}</h3>
                    {filteredCatalog
                      .filter((item) => item.category === category.id)
                      .map((item) => (
                        <button
                          className={
                            catalogTool.id === item.id ? "selected" : ""
                          }
                          disabled={
                            item.authoring_status === "legacy_read_only"
                          }
                          onClick={() => {
                            setCatalogTool(item);
                            setGuidedChoices(
                              Object.fromEntries(
                                (guidedSpecFor(item.id)?.choices ?? []).map(
                                  (choice) => [
                                    choice.name,
                                    choice.defaultValue,
                                  ],
                                ),
                              ),
                            );
                            setNewExpression(guardFormulaForTool(item));
                            setNewName(
                              uniqueName(
                                [
                                  ...allNames(problem),
                                  ...measurements.map((entry) => entry.name),
                                ],
                                item.id.slice(0, 1).toLowerCase() || "o",
                              ),
                            );
                          }}
                          key={item.id}
                        >
                          <span>{item.label_ja}</span>
                          <code>
                            {toolOutput(item) === "guard"
                              ? (GUARD_TOOL_NOTATION[item.id] ?? item.label_ja)
                              : item.id}
                          </code>
                        </button>
                      ))}
                  </section>
                ))}
              </nav>
              <div className="tool-form">
                <span
                  className={`status-pill status-${catalogTool.authoring_status}`}
                >
                  {catalogTool.authoring_status === "legacy_read_only"
                    ? "読み取り専用"
                    : catalogTool.authoring_status === "advanced"
                      ? "上級"
                      : "作成可能"}
                </span>
                <h3>{catalogTool.label_ja}</h3>
                {catalogTool.notes_ja && <p>{catalogTool.notes_ja}</p>}
                {["construction", "measurement"].includes(
                  toolOutput(catalogTool),
                ) && (
                  <label>
                    オブジェクトID
                    <input
                      value={newName}
                      onChange={(event) => setNewName(event.target.value)}
                    />
                  </label>
                )}
                {(guidedSpecFor(catalogTool.id)?.choices ?? []).map(
                  (choice) => (
                    <label key={choice.name}>
                      {choice.label}
                      <select
                        aria-label={choice.label}
                        value={
                          guidedChoices[choice.name] ?? choice.defaultValue
                        }
                        onChange={(event) =>
                          setGuidedChoices((current) => ({
                            ...current,
                            [choice.name]: event.target.value,
                          }))
                        }
                      >
                        {choice.options.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </label>
                  ),
                )}
                <label>
                  {["guard", "constraint"].includes(toolOutput(catalogTool))
                    ? "条件式"
                    : "V15定義式"}
                  <ExpressionAutocomplete
                    multiline
                    className={
                      ["guard", "constraint"].includes(toolOutput(catalogTool))
                        ? "formula-input"
                        : undefined
                    }
                    ariaLabel={
                      ["guard", "constraint"].includes(toolOutput(catalogTool))
                        ? "条件式"
                        : "V15定義式"
                    }
                    ariaControls="math-keyboard"
                    ariaDescribedBy={
                      mathKeyboardOpen &&
                      activeMathField === "catalog-expression"
                        ? "math-keyboard-status"
                        : undefined
                    }
                    dataMathField="catalog-expression"
                    value={newExpression}
                    onChange={setNewExpression}
                    suggestions={expressionSuggestions}
                    onEditorFocus={(editor) =>
                      registerMathTarget(editor, setNewExpression)
                    }
                    onEditorClick={(editor) =>
                      registerMathTarget(editor, setNewExpression)
                    }
                  />
                </label>
                <div className="catalog-formula-preview">
                  <span>数式プレビュー</span>
                  <MathFormula
                    source={newExpression}
                    display
                    label="入力中の数式表示"
                  />
                </div>
                <div className="signature-hint">
                  <span>書式</span>
                  <MathFormula
                    source={
                      toolOutput(catalogTool) === "guard"
                        ? guardFormulaForTool(catalogTool)
                        : catalogTool.signature
                    }
                  />
                </div>
                {toolOutput(catalogTool) === "guard" && (
                  <p className="condition-help">
                    左辺と右辺を数式のまま入力できます。例: Angle(A, B, C) &lt;
                    π/2
                  </p>
                )}
                <div className="dialog-actions">
                  <button onClick={closeCatalog}>キャンセル</button>
                  {guidedSpecFor(catalogTool.id) && (
                    <button
                      className="guided-action"
                      onClick={startGuidedSelection}
                    >
                      図から引数を選ぶ
                    </button>
                  )}
                  <button
                    className="primary-action"
                    disabled={
                      catalogTool.authoring_status === "legacy_read_only"
                    }
                    onClick={addCatalogObject}
                  >
                    {["constraint", "guard"].includes(toolOutput(catalogTool))
                      ? "条件として追加"
                      : toolOutput(catalogTool) === "measurement"
                        ? "測定値に追加"
                        : "構成に追加"}
                  </button>
                </div>
              </div>
            </div>
            {mathKeyboardOpen && (
              <>
                <span
                  id="math-keyboard-status"
                  className="visually-hidden"
                  role="status"
                >
                  数式キーボード表示中
                </span>
                <MathKeyboard
                  functions={mathFunctionNames}
                  onInsert={insertMathText}
                  onBackspace={mathBackspace}
                  onMove={moveMathCaret}
                  onEnter={confirmMathInput}
                  onClose={closeMathKeyboard}
                />
              </>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
