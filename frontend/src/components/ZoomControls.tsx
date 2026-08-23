import { Minus, Plus, Target } from "@phosphor-icons/react";

export function ZoomControls({
  onZoomIn,
  onZoomOut,
  onRecenter,
}: {
  onZoomIn: () => void;
  onZoomOut: () => void;
  onRecenter: () => void;
}) {
  return (
    <div className="zoom-controls">
      <button aria-label="拡大" onClick={onZoomIn}>
        <Plus />
      </button>
      <button aria-label="縮小" onClick={onZoomOut}>
        <Minus />
      </button>
      <button aria-label="表示を中央に戻す" onClick={onRecenter}>
        <Target />
      </button>
    </div>
  );
}
