import os
from typing import List

class ConfigError(Exception):
    pass

def _env(key: str, required: bool = True, default: str = None) -> str:
    val = os.getenv(key, default)
    if required and (val is None or val == ""):
        raise ConfigError(f"Environment variable {key} is required.")
    return val

API_ID = int(_env("API_ID"))
API_HASH = _env("API_HASH")
BOT_TOKEN = _env("BOT_TOKEN")
DATABASE_URL = _env("DATABASE_URL")  # e.g. mongodb+srv://...
DATABASE_NAME = _env("DATABASE_NAME", required=False, default=None)
CHANNEL_ID = int(_env("CHANNEL_ID"))  # private channel where files are uploaded
ADMIN_IDS = [int(x.strip()) for x in _env("ADMIN_IDS", required=False, default="").split(",") if x.strip()]  # comma separated ids
PORT = int(_env("PORT", required=False, default="8080"))

# Optional features
AUTO_DELETE_MINUTES = int(_env("AUTO_DELETE_MINUTES", required=False, default="0"))  # 0 = disabled
SEARCH_RESULT_LIMIT = int(_env("SEARCH_RESULT_LIMIT", required=False, default="7"))

# Session expiration seconds (for TTL index)
SESSION_TTL_SECONDS = int(_env("SESSION_TTL_SECONDS", required=False, default=str(60 * 5)))  # default 5 minutes

# Other runtime flags
ENV = _env("ENV", required=False, default="production")
