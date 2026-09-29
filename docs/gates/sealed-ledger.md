# Sealed 공식 실행 원장 — 준비 양식

실제 sealed 세트/실행 기록 없음. Custodian만 원본 자료와 페이지별 결과를 보관한다.
공식 실행 후 집계 검토를 거쳐 로컬 append-only JSONL receipt의 다음 항목만 기록한다.

| 날짜 | 세트 digest | 빌드 digest | artifact digest | 집계 결과 digest | 회차(1/2) | 판정 | entry digest |
|---|---|---|---|---|---|---|---|

세트당 공식 실행 최대 2회. preflight/합성 시험은 여기에 기록하지 않는다.
기존 행 수정/삭제 대신 보정 내용을 별도 기록하고 원본 JSONL chain을 보존한다.
이미지·정답·페이지 ID·오류 사례·사적 경로는 기록하지 않는다.
절차와 명령: [Custodian 준비 안내](../../eval/sealed/README.md).
