import {
  MouseEvent as ReactMouseEvent,
  PointerEvent as ReactPointerEvent,
} from "react";
import { SceneItem, Vec2, Viewport, worldToScreen } from "./geometry";
import { MathFormula, expressionToTex } from "./MathFormula";
import { FREEDOM_LABEL, type CanvasLabelPlacement, type ObjectStyle } from "./types";

export const DEFAULT_POINT_SIZE = 3.5;
export const MAX_POINT_SIZE = 8;

export function renderedPointSize(style?: ObjectStyle): number {
  return Math.max(
    1.5,
    Math.min(MAX_POINT_SIZE, style?.pointSize ?? DEFAULT_POINT_SIZE),
  );
}

export function displayedObjectLabel(
  item: SceneItem,
  style?: ObjectStyle,
): string {
  if (style?.label === "hidden") return "";
  if (style?.label === "caption") return style.caption || item.name;
  if (style?.label === "name") return item.name;
  return item.kind === "point" ? item.name : "";
}

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

export function canvasLabelLayout(
  items: readonly SceneItem[],
  viewport: Viewport,
  hidden: ReadonlySet<string>,
  styles: Readonly<Record<string, ObjectStyle>>,
  selectedNames: ReadonlySet<string>,
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
        !hidden.has(item.name) &&
        displayedObjectLabel(item, styles[item.name]) !== "",
    )
    .sort((a, b) => {
      const priority = (item: SceneItem) =>
        selectedNames.has(item.name) ? 2 : item.kind === "point" ? 1 : 0;
      return priority(b) - priority(a);
    });
  for (const item of ordered) {
    const label = displayedObjectLabel(item, styles[item.name]);
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
      { x: anchor.x + 18, y: anchor.y - height - 18 },
      { x: anchor.x + 18, y: anchor.y + 18 },
      { x: anchor.x - width - 18, y: anchor.y - height - 18 },
      { x: anchor.x - width - 18, y: anchor.y + 18 },
      { x: anchor.x + 30, y: anchor.y - height / 2 },
      { x: anchor.x - width - 30, y: anchor.y - height / 2 },
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
    const fallback = fit ?? (selectedNames.has(item.name) || item.kind === "point" ? {
      x: Math.max(2, Math.min(viewport.width - width - 2, anchor.x + 8)),
      y: Math.max(2, Math.min(viewport.height - height - 2, anchor.y - height - 5)),
      width,
      height,
    } : undefined);
    if (!fallback) continue;
    placements.set(item.name, fallback);
    occupied.push(fallback);
  }
  return placements;
}

export function CanvasMathLabel({
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

export { expressionToTex };

type SceneShapeProps = {
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
};

export function SceneShape({
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
}: SceneShapeProps) {
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
  const label = displayedObjectLabel(item, objectStyle);
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
