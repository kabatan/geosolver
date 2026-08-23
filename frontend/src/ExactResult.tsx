import { MathFormula, polynomialToTex } from "./MathFormula";
import { ApiResult, RunProgress } from "./useSolverJob";

const STATUS_LABELS: Readonly<Record<string, string>> = {
  solved: "厳密解を検出",
  no_answer_found: "解を検出できませんでした",
  invalid_problem: "入力エラー",
  unsupported_platform: "このOSでは利用できません",
  cancelled: "中止",
  validation_error: "入力エラー",
  resource_error: "リソースエラー",
  engine_error: "solverエラー",
};

const TERMINATION_LABELS: Readonly<Record<string, string>> = {
  initial_work_answered: "初期探索で解を確定",
  extension_stable: "追加探索が安定したため終了",
  safety_cap: "安全上限に到達",
  exact_complete: "厳密完全性を確認",
  cancelled: "ユーザーが中止",
  engine_error: "solverエラー",
};

function polynomialText(coefficients: Array<number | string>) {
  const degree = coefficients.length - 1;
  if (degree < 0) return "—";
  return (
    coefficients
      .map((raw, index) => {
        const coefficient = String(raw);
        const power = degree - index;
        if (coefficient === "0" || coefficient === "0.0") return "";
        const term = power === 0 ? "" : power === 1 ? "x" : `x^${power}`;
        if (!term) return coefficient;
        if (coefficient === "1") return term;
        if (coefficient === "-1") return `-${term}`;
        return `${coefficient}${term}`;
      })
      .filter(Boolean)
      .join(" + ")
      .replace(/\+ -/g, "− ") || "0"
  );
}

export function formatApproximateDecimal(decimal: string): string {
  const value = Number(decimal);
  if (!Number.isFinite(value)) return decimal;
  return value
    .toPrecision(12)
    .replace(/(\.\d*?[1-9])0+(e|$)/i, "$1$2")
    .replace(/\.0+(e|$)/i, "$1");
}

type Props = {
  result?: ApiResult;
  progress: RunProgress;
  activeAnswer: number;
  showWitness: boolean;
  onToggleWitness: (index: number) => void;
};

export default function ExactResult({
  result,
  progress,
  activeAnswer,
  showWitness,
  onToggleWitness,
}: Props) {
  return (
    <section className="inspector-section result-section">
      <div className="result-heading">
        <h2>厳密解</h2>
        {result && <span>{result.answers.length}件</span>}
      </div>
      {!result ? (
        <div className="empty-result">まだ実行していません。</div>
      ) : (
        <>
          <div className={`result-status status-${result.status}`}>
            {STATUS_LABELS[result.status] ?? result.status}
          </div>
          {result.error && <p className="result-detail">{result.error.message}</p>}
          {result.warnings.map((warning) => (
            <p className="warning-strip" key={warning}>
              {warning}
            </p>
          ))}
          {result.answers.map((answer, index) => {
            const approximation = formatApproximateDecimal(answer.decimal);
            return (
              <article
                className={`answer-card ${activeAnswer === index ? "active-answer" : ""}`}
                key={`${answer.decimal}-${index}`}
              >
                <div className="answer-number">
                  <span>#{index + 1} · 近似値（有効12桁）</span>
                  <strong>
                    <MathFormula
                      source={approximation}
                      label={`近似値 ${approximation}`}
                    />
                  </strong>
                  {answer.approximate_witness && (
                    <button onClick={() => onToggleWitness(index)}>
                      {activeAnswer === index && showWitness
                        ? "表示を隠す"
                        : "作図に表示"}
                    </button>
                  )}
                </div>
                {answer.kind === "algebraic" ? (
                  <dl>
                    <div>
                      <dt>最小多項式</dt>
                      <dd className="exact-formula">
                        <MathFormula
                          source={polynomialText(answer.minimal_polynomial)}
                          tex={polynomialToTex(answer.minimal_polynomial)}
                          label={`最小多項式 ${polynomialText(answer.minimal_polynomial)}`}
                        />
                      </dd>
                    </div>
                    <div>
                      <dt>実根 index</dt>
                      <dd>{answer.real_root_index}</dd>
                    </div>
                  </dl>
                ) : (
                  <dl>
                    <div>
                      <dt>π係数</dt>
                      <dd>{answer.pi_coefficient}</dd>
                    </div>
                    <div>
                      <dt>定数項</dt>
                      <dd>{answer.constant}</dd>
                    </div>
                  </dl>
                )}
                <details>
                  <summary>完全精度・隔離区間</summary>
                  <dl>
                    <div>
                      <dt>完全decimal</dt>
                      <dd className="full-decimal">
                        <code>{answer.decimal}</code>
                        <button
                          type="button"
                          onClick={() => void navigator.clipboard?.writeText(answer.decimal)}
                        >
                          コピー
                        </button>
                      </dd>
                    </div>
                    {answer.kind === "algebraic" ? (
                      <div>
                        <dt>隔離区間</dt>
                        <dd className="exact-formula">
                          <MathFormula
                            source={`[${answer.isolating_interval.join(", ")}]`}
                            tex={`\\left[${answer.isolating_interval.join(",\\,")}\\right]`}
                            label={`隔離区間 ${answer.isolating_interval.join(" から ")}`}
                          />
                        </dd>
                      </div>
                    ) : (
                      <div>
                        <dt>厳密式</dt>
                        <dd>{`${answer.pi_coefficient}π + ${answer.constant}`}</dd>
                      </div>
                    )}
                  </dl>
                </details>
                {answer.approximate_witness && (
                  <details open={activeAnswer === index && showWitness}>
                    <summary>近似配置 (witness)</summary>
                    <pre>{JSON.stringify(answer.approximate_witness, null, 2)}</pre>
                  </details>
                )}
              </article>
            );
          })}
          <dl className="result-meta">
            <div>
              <dt>solver計算時間</dt>
              <dd>{result.elapsed_seconds.toFixed(3)}秒</dd>
            </div>
            <div>
              <dt>Engine</dt>
              <dd>
                {result.engine.name}
              </dd>
            </div>
            <div>
              <dt>Hash</dt>
              <dd><code>{result.engine.hash}</code></dd>
            </div>
            <div>
              <dt>Problem SHA</dt>
              <dd><code>{result.problem_hash}</code></dd>
            </div>
            <div>
              <dt>完了starts</dt>
              <dd>
                {progress.completedStarts ?? "—"}
                {progress.totalStarts !== undefined && ` / ${progress.totalStarts}`}
              </dd>
            </div>
            <div>
              <dt>追加batch / 安定回数</dt>
              <dd>
                {progress.batch !== undefined ? `#${progress.batch}` : "—"}
                {" / "}
                {progress.stabilityCount ?? "—"}
              </dd>
            </div>
            <div>
              <dt>使用コア</dt>
              <dd>
                {progress.usedCores ??
                  (typeof result.used_resources?.cores === "number"
                    ? result.used_resources.cores
                    : "—")}
              </dd>
            </div>
            <div>
              <dt>終了理由</dt>
              <dd>
                {TERMINATION_LABELS[
                  result.termination_reason ?? progress.terminationReason ?? ""
                ] ?? result.termination_reason ?? progress.terminationReason ?? "—"}
              </dd>
            </div>
          </dl>
        </>
      )}
    </section>
  );
}
