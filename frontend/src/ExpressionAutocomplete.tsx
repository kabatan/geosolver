import {
  CSSProperties,
  FocusEvent,
  KeyboardEvent,
  MouseEvent,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";

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
  onCommit?: (value: string) => boolean | void;
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
  let end = caret;
  while (end < value.length && /[A-Za-z0-9_]/.test(value[end])) end += 1;
  return { start: match?.index ?? caret, end, query: match?.[0] ?? "" };
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
  const committedByEnterRef = useRef(false);
  const [focused, setFocused] = useState(false);
  const [caret, setCaret] = useState(value.length);
  const [active, setActive] = useState(0);
  const [popupStyle, setPopupStyle] = useState<CSSProperties>();
  const range = completionRange(value, caret);
  const matches = useMemo(() => {
    if (!focused) return [];
    const query = range.query.toLocaleLowerCase();
    if (!query && value.trim()) return [];
    return suggestions
      .map((item, order) => {
        const label = item.label.toLocaleLowerCase();
        const keywords = (item.keywords ?? "").toLocaleLowerCase();
        const detail = item.detail.toLocaleLowerCase();
        const keywordTokens = keywords.split(/[^a-z0-9_]+/).filter(Boolean);
        const score = !query
          ? 5
          : label === query || keywordTokens.includes(query)
            ? 0
            : label.startsWith(query) || keywordTokens.some((word) => word.startsWith(query))
              ? 1
              : label.includes(query)
                ? 2
                : keywords.includes(query)
                  ? 3
                  : detail.includes(query)
                    ? 4
                    : 6;
        return { item, order, score };
      })
      .filter(({ score }) => {
        if (!query) return true;
        return score < 6;
      })
      .sort((left, right) => left.score - right.score || left.order - right.order)
      .slice(0, 8)
      .map(({ item }) => item);
  }, [focused, range.query, suggestions, value]);
  const open = matches.length > 0;
  const listId = `${dataMathField ?? ariaLabel.replace(/\s+/g, "-")}-suggestions`;

  useLayoutEffect(() => {
    if (!open) {
      setPopupStyle(undefined);
      return;
    }
    const positionPopup = () => {
      const editor = editorRef.current;
      if (!editor) return;
      const rect = editor.getBoundingClientRect();
      const margin = 8;
      const viewportWidth = window.innerWidth;
      const viewportHeight = window.innerHeight;
      const width = Math.min(
        560,
        Math.max(rect.width, Math.min(440, viewportWidth - margin * 2)),
        viewportWidth - margin * 2,
      );
      const left = Math.max(
        margin,
        Math.min(rect.left, viewportWidth - width - margin),
      );
      const below = viewportHeight - rect.bottom - margin;
      const above = rect.top - margin;
      const placeAbove = below < 180 && above > below;
      const maxHeight = Math.max(120, Math.min(320, placeAbove ? above : below));
      setPopupStyle({
        left,
        width,
        maxHeight,
        ...(placeAbove
          ? { bottom: viewportHeight - rect.top + 4 }
          : { top: rect.bottom + 4 }),
      });
    };
    positionPopup();
    window.addEventListener("resize", positionPopup);
    window.addEventListener("scroll", positionPopup, true);
    return () => {
      window.removeEventListener("resize", positionPopup);
      window.removeEventListener("scroll", positionPopup, true);
    };
  }, [open]);

  const updateCaret = (editor: Editor) => {
    setCaret(editor.selectionStart ?? editor.value.length);
    setActive(0);
  };
  const apply = (item: ExpressionSuggestion) => {
    const editor = editorRef.current;
    // Complete the whole identifier, including the suffix to the right of a
    // caret that was moved into the middle of a word.  Function suggestions
    // already contain "(", so consume an existing opening parenthesis too.
    // Without both rules, `Ang|le(` became `Angle(le(` and `Angle|(` became
    // `Angle((`, silently corrupting otherwise valid geometry conditions.
    const end =
      item.insert.endsWith("(") && value[range.end] === "("
        ? range.end + 1
        : range.end;
    const next = `${value.slice(0, range.start)}${item.insert}${value.slice(end)}`;
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
      if (onCommit?.(value) === false) return;
      committedByEnterRef.current = true;
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
      committedByEnterRef.current = false;
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
      if (committedByEnterRef.current) {
        committedByEnterRef.current = false;
        return;
      }
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
      {open && popupStyle && createPortal(
        <div
          className="expression-suggestions"
          id={listId}
          role="listbox"
          style={popupStyle}
        >
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
        </div>,
        document.body,
      )}
    </div>
  );
}
