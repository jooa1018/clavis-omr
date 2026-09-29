# assemble

Owner: W8.

The first oracle path accepts one system's single staff `StaffLattice` and selects
rank zero without changing its attributes. It uses exact fractions, eleven clefs,
key signatures, staff/position accidental state shared across voices, adjacent
ties, grace notes, chords, triplets, measure rests and counted multi-rests.

`assemble_staff(lattice, engine=ScoreEngine(...), clef=None, key=None, time=None)`
returns `Assembly(score, hints, sources)`. Clef and meter must be visible in the
lattice or supplied as known context; absence is never guessed. An absent key
means no key alterations. Courtesy attributes do not update context. A boundary
clef preceding a bar takes effect on the following measure; mid-measure changes,
text, endings and navigation are explicitly unsupported in this first path.

Initial repeatStart creates a left barline; eventless bars do not create empty
measures. Voices start at zero, and chord members share their preceding onset.
An observed multi-rest expands only its declared count; all derived rest events
retain the same source symbols. Duration mismatches receive a blocking hint with
no fabricated alternatives. There is no search, insertion/deletion API or padding
rest operation. T8.4 lattice alternative search is not implemented.

Every emitted event is traceable through `sources[event_id]` to input symbol IDs.
These are **not** original-frame evidence boxes. Evidence IDs remain empty until
T8.5 supplies geometry. `confidenceBp` propagates item scores (measure minimum),
not calibration. The returned ScoreIR stays `partial` (or `blocked` if empty),
with explicit export-pending and uncalibrated diagnostics. This is not a product
recognition result or a complete output bundle.

Rules live in `configs/assemble/rules.yaml` (JSON-compatible YAML).
`Rules.from_catalog(path)` reads boolean `enabled` flags; pass the result through
`rules=`. Disabling a foundational theory rule fails closed: an ablation must not
invent substitute pitches or durations. The catalog records provisional status;
unit on/off checks are not corpus contribution measurements. Mathematical note
units and clef anchors are contract definitions, not tuned thresholds; no fitted
constants exist. Recognition-dependent constants must be registered before use.

Tests: `uv run --locked --all-groups pytest tests/assemble tests/export`.
W1 T1.4's future sequence automaton will replace the local supported-input guards.
