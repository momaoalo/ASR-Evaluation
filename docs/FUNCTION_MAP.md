# Source navigation

The old function and line-number map was captured for Dashboard 1.6.0.
**Line numbers drift with changes** and that inventory must not be presented as
a current verified API map. The archived `docs/function_map.json` is retained
for migration reference only.

For the **current code**, follow these entry points:

| Responsibility | Source entry point |
|---|---|
| Local Flask application and actual routes | [`app.py`](../app.py), `create_app()` |
| Request/case validation | [`pipeline.py`](../pipeline.py), `validate_request()`, `build_case()` |
| Media-to-model pipeline | [`pipeline.py`](../pipeline.py), `run_case()` |
| Persistent jobs and sequential worker | [`jobs.py`](../jobs.py), `JobManager` |
| Audio upload/crop/format | [`services/audio_processor.py`](../services/audio_processor.py) |
| YouTube URL and yt-dlp | [`services/downloader.py`](../services/downloader.py) |
| Model API adapters | [`services/humain_asr.py`](../services/humain_asr.py), [`services/elevenlabs_asr.py`](../services/elevenlabs_asr.py) |
| Text normalization and edits | [`evaluation/normalizer.py`](../evaluation/normalizer.py) and [`evaluation/evaluator.py`](../evaluation/evaluator.py) |
| Saved-results aggregation | [`evaluation/overview.py`](../evaluation/overview.py), [`evaluation/dashboard.py`](../evaluation/dashboard.py) |
| HTML / CSV / JSON reports | [`reporting.py`](../reporting.py) |
| Browser application and scorecards | [`static/js/app.js`](../static/js/app.js) |
| Native SVG charts | [`static/js/charts.js`](../static/js/charts.js) |
| Unit, integration, and simulated-provider checks | [`tests/`](../tests) |

See [architecture](ARCHITECTURE.md) for the live HTTP route inventory and
workflow, and [verification](portfolio/VERIFICATION.md) for tested scope.
