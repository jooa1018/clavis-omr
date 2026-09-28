# Clavis 평가 프로토콜 v1.1

> 소유: W4(구현·운영), Orchestrator(승인), Custodian(sealed 보관·실행).
> 이 문서는 "무엇을 잘했다고 말할 수 있는가"의 유일한 기준이다. 평가기를 바꾸면 버전을 올리고 기준선부터 다시 측정한다.

> v1.1: ADR-012 수정 채택(Orchestrator, 2026-09-29). §4.2·5.1·5.2·5.4의
> 객체 단위 교정·정렬·분모를 확정했다. 기존 평가기·B0 측정은 없어 재측정 대상 없음.

## 1. 원칙

1. **자 먼저**: 평가기, 기준선(B0), Dev v0가 준비되기 전에는 인식 개선을 주장할 수 없다.
2. **블랙박스 평가**: 평가기는 엔진의 공개 출력(MusicXML, evidence, hints, confidence)만 읽는다. 엔진 내부를 import하지 않는다.
3. **정직한 분모**: 판독 불가 영역을 뺀 모든 기준 요소가 분모다. 누락은 오류로 센다.
4. **통계적 엄밀성**: page 단위 bootstrap 신뢰구간을 보고한다. 개선 주장은 paired bootstrap으로 한다.
5. **분리와 보관**: 곡, 촬영, 조판 단위로 분리하고 sealed는 Custodian이 보관한다.

## 2. 데이터 tier와 분할

| Tier | 설명 | 정답(GT) | train | Dev | Sealed | 권리 |
|---|---|---|---|---|---|---|
| **SYN** | LeadGen + PD 코퍼스를 렌더링하고 열화한 합성 데이터 | 렌더 원본 MusicXML(정확) | ✔ SYN-Train | **SYN-Val**(고정·층화, 500쪽 × interline 10구간, 게이트용), 부분집합 **SYN-Val-nightly**(100쪽 × 10구간), **SYN-Val-quick**(30쪽 × 6구간, PR용), SYN-Fresh(nightly 새 시드) | — | PD, CC0, 자체 생성 |
| **R-PC** | 평가 전용 곡 풀의 렌더를 인쇄해 휴대폰·스캐너·메신저 경로로 수집 | 렌더 원본 MusicXML(정확) + 사진↔렌더 정합으로 얻은 기호 박스 | 선택: R-PC-Train(학습 풀 곡만) | ✔ | ✔ | 자체 제작 |
| **R-LIED** | OpenScore Lieder의 IMSLP 공개 도메인 스캔. 원본 해상도와 저해상도 변형 | OpenScore MusicXML(CC0), 판본 일치 확인 | ✘ **학습 금지** | ✔ | ✔ | PD, CC0 |
| **R-TGT** | 사용자가 가진 한국 찬양 리드시트(카톡, 웹, 사진) | Custodian 수기 전사(부분 정답 허용) | ✘ | ✔ | ✔ | user-confirmed-rights, 평가 전용 |
| **R-LEGACY** | HarmonyMaker 개발에 이미 쓰인 이미지(사용자 JPEG, 독립 A/B/C, 자체 제작 6/8 등) | 기존 독립 전사(검증 후) | ✘ | ✔ (회귀 사례, 오염 표시) | ✘ **금지** | 기존 권리 기록 |

### 2.1 규모 목표

| 시점 | Dev | Sealed |
|---|---|---|
| G0 (Dev v0) | ≥ 20쪽 (R-PC 12 + R-LEGACY + R-LIED 일부) | 구축 시작 전 |
| G2 | ≥ 60쪽 (R-PC 30, R-LIED 15, R-TGT 15), HarmonyMaker 최소 36쪽 충족 | 구축 중 |
| G3 | 위와 같음 + 보정 | **≥ 40쪽** (R-PC 20, R-LIED 10, R-TGT 10), HarmonyMaker 최소 24쪽 충족 |

각 분할은 HarmonyMaker corpus 범주 요구(digital-pdf, scanned-pdf, camera-photo; 4/4와 6/8; 장조와 단조; 임시표·점음표·붙임줄)를 모두 포함해야 한다. 추가로 **interline 구간 7–9, 9–11, 11–14, 14+ px**에 각각 최소 5쪽이 있어야 한다.

