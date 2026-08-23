import type { SolverMode } from "./types";

const TERMINATION_LABELS: Readonly<Record<string, string>> = {
  initial_work_answered: "初期探索で解を確定",
  extension_stable: "追加探索が安定したため終了",
  safety_cap: "安全上限に到達",
  exact_complete: "厳密完全性を確認",
  cancelled: "ユーザーが中止",
  engine_error: "engine error",
};

export function terminationLabel(reason?: string): string {
  if (!reason) return "—";
  return TERMINATION_LABELS[reason] ?? reason;
}

export function runPhaseLabel(phase: string): string {
  const labels: Readonly<Record<string, string>> = {
    idle: "待機中",
    submitting: "問題を検証・送信中",
    queued: "実行待ち",
    running: "初期探索",
    cancelling: "中止を要求中",
    watchdog: "応答待ち（再接続中）",
    initial_search: "初期探索",
    extension: "追加探索",
    exact_authority: "厳密判定",
    finalizing: "結果を整理中",
    completed: "完了",
    succeeded: "完了",
    cancelled: "中止",
    failed: "エラー",
  };
  return labels[phase] ?? phase;
}

export type { SolverMode };
