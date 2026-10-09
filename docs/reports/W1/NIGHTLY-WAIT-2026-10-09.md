# [W1] 야간 대기 실행과 사용자 예약 스크립트 — 2026-10-09
판정: PARTIAL — 로컬 PASS, 두 OS CI 대기

## 1. 요약
run --wait가 다음 01:00–07:00 창을 기다리고 빈 큐도 닫힐 때까지 감시한다.
현재 사용자·일반 권한·매일 00:55·AC 전원·IgnoreNew 예약 등록/해제 스크립트를 제공한다.
사용자 지시에 따라 실제 스케줄러 등록은 하지 않았다.

## 2. 변경
training/jobs/{clock,window,runner,__main__}.py, scripts/{register,unregister}-nightly.ps1.
기존 run/manual 동작 유지, --manual과 --wait 동시 사용 거부. 잠금 점유 시 즉시 종료 코드 75.
일시 중지 및 고정된 창 종료 날짜를 적용하고 종료 시 checkpoint stop을 전달한다.

## 3. 계약·결정
Orchestrator 2026-10-09 야간 시작 지시. 외부 엔진 계약/의존성 변경 없음.
기존 H9 두 건은 AST digest 그대로 줄 번호만 이동했다. 신규 예외 없음.
PLATFORM-NIGHTLY-001 운영 규칙 등록.

## 4. 검증
야간 경계·잠금·빈 큐·pause·날짜를 넘는 suspend/deadline 논리 시각 시험 9 passed.
ruff, mypy 92파일, AST PASS. 등록 스크립트를 -WhatIf로 실행해 예약 객체만 생성하고 실제 등록하지 않았다.
전체 Windows 명령: python -m training.jobs.short run pytest tests/ --cov=clavis --cov=scripts --cov=eval --cov=training.jobs --cov-report=json:work/nightly-coverage.json --junitxml=work/nightly-tests.xml
Windows 전체 1484 passed, 실패/skip 0. 슬롯 99.813초, peak RSS 324517888 bytes. 두 OS CI 대기.

## 5. 지표
Windows REF-LAPTOP RAM 24 GB(16+8 GB DDR4-3200 듀얼 채널). 슬롯 시험 2스레드, RAM 3 GB.
합성 운영 시험만 수행. 인식 성능/Dev/SYN-Val/sealed/95% CI NOT_RUN.
실제 야간 큐·학습·렌더 시작 NOT_RUN: 예약 등록은 사용자에게 맡긴다.

## 6. 일반화
입력 식별 분기·음악 요소 생성·새 인식 상수 없음. 운영 규칙만 변경.
사적 데이터 접근·GPU·유료 컴퓨트 0. 인식 ablation은 해당 없음.

## 7. 한계와 실패
사용자가 로그인 상태를 유지해야 한다. 절전 깨우기는 하드웨어/OS 설정에 달려 있다.
대기 모드가 머신 잠금을 잡으므로 취침 전에 켠다. 기존 사용자 pause를 자동으로 풀지 않는다.
스케줄러 등록/삭제는 -WhatIf만 검증했다. 사용자 승인 없는 실제 등록은 하지 않았다.

## 8. 다음 단계
등록: powershell -NoProfile -ExecutionPolicy Bypass -File scripts/register-nightly.ps1
해제: powershell -NoProfile -ExecutionPolicy Bypass -File scripts/unregister-nightly.ps1
직접 대기: uv run --locked --all-groups python -m training.jobs run --wait
사용자는 저장소 루트에서 명령을 실행한다. 그 다음 작업은 불안정 시험의 시각 주입과 3슬롯 부하 반복 검증이다.
