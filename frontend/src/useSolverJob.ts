import { useEffect, useReducer, useRef } from "react";

export type ExactAnswer =
  | {
      kind: "algebraic";
      minimal_polynomial: string[];
      real_root_index: number;
      isolating_interval: [string, string];
      decimal: string;
      approximate_witness?: Record<string, unknown> | null;
    }
  | {
      kind: "affine_pi";
      pi_coefficient: string;
      constant: string;
      decimal: string;
      approximate_witness?: Record<string, unknown> | null;
    };

export type SolverCores = "auto" | number;
export type ResourceSummary = {
  max_time_seconds?: number;
  time_limit_seconds?: number;
  cores?: SolverCores;
  seed?: number;
};
export type WorkCheckpointSummary = {
  plan_sha256?: string;
  completed_start_ordinals?: number[];
  pending_start_ordinals?: number[];
  extension_batch?: number;
  extension_batch_ordinal?: number;
  batch?: number;
  batch_ordinal?: number;
  window?: number;
  stability_count?: number;
  stable_batch_count?: number;
  extension_stability_count?: number;
};
export type ApiResult = {
  status: string;
  completeness: "proven" | "unknown";
  elapsed_seconds: number;
  engine: { name: "standard" | "reference"; hash: string };
  problem_hash: string;
  requested_resources?: ResourceSummary;
  used_resources?: ResourceSummary;
  work_checkpoint?: WorkCheckpointSummary;
  termination_reason?: string | null;
  warnings: string[];
  answers: ExactAnswer[];
  error?: { code: string; message: string } | null;
};
export type RunProgress = {
  phase: string;
  completedStarts?: number;
  totalStarts?: number;
  batch?: number;
  stabilityCount?: number;
  usedCores?: number;
  elapsedSeconds: number;
  wallElapsedSeconds: number;
  engineElapsedSeconds?: number;
  capSeconds: number;
  terminationReason?: string;
};
export type SolverJobPhase =
  | "idle"
  | "submitting"
  | "queued"
  | "running"
  | "cancelling"
  | "succeeded"
  | "cancelled"
  | "failed"
  | "watchdog";

type State = {
  phase: SolverJobPhase;
  jobId?: string;
  progress: RunProgress;
  result?: ApiResult;
  cancelError?: string;
};

type Action =
  | { type: "start"; capSeconds: number; usedCores?: number }
  | { type: "created"; jobId: string }
  | { type: "payload"; payload: JobPayload }
  | { type: "tick" }
  | { type: "cancelling" }
  | { type: "cancel_error"; message: string }
  | { type: "watchdog" }
  | { type: "clear_result" }
  | { type: "failed"; message?: string };

type JobPayload = {
  state: string;
  result: ApiResult | null;
  progress?: unknown;
  [key: string]: unknown;
};

const initialState: State = {
  phase: "idle",
  progress: {
    phase: "idle",
    elapsedSeconds: 0,
    wallElapsedSeconds: 0,
    capSeconds: 180,
  },
};

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === "object"
    ? (value as Record<string, unknown>)
    : {};
}

function firstFinite(...values: unknown[]): number | undefined {
  for (const value of values) {
    if (typeof value === "number" && Number.isFinite(value)) return value;
  }
  return undefined;
}

function firstText(...values: unknown[]): string | undefined {
  return values.find(
    (value): value is string => typeof value === "string" && !!value.trim(),
  );
}

