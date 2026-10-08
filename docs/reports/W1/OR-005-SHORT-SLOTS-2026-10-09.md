# [W1] OR-005 짧은 실행 슬롯 — 2026-10-09
판정: PARTIAL — 로컬 Windows PASS, 두 OS CI 대기

## 1. 요약 (3줄 이내)
기본 3개의 머신 공통 짧은 실행 슬롯을 구현했다. 스레드 요청 2, RAM 최대 3 GB, 벽시계 최대 600초다.
기존 큐의 worker.lock을 공유 잠금으로 사용하고 슬롯별 독점 잠금을 추가해 무거운 큐와 상호 배제한다.
워커 전달 명령: uv run --locked --all-groups python -m training.jobs.short run pytest tests/

## 2. 변경 (PR 링크, 주요 파일·모듈)
브랜치 w1/short-run-slots. training/jobs/{short,slots}.py, tests/platform/test_short_slots.py.
COMMON10과 training/jobs/README.md, 규칙 PLATFORM-SHORT-001. PR38 최종 CI·병합 기록도 갱신했다.

## 3. 계약·결정 (사용한 계약 버전, CCR·ADR 번호)
Orchestrator 2026-10-06 OR-005 승인 및 2026-10-09 우선순위 확인. 계약 v0.1 변경 없음.
ADR-002의 머신 공통 잠금을 그대로 재사용하며, Windows 공유 잠금은
[LockFileEx](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-lockfileex), Linux는 flock이다.
설정은 ~/.clavis/short-slots.json이며 큐/슬롯이 모두 비었을 때만 변경한다.

## 4. 검증 (테스트 수, CI 결과, 결정성, 스캐너, 라이선스 스캔)
명령: python -m training.jobs.short run pytest tests/ --cov=clavis --cov=scripts --cov=eval
--cov=training.jobs --cov-report=json:work/slots-coverage.json --junitxml=work/slots-tests.xml.
새 래퍼로 Windows 전체 636 passed, 실패/skip 0, 56.140초. 새 시험 12개.
3슬롯·설정 1/4개·초과 요청·무거운 큐 상호 배제·다른 프로세스 crash 후 재사용·예외 후 해제·CLI 상태를 검증했다.
실제 작은 합성 작업으로 기존 큐의 스레드/RAM/시간 요청과 실행 성공을 확인했다.
커버리지: short.py 98.18%, slots.py 93.33%, 독립 4개 게이트 PASS. ruff/format/mypy68/H1–H9/개인정보 PASS.
기존 runner.py를 수정하지 않았고 H9 예외 추가 0. 원격 CI는 대기 중.

## 5. 지표 (평가기 JSON 경로 + 핵심 수치 표: 이전 대비 변화와 95% CI, 슬라이스별)
[OR-005-SHORT-SLOTS-2026-10-09.json](OR-005-SHORT-SLOTS-2026-10-09.json)에 측정 집계를 기록했다.
벽시계 58.110초, CPU 47.140625초, peak RSS 305373184 bytes, 실제 CPU 상한 2.
로컬 RAM 24 GB(16+8), DDR4-3200 듀얼 채널. 합성 자동 시험. Dev/sealed/실사/학습/인식 평가/95% CI NOT_RUN.

## 6. 일반화 점검 (헌장 8절 체크리스트, 실패 패턴 패키지 첨부 여부)
음악 인식·데이터 생성·임계값·입력 식별 규칙 변경 없음. 자원 정책만 등록했다.
사적 입력 접근/원문 출력 저장 없음. 인식 ablation과 음악 실패 패키지는 해당 없음.

## 7. 알려진 한계와 실패 사례 (숨기지 말 것)
슬롯이 없으면 시작 전에 75로 종료한다. 기다림/FIFO 우선순위는 없으며 여유가 생긴 뒤 다시 실행한다.
이미지 수는 호출자 선언(--items)을 검증한다. 실제 처리량은 모듈이 제한해야 한다.
원문 stdout/stderr는 기존 큐와 같이 보관하지 않는다. 상세 시험 결과는 무시된 work/에 JUnit을 지정한다.
status는 설정 수만 표시한다. Ctrl+C로 현재 작업을 중단할 수 있다. 임의 daemon·주입 우회는 기존 큐와 같이 지원하지 않는다.
기존 CPU 선택 정책을 재사용하므로 슬롯 간 CPU 집합이 겹칠 수 있다.

## 8. 다음 단계 / 필요한 결정 / 블로커
두 OS CI 후 승인된 범위를 squash 병합한다. 다음은 RAM 문서/PLAN 원칙 갱신 후 T1.4다.
