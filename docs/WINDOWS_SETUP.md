# Windows setup and troubleshooting

This guide targets **Windows 11 / PowerShell**. The main [README](../README.md) explains the evaluation approach; this page contains installation details.

## Prerequisites

- Git
- Python **3.12** recommended (the setup script falls back to another installed Python 3 version)
- Internet access to download Python packages
- FFmpeg + FFprobe for live audio conversion
- Deno for more reliable YouTube downloads (recommended, not needed for local text scoring)

Do not work inside `C:\Windows\System32`. No GPU or local ASR model download is needed.

## First-time setup

Open PowerShell:

```powershell
cd "$env:USERPROFILE\Documents"
git clone https://github.com/momaoalo/ASR-Evaluation.git
cd .\ASR-Evaluation
.\SETUP_WINDOWS.bat
```

The setup creates a local `.venv`, installs `requirements.txt` (including Waitress, HUMAIN Voice SDK and yt-dlp), and runs the offline diagnostics. The launcher always uses this venv; you do not need `Activate.ps1` or changes to PowerShell execution policy.

### Media tools

If you want live ASR from uploaded audio or a YouTube URL, install media tools before running the app. **Recommended option:**

```powershell
.\INSTALL_MEDIA_WINDOWS.bat
```

This script downloads the Windows FFmpeg Essentials distribution and Deno from their published release URLs, checks their published SHA-256 values, and puts the executables in ignored `.tools/` folders. The launcher uses those paths for the application process only. Inspect the installer source if you wish before running it. Internet access is necessary.

Alternatively, with a *working* Windows Package Manager:

```powershell
winget install -e --id Gyan.FFmpeg
winget install -e --id DenoLand.Deno
```

If using WinGet, open a fresh terminal afterward. If `winget` fails with `0x80073cfc`, the portable option above avoids WinGet entirely. To repair WinGet itself on supported Windows versions, you may try `Get-AppxPackage Microsoft.DesktopAppInstaller | Reset-AppxPackage`.

## Start the application

```powershell
.\START_WINDOWS.bat
```

Open <http://127.0.0.1:5000>. Keep the launching console open and stop it with **Ctrl+C**. Do not expose the app on a public network.

## First evaluation

**Text-only illustration (no API):** choose **View sample results**. This reads saved transcripts and computes WER/CER; the first historical candidate's model identity is unverified. The public repository intentionally excludes the sample MP3. Those numbers are not live-provider benchmarks.

**Live evaluation:** choose **New evaluation → Upload** (or YouTube URL), enter the reviewed Ground Truth for *that same recording*, select the appropriate model(s), enter your own credentials in **Model connections**, confirm reference and provider consent, and run. HUMAIN requires an account-specific endpoint. Provider accounts and network access are not validated by the offline tests; live calls may incur charges. You can evaluate just one provider while you configure the other.

## Updating a clone

```powershell
cd "$env:USERPROFILE\Documents\ASR-Evaluation"
git status
git pull --ff-only
.\SETUP_WINDOWS.bat
.\START_WINDOWS.bat
```

Use the actual clone path; yours may have another folder name. If another copy already serves port 5000, close that process before starting this one.

## Check installation

```powershell
.\.venv\Scripts\python.exe diagnose.py
.\.venv\Scripts\python.exe verify_package.py
.\.venv\Scripts\python.exe -m yt_dlp --version
```

The verifier checks the **current Git source** and integrity-protected UI files. It does not authenticate providers. Check the local media tools directly when installed by the portable script:

```powershell
.\.tools\ffmpeg\ffmpeg.exe -version
.\.tools\ffmpeg\ffprobe.exe -version
.\.tools\deno\deno.exe --version
```

If you installed via WinGet, use `ffmpeg -version`, `ffprobe -version`, and `deno --version` instead.

### Common failures

| Symptom | What it means / what to do |
|---|---|
| `No module named waitress` | The wrong Python interpreter or incomplete setup was used. Run `SETUP_WINDOWS.bat` and launch with `START_WINDOWS.bat`. |
| `yt-dlp was not found` | Update the clone and rerun `SETUP_WINDOWS.bat`. yt-dlp now runs from the project Python environment. |
| FFmpeg or FFprobe missing | Run `INSTALL_MEDIA_WINDOWS.bat`, then start with `START_WINDOWS.bat`. |
| `winget` error `0x80073cfc` | WinGet source/App Installer problem, not an ASR error. Use the portable installer. |
| YouTube download unsuccessful | Some videos are unavailable or require authentication. Deno helps with JavaScript challenges but is not a bypass. Upload your own permitted local audio. |
| `Incomplete application files` | Check `git status`, ensure a clean clone, run `git pull --ff-only`; tracked UI files use LF newlines for hash validation. |
| `Waiting for the first saved result` | The overview has no saved scores yet. It is not proof that an evaluation is running. Create a sample text score or new run, then inspect Saved runs. |
| A live run fails | Check Saved runs for the actual stage and per-provider error. Confirm the right key, endpoint, credits, audio and reference. Never interpret a failed provider as WER 0%. |

## Tests and their scope

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_first_run_smoke.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_youtube_setup.py -v
```

These automated checks are **offline**; real API responses are mocked. Additional historical tests use a sample audio fixture not distributed in the public clone. See [verification](portfolio/VERIFICATION.md) for historical records and current CI scope.
