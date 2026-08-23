import {
  ArrowClockwise,
  ArrowCounterClockwise,
  ArrowsOut,
  CaretLeft,
  CaretRight,
  DotsNine,
  DotsThreeVertical,
  Eye,
  EyeSlash,
  GridFour,
  Hand,
  MagnifyingGlass,
  Minus,
  Plus,
  Shapes,
  Target,
  Trash,
  Wrench,
  X,
} from "@phosphor-icons/react";
import {
  CSSProperties,
  ChangeEvent,
  KeyboardEvent as ReactKeyboardEvent,
  PointerEvent as ReactPointerEvent,
  Suspense,
  WheelEvent as ReactWheelEvent,
  lazy,
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
import { MathFormula, expressionToTex } from "./MathFormula";
import {
  ExpressionAutocomplete,
  ExpressionSuggestion,
} from "./ExpressionAutocomplete";
import { MathKeyboard } from "./MathKeyboard";
import {
  ApiResult,
  RunProgress,
  SolverCores,
  useSolverJob,
} from "./useSolverJob";
import {
  DEFAULT_LAYOUT_SIZES,
  DESKTOP_MODEL_PANE_MIN_WIDTH,
  WIDE_WORKBENCH_MIN_WIDTH,
  useWorkbenchLayout,
} from "./useWorkbenchLayout";
import {
  CANVAS,
  EMPTY_CATALOG,
  FREEDOM_LABEL,
  GuidedSelection,
  HistoryState,
  INITIAL_PROBLEM,
  Measurement,
  ObjectStyle,
  PendingPoint,
  PointNaming,
  PaletteTool,
  Problem,
  ProjectEnvelope,
  SolverMode,
  ToolMode,
  ValidationReport,
  Construction,
  DslCatalog,
  DslTool,
} from "./types";
import {
  appendUiCondition,
  conditionFromFormula,
  constraintToFormula,
  displayMathConstants,
  expandDistanceShorthand,
  formatConditionDraft,
  guardToFormula,
  internalMathConstants,
  GUARD_TOOL_NOTATION,
  migrateLegacyUiEquationGuards,
  replaceCondition,
  withoutBlankExpressions,
} from "./mathFormat";
import {
  allNames,
  cloneProblem,
  completeVariablePreview,
  deletionClosure,
  isDslCatalog,
  isProblem,
  referencesIdentifier,
  replaceIdentifier,
  validIdentifier,
} from "./problemModel";
import {
  extractWitnessPoints,
  loadLastProject,
  PROJECT_FORMAT_VERSION,
  saveLastProject,
  validationIssueExpression,
  validationIssueLocation,
} from "./projectStore";
import {
  BASIC_PALETTE_GROUP,
  catalogPaletteGroups,
  guardFormulaForTool,
  PaletteGlyph,
  toolOutput,
} from "./palette";
import {
  canvasLabelLayout,
  CanvasMathLabel,
  DEFAULT_POINT_SIZE,
  MAX_POINT_SIZE,
  renderedPointSize,
  SceneShape,
} from "./canvasParts";
import { clamp, PaneResizeHandle } from "./chrome";
import { ConditionEditorRow } from "./components/ConditionEditorRow";
import { CanvasToolbar } from "./components/CanvasToolbar";
import { ToolInstruction } from "./components/ToolInstruction";
import { ZoomControls } from "./components/ZoomControls";
import { EditorTabs } from "./components/EditorTabs";
import { AppBar } from "./components/AppBar";
import { SolverExecutionDock } from "./components/SolverExecutionDock";
import {
  WorkflowStageNav,
  type WorkflowStage,
} from "./components/WorkflowStageNav";
import { SolverInstrumentRail } from "./components/SolverInstrumentRail";

const ExactResult = lazy(() => import("./ExactResult"));

export { catalogPaletteGroups };
export {
  conditionDraftIssue,
  conditionFromFormula,
  expandDistanceShorthand,
  formulaToGuard,
  guardToFormula,
  migrateLegacyUiEquationGuards,
  withoutBlankExpressions,
} from "./mathFormat";
export { validationIssueLocation } from "./projectStore";
export type { DslCatalog } from "./types";

const SKETCH_TOOL_IDS = [
  "Move",
  "Point",
  "Segment",
  "Line",
  "CircleThroughPoint",
  "Polygon",
] as const;

const SKETCH_TOOL_SHORTCUTS: Readonly<Record<string, string>> = {
  Move: "M",
  Point: "P",
  Segment: "S",
  Line: "L",
  Arc: "A",
  CircleThroughPoint: "C",
  CircleThroughThreePoints: "3",
  Polygon: "G",
  ParallelLine: "R",
  PerpendicularLine: "N",
  Reflect: "F",
  Angle: "Q",
  Distance: "D",
  Delete: "Del",
};

const CONSTRAINT_SHORTCUTS = [
  { id: "Parallel", label: "平行", key: "A" },
  { id: "Perpendicular", label: "垂直", key: "P" },
  { id: "IsTangent", label: "接する", key: "T" },
  { id: "Collinear", label: "共線", key: "C" },
  { id: "OnCircle", label: "円周上", key: "O" },
  { id: "Midpoint", label: "中点", key: "M" },
  { id: "AssumeEq", label: "等しい", key: "E" },
  { id: "AssumeNe", label: "異なる", key: "N" },
  { id: "AssumeLt", label: "未満", key: "<" },
  { id: "AssumeLe", label: "以下", key: "≤" },
  { id: "AssumeGt", label: "より大", key: ">" },
  { id: "AssumeGe", label: "以上", key: "≥" },
] as const;


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
  const [pointNaming, setPointNaming] = useState<PointNaming>();
  const [pointNameDraft, setPointNameDraft] = useState("");
  const [leftMode, setLeftMode] = useState<"algebra" | "tools">("algebra");
  const [workflowMode, setWorkflowMode] = useState<WorkflowStage>("draw");
  const [leftDeckOpen, setLeftDeckOpen] = useState(true);
  const [editorDockOpen, setEditorDockOpen] = useState(true);
  const [sourceDrawerOpen, setSourceDrawerOpen] = useState(false);
  const layout = useWorkbenchLayout();
  const layoutSizes = layout.sizes;
  const viewportWidth = layout.viewportWidth;
  const inspectorDrawerOpen = layout.drawerOpen;
  const setInspectorDrawerOpen = layout.setDrawerOpen;
  const [showAllTools, setShowAllTools] = useState(false);
  const [viewToolsOpen, setViewToolsOpen] = useState(false);
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
  const [camera, setCamera] = useState(() =>
    typeof window !== "undefined" && window.innerWidth < 768
      ? {
          center: { x: 2, y: 1.5 } as Vec2,
          pixelsPerUnit: 80,
        }
      : {
          center: { x: 0, y: 0 } as Vec2,
          pixelsPerUnit: 65,
        },
  );
  const [mobileFitRequested, setMobileFitRequested] = useState(
    () => typeof window !== "undefined" && window.innerWidth < 768,
  );
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
  const [guidedPointReady, setGuidedPointReady] = useState<string>();
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
  const [uiNotice, setUiNotice] = useState("");
  const [validation, setValidation] = useState<ValidationReport>();
  const [doctor, setDoctor] = useState<{
    ok: boolean;
    checks?: unknown;
    errors?: unknown[];
  }>();
  // Start fail-closed, then apply the backend qualification policy atomically.
  const [solverMode, setSolverMode] = useState<SolverMode>("reference");
  const [optimizedQualified, setOptimizedQualified] = useState(false);
  const [maxTime, setMaxTime] = useState(180);
  const [cores, setCores] = useState<SolverCores>(1);
  const [manualCores, setManualCores] = useState(1);
  const [seed, setSeed] = useState(0);
  const solverJob = useSolverJob(setUiError);
  const phase = solverJob.phase;
  const runProgress: RunProgress = solverJob.progress;
  const result: ApiResult | undefined = solverJob.result;
  const [activeAnswer, setActiveAnswer] = useState(0);
  const importRef = useRef<HTMLInputElement>(null);
  const dialogInputRef = useRef<HTMLInputElement>(null);
  const pointNameInputRef = useRef<HTMLInputElement>(null);
  const mathTargetRef = useRef<HTMLInputElement | HTMLTextAreaElement | null>(
    null,
  );
  const mathSetterRef = useRef<(value: string) => void>(() => undefined);
  const suppressMathFocusRef = useRef(false);
  const canvasRef = useRef<SVGSVGElement>(null);
  const problemRef = useRef(problem);
  const dialogRef = useRef<HTMLElement | null>(null);
  const dialogTriggerRef = useRef<HTMLElement | null>(null);
  const sourceDrawerRef = useRef<HTMLDivElement | null>(null);
  const sourceDrawerTriggerRef = useRef<HTMLButtonElement | null>(null);
  const inspectorDrawerRef = useRef<HTMLElement | null>(null);
  const inspectorDrawerTriggerRef = useRef<HTMLButtonElement | null>(null);
  const inspectorScrollBodyRef = useRef<HTMLDivElement | null>(null);
  const modelPaneRef = useRef<HTMLElement | null>(null);
  const mobileModelTriggerRef = useRef<HTMLButtonElement | null>(null);
  const viewToolsRef = useRef<HTMLDivElement | null>(null);
  const viewToolsTriggerRef = useRef<HTMLButtonElement | null>(null);
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

  const leftPaneMaximum =
    viewportWidth >= WIDE_WORKBENCH_MIN_WIDTH
      ? clamp(viewportWidth - layoutSizes.right - 14 - 280, 250, 520)
      : 520;
  const rightPaneMaximum =
    viewportWidth >= WIDE_WORKBENCH_MIN_WIDTH
      ? clamp(viewportWidth - layoutSizes.left - 14 - 280, 270, 520)
      : 520;
  const inspectorIsDrawer = true;

  useEffect(() => {
    if (viewportWidth < WIDE_WORKBENCH_MIN_WIDTH) {
      setEditorDockOpen(false);
    }
    if (viewportWidth < DESKTOP_MODEL_PANE_MIN_WIDTH) {
      setLeftDeckOpen(false);
    }
  }, [viewportWidth]);

  useEffect(() => {
    if (!inspectorIsDrawer || !inspectorDrawerOpen) return;
    const drawer = inspectorDrawerRef.current;
    const focusable = () =>
      drawer
        ? [
            ...drawer.querySelectorAll<HTMLElement>(
              'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex="0"]',
            ),
          ]
        : [];
    focusable()[0]?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.defaultPrevented) return;
      if (event.key === "Escape") {
        event.preventDefault();
        setInspectorDrawerOpen(false);
        window.setTimeout(
          () => inspectorDrawerTriggerRef.current?.focus(),
          0,
        );
        return;
      }
      if (event.key !== "Tab") return;
      const items = focusable();
      if (!items.length) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [inspectorDrawerOpen, inspectorIsDrawer]);

  useEffect(() => {
    if (!sourceDrawerOpen) return;
    const drawer = sourceDrawerRef.current;
    const inertTargets = [
      document.querySelector<HTMLElement>(".app-bar"),
      document.querySelector<HTMLElement>(".model-pane"),
      ...(drawer?.parentElement
        ? [...drawer.parentElement.children]
            .filter((element) => element !== drawer)
            .filter((element): element is HTMLElement => element instanceof HTMLElement)
        : []),
    ].filter((element): element is HTMLElement => !!element);
    const priorInert = inertTargets.map(
      (element) => [element, element.hasAttribute("inert")] as const,
    );
    inertTargets.forEach((element) => {
      element.inert = true;
      element.setAttribute("inert", "");
    });
    const focusable = () =>
      drawer
        ? [
            ...drawer.querySelectorAll<HTMLElement>(
              'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex="0"]',
            ),
          ]
        : [];
    focusable()[0]?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.defaultPrevented) return;
      if (event.key === "Escape") {
        event.preventDefault();
        setSourceDrawerOpen(false);
        return;
      }
      if (event.key !== "Tab") return;
      const items = focusable();
      if (!items.length) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      priorInert.forEach(([element, wasInert]) => {
        element.inert = wasInert;
        if (!wasInert) element.removeAttribute("inert");
      });
      if (drawer?.contains(document.activeElement)) {
        sourceDrawerTriggerRef.current?.focus();
      }
    };
  }, [sourceDrawerOpen]);

  useEffect(() => {
    if (!viewToolsOpen) return;
    const onPointerDown = (event: PointerEvent) => {
      if (!viewToolsRef.current?.contains(event.target as Node)) {
        setViewToolsOpen(false);
      }
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      setViewToolsOpen(false);
      viewToolsTriggerRef.current?.focus();
    };
    window.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("pointerdown", onPointerDown);
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [viewToolsOpen]);

  useEffect(() => {
    if (viewportWidth >= 768 || !leftDeckOpen) return;
    const pane = modelPaneRef.current;
    const focusable = () =>
      pane
        ? [
            ...pane.querySelectorAll<HTMLElement>(
              'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex="0"]',
            ),
          ]
        : [];
    focusable()[0]?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopImmediatePropagation();
        setLeftDeckOpen(false);
        mobileModelTriggerRef.current?.focus();
        return;
      }
      if (event.key !== "Tab") return;
      const items = focusable();
      if (!items.length) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [leftDeckOpen, viewportWidth]);

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
  useEffect(() => {
    if (viewportWidth < 768) setMobileFitRequested(true);
  }, [viewportWidth]);
  useEffect(() => {
    if (!mobileFitRequested || viewportWidth >= 768 || !scene.items.length)
      return;
    fitAllObjects();
    setMobileFitRequested(false);
  }, [hidden, mobileFitRequested, scene.items, viewportWidth]);
  useEffect(() => {
    if (!guidedPointReady || !scene.byName.has(guidedPointReady)) return;
    setGuidedPointReady(undefined);
    chooseObject(guidedPointReady);
  }, [guidedPointReady, scene]);
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
        new Set([selected, ...toolPoints, ...(guided?.names ?? [])]),
      ),
    [
      scene.items,
      camera.center.x,
      camera.center.y,
      camera.pixelsPerUnit,
      hidden,
      objectStyles,
      selected,
      toolPoints,
      guided?.names,
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
  const allPaletteTools = useMemo(() => {
    const tools = [
      ...BASIC_PALETTE_GROUP.tools,
      ...catalogPaletteGroups(catalog).flatMap((group) => group.tools),
    ];
    return new Map(tools.map((item) => [item.id, item]));
  }, [catalog]);
  const sketchTools = useMemo(
    () =>
      showAllTools
        ? paletteGroups.flatMap((group) => group.tools)
        : SKETCH_TOOL_IDS.map((id) => allPaletteTools.get(id)).filter(
            (item): item is PaletteTool => !!item,
          ),
    [allPaletteTools, paletteGroups, showAllTools],
  );
  const constraintTools = useMemo(
    () =>
      CONSTRAINT_SHORTCUTS.map((shortcut) => ({
        ...shortcut,
        tool: allPaletteTools.get(shortcut.id),
      })),
    [allPaletteTools],
  );
  useEffect(() => {
    const activateShortcut = (event: KeyboardEvent) => {
      if (
        event.defaultPrevented ||
        event.altKey ||
        event.ctrlKey ||
        event.metaKey ||
        catalogOpen ||
        sourceDrawerOpen ||
        inspectorDrawerOpen
      )
        return;
      const target = event.target;
      if (
        target instanceof HTMLInputElement ||
        target instanceof HTMLTextAreaElement ||
        target instanceof HTMLSelectElement ||
        (target instanceof HTMLElement && target.isContentEditable)
      )
        return;
      const key = event.key.toUpperCase();
      const toolId = Object.entries(SKETCH_TOOL_SHORTCUTS).find(
        ([, shortcut]) => shortcut === key,
      )?.[0];
      if (!toolId) return;
      const shortcutTool = allPaletteTools.get(toolId);
      if (!shortcutTool) return;
      event.preventDefault();
      setWorkflowMode("draw");
      activatePaletteTool(shortcutTool);
      window.setTimeout(() => canvasRef.current?.focus(), 0);
    };
    window.addEventListener("keydown", activateShortcut);
    return () => window.removeEventListener("keydown", activateShortcut);
  }, [allPaletteTools, catalogOpen, inspectorDrawerOpen, sourceDrawerOpen]);
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
      if (window.innerWidth < 768) setMobileFitRequested(true);
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
    solverJob.clearResult();
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
  function beginPointNaming(generatedName: string) {
    setObjectStyles((current) => ({
      ...current,
      [generatedName]: {
        ...current[generatedName],
        label: "hidden",
      },
    }));
    setPointNameDraft("");
    setPointNaming({ generatedName });
    window.setTimeout(() => pointNameInputRef.current?.focus(), 0);
  }
  function finishPointNaming() {
    if (!pointNaming) return;
    const previousName = pointNaming.generatedName;
    const nextName = pointNameDraft.trim();
    if (!nextName) {
      setPointNaming(undefined);
      window.setTimeout(() => canvasRef.current?.focus(), 0);
      return;
    }
    if (!validIdentifier(nextName)) {
      setUiError("名前は英字または_で始め、英数字と_だけを使ってください");
      return;
    }
    if (
      allNames(problem).some(
        (name) => name !== previousName && name === nextName,
      ) ||
      measurements.some((item) => item.name === nextName)
    ) {
      setUiError(`${nextName} は既に使われています`);
      return;
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
    problemRef.current = next;
    setProblem(next);
    setMeasurements((items) =>
      items.map((item) => ({ ...item, expr: replace(item.expr) })),
    );
    setObjectStyles((current) => {
      const styles = {
        ...current,
        [nextName]: { ...current[previousName], label: "name" as const },
      };
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
    setToolPoints((current) =>
      current.map((name) => (name === previousName ? nextName : name)),
    );
    setPendingPoints((current) =>
      current.map((item) =>
        item.name === previousName
          ? { ...item, name: nextName }
          : item,
      ),
    );
    setSelected(nextName);
    setJsonDirty(false);
    setUiError("");
    setPointNaming(undefined);
    window.setTimeout(() => canvasRef.current?.focus(), 0);
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
    // Browser fallback for the responsive SVG viewBox transform.
    const scale =
      viewportWidth < 768
        ? Math.max(box.width / CANVAS.width, box.height / CANVAS.height)
        : Math.min(box.width / CANVAS.width, box.height / CANVAS.height);
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
    beginPointNaming(name);
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
  ): string | undefined {
    const placement = axisPlacementNear(hitPoint);
    if (!placement) return undefined;
    if (placement === "origin") {
      const existing = scene.items.find(
        (item) =>
          item.kind === "point" &&
          Math.hypot(item.position.x, item.position.y) < 1e-10,
      );
      if (existing) {
        setSelected(existing.name);
        return existing.name;
      }
      return addPointAt({ x: 0, y: 0 }, "fixed");
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
    beginPointNaming(name);
    return name;
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
    beginPointNaming(draft.name);
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
    if (carrier.kind === "segment" || carrier.kind === "vector")
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
  function addPointOnObject(name: string, point: Vec2): string | undefined {
    const item = scene.byName.get(name);
    const construction = problem.construction.find(
      (entry) => entry.name === name,
    );
    if (!item || !construction) return undefined;
    const outputName = uniqueName(allNames(problem), "P");
    const variable = uniqueIdentifier(allNames(problem), `t${outputName}`);
    let expression: string | undefined;
    const addedGuards: string[] = [];
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
        addedGuards.push(`Bound(${variable}, (0, 1))`);
      }
    } else if (item.kind === "ray") {
      const endpoints = endpointNames(name, "Ray");
      if (endpoints) {
        expression = `PointOnLine(Line(${endpoints[0]}, ${endpoints[1]}), ${variable})`;
        addedGuards.push(
          `AssumeGe(Dot(Vector(${endpoints[0]}, ${outputName}), Vector(${endpoints[0]}, ${endpoints[1]})), 0)`,
        );
      }
    } else if (item.kind === "vector") {
      const endpoints =
        /^\s*Vector\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*,\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)\s*$/.exec(
          construction.expr,
        );
      if (endpoints) {
        expression = `PointOnSegment(${endpoints[1]}, ${endpoints[2]}, ${variable})`;
        addedGuards.push(`Bound(${variable}, (0, 1))`);
      }
    }
    const parameter = parameterAt(item, point);
    if (!expression || parameter === undefined) {
      setUiError("点は直線・線分・円の上に配置できます");
      return undefined;
    }
    const next = {
      ...problem,
      variables: { names: [...problem.variables.names, variable] },
      construction: [
        ...problem.construction,
        { name: outputName, expr: expression },
      ],
      guards: [...problem.guards, ...addedGuards],
    };
    commit(next, {
      ...completeVariablePreview(next, variablePreview),
      [variable]: parameter,
    });
    setSelected(outputName);
    beginPointNaming(outputName);
    return outputName;
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
    beginPointNaming(outputName);
    setIntersectionHint(undefined);
    return outputName;
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
  ): string | undefined {
    const first = scene.byName.get(candidate.first);
    const second = scene.byName.get(candidate.second);
    if (!first || !second) {
      setUiError("交点を構成する図形を確認できません");
      return undefined;
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
      return undefined;
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
      return undefined;
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
    beginPointNaming(outputName);
    setIntersectionHint(undefined);
    return outputName;
  }
  function createIntersection(candidate: IntersectionCandidate): string | undefined {
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
      return exactExisting.name;
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
      return addIntersection(candidate, `exclude=${shared}`);
    }
    if (shared) return addRelationalIntersection(candidate, shared);
    if (candidate.alternatives.length <= 1 && !finiteCarrier) {
      return addIntersection(candidate);
    }
    return addRelationalIntersection(candidate);
  }
  function createIntersectionNear(point: Vec2): string | undefined {
    const candidate = intersectionNear(point);
    return candidate ? createIntersection(candidate) : undefined;
  }

  function collectSmartPointAt(
    hitPoint: Vec2,
    placementPoint = hitPoint,
    carrierName?: string,
  ) {
    const existing = scene.items.find(
      (item) =>
        item.kind === "point" &&
        Math.hypot(
          item.position.x - hitPoint.x,
          item.position.y - hitPoint.y,
        ) <=
          8 / camera.pixelsPerUnit,
    );
    if (existing) {
      collectSimplePoint(existing.name);
      return;
    }
    const created =
      createIntersectionNear(hitPoint) ??
      (!carrierName
        ? createAxisPointNear(hitPoint, placementPoint)
        : undefined) ??
      (carrierName
        ? addPointOnObject(carrierName, placementPoint)
        : addPointAt(placementPoint, "free"));
    if (created) collectSimplePoint(created);
  }
  function acceptsGuidedSelection(
    selection: GuidedSelection,
    item: SceneItem,
  ): boolean {
    const slot = selection.spec.slots[selection.names.length];
    if (!slot) return false;
    if (
      slot.kind === "point" &&
      ["line", "segment", "ray", "vector", "circle"].includes(item.kind)
    )
      return true;
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
    setWorkflowMode("constrain");
    return true;
  }
  function addInscribedPolygon(
    circleName: string,
    vertexCount: number,
    polygonName: string,
  ): boolean {
    const circle = scene.byName.get(circleName);
    if (circle?.kind !== "circle") {
      setUiError("円に内接する多角形には円を選択してください");
      return false;
    }
    if (!Number.isInteger(vertexCount) || vertexCount < 3) {
      setUiError("頂点数は3以上の整数にしてください");
      return false;
    }
    const reserved = new Set(allNames(problem));
    reserved.add(polygonName);
    const vertices: string[] = [];
    const variables: string[] = [];
    const constructions: Construction[] = [];
    const preview: Record<string, number> = {};
    for (let index = 0; index < vertexCount; index += 1) {
      const vertex = uniqueName(reserved, "P");
      reserved.add(vertex);
      vertices.push(vertex);
      if (index === 0) {
        constructions.push({
          name: vertex,
          expr: `PointOnCircle(${circleName}, 0.25)`,
        });
        continue;
      }
      const parameter = uniqueIdentifier(reserved, `t${vertex}`);
      reserved.add(parameter);
      variables.push(parameter);
      preview[parameter] = (0.25 + index / vertexCount) % 1;
      constructions.push({
        name: vertex,
        expr: `PointOnCircle(${circleName}, ${parameter})`,
      });
    }
    const next: Problem = {
      ...problem,
      variables: { names: [...problem.variables.names, ...variables] },
      construction: [
        ...problem.construction,
        ...constructions,
        { name: polygonName, expr: `Polygon([${vertices.join(", ")}])` },
      ],
    };
    const dryScene = evaluateScene(next.construction, {
      ...completeVariablePreview(next, variablePreview),
      ...preview,
    });
    if (!dryScene.byName.has(polygonName)) {
      setUiError("選択した円から内接多角形を作図できませんでした");
      return false;
    }
    commit(next, {
      ...completeVariablePreview(next, variablePreview),
      ...preview,
    });
    setObjectStyles((current) => ({
      ...current,
      ...Object.fromEntries(
        vertices.map((name) => [
          name,
          { ...current[name], label: "hidden" as const },
        ]),
      ),
    }));
    setSelected(polygonName);
    return true;
  }
  function revealConditions() {
    setLeftMode("algebra");
    setWorkflowMode("constrain");
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
      if (
        item &&
        slot?.kind === "point" &&
        item.kind !== "point" &&
        point
      ) {
        const created =
          createIntersectionNear(point) ?? addPointOnObject(name, point);
        if (created) setGuidedPointReady(created);
        return;
      }
      if (!item || !slot || !acceptsGuidedSelection(guided, item)) {
        setUiError(
          `${slot?.label ?? "引数"}には${guided.tool.id === "PointOnLine" ? "直線" : slot?.kind === "line" ? "直線・線分・半直線・ベクトル" : slot?.kind === "line-or-circle" ? "直線・線分・半直線・ベクトル・円" : slot?.kind === "point-or-line" ? "点・直線・線分・半直線・ベクトル" : slot?.kind === "segment" ? "線分" : slot?.kind === "point" ? "点" : "対応するオブジェクト"}を選択してください`,
        );
        return;
      }
      const names = [...guided.names, name];
      if (names.length === guided.spec.slots.length) {
        if (guided.tool.id === "InscribedPolygonVertices") {
          const vertexCount = Number(guided.choices?.n ?? "3");
          if (!addInscribedPolygon(names[0], vertexCount, guided.outputName))
            return;
          setGuided(undefined);
          setTool("select");
          return;
        }
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
    if (["segment", "line", "circle", "polygon"].includes(tool)) {
      if (sceneItem?.kind === "point") collectSimplePoint(name);
      else if (sceneItem && point)
        collectSmartPointAt(point, point, sceneItem.name);
    }
  }
  function canvasPointerDown(event: ReactPointerEvent<SVGSVGElement>) {
    if (event.button !== 0) return;
    if ((event.target as Element).closest("[data-object]")) return;
    const guidedSlot = guided?.spec.slots[guided.names.length];
    if (guided && guidedSlot?.kind === "point") {
      const hitPoint = worldPointFromClient(
        event.clientX,
        event.clientY,
        false,
      );
      const placementPoint = worldPointFromClient(event.clientX, event.clientY);
      const created =
        createIntersectionNear(hitPoint) ??
        createAxisPointNear(hitPoint, placementPoint) ??
        addPointAt(placementPoint, "free");
      if (created) setGuidedPointReady(created);
      return;
    }
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
      const hitPoint = worldPointFromClient(
        event.clientX,
        event.clientY,
        false,
      );
      const placementPoint = worldPointFromClient(event.clientX, event.clientY);
      const created =
        createIntersectionNear(hitPoint) ??
        createAxisPointNear(hitPoint, placementPoint);
      if (created) collectSimplePoint(created);
      else collectBlankPoint(placementPoint);
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
    setWorkflowMode("draw");
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
    setUiError("");
    await solverJob.start({
      problem: prepared,
      options,
      capSeconds: requestedMaxTime,
      usedCores:
        typeof requestedCores === "number" ? requestedCores : undefined,
      validate: async () => Boolean((await validateCurrent(prepared))?.valid),
      isCurrentProblem: () =>
        JSON.stringify(withoutBlankExpressions(problemRef.current)) ===
        submittedProblem,
    });
  }
  async function cancelSolve() {
    await solverJob.cancel();
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
  function download(value: unknown, suffix: string, label: string) {
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }),
    );
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${problem.id}${suffix}`;
    anchor.hidden = true;
    document.body.append(anchor);
    anchor.click();
    window.setTimeout(() => {
      anchor.remove();
      URL.revokeObjectURL(url);
    }, 1_000);
    setUiNotice(`${label}を書き出しました · ${anchor.download}`);
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
    const horizontalBudget =
      viewportWidth < 768
        ? Math.max(240, viewportWidth - 72)
        : CANVAS.width - 120;
    setCamera({
      center: { x: (minX + maxX) / 2, y: (minY + maxY) / 2 },
      pixelsPerUnit: Math.max(
        20,
        Math.min(
          180,
          horizontalBudget / width,
          (CANVAS.height - 120) / height,
        ),
      ),
    });
  }
  const running = [
    "submitting",
    "queued",
    "running",
    "cancelling",
    "watchdog",
  ].includes(phase);
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
  const activeToolLabel =
    guided?.tool.label_ja ??
    paletteGroups
      .flatMap((group) => group.tools)
      .find((item) => item.action === "mode" && item.value === tool)?.label ??
    "移動";

  return (
    <div
      className="app-shell"
      style={
        {
          "--left-pane-width": `${layoutSizes.left}px`,
          "--right-pane-width": `${layoutSizes.right}px`,
          "--bottom-pane-height": `${layoutSizes.bottom}px`,
        } as CSSProperties
      }
    >
      <AppBar
        projectName={`${problem.id}.geotarget.json`}
        modalOpen={catalogOpen}
        importRef={importRef}
        onImport={importProject}
        onExportProject={() =>
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
            "プロジェクト",
          )
        }
        onExportJson={() => download(problem, ".json", "V15 JSON")}
        sourceTriggerRef={sourceDrawerTriggerRef}
        sourceOpen={sourceDrawerOpen}
        onToggleSource={() => {
          if (sourceDrawerOpen) {
            setSourceDrawerOpen(false);
            sourceDrawerTriggerRef.current?.focus();
            return;
          }
          setEditorTab("json");
          setEditorDockOpen(true);
          setSourceDrawerOpen(true);
        }}
        inspectorTriggerRef={inspectorDrawerTriggerRef}
        inspectorOpen={inspectorDrawerOpen}
        onToggleInspector={() => {
          if (inspectorDrawerOpen) {
            setInspectorDrawerOpen(false);
            window.setTimeout(
              () => inspectorDrawerTriggerRef.current?.focus(),
              0,
            );
          } else {
            setInspectorDrawerOpen(true);
          }
        }}
        doctor={doctor}
        mobileStage={workflowMode}
        mobileStageCount={
          workflowMode === "draw"
            ? problem.construction.length
            : workflowMode === "constrain"
              ? problem.constraints.length + problem.guards.length
              : problem.answer.trim()
                ? 1
                : 0
        }
        mobileModelOpen={leftDeckOpen}
        mobileModelTriggerRef={mobileModelTriggerRef}
        onToggleMobileModel={() => setLeftDeckOpen((open) => !open)}
      />
      <main
        className={`workspace ${leftDeckOpen ? "left-deck-open" : "left-deck-collapsed"} ${editorDockOpen ? "editor-dock-open" : "editor-dock-collapsed"} ${sourceDrawerOpen ? "source-drawer-open" : "source-drawer-closed"} workflow-${workflowMode}`}
        style={
          {
            "--left-pane-width": `${layoutSizes.left}px`,
            "--right-pane-width": `${layoutSizes.right}px`,
            "--bottom-pane-height": `${layoutSizes.bottom}px`,
          } as CSSProperties
        }
        inert={catalogOpen ? true : undefined}
        aria-hidden={catalogOpen || undefined}
      >
        {viewportWidth < 768 && leftDeckOpen ? (
          <button
            className="mobile-model-backdrop"
            aria-label="作図ナビゲーションの外側を閉じる"
            onPointerDown={(event) => {
              event.preventDefault();
              setLeftDeckOpen(false);
              mobileModelTriggerRef.current?.focus();
            }}
            onClick={() => {
              setLeftDeckOpen(false);
              mobileModelTriggerRef.current?.focus();
            }}
          />
        ) : null}
        <aside
          id="model-navigator"
          ref={modelPaneRef}
          className={`model-pane geogebra-pane mode-${leftMode} ${leftDeckOpen ? "deck-open" : "deck-collapsed"}`}
          aria-label="作図サイドバー"
          role={viewportWidth < 768 && leftDeckOpen ? "dialog" : undefined}
          aria-modal={viewportWidth < 768 && leftDeckOpen ? true : undefined}
          inert={viewportWidth < 768 && !leftDeckOpen ? true : undefined}
          aria-hidden={viewportWidth < 768 && !leftDeckOpen ? true : undefined}
        >
          <WorkflowStageNav
            mode={workflowMode}
            objectCount={problem.construction.length}
            conditionCount={problem.constraints.length + problem.guards.length}
            solverReady={!!problem.answer.trim()}
            onDraw={() => {
              setWorkflowMode("draw");
              // The drawing tools already live on the canvas bench. Keep the
              // object navigator visible so switching workflow stages never
              // replaces useful project context with an empty instruction view.
              setLeftMode("algebra");
            }}
            onConstrain={() => {
              setWorkflowMode("constrain");
              setLeftMode("algebra");
            }}
            onSolve={() => {
              setWorkflowMode("solve");
              setLeftMode("algebra");
              setInspectorDrawerOpen(true);
              window.setTimeout(() => {
                const scrollBody = inspectorScrollBodyRef.current;
                const solverSection =
                  scrollBody?.querySelector<HTMLElement>(
                    ".solver-settings-section",
                  );
                if (scrollBody && solverSection)
                  scrollBody.scrollTop = Math.max(
                    0,
                    solverSection.offsetTop - scrollBody.offsetTop,
                  );
              }, 0);
            }}
          />
          <button
            className="left-deck-toggle"
            aria-label={leftDeckOpen ? "作図デッキを折りたたむ" : "作図デッキを開く"}
            aria-expanded={leftDeckOpen}
            onClick={() => {
              setLeftDeckOpen((open) => !open);
              if (leftDeckOpen && viewportWidth < 768)
                window.setTimeout(
                  () => mobileModelTriggerRef.current?.focus(),
                  0,
                );
            }}
          >
            {leftDeckOpen ? <CaretLeft /> : <CaretRight />}
            <span>{leftDeckOpen ? "COLLAPSE" : "OPEN"}</span>
          </button>
          <div className="left-view">
            {leftMode === "tools" ? (
              <>
                <div className="sketch-tool-actions">
                  <button
                    aria-label="選択モードに戻る"
                    onClick={() => setMode("select")}
                  >
                    <X />
                    <span>選択に戻る</span>
                  </button>
                </div>
                <div className="draw-mode-note">
                  <strong>DRAW MODE</strong>
                  <span>上のツールベンチから作図を開始します。</span>
                </div>
              </>
            ) : (
              <>
                <div className="geogebra-view-heading">
                  <div>
                    <h1>オブジェクト</h1>
                    <small>MODEL GRAPH</small>
                  </div>
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
                        <div className="object-summary">
                          <div className="object-id">
                            <strong>{item.name}</strong>
                            <span>{FREEDOM_LABEL[freedom]}</span>
                          </div>
                          <MathFormula
                            className="object-formula"
                            source={item.expr}
                            label={`${item.name}の定義: ${item.expr}`}
                          />
                        </div>
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
                    <div>
                      <span>条件と変数</span>
                      <small>CONSTRAINT SYSTEM</small>
                    </div>
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
          onChange={(left) => layout.setSize("left", left)}
        />
        <section
          className="center-stage"
          style={
            { "--bottom-pane-height": `${layoutSizes.bottom}px` } as CSSProperties
          }
        >
          <div className={`instrument-tool-bench ${showAllTools ? "expanded" : ""}`}>
            <div className="instrument-tool-grid" aria-label="作図ツール">
              {sketchTools.map((item) => {
                const active =
                  (item.action === "mode" && tool === item.value) ||
                  guided?.tool.id === item.value;
                return (
                  <button
                    key={item.id}
                    className={active ? "active" : ""}
                    aria-pressed={active}
                    aria-label={`作図ツール ${item.label}`}
                    title={item.note ?? item.label}
                    onClick={() => activatePaletteTool(item)}
                  >
                    <PaletteGlyph id={item.id} />
                    <span>{item.label}</span>
                    <kbd>{SKETCH_TOOL_SHORTCUTS[item.id] ?? ""}</kbd>
                  </button>
                );
              })}
            </div>
            <button
              className="more-tools"
              aria-expanded={showAllTools}
              onClick={() => {
                setViewToolsOpen(false);
                setShowAllTools((value) => !value);
              }}
            >
              <DotsNine />
              <span>
                {showAllTools ? "基本ツールだけ表示" : "その他のツール"}
              </span>
            </button>
            <button
              className="catalog-tool-trigger"
              aria-label="すべてのV15ツールを開く"
              onClick={() => openCatalog()}
            >
              <MagnifyingGlass />
              <span>CATALOG</span>
            </button>
            <div className="view-tools" ref={viewToolsRef}>
              <button
                ref={viewToolsTriggerRef}
                className="view-tools-trigger"
                aria-label="表示・履歴ツール"
                aria-expanded={viewToolsOpen}
                aria-controls="view-tools-popover"
                onClick={() => setViewToolsOpen((value) => !value)}
              >
                <GridFour />
              </button>
              {viewToolsOpen ? (
                <div
                  id="view-tools-popover"
                  className="view-tools-popover"
                  role="group"
                  aria-label="表示と履歴"
                >
                  <span className="view-tools-eyebrow">VIEW / HISTORY</span>
                  <CanvasToolbar
                    canUndo={!!history.length || draftActive}
                    canRedo={!!future.length || draftActive}
                    onUndo={undo}
                    onRedo={redo}
                    grid={grid}
                    snap={snap}
                    onToggleGrid={() => setGrid(!grid)}
                    onToggleSnap={() => setSnap(!snap)}
                    onPan={() => setMode("pan")}
                    canShowAll={!!hidden.size}
                    onShowAll={() => setHidden(new Set())}
                    canFitAll={!!scene.items.length}
                    onFitAll={fitAllObjects}
                    canClearAll={
                      !!(
                        problem.construction.length ||
                        problem.variables.names.length ||
                        problem.constraints.length ||
                        problem.guards.length ||
                        problem.answer ||
                        problem.post_process ||
                        measurements.length
                      )
                    }
                    onClearAll={clearAll}
                  />
                </div>
              ) : null}
            </div>
          </div>
          <ToolInstruction
            toolLabel={activeToolLabel}
            message={`${instruction}${
              !guided &&
              [
                "free-point",
                "fixed-point",
                "segment",
                "line",
                "circle",
                "polygon",
              ].includes(tool)
                ? ` · キーボード位置 x ${keyboardPoint.x.toFixed(1)}, y ${keyboardPoint.y.toFixed(1)}。矢印キーで移動、Enterで確定`
                : ""
            }`}
            warningCount={scene.warnings.length}
            showCancel={
              !!guided ||
              toolPoints.length > 0 ||
              !["select", "pan"].includes(tool)
            }
            onCancel={() => {
              setGuided(undefined);
              setToolPoints([]);
              setPendingPoints([]);
              setTool("select");
              window.setTimeout(() => canvasRef.current?.focus(), 0);
            }}
          />
          <div className={`canvas-wrap mode-${tool}`}>
            <svg
              ref={canvasRef}
              className="geometry-canvas"
              viewBox={`0 0 ${CANVAS.width} ${CANVAS.height}`}
              preserveAspectRatio={
                viewportWidth < 768 ? "xMidYMid slice" : "xMidYMid meet"
              }
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
                  id="micro-grid"
                  className="minor-grid-pattern"
                  width={camera.pixelsPerUnit / 5}
                  height={camera.pixelsPerUnit / 5}
                  patternUnits="userSpaceOnUse"
                >
                  <path
                    d={`M ${camera.pixelsPerUnit / 5} 0 L 0 0 0 ${camera.pixelsPerUnit / 5}`}
                  />
                </pattern>
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
                <pattern
                  id="major-grid"
                  className="major-grid-pattern"
                  width={camera.pixelsPerUnit}
                  height={camera.pixelsPerUnit}
                  patternUnits="userSpaceOnUse"
                >
                  <rect
                    width={camera.pixelsPerUnit}
                    height={camera.pixelsPerUnit}
                    fill="url(#micro-grid)"
                  />
                  <path
                    d={`M ${camera.pixelsPerUnit} 0 L 0 0 0 ${camera.pixelsPerUnit}`}
                  />
                </pattern>
              </defs>
              <rect
                className="canvas-hit"
                width={CANVAS.width}
                height={CANVAS.height}
                fill={grid ? "url(#major-grid)" : "var(--drafting-paper)"}
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
                    {objectStyles[item.name]?.label !== "hidden" && (
                      <CanvasMathLabel
                        source={item.name}
                        placement={{
                          x: point.x + 8,
                          y: point.y - 31,
                          width: 60,
                          height: 26,
                        }}
                      />
                    )}
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
            <ZoomControls
              onZoomIn={() =>
                setCamera((value) => ({
                  ...value,
                  pixelsPerUnit: Math.min(180, value.pixelsPerUnit * 1.2),
                }))
              }
              onZoomOut={() =>
                setCamera((value) => ({
                  ...value,
                  pixelsPerUnit: Math.max(20, value.pixelsPerUnit / 1.2),
                }))
              }
              onRecenter={() =>
                setCamera({ center: { x: 0, y: 0 }, pixelsPerUnit: 65 })
              }
            />
          </div>
          <SolverInstrumentRail
            target={problem.answer}
            phase={phase}
            progress={runProgress}
            running={running}
            profile={
              solverMode === "reference"
                ? "180s  /  1 core"
                : `${maxTime}s  /  ${cores === "auto" ? "auto cores" : `${cores} cores`}`
            }
            onOpenTarget={() => {
              setWorkflowMode("solve");
              setInspectorDrawerOpen(true);
            }}
            onOpenDetails={() => {
              setWorkflowMode("solve");
              setInspectorDrawerOpen(true);
            }}
            onStart={() => {
              setWorkflowMode("solve");
              void startSolve();
            }}
            onCancel={() => void cancelSolve()}
          />
          <PaneResizeHandle
            orientation="horizontal"
            label="下部エディターの高さを変更"
            value={layoutSizes.bottom}
            minimum={150}
            maximum={420}
            valuePerPixel={-1}
            defaultValue={DEFAULT_LAYOUT_SIZES.bottom}
            onChange={(bottom) => layout.setSize("bottom", bottom)}
          />
          <div
            id="advanced-source-drawer"
            ref={sourceDrawerRef}
            className={`editor-panel ${editorDockOpen ? "dock-open" : "dock-collapsed"} ${sourceDrawerOpen ? "source-visible" : "source-hidden"}`}
            role={sourceDrawerOpen ? "dialog" : undefined}
            aria-label={sourceDrawerOpen ? "Advanced Source" : undefined}
            aria-modal={sourceDrawerOpen || undefined}
          >
            <EditorTabs
              tab={editorTab}
              onChange={setEditorTab}
              expanded={editorDockOpen}
              onToggleExpanded={() => {
                const next = !editorDockOpen;
                setEditorDockOpen(next);
                setSourceDrawerOpen(next);
              }}
            />
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
          <nav className="constraint-rail" aria-label="制約ショートカット">
            <button
              className="constraint-settings"
              aria-label={`選択: ${selected || "—"}`}
              aria-controls="solver-inspector"
              aria-expanded={inspectorDrawerOpen}
              onClick={() => setInspectorDrawerOpen(true)}
            >
              <span className="constraint-context-label">SELECTED</span>
              <strong>{selected || "—"}</strong>
              <Wrench />
            </button>
            <div className="constraint-shortcuts">
              {constraintTools
                .filter(({ id }) =>
                  ["Parallel", "Perpendicular", "AssumeEq", "Midpoint"].includes(
                    id,
                  ),
                )
                .map(({ id, label, key, tool: shortcutTool }) =>
                  shortcutTool ? (
                    <button
                      key={id}
                      aria-label={`制約 ${label}`}
                      title={shortcutTool.note ?? label}
                      onClick={() => activatePaletteTool(shortcutTool)}
                    >
                      <span className="constraint-key">
                        <kbd>Shift</kbd>
                        <kbd>{key}</kbd>
                      </span>
                      <strong>{label}</strong>
                      <PaletteGlyph id={id} />
                    </button>
                  ) : null,
                )}
            </div>
          </nav>
        </section>
        <PaneResizeHandle
          orientation="vertical"
          label="右パネルの幅を変更"
          value={layoutSizes.right}
          minimum={270}
          maximum={rightPaneMaximum}
          valuePerPixel={-1}
          defaultValue={DEFAULT_LAYOUT_SIZES.right}
          onChange={(right) => layout.setSize("right", right)}
        />
        {inspectorIsDrawer && inspectorDrawerOpen && (
          <button
            className="inspector-drawer-backdrop"
            aria-label="Inspector外側を閉じる"
            onClick={() => {
              setInspectorDrawerOpen(false);
              window.setTimeout(
                () => inspectorDrawerTriggerRef.current?.focus(),
                0,
              );
            }}
          />
        )}
        <aside
          id="solver-inspector"
          ref={inspectorDrawerRef}
          className={`solver-pane ${inspectorDrawerOpen ? "drawer-open" : ""}`}
          aria-label="プロパティとsolver"
          inert={inspectorIsDrawer && !inspectorDrawerOpen ? true : undefined}
          aria-hidden={inspectorIsDrawer && !inspectorDrawerOpen ? true : undefined}
        >
          <button
            className="inspector-drawer-close"
            aria-label="Inspectorを閉じる"
            onClick={() => {
              setInspectorDrawerOpen(false);
              window.setTimeout(
                () => inspectorDrawerTriggerRef.current?.focus(),
                0,
              );
            }}
          >
            <X />
          </button>
          <div className="inspector-deck-title">
            <div>
              <span className="inspector-eyebrow">INSPECTOR</span>
              <strong>{selectedConstruction?.name || "No selection"}</strong>
              <span className="inspector-selection-meta">
                {selectedConstruction
                  ? FREEDOM_LABEL[
                      freedomOf(
                        selectedConstruction,
                        problem.variables.names,
                      )
                    ]
                  : "オブジェクトを選択してください"}
              </span>
            </div>
            <i aria-hidden="true" />
          </div>
          <div ref={inspectorScrollBodyRef} className="inspector-scroll-body">
            <section className="inspector-section property-inspector">
            <h2>オブジェクト</h2>
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
                    <div className="property-actions">
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
                        value={
                          selectedStyle.label ??
                          (selectedSceneItem?.kind === "point"
                            ? "name"
                            : "hidden")
                        }
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
            <section className="inspector-section solver-settings-section">
            <h2>Solver設定</h2>
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
                    <strong>{validationIssueLocation(issue.path, problem)}</strong>
                    <span>{issue.message}</span>
                    {validationIssueExpression(issue.path, problem) && (
                      <code>{validationIssueExpression(issue.path, problem)}</code>
                    )}
                  </li>
                ))}
              </ul>
            )}
            {validation?.warnings && validation.warnings.length > 0 && (
              <ul className="validation-errors validation-warnings">
                {validation.warnings.map((warning) => (
                  <li key={`${warning.path}-${warning.code}`}>
                    <strong>{validationIssueLocation(warning.path, problem)}</strong>
                    <span>{warning.message}</span>
                  </li>
                ))}
              </ul>
            )}
            </section>
            <Suspense
              fallback={
                <section className="inspector-section result-section">
                  <div className="empty-result">結果表示を読み込み中…</div>
                </section>
              }
            >
              <ExactResult
                result={result}
                progress={runProgress}
                activeAnswer={activeAnswer}
                showWitness={showWitness}
                onToggleWitness={(index) => {
                  if (activeAnswer === index && showWitness)
                    setShowWitness(false);
                  else {
                    setActiveAnswer(index);
                    setShowWitness(true);
                  }
                }}
              />
            </Suspense>
          </div>
          <SolverExecutionDock
            phase={phase}
            progress={runProgress}
            running={running}
            cancelError={solverJob.cancelError}
            onStart={() => void startSolve()}
            onCancel={() => void cancelSolve()}
          />
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
      {pointNaming && (
        <form
          className="point-name-card"
          role="dialog"
          aria-modal="false"
          aria-labelledby="point-name-title"
          onSubmit={(event) => {
            event.preventDefault();
            finishPointNaming();
          }}
          onKeyDown={(event) => {
            if (event.key === "Escape") {
              event.preventDefault();
              event.stopPropagation();
              const cancelsConstruction = pendingPoints.some(
                (item) => item.name === pointNaming.generatedName,
              );
              setPointNameDraft("");
              setPointNaming(undefined);
              if (cancelsConstruction) {
                setToolPoints([]);
                setPendingPoints([]);
                setTool("select");
              }
              window.setTimeout(() => canvasRef.current?.focus(), 0);
            }
          }}
        >
          <div>
            <strong id="point-name-title">点の名前</strong>
            <span>任意</span>
          </div>
          <p>名前を表示する場合だけ入力してください。</p>
          <input
            ref={pointNameInputRef}
            aria-label="新しい点の名前"
            value={pointNameDraft}
            onChange={(event) => setPointNameDraft(event.target.value)}
            placeholder="例: P"
            autoComplete="off"
          />
          <div>
            <button
              type="button"
              onClick={() => {
                setPointNameDraft("");
                setPointNaming(undefined);
                window.setTimeout(() => canvasRef.current?.focus(), 0);
              }}
            >
              名前なし
            </button>
            <button type="submit" className="primary-action">
              確定
            </button>
          </div>
        </form>
      )}
      {uiError && (
        <div className="toast" role="alert">
          <span>{uiError}</span>
          <button aria-label="閉じる" onClick={() => setUiError("")}>
            <X />
          </button>
        </div>
      )}
      {uiNotice && (
        <div className="toast success" role="status">
          <span>{uiNotice}</span>
          <button aria-label="通知を閉じる" onClick={() => setUiNotice("")}>
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
                <span>{catalog.version}</span>
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
