# 노트북 CPU 단일 큐 v0 (W1)

`uv sync --locked --all-groups` 후 `uv run --locked --all-groups python -m training.jobs`를 사용한다.
기본 큐는 `~/.clavis/jobs`, 머신 공통 실행 잠금은 `~/.clavis/worker.lock`이다. 다른 worktree도 같은 큐를 사용한다.
`--root`는 상태 경로를 바꾸지만 실행 잠금은 바뀌지 않는다. 큐를 여러 개 만들어도 병렬 worker는 실행되지 않는다.

## 요청과 실행
요청 JSON의 필수 키는 `module`, `cwd`(공개 checkout 절대 경로), `config`, `seed`, `data_digest`(SHA-256), `git_sha`(40 hex)다.
`arguments`는 선택 CLI 인자 목록이다. `threads` 기본 8(허용 1–8)은 연산 자원 요청이며 OS 총 스레드 수가 아니다.
`ram_bytes` 기본/최대 3,000,000,000, `wall_seconds` 기본/최대 14,400이다. 재개 전후 벽시계 합에도 상한을 적용한다.
사적 경로는 요청/config/인자/보고서에 넣지 않고 **CLAVIS_PRIVATE_ROOT 환경 변수로만** 전달한다.
`config`에는 공개 설정만 넣는다. 원문 stdout/stderr는 보관하지 않는다. 결과는 job directory에 별도로 저장한다.

```powershell
uv run --locked --all-groups python -m training.jobs submit work/job-request.json
uv run --locked --all-groups python -m training.jobs status
uv run --locked --all-groups python -m training.jobs run --manual
uv run --locked --all-groups python -m training.jobs pause
uv run --locked --all-groups python -m training.jobs resume
uv run --locked --all-groups python -m training.jobs run --manual
```

`run`은 로컬 시간 01:00 이상 07:00 미만에만 시작/계속한다. 밖에서는 큐를 남기고 종료한다.
`--manual`은 사용자가 수동으로 시작할 때만 사용한다. `resume`은 상태만 풀며 실행을 자동 시작하지 않는다.
`pause`는 다른 터미널에서도 가능하다. 중단 파일을 전달해 최대 2초 checkpoint 시간을 준 후 작업 트리를 종료한다.
Ctrl+C도 큐를 pause하고 종료한다. 다음 실행에서 비정상 종료된 작업은 paused로 회수되므로 `resume`을 다시 실행한다.
자동 Task Scheduler 등록이나 무거운 실제 작업의 시작은 이 구현에 포함되지 않는다.

## 워커 API
`Queue().submit(JobSpec(...))`, `run(Queue(), manual=False)`를 사용할 수 있다.
작업은 Python module로 실행한다. 외부 도구가 필요하면 소유 워커 module에서 subprocess로 실행하고 반환값을 검사한다.
Windows 자식·손자는 Job Object에 속하고 affinity/Below Normal/메모리/kill-on-close를 상속한다.
CPU가 8개 이하면 한 개를 남긴다. 사용할 수 있는 CPU가 한 개뿐이면 작업을 거부한다.
환경 변수 OMP/MKL/OPENBLAS/NUMEXPR와 설치된 torch intra/inter, cv2, LightGBM Booster/Dataset, ORT session 설정을 주입한다.
Python 손자도 큐 전용 sitecustomize를 통해 설정을 주입받는다. Python `-S`, `-I`로 주입을 우회하거나 자식에서 affinity를 넓히면 안 된다.
Torch/LightGBM/ORT가 설치되지 않았다면 설치를 자동으로 하지 않는다. 실제 학습 전에 해당 라이브러리 버전별 smoke 검증이 필요하다.
OS 총 스레드는 진단값이다. CPU/RSS를 100ms마다 합산하며 평균/최대 논리 CPU 환산 및 평균>8 경고를 기록한다.

```python
from training.jobs.context import Context
context = Context()
state = context.load() or {"step": 0}
# 각 bounded 작업 단위 뒤에 state, RNG state 등 재개에 필요한 모든 상태를 저장한다.
context.save(state)
if context.stopping():
    # 종료한 뒤 다시 호출되면 동일 checkpoint에서 진행한다.
    pass
```

`Context.save`는 fsync+replace를 사용한다. job digest가 다른 checkpoint는 거부한다.
결과 경로는 `CLAVIS_JOB_DIR`이다. 예제 `training.jobs.example`은 작은 정수 합계만 계산하며 인식/학습을 하지 않는다.

