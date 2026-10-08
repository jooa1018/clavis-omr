# [W1] 공개 저장소 PR 두 OS CI 복구 — 2026-10-09
판정: PARTIAL — 로컬 PASS, 원격 두 OS 검증 대기

## 1. 요약 (3줄 이내)
사용자의 공개 전환 완료 통보에 따라 일반 PR의 Linux·Windows 검사를 복구했다.
draft 제외와 문서 전용 경량 검사, 읽기 전용 권한을 유지한다.
main push의 Linux 및 변경된 main 일일 예약/수동 실행의 Windows 정책은 유지한다.

## 2. 변경 (PR 링크, 주요 파일·모듈)
브랜치 w1/public-pr-ci. scripts/ci_plan.py의 PR 경로별 Windows 제한을 제거했다.
tests/platform/test_ci_budget.py에서 일반 코드·혼합 변경·빈 파일 목록과 보안 설정을 검증한다.
COMMON10, scripts/README.md, configs/platform/rules.yaml(PLATFORM-CI-001)에 정책을 기록했다.

## 3. 계약·결정 (사용한 계약 버전, CCR·ADR 번호)
Orchestrator 2026-10-09 A등급 승인 및 사용자 공개 전환 완료 통보.
GitHub visibility PUBLIC 확인. 계약 v0.1 변경 없음, 신규 CCR/ADR 없음.
워크플로 contents: read, pull-requests: read, actions: read 유지. pull_request_target 미사용.

## 4. 검증 (테스트 수, CI 결과, 결정성, 스캐너, 라이선스 스캔)
라우팅·커버리지 게이트·워크플로 권한 시험 25 passed. ruff/format/mypy(65개 파일) PASS.
Windows 전체 시험 명령: python -m training.jobs --root work/public-ci-validation run --manual.
큐 작업: pytest tests/ --junitxml=work/public-ci-tests.xml. threads=2, RAM 상한 3 GB, 벽시계 상한 600초.
Windows 전체 621 passed, 실패/skip 0, 62.364초. H1–H9 AST 및 개인정보 검사 PASS. 원격 두 OS 결과 대기.

## 5. 지표 (평가기 JSON 경로 + 핵심 수치 표: 이전 대비 변화와 95% CI, 슬라이스별)
PUBLIC-PR-CI-2026-10-09.json에 비식별 검증 집계를 저장한다.
큐 벽시계 64.797초, CPU 54.75초, peak RSS 226537472 bytes.
로컬 REF-LAPTOP: RAM 24 GB(16+8), DDR4-3200 듀얼 채널, CPU만 사용.
합성 자동 시험. Dev/sealed/실사/학습/인식 평가와 95% CI는 NOT_RUN(범위 밖).

## 6. 일반화 점검 (헌장 8절 체크리스트, 실패 패턴 패키지 첨부 여부)
음악 입력, 식별 정보, 기하 상수, 임계값, 평가기 변경 없음.
운영 규칙 PLATFORM-CI-001 등록. 인식 ablation/실패 패턴 패키지는 해당 없음.
사적 데이터·sealed를 읽거나 CI로 전송하지 않는다. 영상 크기·회전·곡에 의존하지 않는다.

## 7. 알려진 한계와 실패 사례 (숨기지 말 것)
문서 전용 PR은 전체 pytest를 실행하지 않으며 UTF-8/JSON/whitespace/개인정보 경량 검사를 수행한다.
기존 draft PR은 준비 완료로 전환해야 실행된다. 과거 PR의 완료된 검사 기록은 소급 변경하지 않는다.
공개 PR에서도 인식 실사 평가는 수행하지 않는다.

## 8. 다음 단계 / 필요한 결정 / 블로커
승인된 범위이며 두 OS CI 통과 후 squash 병합한다.
후속 우선순위는 #29 → xmlschema → OR-005 → RAM 문서 → T1.4다.
