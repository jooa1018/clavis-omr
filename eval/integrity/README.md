# 무결성 도구 v0.1 (W4)

로컬 CPU 전용이며 엔진·네트워크·이미지·GT를 읽지 않는다. 스캐너는 Git 추적 파일과
ignore되지 않은 신규 파일만 읽는다. 저장소 밖 경로와 심볼릭 링크는 거부한다.

```powershell
python -m eval.integrity.hardcode_scan --root . --out work/hardcode.json
python -m eval.integrity.leakage --train work/train-hashes.json --reserved work/protected-set.json --out work/leakage.json --admitted work/admission.json
```

종료 코드: PASS=0, 위반·파싱/설정 오류=1. 누출 검사의 자료 없음은 NOT_RUN=2이며
admission은 비어 있다. 오염 샘플을 제외한 admission.inventory만 학습에
사용한다. 원래 입력 목록으로 학습을 계속하면 안 된다. 오류 시 기존 admission도 빈
출력으로 덮어써 이전 실행의 허용 결과를 재사용하지 못하게 한다.

## OR-003 보호 집합과 재검사

protected-set.json 형식: `schema: clavis-protected-set-1`, 정수 `version`, `sources`.
sources 키는 eval-pool, lieder, dev-melodies, dev-images만 허용하며 sealed는 거부한다.
각 값은 `{"complete":true,"inventory":{...role:reserved...}}`다.
eval-pool 전체와 OpenScore Lieder 전체 성악 선율은 필수이고 비어 있으면 거부한다.
수집 완료 근거가 있어야 complete=true로 선언한다. 둘이 갖춰지면 v1이며 접수된 Dev
GT 선율(R-TGT Dev/R-LEGACY)·이미지 SHA256/pHash를 추가할 때 버전을 올린다.
sealed 자료는 입력하지 않는다. sealed 부재는 편입 차단 이유가 아니다.

출력 clavis-training-admission-1은 `protectedSetDigest`, `protectedSetVersion`,
제외 후 `inventory`를 담는다. W2 학습 manifest에 그 digest를 그대로 기록하고 학습
직전에 현 보호 집합 digest와 대조한다. 아래 API로 갱신 검사를 한다.

`eval.integrity.protection.recheck(prior_admission, new_bundle, sample_id_to_song_id)`

이전 실제 학습 목록과 명시적 sample→song 대응표를 넣어 곡 단위 분모를 보존한다.
새 충돌이 1% 초과면 ESCALATE. 다음 학습부터 제외하되 기존 체크포인트는 고치거나
재학습하지 않는다. 로컬 결과 contaminatedDevPageIds로 Dev metadata.contaminated를
표시한다. eval.aggregate는 contaminated/clean/unknown 슬라이스를 별도 출력한다.
접수 자료가 없는데 clean으로 채우지 않는다. recheck 출력은 Dev 내부 자료다.

편입 전 속도/경로 시험용 학습은 LeadGen 개발 프로필·smoke 렌더만 허용한다.
eval-*·PDMX·실사 금지, checkpoint=measurement-only. 평가 보고·엔진 모델·체크포인트
선택에 사용 금지. 실제 학습/체크포인트 계보 강제는 W1/W2 및 학습 소유자의 책임이다.

sealed는 Custodian의 `eval.sealed reverse-screen`으로 동결 학습·Dev inventory에
대조해 후보를 제외한다. 후보·제외 건수만 공유하며 선율 지문은 누구에게도 넘기지
않는다. 학습을 sealed 결과로 재필터하지 않는다. eval/sealed/README.md를 따른다.

## 스캐너

헌장 §6 H1–H9의 AST 후보 검출기다. H4만 tests 경로를 제외한다. H5/H6/H7은
src/clavis에 한정한다. H1/H2/H3/H8/H9는 전체 Python 파일에 적용한다.
H2는 data/manifests JSON의 ID·파일명·경로 필드를 추출한다. 사적 또는 sealed 원본
manifest를 저장소에 복사하지 않는다. 없는 manifest의 식별자는 검사할 수 없다.
H8은 명시 seed 없는 RNG 생성, 모듈 전역 RNG 호출, secrets를 탐지한다.
H9는 시각 호출과 단순 변수 전파가 분기·조건식·assert·comprehension에 들어갈 때
탐지한다. 시각을 기록하는 로그·보고서 컨테이너는 판정값으로 간주하지 않는다.

