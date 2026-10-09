# [W1] 실행기 시험 격리와 동시 슬롯 반복 — 2026-10-09
판정: PARTIAL — 20회 반복 및 전체 검증 진행 중

## 1. 요약
공유 time 모듈 패치를 제거하고 preflight에 시험별 Clock과 host sampler를 주입한다.
Windows redirector 대신 handshake가 알려 준 실제 잠금 소유 프로세스를 종료·회수한다.
자식 실패 이유·종료 코드·비식별 stderr를 assertion에 기록하고 실제 3슬롯 부하 시험을 제공한다.

## 2. 변경
training/jobs/benchmark_monitor.py, bootstrap/sitecustomize.py, runner.py; tests/platform/{conftest,test_benchmark,test_short_slots,load_companion}.py; scripts/stress_platform.py.
모든 시험 임시 폴더는 pytest tmp_path 또는 실행별 UUID 하위다. 스트레스 실행마다 20라운드, 각 라운드 두 CPU 부하 작업이 ready를 알린 뒤 세 번째 슬롯에서 tests/platform을 실행한다. 끝날 때까지 두 작업이 살아 있었는지 확인한다.

## 3. 계약·결정
Orchestrator 2026-10-09 불안정 시험 수정·20회 부하 검증 지시. COMMON 10절에 벽시계 단언 금지 문안 추가.
벤치마크 기준·스레드/RAM/시간 상한·슬롯 수 변경 없음. H9는 W4의 시계 주입 전환 확인을 받아 정리한다.

## 4. 검증
초기 관련 시험 37 passed, 실패/skip 0. 세 슬롯이 모두 비지 않은 첫 스트레스 시도는 not-started로 종료했다.
재현 명령: python -m scripts.stress_platform. 실제 머신 3슬롯을 취득하며 각 작업은 기존 execute의 2스레드/RAM 3 GB/600초 한도를 적용한다.
20회·전체 Windows·두 OS CI·무결성 결과는 후속 기록한다.

## 5. 지표
Windows REF-LAPTOP RAM 24 GB(16+8 GB DDR4-3200 듀얼 채널). 합성 CPU 활동과 플랫폼 단위 시험만 실행한다.
실제 성능 판정/Dev/SYN-Val/sealed/학습·렌더·GPU·유료 컴퓨트 NOT_RUN 또는 0.
반복 결과의 실패·오류·skip을 모두 기록하며 실패 라운드를 버리지 않는다.

## 6. 일반화
인식 결과·데이터 선별·평가기 지표 변경 없음. 인식 실패 계열/ablation 해당 없음.
stderr 원문은 로컬 임시 파일에만 두며 assertion은 저장소/사용자 경로를 치환한다.

## 7. 한계와 실패
시각 단위 시험은 실제 sleep을 실행하지 않는다. OS 프로세스 시험은 ready/stop/종료 handshake로 동기화하며 timeout은 고장 종료 안전망이다.
스케줄러 실제 등록은 하지 않는다. 야간 기능은 선행 PR #59에서 별도 병합했다.

## 8. 다음 단계
W4 H9 확인·실제 동시 부하 20회 실패 0·전체 Windows·두 OS CI 통과 후 병합한다.
보고서 JSON에 각 라운드와 두 companion 상태를 남긴다.
