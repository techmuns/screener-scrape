"""Central configuration, loaded from environment / .env file."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the repo root if present. Real secrets live only there.
_REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_REPO_ROOT / ".env")

# Where downloaded .xlsx exports are cached (gitignored).
DATA_DIR = _REPO_ROOT / "data"


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    database_url: str
    anthropic_api_key: str
    request_delay: float
    prefer_consolidated: bool


def load_settings() -> Settings:
    return Settings(
        database_url=os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://screener:screener@localhost:5432/screener",
        ),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", "").strip(),
        request_delay=float(os.getenv("SCREENER_REQUEST_DELAY", "3")),
        prefer_consolidated=_as_bool(os.getenv("SCREENER_PREFER_CONSOLIDATED"), True),
    )


settings = load_settings()
