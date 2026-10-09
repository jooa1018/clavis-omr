# [W2] #48 반영·슬롯 전체 시험 재검증 — 2026-10-09
판정: FAIL — monitor-error 해소, W1 벤치마크 시험 3건 실패

## 1. 요약 (3줄 이내)
최신 main을 w2/production-profile에 병합하고 #48 monitor-error 수정을 반영했다.
이전 실패 기록을 보존하고 해소 이력을 2026-10-09-production-notation.md에 덧붙였다.
생산 블록 수용과 학습 편입 완료를 주장하지 않는다.

## 2. 변경 (PR 링크, 주요 파일·모듈)
[PR #11](https://github.com/jooa1018/clavis-omr/pull/11), main merge 0287b9b1f54e888d0dc6ba51ea32299022bcc835.
W1 #48(9623fac)과 후속 실행기·독점 벤치마크·공통 정책을 반영했다.
W2 생성기·설정·원천 집계 및 계약은 이번 작업에서 변경하지 않았다.

## 3. 계약·결정 (사용한 계약 버전, CCR·ADR 번호)
lstl-0.1.1 / clavis-ir-0.1.1, ADR-010 B와 OR-003 차단 유지.
전체 시험은 계속 OR-005 슬롯으로 실행한다. 지연/속도 정식 측정은 01:00–07:00에
training.jobs.benchmark를 쓰고 valid 결과만 판정에 사용한다. 기존 미리보기 시간은 계획 참고치다.

## 4. 검증 (테스트 수, CI 결과, 결정성, 스캐너, 라이선스 스캔)
명령: `uv run --locked --all-groups python -m training.jobs.short run pytest tests/ --junitxml=work/production-after-pr48.xml`.
전체 1516 passed / 3 failed / 0 errors / 0 skipped, W2 data 126시험 실패 0.
253.000초 / CPU 147.172초 / 최대 RSS 316,952,576 bytes / CPU limit 2.
실행기 reason=command-failed이며 monitor-error 재발 없음. NoSuchProcess 자식 표본 27건을
건너뛴 진단이 정상 보존됐다. 실행 결과·진단은 pr48-validation.json에 기록한다. PR #11은 draft이므로 원격 CI는 미실행이다.
기존 소스 digest와 큐 요청의 동일성을 확인했다. 실제 데이터/렌더/훈련은 이번 작업에서 미실행.

## 5. 지표 (평가기 JSON 경로 + 핵심 수치 표: 이전 대비 변화와 95% CI, 슬라이스별)
근거 pr48-validation.json. 증설 후 24 GB(16+8 DDR4-3200) Windows 노트북 합성 자동 시험이다.
이전 실행은 AccessDenied ERROR, 이번 재검증은 별도 실행으로 보존한다.
Dev/sealed/실사 성능, 지연 예산, 인식 변화 및 95% CI는 해당 없음.

## 6. 일반화 점검 (헌장 8절 체크리스트, 실패 패턴 패키지 첨부 여부)
새 인식 규칙·임계값·특정 입력 예외 없음. 실행기 상한·머신 잠금을 우회하지 않았다.
원본 checkout 브랜치는 변경하지 않았다. 학습 편입은 0건이다.

## 7. 알려진 한계와 실패 사례 (숨기지 말 것)
tests/platform/test_benchmark.py 실패: pause_during_sampling_or_retry[1](147행),
four_threads_full_affinity_normal_priority_and_evidence(213행),
admission_timing_does_not_change_job_bytes(270행). 첫 항목의 가상 clock은 238.5로 기대 <2를
초과했고, 나머지 두 항목은 중첩 execute의 failed 상태를 반환했다. 근본 원인은 미확정이다.
W1 소유 코드이므로 COMMON §8.8에 따라 수정하지 않고 Orchestrator에게 에스컬레이션한다.
전체 시험 통과가 생산 1만 곡·P0·희귀 음가 하한·실제 렌더 감사를 대신하지 않는다.
과거 실패 진단과 미리보기 수치는 삭제하거나 정상 실행 결과와 합치지 않는다.

## 8. 다음 단계 / 필요한 결정 / 블로커
기존 1만 곡 job 0f683a7002ba40b9a7b6a973a1ec6321은 queued, sourceDigest 일치다.
W1 벤치마크 시험 3건 해소와 야간 큐 worker 시작을 기다린다. 자동 스케줄러나 낮 시간 장기 실행은 추가하지 않았다.
순서: PR #11 생산 수용·W4 준비 통보 → W7 PR #50 독립 artifact 검증·등록 → T2.5.
PR #28은 이미 병합 완료. PR #11은 생산 수용 및 최종 CI 전까지 draft 유지.
