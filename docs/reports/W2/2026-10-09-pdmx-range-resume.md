# [W2] T2.2 PDMX 구간 이어받기 재개 — 2026-10-09
판정: PARTIAL — 실제 다운로드 진행, 전체 집계·병합 대기

## 1. 요약 (3줄 이내)
2026-10-06 Orchestrator 재개 판정을 2026-10-09 반영했다. 최신 origin/main을 W2 브랜치에 병합했다.
HTTP range 캐시와 구간 체크포인트를 구현해 재전송 범위를 미완료·손상 구간으로 제한했다.
실제 실행은 OR-004 자원 제한으로 진행 중이다. 생산 프로필·학습 편입 완료 주장은 없다.

## 2. 변경 (PR 링크, 주요 파일·모듈)
[PR #28](https://github.com/jooa1018/clavis-omr/pull/28), w2/pdmx-aggregate.
pdmx_download.py: 최대 4연결, 4 MiB 구간, fsync 후 SHA-256 구간 저널,
프로세스 종료 시 해제되는 OS 잠금, 429/503 Retry-After와 지수 backoff.
pdmx_stream.py: 검증된 로컬 파일을 스트리밍으로 집계하고 성공 후 원본 CSV/압축본만 삭제.
설정·README·등록부와 합성 시험을 갱신했다. 원본 저장소 브랜치는 변경하지 않았다.

## 3. 계약·결정 (사용한 계약 버전, CCR·ADR 번호)
계약 v0.1 변경 없음. OR-004 보완 A판정으로 외부 임시 캐시 및 range 다운로드 허용.
메모리 1.5 GB, Below Normal, 2 CPU 제한 유지. 학습 편입은 OR-003 보호 집합 v1 receipt 대기.
W1 CI 재가동과 로컬 전체 시험 슬롯을 확인하기 전 PR을 병합하지 않는다.

## 4. 검증 (테스트 수, CI 결과, 결정성, 스캐너, 라이선스 스캔)
합성 로컬 Windows CPU: 18 passed, JUnit 1.172초. 관련 4개 모듈 라인 커버리지 92.22%.
명령: `.venv\Scripts\python.exe -m pytest tests/data/test_pdmx_download.py tests/data/test_pdmx_aggregate.py -q --cov=training.data.pdmx_download --cov=training.data.pdmx_stream --cov=training.data.pdmx_aggregate --cov=training.data.pdmx_windows --cov-report=json:work/pdmx-range-coverage.json --junitxml=work/pdmx-range-tests.xml`.
중단/연속 집계 바이트 동일, 완료 구간 무재요청, 손상 구간 재요청, 잘못된 HTTP 응답·해시 차단,
성공 시에만 지정 원본 삭제 및 무관 파일 보존 시험. ruff/strict mypy PASS. 새 의존성 없음.
전체 시험 NOT_RUN(W1 짧은 슬롯 대기). CI workflow API는 active, W1 준비 완료 확인 전 draft 유지.
스캐너 FAIL: 98파일, H3 1건(구간 byte width), H9 2건(backoff 취소 대기와 계측 주기).
인식 로직과 무관한 운영 코드지만 allowlist/스캐너는 수정하지 않았다. W4 문맥 확인·판정 요청 필요.

## 5. 지표 (평가기 JSON 경로 + 핵심 수치 표: 이전 대비 변화와 95% CI, 슬라이스별)
근거: pdmx-range-preflight.json, 실제 실행 work/pdmx-v9-range-aggregate/run-metrics.json.

| 시작 조건 | bytes |
|---|---:|
| CSV + MXL 입력 | 2,119,735,535 |
| 필요한 여유 (입력 + 3 GB) | 5,119,735,535 |
| 관측 시작 여유 | 8,320,798,720 |
| RAM 상한 | 1,500,000,000 |

4연결 단순 예상 약 51분, 실제 서버 제한에 따라 달라진다. 최종 wall/RSS/CPU/전송 및
두 파일 전체 크기·MD5·SHA-256은 종료 후 기록한다. 공개 코퍼스 집계 전용,
합성 자동 시험이며 실제 Dev/sealed/인식/학습 미실행. 인식 지표 및 95% CI 해당 없음.

## 6. 일반화 점검 (헌장 8절 체크리스트, 실패 패턴 패키지 첨부 여부)
no_license_conflict + PDM/CC0 필터 유지. 산출물은 집계 표와 manifest digest 및 운영 증거뿐이다.
원천 CSV·압축본은 저장소 밖 임시 폴더에만 유지하고 성공 후 삭제한다.
부분 다운로드·미검증 압축본으로 목표 분포를 발행하지 않는다. 곡 ID/곡별 값은 산출물에 없음.

## 7. 알려진 한계와 실패 사례 (숨기지 말 것)
2026-09-29 이전 스트림의 미완결 계측은 별도 보존하며 이번 실행 계측에 섞지 않는다.
실제 전체 집계는 아직 미완료. 구간 재개는 합성으로 검증했고 실제 중단 시험을 위해 실행을 죽이지 않았다.
스캐너 문맥 판정과 W1 슬롯·CI가 병합 의존성이다. 예외를 자체 승인하지 않는다.
W1 배치 큐 PR #27은 2026-10-09 01:00 KST 병합 확인(a62d6f9). 짧은 슬롯은 아직 대기다.
COMMON의 H9 사전 승인은 training/jobs에 한정되므로 W2 다운로드에 확대 적용하지 않는다.
W7이 요청한 PP-OCR/한·영 폰트 등록 검토는 접수만 기록: detector ONNX 후보와
Latin/Korean 원본 revision을 전달받았으며 독립 라이선스·artifact 해시 확인은 아직 하지 않았다.

## 8. 다음 단계 / 필요한 결정 / 블로커
다운로드 → 전체 파일 검증 → 로컬 집계 → 원본 삭제 → 최종 운영 계측 기록.
W4 스캐너 문맥 확인 후 필요한 A판정, W1 짧은 슬롯 전체 시험과 CI 확인 뒤 PR #28 병합.
이어 PR #11 UTF-8 fixture 및 기보 검증, 실제 목표 분포·KL·1만 곡 검증.
OR-001을 넘는 검증은 W1 큐로 실행한다. 그 뒤에만 W4에 생산 프로필/eval-* 준비 완료 통지.
학습 receipt가 없으면 편입 0건. 다음 T2.5는 CONTRACTS 4.2와 W1 T1.4 오토마톤을 따른다.
