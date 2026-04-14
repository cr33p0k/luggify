import os
from pathlib import Path

from dotenv import dotenv_values


_ENV_LOADED = False


def load_app_env() -> None:
    """Load backend env files with process env taking precedence.

    Priority:
    1. Existing non-empty process environment variables
    2. `server/.env`
    3. project root `.env`

    Empty strings from the process environment are treated as missing so a blank
    `RAPIDAPI_KEY` injected by docker-compose does not shadow the real value from
    `server/.env`.
    """

    global _ENV_LOADED
    if _ENV_LOADED:
        return

    server_dir = Path(__file__).resolve().parent
    project_root = server_dir.parent

    for env_path in (server_dir / ".env", project_root / ".env"):
        if not env_path.is_file():
            continue

        for key, value in dotenv_values(env_path).items():
            if value is None:
                continue
            existing = os.environ.get(key)
            if existing is None or not existing.strip():
                os.environ[key] = value

    _ENV_LOADED = True
