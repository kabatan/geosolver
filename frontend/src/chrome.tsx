import { PointerEvent as ReactPointerEvent } from "react";

export function clamp(
  value: number,
  minimum: number,
  maximum: number,
): number {
  return Math.min(maximum, Math.max(minimum, value));
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

export function PaneResizeHandle({
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
