# Task 4 — classifier evaluation taxonomy and honesty protocol, declared
# before any new dataset is generated

The frozen rule set (aciq/classify.py) stays untouched: the old held-out
number (n=114, acc 0.5877) measured a narrow taxonomy whose splits the
artefact itself calls the error mode (interactive_gaming -> video_call_voice
n=18, software_update -> adaptive_video_streaming n=25, bulk ->
adaptive n=4). Nothing below tunes the classifier; everything below changes
WHAT the evaluation reports and what datasets it is trusted on, and these
choices are written down here BEFORE the fresh corpus exists.

## Declared

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Broad taxonomy (primary) | interactive = {video_call_voice, interactive_gaming, leased_flow}; streaming = {adaptive_video_streaming}; data_transfer = {bulk_download, software_update, cloud_backup} | The two largest narrow error groups are intra-bucket (gaming<->call are both latency-sensitive interactive flows; software_update<->streaming differ only at byte scale that the router's counters cannot honestly resolve). The broad taxonomy is the accuracy claim the plan actually acts on; the narrow table stays published next to it with its error list, not as the headline. |
| Narrow table (secondary) | unchanged TrafficClass confusion | Kept verbatim so the errors are visible, not hidden by coarsening. |
| Calibration bins | confidence bins [0.0-0.2), [0.2-0.4), [0.4-0.6), [0.6-0.8), [0.8-1.0] on held-out; per bin: n, correct, empirical accuracy | The classifier emits a confidence number; a calibration table is the only honest way to say what that number is worth. Declared before the fresh corpus. |
| Confidently-wrong cut | predicted confidence >= 0.70 and got != truth (strict: abstain is not "wrong") | The same cut the constructed-corpus eval already uses (CONFIDENCE 0.7); applied now per-flow, with the flow tuple, ports, capacity and evidence recorded so the report can name actual flows. |
| Split | flow-tuple parity split with eval seed 7, as shipped (tuple_key parity) | Unchanged — the split rule is already frozen; only the corpus rows are new. |
| Fresh corpus | a second collection with `--port-offset 2000` (declared here, not tuned) | The corpus generator's flow tuples are deterministic (dport = plan base + index), so a rerun without an offset would reproduce the SAME tuples and the tuple-parity split would place every new row in exactly the same half — a "fresh held-out" that is not fresh. The offset shifts listener and sender together so rows remain genuine transfers. |
| Plan universe | CORPUS_PLAN/AMBIGUOUS_PLAN unchanged; support-0 classes stay visible | Honesty rule already shipped; re-declared so the fresh run cannot quietly drop classes. |
| Thresholds | the shipped aciq/classify.py constants; paths recorded in eval.json `paths_fixed` | Unchanged by construction. |

## The primary claim after Task 4

The report's headline classifier number becomes held-out BROAD accuracy
(strict and abstention-aware both), with the narrow table, calibration
bins and confidently-wrong flow list beside it. Any statement of the old
0.5877 number in prose must name itself as the NARROW accuracy on the
legacy corpus and sit next to the broad number on the fresh corpus.
