import os
from pathlib import Path

from dotenv import dotenv_values


_ENV_LOADED = False


def load_app_env() -> None:
    """Load backend env with process env taking precedence.

    Priority:
    1. Existing non-empty process environment variables
    2. project root `.env`

    Empty strings from the process environment are treated as missing so a blank
    variable injected by docker-compose does not shadow a real value from `.env`.
    """

    global _ENV_LOADED
    if _ENV_LOADED:
        return

    project_root = Path(__file__).resolve().parent.parent

    for env_path in (project_root / ".env",):
        if not env_path.is_file():
            continue

        for key, value in dotenv_values(env_path).items():
            if value is None:
                continue
            existing = os.environ.get(key)
            if existing is None or not existing.strip():
                os.environ[key] = value

    _ENV_LOADED = True
