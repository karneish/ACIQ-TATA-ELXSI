# Phase 7 — Dashboard & Reporting

Implemented in `aciq/intelligence/dashboard.py` (panels) + additive hooks in
`aciq/dashboard.py` (`build_from_samples(..., intelligence=...)`,
`render_page(..., intelligence=...)`). Default empty → **existing pages are
byte-identical** (the six-panel pin in `tests/test_intent.py` — exactly the
`latency/jitter/loss/throughput/queue_depth/fairness` keys — still passes).

## New section (read-only, after the six base panels)
- **Tiles**: decisions recorded (Observed), latest action (Verified), experiences
  stored with status breakdown (Verified measured outcomes only).
- **Prediction panel**: capacity + degradation-severity series, titled
  *"Prediction (Estimated — never a measurement)"*.
- **Decisions list**: last 12 — t, action, reason, badge (Observed vs Verified
  when a candidate was selected).
- **Experiences list**: last 12 — status + measured evidence; measured records
  badge *Verified*, simulation/prediction records badge *Predicted*.

## Honesty rules enforced
- Predicted ≠ Observed ≠ Verified are separate badges on every value.
- Empty everything renders **nothing** (no empty section, no placeholder zeros).
- No control element, no JS, no external requests — same read-only contract.

## Tests (7, `tests/test_intelligence_dashboard.py`)
Empty→nothing · badges present · prediction series · summary counts ·
**base page unchanged by default (still exactly 6 panels)** ·
with-section page renders 7 · `PANELS` tuple untouched.
