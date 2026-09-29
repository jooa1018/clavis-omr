# GT / Dev 접수 형식 v1

EVALUATION §3, CONTRACTS §12.5의 필드를 보존한 W4 내부 sidecar 형식이다.
엔진 계약을 바꾸지 않는다. 모델은 `eval/gt/__init__.py`, 생성된 JSON Schema는
`configs/eval/gt.schema.json`, `gt-manifest.schema.json`이다.
재생성은 `python -m eval.gt.schema`이며 실제 자료를 읽지 않는다.

## 보관과 의미

`CLAVIS_PRIVATE_ROOT`는 Git 저장소와 그 상위 폴더를 피한 로컬 폴더다.
원본 이미지, GT, MuseScore 프로젝트, 렌더 PDF, sidecar, manifest를 모두 그 아래에 둔다.
메타데이터의 파일 경로는 private root 기준 슬래시 상대 경로다. 원본 경로·제목·가사는
git/CI에 넣지 않는다. 도구의 에러에는 원문·사적 경로를 출력하지 않는다.

MusicXML은 압축하지 않은 partwise 4.0이다. groundTruthDigest는 파일 원본 바이트의
SHA256이다. 원본 이미지와 렌더 파일에도 SHA256을 기록한다. 외부 DTD는 읽지 않으며
entity 선언은 거부한다. GT 접수 성공과 평가기 투영 지원은 별개다. 현재 첫 평가기의
미지원 요소·부분 영역은 evaluation-unsupported이며 점수를 만들지 않는다.

sidecar에 계약 필드 외에 devPartition, image/musicXml/render 경로 및 digest,
selection, review, legacy, contaminated, assisted를 추가한다. split은 원래 계약대로
dev|sealed를 보존하고 Dev-Tune/Check를 split에 넣지 않는다. 이 CLI는 dev만 받는다.
봉인 절차의 형식 호환성을 위해 모델에 sealed enum은 있지만 이 CLI로 봉인 파일을
열지 않는다. sealed 목록을 만들어 시험하지 않는다.

기존 HarmonyMaker 자료는 R-LEGACY, legacy=true, contaminated=true, split=dev.
알 수 없는 장치·조판 도구·폰트는 null이다. 임의 이름으로 균형을 만족시키지 않는다.
권리는 basis, allowedUses에 evaluation, 확인 근거 reference를 필수로 기록한다.

## 부분 GT

시스템은 한 줄에 함께 연주되는 보표 묶음이다. 위에서부터 1부터 세며 보표 하나와
혼동하지 않는다. 2–4개를 사전 선택하고 selection.json을 보관한다.

```powershell
.venv\Scripts\python.exe -m eval.gt select --page-id dev-001 --systems 6 --count 3 --seed dev-intake-session1 --date 2026-09-29 --out dev/dev-001/selection.json
```

내용을 전사하기 전에 seed·총 시스템 수·count를 고정한다. 도구는 SHA256 rank로 비복원
추출하며 기존 출력은 덮어쓰지 않는다. 재추첨하지 않는다. 1시스템 페이지는 whole-page
방식으로 전부 전사한다. 전체 페이지는 evalRegions=[]와 모든 시스템 목록을 기록한다.

선택한 시스템만 원본 순서로 하나의 MusicXML에 전사한다. 생략 구간을 쉼표 마디로
채우지 않는다. 각 evalRegions 항목은 systemIndex, sourceMeasureLabels,
xmlMeasureStart/End(선택 XML의 1부터 연속 위치), bbox(x,y,width,height; 원본 px)를
기록한다. 모든 XML 마디가 정확히 한 영역에 속해야 한다. 이 매핑을 사용해 영역을
분리해 평가하며 생략 구간 경계에 이벤트를 정렬하지 않는다(평가기 지원 전은 미지원).
보이지 않는 길이·음·tie를 생성하지 않는다. 시작 경계 조표/박자/음자리표는 원본의
지속 상태를 확인해 입력하고, 확인할 수 없는 문맥은 illegibleRegions에 기록한다.
보이지 않는 문맥이나 판독 불가를 제외하는 최종 범위는 W4가 검토하고 커버리지에 남긴다.

review는 전사일 ≤ 렌더 대조일 < 다른 날 재검토일, 검토자 ID, 독립 검토 여부,
모든 선택 마디 대조 여부를 기록한다. selection.recordedOn은 전사일 이전/당일이어야 한다.
Dev에 엔진 초안을 사용했다면 assisted=true로 표시한다.

## 검증과 분할

manifest 예: `{"schemaVersion":"clavis-gt-manifest-1","datasetVersion":"dev-v0-draft","sidecars":["dev/dev-001/gt.json"]}`.

```powershell
.venv\Scripts\python.exe -m eval.gt validate --manifest dev/manifest.json --out reports/intake.json
```

형식·권리·해시·선택 재현·지역 매핑·다른 날 검토를 검증한다. 곡(편곡/조옮김도 같은
songId), 촬영 session인 captureId, 인쇄물 printId는 Dev-Tune/Check를 넘나들지 않는다.
기존 ID가 달라도 같은 곡일 수 있으므로 MinHash 검사와 사람의 곡 동일성 확인도 필요하다.
약 60:40 곡 분할은 W4가 접수 묶음 전체에서 고정하고 사용자에게 선별을 요구하지 않는다.
감사 출력은 범주·7–9/9–11/11–14/14+ 구간 각 5쪽·20쪽·조판/폰트 50%를 확인한다.
범위가 부족하거나 미상 metadata가 있으면 PARTIAL이다. 이는 데이터 검증 결과이며
G0 PASS가 아니다. 불일치/분리 위반은 FAIL 또는 ERROR, 잘못된 입력은 nonzero다.
선택 기록과 검증 보고서는 기존 파일을 덮어쓰지 않는다. 재검증 시 새 출력 이름을 쓴다.
실제 자료가 아직 없어 Dev v0, 분리 비율, 실제 해시·권리는 NOT_RUN이다.

사용자에게는 보고서 첨부의 `GUIDE-R-LEGACY.ko.md`, `GUIDE-DEV11.ko.md`를 전달한다.
