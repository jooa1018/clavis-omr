# CCR-0003 — LSTL 열 표시와 정규 시퀀스

상태: 승인(수정 채택) · Orchestrator · 2026-10-09 · 구현: W1, PR #41

## 1. 동기
LSTL 텍스트와 StaffLattice 자체에서 같은 열의 성부·화음 순서를 검증할 수 있어야 한다.
기존 초안의 외부 columnIndex 문맥/API 안은 채택하지 않았다.

## 2. 승인 결정
### C1. 열 표시는 LSTL 안에 둔다
- chord=1은 앞 note와 같은 stem·같은 열이다. 별도 열 표시는 붙이지 않는다.
- note·rest에 선택 정수 join ∈ {0,1}을 추가한다. 기본 0은 생략한다.
  join=1은 앞 항목과 같은 열, 다른 성부다. note 속성 순서에서 chord 바로 뒤이며,
  chord가 없는 rest는 선택 속성 첫 자리(join, pos, measureRest, fermata, tup3)에 둔다.
- 새 시간 항목 또는 비시간 항목에서 열이 시작하고 뒤따르는 chord=1·join=1이 잇는다.
  join=1의 v는 앞 항목의 v보다 커야 한다. chord=1은 앞 note와 v·dur·dots·grace가 같고
  pos 오름차순이며 join을 쓰지 않는다. 비시간 항목·grace·mrest에 join은 금지다.
- 외부 열 문맥 및 COLUMN_CONTEXT_REQUIRED API는 만들지 않는다. 오토마톤은 기하를
  검증하지 않는다. 같은 x인지의 근거는 W2 렌더 정답과 W6 기호 박스가 책임진다.
- attrTopK에 join을 추가한다. 기본 후보 0도 허용하고 현재/생략 기본값을 포함한다.

### C2. 정규 텍스트
ending numbers는 공백 없는 JSON 정수 목록이다. 속성은 4.1 순서, 항목당 한 줄,
UTF-8·NFC·LF, 끝 LF 하나다. 선택 기본값 및 dots=0은 생략한다. 나머지 필수 값은
0이어도 쓴다. rest.pos도 제공됐으면 0을 쓴다. strict parser는 알 수 없는 속성,
중복·순서 오류·명시적 기본값을 거부한다.

### C3. 유일한 인쇄 순서
겹치지 않는 열은 인쇄 순서, 겹치는 열은 계약 관례만 적용한다. 유일한 순서를
정할 수 없거나 선행 관계가 순환하면 AMBIGUOUS_COLUMN_ORDER로 거부한다.
임계값과 임의 tie-breaker를 만들지 않는다.

## 3. 버전과 마이그레이션
lstl-0.1.1 및 clavis-ir-0.1.1. 기존 0.1 문서는 계속 읽고 버전 표기를 보존한다.
새 fixture/생산자는 0.1.1을 쓴다. 기존 3시스템 mock은 전부 단일 성부이므로
join 변환 대상이 없다. 다성부 golden에는 join=1을 명시한다. 박스로 join을 추정하지 않는다.

## 4. 영향과 검증
W2 라벨, W6 읽기 구성, W8 검증, W4 문법 도구가 공통 API를 쓴다.
인식·평가 지표·사적/Dev/sealed 데이터는 변경하거나 접근하지 않는다.
20개 이상 golden, 30개 이상 무효 사례, join/chord/성부 순서와 0.1 읽기를 시험한다.
세부 증거는 docs/reports/W1/T1.4-LSTL-2026-10-09.md에 기록한다.

## 5. 승인 및 병합 조건
Orchestrator 메시지(2026-10-09)가 A등급 승인이다. 구현이 이 판정과 일치하고
Linux·Windows CI가 통과하면 추가 확인 없이 squash 병합한다.
