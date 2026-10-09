# [W8] 전체 Windows 시험 임시 예외 — 2026-10-09
판정: PARTIAL — 전체 Windows 및 필수 게이트 PASS, 양 OS CI 대기
기계 근거: [집계 JSON](DIRECT-EXCEPTION-2026-10-09.json).

## 1. 요약 (3줄 이내)
Orchestrator는 W1 실행기의 monitor-error 수정을 W1에 배정하고, 동일 pytest 명령의 래퍼 없는 직접 실행을 한 번 승인했다.
기존 래퍼 실패와 직접 실행 결과를 모두 기록하며, 직접 실행 통과 후 PR #25의 두 OS CI와 B등급 병합을 진행한다.

## 2. 변경 (PR 링크, 주요 파일·모듈)
[PR #25](https://github.com/jooa1018/clavis-omr/pull/25), 검증 대상 `888660e`.
이번 작업은 검증·보고·병합이며 엔진, 규칙, 계약, W1 실행기는 변경하지 않는다.

## 3. 계약·결정 (사용한 계약 버전, CCR·ADR 번호)
Orchestrator 2026-10-09 임시 예외: monitor-error 발생 시 같은 pytest 명령을 직접 한 번 실행한다.
다른 무거운 실행과 겹치지 않도록 기존 머신 공통 worker.lock을 독점 취득하고 실행 내내 유지한다.
W1이 수정을 알리면 이후 실행은 다시 짧은 실행 슬롯 래퍼를 사용한다. 계약/라이선스 판정 변경 없음.

## 4. 검증 (테스트 수, CI 결과, 결정성, 스캐너, 라이선스 스캔)
Windows REF-LAPTOP, RAM 24 GB(16+8 GB, DDR4-3200 듀얼 채널). OMP/OPENBLAS/MKL은 각각 2.

| 실행 | 결과 |
|---|---|
| 기존 W1 래퍼 전체 시험 | failed / monitor-error; 벽시계 215.20300000000134초; JUnit/coverage 미생성 |
| 승인된 직접 실행 1회 | 1048 passed, 실패·오류·skip 0; pytest 129.46초, 전체 명령 131.4421274초 |
| 전체 커버리지·필수 시험 게이트 | overall/platform/eval/jobs 모두 PASS; 계약 298개, 무결성 positive/negative 24개 PASS |
| PR Linux·Windows CI | ready 전환 후 [PR checks](https://github.com/jooa1018/clavis-omr/pull/25/checks)로 확인 |

직접 실행 명령(기존 명령에서 training.jobs.short run만 제거):
```text
uv run --locked --all-groups pytest tests/ --cov=clavis --cov=scripts --cov=eval --cov=training.jobs --cov-report=json:work/w8-full-coverage.json --junitxml=work/w8-full-tests.xml
```

## 5. 지표 (평가기 JSON 경로 + 핵심 수치 표)
W4 정본은 [T8.2-oracle-2026-10-09.json](T8.2-oracle-2026-10-09.json)이다.
K1=0, measureExactMatchRate=1.0(2/2). 직접 작성한 합성 기호 smoke이며 **SYN-Val 아님**.
이번에는 인식 평가를 새로 실행하지 않는다. 학습·렌더·GPU·유료 컴퓨트 사용 없음.

## 6. 일반화 점검 (헌장 8절 체크리스트)
새 인식 규칙·상수·특정 입력 분기 없음. Dev/sealed/실사 및 paired 95% CI NOT_RUN.
원본 JUnit의 로컬 식별 정보는 공개하지 않고 허용된 집계 필드만 보고서에 옮긴다.

## 7. 알려진 한계와 실패 사례 (숨기지 말 것)
기존 degrade 시험에서 record_property/xunit2 관련 경고 4건이 있었다. 실패·skip은 없으며 타 소유 시험을 변경하지 않았다.
래퍼 실패를 숨기거나 구성요소 298개 통과로 전체 시험을 대체하지 않는다.
이번 직접 실행은 한 번뿐인 예외이며 W1 실행기의 수정 완료를 의미하지 않는다.
전체 근거 좌표·신뢰도 보정·제품 번들은 후속 범위이며 G1 달성을 주장하지 않는다.

## 8. 다음 단계 / 필요한 결정 / 블로커
직접 실행과 독립 게이트를 통과했다. ready 전환 후 두 OS CI를 확인하여 승인된 B등급 squash 병합을 진행한다.
실패하면 직접 재실행하지 않고 결과를 보존해 보고한다. 이후 실행기는 W1 수정 통보를 따른다.