export function progressFromPayload(
  payloadValue: unknown,
  fallback: RunProgress,
): RunProgress {
  const payload = record(payloadValue);
  const progress = record(payload.progress);
  const result = record(payload.result);
  const checkpoint = record(
    progress.work_checkpoint ?? payload.work_checkpoint ?? result.work_checkpoint,
  );
  const usedResources = record(
    progress.used_resources ?? payload.used_resources ?? result.used_resources,
  );
  const requestedResources = record(
    progress.requested_resources ??
      payload.requested_resources ??
      result.requested_resources,
  );
  const completedOrdinals = checkpoint.completed_start_ordinals;
  const pendingOrdinals = checkpoint.pending_start_ordinals;
  const completedStarts = Array.isArray(completedOrdinals)
    ? completedOrdinals.length
    : firstFinite(
        progress.completed_starts,
        progress.completed_start_count,
        payload.completed_starts,
        checkpoint.completed_starts,
      );
  const pendingStarts = Array.isArray(pendingOrdinals)
    ? pendingOrdinals.length
    : undefined;
  const totalStarts = firstFinite(
    progress.total_starts,
    payload.total_starts,
    checkpoint.total_starts,
    completedStarts !== undefined && pendingStarts !== undefined
      ? completedStarts + pendingStarts
      : undefined,
  );
  const legacyElapsed = firstFinite(
    progress.elapsed_seconds,
    payload.elapsed_seconds,
    result.elapsed_seconds,
  );
  return {
    phase:
      firstText(progress.phase, payload.phase, payload.state, result.phase) ??
      fallback.phase,
    completedStarts: completedStarts ?? fallback.completedStarts,
    totalStarts: totalStarts ?? fallback.totalStarts,
    batch:
      firstFinite(
        progress.extension_batch,
        progress.extension_batch_ordinal,
        progress.batch,
        progress.batch_ordinal,
        checkpoint.extension_batch,
        checkpoint.extension_batch_ordinal,
        checkpoint.batch,
        checkpoint.batch_ordinal,
      ) ?? fallback.batch,
    stabilityCount:
      firstFinite(
        progress.stability_count,
        progress.stable_batch_count,
        progress.extension_stability_count,
        checkpoint.stability_count,
        checkpoint.stable_batch_count,
        checkpoint.extension_stability_count,
      ) ?? fallback.stabilityCount,
    usedCores:
      firstFinite(progress.used_cores, payload.used_cores, usedResources.cores) ??
      fallback.usedCores,
    elapsedSeconds: legacyElapsed ?? fallback.elapsedSeconds,
    wallElapsedSeconds:
      firstFinite(
        progress.wall_elapsed_seconds,
        payload.wall_elapsed_seconds,
        fallback.wallElapsedSeconds,
        legacyElapsed,
      ) ?? 0,
    engineElapsedSeconds:
      firstFinite(
        progress.engine_elapsed_seconds,
        payload.engine_elapsed_seconds,
        result.elapsed_seconds,
      ) ?? fallback.engineElapsedSeconds,
    capSeconds:
      firstFinite(
        progress.max_time_seconds,
        progress.cap_seconds,
        payload.max_time_seconds,
        requestedResources.max_time_seconds,
        requestedResources.time_limit_seconds,
      ) ?? fallback.capSeconds,
    terminationReason:
      firstText(
        progress.termination_reason,
        payload.termination_reason,
        result.termination_reason,
      ) ?? fallback.terminationReason,
  };
}

function terminalPhase(result: ApiResult): SolverJobPhase {
  if (result.status === "cancelled") return "cancelled";
  if (result.status.endsWith("error")) return "failed";
  return "succeeded";
}

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case "start":
      return {
        phase: "submitting",
        progress: {
          phase: "submitting",
          elapsedSeconds: 0,
          wallElapsedSeconds: 0,
          capSeconds: action.capSeconds,
          usedCores: action.usedCores,
        },
      };
    case "created":
      return {
        ...state,
        phase: "queued",
        jobId: action.jobId,
        progress: { ...state.progress, phase: "queued" },
      };
    case "payload": {
      const progress = progressFromPayload(action.payload, state.progress);
      if (action.payload.result) {
        const phase = terminalPhase(action.payload.result);
        return {
          ...state,
          phase,
          result: action.payload.result,
          progress: { ...progress, phase },
          cancelError: undefined,
        };
      }
      if (action.payload.state === "cancelled") {
        return {
          ...state,
          phase: "cancelled",
          progress: {
            ...progress,
            phase: "cancelled",
            terminationReason: "cancelled",
          },
          cancelError: undefined,
        };
      }
      const backendPhase = action.payload.state === "running" ? "running" : "queued";
      return {
        ...state,
        phase: state.phase === "cancelling" ? "cancelling" : backendPhase,
        progress: {
          ...progress,
          phase: state.phase === "cancelling" ? "cancelling" : progress.phase,
        },
      };
    }
    case "tick":
      return {
        ...state,
        progress: {
          ...state.progress,
          wallElapsedSeconds: state.progress.wallElapsedSeconds + 1,
        },
      };
    case "cancelling":
      return {
        ...state,
        phase: "cancelling",
        cancelError: undefined,
        progress: { ...state.progress, phase: "cancelling" },
      };
    case "cancel_error":
      return { ...state, cancelError: action.message };
    case "watchdog":
      return {
        ...state,
        phase: "watchdog",
        progress: { ...state.progress, phase: "watchdog" },
      };
    case "clear_result":
      return { ...state, result: undefined };
    case "failed":
      return {
        ...state,
        phase: "failed",
        progress: {
          ...state.progress,
          phase: "failed",
          terminationReason: state.progress.terminationReason ?? "engine_error",
        },
      };
  }
}