### 2.2 분리 규칙

- **곡 단위 분리**: 같은 곡(편곡, 조옮김 포함)이 두 분할에 걸치면 안 된다. 멜로디 지문(음정 + 리듬 n-gram MinHash)으로 검사한다.
- **촬영 단위 분리**: 같은 인쇄물이나 같은 촬영 세션이 두 분할에 걸치면 안 된다.
- **조판 균형**: 한 조판 도구나 폰트가 한 분할의 50%를 넘지 않게 한다.
- **평가 전용 곡 풀**: W4가 LeadGen 새 시드와 선별 PD 곡으로 200곡 이상의 풀을 만든다. 풀의 지문을 학습 필터에 등록한다. R-PC의 Dev와 sealed 곡은 모두 이 풀에서 나온다. Custodian이 sealed 곡을 풀에서 **비공개로** 고른다.
- **Dev-Tune / Dev-Check**: Dev를 곡 단위로 약 60:40으로 나눈다. 임계값, 신뢰도 보정, 규칙 파라미터 적합은 Dev-Tune에서만 한다. 개선 주장은 Dev-Check와 SYN-Val로 한다.

## 3. 정답(GT) 형식과 제작

- GT 본체는 MusicXML 4.0이고, 부가 정보는 sidecar JSON(`gt.json`)에 둔다: `pageId`, `songId`, `captureId`, `tier`, `split`, `sourceKind`, `captureChannel`(scan-150, scan-300, phone-daylight, phone-indoor, phone-angle, messenger, screenshot 등), `captureDevice`, `engravingTool`, `musicFont`, `measuredInterlinePx`, `leadStaff`(파트, 보표, 성부), `evalRegions?`(부분 정답일 때 평가할 시스템 목록), `illegibleRegions?`, `rights`, `notes`.
- HarmonyMaker `OmrCorpusEntry` 필드를 모두 담아 두 시스템 간에 manifest를 변환할 수 있게 한다(CONTRACTS.md 12.5절).
- **R-PC**: GT는 렌더에 쓴 MusicXML이다. W4의 정합 도구가 사진을 렌더 페이지에 특징점 정합(homography)해 페이지를 식별하고 기호 박스 GT를 만든다. 인쇄물에 식별 코드(QR 등)를 넣지 않는다. 식별 코드는 엔진이 악용할 수 있는 식별 정보이기 때문이다.
- **R-LIED**: OpenScore MusicXML과 스캔 판본이 맞는지 확인한다(마디 수, 조표, 박자, 표본 마디 대조). 불일치 구간은 `illegibleRegions`로 제외한다.
- **R-TGT**: Custodian이 MuseScore 등으로 전사한다.
  - 절차: 전사 → 렌더 → 원본과 나란히 비교 → 다른 날에 한 번 더 검토. 가능하면 다른 사람이 검토한다.
  - **Sealed GT는 엔진 출력으로 초안을 만들지 않는다.** 엔진 쪽으로 편향되기 때문이다.
  - Dev GT는 엔진 초안을 쓸 수 있다. 단, 모든 마디를 눈으로 대조하고 `assisted: true`를 표시한다.
  - **부분 정답**: 쪽마다 2–4개 시스템만 전사하고 `evalRegions`로 지정하면 전사 부담이 크게 준다. 선택은 무작위로 하고 선택 기록을 남긴다.
- 판독 불가: 사람도 읽을 수 없는 영역은 `illegible`로 표시해 정확도 분모에서 빼고, 커버리지 지표에는 반영한다.

## 4. 평가 투영과 정렬

### 4.1 평가 투영 (Evaluation Projection)

MusicXML을 다음 정규 구조로 바꾼다(W4 `eval/projection/`).

- 파트 → 보표 → 마디(순서) → {박자, 조표, 음자리표, 성부별 이벤트, 코드, 가사, 진행 요소}
- 이벤트: `kind`(note, rest, rhythm), `onset`, `duration`(4분음표 단위 Fraction), `pitch`(step, alter, octave), `tieStart`, `tieStop`, `voice`, `grace`, `chordMember`
- divisions, backup, forward, chord, grace, tuplet, 여러 보표를 정확히 처리한다. partwise와 timewise를 모두 읽는다.
- 코드: onset과 정규형(CONTRACTS.md 6절 파서로 파싱한 의미 구조)
- 가사: 절, 음절 텍스트(NFC), syllabic, 부착 이벤트
- 진행: 도돌이, 볼타, 네비게이션을 **펼친 연주 순서**의 마디 ID 목록

