# Dashboard 1.6.2 — scorecards and result navigation

## What changed

The overview now has compact historical-count cards, two prominent model scorecards,
a collapsed-by-default chart section, and the full audio-case list. Scores, Charts
and Audio cases shortcut buttons scroll to the relevant section. Export formats are
inside one menu. Problems remain on each affected case, in an expandable disclosure.
The pinned sample stays only in New evaluation. No Connections/Code Map/global
quality/configuration section has been restored.

Each scorecard uses the same paired subset as the comparison charts:

- Average WER = arithmetic mean of the per-case WER values (macro average).
- Average CER = arithmetic mean of the per-case CER values (macro average).
- S, D, I = sums of WORD substitutions, deletions, and insertions on those cases.
- Corpus WER = sum(S + D + I) / sum(reference words).
- Corpus CER = sum(character edits) / sum(reference characters).

Average and Corpus are intentionally not interchangeable. A 10-word case with one
error and a 100-word case with 50 errors give Average WER = 30%, Corpus WER = 46.36%.
Corpus remains the value used in the charts. No mean across two different providers
is displayed. A single model's summary is never mixed with another model's edits.
If no common scored cases exist, cards show dashes rather than perfect zero scores.
Warnings about unreviewed references remain; no reference is rewritten or excluded
because its WER happens to be high. Existing Cleaning / No cleaning rules are unchanged.

## Completion behavior

Only the evaluation submitted from the current tab is automatically followed. The
UI stores its run ID and selected scoring view in sessionStorage where available.
Once its saved job reaches complete/partial/failed/cancelled/interrupted:

- One saved case: open that run and its case inspector.
- A batch: open that run's result list, scrolling it into view.
- Another form, inspector or hidden browser tab: do not steal focus; show a
  completion notice with View results instead.

Terminal history present at page load does not cause navigation. Each followed job
is consumed only once. The job itself is never resubmitted by the navigation code.
If opening a saved result fails, the completion notice provides a retry action.
A temporarily failed refresh does not erase the saved results or the pending run.
Reduced-motion preferences are respected by the new section-scroll controls.

## Implementation map

- evaluation/dashboard.py::_totals — adds mean_case_wer, mean_case_cer, mean_case_count;
  existing paired rows, corpus counts, identity and review selection remain unchanged.
- static/js/app.js::renderModelScorecards — displays backend values; no text scoring.
- followSubmittedRun / checkFollowCompletion / openCompletedResult — run-specific flow.
- jumpTo — section navigation and batch result focus.
- templates/_workspace.html / static/css/app.css — layout, accessible disclosures.

## Historical installation notes (archived original release)

**These steps describe the older full ZIP release; do not follow them for a modern Git clone.** Use [Windows setup](WINDOWS_SETUP.md) instead.

For historical context only: stop the original application. Extract the archived release outside C:\asr-evaluator, then run
UPDATE_EXISTING.bat from the extracted asr-evaluator folder. Confirm the existing
project path. The updater backs up code and preserves config.py, config.local.json,
.env, and all of data/. Start START_WINDOWS.bat from the original project and refresh
the browser. Look for UI 1.6.2. Do not overlay previous update ZIPs afterward.

No new runtime dependencies or ASR requests are required for these reporting changes.
The old saved scores remain readable. Export a fresh HTML snapshot to include the
new scorecards; already exported HTML files are intentionally immutable snapshots.

## Primary documentation

- Python arithmetic mean: https://docs.python.org/3/library/statistics.html#statistics.fmean
- JiWER word/character metrics and edit counts: https://jitsi.github.io/jiwer/usage/
- Browser section scrolling: https://developer.mozilla.org/en-US/docs/Web/API/Element/scrollIntoView
