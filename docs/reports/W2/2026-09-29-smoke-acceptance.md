# [W2] 첫 목표 실제 렌더 수용 보고 — 2026-09-29
판정: PASS (첫 목표 범위만; G0 전체 아님)

## 1. 요약 (3줄 이내)
origin/main의 W1 training/CI 변경을 w2/start에 병합하고 OR-001 짧은 개발 실행으로 검증했다.
자체 생성 10곡 × 3폰트의 30페이지를 렌더하고 전체 오선 겹침을 시각 감사했다.
라이선스 등록부 v0와 첫 렌더·추출 도구 수용 기준 충족. 미확인 원천과 학습 편입 차단 유지.

## 2. 변경 (PR 링크, 주요 파일·모듈)
[PR #5](https://github.com/jooa1018/clavis-omr/pull/5), training/data 및 configs/data와 tests/data.
실제 폰트 리소스 해시, 사용 글리프 일치, 보표 소속 대조를 render-audit-v0.json에 기록했다.
실제 렌더 subprocess 회귀 테스트와 peak RSS 계측 추가. 원본 worktree는 변경하지 않았다.

## 3. 계약·결정 (사용한 계약 버전, CCR·ADR 번호)
IR/LSTL v0.1 변경 없음. OR-001: 짧은 30종 실행 승인. OR-002: W4 스캐너 NOT_RUN으로 B등급 병합 허용.
등록부 v0도 B등급이라는 사용자 전달 Orchestrator 판정 적용. 신규 라이선스 계열 없음.
라벨은 내부 SVG staff-local 감사 산출물이며 런타임 계약 구현이나 LeadGen 완성을 주장하지 않는다.

## 4. 검증 (테스트 수, CI 결과, 결정성, 스캐너, 라이선스 스캔)
validation-smoke-acceptance.json: W2 25 tests passed, coverage 92.34%; 전체 36 passed / 1 기존 skip.
ruff·format·mypy(base/W2 strict)·import 경계·런타임 라이선스 통과. CI는 PR 최종 head 확인 후 병합한다.
3폰트 각각 동일 MusicXML의 실제 재렌더 SVG 바이트 일치. 10개 시드의 선율 윤곽도 서로 다름을 검사했다.
W4 스캐너/평가 전용 곡 지문 필터 NOT_RUN(OR-002). 합성물의 학습 편입은 계속 차단한다.
W2 에이전트가 전체 30페이지를 10개 3열 감사 이미지로 확인했다(사람의 승인으로 표시하지 않음).

## 5. 지표 (평가기 JSON 경로 + 핵심 수치 표: 이전 대비 변화와 95% CI, 슬라이스별)
측정 JSON: render-audit-v0.json. 인식 평가기·Dev·sealed·실사 NOT_RUN; 인식 성능/95% CI 해당 없음.

| 합성 개발 감사 수치 | 결과 |
|---|---:|
| 원본 MusicXML / 렌더 페이지 | 10 / 30 |
| Leipzig / Bravura / Leland | 10 / 10 / 10 |
| 보표 마디 구간 / 실패 | 180 / 0 |
| 사용 글리프의 폰트 fallback | 0 |
| 최종 30종 CPU 실행 벽시계 | 17.844초 |
| 렌더러 최대 peak RSS | 27,193,344 bytes |
| XML·SVG·라벨·메타데이터 합계 | 499,904 bytes |

REF-LAPTOP Windows CPU, 수동 시작·자동 검사 + 에이전트 시각 감사. 학습/GPU/유료 컴퓨트 미사용.

## 6. 일반화 점검 (헌장 8절 체크리스트, 실패 패턴 패키지 첨부 여부)
입력 식별 분기/사적·sealed 접근 없음. train-* 시드와 명시적 numpy Generator 사용.
DATA-SVG-001은 원본 renderer 오선만 읽으며 추정·보완하지 않는다. 상위 transform/viewBox 유지.
실제 페이지의 CSS가 감사선 색을 덮는 일반 SVG 표시 문제를 인라인 스타일로 수정하고 회귀 검사했다.
인식 실패 맞춤 수정이 아니므로 인식 실패 패턴 패키지와 Dev 성능 비교 해당 없음.

## 7. 알려진 한계와 실패 사례 (숨기지 말 것)
첫 실행의 오버레이는 좌표는 맞지만 CSS 때문에 검정이었다. 수정 후 전 페이지 재감사 완료.
초기 열거 fixture는 조·박자 변형에 치우쳐 시드별 독립 선율로 보강했다. 최종 수치는 보강본 기준이다.
30곡/페이지의 단순 5선 smoke 성공을 복잡한 코퍼스·곡선·비5선 보표 정확도로 일반화하지 않는다.
W4 지문 검사가 없으므로 공개 코퍼스 수집·학습 shard 생성은 여전히 금지 상태다.

## 8. 다음 단계 / 필요한 결정 / 블로커
PR #5 draft 해제, 최종 Windows/Linux CI 후 B등급 squash 병합. 다음 PR에서 LeadGen 착수.
조건부·미확인 후보는 차단 유지하며 지금 새 라이선스 결정을 요청할 항목은 없다.
향후 CC-BY-SA를 실제 사용하려면 별도 승인, W4 학습 편입 필터 연계는 계속 필요하다.
