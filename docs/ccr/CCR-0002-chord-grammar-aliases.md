# CCR-0002 — 코드 문법 시작 규칙과 인쇄 별칭의 수용 범위

상태: APPROVED — Orchestrator 2026-10-06 판정, 2026-10-09 사용자 메시지로 수신.
**v0.1 정오표, 버전 불변.** 1–4절은 승인 전 제안의 이력이며 현재 판정은 5절이다.
작성: W7, 2026-09-29. 기준: 6d529726ca176e5bd60b7b9b531412602048d09f.
영향: W1(계약), W7(인식·정규화), W8(harmony·힌트), W4(평가), W9(소비자).

## 1. 동기와 재현 근거

첫 T7.3 문법 오토마톤 및 CONTRACTS 12.6 전체 어휘 적합성 시험을 작성하기 전에,
동결된 6절의 생성 문법과 요구되는 표기 집합 사이에 다음 차이를 확인했다.
실제 이미지·Dev·sealed와 무관한 문서의 문자열 예시다.

| 문자열 | 문서 근거 | 6절 시작 규칙을 문자 그대로 적용한 결과 |
|---|---|---|
| Cø7 | 6절 composite, 12.6 복합 | chord → root body인데 body 어디에서도 composite를 참조하지 않아 도출 불가 |
| CmMaj7 | 6절 composite, 12.6 복합 | quality=m 다음 primary에 Maj7이 없고 composite도 연결되지 않아 도출 불가 |
| CMAJ7 | 12.6 maj7 별칭 | quality=M 다음 AJ7을 소비할 규칙이 없어 도출 불가 |
| CM9 | 12.6 maj9 별칭 | quality=M + primary=9로는 도출되나 maj9 정규화 의미를 명확히 해야 함 |
| CΔ9 | 12.6 maj9 별칭 | quality=Δ + primary=9로는 도출되나 maj9 정규화 의미를 명확히 해야 함 |
| CminMaj9 | 12.6 복합 | 6절 composite에도 없으며 body에서 Maj9를 소비할 수 없음 |
| C△7 | W7 T7.3 인쇄 변형, 6절 kindText 예 | 6절 quality/primary에 △가 없어 인쇄형과 정규형의 검증 경계가 필요 |

`src/clavis/contracts/README.md` 및 승인 CCR-0001은 코드 문자열 파싱을 W7 책임으로
남기며, 현재 wire 타입 검증은 위 문자열의 문법이나 정규화 의미를 확정하지 않는다.
기존 TextIR fixture의 C/Am7/F/G7/N.C./C/E만으로는 이 차이를 판정할 수 없다.

## 2. 판정 요청과 제안

아래는 승인 전 실행하지 않는 제안이다. 거부 시 대체 수용 범위를 지정해 달라.

1. **복합 연결:** `body := composite | [quality] [primary] [sus] {modifier}`로 연결할지
   결정한다. composite 뒤 modifier/sus를 추가로 허용할지도 명시한다.
   제안은 우선 문서에 열거된 composite 전체와 slash bass만 허용하는 최소 연결이다.
2. **12.6 별칭:** MAJ7/Maj7/M7/Δ7 → maj7, M9/Δ9 → maj9,
   minMaj9 → mMaj9를 명시적인 인쇄 별칭으로 수용할지 결정한다.
   quality=M/Δ와 primary=9 결합은 maj9로 해석하는 것을 제안한다.
3. **검증 경계:** `TextItem.text`와 `kindText`에는 관측 인쇄 표기를 보존하고,
   `chord.normalized`와 정규화 이후 후보가 6절 문법을 통과하도록 할지 결정한다.
   △→Δ, ♭→b, ♯→# 등은 관측 글리프의 표기 정규화이고,
   OCR의 A→△ 같은 모호한 시각 혼동은 별도의 확률 대안이어야 한다.
   검증 경계를 명시하면 인쇄형 보존과 "문법을 통과한 문자열만 출력"을 함께 시험할 수 있다.

권고: 1–3을 계약의 명시적 의미로 확정하고 W1이 버전·fixture를 반영한 뒤 W7 구현을 재개한다.
문법을 한쪽만 따르거나 테스트에서 불일치 항목을 빼는 방안은 제안하지 않는다.

