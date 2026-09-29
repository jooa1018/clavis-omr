# W2 data factory — first smoke audit

`licenses/REGISTER.md` and `sources.json` contain the v0 inventory. Unknown or
pending uses fail closed. No corpus, lyrics, fonts or renderer code are vendored.

Prepare the 30-job fixture matrix without rendering:

```powershell
uv run --locked python -m training.data.smoke work/w2-smoke
```

These are ten self-authored MusicXML fixtures, not ten collected public-domain
compositions or a LeadGen release. They vary key, meter and staff count, with an
encoded system break. Only `train-*` identifiers are used. All artifacts remain
under `work/`, with training admission blocked pending W4 melody exclusion.
OpenScore Lieder and private scores are not read. No training manifest is emitted.

## Short development runs and W1 handoff

OR-001 explicitly permits this 30-variant smoke run outside the night queue:
at most 10 minutes, 3 GB RAM, 100 renders/images, user-supervised development.
Install the W1-pinned **verovio==6.3.0** with `uv sync --locked --group training`.
The toolkit runs in a separate process, never in the engine. Font resources and
all 30 rendered pages were verified in `docs/reports/W2/render-audit-v0.json`.

```text
uv run --locked --group training python -m training.data.smoke work/w2-smoke --renderer-python .venv/Scripts/python.exe
```

For larger runs, queue requirements: one job, CPU only, one thread, RAM cap 3 GB supplied by W1;
per score/font subprocess timeout 60 s. This payload does not implement a second
scheduler or pretend an environment variable proves admission. W1 must apply its
actual queue API once available. On Linux pass `.venv/bin/python` instead.

`configs/data/smoke.json` pins renderer/options, fonts, page/input limits, a 4 GB
data ceiling and 3 GB minimum free disk. Storage is checked conservatively against
`data/` and `work/` before each render, including a per-job reserve. These are
operational limits, not recognition thresholds. The pink audit stroke uses one
eighth of observed staff spacing for display only, never for classification.

## Output and limitations

Each job stores input XML, deterministic gzip SVG, gzip overlay, JSON labels and
a hash-checked checkpoint. Interrupted or corrupted jobs rerun; completed jobs
resume. Failures are recorded in `report.json` and cause CLI exit 1. No raster
cache is created. Versions/options and source hashes are saved. Reports keep
rendering success separate from the pending visual audit.

The extractor reads direct `path` children of `g.staff`, with system/measure IDs
and `data-n` from `svgAdditionalAttribute: ["staff@n"]`. Nested ledger paths are
excluded. Five straight `M … L …` paths are supported; curves, missing provenance,
duplicate IDs and direct-path transforms/styles fail closed. System membership is
`(system_id, staff_number)`; `staff_id` identifies a measure segment.

Labels use **SVG staff-local coordinates**, addressed by IDs in the unchanged
ancestor transform/viewBox chain. Overlays are inserted under that same staff,
preserving nested viewports and transforms. This is a private audit artifact,
not StaffGeometry IR. Global coordinate conversion and contract schema validation
are not claimed. LSTL, symbol relations and text labels are not yet implemented.

For every new smoke acceptance: inspect every page overlay (inflate to a temporary
SVG), record failures and proportions, verify font fallback/resource metadata,
and attach the audit results. OR-001 permits the short development run above.
`RENDERED_PENDING_VISUAL_AUDIT` never means PASS. Mock tests do not establish
compatibility with the actual pinned renderer.

```text
uv run --locked --group training pytest tests/data --cov=training.data --cov-fail-under=80
uv run --locked mypy --strict training/data
```

References: [SVG metadata](https://book.verovio.org/toolkit-reference/toolkit-options.html),
[toolkit methods](https://book.verovio.org/toolkit-reference/toolkit-methods.html),
[font/fallback behavior](https://book.verovio.org/advanced-topics/smufl.html).

## LeadGen development core

```text
uv run --locked --group training python -m training.data.leadgen --config configs/data/leadgen-development.yaml --seed train-demo --output work/leadgen-demo
```

This explicit **development-only** profile exercises all key signatures, six
meters, treble/bass/tenor clefs, 4/8 measures, notes/rests from whole to 32nd,
one/two dots, quarter-note pickup, title and tempo. SHA-256 maps train-* seed
strings to a local numpy Generator. Identical seed + profile + pinned versions
produce identical MusicXML. Positive rhythms are composed with exact division
arithmetic before pitches are drawn; no missing events are inferred or repaired.
Pitch alterations encode the selected key explicitly. YAML forbids unknown fields,
invalid probabilities and training purpose; impossible durations fail closed.

This is not LeadGen G0 acceptance. Mid-score key/meter changes, minor-key profile,
ties, tuplets, grace, harmony, lyrics, repeats/navigation, multiple voices, slash
rhythm and remaining P0 coverage are still pending. No 10,000-song benchmark or
P0 >=1% claim has been made. Configuration weights are tested, not fitted.
The development profile is not the adopted training distribution. ADR-010 option B
was adopted by Orchestrator on 2026-09-29; production implementation is separate.
The development remaining-duration sampler must not be reused in production. All output stays in work/ and records
training_admission=BLOCKED_PENDING_W4_AND_APPROVED_PROFILE. Nothing is admitted
to a training manifest, and unverified lyric/font sources remain forbidden.

## Adopted production profile (implementation in progress)

`configs/data/leadgen-production.yaml` records ADR-010 option B exactly, including
mode-first key weights, meter weights, two-level feature rates, block acceptance,
and rare-duration floors. It cannot be passed to the development CLI.
`rhythm_groups.py` samples complete caller-supplied beat-group patterns with exact
rational sums. It never fills a remaining duration. Groups may span multiple beats
for cross-beat rhythms; notation, ties and XML serialization are not implemented
here. Pattern weights are not automatically fitted to the marginal note target.

The independent KL helper uses natural-log D_KL(generated || target), per meter,
with no smoothing. Missing target support yields infinity, not a finite score.
The conditional-count helper rejects impossible integer ranges: for example, one
grace note among 19 notes exceeds the approved 5% upper bound. It does not silently
round or alter the denominator. Production reporting must include numerator and
denominator for every selected song, plus the overall song occurrence rate.

Actual PDMX training-subset aggregates and provenance are absent. No invented
reference distribution, production XML, or 10,000-song acceptance is emitted.
W4 admission remains blocked. PR #4 was OPEN on 2026-09-29: T2.5 LSTL ordering is
on hold until its merge (recheck when starting T2.5).
