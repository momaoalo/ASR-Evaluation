"""Regression checks for public Windows onboarding; no network or paid API calls."""
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from config import Settings
from services import downloader
from storage import digest, write_json
from ui_integrity import verify_ui_files


class YoutubeSetupTests(unittest.TestCase):
    def test_venv_python_module_is_preferred(self):
        with patch("services.downloader.importlib.util.find_spec", return_value=object()):
            self.assertEqual(downloader.yt_dlp_command(), [sys.executable, "-m", "yt_dlp"])

    def test_global_executable_is_fallback(self):
        with patch("services.downloader.importlib.util.find_spec", return_value=None):
            with patch("services.downloader.shutil.which", return_value="yt-dlp-path"):
                self.assertEqual(downloader.yt_dlp_command(), ["yt-dlp-path"])

    def test_missing_tool_reports_an_actionable_error(self):
        with TemporaryDirectory() as tmp:
            settings = Settings(root=Path(tmp))
            with patch("services.downloader.yt_dlp_command", return_value=None):
                with self.assertRaisesRegex(ValueError, "SETUP_WINDOWS.bat"):
                    downloader.download_audio("https://youtu.be/IV3uF59g7rs", settings)

    def test_cached_download_does_not_require_tool(self):
        with TemporaryDirectory() as tmp:
            settings = Settings(root=Path(tmp))
            url = "https://www.youtube.com/watch?v=IV3uF59g7rs"
            directory = settings.data / "audio" / ("youtube_" + digest(url)[:16])
            directory.mkdir(parents=True)
            file = directory / "source.wav"
            file.write_bytes(b"cached-test-bytes")
            write_json(directory / "source.json", {"filename": "source.wav", "video_id": "IV3uF59g7rs"})
            with patch("services.downloader.yt_dlp_command", return_value=None):
                actual, metadata = downloader.download_audio(url, settings)
            self.assertEqual(actual, file)
            self.assertEqual(metadata["video_id"], "IV3uF59g7rs")

    def test_ui_integrity_matches_checked_in_files(self):
        self.assertEqual(verify_ui_files(Path(__file__).resolve().parents[1]), [])


if __name__ == "__main__":
    unittest.main()
