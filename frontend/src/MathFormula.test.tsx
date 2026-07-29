import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { expressionToTex, MathFormula, polynomialToTex } from "./MathFormula";

describe("expressionToTex", () => {
  it("uses conventional geometry notation", () => {
    expect(expressionToTex("Distance(A, B)")).toBe("\\left|AB\\right|");
    expect(expressionToTex("Segment(P1, P2)")).toBe(
      "\\overline{P_{1}P_{2}}",
    );
    expect(expressionToTex("Angle(A, B, C)")).toBe("\\angle ABC");
  });

  it("typesets arithmetic, roots, fractions, and relations", () => {
    expect(expressionToTex("Sqrt(x^2 + y^2) <= pi/2")).toContain(
      "\\sqrt",
    );
    expect(expressionToTex("Sqrt(x^2 + y^2) <= pi/2")).toContain("\\le");
    expect(expressionToTex("Sqrt(x^2 + y^2) <= pi/2")).toContain("\\frac");
    expect(expressionToTex("-x^2")).toBe("-{x}^{2}");
    expect(expressionToTex("Distance(i, c) = sqrt(17)")).toBe(
      "\\left|ic\\right| = \\sqrt{17}",
    );
  });

  it("falls back safely for syntax outside the display grammar", () => {
    expect(expressionToTex('Raw("<script>")')).toContain("\\mathtt");
  });

  it("typesets canvas-style identifiers with subscripts and Greek letters", () => {
    expect(expressionToTex("P3")).toBe("P_{3}");
    expect(expressionToTex("I_A")).toBe("I_{A}");
    expect(expressionToTex("omega")).toBe("\\omega");
  });
});

describe("polynomialToTex", () => {
  it("formats signs, powers, and unit coefficients", () => {
    expect(polynomialToTex([1, 0, -2, 1])).toBe(
      "x^{3}\\,-\\,2\\,x\\,+\\,1",
    );
  });
});

describe("MathFormula", () => {
  it("renders KaTeX while exposing the source as its accessible name", () => {
    render(<MathFormula source="Distance(A, B)" />);
    const formula = screen.getByRole("math", { name: "Distance(A, B)" });
    expect(formula).toHaveClass("math-formula");
    expect(formula.querySelector(".katex")).not.toBeNull();
    expect(formula.querySelector(".math-render")).not.toBeNull();
    expect(formula.querySelector(".math-source")).toHaveTextContent(
      "Distance(A, B)",
    );
  });
});
