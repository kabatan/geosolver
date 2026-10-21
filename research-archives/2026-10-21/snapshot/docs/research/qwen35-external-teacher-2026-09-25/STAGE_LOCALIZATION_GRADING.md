# Grading the fresh4 stage-localization probes

Fix these criteria before opening any fresh4 generation. The six fresh4
instances comprise two repeated numeric probes for each of H03, H04, and H14;
they are not independent construction families. Evaluate each answer after
explicit self-correction, but do not excuse unresolved contradictions.

Record separately:

1. **Mapping claim:** the model states the correct link between the
   problem-defined construction and the orthocenter/median projection.
   H03: each of `Pa,Pb,Pc` is the corresponding foot. H14: `R` is the foot
   from H to AM. H04: `P` is already defined as the foot in the original
   problem, so record `given_in_original_problem` instead of treating this as
   a discovered mapping. If a probe prompt supplies the claim, record
   `supplied`, not a model discovery.
2. **Mapping proof:** the *model's own answer* derives the link from the
   construction with the decisive algebra/geometry, correct selected
   intersection, signs, nonzero factors, and point order. A claim copied
   from a cue is not proof. In the proof-supplied condition record
   `supplied_in_prompt`; it cannot pass the independent-proof criterion.
3. **Downstream relation/proof:** H03 must connect the feet to the
   diameter-HG circle and its center and justify the centroid/orthocenter
   relation used for OZ. H04 must derive the perpendicular-bisector equation
   and exterior-branch product. H14 must use the projection to derive the
   right-triangle area with the correct branch. Record a true relation and
   its decisive justification separately.
4. **Exact application:** the final exact value and substitution are correct.
   A guessed value may pass exact value alone, but not downstream use.

For the unhinted base and directly taught same-ID adapter, a complete proof
requires a self-contained decisive construction argument, branch validity,
and exact application. A mathematically sound alternative route can count as
complete without explicitly using the orthocenter projection; record
`alternative_valid_proof` and explain its decisive construction step rather
than forcing projection-mapping credit. For the general-lemma condition, the
lemma is provided and cannot count as independent relation discovery; any
target-specific mapping used and the downstream proof still must be
model-generated.
For the mapping-claim condition, mapping discovery is supplied; only an
independent mapping proof can receive mapping-proof credit. For the
mapping-proof-supplied condition, score conditional downstream execution and
exact answer, **never independent proof or transfer**.

Compare paired jobs under the same base weights, numeric inputs, random seed,
and decoding settings, and report every item, completion length, and finish
reason. Prompt length/content differences mean this is an intervention ladder
for diagnosis, not a clean causal decomposition or an SFT success measure.
