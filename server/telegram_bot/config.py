import os
from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse

from env_utils import load_app_env


load_app_env()


@dataclass(frozen=True)
class TelegramBotSettings:
    token: str
    mini_app_url: str
    request_timeout: float
    polling_timeout: int


def _read_float_env(name: str, default: float) -> float:
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return default
    try:
        return float(raw_value)
    except ValueError:
        return default


def _read_int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return default
    try:
        return int(raw_value)
    except ValueError:
        return default


def _ensure_tma_path(raw_url: str) -> str:
    parsed = urlparse(raw_url)
    base_path = parsed.path.rstrip("/")
    if base_path.endswith("/tma"):
        tma_path = base_path
    else:
        tma_path = f"{base_path}/tma" if base_path else "/tma"
    return urlunparse(parsed._replace(path=tma_path, params="", query="", fragment=""))


def _build_mini_app_url() -> str:
    explicit_url = os.getenv("TELEGRAM_MINI_APP_URL", "").strip()
    if explicit_url:
        return _ensure_tma_path(explicit_url)

    web_app_url = os.getenv("WEB_APP_URL", "").strip()
    if not web_app_url:
        return ""

    return _ensure_tma_path(web_app_url)


def get_bot_settings() -> TelegramBotSettings:
    return TelegramBotSettings(
        token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
        mini_app_url=_build_mini_app_url(),
        request_timeout=_read_float_env("TELEGRAM_REQUEST_TIMEOUT", 120.0),
        polling_timeout=_read_int_env("TELEGRAM_POLLING_TIMEOUT", 50),
    )
