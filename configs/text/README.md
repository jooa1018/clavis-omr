# text

Owner: W7.

`constants.yaml`: provisional artifact/tensor resource caps; no fitted recognition threshold.
`rules.yaml`: TEXT-CTC-001 collapse rule and disable-to-abstain flag.
Both are UTF-8 JSON-subset YAML, readable without adding a runtime YAML dependency.
Caller reads values once and supplies `CtcLimits`, `max_bytes`, and `enabled` explicitly.
These caps do not select an image, model, dictionary, or acceptable chord grammar.
