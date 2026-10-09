# [W2] PR #28 완료·PR #11 기보/생산 검증 준비 — 2026-10-09
판정: PARTIAL — PR #28 병합 완료, 생산 프로필 수용 대기

## 1. 요약 (3줄 이내)
PR #28은 사용자 A승인, W4 확인, 스캐너 0건, 양 OS CI 통과 후 70ed6fb로 병합했다.
PR #11의 UTF-8 fixture, 꾸밈음 성부, 최종 barline, 최종 음높이의 임시표 상태를 보완했다.
실제 PDMX 집계를 연결했으며 학습 편입은 0건이다. 생산 준비 완료 통지는 아직 하지 않았다.

## 2. 변경 (PR 링크, 주요 파일·모듈)
[PR #28](https://github.com/jooa1018/clavis-omr/pull/28), [PR #11](https://github.com/jooa1018/clavis-omr/pull/11).
main을 production-profile에 반영하며 규칙 카탈로그 충돌은 GEN-002~004와 PDMX-001을 모두 보존했다.
production_notation/xml: 꾸밈음 본음 성부 유지, 오른쪽 barline 단일화, 최종 음높이에서 임시표 재계산.
production_audit/check: 실제 XML XSD·음가/성부 시간합·화음·붙임줄 연속성·코드 시점 검사,
P0·두 단계 비율·박자별 KL 집계, 곡별 체크포인트, 발행 전 원천 집계 digest 확인.
production_rhythm: 음표 수가 다른 패턴의 밀도로 기울기가 증폭되던 적합을 notehead-mixture
공간의 정규화된 histogram으로 변경하고 패턴 확률로 역변환했다. 학습률은 설정에 기록했다.

## 3. 계약·결정 (사용한 계약 버전, CCR·ADR 번호)
ADR-010 B의 가중치·비율·하한은 유지한다. 원천 분포·KL 정의·수용 기준은 변경하지 않았다.
lstl-0.1.1 / clavis-ir-0.1.1 유지, T2.5 미구현. W4 평가 투영은 direction/segno/coda를
지원하지 않아 수정하거나 요소를 제거해 통과시키지 않았다. W2 자체 생성 검증으로 구분한다.
PDMX 원천 manifest digest와 canonical JSON target SHA-256을 기록해 OS 줄바꿈에 독립이다.
규칙 GEN-005/006 등록. 큐 실행 전 생성기·설정·uv.lock sourceDigest가 다르면 거부한다.

## 4. 검증 (테스트 수, CI 결과, 결정성, 스캐너, 라이선스 스캔)
PR #28: 전체 Windows 793 passed, Linux/Windows CI PASS, W4 독립 7시험 확인, H9 정확한 2건 승인.
[W4 확인](https://github.com/jooa1018/clavis-omr/pull/28#issuecomment-6075443073).
[CI](https://github.com/jooa1018/clavis-omr/actions/runs/37892508095).
생산 focused 31 passed, 4개 신규/보완 모듈 coverage 94.62%(리듬 안정화 전 측정).
후속 밀도 차이 회귀 시험 포함 리듬 3 passed. strict mypy/ruff/scanner PASS.
생성기 중단/연속 보고서·fitted profile 바이트 동일. 20개 합성 기보 계열과 음성 검증 포함.
명령: `uv run --locked --all-groups python -m training.jobs.short run pytest tests/ --junitxml=work/production-full.xml`.
이번 전체 실행은 W1 launcher.kill_tree의 psutil.AccessDenied로 종료되어 PASS가 아니다.
해당 실행 소유 프로세스는 종료됐음을 확인했다. 실행기 수정 후 최종 전체 시험을 다시 해야 한다.

## 5. 지표 (평가기 JSON 경로 + 핵심 수치 표: 이전 대비 변화와 95% CI, 슬라이스별)
근거: production-preview-v1.json. 실제 집계 기반 합성 100곡에서 XML/기보 오류 0건.
v1 PREVIEW 벽시계 23.329초, 최대 RSS 115,560,448 bytes. 선형 예산 추정은 약 39분/1만 곡으로
OR-001을 초과한다. 고정 적합 시작 비용·동시 부하가 포함되어 독점 성능 벤치마크가 아니다.
v1의 12/8 겹점 기대 질량이 사실상 0인 적합 결함을 발견해 수정했다. v1은 채택하지 않는다.
v2 근거 production-preview-v2.json: 100곡 XML/기보 오류 0, 조건부 비율 위반 0,
28.672초 / RSS 115,580,928 bytes / 2 CPU. 선형 예산 추정 2,867.2초(약 48분).
12/8 겹점 기대 비율 0.0086613으로 회복됐지만 표본 비율 0.0029586은 하한 미달이다.
미리보기는 여전히 PREVIEW이며 생산 PASS가 아니다. 후속 단위 시험 7 passed. 24 GB(16+8 DDR4-3200) Windows 노트북 CPU,
공개 집계 기반 합성 자동 검증이다. Dev/sealed/실사/학습 NOT_RUN, 인식 비교 및 95% CI 해당 없음.

## 6. 일반화 점검 (헌장 8절 체크리스트, 실패 패턴 패키지 첨부 여부)
특정 곡/이미지 분기, 정답 주입, 평가기 변경, 시드 선택 쇼핑 없음. 동일 train-production-v1을 유지한다.
원천 통계만 사용하고 원본 곡은 열지 않았다. 실사 실패 맞춤이 아닌 생성기·산술 결함이다.
선택한 곡 수/비율이 아닌 실제 XML에서 출현을 센다. 작은 미리보기는 절대 블록 PASS가 아니다.

## 7. 알려진 한계와 실패 사례 (숨기지 말 것)
기존 fixture는 cp949 기본 decoding으로 한글 YAML을 읽지 못했다. UTF-8을 명시했다.
꾸밈음 성부 오류는 20개 합성 계열에서 재현했다. XSD만으로 성부·박자 의미를 보증하지 않는다.
진행 기호의 펼친 연주 경로·실제 렌더 겹침 감사는 아직 완료하지 않았다. T2.5 수용도 미달이다.
v1 preview의 래퍼 dataDigest는 기본 영 해시였으나 실제 target/source digest는 산출물에 있다.
v2와 1만 곡 요청에는 실제 target digest를 넣는다. 이 메타데이터 한계를 숨기지 않는다.
W7 artifact 등록 요청은 접수 상태이며 이 PR 범위에서 확인 완료로 표시하지 않는다.

## 8. 다음 단계 / 필요한 결정 / 블로커
production-queue-v2.json: W1 단일 큐에 0f683a7002ba40b9a7b6a973a1ec6321 등록, 아직 미실행.
2 CPU, RAM 1.5 GB, 최대 5,735초, 야간 01:00–07:00. 자동 스케줄러는 설치하지 않았다.
큐 worker 시작 및 W1 실행기 수정을 기다린다. 제출한 생성기/config/lock digest가 바뀌면 거부한다.
야간 작업 완료 전 PR #11은 draft 유지.
W1 실행기 수정 후 전체 시험 및 최종 CI 필요. 사전 승인 확대는 W1에게 직접 요청했으며 반영 대기.
수용 실패는 수치 그대로 보고한다. 실제 렌더·생산 블록 기준을 모두 채운 뒤 W4에 준비 완료 통지한다.
OR-003 보호 집합 v1과 --admitted 결과 전 학습 편입은 계속 0건이다.
