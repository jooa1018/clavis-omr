# [W8] cold XSD 시험 진단·동시 부하 재현 — 2026-10-09
판정: PASS — 동시 부하 10/10 및 진단 수정 후 전체 Windows 검증

## 1. 요약 (3줄 이내)
W4가 보고한 cold XSD 자식 종료 실패의 진단을 보강했다. 기존 시험에는 적재 시간 단언이 없었다.
단위 시험은 네트워크 접근 차단, XSD 검증과 재파싱을 거친 출력 일치만 확인한다.
두 CPU 부하 슬롯과 함께 새 프로세스에서 10회 반복하는 명시적 재현 도구를 추가했다.

## 2. 변경 (PR 링크, 주요 파일·모듈)
`tests/export/test_musicxml.py`: 실패 시 종료 코드(십진수/16진수), 진행 단계, stdout/stderr를 assertion에 남긴다.
pytest가 원본 프로세스 표현을 덧붙이지 않도록 정리된 메시지로 명시적 AssertionError를 발생시킨다.
네트워크 차단을 import 이전에 설치하고, 호출이 내부에서 삼켜져도 접근 시도 기록으로 실패한다.
대상 시험의 cache miss 수 단언은 제외했다. 프로세스당 1회 적재 계약은 별도 기존 시험이 계속 확인한다.
`tests/export/cold_schema_stress.py`: W1 슬롯 API로 CPU 부하 2개와 시험 1개를 실행한다.
각 부하에는 SHA-256 반복 스레드 2개가 있다. 10회 각각 새 pytest와 새 XSD 자식을 시작한다.
재시도나 실패 무시는 없으며 종료 후 두 부하를 정리한다. 실행 구간·슬롯·CPU 표본·실패를 보존한다.
이전 직접 실행 예외 종료 보고서도 포함한다. 런타임·의존성·W1 실행기 변경은 없다.

## 3. 계약·결정 (사용한 계약 버전, CCR·ADR 번호)
Orchestrator 2026-10-09 요청: 단위 시험의 시간 판정 금지, 실패 이유 표시, 다른 슬롯 2개와 10회 검증.
CONTRACTS 8절의 실행 중 XSD·재파싱 조건, CCR-0003 계약 버전은 그대로다. 새 CCR/ADR 없음.
적재 시간은 보고/벤치마크에서만 측정한다. 이 동시 부하 실행은 지연 예산 판정에 쓰지 않는다.

