# Clavis — 독립 OMR 엔진 (코드명)

> 상태: 설계 v1.1 — CPU 전용 재설계 (2026-09-29) · 설계 권한: Orchestrator (Opus 5.5) · 구현: Astra 워커 W1–W9
> **GPU를 쓰지 않는다.** 학습과 실행 모두 사용자의 노트북 CPU에서 하며 외부 컴퓨트 비용은 0원이다(`docs/PLAN.md` 6.3절 AD-2, 7.5절).
> "Clavis"는 임시 코드명이다. 바꿀 때는 저장소 전체를 일괄 치환한다.

Clavis는 **실사용 저해상도 악보 이미지**를 MusicXML로 바꾸는 독립 OMR 엔진이다. 대상 이미지는 휴대폰 사진, 메신저에서 재압축된 JPEG, 저해상도 스캔, 디지털 PDF다. 엔진은 MusicXML과 함께 근거 좌표(evidence), 신뢰도, 검토 힌트를 낸다.

HarmonyMaker는 이 엔진을 OMR provider 가운데 하나로 호출할 뿐이다. **이 저장소는 HarmonyMaker 코드에 의존하지 않는다.** 필요한 호환 규약은 `docs/CONTRACTS.md` 12절에 발췌해 두었다.

## 문서 지도

| 문서 | 읽는 사람 | 내용 |
|---|---|---|
| [docs/PLAN.md](docs/PLAN.md) | 사용자, 오케스트레이터, 전 워커 | **기획서**: 배경, 목표, 범위, 아키텍처, 개발 전략, 평가 요약, 분업, 게이트, 리스크, 결정 사항 |
| [docs/CONTRACTS.md](docs/CONTRACTS.md) | 전 워커 | 인터페이스 계약 v0.1: IR, 토큰 언어(LSTL), 출력 파일, CLI/HTTP 규약, 좌표·근거 |
| [docs/EVALUATION.md](docs/EVALUATION.md) | 전 워커(특히 W4), Custodian | 평가 프로토콜: 데이터 tier, 정답(GT), 지표, sealed 보관, 게이트 판정, Custodian 가이드 |
| [docs/GENERALIZATION_CHARTER.md](docs/GENERALIZATION_CHARTER.md) | 전 워커 | 일반화 헌장: 하드코딩 금지 규칙, 자동 탐지 장치, 리뷰 체크리스트 |
| [docs/tasks/00_COMMON.md](docs/tasks/00_COMMON.md) | 전 워커 | 공통 작업 규칙, 완료 정의(DoD), 보고 양식, 에스컬레이션 |
| [docs/tasks/](docs/tasks/) `W1`–`W9` | 해당 워커 | **구현 지시서** |
| [docs/tasks/HANDOFF_PROMPTS.md](docs/tasks/HANDOFF_PROMPTS.md) | 사용자 | 각 워커에게 그대로 붙여넣을 시작 메시지와 게이트 리뷰 요청 양식 |

## 시작 순서

1. 사용자: `docs/PLAN.md` 13절의 결정 사항을 확정한다. D1은 노트북 야간 실행 준비(절전 해제, 디스크 여유)다. D2(sealed 보관자)는 G2 전까지 정하면 되지만, **지금 가진 찬양 악보를 "Dev 후보"와 "보류" 폴더로 나누고 보류 쪽은 누구에게도 보여주지 않는다.**
2. Wave A 투입: W1(플랫폼·계약·배치 실행기), W4(평가), W2(데이터 팩토리), W3(열화 시뮬레이터).
3. W1이 계약 패키지 v0.1을 main에 병합하면 Wave B를 투입한다: W5(기하·레이아웃), W6(기호 인식, CPU), W7(텍스트), W8(조립·출력).
4. G1 게이트를 통과하면 Wave C로 W9(서비스·통합)를 투입한다.
5. 게이트(G0–G4)마다 워커 보고서를 오케스트레이터에게 보내 판정을 받는다. 양식은 `HANDOFF_PROMPTS.md`에 있다.