## 제한과 상태
큐·checkout·환경 변수로 지정한 사적 루트가 있는 디스크 중 하나라도 여유 3 GB 미만이면 새 작업을 시작하지 않는다.
실행 중 부족해져도 중단한다. 사적 디렉터리는 나열하거나 읽지 않는다.
RAM/시간 초과는 failed, 사용자/시간 창/디스크 중단은 paused다. failed는 자동 재시도하지 않는다.
Windows memory limit은 job 전체 commit 상한이며 RSS도 표본 검사한다. Linux는 프로세스 그룹+RSS 감시이므로 표본 사이 일시 초과 가능성이 있다.
분리된 Linux session으로 탈출하는 daemon은 지원하지 않는다. 정상 subprocess/DataLoader가 대상이다.
기록 정본은 SQLite 상태와 experiments.jsonl 시작/종료 행이다. 원문 데이터/출력은 기록하지 않는다.
ADR-002는 Orchestrator가 2026-10-06 채택했다.
시작 시 시스템 commit 여유가 작업 RAM 상한 + 1 GB 미만이면 memory-low로 기록하고 paused 상태로 남긴다.
실행 중 hostMemorySamples에 물리 RAM 총량/여유와 페이지파일 크기, commit 여유를 기록한다. Windows는 GetPerformanceInfo와 EnumPageFiles, Linux는 /proc/meminfo를 사용한다.
메모리 구성(증설 전 8 GB / 증설 후 24 GB)을 실행 예산 보고에 명시하며 서로 섞어 비교하지 않는다.

## OR-005 짧은 실행 슬롯
전체 시험과 OR-001 렌더·학습·OCR smoke는 다음 래퍼로 실행한다.
몇 개의 단위 시험만 실행하는 경우에는 래퍼를 생략할 수 있다.

```powershell
uv run --locked --all-groups python -m training.jobs.short run pytest tests/ --junitxml=work/short-tests.xml
uv run --locked --all-groups python -m training.jobs.short status
uv run --locked --all-groups python -m training.jobs.short configure --slots 3
```

기본 3슬롯, 설정 정본은 머신 공통 `~/.clavis/short-slots.json`이다. 변경은 큐와 슬롯이 모두 비었을 때만 가능하다.
각 실행은 `worker.lock`의 공유 잠금과 별도 슬롯 잠금을 잡는다. 무거운 큐의 독점 잠금과 상호 배제되며,
프로세스 종료 시 OS가 잠금을 해제한다. Windows LockFileEx와 Linux flock을 사용한다.
슬롯이 꽉 찼거나 무거운 큐가 돌면 새 작업을 시작하지 않고 종료 코드 75를 반환한다. 여유가 생긴 뒤 다시 실행한다.
실행 성공은 0, 실패·중단은 1, 잘못된 요청·설정은 2다. `status`는 설정 수를 표시하며 현재 점유 수는 표시하지 않는다.

연산 스레드 요청은 항상 2이며 실제 CPU affinity는 기존 예약 정책을 따른다.
RAM 최대 3 GB, 기본/최대 벽시계 600초, 시작 commit 여유 +1 GB와 디스크 여유 3 GB 검사는 큐 실행기를 재사용한다.
Windows Job Object, 자손 프로세스 제한, Below Normal, CPU/RAM 표본, Ctrl+C 중단도 그대로 적용된다.
사용자가 지켜보는 수동 실행이므로 01:00–07:00 창 밖에서도 실행할 수 있다. 자동 야간 실행에는 단일 큐를 쓴다.

래퍼 옵션은 module 앞에 둔다: `run --wall-seconds 120 --items 30 --seed 7 --data-digest <sha256> <module> <args>`.
렌더·이미지 수는 호출자가 `--items`로 선언한다(기본 0: 데이터 없는 시험). 100 초과는 거부하며 실제 처리량은 호출 모듈이 제한한다.
seed 기본 0, data digest 기본 영 해시는 데이터 없는 시험용이다. 데이터를 쓰는 smoke는 실제 manifest digest를 제공한다.
사적 경로는 인자로 넣지 않고 CLAVIS_PRIVATE_ROOT만 사용한다.

출력 JSON은 상태·이유·슬롯·runId·jobId와 자원 집계만 담는다.
큐와 동일하게 원문 stdout/stderr는 저장하지 않는다. pytest 결과가 필요하면 위처럼 저장소의 무시된 work/에 JUnit을 지정한다.
실험 기록과 체크포인트는 `~/.clavis/short-runs/<runId>/<jobId>` 및 실행별 experiments.jsonl에 남는다.
원본 로그/JUnit을 커밋하지 않고 개인정보를 제거한 집계만 보고한다.
