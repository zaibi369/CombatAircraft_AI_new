import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip()
    if value == "":
        return default
    return value


CHAT_URL = _env("CHAT_URL", "http://127.0.0.1:8081/v1/chat/completions")
CHAT_MODEL = _env("CHAT_MODEL", "qwen3-0.6b")
CHAT_API_KEY = _env("CHAT_API_KEY")
QDRANT_URL = _env("QDRANT_URL")
QDRANT_API_KEY = _env("QDRANT_API_KEY")
OPENROUTER_API_KEY = _env("OPENROUTER_API_KEY")
VECTOR_DB_PATH = Path(_env("VECTOR_DB_PATH", str(BASE_DIR / "aircraft_vector_db_clean")))
SEARCH_PROVIDER = _env("SEARCH_PROVIDER", "tavily")
DATASET_STORAGE_PATH = Path(_env("DATASET_STORAGE_PATH", str(BASE_DIR / "dataset")))

__all__ = [
    "BASE_DIR",
    "CHAT_API_KEY",
    "CHAT_MODEL",
    "CHAT_URL",
    "DATASET_STORAGE_PATH",
    "OPENROUTER_API_KEY",
    "QDRANT_API_KEY",
    "QDRANT_URL",
    "SEARCH_PROVIDER",
    "VECTOR_DB_PATH",
]
