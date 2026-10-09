# Security and privacy

This application is designed for a single user on `127.0.0.1`, not public hosting.
The original local-only request boundary, CSRF checks, safe provider errors, and
response-header protections are preserved. These are implementation safeguards,
not a security certification.

## Keep out of version control

- `.env`, `config.local.json`, and any real credentials inserted into `config.py`.
- `data/`: recordings, uploads, raw provider responses, jobs, results, and caches.
- Backups of local workspaces, credential-bearing diagnostics, and private exports.

Use `.env` or the supported local settings file rather than committing keys.
Local settings are plaintext, not an encrypted secret store. Do not share them.
A successful secret-pattern scan does not prove that a repository contains no
confidential information; review the intended publication contents separately.

## Provider and source permissions

Live ASR sends audio to the selected external provider and can incur usage charges.
Only submit audio you are authorized to process. Publicly viewable media is not
an automatic grant of permission to redistribute it. Preserve source attribution
and review the applicable media/provider terms before publication or reuse.

Do not include patient information, internal company data, or private recordings in
public examples. Reports can contain complete reference and hypothesis transcripts;
review exports before sharing even when API keys are not included.

## Reporting a problem

For a non-sensitive defect, open an issue with synthetic reproduction data. Do not
post secrets, personal recordings, or confidential transcripts in an issue. For an
accidentally exposed key, revoke/rotate it with the provider and remove the exposure;
removing only the latest file does not remove older Git history.
