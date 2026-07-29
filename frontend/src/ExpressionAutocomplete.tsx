import {
  FocusEvent,
  KeyboardEvent,
  MouseEvent,
  useMemo,
  useRef,
  useState,
} from "react";

export type ExpressionSuggestion = {
  id: string;
  label: string;
  detail: string;
  insert: string;
  keywords?: string;
};

type Editor = HTMLInputElement | HTMLTextAreaElement;

type Props = {
  value: string;
  onChange: (value: string) => void;
  onCommit?: (value: string) => void;
  onEditorFocus?: (editor: Editor) => void;
  onEditorClick?: (editor: Editor) => void;
  onEscape?: () => void;
  suggestions: readonly ExpressionSuggestion[];
  ariaLabel: string;
  ariaControls?: string;
  ariaDescribedBy?: string;
  dataMathField?: string;
  className?: string;
  multiline?: boolean;
  commitOnEnter?: boolean;
  autoFocus?: boolean;
};

function completionRange(value: string, caret: number) {
  const before = value.slice(0, caret);
  const match = /[A-Za-z_][A-Za-z0-9_]*$/.exec(before);
  return { start: match?.index ?? caret, end: caret, query: match?.[0] ?? "" };
}

export function ExpressionAutocomplete({
  value,
  onChange,
  onCommit,
  onEditorFocus,
  onEditorClick,
  onEscape,
  suggestions,
  ariaLabel,
  ariaControls,
  ariaDescribedBy,
  dataMathField,
  className,
  multiline = false,
  commitOnEnter = !multiline,
  autoFocus = false,
}: Props) {
  const editorRef = useRef<Editor>(null);
  const [focused, setFocused] = useState(false);
  const [caret, setCaret] = useState(value.length);
  const [active, setActive] = useState(0);
  const range = completionRange(value, caret);
  const matches = useMemo(() => {
    if (!focused) return [];
    const query = range.query.toLocaleLowerCase();
    if (!query && value.trim()) return [];
    return suggestions
      .map((item, order) => {
        const label = item.label.toLocaleLowerCase();
        const detail = `${item.detail} ${item.keywords ?? ""}`.toLocaleLowerCase();
        const score = !query
          ? 3
          : label.startsWith(query)
            ? 0
            : label.includes(query)
              ? 1
              : detail.includes(query)
                ? 2
                : 4;
        return { item, order, score };
      })
      .filter(({ score }) => {
        if (!query) return true;
        return score < 4;
      })
      .sort((left, right) => left.score - right.score || left.order - right.order)
      .slice(0, 8)
      .map(({ item }) => item);
  }, [focused, range.query, suggestions, value]);
  const open = matches.length > 0;
  const listId = `${dataMathField ?? ariaLabel.replace(/\s+/g, "-")}-suggestions`;

  const updateCaret = (editor: Editor) => {
    setCaret(editor.selectionStart ?? editor.value.length);
    setActive(0);
  };
  const apply = (item: ExpressionSuggestion) => {
    const editor = editorRef.current;
    const next = `${value.slice(0, range.start)}${item.insert}${value.slice(range.end)}`;
    const nextCaret = range.start + item.insert.length;
    onChange(next);
    setCaret(nextCaret);
    setActive(0);
    window.requestAnimationFrame(() => {
      editor?.focus();
      editor?.setSelectionRange(nextCaret, nextCaret);
      if (editor) onEditorFocus?.(editor);
    });
  };
  const keyDown = (event: KeyboardEvent<Editor>) => {
    if (open && ["ArrowDown", "ArrowUp"].includes(event.key)) {
      event.preventDefault();
      setActive((current) =>
        event.key === "ArrowDown"
          ? (current + 1) % matches.length
          : (current - 1 + matches.length) % matches.length,
      );
      return;
    }
    if (
      open &&
      (event.key === "Tab" ||
        (event.key === "Enter" && !event.ctrlKey && !event.metaKey))
    ) {
      event.preventDefault();
      apply(matches[active] ?? matches[0]);
      return;
    }
    if (event.key === "Escape") {
      event.preventDefault();
      setFocused(false);
      if (!open) onEscape?.();
      return;
    }
    if (
      event.key === "Enter" &&
      (commitOnEnter || event.ctrlKey || event.metaKey)
    ) {
      event.preventDefault();
      onCommit?.(value);
      event.currentTarget.blur();
    }
  };
  const common = {
    ref: editorRef as never,
    value,
    className,
    role: "combobox" as const,
    "aria-label": ariaLabel,
    "aria-autocomplete": "list" as const,
    "aria-haspopup": "listbox" as const,
    "aria-expanded": open,
    "aria-controls": `${listId}${ariaControls ? ` ${ariaControls}` : ""}`,
    "aria-activedescendant": open
      ? `${listId}-${matches[active]?.id}`
      : undefined,
    "aria-describedby": ariaDescribedBy,
    "data-math-field": dataMathField,
    autoFocus,
    autoComplete: "off",
    spellCheck: false,
    onChange: (event: { currentTarget: Editor }) => {
      setFocused(true);
      onChange(event.currentTarget.value);
      updateCaret(event.currentTarget);
    },
    onSelect: (event: { currentTarget: Editor }) =>
      updateCaret(event.currentTarget),
    onKeyDown: keyDown,
    onFocus: (event: FocusEvent<Editor>) => {
      setFocused(true);
      updateCaret(event.currentTarget);
      onEditorFocus?.(event.currentTarget);
    },
    onClick: (event: MouseEvent<Editor>) => {
      setFocused(true);
      updateCaret(event.currentTarget);
      onEditorClick?.(event.currentTarget);
    },
    onBlur: (event: FocusEvent<Editor>) => {
      setFocused(false);
      const next = event.relatedTarget;
      if (
        next instanceof Node &&
        document.getElementById("math-keyboard")?.contains(next)
      )
        return;
      onCommit?.(value);
    },
  };

  return (
    <div className="expression-autocomplete">
      {multiline ? <textarea {...common} /> : <input {...common} />}
      {open && (
        <div className="expression-suggestions" id={listId} role="listbox">
          {matches.map((item, index) => (
            <button
              key={item.id}
              id={`${listId}-${item.id}`}
              type="button"
              role="option"
              aria-selected={index === active}
              onPointerDown={(event) => {
                event.preventDefault();
                apply(item);
              }}
            >
              <strong>{item.label}</strong>
              <span>{item.detail}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
