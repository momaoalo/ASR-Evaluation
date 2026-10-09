# Dashboard 1.6.0 — verified scope

Date: 2026-09-17. Based on the complete 1.5.2 application and the Windows import-lock fix. This release changes reporting, review workflows, input safeguards, exports and packaging; not ASR provider adapters or normalization/scoring rules.

## Executed

- Full Python suite: **388 tests: 353 passed, 35 skipped, 0 failures and 0 errors**.
- New executed tests: **40 dashboard/reference regressions and 11 updater tests**, included in the total. The 10 newly added genuine Flask route tests are present but skipped here.
- **76 Chromium checks passed** against actual application templates/scripts/styles, actual exported report data and real Python storage/aggregation/review functions. All 12 saved runs and their inspectors opened. Original-reference access worked for failed records. Both cleaning views, search, source/reference safeguards, supplied input fields, pair changes, explicit exclusions, reference re-score clones, and offline CSV/JSON downloads were checked.
- A chart-keyboard bug was found during verification (SVG elements do not implement HTMLElement.click) and fixed by dispatching a bubbling MouseEvent. Click and keyboard inspection were both retested.
- Independent Dynamic Programming rechecked **68 stored WER/CER values** (17 successful outputs × two scoring views × two metrics) and C/S/D/I invariants. Every value matched. This is arithmetic verification, not audio verification.
- Original normalizer, evaluator, profiles, HUMAIN and ElevenLabs adapters, bundled MP3 and Ground Truth were hash-compared with 1.5.2 and are unchanged.
- Python compilation and JavaScript syntax checks passed.
- The completed ZIP was CRC-checked and extracted into a fresh directory: the suite again reported 388 tests, 353 passed and 35 explicitly skipped; package/UI hashes matched. The complete updater was also applied to a temporary original 1.5.2 project: 43 files updated, config.py/.env/config.local.json/data remained byte-identical, and a repeat update copied zero files.
- Synthetic compact-record aggregation: 100 cases/200 outputs ≈8.82 ms; 1000 cases/2000 outputs ≈97.99 ms in this container. All records remained listed. This excludes disk/network/audio/model time and is not a performance guarantee.

## Actual snapshot regression

The supplied report has 12 evaluation attempts, 17 scored outputs and 3 failed model outputs, plus 2 pre-inference media failures. The new evidenced audio-input count is **3**, not the old misleading 6. It counts known sources/intervals or hashes, not acoustically unique spoken content. Differently encoded uploads without proven lineage remain separate.

The live HUMAIN/ElevenLabs pair shares **3 input/reference test cases**, one flagged for reference review. Its high error is retained, not filtered to make a better benchmark. The two old text-import models and missing-settings failures remain visible in history but do not zero that live comparison. Reference correction requires user confirmation and creates a separate reviewed run without calling ASR. The generic application ZIP does not contain the user's saved runs or credentials; the separate HTML preview contains their provided snapshot.

## Installer scope

UPDATE_EXISTING.bat runs standard-library update_existing.py from the newly extracted release outside the existing project. It validates payload hashes, refuses while port 5000 is occupied, backs up old runtime files outside the project, and rolls code back on a failed copy. It never replaces config.py, .env, config.local.json or any data/ file. No old-source folder or saved result is deleted. Transient Windows-style sharing failures were simulated in Python tests. Real Windows BAT execution was not available here.

## Explicit limitations

Flask, JiWER and Waitress are unavailable in this build environment; attempted installation was blocked by network/DNS access. The **35 skipped tests are 34 genuine Flask route checks and 1 JiWER parity check**. Scoring tests use the existing RapidFuzz fallback; skips are not successes.

The agent-browser CLI was unavailable. Playwright used system Chromium with Jinja-rendered HTML and an injected fetch transport to actual Python storage/report functions. These are **not live Flask HTTP end-to-end tests**, and do not establish Windows launch behavior, actual provider keys/permissions/quotas, or live transcription latency. CSV/JSON blob downloads from the independent report were exercised in Chromium.

No live ASR request, credential validation or independent listening to the alternate YouTube clip took place. Automatic reference flags are heuristic, not proof; cases are never silently removed for high WER. Generalization beyond the tested cases is not guaranteed.

Run TEST_WINDOWS.bat on the user's existing installed Python 3.12 environment to execute available Flask/JiWER tests. No paid provider requests run in that suite. Existing results are read rather than automatically re-scored during update.

## Evidence

- python_tests.txt / python_tests.json: complete suite and explicit skips.
- browser_checks.json: 76 checks and browser transport scope.
- actual_arithmetic_checks.json: independent checks on the user's supplied snapshot, not the live server.
- performance.json: compact-record timing and limits.
- tests/test_dashboard_v16.py, tests/test_dashboard_routes_v16.py, tests/test_update_existing.py: repeatable regression tests.

## Primary references

- JiWER metrics and alignment: https://jitsi.github.io/jiwer/usage/
- W3C complex-chart textual alternatives: https://www.w3.org/WAI/tutorials/images/complex/