출력은 파일·줄·규칙·소유자·AST digest다. 문자열 원문/사적 ID는 출력하지 않는다.
후보가 하나라도 있으면 실패한다. raise만 하는 guard에서 0의 크기 경계와 RGB
채널 축의 3 확인은 헌장 §4의 일반 형식 검증으로 구분한다(W3 검토).
합성 fixture처럼 정당한 코드도 탐지될 수 있다. 소유자가 검토하고 수정하거나 Orchestrator에게 예외를
요청한다. 자동으로 예외를 추가하지 않는다.

allowlist.yaml은 외부 의존성 없이 읽는 JSON 부분집합 YAML 배열이다. 항목:
`file, line, rule, reason, approvedBy: ["W4", "orchestrator"], evidence_digest`.
빈 배열은 예외가 없다는 뜻이다. digest·줄 불일치, 중복, 승인 누락은 검사 오류다.
기록 문자열은 승인 진위의 증명이 아니므로 PR 승인 기록을 함께 확인해야 한다.

이 검사는 정적 휴리스틱이다. 동적 import/eval, 함수 간 데이터 흐름, 런타임 생성
경로, 사용자 정의 RNG wrapper를 완전히 증명하지 않는다. import-linter, 코드 리뷰,
결정성 시험과 함께 사용한다. PASS를 하드코딩 부재의 수학적 증명으로 인용하지 않는다.

## 해시 inventory v1

최상위 필드: schema=`clavis-hash-inventory-1`, role=`train|reserved`,
phashAlgorithm=`phash-dct32-low8-median63-v1`,
melodyAlgorithm=`interval-rhythm-ngram4-minhash64-sha256-v1`, samples 배열.
샘플은 `sampleId`(영숫자·하이픈·밑줄, 1–80자), `imageSha256`(소문자 64 hex),
`phash`(소문자 16 hex), `melodyMinhash`(소문자 64 hex × 64개)만 받는다.
경로·악보 내용·가사 필드는 받지 않는다. ID 중복, 누락 필드, 알고리즘 불일치는 실패다.

pHash 생산 규약은 회색조 32×32의 DCT-II 정규 직교 변환, 좌상단 8×8(DC 제외 63개)의
중앙값을 기준으로 `>` 비트화하고 DC=0, 행 우선 big-endian 64비트다. 리사이즈는
Pillow 11.2.1 Lanczos다. DC만 제거하는 평균 중심화와 DCT 소수 8자리 반올림으로
퇴화 영상의 부동소수 잡음을 고정한다. 동일 생산기 버전을 써야 한다.
생산기는 eval/integrity/hashes.py이며 eval/sealed README의 로컬 hashes 명령을 쓴다.
호환 확인되지 않은 외부 pHash를 이 이름으로 바꾸어 입력하지 않는다.

누출: SHA256 동일 또는 pHash Hamming ≤6 또는 전체 멜로디 MinHash 동일이면 제외한다.
멜로디는 `melody_fingerprint([(MIDI, Fraction duration), ...])`로 생성한다.
연속 음정/길이 비율의 4음 n-gram, SHA256 64개 고정 라벨별 최솟값이다.
조옮김·일괄 템포 변화에 불변이다. 멜로디 부분 일치의 새로운 임계값은 도입하지 않는다.
짧은 곡은 충돌할 수 있어 보수적으로 제외된다. 장식음 추가·부분 인용·성부 선택이 다른
편곡의 검출은 보장하지 않으며 전체 곡 ID 분리 검사를 대체하지 않는다.
protected 원본 ID·해시는 공유 보고서에 싣지 않는다. 실제 sealed 목록은 읽지 않았다.

## W1 CI / W2 admission 연동

CI 필수: AST 명령 + `pytest tests/eval/test_integrity.py`의 H1–H9 및 누출 양성/음성
시험. 실제 데이터 admission에는 누출 명령도 필수이며 NOT_RUN은 허용으로 취급하지
않는다. 저장소에 데이터가 없을 때 테스트 fixture의 PASS와 실제 검사의 NOT_RUN을
별도로 보고한다. W1이 main 소급 결과를 저장하고 탐지를 소유자별로 전달한다.
