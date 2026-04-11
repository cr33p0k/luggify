import re
from datetime import date

from aiogram.types import User as TelegramUser

import crud
from ai_service import ask_travel_ai
from checklist_ai import apply_checklist_ai_actions, preview_checklist_ai_command
from database import SessionLocal
from telegram_link import TelegramLinkTokenError, decode_telegram_link_token

CHECKLIST_BUTTON_PAGE_SIZE = 8


def _merge_checklists(*collections):
    merged = {}
    for collection in collections:
        for checklist in collection or []:
            merged[checklist.slug] = checklist
    return list(merged.values())


def _sort_checklists(checklists):
    today = date.today()
    return sorted(
        checklists,
        key=lambda checklist: (
            0
            if checklist.start_date and checklist.end_date and checklist.start_date <= today <= checklist.end_date
            else 1
            if checklist.start_date and checklist.start_date > today
            else 2,
            checklist.start_date or date.max,
            checklist.end_date or date.max,
        ),
    )


def _pick_primary_checklist(checklists):
    if not checklists:
        return None

    today = date.today()
    active = [
        checklist
        for checklist in checklists
        if checklist.start_date and checklist.end_date and checklist.start_date <= today <= checklist.end_date
    ]
    if active:
        return min(active, key=lambda checklist: (checklist.end_date, checklist.start_date))

    upcoming = [checklist for checklist in checklists if checklist.start_date and checklist.start_date > today]
    if upcoming:
        return min(upcoming, key=lambda checklist: checklist.start_date)

    past = [checklist for checklist in checklists if checklist.end_date and checklist.end_date < today]
    if past:
        return max(past, key=lambda checklist: checklist.end_date)

    return checklists[0]


def _remaining_items(checklist):
    checked = set(checklist.checked_items or [])
    removed = set(checklist.removed_items or [])
    return [item for item in (checklist.items or []) if item not in checked and item not in removed]


def _format_dates(checklist):
    if not checklist.start_date or not checklist.end_date:
        return "даты не указаны"
    return f"{checklist.start_date:%d.%m.%Y} — {checklist.end_date:%d.%m.%Y}"


def _normalize_text(value: str) -> str:
    return (value or "").strip().lower().replace("ё", "е")


def _candidate_city_names(city: str) -> list[str]:
    raw = (city or "").strip()
    if not raw:
        return []

    parts = re.split(r"\s*\+\s*|\s*/\s*|,", raw)
    candidates = [part.strip() for part in parts if part.strip()]
    if raw not in candidates:
        candidates.insert(0, raw)
    return candidates


def _build_city_patterns(city: str) -> list[re.Pattern]:
    patterns = []
    seen = set()
    for candidate in _candidate_city_names(city):
        normalized = _normalize_text(candidate)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        patterns.append(re.compile(rf"(?<!\w){re.escape(normalized)}(?!\w)", re.IGNORECASE))

        if len(normalized) > 4 and normalized[-1] in "аеиоуыэюяьй":
            stem = normalized[:-1]
            if stem and stem not in seen:
                patterns.append(re.compile(rf"(?<!\w){re.escape(stem)}\w*(?!\w)", re.IGNORECASE))
                seen.add(stem)
    return patterns


def _extract_trip_date_hints(prompt: str) -> list[dict]:
    hints = []
    current_year = date.today().year
    for day, month, year in re.findall(r"(?<!\d)(\d{1,2})\.(\d{1,2})(?:\.(\d{2,4}))?(?!\d)", prompt or ""):
        parsed_year = None
        if year:
            parsed_year = int(year)
            if parsed_year < 100:
                parsed_year += 2000

        hints.append(
            {
                "day": int(day),
                "month": int(month),
                "year": parsed_year or current_year,
                "has_explicit_year": bool(year),
            }
        )
    return hints


