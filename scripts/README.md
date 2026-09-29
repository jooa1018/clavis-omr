# Development and CI tools — W1

These tools are never imported by the engine.

CI runs the W4 AST scanner directly as a required step, then runs the explicit
integrity tests and an independent eval coverage gate. Existing clavis/scripts
coverage remains an independent 80% gate. Strict mypy includes eval.

```text
uv run --all-groups python -m eval.integrity.hardcode_scan --root . --out work/hardcode.json
uv run --all-groups pytest tests/eval/test_integrity.py
uv run --all-groups python scripts/integrity_status.py --ast-report work/hardcode.json --out work/integrity-status.json
```

The summary requires a successful scanner report with no findings; missing,
invalid, failed or contradictory reports return nonzero. It does not replace the
required scanner execution. The CI job uploads the AST report, this summary and
both coverage reports.

Real train/reserved inventories are not provided to CI. Synthetic leakage tests
are separate from real admission: the summary explicitly records real leakage as
NOT_RUN and trainingAdmissionAllowed=false. For actual admission, use W4's CLI
and inventory rules in `eval/integrity/README.md`; NOT_RUN must block admission.
No private or sealed inputs are read by the CI summary.

## CI 실행 비용 제어
`ci_plan.py`는 PR 변경 경로와 예약 main SHA로 작업을 선택한다.
`ci_results.py`는 한 번의 pytest coverage JSON/JUnit에서 독립 커버리지 기준과 필수 시험 결과를 판정한다.
문서 전용 PR은 UTF-8/NUL/JSON 및 git diff whitespace 검사만 수행한다.
