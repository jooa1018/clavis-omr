# [W7] main·계약 0.1.1 반영과 OR-005 재검증 — 2026-10-09
판정: PASS (호출 경계의 main 호환성·로컬 검증 범위; 실제 OCR은 미완료)

## 1. 요약 (3줄 이내)
#29/#38/#39/#40/#41을 main 91cbda7에서 반영하고 잠금 환경을 동기화했다.
RAM 24 GB 환경의 OR-005 슬롯으로 Windows 전체 792개 시험이 통과했다.
CCR-0002 #24는 [W1 확인]과 문서 CI PASS 후 squash 병합했다(0fa3fa0).

## 2. 변경 (PR 링크, 주요 파일·모듈)
- 구현 PR: https://github.com/jooa1018/clavis-omr/pull/31
- 정오표 PR: https://github.com/jooa1018/clavis-omr/pull/24
- W7 런타임 수정 없음. 모듈 README의 의존성·계약·실행법을 최신 상태로 갱신했다.
- 집계: 2026-10-09-main-validation.json. 원문 JUnit·로그·개인 경로는 커밋하지 않는다.

## 3. 계약·결정 (사용한 계약 버전, CCR·ADR 번호)
현재 clavis-ir-0.1.1 / lstl-0.1.1, CCR-0003. 같은 열의 다른 성부는 join=1이다.
공통 파서·오토마톤은 clavis.contracts.lstl에 있다. 현재 W7 raw 경계는 IR/LSTL을
생산하지 않아 버전/필드 코드 이관은 없으며, 향후 TextIR 생산자는 공통 모델을 사용한다.
CCR-0002의 v0.1 정오표 승인 이력은 현행 0.1.1을 되돌리지 않는다.
[W1 확인]: https://github.com/jooa1018/clavis-omr/pull/24#issuecomment-6075214694

## 4. 검증 (테스트 수, CI 결과, 결정성, 스캐너, 라이선스 스캔)
실행 장소: 로컬 Windows, 사용자 요청 수동, RAM 24 GB(16+8). 증설 전 결과와 혼합하지 않는다.
uv 실행 파일은 PATH 대신 work/uv.exe를 사용했다. 실제 명령:

```text
uv sync --locked --all-groups
uv run --locked --all-groups python -m training.jobs.short run pytest tests/ --cov=clavis --cov=scripts --cov=eval --cov=training.jobs --cov-report=json:work/resume-coverage.json --junitxml=work/resume-tests.xml
uv run --locked --all-groups python -m training.jobs.short run training.models.text.smoke --out work/resume-smoke.json
```

- 전체 792 passed, 실패/오류/skip 0. W7 42개, text 런타임 라인 커버리지 100%.
- 슬롯 succeeded, wall 123.6559999999954 s, 표본 CPU 84.046875 s,
  표본 peak RSS 297848832 bytes, cpuLimit=2. JUnit 시험 시간 115.427 s.
- CTC 실제 Python 1/4 workers 각 3회 바이트 동일 시험 포함. 실제 PP-OCR 수치 결정성 NOT_RUN.
- ruff lint/format, mypy 75개 파일, import 계약 2개, runtime 전이 라이선스,
  H1–H9·개인정보 스캔, coverage 4개 게이트, wheel 명세 자산 검사 PASS.
- 필수 contracts 298개 및 integrity positive/negative 24개 PASS.
- #24 문서 CI PASS: https://github.com/jooa1018/clavis-omr/actions/runs/37891001787
  quality는 문서 전용 라우팅으로 SKIPPED이며 런타임 CI 통과로 간주하지 않는다.
- #31 원격 CI는 이 보고서 작성 시 준비 완료 전환 전이다. 현재 공개 저장소 정책상
  Linux·Windows 모두 확인하고 병합한다. 결과는 PR checks와 병합 기록에서 확인한다.

## 5. 지표 (평가기 JSON 경로 + 핵심 수치 표: 이전 대비 변화와 95% CI, 슬라이스별)
집계 JSON smoke: 합성 CTC 텐서 12/12, 3회 동일, rule off 시 12 abstain.
**SYN-Val 아님; 이미지 OCR 정확도 아님.** W4 인식 평가기 JSON은 없다.
실사/Dev/SYN-Val·CER·검출 재현율·95% CI·페이지 지연은 NOT_RUN. sealed 미접근.

## 6. 일반화 점검 (헌장 8절 체크리스트, 실패 패턴 패키지 첨부 여부)
인식 결과 변경·실사 튜닝·새 상수·규칙·모델·의존성 선택 없음.
기존 TEXT-CTC-001·provisional 자원 상한을 유지한다. 실패 이미지 유래 수정이 아니다.
학습/렌더/실제 OCR 실행 없음. 모든 전체 시험·합성 tensor smoke에 OR-005를 적용했다.

## 7. 알려진 한계와 실패 사례 (숨기지 말 것)
이전 디스크 부족 5건은 이번 전체 시험에서 재현되지 않았다. W4의 시험 코드 자체는 수정하지 않았다.
현재 코드는 실제 PP-OCR 이미지 입력 연결, 코드 문법 decoder, TextIR 출력을 아직 제공하지 않는다.
W2 artifact 등록·확인은 대기 중이며 모델 파일 취득·git 포함·OCR 재학습은 하지 않았다.

## 8. 다음 단계 / 필요한 결정 / 블로커
#31 원격 CI 통과 후 B등급 squash 병합. 이후 승인된 코드 문법·어휘 시험과 실제 PP-OCR 연결.
모델과 한·영 폰트의 URL/라이선스/SHA-256 및 [W2 확인]을 받아 모델별 전처리·사전을 고정한다.
소형 CRNN은 배치 큐에서만 학습하고 비교 측정 전 채택하지 않는다.
