# Clavis 인터페이스 계약 v0.1

> 소유: W1(구현), Orchestrator(승인). 이 문서와 `src/clavis/contracts/`의 스키마가 모듈 사이의 **유일한 약속**이다.
> 변경은 CCR(0절)로만 한다. 워커는 상류 산출물이 없어도 이 계약의 예시와 fixture로 먼저 개발한다.
> 구현 전 개정(2026-09-29, PLAN v1.1): GPU 없는 구조로 바꾸면서 3.4절(`StaffLattice` 생산자), 3.5절(`SymbolGraph`), 4.4절, 2.1절(strip 채널)을 고쳤다. 아직 구현된 것이 없으므로 버전은 v0.1을 유지한다.

## 0. 버전과 변경 규칙

- 버전 식별자: IR `clavis-ir-0.1` · 토큰 언어 `lstl-0.1` · 출력 `clavis-evidence-0.1`, `clavis-hints-0.1`, `clavis-confidence-0.1`, `clavis-report-0.1`.
- 하위 호환이 깨지는 변경은 minor를 올린다(0.1 → 0.2). 필드 추가처럼 호환되는 변경은 patch를 올린다(0.1.1).
- 변경 절차: `docs/ccr/CCR-NNNN.md`(동기, 변경안, 영향 모듈, 마이그레이션, 평가 영향) → 영향 모듈 소유자 의견 → Orchestrator 승인 → W1이 구현하고 fixture와 JSON Schema를 갱신 → 영향 모듈이 따라온다.
- 모든 JSON 산출물에는 `schema` 필드로 버전을 적는다.

## 1. 공통 규약

| 항목 | 규약 |
|---|---|
| 인코딩 | UTF-8, LF, 텍스트는 NFC 정규화 |
| JSON 키 | 외부로 나가는 파일과 IR 덤프는 camelCase. Python 내부 속성은 snake_case + alias |
| 정수 전용 외부 값 | 외부 출력의 좌표는 microunit 정수(1 px = 1,000,000 µ), 행렬은 nanounit(1.0 = 1,000,000,000), 신뢰도는 basis point 정수(0–10000, 이하 bp) |
| 내부 실수 | IR 덤프의 px 좌표는 소수 셋째 자리에서 round-half-even |
| 시간 | 온음표가 아니라 **4분음표 단위**의 기약분수 `{"n": int, "d": int}`, `d > 0` |
| 음높이 | `{"step": "A".."G", "alter": -2..2, "octave": int}` (과학적 음높이 표기, C4 = 가온 다) |
| ID | 구조 위치에서 결정적으로 만든다(1.1절). 난수 UUID 금지 |
| 정렬 | 집합형 배열은 문서화된 정렬 키로 정렬한다. 정렬 키가 같으면 ID 문자열 사전순 |
| 금지 | NaN, Infinity, 현재 시각, 호스트명, 절대 경로를 결정적 산출물에 넣지 않는다 |

### 1.1 ID 규칙

| 대상 | 형식 | 예 |
|---|---|---|
| 페이지 | `pg{p}` | `pg0` |
| 시스템 | `pg{p}-sy{s}` | `pg0-sy3` |
| 보표(시스템 안) | `pg{p}-sy{s}-st{k}` (위에서부터 k = 0..) | `pg0-sy3-st1` |
| 마디(전역, 파트별) | `{part}-m{i}` (i는 0부터 시작하는 문서 순서) | `P1-m12` |
| 보표-마디 | `{part}-m{i}-s{staffInPart}` | `P1-m12-s1` |
| 이벤트 | `{part}-m{i}-s{staff}-v{voice}-e{j}` (j는 성부 안 순서) | `P1-m12-s1-v1-e3` |
| 코드 심벌 | `{part}-m{i}-h{j}` | `P1-m12-h0` |
| 가사 음절 | `{eventId}-l{verse}` | `P1-m12-s1-v1-e3-l2` |
| 방향 지시 | `{part}-m{i}-d{j}` | `P1-m4-d0` |
| 텍스트 항목 | `pg{p}-t{j}` (페이지 안에서 (y, x) 정렬 순서) | `pg0-t15` |
| 기호(보표 안) | `{staffId}-s{j}` (strip 안에서 (u, v) 정렬 순서) | `pg0-sy3-st0-s41` |
| 근거 | `ev-{targetId}-{granularity}` | `ev-P1-m12-s1-v1-e3-symbol` |

이 ID는 MusicXML `id` 속성과 evidence의 `vendorTargetId`로 그대로 쓴다.

## 2. 좌표계와 변환

| 프레임 | 뜻 |
|---|---|
| `original` | 업로드된 원본 페이지 래스터. HTTP 경로에서는 HarmonyMaker가 보낸 PNG, CLI의 PDF 입력에서는 `report.json`에 기록한 dpi로 래스터화한 이미지 |
| `processed` | 회전, 원근 보정, 자르기, 크기 조정을 거친 페이지 |
| `strip:{staffId}` | 보표를 펴고 s*로 정규화한 이미지 |

- `original → processed`: 3×3 homography(내부 float64). 여러 단계면 합성해 하나로 기록한다.
- `processed ↔ strip`: dewarp mesh. strip 열 u마다 중심선의 `x(u)`, 맨 위 오선의 `yTop(u)`, 국소 interline `I(u)`를 `uStep`(기본 8 px) 간격으로 표본화하고 선형 보간한다. strip 좌표 (u, v)는 `x = x(u)`, `y = yTop(u) + (v − vTop)·I(u)/s*`로 processed에 대응한다. 여기서 `vTop = marginAbove·s*`다.
- **외부 출력 좌표는 항상 `original` 프레임**이다. strip 박스는 네 모서리와 변의 중점을 역변환한 뒤 축 정렬 외접 사각형을 취하고, 프레임 경계로 자른다. 따라서 HarmonyMaker는 transform 없이 바로 겹쳐 그릴 수 있다.

### 2.1 정규화 상수 (기본값. 변경은 ADR-003)

