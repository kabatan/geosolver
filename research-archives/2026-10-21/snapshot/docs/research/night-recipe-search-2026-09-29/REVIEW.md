# Condition-hidden review procedure

Read `review/blind-packets.json` without opening its condition mapping. Each
packet includes the exact question, the generated final text, the expected
numeric value, and a condition-free ID. Byte-identical question/output pairs
share a review. All naturally terminated numeric successes must be reviewed.
Packets do not contain adapter paths or condition names. The reviewer is the
executing assistant, not an independently recruited reviewer.

For each packet record:

- `valid`: a coherent derivation or a correct applicable geometric relation
  connects the hypotheses to the answer. Standard or specialized known results
  may be used without reproof for this numeric task.
- `invalid`: a wrong inference, unjustified decisive relation, inconsistent
  algebra, circular assumption, guessed number, or an abandoned false proof is
  essential to the committed answer. Merely arriving at the right number fails.
- `unclear`: insufficient detail to establish a decisive step. This is zero in
  the primary analysis. A separately flagged lenient assessment may count an
  applicable known relation stated too tersely, but cannot rescue a wrong one.

An output can correct an earlier mistake if it clearly replaces that reasoning
with a valid complete route. Do not reject a correct coordinate solution for
being algebraic. Do not insist the model rediscover an elementary theorem.
For the source problem's hidden specialized result, distinguish an asserted
correct applicable property (allowed) from an asserted lemma that is false or
not supported by the actual configuration. Record the exact decisive passage.

Save packet ID, verdict, lenient verdict, rationale, and relevant excerpt in
`review/grades.json`. Only then join the frozen condition mapping, count primary
successes, and apply the preregistered exploratory branch gate.

If extensions are necessary, review only the final common-cap output. Previous
outputs stay archived but are not alternative attempts from which to choose.
Incomplete/capped output is censored and never counted as a natural-stop success.
