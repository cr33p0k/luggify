from datetime import datetime, timedelta, timezone
import base64

from jose import JWTError, jwt

from auth import ALGORITHM, SECRET_KEY


class TelegramLinkTokenError(ValueError):
    """Raised when a telegram link token is invalid or expired."""


def _encode_for_deeplink(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii").rstrip("=")


def _decode_from_deeplink(value: str) -> str:
    padding = "=" * (-len(value) % 4)
    try:
        return base64.urlsafe_b64decode(f"{value}{padding}".encode("ascii")).decode("utf-8")
    except Exception as exc:
        raise TelegramLinkTokenError("Некорректный токен привязки Telegram") from exc


def create_telegram_link_token(user_id: int, expires_minutes: int = 20) -> tuple[str, datetime]:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    jwt_token = jwt.encode(
        {
            "sub": str(user_id),
            "type": "telegram_link",
            "exp": expires_at,
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )
    return _encode_for_deeplink(jwt_token), expires_at


def decode_telegram_link_token(encoded_token: str) -> int:
    raw_token = _decode_from_deeplink(encoded_token)
    try:
        payload = jwt.decode(raw_token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise TelegramLinkTokenError("Ссылка привязки Telegram устарела или недействительна") from exc

    if payload.get("type") != "telegram_link":
        raise TelegramLinkTokenError("Неверный тип токена привязки Telegram")

    raw_user_id = payload.get("sub")
    if raw_user_id is None:
        raise TelegramLinkTokenError("В токене привязки отсутствует пользователь")

    try:
        return int(raw_user_id)
    except (TypeError, ValueError) as exc:
        raise TelegramLinkTokenError("Некорректный пользователь в токене привязки Telegram") from exc
