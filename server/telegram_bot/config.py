import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class TelegramBotSettings:
    token: str
    mini_app_url: str


def get_bot_settings() -> TelegramBotSettings:
    return TelegramBotSettings(
        token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
        mini_app_url=(
            os.getenv("TELEGRAM_MINI_APP_URL", "").strip()
            or os.getenv("WEB_APP_URL", "").strip()
        ),
    )
