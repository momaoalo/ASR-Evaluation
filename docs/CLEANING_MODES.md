# Cleaning modes (UI update 1.4.0)

The UI has exactly two choices: Cleaning and No cleaning. Both use the same saved
reference/prediction pair. Python computes `normalized` and `raw` once, and the
view selector controls tables, charts, inspection and export. No third
conservative metric is computed for new results.

`evaluation/profiles.py:get_cleaning_profile()` owns the full rule set. It combines
1.3.0 general rules with final ت/ة/ه equivalence, terminal تي/ت handling, broader
final ي/ى omission (at least three base letters must remain), English lowercasing,
and the previously agreed question-phrase equivalence. Numeric signs and values
are not intentionally removed; suffix rules are spelling heuristics, not grammar.
`lowercase` is global when active, including units, as requested.

No cleaning uses the baseline path: no NFC/alif/diacritic/case/spelling changes.
Whitespace and display-only controls are prepared; documented metadata extraction
precedes both modes. Thus it is not a byte-level diff.

Internal keys remain raw/normalized for compatibility. `score_view` is saved on
the job and honored by exports. Previously saved scores are neither silently
reinterpreted nor overwritten; explicitly re-score to adopt this fixed profile.
Legacy get_preset() remains for prior API callers and historical tests, but the
browser is not offered these presets. Detailed profile JSON remains an audit
record, not a collection of UI controls.

No spelling engine can be assumed semantically lossless. Final-letter folds can
merge genuinely different words. Use the No cleaning comparison for auditing.
