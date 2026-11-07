# Classifier accuracy — fresh corpus (current revision)

Source: `data/experiments/classifier_corpus_fresh/corpus.jsonl` (n=228) re-scored with the fixed classifier at HEAD. Heldout = tuple-parity half (n=120).

- BEFORE fix (frozen band): 61.0% strict / 74.1% broad (heldout 65.0%)
- AFTER fix (gaming summary-counter fallback + update packet-size discriminator + bulk-ambiguous 30-45 Mbps band): 92.1% strict (heldout 91.7%)

Per-class F1 after fix: adaptive_video_streaming 0.839, bulk_download 0.889,
cloud_backup 1.0, interactive_gaming 1.0, software_update 0.909, video_call_voice 1.0.

The frozen final band (`7c6c7235`) remains the acceptance authority; the accuracy gain above is post-band code. No verdict was rerun.
