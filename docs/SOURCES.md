# Technical sources

Reviewed for this implementation: 16 September 2026. These are provider/library contracts, not evidence of a successful live request with your account.

- HUMAIN official Python SDK 0.18.0: https://pypi.org/project/humain-voice/0.18.0/
  `humain_voice.stt.FastTranscriptionClient`, account API URL/key, optional Socket.IO path, `Language.ArEn`, `ASRModel.BayanArEn`. The unversioned model is an alias and can change; record the constant/resolved value and date.
- HUMAIN developer entry: https://voice.humain.com/
- ElevenLabs Create transcript: https://elevenlabs.io/docs/api-reference/speech-to-text/convert
  HTTPS multipart POST `/v1/speech-to-text`, `model_id=scribe_v2`, `xi-api-key`. No reference hints/keyterms are sent.
- JiWER: https://jitsi.github.io/jiwer/usage/
  `process_words()` / `process_characters()` counts and alignments.
- RapidFuzz: https://rapidfuzz.github.io/RapidFuzz/Usage/distance/Levenshtein.html
  Explicit fallback edit engine only; version is recorded.
- Flask file uploads: https://flask.palletsprojects.com/en/stable/patterns/fileuploads/
- Flask and Waitress on Windows: https://flask.palletsprojects.com/en/stable/deploying/waitress/
- FFprobe: https://ffmpeg.org/ffprobe.html
- FFmpeg: https://ffmpeg.org/ffmpeg.html
- yt-dlp: https://github.com/yt-dlp/yt-dlp
- Python subprocess: https://docs.python.org/3/library/subprocess.html
- Python JSON: https://docs.python.org/3/library/json.html
- Python Unicode: https://docs.python.org/3/library/unicodedata.html
- Requests multipart files/timeouts: https://requests.readthedocs.io/en/latest/user/quickstart/

No library source code or font files are redistributed here. Installation uses the listed package managers; each dependency retains its own license. The bundled audio was supplied by the user, not created by this application.