### 4.2 정렬

1. **마디 정렬**: 기준과 예측의 마디열을 DP로 정렬한다. 연산은 일치, 삽입, 삭제, 분할(1→2), 병합(2→1). 비용은 해당 마디 쌍의 이벤트 DP K1 비용을 그대로 쓴다. 분할·병합은 마디를 이어 붙여 비교하고 구조 연산 +1, 누락·여분 마디는 내부 이벤트 수 +1(빈 마디도 1)이다. 이어 붙일 때 onset은 앞 마디 길이만큼 누적한다. 다중집합 대칭차 근사는 쓰지 않는다.
2. **성부 대응**: 정렬된 마디 쌍 안에서 성부를 최적 매칭한다(헝가리안, 비용 = 이벤트 편집 거리).
3. **이벤트 정렬**: 성부 쌍마다 onset 순서로 정렬하되 onset은 대응 키에서 제외한다. 목적함수 `(K1 연산 수, 대응 쌍 필드 불일치 총수, |Δonset| 총합)`를 사전식 최소화한다. kind·pitch·duration·tie(start/stop) 중 하나라도 다르면 K1 비용은 1, 누락·여분 각 1이다. 필드 정확도와 pairs.json은 이 정렬로 계산한다.
4. **코드 정렬**: 정렬된 마디 안에서 코드 객체를 대응한다. 위치는 onset 일치로 판정하되 위치가 다른 코드도 대응해 오류를 기록한다. 값 또는 위치가 틀리면 객체당 1, 누락·여분 각 1이다.
5. **가사 정렬**: 정렬된 이벤트 쌍을 따라 절별로 비교한다.

모든 쌍과 필드 오류를 `pairs.json`에 기록한다. 평가기 버전과 해시를 모든 보고서에 싣는다.
완전 동점은 이벤트 대응→삭제→삽입, 마디 1:1→분할→병합→삭제→삽입,
동일 후보는 입력 문서 순서다(ADR-012). 미지원 투영 요소는 조용히 버리지 않고
`evaluation-unsupported`로 표시한다.

## 5. 지표

### 5.1 K1 교정 부담 (correction ops / 100 기준 이벤트)

단위는 **교정 대상 객체 수**다. 같은 kind에도 replace-event를 허용하며,
한 객체의 여러 필드 오류를 중복 과금하지 않는다(ADR-012).

| 오류 | 연산 수 |
|---|---|
| 이벤트 누락(삽입 필요), 여분 이벤트(삭제 필요) | 각 1 |
| 대응 이벤트의 kind·pitch·duration·tie(start/stop) 중 하나라도 다름 | 객체당 1 (replace-event), 필드 수와 무관 |
| 마디 분할·병합 필요 | 각 1 (barline 삽입·삭제) |
| 누락·여분 마디 | 내부 이벤트 수 + 1 (빈 마디는 1), 이벤트 누락·여분을 다시 더하지 않음 |
| 조표·박자·음자리표 오류 | 발생 지점당 1 |
| 대응 코드의 값 또는 위치 오류 | 객체당 1 |
| 코드 누락·여분 | 각 1 |

K1 = 총 연산 수 / 기준 이벤트 수 × 100. 가사는 따로 **K1-L**(가사 음절 연산 / 100 음절)로 보고한다.
onset만 다른 이벤트는 K1에 더하지 않고 `onsetOnlyMismatch`와 measureExact에만
반영한다. 앞선 길이·삽입에서 파생되는 onset을 중복 과금하지 않는다.
진단 수치가 커지면(예: 성부 2 forward 오류) ADR-012 재검토를 요청한다.
계약 변경이나 새 onset patch는 없다. 분모 0은 null과 denominator 0으로 보고한다.

### 5.2 K2 무표시 오류율

