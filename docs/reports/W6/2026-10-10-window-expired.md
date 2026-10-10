# [W6] T6.0 승인 창 만료 보고 — 2026-10-10
판정: NOT_RUN

## 1. 요약 (3줄 이내)
이번 heartbeat 호출 시각은 10월 10일 13:39:49 KST로, 승인된 당일 01:00–07:00 창 이후다.
등록된 준비 1건·학습 4건은 모두 queued, 누적 벽시계 0초이며 정식 결과가 없다.
v2 큐와 자동화를 PAUSED로 전환했고, 다음 날 실행이나 자동 재등록은 하지 않는다.

## 2. 변경 (PR 링크, 주요 파일·모듈)
[PR #64](https://github.com/jooa1018/clavis-omr/pull/64), 브랜치 `w6/missed-window`; 이 보고서와 `2026-10-10-window-expired.json`만 추가한다.
코드·설정·동결 source descriptor·요청·데이터·가중치는 변경하지 않는다.
이전 구현 및 검증은 [PR #58](https://github.com/jooa1018/clavis-omr/pull/58)에 병합됐다.

## 3. 계약·결정 (사용한 계약 버전, CCR·ADR 번호)
clavis-ir/lstl 0.1.1, CCR-0003 유지. 새 CCR·ADR·규칙 없음.
Orchestrator의 일반 batch 4→8→4→8 판정은 유지한다. 독점 benchmark는 엔진 지연 예산 전용이다.
이번 heartbeat의 창 만료 시 미실행 보고·PAUSED 지시를 적용했다. 수동 우회나 창 연장은 하지 않았다.

## 4. 검증 (테스트 수, CI 결과, 결정성, 스캐너, 라이선스 스캔)
노트북에서 큐 SQLite를 읽어 5건의 상태·벽시계·pid를 확인했고 experiments.jsonl 및 measurement.json 부재를 확인했다.
동결 파일 59개와 요청 5개의 SHA-256이 등록값과 일치한다. 자동화와 신·구 큐 모두 paused 상태를 재확인했다.
처음 checkout SHA는 `f96e1da7adb9b3cb1edab7f15d831df908cbe759`, 요청 SHA는 `d096b6808932f705c783eff17780152475fa4a4a`다.
문서 브랜치는 병합 정본 `cb0f4fcc63bf2d29ef41731f4d5939f1e7f3b35b`에서 만들었고 동결 파일 동일성을 확인했다.
이번 변경은 문서 전용이다. 전체 pytest·결정성·AST·라이선스 검사는 NOT_RUN이며 이전 실행을 이번 PASS로 세지 않는다.
이전 Windows 전체 1475 passed 및 양 OS CI 근거는 `2026-10-09-monitor48.md`에 있다.
`git diff --cached --check` PASS, `python scripts/check_privacy.py --out work/w6-window-privacy.json` PASS(664개 추적 파일, findings 0).
CI의 경량 문서 검사 결과는 이 보고서 PR의 checks를 정본으로 한다.

## 5. 지표 (평가기 JSON 경로 + 핵심 수치 표: 이전 대비 변화와 95% CI, 슬라이스별)
정제 운영 근거: `2026-10-10-window-expired.json`. 평가기 출력이 아닌 큐·해시 감사 결과다.

| 항목 | 관측값 |
|---|---:|
| 새 큐 등록 건수 / 실행 건수 | 5 / 0 |
| 새 큐 누적 벽시계(초) | 0 |
| measurement.json / 유효 4·8스레드 쌍 | 0 / 0 |
| 일치한 동결 파일 / 요청 해시 | 59 / 5 |

FCN/LightGBM × 4/8의 처리량·fit·RSS·CPU·외부 CPU·가용 RAM·priority·affinity·반복 분산·95% CI는 모두 NOT_RUN이다.
부하가 큰 회차나 유효 쌍을 판별할 표본 자체가 없다. batch 결과를 benchmark.validity로 해석하지 않는다.
2스레드 예비 값과 증설 전 값을 대입하지 않았다. 인식 정확도 아님, SYN-Val 아님.

## 6. 일반화 점검 (헌장 8절 체크리스트, 실패 패턴 패키지 첨부 여부)
자동 호출에 따른 로컬 상태 감사만 수행했다. 기존 합성 artifact는 해시 확인만 했으며 이미지 디코딩·렌더·학습은 없다.
실사·Dev·sealed·R-LIED·R-TGT·PDMX에 접근하지 않았다. 새 다운로드·GPU·유료 컴퓨트 없음.
OR-003 measurement-only 목적을 유지한다. 평가 보고·가중치 선택·엔진 사용은 금지한다.
인식 변경과 실패 패턴 패키지는 해당 없음.

## 7. 알려진 한계와 실패 사례 (숨기지 말 것)
관측된 호출은 승인 창 이후이며, 큐에 실행 근거가 없다. 예약 전달 지연이나 기기 상태의 원인은 확인하지 않았다.
큐 control은 paused=true지만 개별 요청 행은 queued로 보존된다. 이를 실행 실패나 완료로 바꾸지 않았다.
PLAN 7.5의 20–40시간 추정 검증 및 4시간 내 데이터 규모·모델 크기 제안은 정식 처리량 부재로 NOT_RUN이다.
향후 수치가 생겨도 실제 학습 일정·수렴·라벨 과제가 없는 상태에서는 조건부 검증만 가능하다.

## 8. 다음 단계 / 필요한 결정 / 블로커
`work/w6-training-compare-queue`와 구 `work/w6-measurement-queue`는 중지 상태로 보존한다.
자동화 `w6-t6-0-cpu`도 PAUSED다. 다음 날 임의 실행·실패 자동 재등록·추가 trial을 하지 않는다.
재개 첫 단계는 Orchestrator의 새 창 판정 확인이다. 승인 후 동결 해시·요청·큐 상태를 다시 확인한다.
이후 같은 승인 창에서 준비 → FCN-4 → FCN-8 → LightGBM-4 → LightGBM-8을 실행하고 유효한 동일 크기·seed 쌍만 비교한다.
