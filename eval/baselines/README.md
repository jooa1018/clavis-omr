# CPU 기준선 외부 실행기

고정: Audiveris 5.10.2, homr 457e7c6518a10ba755db2e60883419e56c4d7369,
oemer 0.1.8. 버전·명령·oemer wheel digest는 configs/eval/baselines.json에 기록한다.
엔진/평가기에서 이들 패키지를 import하거나 소스를 복사하지 않는다.

Audiveris는 Docker 실행, homr/oemer는 각각 독립 venv를 가진 별도 Docker 이미지 안에서
실행한다. venv만으로는 네트워크를 차단할 수 없어 외부 컨테이너를 추가한 것이다.
GPU 장치를 전달하지 않고 CPU 패키지만 설치한다. baseline 가중치를 Clavis 모델이나
배포물에 넣지 않는다. 설치·가중치 수령은 평가 실행과 분리한다.

## 설치 환경 준비 목록 (아직 실행하지 않음)

1. 로컬 Docker를 준비한다. 3 GiB 이상의 디스크 여유와 이미지/가중치 저장 공간을
   확인한다. 이미지 빌드·다운로드·대량 추론은 W1 큐 준비 후 수행한다.
2. Audiveris 공식 5.10.2 Linux 배포를 별도 이미지에 설치하고 `audiveris -version`으로
   확인한다. 컨테이너 PATH에 audiveris 실행기가 있어야 한다. 배포 파일·기반 이미지·
   JRE·Tesseract의 버전과 SHA256을 설치 lock에 남긴다.
3. homr 지정 revision을 별도 빌드 환경에서 checkout한다. Python 3.12 독립 venv를
   `/opt/homr-venv`에 만들고 CPU extra만 설치한다. 명령은 해당 venv의 `homr`다.
   체크아웃 HEAD·잠근 종속성·CPU backend·사전 준비한 가중치 digest를 기록한다.
4. oemer==0.1.8을 `/opt/oemer-venv`에 설치하고 배포 wheel SHA256을 확인한다.
   기본 ONNX Runtime CPU를 사용한다. `--use-tf`, 이미지별 deskew 변경 등은 쓰지 않는다.
   모델은 별도 설치 단계에서 미리 준비한다. 실행 중 자동 다운로드가 필요하면 실패다.
5. 각 최종 이미지에 아래 provenance labels를 넣고 **로컬 image ID sha256**을 기록한다.
   라벨만 붙이는 것은 버전 검증이 아니다. 설치 lock·실행 버전 확인·weights 목록과
   그 digest를 별도 감사 자료로 보관한다. 검증 전 이미지는 B0에 사용하지 않는다.

```text
org.clavis.baseline = audiveris | homr | oemer
org.clavis.version = 해당 고정 버전 또는 전체 revision
org.clavis.lockDigest = 설치 lock SHA256
org.clavis.weightsDigest = 가중치/내장 분류기 inventory SHA256
```

이 저장소에는 이미지·venv·GPL/AGPL 소스·가중치를 넣지 않는다. 공식 Docker image/tag가
있다고 가정하지 않는다. 설치 lock과 실제 실행 환경은 아직 NOT_RUN이다.

## 수동 한 페이지 시험

기존 CLAVIS_PRIVATE_ROOT 안의 Dev 입력만 지정한다. OR-001 범위에서 사용자가 수동으로
실행할 때만 다음 명령을 사용한다. sealed용 도구가 아니다.

```powershell
.venv\Scripts\python.exe -m eval.baselines oemer --image-id sha256:<검증한_로컬_image_ID> --input dev/dev-001/original.png --cache baseline-cache --dataset-digest <manifest_SHA256> --manual-or001
```

한 페이지 PNG/JPEG만 받는다. PDF는 준비 단계에서 페이지로 래스터화한 후 같은 입력
정의를 세 기준선에 사용해야 한다. 원본을 별도 작업 디렉터리에 복사하므로 homr의
입력 옆 출력도 원본 폴더에 쓰이지 않는다.

Docker는 pull 금지, network=none, 읽기 전용 root, 2560 MiB 메모리/동일 swap 한도,
2 CPU/라이브러리 2스레드, 프로세스 256개, capability 없음으로 실행한다. 추론 timeout은
480초이고 timeout/크래시/무출력은 FAIL이다. 컨테이너 ID로 종료 정리를 수행한다.
stdout/stderr는 사적 내용 유출을 피하려고 콘솔에 전달하지 않는다.
페이지별 실행을 병렬 루프로 호출하지 않는다. W1 큐가 생기면 그 단일 큐 payload로
이 함수를 연결하고 전체 B0를 실행한다. 현재 호출 가능한 W1 큐 API는 없다.

## 캐시·실패·평가

키는 입력/데이터셋/이미지 ID/runner/정책 digest를 포함한다. 완료 출력의 SHA256을
확인한 캐시만 재사용한다. 중단된 디렉터리를 성공 캐시로 취급하지 않는다.
여러 MusicXML/mxl은 movement별 파일과 digest를 각각 남기며 합치거나 최고 결과만
고르지 않는다. 최대 128 movement, 파일당 8 MiB를 검사한다. run PASS는 프로세스가
출력을 만들었다는 뜻이며 MusicXML 정답률·G0 통과가 아니다. 파싱 실패/분할 출력의
손실도 B0 평가기에 넘겨 실패로 기록해야 한다. 압축 MXL 해제·전체 dataset 평가 연결은
후속 B0 통합 단계다. 이 러너는 GT를 읽지 않는다.

시험은 가짜 subprocess 응답과 실제 Python 외부 stub만 사용한다. 실제 Docker 격리,
세 기준선 설치·CPU 추론·B0는 NOT_RUN이다. 실제 외부 코드를 설치하지 않았으므로
라이선스 검토와 분리 경계를 넘어서는 코드 복사도 없다.

## 공식 근거 (2026-09-29 확인)

- [Audiveris 고정 릴리스](https://github.com/Audiveris/audiveris/releases/tag/5.10.2),
  [CLI](https://audiveris.github.io/audiveris/_pages/guides/advanced/cli/): batch/transcribe/export/output.
- [homr 지정 revision README](https://github.com/liebharc/homr/blob/457e7c6518a10ba755db2e60883419e56c4d7369/README.md):
  CPU extra, CLI 및 입력 옆 출력. GitHub API로 revision/README를 확인했다.
- [oemer 0.1.8](https://pypi.org/project/oemer/0.1.8/): 기본 ONNX, CLI, wheel hash,
  첫 실행의 가중치 다운로드 필요. 평가 실행에서는 네트워크로 받지 않는다.