- **편곡 영향 오류**: K1 교정 객체 중 pitch, duration, 종류, tie, 마디 구조, 조표·박자·음자리표, 코드 값·위치 오류. 한 객체에 여러 오류가 있어도 1이다. 가사와 onset만 다른 이벤트는 K2에서 제외한다.
- 오류 요소(또는 그 요소가 속한 마디)가 `element-confidence.json`에서 `flagged=true`가 아니면 **무표시 오류**다. 누락 오류는 정렬된 예측 마디가 flag됐는지로 판단한다.
- K2 = 무표시 편곡 영향 오류 수 / 기준 이벤트 수.
- 함께 보고: **flag 부담**(flag된 예측 요소 비율), **flag 정밀도**(flag된 것 중 실제 오류 비율), **오류 재현율**(오류 중 flag된 비율).

### 5.3 K3 harmonizationReadyRate

무표시 편곡 영향 오류가 0인 페이지의 비율이다. HarmonyMaker 스펙 22.3절과 정의가 같다.

### 5.4 HarmonyMaker 지표 (이름 동일)

분자는 정렬된 쌍 중 해당 필드가 맞은 수다. 누락은 분모에서 빼지 않는다.
micro와 macro를 모두 내며 분모 0은 null + denominator 0이다.

| 지표 | 분모 |
|---|---|
| `pitchExactRate` | 기준 note, grace 제외 |
| `durationExactRate` | 기준 note·rest·rhythm, grace 제외 |
| `graceExact` | 기준 grace, 일반 pitch/duration과 분리 |
| `restExactRate` | 기준 rest |
| `tieExactRate` | 기준 또는 대응 예측 note 중 tie 표시가 하나라도 있는 note |
| `accidentalExactRate` | 기준 note 중 alter가 조표 기본값과 다르거나 임시표가 보이는 note |
| `keySignatureExactRate`, `timeSignatureExactRate` | 기준의 설정·변경 지점 |
| `chordSymbolExactRate` | 기준 코드 객체, 값+위치 일치 |
| `measureExactMatchRate` | 기준 마디 |

measureExact는 1:1 대응 마디에서 이벤트(kind·pitch·duration·onset·tie),
조표·박자·음자리표, 코드 값·위치, 도돌이·볼타 표시가 모두 일치해야 한다.
가사는 제외하고 참고 지표 `measureExactWithLyrics`를 별도로 낸다.
분할·병합은 exact가 아니다. ID·표시 번호·성부 번호·divisions 직렬화는 제외한다.
`parseableMusicXmlRate`, `measureDurationValidRate`, `voiceTimelineValidRate`,
`retakeRate`도 보고한다. 미지원 투영 요소는 `evaluation-unsupported`로 표시한다.

### 5.5 텍스트

- 코드: `chordSymbolExactRate`(값 + 위치), `chordValueRate`(값만), 코드 누락·여분률
- 가사: 음절 정확도(텍스트 일치 + 올바른 이벤트 부착), 음절 CER(한글은 음절 단위, 보조로 자모 단위), 절 배정 정확도
- 기타: 제목 정확 일치(정보용), 템포 값 일치, 섹션 라벨 일치

### 5.6 구조

마디 수 정확률, barline F1(정렬 기반), 도돌이·볼타·네비게이션 정확도(펼친 연주 순서 일치), 못갖춘마디 정확도

### 5.7 기하 (GT 기하가 있는 SYN, R-PC)

보표 검출 정밀도·재현율, interline 추정 오차(중앙값, p95), barline 위치 오차(staff-space), evidence 박스 IoU와 중심 오차

### 5.8 보정 (calibration)

요소 유형별 ECE(15구간), 신뢰도 다이어그램, 오류 탐지 AUROC, risk–coverage 곡선

### 5.9 운영

MusicXML 유효율, 결정성(같은 입력 3회, 1·4스레드), 지연 p50·p95(REF-LAPTOP), 최대 RSS, 크래시율

### 5.10 견고성

- **해상도 곡선**: interline 6, 7, 8, 9, 10, 12, 14, 16, 20, 24 px 구간별 K1, K2, pitch, duration. SYN과 R-PC 다운샘플 변형으로 만든다.
- **최소 사용 가능 interline**: K1 ≤ 12이고 K2 ≤ 1%를 만족하는 가장 작은 구간
- 열화 유형별, 촬영 경로별 분해
- 변환 불변성 통과율(GENERALIZATION_CHARTER.md 6절)

### 5.11 집계와 층화

