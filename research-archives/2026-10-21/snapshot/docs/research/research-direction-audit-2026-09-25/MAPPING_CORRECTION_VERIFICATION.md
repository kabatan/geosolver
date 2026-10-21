# Verification after the mapping incident

The corrected effect check is saved in BRIDGE_ADAPTER_EFFECT.json. Raw adapter
vs base had exactly zero top-token log-probability difference on H01 and H14;
mapped treatment/control both changed probabilities (maximum common-top-token
differences about 3.14 on H01 and 4.35/4.59 on H14). All 400 mapped numerical
tensors equal their raw counterparts. The first effect-check script required
a multiprocessing main guard; that initialization failure occurred before any
scored generation. The repaired script and mapping are frozen in
BRIDGE_MAPPING_FREEZE_v2.json. No training rerun or outcome-driven selection
was made. Original faulty outputs are excluded, as recorded in MAPPING_INCIDENT.md.
