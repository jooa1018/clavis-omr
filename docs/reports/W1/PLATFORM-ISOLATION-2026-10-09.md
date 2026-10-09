# [W1] 실행기 시험 격리와 동시 슬롯 반복 — 2026-10-09
판정: PARTIAL — 동시 슬롯 20회·전체 Windows PASS, 두 OS CI 대기

## 1. 요약
공유 time 모듈 패치를 제거하고 preflight에 시험별 Clock과 host sampler를 주입한다.
Windows redirector 대신 handshake가 알려 준 실제 잠금 소유 프로세스를 종료·회수한다.
자식 실패 이유·종료 코드·비식별 stderr를 assertion에 기록하고 실제 3슬롯 부하 시험을 제공한다.

## 2. 변경
training/jobs/benchmark_monitor.py, bootstrap/sitecustomize.py, runner.py; tests/platform/{conftest,test_benchmark,test_short_slots,load_companion}.py; scripts/stress_platform.py.
모든 시험 임시 폴더는 pytest tmp_path 또는 실행별 UUID 하위다. 스트레스 실행마다 20라운드, 각 라운드 두 CPU 부하 작업이 ready를 알린 뒤 세 번째 슬롯에서 tests/platform을 실행한다. 끝날 때까지 두 작업이 살아 있었는지 확인한다.

## 3. 계약·결정
Orchestrator 2026-10-09 불안정 시험 수정·20회 부하 검증 지시. COMMON 10절에 벽시계 단언 금지 문안 추가.
벤치마크 기준·스레드/RAM/시간 상한·슬롯 수 변경 없음. [W4 확인](https://github.com/jooa1018/clavis-omr/pull/60#issuecomment-6076938635)에 따라 stale benchmark_monitor.py 예외를 삭제하고 runner의 동일 digest 좌표만 갱신했다.
**탐지 한계**: clock.monotonic()은 여전히 시각 의존 운영 제어다. 스캐너가 주입 객체/함수 간 시각을 추적하지 못하며, 예외 삭제는 시각 의존성 제거를 뜻하지 않는다. 승인 범위·수동 predicate digest는 W4 T4.9-clock-h9-review 보고서에 보존했다.

## 4. 검증
초기 관련 시험 37 passed, 실패/skip 0. 세 슬롯이 모두 비지 않은 첫 스트레스 시도는 not-started로 종료했다.
재현 명령: python -m scripts.stress_platform. 실제 머신 3슬롯을 취득하며 각 작업은 기존 execute의 2스레드/RAM 3 GB/600초 한도를 적용한다.
실행 소스 11200553278ef4784d073292588f81d3911e3230에서 20/20회 PASS: 168개 × 20 = 3360 tests, failures/errors/skipped 모두 0. 모든 라운드에서 두 companion이 시험 끝까지 실행되고 성공 종료했다. 최소 companion CPU 표본 합계는 1.609375초였다. JSON에 20개 라운드의 상태·CPU·RSS·예외 표본을 기록한다.
ruff/format, mypy 93파일, H1–H9 AST, 런타임 라이선스 14개, import 경계 2개 PASS. 전체 Windows 1485 passed, failures/errors/skipped 0; JUnit 217.336초, 슬롯 221.203초, CPU 182.078125초, peak RSS 323035136 bytes. overall/platform/eval/jobs ≥80% 모두 PASS; 계약 298개, 무결성 양성·음성 24개 PASS.
전체 명령: `python -m training.jobs.short run pytest tests/ --cov=clavis --cov=scripts --cov=eval --cov=training.jobs --cov-report=json:work/isolation-coverage.json --junitxml=work/isolation-tests.xml`. 두 OS CI 대기.

## 5. 지표
Windows REF-LAPTOP RAM 24 GB(16+8 GB DDR4-3200 듀얼 채널). 합성 CPU 활동과 플랫폼 단위 시험만 실행한다.
실제 성능 판정/Dev/SYN-Val/sealed/학습·렌더·GPU·유료 컴퓨트 NOT_RUN 또는 0.
두 companion은 각 2개 스레드로 합성 바이트 hash와 협력 대기를 반복한다. 실제 CPU 활동이 있는 동시 슬롯 검증이며 최대 CPU 포화 시험은 아니다. 반복 결과의 실패·오류·skip을 모두 기록하며 실패 라운드를 버리지 않는다.

## 6. 일반화
인식 결과·데이터 선별·평가기 지표 변경 없음. 인식 실패 계열/ablation 해당 없음.
stderr 원문은 로컬 임시 파일에만 두며 assertion은 저장소/사용자 경로를 치환한다.

## 7. 한계와 실패
시각 단위 시험은 실제 sleep을 실행하지 않는다. OS 프로세스 시험은 ready/stop/종료 handshake로 동기화하며 timeout은 고장 종료 안전망이다.
스케줄러 실제 등록은 하지 않는다. 야간 기능은 선행 PR #59에서 별도 병합했다.

## 8. 다음 단계
W4 H9 확인·실제 동시 부하 20회 실패 0을 완료했다. 전체 Windows 검증도 완료했다. 두 OS CI 통과 후 병합한다.
보고서 JSON에 각 라운드와 두 companion 상태를 남긴다.
