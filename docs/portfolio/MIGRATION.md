# Source migration and preservation

## Recovered source

This repository packages the actual **ASR Evaluator Dashboard 1.6.2** application
recovered from the owner's earlier ChatGPT-generated archive. It is not a newly
implemented replacement for that application.

```
Archive: ASR_Evaluator_Dashboard_1_6_2.zip
SHA-256: e5099d514cf0119421d298d4c199f4ed685cabea5b761e9d753f2d1d63e40d8d
Original archive entries: 104 files
```

The original archive passed its supplied package checksum check before changes.
`original-files.json` records the original hashes. The complete local delivery
preserves **102 of the 104 original files byte-for-byte**, including all 49 original
Python files, the templates, stylesheets, JavaScript, tests, and sample transcripts.
A source-only clone omits one of those 102 files: the separately distributed MP3.

## Exactly what changed

Two original packaging files changed:

1. `.gitignore` now excludes the entire private runtime data directory and common
   local secret/cache files. No runtime code changed.
2. `package_manifest.json` contains the new `.gitignore` hash so the original
   package verifier remains meaningful for the full delivery bundle.

New English README, configuration, provenance, verification, security, and migration
documentation were added. New source-verification and synthetic-demo helpers are
separate from the application. Original Arabic legacy notes were retained rather
than replacing reference text or silently rewriting the source.

The additional synthetic English example is explicitly labeled, has no audio or
real model predictions, and uses the original scoring/reporting implementation.
Historical verification reports remain historical. Fresh evidence is under
`verification/migration/`.

## Media packaging

The original `examples/doctor_clip.mp3` is retained in the full local delivery ZIP
but is not redistributed in the public source repository. Its educational source
is attributed; a public redistribution license was not established in this review.
No replacement recording or invented audio checksum was introduced. See
[Data and provenance](DATA_AND_PROVENANCE.md) for the expected original hash and
which workflows/tests require it.

## Verification and limits

```
python tools/verify_source.py
```

This command validates the preserved original source and reports missing optional
media separately. It does not test runtime dependencies, live APIs, or permissions
to publish company-owned code. The original full-package verifier and test runner
still require their original fixtures; neither was modified to hide missing media.

No API keys, local settings, private result store, or development history were
included. A scoped credential-pattern scan found no matches; that is not a guarantee
of universal secrecy. No new license or company endorsement was added.
