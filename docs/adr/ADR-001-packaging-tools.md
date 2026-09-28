# ADR-001 — 패키징·도구

상태: W1 제안, Orchestrator 리뷰 대기 · 2026-09-29

## 선택지와 근거
지시서 T1.1은 Python 3.12, uv, ruff, mypy, pytest, import-linter,
pip-licenses를 지정한다. 별도 도구 체계는 도입하지 않는다.
패키지 빌드는 Hatchling(MIT)을 사용하며 배포 범위는 `src/clavis`뿐이다.
학습·평가 경로는 import-linter 분석용 패키지로만 둔다.

## 구현
`uv.lock`으로 두 OS의 의존성을 고정한다. `uv sync` 기본 그룹은 runtime과 dev다.
service/training/eval 그룹은 예약했으며 담당 구현이 추가될 때 채운다.
CPU PyTorch 의존성은 T1.9에서 명시적 CPU 인덱스로 연결한다.
현재 실제 런타임 의존성은 pydantic 및 그 전이 의존성이다.
pip-licenses의 미확인·복합 라이선스는 자동 승인하지 않는다. MPL은 수정 없는 패키지만 허용한다.
전체 개발 도구 목록을 엔진 라이선스 검사 대상으로 오인하지 않도록 런타임 의존성 폐쇄를 검사한다.

## 초기 저장소와 리뷰
기존 문서만 `w1/bootstrap-docs`에 첫 커밋·push하고 GitHub에서 그 브랜치를 `main`으로
이름 변경했다. main에 직접 push하지 않았으며 골격은 `w1/platform-bootstrap` PR로 제출한다.
CODEOWNERS는 지시서의 워커 자리표시자를 사용한다. 실제 승인 권한을 제공하지 않으므로
Orchestrator가 실계정 대응을 지정해야 한다. CI 통과만으로 승인이나 병합을 대신하지 않는다.

## 검증 / 되돌릴 조건
두 OS의 lint/type/test/import/license 결과는 T1.1 보고서에 기록한다.
빌드가 training/eval을 포함하거나 잠금 환경이 재현되지 않으면 설정을 수정하고 재검증한다.
W4 검사와 계약 검사는 아직 NOT_RUN이며 T1.8/T1.2 게이트 통과로 간주하지 않는다.

참고: [uv dependency groups](https://docs.astral.sh/uv/concepts/projects/dependencies/),
[CPU index](https://docs.astral.sh/uv/guides/integration/pytorch/),
[Import Linter contracts](https://import-linter.readthedocs.io/en/v2.7/contract_types.html).
