# W4 — 평가·무결성 구현 지시서

| 항목 | 값 |
|---|---|
| 투입 | **Wave A (즉시)** |
| 소유 경로 | `eval/`, `configs/eval/`, `configs/integrity/`, `data/manifests/{dev,syn-val,eval-pool}/**` |
| 필독 | **EVALUATION.md 전체**, GENERALIZATION_CHARTER.md 전체, CONTRACTS.md 8절과 12.5절 |
| 상류 | W1 계약 패키지(공개 출력 파서와 스키마만), W2 LeadGen(평가 전용 곡 풀 생성), W3 변환 함수 |
| 하류 | 전 워커(평가 보고서), Custodian(sealed 도구), Orchestrator(게이트 보고서) |

## 1. 미션

프로젝트의 **자**를 만들고 지킨다. "좋아졌다"는 말은 네 평가기가 낸 수치로만 성립한다. 평가기는 엔진을 모르는 블랙박스이고, 정확하고, 재현 가능하며, 조작할 수 없어야 한다.

**직무 분리**: 너는 모델이나 인식 규칙을 튜닝하지 않는다. 너도 sealed 내용을 보지 않는다. sealed 실행은 Custodian이 네 도구로 한다.

## 2. 범위

- 범위: GT 형식과 manifest, 평가 투영, 정렬, 지표, 보고서, 기준선 실행기, Dev 데이터셋 구축 도구, R-PC 수집·정합 도구, sealed 도구, 무결성 장치(스캐너, 누출 검사, 변환 불변성, 새 시드 시험), 게이트 보고서 초안
- 범위 밖: 엔진 코드, 학습 데이터 생산(W2)

## 3. 작업 목록

### T4.1 GT 형식과 manifest

- EVALUATION.md 3절의 `gt.json` sidecar 스키마와 manifest 스키마. HarmonyMaker `OmrCorpusEntry` 필드를 모두 포함한다(CONTRACTS.md 12.5절).
- 검증기: 분리 규칙(곡, 촬영, 조판 균형), 범주 범위(EVALUATION.md 2.1절), 권리 필드, 해시 무결성.
- HarmonyMaker manifest로 내보내는 변환기(선택).

### T4.2 평가 투영 (`eval/projection/`)

- EVALUATION.md 4.1절. MusicXML의 divisions, backup, forward, chord, grace, tuplet, 여러 보표와 성부, 가사, harmony, 반복·볼타·네비게이션을 정확히 처리한다. partwise와 timewise 모두.
- 코드는 CONTRACTS.md 6절 문법으로 파싱해 의미 구조로 비교한다. 인쇄형 차이(M7과 maj7)는 같은 것으로 본다.
- 판독 불가 영역과 `evalRegions`를 적용한다.

### T4.3 정렬 (`eval/align/`, ADR-012)

- 마디 DP(일치, 삽입, 삭제, 분할, 병합), 성부 최적 매칭, 이벤트 편집 거리, 코드 정렬, 가사 정렬(EVALUATION.md 4.2절)
- 모든 쌍과 필드 오류를 `pairs.json`에 남긴다. 결정적으로 동작해야 한다(동점 처리 규칙 명시).

### T4.4 지표와 보고서 (`eval/metrics/`, `eval/report/`)

- EVALUATION.md 5절 전체: K1, K1-L, K2, K3, HarmonyMaker 지표, 텍스트, 구조, 기하, 보정, 운영, 견고성
- page 단위 bootstrap CI, paired bootstrap 비교, 필수 슬라이스 층화, 표본 부족 표시
- 출력: `report.json`(기계용) + `report.md`(사람용 요약 표) + 선택적 정적 HTML
- CLI: `clavis-eval run --engine <cmd|outputs> --dataset <manifest> --out <dir>`, `clavis-eval compare <A> <B>`

### T4.5 평가기 검증

- **돌연변이 시험**: GT에 알려진 오류를 20종 이상 주입한다(음높이 ±1단계, 변화표 변경, 음길이 변경, 점 추가·제거, 음표 삭제·추가, 쉼표↔음표, 붙임줄 토글, 성부 교환, 마디 분할·병합, 조표·박자 변경, 코드 값·위치 변경, 가사 치환·누락, 볼타 누락). 각 지표가 **정확히 기대만큼** 변하는지 확인한다.
- GT를 자기 자신과 비교하면 완벽 점수여야 한다. 동등한 MusicXML의 다른 직렬화(divisions 차이, 성부 번호 차이)에 대해서도 완벽 점수여야 한다.

### T4.6 기준선 실행기 (`eval/baselines/`)

- Audiveris 5.10.2(Docker), homr `457e7c65…`(격리 venv), oemer(고정 버전)를 **외부 프로세스**로 실행한다. 엔진 코드와 섞지 않는다(AGPL 격리).
- 기본 설정만 쓰고 이미지별 튜닝은 하지 않는다. 시간 초과와 크래시는 실패로 기록한다.
- 출력 캐시와 digest를 남긴다. 여러 movement 출력은 합치지 않고 평가한다.
- 산출물: **B0 보고서**(G0 필수).

### T4.7 Dev 데이터셋 구축