def _trip_matches_date_hints(checklist, date_hints: list[dict]) -> bool:
    if not date_hints:
        return True
    if not checklist.start_date or not checklist.end_date:
        return False

    for hint in date_hints:
        try:
            hint_date = date(hint["year"], hint["month"], hint["day"])
        except ValueError:
            continue

        if hint["has_explicit_year"]:
            if checklist.start_date <= hint_date <= checklist.end_date:
                return True
            continue

        current = checklist.start_date
        while current <= checklist.end_date:
            if current.day == hint["day"] and current.month == hint["month"]:
                return True
            current = current.fromordinal(current.toordinal() + 1)

    return False


def _strip_trip_reference(prompt: str, checklist) -> str:
    cleaned = prompt or ""
    for candidate in _candidate_city_names(checklist.city):
        normalized = _normalize_text(candidate)
        if not normalized:
            continue
        city_variants = [re.escape(normalized)]
        if len(normalized) > 4 and normalized[-1] in "аеиоуыэюяьй":
            city_variants.append(rf"{re.escape(normalized[:-1])}\w*")

        city_group = "(?:" + "|".join(city_variants) + ")"
        patterns = [
            rf"\b(?:в|во|для|по)\s+поездк\w*\s+(?:в|во)\s+{city_group}\b",
            rf"\b(?:для|по)\s+{city_group}\b",
            rf"\b(?:в|во)\s+{city_group}\b",
            rf"\btrip\s+to\s+{city_group}\b",
            rf"\bfor\s+{city_group}\b",
        ]
        for pattern in patterns:
            cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)

    cleaned = re.sub(r"(?<!\d)(\d{1,2})\.(\d{1,2})(?:\.(\d{2,4}))?(?!\d)", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.;:-")
    return cleaned or (prompt or "").strip()


def _resolve_trip_reference(prompt: str, checklists, selected_slug: str = None) -> dict:
    normalized_prompt = _normalize_text(prompt)
    city_matches = []

    for checklist in checklists:
        patterns = _build_city_patterns(checklist.city)
        if any(pattern.search(normalized_prompt) for pattern in patterns):
            city_matches.append(checklist)

    if not city_matches:
        return {"mode": "no_explicit_target"}

    date_hints = _extract_trip_date_hints(prompt)
    dated_matches = [checklist for checklist in city_matches if _trip_matches_date_hints(checklist, date_hints)]

    if date_hints and not dated_matches:
        return {
            "mode": "pick_trip",
            "message": "Я нашёл поездки в этот город, но не смог точно сопоставить дату. Выберите нужную поездку:",
            "checklists": city_matches,
        }

    matches = dated_matches or city_matches
    if selected_slug:
        selected = next((checklist for checklist in matches if checklist.slug == selected_slug), None)
        if selected:
            return {
                "mode": "resolved",
                "checklist": selected,
                "cleaned_prompt": _strip_trip_reference(prompt, selected),
            }

    if len(matches) == 1:
        checklist = matches[0]
        return {
            "mode": "resolved",
            "checklist": checklist,
            "cleaned_prompt": _strip_trip_reference(prompt, checklist),
        }

    city_label = matches[0].city if matches else "этот город"
    return {
        "mode": "pick_trip",
        "message": f"У вас несколько поездок в {city_label}. Выберите нужную:",
        "checklists": matches,
    }


async def _load_user_checklists_with_session(db, tg_user: TelegramUser):
    user = await crud.get_user_by_tg_id(db, str(tg_user.id))
    own = []
    shared = []
    if user:
        own = await crud.get_checklists_by_user_id(db, user.id)
        shared = await crud.get_shared_checklists_by_user_id(db, user.id)

    legacy = await crud.get_all_checklists_by_tg_user_id(db, str(tg_user.id))
    return _sort_checklists(_merge_checklists(own, shared, legacy))


async def ensure_telegram_user(tg_user: TelegramUser):
    async with SessionLocal() as db:
        user = await crud.get_user_by_tg_id(db, str(tg_user.id))
        if user:
            return user
        return await crud.create_user_from_telegram(
            db=db,
            tg_id=str(tg_user.id),
            username=tg_user.username,
            first_name=tg_user.first_name,
        )


async def get_telegram_user_checklists(tg_user: TelegramUser):
    async with SessionLocal() as db:
        return await _load_user_checklists_with_session(db, tg_user)


async def get_primary_checklist_for_user(tg_user: TelegramUser):
    checklists = await get_telegram_user_checklists(tg_user)
    return _pick_primary_checklist(checklists)


async def _get_primary_checklist_with_session(db, tg_user: TelegramUser):
    checklists = await _load_user_checklists_with_session(db, tg_user)
    return _pick_primary_checklist(checklists)


async def _get_checklist_by_slug_with_session(db, tg_user: TelegramUser, slug: str):
    if not slug:
        return None

    checklist = await crud.get_checklist_by_slug(db, slug)
    if not checklist:
        return None

    user = await crud.get_user_by_tg_id(db, str(tg_user.id))
    if user:
        if checklist.user_id == user.id:
            return checklist
        if any(backpack.user_id == user.id for backpack in (checklist.backpacks or [])):
            return checklist

    if checklist.tg_user_id == str(tg_user.id):
        return checklist
    return None


async def _get_checklist_by_id_with_session(db, tg_user: TelegramUser, checklist_id: int):
    checklist = await crud.get_checklist_by_id(db, checklist_id)
    if not checklist:
        return None

    user = await crud.get_user_by_tg_id(db, str(tg_user.id))
    if user:
        if checklist.user_id == user.id:
            return checklist
        if any(backpack.user_id == user.id for backpack in (checklist.backpacks or [])):
            return checklist

    if checklist.tg_user_id == str(tg_user.id):
        return checklist
    return None


async def get_selected_or_primary_checklist(tg_user: TelegramUser, selected_slug: str = None):
    async with SessionLocal() as db:
        if selected_slug:
            selected = await _get_checklist_by_slug_with_session(db, tg_user, selected_slug)
            if selected:
                return selected
        return await _get_primary_checklist_with_session(db, tg_user)


async def get_checklists_for_picker(tg_user: TelegramUser):
    return await get_telegram_user_checklists(tg_user)


def format_checklist_title(checklist):
    if not checklist:
        return "Поездка"
    if checklist.start_date and checklist.end_date:
        return f"{checklist.city} · {checklist.start_date:%d.%m} — {checklist.end_date:%d.%m}"
    return checklist.city


def _encode_section_key(backpack_id: int | None = None) -> str:
    return "s" if backpack_id is None else f"b{backpack_id}"


def _normalize_section_key(section_key: str | None) -> str:
    if not section_key or section_key in {"shared", "s"}:
        return "s"
    if isinstance(section_key, str):
        if section_key.startswith("bp:"):
            suffix = section_key.split(":", 1)[1]
            return f"b{suffix}" if suffix.isdigit() else "s"
        if re.fullmatch(r"b\d+", section_key):
            return section_key
    return "s"


def _normalize_items_list(items):
    return list(items or [])


def _normalize_quantity_map(raw_map):
    normalized = {}
    for key, value in (raw_map or {}).items():
        normalized_key = _normalize_text(str(key))
        if not normalized_key:
            continue
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = 1
        normalized[normalized_key] = parsed if parsed > 0 else 1
    return normalized


def _get_item_quantity(quantity_map, item_name: str) -> int:
    normalized_key = _normalize_text(item_name)
    return _normalize_quantity_map(quantity_map).get(normalized_key, 1)


def _format_item_with_quantity(item_name: str, quantity_map) -> str:
    quantity = _get_item_quantity(quantity_map, item_name)
    return f"{item_name} ×{quantity}" if quantity > 1 else item_name


def _build_baggage_label(backpack, actor_user_id: int | None = None) -> str:
    username = backpack.user.username if getattr(backpack, "user", None) else f"user_{backpack.user_id}"
    baggage_name = (getattr(backpack, "name", None) or "Рюкзак").strip()
    is_default = bool(getattr(backpack, "is_default", False))

    if actor_user_id and backpack.user_id == actor_user_id:
        return "Мой рюкзак" if is_default else baggage_name
    if is_default:
        return username
    return f"{username} · {baggage_name}"


def _build_checklist_sections(checklist, actor_user_id: int | None = None) -> list[dict]:
    sections = [
        {
            "key": "s",
            "label": "Общие вещи",
            "items": _normalize_items_list(checklist.items),
            "checked_items": _normalize_items_list(checklist.checked_items),
            "removed_items": _normalize_items_list(checklist.removed_items),
            "item_quantities": _normalize_quantity_map(getattr(checklist, "item_quantities", None)),
        }
    ]

    for backpack in (checklist.backpacks or []):
        sections.append(
            {
                "key": _encode_section_key(backpack.id),
                "label": _build_baggage_label(backpack, actor_user_id),
                "items": _normalize_items_list(backpack.items),
                "checked_items": _normalize_items_list(backpack.checked_items),
                "removed_items": _normalize_items_list(backpack.removed_items),
                "item_quantities": _normalize_quantity_map(getattr(backpack, "item_quantities", None)),
            }
        )
    return sections


def _build_interactive_checklist_view_data(
    checklist,
    actor_user_id: int | None = None,
    section_key: str | None = None,
    page: int = 0,
) -> dict:
    sections = _build_checklist_sections(checklist, actor_user_id)
    selected_key = _normalize_section_key(section_key)
    selected_section = next((section for section in sections if section["key"] == selected_key), None)
    if not selected_section:
        selected_section = sections[0]
        selected_key = selected_section["key"]

    removed_normalized = {_normalize_text(item) for item in selected_section["removed_items"]}
    checked_normalized = {_normalize_text(item) for item in selected_section["checked_items"]}
    quantity_map = selected_section.get("item_quantities") or {}
    visible_items = [
        item for item in selected_section["items"]
        if _normalize_text(item) not in removed_normalized
    ]
    checked_count = sum(
        _get_item_quantity(quantity_map, item)
        for item in visible_items
        if _normalize_text(item) in checked_normalized
    )
    total_count = sum(_get_item_quantity(quantity_map, item) for item in visible_items)
    page_count = max(1, (total_count + CHECKLIST_BUTTON_PAGE_SIZE - 1) // CHECKLIST_BUTTON_PAGE_SIZE)
    safe_page = min(max(page, 0), page_count - 1)
    start = safe_page * CHECKLIST_BUTTON_PAGE_SIZE
    page_items = visible_items[start:start + CHECKLIST_BUTTON_PAGE_SIZE]

    return {
        "ok": True,
        "checklist_id": checklist.id,
        "checklist_slug": checklist.slug,
        "title": format_checklist_title(checklist),
        "section_key": selected_key,
        "section_label": selected_section["label"],
        "sections": [
            {
                "key": section["key"],
                "label": section["label"],
                "active": section["key"] == selected_key,
            }
            for section in sections
        ],
        "page": safe_page,
        "page_count": page_count,
        "items": [
            {
                "name": item,
                "label": _format_item_with_quantity(item, quantity_map),
                "quantity": _get_item_quantity(quantity_map, item),
                "checked": _normalize_text(item) in checked_normalized,
            }
            for item in page_items
        ],
        "total_count": total_count,
        "checked_count": checked_count,
        "remaining_count": max(total_count - checked_count, 0),
        "empty": total_count == 0,
        "text": (
            f"{format_checklist_title(checklist)}\n"
            f"Раздел: {selected_section['label']}\n"
            f"Собрано: {checked_count}/{total_count}\n"
            f"Осталось: {max(total_count - checked_count, 0)}"
            + ("\n\nНажмите на вещь ниже, чтобы отметить или снять отметку." if total_count else "\n\nВ этом разделе пока пусто.")
        ),
    }


async def build_interactive_checklist_view(
    tg_user: TelegramUser,
    selected_slug: str | None = None,
    checklist_id: int | None = None,
    section_key: str | None = None,
    page: int = 0,
) -> dict:
    async with SessionLocal() as db:
        current_user = await crud.get_user_by_tg_id(db, str(tg_user.id))
        if checklist_id is not None:
            checklist = await _get_checklist_by_id_with_session(db, tg_user, checklist_id)
        elif selected_slug:
            checklist = await _get_checklist_by_slug_with_session(db, tg_user, selected_slug)
        else:
            checklist = await _get_primary_checklist_with_session(db, tg_user)

        if not checklist:
            return {
                "ok": False,
                "message": "Пока не вижу поездок. Сначала создайте чеклист в приложении.",
            }

        return _build_interactive_checklist_view_data(
            checklist,
            actor_user_id=current_user.id if current_user else None,
            section_key=section_key,
            page=page,
        )


async def toggle_interactive_checklist_item(
    tg_user: TelegramUser,
    checklist_id: int,
    section_key: str,
    page: int,
    item_index: int,
) -> dict:
    async with SessionLocal() as db:
        current_user = await crud.get_user_by_tg_id(db, str(tg_user.id))
        checklist = await _get_checklist_by_id_with_session(db, tg_user, checklist_id)
        if not checklist:
            return {
                "ok": False,
                "message": "Не удалось найти эту поездку. Попробуйте открыть чеклист заново.",
            }

        actor_user_id = current_user.id if current_user else None
        view = _build_interactive_checklist_view_data(
            checklist,
            actor_user_id=actor_user_id,
            section_key=section_key,
            page=page,
        )
        if item_index < 0 or item_index >= len(view["items"]):
            return {
                "ok": False,
                "message": "Эта кнопка уже устарела. Откройте чеклист заново.",
            }

        item_name = view["items"][item_index]["name"]
        normalized_item = _normalize_text(item_name)

        if view["section_key"] == "s":
            checked_items = list(checklist.checked_items or [])
            removed_items = [item for item in (checklist.removed_items or []) if _normalize_text(item) != normalized_item]
            is_checked = any(_normalize_text(item) == normalized_item for item in checked_items)
            if is_checked:
                checked_items = [item for item in checked_items if _normalize_text(item) != normalized_item]
            else:
                checked_items.append(item_name)
            checklist.checked_items = checked_items
            checklist.removed_items = removed_items
        else:
            backpack_id = int(view["section_key"][1:])
            backpack = next((bp for bp in (checklist.backpacks or []) if bp.id == backpack_id), None)
            if not backpack:
                return {
                    "ok": False,
                    "message": "Не удалось найти нужный рюкзак. Откройте чеклист заново.",
                }

            checked_items = list(backpack.checked_items or [])
            removed_items = [item for item in (backpack.removed_items or []) if _normalize_text(item) != normalized_item]
            is_checked = any(_normalize_text(item) == normalized_item for item in checked_items)
            if is_checked:
                checked_items = [item for item in checked_items if _normalize_text(item) != normalized_item]
            else:
                checked_items.append(item_name)
            backpack.checked_items = checked_items
            backpack.removed_items = removed_items

        await db.commit()
        updated_checklist = await crud.get_checklist_by_id(db, checklist.id)
        updated_view = _build_interactive_checklist_view_data(
            updated_checklist,
            actor_user_id=actor_user_id,
            section_key=view["section_key"],
            page=page,
        )

        return {
            "ok": True,
            "view": updated_view,
            "message": "Отметил" if not view["items"][item_index]["checked"] else "Снял отметку",
        }


async def build_trip_overview_text(tg_user: TelegramUser, selected_slug: str = None) -> str:
    checklist = await get_selected_or_primary_checklist(tg_user, selected_slug)
    if not checklist:
        return (
            "У вас пока нет поездок в Luggify.\n\n"
            "Откройте mini app, создайте первую поездку, и я смогу подсказывать по ней."
        )

    remaining = _remaining_items(checklist)
    quantity_map = _normalize_quantity_map(getattr(checklist, "item_quantities", None))
    total_items = sum(_get_item_quantity(quantity_map, item) for item in (checklist.items or []))
    checked_items = total_items - sum(_get_item_quantity(quantity_map, item) for item in remaining)
    today = date.today()

    if checklist.start_date and checklist.end_date and checklist.start_date <= today <= checklist.end_date:
        trip_status = "Сейчас у вас активная поездка"
    elif checklist.start_date and checklist.start_date > today:
        trip_status = "Ближайшая поездка"
    else:
        trip_status = "Последняя поездка"

    return (
        f"{trip_status}\n"
        f"Город: {checklist.city}\n"
        f"Даты: {_format_dates(checklist)}\n"
        f"Собрано: {checked_items}/{total_items}\n"
        f"Осталось вещей: {len(remaining)}"
    )


async def build_remaining_items_text(tg_user: TelegramUser, selected_slug: str = None) -> str:
    checklist = await get_selected_or_primary_checklist(tg_user, selected_slug)
    if not checklist:
        return "Пока не вижу поездок. Сначала создайте чеклист, и я подскажу, что осталось собрать."

    remaining = _remaining_items(checklist)
    if not remaining:
        return f"По поездке в {checklist.city} у вас всё отмечено. Похоже, вы отлично собраны."

    quantity_map = _normalize_quantity_map(getattr(checklist, "item_quantities", None))
    preview = "\n".join(f"• {_format_item_with_quantity(item, quantity_map)}" for item in remaining[:10])
    suffix = "\n…" if len(remaining) > 10 else ""
    remaining_total = sum(_get_item_quantity(quantity_map, item) for item in remaining)
    return f"По поездке в {checklist.city} ещё осталось {remaining_total} вещей:\n{preview}{suffix}"


async def build_account_debug_text(tg_user: TelegramUser, selected_slug: str = None) -> str:
    async with SessionLocal() as db:
        user = await crud.get_user_by_tg_id(db, str(tg_user.id))
        checklists = await _load_user_checklists_with_session(db, tg_user)

    selected = None
    if selected_slug:
        selected = next((checklist for checklist in checklists if checklist.slug == selected_slug), None)

    lines = [
        "Telegram-статус",
        f"tg_id: {tg_user.id}",
        f"username: @{tg_user.username}" if tg_user.username else "username: не задан",
        f"Связанный пользователь: {user.username} (id={user.id})" if user else "Связанный пользователь: не найден",
        f"Поездок видно боту: {len(checklists)}",
    ]
    if selected:
        lines.append(f"Выбранная поездка: {format_checklist_title(selected)}")
    elif checklists:
        lines.append(f"По умолчанию будет: {format_checklist_title(_pick_primary_checklist(checklists))}")

    if not user:
        lines.append("")
        lines.append("Если поездки не видны, скорее всего web-аккаунт ещё не привязан к tg_id.")

    return "\n".join(lines)


async def link_web_account_from_telegram(tg_user: TelegramUser, encoded_token: str) -> str:
    try:
        user_id = decode_telegram_link_token(encoded_token)
    except TelegramLinkTokenError as exc:
        return str(exc)

    async with SessionLocal() as db:
        try:
            user = await crud.bind_telegram_to_user(
                db,
                user_id=user_id,
                tg_id=str(tg_user.id),
                telegram_username=tg_user.username,
            )
        except ValueError as exc:
            return str(exc)

    if not user:
        return "Не удалось найти веб-аккаунт для привязки."

    return (
        f"Готово! Telegram привязан к аккаунту {user.username}.\n\n"
        "Теперь бот и сайт работают как один профиль."
    )


async def process_ai_prompt_for_telegram(tg_user: TelegramUser, prompt: str, selected_slug: str = None) -> dict:
    prompt = (prompt or "").strip()
    if not prompt:
        return {"mode": "message", "message": "Напишите вопрос, и я постараюсь помочь."}

    if "|" in prompt:
        city_part, question_part = [part.strip() for part in prompt.split("|", 1)]
        if city_part and question_part:
            result = await ask_travel_ai(city=city_part, question=question_part, language="ru")
            return {"mode": "message", "message": result.get("answer", "Не удалось получить ответ от AI.")}

    async with SessionLocal() as db:
        current_user = await crud.get_user_by_tg_id(db, str(tg_user.id))
        all_checklists = await _load_user_checklists_with_session(db, tg_user)
        resolved_reference = _resolve_trip_reference(prompt, all_checklists, selected_slug)
        if resolved_reference["mode"] == "pick_trip":
            return {
                "mode": "pick_trip",
                "message": resolved_reference["message"],
                "checklists": resolved_reference["checklists"],
                "prompt": prompt,
            }

        checklist = None
        cleaned_prompt = prompt
        if resolved_reference["mode"] == "resolved":
            checklist = resolved_reference["checklist"]
            cleaned_prompt = resolved_reference["cleaned_prompt"]
        elif selected_slug:
            checklist = await _get_checklist_by_slug_with_session(db, tg_user, selected_slug)
        if not checklist:
            checklist = await _get_primary_checklist_with_session(db, tg_user)
        if not checklist:
            return {
                "mode": "message",
                "message": (
                    "Я могу отвечать по вашей ближайшей поездке, но пока не вижу чеклистов.\n\n"
                    "Либо создайте поездку в mini app, либо напишите вопрос так:\n"
                    "Париж | что попробовать из еды?"
                ),
            }

        preview = await preview_checklist_ai_command(
            checklist,
            cleaned_prompt,
            "ru",
            actor_user_id=current_user.id if current_user else None,
        )
        if preview["recognized_action_request"]:
            if preview.get("requires_confirmation"):
                return {
                    "mode": "confirm",
                    "message": preview["message"],
                    "actions": preview.get("raw_actions") or preview["actions"],
                    "checklist_slug": checklist.slug,
                    "checklist_title": format_checklist_title(checklist),
                }
            if preview["actions"]:
                command_result = await apply_checklist_ai_actions(
                    db=db,
                    checklist=checklist,
                    actions=preview.get("raw_actions") or preview["actions"],
                    language="ru",
                    actor_user_id=current_user.id if current_user else None,
                )
                return {
                    "mode": "action",
                    "message": command_result["message"],
                    "checklist_slug": checklist.slug,
                    "checklist_title": format_checklist_title(command_result["checklist"]),
                }
            return {"mode": "message", "message": preview["message"]}

        result = await ask_travel_ai(
            city=checklist.city,
            question=cleaned_prompt,
            language="ru",
            start_date=str(checklist.start_date or ""),
            end_date=str(checklist.end_date or ""),
            avg_temp=checklist.avg_temp,
        )
        return {"mode": "message", "message": result.get("answer", "Не удалось получить ответ от AI.")}


async def confirm_ai_actions_for_telegram(
    tg_user: TelegramUser,
    checklist_slug: str,
    actions: list[dict],
    language: str = "ru",
) -> dict:
    async with SessionLocal() as db:
        current_user = await crud.get_user_by_tg_id(db, str(tg_user.id))
        checklist = await _get_checklist_by_slug_with_session(db, tg_user, checklist_slug)
        if not checklist:
            return {
                "applied": False,
                "message": "Не удалось найти выбранную поездку. Попробуйте выбрать её снова.",
            }
        return await apply_checklist_ai_actions(
            db,
            checklist,
            actions,
            language,
            actor_user_id=current_user.id if current_user else None,
        )
