# [W2] H4 smoke fixture 경로 정리 — 2026-09-29
판정: PARTIAL

## 1. 요약 (3줄 이내)
W4 사전 스캔의 H4 지적을 받아 고정 마디 fixture 작성 코드를 tests/data로 이동했다.
allowlist나 비교식 우회 없이 헌장의 테스트 코드 제외 범위에 맞췄다.
입력 10곡의 XML 바이트를 보존했고 데이터 테스트 35개가 통과했다.

## 2. 변경 (PR 링크, 주요 파일·모듈)
w2/smoke-fixtures: training/data/smoke_inputs.py → tests/data/smoke_inputs.py.
smoke 및 테스트 import, 원천 등록 URL, README 갱신. 테스트 코드 내용 변경 없음.
원본 저장소 브랜치는 변경하지 않았다. CI 확인 후 B등급 squash 병합 대상.

## 3. 계약·결정 (사용한 계약 버전, CCR·ADR 번호)
헌장 H4의 tests 제외를 적용. 계약·상수·생성 분포·allowlist 변경 없음.
최신 origin/main에는 PR #4가 e62be2f로 병합됨을 확인했다.
따라서 T2.5 LSTL 순서 구현의 병합 대기 조건은 해소됨(이 PR은 T2.5 미구현).

## 4. 검증 (테스트 수, CI 결과, 결정성, 스캐너, 라이선스 스캔)
pytest tests/data: 35 passed(8.05초), 실제 외부 Verovio 3폰트 반복 렌더 포함.
ruff/check-format, W2 strict mypy, import 경계 통과. 새 의존성 없음.
W4 실제 H4 재스캔 NOT_RUN: 도구가 main에 없어 W4에 재검사 요청.
CI 결과는 PR checks 참조. 새 생성 로직이 없어 기존 테스트로 검증.

## 5. 지표 (평가기 JSON 경로 + 핵심 수치 표: 이전 대비 변화와 95% CI, 슬라이스별)
smoke-fixture-move-validation.json: 입력 10곡 중 바이트 변경 0건.
Windows REF-LAPTOP CPU, 합성 자동 검사. dev/sealed/실사/학습 미실행.
인식 지표·95% CI 해당 없음. 과거 SVG 감사의 입력 해시가 그대로 유지된다.

## 6. 일반화 점검 (헌장 8절 체크리스트, 실패 패턴 패키지 첨부 여부)
실제 악보·이미지를 읽지 않는다. 고정 fixture 코드를 올바른 테스트 경로에 배치.
스캐너 조건식이나 이름을 바꿔 탐지를 회피하지 않는다. 특정 인식 실패 해당 없음.

## 7. 알려진 한계와 실패 사례 (숨기지 말 것)
smoke 명령은 저장소 테스트 트리를 필요로 하는 개발 감사 도구다.
배포 생산 생성기로 사용하지 않는다. W4 재스캔 전 H4 PASS를 주장하지 않는다.

## 8. 다음 단계 / 필요한 결정 / 블로커
W4 재스캔 요청. 학습 admission 차단 유지. PDMX 집계 관련 생산 블로커는 별도 PR #11.
