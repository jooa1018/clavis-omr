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

The smoke command is a repository-only test harness: its fixed four-measure
fixture author lives in `tests/data/smoke_inputs.py`, excluded from H4 by the
charter. It requires the repository's tests tree and is not a production data
generator. The move preserves input XML bytes and existing audit provenance.

## PDMX aggregate-only local streaming (OR-004, amended 2026-10-06)

The approved v9 source is `https://zenodo.org/records/15571083`. The per-row gate
requires no-license-conflict membership, false license_conflict, and the exact
PDM or CC0 license URL. Only CSV and the MXL archive are fetched into an external
temporary cache. They are removed after successful aggregation; extracted source
XML never persists. No song IDs or per-song values enter output artifacts. The
complete CSV SHA-256 is the source manifest digest. Both files must match publisher sizes and MD5 before
`aggregate.json` is written; that file contains aggregate tables and manifest digest.

```text
python -m training.data.pdmx_stream --config configs/data/pdmx-aggregate.json --output work/pdmx-v9-range-aggregate --cache "$env:LOCALAPPDATA/Temp/clavis-w2-pdmx-v9"
```

This is a local Windows queue payload; never run real data in GitHub Actions.
OR-004 authorizes one long execution: one process, <=2 compute threads, 1.5 GB
process memory cap, Below Normal priority, >=3 GB disk free, <=4 GB repository data.
The launcher must also set OMP_NUM_THREADS, OPENBLAS_NUM_THREADS and MKL_NUM_THREADS
to 2 before Python imports. Windows Job Object enforces one process/memory; affinity
limits execution to two available logical CPUs. Allocation/limit failures stop work.

The downloader requests 4 MiB ranges (download.segment_bytes) with a registered
16 MiB maximum (download.max_segment_bytes, bytes; Orchestrator 2026-10-09
resource-bound approval, independent of image dimensions) through at most four I/O connections in the
same process. Exact HTTP 206 Content-Range and identity encoding are mandatory.
429/503 honor Retry-After with shared exponential backoff. An OS cache lock prevents
concurrent writers and is released on process death. Segment data is fsynced before
an atomic journal records its SHA-256. Resume rehashes completed segments and fetches
only missing/corrupt ranges. It never falls back to a full network stream. File size
and MD5 are checked against Zenodo, including when all segments were already cached.
Disk preflight reserves both sources plus 3 GB free; runtime checks preserve that
margin. Cache must be outside Git repositories. No source bytes enter Git or CI.

Aggregate checkpoints retain counts and the processed TAR ordinal, not member names.
Resume rereads local compressed bytes and skips already counted members, without
retransmitting the network prefix. An interrupted result is not a target. Synthetic
interrupted/uninterrupted final aggregate bytes must match. After success only the
two explicitly named source files and their range journals are deleted; no recursive
cleanup is used. Keep the external cache on interruption to permit resumption.

The denominator is written pitched noteheads with a notated type, across all parts,
counting each tied segment and each chord member; no repeat unfolding. Grace and rests
are separate counters. Time changes update the applicable staff; unsupported/missing
meter is excluded. Unknown note types remain an explicit counter, never inferred.
Per-meter `songs` counts a source once if it contributes notation to that meter.
This full-population aggregate does not use a sampled 1,000-song shortcut.

MXL root selection follows the MusicXML compressed-container standard: the first
rootfile identifies MusicXML and an omitted media-type defaults to MusicXML.
Additional renditions are not aggregated. A missing path or explicit non-MusicXML
first root is rejected. This applies to all containers, independent of source or
song identity; tests cover namespaces, paths and alternate renditions.
Reference: https://www.w3.org/2021/06/musicxml40/tutorial/compressed-mxl-files/
XML syntax errors are excluded under T2.2 and counted as `rejected_invalid_xml`.
No error recovery or inferred repair is applied. Size/ratio, container format,
source integrity, and resource guard failures still stop the job. The excluded
count is checkpointed with parsed counts, so resuming does not duplicate exclusions.

`run-metrics.json` records cumulative active wall/CPU time, peak RSS, transfer bytes,
and mean CPU percent (one-core and whole-machine denominators). Operational checkpoint
and telemetry files have no song identifiers. Aggregate statistics do not authorize
training. OR-003 protected-set v1 and the admitted receipt remain mandatory.
