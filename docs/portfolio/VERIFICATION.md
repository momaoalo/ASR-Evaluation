# Verification: current repository vs. historical archive

Evidence should be read according to **when it was produced** and **what it
actually tested**. A test against a mocked provider is not a successful paid
request to that provider.

## Current public GitHub checks — 9 October 2026

The [Windows onboarding CI workflow](../../.github/workflows/windows-setup-smoke.yml)
uses Windows with Python 3.12 and performs the following on a fresh checkout:

1. Runs the actual `SETUP_WINDOWS.bat` setup into a project venv.
2. Parses and exercises `INSTALL_MEDIA_WINDOWS.ps1`, including downloaded
   FFmpeg/FFprobe/Deno checksums, without WinGet.
3. Checks Python imports and yt-dlp availability.
4. Runs focused offline tests for yt-dlp, UI integrity, first saved
   transcript scoring and **mocked** live upload/provider processing.
5. Verifies source/UI files and a local Flask `/api/build` response.

The workflow is automatically executed on commits to `main`.
For current status and exact tests, consult [GitHub Actions](../../.github/workflows/windows-setup-smoke.yml)
or the repository's Actions tab; **do not treat this document as a continuously
updated pass/fail counter**.

The first-run API smoke exercises application plumbing using a fake key and
mocked response. It does **not** authenticate a real HUMAIN/ElevenLabs account,
confirm a live model ID/endpoint, or establish real-world ASR quality. A clean
public clone also lacks the historical sample MP3.

## Historical baseline — 4 October 2026

Before later GitHub changes, the recovered full archive was inspected and the
original offline runner reported:

| Metric | Historical observation |
|---|---:|
| Tests run | 407 |
| Passed | 372 |
| Skipped | 35 |
| Failures | 0 |
| Errors | 0 |

Source evidence: [migration/test_results.json](../../verification/migration/test_results.json).

This historical environment used Python 3.13.5, with Flask and JiWER unavailable.
Tests requiring those packages were **skipped**; fallback scoring was used.
This is **not a current full-suite result or a live-provider validation**.
The original media fixture was present for that run, and should not be assumed
present in a public clone.

The historical synthetic-report screenshot and browser check are captured in
[the migration record](../../verification/migration/browser_report.json).

## Reproducing appropriately

For today's public Git checkout:

```powershell
.\.venv\Scripts\python.exe verify_package.py
.\.venv\Scripts\python.exe diagnose.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_first_run_smoke.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_youtube_setup.py -v
```

The full legacy `run_tests.py` suite may need the original separately
distributed media fixture; don't represent missing-fixture errors as provider
regressions or the focused CI checks as a full-suite pass.

## Explicitly unverified

- Paid live requests and account authorization at HUMAIN/ElevenLabs
- Generalization of ASR scores to arbitrary audio, dialects, or medical tasks
- Every public YouTube video's download availability
- Public web deployment or multi-user security
- Company approvals/endorsements and third-party content licenses

See [data provenance](DATA_AND_PROVENANCE.md), [migration context](MIGRATION.md),
and [security guidance](../../SECURITY.md).
