# W1 — 플랫폼·계약 구현 지시서

| 항목 | 값 |
|---|---|
| 투입 | **Wave A (즉시)** |
| 소유 경로 | 루트 설정 파일, `.github/`, `src/clavis/{contracts,core,cli,pipeline}`(pipeline은 골격만, 통합은 W8), `training/jobs/`, `models/MANIFEST.json`, `scripts/` |
| 필독 | CONTRACTS.md 전체, PLAN.md 6.4–6.6절, GENERALIZATION_CHARTER.md 4·6절 |
| 하류 | 전 워커. **네가 계약 패키지 v0.1을 병합하는 시점이 Wave B의 출발 신호다** |

## 1. 미션

모든 워커가 같은 약속 위에서 병렬로 일할 수 있는 바닥을 만든다. 저장소, CI, 계약 패키지(IR 스키마, LSTL, 문법 오토마톤), 좌표·fixed-point 코어, CLI·파이프라인 골격, 모델 레지스트리, 결정성 하네스, **노트북용 재개 가능 배치 실행기**가 네 산출물이다. **인식 로직은 구현하지 않는다.**

이 프로젝트는 GPU를 쓰지 않는다(PLAN v1.1). 학습, 렌더링, 야간 평가가 모두 사용자의 노트북 한 대에서 돈다. 네 배치 실행기가 그 노트북을 여러 워커가 안전하게 나눠 쓰게 하는 장치다.

## 2. 범위

- 범위: 위 소유 경로 전부, CI 워크플로, 무결성 도구(W4 제작)의 CI 연결
- 범위 밖: 각 단계의 인식 알고리즘, 평가 지표, 데이터 생성

## 3. 작업 목록

### T1.1 저장소 부트스트랩

- `git init`. D5 결정에 따라 비공개 GitHub 저장소와 연결한다. 결정 전이면 로컬 저장소로 시작한다.
- `pyproject.toml`(uv, Python 3.12). 의존성 그룹은 `runtime`, `service`, `training`, `eval`, `dev`로 나눈다.
- PLAN.md 6.5절의 디렉터리 골격과 각 디렉터리 `README.md`(소유자, 목적)를 만든다.
- `.gitattributes`(`* text=auto eol=lf`, 바이너리 지정), `.gitignore`(`data/**`, `models/**`에서 `models/MANIFEST.json`과 `data/manifests/**`는 제외, `.venv`, 사적 경로)
- ruff, mypy, pytest 설정. pre-commit.
- `CODEOWNERS`: 경로를 워커 핸들(`@astra-w1` … `@astra-w9`, 자리표시자)에 대응시킨다.
- PR 템플릿: 헌장 8절 체크리스트, 보고서 링크, 평가 보고서 링크. 이슈 템플릿: CCR, ADR, 버그.
- **CI**(GitHub Actions): `ubuntu-latest`와 `windows-latest` × Python 3.12에서 lint, type, test, schema 검증을 돌린다. import 방향 검사(import-linter), 의존성 라이선스 검사(pip-licenses 허용 목록, 00_COMMON.md 12절)도 넣는다. 하드코딩 스캐너 자리를 만들어 두고 W4 도구가 오면 연결한다.
- 수용 기준: 두 OS에서 CI 통과. 새 PC에서 `uv sync` 후 테스트가 도는 절차를 README에 PowerShell과 bash 모두로 적는다.

### T1.2 계약 패키지 v0.1 (`src/clavis/contracts/`)

