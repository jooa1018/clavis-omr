# Custodian용 G0 준비 도구

**현재 실제 sealed 자료나 실행을 요청하지 않는다.** 이 도구는 해시 생산, 동결 receipt
대조, 집계 공개 경계, 원장만 준비한다. W9 동결 빌드/실행 경계와 G3 승인 artifact가
아직 없어 엔진을 실행하지 않으며 G0의 sealed 실행기 전체 완료로 표시하지 않는다.
개발 시험은 자체 합성 XML/임시 PNG와 가상 receipt만 사용했다.

아래 명령은 향후 Custodian 로컬 PC에서만 실행한다. CLAVIS_PRIVATE_ROOT는 Git/클라우드
밖의 폴더다. 원본 이미지·GT·페이지별 결과·상세 pairs는 그 폴더 밖으로 보내지 않는다.
명령의 모든 경로는 private root 기준 상대 경로다. 출력은 새 파일이어야 한다.

## 1. SHA256 / pHash / 멜로디 MinHash 목록

로컬 manifest는 `{"role":"reserved","samples":[{"sampleId":"opaque-001",
"imagePath":"local/page.png","musicXmlPath":"local/gt.musicxml","voice":"1"}]}`다.
이 manifest는 밖으로 공유하지 않는다. Dev/eval-pool에도 같은 형식을 사용하며 W2는
training inventory 생성 시 role=train으로 동일 생산기를 사용한다.

```powershell
.venv\Scripts\python.exe -m eval.sealed hashes --manifest local/hash-input.json --out share/hashes.json
```

공유 출력은 opaque ID와 해시만 담은 clavis-hash-inventory-1이다. 이미지·음열·가사·경로는
없다. 회색조 32×32 Lanczos → 직교 DCT-II 저주파 8×8, AC 중앙값, DC=0의 64bit pHash다.
평균 중심화 후 계수 소수 8자리 정규화. Pillow 11.2.1/NumPy 2.2.6을 고정한다.
멜로디는 명시한 단선율 성부의 음정/길이 비율 n-gram MinHash다. 한 성부 안 화음,
미세음정, 여러 파트/보표 등 현재 투영 미지원은 거부하며 일부 샘플을 조용히 빼지 않는다.
자료 없음도 허용 목록이 아니다. role의 의미/전체 보호 집합 포함 여부는 별도 감사한다.
한 번에 100쪽 이하, 이미지 32 MiB/40 MP/단일 프레임 제한. 실제 sealed 해시 생산 미실행.

## 2. 동결 artifact 사전 대조

```powershell
.venv\Scripts\python.exe -m eval.sealed preflight --artifact frozen/threshold-artifact.json --observed-digests frozen/observed.json --out receipts/preflight.json
```

artifact는 EVALUATION §7.2의 승인·동결 형식이다. observed.json은 W9/Custodian이 실제
패키지에서 측정한 engineBuildDigest, configDigest, models(name/sha256 배열),
evaluatorVersion이다. 이 도구는 두 receipt를 비교할 뿐, 문자열을 승인/실측의 증명으로
삼지 않는다. 빌드 패키지의 실제 검증·네트워크 차단은 W9 실행 경계에서 확인해야 한다.
대조 성공도 `PARTIAL, execution=NOT_RUN`이다. 공식 실행 횟수는 증가시키지 않는다.

## 3. 공유 가능한 집계 파일 추출

```powershell
.venv\Scripts\python.exe -m eval.sealed release --aggregate local/aggregate.json --public-vocabulary frozen/public-slices.json --pairs-manifest local/pairs-manifest.json --out share/aggregate.json
```

입력은 eval.aggregate의 단일 실행 결과다. public-slices.json 예:
`{"tier":["R-PC","R-LIED","R-TGT"],"interline":["7-9","9-11","11-14","14+"]}`.
공개 label 목록은 **실제 sealed 결과를 보기 전에** Orchestrator와 고정하고 식별정보를
넣지 않는다. 도구는 여기에 있는 슬라이스만 내보낸다. pageCount<5는 숨기며 전체<5도
SUPPRESSED 처리한다. 미지원 페이지를 빠뜨린 incomplete 집계는 공개 성공으로 만들지 않는다.
알려진 지표의 숫자 필드만 복사해 페이지 목록·임의 메시지·경로·원문을 제거한다.
선택 입력 pairs-manifest.json은 `{"pairs":["local/page-001/pairs.json"]}` 형식으로
전체 페이지의 로컬 pairs 경로를 열거한다. 페이지 수·평가기 digest·K1 합계를 대조한 뒤
고정 오류 유형별 건수만 공개한다. 필드 오류 히스토그램은 K1 연산 수와 합산하지 않는다.
pairs 입력이 없으면 히스토그램은 null/NOT_RUN이다. W9 엔진 실행 통합은 미완료다.
이 도구는 차등 개인정보보호나
반복 질의에 대한 익명성을 보장하지 않으며 최대 2회 실행 규칙을 계속 지켜야 한다.

## 4. 공식 실행 원장 (집계 검토 후에만)

```powershell
.venv\Scripts\python.exe -m eval.sealed ledger --receipt receipts/official.json --ledger local/sealed-ledger.jsonl --out share/ledger-receipt.json
```

official.json 필드: date(YYYY-MM-DD), sealedSetDigest, buildDigest, artifactDigest,
resultDigest(모두 64자리 SHA256), verdict(PASS/CONDITIONAL PASS/FAIL).
이 명령은 Custodian이 이미 수행한 **공식** 실행을 기록한다. 시험/preflight용으로 부르지 않는다.
동일 sealedSetDigest당 최대 2건, 중복 결과 거부, 이전 entryDigest와 연결한 append-only
JSONL이며 동시 쓰기 lock을 사용한다. 기존 행 변경은 거부된다. 이전 digest를 별도로
보관해 전체 파일을 다시 작성한 변조도 발견할 수 있도록 한다. 비정상 종료의 lock은
Custodian이 이전 실행 종료/기록을 확인한 후에만 정리한다.
공유용 원장 틀은 docs/gates/sealed-ledger.md. 실제 공식 실행 기록은 아직 0건이다.

두 번 이후에는 기존 세트로 재평가하지 않는다. 폐기/Dev 전환과 새 세트 준비는
Orchestrator·Custodian 절차를 따른다. 결과를 보고 동결 기준을 바꾸지 않는다.
