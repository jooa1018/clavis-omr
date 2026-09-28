# Clavis evaluator 0.1.0

Owner: W4. Implements the first evaluator PR under EVALUATION v1.1 / ADR-012.
Offline standard-library implementation. No engine, training, network, LLM,
third-party baseline imports or new package dependencies.

## Run a public-output pair

From the repository checkout (Python 3.12):

```powershell
uv run --locked python -m eval reference.musicxml prediction.musicxml --out work/evaluation
uv run --locked pytest tests/eval --cov=eval --cov-fail-under=80
uv run --locked mypy --strict eval
```

Exit 0 means this pair was evaluated, not that an engine passed a quality gate.
Exit 2 means `evaluation-unsupported`, with no numeric scores. Output:
`report.json`, `report.md`, `pairs.json`. Evaluation version, code/config digest,
input digests, rational onsets/durations, matched/missing/extra objects and field
errors are retained. Reports are deterministic UTF-8/LF. Private pair details
must remain local. This command is not a sealed or dataset runner.

## Implemented

- One part/staff/voice, UTF-8 uncompressed score-partwise MusicXML. Decimal
  divisions/durations are exact Fractions. Backup/forward cursors, simultaneous
  chord members, grace, tuplet duration (already encoded in XML), note/rest/slash,
  ties, NFC lyrics/verses and harmony root/kind/degree/bass are projected.
- Native harmony meaning ignores printed kind text (M7/maj7), degree ordering,
  IDs and layout. Unsupported free-text `kind=other` is not guessed. Harmony
  degree normalization follows W3C degree-alter; half-diminished and minor7+b5
  native representations compare equal.
- Key/time/clef settings at measure starts, inherited state, repeat/volta marks.
  Redundant repeated attribute settings are not new changes. Attribute pairs
  with `/state/` refs refer to inherited projected state, not invented XML nodes.
- Event DP lexicographically minimizes object corrections, corresponding-pair
  field mismatches (kind, pitch, duration, tie_start, tie_stop), onset displacement.
  Onset itself is not charged. Measure DP uses these event costs with structural
  +1, in the approved tie order. Code objects and attributes are evaluated after
  measure/event alignment. Missing/extra measures count their events +1 without
  charging contained attributes/chords twice.
- K1, pitch/duration/rest/tie/accidental/grace exactness, key/time/chord exactness,
  measureExact, measureExactWithLyrics, lyric syllable-object accuracy and K1-L.
  `k1Operations` is an integer; K1 is that count per 100 reference events.
  `onsetOnlyMismatch` is the number of corresponding pairs with only onset error.
  The reference event K1 denominator includes grace; pitch/duration exclude grace.
  Empty denominators produce null. The report JSON Schema is evaluator-owned.

## Deliberate first-PR limits

Timewise, multiple parts/staves/voices, transposition, mid-measure attributes,
navigation/directions, nontraditional keys, composite meters, stacked/free-text
harmonies, elided lyrics and extension-only lyric objects are unsupported.
Partial-GT regions are not accepted by this pair-only CLI. Full GT/XML XSD
validation, dataset aggregation (micro/macro/bootstrap), K2/K3 confidence handling,
expanded playback, lyric CER, geometry, calibration, operating metrics, baseline
execution and sealed tools remain follow-up work. Report `notImplemented` states
this scope; successful first-PR tests do not meet G0.

Non-evaluated engraving details such as stems, beams, fonts and spacing are
ignored; the XML duration is authoritative rather than recomputed from type/dots.
The projection records grace/chordMember but measureExact uses the approved
event fields. Tied extra events count in K1; tieExact uses reference objects and
their corresponding predicted notes, including falsely introduced ties.

Resource limits are `configs/eval/limits.json` (bytes/nodes/measures/events/DP
cells). They are conservative safety bounds, not image-fitted accuracy constants.
No rule disables the approved scoring definition; `rules.yaml` catalogs the
evaluator semantics, not recognition rules subject to ablation. Changing scoring
requires the evaluation version/review procedure. Changing limits or tables
changes the evaluator digest.

## Evidence and specification

`tests/eval/fixtures/golden` contains 13 independent synthetic pairs. Edge tests
cover split/merge, empty denominators, inheritance, exact rational timing,
unsupported input, offline XML safety, deterministic output, exhaustive small-DP
optimality and the pair CLI. No Dev/sealed images were used.

Primary MusicXML sources: [duration](https://www.w3.org/2021/06/musicxml40/musicxml-reference/elements/duration/),
[chord](https://www.w3.org/2021/06/musicxml40/musicxml-reference/elements/chord/),
[harmony](https://www.w3.org/2021/06/musicxml40/musicxml-reference/elements/harmony/),
[degree-alter](https://www.w3.org/2021/06/musicxml40/musicxml-reference/elements/degree-alter/).
