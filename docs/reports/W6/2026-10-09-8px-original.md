# [W6] T6.1 8 px 원본 채널 확인 — 2026-10-09
판정: PARTIAL — 원본 단독 경로 PASS, 인식 정확도 NOT_RUN

## 1. 요약 (3줄 이내)
PR #49의 W5 strip→SymbolGraph→StaffLattice 초안 연결에 8 px 원본 단독 확인을 추가했다.
제거 채널을 흰 영상으로 대체해도 합성 입력에서 머리 템플릿·세로선·관계 후보를 생성한다.
beam/flag·dots·voice가 미해결이므로 완성 항목은 0개이며, 인식 성공이나 개선으로 주장하지 않는다.

## 2. 변경 (PR 링크, 주요 파일·모듈)
[PR #53](https://github.com/jooa1018/clavis-omr/pull/53), 브랜치 `w6/original-channel-8px`.
`tests/symbols/test_staff.py` 회귀 시험 1개와
`training/models/symbols/lowres_smoke.py`의 재현 가능한 합성 채널 비교를 추가했다.
모듈 README에 설치 환경의 명시적 geometry 설정 경로 및 smoke 범위를 설명했다.
엔진·설정·임계값·기존 학습 측정 코드는 변경하지 않는다.

## 3. 계약·결정 (사용한 계약 버전, CCR·ADR 번호)
승인 CCR-0003, clavis-ir-0.1.1 / lstl-0.1.1 및 기존 W1 파서·오토마톤 검증 경계를 사용한다.
`load_config(Path(.../configs/geometry))`를 명시하고 공유 `extract_strip`을 호출한다.
입력 interline 8 px를 s*=16으로 정규화한다. 위/아래 여백 6/5, 높이 240은 W5 설정을 따른다.
기하 jitter는 W5 `synthetic-v0`의 8 px 행 전체를 재표집한다. 새 규칙·상수 채택·CCR/ADR 없음.

## 4. 검증 (테스트 수, CI 결과, 결정성, 스캐너, 라이선스 스캔)
Windows CPU, RAM 24 GB(16+8 GB DDR4-3200 듀얼 채널), GPU·추가 의존성 없음.
새 authored 8 px 회귀 시험 PASS: 원본 단독 머리/세로선 후보, 미관측 속성 미생성, 미해결 finalize 거부.
W2 합성 smoke는 OR-005 CPU 2·RAM 3 GB·32 images 선언으로 실행했다.
`python -m training.jobs.short run --items 32 --seed 6 --data-digest <W2-report-sha256> training.models.symbols.lowres_smoke work/w6-smoke work/w6-templates work/w6-8px-smoke.json`.
큐 벽시계 12.156000000002678초, peak RSS 표본 297295872 bytes, monitorDiagnostics 빈 목록.
ruff check/format, mypy(87 sources), H1–H9, privacy, runtime license와 import 경계 PASS.
전체 시험은 `uv run --locked --all-groups python -m training.jobs.short run pytest tests/`
뒤에 coverage/JUnit 인자만 추가했다. **1447 passed**, 실패/오류/skip 0, JUnit 94.340초,
큐 벽시계 97.95300000000134초, peak RSS 표본 300601344 bytes.
전체 커버리지 93.88502380080557%, 전체/platform/eval/jobs 게이트 및 계약·무결성 필수 시험 PASS.
정제 근거: `2026-10-09-8px-validation.json`. 종료된 자식의 NoSuchProcess 진단은 W1 실행기 정책대로 기록됐다.
Linux·Windows CI 최종 정본은 [PR checks](https://github.com/jooa1018/clavis-omr/pull/53/checks)이며,
양쪽 성공 후 B등급 squash 병합한다.

## 5. 지표 (평가기 JSON 경로 + 핵심 수치 표: 이전 대비 변화와 95% CI, 슬라이스별)
정본: `2026-10-09-8px-smoke.json`. **자동 합성 smoke, SYN-Val 아님**. W4 정확도 평가 아님.
기존 W2 train-smoke 두 쪽(Leipzig/Bravura), 각 두 보표, clean/jitter 기하로 8 strips를 비교했다.

| 채널 | 기호 후보 | 템플릿 후보 | 세로선 후보 | 관계 후보 | 미해결 근거 | lattice 항목 |
|---|---:|---:|---:|---:|---:|---:|
| 원본+제거 | 106 | 66 | 40 | 20 | 288 | 0 |
| 원본만 | 106 | 66 | 40 | 20 | 287 | 0 |

폰트·보표·clean/jitter별 결과와 실제 입력 interline(모두 8.0)은 JSON에 보존했다.
집계 수가 같아도 후보 박스·확률·거절 후보까지 같다는 뜻은 아니다. IER/oracle@k/95% CI는 NOT_RUN.

## 6. 일반화 점검 (헌장 8절 체크리스트, 실패 패턴 패키지 첨부 여부)
원본 NCC와 세로선 경로를 확인했으며 runtime 조건·임계값·채널 선택 규칙은 바꾸지 않았다.
기존 카탈로그 8개 및 on/off·ablation을 유지한다. 기존 단위·결정성·스케일 시험도 유지한다.
W2 source/seed/hash를 검사했다. 실사·Dev·sealed·R-LIED·R-TGT·PDMX 접근이나 학습 없음.
이번 입력에서 잘 보이도록 상수를 조정하지 않았다. 특정 실사 실패 일반화 패키지는 해당 없음.

## 7. 알려진 한계와 실패 사례 (숨기지 말 것)
W2의 알려진 합성 보표 기하를 사용하므로 W5의 보표 누락을 시험하거나 복구한 것이 아니다.
W5 공지의 8 px 보표 누락과 높은 선 잔여율은 이 확인으로 해소되지 않는다.
jitter는 누락 보표를 포함하지 않고 실사 오류 분포도 아니다. 기호 정답 라벨이 없어 후보의 정오를 판단하지 않는다.
빈 lattice는 미해결 초안이며 완성 인식 산출물이 아니다. 음높이와 관측되지 않은 속성 생성 없음.

## 8. 다음 단계 / 필요한 결정 / 블로커
T6.0 정식 측정은 PR #49에서 등록한 동일 큐 5건과 `w6-t6-0-cpu` 자동화를 유지한다.
10월 10일 01:00–07:00 KST, measurement-only, FCN/LightGBM × 4/8스레드. 중복 등록하지 않았다.
야간 source descriptor 55개 파일의 해시 불변을 확인한다. 새 시험·smoke·README는 동결 대상 변경이 아니다.
정식 수치와 PLAN 7.5 조건부 검증·4시간 규모 제안은 해당 실행 후 보고한다.
실제 인식/후보 보존 oracle@k 평가는 W2 기호·관계 라벨과 W4 평가 경계 제공 후 진행한다.
