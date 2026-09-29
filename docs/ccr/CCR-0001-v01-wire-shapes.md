# CCR-0001 — v0.1 최초 구현에 필요한 객체 구조 확정

상태: 승인 · Orchestrator 판정: 2026-09-29 · 작성: W1

## 1. 동기와 범위

T1.2는 CONTRACTS 3·8절의 모든 객체를 pydantic/JSON Schema로 고정하고,
Wave B가 공유할 현실적인 fixture를 제공해야 한다. 현재 문서는 필드 요약이며
아래 연결·하위 타입이 빠져 있다. 빈 배열이나 `dict[str, Any]`로 감추면
검증을 통과해도 W5–W8이 같은 인터페이스를 쓸 수 없다.

W1 지시서 6절: "계약의 모호함을 코드로 조용히 결정하지 않는다. 모호하면 CCR 초안을 써서 Orchestrator에게 묻는다."
C1–C7은 Orchestrator가 아래 수정 사항을 포함해 승인했다.
최종 T1.2 구현 PR 승인은 별도로 받는다.

## 2. 근거와 결정 요청

| ID | 계약 근거와 빈칸 | W1 제안 | 영향 |
|---|---|---|---|
| C1 | 3.7절: `parts[]`, `measures[]`와 독립 Harmony/Direction 정의만 있고 실제 저장 위치·파트 연결이 없음 | ScoreIR의 `measures[]`를 유지하고 Measure에 `partId`, `harmonies[]`, `directions[]` 추가. 동일 파트의 시간 위치는 해당 마디 기준 onset | W8, W4, W9 |
| C2 | 3.7절: `staffSlots[]`, clef/barline/ending, flow 반복·볼타, tempo/value의 타입 없음 | 아래 3절의 명시적 하위 구조 채택 | W5, W8, W4 |
| C3 | 3.6·6절: chord 파싱 결과는 문법만 있고 JSON 객체 정의 없음. N.C.는 허용되지만 Harmony root는 필수처럼 기술됨 | 아래 ChordParseResult를 공유하고 kind=none일 때만 Harmony/root 생략 허용 | W7, W8, W9 |
| C4 | 3.1·3.3·8.3절: frames/transforms·interlineProfile·nonStaffMask·evidence 확장 배열 원소 형태 없음 | 아래 4절 구조 채택. IR float 좌표와 외부 fixed-point는 별도 타입 | W5, W7, W8, W9 |
| C5 | 3절의 모든 객체 schema/id 규정과 ReviewHint 예시의 hintId만 있는 형태가 일치하지 않음. 8.2절의 부모 ID·경로가 8.4절 confidence 객체에는 없음 | schema/id 적용 범위와 confidence 부모 참조를 아래 5절처럼 명시 | 전 워커 |
| C6 | 8.1절은 runtime.json을 항상 요구하지만 필드·schema 버전이 없음 | 아래 6절 RuntimeReport 채택 | W1, W8, W9 |
| C7 | 0절 버전 규칙상 추가 필드는 patch 증가 대상이나 최초 구현은 v0.1로 요청됨 | 아직 배포·소비된 구현이 없으므로 승인된 최초 완성본을 v0.1로 동결하는 예외를 명시. 이후에는 0절의 버전 규칙 적용 | 전 워커 |

대안은 Orchestrator가 다른 wire 구조를 지정하는 것이다. 일반 dict·알 수 없는 필드 허용으로
구현을 먼저 진행하는 대안은 타입·mock의 의미를 약하게 하므로 제안하지 않는다.

## 3. ScoreIR와 텍스트 하위 타입 제안 (C1–C3)

`?`는 생략 가능이며 나머지는 필수다. 모든 이름은 외부 camelCase다.
이 표는 CONTRACTS의 기존 명시 필드를 대체하지 않고 빠진 형태만 채운다.