async function timedFetch(input: RequestInfo | URL, init?: RequestInit) {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), 10_000);
  try {
    return await fetch(input, { ...init, signal: controller.signal });
  } finally {
    window.clearTimeout(timer);
  }
}

type StartArguments = {
  problem: unknown;
  options: Record<string, unknown>;
  capSeconds: number;
  usedCores?: number;
  validate: () => Promise<boolean>;
  isCurrentProblem: () => boolean;
};

export function useSolverJob(onError: (message: string) => void) {
  const [state, dispatch] = useReducer(reducer, initialState);
  const generation = useRef(0);

  useEffect(() => {
    if (!["queued", "running", "cancelling", "watchdog"].includes(state.phase))
      return;
    const timer = window.setInterval(() => dispatch({ type: "tick" }), 1000);
    return () => window.clearInterval(timer);
  }, [state.phase]);

  async function start(arguments_: StartArguments) {
    const token = ++generation.current;
    dispatch({
      type: "start",
      capSeconds: arguments_.capSeconds,
      usedCores: arguments_.usedCores,
    });
    if (!(await arguments_.validate())) {
      if (token === generation.current) dispatch({ type: "failed" });
      return;
    }
    try {
      const response = await timedFetch("/api/v1/solves", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ problem: arguments_.problem, options: arguments_.options }),
      });
      if (!response.ok)
        throw new Error(`solve request failed (HTTP ${response.status})`);
      const created = (await response.json()) as { job_id: string };
      if (token !== generation.current) {
        await timedFetch(`/api/v1/solves/${created.job_id}`, {
          method: "DELETE",
          credentials: "same-origin",
        }).catch(() => undefined);
        return;
      }
      dispatch({ type: "created", jobId: created.job_id });
      const startedAt = Date.now();
      while (token === generation.current) {
        await new Promise((resolve) => window.setTimeout(resolve, 700));
        const current = await timedFetch(`/api/v1/solves/${created.job_id}`, {
          credentials: "same-origin",
        });
        if (!current.ok)
          throw new Error(`job status failed (HTTP ${current.status})`);
        const payload = (await current.json()) as JobPayload;
        if (token !== generation.current) return;
        if (payload.result && !arguments_.isCurrentProblem()) {
          onError(
            "計算中に問題が変更されたため、この結果は表示しません。もう一度実行してください",
          );
          dispatch({ type: "failed" });
          return;
        }
        dispatch({ type: "payload", payload });
        if (payload.result || payload.state === "cancelled") return;
        if (Date.now() - startedAt > (arguments_.capSeconds + 120) * 1000)
          dispatch({ type: "watchdog" });
      }
    } catch (error) {
      if (token !== generation.current) return;
      const message = error instanceof Error ? error.message : "solverに接続できません";
      onError(message);
      dispatch({ type: "failed", message });
    }
  }

  async function cancel() {
    if (!state.jobId) {
      ++generation.current;
      dispatch({ type: "failed" });
      return;
    }
    dispatch({ type: "cancelling" });
    try {
      const response = await timedFetch(`/api/v1/solves/${state.jobId}`, {
        method: "DELETE",
        credentials: "same-origin",
      });
      if (!response.ok) throw new Error(`中止要求に失敗しました (HTTP ${response.status})`);
      // DELETE acknowledges the request only.  The polling loop owns terminal state.
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "中止要求に失敗しました";
      onError(message);
      dispatch({ type: "cancel_error", message });
    }
  }

  function clearResult() {
    dispatch({ type: "clear_result" });
  }

  return { ...state, start, cancel, clearResult };
}
