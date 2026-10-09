# Configuration and first-run troubleshooting

## Two distinct workflows

- **Supplied transcripts / saved example:** runs local WER/CER calculations on supplied texts; no provider requests or charges. The first historical example's ASR source is **unverified**, not HUMAIN. The public checkout does **not** include the original sample audio file.
- **Live audio:** choose Upload or YouTube, add the matching reviewed Ground Truth, select one or both providers, and confirm consent. The selected services receive audio and may charge credits.

## Enter API keys in the interface

Open **New evaluation → ASR models → Model connections**. Enter the provider keys for the run. HUMAIN also needs your account's **actual API endpoint**. The ElevenLabs URL is fixed by its adapter and displayed read-only.

No API keys are shipped with the repository. Keys entered in the interface are held only as necessary to process the running job and are not stored in result JSON or Git. **Do not** commit keys to tracked files, include them in screenshots, or share them in issues.

You may still configure keys locally with `.env` or `config.local.json` if desired. `Settings.credentials()` reads environment values, then local JSON, then any nonempty constants in `config.py` (which are empty in the public source). In-run keys entered through the UI override those defaults for the selected job.

## Supported providers and language modes

HUMAIN's original SDK mapping:

| UI language | SDK language | Model |
|---|---|---|
| Arabic | `Ar` | `BayanAr` |
| English | `En` | `FastEn` |
| Mixed | `ArEn` | `BayanArEn` |

The original adapter does not use `HUMAIN_MODEL` as a user override. ElevenLabs uses its Scribe v2 integration.

## Python environment and media dependencies

Run `SETUP_WINDOWS.bat` to create `.venv` and install the requirements, including `yt-dlp[default]` for YouTube EJS scripts. Launch with `START_WINDOWS.bat` or `.venv\Scripts\python.exe run_local.py`; this avoids conflicts with another global Python.

```powershell
winget install -e --id Gyan.FFmpeg
winget install -e --id DenoLand.Deno
```

- **FFmpeg and FFprobe** are required to prepare all live audio. If WinGet is broken, run `INSTALL_MEDIA_WINDOWS.bat`; this installs official checksum-verified FFmpeg/FFprobe and Deno in the ignored project-local `.tools/` folder. `START_WINDOWS.bat` adds that location to the process PATH.
- **yt-dlp** runs from the same Python environment as the app; no separate global executable is needed.
- **Deno 2.3+** is recommended for YouTube JavaScript challenges; some videos can still be restricted.
- The app is single-user and loopback-only. Do not expose it to the public internet.

Check readiness (no paid calls):

```powershell
.\.venv\Scripts\python.exe diagnose.py
.\.venv\Scripts\python.exe -m yt_dlp --version
```

`/api/health` reports installed tools; it does **not** validate a provider's account access, live endpoint or available credits.

## Troubleshooting

Refer to [Windows setup](../WINDOWS_SETUP.md) or [Arabic quick start](../../README_AR.md). Missing `waitress` means you used the wrong Python or skipped setup. If YouTube acquisition fails, try Upload and check FFmpeg, Deno and video access. Use `python verify_package.py` to validate the **current Git checkout**, or `--full-release` only for the original historical ZIP archive.

No automatic retries should be assumed after a provider timeout: the service might already have processed a billable request. Live provider credentials, account authorization and billing remain untested in offline CI.
