# [W1] xmlschema 런타임 추가 — 2026-10-09
판정: PASS — 두 OS CI 완료, PR38 병합(0cd3113)

## 1. 요약 (3줄 이내)
lxml 대체 XSD 검증 의존성으로 xmlschema 4.3.2와 elementpath 5.1.4를 고정했다.
공식 PyPI wheel SHA-256을 대조하고 각 wheel의 원본 LICENSE에서 MIT를 확인했다.
원본 MusicXML XSD 3종을 로컬에서만 읽는 유효·무효 합성 XML 시험을 추가했다.

## 2. 변경 (PR 링크, 주요 파일·모듈)
[PR #38](https://github.com/jooa1018/clavis-omr/pull/38), 브랜치 w1/xmlschema-runtime. pyproject.toml/uv.lock, COMMON4 승인 목록, THIRD_PARTY_NOTICES.md.
tests/platform/test_xmlschema_runtime.py에 네트워크 차단 검증 예시를 둔다. W8 exporter 구현은 변경하지 않는다.
PR29 최종 CI PASS와 병합 결과도 기존 보고서에 반영했다.

## 3. 계약·결정 (사용한 계약 버전, CCR·ADR 번호)
Orchestrator 2026-10-09: lxml 제외, xmlschema(+elementpath) runtime 승인. 계약 v0.1 변경 없음.
MIT는 기존 허용 계열이므로 추가 라이선스 예외가 없다. 선택적 dev/docs/codegen extras를 설치하지 않는다.

## 4. 검증 (테스트 수, CI 결과, 결정성, 스캐너, 라이선스 스캔)
각 공식 wheel 및 LICENSE 파일의 출처·크기·SHA-256을 첨부 JSON에 기록했다.
runtime 폐쇄 14개 라이선스 위반 0. lxml은 runtime 폐쇄와 lock에 없다.
네트워크 socket 연결을 금지하고 allow=local, defuse=always, 로컬 namespace 매핑으로 XSD를 검증한다.
Windows 전체 시험: python -m training.jobs --root work/xmlschema-validation run --manual.
큐 작업: pytest tests/ --junitxml=work/xmlschema-tests.xml, threads=2, RAM 3 GB, 600초 상한.
Windows 전체 624 passed, 실패/skip 0, 39.955초. ruff/format/mypy66/AST/wheel PASS. [원격 두 OS CI PASS](https://github.com/jooa1018/clavis-omr/actions/runs/37818068581).

## 5. 지표 (평가기 JSON 경로 + 핵심 수치 표: 이전 대비 변화와 95% CI, 슬라이스별)
[XMLSCHEMA-LICENSE-2026-10-09.json](XMLSCHEMA-LICENSE-2026-10-09.json)에 공식 배포물·검증 집계를 기록한다.
큐 벽시계 41.203초, CPU 34.359375초, peak RSS 280756224 bytes.
로컬 Windows CPU, RAM 24 GB(16+8), DDR4-3200 듀얼 채널. 합성 자동 시험만 수행한다.
Dev/sealed/실사/학습/인식 지표/95% CI는 NOT_RUN(범위 밖).

## 6. 일반화 점검 (헌장 8절 체크리스트, 실패 패턴 패키지 첨부 여부)
인식 알고리즘·임계값·악보 식별 분기·데이터 생성 변경 없음. 인식 규칙/ablation 해당 없음.
공식 표준 XSD에 대한 합성 문자열 시험이며 실제 악보나 사적 폴더에 접근하지 않는다.

## 7. 알려진 한계와 실패 사례 (숨기지 말 것)
패키지는 원래 URL 접근 기능도 제공하므로 호출자는 시험 예시처럼 로컬 자원 제한을 명시해야 한다.
엔진용 입력 파서·자원 제한·exporter의 실제 통합 검증은 해당 소유자의 후속 작업이다.
개별 배포 wheel의 원본 고지를 보존한다. 새 명세 파일을 Clavis 소스에 복사하지 않았다.

## 8. 다음 단계 / 필요한 결정 / 블로커
두 OS CI 후 승인 범위로 squash 병합했다. 다음은 OR-005 짧은 실행 슬롯(기본 3)이다.
