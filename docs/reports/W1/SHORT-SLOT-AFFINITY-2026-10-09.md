# [W1] Windows 슬롯 affinity 감시 수정 — 2026-10-09
판정: PASS — Windows 전체 933개 및 Linux·Windows CI 통과

## 1. 요약 (3줄 이내)
승인된 H9 운영 정책의 문서 반영 전 전체 시험이 monitor-error로 반복 중단됐다.
진단에서 runner.py:153의 자식 cpu_affinity 조회가 AccessDenied를 던진 것을 확인했다.
Windows Job Object가 affinity를 강제하는 경우 중복 조회만 생략한다.

## 2. 변경 (PR 링크, 주요 파일·모듈)
training/jobs/runner.py 조건 한 줄, tests/platform/test_jobs.py 회귀 시험 및 이 보고서.
W1 소유 코드의 B등급 수정이다. H9 정책 문서는 별도 승인 PR로 유지한다.
CI·계약·allowlist·의존성은 변경하지 않는다.

## 3. 계약·결정 (사용한 계약 버전, CCR·ADR 번호)
기존 Orchestrator 승인 Windows Job Object CPU/메모리/우선순위/자식 상속 정책을 따른다.
Guard는 AFFINITY 및 PRIORITY_CLASS/JOB_MEMORY/KILL_ON_CLOSE를 OS에 설정하고,
설정이나 편입 실패 시 시작을 중단한다. 성공한 Windows Job handle이 있을 때만
psutil affinity 재조회가 불필요하다. Linux(handle 없음)는 계속 조회·교정한다.
라이브러리 스레드 설정, RSS·CPU 계측, 메모리·디스크·시간·창 감시 및 오류 중단은 유지한다.
새 판정 규칙/상한/예외는 없다. PLATFORM-SHORT-001의 기존 강제 방식 구현 보완이다.

## 4. 검증 (테스트 수, CI 결과, 결정성, 스캐너, 라이선스 스캔)
회귀 시험 2개 PASS: 자식 affinity 조회 AccessDenied 주입, 실제 자식 CPU/환경 상속.
Windows는 kernel guard 아래 작업 성공, Linux는 조회 불가 시 monitor-error로 중단하도록 시험한다.
기존 sample AccessDenied 중단 시험도 전체 시험에 유지한다.
ruff·mypy·H1–H9 AST PASS. 기존 runner H9 예외 두 건의 위치/digest는 그대로다.
OR-005 Windows 전체 933개 PASS, 81.262초. 전체/platform/eval/jobs 커버리지 게이트 PASS.
명령: `python -m training.jobs.short run pytest tests/ --cov=clavis --cov=scripts --cov=eval --cov=training.jobs --cov-report=json:work/affinity-coverage.json --junitxml=work/affinity-tests.xml`.
집계: SHORT-SLOT-AFFINITY-evidence.json. Windows 슬롯 벽시계 83.609초,
CPU 표본 72.921875초, peak RSS 표본 292917248 bytes.

## 5. 지표 (평가기 JSON 경로 + 핵심 수치)
로컬 Windows CPU, RAM 24 GB(16 + 8 GB, DDR4-3200 듀얼 채널).
원래 전체 시험 2회가 각각 69.156초·117.844초에 monitor-error, JUnit 미생성.
별도 진단 실행에서 4.015초에 AccessDenied 위치를 확인했다.
개인 경로·프로세스 명령줄 없이 예외 클래스/함수/줄 번호만 수집했다.
수정 후 전체 시험 첫 시작은 슬롯 사용 중으로 not-started였으며 보호를 우회하지 않았다.
인식 평가·Dev·실사·sealed·SYN-Val·95% CI 모두 NOT_RUN.

## 6. 일반화 점검 (헌장 8절)
특정 악보/이미지/파일 식별 정보 기반 분기 없음. 사적/sealed 미접근.
기존 OS 자원 강제를 사용하며 새 임계값·학습·의존성 없음.
인식 규칙 ablation 해당 없음. 원인 재현은 합성 프로세스 조회 오류 주입이다.

## 7. 알려진 한계와 실패 사례
AccessDenied를 일괄 무시하지 않는다. kernel guard가 없는 환경과 다른 자원 계측
오류는 기존대로 중단한다. 실패한 실행 결과를 시험 PASS로 간주하지 않는다.
회귀 시험의 오류 주입과 실제 OS 자식 상속 검증을 구분한다.

## 8. 다음 단계 / 필요한 결정 / 블로커
두 OS CI PASS: https://github.com/jooa1018/clavis-omr/actions/runs/37893247989
PR #46 squash 병합 완료: 22b546ab48f98c01f871dc5bc1a4ab73ca4c7c26.
이후 보존한 H9 운영 정책 문서 반영을 완료하고 W2 PR #28에 [W1 확인]을 남긴다.
