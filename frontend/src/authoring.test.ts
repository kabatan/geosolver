import { describe, expect, it } from "vitest";
import { acceptsSceneItem, directPointVariables, freePointDefinition, freedomOf, guidedExpression, guidedSpecFor, guidedSpecs, isFixedPointDefinition, parameterizedPoint } from "./authoring";
import type { SceneItem } from "./geometry";

describe("visual authoring semantics", () => {
  it("creates a V15 free point from two scalar variables", () => {
    const definition = freePointDefinition("P", { x: 1.5, y: -2 }, []);
    expect(definition).toEqual({ variables: ["Px", "Py"], expression: "Point(Px, Py)", preview: { Px: 1.5, Py: -2 } });
    expect(directPointVariables({ name: "P", expr: definition.expression }, definition.variables)).toEqual(["Px", "Py"]);
    expect(freedomOf({ name: "P", expr: definition.expression }, definition.variables)).toBe("free");
  });

  it("distinguishes fixed and derived constructions", () => {
    expect(isFixedPointDefinition({ name: "A", expr: "Point(-1, 2.5)" })).toBe(true);
    expect(freedomOf({ name: "A", expr: "Point(-1, 2.5)" }, [])).toBe("fixed");
    expect(freedomOf({ name: "M", expr: "Midpoint(A, B)" }, [])).toBe("derived");
  });

  it("builds guided expressions in diagram selection order", () => {
    const spec = guidedSpecFor("CircleThroughThreePoints")!;
    expect(spec.slots.map((slot) => slot.kind)).toEqual(["point", "point", "point"]);
    expect(guidedExpression("CircleThroughThreePoints", ["A", "B", "C"], spec)).toBe("CircleThroughThreePoints(A, B, C)");
  });

  it("recognizes one-parameter free points on carriers", () => {
    const spec = guidedSpecFor("PointOnSegment")!;
    expect(spec.parameters).toEqual([{ suffix: "t", initial: 0.5, boundUnit: true }]);
    expect(guidedExpression("PointOnSegment", ["A", "B"], spec, ["tP"])).toBe("PointOnSegment(A, B, tP)");
    expect(parameterizedPoint({ name: "P", expr: "PointOnSegment(A, B, tP)" }, ["tP"])).toEqual({ operation: "PointOnSegment", carriers: ["A", "B"], variable: "tP" });
    expect(parameterizedPoint({ name: "X", expr: "Point(xX, 0)" }, ["xX"])).toEqual({ operation: "PointOnAxis", carriers: [], variable: "xX", axis: "x" });
    expect(parameterizedPoint({ name: "Y", expr: "Point(0, yY)" }, ["yY"])).toEqual({ operation: "PointOnAxis", carriers: [], variable: "yY", axis: "y" });
  });

  it("requires actual lines and preserves canonical relation argument order", () => {
    const lineSpec = guidedSpecFor("PointOnLine")!;
    expect(guidedExpression("PointOnLine", ["lineAB"], lineSpec, ["tP"])).toBe("PointOnLine(lineAB, tP)");
    const parallel = guidedSpecFor("ParallelLine")!;
    expect(parallel.slots.map((slot) => slot.kind)).toEqual(["line", "point"]);
    expect(guidedExpression("ParallelLine", ["lineAB", "P"], parallel)).toBe("ParallelLine(lineAB, P)");
  });

  it("treats linear carriers naturally and restricts Length to segments", () => {
    const segment = { kind: "segment", name: "s", source: "Segment(A, B)", start: { x: 0, y: 0 }, end: { x: 1, y: 0 } } as SceneItem;
    expect(acceptsSceneItem(guidedSpecFor("ParallelLine")!.slots[0], segment)).toBe(true);
    expect(guidedSpecFor("Length")!.slots[0].kind).toBe("segment");
    expect(acceptsSceneItem(guidedSpecFor("Length")!.slots[0], segment)).toBe(true);
    expect(acceptsSceneItem(guidedSpecFor("Length")!.slots[0], { kind: "point", name: "A", source: "Point(0,0)", position: { x: 0, y: 0 } } as SceneItem)).toBe(false);
  });

  it("declares output routing and carrier coercion in the shared tool contract", () => {
    for (const id of ["Distance", "Ratio", "Length", "Angle", "Area", "Radius", "Circumference"]) {
      expect(guidedSpecFor(id)?.output, id).toBe("measurement");
    }
    expect(guidedSpecFor("Center")?.output).toBeUndefined();
    const segment = { kind: "segment", name: "s", source: "Segment(A, B)", start: { x: 0, y: 0 }, end: { x: 1, y: 0 } } as SceneItem;
    expect(acceptsSceneItem(guidedSpecFor("FootOfPerpendicular")!.slots[1], segment)).toBe(true);
    expect(acceptsSceneItem(guidedSpecFor("Intersect")!.slots[0], segment)).toBe(false);
    expect(Object.keys(guidedSpecs())).toContain("Center");
  });

  it("keeps branch choices explicit in guided construction expressions", () => {
    const excenter = guidedSpecFor("Excenter")!;
    expect(excenter.choices?.[0].name).toBe("vertex");
    expect(guidedExpression("Excenter", ["A", "B", "C"], excenter)).toBe("Excenter(A, B, C, vertex='A')");
    expect(guidedExpression("Excenter", ["A", "B", "C"], excenter, [], { vertex: "'C'" })).toBe("Excenter(A, B, C, vertex='C')");
    const regular = guidedSpecFor("RegularPolygon")!;
    expect(guidedExpression("RegularPolygon", ["A", "B"], regular, [], { n: "5", ccw: "False" })).toBe("RegularPolygon(A, B, 5, ccw=False)");
  });

  it("authors a tangent through the stable Polar construction", () => {
    const tangent = guidedSpecFor("TangentAtPoint")!;
    expect(guidedExpression("TangentAtPoint", ["P", "omega"], tangent)).toBe("Polar(P, omega)");
  });
});
