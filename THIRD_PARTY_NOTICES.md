# Clavis third-party notices

## Runtime packages
Runtime packages are installed as separate wheels; retain their complete bundled license and notice files when distributing an environment.
- Pillow 11.2.1: MIT-CMU (Orchestrator approved 2026-10-06). Retain copyright/permission notices and the restriction on use of names. https://github.com/python-pillow/Pillow/blob/11.2.1/LICENSE
- lxml 6.1.3: BSD-3-Clause; bundled libxml2 2.11.9/libxslt 1.1.45 (Windows) are MIT. **BLOCKED for distribution:** the official binary-wheel notice also identifies iconv as LGPL 2.1, conflicting with the current static-inclusion policy. This dependency addition remains draft pending Orchestrator direction. https://github.com/lxml/lxml/blob/lxml-6.1.3/LICENSES.txt
- ONNX Runtime 1.30.0: CPU package `onnxruntime`, MIT. Retain its LICENSE and ThirdPartyNotices.txt. https://github.com/microsoft/onnxruntime/blob/v1.30.0/LICENSE
- The complete Python runtime dependency closure and wheel metadata are recorded in docs/reports/W1/T1.3-runtime-license-evidence.json and uv.lock.

## Bundled specification: MusicXML 4.0
MusicXML 4.0 XSD: musicxml.xsd, xlink.xsd, xml.xsd, copied unmodified from W3C release v4.0 (commit 799e2defb2ece0ae7bafe08dcbcac25b2c631d53).
Copyright © 2004-2021 the Contributors to the MusicXML Specification, published by the W3C Music Notation Community Group.
The W3C Community Final Specification Agreement and W3C Software and Document License apply as identified by the original notices. Specification name/version are preserved for FSA 2.2.
- Specification: https://www.w3.org/2021/06/musicxml40/
- FSA: https://www.w3.org/community/about/agreements/final/
- W3C Software and Document License: https://www.w3.org/copyright/software-license-2023/
- Original notices and annotations: `clavis/export/schemas/musicxml-4.0/NOTICE` and each XSD.
- Exact source URLs, byte lengths and SHA-256: `clavis/export/schemas/musicxml-4.0/manifest.json`.
- This approval is limited to these three schemas (Orchestrator 2026-10-06); it does not authorize other specifications or libraries.

Original byte copies, NOTICE and manifest were supplied in W8 PR #25. W1 includes only these approved schema assets to verify distribution before the exporter is merged.
