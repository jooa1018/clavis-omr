# Clavis evaluator 0.2.0

Owner: W4. Implements EVALUATION v1.1 / ADR-012 without changing their definitions.
Offline implementation; the public confidence contract parser and NumPy bootstrap
are dependencies. No engine internals, training, network, LLM or baseline imports.

## Run a public-output pair

From the repository checkout (Python 3.12):

```powershell
uv run --locked python -m eval reference.musicxml prediction.musicxml --out work/evaluation
uv run --locked --group eval python -m eval reference.musicxml prediction.musicxml --confidence element-confidence.json --out work/evaluation-flagged
uv run --locked --group eval python -m eval.aggregate pages-A.json --compare pages-B.json --out work/paired.json
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

- One part/staff, up to eight voices, UTF-8 uncompressed score-partwise MusicXML. Decimal
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
- Voices are assigned by Hungarian matching over the same lexicographic event
  costs. Dummy rows/columns retain missing/extra voices. Voice labels and document
  voice order can change without changing exactness. All paired voice IDs remain
  in pairs.json event records; ties retain document traversal order.
- Optional K2/K3 use public element-confidence IDs or parentId/relative paths.
  Elements OR their containing predicted measures can flag an error. Missing
  events use the aligned predicted measure(s); absent measures cannot be flagged
  through unrelated measures. Lyrics and onset-only errors are excluded. Invalid
  or unresolvable confidence yields evaluation-unsupported. Absent confidence
  leaves K2/K3 unmeasured. Flag burden/precision/error recall are reported.
- `eval.aggregate` computes micro/macro, 10,000 fixed-seed page bootstrap draws and
  95% percentile intervals; paired comparisons reuse exactly the same page draws.
  A/B page IDs, metadata and evaluator digests must match. Every required slice is
  retained, with conclusions withheld below five pages. Missing/unsupported pages
  prevent complete aggregation, rather than silently shrinking the cohort.

Aggregate input is an array of `{pageId, metadata, report}`. Metadata requires
tier, devPartition, sourceKind, captureChannel, engravingTool, musicFont,
measuredInterlinePx, notationFeatures and chordDensity. Unknown values are null;
notationFeatures uses ties/dotted-notes/accidentals/6/8/two-voices/slash/lyrics-ko/
lyrics-en. Chord density labels must be fixed in dataset metadata before comparison.
The tool does not choose bins based on observed engine scores. Zero denominators
remain null, undefined bootstrap draws are counted, and macroDenominator states
how many pages had a defined rate. Delta is B minus A, in each metric's units.

## Remaining limits

Timewise, multiple parts/staves, transposition, mid-measure attributes,
navigation/directions, nontraditional keys, composite meters, stacked/free-text
harmonies, harmony inversion, elided lyrics and extension-only lyric objects are unsupported.
Partial-GT regions are not accepted by this pair-only CLI. Full GT/XML XSD
validation, partial-region dataset execution, expanded playback, lyric CER,
geometry, calibration, operating metrics, baseline
execution and sealed tools remain follow-up work. Report `notImplemented` states
this scope; this extension still does not complete every G0 metric.

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
optimality and the pair CLI. `test_extended.py` adds 27 independent mutation types,
brute-force checks of small Hungarian assignments, K2 counterexamples and paired
bootstrap validation. No Dev/sealed images were used. Version 0.2.0 preserves the
13 golden results; no measured B0 exists yet. Both sides of a comparison must be
rerun with the final evaluator digest before making a performance claim.

Primary MusicXML sources: [duration](https://www.w3.org/2021/06/musicxml40/musicxml-reference/elements/duration/),
[chord](https://www.w3.org/2021/06/musicxml40/musicxml-reference/elements/chord/),
[harmony](https://www.w3.org/2021/06/musicxml40/musicxml-reference/elements/harmony/),
[degree-alter](https://www.w3.org/2021/06/musicxml40/musicxml-reference/elements/degree-alter/).
