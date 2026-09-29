# [W2] PDMX 집계 실행 준비·착수 — 2026-09-29
판정: PARTIAL

## 1. 요약 (3줄 이내)
Orchestrator 판정으로 T2.2 PDMX 집계를 시작했다. 학습 편입은 아니다.
v9 CSV/MXL 스트리밍, 항목별 권리 필터, 식별자 없는 집계/재개 경로를 구현했다.
OR-004 승인 자원 제한으로 실제 집계 실행 중이며 결과를 아직 주장하지 않는다.

## 2. 변경 (PR 링크, 주요 파일·모듈)
w2/pdmx-aggregate: pdmx_aggregate.py, pdmx_stream.py, pdmx_windows.py,
pdmx-aggregate.json, 원천 등록부, DATA-PDMX-001, 합성 중단·재개 시험.
원본 폴더 브랜치는 변경하지 않고 W2 전용 worktree에서 진행.

## 3. 계약·결정 (사용한 계약 버전, CCR·ADR 번호)
A5/사용자 2026-09-29: W4 필터 전 집계만 허용. no_license_conflict와 PDM/CC0 필수.
OR-004는 이번 한 번만 장시간 로컬 실행 허용. 일반 큐 규칙을 바꾸지 않는다.
OR-003의 보호 집합 v1/receipt digest를 후속 학습 manifest에 남긴다. sealed 대기 아님.
계약 변경 없음. W4의 보호 집합 도구와 LeadGen 생산 준비는 후속 연동.

## 4. 검증 (테스트 수, CI 결과, 결정성, 스캐너, 라이선스 스캔)
합성 fixture 중단/재개와 연속 실행의 aggregate.json 바이트가 동일하다.
필터 음성 사례, 압축 제한, 엔티티 거절, 박자 변경/음표·쉼표·꾸밈음 분리 시험.
Windows Job Object 메모리/프로세스 제한·Below Normal·2 CPU affinity 적용 확인.
하드코딩 검사 92파일, 후보 0 PASS. 로컬 Windows `pytest tests/ -q --junitxml=work/pdmx-windows-tests.xml`: 501 passed, 48.68초.
새 시험 5 passed, 신규 코드 커버리지 82.26%. ruff/format/W2 strict mypy 통과.
Draft CI 미실행. GitHub Actions에서 데이터 처리하지 않는다.

## 5. 지표 (평가기 JSON 경로 + 핵심 수치 표: 이전 대비 변화와 95% CI, 슬라이스별)
pdmx-preflight.json에 배포 파일 크기, 전송 실측, 예상 벽시계, 자원 상한 기록.
8 MiB 전송 48.615171초. 실제 완료 후 wall/peak RSS/평균 CPU/전송량을 보고한다.
공개 PDMX 권리필터 집계, 로컬 Windows CPU. Dev/sealed/실사/학습 미실행.
인식 지표·95% CI 해당 없음. KL/1만 곡 블록은 아직 NOT_RUN.

## 6. 일반화 점검 (헌장 8절 체크리스트, 실패 패턴 패키지 첨부 여부)
개별 곡·실패 이미지에 맞춘 분포 선택 없음. 전체 적격 MXL 모집단 스트리밍.
출력은 박자별 type+dots 집계와 원천 manifest digest, 운영 상태뿐이다.
곡 ID/곡별 값, 원본 압축본/MXL을 저장하지 않는다. 새 라이브러리/복사 코드 없음.

## 7. 알려진 한계와 실패 사례 (숨기지 말 것)
전송 속도가 느려 수시간이 예상된다. 재개는 원본 prefix를 다시 전송하되 누적은 중복하지 않는다.
중단 체크포인트는 최종 목표 분포가 아니며, 전체 크기/해시 확인 전 publish하지 않는다.
시작 전 디스크 여유가 잠시 3 GB 아래여서 멈췄고 회복을 확인한 뒤 시작했다.
venv redirector가 별도 Python을 남겨 CSV 단계에서 중단하고 base Python 직접 실행으로 수정했다.
첫 시도의 강제 중단 말미 전송/CPU는 마지막 계측 체크포인트 이후 누락 가능하여 하한으로 구분한다.
샘플링 허용을 쓰지 않고 전수 집계한다. 지원 밖 박자·알 수 없는 음가를 목표로 추정하지 않는다.

## 8. 다음 단계 / 필요한 결정 / 블로커
집계 중 합성 입력으로 생산 프로필/KL 코드를 준비한다. 완료 후 실제 분포·1만 곡 검증.
완료 전 W4에 eval-* 준비 완료를 통지하지 않는다. 학습 편입 차단 유지.
