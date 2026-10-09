# Data and evaluation provenance

## Historical Arabic example

`examples/sample.json` contains a previously supplied Arabic reference and
candidate transcripts for the educational **At the doctor** dialogue. The
reference was supplied by the owner and was **not independently verified
against the original audio** as part of the public migration.

The example's first candidate was historically called **ASR AI Transcriber**.
Its underlying provider/model is **unknown**, so the current example labels it
**Unverified ASR model · supplied**. It must not be attributed to HUMAIN.
The other sample candidate is labeled ElevenLabs in the original supplied
material, but its original model version and API request were **not
independently verified**. Neither candidate is evidence of a newly executed
provider request.

Earlier snapshots may contain the original labels. Do not reinterpret them as
live HUMAIN results. A `supplied` result means text was scored locally; a
`live` result identifies the runtime processing path, not an independently
certified provider benchmark.

The reference, source URL, estimated duration and expected original-media
metadata are included for transparency. This is **not patient clinical data**.

## Why the MP3 is not in GitHub

The historical full local bundle contained `examples/doctor_clip.mp3`. Its
original expected metadata was:

```text
Path:    examples/doctor_clip.mp3
Bytes:   2505068
SHA-256: ee8011b5240ea0a5189489926cb7cc2386810621a467f4c84bd3533417e29abb
```

Public redistributability was not established. The public repository omits
the MP3; do not claim that the media-backed example can run from a clean clone.
The **View sample results** route can score the saved text without the MP3.
Live ASR requires a permitted local upload or accessible YouTube media instead.

Tests requiring the historical MP3 should be reported as requiring a
**nonpublic fixture**, not silently represented as passing. Do not substitute
different audio while claiming the original checksum.

## Portfolio demonstration

`examples/portfolio/transcripts.json` uses **synthetic, manually authored
English transcripts**. The generated HTML, JSON and CSV results demonstrate
scoring and visualization, **not actual model performance**. No original
patient audio or provider traffic is involved.

## Publishing and interpreting results

- WER/CER measures edit distance relative to the selected reference and
  normalization policy, not medical, semantic or universal model quality.
- An illustrative 0% error rate is not evidence that a model is always accurate.
- Failed requests must remain failures, not zero-error predictions.
- Runtime jobs, private uploads, transcripts and raw responses are saved
  under ignored `data/`. Review local export files before sharing.
- Do not commit API keys, company-confidential recordings or patient data.

See [verification scope](VERIFICATION.md) and [security notes](../../SECURITY.md).