## 3. 변경 범위와 마이그레이션

- 현재 변경은 이 CCR 초안과 W7 착수 보고서뿐이다. CONTRACTS/스키마/런타임은 변경하지 않았다.
- 승인 후 계약 버전은 CONTRACTS 0절에 따라 Orchestrator/W1이 판정한다.
  v0.1을 W7이 임의로 다시 동결하거나 기존 동결 예외를 재사용하지 않는다.
- wire 필드 추가는 제안하지 않는다. 정규형·인쇄형·파싱 결과 의미를 먼저 합의한다.
- 승인 후 W7은 모든 12.6 표기와 거부 예시, alias 보존, 결정성 시험을 작성하고
  수작업 정규화 대응표를 configs/text/rules.yaml에 등록한다.
- W4/W8은 코드 비교 및 MusicXML kind/degree 대응이 같은 의미인지 확인해야 한다.

## 4. 평가 영향과 현재 상태

측정 변경 없음. 인식·학습·렌더·평가 실행 없음. Dev/sealed 데이터 접근 없음.
승인 전에 이 제안에 의존하는 파서·합성 코드 생성기·CTC 디코더를 구현/병합하지 않는다.
별개의 W2 텍스트 폰트 등록과 PP-OCR artifact 확인은 W7 보고서의 재개 의존성으로 남긴다.

## 5. 승인 기록 — 2026-10-06 (수신·반영 2026-10-09)

승인 주체: Orchestrator. 사용자 전달 메시지: "CCR-0002 승인(A등급, 이 메시지가 승인이다)."
범위: 이 PR #24에서 W7이 CONTRACTS 6절을 승인 문안으로 수정하고 [W1 확인] 후 병합한다.
CI는 W1 재활성화 이후만 병합 가능하다. 아래 승인 내용이 2절의 미승인 제안을 대체한다.

1. `body := composite {modifier} | [quality] [primary] [sus] {modifier}`.
   composite는 m7b5/min7b5/ø/ø7/dim7/°7/mMaj7/minMaj7/mMaj9/minMaj9 전체다.
   composite 뒤 modifier는 허용하고 modifier 자체 문법은 변경하지 않는다.
2. primary의 maj7은 maj7/MAJ7/Maj7/M7/Δ7, maj9는 maj9/MAJ9/Maj9/M9/Δ9를 수용한다.
   나머지 root/bass/quality/primary/sus는 승인 문안대로 CONTRACTS 6절에 반영했다.
3. 최장 일치 토큰화: M7·Δ7 → maj7, M9·Δ9 → maj9, m7b5 → composite.
   복수 도출의 정규형은 모두 같아야 하며 W7 구현 PR에서 시험한다.
   M·Δ·maj 단독은 HarmonyMaker와 같은 장3화음이다.
4. 정규형: ø·ø7·min7b5 → m7b5, °7 → dim7, minMaj7 → mMaj7,
   minMaj9 → mMaj9, maj7/maj9 별칭 → maj7/maj9, min·- → m,
   ° 단독 → dim, + → aug, maj·M·Δ 단독 → 접미사 없음. 변화음 순서와 /bass는 유지한다.
5. TextItem.text와 kind@text는 관측 인쇄형을 보존한다. chord.normalized와 정규화 뒤 후보를
   문법 검증한다. △/♭/♯/전각/위첨자/Ø의 결정적 표기 대응은 W7 규칙 등록부에 일반 관례 근거와
   함께 기록하고, A↔△ 및 0↔o↔°는 치환 규칙이 아닌 인식 확률 대안으로 다룬다.
6. **정오표·버전 불변 사유:** 문법 내부 모순이 있었으며 해당 문법을 구현한 코드와 산출물이
   아직 없다. 따라서 v0.1을 유지한다. 구현 이후 변경은 CONTRACTS 0절의 버전 규칙을 적용한다.
7. 12.6 전 어휘·거부 예시·복수 도출 정규형 동일성 시험은 W7 구현 PR에 둔다.
   이 문서 PR은 인식 코드·JSON Schema·fixture·평가기·모델을 변경하지 않는다.

[W1 확인]: 요청 예정/미수신. Orchestrator 승인과 W1 확인 및 CI 결과를 혼동하지 않는다.
