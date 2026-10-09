# [W1] training H9 운영 예외 확대 — 2026-10-09
판정: PASS — 사용자 승인 문안 반영, 개별 예외 판정은 W4 담당

## 1. 요약 (3줄 이내)
W2가 전달한 요청을 W2 대화의 사용자 직접 승인 원문과 대조했다.
00_COMMON 10절에 training/ 운영 시각 사용의 H9 사전 승인 확대를 기록했다.
산출물 바이트 동일성 시험과 W4 확인을 필수 조건으로 유지했다.

## 2. 변경 (PR 링크, 주요 파일·모듈)
docs/tasks/00_COMMON.md 10절 및 이 보고서.
관련 요청 PR: https://github.com/jooa1018/clavis-omr/pull/28
W1 문서 반영 PR 및 [W1 확인] 링크는 해당 PR의 코멘트에 남긴다.
실행 코드·무결성 스캐너·allowlist는 변경하지 않았다.

## 3. 계약·결정 (사용한 계약 버전, CCR·ADR 번호)
Orchestrator 사용자 직접 판정 2026-10-09의 3번(사전 승인 확대).
training/에서 산출 데이터 내용에 영향을 주지 않는 네트워크 재시도·대기,
진행 보고 주기, 실행 시간 상한 등의 H9 시각 사용에 한한다.
중단·재개나 타이밍이 달라도 산출물이 바이트 동일한 시험과 W4 확인 후,
정확한 file/line/digest 및 approvedBy ["W4", "orchestrator"]로 등록한다.
src/clavis와 eval에는 적용하지 않는다. 기존 2026-10-06 training/jobs 승인 기록도 보존한다.
계약 IR/LSTL 버전·평가 기준·개별 예외를 변경하지 않는다.

## 4. 검증 (테스트 수, CI 결과, 결정성, 스캐너, 라이선스 스캔)
수동 사용자 승인 원문/문서 대조, git diff --check, 추적 문서 개인정보 검사.
문서 전용 CI 통과 후 병합한다. 코드·의존성 변경이 없어 새 단위/라이선스 시험은 NOT_RUN.
최신 main에는 다른 워커의 코드가 추가됐으므로 이전 T1.4 750개 결과를 재사용하지 않는다.
준비 완료 전 OR-005 Windows 전체 시험: 933개 PASS, JUnit 81.262초.
명령: `python -m training.jobs.short run pytest tests/ --cov=clavis --cov=scripts --cov=eval --cov=training.jobs --cov-report=json:work/affinity-coverage.json --junitxml=work/affinity-tests.xml`.
증거: SHORT-SLOT-AFFINITY-evidence.json. 이 문서 PR 자체의 실행 코드 변경은 없다.
전체 시험 결과를 W2의 개별 H9 바이트 동일성 시험 PASS로 간주하지 않는다.
개별 위치·digest·시험 확인 및 allowlist 등록은 W4/W2의 PR #28 범위다.

## 5. 지표 (평가기 JSON 경로 + 핵심 수치)
인식 지표, 95% CI, Dev/SYN-Val/실사/sealed 평가 모두 NOT_RUN.
로컬 Windows에서 수동 문서 대조·GitHub 조회 및 OR-005 자동 전체 시험을 수행했다.
슬롯 벽시계 83.609초, CPU 표본 72.921875초, peak RSS 표본 292917248 bytes.
REF-LAPTOP RAM 24 GB(16 + 8 GB, DDR4-3200 듀얼 채널), 슬롯 2 CPU·RAM 상한 3 GB.
렌더·학습·추론·설치 및 데이터 다운로드 없음.

## 6. 일반화 점검 (헌장 8절)
특정 입력/악보·데이터 식별 분기·인식 상수·생성 규칙 없음.
운영 시각과 산출 데이터 내용의 독립성을 시험으로 입증해야 하는 승인 정책이다.
사적/sealed 접근 없음. 코드 규칙 및 ablation 추가 해당 없음.

## 7. 알려진 한계와 실패 사례
이번 W1 확인은 운영 정책의 문서 반영이다. PR #28의 H3/H9 수정·시험·스캐너
통과나 전체 PR 승인을 대신하지 않는다. 운영 예외로 인식/평가나 데이터 선별을 허용하지 않는다.
수정 전 전체 시험 두 번이 monitor-error로 중단돼 JUnit을 만들지 못했다. 진단에서
자식 affinity 조회 AccessDenied를 확인했고 별도 B등급 PR #46에서 Windows Job Object
아래의 중복 조회를 제거했다. 수정 후 동일 슬롯 경로의 전체 933개가 통과했다.
정책 문서는 실행기·스캐너·allowlist를 변경하지 않는다.

## 8. 다음 단계 / 필요한 결정 / 블로커
추가 Orchestrator 판정은 필요 없다. 이미 승인된 범위를 그대로 반영했다.
W2는 W4 확인과 정확한 allowlist, 바이트 동일성 시험, PR #28 필수 검사를 완료한다.
