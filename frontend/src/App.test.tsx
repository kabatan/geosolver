import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { IDBFactory } from "fake-indexeddb";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import productCatalog from "../../src/geotarget/dsl_catalog.json";
import { App, catalogPaletteGroups, conditionFromFormula, expandDistanceShorthand, formulaToGuard, guardToFormula, migrateLegacyUiEquationGuards, withoutBlankExpressions, type DslCatalog } from "./App";

const catalog = {
  version: "V15",
  categories: [
    { id: "points", label_ja: "点", label_en: "Points" },
    { id: "lines", label_ja: "線", label_en: "Lines" },
    { id: "measurements", label_ja: "測定", label_en: "Measurements" },
    { id: "relations", label_ja: "平行・垂直・接線", label_en: "Relations" },
    { id: "constraints", label_ja: "制約", label_en: "Constraints" },
    { id: "guards", label_ja: "条件", label_en: "Guards" },
  ],
  tools: [
    { id: "Point", category: "points", label_ja: "点", signature: "Point(0, 0)", authoring_status: "supported" },
    { id: "Midpoint", category: "points", label_ja: "中点または中心", signature: "Midpoint(A, B)", authoring_status: "supported" },
    { id: "PointOnSegment", category: "points", label_ja: "線分上の点", signature: "PointOnSegment(A, B, t)", authoring_status: "supported" },
    { id: "Center", category: "points", label_ja: "円の中心", signature: "Center(c)", authoring_status: "supported" },
    { id: "Segment", category: "lines", label_ja: "線分", signature: "Segment(A, B)", authoring_status: "supported" },
    { id: "FootOfPerpendicular", category: "lines", label_ja: "垂線の足", signature: "FootOfPerpendicular(P, line)", authoring_status: "supported" },
    { id: "Angle", category: "measurements", label_ja: "角度", signature: "Angle(A, B, C)", authoring_status: "supported" },
    { id: "Distance", category: "measurements", label_ja: "距離", signature: "Distance(A, B)", authoring_status: "supported" },
    { id: "Ratio", category: "measurements", label_ja: "比", signature: "Distance(A, B) / Distance(C, D)", authoring_status: "supported" },
    { id: "TangentAtPoint", category: "relations", label_ja: "接点における接線", signature: "Polar(P, omega)", authoring_status: "supported" },
    { id: "OnCircle", category: "constraints", label_ja: "円上", signature: "OnCircle(P, c)", authoring_status: "supported" },
    { id: "AssumeLt", category: "guards", label_ja: "未満", signature: "AssumeLt(lhs, rhs)", authoring_status: "supported" },
  ],
};

beforeEach(() => {
  window.localStorage.clear();
  vi.stubGlobal("indexedDB", new IDBFactory());
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.endsWith("/api/v1/dsl/catalog")) return new Response(JSON.stringify(catalog));
    if (url.endsWith("/api/v1/doctor")) return new Response(JSON.stringify({ ok: true }));
    if (url.endsWith("/api/v1/qualification")) return new Response(JSON.stringify({ default_engine: "reference" }));
    if (url.endsWith("/api/v1/session")) return new Response(JSON.stringify({ status: "ready" }));
    if (url.endsWith("/api/v1/preview")) return new Response(JSON.stringify({ validation: { valid: true, issues: [] } }));
    throw new Error(`unexpected fetch ${url}`);
  }));
});

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("condition formula presentation", () => {
  it("round-trips relational guards without exposing internal Assume calls", () => {
    expect(guardToFormula("AssumeLt(Angle(A, B, C), pi/2)")).toBe("Angle(A, B, C) < π/2");
    expect(formulaToGuard("Angle(A, B, C) < π/2")).toBe("AssumeLt(Angle(A, B, C), pi/2)");
    expect(guardToFormula("AssumeGe(Dot(Vector(A, P), Vector(A, B)), 0)")).toBe("Dot(Vector(A, P), Vector(A, B)) ≥ 0");
    expect(guardToFormula("Bound(t, (0, 1))")).toBe("0 ≤ t ≤ 1");
    expect(formulaToGuard("0 ≤ t ≤ 1")).toBe("Bound(t, (0, 1))");
  });

  it("classifies equations and inequalities without retaining blank rows", () => {
    expect(conditionFromFormula("Distance(A, B) = 5")).toEqual({
      kind: "constraint",
      value: { def: "Distance(A, B)", value: 5 },
    });
    expect(conditionFromFormula("Distance(A, B) < 5")).toEqual({
      kind: "guard",
      value: "AssumeLt(Distance(A, B), 5)",
    });
    expect(conditionFromFormula("   ")).toBeUndefined();
    expect(
      withoutBlankExpressions({
        task: "solve", id: "blank-cleanup", variables: { names: [] },
        construction: [], constraints: [
          { def: " ", value: 0 },
          { def: "Distance(A, B)", value: 5 },
        ], guards: ["", "AssumeLt(x, 1)"], answer: "x", post_process: "",
      }),
    ).toMatchObject({
      constraints: [{ def: "Distance(A, B)", value: 5 }],
      guards: ["AssumeLt(x, 1)"],
    });
  });

  it("migrates every legacy UI equality guard without function-specific heuristics", () => {
    const original = {
      task: "solve" as const,
      id: "legacy-equations",
      variables: { names: ["x"] },
      construction: [],
      constraints: [{ def: "x", value: 1 }],
      guards: [
        "AssumeEq(Distance(A, B), sqrt(17))",
        "AssumeEq(Angle(A, B, C) + x, pi/3)",
        "AssumeEq(OnSegment(P, A, B), 0)",
        "AssumeLt(x, 10)",
        "AssumeNe(x, 0)",
      ],
      answer: "x",
      post_process: "",
    };

    const migrated = migrateLegacyUiEquationGuards(original);

    expect(migrated.migratedCount).toBe(3);
    expect(migrated.problem.constraints).toEqual([
      { def: "x", value: 1 },
      { def: "Distance(A, B)", value: "sqrt(17)" },
      { def: "Angle(A, B, C) + x", value: "pi/3" },
      { def: "OnSegment(P, A, B)", value: 0 },
    ]);
    expect(migrated.problem.guards).toEqual([
      "AssumeLt(x, 10)",
      "AssumeNe(x, 0)",
    ]);
  });

  it("deduplicates an equality already present as a constraint during migration", () => {
    const original = {
      task: "solve" as const,
      id: "duplicate-equation",
      variables: { names: [] },
      construction: [],
      constraints: [{ def: "Distance(A, B)", value: 5 }],
      guards: ["AssumeEq(Distance(A, B), 5)"],
      answer: "Distance(A, B)",
      post_process: "",
    };

    const migrated = migrateLegacyUiEquationGuards(original);

    expect(migrated.problem.constraints).toEqual(original.constraints);
    expect(migrated.problem.guards).toEqual([]);
  });
});

describe("distance shorthand", () => {
  it("expands an unambiguous concatenation of two point IDs", () => {
    expect(expandDistanceShorthand("AB + P1P2", ["A", "B", "P1", "P2"])).toBe(
      "Distance(A, B) + Distance(P1, P2)",
    );
  });

  it("preserves a real object with the same name and function identifiers", () => {
    expect(
      expandDistanceShorthand(
        "AB + Distance(A, B)",
        ["A", "B"],
        ["A", "B", "AB"],
      ),
    ).toBe("AB + Distance(A, B)");
  });

  it("does not rewrite strings, keyword names, attributes, or numeric literals", () => {
    expect(
      expandDistanceShorthand(
        "F(x, method='cross') + obj.method + 1e3 + AB",
        ["met", "hod", "c", "ross", "A", "B", "e", "3"],
        ["met", "hod", "c", "ross", "A", "B", "e", "3"],
      ),
    ).toBe("F(x, method='cross') + obj.method + 1e3 + Distance(A, B)");
  });

  it("preserves scalar-language keywords and constants", () => {
    expect(
      expandDistanceShorthand(
        "True and not False or (AB if flag else None) + pi",
        ["a", "nd", "n", "ot", "o", "r", "i", "f", "el", "se", "p", "i", "A", "B"],
      ),
    ).toBe(
      "True and not False or (Distance(A, B) if flag else None) + pi",
    );
  });

  it("preserves ambiguous and unfinished trailing point concatenations", () => {
    expect(
      expandDistanceShorthand("ABC", ["A", "AB", "BC", "C"]),
    ).toBe("ABC");
    expect(
      expandDistanceShorthand("AB", ["A", "B", "BC"], undefined, false),
    ).toBe("AB");
    expect(expandDistanceShorthand("ABC", ["A", "B", "BC"])).toBe(
      "Distance(A, BC)",
    );
  });
});

