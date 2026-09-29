# Golden 13 pairs

Manually authored, minimal synthetic MusicXML; no real score, private data,
engine output, training sample or sealed item was used. These fixtures are
dedicated to evaluator verification, not SYN-Val or evidence of OMR quality.
The same source/prediction structure uses one part, staff and voice.

`expected.json` contains independent hand-set assertions approved by ADR-012.
`k1Operations` is the correction object count, not the rate per 100 events.
Cases 11/12/13 are the additional Orchestrator regressions. Divisions and voice
numbers deliberately differ in the equivalence cases. Report metrics are
generated separately and must not be used to regenerate expected.json.

The C/D/E fragments and isolated syllables were authored for Clavis tests;
no third-party score or code license is introduced. No corpus registration.
