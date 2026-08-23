import type { Vec2 } from "./geometry";
import type { GuidedSpec } from "./authoring";

export type Construction = { name: string; expr: string };
export type Constraint = { def: string; value: number | string };
export type Problem = {
  task: "solve";
  id: string;
  variables: { names: string[] };
  construction: Construction[];
  constraints: Constraint[];
  guards: string[];
  answer: string;
  post_process: string;
};

export type SolverMode = "adaptive" | "fixed" | "reference";

export type ValidationIssue = { path: string; code: string; message: string };
export type ValidationReport = {
  valid: boolean;
  issues: ValidationIssue[];
  warnings?: ValidationIssue[];
};

export type DslCategory = { id: string; label_ja: string; label_en: string };
export type DslTool = {
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

export type ToolMode =
  | "select"
  | "pan"
  | "free-point"
  | "fixed-point"
  | "point-on-object"
  | "segment"
  | "line"
  | "circle"
  | "polygon";

export type ObjectStyle = {
  color?: string;
  lineWidth?: number;
  pointSize?: number;
  lineDash?: "solid" | "dashed" | "dotted";
  label?: "name" | "caption" | "hidden";
  caption?: string;
};

export type ProjectEnvelope = {
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

export type Measurement = { name: string; expr: string };

export type HistoryState = {
  problem: Problem;
  variablePreview: Record<string, number>;
  objectStyles: Record<string, ObjectStyle>;
  hidden: string[];
  measurements: Measurement[];
};

export type GuidedSelection = {
  tool: DslTool;
  spec: GuidedSpec;
  names: string[];
  outputName: string;
  choices?: Record<string, string>;
  repeatable?: boolean;
};

export type PendingPoint = {
  name: string;
  variables: readonly [string, string];
  expression: string;
  position: Vec2;
};

export type PointNaming = {
  generatedName: string;
};

export type PaletteTool = {
  id: string;
  label: string;
  action: "mode" | "guided" | "catalog" | "hint";
  value: string;
  note?: string;
};
export type PaletteGroup = { id: string; label: string; tools: PaletteTool[] };

export type CanvasLabelPlacement = Readonly<{
  x: number;
  y: number;
  width: number;
  height: number;
}>;

export const FREEDOM_LABEL = {
  free: "自由",
  fixed: "固定",
  derived: "従属",
} as const;

export const CANVAS = { width: 1000, height: 700 };

export const INITIAL_PROBLEM: Problem = {
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

export const EMPTY_CATALOG: DslCatalog = {
  version: "V15",
  categories: [],
  tools: [],
};
