import { Function, PencilLine, PlayCircle } from "@phosphor-icons/react";

export type WorkflowStage = "draw" | "constrain" | "solve";

type WorkflowStageNavProps = {
  mode: WorkflowStage;
  objectCount: number;
  conditionCount: number;
  solverReady: boolean;
  onDraw: () => void;
  onConstrain: () => void;
  onSolve: () => void;
};

export function WorkflowStageNav({
  mode,
  objectCount,
  conditionCount,
  solverReady,
  onDraw,
  onConstrain,
  onSolve,
}: WorkflowStageNavProps) {
  return (
    <nav className="workflow-stage-nav" aria-label="作業モード">
      <button
        aria-label="ツール"
        aria-pressed={mode === "draw"}
        className={mode === "draw" ? "active" : ""}
        onClick={onDraw}
      >
        <PencilLine className="workflow-stage-icon" aria-hidden="true" />
        <span className="workflow-stage-copy">
          <strong>作図</strong>
          <small>DRAW</small>
        </span>
        <span className="workflow-stage-state">{objectCount}</span>
      </button>
      <button
        aria-label="代数"
        aria-pressed={mode === "constrain"}
        className={mode === "constrain" ? "active" : ""}
        onClick={onConstrain}
      >
        <Function className="workflow-stage-icon" aria-hidden="true" />
        <span className="workflow-stage-copy">
          <strong>条件</strong>
          <small>CONSTRAIN</small>
        </span>
        <span className="workflow-stage-state">{conditionCount}</span>
      </button>
      <button
        aria-label="Solveワークスペース"
        aria-pressed={mode === "solve"}
        className={mode === "solve" ? "active" : ""}
        onClick={onSolve}
      >
        <PlayCircle className="workflow-stage-icon" aria-hidden="true" />
        <span className="workflow-stage-copy">
          <strong>Solve</strong>
          <small>SOLVER</small>
        </span>
        <span
          className={`workflow-stage-state workflow-stage-ready ${solverReady ? "ready" : ""}`}
        >
          {solverReady ? "READY" : "SET"}
        </span>
      </button>
    </nav>
  );
}
