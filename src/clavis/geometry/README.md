# geometry

Owner: W5.

Staff geometry and layout.

## Synthetic v0 (T5.3/4/6/7)

`estimate_interline(gray, config)` returns supported vertical run-length modes.
`detect_staves(gray, config)` uses slope-corrected grayscale projections across
staff-space column bands. It returns `StaffCandidate`s and diagnostic strings.
Assign real S2 identities with `candidate.as_staff(staff_id, system_id)`; this
component does not invent systems, barlines, music symbols or probabilities.
`confidence_bp` describes track coverage, not calibrated correctness.

`extract_strip(page, staff_geometry, s_star=None, margins=None, *, config=None)`
returns **(H×W×2 uint8 image, DewarpMesh)**. Channels are original grayscale then
staff-removed. Frozen defaults are s*=16, margins=(6,5), height=240. Both W6
sampling and inference must call this function. No random state or network is used.
`strip_to_processed` and `processed_to_strip` invert the same sampled mesh.
The last uniform-u knot is exactly the right supported endpoint; uStep can be
slightly smaller than the default 8 px to avoid inventing an extrapolated column.
Out-of-page pixels are white; out-of-mesh point queries raise ValueError.

Five x-monotone noncrossing lines are required; OOD staves are rejected. Lines
determine local top/spacing (no invented geometry from musical context).
Removal clears short vertical ink runs at canonical staff rows and preserves
long crossing runs. Thin coincident symbol strokes and antialias residues remain
limitations; the original grayscale channel is always retained.

Pass `load_config(Path(bundle_directory))` in installed deployments. The optional
default reads the repository's configs/geometry folder for development; configs
are not silently embedded or packaged by this module. JSON-subset YAML avoids a
new runtime YAML dependency. All registry values are provisional, with provenance.

Current evidence is **synthetic smoke, not SYN-Val**, no real-image improvement
claim. 8 px has a missed staff in the fixed smoke family. Curved/perpective staff
tracking, lyrics/beam distractors and local mixed-scale recall are not validated
on a production corpus. S0 normalization and S2 layout remain separate work.

## S2 proposal boundary

`clavis.geometry.barlines.propose_barlines(original_strip, s_star, margin_above)`
returns thin full-height vertical stroke proposals with observed coverage and
`BARLINE_OR_STEM` ambiguity. It never creates musical barlines, repeat styles,
systems or measures. A full-height stem can be visually identical at this stage.
GEO-VERTICAL is switchable and its staff-space/ratio thresholds are provisional.
Cross-staff alignment, brace/bracket evidence, system grouping, multi-column
rejection, style classification and masks remain to be implemented and evaluated.
