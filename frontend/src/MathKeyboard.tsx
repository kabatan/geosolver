import { ArrowBendDownLeft, ArrowLeft, ArrowRight, Backspace, DotsThree } from "@phosphor-icons/react";
import { useMemo, useState, type KeyboardEvent } from "react";

type TabId = "numbers" | "functions" | "letters" | "symbols";
type MathKey = { label: string; insert?: string; caretBack?: number; action?: "backspace" | "left" | "right" | "enter"; split?: boolean };
const TABS: Array<{ id: TabId; label: string }> = [
  { id: "numbers", label: "123" }, { id: "functions", label: "f(x)" },
  { id: "letters", label: "ABC" }, { id: "symbols", label: "#&¬" },
];

const NUMBER_KEYS: MathKey[] = [
  { label: "x", insert: "x" }, { label: "y", insert: "y" }, { label: "π", insert: "π" }, { label: "e", insert: "e" },
  { label: "7", insert: "7", split: true }, { label: "8", insert: "8" }, { label: "9", insert: "9" }, { label: "×", insert: "*" }, { label: "÷", insert: "/" },
  { label: "x²", insert: "^2" }, { label: "xⁿ", insert: "^()", caretBack: 1 }, { label: "√x", insert: "sqrt()", caretBack: 1 }, { label: "|x|", insert: "abs()", caretBack: 1 },
  { label: "4", insert: "4", split: true }, { label: "5", insert: "5" }, { label: "6", insert: "6" }, { label: "+", insert: "+" }, { label: "−", insert: "-" },
  { label: "<", insert: "<" }, { label: ">", insert: ">" }, { label: "a⁄b", insert: "/" }, { label: "aₙ", insert: "_" },
  { label: "1", insert: "1", split: true }, { label: "2", insert: "2" }, { label: "3", insert: "3" }, { label: "=", insert: "=" }, { label: "削除", action: "backspace" },
  { label: "ans", insert: "ans" }, { label: ",", insert: ", " }, { label: "(", insert: "(" }, { label: ")", insert: ")" },
  { label: "0", insert: "0", split: true }, { label: ".", insert: "." }, { label: "左", action: "left" }, { label: "右", action: "right" }, { label: "確定", action: "enter" },
];

const SYMBOL_KEYS: MathKey[] = [
  { label: "≤", insert: "≤" }, { label: "≥", insert: "≥" }, { label: "≠", insert: "≠" }, { label: "=", insert: "=" },
  { label: "<", insert: "<" }, { label: ">", insert: ">" }, { label: "+", insert: "+" }, { label: "−", insert: "-" }, { label: "×", insert: "*" },
  { label: "÷", insert: "/" }, { label: "^", insert: "^" }, { label: "(", insert: "(" }, { label: ")", insert: ")" },
  { label: "[", insert: "[" }, { label: "]", insert: "]" }, { label: ",", insert: ", " }, { label: ".", insert: "." }, { label: "_", insert: "_" },
  { label: "π", insert: "π" }, { label: "e", insert: "e" }, { label: "sqrt", insert: "sqrt()", caretBack: 1 }, { label: "abs", insert: "abs()", caretBack: 1 },
  { label: "x", insert: "x" }, { label: "y", insert: "y" }, { label: "削除", action: "backspace" }, { label: "左", action: "left" }, { label: "右", action: "right" },
  { label: "空白", insert: " " }, { label: "確定", action: "enter" },
];

function keyIcon(action?: MathKey["action"]) {
  if (action === "backspace") return <Backspace weight="bold" />;
  if (action === "left") return <ArrowLeft weight="bold" />;
  if (action === "right") return <ArrowRight weight="bold" />;
  if (action === "enter") return <ArrowBendDownLeft weight="bold" />;
  return undefined;
}

export function MathKeyboard({ functions, onInsert, onBackspace, onMove, onEnter, onClose }: {
  functions: string[]; onInsert: (text: string, caretBack?: number) => void; onBackspace: () => void;
  onMove: (direction: -1 | 1) => void; onEnter: () => void; onClose: () => void;
}) {
  const [tab, setTab] = useState<TabId>("numbers");
  const functionKeys = useMemo<MathKey[]>(() => functions.map((name) => ({ label: name, insert: `${name}()`, caretBack: 1 })), [functions]);
  const letterKeys = useMemo<MathKey[]>(() => "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij".split("").map((letter) => ({ label: letter, insert: letter })), []);
  const keys = tab === "numbers" ? NUMBER_KEYS : tab === "functions" ? functionKeys : tab === "letters" ? letterKeys : SYMBOL_KEYS;
  function chooseTab(next: TabId) {
    setTab(next); window.requestAnimationFrame(() => document.getElementById(`math-keyboard-tab-${next}`)?.focus());
  }
  function moveTab(event: KeyboardEvent<HTMLDivElement>) {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault(); const index = TABS.findIndex((item) => item.id === tab);
    const next = event.key === "Home" ? TABS[0] : event.key === "End" ? TABS.at(-1)! : TABS[(index + (event.key === "ArrowRight" ? 1 : TABS.length - 1)) % TABS.length];
    chooseTab(next.id);
  }
  return <section id="math-keyboard" className="math-keyboard" aria-label="数式キーボード" onKeyDown={(event) => { if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); onClose(); } }}>
    <header className="math-keyboard-tabs">
      <div role="tablist" aria-label="数式キーボードの種類" onKeyDown={moveTab}>
        {TABS.map((item) => <button id={`math-keyboard-tab-${item.id}`} role="tab" aria-controls="math-keyboard-panel" aria-selected={tab === item.id} tabIndex={tab === item.id ? 0 : -1} className={tab === item.id ? "active" : ""} onMouseDown={(event) => event.preventDefault()} onClick={() => chooseTab(item.id)} key={item.id}>{item.label}</button>)}
      </div>
      <button className="math-keyboard-close" aria-label="数式キーボードを閉じる" title="キーボードを閉じる" onMouseDown={(event) => event.preventDefault()} onClick={onClose}><DotsThree weight="bold" /></button>
    </header>
    <div id="math-keyboard-panel" role="tabpanel" aria-label={`${TABS.find((item) => item.id === tab)?.label ?? tab} キー`} className={`math-key-grid math-key-grid-${tab}`}>
      {keys.map((key, index) => <button data-math-key="true" className={`${key.split ? "split" : ""} ${key.action ? `action-${key.action}` : ""}`} aria-label={key.action ? key.label : undefined} title={tab === "functions" ? key.label : undefined} key={`${tab}-${index}-${key.label}`} onMouseDown={(event) => event.preventDefault()} onClick={() => {
        if (key.action === "backspace") onBackspace(); else if (key.action === "left") onMove(-1); else if (key.action === "right") onMove(1); else if (key.action === "enter") onEnter(); else if (key.insert !== undefined) onInsert(key.insert, key.caretBack);
      }}>{keyIcon(key.action) ?? key.label}</button>)}
    </div>
  </section>;
}
