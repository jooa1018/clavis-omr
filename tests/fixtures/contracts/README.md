# Wave B mock: 자체 작성 3시스템 리드시트

실제 악보·이미지에서 추출한 결과가 아니다. 사적 데이터, Dev, sealed와 무관한
수작업 합성 계약 예시이며, 해시도 mock 표식에서 만든 값이다. 대응 래스터와
실행된 인식 모델은 없다. runtime.json의 0 계측 값도 실제 벤치마크가 아니다.
이 fixture의 complete는 구조화한 악보 상태다. CLI mock 단계에서는 T1.5 규정대로
status=blocked / MOCK_STAGE 진단을 붙여야 한다.

| 파일 | 비어 있지 않은 내용과 하류 사용 |
|---|---|
| valid/page-input.json, quality.json | 880×1180 페이지, original/processed 프레임과 항등 homography, interline 10 px의 mock 품질 보고 |
| valid/layout.json | 세 시스템, 각 5선 보표 1개·두 마디, 오선 polyline, interline profile, 153열 mesh 표본, barline과 RLE mask (W5) |
| valid/symbols-0/1/2.json | 머리·stem·beam·점·쉼표·임시표·곡선·barline 후보와 관계, 거절 후보 (W6) |
| valid/lattice-0/1/2.json | 모든 항목에 실제 graph symbolIds, 첫 보표 박자, 둘째 보표 duration top-k와 N-best 2개 (W6/W8) |
| valid/text.json | 제목·Moderato·6코드·11한글 음절, 보표 연결·박스·음절 정보 (W7/W8) |
| valid/score.json | 파트 1개, slot에 세 물리 보표, 6마디/20이벤트/6코드/11가사, 점음표·쉼표·리듬 슬래시·F#·시스템 간 tie (W8) |
| valid/evidence.json | 모든 파트 마디와 이벤트·코드·템포의 original µ 박스, staff polygons/measure boxes, transforms=[] |
| valid/hints.json, confidence.json | P1-m3 첫 음의 낮은 duration 신뢰도와 16분음표 대안, 전체 음악 요소 confidence |
| valid/report.json, runtime.json | 모의 산출물 개수와 품질·진단·선택 platform 형식 |

`manifest.json`은 파일마다 모델 이름을 명시한다. 같은 schema를 사용하는 IR은
schema만으로 구별하지 말고 단계가 기대하는 모델로 읽는다.

```python
from pathlib import Path
from clavis.contracts import PageLayout, SymbolGraph, StaffLattice, TextIR, ScoreIR

p = Path("tests/fixtures/contracts/valid")
layout = PageLayout.model_validate_json((p / "layout.json").read_bytes())
graph = SymbolGraph.model_validate_json((p / "symbols-1.json").read_bytes())
lattice = StaffLattice.model_validate_json((p / "lattice-1.json").read_bytes())
text = TextIR.model_validate_json((p / "text.json").read_bytes())
score = ScoreIR.model_validate_json((p / "score.json").read_bytes())
assert graph.id == lattice.id == layout.staves[1].staff_id
assert score.parts[0].staff_slots[0].staff_ids[1] == graph.id
assert score.measures[3].staff_measures[0].voices[0].events[0].event_id == "P1-m3-s1-v1-e0"
```

추적 예시: lattice-1의 8분음표(신뢰도 7200, 대안 16분음표 2600) → 해당 graph 기호들 →
`P1-m3-s1-v1-e0` → `ev-P1-m3-s1-v1-e0-symbol` → 같은 이벤트를 가리키는 검토 힌트.
마디 길이를 맞추는 수정은 수행하지 않았다. 대안은 후보로만 남는다.

유효 파일은 `tests/contracts/build_fixtures.py`로 재생성한다. JSON Schema 스냅샷,
모델→JSON→모델 왕복, 모든 문서의 2개 이상 무효 사례(`invalid/`), 참조 결손,
NFC/분수/bp/유한 좌표, 1·4스레드 환경별 3회 동일 바이트를 자동 검증한다.
invalid 파일의 payload는 **의도적으로 무효**이며 model 필드는 시험 메타데이터다.
JSON Schema가 표현하지 못하는 의미 제약은 pydantic과 ContractBundle이 검사한다.
