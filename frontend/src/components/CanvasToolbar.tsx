import {
  ArrowClockwise,
  ArrowCounterClockwise,
  ArrowsOut,
  Eye,
  GridFour,
  Hand,
  Target,
  Trash,
} from "@phosphor-icons/react";

type CanvasToolbarProps = {
  canUndo: boolean;
  canRedo: boolean;
  onUndo: () => void;
  onRedo: () => void;
  grid: boolean;
  snap: boolean;
  onToggleGrid: () => void;
  onToggleSnap: () => void;
  onPan: () => void;
  canShowAll: boolean;
  onShowAll: () => void;
  canFitAll: boolean;
  onFitAll: () => void;
  canClearAll: boolean;
  onClearAll: () => void;
};

export function CanvasToolbar({
  canUndo,
  canRedo,
  onUndo,
  onRedo,
  grid,
  snap,
  onToggleGrid,
  onToggleSnap,
  onPan,
  canShowAll,
  onShowAll,
  canFitAll,
  onFitAll,
  canClearAll,
  onClearAll,
}: CanvasToolbarProps) {
  return (
    <div
      className="canvas-toolbar geogebra-canvas-bar"
      aria-label="作図操作"
    >
      <div className="tool-group compact">
        <button aria-label="元に戻す" disabled={!canUndo} onClick={onUndo}>
          <ArrowCounterClockwise />
        </button>
        <button aria-label="やり直す" disabled={!canRedo} onClick={onRedo}>
          <ArrowClockwise />
        </button>
      </div>
      <div className="tool-group compact">
        <button
          className={grid ? "active" : ""}
          aria-label="グリッド"
          aria-pressed={grid}
          onClick={onToggleGrid}
        >
          <GridFour />
        </button>
        <button
          className={snap ? "active" : ""}
          aria-label="スナップ"
          aria-pressed={snap}
          onClick={onToggleSnap}
        >
          <Target />
        </button>
        <button aria-label="表示を移動" onClick={onPan}>
          <Hand />
        </button>
        <button
          aria-label="すべてのオブジェクトを表示"
          title="すべて表示"
          disabled={!canShowAll}
          onClick={onShowAll}
        >
          <Eye />
        </button>
        <button
          aria-label="図全体に表示を合わせる"
          title="全体表示"
          disabled={!canFitAll}
          onClick={onFitAll}
        >
          <ArrowsOut />
        </button>
        <button
          className="clear-all-button"
          aria-label="すべて消去"
          title="すべて消去"
          disabled={!canClearAll}
          onClick={onClearAll}
        >
          <Trash />
        </button>
      </div>
    </div>
  );
}
