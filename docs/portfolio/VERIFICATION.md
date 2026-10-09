# Migration verification — 4 October 2026

## Fresh checks performed

- Recovered the complete `ASR_Evaluator_Dashboard_1_6_2.zip` archive.
- Safely extracted it and ran the supplied `verify_package.py`: all original package
  hashes matched before portfolio additions.
- Parsed all **49 original Python files** successfully.
- Checked original text files for common GitHub-token, private-key, AWS access-key,
  and long literal API-secret patterns. No matching credential was detected. This
  is a scoped pattern check, not proof of universal secrecy or a full security audit.
- Executed the original offline test runner with the original media fixture present.

| Test-run measure | Fresh observed result |
|---|---:|
| Discovered / run | 407 |
| Passed | 372 |
| Skipped | 35 |
| Failures | 0 |
| Errors | 0 |

The detailed result is in `verification/migration/test_results.json`. Python version
was 3.13.5. The original recommended setup remains Python 3.12.

## Important limits

Flask and JiWER were unavailable in this execution environment. Attempting to
install the pinned dependencies failed because network name resolution was
unavailable. Tests designed to require Flask or official JiWER parity were skipped,
not passed. Evaluation used the original RapidFuzz fallback.

No paid ASR request was made. Provider account authorization, a fresh live-provider
comparison, a full Flask UI/backend run, and Windows execution were not established
by this test run. The full test run included the original local audio fixture;
a source-only clone without that fixture cannot be assumed to have the same result.

Standalone-report browser checks, when listed in the migration evidence, concern
that exported report only. They are not a substitute for Flask integration tests.

## Standalone report check

The original HTML report renderer was exercised with the new synthetic English
text fixture. The exported report was opened in Chromium using Playwright, and a
real screenshot was captured. The synthetic-data label was present and no uncaught
page JavaScript errors were observed. This check does not run Flask or provider APIs.
Evidence: `verification/migration/browser_report.json` and
`docs/assets/synthetic-dashboard.jpg`.

## Reproduce locally

Install the original requirements and external media tools, restore the original
sample MP3, then run:

```bash
python tools/verify_source.py
python verify_package.py
python run_tests.py
```

`run_tests.py` writes your own fresh `verification/local_test_results.json`, including
skip reasons. Inspect the counts rather than treating `OK (skipped=...)` as a complete
pass. All existing `verification/dashboard_*` reports remain historical evidence.