| 이름 | 기본 | 후보 | 비고 |
|---|---|---|---|
| `sStar` | 16 px | 12, 16, 20 | 정규 staff-space |
| `marginAboveSpaces` | 6 | — | 덧줄, 볼타, 셋잇단 숫자 포함 |
| `marginBelowSpaces` | 5 | — | 덧줄, 아래 성부 쉼표 포함 |
| strip 높이 | (4 + 6 + 5) × 16 = **240 px** | — | |
| strip 최대 폭 | 제한 없음 | — | FCN은 폭과 무관하게 적용된다. 메모리가 넘칠 때만 겹침 타일(W6) |
| strip 채널 | 2 | — | 원본 그레이스케일 + 오선 제거 채널(W5 T5.7) |

## 3. 파이프라인 IR (`clavis-ir-0.1`)

필드는 요약이다. 정본은 `src/clavis/contracts/`의 pydantic 모델과 자동 생성된 JSON Schema다. 모든 객체에 `schema`와 `id`가 있다.

### 3.1 `PageInput` (S0)

`pageIndex`, `source{kind: image|pdf, mime, bytesSha256, pdfPageIndex?, rasterDpi?}`, `original{width, height, pixelsSha256}`, `frames[]`, `transforms[]`.

### 3.2 `QualityReport` (S0)

HarmonyMaker `ImageQualityReport` 필드 `blurBp`, `perspectiveBp`, `glareBp`, `cropRiskBp`, `estimatedStaffSpacePixels`, `status: pass|warn|retake`, `reasons[]`를 그대로 두고 다음을 확장한다: `contrastBp`, `noiseBp`, `jpegQualityEstimate?`, `interlineSpreadBp`(페이지 안 interline 편차), `expectedBurdenBucket?`(P1: low|medium|high).

### 3.3 `PageLayout` (S1–S2)

- `staves[]`: `staffId`, `systemId`, `lines`(5개 polyline, processed px), `interlinePx`(중앙값), `interlineProfile[]`, `lineThicknessPx`, `bbox`, `lineCount`, `ood?: tablature|percussion|unknown`, `confidenceBp`
- `systems[]`: `systemId`, `staffIds`(위→아래), `groups[]{type: brace|bracket|none, staffIds}`, `barlines[]{xProcessed, uByStaff{staffId: u}, spanStaffIds, styleGuess, confidenceBp}`
- `strips[]`: `stripId(=staffId)`, `sStar`, `width`, `height`, `marginAboveSpaces`, `marginBelowSpaces`, `mesh{uStep, x[], yTop[], interline[]}`, `pixelsSha256`
- `readingOrder[]`(systemId), `nonStaffMask?`(텍스트 검출용), `oodFlags[]`

### 3.4 `StaffLattice` (S3d, W6 읽기 구성기)

```json
{
  "schema": "clavis-ir-0.1", "id": "pg0-sy3-st0", "stripId": "pg0-sy3-st0",
  "producer": {"name": "symbols", "version": "0.3.0", "sha256": "<분류기 모델 묶음 + 규칙 카탈로그 + 설정 digest>"},
  "hypotheses": [
    {"rank": 0, "logProbMicro": -1834567,
     "items": [
       {"item": {"type": "note", "dur": "eighth", "dots": 0, "pos": 5, "head": "normal", "v": 1, "beam": "begin"},
        "attrTopK": {"dur": [["eighth", 9120], ["16th", 810]], "pos": [[5, 9650], [4, 300]]},
        "spanU": [412.0, 431.5], "itemProbBp": 8890,
        "symbolIds": ["pg0-sy3-st0-s41", "pg0-sy3-st0-s42"]}
     ]}
  ]
}
```

- `hypotheses`는 최대 8개이고 rank 오름차순이다. 관계 모호성의 조합에서 결정적으로 열거한다. `logProbMicro`는 log 확률 × 10⁶을 정수로 반올림한 값이다.
- `attrTopK`는 속성별 상위 3개까지 담는다(bp). 값은 W6 분류기·속성 추정기의 분포에서 온다.
- `spanU`는 근거 기호 박스의 x 구간이다. `symbolIds`는 이 항목을 만든 `SymbolGraph` 기호들이다. W8은 이것으로 evidence를 만든다.

### 3.5 `SymbolGraph` (S3a–S3c, W6) — 주 인식 결과

```json
{
  "schema": "clavis-ir-0.1", "id": "pg0-sy3-st0", "stripId": "pg0-sy3-st0",
  "producer": {"name": "symbols", "version": "0.3.0", "sha256": "…"},
  "symbols": [
    {"symbolId": "pg0-sy3-st0-s41", "sources": ["fcn", "template"],
     "classTopK": [["noteheadFilled", 9420], ["noteheadHollow", 410], ["reject", 170]],
     "boxStrip": [405.2, 61.0, 17.8, 14.1], "centerStrip": [414.1, 68.0],
     "posTopK": [[5, 9650], [4, 300]],
     "attrs": {"stemDir": [["up", 9100]], "dotsTopK": [[0, 9700], [1, 300]]}},
    {"symbolId": "pg0-sy3-st0-s42", "sources": ["vline"],
     "classTopK": [["stem", 9800]], "boxStrip": [430.0, 12.0, 2.1, 56.0], "centerStrip": [431.0, 40.0],
     "attrs": {"beamCountTopK": [[1, 7000], [2, 2900]], "flagCountTopK": [[0, 9900]]}}
  ],
  "relations": [
    {"kind": "stemOf", "from": "pg0-sy3-st0-s42", "to": "pg0-sy3-st0-s41", "probBp": 9600}
  ],
  "rejectedCandidates": [
    {"symbolId": "pg0-sy3-st0-s77", "sources": ["cc"], "classTopK": [["reject", 6100], ["noteheadFilled", 3500]], "boxStrip": [980.0, 60.0, 16.0, 14.0]}
  ]
}
```

