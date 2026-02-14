# config.py
import os

def _env(key: str, required: bool = True, default: str | None = None) -> str | None:
    val = os.getenv(key, default)
    if required and (val is None or val == ""):
        raise RuntimeError(f"Environment variable {key} is required.")
    return val

API_ID = int(_env("API_ID"))
API_HASH = _env("API_HASH")
BOT_TOKEN = _env("BOT_TOKEN")
DATABASE_URL = _env("DATABASE_URL")
DATABASE_NAME = _env("DATABASE_NAME", required=False, default=None)  # optional
CHANNEL_ID = int(_env("CHANNEL_ID"))
ADMIN_IDS = [int(x.strip()) for x in (_env("ADMIN_IDS", required=False, default="")).split(",") if x.strip()]
PORT = int(_env("PORT", required=False, default="8080"))

AUTO_DELETE_MINUTES = int(_env("AUTO_DELETE_MINUTES", required=False, default="0"))
SEARCH_RESULT_LIMIT = int(_env("SEARCH_RESULT_LIMIT", required=False, default="7"))
SESSION_TTL_SECONDS = int(_env("SESSION_TTL_SECONDS", required=False, default=str(60 * 5)))
ENV = _env("ENV", required=False, default="production")
