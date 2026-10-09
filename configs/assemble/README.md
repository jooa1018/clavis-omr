# assemble

Owner: W8.

`rules.yaml` catalogs all first-path theory/assembly rules and their provisional
implementation status. It uses the JSON subset of YAML so the offline engine can
read it without introducing a YAML dependency. Every `enabled` flag is consumed
by `Rules.from_catalog(path)` and supplied to `assemble_staff(..., rules=...)`.

Disabling a foundational rule makes this first oracle path unavailable; it does
not authorize alternative pitches, fabricated rests or bypassing validation.
Unit ablations verify this. Corpus contribution estimates remain NOT_RUN until
SYN-Val-quick/Dev v0 exist, per Orchestrator's 2026-09-29 Wave B notice.

`constants.yaml` is empty: there are no geometry/confidence/tuning thresholds.
Pitch anchors, accidental values and quarter-note ratios are exact definitions
from CONTRACTS 5.1–5.3, covered exhaustively by unit tests. Future recognition
constants must be registered with provisional status, source and evidence.
