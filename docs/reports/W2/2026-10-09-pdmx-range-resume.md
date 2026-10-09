# [W2] T2.2 PDMX 구간 이어받기·집계 — 2026-10-09
판정: PARTIAL — 실제 집계 PASS, 스캐너 판정·CI 대기로 PR 병합 보류

## 1. 요약 (3줄 이내)
Orchestrator 2026-10-06 OR-004 보완을 적용해 실제 PDMX v9 집계를 완료했다.
권리 필터 대상 222,820곡 중 222,818곡 파싱, 문법 오류 XML 2곡 제외. 학습 편입 0건.
CSV·MXL 전체 크기/MD5 검증 PASS, 원본 캐시 삭제 완료. PR #28은 draft 유지.

## 2. 변경 (PR 링크, 주요 파일·모듈)
[PR #28](https://github.com/jooa1018/clavis-omr/pull/28), w2/pdmx-aggregate.
pdmx_download.py: 최대 4연결, 4 MiB 구간, fsync 후 SHA-256 완료 저널, OS 잠금,
429/503 Retry-After/backoff, 디스크 시작·진행 가드. 완료·정상 구간은 다시 받지 않는다.
pdmx_stream.py: 검증된 로컬 파일 집계·TAR ordinal 재개·성공 후 지정 원본 삭제.
표준 MXL rootfile 처리, XML 문법 오류 제외 집계, 설정·등록부·README·시험을 보완했다.

## 3. 계약·결정 (사용한 계약 버전, CCR·ADR 번호)
계약 v0.1 변경 없음. OR-004 보완 A판정, A5 집계만 허용, OR-003 학습 차단 유지.
실제 실행은 프로세스 1개, RAM 1.5 GB, Below Normal, affinity 2 CPU, 최대 4연결.
원본 저장소 브랜치는 변경하지 않았다. W1 CI 복원 후에도 자체 병합 게이트를 모두 충족해야 한다.

## 4. 검증 (테스트 수, CI 결과, 결정성, 스캐너, 라이선스 스캔)
로컬 Windows 합성 41 passed, JUnit 1.158초, 관련 4개 모듈 coverage 92.56%. ruff/strict mypy PASS.
명령: `.venv\Scripts\python.exe -m pytest tests/data/test_pdmx_download.py tests/data/test_pdmx_aggregate.py -q --cov=training.data.pdmx_download --cov=training.data.pdmx_stream --cov=training.data.pdmx_aggregate --cov=training.data.pdmx_windows --cov-report=json:work/pdmx-range-coverage.json --junitxml=work/pdmx-range-tests.xml`.
합성 중단/연속 집계 바이트 동일, 손상 구간 재전송, 정상 캐시 무재요청, 비정상 응답/해시 차단,
20개 컨테이너 변형, XML 오류 제외·재개 일치, 성공 후에만 지정 파일 삭제를 확인했다.
후속 CCR-0003 반영 후 Windows 전체 시험 791 passed (W1 짧은 슬롯).
명령·계측·HEAD는 2026-10-09-ccr0003-sync.md와 ccr0003-validation.json 참조.
실제 연속 실행과의 이중 비교 NOT_RUN.
스캐너 FAIL 3건: H3 byte width, H9 backoff 취소 대기·계측 주기. W4 문맥 판정/필요한 A승인 대기.
스캐너/allowlist 변경 없음. 새 의존성 없음. 실제 데이터는 CI에서 처리하지 않았다.
W1 PR #37의 Linux·Windows CI 복원을 반영했다. 개인정보 검사 473파일/0건 PASS.

## 5. 지표 (평가기 JSON 경로 + 핵심 수치 표: 이전 대비 변화와 95% CI, 슬라이스별)
근거: [최종 운영 계측](pdmx-range-final.json), [원본 집계](pdmx-v9-aggregate.json), [시험·스캐너](pdmx-range-preflight.json).

| 운영 지표 | 결과 |
|---|---:|
| 활성 벽시계 / 수정·대기 포함 경과 | 58.00분 / 67.89분 |
| 최대 RSS | 581,062,656 bytes |
| 평균 CPU (1코어 / 전체 12논리 CPU 기준) | 39.22% / 3.27% |
| HTTP body 누적 전송 (재시도 포함) | 2,153,150,894 bytes |
| CSV / MXL 검증 크기 | 225,399,738 / 1,894,335,797 bytes |
| 전체 MD5 및 manifest SHA-256 대조 | PASS / PASS |
| 저장소 work+data / 종료 후 디스크 여유 | 58,652,366 / 6,629,793,792 bytes |

| 박자 | 기보가 있는 곡 수 | 일반 pitched notehead 수 |
|---|---:|---:|
| 4/4 | 91,912 | 37,922,755 |
| 3/4 | 30,981 | 8,191,327 |
| 6/8 | 42,452 | 6,624,830 |
| 2/4 | 29,099 | 5,600,784 |
| 12/8 | 2,287 | 1,182,203 |
| 2/2 | 27,852 | 6,558,218 |

전수 집계이며 표본 추출 안 함. 박자 변경 곡은 여러 행에 포함될 수 있다. 모든 성부의 written
notehead를 세고 화음 머리·붙임줄 분절도 각각 센다. 쉼표·꾸밈음은 별도이며 반복을 펼치지 않는다.
공개 코퍼스 집계/합성 자동 시험, 증설 후 RAM 23.7 GiB 노트북 CPU. Dev/sealed/실사/학습 미실행.
인식 지표·95% CI 비교 없음. 상세 음가·점 분포와 원천 manifest digest만 집계 산출물에 남겼다.

## 6. 일반화 점검 (헌장 8절 체크리스트, 실패 패턴 패키지 첨부 여부)
no_license_conflict + PDM/CC0 필터 유지. 곡 ID·곡별 값·악보 원문은 산출물에 없다.
원천 전체 검증 후 집계하고, 종료 시 CSV/압축본/구간 저널 삭제를 확인했다(잠금 파일만 남음).
입력 식별 예외·XML 복구·음악 요소 추정 없음. 합성 입력을 실제 PDMX 분포로 대체하지 않았다.

## 7. 알려진 한계와 실패 사례 (숨기지 말 것)
중단 3회: 선택 media-type을 필수로 검사한 파서 결함, 외부 디스크 여유 <3 GB, 원천 XML 문법 오류.
[MusicXML 표준](https://www.w3.org/2021/06/musicxml40/tutorial/compressed-mxl-files/)의 첫 rootfile/생략 시 MusicXML 기본값을 구현하고 시험했다.
디스크가 5.49 GB로 회복된 뒤 재개했다. 문법 오류는 추정 복구 없이 제외 개수만 기록했다.
모든 재개에서 HTTP 전송량은 늘지 않았다. 과거 2026-09-29 중단 계측은 이번 수치에 섞지 않았다.
로컬 운영 traceback의 프로필 경로는 새 개인정보 규칙에 맞춰 상대 경로/%USERPROFILE%로 정리했다.
W7의 PP-OCR/한·영 폰트 등록 요청은 접수만 기록했으며 artifact 라이선스·해시 확인은 아직 미수행.

## 8. 다음 단계 / 필요한 결정 / 블로커
스캐너 3건의 W4 문맥 검토 전달 및 필요한 Orchestrator 판정 대기. 정확한 위치/digest는 근거 JSON 참조.
W1 짧은 슬롯 전체 시험 완료. 스캐너 판정 및 현재 CI 통과 후 PR #28 병합. W1 큐 PR #27은 main 반영 완료.
그 뒤 PR #11 UTF-8 fixture·기보 검증 → 생산 프로필·KL·1만 곡 검증(OR-001 초과 시 큐).
준비가 끝난 뒤에만 W4에 eval-* 준비 완료 통지. 지금은 미통지이며 학습 편입은 0건이다.
다음 T2.5는 CONTRACTS 4.2 및 W1 T1.4 오토마톤을 따른다.
