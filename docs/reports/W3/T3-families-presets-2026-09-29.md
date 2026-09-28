# [W3] T3 계열·프리셋 확장 보고 — 2026-09-29
판정: PARTIAL

## 1. 요약 (3줄 이내)
PR #6은 두 OS W3 44개 실제 통과와 OR-002에 따라 draft 해제 후 squash 병합했다(49e8dd9).
총 9계열 및 12개 실험용 경로, 비선형 라벨 변환과 RNG trace replay를 구현했다.
실사 사실성·지속 성능 PASS를 주장하지 않으며 ADR-011의 분포 해석/휨 근사 채택을 요청한다.

## 2. 변경 (PR 링크, 주요 파일·모듈)
확장 PR: https://github.com/jooa1018/clavis-omr/pull/10 (draft). 브랜치 `w3/families-presets`, 원본 worktree 변경 없음.
`training/degrade/{ops,photometric,curve,presets,smoke}.py`, 모듈 README,
`configs/degrade/presets.yaml`, `tests/degrade/test_effects.py`, ADR-011 초안.
최신 W1 training 그룹과 W2 PR #5를 main에서 반영했다. 중복 requirements는 없다.

## 3. 계약·결정 (사용한 계약 버전, CCR·ADR 번호)
공개 계약/엔진 변경 및 CCR 없음. 기존 CONTRACTS 2절 유지.
W3 내부 비선형 trace는 `matrix: null`과 순차 operations를 사용하며 homography라고 표시하지 않는다.
ADR-011은 **DRAFT**: 구간 내 uniform, 24+ 상한=현재 렌더 interline, 지원 불가능 입력 거부,
phone-curl의 sine 근사는 검토용 제안이다. 학습 기본값으로 자체 채택하지 않았다.

## 4. 검증 (테스트 수, CI 결과, 결정성, 스캐너, 라이선스 스캔)
로컬 Windows CPU 자동 합성 시험: 전체 120 PASS / 계약 fixture 1 SKIP, W3 84 PASS.
JUnit 실행 시간 17.444초, W3 라인 커버리지 97.45222929936305%.
ruff/format/루트 mypy/W3 strict mypy/import 경계/runtime license audit PASS. 새 의존성 없음.
12개 경로 각각 1·4스레드 × 3회 동일 시드/출력/trace 일치, 기록 replay 일치.
PCG64·MT19937 RNG 상태 JSON 왕복, 기존 4연산 검사, 곡선 극값/마스크/접선 검사를 포함한다.
원격 CI run 36499670575: 두 OS 모두 W3 84개 실제 통과, W3 SKIP 0.
CI 통합 checkout에는 새 W4 PR #8도 포함되어 전체 172 PASS / 계약 fixture 1 SKIP이다.
https://github.com/jooa1018/clavis-omr/actions/runs/36499670575 (코드 341c4ac).
W4 스캐너 NOT_RUN(OR-002), schema fixture NOT_RUN.

## 5. 지표 (평가기 JSON 경로 + 핵심 수치 표: 이전 대비 변화와 95% CI, 슬라이스별)
자동 근거: `families-presets-validation.json`, `families-presets-smoke.json`,
`families-presets-smoke-before.json` (모두 이 디렉터리). 인식 평가기 수치는 아니다.

| 측정 | 결과 |
|---|---|
| 기존 고정 격자 156점 최대 오차 | 0.030923823488822055 px |
| paper-wave 격자 최대 오차 | 0.0447976235569325 px (기준 ≤0.5) |
| paper-wave polyline 최대 보간 오차 | 0.24011257668263752 px (설정 ≤0.25) |
| 수동 소규모 실행 / 스레드 | 자체 합성 72쪽 / CPU 1스레드 |
| 전체 벽시계 / 최대 RSS | 6.127605500019854초 / 130215936 bytes |
| 최저 처리율 | 4 MP phone-angle: 4.816130956647241쪽/초 (5 미달) |
| 축소 중복 warp 제거 전후 | 12개 시연 PNG SHA-256 모두 동일 |

12경로 × 2.048/4 MP 전체 24슬라이스 및 개별 시간은 smoke JSON에 모두 포함했다.
슬라이스당 warmup 1회 + 측정 2회이며 지속 성능/95% CI는 NOT_RUN이다.
최초 측정 최저 4.68385062181779쪽/초에서 중복 리샘플링을 제거했으나 최종도 목표에 못 미친다.
학습/무거운 배치/GPU/유료 컴퓨트 없음. OR-001 안의 CPU 수동 개발 실행이다.

## 6. 일반화 점검 (헌장 8절 체크리스트, 실패 패턴 패키지 첨부 여부)
기하·조명·광학·해상도·압축·센서·스캔·종이·화면 9계열이다.
12경로는 지시서 이름을 모두 포함하며 `experimental-unfitted`로 표시했다.
모든 범위는 YAML에 단위/출처/근거를 기록했다. 실사/사적/sealed 접근이나 픽셀·텍스처 복사 없음.
기하 길이는 staff-space, 조명/압축 강도는 무차원이다. 입력 식별 분기/인식 규칙 추가 없음.
규칙 카탈로그/ablation 및 특정 실사 실패 패키지는 비해당. 하류 인식/학습에 연결하지 않았다.

## 7. 알려진 한계와 실패 사례 (숨기지 말 것)
4 MP phone-angle 성능 목표 미달을 숨기지 않는다. 짧은 측정으로 속도 개선 유의성을 주장하지 않는다.
W4 집계/도메인 분류기 결과가 없어 현실성 KS·분위수·AUC NOT_RUN이다.
시연은 도식 렌더다. 저해상도/이진화에서 얇은 오선이 사라지는 결과도 그대로 포함했다.
원통형 정밀 모델, caller-owned mesh cache, WebP 등 개별 확장 연산은 미구현이다.
24+ 구간을 지원하지 못하는 저해상도 원본은 거부한다. 업샘플·구간 재가중으로 감추지 않는다.
W2 최신 결과는 SVG staff-local audit이며 공개 라벨 계약으로 임의 해석해 연결하지 않았다.

## 8. 다음 단계 / 필요한 결정 / 블로커
COMMON 1·8절에 따라 **ADR-011 채택 판정 전 학습 기본값 연결과 이 확장 PR 병합을 보류**한다.
Orchestrator: 제안한 분포 상한/지원 불가능 입력 처리와 phone-curl 초기 근사를 판정해 달라.
W4: 집계/분류기 결과 수신 후 분포 수준 사실성 평가. 소유 경로나 평가기는 수정하지 않았다.
W4 스캐너 부재는 OR-002상 B등급 병합 블로커로 취급하지 않는다. 이 보고서는 G1 PASS가 아니다.
