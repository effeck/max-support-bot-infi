"""Configuration loaded from environment variables (.env)."""

import os
from dotenv import load_dotenv

load_dotenv()


def _get(name: str, required: bool = True, default: str | None = None) -> str:
    val = os.getenv(name, default)
    if required and not val:
        raise RuntimeError(
            f"Environment variable {name} is required. "
            f"Copy .env.example to .env and fill it in."
        )
    return val  # type: ignore[return-value]


BOT_TOKEN: str = _get("BOT_TOKEN")
ADMIN_ID: int = int(_get("ADMIN_ID"))
DATABASE_PATH: str = _get("DATABASE_PATH", required=False, default="bot.db")