| 타입/필드 | 제안 형태 |
|---|---|
| Harmony.staffInPart | `int >= 1`, 기본 1; 여러 보표 파트에서 코드가 놓인 보표 |
| Measure 추가 필드 | `partId: string`, `harmonies: Harmony[]`, `directions: Direction[]`; 비어 있어도 배열을 명시 |
| Part.staffSlots | `[{staffInPart: int >= 1, staffIds: string[]}]`; 한 슬롯은 여러 시스템의 물리 staffId를 문서 순서로 연결. 슬롯 번호는 파트 안에서 1부터 연속 |
| StaffMeasure.clef | `{sign: LSTL clef.sign}`; 옥타브 표기도 LSTL 어휘 재사용 |
| StaffMeasure.barlineLeft/Right | `{style: LSTL bar.style}` |
| StaffMeasure.ending | `{numbers: positive int[], mark: start|stop|discontinue}` |
| Event.grace | `none|acciaccatura|appoggiatura`; Event.accidentalVisible는 LSTL acc 어휘 |
| Event.tie/slur | `{start: bool, stop: bool}`; fermata/measureRest/chordWithPrev는 bool |
| TempoValue | `{text?: NFC string, beatUnit?: LSTL dur, dots?: 0/1/2, perMinute?: positive Fraction}`; text 또는 perMinute 필수, perMinute가 있으면 beatUnit 필수 |
| ScoreIR.meta.tempo | `TempoValue` |
| Direction.value | kind=tempo면 `TempoValue`, 나머지는 NFC 문자열 |
| flow.repeats | `[{startMeasureId, endMeasureId, times: int >= 2}]` |
| flow.endings | `[{startMeasureId, endMeasureId, numbers: positive int[]}]` |
| ChordParseResult | `{normalized: string, root?: {step, alter}, kind, kindText, degrees[], bass?: {step, alter}}`; kind/degrees는 6절의 어휘와 동일 |
| N.C. | `normalized="N.C."`, `kind="none"`, root/bass 없음, degrees 빈 배열. Harmony에서도 kind=none일 때 같은 규칙 |
| Diagnostic | `{code: string, severity: blocking|warning|info, target?: {kind, id}}`; target 어휘는 ReviewHint.target 재사용 |

코드 문자열 인식·파싱 알고리즘은 W7 책임이다. T1.2는 이 객체의 타입·범위만 검증한다.
음표 선택, 붙임줄 판정, 흐름 해석, confidence 보정은 W8 책임으로 남긴다.

## 4. 기하·근거 하위 타입 제안 (C4)

| 타입/필드 | 제안 형태 |
|---|---|
| IR frames | 12.3절 ImageCoordinateFrame 형태를 재사용. original-pixels 또는 processed-pixels |
| IR homography | `{id, fromFrameId, toFrameId, kind: "homography", matrix: number[9]}`; float row-major, 2절 정규화 적용 |
| 외부 evidence transforms | v0.1에서는 빈 배열 `[]` 고정. 모든 외부 박스는 original 프레임. 확장은 별도 CCR |
| PageLayout.bbox, glyph/syllable box | `[x, y, width, height]` processed px. polygon/polyline은 `[[x,y], ...]` |
| interlineProfile | `[{x: number, interlinePx: positive number}]`; processed x 오름차순 |
| nonStaffMask | `{frameId, width, height, counts: nonnegative int[]}`; 행 우선 RLE, 0-run부터 0/1 교대, 합은 width×height. 경로·바이너리 blob 없음 |
| extensions.staffPolygons | `[{staffId, frameId, pointsMu: int[2][]}]`; original 프레임 |
| extensions.measureBoxes | `[{staffMeasureId, box: BoundingBox}]`; 12.3절 fixed-point box 재사용 |

채택 결정: v0.1 외부 `evidence.transforms`를 빈 배열로 한정하고 모든 박스를 original로
출력한다(2절에 부합). 이 경우 외부 transform wire 형식을 새로 정하지 않아도 된다.
**C4 중 외부 transforms는 빈 배열 대안을 채택**했다. 비어 있지 않은 전송이 필요해지면
HarmonyMaker 구조를 확인한 별도 CCR로 추가한다. 내부 IR transforms는 여전히 위 타입으로 구현한다.

이미 충분히 명시된 기본값(sStar 등)은 바꾸지 않는다. 3.5절의 SymbolGraph 좌표는
구체적인 2자리 규정을 적용하고, 다른 IR px는 1절의 3자리 규정을 적용한다.

## 5. 공통 envelope·참조·patch 제안 (C5)

- `schema="clavis-ir-0.1"`와 `id`는 독립 IR 문서인 PageInput, QualityReport,
  PageLayout, SymbolGraph, StaffLattice, TextIR, ScoreIR에 적용한다.
- 페이지 IR id는 `pg{p}`, 보표 IR id는 staffId, 문서 ScoreIR id는 `score0`로 한다.
  ID 고유성은 해당 타입·문서 범위이며 모든 IR 타입 사이의 전역 고유성을 요구하지 않는다.
