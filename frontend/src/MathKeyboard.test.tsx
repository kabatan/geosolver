import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { MathKeyboard } from "./MathKeyboard";

describe("MathKeyboard", () => {
  it("keeps every catalog function reachable in the scrollable function panel", async () => {
    const functions = Array.from({ length: 77 }, (_, index) => `Function${index}`);
    functions.push("CircleThroughThreePoints", "Distance");
    render(<MathKeyboard functions={functions} onInsert={vi.fn()} onBackspace={vi.fn()} onMove={vi.fn()} onEnter={vi.fn()} onClose={vi.fn()} />);
    const keyboard = screen.getByRole("region", { name: "数式キーボード" });
    await userEvent.click(within(keyboard).getByRole("tab", { name: "f(x)" }));
    expect(within(keyboard).getAllByRole("button")).toHaveLength(80);
    expect(within(keyboard).getByRole("button", { name: "Distance" })).toBeInTheDocument();
    expect(within(keyboard).getByRole("button", { name: "CircleThroughThreePoints" })).toHaveAttribute("title", "CircleThroughThreePoints");
  });
});