- 좌표는 strip px(소수 둘째 자리). 모든 확률은 bp 정수다.
- `sources`: 후보를 낸 생성기(`fcn`, `template`, `cc`, `vline`, `beam`, `curve`, `ledger`). 생성기 간 일치는 신뢰도 신호다.
- `attrs`: 클래스별 속성 분포. `posTopK`(음표 머리, 쉼표), `stemDir`, `beamCountTopK`·`flagCountTopK`(stem), `dotsTopK`, `headType` 등.
- `relations.kind`: `stemOf`, `beamOf`, `flagOf`, `dotOf`, `accidentalOf`, `tieFrom`, `tieTo`, `slurFrom`, `slurTo`, `ledgerOf`, `chordWith`, `voiceOf`. 한 기호에 경쟁 관계가 있으면 모두 남긴다(상위 2개).
- `rejectedCandidates`: 거절됐지만 점수가 기준 이상인 후보. W8의 누락 의심 신호로 쓴다.

클래스(v0.1): `noteheadFilled`, `noteheadHollow`, `noteheadWhole`, `noteheadSlash`, `noteheadX`, `stem`, `beam`, `flag`, `accSharp`, `accFlat`, `accNatural`, `accDoubleSharp`, `accDoubleFlat`, `augDot`, `restWhole`, `restHalf`, `restQuarter`, `rest8th`, `rest16th`, `rest32nd`, `clefG`, `clefF`, `clefC`, `timeDigit`, `timeCommon`, `timeCut`, `barline`, `repeatDots`, `curve`(tie·slur), `tupletNumber`, `fermata`, `ledgerLine`, `segno`, `coda`, `voltaBracket`, `reject`(배경·글자·기타).

### 3.6 `TextIR` (S4, W7)

`items[]`:

- `textId`, `pageIndex`, `boxProcessed[x, y, w, h]`, `polygon?`
- `role`: `chord` | `lyric` | `title` | `subtitle` | `tempo` | `section` | `navigation` | `rehearsal` | `credit` | `pageNumber` | `other`, 그리고 `roleProbs{role: bp}`
- `text`(NFC), `alternatives[]{text, probBp}`, `confidenceBp`
- `glyphs[]?{char, box, probBp}`, `syllables[]?{text, box, hyphenAfter, extender}`(가사 줄), `verse?`
- `staffLink{staffId, relation: above|below, distanceSpaces}`
- `chord?`: 6절의 파싱 결과(role이 chord일 때)

### 3.7 `ScoreIR` (S5–S7, W8)

- `meta{title?, subtitle?, tempo?}`, `engine{version, buildDigest}`
- `parts[]{partId, name?, staffCount, staffSlots[]}`: brace로 묶인 보표 무리는 한 파트의 여러 보표, 나머지는 보표 하나가 한 파트다.
- `measures[]`(파트별): `measureId`, `index`, `number`(표시용 문자열. 못갖춘마디는 `"0"`), `implicit`, `pageIndex`, `systemId`, `capacity`(Fraction), `staffMeasures[]`
  - `staffMeasures[]`: `staffMeasureId`, `staffId`, `clef?`, `key?{fifths}`, `time?{beats, beatType, symbol?}`, `barlineLeft?`, `barlineRight?`, `ending?`, `voices[]{voice, events[]}`, `evidenceIds[]`, `confidenceBp`, `status: ok|flagged|blocked`
- `Event`: `eventId`, `kind: note|rest|rhythm`, `onset`, `duration`, `notated{type, dots, tuplet?{actual, normal}}`, `chordWithPrev`, `grace?`, `pitch?`, `pos?`, `accidentalVisible?`, `tie{start, stop}`, `slur{start, stop}`, `fermata`, `measureRest`, `lyrics[]{verse, text, syllabic, extend, textId}`, `evidenceIds[]`, `confidenceBp`, `flags[]`
- `Harmony`: `harmonyId`, `onset`, `root{step, alter}`, `kind`(MusicXML kind), `kindText`, `degrees[]{value, alter, type: add|alter|subtract}`, `bass?`, `sourceText`, `textId`, `confidenceBp`, `evidenceIds[]`
- `Direction`: `directionId`, `onset`, `kind: tempo|section|navigation|rehearsal|words`, `value`, `textId?`, `symbolId?`, `confidenceBp`
- `flow{repeats[], endings[], navigation[]{kind: segno|coda|toCoda|dalSegno|daCapo|fine|dsAlCoda|dsAlFine|dcAlCoda|dcAlFine, measureId}}`
- `status: complete|partial|blocked`, `diagnostics[]`

### 3.8 `ReviewHint` (S7, W8)

```json
{
  "hintId": "hint-P1-m12-s1-v1-e3-DURATION_MISMATCH",
  "target": {"kind": "event", "id": "P1-m12-s1-v1-e3"},
  "reasonCode": "DURATION_MISMATCH",
  "severity": "blocking",
  "confidenceBp": 4120,
  "alternatives": [
    {"alternativeId": "a0", "labelKo": "16분음표로 변경", "patch": {"kind": "duration", "duration": {"n": 1, "d": 4}}, "confidenceBp": 3900}
  ],
  "evidenceIds": ["ev-P1-m12-s1-v1-e3-symbol"]
}
```

- `target.kind`: `event` | `measure` | `measureStart` | `measureEnd` | `harmony` | `lyric` | `text` | `flow`
- `severity`: `blocking`(편곡 결과를 바꿀 수 있음) | `warning` | `info`
- `patch.kind`는 HarmonyMaker typed patch와 1:1로 대응한다: `pitch`, `duration`, `accidental`, `tie`, `chord`, `timeSignature`, `keySignature`, `replaceEvent`, `replaceSourceText`, `insertBarline`, `deleteBarline`
- `reasonCode`(v0.1): `DURATION_MISMATCH`, `LOW_CONFIDENCE_PITCH`, `LOW_CONFIDENCE_DURATION`, `ACCIDENTAL_AMBIGUOUS`, `TIE_SLUR_AMBIGUOUS`, `KEY_SIGNATURE_UNCERTAIN`, `TIME_SIGNATURE_UNCERTAIN`, `CLEF_UNCERTAIN`, `BARLINE_UNCERTAIN`, `VOICE_ASSIGNMENT_UNCERTAIN`, `CHORD_TEXT_UNCERTAIN`, `CHORD_POSITION_UNCERTAIN`, `CHORD_OUTSIDE_CONSUMER_VOCAB`, `LYRIC_TEXT_UNCERTAIN`, `LYRIC_ALIGNMENT_UNCERTAIN`, `FLOW_UNRESOLVED`, `EVIDENCE_MISSING`, `MODEL_DISAGREEMENT`, `OOD_REGION`, `ILLEGIBLE_REGION`
- 정렬: (pageIndex, systemIndex, measure index, target.id, reasonCode)

