# 00 — 모든 Astra 워커 공통 작업 규칙

## 1. 너의 위치

- 너는 Clavis 프로젝트의 Astra 워커 **Wn**이다. 설계 권한은 Orchestrator(Opus 5.5)에게 있다. 너는 지시서 범위 안에서 설계를 **구현**하고, 근거를 **측정**하고, 결과를 **정직하게 보고**한다.
- 지시서가 모호하면 가장 보수적인 해석을 택하고 보고서에 적는다. 해석이 결과를 크게 바꾸면 멈추고 에스컬레이션한다(8절).
- 다른 워커의 소유 경로(PLAN.md 6.5절)는 직접 고치지 않는다. 그 소유자에게 PR 리뷰를 요청하거나 CCR을 낸다.

## 2. 읽기 순서

1. `AGENTS.md`
2. 이 문서
3. 자기 지시서 `docs/tasks/Wn_*.md`
4. `docs/GENERALIZATION_CHARTER.md` 전체
5. `docs/CONTRACTS.md` 중 지시서가 지정한 절
6. `docs/PLAN.md` 5, 6, 10절
7. `docs/EVALUATION.md` 중 지시서가 지정한 절

## 3. 작업 방식

- **브랜치**: `w{n}/<짧은-주제>`(예: `w5/staff-unet`). main에 직접 push하지 않는다.
- **PR**: 한 PR은 한 가지 목적이다. 가능하면 변경 400줄 이하로 유지한다(생성 파일 제외). PR 템플릿의 헌장 체크리스트를 모두 채운다.
- **커밋**: Conventional Commits(`feat(geometry): …`, `fix(eval): …`, `docs(adr): …`).
- **리뷰와 병합 등급**: 모든 워커가 같은 GitHub 계정을 쓰므로 GitHub 승인 기능 대신 다음 절차를 따른다.
  - **A등급(Orchestrator 승인 필요)**: `src/clavis/contracts/`, `tests/contracts/`, `docs/`(단 `docs/reports/`, `docs/adr/`·`docs/ccr/`의 초안 제외), 평가기 지표·정렬 정의 변경, `configs/integrity/allowlist.yaml`, 임계값 artifact, CI 검사를 약하게 하는 변경, ADR 채택. 워커가 PR과 보고서를 올리면 사용자가 Orchestrator 판정을 받아 PR 코멘트("Orchestrator 승인, 날짜")로 남긴 뒤 병합한다.
  - **B등급(워커 자체 병합)**: 자기 소유 경로 안의 변경이고, CI가 통과했고, PR 템플릿을 모두 채웠고, A등급 파일이 없으면 워커가 직접 병합한다. 다른 워커의 소유 경로를 건드리면 그 워커의 확인 코멘트("[Wn 확인]")가 먼저 있어야 한다.
  - 병합 방식은 squash, main 직접 push 금지는 유지한다.
- **CCR**: 계약 변경이 필요하면 `docs/ccr/CCR-NNNN-<주제>.md`를 쓰고, 승인 전에는 그 변경에 의존하는 작업을 main에 넣지 않는다.
- **ADR**: 설계 선택(모델 구조, 형식, 라이브러리)은 `docs/adr/ADR-NNNN-<주제>.md`에 선택지, 실험 근거, 결정, 되돌릴 조건을 적는다. 아래 번호는 예약되어 있다. 새 ADR은 018부터 쓴다.

  | 번호 | 주제 | 작성 | 번호 | 주제 | 작성 |
  |---|---|---|---|---|---|
  | 001 | 패키징·도구 | W1 | 010 | LeadGen 기본 분포 | W2 |
  | 002 | 실험 레지스트리 | W1 | 011 | 열화 프리셋과 목표 interline 분포 | W3 |
  | 003 | 정규 staff-space s* | W5·W6 | 012 | 평가 정렬 알고리즘과 비용 | W4 |
  | 004 | 후보 생성기와 분류기 구조 | W6 | 013 | 오선 검출 방식 | W5 |
  | 005 | 텍스트 검출기 | W7 | 014 | 관계 추론과 읽기 구성 | W6 |
  | 006 | 신뢰도 보정 방법 | W8 | 015 | 코드 인식기 구조 | W7 |
  | 007 | 서비스 프레임워크와 작업 실행 | W9 | 016 | 가사 OCR 엔진과 음절 분할 | W7 |
  | 008 | 설정·상수 레지스트리 형식 | W1 | 017 | 제약 해석 탐색과 N-best 재조합 | W8 |
  | 009 | 데이터 shard 형식 | W2 | | | |
- **Mock 우선**: 상류 산출물이 없으면 계약 fixture(`tests/fixtures/contracts/`)로 개발한다. 상류를 기다리며 멈추지 않는다.

