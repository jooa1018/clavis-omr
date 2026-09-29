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
options remain the host factory's responsibility. ONNX Runtime is not yet a declared
runtime dependency in W1's pyproject. Real-model integration remains pending W1/W2.
API reference: https://onnxruntime.ai/docs/api/python/api_summary.html

For a recognizer output shaped [batch, time, class], pass one batch member's `.tolist()`
and its exact export dictionary to `greedy_observation`. Pass normalized probabilities,
not logits. Blank position is explicit. Dictionary order is never inferred from language.
Scores are quantized to 1e-4 before argmax, with lower class index winning ties.
Adjacent repeats collapse before blank removal; `enabled=False` abstains.

The result contains NFC text, original emitted tokens, CTC frame indices and raw token bp.
Frames are **not** glyph boxes; token bp are **not** calibrated confidence or sequence
posteriors. This is a greedy observation utility for future lyric wiring. It must not be
used to emit accepted chords: grammar-constrained decoding still awaits CCR-0002.
It does not build TextIR or infer roles, staff links, missing text, or geometry.

## Configuration and validation

`configs/text/*.yaml` use the JSON subset of YAML so hosts can read them with the standard
library. All resource caps are provisional; they reject oversized inputs rather than
silently truncating a sequence. Supply them to `CtcLimits` / `max_bytes` explicitly.
TEXT-CTC-001 is catalogued with an enable flag; the smoke also measures disabled abstention.
No runtime configuration reads evaluation files.

Run `python -m pytest tests/text` and
`python -m training.models.text.smoke --out work/text-smoke.json`.
The smoke uses self-authored CTC tensors: **SYN-Val 아님, image OCR accuracy 아님**.
The 1/4-thread unit exercise uses mock factories; actual ONNX numerical determinism is
NOT_RUN. No pretrained weights, dictionary, font or private image is bundled.

## Pending

Actual PP-OCR model hashes/licenses and W2 register confirmation; W1 runtime dependency
registration; model-specific preprocessing/dictionaries; DBNet boxes; constrained chord
decoding; Korean/Latin OCR; TextIR wiring; rendered crop and page metrics; CRNN comparison.
The official PP-OCR detector candidate is
https://huggingface.co/PaddlePaddle/PP-OCRv5_mobile_det_onnx (not acquired/admitted here).