- ReviewHint는 3.8절 예시처럼 `hintId`만 쓰는 중첩 객체로 둔다. 독립 ReviewHint 파일은
  내보내지 않고 `clavis-hints-0.1` envelope의 hints에 담는다. 그 밖의 중첩 객체에도
  별도의 schema/id를 강제로 추가하지 않는다.
- ElementConfidence 기존 필드에 `parentId?: string`, `path?: string`을 추가한다.
  MusicXML에서 자체 id를 갖지 못하는 요소는 둘을 함께 요구한다. path는 부모 아래
  `attributes[1]/key[1]` 같은 1-based 요소 경로로 한정하며 임의 XPath 실행을 뜻하지 않는다.
  id는 confidence 항목의 결정적 ID이며 MusicXML id 없는 항목을 실제 XML id인 것처럼 쓰지 않는다.
- ReviewHint 정렬 위치는 대상 IR의 page/system/measure를 resolve하여 얻는다.
  위치를 힌트 객체에 추가하지 않고 문맥 없는 단독 힌트 직렬화기는 목록 순서를 보존한다.
- patch.kind는 3.8절 camelCase를 유지한다. payload는 12.7절의 각 필드를 사용한다.
  예: `timeSignature{value}`, `replaceEvent{event}`, `tie{tieStart,tieStop}`.
  `pitch`는 Pitch, `duration`은 Fraction, `chord.parseResult`는 위 ChordParseResult,
  time/key의 value는 기존 ScoreIR time/key, event는 Event다. 나머지는 12.7절과 같다.
  HarmonyMaker kebab-case와 target 이름으로의 변환은 소비자 어댑터 책임이다.

추가 필드 거부·bp 0–10000·기약분수·유한 좌표·NFC·고유 ID/참조 검증은
문서에 정해진 구조를 검증하는 장치다. 불확실한 음악을 채우는 추론 규칙은 넣지 않는다.

## 6. RuntimeReport 제안 (C6)

```text
{
  schema: "clavis-runtime-0.1",
  threads: int >= 1,
  elapsedMs: nonnegative int,
  cpuMs: nonnegative int,
  peakRssBytes: nonnegative int,
  stages: [{stageId: string, elapsedMs, cpuMs, peakRssBytes, threads}],
  platform?: {os: string, pythonVersion: string, onnxruntimeVersion?: string}
}
```

값은 관측된 계측 값만 쓴다. 벽시계 날짜, 호스트명, 절대 경로는 필요하지 않다.
T1.2에서는 타입과 fixture만 제공하고 실제 계측은 T1.5/W8에서 연결한다.

## 7. Wave B용 한 쪽 fixture 구성

승인 후 T1.2에서 `tests/fixtures/contracts/`에 구현했다. 사적 악보를 바탕으로 하지 않는 자체 작성
합성 예시 하나를 모든 IR이 함께 참조한다. 빈 배열만 채운 파일은 완료 예시로 인정하지 않는다.

| 묶음 | 구성과 소비 예시 |
|---|---|
| PageInput / QualityReport / PageLayout | 한 페이지, 세 시스템에 각각 단일 보표, 시스템당 두 마디. 오선 polyline·interlineProfile·barlines·mesh·읽기 순서 제공. W5가 strip/layout mock으로 사용 |
| SymbolGraph | 각 보표 파일 하나씩. notehead/stem/beam/accidental/augDot/rest/barline/curve 및 관계, 거절 후보와 속성 top-k. W6가 graph→lattice mock으로 사용 |
| StaffLattice | 각 보표 파일 하나씩. 정상 읽기와 한 군데 길이 대안, 실제 graph symbolIds·spanU 연결. W6/W8이 읽기/대안 소비 mock으로 사용 |
| TextIR | 코드·자체 작성 한국어 음절·제목·템포, 박스·대안·보표 링크. W7/W8이 역할별 텍스트 부착 mock으로 사용 |
| ScoreIR | 한 파트, 세 물리 보표를 연결하는 한 staff slot, 여섯 마디. 점음표·8분 beam·쉼표·시스템 간 tie, 코드와 가사 및 confidence/flag. W8이 조립·출력 mock으로 사용 |
| 출력 묶음 | 모든 마디 근거 + 대표 기호 근거, 검토 힌트와 대안, confidence/report/runtime. original fixed-point 박스·ID 교차 참조 검증 |

연결 예시: `pg0-sy1-st0-s0` 기호 → 해당 보표 lattice의 `symbolIds` →
`P1-m2-s1-v1-e0` 이벤트 → `ev-P1-m2-s1-v1-e0-symbol` → 같은 target의 ReviewHint.
`P1-m2`는 `pg0-sy1`, `staffSlots[0].staffIds[1]`은 `pg0-sy1-st0`다.