describe("GeoTarget workbench", () => {
  it("uses the supplied geometry icon sprite and exposes persistent pane separators", async () => {
    render(<App />);

    const pointTool = screen.getByRole("button", { name: "作図ツール 点" });
    expect(pointTool.querySelector("use")).toHaveAttribute(
      "href",
      "/tool-icons.svg#tool-Point",
    );

    const left = screen.getByRole("separator", { name: "左パネルの幅を変更" });
    const right = screen.getByRole("separator", { name: "右パネルの幅を変更" });
    const bottom = screen.getByRole("separator", {
      name: "下部エディターの高さを変更",
    });
    expect(left).toHaveAttribute("aria-valuenow", "350");
    expect(right).toHaveAttribute("aria-valuenow", "330");
    expect(bottom).toHaveAttribute("aria-valuenow", "196");

    fireEvent.keyDown(left, { key: "ArrowRight" });
    fireEvent.keyDown(right, { key: "ArrowLeft" });
    fireEvent.keyDown(bottom, { key: "ArrowUp" });
    expect(left).toHaveAttribute("aria-valuenow", "366");
    expect(right).toHaveAttribute("aria-valuenow", "346");
    expect(bottom).toHaveAttribute("aria-valuenow", "212");

    await waitFor(() =>
      expect(JSON.parse(localStorage.getItem("geotarget.layout.v1") ?? "{}")).toEqual({
        left: 366,
        right: 346,
        bottom: 212,
      }),
    );
    fireEvent.doubleClick(left);
    expect(left).toHaveAttribute("aria-valuenow", "350");
  });

  it("accepts AB as a target shorthand and stores canonical V15 JSON", async () => {
    render(<App />);
    const target = screen.getByRole("textbox", { name: "ターゲット式" });
    await userEvent.clear(target);
    await userEvent.type(target, "AB");
    await userEvent.click(screen.getByRole("button", { name: "ターゲットに設定" }));
    await userEvent.click(screen.getByRole("tab", { name: "V15 JSON" }));
    const saved = JSON.parse(
      (screen.getByRole("textbox", { name: "V15 JSON" }) as HTMLTextAreaElement)
        .value,
    );
    expect(saved.answer).toBe("Distance(A, B)");
  });

  it("accepts AB inside a mathematical condition", async () => {
    render(<App />);
    await userEvent.click(screen.getByRole("button", { name: "代数" }));
    await userEvent.click(screen.getByRole("button", { name: "条件を追加" }));
    const condition = screen.getByRole("combobox", { name: "条件 1" });
    await userEvent.clear(condition);
    await userEvent.type(condition, "AB<6");
    expect(condition).toHaveValue("Distance(A, B) < 6");
    await userEvent.click(screen.getByRole("tab", { name: "V15 JSON" }));
    const saved = JSON.parse(
      (screen.getByRole("textbox", { name: "V15 JSON" }) as HTMLTextAreaElement)
        .value,
    );
    expect(saved.guards).toContain("AssumeLt(Distance(A, B), 6)");
  });

  it("stores mathematical equality input as a residual constraint", async () => {
    render(<App />);
    await userEvent.click(screen.getByRole("button", { name: "代数" }));
    await userEvent.click(screen.getByRole("button", { name: "条件を追加" }));
    const condition = screen.getByRole("combobox", { name: "条件 1" });
    await userEvent.type(condition, "Distance(A, B)=sqrt(17)");
    fireEvent.keyDown(condition, { key: "Enter" });
    await userEvent.click(screen.getByRole("tab", { name: "V15 JSON" }));
    const saved = JSON.parse(
      (screen.getByRole("textbox", { name: "V15 JSON" }) as HTMLTextAreaElement)
        .value,
    );
    expect(saved.constraints).toContainEqual({
      def: "Distance(A, B)",
      value: "sqrt(17)",
    });
    expect(saved.guards).not.toContain(
      "AssumeEq(Distance(A, B), sqrt(17))",
    );
  });

  it("migrates legacy equality guards when restoring an autosaved UI project", async () => {
    const legacy = {
      problem: {
        task: "solve",
        id: "legacy-autosave",
        variables: { names: [] },
        construction: [
          { name: "A", expr: "Point(0, 0)" },
          { name: "B", expr: "Point(1, 0)" },
        ],
        constraints: [],
        guards: [
          "AssumeEq(Distance(A, B), 1)",
          "AssumeLt(Distance(A, B), 2)",
        ],
        answer: "Distance(A, B)",
        post_process: "",
      },
    };
    await new Promise<void>((resolve, reject) => {
      const open = indexedDB.open("geotarget", 2);
      open.onupgradeneeded = () => open.result.createObjectStore("projects");
      open.onerror = () => reject(open.error);
      open.onsuccess = () => {
        const write = open.result
          .transaction("projects", "readwrite")
          .objectStore("projects")
          .put(legacy, "__last__");
        write.onerror = () => reject(write.error);
        write.onsuccess = () => resolve();
      };
    });

    render(<App />);
    await waitFor(() =>
      expect(screen.getByText("legacy-autosave.geotarget.json")).toBeInTheDocument(),
    );
    await userEvent.click(screen.getByRole("tab", { name: "V15 JSON" }));
    const saved = JSON.parse(
      (screen.getByRole("textbox", { name: "V15 JSON" }) as HTMLTextAreaElement)
        .value,
    );
    expect(saved.constraints).toEqual([{ def: "Distance(A, B)", value: 1 }]);
    expect(saved.guards).toEqual(["AssumeLt(Distance(A, B), 2)"]);
  });

  it("canonicalizes AB when a catalog measurement is saved", async () => {
    render(<App />);
    await userEvent.click(
      screen.getByRole("button", { name: "すべてのV15ツールを開く" }),
    );
    await userEvent.click(screen.getByRole("button", { name: /比Ratio/ }));
    const definition = screen.getByRole("combobox", { name: "V15定義式" });
    await userEvent.clear(definition);
    await userEvent.type(definition, "AB");
    await userEvent.click(screen.getByRole("button", { name: "測定値に追加" }));
    expect(screen.getByRole("region", { name: "測定値" })).toHaveTextContent(
      "Distance(A, B)",
    );
  });

  it("exposes every authorable V15 catalog function in the full palette", () => {
    const visible = new Set(catalogPaletteGroups(productCatalog as DslCatalog).flatMap((group) => group.tools.map((tool) => tool.id)));
    const expected = productCatalog.tools.filter((tool) => tool.authoring_status !== "legacy_read_only").map((tool) => tool.id);
    expect(expected.filter((id) => !visible.has(id))).toEqual([]);
  });
  it("starts without a fabricated result and visibility affects the real scene", async () => {
    render(<App />);
    expect(screen.getByText("まだ実行していません。")).toBeInTheDocument();
    expect(document.querySelector('[data-object="A"]')).toBeInTheDocument();
    expect(document.querySelector('[data-object="A"] circle:not(.point-hit):not(.point-selection-ring)')).toHaveAttribute("r", "3.5");
    await userEvent.click(screen.getByRole("button", { name: "代数" }));
    await userEvent.click(screen.getByRole("button", { name: "Aを非表示" }));
    expect(document.querySelector('[data-object="A"]')).not.toBeInTheDocument();
  });

  it("provides show-all, fit-all, and undoable clear-all convenience actions", async () => {
    render(<App />);
    const fit = screen.getByRole("button", { name: "図全体に表示を合わせる" });
    const gridPattern = document.querySelector<SVGPatternElement>("#minor-grid")!;
    expect(gridPattern.getAttribute("width")).toBe("32.5");
    await userEvent.click(fit);
    expect(Number(gridPattern.getAttribute("width"))).toBeGreaterThan(32.5);

    await userEvent.click(screen.getByRole("button", { name: "代数" }));
    await userEvent.click(screen.getByRole("button", { name: "Aを非表示" }));
    expect(document.querySelector('[data-object="A"]')).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "すべてのオブジェクトを表示" }));
    expect(document.querySelector('[data-object="A"]')).toBeInTheDocument();

    const confirm = vi.spyOn(window, "confirm").mockReturnValueOnce(false).mockReturnValueOnce(true);
    const clear = screen.getByRole("button", { name: "すべて消去" });
    await userEvent.click(clear); expect(document.querySelector('[data-object="A"]')).toBeInTheDocument();
    await userEvent.click(clear); expect(document.querySelector("[data-object]")).not.toBeInTheDocument();
    expect(confirm).toHaveBeenCalledTimes(2);
    await userEvent.click(screen.getByRole("button", { name: "元に戻す" }));
    expect(document.querySelector('[data-object="A"]')).toBeInTheDocument();
  });

  it("keeps the large pointer hit target invisible on free points", async () => {
    render(<App />);
    const canvas = screen.getByRole("application", { name: /幾何作図キャンバス/ });
    Object.defineProperty(canvas, "getBoundingClientRect", { value: () => ({ left: 0, top: 0, width: 1000, height: 700, right: 1000, bottom: 700, x: 0, y: 0, toJSON() {} }) });
    await userEvent.click(screen.getByRole("button", { name: "作図ツール 点" }));
    fireEvent.pointerDown(canvas.querySelector(".canvas-hit")!, { clientX: 700, clientY: 300, pointerId: 90, button: 0 });
    const hitTarget = document.querySelector<SVGCircleElement>('[data-object="P"] .point-hit')!;
    expect(hitTarget).toHaveAttribute("r", "12");
    expect(hitTarget.style.fill).toBe("transparent");
    expect(document.querySelector('[data-object="P"] circle:not(.point-hit):not(.point-selection-ring)')).toHaveAttribute("r", "3.5");
  });

  it("keeps JSON as an explicit draft and applies it to the canvas", async () => {
    render(<App />);
    await userEvent.click(screen.getByRole("tab", { name: "V15 JSON" }));
    const replacement = {
      task: "solve", id: "one-point", variables: { names: [] },
      construction: [{ name: "X", expr: "Point(2, 1)" }], constraints: [], guards: [],
      answer: "Distance(X, X)", post_process: "",
    };
    fireEvent.change(screen.getByRole("textbox", { name: "V15 JSON" }), { target: { value: JSON.stringify(replacement) } });
    expect(document.querySelector('[data-object="X"]')).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "JSONを適用" }));
    await waitFor(() => expect(document.querySelector('[data-object="X"]')).toBeInTheDocument());
    expect(document.querySelector('[data-object="B"]')).not.toBeInTheDocument();
  });

  it("offers and creates an exact intersection when the Point tool is used near a crossing", async () => {
    render(<App />);
    await userEvent.click(screen.getByRole("tab", { name: "V15 JSON" }));
    const crossing = {
      task: "solve", id: "crossing", variables: { names: [] },
      construction: [
        { name: "A", expr: "Point(-3, 0)" }, { name: "B", expr: "Point(3, 0)" },
        { name: "C", expr: "Point(0, -3)" }, { name: "D", expr: "Point(0, 3)" },
        { name: "horizontal", expr: "Line(A, B)" }, { name: "vertical", expr: "Line(C, D)" },
      ], constraints: [], guards: [], answer: "Distance(A, B)", post_process: "",
    };
    fireEvent.change(screen.getByRole("textbox", { name: "V15 JSON" }), { target: { value: JSON.stringify(crossing) } });
    await userEvent.click(screen.getByRole("button", { name: "JSONを適用" }));
    const canvas = screen.getByRole("application", { name: /幾何作図キャンバス/ });
    Object.defineProperty(canvas, "getBoundingClientRect", { value: () => ({ left: 0, top: 0, width: 1000, height: 700, right: 1000, bottom: 700, x: 0, y: 0, toJSON() {} }) });
    await userEvent.click(screen.getByRole("button", { name: "作図ツール 点" }));
    fireEvent.pointerMove(canvas.querySelector(".canvas-hit")!, { clientX: 505, clientY: 352, pointerId: 81 });
    expect(canvas.querySelector(".intersection-snap")).toBeInTheDocument();
    fireEvent.click(document.querySelector('[data-object="horizontal"]')!, { clientX: 505, clientY: 352, detail: 1 });
    expect(screen.getByDisplayValue("Intersect(horizontal, vertical)")).toBeInTheDocument();
    expect(document.querySelector('[data-object="P"]')).toHaveAttribute("data-freedom", "derived");
  });

  it("keeps both line-circle branches as one parameter plus an incidence constraint", async () => {
    render(<App />);
    await userEvent.click(screen.getByRole("tab", { name: "V15 JSON" }));
    const crossing = {
      task: "solve", id: "line-circle-branch", variables: { names: [] },
      construction: [
        { name: "O", expr: "Point(0, 0)" }, { name: "R", expr: "Point(2, 0)" },
        { name: "C", expr: "Point(0, -3)" }, { name: "D", expr: "Point(0, 3)" },
        { name: "omega", expr: "CircleThroughPoint(O, R)" }, { name: "vertical", expr: "Line(C, D)" },
        { name: "A", expr: "Point(0, -2)" },
      ], constraints: [], guards: [], answer: "Distance(O, R)", post_process: "",
    };
    fireEvent.change(screen.getByRole("textbox", { name: "V15 JSON" }), { target: { value: JSON.stringify(crossing) } });
    await userEvent.click(screen.getByRole("button", { name: "JSONを適用" }));
    const canvas = screen.getByRole("application", { name: /幾何作図キャンバス/ });
    Object.defineProperty(canvas, "getBoundingClientRect", { value: () => ({ left: 0, top: 0, width: 1000, height: 700, right: 1000, bottom: 700, x: 0, y: 0, toJSON() {} }) });
    await userEvent.click(screen.getByRole("button", { name: "作図ツール 点" }));
    fireEvent.click(document.querySelector('[data-object="vertical"]')!, { clientX: 500, clientY: 220, detail: 1 });
    expect(screen.getByDisplayValue("PointOnCircle(omega, tP)")).toBeInTheDocument();
    const saved = JSON.parse((screen.getByRole("textbox", { name: "V15 JSON" }) as HTMLTextAreaElement).value);
    expect(saved.variables.names).toContain("tP");
    expect(saved.constraints).toContainEqual({ def: "OnLine(P, vertical)", value: 0 });
    expect(saved.construction).not.toContainEqual(expect.objectContaining({ expr: expect.stringContaining("exclude=") }));
    expect(document.querySelector('[data-object="P"]')).toHaveAttribute("data-freedom", "derived");
  });

  it("keeps both circle-circle branches without relying on internal list order", async () => {
    render(<App />);
    await userEvent.click(screen.getByRole("tab", { name: "V15 JSON" }));
    const crossing = {
      task: "solve", id: "circle-circle-branches", variables: { names: [] },
      construction: [
        { name: "O1", expr: "Point(-1, 0)" }, { name: "O2", expr: "Point(1, 0)" },
        { name: "c1", expr: "Circle(O1, 2)" }, { name: "c2", expr: "Circle(O2, 2)" },
      ], constraints: [], guards: [], answer: "Distance(O1, O2)", post_process: "",
    };
    fireEvent.change(screen.getByRole("textbox", { name: "V15 JSON" }), { target: { value: JSON.stringify(crossing) } });
    await userEvent.click(screen.getByRole("button", { name: "JSONを適用" }));
    const canvas = screen.getByRole("application", { name: /幾何作図キャンバス/ });
    Object.defineProperty(canvas, "getBoundingClientRect", { value: () => ({ left: 0, top: 0, width: 1000, height: 700, right: 1000, bottom: 700, x: 0, y: 0, toJSON() {} }) });
    await userEvent.click(screen.getByRole("button", { name: "作図ツール 点" }));
    fireEvent.click(document.querySelector('[data-object="c1"]')!, { clientX: 500, clientY: 237, detail: 1 });
    expect(screen.getByDisplayValue("PointOnCircle(c1, tP)")).toBeInTheDocument();
    const saved = JSON.parse((screen.getByRole("textbox", { name: "V15 JSON" }) as HTMLTextAreaElement).value);
    expect(saved.constraints).toContainEqual({ def: "OnCircle(P, c2)", value: 0 });
    expect(saved.guards).not.toContain(expect.stringContaining("n="));
  });

  it("uses exclude when both objects are proven to share the other intersection", async () => {
    render(<App />);
    await userEvent.click(screen.getByRole("tab", { name: "V15 JSON" }));
    const crossing = {
      task: "solve", id: "shared-circle-intersection", variables: { names: [] },
      construction: [
        { name: "O1", expr: "Point(-3, 0)" }, { name: "O2", expr: "Point(3, 0)" }, { name: "P", expr: "Point(0, 4)" },
        { name: "c1", expr: "CircleThroughPoint(O1, P)" }, { name: "c2", expr: "CircleThroughPoint(O2, P)" },
      ], constraints: [], guards: [], answer: "Distance(O1, O2)", post_process: "",
    };
    fireEvent.change(screen.getByRole("textbox", { name: "V15 JSON" }), { target: { value: JSON.stringify(crossing) } });
    await userEvent.click(screen.getByRole("button", { name: "JSONを適用" }));
    const canvas = screen.getByRole("application", { name: /幾何作図キャンバス/ });
    Object.defineProperty(canvas, "getBoundingClientRect", { value: () => ({ left: 0, top: 0, width: 1000, height: 700, right: 1000, bottom: 700, x: 0, y: 0, toJSON() {} }) });
    await userEvent.click(screen.getByRole("button", { name: "作図ツール 点" }));
    fireEvent.click(document.querySelector('[data-object="c1"]')!, { clientX: 500, clientY: 610, detail: 1 });
    expect(screen.getByDisplayValue("Intersect(c1, c2, exclude=P)")).toBeInTheDocument();
    const saved = JSON.parse((screen.getByRole("textbox", { name: "V15 JSON" }) as HTMLTextAreaElement).value);
    expect(saved.variables.names).toEqual([]);
    expect(saved.constraints).toEqual([]);
  });

  it("combines the shared-point heuristic with finite segment semantics", async () => {
    render(<App />);
    await userEvent.click(screen.getByRole("tab", { name: "V15 JSON" }));
    const crossing = {
      task: "solve", id: "shared-segment-intersection", variables: { names: [] },
      construction: [
        { name: "O", expr: "Point(0, 0)" }, { name: "P", expr: "Point(-2, 0)" }, { name: "Q", expr: "Point(3, 0)" },
        { name: "omega", expr: "CircleThroughPoint(O, P)" }, { name: "s", expr: "Segment(P, Q)" },
      ], constraints: [], guards: [], answer: "Distance(P, Q)", post_process: "",
    };
    fireEvent.change(screen.getByRole("textbox", { name: "V15 JSON" }), { target: { value: JSON.stringify(crossing) } });
    await userEvent.click(screen.getByRole("button", { name: "JSONを適用" }));
    const canvas = screen.getByRole("application", { name: /幾何作図キャンバス/ });
    Object.defineProperty(canvas, "getBoundingClientRect", { value: () => ({ left: 0, top: 0, width: 1000, height: 700, right: 1000, bottom: 700, x: 0, y: 0, toJSON() {} }) });
    await userEvent.click(screen.getByRole("button", { name: "作図ツール 点" }));
    fireEvent.click(document.querySelector('[data-object="s"]')!, { clientX: 630, clientY: 350, detail: 1 });
    const saved = JSON.parse((screen.getByRole("textbox", { name: "V15 JSON" }) as HTMLTextAreaElement).value);
    expect(saved.constraints).toContainEqual({ def: "OnSegment(P2, P, Q)", value: 0 });
    expect(saved.guards).toContain("AssumeNe(Distance(P2, P), 0)");
  });

  it("creates the same branch-neutral intersection from the keyboard crosshair", async () => {
    render(<App />);
    await userEvent.click(screen.getByRole("tab", { name: "V15 JSON" }));
    const crossing = {
      task: "solve", id: "keyboard-intersection", variables: { names: [] },
      construction: [
        { name: "O", expr: "Point(0, 0)" }, { name: "R", expr: "Point(2, 0)" },
        { name: "C", expr: "Point(0, -3)" }, { name: "D", expr: "Point(0, 3)" },
        { name: "omega", expr: "CircleThroughPoint(O, R)" }, { name: "vertical", expr: "Line(C, D)" },
      ], constraints: [], guards: [], answer: "Distance(O, R)", post_process: "",
    };
    fireEvent.change(screen.getByRole("textbox", { name: "V15 JSON" }), { target: { value: JSON.stringify(crossing) } });
    await userEvent.click(screen.getByRole("button", { name: "JSONを適用" }));
    await userEvent.click(screen.getByRole("button", { name: "作図ツール 点" }));
    const canvas = screen.getByRole("application", { name: /幾何作図キャンバス/ }); canvas.focus();
    for (const key of ["ArrowLeft", "ArrowLeft", "ArrowUp", "ArrowUp"]) fireEvent.keyDown(canvas, { key });
    expect(screen.getByRole("status")).toHaveTextContent("交点候補");
    fireEvent.keyDown(canvas, { key: "Enter" });
    expect(screen.getByDisplayValue("PointOnCircle(omega, tP)")).toBeInTheDocument();
    const saved = JSON.parse((screen.getByRole("textbox", { name: "V15 JSON" }) as HTMLTextAreaElement).value);
    expect(saved.constraints).toContainEqual({ def: "OnLine(P, vertical)", value: 0 });
  });

  it("preserves segment and ray domains instead of widening them to lines", async () => {
    render(<App />);
    await userEvent.click(screen.getByRole("tab", { name: "V15 JSON" }));
    const crossing = {
      task: "solve", id: "finite-carrier-intersection", variables: { names: [] },
      construction: [
        { name: "A", expr: "Point(0, 0)" }, { name: "B", expr: "Point(1, 0)" },
        { name: "C", expr: "Point(2, -2)" }, { name: "D", expr: "Point(2, 2)" },
        { name: "r", expr: "Ray(A, B)" }, { name: "vertical", expr: "Line(C, D)" },
      ], constraints: [], guards: [], answer: "Distance(A, B)", post_process: "",
    };
    fireEvent.change(screen.getByRole("textbox", { name: "V15 JSON" }), { target: { value: JSON.stringify(crossing) } });
    await userEvent.click(screen.getByRole("button", { name: "JSONを適用" }));
    const canvas = screen.getByRole("application", { name: /幾何作図キャンバス/ });
    Object.defineProperty(canvas, "getBoundingClientRect", { value: () => ({ left: 0, top: 0, width: 1000, height: 700, right: 1000, bottom: 700, x: 0, y: 0, toJSON() {} }) });
    await userEvent.click(screen.getByRole("button", { name: "作図ツール 点" }));
    fireEvent.click(document.querySelector('[data-object="r"]')!, { clientX: 630, clientY: 350, detail: 1 });
    const saved = JSON.parse((screen.getByRole("textbox", { name: "V15 JSON" }) as HTMLTextAreaElement).value);
    expect(saved.construction).toContainEqual({ name: "P", expr: "PointOnLine(vertical, tP)" });
    expect(saved.constraints).toContainEqual({ def: "OnLine(P, Line(A, B))", value: 0 });
    expect(saved.guards).toContain("AssumeGe(Dot(Vector(A, P), Vector(A, B)), 0)");
  });

  it("creates a free point and segment directly, then undo and redo restore one operation", async () => {
    render(<App />);
    await userEvent.click(screen.getByRole("button", { name: "作図ツール 点" }));
    const canvas = screen.getByRole("application", { name: /幾何作図キャンバス/ });
    Object.defineProperty(canvas, "getBoundingClientRect", { value: () => ({ left: 0, top: 0, width: 1000, height: 700, right: 1000, bottom: 700, x: 0, y: 0, toJSON() {} }) });
    fireEvent.pointerDown(canvas.querySelector(".canvas-hit")!, { clientX: 700, clientY: 300, pointerId: 1 });
    expect(document.querySelector('[data-object="P"]')).toHaveAttribute("data-freedom", "free");
    await userEvent.click(screen.getByRole("button", { name: "作図ツール 線分" }));
    await userEvent.click(screen.getByRole("button", { name: /^固定点 A/ }));
    await userEvent.click(screen.getByRole("button", { name: /^固定点 B/ }));
    expect(document.querySelector('[data-object="s"]')).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "元に戻す" }));
    expect(document.querySelector('[data-object="s"]')).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "やり直す" }));
    expect(document.querySelector('[data-object="s"]')).toBeInTheDocument();
    expect(document.querySelector('[data-object="s"] .geometry-object-hit')).toHaveAttribute("class", "geometry-object-hit");
  });

  it("asks for a new point name and keeps blank names visually hidden", async () => {
    render(<App />);
    await userEvent.click(screen.getByRole("button", { name: "作図ツール 点" }));
    const canvas = screen.getByRole("application", { name: /幾何作図キャンバス/ });
    Object.defineProperty(canvas, "getBoundingClientRect", { value: () => ({ left: 0, top: 0, width: 1000, height: 700, right: 1000, bottom: 700, x: 0, y: 0, toJSON() {} }) });

    fireEvent.pointerDown(canvas.querySelector(".canvas-hit")!, { clientX: 700, clientY: 300, pointerId: 101, button: 0 });
    const nameInput = screen.getByRole("textbox", { name: "新しい点の名前" });
    await waitFor(() => expect(nameInput).toHaveFocus());
    await userEvent.type(nameInput, "Q{Enter}");

    expect(document.querySelector('[data-object="P"]')).not.toBeInTheDocument();
    expect(document.querySelector('[data-object="Q"] .canvas-math-label')).toBeInTheDocument();

    fireEvent.pointerDown(canvas.querySelector(".canvas-hit")!, { clientX: 760, clientY: 260, pointerId: 102, button: 0 });
    const blankNameInput = screen.getByRole("textbox", { name: "新しい点の名前" });
    await userEvent.type(blankNameInput, "{Enter}");

    expect(document.querySelector('[data-object="P"]')).toBeInTheDocument();
    expect(document.querySelector('[data-object="P"] .canvas-math-label')).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "元に戻す" }));
    expect(document.querySelector('[data-object="P"]')).not.toBeInTheDocument();
    expect(document.querySelector('[data-object="Q"]')).toBeInTheDocument();
  });

  it("hides line and circle labels until the user explicitly enables them", async () => {
    render(<App />);
    await userEvent.click(screen.getByRole("tab", { name: "V15 JSON" }));
    const labeledObjects = {
      task: "solve", id: "default-object-labels", variables: { names: [] },
      construction: [
        { name: "A", expr: "Point(0, 0)" },
        { name: "B", expr: "Point(2, 0)" },
        { name: "l", expr: "Line(A, B)" },
        { name: "c", expr: "CircleThroughPoint(A, B)" },
      ],
      constraints: [], guards: [], answer: "Distance(A, B)", post_process: "",
    };
    fireEvent.change(screen.getByRole("textbox", { name: "V15 JSON" }), { target: { value: JSON.stringify(labeledObjects) } });
    await userEvent.click(screen.getByRole("button", { name: "JSONを適用" }));

    expect(document.querySelector('[data-object="A"] .canvas-math-label')).toBeInTheDocument();
    expect(document.querySelector('[data-object="l"] .canvas-math-label')).not.toBeInTheDocument();
    expect(document.querySelector('[data-object="c"] .canvas-math-label')).not.toBeInTheDocument();

    fireEvent.click(document.querySelector('[data-object="l"]')!);
    await userEvent.click(screen.getByRole("tab", { name: "スタイル" }));
    expect(screen.getByLabelText("ラベル")).toHaveValue("hidden");
    await userEvent.selectOptions(screen.getByLabelText("ラベル"), "name");
    expect(document.querySelector('[data-object="l"] .canvas-math-label')).toBeInTheDocument();
  });

  it("creates blank-click endpoint points and their segment as one undoable construction", async () => {
    render(<App />);
    const canvas = screen.getByRole("application", { name: /幾何作図キャンバス/ });
    Object.defineProperty(canvas, "getBoundingClientRect", { value: () => ({ left: 0, top: 0, width: 1000, height: 700, right: 1000, bottom: 700, x: 0, y: 0, toJSON() {} }) });
    await userEvent.click(screen.getByRole("button", { name: "作図ツール 線分" }));
    fireEvent.pointerDown(canvas.querySelector(".canvas-hit")!, { clientX: 620, clientY: 420, pointerId: 40, button: 0 });
    expect(document.querySelector('[data-pending-point="P"]')).toBeInTheDocument();
    expect(document.querySelector('[data-object="P"]')).not.toBeInTheDocument();
    fireEvent.pointerDown(canvas.querySelector(".canvas-hit")!, { clientX: 760, clientY: 300, pointerId: 41, button: 0 });
    expect(document.querySelector('[data-object="P"]')).toBeInTheDocument();
    expect(document.querySelector('[data-object="P2"]')).toBeInTheDocument();
    expect(document.querySelector('[data-object="s"]')).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "元に戻す" }));
    expect(document.querySelector('[data-object="P"]')).not.toBeInTheDocument();
    expect(document.querySelector('[data-object="s"]')).not.toBeInTheDocument();
  });

  it("discards provisional blank-click points when construction is cancelled", async () => {
    render(<App />);
    const canvas = screen.getByRole("application", { name: /幾何作図キャンバス/ });
    Object.defineProperty(canvas, "getBoundingClientRect", { value: () => ({ left: 0, top: 0, width: 1000, height: 700, right: 1000, bottom: 700, x: 0, y: 0, toJSON() {} }) });
    await userEvent.click(screen.getByRole("button", { name: "作図ツール 直線" }));
    fireEvent.pointerDown(canvas.querySelector(".canvas-hit")!, { clientX: 620, clientY: 420, pointerId: 42, button: 0 });
    expect(document.querySelector("[data-pending-point]")).toBeInTheDocument();
    await userEvent.keyboard("{Escape}");
    expect(document.querySelector("[data-pending-point]")).not.toBeInTheDocument();
    expect(document.querySelector('[data-object="P"]')).not.toBeInTheDocument();
  });

  it("uses Undo to cancel the first draft even when committed history is empty", async () => {
    render(<App />);
    const canvas = screen.getByRole("application", { name: /幾何作図キャンバス/ });
    await userEvent.click(screen.getByRole("button", { name: "作図ツール 直線" }));
    canvas.focus(); fireEvent.keyDown(canvas, { key: "Enter" });
    expect(document.querySelector("[data-pending-point]")).toBeInTheDocument();
    const undo = screen.getByRole("button", { name: "元に戻す" });
    expect(undo).toBeEnabled(); await userEvent.click(undo);
    expect(document.querySelector("[data-pending-point]")).not.toBeInTheDocument();
  });

  it("supports keyboard placement, polygon closure, and draft-first undo", async () => {
    render(<App />);
    const canvas = screen.getByRole("application", { name: /幾何作図キャンバス/ });
    await userEvent.click(screen.getByRole("button", { name: "作図ツール 点" }));
    await userEvent.keyboard("{Enter}");
    expect(document.querySelector('[data-object="P"]')).toHaveAttribute("data-freedom", "free");

    await userEvent.click(screen.getByRole("button", { name: "作図ツール 直線" }));
    canvas.focus(); fireEvent.keyDown(canvas, { key: "ArrowRight" }); fireEvent.keyDown(canvas, { key: "Enter" });
    expect(document.querySelector("[data-pending-point]")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "元に戻す" }));
    expect(document.querySelector("[data-pending-point]")).not.toBeInTheDocument();
    expect(document.querySelector('[data-object="P"]')).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "作図ツール 多角形" }));
    canvas.focus(); for (const key of ["Enter", "ArrowRight", "Enter", "ArrowUp", "Enter"]) fireEvent.keyDown(canvas, { key });
    const firstPoint = screen.getByRole("button", { name: /^自由点 P / });
    firstPoint.focus(); await userEvent.keyboard("{Enter}");
    expect(document.querySelector('[data-object^="poly"]')).toBeInTheDocument();
  });

  it("keeps nested algebra actions keyboard-operable and creates a carrier point without a pointer", async () => {
    render(<App />);
    await userEvent.click(screen.getByRole("button", { name: "作図ツール 直線" }));
    await userEvent.click(screen.getByRole("button", { name: /^固定点 A/ }));
    await userEvent.click(screen.getByRole("button", { name: /^固定点 B/ }));
    await userEvent.click(screen.getByRole("button", { name: "作図ツール 点" }));
    await userEvent.click(screen.getByRole("button", { name: "代数" }));
    const lineRow = screen.getAllByRole("treeitem").find((item) => item.textContent?.includes("Line(A, B)"))!;
    lineRow.focus(); await userEvent.keyboard("{Enter}");
    expect(screen.getByDisplayValue("PointOnLine(l, tP)")).toBeInTheDocument();
    const visibility = screen.getByRole("button", { name: "Aを非表示" });
    visibility.focus(); await userEvent.keyboard(" ");
    expect(screen.getByRole("button", { name: "Aを表示" })).toBeInTheDocument();
  });

  it("maps pointer coordinates through SVG letterboxing", async () => {
    render(<App />);
    const canvas = screen.getByRole("application", { name: /幾何作図キャンバス/ });
    Object.defineProperty(canvas, "getBoundingClientRect", { value: () => ({ left: 0, top: 0, width: 1000, height: 1000, right: 1000, bottom: 1000, x: 0, y: 0, toJSON() {} }) });
    await userEvent.click(screen.getByRole("button", { name: "作図ツール 点" }));
    fireEvent.pointerDown(canvas.querySelector(".canvas-hit")!, { clientX: 500, clientY: 200, pointerId: 30, button: 0 });
    expect(screen.getByRole("spinbutton", { name: "Pのparameter表示値" })).toHaveValue(4.5);
    expect(screen.getByRole("combobox", { name: "定義" })).toHaveValue("Point(0, yP)");
  });

  it("snaps the Point tool to the coordinate axes and origin", async () => {
    render(<App />);
    await userEvent.click(screen.getByRole("tab", { name: "V15 JSON" }));
    const empty = { task: "solve", id: "axes", variables: { names: [] }, construction: [], constraints: [], guards: [], answer: "", post_process: "" };
    fireEvent.change(screen.getByRole("textbox", { name: "V15 JSON" }), { target: { value: JSON.stringify(empty) } });
    await userEvent.click(screen.getByRole("button", { name: "JSONを適用" }));
    const canvas = screen.getByRole("application", { name: /幾何作図キャンバス/ });
    Object.defineProperty(canvas, "getBoundingClientRect", { value: () => ({ left: 0, top: 0, width: 1000, height: 700, right: 1000, bottom: 700, x: 0, y: 0, toJSON() {} }) });
    await userEvent.click(screen.getByRole("button", { name: "作図ツール 点" }));

    fireEvent.pointerDown(canvas.querySelector(".canvas-hit")!, { clientX: 650, clientY: 356, pointerId: 81, button: 0 });
    expect(screen.getByRole("combobox", { name: "定義" })).toHaveValue("Point(xP, 0)");
    expect(document.querySelector('[data-object="P"]')).toHaveAttribute("data-freedom", "free");

    fireEvent.pointerDown(canvas.querySelector(".canvas-hit")!, { clientX: 506, clientY: 220, pointerId: 82, button: 0 });
    expect(screen.getByRole("combobox", { name: "定義" })).toHaveValue("Point(0, yP2)");
    expect(document.querySelector('[data-object="P2"]')).toHaveAttribute("data-freedom", "free");

    fireEvent.pointerDown(canvas.querySelector(".canvas-hit")!, { clientX: 505, clientY: 345, pointerId: 83, button: 0 });
    expect(screen.getByRole("combobox", { name: "定義" })).toHaveValue("Point(0, 0)");
    expect(document.querySelector('[data-object="P3"]')).toHaveAttribute("data-freedom", "fixed");

    await userEvent.click(screen.getByRole("button", { name: "作図ツール 移動" }));
    const xPoint = document.querySelector<SVGGElement>('[data-object="P"]')!;
    fireEvent.pointerDown(xPoint, { clientX: 662.5, clientY: 350, pointerId: 84, button: 0 });
    fireEvent.pointerMove(xPoint, { clientX: 760, clientY: 200, pointerId: 84 });
    fireEvent.pointerUp(xPoint, { clientX: 760, clientY: 200, pointerId: 84 });
    expect(screen.getByRole("spinbutton", { name: "Pのparameter表示値" })).toHaveValue(4);
    expect(document.querySelector('[data-object="P"] circle:not(.point-hit)')).toHaveAttribute("cy", "350");
  });

  it("keeps free-point drag as preview metadata without rewriting the V15 expression", async () => {
    render(<App />);
    const canvas = screen.getByRole("application", { name: /幾何作図キャンバス/ });
    Object.defineProperty(canvas, "getBoundingClientRect", { value: () => ({ left: 0, top: 0, width: 1000, height: 700, right: 1000, bottom: 700, x: 0, y: 0, toJSON() {} }) });
    await userEvent.click(screen.getByRole("button", { name: "作図ツール 点" }));
    fireEvent.pointerDown(canvas.querySelector(".canvas-hit")!, { clientX: 650, clientY: 300, pointerId: 1 });
    const point = document.querySelector<SVGGElement>('[data-object="P"]')!;
    expect(point).toHaveClass("draggable");
    const before = point.querySelector("circle:not(.point-hit)")?.getAttribute("cx");
    await userEvent.click(screen.getByRole("button", { name: "作図ツール 移動" }));
    fireEvent.pointerDown(point, { clientX: 650, clientY: 300, pointerId: 2 });
    fireEvent.pointerMove(canvas, { clientX: 780, clientY: 280, pointerId: 2 });
    fireEvent.pointerUp(canvas, { clientX: 780, clientY: 280, pointerId: 2 });
    expect(document.querySelector('[data-object="P"] circle:not(.point-hit)')?.getAttribute("cx")).not.toBe(before);
    expect(screen.getByRole("spinbutton", { name: "Pのx表示位置" })).toHaveValue((780 - 500) / 65);
    expect(screen.getByDisplayValue("Point(Px, Py)")).toBeInTheDocument();
  });

  it("drags a free point through the point's own captured pointer stream", async () => {
    render(<App />);
    const canvas = screen.getByRole("application", { name: /幾何作図キャンバス/ });
    Object.defineProperty(canvas, "getBoundingClientRect", { value: () => ({ left: 0, top: 0, width: 1000, height: 700, right: 1000, bottom: 700, x: 0, y: 0, toJSON() {} }) });
    await userEvent.click(screen.getByRole("button", { name: "作図ツール 点" }));
    fireEvent.pointerDown(canvas.querySelector(".canvas-hit")!, { clientX: 650, clientY: 300, pointerId: 21 });
    await userEvent.click(screen.getByRole("button", { name: "作図ツール 移動" }));
    const point = document.querySelector<SVGGElement>('[data-object="P"]')!;
    const before = point.querySelector("circle:not(.point-hit)")?.getAttribute("cx");
    fireEvent.pointerDown(point, { clientX: 650, clientY: 300, pointerId: 22 });
    fireEvent.pointerMove(point, { clientX: 820, clientY: 250, pointerId: 22 });
    fireEvent.pointerUp(point, { clientX: 820, clientY: 250, pointerId: 22 });
    expect(document.querySelector('[data-object="P"] circle:not(.point-hit)')?.getAttribute("cx")).not.toBe(before);
  });

  it("drags points constrained to a line, segment, and circle", async () => {
    render(<App />);
    await userEvent.click(screen.getByRole("tab", { name: "V15 JSON" }));
    const constrained = {
      task: "solve", id: "constrained-drag", variables: { names: ["tl", "ts", "tc"] },
      construction: [
        { name: "A", expr: "Point(0, 0)" }, { name: "B", expr: "Point(4, 0)" },
        { name: "line", expr: "Line(A, B)" }, { name: "circle", expr: "Circle(A, 2)" },
        { name: "L", expr: "PointOnLine(line, tl)" }, { name: "S", expr: "PointOnSegment(A, B, ts)" }, { name: "C", expr: "PointOnCircle(circle, tc)" },
      ], constraints: [], guards: ["Bound(ts, (0, 1))"], answer: "Distance(A, B)", post_process: "",
    };
    fireEvent.change(screen.getByRole("textbox", { name: "V15 JSON" }), { target: { value: JSON.stringify(constrained) } });
    await userEvent.click(screen.getByRole("button", { name: "JSONを適用" }));
    const canvas = screen.getByRole("application", { name: /幾何作図キャンバス/ });
    Object.defineProperty(canvas, "getBoundingClientRect", { value: () => ({ left: 0, top: 0, width: 1000, height: 700, right: 1000, bottom: 700, x: 0, y: 0, toJSON() {} }) });
    await userEvent.click(screen.getByRole("button", { name: "作図ツール 移動" }));
    for (const [name, variable, pointerId] of [["L", "tl", 71], ["S", "ts", 72], ["C", "tc", 73]] as const) {
      const point = document.querySelector<SVGGElement>(`[data-object="${name}"]`)!;
      fireEvent.pointerDown(point, { clientX: 500, clientY: 350, pointerId, button: 0 });
      fireEvent.pointerMove(point, { clientX: 650, clientY: 250, pointerId });
      fireEvent.pointerUp(point, { clientX: 650, clientY: 250, pointerId });
      expect(screen.getByRole("spinbutton", { name: `${name}のparameter表示値` })).not.toHaveValue(0);
      expect(screen.getByText(variable)).toBeInTheDocument();
    }
  });

  it("creates a one-degree-of-freedom point by clicking directly on a line", async () => {
    render(<App />);
    const canvas = screen.getByRole("application", { name: /幾何作図キャンバス/ });
    Object.defineProperty(canvas, "getBoundingClientRect", { value: () => ({ left: 0, top: 0, width: 1000, height: 700, right: 1000, bottom: 700, x: 0, y: 0, toJSON() {} }) });
    await userEvent.click(screen.getByRole("button", { name: "作図ツール 直線" }));
    await userEvent.click(screen.getByRole("button", { name: /^固定点 A/ }));
    await userEvent.click(screen.getByRole("button", { name: /^固定点 B/ }));
    await userEvent.click(screen.getByRole("button", { name: "作図ツール 点" }));
    fireEvent.click(document.querySelector('[data-object="l"]')!, { clientX: 650, clientY: 350 });
    expect(document.querySelector('[data-object="P"]')).toHaveAttribute("data-freedom", "free");
    expect(screen.getByDisplayValue("PointOnLine(l, tP)")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "代数" }));
    await userEvent.click(screen.getByText("条件と変数"));
    expect(screen.getByDisplayValue("tP")).toBeInTheDocument();
    expect(Number((screen.getByRole("spinbutton", { name: "Pのparameter表示値" }) as HTMLInputElement).value)).toBeLessThan(0);
  });

  it("uses the clicked carrier to create natural points on a circle and segment", async () => {
    render(<App />);
    const canvas = screen.getByRole("application", { name: /幾何作図キャンバス/ });
    Object.defineProperty(canvas, "getBoundingClientRect", { value: () => ({ left: 0, top: 0, width: 1000, height: 700, right: 1000, bottom: 700, x: 0, y: 0, toJSON() {} }) });
    const pointA = screen.getByRole("button", { name: /^固定点 A/ }); const pointB = screen.getByRole("button", { name: /^固定点 B/ });
    await userEvent.click(screen.getByRole("button", { name: "作図ツール 中心と1点で円" })); await userEvent.click(pointA); await userEvent.click(pointB);
    await userEvent.click(screen.getByRole("button", { name: "作図ツール 点" }));
    fireEvent.click(document.querySelector('[data-object="c"]')!, { clientX: 760, clientY: 350 });
    expect(screen.getByDisplayValue("PointOnCircle(c, tP)")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "ツール" }));
    await userEvent.click(screen.getByRole("button", { name: "作図ツール 線分" })); await userEvent.click(pointA); await userEvent.click(pointB);
    await userEvent.click(screen.getByRole("button", { name: "作図ツール 点" }));
    fireEvent.click(document.querySelector('[data-object="s"]')!, { clientX: 720, clientY: 350 });
    expect(screen.getByDisplayValue("PointOnSegment(A, B, tP2)")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "代数" }));
    await userEvent.click(screen.getByText("条件と変数"));
    expect(screen.getByDisplayValue("0 ≤ tP2 ≤ 1")).toBeInTheDocument();
  });

  it("creates a construction by selecting its arguments on the diagram", async () => {
    render(<App />);
    await userEvent.click(screen.getByRole("button", { name: "すべてのV15ツールを開く" }));
    await userEvent.click(screen.getByRole("button", { name: /中点/ }));
    await userEvent.click(screen.getByRole("button", { name: "図から引数を選ぶ" }));
    expect(screen.getByRole("status")).toHaveTextContent("1点目を図から選択");
    await userEvent.click(screen.getByRole("button", { name: /^固定点 A/ }));
    expect(screen.getByRole("status")).toHaveTextContent("2点目を図から選択");
    await userEvent.click(screen.getByRole("button", { name: /^固定点 B/ }));
    expect(document.querySelector('[data-object="m"]')).toBeInTheDocument();
    expect(screen.getByDisplayValue("Midpoint(A, B)")).toBeInTheDocument();
  });

  it("creates only a genuine circle tangent through the Polar construction", async () => {
    render(<App />);
    await userEvent.click(screen.getByRole("tab", { name: "V15 JSON" }));
    const setup = {
      task: "solve", id: "tangent", variables: { names: [] },
      construction: [{ name: "O", expr: "Point(0, 0)" }, { name: "P", expr: "Point(2, 0)" }, { name: "Q", expr: "Point(1, 0)" }, { name: "c", expr: "CircleThroughPoint(O, P)" }],
      constraints: [], guards: [], answer: "Distance(O, P)", post_process: "",
    };
    fireEvent.change(screen.getByRole("textbox", { name: "V15 JSON" }), { target: { value: JSON.stringify(setup) } });
    await userEvent.click(screen.getByRole("button", { name: "JSONを適用" }));
    await userEvent.click(screen.getByRole("button", { name: "ツール" }));
    await userEvent.click(screen.getByRole("button", { name: "その他のツール" }));
    await userEvent.click(screen.getByRole("button", { name: "作図ツール 接点における接線" }));
    await userEvent.click(screen.getByRole("button", { name: /^固定点 Q/ }));
    await userEvent.click(document.querySelector('[data-object="c"]')!);
    expect(screen.getByRole("alert")).toHaveTextContent("円周上にある点");
    await userEvent.click(screen.getByRole("button", { name: /^固定点 P/ }));
    await userEvent.click(document.querySelector('[data-object="c"]')!);
    expect(screen.getByDisplayValue("Polar(P, c)")).toBeInTheDocument();
  });

  it("supports keyboard guided selection through the object tree and Escape cancellation", async () => {
    render(<App />);
    const canvas = screen.getByRole("application", { name: /幾何作図キャンバス/ });
    await userEvent.click(screen.getByRole("button", { name: "すべてのV15ツールを開く" }));
    await userEvent.click(screen.getByRole("button", { name: /中点/ }));
    await userEvent.click(screen.getByRole("button", { name: "図から引数を選ぶ" }));
    await userEvent.click(screen.getByRole("button", { name: "代数" }));
    const treeItems = screen.getAllByRole("treeitem");
    treeItems[0].focus(); await userEvent.keyboard("{Enter}");
    treeItems[1].focus(); await userEvent.keyboard("{Enter}");
    expect(document.querySelector('[data-object="m"]')).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "ツール" }));
    await userEvent.click(screen.getByRole("button", { name: "作図ツール 線分" }));
    treeItems[0].focus(); await userEvent.keyboard("{Enter}");
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("button", { name: "作図を中止" })).not.toBeInTheDocument();
    expect(canvas).toHaveFocus();
  });

  it("creates and cleanly removes a bounded one-parameter point", async () => {
    render(<App />);
    await userEvent.click(screen.getByRole("button", { name: "すべてのV15ツールを開く" }));
    await userEvent.click(screen.getByRole("button", { name: /線分上の点/ }));
    await userEvent.click(screen.getByRole("button", { name: "図から引数を選ぶ" }));
    await userEvent.click(screen.getByRole("button", { name: /^固定点 A/ }));
    await userEvent.click(screen.getByRole("button", { name: /^固定点 B/ }));
    const parameter = screen.getByRole("spinbutton", { name: "pのparameter表示値" });
    expect(parameter).toHaveAttribute("min", "0"); expect(parameter).toHaveAttribute("max", "1");
    expect(screen.getByDisplayValue("PointOnSegment(A, B, tp)")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "代数" }));
    await userEvent.click(screen.getByText("条件と変数"));
    expect(screen.getByDisplayValue("0 ≤ tp ≤ 1")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "削除" }));
    expect(document.querySelector('[data-object="p"]')).not.toBeInTheDocument();
    expect(screen.queryByDisplayValue("tp")).not.toBeInTheDocument();
    expect(screen.queryByDisplayValue("Bound(tp, (0, 1))")).not.toBeInTheDocument();
  });

  it("deletes the full dependent closure even when definitions form a cycle", async () => {
    render(<App />);
    await userEvent.click(screen.getByRole("tab", { name: "V15 JSON" }));
    const cyclic = {
      task: "solve", id: "cyclic-delete", variables: { names: [] },
      construction: [
        { name: "A", expr: "Midpoint(B, C)" },
        { name: "B", expr: "Midpoint(A, C)" },
        { name: "C", expr: "Point(0, 0)" },
      ],
      constraints: [{ def: "Distance(A, C)", value: 1 }], guards: ["NonZero(Distance(B, C))"],
      answer: "Distance(B, C)", post_process: "A",
    };
    fireEvent.change(screen.getByRole("textbox", { name: "V15 JSON" }), { target: { value: JSON.stringify(cyclic) } });
    await userEvent.click(screen.getByRole("button", { name: "JSONを適用" }));
    await userEvent.click(screen.getByRole("button", { name: "削除" }));
    expect(document.querySelector('[data-object="A"]')).not.toBeInTheDocument();
    expect(document.querySelector('[data-object="B"]')).not.toBeInTheDocument();
    expect(document.querySelector('[data-object="C"]')).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "ターゲット" }));
    expect(screen.getByRole("textbox", { name: "ターゲット式" })).toHaveValue("");
    await userEvent.click(screen.getByRole("tab", { name: "V15 JSON" }));
    await waitFor(() => {
      const saved = JSON.parse((screen.getByRole("textbox", { name: "V15 JSON" }) as HTMLTextAreaElement).value);
      expect(saved.construction).toEqual([{ name: "C", expr: "Point(0, 0)" }]);
      expect(saved.constraints).toEqual([]); expect(saved.guards).toEqual([]); expect(saved.post_process).toBe("");
    });
  });

  it("rejects a degenerate direct construction", async () => {
    render(<App />);
    await userEvent.click(screen.getByRole("button", { name: "作図ツール 直線" }));
    const pointA = screen.getByRole("button", { name: /^固定点 A/ });
    await userEvent.click(pointA); await userEvent.click(pointA);
    expect(screen.getByRole("alert")).toHaveTextContent("異なる2点");
    expect(document.querySelector('[data-object="l"]')).not.toBeInTheDocument();
  });

  it("keeps a keyboard entry point in a filtered object tree", async () => {
    render(<App />);
    await userEvent.click(screen.getByRole("button", { name: "代数" }));
    const items = screen.getAllByRole("treeitem");
    await userEvent.click(items[1]);
    await userEvent.type(screen.getByRole("textbox", { name: "オブジェクトを検索" }), "A");
    expect(screen.getByRole("treeitem")).toHaveAttribute("tabindex", "0");
  });

  it("connects tabs to panels and supports arrow-key navigation", async () => {
    render(<App />);
    const targetTab = screen.getByRole("tab", { name: "ターゲット" });
    targetTab.focus();
    await userEvent.keyboard("{ArrowRight}");
    const jsonTab = screen.getByRole("tab", { name: "V15 JSON" });
    expect(jsonTab).toHaveAttribute("aria-controls", "panel-json");
    expect(jsonTab).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tabpanel", { name: "V15 JSON" })).toHaveAttribute("aria-labelledby", "tab-json");
  });

  it("opens a modal catalog, traps the workflow, and restores trigger focus", async () => {
    render(<App />);
    const trigger = screen.getByRole("button", { name: "すべてのV15ツールを開く" });
    trigger.focus();
    await userEvent.click(trigger);
    expect(await screen.findByRole("dialog", { name: "作図・条件カタログ" })).toBeInTheDocument();
    expect(screen.getByPlaceholderText("ツールを検索")).toHaveFocus();
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it("keeps the workbench interactive while the DSL catalog is unavailable", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      if (String(input).endsWith("/api/v1/dsl/catalog")) return await new Promise<Response>(() => undefined);
      if (String(input).endsWith("/api/v1/doctor")) return new Response(JSON.stringify({ ok: true }));
      throw new Error(`unexpected fetch ${input}`);
    }));
    render(<App />);
    await userEvent.click(screen.getByRole("button", { name: "すべてのV15ツールを開く" }));
    expect(screen.getByRole("alert")).toHaveTextContent("作図カタログを読み込み中");
    expect(screen.getByRole("main")).not.toHaveAttribute("inert");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("rejects an HTTP error payload instead of treating it as a DSL catalog", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      if (String(input).endsWith("/api/v1/dsl/catalog")) return new Response(JSON.stringify({ detail: "failed" }), { status: 500 });
      if (String(input).endsWith("/api/v1/doctor")) return new Response(JSON.stringify({ ok: true }));
      throw new Error(`unexpected fetch ${input}`);
    }));
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent("DSLカタログを読み込めませんでした");
    await userEvent.click(screen.getByRole("button", { name: "すべてのV15ツールを開く" }));
    expect(screen.getByRole("alert")).toHaveTextContent("作図カタログを利用できません");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("exposes the complete tool palette to keyboard users", async () => {
    render(<App />);
    const trigger = screen.getByRole("button", { name: "その他のツール" });
    trigger.focus(); await userEvent.keyboard("{Enter}");
    const midpoint = screen.getByRole("button", { name: "作図ツール 中点または中心" });
    midpoint.focus(); await userEvent.keyboard("{Enter}");
    expect(screen.getByRole("status")).toHaveTextContent("1点目を図から選択");
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("button", { name: "作図を中止" })).not.toBeInTheDocument();
    expect(screen.getByRole("application", { name: /幾何作図キャンバス/ })).toHaveFocus();
  });

  it("creates a perpendicular foot that remains geometrically derived", async () => {
    render(<App />);
    await userEvent.click(screen.getByRole("tab", { name: "V15 JSON" }));
    const setup = {
      task: "solve", id: "perpendicular-foot", variables: { names: [] },
      construction: [
        { name: "P2", expr: "Point(-2, 0)" }, { name: "P3", expr: "Point(2, 0)" },
        { name: "i", expr: "Point(1, 3)" }, { name: "base", expr: "Segment(P2, P3)" },
      ], constraints: [], guards: [], answer: "Distance(P2, P3)", post_process: "",
    };
    fireEvent.change(screen.getByRole("textbox", { name: "V15 JSON" }), { target: { value: JSON.stringify(setup) } });
    await userEvent.click(screen.getByRole("button", { name: "JSONを適用" }));
    await userEvent.click(screen.getByRole("button", { name: "ツール" }));
    await userEvent.click(screen.getByRole("button", { name: "その他のツール" }));
    await userEvent.click(screen.getByRole("button", { name: "作図ツール 垂線の足" }));
    await userEvent.click(screen.getByRole("button", { name: /^固定点 i/ }));
    await userEvent.click(document.querySelector('[data-object="base"]')!);

    expect(screen.getByDisplayValue("FootOfPerpendicular(i, Line(P2, P3))")).toBeInTheDocument();
    const foot = document.querySelector<SVGGElement>('[data-object="f"]')!;
    expect(foot).toHaveAttribute("data-freedom", "derived");
    expect(foot.querySelector("circle:not(.point-hit):not(.point-selection-ring)")).toHaveAttribute("cx", "565");
    expect(foot.querySelector("circle:not(.point-hit):not(.point-selection-ring)")).toHaveAttribute("cy", "350");
  });

  it("adds computed angle and ratio values without changing the solver target", async () => {
    render(<App />);
    await userEvent.click(screen.getByRole("tab", { name: "V15 JSON" }));
    const setup = {
      task: "solve", id: "measurements", variables: { names: [] },
      construction: [
        { name: "A", expr: "Point(1, 0)" }, { name: "B", expr: "Point(0, 0)" },
        { name: "C", expr: "Point(0, 1)" }, { name: "D", expr: "Point(0, 2)" },
      ], constraints: [], guards: [], answer: "Distance(A, B)", post_process: "",
    };
    fireEvent.change(screen.getByRole("textbox", { name: "V15 JSON" }), { target: { value: JSON.stringify(setup) } });
    await userEvent.click(screen.getByRole("button", { name: "JSONを適用" }));
    await userEvent.click(screen.getByRole("button", { name: "ツール" }));
    await userEvent.click(screen.getByRole("button", { name: "その他のツール" }));

    await userEvent.click(screen.getByRole("button", { name: "作図ツール 角度" }));
    for (const name of ["A", "B", "C"]) await userEvent.click(screen.getByRole("button", { name: new RegExp(`^固定点 ${name}`) }));
    expect(screen.getByRole("region", { name: "測定値" })).toBeInTheDocument();
    expect(screen.getByRole("status", { name: "aの値" })).toHaveTextContent("90.00°");
    expect(JSON.parse((screen.getByRole("textbox", { name: "V15 JSON" }) as HTMLTextAreaElement).value).answer).toBe("Distance(A, B)");

    await userEvent.click(screen.getByRole("button", { name: "ツール" }));
    await userEvent.click(screen.getByRole("button", { name: "作図ツール 比" }));
    for (const name of ["A", "B", "B", "D"]) await userEvent.click(screen.getByRole("button", { name: new RegExp(`^固定点 ${name}`) }));
    expect(screen.getByRole("status", { name: "rの値" })).toHaveTextContent("0.5");
    expect(JSON.parse((screen.getByRole("textbox", { name: "V15 JSON" }) as HTMLTextAreaElement).value).answer).toBe("Distance(A, B)");

    await userEvent.click(screen.getByRole("button", { name: "aをターゲットに設定" }));
    expect(JSON.parse((screen.getByRole("textbox", { name: "V15 JSON" }) as HTMLTextAreaElement).value).answer).toBe("Angle(A, B, C)");
  });

  it("shows the math keyboard only from contextual expression fields", async () => {
    render(<App />);
    expect(
      screen.queryByRole("button", { name: "作図ツール 数式入力" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("textbox", { name: "数式入力" }),
    ).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "代数" }));
    await userEvent.click(screen.getByRole("button", { name: "条件を追加" }));
    const condition = screen.getByRole("combobox", { name: "条件 1" });
    expect(
      screen.queryByRole("region", { name: "数式キーボード" }),
    ).not.toBeInTheDocument();
    await userEvent.click(condition);
    expect(
      screen.getByRole("region", { name: "数式キーボード" }),
    ).toBeInTheDocument();
    expect(condition).toHaveAttribute(
      "aria-controls",
      "condition-1-suggestions math-keyboard",
    );
    expect(condition).toHaveAttribute(
      "aria-describedby",
      "math-keyboard-status",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "数式キーボードを閉じる" }),
    );
    expect(condition).not.toHaveAttribute("aria-describedby");
  });

  it("suggests objects and DSL functions while entering algebra", async () => {
    render(<App />);
    await userEvent.click(screen.getByRole("button", { name: "代数" }));
    await userEvent.click(screen.getByRole("button", { name: "条件を追加" }));
    const condition = screen.getByRole("combobox", { name: "条件 1" });

    await userEvent.type(condition, "Dis");
    expect(screen.getByRole("option", { name: /^Distance/ })).toBeInTheDocument();
    expect(condition).toHaveAttribute(
      "aria-activedescendant",
      "condition-1-suggestions-tool-Distance",
    );
    await userEvent.keyboard("{ArrowDown}");
    expect(condition).toHaveAttribute(
      "aria-activedescendant",
      "condition-1-suggestions-tool-Ratio",
    );
    await userEvent.keyboard("{Escape}");
    expect(condition).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByRole("region", { name: "数式キーボード" })).toBeInTheDocument();
    await userEvent.type(condition, "t");
    expect(condition).toHaveAttribute("aria-expanded", "true");
    await userEvent.keyboard("{Tab}");

    expect(condition).toHaveValue("Distance(");
  });

  it("keeps keyboard focus on virtual keys and commits from the Enter key", async () => {
    render(<App />);
    await userEvent.click(screen.getByRole("button", { name: "代数" }));
    await userEvent.click(screen.getByRole("button", { name: "条件を追加" }));
    const input = screen.getByRole("combobox", { name: "条件 1" });
    await userEvent.click(input);
    const keyboard = screen.getByRole("region", { name: "数式キーボード" });
    const xKey = within(keyboard).getByRole("button", { name: "x" });
    xKey.focus();
    await userEvent.keyboard("{Enter}");
    expect(xKey).toHaveFocus();
    expect(input).toHaveValue("x");
    const leftKey = within(keyboard).getByRole("button", { name: "左" });
    leftKey.focus();
    await userEvent.keyboard("{Enter}");
    expect(leftKey).toHaveFocus();
    const rightKey = within(keyboard).getByRole("button", { name: "右" });
    rightKey.focus();
    await userEvent.keyboard("{Enter}");
    expect(rightKey).toHaveFocus();

    fireEvent.change(input, { target: { value: "x < 6" } });
    const enterKey = within(keyboard).getByRole("button", { name: "確定" });
    enterKey.focus();
    await userEvent.keyboard("{Enter}");
    expect(screen.getByRole("combobox", { name: "条件 1" })).toHaveValue("x < 6");
    await userEvent.click(screen.getByRole("tab", { name: "V15 JSON" }));
    expect(
      (screen.getByRole("textbox", { name: "V15 JSON" }) as HTMLTextAreaElement)
        .value,
    ).toContain("AssumeLt(x, 6)");
  });

  it("dismisses definition suggestions without discarding the draft", async () => {
    render(<App />);
    await userEvent.click(screen.getByRole("button", { name: /^固定点 A/ }));
    const definition = screen.getByRole("combobox", { name: "定義" });
    await userEvent.clear(definition);
    await userEvent.type(definition, "Poi");
    expect(definition).toHaveAttribute("aria-expanded", "true");

    await userEvent.keyboard("{Escape}");

    expect(definition).toHaveValue("Poi");
    expect(definition).toHaveAttribute("aria-expanded", "false");
  });

  it("renders diagram labels as collision-backed KaTeX instead of SVG text", () => {
    const { container } = render(<App />);
    const labels = container.querySelectorAll("svg .canvas-math-label");
    expect(labels.length).toBeGreaterThanOrEqual(2);
    expect(container.querySelectorAll("svg .canvas-math-label .katex").length).toBe(labels.length);
    expect(container.querySelector("svg .geometry-point > text")).toBeNull();
  });

  it("closes the contextual keyboard when its expression field unmounts", async () => {
    render(<App />);
    const target = screen.getByRole("textbox", { name: "ターゲット式" });
    await userEvent.click(target);
    expect(target).toHaveAttribute(
      "aria-describedby",
      "math-keyboard-status",
    );
    await userEvent.click(screen.getByRole("tab", { name: "V15 JSON" }));
    await waitFor(() =>
      expect(
        screen.queryByRole("region", { name: "数式キーボード" }),
      ).not.toBeInTheDocument(),
    );

    await userEvent.click(screen.getByRole("tab", { name: "ターゲット" }));
    const definition = screen.getByRole("combobox", { name: "定義" });
    await userEvent.click(definition);
    expect(definition).toHaveAttribute(
      "aria-describedby",
      "math-keyboard-status",
    );
    await userEvent.click(screen.getByRole("tab", { name: "スタイル" }));
    await waitFor(() =>
      expect(
        screen.queryByRole("region", { name: "数式キーボード" }),
      ).not.toBeInTheDocument(),
    );
  });

  it("clears the active expression when moving to ordinary controls or opening the catalog", async () => {
    render(<App />);
    await userEvent.click(screen.getByRole("button", { name: "代数" }));
    await userEvent.click(screen.getByRole("button", { name: "条件を追加" }));
    const condition = screen.getByRole("combobox", { name: "条件 1" });
    const originalCondition = (condition as HTMLInputElement).value;
    await userEvent.click(condition);
    expect(
      screen.getByRole("region", { name: "数式キーボード" }),
    ).toBeInTheDocument();

    await userEvent.click(screen.getByRole("spinbutton", { name: "上限時間 (秒)" }));
    expect(
      screen.queryByRole("region", { name: "数式キーボード" }),
    ).not.toBeInTheDocument();
    expect(condition).toHaveValue(originalCondition);

    await userEvent.click(condition);
    await userEvent.click(screen.getByRole("button", { name: "ツール" }));
    await userEvent.click(
      screen.getByRole("button", { name: "すべてのV15ツールを開く" }),
    );
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(
      screen.queryByRole("region", { name: "数式キーボード" }),
    ).not.toBeInTheDocument();
    const definition = screen.getByRole("combobox", { name: "V15定義式" });
    await userEvent.click(definition);
    expect(
      screen.getByRole("region", { name: "数式キーボード" }),
    ).toBeInTheDocument();
  });

  it("routes point-valued catalog tools by their contract instead of their visual category", async () => {
    render(<App />);
    await userEvent.click(screen.getByRole("tab", { name: "V15 JSON" }));
    const setup = {
      task: "solve", id: "center-routing", variables: { names: [] },
      construction: [{ name: "O", expr: "Point(0, 0)" }, { name: "R", expr: "Point(2, 0)" }, { name: "c", expr: "CircleThroughPoint(O, R)" }],
      constraints: [], guards: [], answer: "Radius(c)", post_process: "",
    };
    fireEvent.change(screen.getByRole("textbox", { name: "V15 JSON" }), { target: { value: JSON.stringify(setup) } });
    await userEvent.click(screen.getByRole("button", { name: "JSONを適用" }));
    await userEvent.click(screen.getByRole("button", { name: "すべてのV15ツールを開く" }));
    await userEvent.click(screen.getByRole("button", { name: /円の中心/ }));
    await userEvent.click(screen.getByRole("button", { name: "図から引数を選ぶ" }));
    await userEvent.click(document.querySelector('[data-object="c"]')!);

    expect(screen.getByDisplayValue("Center(c)")).toBeInTheDocument();
    expect(document.querySelector('[data-object="c2"]')).toHaveAttribute("data-freedom", "derived");
    expect(screen.queryByRole("region", { name: "測定値" })).not.toBeInTheDocument();
  });

  it("adds a condition even after a construction ID was cleared", async () => {
    render(<App />);
    await userEvent.click(screen.getByRole("button", { name: "すべてのV15ツールを開く" }));
    await userEvent.clear(screen.getByLabelText("オブジェクトID"));
    await userEvent.click(screen.getByRole("button", { name: /円上/ }));
    expect(screen.queryByLabelText("オブジェクトID")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "条件として追加" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "条件 1" })).toHaveValue("OnCircle(P, c) = 0");
  });

  it("inserts equations with the tabbed on-screen math keyboard", async () => {
    render(<App />);
    await userEvent.click(screen.getByRole("button", { name: "代数" }));
    await userEvent.click(screen.getByRole("button", { name: "条件を追加" }));
    const input = screen.getByRole("combobox", { name: "条件 1" });
    await userEvent.clear(input);
    await userEvent.click(input);
    const keyboard = screen.getByRole("region", { name: "数式キーボード" });
    await userEvent.click(within(keyboard).getByRole("button", { name: "x" }));
    await userEvent.click(within(keyboard).getByRole("button", { name: "<" }));
    await userEvent.click(within(keyboard).getByRole("button", { name: "6" }));
    expect(input).toHaveValue("x < 6");
    await userEvent.click(within(keyboard).getByRole("button", { name: "確定" }));
    const committedInput = screen.getByRole("combobox", { name: "条件 1" });
    expect(committedInput).toHaveValue("x < 6");

    await userEvent.click(committedInput);
    const reopenedKeyboard = screen.getByRole("region", { name: "数式キーボード" });
    await userEvent.click(within(reopenedKeyboard).getByRole("tab", { name: "f(x)" }));
    expect(within(reopenedKeyboard).getByRole("button", { name: "Angle" })).toBeInTheDocument();
    await userEvent.clear(committedInput);
    await userEvent.click(within(reopenedKeyboard).getByRole("button", { name: "Point" }));
    expect(committedInput).toHaveValue("Point()");
    await waitFor(() => expect(committedInput).toHaveFocus());
    const functionTab = within(reopenedKeyboard).getByRole("tab", { name: "f(x)" });
    expect(functionTab).toHaveAttribute("tabindex", "0");
    functionTab.focus();
    await userEvent.keyboard("{ArrowRight}");
    await waitFor(() => expect(within(reopenedKeyboard).getByRole("tab", { name: "ABC" })).toHaveFocus());
    await userEvent.click(within(reopenedKeyboard).getByRole("button", { name: "数式キーボードを閉じる" }));
    expect(screen.queryByRole("region", { name: "数式キーボード" })).not.toBeInTheDocument();
    await waitFor(() => expect(committedInput).toHaveFocus());
    expect(screen.queryByRole("region", { name: "数式キーボード" })).not.toBeInTheDocument();
    expect(committedInput).not.toHaveAttribute("aria-describedby");
    await userEvent.click(committedInput);
    expect(screen.getByRole("region", { name: "数式キーボード" })).toBeInTheDocument();
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("region", { name: "数式キーボード" })).not.toBeInTheDocument();
    expect(committedInput).toHaveFocus();
  });

  it("keeps the catalog keyboard inside its modal and canonicalizes pi", async () => {
    render(<App />);
    await userEvent.click(screen.getByRole("button", { name: "すべてのV15ツールを開く" }));
    const dialog = screen.getByRole("dialog");
    const definition = screen.getByRole("combobox", { name: "V15定義式" });
    await userEvent.clear(definition);
    await userEvent.type(definition, "Point(");
    const keyboard = screen.getByRole("region", { name: "数式キーボード" });
    expect(dialog).toContainElement(keyboard);
    await userEvent.click(within(keyboard).getByRole("button", { name: "π" }));
    await waitFor(() => expect(definition).toHaveFocus());
    expect(definition).toHaveValue("Point(π");
    fireEvent.change(definition, { target: { value: "Point(π, 0)" } });
    await userEvent.keyboard("{Escape}");
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "数式キーボード" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "構成に追加" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "数式キーボード" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "V15 JSON" }));
    expect((screen.getByRole("textbox", { name: "V15 JSON" }) as HTMLTextAreaElement).value).toContain('"expr": "Point(pi, 0)"');
  });

  it("opens the math keyboard from the target formula and canonicalizes pi", async () => {
    render(<App />);
    const target = screen.getByRole("textbox", { name: "ターゲット式" });
    await userEvent.click(target);
    await userEvent.clear(target);
    const keyboard = screen.getByRole("region", { name: "数式キーボード" });
    await userEvent.click(within(keyboard).getByRole("button", { name: "π" }));
    expect(target).toHaveValue("π");
    await userEvent.click(screen.getByRole("button", { name: "ターゲットに設定" }));
    await userEvent.click(screen.getByRole("tab", { name: "V15 JSON" }));
    expect((screen.getByRole("textbox", { name: "V15 JSON" }) as HTMLTextAreaElement).value).toContain('"answer": "pi"');
  });

  it("keeps the solver target caret aligned while canonicalizing pi", async () => {
    render(<App />);
    const solver = screen.getByRole("complementary", { name: "プロパティとsolver" });
    const target = within(solver).getByRole("textbox", { name: "ターゲット" });
    await userEvent.click(target);
    await userEvent.clear(target);
    const keyboard = screen.getByRole("region", { name: "数式キーボード" });
    await userEvent.click(within(keyboard).getByRole("button", { name: "π" }));
    await userEvent.click(within(keyboard).getByRole("button", { name: "÷" }));
    expect(target).toHaveValue("π/");
    fireEvent.change(target, { target: { value: "π/2" } });
    expect(target).toHaveValue("π/2");
    await userEvent.click(screen.getByRole("tab", { name: "V15 JSON" }));
    expect((screen.getByRole("textbox", { name: "V15 JSON" }) as HTMLTextAreaElement).value).toContain('"answer": "pi/2"');
  });

  it("reveals a newly added inequality in the visible conditions list", async () => {
    render(<App />);
    await userEvent.click(screen.getByRole("button", { name: "すべてのV15ツールを開く" }));
    await userEvent.click(screen.getByRole("button", { name: /未満/ }));
    const expression = screen.getByRole("combobox", { name: "条件式" });
    expect(expression).toHaveValue("lhs < rhs");
    fireEvent.change(expression, { target: { value: "Distance(A, B) < 6" } });
    await userEvent.click(screen.getByRole("button", { name: "条件として追加" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "代数" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("等式・不等式をまとめて表示します。内部形式の違いを意識せず、数式のまま編集できます。")).toBeVisible();
    expect(screen.getByRole("combobox", { name: "条件 1" })).toHaveValue("Distance(A, B) < 6");
    await userEvent.click(screen.getByRole("tab", { name: "V15 JSON" }));
    expect((screen.getByRole("textbox", { name: "V15 JSON" }) as HTMLTextAreaElement).value).toContain("AssumeLt(Distance(A, B), 6)");
    await userEvent.click(screen.getByRole("button", { name: "条件 1を削除" }));
    expect(screen.queryByRole("combobox", { name: "条件 1" })).not.toBeInTheDocument();
  });

  it("edits an object's name and definition from the property inspector", async () => {
    render(<App />);
    await userEvent.click(screen.getByRole("button", { name: /^固定点 A/ }));
    const name = screen.getByRole("textbox", { name: "名前" });
    await userEvent.clear(name); await userEvent.type(name, "P{Enter}");
    expect(document.querySelector('[data-object="P"]')).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "ターゲット" })).toHaveValue("Distance(P, B)");

    const definition = screen.getByRole("combobox", { name: "定義" });
    await userEvent.clear(definition); await userEvent.type(definition, "Point(1, 2)");
    await userEvent.keyboard("{Control>}{Enter}{/Control}");
    expect(screen.getByRole("combobox", { name: "定義" })).toHaveValue("Point(1, 2)");

    await userEvent.click(screen.getByRole("button", { name: "元に戻す" }));
    expect(screen.getByRole("combobox", { name: "定義" })).toHaveValue("Point(0, 0)");
  });

  it("keeps a solve result when imported blank expressions are sanitized", async () => {
    let submitted: Record<string, unknown> | undefined;
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method || "GET";
      if (url.endsWith("/api/v1/dsl/catalog")) return new Response(JSON.stringify(catalog));
      if (url.endsWith("/api/v1/doctor")) return new Response(JSON.stringify({ ok: true }));
      if (url.endsWith("/api/v1/session")) return new Response(JSON.stringify({ status: "ready" }));
      if (url.endsWith("/api/v1/preview")) return new Response(JSON.stringify({ validation: { valid: true, issues: [] } }));
      if (url.endsWith("/api/v1/solves") && method === "POST") {
        submitted = JSON.parse(String(init?.body));
        return new Response(JSON.stringify({ job_id: "clean-job" }), { status: 202 });
      }
      if (url.endsWith("/api/v1/solves/clean-job"))
        return new Response(JSON.stringify({
          state: "completed",
          result: {
            status: "answers_found_completeness_unknown",
            engine_id: "test-engine",
            engine_hash: "test-hash",
            problem_sha256: "problem-hash",
            elapsed_seconds: 0.01,
            warnings: [],
            answers: [],
          },
        }));
      throw new Error(`unexpected fetch ${method} ${url}`);
    }));
    render(<App />);
    await userEvent.click(screen.getByRole("tab", { name: "V15 JSON" }));
    const editor = screen.getByRole("textbox", { name: "V15 JSON" });
    const imported = JSON.parse((editor as HTMLTextAreaElement).value);
    imported.guards = [""];
    fireEvent.change(editor, { target: { value: JSON.stringify(imported) } });
    await userEvent.click(screen.getByRole("button", { name: "JSONを適用" }));
    await userEvent.click(screen.getByRole("button", { name: "解く" }));

    await waitFor(() => expect(screen.getByText("完了")).toBeInTheDocument(), {
      timeout: 2500,
    });
    expect((submitted?.problem as { guards: string[] }).guards).toEqual([]);
    expect(
      screen.queryByText(/計算中に問題が変更されたため/),
    ).not.toBeInTheDocument();
  });

  it("runs the opt-in adaptive candidate and renders adaptive progress", async () => {
    let submitted: Record<string, unknown> | undefined;
    let polls = 0;
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method || "GET";
      if (url.endsWith("/api/v1/dsl/catalog")) return new Response(JSON.stringify(catalog));
      if (url.endsWith("/api/v1/doctor")) return new Response(JSON.stringify({ ok: true }));
      if (url.endsWith("/api/v1/session")) return new Response(JSON.stringify({ status: "ready" }));
      if (url.endsWith("/api/v1/preview")) return new Response(JSON.stringify({ validation: { valid: true, issues: [] } }));
      if (url.endsWith("/api/v1/solves") && method === "POST") {
        submitted = JSON.parse(String(init?.body));
        return new Response(JSON.stringify({ job_id: "adaptive-job" }), { status: 202 });
      }
      if (url.endsWith("/api/v1/solves/adaptive-job")) {
        polls += 1;
        if (polls === 1)
          return new Response(JSON.stringify({
            state: "running",
            progress: {
              phase: "extension",
              completed_starts: 128,
              total_starts: 256,
              extension_batch: 3,
              stability_count: 2,
              used_cores: 4,
              elapsed_seconds: 210,
              max_time_seconds: 900,
            },
            result: null,
          }));
        return new Response(JSON.stringify({
          state: "completed",
          result: {
            status: "answers_found_completeness_unknown",
            engine_id: "champion-v2",
            engine_hash: "test-hash",
            engine_variant: "optimized",
            problem_sha256: "problem-hash",
            requested_resources: { max_time_seconds: 900, cores: "auto", seed: 0 },
            used_resources: { max_time_seconds: 900, cores: 4, seed: 0 },
            elapsed_seconds: 224.5,
            work_checkpoint: {
              completed_start_ordinals: [0, 1, 2, 3],
              pending_start_ordinals: [],
              extension_batch: 4,
              stability_count: 3,
            },
            termination_reason: "extension_stable",
            warnings: [],
            answers: [],
          },
        }));
      }
      throw new Error(`unexpected fetch ${method} ${url}`);
    }));

    render(<App />);
    await userEvent.click(screen.getByText("詳細設定"));
    await userEvent.click(screen.getByRole("radio", { name: /適応/ }));
    expect(screen.getByRole("spinbutton", { name: "上限時間 (秒)" })).toHaveValue(900);
    expect(screen.getByRole("combobox", { name: "使用コア" })).toHaveValue("auto");
    await userEvent.click(screen.getByRole("button", { name: "解く" }));

    await waitFor(() => expect(screen.getByText("追加探索")).toBeInTheDocument(), {
      timeout: 2500,
    });
    expect(screen.getByText("128 / 256")).toBeInTheDocument();
    expect(screen.getByText("#3")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();
    await waitFor(
      () => expect(screen.getAllByText("追加探索が安定したため終了").length).toBeGreaterThan(0),
      { timeout: 2500 },
    );
    expect(submitted?.options).toEqual({
      engine: "optimized",
      run_mode: "adaptive",
      max_time_seconds: 900,
      cores: "auto",
      seed: 0,
    });
    expect(submitted?.options).not.toHaveProperty("time_limit_seconds");
    expect(screen.getByText("champion-v2 · optimized")).toBeInTheDocument();
    expect(screen.getAllByText("224.500秒 / 900秒").length).toBeGreaterThan(0);
  });

  it("offers fixed-time and frozen reference execution as advanced choices", async () => {
    render(<App />);
    await userEvent.click(screen.getByText("詳細設定"));
    const adaptive = screen.getByRole("radio", { name: /適応/ });
    const fixed = screen.getByRole("radio", { name: /固定時間/ });
    const reference = screen.getByRole("radio", { name: /参照版/ });
    expect(reference).toBeChecked();

    await userEvent.click(adaptive);
    expect(screen.getAllByText(/未認定候補・実験用/).length).toBeGreaterThan(0);
    await userEvent.click(fixed);
    expect(
      screen.getByText("固定時間（未認定候補）", {
        selector: ".solver-profile-summary strong",
      }),
    ).toBeInTheDocument();
    await userEvent.click(reference);
    expect(screen.getByText("凍結版 · 180秒 · 1コア")).toBeInTheDocument();
    expect(screen.getByRole("spinbutton", { name: "上限時間 (秒)" })).toBeDisabled();
    expect(screen.getByRole("combobox", { name: "使用コア" })).toBeDisabled();
  });

  it("applies the promoted backend qualification tuple atomically", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/v1/dsl/catalog")) return new Response(JSON.stringify(catalog));
      if (url.endsWith("/api/v1/doctor")) return new Response(JSON.stringify({ ok: true }));
      if (url.endsWith("/api/v1/qualification")) return new Response(JSON.stringify({ default_engine: "optimized", promotion_status: "qualified" }));
      if (url.endsWith("/api/v1/session")) return new Response(JSON.stringify({ status: "ready" }));
      throw new Error(`unexpected fetch ${url}`);
    }));

    render(<App />);
    await waitFor(() =>
      expect(
        screen.getByText("適応実行", { selector: ".solver-profile-summary strong" }),
      ).toBeInTheDocument(),
    );
    expect(screen.getByRole("spinbutton", { name: "上限時間 (秒)" })).toHaveValue(900);
    expect(screen.getByRole("combobox", { name: "使用コア" })).toHaveValue("auto");
    await userEvent.click(screen.getByText("詳細設定"));
    expect(screen.getByRole("radio", { name: /適応/ })).toBeChecked();
  });

  it("cancels a job that is created after the user cancels the pending POST", async () => {
    let releasePost!: () => void;
    const postGate = new Promise<void>((resolve) => { releasePost = resolve; });
    const calls: Array<{ url: string; method: string }> = [];
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input); const method = init?.method || "GET"; calls.push({ url, method });
      if (url.endsWith("/api/v1/dsl/catalog")) return new Response(JSON.stringify(catalog));
      if (url.endsWith("/api/v1/doctor")) return new Response(JSON.stringify({ ok: true }));
      if (url.endsWith("/api/v1/session")) return new Response(JSON.stringify({ status: "ready" }));
      if (url.endsWith("/api/v1/preview")) return new Response(JSON.stringify({ validation: { valid: true, issues: [] } }));
      if (url.endsWith("/api/v1/solves") && method === "POST") { await postGate; return new Response(JSON.stringify({ job_id: "late-job" }), { status: 202 }); }
      if (url.endsWith("/api/v1/solves/late-job") && method === "DELETE") return new Response(JSON.stringify({ state: "cancelled" }));
      throw new Error(`unexpected fetch ${method} ${url}`);
    }));
    render(<App />);
    await userEvent.click(screen.getByRole("button", { name: "解く" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "中止" })).toBeEnabled());
    await userEvent.click(screen.getByRole("button", { name: "中止" }));
    releasePost();
    await waitFor(() => expect(calls).toContainEqual({ url: "/api/v1/solves/late-job", method: "DELETE" }));
    expect(screen.getAllByText("中止").length).toBeGreaterThan(0);
  });
});
