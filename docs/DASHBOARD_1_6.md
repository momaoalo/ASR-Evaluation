# Reporting contract — 1.6.0

The UI renders Python-provided metrics; it does not re-score in JavaScript.

## Distinct scopes
- `listed_case_count`: every saved run/case attempt, including repeated, failed and incomplete cases.
- `successful_transcripts`: all historical scored model records; cached and imported are labelled and are not new network calls.
- `audio_input_count`: known positive-duration media grouped by explicit source+interval lineage or exact prepared-file hash, independently of reference. This is not acoustic similarity. Unknown media is reported separately. Different encodings without proven lineage may remain distinct.
- Paired case: the same known audio input plus the same scored reference plus compatible saved scoring policy; only one latest observation per model/configuration is used. A failure never becomes a zero or silently falls back to an earlier success.
- Unknown-settings failures remain in history and operational coverage, but are not invented competitors. Live and supplied provenance are separate.
- The selected pair affects paired charts and their numeric table, not visibility of all history cards.

## Ratios
Corpus WER = sum(S+D+I) / sum(reference word counts). CER uses the separately saved character alignment counts and character denominators. Rounding is display-only. WER over 100% is not clipped. Means of file percentages are not labelled corpus WER.

## Reference safeguards
Source/file/crop changes invalidate the form confirmation. A bundled reference inherited into a non-sample request requires explicit backend acknowledgement. Automatic warnings are heuristics (agreement of poor-to-reference ASR outputs, probable pasted timestamps), not linguistic or acoustic proof. They do not exclude cases. No winner is declared while unresolved paired-reference warnings exist.
Review decisions are sidecars under data/reviews. Correcting a reference uses saved model speech text and creates a new run, preserving the old result and explicitly excluding that superseded case from aggregate statistics. No reference is sent as an ASR hint.

## Readability and exports
Horizontal grouped SVG bars identify models consistently, show exact percentages and support case inspection. An accompanying numeric table exposes counts and denominators. Cases are categorical, not a trend over time. Blank/failure states are textual. HTML freezes the pair/scope and both cleaning views. CSV contains model-attempt rows and media-only failures; JSON includes case-level provenance and review decisions, not credentials. A standalone report cannot mutate a local workspace.

## Implementation map
- evaluation/overview.py: compact index and validated legacy rows.
- evaluation/report_metadata.py: evidenced media identity and advisory quality signals.
- evaluation/dashboard.py: history and paired aggregate views.
- reporting_review.py: explicit review decisions and reference re-score clones.
- reporting.py: one HTML/CSV export implementation shared by dashboard/run views.
- static/js/charts.js: readable plots; no metric computation.
- static/js/app.js: navigation, forms, inspection and rendering.
- update_existing.py: verified update with code backup, rollback and user-state preservation.

## Primary references
- JiWER definitions and alignment: https://jitsi.github.io/jiwer/ and https://jitsi.github.io/jiwer/usage/
- Complex charts need textual alternatives: https://www.w3.org/WAI/tutorials/images/complex/

These are engineering choices for this evaluator, not a universal ASR benchmark protocol. The existing normalization policy remains a user-chosen tolerance policy.
