# Configuration

## Two independent modes

**Supplied transcripts:** local comparison of reference and candidate text. No API
key is needed; importing text does not create a live ASR result.

**Live ASR:** configure your own credentials and media tools. The application sends
a prepared audio file to a provider and records its returned transcript.

## Credential precedence in the original source

`Settings.credentials()` loads environment values (including `.env`), then nonempty
values from `config.local.json`, then any nonempty API-key constants in `config.py`.
Those constants are empty in the recovered package. Do not insert real keys into
tracked source files. An already present nonempty local value can override an
environment value, so check precedence when troubleshooting.

The example `.env` is a template, not a working provider configuration. In particular,
set `HUMAIN_API_URL` to your account's documented endpoint rather than leaving the
example's empty value in a live configuration. A website or login URL is not an API
endpoint. The adapter supports an account-provided Socket.IO path.

The original HUMAIN language mapping is:

| Language mode | SDK language | Model constant |
|---|---|---|
| Arabic | `Ar` | `BayanAr` |
| English | `En` | `FastEn` |
| Mixed | `ArEn` | `BayanArEn` |

The original example mentions `HUMAIN_MODEL`, but the adapter chooses from this
mapping; it does not read that environment variable as an override.

ElevenLabs uses the configured API key and the request settings implemented in
`services/elevenlabs_asr.py`. Record the actual model settings with each run. The
historical bundled transcript labels do not prove which version originally produced
them.

## External programs

- FFmpeg and FFprobe: required for audio inspection and preparation.
- yt-dlp: required for the YouTube acquisition path.
- A supported JavaScript runtime such as Deno: relevant to the installed yt-dlp setup.

These are not bundled by `requirements.txt`. Confirm that the programs can be found
on `PATH`; `/api/health` checks presence, not permission to use a provider account.

## Running safely

Use `python run_local.py`. Keep the loopback binding. No automatic retries should be
assumed after a provider timeout: the provider may have accepted a request before
the local deadline expired. Inspect account state before intentionally rerunning it.

The source and adapter versions are preserved from the original archive. Current
account access, provider billing, and live endpoint compatibility were not verified
by this migration.
