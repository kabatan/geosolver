import type { RunProgress, SolverJobPhase } from "../useSolverJob";
import { runPhaseLabel } from "../solverMeta";

type SolverInstrumentRailProps = {
  target: string;
  phase: SolverJobPhase;
  progress: RunProgress;
  running: boolean;
  profile: string;
  onOpenTarget: () => void;
  onOpenDetails: () => void;
  onStart: () => void;
  onCancel: () => void;
};

export function SolverInstrumentRail({
  target,
  phase,
  progress,
  running,
  profile,
  onOpenTarget,
  onOpenDetails,
  onStart,
  onCancel,
}: SolverInstrumentRailProps) {
  const stateLabel =
    phase === "idle"
      ? target.trim()
        ? "TARGET SET"
        : "TARGET REQUIRED"
      : runPhaseLabel(
          ["succeeded", "cancelled", "failed", "watchdog"].includes(phase)
            ? phase
            : progress.phase,
        ).toUpperCase();

  return (
    <section className="solver-instrument-rail" aria-label="Solverクイック実行">
      <button className="solver-target-readout" onClick={onOpenTarget}>
        <span>TARGET</span>
        <strong>{target || "—"}</strong>
      </button>
      <button className="solver-state-readout" onClick={onOpenDetails}>
        <strong className={phase === "failed" ? "bad" : ""}>{stateLabel}</strong>
        <span>{profile}</span>
      </button>
      <button
        className={`solver-run-signal ${running ? "running" : ""}`}
        aria-label={running ? "Solverを中止" : "Solverを実行"}
        onClick={running ? onCancel : onStart}
      >
        {running ? "STOP" : "RUN SOLVER"}
      </button>
    </section>
  );
}