- CONTRACTS.md 3절(IR)과 8절(출력)의 모든 객체를 pydantic v2 모델로 만든다. 열거형, 오류 코드, `schema` 상수도 포함한다.
- JSON Schema 자동 생성 스크립트를 만들고 결과를 `src/clavis/contracts/schemas/*.json`에 커밋한다. 스키마 스냅샷 테스트를 둔다.
- `tests/fixtures/contracts/`: 객체마다 유효 예시 1개 이상과 무효 예시 여러 개. **Wave B 워커가 mock으로 쓸 수 있을 만큼 현실적으로** 만든다. 예: 3시스템 리드시트 한 쪽 분량의 `PageLayout`, `StaffLattice`, `TextIR`, `ScoreIR`.
- 정규 JSON 작성기: 키 정렬, UTF-8, LF, NaN 금지, IR 덤프의 실수 자릿수 고정.
- 수용 기준: 모든 fixture가 검증을 통과한다. 모델 → JSON → 모델 왕복이 같다. 무효 fixture는 모두 거부된다.

### T1.3 코어 유틸 (`src/clavis/core/`)

- Fraction 직렬화, 음높이 타입, **ID 생성기**(CONTRACTS.md 1.1절)
- **fixed-point 코덱**: px → µ(절댓값 round-half-up 후 부호 복원), 행렬 nanounit, homography 정규화(`m[8] = 1`, 안전 임계값 미만이면 오류)
- **프레임·변환 그래프**: homography 합성·역변환, dewarp mesh 순방향·역방향 대응, strip 박스를 `original` 프레임의 외접 사각형으로 옮기는 함수(CONTRACTS.md 2절)
- 해시(바이트, 픽셀), 결정적 정렬 도우미
- 설정 로더(YAML → pydantic)와 **상수 레지스트리 검증기**: 단위 열거형, `source: fit`이면 `fitted_on`, `metric`, `evidence` 필수
- 수용 기준: hypothesis 속성 시험(역변환∘합성 ≈ 항등, 오차 1e-6 px 이내), fixed-point 시험 벡터(CONTRACTS.md 12.3절 규칙)를 통과한다. 출처 없는 fit 상수는 거부한다.

### T1.4 LSTL 코어 (`src/clavis/contracts/lstl/`)

- CONTRACTS.md 4절의 데이터 모델, 검증기(type별 허용 속성과 값 범위), **정규화기**(열 정보가 있는 항목 목록 → 정규 순서), 텍스트 직렬화·파서(4.3절)
- 헤드별 정수 어휘 파일 `lstl-0.1-vocab.json`(버전과 해시 기록)
- **문법 오토마톤**: `allowed(state) → 속성별 허용 값`, `advance(state, item) → state`. 순수 Python/numpy로 구현해 W6 읽기 구성기, W8 제약 해석, W4 평가 도구가 함께 쓴다. 순서 제약(예: `chord=1`은 같은 열의 `note` 뒤에만)을 강제한다.
- 수용 기준: golden 파일 20개 이상 왕복. 무효 사례 30개 이상 거부. 오토마톤이 golden 시퀀스를 모두 받아들이고 무효 시퀀스를 모두 거부한다.

### T1.5 파이프라인 골격과 CLI

- 단계 인터페이스 `Stage.run(...) -> IR`, 단계 레지스트리, 설정 주입, 단계별 시간과 RSS 표본(psutil) → `runtime.json`
- `--debug`면 단계별 IR을 덤프한다.
- **mock 단계**: 각 단계가 fixture를 돌려주게 해 첫날부터 `clavis recognize`가 끝까지 돈다. mock이 있는 출력은 `status=blocked`, 진단 `MOCK_STAGE`로 표시한다.
- CLI: CONTRACTS.md 9절의 `recognize`, `selfcheck`, `version`, 종료 코드, 마지막 줄 요약 JSON
- 수용 기준: Windows와 Linux에서 `clavis recognize tests/fixtures/images/blank.png --out <tmp>`가 스키마에 맞는 파일 일체를 만든다.

### T1.6 모델 레지스트리

- `models/MANIFEST.json` 스키마(이름, 버전, SHA-256, 크기, 라이선스, 학습 데이터 manifest digest, 설정 digest, 지표 보고서 경로)
- `scripts/fetch_models.py`: 설정된 저장소(로컬 경로 또는 URL)에서 받아 해시를 검증한다.
- 런타임 로더는 해시가 맞지 않는 모델을 거부한다. `clavis selfcheck`가 이를 검사한다.

