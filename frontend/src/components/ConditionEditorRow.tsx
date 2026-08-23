import { useEffect, useState } from "react";
import { X } from "@phosphor-icons/react";
import {
  conditionDraftIssue,
} from "../mathFormat";
import { ExpressionAutocomplete, ExpressionSuggestion } from "../ExpressionAutocomplete";
import { MathFormula } from "../MathFormula";

type ConditionEditorProps = {
  formula: string;
  conditionIndex: number;
  suggestions: readonly ExpressionSuggestion[];
  normalizeDraft: (value: string) => string;
  mathKeyboardOpen: boolean;
  activeMathField: string;
  autoFocus?: boolean;
  registerMathTarget: (
    editor: HTMLInputElement | HTMLTextAreaElement,
    setter: (value: string) => void,
  ) => void;
  onCommit: (formula: string) => void;
  onDelete: () => void;
};

export function ConditionEditorRow({
  formula,
  conditionIndex,
  suggestions,
  normalizeDraft,
  mathKeyboardOpen,
  activeMathField,
  autoFocus,
  registerMathTarget,
  onCommit,
  onDelete,
}: ConditionEditorProps) {
  const [draft, setDraft] = useState(formula);
  const [draftIssue, setDraftIssue] = useState("");
  useEffect(() => {
    setDraft(formula);
    setDraftIssue("");
  }, [formula]);
  const field = `condition-${conditionIndex}`;
  const commitDraft = (value: string) => {
    const normalized = normalizeDraft(value);
    const issue = conditionDraftIssue(normalized);
    setDraftIssue(issue ?? "");
    if (issue) return false;
    onCommit(normalized);
    return true;
  };
  return (
    <div className="guard-row">
      <div className="formula-editor formula-editor-compact">
        <ExpressionAutocomplete
          value={draft}
          onChange={(value) => {
            setDraftIssue("");
            setDraft(normalizeDraft(value));
          }}
          onCommit={commitDraft}
          suggestions={suggestions}
          ariaLabel={`条件 ${conditionIndex}`}
          ariaControls="math-keyboard"
          ariaDescribedBy={
            mathKeyboardOpen && activeMathField === field
              ? "math-keyboard-status"
              : undefined
          }
          dataMathField={field}
          autoFocus={autoFocus}
          onEditorFocus={(editor) =>
            registerMathTarget(editor, (value) =>
              setDraft(normalizeDraft(value)),
            )
          }
          onEditorClick={(editor) =>
            registerMathTarget(editor, (value) =>
              setDraft(normalizeDraft(value)),
            )
          }
        />
        <MathFormula
          className="formula-preview"
          source={draft}
          label={`条件 ${conditionIndex}の数式表示`}
        />
        {draftIssue && (
          <p className="condition-draft-error" role="alert">
            {draftIssue}
          </p>
        )}
      </div>
      <button aria-label={`条件 ${conditionIndex}を削除`} onClick={onDelete}>
        <X />
      </button>
    </div>
  );
}
