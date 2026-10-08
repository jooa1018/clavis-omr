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
Only this bounded manual OR-001 probe may run outside the W1 queue. Formal
measurement waits for T1.9 and the 01:00–07:00 window; formal training requires
W2's W4-admitted manifest, and selection uses SYN-Val-quick only.

`component_smoke` records authored mock counts, on/off rule behavior, and 1/4
thread byte equality. It imports test fixtures deliberately and is not a W4
accuracy evaluator. The runtime has no test/training/eval imports. IER and
oracle@k remain NOT_RUN until the owning workers provide labels and metrics.

Licenses/provenance: W2 `training/data/licenses/sources.json`;
[resvg-py MIT](https://github.com/baseplate-admin/resvg-py/blob/master/LICENSE);
[Bravura OFL](https://github.com/steinbergmedia/bravura/blob/master/LICENSE.txt).
LightGBM 4.6.0's installed metadata contains the Microsoft MIT license. The
installed resvg-py 0.2.6 wheel includes its MIT text. No renderer code is copied.
