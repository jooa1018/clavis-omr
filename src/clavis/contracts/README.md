# 계약 패키지 v0.1 — W1

정본: `docs/CONTRACTS.md`, 승인 CCR-0001. 이 패키지는 관측값의 구조·범위·참조를
검사한다. 인식, 음악 복원, 보정, 코드 문자열 파싱, 좌표 역변환은 구현하지 않는다.

## 사용

```python
from pathlib import Path
from clavis.contracts import PageLayout, ScoreIR, canonical_json

root = Path("tests/fixtures/contracts/valid")
layout = PageLayout.model_validate_json((root / "layout.json").read_bytes())
score = ScoreIR.model_validate_json((root / "score.json").read_bytes())
assert len(layout.systems) == 3
assert len(score.measures) == 6
payload = canonical_json(score)  # UTF-8 bytes, 정렬된 키, LF
```

독립 문서 12종은 `DOCUMENT_MODELS`에 등록되어 있다. Python 속성은 snake_case,
wire 이름은 camelCase이며 schema 상수는 `schema_version` 속성으로 읽는다.
`Fraction`, `Pitch`, `TempoValue`, `ChordParseResult`, `Event`, `Harmony`, `ReviewHint`도
공개한다. 하위 구조는 common/geometry/tokens/symbols/text/score/outputs 모듈에 있다.

JSON Schema는 구조·열거형·범위를 검사한다. 기약분수, NFC, 연결된 필드 조건,
중복 ID, 경계/참조 같은 의미 제약은 pydantic 검증도 함께 실행해야 한다.
여러 문서 사이의 참조는 `ContractBundle(...).validate()`로 검사한다.
ContractBundle은 호출자용 Python 문맥이며 추가 wire envelope가 아니다.
구성 예시는 `tests/contracts/test_schemas.py`의 `bundle()`을 참고한다.

정규 작성기는 객체 목록의 순서를 보존한다. 읽기 순서·rank와 문맥 기반 힌트 정렬은
생산자가 계약대로 제공한다. 문맥 없는 힌트 작성기는 배열을 재정렬하지 않는다.
SymbolGraph 실수는 2자리, 다른 IR 실수는 3자리 round-half-even으로 기록하므로
더 정밀한 입력은 기록 시 양자화된다. 외부 좌표는 정수 그대로 기록한다.

## 갱신과 검증

```text
uv run --all-groups python scripts/generate_schemas.py
uv run --all-groups python scripts/generate_schemas.py --check
uv run --all-groups pytest tests/contracts
```

첫 승인 완성본은 v0.1로 동결한다. 이후 변경은 CCR과 계약 0절의 버전 규칙을 따른다.
LSTL의 항목 타입은 lattice payload 때문에 제공하지만 정규화기·텍스트 파서·문법
오토마톤·정수 어휘는 T1.4다. MusicXML 생성/XSD/재파싱은 W8 범위다.
구조 검증은 음악을 선택하는 조립·판정 규칙이 아니며 카탈로그 ablation 대상이 아니다.
