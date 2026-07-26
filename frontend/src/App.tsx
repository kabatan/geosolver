import {
  ArrowCounterClockwise,
  ArrowUUpRight,
  CaretDown,
  CaretRight,
  Check,
  Circle,
  CloudArrowDown,
  CloudArrowUp,
  Cursor,
  DotsThreeVertical,
  Eye,
  EyeSlash,
  GridFour,
  LineSegment,
  LockSimple,
  MagnifyingGlass,
  Minus,
  Pentagon,
  Play,
  Plus,
  SlidersHorizontal,
  Stop,
  Target,
} from "@phosphor-icons/react";
import { ChangeEvent, MouseEvent, useEffect, useMemo, useRef, useState } from "react";

type Construction = { name: string; expr: string };
type Problem = {
  task: "solve";
  id: string;
  variables: { names: string[] };
  construction: Construction[];
  constraints: { def: string; value: number | string }[];
  guards: string[];
  answer: string;
  post_process: string;
};

type ExactAnswer = {
  minimal_polynomial_high_to_low: Array<number | string>;
  selected_real_root_index: number;
  isolating_interval: string[];
  decimal: string;
};

type ApiResult = {
  status: string;
  elapsed_seconds: number;
  engine_hash: string;
  work_checkpoint: { plan_sha256?: string };
  warnings: string[];
  answers: ExactAnswer[];
  detail?: string;
};

const INITIAL_PROBLEM: Problem = {
  task: "solve",
  id: "cyclic-tangent",
  variables: { names: [] },
  construction: [
    { name: "A", expr: "Point(-2, 4)" },
    { name: "B", expr: "Point(-2, -2)" },
    { name: "C", expr: "Point(4, -2)" },
    { name: "D", expr: "Point(4, 4)" },
    { name: "O", expr: "Point(1, 1)" },
    { name: "omega", expr: "CircleThroughThreePoints(A, B, C)" },
    { name: "t", expr: "Line(D, Point(5, 3))" },
  ],
  constraints: [
    { def: "OnCircle(C, omega)", value: 0 },
    { def: "OnCircle(D, omega)", value: 0 },
    { def: "IsTangent(t, omega)", value: 0 },
  ],
  guards: ["Distinct(A, B)", "Distinct(A, C)", "Distinct(A, D)"],
  answer: "Distance(A, C)**2",
  post_process: "",
};

const SAMPLE_RESULT: ApiResult = {
  status: "answers_found_completeness_unknown",
  elapsed_seconds: 157.4,
  engine_hash: "9fa23aecdb9372df",
  work_checkpoint: { plan_sha256: "b3f4c2e9f0a7d3b1" },
  warnings: ["発見済みの厳密値。全targetの完全性は未証明"],
  answers: [
    {
      minimal_polynomial_high_to_low: [1, -40],
      selected_real_root_index: 0,
      isolating_interval: ["39.99999999", "40.00000001"],
      decimal: "40.0000000000",
    },
  ],
};

const COMMANDS = [
  ["Distance", "Distance(point, point)"],
  ["Distance", "Distance(point, line)"],
  ["Distance", "Distance(line, line)"],
  ["Distance", "Distance(point, circle)"],
];

const points = {
  A: { x: 242, y: 154, label: "A", detail: "(-2, 4)" },
  B: { x: 205, y: 356, label: "B", detail: "(-2, -2)" },
  C: { x: 520, y: 400, label: "C", detail: "(4, -2.4721)" },
  D: { x: 554, y: 206, label: "D", detail: "(5.6569, 1.6569)" },
  O: { x: 390, y: 286, label: "O", detail: "" },
};

function polynomialText(answer?: ExactAnswer) {
  if (!answer || answer.minimal_polynomial_high_to_low.length !== 2) return "—";
  const [a, b] = answer.minimal_polynomial_high_to_low;
  return `${a === 1 ? "x" : `${a}x`} ${Number(b) < 0 ? "−" : "+"} ${Math.abs(Number(b))}`;
}

function saveProject(problem: Problem) {
  const request = indexedDB.open("geotarget", 1);
  request.onupgradeneeded = () => request.result.createObjectStore("projects");
  request.onsuccess = () => {
    const transaction = request.result.transaction("projects", "readwrite");
    transaction.objectStore("projects").put(problem, problem.id);
  };
}

