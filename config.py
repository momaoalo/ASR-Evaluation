"""Application settings. Provider credentials stay in the Python backend."""
from dataclasses import dataclass
from pathlib import Path
import json
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env')
VERSION = '1.6.1'
SCHEMA_VERSION = 1

# Optional local backend credentials. Paste keys here once if you prefer not to use .env.
# Do not commit/share real keys with a submitted project. Existing .env/config.local.json
# values remain supported as a compatibility fallback.
HUMAIN_API_KEY = ""
ELEVENLABS_API_KEY = ""
HUMAIN_API_URL = "https://api.voice.humain.com"
HUMAIN_API_PATH = "/socket.io"


@dataclass(frozen=True)
class Settings:
    root: Path = BASE_DIR
    max_cases: int = 100
    max_upload_mb: int = 100
    max_audio_seconds: int = 1800
    api_timeout: int = 300
    media_timeout: int = 180
    max_text_chars: int = 50000
    sample_rate: int = 16000

    @property
    def data(self) -> Path:
        return self.root / 'data'

    def credentials(self) -> dict:
        """Return backend-only provider settings. Code constants take priority when set."""
        values = {
            'humain_api_key': os.getenv('HUMAIN_API_KEY', ''),
            'humain_api_url': os.getenv('HUMAIN_API_URL', HUMAIN_API_URL),
            'humain_api_path': os.getenv('HUMAIN_API_PATH', HUMAIN_API_PATH),
            'elevenlabs_api_key': os.getenv('ELEVENLABS_API_KEY', ''),
        }
        path = self.root / 'config.local.json'
        if path.exists():
            saved = json.loads(path.read_text(encoding='utf-8-sig'))
            if not isinstance(saved, dict):
                raise ValueError('config.local.json must contain a JSON object.')
            for key in values:
                if saved.get(key):
                    values[key] = saved[key]
        if HUMAIN_API_KEY:
            values['humain_api_key'] = HUMAIN_API_KEY
        if ELEVENLABS_API_KEY:
            values['elevenlabs_api_key'] = ELEVENLABS_API_KEY
        return values