- page 단위 bootstrap(10,000회, 고정 시드)으로 95% 신뢰구간을 낸다. 비교는 같은 페이지 집합의 paired bootstrap으로 한다.
- 모든 보고서에 **필수 슬라이스**를 싣는다: tier, split(Dev-Tune/Dev-Check), sourceKind, captureChannel, interline 구간, engravingTool, musicFont, 기보 특성(붙임줄, 점음표, 임시표, 6/8, 2성부, 슬래시, 가사 한/영, 코드 밀도).
- 슬라이스 표본이 5쪽 미만이면 "표본 부족"으로 표시하고 결론을 내지 않는다.

## 6. 기준선 (Baselines)

| 기준선 | 버전 | 실행 | 비고 |
|---|---|---|---|
| Audiveris | 5.10.2 | Docker CLI, 기본 설정 | HarmonyMaker와 같은 버전. 여러 movement는 합치지 않고 그대로 평가(결과 손실로 셈) |
| homr | `457e7c6518a10ba755db2e60883419e56c4d7369` | 격리된 가상환경 CLI | HarmonyMaker 고정 revision |
| oemer | 고정 버전(W4가 기록) | 격리된 가상환경 | MIT |
| Clavis 무학습 구성(내부) | 엔진 버전과 같이 기록 | W6 T6.1 템플릿 구성 | 학습한 분류기의 이득을 재는 내부 기준 |

GPU를 쓰지 않으므로(PLAN v1.1) GPU가 필요한 공개 모델(LEGATO 등)은 기준선에서 제외한다. 위 기준선은 모두 CPU로 돈다.

- 기준선은 **이미지별로 튜닝하지 않는다.** 시간 초과와 크래시는 실패로 센다.
- 출력은 digest와 함께 캐시한다. 데이터셋 버전이 바뀔 때만 다시 실행한다.
- 기준선은 엔진과 다른 프로세스, 다른 환경에서 실행한다(라이선스 격리).
- **B0 보고서**(G0 필수): 모든 Dev tier와 SYN-Val에 대한 전체 지표와 해상도 곡선.

## 7. 절차

### 7.1 개발 루프

인식에 영향을 주는 PR은 `eval dev`(Dev 전체)와 `eval syn-val-quick`을 실행한다(REF-LAPTOP에서 합계 약 15–20분). 이전 main과의 paired 비교 보고서를 PR에 첨부한다(GENERALIZATION_CHARTER.md 5절). SYN-Val-nightly, 변환 불변성, 새 시드 시험, 규칙 ablation은 nightly 배치(약 1–2시간)로 돈다. SYN-Val 전체(약 3–5시간)는 게이트 직전 야간에 돈다. 세 세트 모두 W3 결정적 열화로 재생성할 수 있으므로 이미지를 저장해 둘 필요는 없다.

### 7.2 임계값 동결 artifact (G3 전)

`docs/gates/threshold-artifact-vN.json`:

```json
{
  "schema": "clavis-threshold-artifact-0.1",
  "engineBuildDigest": "…", "models": [{"name": "r1", "sha256": "…"}], "configDigest": "…",
  "devManifestDigest": "…", "evaluatorVersion": "…",
  "reviewThresholds": {"event": 8500, "harmony": 8000, "measure": 8000},
  "frozenTargets": {"K1": {"ge10": 6.0, "8to10": 12.0}, "K2": {"ge10": 0.005, "8to10": 0.01}},
  "frozenAt": "2026-12-15",
  "approvedBy": "orchestrator"
}
```

동결한 뒤에는 이 artifact를 바꾸지 않는다. 바꾸면 버전을 올리고, 그 결과는 다음 sealed 세트로만 평가한다.

### 7.3 Sealed 실행

