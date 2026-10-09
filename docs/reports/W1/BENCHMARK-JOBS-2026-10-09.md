# [W1] 독점 벤치마크 작업 — 2026-10-09

## 1. 요약
4 연산 스레드·보통 우선순위·전체 CPU affinity의 독점 측정 작업을 추가한다.
외부 부하/RAM/AC 시작 검사와 실행 중 무효 판정 및 표본 보존을 구현했다.
판정: 단위 PASS; W4 신규 H9 확인·전체 Windows·두 OS CI 대기.

## 2. 변경
training/jobs의 benchmark CLI, JobSpec.kind, runner, benchmark_monitor, power, configs/jobs/benchmark.yaml.
COMMON 10절과 실행기 README에 사용법·판정 기준을 기록했다. PLATFORM-BENCHMARK-001 등록.
선행 [PR #48](https://github.com/jooa1018/clavis-omr/pull/48)은 두 OS CI [37894532479](https://github.com/jooa1018/clavis-omr/actions/runs/37894532479) PASS 후 9623fac으로 병합됐다. W8 동일 명령 1428 passed, 슬롯 228.062초. W5·W8 슬롯 복귀 가능.

## 3. 계약·결정
Orchestrator 2026-10-09 본 지시·외부 부하 추가 판정·W4 직접 확인 요청 승인.
엔진 계약 변경 없음. 기존 batch 체크포인트 digest 호환을 유지한다.
기존 H9 두 건 AST digest 동일, 줄 번호만 갱신한다. 새 예외는 재확인 대기 루프 1건이며 W4 확인 후 등록한다.

## 4. 검증
벤치마크 관련 24 passed (5.25초). 경계·이동 창·재시도·pause·상호 잠금·프로세스 자원 상속·invalid 보존·시각 독립 체크포인트 바이트 동일 시험.
ruff/format/mypy PASS. 전체 Windows/커버리지/AST/개인정보/두 OS CI는 완료 후 기록한다.
명령: `python -m training.jobs.short run pytest tests/ --cov=clavis --cov=scripts --cov=eval --cov=training.jobs --cov-report=json:work/benchmark-coverage.json --junitxml=work/benchmark-tests.xml`.

## 5. 지표
REF-LAPTOP RAM 24 GB(16+8 GB DDR4-3200 듀얼 채널), 작업 RAM 상한 3 GB 유지.
시작: 10초 평균 외부 CPU ≤0.5, 가용 RAM ≥4 GB, AC 연결. 시작 간격 60초로 최대 10회 재확인.
실행: 전체 외부 평균 >0.5 CPU, 어떤 5초 평균 >1 CPU, RAM <2 GB, AC 이탈/미확인은 invalid.
시스템 CPU 사용에서 작업 트리 사용을 빼며 음수 표본은 0으로 자른다. 시간 가중 평균과 부분 구간을 포함한 이동 창을 계산한다.
실측 결과는 동명 JSON에 추가한다. 부하를 낮추기 위한 임의 기준 변경은 하지 않는다.

## 6. 일반화
인식·학습 데이터·평가기 지표를 변경하지 않는다. 인식 성능/Dev/SYN-Val/sealed/ablation NOT_RUN.
GPU·유료 컴퓨트·렌더·학습 0. Windows 전원 모드는 식별 정보 없는 GUID로만 기록한다.

## 7. 한계와 실패
짧게 종료된 자식의 미관찰 CPU를 추정하지 않아 외부 부하가 보수적으로 높을 수 있다. 5초 미만은 5초 창 최대 null.
AC 상태가 미확인이면 시작하지 않는다. Windows 11 전원 모드 API를 제공하지 않는 OS는 unavailable을 기록한다.
표본 간의 짧은 RAM/AC 변동은 놓칠 수 있다. 기준은 provisional이며 정상 상태 invalid 반복 시 수치와 함께 재판정을 요청한다.
원시 JUnit/절대 경로/사용자·기기 이름은 보고하지 않는다.

## 8. 다음 단계
W4 H9 확인 후 정확한 file/line/digest를 등록하고 전체 Windows·두 OS CI 통과 후 squash 병합한다.
사용법: `uv run --locked --all-groups python -m training.jobs.benchmark <module> ...`.
지연 예산 판정은 benchmark.validity=valid인 완료 결과로만 하고 슬롯 측정은 참고값이다.

참고: [Microsoft PowerGetUserConfiguredACPowerMode](https://learn.microsoft.com/en-us/windows/win32/api/powrprof/nf-powrprof-powergetuserconfiguredacpowermode), [GetSystemPowerStatus](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getsystempowerstatus), [psutil CPU 사용 측정](https://psutil.readthedocs.io/stable/index.html).
