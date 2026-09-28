# ADR-012 — 평가 정렬과 교정 연산 의미

상태: **채택** — Orchestrator 수정 승인 · 2026-09-29.
승인: 사용자가 전달한 Orchestrator 판정. [PR #3](https://github.com/jooa1018/clavis-omr/pull/3).
담당: W4. EVALUATION v1.1 §4.2·5.1·5.2·5.4에 반영. CONTRACTS v0.1 변경 없음.

## 선택지와 근거

초안의 필드별 합산과 삭제·삽입 최소화는 같은 입력에서 다른 K1을 만들었다.
Orchestrator는 replace-event가 같은 kind에도 허용됨을 확인하고, K1 단위를
**교정 대상 객체 수**로 확정했다. 실사 점수에 맞춘 비용 선택이 아니며,
이전 평가기와 B0 측정은 없어 재측정할 기존 수치는 없다.

## 채택한 결정

- 이벤트 누락·여분 각 1. 대응 쌍의 kind·pitch·duration·tie(start/stop) 중
  하나라도 다르면 replace-event 1회로 센다. 필드 오류 수를 중복 과금하지 않는다.
- 정렬 목적함수는 사전식 `(K1 연산 수, 대응 쌍 필드 불일치 총수, |Δonset| 총합)`.
  onset은 대응 키에서 제외한다. 필드 정확도와 pairs.json은 이 정렬을 사용한다.
- 코드 객체는 값 또는 위치가 다르면 1, 누락·여분 각 1.
- 마디 분할·병합 각 1. 누락·여분 마디는 내부 이벤트 수 + 1.
  조표·박자·음자리표 오류는 발생 지점당 1.
- 마디 DP는 해당 쌍의 이벤트 DP K1 비용을 사용한다. 분할·병합은 이어 붙여
  비교하고 +1, 빈 마디 삽입·삭제는 1. 다중집합 대칭차 근사는 사용하지 않는다.
- 가사는 K1에서 제외하고 K1-L로 보고한다.
- onset만 다른 이벤트는 K1·K2에서 제외하고 `onsetOnlyMismatch`와 measureExact에
  반영한다. 앞선 길이·삽입 오류에서 파생되는 onset을 중복 과금하지 않는다.
- K2도 K1의 객체 단위 중 편곡 영향 오류를 센다. 요소 또는 속한 마디의 flag를
  인정하며 가사·onset 단독 오류는 제외한다.

## 분모와 exact 범위

| 지표 | 분모 / 조건 |
|---|---|
| pitchExact | 기준 note, grace 제외 |
| durationExact | 기준 note·rest·rhythm, grace 제외 |
| graceExact | grace를 별도 평가 |
| restExact | 기준 rest |
| tieExact | 기준 또는 대응 예측 note에 tie 표시가 하나라도 있는 note |
| accidentalExact | 기준 note의 alter가 조표 기본값과 다르거나 임시표가 보임 |
| key/timeSignatureExact | 기준의 설정·변경 지점 |
| chordSymbolExact | 기준 코드 객체, 값+위치 |

measureExact는 1:1 대응 마디에서 이벤트(kind·pitch·duration·onset·tie),
조표·박자·음자리표, 코드 값·위치, 도돌이·볼타 표시가 모두 같아야 한다.
가사는 제외하고 `measureExactWithLyrics`를 참고 지표로 낸다.
분할·병합은 exact가 아니다. ID·표시 번호·성부 번호·divisions는 비교하지 않는다.
분모 0은 null + denominator 0. 미지원 투영 요소는 `evaluation-unsupported`로 표시한다.

## 구현과 동점 규칙

Fraction 기반 결정적 DP. 분할·병합의 onset은 앞 마디 길이만큼 누적한다.
완전 동점은 이벤트 대응→삭제→삽입, 마디 1:1→분할→병합→삭제→삽입,
동일 후보는 입력 문서 순서로 결정한다. 다성부 최적 매칭은 후속 범위다.
첫 PR은 단일 보표·단일 성부이며 원본 위치·모든 쌍·필드 오류·연산을 기록한다.

## 승인된 golden 13쌍

| 쌍 | 차이 | 검증 대상 |
|---|---|---|
| 01 | 동일 | 자기 비교 |
| 02 | divisions | Fraction 동등성 |
| 03 | 성부 번호 | 재번호 동등성 |
| 04 | pitch | pitch 오류 |
| 05 | duration | duration 오류 |
| 06 | 이벤트 누락 | 분모 유지 |
| 07 | 이벤트 여분 | 교정·measureExact |
| 08 | kind·duration 동시 오류 | 객체 1회 |
| 09 | M7/maj7 인쇄형 | 코드 의미 동등성 |
| 10 | 가사 오류 | K1 제외, measureExactWithLyrics |
| 11 | 앞 쉼표 누락·뒤 onset 연쇄 | K1 연산 1, onsetOnlyMismatch > 0 |
| 12 | pitch·duration·tie 동시 오류 | K1 연산 1 |
| 13 | 가사 없음 | null, denominator 0 |

표의 K1=1은 비율이 아닌 교정 객체 **연산 수**다. K1 비율은 100 기준 이벤트로 환산한다.

## 검증과 재검토 조건

golden과 경계·돌연변이 시험으로 정의를 검증한다. 공개 정의가 바뀌면 평가기
버전을 올리고 main·기준선을 재측정한다. `onsetOnlyMismatch`가 커지거나
성부 2의 forward 오류처럼 교정 부담을 숨기는 패턴이 생기면 ADR 재검토를 요청한다.
새 임계값은 발명하지 않고 진단 수치와 재현을 보고한다.

운영 판정 **OR-002**: 스캐너 미구현이어도 B등급 병합 가능. 첫 평가기 다음
우선순위로 스캐너를 구현하고 main에 소급 적용한다. G0 검사 완료를 뜻하지 않는다.
