# Documentation index

Start at the [main README](../README.md) for the portfolio presentation or the
[Arabic README](../README_AR.md). This index distinguishes **current application
contracts** from **historical version records**.

## Current application and engineering

| Need | Open |
|---|---|
| System architecture and implemented HTTP routes | [Architecture](ARCHITECTURE.md) |
| Source files and responsibility map | [Source navigation](FUNCTION_MAP.md) |
| Evaluation scoring and normalisation | [Cleaning modes](CLEANING_MODES.md) and [Arabic policy](NORMALIZATION_POLICY.md) |
| Windows setup and failure recovery | [Windows setup](WINDOWS_SETUP.md) |
| Provider keys and API configuration | [Provider configuration](portfolio/CONFIGURATION.md) |
| Source material, provider identifiers and sample honesty | [Data & provenance](portfolio/DATA_AND_PROVENANCE.md) |
| Verified test scope, skipped fixtures, and limitations | [Verification](portfolio/VERIFICATION.md) |
| Source API/library references | [Technical sources](SOURCES.md) |
| Security and local-data precautions | [Security](../SECURITY.md) |

## Code directory map

```text
app.py / run_local.py    Application API and local runner
config.py               Limits and private configuration loading
pipeline.py / jobs.py   Case preparation, provider jobs and storage orchestration
services/               Audio download/FFmpeg and HUMAIN/ElevenLabs adapters
evaluation/             Arabic normalization, edit alignments and metrics
reporting*.py           HTML/JSON/CSV report serialization and reviews
storage.py              Durable local JSON results
templates/ / static/    Web application and browser charts
tests/                  Unit, integration, and mocked-provider regressions
tools/                  Source, UI, demo and file-audit utilities
examples/               Supplied text and labeled synthetic sample exports
verification/           Historical, version-specific test evidence
```

The root contains several legacy compatibility entrypoints. Specifically,
`UPDATE_EXISTING.bat`, `update_existing.py`, `IMPORT_OLD_DATA.bat` and
`import_old_data.py` are for **previous full ZIP installations or importing
earlier local data**; they are not part of normal GitHub onboarding.
`package_manifest.json` is a **historical ZIP checksum snapshot**, not a
manifest of current Git source files. Use `verify_package.py` (without
`--full-release`) or `tools/repo_audit.py` for the current checkout.
Older source-hash evidence remains in
[original-files.json](portfolio/original-files.json), separate from current
UI integrity hashes in [ui_manifest.json](../ui_manifest.json).

## Historical engineering records

- [Dashboard 1.6.0 metrics](DASHBOARD_1_6.md) and
  [Dashboard 1.6.2 UI](DASHBOARD_1_6_2.md): version-specific decisions;
  some historical update instructions no longer apply to the GitHub clone.
- [Rule-based Arabic normalization 1.3.0](RULE_BASED_NORMALIZATION.md):
  research rationale, edge cases, and an older options interface. Today the UI
  shows **Cleaning / No cleaning** only.
- [Overview and history behavior](OVERVIEW.md) and
  [historical case-list rules](OVERVIEW_CASE_LIST.md).
- [Archived function map](function_map.json): older locations/line numbers,
  not a current route index.
- [Source migration](portfolio/MIGRATION.md) and
  [historical verification index](../verification/VERIFICATION.md).

## Demonstrations

The [sample data](../examples/sample.json) is text-only in public GitHub.
**It does not certify any HUMAIN Voice result.** The first historical source
model is unverified. The [synthetic English portfolio example](../examples/portfolio/README.md)
shows WER/CER reports without recording, transcript provenance, or paid API
claims. The original historical MP3 is **not** redistributed.

## Reproducibility

The Windows GitHub Actions workflow is defined at
[windows-setup-smoke.yml](../.github/workflows/windows-setup-smoke.yml).
It runs the full available offline test suite, UI checks, and a tracked-file
audit; providers are **mocked**. Real paid calls and individual user credentials
have not been authenticated by CI.
