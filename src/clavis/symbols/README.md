# symbols — W6 provisional component baseline

`templates.template_responses` keeps separate, quantized grayscale NCC responses
from original and staff-removed strips. `detection.detect` produces notehead,
stem/barline and competing stem-link evidence. Callers supply normalized strip
pixels, staff spacing, top staff row, a template bank, settings and a producer
digest. This module does not extract strips or calculate pitch.

Load settings with `Settings.load(Path("configs/symbols/constants.yaml"))`.
The registry is JSON-compatible YAML. Decision rules are catalogued in
`configs/symbols/rules.yaml`; disable detector rules using `disabled=frozenset({id})`.
Scores and Gaussian pos/line distributions are **uncalibrated provisional values**,
authorized for initial component work by the Orchestrator notice of 2026-09-29.
No Dev image or result was used to choose them.

`reading.draft_reading(graph, producer)` preserves head-class alternatives,
observed duration/pos/dots/voice distributions and competing stem evidence in up
to eight hypotheses. Missing attributes remain unknown. Unsupported evidence is
returned in `ReadingDraft.unresolved_symbol_ids`. Both reading rules have separate
on/off arguments (`enabled`, `durations_enabled`).

This is **not yet a complete strip-to-lattice recognizer**: the detector does not
estimate beam/flag or dots/voice attributes, and the reader does not recognize
clefs, bar styles, chords or other notation. It must not invent these values.
The typed proposal passes v0.1 wire validation but production finalization needs
W1's normalizer/grammar callback. There is deliberately no default grammar stub.
Fixtures supply attributes only in tests; the runtime never loads fixtures.

```text
uv sync --locked --all-groups
uv run --locked --all-groups pytest tests/symbols --cov=clavis.symbols
uv run --locked --all-groups python -m training.models.symbols.component_smoke work/w6-component.json
```

Numpy/OpenCV are already pinned in the repository training group. W1 must include
them in runtime packaging before deployment; this component PR does not modify
W1-owned dependency declarations. Template binaries remain in `work/`.
Production producer hashes must cover code, settings, rules and template bytes.
