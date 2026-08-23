import { Play, Stop } from "@phosphor-icons/react";
import type {
  RunProgress,
  SolverJobPhase,
} from "../useSolverJob";
import { runPhaseLabel, terminationLabel } from "../solverMeta";

type SolverExecutionDockProps = {
  phase: SolverJobPhase;
  progress: RunProgress;
  running: boolean;
  cancelError?: string;
  onStart: () => void;
  onCancel: () => void;
};

export function SolverExecutionDock({
  phase,
  progress,
  running,
  cancelError,
  onStart,
  onCancel,
}: SolverExecutionDockProps) {
  const elapsed = progress.wallElapsedSeconds;

  return (
    <section className="inspector-section execution-section solver-execution-dock">
      <div className="execution-heading">
        <h2>実行</h2>
        <span aria-live="polite">
          {phase === "idle"
            ? "待機中"
            : `${runPhaseLabel(
                ["succeeded", "cancelled", "failed", "watchdog"].includes(
                  phase,
                )
                  ? phase
                  : progress.phase,
              )} · 全体時間 ${Math.round(elapsed)}秒`}
        </span>
      </div>
      {phase !== "idle" && (
        <div className="run-progress" aria-label="solver進捗">
          <div className="run-progress-line">
            <strong>{runPhaseLabel(progress.phase)}</strong>
            <span>
              全体時間 {Math.round(elapsed)}/{Math.round(progress.capSeconds)}秒
            </span>
          </div>
          <progress
            aria-label="経過時間"
            max={Math.max(1, progress.capSeconds)}
            value={Math.min(progress.capSeconds, elapsed)}
          />
          <dl className="run-progress-grid">
            <div>
              <dt>完了starts</dt>
              <dd>
                {progress.completedStarts ?? "—"}
                {progress.totalStarts !== undefined &&
                  ` / ${progress.totalStarts}`}
              </dd>
            </div>
            <div>
              <dt>追加batch</dt>
              <dd>{progress.batch !== undefined ? `#${progress.batch}` : "—"}</dd>
            </div>
            <div>
              <dt>安定回数</dt>
              <dd>{progress.stabilityCount ?? "—"}</dd>
            </div>
            <div>
              <dt>使用コア</dt>
              <dd>{progress.usedCores ?? "自動調整中"}</dd>
            </div>
          </dl>
          {progress.terminationReason && (
            <p className="termination-line">
              終了理由: {terminationLabel(progress.terminationReason)}
            </p>
          )}
          {cancelError && (
            <p className="termination-line cancel-error" role="alert">
              {cancelError}。中止を再試行できます。
            </p>
          )}
        </div>
      )}
      <div className="solve-actions">
        <button className="primary-action" disabled={running} onClick={onStart}>
          <Play weight="fill" />
          解く
        </button>
        <button className="cancel-action" disabled={!running} onClick={onCancel}>
          <Stop />
          中止
        </button>
      </div>
    </section>
  );
}
