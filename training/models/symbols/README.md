# W6 template construction and measurement-only probes

All scripts run locally on CPU. Install the repository's locked groups first.
For these optional manual probes, install `requirements-probe.txt` into the W6
environment, plus **torch==2.5.1+cpu** from `https://download.pytorch.org/whl/cpu`.
These are training tools, never engine imports. Root packaging belongs to W1.

```text
python -m training.data.smoke work/w6-smoke --renderer-python .venv/Scripts/python.exe
python -m training.models.symbols.font_templates work/w6-templates
python -m training.models.symbols.preliminary work/w6-smoke work/t6-0.json
python -m training.models.symbols.component_smoke work/t6-1.json
```

`font_templates` consumes the installed W2-pinned Verovio font resources after
the W2 license gate. Bravura and Leland OFL notehead outlines become 12 grayscale
templates (three head shapes, two fonts, two blur variants). The optional MIT
resvg-py rasterizer is outside the engine. Only manifests belong in git.
Font configuration/blur amounts are in `configs/symbols/template-build.json`.

`preliminary` consumes the first two ordered W2 **train-smoke** jobs, verifies
their artifact hashes and keeps 64 48x48 patches in memory. Ink density is a
surrogate LightGBM label; a dense grayscale target exercises FCN backpropagation.
The FCN duplicates the original grayscale into two channels because the W5 strip
channel is unavailable. These timings do not measure symbol accuracy or T6.2
sampling. No checkpoint is saved and nothing is admitted to model selection.
Every setting uses its own subprocess (60-second timeout); the disk floor is
checked before rasterization. Peak RSS is measured and checked, not OS-enforced.
This historical probe now requires the OR-005 short-slot wrapper. Formal
measurement uses T1.9 in the 01:00–07:00 window; formal training requires
W2's W4-admitted manifest, and selection uses SYN-Val-quick only.

## Queued measurement with W5 strips

`measurement_data` reads existing W2 smoke artifacts, verifies their hashes and
extracts strips through `clavis.symbols.staff.read_staff`. W5's own label adapter
supplies synthetic staff geometry. `jitter.sample_row` resamples an entire W5
`synthetic-v0` row in the configured interline slice; no real error distribution
is inferred. Center-line offsets already include spacing error, so the adapter
does not add it twice. Jitter is training-only; inference remains deterministic.

The fixed `configs/symbols/measurement.json` workload draws 8192 two-channel
48×48 patches with replacement from two **train-smoke** pages. Half are uniform
crops and half are centered on removed-channel ink. This is a throughput fixture,
not T6.2's labeled sampler, W2 data production, admission, SYN-Val or a recognition
benchmark. No Dev, sealed, R-LIED, R-TGT or PDMX source is consumed.

`measurement` performs independent seeded fits at 512/2048/8192 records, three
repeats per size, for a 102209-parameter FCN (batch 8, three epochs) and a
15-leaf LightGBM (100 requested rounds). Both use grayscale/ink-density surrogate
targets. The queue supplies CPU-only library settings, affinity and the 3 GB
limit. Four jobs compare model × 4/8 threads; each has a 3600-second wall cap,
including interrupted attempts. Completed trials checkpoint their **timings**;
an interrupted fit restarts at its own fixed seed. No model weights are saved,
selected, evaluated or admitted to the engine.

Use a separate optional environment with the CPU torch wheel above and pinned
probe requirements, plus locked runtime packages and psutil. The queue launcher
uses its invoking Python, so launch it with that environment, not a uv command
that synchronizes away optional trainers. Source/config descriptor hashes are
checked before preparing data; the trainer checks descriptor, cache, config and
code hashes. Requests and paths stay in ignored `work/`; only sanitized evidence
is committed. The W6 queue root shares W1's machine-wide exclusive worker lock.

```text
work/measurement-venv/Scripts/python.exe -m training.jobs --root work/w6-measurement-queue submit work/request.json
work/measurement-venv/Scripts/python.exe -m training.jobs --root work/w6-measurement-queue run
```

Submit the preparation job before the four fitting jobs. Never use `--manual`
for the scheduled comparison. For daytime path checks use OR-005, a separate
64-record config/cache and `measurement --probe`; the resulting 2-thread values
are preliminary and cannot substitute for the formal 4/8-thread comparison.
Report fit-only throughput separately from queue wall time and process-tree RSS.
Orchestrator ruling (2026-10-09): T6.0 throughput uses the ordinary training queue,
with comparison jobs ordered FCN-4, FCN-8, LightGBM-4, LightGBM-8 in one night.
The four-thread exclusive benchmark is only for engine latency budgets.
`trial_load.observe_load` consumes W1's public load sampler and provisional
policy for each independent fit, without changing batch priority or affinity.
It records external CPU/RAM/AC samples and marks contaminated or unobserved
trials `comparisonEligible=false`. Preserve those rows in reports but exclude
them from throughput comparisons; compare matching size/seed pairs only when
both thread settings are eligible. The screen is not engine benchmark validity.
Use the v2 queue registration report after the ruling; the original pending
queue is paused and retained solely as registration history.
The timing fixture cannot confirm convergence, oracle@k or PLAN 7.5's aggregate
20–40-hour retraining budget without admitted data and actual training schedules.

`lowres_smoke` checks the existing detector at an input interline of 8 px, then
uses the same W5 `extract_strip` path as inference to normalize to s*=16. It
compares both channels with original-only input (a white removed channel), on
clean geometry and complete 8 px `synthetic-v0` rows. Run it through OR-005 with
32 declared images and the W2 report digest. It reads the same two development
smoke pages; it does not train, tune thresholds or evaluate recognition accuracy.
Known synthetic staff geometry does not test W5's missed-staff cases.

`component_smoke` records authored mock counts, on/off rule behavior, and 1/4
thread byte equality. It imports test fixtures deliberately and is not a W4
accuracy evaluator. The runtime has no test/training/eval imports. IER and
oracle@k remain NOT_RUN until the owning workers provide labels and metrics.

Licenses/provenance: W2 `training/data/licenses/sources.json`;
[resvg-py MIT](https://github.com/baseplate-admin/resvg-py/blob/master/LICENSE);
[Bravura OFL](https://github.com/steinbergmedia/bravura/blob/master/LICENSE.txt).
LightGBM 4.6.0's installed metadata contains the Microsoft MIT license. The
installed resvg-py 0.2.6 wheel includes its MIT text. No renderer code is copied.
