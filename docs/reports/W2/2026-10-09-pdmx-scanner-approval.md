# [W2] PR #28 스캐너 판정 반영 — 2026-10-09
판정: PARTIAL

## 1. 요약 (3줄 이내)
Orchestrator 사용자 원문(2026-10-09 A등급 승인)에 따라 H3 코드 수정과 H9 예외를 처리한다.
원본 PDMX 집계 값은 변경하지 않았으며 학습 편입은 0건이다.
W4 문맥 확인, 전체 Windows 시험 및 양 OS CI를 별도 병합 게이트로 유지한다.

## 2. 변경 (PR 링크, 주요 파일·모듈)
[PR #28](https://github.com/jooa1018/clavis-omr/pull/28).
pdmx_download.py의 width를 segment_bytes로 바꾸고 16 MiB 상한을
configs/data/pdmx-aggregate.json의 download.max_segment_bytes로 옮겼다.
기존 4 MiB 구간 크기와 HTTP/캐시 무결성 동작은 유지한다. 경계 초과·0바이트를
네트워크 및 파일 생성 전에 거부하는 합성 시험을 추가했다.

## 3. 계약·결정 (사용한 계약 버전, CCR·ADR 번호)
계약 lstl-0.1.1 / clavis-ir-0.1.1 변경 없음. OR-004 집계 전용 허가, OR-003 차단 유지.
H9 사용자 직접 승인: 네트워크 재시도 대기와 진행 보고 주기는 데이터 내용을 결정하지 않는다.
전체 source 크기·MD5 검증을 통과한 파일에서만 집계를 발행하며 중단·연속 aggregate.json의
바이트 동일성 시험이 있다. training/의 같은 조건 H9 사전 승인 확대는 W1에게
00_COMMON 반영 및 [W1 확인]을 요청했다. src/clavis와 eval은 해당하지 않는다.

## 4. 검증 (테스트 수, CI 결과, 결정성, 스캐너, 라이선스 스캔)
합성 focused 43 passed. 명령: `.venv/Scripts/python.exe -m pytest tests/data/test_pdmx_download.py tests/data/test_pdmx_aggregate.py -q --junitxml=work/pdmx-approved-focused.xml`.
ruff/format, 전체 mypy 및 training/data strict mypy PASS. 런타임 라이선스 위반 0건.
수정 후 H3 탐지 0건. H9 두 항목은 동일한 위치/digest의 승인 대상이다.
Windows 전체 793 passed/0 skipped/errors/failures. OR-005 벽시계 125.594초,
최대 RSS 301,117,440 bytes, CPU 86.594초, affinity 2.
명령: `uv run --locked --all-groups python -m training.jobs.short run pytest tests/ --junitxml=work/pdmx-approved-full.xml`.
[W4 확인](https://github.com/jooa1018/clavis-omr/pull/28#issuecomment-6075443073): 독립 합성 7시험 및 정확한 두 H9 승인.
allowlist 두 항목에 approvedBy ["W4","orchestrator"]와 정확한 file/line/digest를 기록했다.
최종 스캐너 PASS(지적 0건); CI는 준비 완료 전환 후 확인한다.

## 5. 지표 (평가기 JSON 경로 + 핵심 수치 표: 이전 대비 변화와 95% CI, 슬라이스별)
이번 시험·스캐너 근거는 pdmx-approved-validation.json.
원천·집계·자원 결과는 pdmx-range-final.json 및 pdmx-v9-aggregate.json 그대로다.
이번 검증은 증설 후 24 GB(16+8 DDR4-3200) Windows 노트북의 합성 자동 시험이다.
실제 PDMX 재다운로드·렌더·학습·Dev/sealed 평가는 NOT_RUN. 인식 비교/95% CI 해당 없음.

## 6. 일반화 점검 (헌장 8절 체크리스트, 실패 패턴 패키지 첨부 여부)
상한은 HTTP 구간 bytes 단위 자원 제한이며 이미지 식별·음악 판정과 무관하다.
H3 회피 예외 없이 의미 있는 변수명과 설정을 사용했다. H9는 공개 승인과 정확한 digest에 한정한다.
곡별 값·식별자·원문을 보고서에 추가하지 않았다. 사적 자료와 sealed에 접근하지 않았다.

## 7. 알려진 한계와 실패 사례 (숨기지 말 것)
실제 전수 연속/재개 이중 실행은 NOT_RUN; 합성 중단/재개 바이트 동일성 및 실제 재개 계측을 구분한다.
현재 합성 fixture와 집계 시험은 향후 생산 프로필 및 T2.5 수용을 대신하지 않는다.

## 8. 다음 단계 / 필요한 결정 / 블로커
W4 확인과 승인 예외 → 전체 시험·양 OS CI → PR #28 squash 병합.
이후 PR #11 UTF-8 fixture·기보 검증 → 실제 집계 기반 생산 프로필·KL·1만 곡 검증.
모두 준비된 뒤에만 W4에 생산 프로필과 eval-* 시드 준비 완료를 알린다.
