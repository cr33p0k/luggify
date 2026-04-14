import os
from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse

from env_utils import load_app_env


load_app_env()


@dataclass(frozen=True)
class TelegramBotSettings:
    token: str
    mini_app_url: str


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
    )