## 4. 코딩 표준

- Python 3.12, 환경 관리는 uv, 린트·포맷은 ruff, 타입 검사는 mypy(`contracts`, `core`는 strict), 테스트는 pytest. 속성 기반 테스트에는 hypothesis를 권장한다.
- **엔진 런타임 의존성**(`src/clavis`)은 numpy, opencv-python-headless, pillow, pypdfium2, onnxruntime, xmlschema, elementpath, pydantic, (서비스) fastapi/uvicorn으로 제한한다. 새 런타임 의존성은 W1 승인과 라이선스 확인을 거친다.
- **학습 도구**(PyTorch CPU 휠, LightGBM, scikit-learn)는 `training/`에서만 쓴다. **GPU와 CUDA는 쓰지 않는다**(PLAN v1.1). 학습한 모델은 ONNX로 내보내 런타임에서 쓴다. LightGBM 모델도 ONNX로 변환하거나, 불가능하면 런타임 의존성 추가를 ADR로 제안한다.
- 로깅은 표준 `logging` 구조화 로그를 쓴다. `print`는 CLI 출력에만 쓴다. 로그에 이미지 내용이나 사적 경로를 쓰지 않는다.
- 경로는 `pathlib`로 다룬다. Windows와 Linux에서 모두 돌아야 한다. 심볼릭 링크에 의존하지 않는다. 줄바꿈은 LF다.
- 전역 가변 상태는 금지다. 난수는 `numpy.random.Generator`에 시드를 명시해 쓰고, **`src/clavis` 추론 경로에서는 난수를 쓰지 않는다.**
- 상수는 `configs/<module>/constants.yaml` 레지스트리에 둔다(헌장 4절).
- 공개 함수에는 타입 힌트를 단다. 주석은 "왜"만 적는다. 수식이나 이론 규칙에는 출처를 단다.

## 5. 데이터와 모델 취급

- 데이터와 모델 바이너리는 git에 넣지 않는다. git에는 manifest(JSON: 경로, SHA-256, 크기, 라이선스, 출처, 분할)만 넣는다.
- 사적 데이터(R-TGT, R-LEGACY)는 환경 변수 `CLAVIS_PRIVATE_ROOT`가 가리키는 저장소 밖 경로에만 둔다. 어떤 클라우드 환경에도 올리지 않는다.
- 모델 가중치는 `models/MANIFEST.json`에 이름, 버전, SHA-256, 학습 데이터 manifest digest, 학습 설정 digest, 지표 보고서 경로, 라이선스를 등록한다. 런타임은 manifest 해시가 맞는 가중치만 읽는다.
- 모든 학습 실행은 설정 파일, 시드, 데이터 manifest digest, git SHA를 실험 레지스트리에 남긴다.

## 6. 완료 정의 (Definition of Done)

- [ ] 코드와 테스트가 있다. 새 로직의 라인 커버리지 ≥ 80%(모델 학습 스크립트 제외)
- [ ] ruff, mypy, pytest가 Linux와 Windows CI에서 통과한다
- [ ] 산출 IR과 파일이 계약 JSON Schema 검증을 통과한다
- [ ] 엔진 모듈은 결정성 시험(같은 입력 3회, 1·4스레드)을 통과한다
- [ ] 새 상수는 레지스트리에 등록했다. 하드코딩 스캐너 결과가 깨끗하다
- [ ] 의존성 라이선스 스캔이 깨끗하다
- [ ] 모듈 README를 갱신했다. 결정이 있었으면 ADR을 남겼다
- [ ] 인식에 영향이 있으면 Dev 전체와 SYN-Val 비교 보고서를 첨부했다(헌장 5절)
- [ ] 7절 양식의 보고서를 `docs/reports/Wn/`에 저장했다

## 7. 보고서 양식 (2쪽 이내. 상세는 첨부 파일로)

```markdown
# [Wn] <작업 ID> 보고 — YYYY-MM-DD
판정: PASS | PARTIAL | FAIL | BLOCKED | NOT_RUN

## 1. 요약 (3줄 이내)
## 2. 변경 (PR 링크, 주요 파일·모듈)
## 3. 계약·결정 (사용한 계약 버전, CCR·ADR 번호)
## 4. 검증 (테스트 수, CI 결과, 결정성, 스캐너, 라이선스 스캔)
## 5. 지표 (평가기 JSON 경로 + 핵심 수치 표: 이전 대비 변화와 95% CI, 슬라이스별)
## 6. 일반화 점검 (헌장 8절 체크리스트, 실패 패턴 패키지 첨부 여부)
## 7. 알려진 한계와 실패 사례 (숨기지 말 것)
## 8. 다음 단계 / 필요한 결정 / 블로커
```

