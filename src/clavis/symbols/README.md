# symbols — W6 provisional component baseline

`templates.template_responses` keeps separate, quantized grayscale NCC responses
from original and staff-removed strips. `detection.detect` produces notehead,
stem/barline and competing stem-link evidence. Callers supply normalized strip
pixels, staff spacing, top staff row, a template bank, settings and a producer
digest. `staff.read_staff` calls the shared W5 `extract_strip` and passes its
original/removal channels, registry spacing and top-row margin into the detector.
It returns the channels, coordinate mesh, graph and validated reading draft.
No geometry implementation is duplicated and no pitch is calculated.
For an installed environment, pass
`geometry_config=load_config(Path("<bundle>/configs/geometry"))` explicitly;
the default registry lookup is for repository development.

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
N-best slots represent relationship/head-class combinations; attribute choices
stay in `attrTopK` so they cannot crowd a weak competing connection out of N-best.

The strip-to-lattice **draft path is connected, but music reading is incomplete**:
the detector does not
estimate beam/flag or dots/voice attributes, and the reader does not recognize
clefs, bar styles or other unsupported notation. It must not invent these values.
New graphs/lattices use clavis-ir-0.1.1, including when consuming legacy graphs.
Selected shared stems form `chord=1` groups in voice/pos order. Overlapping head
boxes in different voices propose `join=1` with both 0/1 alternatives at equal
provisional mass. This is uncertainty, not calibrated onset confidence. Overlap
chains without pairwise evidence and incompatible voice/chord attributes remain
unresolved. Disable these rules with `chords_enabled` / `joins_enabled`.
Every retained hypothesis passes W1 `normalize`, `serialize`, `parse`, and the
sequence automaton. `ReadingDraft.finalize()` repeats this boundary and refuses
unresolved evidence; a caller-supplied identity callback can no longer bypass it.
Fixtures supply attributes only in tests; the runtime never loads fixtures.

```text
uv sync --locked --all-groups
uv run --locked --all-groups pytest tests/symbols --cov=clavis.symbols
uv run --locked --all-groups python -m training.models.symbols.component_smoke work/w6-component.json
```

Numpy/OpenCV are pinned runtime dependencies since W1 PR #29. Template binaries remain in `work/`.
Production producer hashes must cover code, settings, rules and template bytes.
