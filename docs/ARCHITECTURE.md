# ASR Evaluator — implemented architecture

This describes actual source files, not a claim that external API accounts have been tested.

For a navigable directory of current and archived documents, see the [documentation index](INDEX.md).

## Reading order

1. `app.py:create_app()` owns the local web boundary and routes. Browser sends JSON or uploaded file bytes. Requests need the CSRF token supplied to the page. Provider keys never go into browser responses.
2. `pipeline.validate_request()` validates each case and freezes the reference, crop and shared normalization profile. Source filenames are not server paths. Uploaded files are persisted under generated IDs before queuing.
3. `jobs.JobManager.create_job()` persists the job snapshot and queues its ID. HTTP returns **202**; one thread processes jobs. `run_batch()` iterates cases and `run_case()` owns one case's orchestration.
4. Sources join at a local artifact: `download_audio()` invokes installed yt-dlp with an argument list, `shell=False` and a timeout, while `resolve_uploaded_audio()` resolves a controlled artifact ID. The included sample bypasses downloading only when the original MP3 is present; that file is not published in the GitHub checkout.
5. `probe_audio()` checks media metadata. `prepare_audio()` decodes, crops and produces a deterministic cached WAV, preserving original bytes/hash and actual conversion settings. No automatic denoising or pause removal.
6. Providers are called independently, sequentially, on the same prepared file. ElevenLabs uses Requests multipart HTTPS. HUMAIN uses its official Socket.IO SDK in a short-lived child process, so the parent can enforce a deadline. The secret travels via stdin, not command-line arguments.
7. `build_model_result()` unifies the provider result. Raw provider response is checkpointed, then the spoken-text scoring copy is evaluated. Live text is not corrected to match the reference.
8. `normalize_text()` preserves raw text and produces the scored text plus source-span mapping/change logs. Profile is shared by all selected models. The raw baseline is also evaluated after explicit structured-metadata extraction.
9. `evaluate_transcription()` uses JiWER when installed, with an explicitly identified RapidFuzz fallback. Words are whitespace-delimited; characters are Unicode code points, not UTF-8 bytes. Every edit is tied to a position, so repeated strings do not cause false highlighting.
10. `save_result()` writes UTF-8 JSON through a temporary file + fsync + os.replace. One worker owns live runs. Each provider is checkpointed; a second failure cannot erase the first success.
11. `aggregate_results()` computes corpus metrics on a matched successful case set, not an average of file percentages. Failures are shown separately; null scores are not zero. Summary responses omit bulky alignments; the inspector requests details.
12. `reporting.export_html_report()` embeds the same saved data, CSS and frontend scripts into one HTML report. It never repeats inference. Optional playback is available in the live app; exported reports do not embed audio or secrets.

## Contracts

Case: `case_id`, `title`, `source`, `crop`, `ground_truth`, `reference_hash`, `profile`.

Source: `{type: sample}`, `{type: youtube, url: ...}`, or `{type: upload, upload_id: ...}`. The UI converts a batch manifest's `source.filename` to an upload ID after uploading its matching file.

Model result: `key`, `label`, `status`, `raw_text`, `speech_text`, `request_settings`, `elapsed_ms`, `metadata`, `provenance`, `cache_hit`, `evaluation` or a safe `error`.

Evaluation: `profile`, `profile_id`, `normalizer_version`, `metrics.raw`, `metrics.normalized`, normalized copies/change logs. Each metric view has independent words/characters counts, token metadata and positional operations. Ratios are stored as fractions: 0.08 = 8%.

Job state: queued → running → complete / partial / failed / cancelled. On restart, unfinished work becomes interrupted. Re-score creates a new run from saved predictions with a new profile; the original run stays available.

## Current HTTP API (checked against `app.py`)

The documented paths below reflect the current Flask decorators; older
settings/code-map routes that appeared in previous archived materials
are **not present** in this public version.

