# Dataset hash provenance for the frozen fresh2 jobs

`hashes.json` records the source-file hashes **at the time the fresh2 evaluation jobs were frozen**. At that point, the balanced-QA candidate had SHA-256 `ffd0d6744da140f8287bdb5897ffd8196c93d5aa475cb637df855c3925ba36cc`. The QA targets were subsequently revised after independent mathematical audit to include complete self-contained proofs and balanced true/false claims. The final audited dataset has SHA-256 `da66b08c3d83ddd50bc7c1802030bee0da497b0821fb3378ef0cf07229326291`.

The original fresh2 job and answer-key hashes have not changed. The current `train-protocol-balanced-qa.json` records the final audited dataset hash and is the only QA protocol eligible for training. Its SHA-256 is listed in `train-protocol-hashes.json`. Any training receipt must match `da66…`; `ffd0…` is historical provenance, not the training input. Keeping both hashes preserves the sequence of the evaluation freeze and the later teacher correction.
