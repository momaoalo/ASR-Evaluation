# ASR Evaluation

A local-first toolkit for evaluating and comparing automatic speech recognition (ASR) outputs using word error rate (WER), character error rate (CER), text normalization, and aligned error analysis.

> **Source import in progress.** The original Dashboard 1.6.2 application archive has been recovered and its package checksums verified. This initial README documents the destination repository; it does not yet indicate a completed source import or a fresh runtime-test pass.

## Original application

The recovered package contains a Python/Flask application, provider adapters, an evaluation engine, a browser dashboard, examples, and offline regression tests. Repository preparation preserves the original scoring behavior and adds English documentation.

## Scope

- Score supplied transcripts locally, without paid ASR requests.
- Run supported ASR providers against a shared audio input when credentials and media tools are configured.
- Inspect raw and normalized WER/CER, substitutions, deletions, insertions, and alignments.
- Review saved runs and compare models on shared scored cases.
- Export HTML, JSON, and CSV reports.

WER/CER measure transcript differences relative to a reference. They do not measure clinical safety, SOAP-note accuracy, or general model superiority.

## Privacy and provenance

Do not commit API credentials, local configuration, uploaded recordings, or private evaluation results. Provider integrations are not an endorsement by their respective companies. Sample transcripts and historical outputs must remain labeled with their actual provenance.
