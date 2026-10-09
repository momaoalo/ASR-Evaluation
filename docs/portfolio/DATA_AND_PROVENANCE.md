# Data, sample media, and provenance

## Original sample

`examples/sample.json` and `examples/ground_truth.txt` are preserved unchanged. The
sample metadata links to a public educational dialogue titled “At the doctor” and
records the source, duration, hash, reference, and previously supplied transcripts.
The user identified this as non-patient test material.

The original source URL is retained in `examples/sample.json`. This is attribution,
not a claim that a redistribution license has been verified. The sample reference
was user-supplied and was not independently checked against audio in this migration.

**Do not relabel the historical candidates:** the first is recorded as an unknown
“ASR AI Transcriber”; the bundled ElevenLabs candidate does not independently verify
a model version. Neither is a new inference request performed during migration.
These supplied outputs are distinct from the application's live HUMAIN and ElevenLabs
adapters.

## Separate audio fixture

The full local delivery bundle preserves the original `examples/doctor_clip.mp3`.
The source repository can be used without it for imported-text evaluation, but the
original pinned-sample playback/audio-processing paths and some regression tests
require it.

Expected original file:

```text
Path:    examples/doctor_clip.mp3
Bytes:   2505068
SHA-256: ee8011b5240ea0a5189489926cb7cc2386810621a467f4c84bd3533417e29abb
```

Restore this exact file from the full delivery bundle to run the original media
fixtures. Do not silently substitute a different recording under the original hash
or pretend that a newly downloaded/transcoded file is byte-identical.

If the media is not present in a clone, that is an explicitly documented packaging
limitation, not a new dataset. The original source and test suite are not rewritten
to hide that dependency. `tools/verify_source.py` reports optional media separately;
`verify_package.py` retains the original full-package semantics.

## Additional portfolio example

`examples/portfolio/transcripts.json` contains short synthetic English text and
intentionally edited candidates. It demonstrates deletions, substitutions, and
insertions without patient information, an audio recording, or provider calls.
The names “Demo A” and “Demo B” identify authored candidates, not real models.

## Results and reports

A fresh local test run does not establish real-model quality. Its transports are
mocked or its text supplied. Private runtime recordings/results belong in `data/`,
which is excluded from version control by the portfolio guardrails.

Any generated portfolio report must state the input provenance, evaluation engine,
normalization policy, and whether inference occurred. Never present an illustrative
sample score as a representative benchmark or clinical validation.
