import type { ReactNode } from "react";
import { Cursor, Eye, Selection, Trash } from "@phosphor-icons/react";
import { guidedSpecFor } from "./authoring";
import { guardToFormula } from "./mathFormat";
import type { DslCatalog, DslTool, PaletteGroup, PaletteTool } from "./types";

export const BASIC_PALETTE_GROUP: PaletteGroup = {
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

export const DIRECT_TOOL_MODES: Readonly<Record<string, string>> = {
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

export function toolOutput(
  tool: DslTool,
): "construction" | "measurement" | "constraint" | "guard" {
  const contractOutput = guidedSpecFor(tool.id)?.output;
  if (contractOutput) return contractOutput;
  if (tool.category === "measurements") return "measurement";
  if (tool.category === "constraints") return "constraint";
  if (tool.category === "guards") return "guard";
  return "construction";
}

export function guardFormulaForTool(tool: DslTool): string {
  return toolOutput(tool) === "guard"
    ? guardToFormula(tool.signature)
    : tool.signature;
}

export function PaletteGlyph({ id }: { id: string }) {
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
