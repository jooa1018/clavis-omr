# W9 — 서비스·패키징·통합 구현 지시서

| 항목 | 값 |
|---|---|
| 투입 | **Wave C** (G1 통과 후. 규약 적합성 시험 설계는 그 전에 시작해도 된다) |
| 소유 경로 | `src/clavis/service/`, `deploy/`, `docs/integration/`, `tests/service/`, `configs/service/` |
| 필독 | **CONTRACTS.md 8–12절**; PLAN.md 6.4절(예산), 13절 D5·D7; EVALUATION.md 7.3절(sealed 실행용 동결 빌드) |
| 상류 | W8(파이프라인과 출력, rejected-output 조립), W6·W5·W7(모델, 성능 협업) |
| 하류 | HarmonyMaker(provider로 호출), Custodian(동결 빌드) |

## 1. 미션

엔진을 **HarmonyMaker가 그대로 부를 수 있는 서비스와 로컬 실행기**로 만든다. 기존 Audiveris provider와 같은 HTTP 규약을 구현해, HarmonyMaker는 작은 어댑터만 추가하면 된다. 참조 노트북에서 예산 안에 돌고, 오프라인이며, 재현 가능한 빌드로 배포한다. **HarmonyMaker 저장소는 수정하지 않는다.** 필요한 HarmonyMaker 측 변경은 설계서로 넘긴다.

## 2. 범위

- 범위: HTTP 서비스, job 저장소, 로컬 실행기(CLI 완성), 패키징(Docker, Windows), 성능 최적화, 규약 적합성 시험, 보안, 릴리스와 동결 빌드, HarmonyMaker 어댑터 설계서
- 범위 밖: 인식 알고리즘, 평가, HarmonyMaker 코드 변경

## 3. 작업 목록

### T9.1 HTTP 서비스 (ADR-007: FastAPI + uvicorn 권장)

- CONTRACTS.md 10절의 엔드포인트, 요청과 응답 모양을 **키 집합까지 정확히** 구현한다.
- 인증: Bearer 키(32–512자), 상수 시간 비교
- 크기 한도: 일반 JSON ≤ 64 KiB, 오류 ≤ 4 KiB, 결과 MusicXML ≤ 4 MiB, 확장 엔드포인트 ≤ 4 MiB, 페이지 PNG 크기와 픽셀 수 한도
- **멱등성**: 같은 `Idempotency-Key`와 같은 본문이면 같은 응답을 준다. 같은 키에 다른 본문이면 확정 거절(4xx)한다. 업로드는 `X-Page-Digest`와 본문 SHA-256이 같아야 한다.
- 상태 기계: created → (업로드) → queued → processing(progressBp) → completed / failed(code, message) / cancelled. 상태 조회는 부작용이 없어야 한다.
- 작업 저장소: 작업별 디렉터리, 원자적 상태 파일, 기본 1시간 TTL 후 삭제, 소유자 삭제(파일 생성 중이면 작업이 끝난 뒤 삭제해 재생성을 막는다)
- 실행: 기본 동시 1건(설정 가능)의 작업 큐. 취소는 단계 사이 협조적 검사로 하고, 제한 시간을 넘으면 자식 프로세스를 종료한다.
- `completed`는 엔진 상태가 complete일 때만이다. partial이면 `failed(CLAVIS_OUTPUT_INCOMPLETE)` + `/rejected-output`(W8 조립 함수), blocked, OOD, retake면 해당 오류 코드다.

### T9.2 로컬 실행기 (HarmonyMaker `/local-image` 경로)

- CONTRACTS.md 9절 CLI를 완성한다(종료 코드, 마지막 줄 요약 JSON).
- `deploy/windows/install.ps1`: uv venv 생성, 설치, 모델 내려받기와 해시 검증, `clavis selfcheck`. 새 Windows 사용자 프로필에서 동작하는지 확인한다.
- HarmonyMaker는 이 CLI를 자식 프로세스로 부른다. Windows Job Object 자원 제한은 HarmonyMaker 쪽 책임이다. 너는 필요한 메모리와 시간 수치를 문서로 제공한다.

### T9.3 패키징

- Linux Docker 이미지: CPU 전용, non-root, 헬스체크, 환경 변수 설정, 고정된 의존성과 모델 해시. **런타임 외부 네트워크 호출 0**(시험 중 소켓 차단으로 검증)
- 이미지 크기와 콜드 스타트를 보고한다. 서버 최소 사양(1 vCPU / 2 GB)에서의 지연과 메모리를 측정한다(D7 근거).

### T9.4 성능 최적화