PR에는 파일 목록·가져오기 예시·관계 요약과 시험 출력을 싣는다. 모델/JSON/모델 왕복,
Schema 스냅샷, 객체별 유효·다중 무효 예시, dangling reference·bp 범위·분수·NFC·NaN·좌표
정규화 시험을 포함한다. fixture는 mock이며 인식 성능 증거나 실제 이미지 관측으로 주장하지 않는다.

## 8. 마이그레이션과 평가 영향

현재 구현 소비자가 없으므로 승인 후 최초 v0.1 모델·Schema·fixture를 함께 생성한다.
상류/하류 워커는 같은 버전의 묶음을 사용한다. 모델 코드나 평가 알고리즘은 바꾸지 않는다.
계약 구조 검증과 fixture 참조 무결성만 측정하며 Dev/sealed/SYN-Val 성능 수치를 만들지 않는다.

## 9. 판정 기록

Orchestrator가 2026-09-29 C1–C7을 승인했다. C1/C2/C4/C6 수정은 위 표에 반영했다.
C3/C5/C7은 제안 그대로 채택했다. 승인된 최초 완성본을 v0.1로 동결하고 이후 0절을 따른다.
판정 전달: https://github.com/jooa1018/clavis-omr/pull/4#issuecomment-5880412798
영향 워커 의견은 W4/W5/W6/W7/W8/W9에 요청할 사항이며 아직 받은 것으로 기록하지 않는다.
이 CCR 승인과 최종 T1.2 A등급 구현 PR 승인은 별개의 단계다.

## 10. 승인 조건 보완 — PR #4 조건부 승인 (2026-09-29)

Orchestrator는 아래 1–8을 같은 PR에 반영하고 두 OS CI가 통과하면 추가 확인 없이
squash 병합하도록 승인했다. C7 동결 전 v0.1의 일부이며 별도 버전 증가는 없다.
변경 범위는 이 목록과 해당 Schema·fixture·시험·보고서 갱신으로 한정한다.

1. CONTRACTS 4.2의 인쇄 x 순서/겹침 관례를 Orchestrator 문안으로 정정하고 5.4에
   연속 bar는 하나의 마디 경계, 첫 repeatStart는 왼쪽 barline이라는 해석 문안을 추가한다.
   lattice-0 첫 순서는 clef → time → bar(repeatStart)다. 같은 근거를 가리키는 graph/layout의
   repeatStart x도 첫 clef/time 뒤로 옮겼다. 비시간의 서로 겹치지 않는 열 역순을 거부한다.
2. 지정된 LSTL 선택 속성의 none/0/false, Event.grace/accidentalVisible의 none,
   빈 SymbolGraph.attrs를 생략한다. 명시적 기본값은 검증 오류이며 작성기도 생략한다.
   필수 필드·필수 목록은 유지하고 attrTopK 안의 기본값 후보는 허용한다.
3. posTopK는 기호 최상위만, 성부는 attrs.voiceTopK(1–4,bp)만 허용한다. voiceOf는 제거한다.
   CONTRACTS 3.5에 지정된 모든 관계 방향을 명시하고 chordWith의 from id < to id를 검사한다.
4. 모든 top-k는 값 중복 금지, bp 내림차순/동률 값 정규 순서, 합 ≤10000,
   길이 1–3(classTopK 1–5)을 검사한다. 숫자는 오름차순, 문자열은 NFC 사전순,
   정수 목록은 사전순으로 비교하며 enum 선언 순서나 locale에 의존하지 않는다.
5. attrTopK에 현재 항목 값(생략 시 기본값)을 반드시 포함한다. rank는 0부터 연속이며
   logProbMicro는 rank가 커져도 증가하지 않는다.
6. Event의 duration=0은 acciaccatura/appoggiatura에서만 허용한다.
   grace가 아닌 Event 및 모든 DurationPatch의 duration은 양수다.
7. Measure.index는 파트별 목록 순서대로 0부터 연속이다.
8. EvidenceBundle.vendorTargetId 중복 거부를 시험하고 모든 외부 box의
   widthMu/heightMu ≥1을 검사한다(extensions.measureBoxes 포함).

각 번호에 대응하는 `condition-N-*.json` 무효 fixture 46개를 추가했다.
전체 검증 근거는 `docs/reports/W1/T1.2-conditions.md`에 기록한다.
이 조건 충족 후 병합되는 최초 완성본을 v0.1로 동결한다.
