# text

Owner: W7.

## Available boundary (T7.1a)

`VerifiedCpuModel.load(path, expected_sha256, max_bytes=..., threads=1|4, factory=...)`
checks the complete local artifact before passing its **bytes** and requested thread count
to a session factory. The returned session must report only `CPUExecutionProvider`.
`run(output_name, inputs)` forwards an explicitly named raw output, for either detection
or recognition. It does not download, convert, train, preprocess, classify, or attach text.

The host supplies the ONNX Runtime dependency and factory. Set
`SessionOptions.intra_op_num_threads` to the supplied count, `inter_op_num_threads=1`,
`execution_mode=ORT_SEQUENTIAL`, and construct `InferenceSession(verified_bytes, ...,
providers=["CPUExecutionProvider"])`. The boundary verifies the provider list; thread
options remain the host factory's responsibility. ONNX Runtime 1.30.0 is now a locked
CPU runtime dependency (W1 PR #29). Real-model artifact admission remains pending W2.
API reference: https://onnxruntime.ai/docs/api/python/api_summary.html

For a recognizer output shaped [batch, time, class], pass one batch member's `.tolist()`
and its exact export dictionary to `greedy_observation`. Pass normalized probabilities,
not logits. Blank position is explicit. Dictionary order is never inferred from language.
Scores are quantized to 1e-4 before argmax, with lower class index winning ties.
Adjacent repeats collapse before blank removal; `enabled=False` abstains.

The result contains NFC text, original emitted tokens, CTC frame indices and raw token bp.
Frames are **not** glyph boxes; token bp are **not** calibrated confidence or sequence
posteriors. This is a greedy observation utility for future lyric wiring. It must not be
used to emit accepted chords: grammar-constrained decoding remains to be implemented
with the chord grammar below (CTC beam search is a separate integration step).
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
The 1/4-thread unit exercise uses mock factories; actual ONNX numerical determinism is
NOT_RUN. No pretrained weights, dictionary, font or private image is bundled.

## Pending

Actual PP-OCR model hashes/licenses and W2 register confirmation;
model-specific preprocessing/dictionaries; DBNet boxes; constrained chord
decoding; Korean/Latin OCR; TextIR wiring; rendered crop and page metrics; CRNN comparison.
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