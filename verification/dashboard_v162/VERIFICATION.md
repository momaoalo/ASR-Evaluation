# Dashboard 1.6.2 — metric cards and completion navigation

Date: 2026-09-17. Built over the supplied complete Dashboard 1.6.1 package.

## Executed

- Full Python suite: 407 tests; 372 passed; 35 skipped; 0 failures; 0 errors.
- 17 new regression tests for macro/corpus distinction, word S/D/I totals, paired-only
  scope, filtering, failed/empty scores, repeated attempts, review flags, exports and UI contract.
- 46 Chromium checks passed against the actual templates, scripts, CSS and
  Python aggregation. Includes actual prior-report scorecard values, raw/cleaning
  switch, disclosure/section navigation, all 12 saved-run Open buttons, auto-opening
  a single result, partial/failing jobs, batch-list visibility, preserving the selected
  cleaning view, one-time completion, and not interrupting another form.
- The actual user report used for the preview contained 12 runs, not the later 17
  runs described in chat. No newer local data was assumed or fabricated.
- Updater executed on an extracted 1.6.1 copy containing 12 imported report cases:
  27 protected files (local settings and saved JSON data) stayed byte-identical.
  UI and package manifests verified after installation. Existing installer rollback,
  persistent/transient lock and idempotency tests also passed in the full suite.
- Python syntax, JavaScript syntax, all required DOM IDs and UI hashes verified.

## Test limitations

Flask, JiWER and Waitress are unavailable in this container. Package installation
was attempted and failed. The 35 skipped tests are not counted as passes; exact
names/reasons are in python_tests.json. Metric unit tests used the project's
existing RapidFuzz fallback. Core scoring/normalization algorithms were not edited.

agent-browser is not installed. Chromium URL navigation was blocked by browser
policy (ERR_BLOCKED_BY_ADMINISTRATOR). Browser tests used Playwright set_content,
with a mocked fetch/storage bridge to Python functions. This is not a live Flask
end-to-end test, not Windows execution, and not a provider authentication test.
Session storage persistence across a real browser reload was not tested.
Synthetic submitted-job fixtures exercise completion states; their scores are not
live provider benchmarks. The desktop preview uses the earlier uploaded report.
No ASR calls, credential checks or billable operations were made.

Run TEST_WINDOWS.bat where Flask/JiWER are already installed to execute the optional
route and official-engine tests. Start with START_WINDOWS.bat to use the project's
known Python selection instead of an unrelated VS Code interpreter.

## Scope preserved

- Same source acquisition, audio conversion, provider adapters, caching and reviews.
- Same Cleaning / No cleaning rules and individual saved WER/CER calculations.
- New macro averages are separately named; corpus remains the chart metric.
- New displays neither correct a reference nor suppress a flagged/high-error case.
- Existing config.py, config.local.json, .env and all data/ are not overwritten
  by UPDATE_EXISTING.bat. A clean base config.py in the ZIP contains no real keys.

## Primary implementation references

- https://docs.python.org/3/library/statistics.html#statistics.fmean
- https://jitsi.github.io/jiwer/usage/
- https://developer.mozilla.org/en-US/docs/Web/API/Element/scrollIntoView
