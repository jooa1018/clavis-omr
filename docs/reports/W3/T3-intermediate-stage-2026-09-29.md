# [W3] T3 중간 해상도 처리 보고 — 2026-09-29
판정: PARTIAL (기능 PASS, 성능 미달; Orchestrator의 기본 사용률≤30% 조건으로 병합 승인)

## 1. 요약 (3줄 이내)
PR #13 전단 흐림·잡음을 원본 대신 목표의 2배 중간 해상도에서 처리하도록 수정했다.
측정 최저 1.4548985451746648쪽/초로 3 미만이므로 기본 변형 선택 확률을 30%로 강제한다.
W6 T6.0 뒤 실제 생성 속도 요구를 재판정하며 성능 PASS로 포장하지 않는다.

## 2. 변경 (PR 링크, 주요 파일·모듈)
https://github.com/jooa1018/clavis-omr/pull/13 — `w3/phone-stage-order`, W3 전용 worktree.
`training/degrade/{ops,presets,compare_stages}.py`, README, YAML, stage 시험 및 본 보고서.
main의 CI #22와 W4 스캐너 수정을 반영했다. 원본 worktree 브랜치는 바꾸지 않았다.

## 3. 계약·결정 (사용한 계약 버전, CCR·ADR 번호)
공개 계약/CCR 변경 없음. ADR-011 후속 Orchestrator 판정(2026-09-29)을 구현한다.
중간 폭·높이는 각각 min(원본, 2×최종 정수 크기). 목표 구간은 한 번만 뽑고 확대하지 않는다.
최종 크기를 trace에 고정하여 두 번째 추정·반올림으로 크기가 바뀌지 않는다.
기본 호출(None)은 변형 전체를 확률0.3으로 선택하고 그 안에서 전/후를 균등 선택한다.
명시적 True는 강제 시험/사용, False는 v0 경로다. 유한 배치의 실제 빈도는 변동할 수 있다.
H3 입력 형식·빈 이미지·예산 검증은 수정하지 않았다. W4 문구/검사 해석을 따른다.

## 4. 검증 (테스트 수, CI 결과, 결정성, 스캐너, 라이선스 스캔)
준비 완료 전 Windows 로컬 전체 **524 PASS / SKIP0**, W3 **126 PASS**.
명령: `.venv/Scripts/python.exe -m pytest tests/ --cov=training.degrade --cov=clavis --cov=scripts --cov-fail-under=80 --cov-report=json:work/intermediate-coverage.json --junitxml=work/intermediate-tests.xml -o junit_family=legacy`.
W3 라인 coverage 96.90402476780186%. ruff/format/mypy/W3 strict/import 경계/runtime license PASS.
새 크기·목표 한 번 추출·no-upscale·연속 라벨·JSON replay·1/4스레드 결정성·30% 선택을 검증했다.
H1–H9 AST **PASS, findings0, suppressed0**. 실제 데이터 누수 검사는 NOT_RUN(재고 미제공).
CI는 로컬 검증 완료 후 ready 전환하여 Linux만 실행한다. 작업 단위 push 1회로 묶는다.

## 5. 지표 (평가기 JSON 경로 + 핵심 수치 표: 이전 대비 변화와 95% CI, 슬라이스별)
자동 근거: `intermediate-stage-comparison.json`. 합성/로컬 수동 CPU의 자동 측정이며 인식 평가가 아니다.
90쪽 실행(변형60+원본 참조30), 1스레드, 2.048/4 MP, 40 px 렌더, seed0/1/2.
전/후·5종 모두 유지, 1 warmup+2 timed/슬라이스. 벽시계33.0914344000048초, RSS144195584 bytes.

| 측정 | 값 |
|---|---|
| 평균 / 최저 처리율 | 4.428985142705977 / 1.4548985451746648쪽/초/코어 |
| 최저 슬라이스의 같은 조건 원본 참조 | 1.128166163077776 쪽/초 |
| 픽셀 MAE: 표본 평균 / 최댓값 | 1.7067682501402457 / 3.3631569990820167 |
| 표본 RMSE 최댓값 / 단일 픽셀 최대차 | 10.26828273324931 / 190 |
| 표본별 절대 오차 p95의 최댓값 | 17 |
| 연속 점 라벨 최대 차이 | 2.842170943040401e-14 px |
| 목표 추출 시도 / 거부 | 60 / 0 |

픽셀 단위는 0–255다. 원본 참조는 중간 resize만 제거하고 최종 크기·강도·JPEG·잡음 초기 RNG를 고정한다.
잡음 배열 크기가 달라 동일 실현값이 아니며, 두 번 리샘플링의 영향도 포함한다. 차이 0인 표본은 중간=원본이다.
원본 참조는 resolved replay, 새 경로는 파라미터 추출 포함 실행이라 호출 비용이 완전히 같지는 않다.
95% CI·지속 성능은 NOT_RUN. 이전 다른 시점 측정과 속도 변화의 유의성은 주장하지 않는다.

3쪽/초 미달 슬라이스(나머지 포함 전20슬라이스는 JSON):

| 경로 / 배치 / 원본 픽셀 | 쪽/초 |
|---|---|
| phone-daylight / before_resize / 4000000 | 2.307766511382375 |
| phone-daylight / after_resize / 4000000 | 2.2824036266432652 |
| phone-indoor / before_resize / 4000000 | 2.9618887846754025 |
| phone-angle / before_resize / 4000000 | 2.2143835504722937 |
| phone-angle / after_resize / 4000000 | 1.6424115331083722 |
| phone-shadow / before_resize / 4000000 | 1.4548985451746648 |
| phone-shadow / after_resize / 4000000 | 2.8893045314229795 |

## 6. 일반화 점검 (헌장 8절 체크리스트, 실패 패턴 패키지 첨부 여부)
원본 해상도에 비례하는 일반 연산이며 특정 악보·이미지 식별/튜닝 없음. 기준2배·30%는 YAML에 출처 기록.
실사 픽셀/배경/텍스처·Dev·sealed 데이터 접근 없음. 출력은 CC0 자체 도식, 이미지 바이너리 미커밋.
인식/조립 규칙 추가 없음, 특정 실사 실패 패키지 비해당. GPU·유료·무거운 배치 실행 없음.

## 7. 알려진 한계와 실패 사례 (숨기지 말 것)
평균도5 미만이며 최저도3 미만이다. 판정의 사용률 조건을 적용하며 KPI 자체는 변경하지 않는다.
최대 픽셀 차이190을 숨기지 않는다. 합성 픽셀 차이는 실사 분포 사실성 무손실 증거가 아니다.
두 번 nearest 마스크 샘플링은 경계에서 직접 한 번 샘플링과 다를 수 있고 모든 마스크는 실제 경로를 따른다.
W4 KS/분위수·도메인 AUC와 실제 W2/W6 학습 연결은 NOT_RUN이다. phone-curl은 experimental-unfitted 유지.

## 8. 다음 단계 / 필요한 결정 / 블로커
Linux CI 통과 후 승인된 ≤30% 조건으로 draft 해제 상태에서 squash 병합한다.
W6 T6.0 CPU 학습 측정 뒤 데이터 생성 속도 필요량을 다시 정한다. 현재 추가 승인 요청 없음.
