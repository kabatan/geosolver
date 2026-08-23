import { describe, expect, it } from "vitest";
import { evaluateConstrainedScene, evaluateScalarExpression, evaluateScene, formatPointExpression, nearestIntersection, nearestLineIntersection, parseExpression, screenToWorld, uniqueName, worldToScreen } from "./geometry";
import { guidedExpression, guidedSpecs } from "./authoring";

describe("geometry preview", () => {
  it("derives every visible primitive from GeoSolver construction order", () => {
    const scene = evaluateScene([
      { name: "A", expr: "Point(0, 0)" },
      { name: "B", expr: "Point(3, 4)" },
      { name: "s", expr: "Segment(A, B)" },
      { name: "c", expr: "CircleThroughPoint(A, B)" },
      { name: "p", expr: "Polygon([A, B, PointMissing])" },
    ]);
    expect(scene.items.map((item) => item.name)).toEqual(["A", "B", "s", "c"]);
    expect(scene.byName.get("c")).toMatchObject({ kind: "circle", radius: 5 });
    expect(scene.warnings).toHaveLength(1);
  });

  it("parses canonical Polygon lists without executing source", () => {
    expect(parseExpression("Polygon([A, B, C])")).toMatchObject({ type: "call", name: "Polygon" });
    expect(() => parseExpression("Point(0, 0); globalThis.bad()" )).toThrow();
  });

  it("round-trips viewport coordinates and creates stable point text", () => {
    const viewport = { width: 1000, height: 700, center: { x: 2, y: -1 }, pixelsPerUnit: 50 };
    const world = { x: -3.25, y: 4.5 };
    expect(screenToWorld(worldToScreen(world, viewport), viewport)).toEqual(world);
    expect(formatPointExpression({ x: -0, y: 2.5 }, 3)).toBe("Point(0, 2.5)");
    expect(uniqueName(["P", "P2", "P3"])).toBe("P4");
  });

  it("uses UI-only values to preview free variables and common guided constructions", () => {
    const scene = evaluateScene([
      { name: "A", expr: "Point(Ax, Ay)" },
      { name: "B", expr: "Point(4, 0)" },
      { name: "C", expr: "Point(0, 3)" },
      { name: "bisector", expr: "PerpendicularBisector(A, B)" },
      { name: "centroid", expr: "Centroid(A, B, C)" },
      { name: "base", expr: "Line(A, B)" },
      { name: "altitude", expr: "PerpendicularLine(C, base)" },
      { name: "X", expr: "Intersect(bisector, base)" },
    ], { Ax: 0, Ay: 0 });
    expect(scene.warnings).toEqual([]);
    expect(scene.byName.get("A")).toMatchObject({ kind: "point", position: { x: 0, y: 0 } });
    expect(scene.byName.get("centroid")).toMatchObject({ kind: "point", position: { x: 4 / 3, y: 1 } });
    expect(scene.byName.get("X")).toMatchObject({ kind: "point" });
  });

  it("previews one-dimensional free points on a segment, line, and circle", () => {
    const scene = evaluateScene([
      { name: "A", expr: "Point(0, 0)" }, { name: "B", expr: "Point(4, 0)" },
      { name: "line", expr: "Line(A, B)" }, { name: "circle", expr: "Circle(A, 2)" },
      { name: "S", expr: "PointOnSegment(A, B, ts)" },
      { name: "L", expr: "PointOnLine(line, tl)" },
      { name: "C", expr: "PointOnCircle(circle, tc)" },
    ], { ts: 0.25, tl: 3, tc: 0.25 });
    expect(scene.warnings).toEqual([]);
    expect(scene.byName.get("S")).toMatchObject({ position: { x: 1, y: 0 } });
    // GeoSolver Line(A,B) coefficients orient PointOnLine toward A-B.
    expect(scene.byName.get("L")).toMatchObject({ position: { x: -3, y: 0 } });
    expect(scene.byName.get("C")).toMatchObject({ position: { x: expect.closeTo(0), y: 2 } });
  });

  it("projects coordinate-free points onto their GeoSolver incidence carrier", () => {
    const scene = evaluateConstrainedScene(
      [
        { name: "I_A", expr: "Point(0, 0)" },
        { name: "c", expr: "Point(2, 4)" },
        { name: "I_Ac", expr: "Line(I_A, c)" },
        { name: "P", expr: "Point(Px, Py)" },
        { name: "Q", expr: "Midpoint(P, c)" },
      ],
      [{ def: "OnLine(P, I_Ac)", value: 0 }],
      ["Px", "Py"],
      { Px: 1.4, Py: 1 },
    );
    expect(scene.byName.get("P")).toMatchObject({ kind: "point", position: { x: expect.closeTo(0.68), y: expect.closeTo(1.36) } });
    expect(scene.byName.get("Q")).toMatchObject({ kind: "point", position: { x: expect.closeTo(1.34), y: expect.closeTo(2.68) } });
  });

  it("uses the same incidence projection for circles and finite segments", () => {
    const scene = evaluateConstrainedScene(
      [
        { name: "O", expr: "Point(0, 0)" },
        { name: "R", expr: "Point(2, 0)" },
        { name: "circle", expr: "CircleThroughPoint(O, R)" },
        { name: "C", expr: "Point(Cx, Cy)" },
        { name: "S", expr: "Point(Sx, Sy)" },
      ],
      [
        { def: "OnCircle(C, circle)", value: 0 },
        { def: "OnSegment(S, O, R)", value: 0 },
      ],
      ["Cx", "Cy", "Sx", "Sy"],
      { Cx: 1, Cy: 1, Sx: 3, Sy: 1 },
    );
    expect(scene.byName.get("C")).toMatchObject({ position: { x: expect.closeTo(Math.sqrt(2)), y: expect.closeTo(Math.sqrt(2)) } });
    expect(scene.byName.get("S")).toMatchObject({ position: { x: 2, y: 0 } });
  });

  it("keeps relational intersection points on both carriers after upstream movement", () => {
    const construction = [
      { name: "O", expr: "Point(0, 0)" },
      { name: "R", expr: "Point(2, 0)" },
      { name: "circle", expr: "CircleThroughPoint(O, R)" },
      { name: "A", expr: "Point(lineX, -3)" },
      { name: "B", expr: "Point(lineX, 3)" },
      { name: "I_Ac", expr: "Line(A, B)" },
      { name: "P", expr: "PointOnCircle(circle, tP)" },
      { name: "Q", expr: "Midpoint(O, P)" },
    ];
    const constraints = [{ def: "OnLine(P, I_Ac)", value: 0 }];
    const first = evaluateConstrainedScene(construction, constraints, ["lineX", "tP"], { lineX: 1, tP: 0.2 });
    const moved = evaluateConstrainedScene(construction, constraints, ["lineX", "tP"], { lineX: 1.5, tP: 0.2 });
    expect(first.byName.get("P")).toMatchObject({ position: { x: expect.closeTo(1), y: expect.closeTo(Math.sqrt(3)) } });
    expect(moved.byName.get("P")).toMatchObject({ position: { x: expect.closeTo(1.5), y: expect.closeTo(Math.sqrt(1.75)) } });
    expect(moved.byName.get("Q")).toMatchObject({ position: { x: expect.closeTo(0.75), y: expect.closeTo(Math.sqrt(1.75) / 2) } });
  });

  it("previews line-like guided arguments after canonical inline Line conversion", () => {
    const scene = evaluateScene([
      { name: "A", expr: "Point(0, 0)" }, { name: "B", expr: "Point(4, 0)" }, { name: "P", expr: "Point(1, 2)" },
      { name: "s", expr: "Segment(A, B)" },
      { name: "parallel", expr: "ParallelLine(Line(A, B), P)" },
      { name: "perpendicular", expr: "PerpendicularLine(Line(A, B), P)" },
    ]);
    expect(scene.warnings).toEqual([]);
    expect(scene.byName.get("parallel")).toMatchObject({ kind: "line", anchor: { x: 1, y: 2 } });
    expect(scene.byName.get("perpendicular")).toMatchObject({ kind: "line", anchor: { x: 1, y: 2 } });
  });

  it("finds nearby visible crossings while respecting segment and ray bounds", () => {
    const scene = evaluateScene([
      { name: "A", expr: "Point(-2, 0)" }, { name: "B", expr: "Point(2, 0)" },
      { name: "C", expr: "Point(0, -2)" }, { name: "D", expr: "Point(0, 2)" },
      { name: "horizontal", expr: "Segment(A, B)" }, { name: "vertical", expr: "Ray(C, D)" },
    ]);
    expect(nearestLineIntersection(scene.items, { x: 0.08, y: -0.04 }, 0.2)).toMatchObject({
      first: "horizontal", second: "vertical", position: { x: 0, y: 0 },
    });
    expect(nearestLineIntersection(scene.items, { x: 3, y: 0 }, 0.2)).toBeUndefined();
  });

  it("finds both line-circle branches and respects finite carrier bounds", () => {
    const scene = evaluateScene([
      { name: "O", expr: "Point(0, 0)" }, { name: "R", expr: "Point(2, 0)" },
      { name: "A", expr: "Point(-3, 0)" }, { name: "B", expr: "Point(3, 0)" },
      { name: "shortA", expr: "Point(-1, 0)" }, { name: "shortB", expr: "Point(1, 0)" },
      { name: "circle", expr: "CircleThroughPoint(O, R)" },
      { name: "diameter", expr: "Segment(A, B)" }, { name: "short", expr: "Segment(shortA, shortB)" },
    ]);
    const candidate = nearestIntersection(scene.items, { x: 2.03, y: 0.02 }, 0.1);
    expect(candidate).toMatchObject({ first: "circle", second: "diameter", position: { x: 2, y: 0 } });
    expect(candidate?.alternatives).toEqual([{ x: -2, y: 0 }, { x: 2, y: 0 }]);
    expect(nearestIntersection(scene.items.filter((item) => !["diameter", "A", "B"].includes(item.name)), { x: 2, y: 0 }, 0.1)).toBeUndefined();
  });

  it("finds both circle-circle branches", () => {
    const scene = evaluateScene([
      { name: "O1", expr: "Point(0, 0)" }, { name: "O2", expr: "Point(2, 0)" },
      { name: "c1", expr: "Circle(O1, 2)" }, { name: "c2", expr: "Circle(O2, 2)" },
    ]);
    const candidate = nearestIntersection(scene.items, { x: 1, y: Math.sqrt(3) }, 0.01);
    expect(candidate).toMatchObject({ first: "c1", second: "c2", position: { x: 1, y: expect.closeTo(Math.sqrt(3)) } });
    expect(candidate?.alternatives).toHaveLength(2);
    expect(candidate?.alternatives[1]).toEqual({ x: 1, y: expect.closeTo(-Math.sqrt(3)) });
  });

  it("previews explicit exclude, near, and far intersection selectors", () => {
    const scene = evaluateScene([
      { name: "O", expr: "Point(0, 0)" }, { name: "A", expr: "Point(2, 0)" },
      { name: "Q", expr: "Point(-3, 0)" }, { name: "L", expr: "Point(-3, 0)" },
      { name: "R", expr: "Point(3, 0)" }, { name: "circle", expr: "Circle(O, 2)" },
      { name: "line", expr: "Line(L, R)" },
      { name: "excluded", expr: "Intersect(line, circle, exclude=A)" },
      { name: "near", expr: "Intersect(line, circle, near=Q)" },
      { name: "far", expr: "Intersect(line, circle, far=Q)" },
    ]);
    expect(scene.warnings).toEqual([]);
    expect(scene.byName.get("excluded")).toMatchObject({ kind: "point", position: { x: -2, y: 0 } });
    expect(scene.byName.get("near")).toMatchObject({ kind: "point", position: { x: -2, y: 0 } });
    expect(scene.byName.get("far")).toMatchObject({ kind: "point", position: { x: 2, y: 0 } });
  });

  it("does not guess a branch for an unselected two-intersection expression", () => {
    const scene = evaluateScene([
      { name: "O", expr: "Point(0, 0)" }, { name: "A", expr: "Point(-3, 0)" },
      { name: "B", expr: "Point(3, 0)" }, { name: "circle", expr: "Circle(O, 2)" },
      { name: "line", expr: "Line(A, B)" }, { name: "X", expr: "Intersect(line, circle)" },
    ]);
    expect(scene.byName.has("X")).toBe(false);
    expect(scene.warnings.at(-1)?.message).toContain("selector");
  });

  it("keeps a perpendicular foot constrained after its source points move", () => {
    const constructions = [
      { name: "P2", expr: "Point(x2, y2)" }, { name: "P3", expr: "Point(x3, y3)" },
      { name: "i", expr: "Point(xi, yi)" }, { name: "s", expr: "Segment(P2, P3)" },
      { name: "P4", expr: "FootOfPerpendicular(i, Line(P2, P3))" },
    ];
    const first = evaluateScene(constructions, { x2: -2, y2: 0, x3: 2, y3: 0, xi: 1, yi: 3 });
    expect(first.byName.get("P4")).toMatchObject({ kind: "point", position: { x: 1, y: 0 } });
    const moved = evaluateScene(constructions, { x2: -1, y2: -1, x3: 3, y3: 1, xi: 0, yi: 4 });
    const foot = moved.byName.get("P4"); const p2 = moved.byName.get("P2"); const p3 = moved.byName.get("P3");
    expect(foot?.kind).toBe("point"); expect(p2?.kind).toBe("point"); expect(p3?.kind).toBe("point");
    if (foot?.kind === "point" && p2?.kind === "point" && p3?.kind === "point") {
      const line = { x: p3.position.x - p2.position.x, y: p3.position.y - p2.position.y };
      expect((foot.position.x - p2.position.x) * line.y - (foot.position.y - p2.position.y) * line.x).toBeCloseTo(0, 10);
    }
  });

  it("evaluates angle and ratio measurements from the live scene", () => {
    const scene = evaluateScene([{ name: "A", expr: "Point(1, 0)" }, { name: "B", expr: "Point(0, 0)" }, { name: "C", expr: "Point(0, 1)" }, { name: "D", expr: "Point(0, 2)" }]);
    expect(evaluateScalarExpression("Angle(A, B, C)", scene)).toBeCloseTo(Math.PI / 2);
    expect(evaluateScalarExpression("Distance(A, B) / Distance(B, D)", scene)).toBeCloseTo(0.5);
  });

  it("previews every construction exposed by the guided authoring contract", () => {
    const base = [
      { name: "A", expr: "Point(0, 0)" }, { name: "B", expr: "Point(4, 0)" },
      { name: "C", expr: "Point(1, 3)" }, { name: "D", expr: "Point(0, 3)" },
      { name: "E", expr: "Point(2, 0)" },
      { name: "l1", expr: "Line(A, B)" }, { name: "l2", expr: "Line(A, C)" }, { name: "l3", expr: "Line(C, D)" },
      { name: "s", expr: "Segment(A, B)" }, { name: "c1", expr: "Circle(A, 2)" }, { name: "c2", expr: "Circle(B, 3)" },
    ];
    const argumentsByTool: Record<string, { names: string[]; parameters?: string[] }> = {
      PointOnLine: { names: ["l1"], parameters: ["t"] }, PointOnSegment: { names: ["A", "B"], parameters: ["t"] }, PointOnCircle: { names: ["c1"], parameters: ["t"] },
      Segment: { names: ["A", "B"] }, Line: { names: ["A", "C"] }, Ray: { names: ["A", "B"] }, Vector: { names: ["A", "B"] }, Midpoint: { names: ["A", "B"] },
      ClosestPoint: { names: ["C", "l1"] }, FootOfPerpendicular: { names: ["C", "l1"] }, PerpendicularBisector: { names: ["A", "B"] },
      CircleThroughPoint: { names: ["A", "B"] }, CircleThroughThreePoints: { names: ["A", "B", "C"] }, Arc: { names: ["c1", "B", "C", "D"] }, ContactPoint: { names: ["c1", "l1"] }, RegularPolygon: { names: ["A", "B"] },
      Intersect: { names: ["l1", "l2"] }, Intersection: { names: ["l1", "l2"] }, IntersectLines: { names: ["l1", "l2"] },
      ParallelLine: { names: ["l1", "C"] }, PerpendicularLine: { names: ["l1", "C"] }, AngleBisector: { names: ["A", "C", "B"] }, Reflect: { names: ["C", "l1"] },
      Centroid: { names: ["A", "B", "C"] }, Circumcenter: { names: ["A", "B", "C"] }, Incenter: { names: ["A", "B", "C"] }, Orthocenter: { names: ["A", "B", "C"] },
      NinePointCenter: { names: ["A", "B", "C"] }, Excenter: { names: ["A", "B", "C"] }, FermatPoint: { names: ["A", "B", "C"] }, Incircle: { names: ["A", "B", "C"] }, Circumcircle: { names: ["A", "B", "C"] }, Excircle: { names: ["A", "B", "C"] }, NinePointCircle: { names: ["A", "B", "C"] }, IncircleContactPoint: { names: ["A", "B", "C"] }, IsodynamicPoint: { names: ["A", "B", "C"] },
      SymmedianPoint: { names: ["A", "B", "C"] }, GergonnePoint: { names: ["A", "B", "C"] }, NagelPoint: { names: ["A", "B", "C"] },
      FeuerbachPoint: { names: ["A", "B", "C"] }, Mittenpunkt: { names: ["A", "B", "C"] }, SpiekerCenter: { names: ["A", "B", "C"] },
      RadicalAxis: { names: ["c1", "c2"] }, Polar: { names: ["C", "c1"] }, TangentAtPoint: { names: ["E", "c1"] }, Pole: { names: ["l3", "c1"] }, Center: { names: ["c1"] },
    };
    const variables = { t: 0.25 };
    for (const [id, spec] of Object.entries(guidedSpecs())) {
      if (spec.output && spec.output !== "construction") continue;
      // This UI tool expands to named vertices plus a Polygon construction;
      // it intentionally is not represented by one preview expression.
      if (id === "InscribedPolygonVertices") continue;
      const sample = argumentsByTool[id];
      expect(sample, `${id} needs a contract sample`).toBeDefined();
      const expression = guidedExpression(id, sample.names, spec, sample.parameters);
      const scene = evaluateScene([...base, { name: "result", expr: expression }], variables);
      expect(scene.warnings, `${id}: ${expression}`).toEqual([]);
      expect(scene.byName.has("result"), `${id}: ${expression}`).toBe(true);
    }
  });

  it("uses typed overload resolution instead of positional guessing", () => {
    const scene = evaluateScene([
      { name: "A", expr: "Point(0, 0)" }, { name: "P", expr: "Point(2, 3)" }, { name: "Q", expr: "Point(1, 1)" },
      { name: "B", expr: "Point(4, 0)" }, { name: "line", expr: "Line(A, B)" }, { name: "circle", expr: "Circle(A, 2)" },
      { name: "footCanonical", expr: "FootOfPerpendicular(P, line)" }, { name: "footLegacy", expr: "FootOfPerpendicular(line, P)" },
      { name: "parallelCanonical", expr: "ParallelLine(line, P)" }, { name: "parallelLegacy", expr: "ParallelLine(P, line)" },
      { name: "closestCircle", expr: "ClosestPoint(P, circle)" }, { name: "reflectedInPoint", expr: "Reflect(P, Q)" },
    ]);
    expect(scene.warnings).toEqual([]);
    expect(scene.byName.get("footCanonical")).toMatchObject({ position: { x: 2, y: 0 } });
    expect(scene.byName.get("footLegacy")).toMatchObject({ position: { x: 2, y: 0 } });
    expect(scene.byName.get("reflectedInPoint")).toMatchObject({ position: { x: 0, y: -1 } });
    expect(scene.byName.get("closestCircle")).toMatchObject({ kind: "point" });
  });
});