- 수치는 **평가기 출력 JSON에서 복사**한다. 손으로 계산한 수치는 쓰지 않는다.
- dev/sealed, 합성/실사, 자동/수동, 실행 장소(노트북/무료 클라우드 CPU)를 항상 구분해 적는다. 학습과 배치 작업의 CPU 벽시계 시간도 적는다.

## 8. 에스컬레이션 (멈추고 Orchestrator에게 묻는 경우)

1. 계약을 바꿔야 할 때(→ CCR)
2. 설명할 수 없는 지표 회귀가 있을 때
3. 라이선스가 불확실한 코드, 모델, 데이터, 폰트를 쓰고 싶을 때
4. 없는 데이터(특히 실사 데이터나 정답)가 필요할 때(→ Custodian 요청은 Orchestrator를 거친다)
5. sealed 데이터에 노출됐거나 노출이 의심될 때(즉시)
6. 특정 이미지에서만 효과가 있는 수정밖에 떠오르지 않을 때
7. 시간이나 컴퓨트가 추정의 2배를 넘을 때, 또는 CPU 4시간 안에 학습할 수 없는 모델이 필요해 보일 때
8. 다른 워커의 소유 코드와 충돌할 때

**자체 판단 금지 사항**: KPI나 목표 수치 변경, 평가기 변경(W4 제외), 새 라이선스 계열의 의존성 추가, 경로 소유권 변경, main 직접 push, 데이터 삭제, 승인되지 않은 클라우드 비용 지출.

## 9. 판정 어휘

| 판정 | 뜻 |
|---|---|
| PASS | 수용 기준을 모두 측정했고 모두 충족 |
| PARTIAL | 일부 충족. 미충족 항목과 이유, 계획을 명시 |
| FAIL | 측정했고 미충족 |
| BLOCKED | 외부 의존(데이터, 컴퓨트, 결정) 때문에 진행 불가. 필요한 것을 명시 |
| NOT_RUN | 실행하지 않음. 이유를 명시(PASS로 간주하지 않음) |

## 10. 자원 사용 규칙

- **GPU는 쓰지 않는다.** 학습, 렌더링, 평가가 모두 REF-LAPTOP(RAM 8 GB, 여유 디스크 약 10 GB) 한 대에서 돈다. 이 노트북은 사용자도 쓰는 기기다.
- **무거운 작업은 W1 배치 실행기의 단일 큐로만** 돌린다(동시 1개, 동시에 쓰는 연산 자원 ≤ 논리 CPU 8개, RAM ≤ 3 GB). 개발 중 짧은 실행(단위 테스트, 소규모 추론)은 큐 밖에서 해도 된다.
- **학습 시간 상한**: 모델당 벽시계 4시간(REF-LAPTOP). 넘으면 데이터나 모델을 줄이거나 ADR로 정당화한다. 모든 긴 작업은 체크포인트와 재개를 지원해야 한다.
- 저장소 데이터 총량 ≤ 4 GB, 디스크 여유 ≥ 3 GB를 유지한다.
- 무료 클라우드 CPU 노트북은 보조로만 쓴다. 한도가 바뀔 수 있으므로 필수 경로에 넣지 않고, 사적 데이터는 올리지 않는다.
- 유료 컴퓨트와 GPU는 사용자 승인 없이 쓰지 않는다(PLAN.md 7.4절 확장 규칙).

- OR-001(짧은 개발 실행): 벽시계 10분 이하, RAM 3 GB 이하, 렌더·이미지 100개 이하, 사용자가 지켜보는 수동 실행은 배치 큐 밖에서 해도 된다. 이보다 무거운 작업은 큐로만 돌린다.
- OR-005(짧은 실행 슬롯): 전체 시험, 렌더·학습·OCR smoke 등 OR-001 실행은 W1 슬롯 래퍼로 실행한다(단위 시험 몇 개는 제외). 동시 슬롯은 머신 공통 설정이며 기본 3개다. 래퍼는 연산 스레드 2, RAM 최대 3 GB, 벽시계 최대 600초를 적용하고 기존 큐의 머신 잠금을 공유해 무거운 큐 작업과 동시에 실행하지 않는다. 사용법: `uv run --locked --all-groups python -m training.jobs.short run pytest tests/`. 렌더·이미지 수는 `run --items N <module> ...`로 선언하며 100개를 넘으면 큐로 보낸다. 슬롯 설정·종료·증거 확인은 training/jobs/README.md를 따른다.
- OR-002(스캐너 이전 병합): W4 무결성 도구가 main에 들어오기 전에도 B등급 PR은 병합할 수 있다. 보고서에 NOT_RUN으로 기록하고, 도구가 들어오면 W1이 main 전체에 소급 실행하며 위반은 해당 소유자가 고친다.