## 4. 토큰 언어 LSTL v0.1 (Lead-Sheet Staff Token Language)

LSTL은 **한 시스템 안의 한 보표에 인쇄된 것**을 왼쪽에서 오른쪽으로 적은 시퀀스다. 논리적 악보가 아니라 **시각 표현**이다. 시스템 첫머리에 다시 찍힌 음자리표와 조표도 그 시스템의 LSTL에 나온다.

### 4.1 항목과 속성

| type | 필수 속성 | 선택 속성 |
|---|---|---|
| `clef` | `sign` ∈ {G2, G2_8vb, G2_8va, F4, F4_8vb, F3, C1, C2, C3, C4, C5} | `courtesy` |
| `key` | `fifths` ∈ [−7, 7] | `cancel` ∈ [0, 7](앞에 찍힌 제자리표 수), `courtesy` |
| `time` | `beats` ∈ [1, 16], `beatType` ∈ {1, 2, 4, 8, 16, 32} | `symbol` ∈ {common, cut}, `courtesy` |
| `bar` | `style` ∈ {regular, double, final, repeatStart, repeatEnd, repeatBoth, dashed, heavy} | — |
| `note` | `dur`, `dots`, `pos`, `head`, `v` | `acc`, `accParen`, `tie`, `slur`, `chord`, `grace`, `tup3`, `fermata`, `stem`, `beam` |
| `rest` | `dur`, `dots`, `v` | `pos`, `measureRest`, `fermata`, `tup3` |
| `mrest` | `count` ∈ [2, 64] | — |
| `ending` | `numbers`(정수 목록, 예: [1], [1, 2]), `mark` ∈ {start, stop, discontinue} | — |
| `segno` | — | — |
| `coda` | — | — |

| 속성 | 값 |
|---|---|
| `dur` | breve, whole, half, quarter, eighth, 16th, 32nd, 64th |
| `dots` | 0, 1, 2 |
| `pos` | 정수 [−14, 22]. **0 = 맨 아래 오선, 8 = 맨 위 오선**, 홀수는 칸 |
| `head` | normal, slash, x, diamond (`slash`는 음높이 없는 리듬 이벤트) |
| `acc` | none, sharp, flat, natural, doubleSharp, doubleFlat |
| `tie`, `slur` | none, start, stop, both |
| `chord` | 0, 1 (1 = 앞 음과 같은 stem과 같은 시점) |
| `v` | 1–4 (1 = 위·주 성부) |
| `grace` | none, acciaccatura, appoggiatura |
| `tup3` | none, start, continue, stop (v0.1은 3:2 셋잇단만) |
| `stem`, `beam` | 보조 라벨(none, up, down / none, begin, continue, end). 학습 보조용이며 출력 의미에는 쓰지 않는다 |
| `fermata`, `measureRest`, `courtesy`, `accParen` | 0, 1 |

v0.1 범위 밖(OOD로 표시하거나 무시): 퍼커션·타브 보표, 트레몰로, 8va선, 셋잇단 외 연음부, 두 겹 이상의 이음줄.

### 4.2 정규 순서 (같은 시각 표현 → 하나의 토큰열)

1. 보표 내용을 **열(column)**로 나눈다. 같은 마디에서 같은 음악 시점을 공유하는 음표와 쉼표가 한 열이다. 꾸밈음은 본음 앞에 자기 열을 가진다. 비시간 항목(`clef`, `key`, `time`, `bar`, `ending`, `segno`, `coda`)은 인쇄 위치마다 각자 열이다.
2. 열은 인쇄된 왼쪽→오른쪽 순서를 따른다.
3. 한 열 안에서는 성부 오름차순이다. 같은 성부의 화음은 `pos` 오름차순이고, 첫 음이 `chord=0`, 나머지가 `chord=1`이다.
4. barline 위치의 항목 순서: `bar` → `ending(stop)` → `ending(start)` → `segno`/`coda` → `clef` → `key` → `time`. 시스템 첫머리는 `clef` → `key` → `time`.
5. 시스템 끝의 예고(courtesy) 기호는 마지막 `bar` 뒤에 `courtesy=1`로 온다. 의미 해석에서는 무시한다.
6. 속성 직렬화 순서는 4.1절 표의 순서를 따른다. 기본값(0, none)은 텍스트 표기에서 생략한다.

### 4.3 텍스트 표기 (golden 파일, 디버깅용)

한 줄에 항목 하나를 쓴다. 예시는 3/4박, 조표 ♭1, 첫 마디가 8분음표 두 개 + 점4분음표 + 8분음표인 보표다.

```text
clef sign=G2
key fifths=-1
time beats=3 beatType=4
note dur=eighth pos=5 head=normal v=1 beam=begin
note dur=eighth pos=6 head=normal v=1 beam=end
note dur=quarter dots=1 pos=7 head=normal v=1
note dur=eighth pos=6 head=normal v=1 tie=start
bar style=regular
note dur=half pos=6 head=normal v=1 tie=stop
rest dur=quarter v=1
bar style=final
```

### 4.4 속성 대안과 문법 검증 (W6 읽기 구성기, W8 참고)

- lattice의 속성(`dur`, `dots`, `pos`, `acc`, `head`, `tie`, `slur`, `chord`, `v`, `grace`, `tup3`, `fermata`, `measureRest`, `sign`, `fifths`, `cancel`, `beats`, `beatType`, `symbol`, `style`, `numbers`(1–4 비트마스크), `mark`, `count`)마다 대안 분포를 둔다. 해당 type에 없는 속성은 쓰지 않는다.
- `dur` 대안은 기호 속성에서 계산한다: 머리 종류 × beam/flag 개수 × 셋잇단 숫자. 예를 들어 "채운 머리 + beam 1개(0.7) 또는 2개(0.29)"는 `dur`의 eighth(0.7), 16th(0.29) 대안이 된다.
- 문법 오토마톤(W1 구현)은 type별 허용 속성과 값, 순서 제약(예: `chord=1`은 같은 열의 앞 `note` 뒤에만 올 수 있다)을 강제한다. W6 읽기 구성기와 W8 제약 해석은 오토마톤을 통과하는 조합만 만든다.

