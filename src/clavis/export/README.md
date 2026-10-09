# export

Owner: W8.

MusicXML and public output serialization.

`write_musicxml(score)` returns `(xml_bytes, timing_dict)` for one part/staff,
without lyrics, harmonies, endings or navigation. It writes MusicXML 4.0 with
deterministic structural IDs, part-wide LCM divisions, independent voices,
chords, grace, exact durations, unpitched slash notes, ties/slurs, fermatas,
barlines and page/system breaks. Gaps are forward movements, never invented rests.

Every call requires offline MusicXML 4.0 XSD validation and independent reparse
equivalence of event semantics, notation, attributes and barlines. The writer
rejects overfull voices, invalid chords, overlapping timelines and unsupported
semantic content. It does not promote ScoreIR status or create a `result.musicxml`
bundle: evidence/calibration/full T8.10 bundle assembly remain later tasks.

The three official v4.0 XSDs in `schemas/musicxml-4.0/` are unmodified, including
their original line endings. NOTICE and manifest retain attribution, source tag,
commit and SHA-256. Orchestrator approved only these files on 2026-09-29.
The manifest is checked before first schema compilation. A locked process cache
reuses that schema; only the three original schemaLocation URLs resolve locally.
Unknown URLs fail. The 2026-10-09 ruling replaces lxml with W1's pinned `xmlschema`.
Schema compilation uses `allow="local"`, `defuse="always"`, `use_fallback=False`
and the strict URI mapper; unresolved import warnings are errors. Instance XML
rejects DOCTYPE before entity expansion and rejects processing instructions.
Its XMLResource uses `allow="none"`; instance schema hints are ignored.

Timing fields `schemaLoadNs` (one-time cached load) and `validationNs` (this call)
are measured with a monotonic clock and kept separate from deterministic XML.
The minimum reparser reads validated writer output and is independent of W4.
The oracle smoke invokes W4's public CLI against separately hand-authored XML.

Run: `uv run --locked --all-groups python -m training.jobs.short run tests.export.oracle_smoke --out work/w8-smoke`.
This is authored symbolic smoke, **not SYN-Val**. W2 T2.5 clean labels will replace
the authored oracle input when available. The authored `.lstl` fixture is read by
the shared strict parser. XSD tests must not be skipped to report a passing suite.
