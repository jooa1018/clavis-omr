# [W2] LeadGen 개발 코어 착수 보고 — 2026-09-29
판정: PARTIAL

## 1. 요약 (3줄 이내)
첫 목표 PR #5는 양 OS 최종 CI 후 squash 병합했다(3c996d8).
별도 w2/leadgen-v0에서 설정 기반·결정적 단일 성부 MusicXML 생성 코어를 구현했다.
개발 프로필만 허용하며 생산 분포·전체 P0·학습 편입은 아직 승인/검증 대상이다.

## 2. 변경 (PR 링크, 주요 파일·모듈)
PR 링크는 생성 후 갱신한다. training/data/leadgen.py, configs/data/leadgen-development.yaml,
tests/data/test_leadgen.py, DATA-GEN-001 카탈로그, ADR-010 초안.
LeadGen 자체 작성물은 tool-test만 허용하도록 원천 등록부 갱신. 원본 worktree 변경 없음.

## 3. 계약·결정 (사용한 계약 버전, CCR·ADR 번호)
MusicXML 4.0, LSTL/IR v0.1 계약 변경 없음. ADR-010은 PROPOSED, 채택하지 않았다.
학습 기본 가중치와 드문 기보 발생률의 분모를 Orchestrator에 요청한다(00_COMMON §8).
설정의 purpose는 development만 허용한다. 승인 전 기본 학습 프로필로 승격하지 않는다.

## 4. 검증 (테스트 수, CI 결과, 결정성, 스캐너, 라이선스 스캔)
LeadGen 신규 10 tests passed, 코드 coverage 98.05%. 전체 90 passed / 1 기존 skip.
ruff·format·base/W2 strict mypy·import 경계·runtime license 통과. CI는 PR 생성 후 확인한다.
±7 조표 × 6박자=90 표본을 독립 파싱, 각 마디 시간합과 표기음가를 검사했고 반복 바이트 일치.
높은음자리·낮은음자리·테너 8vb 각각 실제 외부 Verovio 렌더 성공.
W4 스캐너/지문 필터 NOT_RUN(OR-002); 원천 출처 검사와 학습 출력 차단 유지.

## 5. 지표 (평가기 JSON 경로 + 핵심 수치 표: 이전 대비 변화와 95% CI, 슬라이스별)
자동 개발 감사 JSON: leadgen-development-validation.json. 인식 평가기/95% CI 해당 없음.
강제로 조·박자 격자를 덮은 표본이므로 생산 분포의 발생률로 해석하지 않는다.

| 합성 개발 감사 | 결과 |
|---|---:|
| 표본 / 시간합 오류 | 90 / 0 |
| 반복 바이트 일치 | 전체 |
| note / rest 이벤트 | 2,191 / 386 |
| 점1 / 점2 이벤트 | 486 / 129 |
| 생성+파싱+반복 확인 벽시계 | 0.656초 |
| 감사 프로세스 peak RSS | 44,376,064 bytes |

REF-LAPTOP Windows CPU, 자동 검사. dev/sealed/실사/학습 미실행. GPU·유료 컴퓨트 미사용.
1만 곡 처리량과 모든 P0 1% 수용 기준은 NOT_RUN/미충족이며 외삽하지 않는다.

## 6. 일반화 점검 (헌장 8절 체크리스트, 실패 패턴 패키지 첨부 여부)
train-* 시드는 명시적 numpy Generator 초기화에만 쓰며 외부 악보 식별자 분기 없음.
모든 분포값을 명시적 YAML로 받는다. 정수 시간합은 MusicXML divisions 정의에 따른다.
DATA-GEN-001 등록/off 거절 검사. 생성 전에 유효 리듬을 구성하고 사후 음표 보완은 하지 않는다.
인식 규칙/Dev 변경이 없어 인식 ablation·실패 패턴 패키지·Dev 비교 해당 없음.

## 7. 알려진 한계와 실패 사례 (숨기지 말 것)
지금은 단일 성부, 조표·박자·세 음자리표, 온음표–32분음표, 점·쉼표,
quarter pickup, 제목·템포만 지원한다. 조·박자 변경/단조 프로필, 붙임줄,
연음·꾸밈음·코드·가사·진행·2성부·슬래시 등 후속 P0 기능은 미구현이다.
전체 MusicXML XSD 검증 또는 W1 LSTL 정규화 검증을 통과했다고 주장하지 않는다.
남은 시간을 정확히 채우는 조건 때문에 짧은 음가 비중이 커질 수 있다(32nd 720건).
생산 가중치는 이 개발 프로필을 그대로 쓰지 않고 집계 검증을 거쳐 결정해야 한다.

## 8. 다음 단계 / 필요한 결정 / 블로커
ADR-010 생산 분포 제안 B와 tuplet/grace 확률 분모(곡 또는 이벤트)의 Orchestrator 확정 필요.
결정 전에는 이 PR을 draft로 두고 생산 프로필/양산/학습 편입을 진행하지 않는다.
이후 승인된 프로필로 P0 기능 확장, 출현 빈도 감사, W4 지문 필터 연결을 진행한다.
