# License register v0

`sources.json` is the machine-readable inventory. `pending` means no permitted use;
an upstream candidate is not an admitted training source. No corpus was downloaded.

| Source | v0 decision |
|---|---|
| Self-authored smoke notation | Tool tests only, quarantined under `work/` |
| LeadGen | Self-authored development core; tool-test only, training blocked pending W4/profile |
| PDMX | Pending item review; require `no_license_conflict` plus PDM/CC0 per item |
| Mutopia | Pending per-work review; CC-BY-SA requires Orchestrator approval |
| OpenScore Lieder | Entire corpus forbidden for training; evaluation belongs to W4 |
| Verovio 6.3.0 | LGPL-3.0-only, separate non-distributed renderer process |
| Leipzig, Bravura, Leland | Upstream OFL-1.1 and bundled resources verified; hashes in sources.json |
| Other music/text fonts, lyrics | Candidates only; no permission inferred |

The JSON records URL, version, license, permitted uses, attribution, check date
and verification method for every candidate. `train`, `eval`, and `weights` are
all denied unless explicitly present in `allowed_uses`. No v0 entry permits
training or weights distribution. Rendered documents and redistributed font
software have different obligations; preserve exact copyright/OFL with any font
redistribution. Font binaries and renderer code are not committed or distributed.

Evidence reviewed 2026-09-29:
- [Verovio licensing](https://book.verovio.org/introduction/licensing.html)
- [Verovio 6.3.0 metadata](https://pypi.org/project/verovio/6.3.0/)
- [Leipzig license](https://github.com/rism-digital/leipzig/blob/main/LICENSE.txt)
- [Bravura license](https://github.com/steinbergmedia/bravura/blob/master/LICENSE.txt)
- [Leland license](https://github.com/MuseScoreFonts/Leland/blob/main/LICENSE.txt)
- [PDMX distribution](https://zenodo.org/records/14648209)
- [Mutopia terms](https://www.mutopiaproject.org/legal.html)

The 30-page smoke audit matched every used glyph to its selected bundled font
with zero fallback; see `docs/reports/W2/render-audit-v0.json`. This does not
establish full glyph coverage or license clearance for pending candidates.

Next: record item-level rights and W4 exclusion receipts before admitting any shard.
Korean author death dates and
English publication years are screening hints, not blanket rights clearance.