1. W9가 동결 빌드(엔진 + 모델 + 설정)를 패키지로 만든다. digest는 artifact와 일치해야 한다.
2. Custodian이 자기 PC에서 `clavis-eval sealed --build <패키지> --manifest <sealed manifest> --artifact <threshold artifact>`를 실행한다. 네트워크는 끈다.
3. 출력은 **집계 보고서만** 공유한다: 전체 지표, 슬라이스별 지표(표본 부족 슬라이스는 숨김), 오류 유형 히스토그램. 페이지별 상세, 이미지, 출력 XML은 Custodian 밖으로 나가지 않는다.
4. 실행 기록을 `docs/gates/sealed-ledger.md`(추가 전용)에 남긴다: 날짜, 빌드 digest, artifact digest, 결과 digest, 판정.
5. **횟수 제한**: sealed 세트 하나당 공식 실행은 최대 2회다(G3 1회, 수정 후 재평가 1회). 이후에는 소각(Dev로 이관)하고 새 세트를 만든다.
6. 실패해도 동결 기준을 바꾸지 않는다. 원인은 오류 유형 히스토그램과 Dev 재현으로 분석한다.

### 7.4 갱신

v1.0 릴리스 뒤와 매 주요 버전마다 sealed를 새로 만든다. 소각한 세트는 Dev로 옮기되 `burned: true`로 표시한다.

## 8. 무결성 장치

GENERALIZATION_CHARTER.md 6절의 장치를 W4가 구현하고 W1이 CI에 연결한다.

- `eval/integrity/hardcode_scan.py` — H1–H9 규칙, 허용 목록 `configs/integrity/allowlist.yaml`
- `eval/integrity/leakage.py` — pHash 근접 중복, 멜로디 지문 중복. Custodian이 준 sealed 해시 목록도 읽는다
- `eval/metamorphic/` — 변환 8종과 통과 기준
- `eval/fresh_seed/` — nightly 새 시드 50곡과 관리 한계
- 평가기 자체 검증: **돌연변이 시험**. GT에 알려진 오류(음높이 이동, 음표 삭제, 마디 분할, 코드 변경, 가사 치환 등 20종 이상)를 주입해 지표가 정확히 그만큼 변하는지 확인한다.

## 9. 게이트 판정 기준

판정 어휘: **PASS**(모든 필수 항목 충족) · **CONDITIONAL PASS**(비필수 미달이 있고 기한 내 해소 계획이 있음) · **FAIL**.

### G0 — 자와 기반

- [ ] 저장소, CI(Linux + Windows), 계약 패키지 v0.1과 JSON Schema, LSTL 코어가 병합됨
- [ ] 평가기 v1: 투영, 정렬, 전 지표, bootstrap. 돌연변이 시험 20종 이상 통과
- [ ] Dev v0 ≥ 20쪽, manifest와 권리 기록 완비, 분리 검사 통과
- [ ] B0 기준선 보고서(3개 기준선, Dev v0와 SYN-Val)
- [ ] 하드코딩 스캐너, 누출 검사, import 방향 검사가 CI에서 동작
- [ ] Sealed 절차 도구(집계 전용 실행기, 해시 목록, 원장 양식) 준비

### G1 — 수직 슬라이스

- [ ] CLI가 이미지·PDF → 8.1절 파일 전체를 생성(REF-LAPTOP에서 예산의 2배 이내)
- [ ] 데이터 팩토리: 렌더러 2개 이상, 음악 폰트 4개 이상, 렌더 5,000쪽 이상, 라이선스 등록부 완비, 저장소 데이터 총량 ≤ 4 GB
- [ ] 열화기 v1: 연산 계열 8개 이상, 촬영 경로 프리셋, 사실성 보고서 v1
- [ ] 보표 검출 재현율 SYN ≥ 99%, R-Dev ≥ 97%. interline 오차 중앙값 ≤ 3%
- [ ] 기호 인식 v0(무학습 구성과 첫 CPU 분류기)의 SYN-Val 지표가 interline 구간별로 보고됨
- [ ] 모든 학습의 CPU 벽시계 시간 실측(모델당 ≤ 4시간). GPU 사용 0
- [ ] 결정성: 같은 OS에서 3회 실행과 1·4스레드 결과가 바이트 동일
- [ ] Dev 전체 지표와 B0 비교표(목표 판정 없음)

### G2 — 저해상도 견고성

