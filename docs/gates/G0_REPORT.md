# G0 보고서 초안 — 자와 기반

작성: W4 · 2026-09-29 · 검토 기준 커밋: `8734be8`.
**Orchestrator 판정 대기. 이 문서는 G0 통과를 선언하지 않는다.**
기준: EVALUATION v1.0 §9. 문서 검토만 수행했으며 데이터 평가를 실행하지 않았다.

| 필수 항목 | 확인 상태 | 근거 / 미충족 사항 |
|---|---|---|
| 저장소·Linux/Windows CI·계약 v0.1·Schema·LSTL 코어 병합 | PARTIAL | [W1 T1.1a](../reports/W1/T1.1a-review-procedure.md): 저장소·CI 근거. 계약·LSTL 완료 증거는 이 기준 커밋에 없음 |
| 평가기 v1 전체 투영·정렬·지표·bootstrap·돌연변이 20종 | BLOCKED | [ADR-012 초안](../adr/ADR-012-evaluation-alignment.md): 연산 의미 결정 대기. [eval 골격](../../eval/README.md), 첫 golden 10쌍도 아직 미구현 |
| Dev v0 ≥20쪽·manifest·권리·분리 검사 | NOT_RUN | GT 형식·구축 도구 미완료. 사적 데이터·후보 폴더 열람 없음. 요청 계획은 [W4 보고 §8](../reports/W4/T4.0-start.md#8-다음-단계--필요한-결정--블로커) |
| B0: 3개 기준선 × Dev v0·SYN-Val | NOT_RUN | 기준선 실행기·데이터 준비 전. Audiveris 5.10.2, homr 지정 revision, oemer 고정 버전 확정 필요 |
| 하드코딩·누출·import 방향 검사 CI 연결 | PARTIAL | [pyproject.toml](../../pyproject.toml) import 규칙과 W1 CI 근거 있음. [integrity_status.py](../../scripts/integrity_status.py)는 NOT_RUN 자리표시자 |
| Sealed 집계 실행기·해시 목록 도구·원장 | NOT_RUN | Custodian 전용 도구 미구현. sealed 데이터 접근·요청 없음 |

## 평가·자원 기록

평가기 JSON, K1, 정확도, 95% CI, 슬라이스 보고서 모두 없음(NOT_RUN).
Dev/SYN/실사/합성 자동 평가는 실행하지 않았다. sealed는 미접근이다.
작업 장소: 로컬 Windows 노트북, 수동 문서 검토. 학습·렌더·평가 배치 미실행.
GPU·유료 컴퓨트 사용 없음. 무거운 작업은 W1 단일 큐 01:00–07:00만 사용 예정.
W1 보고의 기존 CI 결과를 W4 신규 도구의 검증 결과로 간주하지 않는다.

## 해소 순서

1. Orchestrator: ADR-012의 K1 최소화, onset 처리, exact 분모·범위 결정.
2. W4: 첫 평가기 PR과 golden 10쌍, 돌연변이 시험 20종 이상, 전 지표·bootstrap.
3. W4: 격리 기준선 실행기, GT 형식 확정, Dev v0 구축 도구.
4. GT 확정 후 한국어 접수 안내: CLAVIS_PRIVATE_ROOT, 부분 전사 sidecar,
   MuseScore 전사·렌더 대조·다른 날 검토. 그 전 Dev 후보 11쪽 요청 보류.
5. W4/W1: 무결성 검사 CI 연결. Custodian 도구 준비. Dev/B0 근거로 이 초안 갱신.

권리와 누출 검증 전 데이터셋을 완성된 것으로 등록하지 않는다.
최종 게이트 판정은 Orchestrator가 별도 G0_REVIEW에 기록한다.