- REF-LAPTOP에서 단계별로 프로파일링한다. ONNX Runtime 세션 옵션(스레드, 그래프 최적화, 메모리 arena), 모델 선로딩, strip 배치, 불필요한 복사 제거를 적용한다.
- 예산(PLAN.md 6.4절): p50 ≤ 20 s/쪽, p95 ≤ 45 s, RSS ≤ 1.5 GiB, 콜드 스타트 ≤ 5 s
- CI 성능 회귀 시험: 작은 fixture의 시간과 메모리 상한(허용 오차 포함)
- **최적화가 출력을 바꾸면 안 된다.** 결정성 하네스와 전후 바이트 비교로 확인한다. 바뀌면 인식 변경으로 취급해 헌장 5절 절차를 거친다.

### T9.5 규약 적합성 시험 스위트

- HarmonyMaker 어댑터가 기대하는 것을 블랙박스 HTTP 시험으로 만든다: capabilities 정확 키, 상태 JSON 모양, 409 의미, 멱등성, 크기 한도, 삭제와 보존 응답, rejected-output 형식(CONTRACTS.md 12.4절)
- OpenAPI 명세, Python 예시 클라이언트, TypeScript 타입 정의 파일(HarmonyMaker 팀 참고용 문서)

### T9.6 HarmonyMaker 어댑터 설계서 (`docs/integration/HARMONYMAKER_ADAPTER.md`)

- `OmrVendorAdapter` 메서드와 엔드포인트의 대응표
- HarmonyMaker 측에 필요한 변경:
  - `vendorId: "clavis"`를 받는 새 어댑터 클래스(기존 Audiveris 어댑터는 vendorId를 고정 검사함)
  - `REJECTED_OUTPUT_CODES`에 `CLAVIS_OUTPUT_INCOMPLETE` 추가
  - 확장 엔드포인트(evidence, hints)를 위한 별도 크기 한도 판독기
  - `evidence.vendorTargetId`(MusicXML `id`) → Source target 대응
  - (후속) review hints → `OmrReviewItem` 변환
  - `/local-image` 실행 명령 교체
- 전환 계획: 기능 플래그, Dev에서 기존 경로와의 A/B 비교, 되돌리기 절차. HarmonyMaker 쪽에서 작성할 시험 목록.
- **이 설계서는 HarmonyMaker 워커에게 따로 전달한다.** 이 저장소에서 HarmonyMaker를 고치지 않는다.

### T9.7 보안

- 입력 검증: magic byte, 픽셀 폭탄, PNG 압축 해제 한도, (CLI) PDF 페이지와 객체 한도
- 경로 조작 방지, 작업별 임시 디렉터리 격리, 로그 정제(이미지 내용, 키, 사적 경로 금지)
- 엔진 수준 동시성 보호. 사용자 할당량은 HarmonyMaker 몫이다.

### T9.8 릴리스와 동결 빌드

- 버전 규칙(semver). `buildDigest` = 코드 SHA + 모델 SHA 목록 + 설정 digest의 정규 해시
- **Custodian용 동결 빌드 패키지**: 잠긴 의존성, 모델, 체크섬, 실행 스크립트, W4 sealed 실행기를 묶는다. 다시 빌드해도 같은 `buildDigest`가 나와야 한다.
- 릴리스 노트 양식: 변경, 지표(Dev), 알려진 한계, 호환성

## 4. 첫 PR (투입 후 1주 목표)

규약 적합성 시험 스위트를 **먼저** 만든다. W1 CLI를 부르는 최소 HTTP 서비스로 시험을 통과시킨다. 인식은 mock이어도 된다.

## 5. 수용 기준

| 항목 | G3 | G4 |
|---|---|---|
| 규약 적합성 스위트 | 100% 통과 | 100% 통과 + HarmonyMaker E2E(HarmonyMaker 측) |
| 성능 예산 (REF-LAPTOP) | 충족 | 충족 + 서버 사양 측정 |
| 오프라인 검증(소켓 차단) | 통과 | 통과 |
| Windows 설치 스크립트 | 새 프로필에서 통과 | 유지 |
| 동결 빌드 재현성 | 같은 buildDigest | 유지 |
| HarmonyMaker 어댑터 설계서 | 제출 | 반영 결과 확인 |

## 6. 이 역할의 함정

- **"거의 같은" 규약은 틀린 규약이다.** HarmonyMaker는 키 집합을 정확히 검사한다(`hasExactKeys`). 필드 하나가 더 있어도 계약 위반으로 떨어진다.
- 성능을 위해 모델을 바꾸거나(양자화, 해상도 축소) 단계를 건너뛰는 것은 인식 변경이다. W6·W5와 합의하고 평가 절차를 거친다.
- HarmonyMaker 저장소를 직접 고치고 싶어진다. 고치지 말고 설계서로 넘긴다(독립성 원칙).

## 7. 초기 ADR

- ADR-007 서비스 프레임워크와 작업 실행 모델
