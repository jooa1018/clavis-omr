# text

Owner: W7.

`python -m training.models.text.smoke --out work/text-smoke.json` writes a synthetic
CTC tensor smoke report. This is a tool test, **not SYN-Val or image OCR accuracy**.
It reads only text configuration and self-authored synthetic tensors; no dataset, font,
model, training, queue job, or network access. The report includes rule-off abstentions.

Actual synthetic crop generation and CPU CRNN training remain pending their registered
font artifacts and the W1 batch queue. No OCR retraining is provided.
