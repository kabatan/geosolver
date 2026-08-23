import {
  Check,
  Code,
  DotsThreeVertical,
  DownloadSimple,
  FloppyDisk,
  FolderOpen,
  ListDashes,
  Wrench,
  X,
} from "@phosphor-icons/react";
import {
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type KeyboardEvent,
  type RefObject,
} from "react";

type AppBarProps = {
  projectName: string;
  modalOpen: boolean;
  importRef: RefObject<HTMLInputElement | null>;
  onImport: (event: ChangeEvent<HTMLInputElement>) => void;
  onExportProject: () => void;
  onExportJson: () => void;
  sourceTriggerRef: RefObject<HTMLButtonElement | null>;
  sourceOpen: boolean;
  onToggleSource: () => void;
  inspectorTriggerRef: RefObject<HTMLButtonElement | null>;
  inspectorOpen: boolean;
  onToggleInspector: () => void;
  doctor?: { ok: boolean; errors?: unknown[] };
  mobileStage: "draw" | "constrain" | "solve";
  mobileStageCount: number;
  mobileModelOpen: boolean;
  mobileModelTriggerRef: RefObject<HTMLButtonElement | null>;
  onToggleMobileModel: () => void;
};

export function AppBar({
  projectName,
  modalOpen,
  importRef,
  onImport,
  onExportProject,
  onExportJson,
  sourceTriggerRef,
  sourceOpen,
  onToggleSource,
  inspectorTriggerRef,
  inspectorOpen,
  onToggleInspector,
  doctor,
  mobileStage,
  mobileStageCount,
  mobileModelOpen,
  mobileModelTriggerRef,
  onToggleMobileModel,
}: AppBarProps) {
  const [compactMenuOpen, setCompactMenuOpen] = useState(false);
  const compactMenuRef = useRef<HTMLDivElement | null>(null);
  const compactMenuTriggerRef = useRef<HTMLButtonElement | null>(null);
  const mobileStageLabel =
    mobileStage === "draw"
      ? "DRAW"
      : mobileStage === "constrain"
        ? "CONSTRAIN"
        : "SOLVE";

  useEffect(() => {
    if (!compactMenuOpen) return;
    const closeFromOutside = (event: PointerEvent) => {
      if (!compactMenuRef.current?.contains(event.target as Node)) {
        setCompactMenuOpen(false);
      }
    };
    const closeFromEscape = (event: globalThis.KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      setCompactMenuOpen(false);
      compactMenuTriggerRef.current?.focus();
    };
    window.addEventListener("pointerdown", closeFromOutside);
    window.addEventListener("keydown", closeFromEscape);
    return () => {
      window.removeEventListener("pointerdown", closeFromOutside);
      window.removeEventListener("keydown", closeFromEscape);
    };
  }, [compactMenuOpen]);

  useEffect(() => {
    if (modalOpen) setCompactMenuOpen(false);
  }, [modalOpen]);

  const runCompactAction = (action: () => void) => {
    setCompactMenuOpen(false);
    action();
  };
  const moveCompactMenuFocus = (event: KeyboardEvent<HTMLDivElement>) => {
    if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;
    const items = [
      ...event.currentTarget.querySelectorAll<HTMLButtonElement>(
        '[role="menuitem"]:not([disabled])',
      ),
    ];
    if (!items.length) return;
    event.preventDefault();
    const activeIndex = items.indexOf(document.activeElement as HTMLButtonElement);
    if (event.key === "Home") items[0].focus();
    else if (event.key === "End") items.at(-1)?.focus();
    else if (event.key === "ArrowDown")
      items[(activeIndex + 1 + items.length) % items.length].focus();
    else items[(activeIndex - 1 + items.length) % items.length].focus();
  };
  return (
    <header
      className="app-bar"
      inert={modalOpen ? true : undefined}
      aria-hidden={modalOpen || undefined}
    >
      <div className="product-context">
        <div className="brand-lockup">
          <div className="brand">GEOTARGET</div>
          <span aria-hidden="true">/</span>
          <strong className="project-name">{projectName}</strong>
        </div>
      </div>
      <button
        ref={mobileModelTriggerRef}
        className="mobile-workbench-trigger"
        aria-label={`作図ナビゲーションを開く。現在 ${mobileStageLabel}`}
        aria-controls="model-navigator"
        aria-expanded={mobileModelOpen}
        onClick={onToggleMobileModel}
      >
        <ListDashes />
        <span>{mobileStageLabel}</span>
        <strong>{mobileStageCount}</strong>
      </button>
      <div className="app-actions">
        <input
          ref={importRef}
          className="visually-hidden"
          tabIndex={-1}
          type="file"
          accept=".json,.geotarget.json"
          onChange={onImport}
        />
        <div className="app-action-group file-actions">
          <button title="プロジェクトを読み込む" onClick={() => importRef.current?.click()}>
            <FolderOpen />
            <span>読み込む</span>
          </button>
          <button title="プロジェクトを書き出す" onClick={onExportProject}>
            <DownloadSimple />
            <span>プロジェクト</span>
          </button>
          <button title="V15 JSONを書き出す" onClick={onExportJson}>
            <FloppyDisk />
            <span>V15 JSON</span>
          </button>
          <button
            ref={sourceTriggerRef}
            className="source-drawer-trigger"
            title={sourceOpen ? "Sourceを閉じる" : "Sourceを開く"}
            aria-controls="advanced-source-drawer"
            aria-expanded={sourceOpen}
            onClick={onToggleSource}
          >
            <Code />
            <span>Source</span>
          </button>
        </div>
        <div className="app-action-group status-actions">
          <span
            className={`doctor-status ${doctor?.ok === false ? "bad" : ""}`}
            title={
              doctor?.ok === false
                ? "実行環境の整合性チェックに問題があります。問題式の検証状態とは別です。"
                : "実行環境の整合性チェック"
            }
          >
            {doctor?.ok ? (
              <Check weight="bold" />
            ) : doctor ? (
              <X weight="bold" />
            ) : null}
            {doctor
              ? doctor.ok
                ? "Engine checks: clear"
                : `Engine checks: ${doctor.errors?.length || 1} issue${doctor.errors?.length === 1 ? "" : "s"}`
              : "Engine checks: running"}
          </span>
          <button
            ref={inspectorTriggerRef}
            className="inspector-drawer-trigger"
            aria-controls="solver-inspector"
            aria-expanded={inspectorOpen}
            onClick={onToggleInspector}
          >
            <Wrench />
            Inspector / Solver
          </button>
        </div>
        <div ref={compactMenuRef} className="compact-actions">
          <button
            ref={compactMenuTriggerRef}
            className="compact-actions-trigger"
            aria-label="Projectと実行環境メニュー"
            aria-controls="compact-action-menu"
            aria-expanded={compactMenuOpen}
            onClick={() => setCompactMenuOpen((open) => !open)}
          >
            <DotsThreeVertical weight="bold" />
          </button>
          {compactMenuOpen && (
            <div
              id="compact-action-menu"
              className="compact-action-menu"
              role="menu"
              aria-label="Projectと実行環境"
              onKeyDown={moveCompactMenuFocus}
            >
              <div className="compact-menu-title">
                <strong>PROJECT</strong>
                <span>{projectName}</span>
              </div>
              <button
                role="menuitem"
                onClick={() =>
                  runCompactAction(() => importRef.current?.click())
                }
              >
                <FolderOpen />
                読み込む
              </button>
              <button
                role="menuitem"
                onClick={() => runCompactAction(onExportProject)}
              >
                <DownloadSimple />
                プロジェクトを書き出す
              </button>
              <button
                role="menuitem"
                onClick={() => runCompactAction(onExportJson)}
              >
                <FloppyDisk />
                V15 JSONを書き出す
              </button>
              <button
                role="menuitem"
                onClick={() => runCompactAction(onToggleSource)}
              >
                <Code />
                {sourceOpen ? "Sourceを閉じる" : "Sourceを開く"}
              </button>
              <div
                className={`compact-doctor-status ${doctor?.ok === false ? "bad" : ""}`}
                role="status"
              >
                <span>ENGINE INTEGRITY</span>
                <strong>
                  {doctor
                    ? doctor.ok
                      ? "Checks clear"
                      : `${doctor.errors?.length || 1} issue${doctor.errors?.length === 1 ? "" : "s"}`
                    : "Checking…"}
                </strong>
                <small>Target validationとは別の実行環境チェック</small>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
