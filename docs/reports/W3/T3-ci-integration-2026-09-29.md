# [W3] T3 CI 통합 보고 — 2026-09-29
판정: PARTIAL (원격 CI 확인 전)

## 1. 요약 (3줄 이내)
W1 PR #7과 최신 origin/main을 W3 브랜치에 merge했다.
중복 requirements.txt를 삭제하고 training 그룹/uv.lock으로 통합했다.
W3 테스트의 importorskip을 제거하여 의존성 누락 시 수집 실패로 드러나게 했다.

## 2. 변경 (PR 링크, 주요 파일·모듈)
https://github.com/jooa1018/clavis-omr/pull/6
W3 requirements 삭제, README 실행 절차, tests/degrade/test_ops.py의 직접 import.
원본 worktree의 브랜치는 변경하지 않았다. W1 소유 CI/pyproject는 merge로만 반영했다.

## 3. 계약·결정 (사용한 계약 버전, CCR·ADR 번호)
CONTRACTS 2절 유지. CCR/ADR/공개 계약 변경 없음.
Orchestrator OR-002: W4 스캐너 NOT_RUN을 기록하고 B등급 병합 가능.

## 4. 검증 (테스트 수, CI 결과, 결정성, 스캐너, 라이선스 스캔)
로컬 Windows CPU, 자동 합성 테스트 44 PASS, W3 coverage 97.36842105263158%.
ruff/format/W3 strict mypy PASS. 동일 시드/1·4스레드/replay 시험 포함.
원격 Linux/Windows CI의 W3 실제 실행 결과는 확인 후 아래에 기록한다.
W4 무결성 스캐너 NOT_RUN(OR-002), 계약 fixture 미구현 NOT_RUN.
의존성 버전 변경 없음; W1 승인 그룹 사용. 런타임 license 검사는 CI에서 유지된다.

## 5. 지표 (평가기 JSON 경로 + 핵심 수치 표: 이전 대비 변화와 95% CI, 슬라이스별)
인식 경로/기하 연산 변경 없음. 기존 validation.json은 첫 코드 실행의 역사적 근거다.
이번 작업은 자동 합성 시험과 CI 연결만 검증했다. Dev/SYN-Val/실사/sealed 지표 및 95% CI는 비해당.

## 6. 일반화 점검 (헌장 8절 체크리스트, 실패 패턴 패키지 첨부 여부)
식별 정보 분기, 상수, 인식 규칙, 실사 픽셀 사용 없음. 계약/평가기 변경 없음.
기존 합성 property/격자/재현성 시험 유지. 실패 패턴 패키지는 비해당.

## 7. 알려진 한계와 실패 사례 (숨기지 말 것)
W4 스캐너와 계약 fixture는 미구현이며 전체 G0/G1 통과 선언이 아니다.
첫 보고서의 W3 CI 부재와 draft 유지 제한은 이 후속 검증 완료 시 해소된다.

## 8. 다음 단계 / 필요한 결정 / 블로커
두 OS에서 W3 44개 실제 통과를 확인한 후 draft를 해제하고 B등급 squash 병합한다.
이후 별도 w3 브랜치/PR에서 8계열 연산과 촬영 경로 프리셋을 구현한다.
