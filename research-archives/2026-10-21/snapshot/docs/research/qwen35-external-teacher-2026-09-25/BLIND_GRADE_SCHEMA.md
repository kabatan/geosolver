# Blind scoring output

Each reviewer writes a JSON array with exactly one object per assigned `blind_id`:

```json
{
  "blind_id": "B001",
  "source_id": "H03",
  "exact": false,
  "relation": false,
  "proof": false,
  "use": false,
  "uncertain": false,
  "note": "Brief specific mathematical reason for the four decisions."
}
```

Use only `final_text` in the assigned condition-blind packet and the frozen answer key/rubric. Each Boolean is independent. `exact` means the final stated value is equivalent to the key; `relation` means a true construction-specific useful relation is stated; `proof` means its decisive derivation and branch are present; `use` means it is applied correctly to the fresh givens. `complete` is calculated later as the conjunction. Set `uncertain=true` for any borderline case needing a second review; keep the four provisional fields and explain the ambiguity. Do not read any condition mapping or adapter output path before the grade files are frozen.