## 4. 검증 (테스트 수, CI 결과, 결정성, 스캐너, 라이선스 스캔)
실패 진단 회귀 시험은 합성 자식 실패를 주입해 코드·원인·단계가 남고 로컬 경로가 제거됨을 확인한다.
동시 부하 명령:
```text
uv run --locked --all-groups python -m tests.export.cold_schema_stress coordinate --out work/w8-cold-stress-01
```
조정 프로세스는 입장·대기만 하며 실제 부하·pytest는 모두 W1 `run_short`로 제한한다.
초기 입장은 슬롯 부족으로 NOT_RUN이었다. 슬롯 설정을 바꾸거나 다른 실행을 종료하지 않았다.
반복 10/10 PASS, 실패·오류·skip 0. 모든 회차가 두 CPU 부하의 실행 구간과 겹쳤다.
세 슬롯(0/1 부하, 2 시험) 모두 succeeded/completed. 실패 진단 회귀 시험도 1 PASS.
ruff check/format, mypy(90 source files), import-linter(2 contracts), 런타임 라이선스, AST 검사 PASS.
전체 Windows 명령:
```text
uv run --locked --all-groups python -m training.jobs.short run pytest tests/ --cov=clavis --cov=scripts --cov=eval --cov=training.jobs --cov-report=json:work/w8-cold-full-coverage.json --junitxml=work/w8-cold-full-tests.xml
```
첫 전체 1476 PASS, 실패·오류·skip 0, pytest 101.904초. 슬롯 succeeded/completed, wall 103.703초.
진단 수정 후 최종 전체도 1476 PASS, 실패·오류·skip 0, pytest 230.134초, 슬롯 wall 236.5초.
같은 명령에서 산출 경로만 `work/w8-cold-final-coverage.json`, `work/w8-cold-final-tests.xml`로 구분했다.
전체 coverage 93.82062146892656%, overall/platform/eval/jobs 네 게이트 PASS.
필수 contracts 298 / integrity-positive-negative 24 PASS. 개인정보 검사도 PASS.
[PR #61](https://github.com/jooa1018/clavis-omr/pull/61) 첫 CI: Windows PASS, Linux FAIL(아래 원인·수정).
첫 CI 증거는 `COLD-SCHEMA-ci-first-2026-10-09.json`. 최종 두 OS CI는 수정 push 후 PR 검사/본문에 기록한다.

## 5. 지표 (평가기 JSON 경로 + 핵심 수치 표)
합성 자동 기능 시험, REF-LAPTOP Windows, RAM 24 GB(16+8 GB, DDR4-3200 듀얼 채널).
SYN-Val 아님. Dev/sealed/실사·인식 KPI·95% CI·학습·렌더·정식 지연 벤치마크 NOT_RUN.
GPU·유료 컴퓨트 사용 없음. 시간·CPU/RSS는 실행 비용만 보고하며 통과 임계값으로 쓰지 않는다.
기능 스트레스 증거: `COLD-SCHEMA-stress-2026-10-09.json`(슬롯 실행기·JUnit 산출값).
전체 시험 증거: `COLD-SCHEMA-full-2026-10-09.json`. 전체 슬롯 CPU 표본 85.59375초, peak RSS 315985920 bytes.
최종 전체: `COLD-SCHEMA-final-2026-10-09.json`, CPU 표본 184.6875초, peak RSS 309133312 bytes.
시험 슬롯 wall 184.640초 / CPU 표본 74.328125초 / peak RSS 297082880 bytes.
부하 슬롯 wall 186.703/186.718초, CPU 표본 112.28125/112.484375초.
각 부하의 두 연산 스레드 모두 반복 횟수 >0. 시험 슬롯의 종료된 자식 표본 16건은 W1이 건너뛰었다.
이는 monitor-error나 시험 skip이 아니다. 원시 항목은 증거에 보존한다.

## 6. 일반화 점검 (헌장 8절 체크리스트)
입력 식별자 분기, 인식 규칙·상수·평가기·정답 변경이 없다. 규칙 레지스트리·ablation은 해당 없음.
일반 프로세스 실패를 합성 주입하므로 특정 악보/이미지에 의존하지 않는다. 음악 실패 패턴 패키지는 해당 없음.
스케일·회전·곡에 무관한 시험 진단 변경이며 런타임은 sealed/평가기/Dev 목록을 참조하지 않는다.
원시 JUnit은 로컬 무시 경로에만 남기고, 커밋하는 증거에는 사용자명·호스트명·절대 경로를 넣지 않는다.

## 7. 알려진 한계와 실패 사례 (숨기지 말 것)
W4 최종 전체 실행의 자식 종료 `3221227274 (0xC000070A)`는 원인 미확정이다.
시간 단언 실패였다는 증거는 없으며 이번 진단 보강이 그 OS 종료 원인을 고쳤다고 주장하지 않는다.
10회 통과는 이번 합성 부하 조건의 관찰 결과다. 모든 Windows 실행에서의 무결함을 증명하지 않는다.
첫 Linux CI에서 새 진단 회귀 시험이 FAIL했다. pytest가 assertion 뒤에 원본 CompletedProcess를
자동 첨부해 로컬 경로가 다시 나타났다. 명시적 AssertionError로 고쳐 해당 회귀 시험 1 PASS를 확인했다.
첫 cold 기능 시험 자체는 두 OS CI에서 PASS였다. 첫 CI 실패도 별도 증거로 보존했다.
이후 수정은 실패 메시지를 던지는 방식뿐이며 XSD 자식 코드와 성공 조건은 같아 최초 10회 증거를 유지한다.
수정본 전체 실행의 초기 입장도 슬롯 점유로 NOT_RUN이었다. 빈 슬롯이 생긴 뒤 같은 래퍼로 실행했다.

## 8. 다음 단계 / 필요한 결정 / 블로커
반복·전체 결과를 보존했다. 종료된 직접 실행 예외는 사용하지 않았다.
수정본 전체 시험과 두 OS CI 통과 시 B등급 squash 병합한다. 추가 설계 판정 요청 없음.
같은 자식 종료가 재발하면 새 assertion의 종료 코드·단계·원문 오류를 보존해 W1과 공동 진단한다.
