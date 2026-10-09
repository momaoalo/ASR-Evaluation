"""First-run API smoke checks without proprietary audio or paid model calls."""
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import create_app
from config import Settings
from evaluation.profiles import get_cleaning_profile
from services.asr_common import build_model_result
from storage import read_json


ROOT = Path(__file__).resolve().parents[1]


class FirstSavedResultSmoke(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "examples").mkdir()
        shutil.copy2(ROOT / "examples" / "sample.json", self.root / "examples" / "sample.json")
        self.app = create_app(settings=Settings(root=self.root), start_worker=False)
        self.client = self.app.test_client()
        self.headers = {"X-CSRF-Token": self.app.extensions["csrf"]}

    def test_public_sample_creates_first_saved_results_without_audio(self):
        self.assertFalse((self.root / "examples" / "doctor_clip.mp3").exists())
        result = self.client.post("/api/sample/score", headers=self.headers, json={})
        self.assertEqual(result.status_code, 200, result.get_json())
        job = result.get_json()
        self.assertEqual(job["status"], "complete")
        self.assertEqual(job["mode"], "imported")
        self.assertTrue((self.root / "data" / "jobs" / (job["run_id"] + ".json")).exists())
        overview = self.client.get("/api/overview")
        self.assertEqual(overview.status_code, 200, overview.get_json())
        content = overview.get_json()
        self.assertTrue(content["jobs"])
        self.assertTrue(content["summary"]["audio_cases"])

    def test_live_upload_saves_result_with_transient_key(self):
        upload = self.client.post(
            "/api/uploads",
            headers=self.headers,
            data={"files": (io.BytesIO(b"RIFF" + b"\\x00" * 128), "test.wav")},
            content_type="multipart/form-data",
        )
        self.assertEqual(upload.status_code, 200, upload.get_json())
        upload_id = upload.get_json()["uploads"][0]["upload_id"]
        payload = {
            "cases": [{
                "case_id": "case_001", "title": "Live smoke",
                "source": {"type": "upload", "upload_id": upload_id},
                "ground_truth": "hello world", "reference_confirmed": True,
                "crop": {"start": 0, "end": None},
            }],
            "models": ["elevenlabs"], "consent": True,
            "profile": get_cleaning_profile("en"),
            "provider_credentials": {"elevenlabs_api_key": "not-a-real-key"},
            "reuse_cache": False,
        }

        def fake_asr(audio, creds, lang, timeout):
            self.assertEqual(creds["elevenlabs_api_key"], "not-a-real-key")
            return build_model_result(
                "elevenlabs", "ElevenLabs · test mock", "hello world",
                settings={"model_id": "mock-model"}, provenance="live"
            ), {"text": "hello world"}

        with patch("pipeline.prepare_audio") as prep:
            with patch("pipeline.transcribe_elevenlabs", side_effect=fake_asr):
                prep.return_value = self.root / "data" / "audio" / (upload_id + ".wav"), {
                    "sha256": "a" * 64, "duration": 1.0, "bytes": 132, "sample_rate": 16000
                }
                submit = self.client.post("/api/evaluate", headers=self.headers, json=payload)
                self.assertEqual(submit.status_code, 202, submit.get_json())
                job_id = submit.get_json()["job_id"]
                self.app.extensions["jobs"].execute(job_id)

        job = self.app.extensions["jobs"].get(job_id)
        self.assertEqual(job["status"], "complete", job)
        saved = list((self.root / "data" / "results").rglob("*.json"))
        overview = self.client.get("/api/overview")
        self.assertEqual(overview.status_code, 200, overview.get_json())
        summary = overview.get_json()["summary"]
        self.assertTrue(summary["audio_cases"], summary)
        self.assertNotIn("not-a-real-key", json.dumps(summary))
        self.assertNotIn("not-a-real-key", json.dumps(job))


if __name__ == "__main__":
    unittest.main()
