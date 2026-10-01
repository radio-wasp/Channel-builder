import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
CACHE_DIR = Path(os.getenv("CACHE_DIR", BASE_DIR / "cache"))
LOCAL_COMMERCIALS_DIR = Path(os.getenv("LOCAL_COMMERCIALS_DIR", BASE_DIR / "commercials_local"))

DATA_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)
LOCAL_COMMERCIALS_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "channel_builder.db"
COMMERCIAL_CACHE_DIR = CACHE_DIR / "commercials"
COMMERCIAL_CACHE_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_STREAM_PROFILE = {
    "resolution": "1920x1080",
    "video_bitrate": "4000k",
    "audio_bitrate": "192k",
    "fps": 30,
    "vcodec": "libx264",
    "acodec": "aac"
}
