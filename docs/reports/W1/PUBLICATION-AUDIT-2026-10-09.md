# [W1] 공개 전 감사 — 2026-10-09
판정: PARTIAL — 검사 완료, 과거 사용자 경로·기기 식별자 잔존으로 공개 준비 PASS 아님

## 1. 요약 (3줄 이내)
원격 브랜치 35개 + PR head 34개 + PR merge 9개, 커밋 151개/고유 blob 818개를 검사했다.
실사 이미지·PDF·*.private·사적 GT/manifest·reserved/sealed 해시 inventory·비밀값은 검출되지 않았다.
사용자 프로필 경로와 W8 검증 보고서의 실제 호스트명을 발견했다. 현재 main 문서 경로를 정리하되 히스토리는 유지한다.

## 2. 변경 (PR 링크, 주요 파일·모듈)
브랜치 `w1/publication-audit`의 공개 전 감사/문서 정리 PR.
GUIDE-DEV11.ko.md, GUIDE-R-LEGACY.ko.md, HANDOFF_PROMPTS.md, KICKOFF_WAVE_A.md의 경로 8곳을 일반화했다.
설명에는 %USERPROFILE%, 실행 가능한 PowerShell 예시는 Join-Path $env:USERPROFILE을 쓴다.
저장소 visibility와 CI는 변경하지 않았다. 외부 브랜치의 pending 변경이나 히스토리는 재작성하지 않았다.

## 3. 계약·결정 (사용한 계약 버전, CCR·ADR 번호)
Orchestrator 2026-10-09 A등급 승인: 공개 전 감사 및 추적 문서 경로 정리. 계약 v0.1 변경 없음.
공개 전환은 사용자만 수행한다. 공개 완료 통보 전 PR 두 OS 복원/COMMON10 CI 규칙 변경은 적용하지 않는다.

## 4. 검증 (테스트 수, CI 결과, 결정성, 스캐너, 라이선스 스캔)
Git 모든 대상 commit tree와 blob을 열거해 삭제·이름 변경된 파일도 검사했다. 총 5771229 bytes, 최대 blob 379505 bytes.
확장자/UTF-8/binary/LFS/링크 검사, 비밀값 패턴·자격정보 literal·내장 이미지/PDF base64·개인정보 후보 검사와 수동 분류를 병행했다.
Gitleaks 8.30.1 공식 checksum 확인 후 기본 규칙, 빈 ignore, inline allow 무시, 100% redaction으로 동일 refs를 검사했다: 129개 diff commit, 6188331 bytes, 816ms, 발견 0/exit 0. 전체 tree 검사는 151 commits를 포함한다.
Git author/committer 이메일은 모두 GitHub noreply 주소였다. 비밀값/호스트명 원문은 보고서에 복사하지 않았다.
로컬 Windows 전체 588 passed, 실패/skip 0, 44.211초. 명령: `python -m training.jobs --root work/publication-validation run --manual` (pytest tests/, JUnit; 머신 독점 큐 threads=2).
문서 UTF-8/JSON/NUL/경로 재검색/git diff --check로 수정 검증. 원격은 문서 전용 경량 CI 대상으로 확인한다.

## 5. 지표 (평가기 JSON 경로 + 핵심 수치 표: 이전 대비 변화와 95% CI, 슬라이스별)
[PUBLICATION-AUDIT-2026-10-09.json](PUBLICATION-AUDIT-2026-10-09.json)에 ref별 SHA, 발견 blob/위치, 검사 결과를 기록했다.
바이너리·이미지/PDF·LFS·*.private·symlink/submodule 0. MusicXML 경로 27개는 합성 golden 26개와 W8 합성 oracle 1개다.
sealed-ledger는 빈 양식, sealed-evidence는 NOT_RUN/coverage 보고, manifest는 합성 demo/fixture·공개 W3C 출처 자료다.
전체시험 큐 벽시계 45.5초, CPU 38.046875초, peak RSS 227201024 bytes. RAM 24 GB(16+8), DDR4-3200 듀얼 채널.
인식 평가/Dev/sealed/실사/학습은 NOT_RUN. 성능 개선·95% CI 비교 없음.

## 6. 일반화 점검 (헌장 8절 체크리스트, 실패 패턴 패키지 첨부 여부)
저장소 객체만 검사했다. CLAVIS_PRIVATE_ROOT나 사용자 사적 폴더는 열지 않았다.
인식·규칙·임계값·데이터 생성 변경 없음. 감사 결과에 사적 내용·기기 식별자 원문을 다시 넣지 않았다.

## 7. 알려진 한계와 실패 사례 (숨기지 말 것)
**공개 전 확인할 잔존 정보:**
- 과거 4개 문서의 실제 사용자 프로필 경로: 고유 blob 기준 10회. 현재 main 기준 8곳을 정리해도 과거 commit과 오래된 브랜치 tip에는 남는다.
- `docs/reports/W8/T8.1-validation.json`의 `/tests/hostname`(12행): 실제 노트북 호스트명. `origin/w8/start` 및 PR25 head/merge에 존재하며 최초 commit은 `0437ab18e8ec63daa8e518d7996ad2ebff8a0fdc`다.
- W2 pending `training/data/README.md`의 프로필 경로 1건은 일반 USER 자리표시자이며 실제 사용자 정보는 아니다.
히스토리 재작성 금지 지시를 지켰으므로 위 잔존 정보를 제거했다고 주장하지 않는다. 호스트명 삭제 시에도 기존 commit은 남는다.
검사는 JSON에 고정한 ref SHA의 스냅샷이다. 이후 push, 원격의 삭제된 도달 불가 객체, Issues/PR 대화/Actions 로그·artifact/Release 첨부는 이번 Git 객체 감사 범위 밖이다.
패턴 검사로 모든 종류의 비밀을 수학적으로 배제할 수는 없다. 이번 범위의 검출 결과와 알려진 잔존을 보고한다.

## 8. 다음 단계 / 필요한 결정 / 블로커
경로 정리 PR은 승인된 범위로 CI 확인 후 병합한다. 공개 준비 PASS 선언은 보류한다.
Orchestrator/사용자는 과거 사용자 프로필 경로와 호스트명 잔존을 확인하고 공개 진행 여부를 판정해야 한다. 임의 히스토리 재작성은 하지 않는다.
사용자가 "공개 전환 완료"를 알리면 PR 두 OS 복원(draft 제외·문서 전용 skip 유지), contents: read 유지, pull_request_target 미사용, COMMON10 갱신을 진행한다.
