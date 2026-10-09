# LSTL 0.1.1 — W1 / CCR-0003

`parse(bytes | str) -> list[LSTLItem]`는 정규 텍스트와 전체 시퀀스를 검증한다.
`serialize(items) -> bytes`는 검증 후 UTF-8/NFC/LF를 쓴다. dots=0은 텍스트에서
생략하고 필수 JSON dots에는 복원한다. 속성 순서는 CONTRACTS 4.1과 같다.

`State()`, `advance(state, item) -> State`, `validate_sequence(items) -> State`를
W6/W8/W4가 공유한다. State.column은 0부터 시작하며 빈 시퀀스는 -1이다.
chord/join이 열 소속을 표현하므로 외부 열 문맥이 필요 없다.
StaffLattice.Hypothesis도 같은 시퀀스 검증기를 호출한다.
오류는 LSTLError(ValueError).code 또는 항목 Pydantic ValidationError다.

`allowed(state)`는 다음 항목의 **JSON Schema 마스크 목록(합집합)**이다.
각 마스크의 properties/required로 허용 속성·값을 얻는다. 새 열, 화음 계속,
다른 성부 계속을 별도 마스크로 제공해 v/dur/dots/grace 상관 제약을 보존한다.
완성 후보에는 항상 항목 검증과 advance를 적용한다. JSON Schema의 integer는
1.0도 정수로 보므로 Python StrictInt 경계까지 대체하지 않는다.

`normalize(list[PrintedItem(item, span_u)])`는 chord/join으로 이미 표시된 열
단위를 인쇄 범위 순서로 정렬한다. 열 내부는 승인된 성부/pos 순서를 충족해야 한다.
W2/W6가 열 소속을 먼저 표시한다. 정규화기는 x 겹침에서 같은 음악 시점을
추정하거나 chord/join을 생성하지 않는다. C3의 유일한 위상 정렬만 허용한다.
disjoint 범위는 x 우선, 겹치는 비시간 열은 CONTRACTS 4.2 관례를 적용한다.
관례 없는 겹침(예: bar와 segno)은 AMBIGUOUS_COLUMN_ORDER다.
courtesy는 마지막 bar 이후의 꼬리만 허용한다. tie/slur의 시스템 간 연결은
이 문법만으로 닫힘을 강제하지 않는다.

`lstl-0.1.1-vocab.json`의 heads 배열 인덱스가 각 헤드의 정수 ID다.
sha256은 heads를 sort_keys=True, separators=(',', ':')인 UTF-8 JSON으로
직렬화한 해시다. 생성/점검: `python scripts/generate_lstl_vocab.py [--check]`.
numbers 헤드만 CONTRACTS 4.4의 1–4 ending 비트마스크(1..15)를 쓴다.
텍스트/IR numbers는 JSON 양의 정수 목록이며 이 헤드 표현으로 제한하지 않는다.

0.1 문서도 읽는다. IR 입력 버전은 보존하고 새 생산자는 clavis-ir-0.1.1을 쓴다.
출력 evidence/hints/confidence/report/runtime 버전은 변경하지 않았다.
규칙: configs/contracts/rules.yaml. 합성 fixture: tests/fixtures/lstl/.
