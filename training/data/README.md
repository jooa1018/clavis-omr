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

## W1 handoff (not yet integrated)

The current base has no W1 queue implementation. Do not launch real rendering
outside W1's single 01:00–07:00 queue. W1 should run this payload with a separate
Python environment containing **verovio==6.3.0**, after checking the installed
font resource provenance. Do not add Verovio to engine dependencies.

```text
python -m training.data.smoke work/w2-smoke --renderer-python <isolated-python>
```

Queue requirements: one job, CPU only, one thread, RAM cap 3 GB supplied by W1;
per score/font subprocess timeout 60 s. This payload does not implement a second
scheduler or pretend an environment variable proves admission. W1 must apply its
actual queue API once available. There is no queued/running job yet.

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

Before calling the first goal complete: run all 30 variants through W1, inspect
every page overlay (inflate to a temporary SVG), record failures and proportions,
verify font fallback/resource metadata, and attach the audit results.
`RENDERED_PENDING_VISUAL_AUDIT` never means PASS. Mock tests do not establish
compatibility with the actual pinned renderer.

```text
uv run --locked pytest tests/data --cov=training.data --cov-fail-under=80
uv run --locked mypy --strict training/data
```

References: [SVG metadata](https://book.verovio.org/toolkit-reference/toolkit-options.html),
[toolkit methods](https://book.verovio.org/toolkit-reference/toolkit-methods.html),
[font/fallback behavior](https://book.verovio.org/advanced-topics/smufl.html).
