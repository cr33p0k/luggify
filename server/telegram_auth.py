import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import parse_qsl


class TelegramAuthError(ValueError):
    """Raised when Telegram WebApp auth payload is invalid."""


@dataclass(frozen=True)
class TelegramAuthPayload:
    tg_id: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None


def _strtobool(value: Optional[str]) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _get_bot_token() -> str:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise TelegramAuthError("TELEGRAM_BOT_TOKEN не настроен на сервере")
    return token


def allow_insecure_telegram_auth() -> bool:
    return _strtobool(os.getenv("ALLOW_INSECURE_TELEGRAM_AUTH"))


def _validate_auth_date(raw_auth_date: Optional[str]) -> None:
    if not raw_auth_date:
        raise TelegramAuthError("Отсутствует auth_date в Telegram initData")

    try:
        auth_date = datetime.fromtimestamp(int(raw_auth_date), tz=timezone.utc)
    except (TypeError, ValueError) as exc:
        raise TelegramAuthError("Некорректный auth_date в Telegram initData") from exc

    max_age_seconds = int(os.getenv("TELEGRAM_AUTH_MAX_AGE", "86400"))
    age_seconds = (datetime.now(timezone.utc) - auth_date).total_seconds()
    if age_seconds > max_age_seconds:
        raise TelegramAuthError("Telegram-сессия устарела, откройте mini app заново")


def _build_payload_from_user_data(user_data: dict) -> TelegramAuthPayload:
    tg_id = user_data.get("id")
    if tg_id is None:
        raise TelegramAuthError("Telegram user id не найден в initData")

    return TelegramAuthPayload(
        tg_id=str(tg_id),
        first_name=user_data.get("first_name"),
        last_name=user_data.get("last_name"),
        username=user_data.get("username"),
    )


def validate_telegram_webapp_init_data(init_data: str) -> TelegramAuthPayload:
    if not init_data:
        raise TelegramAuthError("Пустой initData от Telegram")

    parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        raise TelegramAuthError("В Telegram initData отсутствует hash")

    _validate_auth_date(parsed.get("auth_date"))

    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(parsed.items()))
    secret_key = hmac.new(
        b"WebAppData",
        _get_bot_token().encode("utf-8"),
        hashlib.sha256,
    ).digest()
    calculated_hash = hmac.new(
        secret_key,
        data_check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash):
        raise TelegramAuthError("Telegram initData не прошёл проверку подписи")

    raw_user = parsed.get("user")
    if not raw_user:
        raise TelegramAuthError("В Telegram initData отсутствуют данные пользователя")

    try:
        user_data = json.loads(raw_user)
    except json.JSONDecodeError as exc:
        raise TelegramAuthError("Не удалось разобрать user из Telegram initData") from exc

    return _build_payload_from_user_data(user_data)


def validate_telegram_login_widget_payload(data) -> TelegramAuthPayload:
    received_hash = str(getattr(data, "hash", "") or "").strip()
    tg_id = str(getattr(data, "tg_id", "") or "").strip()
    auth_date = str(getattr(data, "auth_date", "") or "").strip()

    if not received_hash:
        raise TelegramAuthError("В Telegram Login отсутствует hash")
    if not tg_id:
        raise TelegramAuthError("В Telegram Login отсутствует user id")

    _validate_auth_date(auth_date)

    payload_fields = {
        "id": tg_id,
        "auth_date": auth_date,
        "first_name": getattr(data, "first_name", None),
        "last_name": getattr(data, "last_name", None),
        "username": getattr(data, "username", None),
        "photo_url": getattr(data, "photo_url", None),
    }

    data_check_string = "\n".join(
        f"{key}={value}"
        for key, value in sorted(
            (key, str(value))
            for key, value in payload_fields.items()
            if value not in (None, "")
        )
    )

    secret_key = hashlib.sha256(_get_bot_token().encode("utf-8")).digest()
    calculated_hash = hmac.new(
        secret_key,
        data_check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash):
        raise TelegramAuthError("Telegram Login не прошёл проверку подписи")

    return TelegramAuthPayload(
        tg_id=tg_id,
        first_name=getattr(data, "first_name", None),
        last_name=getattr(data, "last_name", None),
        username=getattr(data, "username", None),
    )


def parse_telegram_auth_payload(data) -> TelegramAuthPayload:
    if getattr(data, "init_data", None):
        return validate_telegram_webapp_init_data(data.init_data)

    if getattr(data, "hash", None) and (getattr(data, "tg_id", None) or getattr(data, "id", None)):
        return validate_telegram_login_widget_payload(data)

    if allow_insecure_telegram_auth() and getattr(data, "tg_id", None):
        return TelegramAuthPayload(
            tg_id=str(data.tg_id),
            first_name=getattr(data, "first_name", None),
            last_name=getattr(data, "last_name", None),
            username=getattr(data, "username", None),
        )

    raise TelegramAuthError(
        "Для авторизации Telegram mini app требуется корректный initData"
    )