## 5. 이론 모듈 규칙 (W8 구현, 모든 워커 공유)

### 5.1 보표 위치 → 음높이

`pos = 0`(맨 아래 오선)의 음높이:

| clef | pos 0 | clef | pos 0 |
|---|---|---|---|
| G2 | E4 | C1 | C4 |
| G2_8vb | E3 | C2 | A3 |
| G2_8va | E5 | C3 | F3 |
| F4 | G2 | C4 | D3 |
| F4_8vb | G1 | C5 | B2 |
| F3 | B2 | | |

음이름 = 기준 음 + pos(온음계 단계). MusicXML에는 실제 소리 음높이를 쓰고, 옥타브 음자리표는 `<clef-octave-change>`로 표현한다.

### 5.2 변화표 결정 (순서대로 적용)

1. 음표에 임시표가 보이면 그 값을 쓴다(natural = 0, sharp = +1, flat = −1, doubleSharp = +2, doubleFlat = −2). 그리고 **같은 보표, 같은 pos**의 마디 안 상태에 기록한다. 모든 성부가 공유한다.
2. 앞 음과 붙임줄로 이어진 음(`tie` stop)이고 pos가 같으면 앞 음의 변화를 따른다. 마디를 넘어도 같다.
3. 마디 안 상태에 그 pos가 있으면 그 값을 쓴다.
4. 그 밖에는 조표를 따른다.

꾸밈음도 상태에 참여한다. 괄호 임시표(예고)는 의미를 바꾸지 않는다.

### 5.3 길이

- 기본값(4분음표 단위): breve 8, whole 4, half 2, quarter 1, eighth 1/2, 16th 1/4, 32nd 1/8, 64th 1/16
- 점: ×3/2(점 1개), ×7/4(점 2개). 셋잇단: ×2/3. 꾸밈음은 시간축 길이 0
- 마디 용량 = beats × 4 / beatType. 온마디 쉼표(`measureRest=1`)의 길이는 용량과 같다

### 5.4 성부와 마디 유효성

- 각 성부는 0에서 시작하는 시간축을 가진다. 성부가 늦게 시작하거나 일찍 끝나면 export에서 `<forward>`로 표현한다. 보이지 않는 구간은 사건이 아니다.
- **overfull**(어떤 성부의 합 > 용량)은 `complete` 출력에서 허용하지 않는다.
- **못갖춘마디**: 첫 마디는 용량보다 짧을 수 있다(`implicit=true`, `number="0"`). 마지막 마디가 짧고 못갖춘마디와 합이 용량이면 정보성 진단만 남긴다.
- **붙임줄**: 같은 성부에서 음높이가 같고, 다음 음의 onset이 앞 음의 끝과 같을 때만 tie다. 곡선은 있는데 음높이가 다르면 slur로 해석하고 `TIE_SLUR_AMBIGUOUS` 힌트를 단다. 시각 증거가 같으므로 이것은 해석이지 창작이 아니다.
- **리듬 슬래시**: `kind = rhythm`이며 pitch가 없다.

### 5.5 제약 해석 (정직성 규칙)

마디 길이 불일치를 풀기 위한 탐색은 lattice의 **대안 속성**(`attrTopK`, N-best 가설) 가운데서만 고른다. 새 음표를 삽입하거나, 음표를 지우거나, 쉼표를 만들어 채우는 것은 금지다. 높은 확신(기본 ≥ 9500 bp, 레지스트리 값)의 속성을 뒤집어야만 풀리면 풀지 않는다. 대신 마디를 `flagged`나 `blocked`로 두고 `DURATION_MISMATCH` 힌트에 후보 대안을 담는다.

## 6. 코드 심벌 문법과 정규형

```text
chord      := "N.C." | root body ["/" bass]
root, bass := step [acc]            ; step ∈ A..G, acc ∈ {#, b}
body       := [quality] [primary] [sus] {modifier}
quality    := "m" | "min" | "-" | "dim" | "°" | "aug" | "+" | "maj" | "M" | "Δ"
primary    := "2" | "5" | "6" | "6/9" | "7" | "maj7" | "M7" | "Δ7" | "9" | "maj9" | "11" | "13"
sus        := "sus" | "sus2" | "sus4"
modifier   := "add" ("2"|"4"|"6"|"9"|"11"|"13") | ("b"|"#") ("5"|"9"|"11"|"13") | "no3" | "no5"
            | "(" modifier {"," modifier} ")"
composite  := "m7b5" | "ø" | "ø7" | "dim7" | "°7" | "mMaj7" | "minMaj7" | "mMaj9"
```

