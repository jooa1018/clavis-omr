# text

Owner: W7.

## Available boundary (T7.1a)

`VerifiedCpuModel.load(path, expected_sha256, max_bytes=..., threads=1|4, factory=...)`
checks the complete local artifact before passing its **bytes** and requested thread count
to a session factory. The returned session must report only `CPUExecutionProvider`.
`run(output_name, inputs)` forwards an explicitly named raw output, for either detection
or recognition. It does not download, convert, train, preprocess, classify, or attach text.

The host supplies the ONNX Runtime dependency. `ppocr.cpu_factory` implements the CPU factory. Set
`SessionOptions.intra_op_num_threads` to the supplied count, `inter_op_num_threads=1`,
`execution_mode=ORT_SEQUENTIAL`, and construct `InferenceSession(verified_bytes, ...,
providers=["CPUExecutionProvider"])`. The boundary verifies the provider list; thread
options remain the host factory's responsibility. ONNX Runtime 1.30.0 is now a locked
CPU runtime dependency (W1 PR #29). Real-model artifact admission remains pending W2; local smoke acquisition is authorized.
API reference: https://onnxruntime.ai/docs/api/python/api_summary.html

For a recognizer output shaped [batch, time, class], pass one batch member's `.tolist()`
and its exact export dictionary to `greedy_observation`. Pass normalized probabilities,
not logits. Blank position is explicit. Dictionary order is never inferred from language.
Scores are quantized to 1e-4 before argmax, with lower class index winning ties.
Adjacent repeats collapse before blank removal; `enabled=False` abstains.

The result contains NFC text, original emitted tokens, CTC frame indices and raw token bp.
Frames are **not** glyph boxes; token bp are **not** calibrated confidence or sequence
posteriors. This is a greedy observation utility for future lyric wiring. It must not be
used alone to emit accepted chords: use the constrained beam described below.
It does not build TextIR or infer roles, staff links, missing text, or geometry.

## Configuration and validation

`configs/text/*.yaml` use the JSON subset of YAML so hosts can read them with the standard
library. All resource caps are provisional; they reject oversized inputs rather than
silently truncating a sequence. Supply them to `CtcLimits` / `max_bytes` explicitly.
TEXT-CTC-001 is catalogued with an enable flag; the smoke also measures disabled abstention.
No runtime configuration reads evaluation files.

Run full validation through the OR-005 wrapper:
`uv run --locked --all-groups python -m training.jobs.short run pytest tests/`.
Run smoke with `uv run --locked --all-groups python -m training.jobs.short run
training.models.text.smoke --out work/text-smoke.json`.
The smoke uses self-authored CTC tensors: **SYN-Val 아님, image OCR accuracy 아님**.
The 1/4-thread unit exercise uses mock factories; actual ONNX 1-vs-4-thread numerical determinism is
NOT_RUN. No pretrained weights, dictionary, font or private image is bundled.

## Pending

W2 register confirmation (candidate hashes/licenses recorded in T7.1b-artifacts.json);
DBNet box decoding; constrained chord
decoding; Korean/Latin lyric segmentation; TextIR wiring; page metrics; CRNN comparison.
The official PP-OCR detector candidate is
https://huggingface.co/PaddlePaddle/PP-OCRv5_mobile_det_onnx (not acquired/admitted here).

The current shared contracts are `clavis-ir-0.1.1` / `lstl-0.1.1` (CCR-0003).
Same-column continuation in another voice is `join=1`. Future TextIR producers must
use the shared models; this raw boundary currently emits no IR or LSTL sequence.

## Chord grammar v0 (CCR-0002)

`ChordGrammar(catalog, max_chars=..., max_states=...)` reads the explicit
`configs/text/rules.yaml` catalog. Pass the provisional `text.grammar.*` resource
limits from constants.yaml. `start()` / `advance(state, observed_characters)`
return immutable stack states with `viable` and `accepting` flags for a future
CTC beam decoder. The stack supports recursive modifier parentheses. Limits
reject oversized inputs without truncating or changing the musical spelling.

`parse(observed)` returns `None` for invalid strings, otherwise `ChordSpelling`:
exact printed `text`, exact printed suffix `kind_text`, grammar-checked
`normalized`, and `outside_consumer_vocab`. Root accidentals use longest match;
slash inside `6/9` is not a bass separator. Body derivations are enumerated and
must agree before choosing the longest valid tokenization. `derivation_normal_forms`
exposes those body derivations for audits. A consistency failure raises ValueError
instead of silently choosing an interpretation.

This spelling object is not the contract ChordParseResult: it does not invent
MusicXML kinds/degrees, OCR probabilities, roles or evidence. The caller retains
the observation for TextItem.text and maps the vocabulary flag to
CHORD_OUTSIDE_CONSUMER_VOCAB when constructing a contextual hint.

The catalog contains each glyph mapping and its convention rationale. There is
no generic NFKC or visual A/triangle, 0/o/degree correction. Grammar/normalization
disabled means abstention; glyph normalization disabled admits only literal grammar
characters; consumer warning disabled preserves the accepted spelling.

Validation: all CONTRACTS 12.6 spellings, rejection cases, alias derivation
agreement, nested modifiers, idempotence, explicit glyph map and 1/4-worker byte
repeatability. `training.models.text.grammar_smoke` reports symbolic 30-case smoke
and each flag ablation; **SYN-Val 아님, image OCR accuracy 아님**.
## Local PP-OCR image adapter (T7.1b, pending artifact admission)

`ppocr.cpu_factory` constructs CPU-only sequential ONNX Runtime sessions from the
bytes already verified by `VerifiedCpuModel.load`. `PpOcrProfile` is explicit:
metadata-derived BGR means/std, model height/width, stride, IO names and exact
export alphabet. No runtime network or YAML dependency is introduced.
`infer_image(model, bgr_uint8, profile, limits, enabled=True)` preprocesses one
bounded image and returns either a full detector probability map or CTC tensor
with source/tensor dimensions. It returns no text boxes, roles or staff links.

Recognizer resizing preserves aspect ratio and pads normalized zeros on the right.
Long crops are rejected at the registered width budget instead of silently cut.
Detector long-side resizing aligns to the model stride. Probabilities are checked
after CONTRACTS 11 quantization and only endpoint roundoff is clamped to [0,1].
All larger range errors/nonfinite values and shape/dictionary mismatches fail closed.

Some official Latin dictionary class IDs have identical spellings, and both export
alphabets can contain non-NFC entries. Do not deduplicate or rewrite the alphabet:
pass `preserve_export_alphabet=True` to `greedy_observation` for an exact verified
export. Repeat collapse still operates on class IDs, and final text is NFC. Strict
validation remains the default for other callers. This is no visual confusion map.

The 72-crop smoke uses local SHA-verified official model exports and OFL font files
listed in docs/reports/W7/T7.1b-artifacts.json. It renders deterministic grammar
samples plus self-authored Korean/English text with two fonts and two sizes.
No private/sealed images, pretrained-model tuning, checkpoint selection or lexicon
correction is performed. `training.models.text.ppocr_smoke` takes a local manifest
with `id/url/license/sha256/bytes/local` entries and has no download code. Example:

`uv run --locked --all-groups python -m training.jobs.short run --items 72
--data-digest <manifest-sha256> training.models.text.ppocr_smoke
--manifest work/ppocr-artifacts/artifacts.json --out work/ppocr-smoke.json`

This measures greedy crop observations and grammar validation, **not constrained
CTC beam decoding**, page detection recall, SYN-Val or full engine OCR accuracy.
OR-005 forces ORT to two threads; same-run repeats do not establish 1-vs-4-thread
model determinism. Candidate artifact admission/registry remains W2's responsibility;
this PP-OCR PR cannot merge before [W2 확인].
## Constrained beam, boxes and TextIR (T7.1c)

`beam.chord_beam` consumes the full recognizer probability tensor and exact export
alphabet. It tracks CTC blank/nonblank masses per class-ID prefix, rejecting prefixes
outside `ChordGrammar`. Duplicate export spellings keep distinct class IDs until final
canonical forms are merged. No language model, key context or confusion replacement is
used. Frame scores are quantized before decisions; bounded beams use deterministic ties.
Returned `mass_bp` is retained quantized CTC mass, not calibrated correctness. Pruning
and top-k do not renormalize surviving candidates to 100%. Budget exhaustion raises.

`detection.detection_regions` consumes the 2D probability map from `infer_image`.
It thresholds connected outer contours, scores their filled areas, expands each
minimum-area rectangle by the DB area/perimeter distance, clips to image bounds,
and maps to processed coordinates (optional explicit crop offset). This rectangular
approximation is not the upstream arbitrary-polygon offset. Separate components can
have overlapping expanded boxes; no NMS or reading-order model is claimed. Thresholds
come from the pinned model metadata, with provisional registry entries.

`lyrics.lyric_segments` uses Otsu dark ink and horizontal projection with a provisional
staff-space gap. Boxes describe observed ink components. Independently OCR those crops;
do not divide a line into equal boxes or turn CTC time indices into glyph coordinates.
The function does not assert that every component is a syllable, hyphen or extender.

`bridge.text_ir` accepts `TextObservation` with an observed region, text, raw score,
and **explicit upstream role probabilities and staff link**. It emits contract-valid
TextIR and review diagnostics. Printed text stays unchanged apart from required NFC;
chord alternatives contain checked canonical strings. Optional `ChordParseResult`
can be supplied only with the matching normalized and printed kind text. Otherwise
harmonic interpretation stays absent with a diagnostic. It is not inferred by this
adapter. Syllable observations require image-space boxes contained in the region.
Call `canonical_json(result.ir)` from the contracts package for canonical output.

All four operations accept an enable flag from their catalog entries. The caller loads
`TEXT-BEAM-001`, `TEXT-DB-001`, `TEXT-LYRICS-001` and `TEXT-IR-001` and passes registry
limits explicitly. This is a component integration boundary, not a role classifier or
complete page-to-TextIR pipeline; role confusion and real-page recall remain NOT_RUN.

`training.models.text.integration_smoke` reuses verified local artifacts, with at most
100 unique images under OR-005. It reports Korean whitespace-free CER, one-to-one
syllable box matching at diagnostic IoU 0.5, independent syllable transcription, and
spacing boundary accuracy separately. Spacing offsets can shift after insertion or
deletion; read them alongside CER. Arbitrary word boundaries in note-spaced rows are
not recoverable from ink spacing alone. The 16 rows/64 synthetic blocks are **SYN-Val
아님**, not natural lyrics or evidence for a model adoption decision. No rules are fit
on the outcomes. Model/font hashes are unchanged from T7.1b; W2 receipt is not admission.

## Measurement policy (Orchestrator, 2026-10-09)

Continue full tests and component smoke through `training.jobs.short` (OR-005).
Their elapsed time is a diagnostic, not a latency-budget acceptance result.
Formal latency/speed measurements use `python -m training.jobs.benchmark` in
01:00–07:00 Asia/Seoul only; require `benchmark.validity=valid`. No formal
benchmark is scheduled or claimed by this main-sync update. W1 PR #48 resolves
the historical child-sampling monitor-error; distinct child exit failures must
still be reported separately.