- [ ] R-Dev(Dev-Check)에서 K1이 최고 기준선 대비 상대 30% 이상 우위(paired bootstrap 95% CI가 0을 포함하지 않음)
- [ ] 해상도 곡선이 PT(PLAN.md 4절)에 근접. 미달 구간은 원인과 계획을 제시
- [ ] 변환 불변성 통과율 ≥ 95%, 새 시드 합성 시험이 관리 한계 안
- [ ] ECE ≤ 5%(Dev-Check, 요소 유형별). K2와 flag 부담 보고
- [ ] 예산 충족: p50 ≤ 20 s, p95 ≤ 45 s, RSS ≤ 1.5 GiB
- [ ] 규칙 카탈로그 전 규칙의 ablation 기여도 보고(기여 0 이하 규칙 처리 계획 포함)
- [ ] 임계값 동결 artifact 초안과 PT 조정안 제출. 미달 항목은 PLAN.md 7.4절 확장 규칙의 선택지와 함께 보고

### G3 — 리드시트 완성 + Sealed #1

- [ ] 코드, 가사(한·영, 여러 절), 구조·진행, 2성부, 여러 페이지의 Dev 지표가 보고됨
- [ ] 임계값 artifact 동결(오케스트레이터 승인 기록)
- [ ] Custodian sealed #1: 동결 목표 충족 → **v1.0 RC**
- [ ] HTTP 규약 적합성 스위트 통과, HarmonyMaker 어댑터 설계서 제출

### G4 — 통합 릴리스

- [ ] HarmonyMaker 저장소 측 어댑터로 E2E 통과(HarmonyMaker 작업, 별도 지시)
- [ ] 배포 사양(D7) 확정과 운영 점검

## 10. Custodian 가이드 (사용자용)

Custodian은 **개발에 관여하지 않는** 보관자다. 권장: 사용자 본인. 지정 마감은 G2 전(약 12주차)이다.

### 10.0 지금 바로 지킬 보류 규칙 (보관자 지정 전에도 필수)

- 가진 찬양 악보(R-TGT 후보)를 "Dev 후보"와 "보류" 두 폴더로 나눈다. 보류는 10–15쪽 이상 남긴다.
- 보류 폴더의 악보는 워커, 오케스트레이터, 어떤 대화에도 넘기지 않는다. 한 번이라도 넘기면 그 악보는 영구히 Dev 전용이다.
- 이미 HarmonyMaker 작업에 쓴 이미지(R-LEGACY)는 원래 Dev 전용이므로 이 규칙과 관계없다.

### 10.1 촬영 세션 (R-PC) — 회당 약 1.5시간

1. W4가 준비한 인쇄 묶음(PDF)을 받는다. Dev 묶음은 W4가 고른다. **Sealed 묶음은 평가 전용 곡 풀에서 Custodian이 직접 무작위로 고르고, 목록을 누구에게도 알리지 않는다.**
2. A4로 인쇄한다. 가능하면 프린터 2종을 쓴다.
3. 페이지마다 2–3가지 조건으로 수집한다: 밝은 곳 정면, 실내등 비스듬히(15–30°), 그림자 또는 휜 종이, 스캐너 150 dpi, 카카오톡으로 보냈다가 받은 사진, 화면 캡처.
4. W4의 수집 도구로 폴더를 등록한다. 도구가 렌더와 자동 정합해 GT를 붙인다. Sealed는 Custodian 전용 폴더에 두고 **해시 목록만** W4에 준다.

### 10.2 대상 도메인 정답 (R-TGT)

1. 권리를 확인한 악보 이미지를 고른다. 평가 전용이며 외부로 공유하지 않는다.
2. 쪽마다 무작위로 2–4개 시스템을 골라 MuseScore로 전사한다(쪽당 15–30분). 다른 날 한 번 더 대조한다.
3. Dev용은 W4에게 비공개 경로로 전달한다(저장소 커밋 금지). Sealed용은 Custodian만 보관한다.

### 10.3 Sealed 실행 — 회당 약 30분

W9가 준 동결 패키지와 W4의 sealed 실행기를 Custodian PC에서 실행한다. 생성된 **집계 보고서만** 오케스트레이터에게 전달한다.

### 10.4 예상 총 작업량

| 작업 | 시간 |
|---|---|
| 촬영 세션 #1 (Dev) | 1.5시간 |
| R-LEGACY 파일과 기존 전사 전달 | 0.5시간 |
| R-TGT Dev 15–20쪽(부분 정답) | 5–10시간 |
| 촬영 세션 #2 (Sealed) | 1.5시간 |
| R-TGT Sealed 10쪽 | 3–5시간 |
| Sealed 실행(최대 2회) | 1시간 |
