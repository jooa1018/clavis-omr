# integrity

Owner: W4.

Integrity policy; no unapproved scanner exceptions.

`allowlist.yaml` is initially empty. JSON-subset YAML entries must contain file,
line, rule, reason, approvedBy (W4 and orchestrator), and evidence_digest.
No exception is approved by creating this file. See `eval/integrity/README.md`.
