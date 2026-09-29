# G0 보고서 초안 — 자와 기반

작성: W4 · 2026-09-29. 검토 main: `8b7c2f4` + sealed 준비 도구 PR.
**G0 미충족. 최종 판정은 Orchestrator가 한다.** 실제 Dev/B0/sealed 성능 측정 없음.
기준: EVALUATION v1.1 §9, ADR-012 채택, OR-001/002.

| 필수 항목 | 상태 | 병합 근거 / 남은 일 |
|---|---|---|
| 저장소·두 OS CI·계약 v0.1·Schema·LSTL | PARTIAL | W1 PR #4 계약, #15 CI. W2 LSTL 코어 완료 근거는 아직 없음 |
| 평가기 v1 전체 투영·정렬·전 지표·bootstrap·mutation≥20 | PARTIAL | W4 #8 첫 평가기와 golden13, #18 다성부·K2/K3·page bootstrap10000·27종 mutation. 여러 파트/보표·timewise·부분 GT·진행 펼침·CER/기하/보정/운영 등 전 지표는 남음 |
| Dev v0≥20쪽·권리·분리 | NOT_RUN | W4 #16 GT 형식/검증/안내 완료. 사용자에게 legacy·Dev11쪽 로컬 접수 요청. 실제 자료 접근/등록 없음 |
| B0 3기준선 × Dev v0·SYN-Val | NOT_RUN | W4 #19 고정 버전 외부 실행 준비. 실제 Docker/환경/weights·Dev v0·SYN-Val·W1 큐 미준비 |
| 하드코딩·누출·import CI | PARTIAL | W4 #14, W1 #15 필수 CI. main 소급 후보0/예외0 PASS; W2 H4 두 곳 #12 수정. 실제 누출 목록이 없어 데이터 검사는 NOT_RUN/admission 차단 |
| Sealed 집계 실행기·해시·원장 | PARTIAL | 해시 producer, receipt 대조, 숫자 집계 공개/표본<5 억제, 최대2회 원장과 한국어 설명 준비. W9 동결 오프라인 실행/오류 히스토그램 통합 미완료; 실제 sealed 없음 |

## 근거

- [무결성](../reports/W4/T4.9-integrity.md), [W1 CI·소급](../reports/W1/T1.8-integrity-ci.md).
- [GT·접수](../reports/W4/T4.1-gt-intake.md), [R-LEGACY 안내](../reports/W4/GUIDE-R-LEGACY.ko.md), [Dev11쪽 안내](../reports/W4/GUIDE-DEV11.ko.md).
- [평가기 확장](../reports/W4/T4.3-evaluator-extension.md), [27종 실측 JSON](../reports/W4/T4.3-extension-evidence.json).
- [기준선 준비](../reports/W4/T4.6-baseline-tools.md), [sealed 준비](../reports/W4/T4.8-sealed-preparation.md), [원장 양식](sealed-ledger.md).

PR: [#14](https://github.com/jooa1018/clavis-omr/pull/14), [#16](https://github.com/jooa1018/clavis-omr/pull/16), [#18](https://github.com/jooa1018/clavis-omr/pull/18), [#19](https://github.com/jooa1018/clavis-omr/pull/19).
각 최종 head의 Linux/Windows CI 통과 후 B등급 squash 병합. 지표 정의 변경 없음.

## 소급 무결성 소유자별 처리

| 소유자 | 후보 | 처리 |
|---|---|---|
| W2 | smoke fixture의 H4 2곳 | #12에서 tests 경로로 내용 유지 이동, 해소 |
| W3 | RGB/빈 이미지 검증 H3 후보 | 소유자 확인 후 일반 형식 guard로 구분. 예외 추가 없음 |
| W4 | elapsed 필드를 포함한 cache 객체 전체의 H9 오탐 | timestamp 필드 자체 전파는 유지하고 다른 키와 구분, 양성/음성 시험 |
| 전체 main | W1 소급 ece70f4 69파일 / d7fbd33 70파일 | 후보0, 예외0. 이후 CI도 같은 필수 검사 실행 |

## 실행·자원·데이터 경계

측정은 로컬 Windows CPU의 합성 XML/이미지/외부 stub 단위 시험과 무료 GitHub CI다.
27종 mutation·기존 golden13의 정답 기대값은 독립적으로 작성했고 수치는 JSON 출력에서 복사했다.
평가기 0.2.0 확장 시 1·4스레드 각3회 실측 JSON SHA256이 모두
`319579c1b1e818058b88ed843e10b7cc569b1cbc401c3b32a92037222e0c0b40`이었다.
그 digest는 PR #18 당시 평가기/설정 snapshot의 재현 근거이며 이후 도구 추가로 코드 digest는 바뀐다.
실제 Dev/SYN-Val 성능·95% CI·B0·sealed·학습·대규모 렌더 배치는 모두 NOT_RUN.
GPU·유료 컴퓨트·sealed 원본 접근 없음. 무거운 실행은 W1 단일 큐 01:00–07:00 준비 후 한다.

## 다음 의존성과 사용자 작업

1. 사용자: R-LEGACY 정리 약30분, Dev11쪽 사전 무작위 선택·부분 전사·다른 날 검토.
   준비된 로컬 폴더 경로/페이지 ID/검토 상태만 회신 요청. 업로드 요청 없음.
2. W4: 접수 후 실제 권리·해시·곡/촬영/인쇄물 분리·20쪽/범주/폰트 균형 확인.
   부분 영역을 포함한 미지원 투영과 남은 G0 지표 구현·검증.
3. W2: 생산 프로필 PR #11은 draft이며 PDMX 박자별 집계가 미준비. 이 조건 전에는
   eval-* 풀이나 R-PC 묶음을 만들지 않는다. 생산 준비 후 W4 평가 풀≥200곡과 정합 착수.
4. W1: 큐 API 준비. 기준선 설치·모델 수령·3기준선 B0 전체 실행은 이후 진행.
5. R-PC 세션 #1: 인쇄 PDF 제공 후 A4 12쪽, 정면 밝은 사진/실내 각도/메신저 경로,
   가능한 스캔과 촬영 metadata를 요청할 예정(약90분). 현재 촬영 요청은 없음.
6. W9/Custodian: 동결 실행 경계·실제 digest 측정·공식 집계/원장 연결. G0 단계에서
   실제 sealed 자료를 구축·요청·실행하지 않는다. 임계값 artifact 동결은 G3 전 별도 승인.

권리·누출·전체 범위 검증 전 데이터셋 완료나 인식 개선을 주장하지 않는다.
