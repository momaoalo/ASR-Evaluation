# Overview and History separation

`build_overview()` keeps the existing model/corpus accounting and appends `audio_cases` for browsing. `build_case_list()` groups by saved run/case, never by title or deduplicated audio hash. Metric invalidity is a model-level state, not permission to hide the whole case.

Frontend `selectRun()` is retained for compatibility but always requests all runs in the live Overview. `openRun()` uses independent state and a dedicated page. `renderCaseList()` renders both the global case list and saved-run details. No model or run selector mutates the global page.

For known job inputs before a saved result exists, JobManager.public() exposes only case_id/title headers; cards marked has_result=false have no invented metrics. Outcomes replace these placeholders on the next refresh. Read errors remain visible and cannot be treated as real 0% scores.

The model-comparison corpus rules, normalization and live ASR adapters are unchanged. JSON remains the source of stored state.
