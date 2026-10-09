# [W6] T6.0 야간 큐 준비·T6.1 W5 연결 보고 — 2026-10-09
판정: PARTIAL — 연결·예비 경로 검증 완료, 정식 4/8스레드 수치는 야간 실행 대기

## 1. 요약 (3줄 이내)
W5 #32와 W1 monitor-error 수정 #46을 main에서 반영했다.
공유 extract_strip → 원본/제거 채널 → SymbolGraph → 검증된 StaffLattice 초안을 연결했다.
FCN·LightGBM measurement-only 예비 경로를 검증했고, 정식 측정은 10월 10일 01–07시 KST 큐로 실행한다.

## 2. 변경 (PR 링크, 주요 파일·모듈)
브랜치 `w6/queued-measurement`. W6 소유 경로만 변경한다.
`src/clavis/symbols/staff.py`: W5 공개 API 호출과 W6 읽기 구성 연결.
`training/models/symbols/jitter.py`, `measurement_data.py`, `measurement.py`:
W5 synthetic-v0 오차 행 소비, 기존 W2 smoke 조각 준비, 큐 기반 독립 학습 시간 측정.
`configs/symbols/measurement.json`에 실험 규모·시드·예산을 고정한다. W2 생산 코드 변경 없음.

## 3. 계약·결정 (사용한 계약 버전, CCR·ADR 번호)
clavis-ir-0.1.1 / lstl-0.1.1 및 승인 CCR-0003. 공통 normalize/serialize/parse/오토마톤 경계를 유지한다.
W5가 정의한 중심 오차에는 간격 오차가 포함되어 재가산하지 않는다. 전체 오차 행을 같은 interline에서 재표집한다.
추론에서 난수를 쓰지 않으며 새 인식 규칙·상수·임계값을 추가하지 않았다. 기존 카탈로그 8개 그대로다.
FCN 구조는 약 10만 파라미터의 시간 측정 fixture이며 생산 모델 채택 결정이 아니다.

## 4. 검증 (테스트 수, CI 결과, 결정성, 스캐너, 라이선스 스캔)
Windows / CPU / RAM 24 GB(16+8 GB DDR4-3200 듀얼 채널). 증설 전 8 GB 측정값과 비교하지 않는다.
새 경계·결정성·jitter 11개, 해시 변조 거부·중단 trial 재개 7개 단위 시험 PASS.
1·4 OpenCV 스레드 각각 3회 strip/mesh/graph/lattice 바이트 동일, 입력 불변성 및 0.8/1/1.25배 검사.
ruff check/format, mypy, import 경계, runtime license, H1–H9 스캐너 PASS.
선택 학습 환경은 torch 2.5.1+cpu(BSD), LightGBM 4.6.0(MIT), SciPy 1.18.1(BSD),
resvg-py 0.2.6(MIT, 기존 승인 도구). 런타임 의존성과 uv.lock은 변경하지 않았다.
전체 시험은 `uv run --locked --all-groups python -m training.jobs.short run pytest tests/`
뒤에 coverage/JUnit 저장 인자만 추가했다. 첫 시도는 슬롯 경합으로 시작되지 않았다. 결과는 검증 JSON에 갱신한다.
CI는 로컬 전체 시험 후 ready 전환하여 Linux·Windows 둘 다 확인한다.

## 5. 지표 (평가기 JSON 경로 + 핵심 수치 표: 이전 대비 변화와 95% CI, 슬라이스별)
`2026-10-09-queued-probes.json`: 자동 합성 smoke, **SYN-Val 아님**, 실사/Dev/sealed 평가 아님.
기존 W2 train-smoke 두 쪽, 원래/흔든 기하 8 strips: 기호 131, 관계 34, lattice 가설 8,
완성 항목 0, unresolved 근거 240. 실제 IER·oracle@k·paired·95% CI는 NOT_RUN.

| OR-005 예비 실행 (2스레드) | queue 벽시계 초 | 표본 peak RSS bytes |
|---|---:|---:|
| 2쪽·8 strip·64조각 경로 | 14.43699999999808 | 311463936 |
| FCN 64조각·1 epoch | 15.01600000000326 | 341643264 |
| LightGBM 64조각·2 rounds | 10.625 | 270569472 |

이는 라이브러리·큐·경로 확인용 **예비** 측정이다. 정식 스레드 비교나 PLAN 추정 검증으로 사용하지 않는다.
각 fit 시간과 초기 import/warmup을 포함하는 trial/queue 시간을 JSON에서 구분했다.

## 6. 일반화 점검 (헌장 8절 체크리스트, 실패 패턴 패키지 첨부 여부)
실사/Dev/sealed/R-LIED/R-TGT/PDMX 미사용. W2 report 출처와 train-smoke seed 및 artifact hash를 검사한다.
선택된 두 합성 쪽에서 복원 추출하므로 8192 records를 독립 곡이나 라벨 기호 수로 해석하지 않는다.
원본과 제거 채널을 모두 소비한다. beam/flag·dots·voice·pitch를 생성하지 않는다.
W5 synthetic-v0는 합성 오차 분포이며 실사 일반화 근거가 아니다. 특정 실사 실패 패키지는 해당 없음.

## 7. 알려진 한계와 실패 사례 (숨기지 말 것)
상류 속성 라벨이 없어 lattice 초안은 미해결이며 finalize는 거부한다. 빈 항목은 정상 읽기 성공이 아니다.
일부 strip의 제거 채널 변화가 0이며 분포·상수 조정을 하지 않았다. 수치는 제거 품질 평가가 아니다.
FCN은 grayscale, LightGBM은 ink-density 대리 표적이다. 수렴·인식 품질·실제 샘플러 비용을 측정하지 않는다.
완료된 독립 trial의 시간만 checkpoint한다. 중단된 trial은 고정 시드로 다시 시작하며 모델 가중치는 저장하지 않는다.
시간 상한으로 중단되면 미완료 크기·스레드 슬라이스를 FAIL/NOT_RUN으로 명시하고 재시도 예산을 임의 늘리지 않는다.

## 8. 다음 단계 / 필요한 결정 / 블로커
야간에는 전용 상태 루트 `work/w6-measurement-queue`를 사용하되 W1 머신 공통 배타 잠금을 공유한다.
조각 준비 1건(1800초), FCN/LightGBM × 4/8스레드 4건(각 3600초), 모두 RAM 최대 3 GB.
8192조각 cache, 크기 512/2048/8192 × seed 반복 3, FCN batch 8·3 epochs·102209 parameters,
LightGBM 15 leaves·100 requested rounds를 비교한다. 모델별 두 thread job 상한 합은 2시간이다.
정식 완료 후 처리량·RSS·CPU·수준별 반복 분산을 보고하고, 보수적 4시간 데이터 규모와 모델 크기를 제안한다.
PLAN 7.5의 20–40시간은 재학습 일정·실제 데이터가 없는 한 조건부 추정으로만 검증한다.
OR-003 편입 전 measurement-only이며 평가 보고·엔진 모델·체크포인트 선택에는 사용하지 않는다.
