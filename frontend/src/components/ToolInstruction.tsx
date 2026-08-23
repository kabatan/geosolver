export function ToolInstruction({
  toolLabel,
  message,
  warningCount,
  showCancel,
  onCancel,
}: {
  toolLabel: string;
  message: string;
  warningCount: number;
  showCancel: boolean;
  onCancel: () => void;
}) {
  return (
    <div className="tool-instruction">
      <div className="instruction-main">
        <strong className="instruction-tool">{toolLabel}</strong>
        <span className="instruction-copy" role="status">
          {message}
        </span>
      </div>
      <div className="instruction-actions">
        {warningCount > 0 ? (
          <span>{warningCount}件は描画プレビュー対象外</span>
        ) : null}
        {showCancel && (
          <button
            onClick={onCancel}
          >
            作図を中止
          </button>
        )}
      </div>
    </div>
  );
}