| Method | Route | Purpose |
|---|---|---|
| GET | `/` | Evaluation dashboard |
| GET | `/api/build` | Source and UI consistency metadata |
| GET | `/api/health` | Tool and optional local credential presence (not live authentication) |
| GET | `/api/sample` | Supplied example metadata |
| GET | `/api/sample/audio` | Original media **only if privately installed**; otherwise unavailable |
| POST | `/api/sample/score` | Score saved supplied transcripts (no API call) |
| POST | `/api/imported/evaluate` | Score user-provided transcripts locally |
| POST | `/api/uploads` | Save uploaded audio file |
| POST | `/api/evaluate` | Validate and queue live provider evaluation, HTTP 202 |
| GET | `/api/jobs` | Saved job list |
| GET | `/api/jobs/<job_id>` | Individual job state |
| POST | `/api/jobs/<job_id>/cancel` | Stop after current case |
| GET | `/api/overview` | Combined current overview |
| GET | `/api/results/<run_id>` | Saved run summary |
| GET | `/api/results/<run_id>/<case_id>` | Detailed case result |
| GET | `/api/audio/<run_id>/<case_id>` | Local saved-case audio where available |
| POST | `/api/reviews/<run_id>/<case_id>` | Store explicit review decision |
| POST | `/api/reference/<run_id>/<case_id>` | Save corrected reference and re-score |
| POST | `/api/rescore/<run_id>` | Re-score saved text without calling providers |
| GET | `/api/export/<run_id>` | Saved-run HTML export |
| GET | `/api/export/overview` | Full overview HTML export |
| GET | `/api/export/overview.json` | Overview JSON |
| GET | `/api/export/overview.csv` | Overview CSV |
| GET | `/api/results/<run_id>/download/json` | Single-run JSON download |

## Intentional refinements from the planned flowchart

- Native SVG chart rendering replaces Chart.js: two charts, no runtime CDN, no frontend scoring implementation.
- Progress polling refreshes `/api/results/{run_id}` (including job status) during the run. The separate job-status endpoint remains available for clients. No extra `pollJob()` transcription work occurs.
- Validation resides in `pipeline.py`, invoked by `app.py`, rather than being duplicated in both layers.
- `job_id` and `run_id` use the same unique value in this local version; separate concepts are kept in the schema for later split if needed.
- Case and provider calls are sequential for a predictable teaching baseline. Batch does not mean instant or concurrent processing.
- No blind retry of paid POST/SDK requests. A timeout can occur after acceptance. Inspect account state before intentionally rerunning. Cached reuse is explicit and labelled.
- The original supplied Model 1 was an unknown “ASR AI Transcriber”; it is **not** relabelled as HUMAIN.
- No clinical SOAP score or semantic validation is mixed into WER/CER. A small textual difference may still have large clinical significance.

## Accuracy checks and edge cases

For words, `N_reference=C+S+D` and `N_prediction=C+S+I`. Character alignment is independent. `وصورة`→`صورة` is a word substitution, but a character deletion. Multiple minimum-edit alignments can have the same score; engine/version and positional alignment are retained.

A missing/empty reference is rejected. Successful empty output means all reference tokens are deleted. API/media failure is a failure record, not a fabricated empty transcription. WER/CER can exceed 100% and are never clamped. Raw and normalized views have their own denominators.

## Local persistence and limits

This is a local workstation application, not a public multi-user service. It has no account/login system, distributed queue, cost estimation API, or database. JSON writes are atomic but not a distributed transaction. Disk corruption, low disk space and manual file edits can still cause failures. An active case completes before cancellation. Automatic provider model aliases may change despite unchanged settings; disable cache for fresh inference and record the run date.

The app holds a run summary in memory for display. At 100 ordinary short clips this is a reasonable design target, not a measured production SLA. Full details are fetched on demand; long alignments are paginated in the inspector. Very large exports are inherently larger files.

## Safe sharing

Share source + example only. Exclude `.env`, `config.local.json`, and `data/` content containing private audio or provider results. The app's local settings are plaintext, not a secret vault. Rotate already disclosed keys. Consult [current verification scope](portfolio/VERIFICATION.md) before claiming live provider validation; GitHub Actions checks Windows installation but not paid APIs.