### T1.7 결정성 하네스

- `scripts/determinism.py`: 표본 입력마다 CLI를 1·4스레드로 3회 실행하고 `runtime.json`을 뺀 출력을 바이트 비교한다. 보고서를 만든다.
- CI 작업으로 등록한다(OS별). Windows와 Linux 결과를 artifact로 올려 OS 간 일치율을 보고한다.

### T1.8 CI 무결성 연결

- import-linter 규칙: `src/clavis`는 `training`과 `eval`을 import하지 못한다. `eval`은 `src/clavis.contracts`와 공개 출력 파서만 import한다.
- W4의 하드코딩 스캐너와 누출 검사를 필수 작업으로 연결한다. nightly 워크플로 골격(새 시드 합성 시험, 규칙 ablation)을 만든다.

### T1.9 CPU 학습 환경과 배치 실행기 (`training/jobs/`)

- uv 의존성 그룹 `training`: PyTorch **CPU 휠**, LightGBM, scikit-learn, 렌더링 도구 래퍼. CUDA 이미지는 만들지 않는다.
- **재개 가능한 배치 실행기**:
  - 단일 큐로 무거운 작업(학습, 렌더링, SYN-Val 평가)을 **동시에 하나만** 돌린다.
  - 작업마다 스레드 수 ≤ 8, RAM ≤ 3 GB 상한과 벽시계 상한(기본 4시간)을 적용한다. 넘으면 중단하고 보고한다.
  - 체크포인트 규약(작업이 주기적으로 상태를 저장하고, 재시작 시 이어서 진행)을 정의하고 예제를 둔다.
  - 실행 창 설정: 사용자가 정한 시간대(예: 밤 11시–아침 7시)에만 돌거나, 사용자가 수동으로 시작·중지한다. 사용자가 노트북을 쓰기 시작하면 멈출 수 있어야 한다.
  - 디스크 여유가 3 GB 아래로 떨어지면 새 작업을 시작하지 않는다.
  - 작업별 CPU 시간, 최대 RSS, 결과 경로를 실험 레지스트리에 남긴다.
- 실험 레지스트리(ADR-002): MLflow 로컬 파일 저장소나 JSONL 중 하나를 고른다. 모든 학습 실행이 설정, 시드, 데이터 digest, git SHA, CPU 시간을 남기게 한다.
- (선택) 무료 클라우드 CPU 노트북에서 같은 작업을 돌리는 템플릿. 사적 데이터 업로드를 막는 검사를 넣는다.

## 4. 첫 PR (착수 48시간 목표)

1. T1.1 골격 + CI(두 OS lint/test) + PR 템플릿 + CODEOWNERS
2. 바로 이어서 T1.2 계약 패키지 v0.1(스키마, fixture). **병합되면 Orchestrator에게 Wave B 투입 가능을 보고한다.**

## 5. 수용 기준 요약 (게이트 연결)

- G0: T1.1–T1.4, T1.8 완료. T1.5는 mock으로 끝까지 실행. T1.9 배치 실행기 v0(단일 큐, 자원 상한, 재개)
- G1: T1.5–T1.7, T1.9 완료. 실제 단계로 교체된 파이프라인에서 결정성 통과

## 6. 이 역할의 함정

- 계약의 모호함을 코드로 조용히 결정하지 않는다. 모호하면 CCR 초안을 써서 Orchestrator에게 묻는다.
- 골격을 만들며 다른 워커의 알고리즘을 먼저 구현하지 않는다. mock은 fixture를 돌려줄 뿐이다.
- 의존성을 늘리지 않는다. 런타임 의존성 목록은 00_COMMON.md 4절이 상한이다.

## 7. 초기 ADR

- ADR-001 패키징·도구(uv, ruff, mypy, import-linter, pip-licenses)
- ADR-002 실험 레지스트리
- ADR-008 설정·상수 레지스트리 형식
