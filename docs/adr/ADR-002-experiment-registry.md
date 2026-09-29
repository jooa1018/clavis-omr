# ADR-002 — 노트북 로컬 실험 레지스트리
상태: 초안 — T1.9 구현 검토와 함께 Orchestrator 채택 확인 필요
날짜: 2026-09-29
작성: W1

## 문제와 선택지
RAM 8 GB 노트북의 단일 큐에서 실행 설정·시드·데이터 digest·git SHA·CPU 사용을 남겨야 한다.
MLflow 로컬 파일 저장소와 JSONL을 비교했다. v0에는 서버/UI/추가 대형 의존성 없이 읽을 수 있는 JSONL을 제안한다.

## 제안
큐 상태는 Python 표준 SQLite 트랜잭션에 저장하고 실험 기록은 단일 worker가 JSONL에 append+fsync한다.
머신 전체 OS 파일 잠금으로 worktree 간 실행도 직렬화한다. 저장 위치 기본값은 ~/.clavis/jobs이며 git 밖이다.
시작 시 요청 메타데이터를 기록하고 종료 시 결과·중단 이유·누적 벽시계·표본 CPU/RSS/OS 스레드 수를 기록한다.
API는 Python module+arguments 요청, Context.load/save/stopping의 협조형 체크포인트다. 사적 경로는 CLAVIS_PRIVATE_ROOT 환경 변수만 사용한다.

## 근거·한계
합성 검증·자원 상한·재개 결과는 docs/reports/W1/T1.9-batch-runner.md에 기록한다.
JSONL은 인덱스/대시보드가 없고 비정상 디스크 종료 시 마지막 행이 불완전할 수 있다. 큐 상태 정본은 SQLite다.
CPU/RSS는 100ms 표본이며 짧게 생겼다 사라지는 자식의 CPU 시간은 누락될 수 있다.
Windows Job Object로 메모리 commit/affinity/우선순위/일괄 종료를 강제한다. Linux는 affinity 상속 및 RSS 초과 감시 방식이다.

## 되돌릴 조건
여러 노트북 분산 큐, 동시 worker, 복잡한 조회/UI가 실제로 필요하면 별도 ADR로 MLflow 등을 재검토한다.
현재는 새 큐를 늘려 동시 실행하지 않는다.