export function App() {
  const [problem, setProblem] = useState(INITIAL_PROBLEM);
  const [history, setHistory] = useState<Problem[]>([]);
  const [future, setFuture] = useState<Problem[]>([]);
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [selected, setSelected] = useState("C");
  const [tool, setTool] = useState("select");
  const [showToolMenu, setShowToolMenu] = useState(false);
  const [activeEditor, setActiveEditor] = useState<"command" | "json" | "log">("command");
  const [command, setCommand] = useState("Distance(A, C)");
  const [commandFocused, setCommandFocused] = useState(true);
  const [jsonText, setJsonText] = useState(JSON.stringify(INITIAL_PROBLEM, null, 2));
  const [jsonError, setJsonError] = useState("");
  const [timeLimit, setTimeLimit] = useState(300);
  const [cores, setCores] = useState(1);
  const [seed, setSeed] = useState(0);
  const [phase, setPhase] = useState<"idle" | "queued" | "running" | "done" | "error">("idle");
  const [jobId, setJobId] = useState<string>();
  const [result, setResult] = useState<ApiResult>(SAMPLE_RESULT);
  const [overlay, setOverlay] = useState(true);
  const [expandedConstraints, setExpandedConstraints] = useState(true);
  const [expandedTarget, setExpandedTarget] = useState(true);
  const [zoom, setZoom] = useState(1);
  const [elapsed, setElapsed] = useState(0);
  const importRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const timer = window.setTimeout(() => saveProject(problem), 400);
    setJsonText(JSON.stringify(problem, null, 2));
    return () => window.clearTimeout(timer);
  }, [problem]);

  useEffect(() => {
    if (phase !== "running") return;
    const timer = window.setInterval(() => setElapsed((value) => value + 1), 1000);
    return () => window.clearInterval(timer);
  }, [phase]);

  const filteredCommands = useMemo(
    () => COMMANDS.filter(([name]) => name.toLowerCase().includes(command.split("(")[0].toLowerCase())).slice(0, 4),
    [command],
  );

  function commit(next: Problem) {
    setHistory((items) => [...items.slice(-49), problem]);
    setFuture([]);
    setProblem(next);
  }

  function undo() {
    const previous = history.at(-1);
    if (!previous) return;
    setFuture((items) => [problem, ...items]);
    setHistory((items) => items.slice(0, -1));
    setProblem(previous);
  }

  function redo() {
    const next = future[0];
    if (!next) return;
    setHistory((items) => [...items, problem]);
    setFuture((items) => items.slice(1));
    setProblem(next);
  }

  function toggleVisibility(name: string) {
    setHidden((current) => {
      const next = new Set(current);
      next.has(name) ? next.delete(name) : next.add(name);
      return next;
    });
  }

  function canvasClick(event: MouseEvent<SVGSVGElement>) {
    if (tool !== "point") return;
    const box = event.currentTarget.getBoundingClientRect();
    const x = ((event.clientX - box.left) / box.width) * 14 - 7;
    const y = 6 - ((event.clientY - box.top) / box.height) * 12;
    const name = `P${problem.construction.length - 6}`;
    commit({ ...problem, construction: [...problem.construction, { name, expr: `Point(${x.toFixed(3)}, ${y.toFixed(3)})` }] });
    setSelected(name);
    setTool("select");
  }

  function updateJson(value: string) {
    setJsonText(value);
    try {
      const parsed = JSON.parse(value) as Problem;
      if (!parsed.construction || !parsed.answer) throw new Error("V15 fields are missing");
      setJsonError("");
      setProblem(parsed);
    } catch (error) {
      setJsonError(error instanceof Error ? error.message : "JSONを解釈できません");
    }
  }

  async function startSolve() {
    setPhase("queued");
    setElapsed(0);
    try {
      await fetch("/api/v1/session", { credentials: "same-origin" });
      const response = await fetch("/api/v1/solves", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ problem, options: { time_limit_seconds: timeLimit, cores, seed } }),
      });
      if (!response.ok) throw new Error(`solve request failed (${response.status})`);
      const created = (await response.json()) as { job_id: string };
      setJobId(created.job_id);
      setPhase("running");
      while (true) {
        await new Promise((resolve) => window.setTimeout(resolve, 750));
        const current = await fetch(`/api/v1/solves/${created.job_id}`, { credentials: "same-origin" });
        const payload = (await current.json()) as { state: string; result: ApiResult | null };
        if (payload.result) {
          setResult(payload.result);
          setPhase(payload.result.status.endsWith("error") ? "error" : "done");
          break;
        }
      }
    } catch (error) {
      setResult({ ...SAMPLE_RESULT, status: "engine_error", answers: [], detail: error instanceof Error ? error.message : "接続できません" });
      setPhase("error");
    }
  }

  async function cancelSolve() {
    if (jobId) await fetch(`/api/v1/solves/${jobId}`, { method: "DELETE", credentials: "same-origin" });
    setPhase("idle");
  }

  function exportProject() {
    const metadata = { viewport: { zoom }, style: { overlay }, ui: { selected }, problem };
    const url = URL.createObjectURL(new Blob([JSON.stringify(metadata, null, 2)], { type: "application/json" }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${problem.id}.geotarget.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  function importProject(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    file.text().then((text) => {
      const value = JSON.parse(text) as Problem | { problem: Problem };
      commit("problem" in value ? value.problem : value);
    });
  }

  const answer = result.answers[0];
  const running = phase === "queued" || phase === "running";

  return (
    <div className="app-shell">
      <header className="app-bar">
        <div className="brand">GeoTarget</div>
        <div className="bar-divider" />
        <button className="project-crumb" type="button">cyclic-tangent.geotarget.json <CaretRight size={14} /></button>
        <div className="app-actions">
          <input ref={importRef} className="visually-hidden" type="file" accept=".json,.geotarget.json" onChange={importProject} />
          <button type="button" onClick={() => importRef.current?.click()}><CloudArrowDown />インポート</button>
          <button type="button" onClick={exportProject}><CloudArrowUp />エクスポート</button>
          <span className="doctor-status"><Check weight="bold" />ドクター：正常</span>
          <button className="icon-button" type="button" aria-label="その他"><DotsThreeVertical /></button>
        </div>
      </header>

      <main className="workspace">
        <aside className="model-pane" aria-label="構成シーケンス">
          <div className="pane-heading"><h1>構成シーケンス</h1></div>
          <label className="search-field"><MagnifyingGlass /><input aria-label="コマンドを検索" placeholder="コマンドを検索" /></label>
          <div className="sequence-header"><span>表示</span><span>ID</span><span>種別</span><span>式（定義）</span></div>
          <div className="sequence-list" role="tree" aria-label="作図オブジェクト">
            {problem.construction.map((item) => {
              const type = problem.variables.names.includes(item.name) ? "Free" : item.expr.startsWith("Point(") ? "Fixed" : "Derived";
              const isHidden = hidden.has(item.name);
              return (
                <div className={`sequence-row ${selected === item.name ? "selected" : ""}`} role="treeitem" aria-selected={selected === item.name} key={item.name} onClick={() => setSelected(item.name)}>
                  <button type="button" className="visibility" aria-label={`${item.name}を${isHidden ? "表示" : "非表示"}`} onClick={(event) => { event.stopPropagation(); toggleVisibility(item.name); }}>{isHidden ? <EyeSlash /> : <Eye />}</button>
                  <strong>{item.name === "omega" ? "ω" : item.name}</strong>
                  <span>{type}</span>
                  <code>{item.name === "omega" ? "ω" : item.name} = {item.expr}</code>
                  <CaretRight className="row-caret" />
                </div>
              );
            })}
            <div className="sequence-row target-sequence" role="treeitem" aria-selected={false} onClick={() => setSelected("T1")}>
              <span className="target-dot"><Target weight="bold" /></span>
              <strong>T1</strong>
              <span>Target</span>
              <code>T1 = {problem.answer}</code>
              <CaretRight className="row-caret" />
            </div>
          </div>
          <section className="fold-section">
            <button type="button" onClick={() => setExpandedConstraints(!expandedConstraints)}><span>制約セット ({problem.constraints.length})</span><CaretDown className={expandedConstraints ? "" : "collapsed"} /></button>
            {expandedConstraints && <div className="constraint-list">{problem.constraints.map((constraint, index) => <div key={constraint.def}><span>c{index + 1}</span><code>{constraint.def}</code><Check weight="bold" /></div>)}</div>}
          </section>
          <section className="fold-section target-section">
            <button type="button" onClick={() => setExpandedTarget(!expandedTarget)}><span>目標 (1)</span><CaretDown className={expandedTarget ? "" : "collapsed"} /></button>
            {expandedTarget && <div className="target-row"><Target /><span>T1</span><code>{problem.answer}</code></div>}
          </section>
          <div className="tool-launcher">
            {showToolMenu && <div className="tool-menu" role="menu"><button role="menuitem" onClick={() => { setTool("point"); setShowToolMenu(false); }}>点を追加</button><button role="menuitem">直線・線分</button><button role="menuitem">円・円弧</button><button role="menuitem">高度な構成…</button></div>}
            <button type="button" onClick={() => setShowToolMenu(!showToolMenu)}><SlidersHorizontal />作図ツール</button>
          </div>
        </aside>

        <section className="center-stage">
          <div className="canvas-toolbar" aria-label="作図ツールバー">
            <div className="tool-group">
              <button className={tool === "select" ? "active" : ""} type="button" aria-label="選択" onClick={() => setTool("select")}><Cursor /></button>
              <button className={tool === "point" ? "active" : ""} type="button" aria-label="点" onClick={() => setTool("point")}><Circle weight="fill" /></button>
              <button type="button" aria-label="線分"><LineSegment /></button>
              <button type="button" aria-label="円"><Circle /></button>
              <button type="button" aria-label="多角形"><Pentagon /></button>
            </div>
            <div className="tool-group toolbar-right">
              <button type="button" aria-label="元に戻す" disabled={!history.length} onClick={undo}><ArrowCounterClockwise /></button>
              <button type="button" aria-label="やり直す" disabled={!future.length} onClick={redo}><ArrowUUpRight /></button>
              <span className="toolbar-divider" />
              <button type="button" aria-label="グリッド"><GridFour /></button>
              <button className="active-magnet" type="button" aria-label="スナップ"><Target /></button>
            </div>
          </div>
          <div className={`canvas-wrap ${tool === "point" ? "crosshair" : ""}`}>
            <svg className="geometry-canvas" viewBox="0 0 760 560" role="img" aria-label="円と四角形A B C D、中心O、接線tの作図" onClick={canvasClick} style={{ transform: `scale(${zoom})` }}>
              <defs><pattern id="minor-grid" width="40" height="40" patternUnits="userSpaceOnUse"><path d="M 40 0 L 0 0 0 40" fill="none" stroke="#e9ecf1" strokeWidth="1" /></pattern></defs>
              <rect width="760" height="560" fill="url(#minor-grid)" />
              <line x1="0" y1="286" x2="760" y2="286" className="axis" /><line x1="282" y1="0" x2="282" y2="560" className="axis" />
              <circle cx="367" cy="286" r="185" className="primary-shape" />
              <polyline points="242,154 205,356 520,400 554,206 242,154" className="primary-shape" />
              <line x1="440" y1="0" x2="680" y2="560" className="witness-line" />
              {overlay && <><line x1="390" y1="286" x2="554" y2="206" className="witness-guide" /><line x1="390" y1="286" x2="520" y2="400" className="witness-guide" /><path d="M 546 210 l 7 14 l 14 -7" className="right-angle" /></>}
              {Object.values(points).map((point) => <g key={point.label} className={`point-group ${selected === point.label ? "selected-point" : ""}`} tabIndex={0} role="button" aria-label={`点${point.label} ${point.detail}`} onClick={(event) => { event.stopPropagation(); setSelected(point.label); }}><circle cx={point.x} cy={point.y} r="5" /><text x={point.x + 12} y={point.y - 12}>{point.label}</text>{point.detail && <text className="point-detail" x={point.x + 12} y={point.y + 11}>{point.detail}</text>}</g>)}
              <text x="467" y="45" className="tangent-label">t</text><text x="650" y="510" className="scale-label">2 units</text><line x1="610" y1="520" x2="700" y2="520" className="scale-line" />
            </svg>
            <div className="zoom-controls"><button type="button" aria-label="拡大" onClick={() => setZoom(Math.min(1.4, zoom + 0.1))}><Plus /></button><button type="button" aria-label="縮小" onClick={() => setZoom(Math.max(0.8, zoom - 0.1))}><Minus /></button></div>
          </div>
          <div className="editor-panel">
            <div className="editor-tabs" role="tablist">
              <button role="tab" aria-selected={activeEditor === "command"} onClick={() => setActiveEditor("command")}>コマンド</button>
              <button role="tab" aria-selected={activeEditor === "json"} onClick={() => setActiveEditor("json")}>JSON</button>
              <button role="tab" aria-selected={activeEditor === "log"} onClick={() => setActiveEditor("log")}>ログ</button>
            </div>
            {activeEditor === "command" && <div className="command-area"><span className="line-number">1</span><div className="command-stack"><div className="command-row"><input value={command} onChange={(event) => setCommand(event.target.value)} onFocus={() => setCommandFocused(true)} aria-label="V15コマンド" /><button type="button" onClick={() => commit({ ...problem, answer: command })}><Play weight="fill" />実行<CaretDown /></button></div>{commandFocused && <div className="autocomplete">{filteredCommands.map(([name, signature]) => <button key={signature} type="button" onMouseDown={() => { setCommand(`${name}(`); setCommandFocused(false); }}><strong>{name}</strong><span>{signature.slice(name.length)}</span></button>)}</div>}</div><span className="enter-hint">Enter で実行</span></div>}
            {activeEditor === "json" && <div className="json-editor"><textarea value={jsonText} onChange={(event) => updateJson(event.target.value)} aria-label="V15 JSON" spellCheck={false} />{jsonError && <p>{jsonError} — raw JSONは保持されています。</p>}</div>}
            {activeEditor === "log" && <div className="log-view"><code>{phase === "running" ? `[${elapsed}s] champion reference window: running` : `[ready] project ${problem.id} validated locally`}</code></div>}
          </div>
        </section>

        <aside className="solver-pane" aria-label="ターゲットとリソース">
          <section className="inspector-section resource-section">
            <h2>ターゲットとリソース</h2>
            <label>ターゲット<div className="select-like"><span>T1</span><code>{problem.answer}</code><CaretDown /></div></label>
            <h3>リソース設定</h3>
            <div className="resource-grid"><label>時間制限 (秒)<input type="number" min={180} value={timeLimit} onChange={(event) => setTimeLimit(Number(event.target.value))} /></label><label>コア数<input type="number" min={1} value={cores} onChange={(event) => setCores(Number(event.target.value))} /></label><label>シード<input type="number" value={seed} onChange={(event) => setSeed(Number(event.target.value))} /></label></div>
          </section>
          <section className="inspector-section execution-section">
            <div className="section-title-row"><h3>実行状況</h3><span>経過 <strong>{running ? `${elapsed} 秒` : `${result.elapsed_seconds.toFixed(1)} 秒`}</strong></span></div>
            <div className="phase-track"><div className={`phase-node ${phase !== "idle" ? "complete" : ""}`}><i />初期化</div><div className={`phase-node ${running ? "active" : result.answers.length ? "complete" : ""}`}><i />探索</div><div className={`phase-node ${phase === "done" ? "complete" : "active"}`}><i />証明</div><div className="phase-node"><i />検証</div><div className="phase-node"><i />完了</div></div>
            <div className="solve-actions"><button className="primary-action" type="button" disabled={running} onClick={startSolve}><Play weight="fill" />{running ? "実行中" : "解く"}</button><button className="cancel-action" type="button" disabled={!running} onClick={cancelSolve}><Stop />実行を中止</button></div>
          </section>
          <section className="inspector-section result-section">
            <h3>厳密解 <span>(Exact)</span></h3>
            {result.warnings[0] && <div className="warning-strip">{result.warnings[0]}</div>}
            {answer ? <div className="exact-result"><div className="answer-value"><span>値</span><strong>{Number(answer.decimal || 40).toPrecision(2)}</strong></div><dl><div><dt>最小多項式</dt><dd>{polynomialText(answer)}</dd></div><div><dt>選択された実根</dt><dd>#{answer.selected_real_root_index}</dd></div><div className="wide"><dt>隔離区間</dt><dd>[{answer.isolating_interval.join(", ")}]</dd></div></dl><div className="result-meta"><dl><div><dt>エンジン</dt><dd>champion-v2-poc-preloaded</dd></div><div><dt>エンジンhash</dt><dd><code>{result.engine_hash.slice(0, 16)}</code></dd></div><div><dt>チェックポイント</dt><dd><code>{result.work_checkpoint.plan_sha256?.slice(0, 16) || "—"}</code></dd></div></dl></div></div> : <div className="empty-result"><strong>{result.status === "engine_error" ? "実行できませんでした" : result.status === "cancelled" ? "実行を中止しました" : "厳密解は見つかりませんでした"}</strong><p>{result.detail || "これは解なしの証明ではありません。"}</p></div>}
          </section>
          <section className="disclosure"><span>近似解 (Witness)</span><label className="switch">表示<input type="checkbox" checked={overlay} onChange={(event) => setOverlay(event.target.checked)} /><i /></label></section>
          <section className="disclosure"><span>オーバーレイ設定</span><CaretDown /></section>
        </aside>
      </main>
    </div>
  );
}
