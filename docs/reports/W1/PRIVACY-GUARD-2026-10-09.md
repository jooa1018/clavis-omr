# [W1] 개인정보 재발 방지 — 2026-10-09
판정: PASS — 로컬 및 원격 두 OS 검증 완료

## 1. 요약 (3줄 이내)
공개 전환 준비 완료. Orchestrator가 과거 프로필 경로와 호스트명 1건을 수용했으며 히스토리는 재작성하지 않는다.
COMMON11에 승인 문안을 그대로 추가하고, 추적 파일 개인정보 검사를 CI 필수 단계로 추가했다.
문서 전용 PR도 경량 검사에서 검사하며, 위반 값 자체는 출력하지 않는다.

## 2. 변경 (PR 링크, 주요 파일·모듈)
[PR #36](https://github.com/jooa1018/clavis-omr/pull/36), 브랜치 w1/privacy-guard. scripts/check_privacy.py, tests/platform/test_privacy.py, CI, COMMON11.
scripts/README.md와 configs/platform/rules.yaml에 사용법·정책 규칙을 등록했다.
PUBLICATION-AUDIT-2026-10-09.md/json은 원래 PARTIAL 검사 사실을 보존하고 공개 준비 승인만 별도로 기록했다.

## 3. 계약·결정 (사용한 계약 버전, CCR·ADR 번호)
Orchestrator 2026-10-09 A등급 승인. 계약 v0.1 변경 없음. CCR/ADR 신규 없음.
저장소 공개 전환은 사용자가 수행한다. 공개 완료 통보 전 두 OS PR CI 복구는 적용하지 않는다.

## 4. 검증 (테스트 수, CI 결과, 결정성, 스캐너, 라이선스 스캔)
합성 문자열 단위 시험 30 passed: Windows/Linux/macOS 경로, JSON 이스케이프,
문서 자리표시자, JSON/YAML/대입 호스트 필드, 미추적 파일 제외, 미스테이징 변경 포함,
링크·읽기 실패 차단, 출력 비식별화 및 문서/품질 작업의 CI 연결.
ruff, mypy(65개 파일), H1–H9 AST PASS. 전체 Windows 시험은 머신 단일 큐 threads=2로 실행한다.
검증 명령: python -m training.jobs --root work/privacy-validation run --manual.
작업 명령: pytest tests/ --cov=clavis --cov=scripts --cov=eval --cov=training.jobs
--cov-report=json:work/privacy-coverage.json --junitxml=work/privacy-tests.xml.
Windows 전체 618 passed, 실패/skip 0, 93.897초. 전체/platform/eval/jobs 커버리지 80% 게이트 모두 PASS.
import-linter 2개 경계 및 runtime 전이 의존성 5개 라이선스 PASS. 원격 Linux 618 passed(26.45초), Windows 618 passed(40.11초).
[CI 실행 37811209736](https://github.com/jooa1018/clavis-omr/actions/runs/37811209736): 두 OS 및 경량 개인정보 검사 PASS, 추적 파일 456개/발견 0. 검사 스크립트 커버리지 98%.

## 5. 지표 (평가기 JSON 경로 + 핵심 수치 표: 이전 대비 변화와 95% CI, 슬라이스별)
PRIVACY-GUARD-2026-10-09.json에 비식별 검증 집계를 기록한다.
로컬 Windows CPU, RAM 24 GB(16+8), DDR4-3200 듀얼 채널. 작업 RAM 상한 3 GB.
큐 벽시계 97.266초, CPU 83.109375초, peak RSS 236027904 bytes.
합성 자동 시험만 수행한다. Dev/sealed/실사/학습/인식 성능/95% CI는 NOT_RUN(변경 범위 밖).

## 6. 일반화 점검 (헌장 8절 체크리스트, 실패 패턴 패키지 첨부 여부)
특정 실제 사용자명이나 기기 이름을 패턴에 넣지 않는다. OS 프로필 경로와 필드 구조를 검사한다.
엔진·평가기·임계값 변경 없음. 규칙 PLATFORM-PRIVACY-001은 저장소 운영 검사이며 인식 ablation은 해당 없음.
음악 입력 크기·회전·곡에 의존하지 않는다. 사적 입력이나 sealed 데이터에 접근하지 않았다.

## 7. 알려진 한계와 실패 사례 (숨기지 말 것)
현재 추적 파일 검사이며 과거 히스토리·미추적 로컬 로그·GitHub 별도 첨부는 검사하지 않는다.
간단한 텍스트 패턴 검사이므로 모든 개인정보/비밀값이나 난독화·인코딩을 탐지한다고 주장하지 않는다.
검출된 필드 값이 빈 값이나 가짜 값이어도 실패한다. 음성 시험은 문자열을 조립해 실제 위반 literal을 추적 파일에 넣지 않는다.
과거 감사의 알려진 잔존과 범위 한계는 원 감사 보고서에 그대로 남긴다.

## 8. 다음 단계 / 필요한 결정 / 블로커
코드 커밋 79e712c의 두 OS CI가 통과했다. 이 검증 기록 추가 후 최종 CI를 확인하고 squash 병합한다.
사용자의 공개 전환 완료 통보 후 일반 PR에도 두 OS 작업을 복구한다(draft·문서 전용 제외 유지).
그 뒤 기존 우선순위를 따른다. PR #29의 lxml 동봉 LGPL 정적 의존성 검토는 별도 미해결 사항이다.
