# [W1] 실행기 표본 오류와 체크포인트 동기화 — 2026-10-09

## 1. 요약
자식 표본 실패 때문에 전체 작업을 중단하지 않는다. 예외 종류·정적 발생 지점·횟수를 기록한다.
일시 중지 시험은 첫 체크포인트에서 stop 이벤트를 기다려 시작 지연과 독립적이다.
판정: 로컬 PASS, 두 OS CI 대기. 벤치마크 모드는 별도 후속 PR이다.

## 2. 변경
[PR #48](https://github.com/jooa1018/clavis-omr/pull/48): `training/jobs/monitor.py`, `runner.py`, `short.py`, `tests/platform/`.
기준 main: 358fdd22b91be2fb9ad12c57057b4ecfdf56d97c.
표본의 memory_info·num_threads·cpu_times 중 하나라도 실패하면 해당 자식 표본 전체를 버린다.
이미 관찰한 누적 CPU는 보존한다. 루트/열거 오류는 계속 실패시키며 종료 단계 오류도 기록한다.

## 3. 계약·결정
Orchestrator 2026-10-09 실행기 수정 지시. 외부 엔진 계약 변경 없음.
기존 승인 H9 두 건은 AST digest가 동일한지 검사하고 줄 번호만 갱신했다. 신규 예외 없음.
PLATFORM-MONITOR-001에 운영 규칙 등록. 벤치마크 판정은 별도 작업으로 보존한다.

## 4. 검증
관련 단위 시험 43 passed (24.69초). ruff/format, mypy 86파일, import 경계, runtime 라이선스 14개 PASS.
H1–H9 PASS, 새 발견 0. Windows 전체 1428 passed, 실패/오류/skip 0. 전체/platform/eval/jobs 커버리지 및 필수 시험 PASS. 두 OS CI 대기.
W8 재현 명령(동일 pytest 인수, 설치된 잠금 환경 사용):
```text
python -m training.jobs.short run pytest tests/ --cov=clavis --cov=scripts --cov=eval --cov=training.jobs --cov-report=json:work/w8-full-coverage.json --junitxml=work/w8-full-tests.xml
```
NoSuchProcess/AccessDenied/ZombieProcess를 각 표본 단계에 주입해 재현한다. 루트 오류는 실패하는 음성 시험도 있다.
W8 과거 215.203초 실패는 예외 정보가 없으므로 그 실행의 정확한 예외를 소급 확정하지 않는다.

## 5. 지표
Windows REF-LAPTOP RAM 24 GB(16+8 GB DDR4-3200 듀얼 채널), 슬롯 2 연산 스레드, 작업 RAM 3 GB.
전체 실행 집계는 동명 JSON에 기록했다. 슬롯 228.062초, CPU 164.219초, peak RSS 319565824 bytes. 실제 자식 종료 경합 29건을 건너뛰고 전체 시험이 완료됐다. 원시 JUnit은 공개하지 않는다.
인식/Dev/sealed 지표 NOT_RUN. GPU·학습·렌더·유료 컴퓨트 0.

## 6. 일반화
실행기 운영 변경이며 인식 출력·상수·데이터 선별을 바꾸지 않는다.
일반화 패키지·인식 ablation·SYN-Val/Dev 비교는 해당 없음. 사적 데이터 접근 없음.

## 7. 한계와 실패
표본을 놓친 자식의 실제 CPU/RSS는 추정하지 않는다. 건너뛴 횟수를 공개해 표본 한계를 드러낸다.
진단은 예외 메시지/traceback/사용자·호스트·경로·PID를 포함하지 않는다.
체크포인트 시험의 벽시계 상한은 실패 종료 안전망이며 정상 동기화 조건은 파일 이벤트다.

## 8. 다음 단계
두 OS CI 통과 후 squash 병합, 사용자에게 W5·W8의 슬롯 복귀 전달을 요청한다.
다음은 승인된 벤치마크 전용 독점 작업·외부 부하 검사 구현이다.
