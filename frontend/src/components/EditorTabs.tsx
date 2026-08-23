import { CaretDown, CaretUp } from "@phosphor-icons/react";

export type EditorTab = "command" | "json" | "details";

const TABS: readonly EditorTab[] = ["command", "json", "details"];

const TAB_LABELS: Readonly<Record<EditorTab, string>> = {
  command: "ターゲット",
  json: "V15 JSON",
  details: "描画ログ",
};

const TAB_PANEL_IDS: Readonly<Record<EditorTab, string>> = {
  command: "panel-command",
  json: "panel-json",
  details: "panel-details",
};

const TAB_IDS: Readonly<Record<EditorTab, string>> = {
  command: "tab-command",
  json: "tab-json",
  details: "tab-details",
};

export function EditorTabs({
  tab,
  onChange,
  expanded = true,
  onToggleExpanded,
}: {
  tab: EditorTab;
  onChange: (tab: EditorTab) => void;
  expanded?: boolean;
  onToggleExpanded?: () => void;
}) {
  return (
    <div className="editor-tabbar">
      <div
        className="editor-tabs"
        role="tablist"
        aria-label="問題エディター"
        onKeyDown={(event) => {
          if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key))
            return;
          event.preventDefault();
          const index = TABS.indexOf(tab);
          const next =
            event.key === "Home"
              ? TABS[0]
              : event.key === "End"
                ? TABS[2]
                : TABS[(index + (event.key === "ArrowRight" ? 1 : 2)) % 3];
          onChange(next);
          window.setTimeout(
            () =>
              document
                .querySelector<HTMLElement>(`[role="tab"][aria-selected="true"]`)
                ?.focus(),
            0,
          );
        }}
      >
        {TABS.map((item) => (
          <button
            key={item}
            id={TAB_IDS[item]}
            role="tab"
            aria-controls={TAB_PANEL_IDS[item]}
            aria-selected={tab === item}
            tabIndex={tab === item ? 0 : -1}
            onClick={() => {
              onChange(item);
              if (!expanded) onToggleExpanded?.();
            }}
          >
            {TAB_LABELS[item]}
          </button>
        ))}
      </div>
      {onToggleExpanded ? (
        <button
          className="editor-dock-toggle"
          aria-label={expanded ? "問題エディターを折りたたむ" : "問題エディターを開く"}
          aria-expanded={expanded}
          onClick={onToggleExpanded}
        >
          {expanded ? <CaretDown /> : <CaretUp />}
        </button>
      ) : null}
    </div>
  );
}
