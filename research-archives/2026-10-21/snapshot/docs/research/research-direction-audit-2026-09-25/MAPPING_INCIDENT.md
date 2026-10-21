# Invalid first evaluation and correction

The initial new pilot driver passed the raw text-model PEFT adapters directly
to vLLM. This omitted the already documented Qwen3.5 conditional-wrapper name
mapping. Both trained checkpoints themselves passed all 400 tensor reload
checks, but this is insufficient to establish inference application.

The first matching treatment/control output had identical completion IDs. An
inspection of the tensor names found `base_model.model.model.layers.*` instead
of the required `base_model.model.model.language_model.layers.*`. This is the
known issue documented in the earlier ADAPTER_MAPPING_AUDIT.md; the present
driver should have reused that mapping before evaluation. It is an execution
error in this new pilot, not an additional negative learning result.

The first treatment generation completed four answers; the first control
generation was interrupted. Both raw evaluation directories (`eval-treatment`
and `eval-control`) are INVALID for trained-condition inference and excluded
from all grading and effect claims. Their artifacts are retained. No answer
text was read; only completion metadata/equality and tensor keys were examined.

Correction: keep the exact trained numerical weights and protocol, create
inference copies using the existing `map_vllm_adapter.py`, verify all mapped
tensor values against the originals, and test base/raw/mapped first-token
log probabilities. Require an observable mapped-adapter effect before running
the eight originally specified jobs into new `eval-mapped-*` directories.
The repair uses no answer-based checkpoint, prompt, dose, or seed selection.
Record the corrected driver and mapping hashes before these outputs.

`run_bridge_pilot.py` is retained as the original failed execution record;
use `repair_bridge_pilot.py` for the corrected inference stage. Existing earlier
research evaluations used their mapped adapters and are not reclassified by
this incident.