- **인식 결과는 이 문법을 통과한 문자열만** 출력한다(W7 문법 제약 디코딩).
- 정규형은 root + 정규 접미사 + 변화음(b5, #5, b9, #9, #11, b13 순서) + `/bass`다. 예: `Bbmaj7`, `F#m7b5`, `Dsus4`, `G7(b9)` → `G7b9`, `C/E`.
- MusicXML `<harmony>` 대응: `root`, `kind`(major, minor, augmented, diminished, dominant, major-seventh, minor-seventh, diminished-seventh, half-diminished, major-minor, major-sixth, minor-sixth, dominant-ninth, major-ninth, minor-ninth, dominant-11th, dominant-13th, suspended-second, suspended-fourth, power, none), `kind@text`(인쇄된 접미사 그대로, 예: "M7", "△7", "-7"), `degree`(add, alter, subtract), `bass`.
- HarmonyMaker 파서 어휘(12.6절) 밖의 코드(예: `C5` power, `C11`)도 정확히 출력하되 `CHORD_OUTSIDE_CONSUMER_VOCAB`(info) 힌트를 단다.

## 7. 가사 표현

- 보표 아래 가사 줄은 위에서부터 절 번호 1, 2, …다. 줄 앞에 "1.", "2." 같은 표시가 있으면 그것을 우선한다.
- 음절은 `text`(NFC), `syllabic`(single, begin, middle, end), `extend`, `textId`, 부착 이벤트 ID를 가진다.
- **한국어**: 한글 음절 블록 하나가 음절 하나다. 띄어쓰기 없이 이어진 단어는 begin/middle/end, 한 음절 단어는 single이다. 문장부호는 앞 음절에 붙인다.
- **영어**: 하이픈으로 begin/middle/end를 정하고, 연장선이 있으면 `extend=true`다.
- 부착 대상은 note와 rhythm 이벤트다. 붙임줄 끝음(tie stop)과 쉼표에는 붙이지 않는다.

## 8. 출력 산출물

### 8.1 파일 구성 (출력 디렉터리)

| 파일 | 조건 | 결정성 |
|---|---|---|
| `result.musicxml` | 상태가 `complete`일 때만 | 바이트 동일 |
| `partial.musicxml` | 상태가 `partial`일 때 최선 결과(blocked 마디 포함, 힌트로 표시) | 바이트 동일 |
| `evidence.json` | 항상(가능한 범위) | 바이트 동일 |
| `review-hints.json` | 항상 | 바이트 동일 |
| `element-confidence.json` | 항상 | 바이트 동일 |
| `report.json` | 항상 | 바이트 동일 |
| `runtime.json` | 항상 | **비결정적 허용**(지연, 메모리, 스레드) |
| `debug/` | `--debug`일 때만 | 단계별 IR 덤프 |

### 8.2 MusicXML 프로필

- `<?xml version="1.0" encoding="UTF-8"?>`와 `<score-partwise version="4.0">`. **DOCTYPE, 외부 엔티티, 처리 지시문은 금지**한다.
- `<identification><encoding><software>Clavis x.y.z</software>`. 날짜처럼 비결정적인 값은 넣지 않는다.
- `divisions`는 파트별로 한 값이며, 필요한 분모의 최소공배수다.
- 마디 `number`는 표시 번호다. 못갖춘마디는 `number="0" implicit="yes"`다.
- 음표: `pitch` 또는 `unpitched`(리듬 슬래시: `display-step`/`display-octave` + `<notehead>slash</notehead>`) 또는 `rest`, `duration`, `tie`, `voice`, `type`, `dot`, `time-modification`, `staff`(여러 보표일 때), `notations`(tied, slur, tuplet, fermata), `lyric`(number, syllabic, text, extend).
- 화음 구성음은 `<chord/>`. 성부 전환은 `<backup>`/`<forward>`.
- `<harmony>`는 해당 onset의 음표 앞에 둔다. 음표 시작과 어긋나면 `<offset>`을 쓴다.
- `<direction>`: 섹션 라벨과 진행 문구는 `words`, 리허설 마크는 `rehearsal`, 템포는 `metronome` + `<sound tempo>`(인식된 경우만), segno와 coda는 기호로 쓴다.
- `<barline>`: bar-style, repeat, ending(number, type).
- 원본 레이아웃을 `<print new-system="yes"/>`, `<print new-page="yes"/>`로 보존한다.
- **`id` 속성**: MusicXML 4.0 XSD가 허용하는 요소(measure, note, harmony, direction, barline 등)에 1.1절 ID를 단다. 허용하지 않는 요소는 `element-confidence.json`에서 부모 ID와 경로로 참조한다.
- `complete` 조건: XSD 검증 통과, overfull·음수 backup·0 길이·앞 음 없는 chord 없음, **재파싱 동등성**(ScoreIR → MusicXML → 파싱 → 투영이 원래 투영과 같음).

### 8.3 `evidence.json` (`clavis-evidence-0.1`)

HarmonyMaker `VendorEvidenceBundle`과 호환된다.

```json
{
  "schema": "clavis-evidence-0.1",
  "granularity": "measure",
  "frames": [{"id": "clavis:frame:0", "pageIndex": 0, "coordinateSpace": "original-pixels",
              "widthPixels": 1170, "heightPixels": 2532, "imageDigest": "<원본 페이지 bytes SHA-256>"}],
  "transforms": [],
  "evidence": [{"id": "ev-P1-m12-s1-v1-e3-symbol", "vendorTargetId": "P1-m12-s1-v1-e3",
                "granularity": "symbol",
                "box": {"frameId": "clavis:frame:0", "xMu": 512000000, "yMu": 880000000,
                        "widthMu": 14000000, "heightMu": 12000000},
                "confidenceBp": 9731, "vendorId": "clavis"}],
  "extensions": {"staffPolygons": [], "measureBoxes": []}
}
```

- `granularity`는 **모든 마디에 보장하는 최소 수준**이다(v1: `measure`). 개별 evidence는 더 세밀할 수 있다(`symbol`).
- `vendorTargetId`는 번들 안에서 고유하고, 항상 MusicXML에 실제로 있는 `id`를 가리킨다. 마디 근거는 파트 마디(`P1-m12`) 하나에 대해 파트의 모든 보표를 덮는 박스 하나다. 보표별 마디 박스는 `extensions.measureBoxes`에 둔다.
- 좌표는 HarmonyMaker fixed-point 규칙을 따른다. 절댓값에 round-half-up을 적용하고 부호를 복원한다. 박스는 프레임 경계 안에 있어야 한다.
- HarmonyMaker 어댑터는 `schema`와 `extensions`를 뺀 네 키로 번들을 만들고 `providerBundleDigest`를 직접 계산한다. 엔진은 digest를 계산하지 않는다.

### 8.4 `review-hints.json`, `element-confidence.json`, `report.json`

- `review-hints.json`: `{"schema": "clavis-hints-0.1", "thresholdArtifactDigest": "…"|null, "hints": [ReviewHint…]}`
- `element-confidence.json`: `{"schema": "clavis-confidence-0.1", "elements": [{"id", "kind", "confidenceBp", "flagged"}]}`. **출력의 모든 음악 요소**(event, harmony, lyric, measure, key/time/clef 변경, flow)를 담는다. 평가기의 K2 계산이 이 파일을 쓴다.
- `report.json`: `engine{name, version, gitSha, buildDigest}`, `models[]{name, version, sha256}`, `configDigest`, `input.pages[]{pageIndex, bytesSha256, width, height, sourceKind, rasterDpi?}`, `quality[]`, `status`, `errorCode?`, `counts{systems, staves, measures, events, harmonies, lyrics, hintsBySeverity}`, `diagnostics[]{code, severity, target?}`

### 8.5 상태와 오류 코드

| 코드 | 뜻 |
|---|---|
| (상태) `complete` / `partial` / `blocked` | 전체 유효 / 일부 마디 blocked / 유효 결과 없음 |
| `CLAVIS_INPUT_UNSUPPORTED` | 지원하지 않는 형식 |
| `CLAVIS_INPUT_CORRUPT` | 디코딩 실패, magic byte 불일치 |
| `CLAVIS_INPUT_TOO_LARGE` | 바이트, 픽셀 수, 페이지 수 한도 초과 |
| `CLAVIS_QUALITY_RETAKE` | 품질 미달(이유: `RESOLUTION_TOO_LOW`, `BLUR`, `GLARE`, `CROPPED`) |
| `CLAVIS_NO_STAFF_FOUND` | 오선을 찾지 못함 |
| `CLAVIS_OOD` | 범위 밖(하위: `TABLATURE`, `PERCUSSION`, `HANDWRITTEN_SUSPECTED`, `MULTI_COLUMN`, `UNKNOWN`) |
| `CLAVIS_OUTPUT_INCOMPLETE` | partial 결과(HTTP에서는 rejected-output 경로) |
| `CLAVIS_OUTPUT_BLOCKED` | 유효한 음악 결과 없음 |
| `CLAVIS_RESOURCE_LIMIT`, `CLAVIS_TIMEOUT`, `CLAVIS_CANCELLED`, `CLAVIS_INTERNAL` | 운영 오류 |

## 9. CLI 계약 (W1 골격, W9 완성)

```text
clavis recognize <input>... --out <dir> [--pages 0,2] [--config <yaml>] [--threads 4] [--debug]
clavis selfcheck          # 모델 manifest 해시 검증 + 내장 샘플 실행
clavis version            # 엔진·모델·계약 버전 출력(JSON)
```

- `--out`은 존재하지 않거나 비어 있어야 한다.
- 종료 코드: `0` complete · `10` partial · `20` blocked/OOD/retake · `2` 사용법 오류 · `1` 내부 오류.
- 끝나면 stdout 마지막 줄에 요약 JSON 한 줄을 쓴다: `{"status", "errorCode", "outDir", "pages", "measures", "hints"}`.
- HarmonyMaker `/local-image` 경로는 이 CLI를 자식 프로세스로 호출한다.

## 10. HTTP 규약 (HarmonyMaker provider 규약 v1 호환 + 확장, W9)

인증은 `Authorization: Bearer <key>`(32–512자)다. 오류 응답은 `{"detail": "…"}`(≤ 4 KiB)이고, 일반 JSON 응답은 ≤ 64 KiB다.

| 메서드 · 경로 | 요청 | 응답 |
|---|---|---|
| `GET /v1/capabilities` | — | 12.2절의 14개 키를 **정확히** 담는다. `vendorId: "clavis"`, `evidenceGranularity: "measure"`, `supportsInteractiveInput: false` |
| `POST /v1/jobs` | `{"pageCount", "idempotencyKey"}` | `{"jobId": "<uuid>"}` |
| `PUT /v1/jobs/{id}/pages/{i}` | 본문 PNG, 헤더 `Content-Type: image/png`, `Idempotency-Key`, `X-Page-Digest`(본문 SHA-256) | 2xx |
| `POST /v1/jobs/{id}/start` | `{"idempotencyKey"}` | 2xx |
| `GET /v1/jobs/{id}/status` | — | `{"kind": "created"|"queued"|"completed"|"cancelled"}` · `{"kind": "processing", "progressBp"?}` · `{"kind": "failed", "code", "message"}` · `{"kind": "unknown", "rawStatus"}` — 키 집합 정확 일치 |
| `GET /v1/jobs/{id}/result` | — | `result.musicxml`(≤ 4 MiB). complete가 아니면 409 |
| `GET /v1/jobs/{id}/rejected-output` | — | `hm-omr-rejected-output-v1`(12.4절). `code: "CLAVIS_OUTPUT_INCOMPLETE"`, documents는 `partial.musicxml` |
| `GET /v1/jobs/{id}/metadata` | — | `{"pages": [{"pageIndex", "pageDigest", "widthPixels", "heightPixels"}]}` |
| `POST /v1/jobs/{id}/cancel` | `{"idempotencyKey"}` | 2xx |
| `DELETE /v1/jobs/{id}` | 헤더 `Idempotency-Key` | `{"status": "deleted"}` 또는 `{"status": "failed", "code", "message"}` |
| `GET /v1/jobs/{id}/retention` | — | `{"canDeleteImmediately", "vendorDeletesAt"?, "policyReference"?}` |
| **확장** `GET /v1/jobs/{id}/evidence` | — | `evidence.json`(≤ 4 MiB) |
| **확장** `GET /v1/jobs/{id}/review-hints` | — | `review-hints.json` + `element-confidence.json`을 묶은 JSON(≤ 4 MiB) |
| **확장** `GET /v1/jobs/{id}/report` | — | `report.json` |
| `GET /health` | — | `{"status": "ok", "version"}` |

- 확장 엔드포인트는 64 KiB를 넘을 수 있다. HarmonyMaker 쪽 새 어댑터는 별도 크기 한도로 읽어야 한다(W9 설계서에 명시).
- 기존 Audiveris 어댑터는 `vendorId === "audiveris"`를 검사하므로, HarmonyMaker에는 `vendorId: "clavis"`를 받는 새 어댑터가 필요하다. 이 어댑터는 HarmonyMaker 저장소의 별도 작업이다.
- 런타임은 외부 네트워크를 호출하지 않는다. 작업 데이터는 기본 1시간 보관 후 삭제한다.

## 11. 결정성 계약

- 같은 입력 바이트, 같은 엔진 빌드(코드 SHA + 모델 SHA + 설정 digest), 같은 OS 계열이면 `runtime.json`을 뺀 모든 출력이 **바이트 동일**해야 한다.
- 스레드 수(1, 4)가 출력을 바꾸면 안 된다.
- ONNX Runtime의 부동소수 차이에 대비해, 판정에 쓰는 로짓과 점수는 10⁻⁴ 단위로 양자화한 뒤 비교한다. 동점은 클래스 인덱스, ID 사전순으로 깬다.
- Windows와 Linux 사이 일치율은 CI에서 측정해 보고한다(목표 100%). 차이가 나면 결함으로 기록한다.

## 12. HarmonyMaker 호환 발췌 (참조용. 이 저장소는 HarmonyMaker 코드를 import하지 않는다)

출처: HarmonyMaker `docs/HARMONYMAKER_SPEC_v3.1.5.md` 20–22절, `src/server/omr/audiveris-http-adapter.ts`, `src/domain/omr/rejected-output.ts`, `src/domain/omr/evaluation.ts`, `src/domain/chord/parser.ts` (2026-09-29 시점).

### 12.1 이미지 품질 보고

`ImageQualityReport { blurBp, perspectiveBp, glareBp, cropRiskBp, estimatedStaffSpacePixels?, status: pass|warn|retake, reasons[] }`. HarmonyMaker의 초기 휴리스틱은 interline < 12 px이면 retake, 12–17이면 warn, ≥ 18이면 pass 후보다. Clavis는 이 임계값을 **자기 해상도 곡선으로 다시 보정해** 제안한다(목표는 8 px까지 사용 가능).

### 12.2 capabilities 키 (정확히 14개)

`vendorId`, `vendorDisplayName`, `supportedMimeTypes`, `transferMimeType`, `maxPages`, `evidenceGranularity`, `supportsDeletion`, `retentionDisclosure`, `supportsIdempotency`, `supportsInteractiveInput`, `canDeleteImmediately`, `retentionPolicyReference`, `externalTransfer`, `estimatedCreditPerPage`

### 12.3 Evidence 타입

`EvidenceGranularity = none|page|staff|measure|symbol`. `BoundingBox{frameId, xMu, yMu, widthMu, heightMu}`. `OmrEvidence{id, vendorTargetId?, granularity, box, transformId?, confidenceBp?, vendorId}`. `ImageCoordinateFrame{id, pageIndex, coordinateSpace: original-pixels|normalized-original|processed-pixels, widthPixels, heightPixels, imageDigest}`. 1 px = 1,000,000 µ, 행렬 1.0 = 10⁹.

### 12.4 rejected-output 형식

`{version: "hm-omr-rejected-output-v1", status: "incomplete", code, engineVersion(/^[A-Za-z0-9._-]{1,64}$/), pages[1..12]{pageIndex, pageDigest, widthPixels, heightPixels}, documents[1..32]{id: "fragment-<n>", rawMusicXml, sha256}}`. 크기 ≤ 4,000,000 bytes. HarmonyMaker의 허용 코드 목록에 `CLAVIS_OUTPUT_INCOMPLETE` 추가가 필요하다(HarmonyMaker 측 작업).

### 12.5 평가 지표와 corpus 필드 이름

- Ground truth: `pitchExactRate`, `durationExactRate`, `accidentalExactRate`, `restExactRate`, `tieExactRate`, `keySignatureExactRate`, `timeSignatureExactRate`, `chordSymbolExactRate`, `measureExactMatchRate`
- 구조: `parseableMusicXmlRate`, `measureDurationValidRate`, `voiceTimelineValidRate`, `runtimeValidatorReadyRate`
- 제품: `harmonizationReadyRate`, `medianCorrectionTime`, `correctionsPer100Notes`, `retakeRate`, `abandonmentRate`
- Corpus 항목: `pageId`, `songId`, `captureId`, `split(dev|sealed)`, `sourceKind(digital-pdf|scanned-pdf|camera-photo)`, `meter(4/4|6/8|other)`, `keyMode(major|minor)`, `features(accidentals|dotted-notes|ties)`, `groundTruthDigest`, `publicationFont?`, `captureDevice?`, `editingProgram?`, `rights{basis(self-authored|public-domain|licensed|user-confirmed-rights), allowedUses[], reference}`
- HarmonyMaker 최소 규모: Dev ≥ 36쪽, sealed ≥ 24쪽. 곡과 촬영이 두 분할에 걸치면 안 된다.

### 12.6 HarmonyMaker 코드 파서 어휘

- 품질: `m`, `min`, `-`, `dim`, `°`, `aug`, `+`, `maj`, `Δ`
- 주 확장: `2`, `6`, `6/9`, `7`, `maj7`(`MAJ7`, `Maj7`, `M7`, `Δ7`), `9`, `maj9`(`M9`, `Δ9`)
- 서스: `sus`(= sus4), `sus2`, `sus4`
- 추가음: `add2`, `add4`, `add6`, `add9`, `add11`, `add13`
- 변화음: `b5`, `#5`, `b9`, `#9`, `#11`, `b13`. 생략: `no3`, `no5`
- 복합: `m7b5`/`min7b5`/`ø`/`ø7`, `dim7`/`°7`, `mMaj7`/`minMaj7`, `mMaj9`/`minMaj9`
- 괄호 수식어를 허용하고 슬래시 베이스를 허용한다. 목록에 없는 것(예: `5`, `11`, `13` 단독 주 확장)은 HarmonyMaker가 파싱하지 못할 수 있다 → `CHORD_OUTSIDE_CONSUMER_VOCAB`.

### 12.7 HarmonyMaker typed patch 어휘

`pitch{pitch}`, `duration{duration}`, `accidental{alter}`, `chord{parseResult}`, `time-signature{value}`, `key-signature{value}`, `tie{tieStart, tieStop}`, `replace-event{event}`, `replace-source-text{text}`, `insert-barline`, `delete-barline`. 대상은 `voice-event`, `chord-event`, `measure`, `measure-start`, `measure-end`, `section-text`.
