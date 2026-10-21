# R1 tokenizer compatibility incident

`screen-r1_8b` is invalid and excluded from all model-performance summaries. It was interrupted after 309.40 seconds, with four saved answers. Its raw files and failed receipt remain intact. Compute expenditure still includes this attempt.

The published R1 tokenizer JSON specifies a ByteLevel BPE pipeline, but its metadata names `LlamaTokenizerFast`. In the installed Transformers 5.17, `AutoTokenizer` resolves that legacy name to `LlamaTokenizer` and replaces the pipeline with SentencePiece-style processing. This was not merely a display issue: encoding `The triangle is right.` and decoding the IDs returned `Thetriangleisright.`, while `ABCの外心をOとする。` became `ABCO`. Saved prompt IDs differed from the published tokenizer JSON, so the run cannot measure model ability.

The repair creates a local tokenizer directory under the runtime folder. Its `tokenizer.json` is copied byte-for-byte from the pinned model snapshot; only the class metadata is changed to `PreTrainedTokenizerFast`, which preserves the published pipeline. The original chat template and all special token IDs are retained. Both the input driver and vLLM use this repaired tokenizer directory. No model weight or sampling change was made.

`tokenizer-audit.json` records canonical token ID equality and lossless round trips on all 12 screen, 16 confirmation and 4 target-development prompts. The other three models' 72 saved screen answers have canonical input IDs and matching decoded output; they are unaffected.

The valid retry is `screen-corrected-r1_8b`, using the same fixed questions, seeds, BF16 weights, 8192 output limit, and two-sequence screen scheduling. `infer_screen_v1.py` preserves the old driver for auditing. The corrected driver hashes and model metadata hash are saved in each new receipt.

Separately, the Transformers warning about R1's legacy RoPE `attn_factor` field was audited. The configuration retains that field and installed vLLM forwards it into its YaRN implementation; inference does not silently discard it. This check does not establish a matching future Transformers training path for R1. That must be verified if R1 is chosen for updating weights.
