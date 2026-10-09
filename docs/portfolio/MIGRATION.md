# Repository history and source provenance

This page records **historical source migration**. It is not a statement that the
current public Git checkout remains byte-identical to the archived project.

## Source and ownership context

The owner's earlier **ASR Evaluator Dashboard 1.6.2** was recovered from an
existing ChatGPT-generated delivery archive and imported into this repository.
The application was not recreated as a toy WER calculator. Much of the underlying
evaluation and reporting implementation originates from that earlier build.

Historical archive metadata, recorded during the initial migration:

```text
Archive: ASR_Evaluator_Dashboard_1_6_2.zip
SHA-256: e5099d514cf0119421d298d4c199f4ed685cabea5b761e9d753f2d1d63e40d8d
Original archive entries: 104 files
```

See [original-files.json](original-files.json) for original inventory/hashes.
That inventory is **historical evidence**, not a SHA-256 claim about today's
source files.

## Changes since import

The GitHub version has **subsequently changed**: local Python setup, portable
FFmpeg/Deno installation, optional UI-entered credentials, example labeling,
UI checksums, Windows tests, source checks, and public documentation. The
original packaging statement that source code was unchanged **no longer applies**.

The Git history is the authoritative record of successive repairs. This is a
portfolio representation of an existing application and ongoing engineering work,
not an assertion that the current code was written entirely in one session.

## Data and media constraints

The original sample's MP3 audio was kept outside this public repository because
redistribution rights were not confirmed. A publicly accessible video link is
attribution, not proof of permission to republish media. Synthetic demonstrations
have their own explicit labels. Imported text is not reported as fresh provider
inference; the earlier first sample's model identity remains unverified.

The original package verifier can be invoked with
`python verify_package.py --full-release` **only when the complete historical
archive/fixture set is present**. For a current Git checkout use
`python verify_package.py`, `/api/build`, and the CI workflow.

## Evidence and limitations

See [current versus historical verification](VERIFICATION.md) and
[data provenance](DATA_AND_PROVENANCE.md). Provider API keys, patient
information, and private run recordings do not belong in the public repository.
No provider authorization, successful paid inference, company endorsement, or
licensing of third-party components is implied by the migration.