- **평가 전용 곡 풀**: W2 LeadGen의 `eval-*` 시드 네임스페이스와 선별 PD 곡으로 200곡 이상을 만든다. 멜로디 지문 목록을 W2 학습 필터에 제공한다.
- **R-PC 도구**:
  - 인쇄 묶음 생성 요청(W2 T2.7)
  - 수집 폴더 등록기: 사진을 렌더 페이지에 특징점 정합(homography)해 페이지를 식별하고, 기호 박스 GT와 실측 interline을 계산한다.
  - 촬영 메타데이터 입력
- **R-LIED**: OpenScore Lieder에서 곡을 고르고 IMSLP 스캔과 판본이 맞는지 검증한다(마디 수, 조표, 박자, 표본 대조). 원본 해상도와 저해상도 변형(interline 8, 10, 12 px)을 만든다.
- **R-LEGACY 접수**: Custodian이 비공개로 준 기존 이미지와 독립 전사를 검증해 `legacy: true, contaminated: true`로 등록한다.
- **Dev-Tune/Dev-Check** 분할(곡 단위, 약 60:40)을 고정한다.
- 수용 기준: G0에 Dev v0 ≥ 20쪽, G2에 ≥ 60쪽(EVALUATION.md 2.1절).

### T4.8 Sealed 도구 (Custodian용)

- `clavis-eval sealed`: 동결 빌드 패키지, sealed manifest, 임계값 artifact를 받아 네트워크 없이 실행한다. **집계 보고서만** 만든다(표본 부족 슬라이스 숨김, 오류 유형 히스토그램). 페이지별 상세는 Custodian 로컬에만 남긴다.
- Sealed 이미지의 SHA-256과 pHash, 곡 지문 목록을 만드는 로컬 도구. OR-003에 따라 Custodian이 동결 학습·Dev inventory와 역방향 선별하고 건수만 공유한다. sealed 지문은 공유하지 않는다.
- 원장 양식(`docs/gates/sealed-ledger.md`)과 artifact digest 검증.
- Custodian용 한국어 사용 설명서(EVALUATION.md 10절을 실행 명령 수준으로 구체화).

### T4.9 무결성 장치 (`eval/integrity/`, `eval/metamorphic/`, `eval/fresh_seed/`)

- **하드코딩 스캐너**: 헌장 6절 H1–H9. AST 기반으로 만들고, 규칙별 양성·음성 시험을 둔다. 허용 목록 형식(`configs/integrity/allowlist.yaml`: 파일, 줄, 규칙, 사유, 승인자)
- **누출 검사**: OR-003 보호 집합(평가 곡 풀 전체·Lieder 전체 성악 선율·접수된 Dev 선율/이미지)과 학습 inventory 대조. sealed 부재로 편입을 차단하지 않는다.
- **변환 불변성 시험**: W3의 변환 8종을 적용하고, 출력 음악 내용 차이를 K1 방식 연산 수로 잰다. 통과 기준은 헌장 6절.
- **새 시드 합성 시험**: nightly마다 새 시드 LeadGen 50곡 → W2 렌더 → W3 열화 → 엔진 → 지표. SYN-Val 관리 한계(평균 ±2σ)와 비교한다.
- **규칙 ablation 실행기**: 설정 플래그로 규칙 모듈을 하나씩 끈 실행을 비교한다.

### T4.10 게이트 보고서

게이트마다 EVALUATION.md 9절 체크리스트를 채운 `docs/gates/Gn_REPORT.md` 초안을 만든다. 각 항목에 근거 파일 경로를 단다. 판정은 Orchestrator가 한다.

## 4. 첫 PR (착수 48시간 목표)

평가 투영(단일 보표, 단일 성부, 코드, 가사 포함) + 이벤트 정렬 + pitch, duration, measureExact, K1 계산. 손으로 만든 MusicXML 쌍 10개의 golden 시험을 붙인다.

## 5. 수용 기준 요약

- **G0 핵심 책임자**: T4.1–T4.6, T4.8, T4.9의 스캐너와 누출 검사. Dev v0. B0 보고서
- G1: 변환 불변성, 새 시드 시험 운영
- G2: Dev ≥ 60쪽, 보정 지표, 해상도 곡선 보고서
- G3: sealed 실행 지원, 게이트 보고서

## 6. 이 역할의 함정

- **관대한 평가기**: 정렬이 너무 관대하면 오류가 사라진다. 돌연변이 시험이 이것을 막는다. 새 기능마다 돌연변이 종류를 추가한다.
- **평가기 변경의 무게**: 정의를 바꾸면 과거 수치와 비교할 수 없다. 버전을 올리고 기준선과 main을 모두 다시 잰 뒤에만 공개한다.
- **엔진 내부 참조**: 평가기가 엔진의 IR이나 내부 신뢰도에 의존하면 블랙박스가 깨진다. 공개 출력 파일만 읽는다.
- sealed 결과를 워커에게 "힌트"로 흘리지 않는다. 오류 유형 히스토그램 수준을 넘는 정보는 공유하지 않는다.

## 7. 초기 ADR

- ADR-012 정렬 알고리즘과 비용 함수