- draft PR에서는 CI가 돌지 않는다. 준비 완료로 바꾸기 전에 로컬 Windows 전체 시험을 돌려 명령과 통과 수를 보고서에 남긴다. push는 작업 단위로 묶는다. main의 Windows 예약 실행이 실패하면 원인 PR 소유자가 바로 고친다.
- 공개 저장소 CI(Orchestrator 승인 및 사용자 공개 전환 완료, 2026-10-09): draft가 아닌 PR은 변경 모듈에 관계없이 Linux·Windows 두 OS에서 검사한다. docs/**와 *.md만 변경한 PR은 무거운 작업을 건너뛰고 경량 문서·개인정보 검사만 한다. main push는 Linux, main 변경이 있는 날의 일일 예약과 workflow_dispatch는 Windows로 유지한다. 워크플로 권한은 contents: read 및 필요한 API의 읽기 권한만 사용하며 pull_request_target은 쓰지 않는다.
- OR-003: 학습 편입의 보호 집합과 sealed 역방향 선별. 상세는 헌장 6·7절과 EVALUATION 8·10절(W4 반영).
- T1.9 스레드 상한 해석(Orchestrator 승인, 2026-09-29): 상한은 동시에 쓰는 연산 자원 ≤ 논리 CPU 8개다. 큐가 OMP/MKL/OPENBLAS/NUMEXPR 환경 변수와 torch intra/inter op, LightGBM num_threads, onnxruntime intra/inter op, cv2 스레드 설정을 주입하고 CPU affinity를 자식·손자까지 상속한다. Windows Job Object로 묶어 상속·일괄 종료를 보장한다. 논리 CPU가 8개 이하이면 전체 − 1개를 사용하며 Below Normal 우선순위로 실행한다. 전체 OS 스레드 수는 진단값으로만 기록한다. 실제 CPU 사용률 평균·최대를 논리 CPU 환산으로 기록하며 평균이 8 CPU를 넘으면 경고한다.

- H9 운영 예외(Orchestrator 사전 승인, 2026-10-06): training/jobs 안의 벽시계·실행 창·자원 상한 판단만 W4 확인 후 정확한 file/line/digest와 approvedBy ["W4", "orchestrator"]로 추가할 수 있다. 인식·데이터 생성·평가 판정 코드에는 적용하지 않는다.

## 11. 보안과 개인정보

- 보고서·증거 JSON·로그에 사용자명, 호스트명, 절대 경로를 기록하지 않는다. 경로는 저장소 상대 경로나 %USERPROFILE%·CLAVIS_PRIVATE_ROOT 표기로 쓴다.

- 비밀값(API 키 등)은 환경 변수로만 받는다. 코드, 로그, 보고서에 넣지 않는다.
- 사적 이미지의 내용, 가사 원문, 제목을 보고서에 적지 않는다. pageId와 해시만 쓴다.
- 입력 파서는 크기, 픽셀 수, 페이지 수, 압축비 한도를 검사한다(폭탄 입력 방어).

## 12. 라이선스 허용 목록

| 용도 | 허용 | 조건부 | 금지 |
|---|---|---|---|
| 엔진 런타임 코드·의존성 | MIT, MIT-CMU, BSD, Apache-2.0, ISC, PSF, Zlib, HPND, MPL-2.0(수정 없이 사용) | — | GPL, LGPL(정적 포함), AGPL, 상업 전용 |
| 엔진에 동봉하는 명세 스키마 | W3C Community Final Specification Agreement, W3C Software and Document License | 원본 그대로 동봉, 원본 고지·출처·SHA-256 기록, 명세 이름·버전 표기(FSA 2.2). 항목별 Orchestrator 승인. 현재 승인: MusicXML 4.0 XSD 3종 | 다른 명세·라이브러리로 확대 해석 |
| 배포 가중치 | 자체 학습(허용 데이터로), Apache/MIT/BSD 공개 가중치(예: PP-OCRv5) | CC-BY 계열 가중치(표기) | NC, ND, AGPL·GPL 코드와 결합된 가중치 |
| 학습 데이터 | PD, CC0, 자체 생성, CC-BY(표기) | CC-BY-SA(Orchestrator 승인) | NC, ND, 출처 불명, 권리 미확인 |
| 학습·평가 도구(비배포, 외부 프로세스) | 위 전부 + LGPL(Verovio), GPL(MuseScore, LilyPond) | AGPL(Audiveris, homr — `eval/baselines`에서 격리 실행만) | 엔진 코드로의 import나 코드 복사 |
| 폰트(렌더링용) | SIL OFL, Apache, PD | — | 재배포나 사용이 제한된 상용 폰트 |

AGPL·GPL 프로젝트의 소스를 참고해 **코드를 옮기지 않는다.** 아이디어는 공개 논문과 문서에서 가져온다.
