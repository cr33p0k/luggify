import re
from datetime import date

from aiogram.types import User as TelegramUser

import crud
from ai_service import ask_travel_ai
from checklist_ai import apply_checklist_ai_actions, preview_checklist_ai_command
from database import SessionLocal
from telegram_link import TelegramLinkTokenError, decode_telegram_link_token

CHECKLIST_BUTTON_PAGE_SIZE = 8
DEFAULT_CHECKLIST_INTERACTION_MODE = "pack"
CHECKLIST_INTERACTION_MODES = {
    "pack": "+1",
    "unpack": "-1",
    "complete": "✓ всё",
}


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


def _get_section_visible_items(section: dict) -> list[str]:
    removed = {_normalize_text(item) for item in section.get("removed_items") or []}
    return [
        item
        for item in section.get("items") or []
        if _normalize_text(item) not in removed
    ]


def _get_section_progress(section: dict) -> dict:
    quantity_map = section.get("item_quantities") or {}
    packed_map = section.get("packed_quantities") or {}
    visible_items = _get_section_visible_items(section)
    checked_count = sum(
        min(_get_item_packed_quantity(packed_map, item), _get_item_quantity(quantity_map, item))
        for item in visible_items
    )
    total_count = sum(_get_item_quantity(quantity_map, item) for item in visible_items)
    remaining_items = [
        item
        for item in visible_items
        if _get_item_packed_quantity(packed_map, item) < _get_item_quantity(quantity_map, item)
    ]
    remaining_count = sum(
        max(_get_item_quantity(quantity_map, item) - _get_item_packed_quantity(packed_map, item), 0)
        for item in remaining_items
    )
    return {
        "visible_items": visible_items,
        "checked_count": checked_count,
        "total_count": total_count,
        "remaining_items": remaining_items,
        "remaining_count": remaining_count,
    }


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


def _encode_section_key(backpack_id: int) -> str:
    return f"b{backpack_id}"


def _normalize_section_key(section_key: str | None) -> str:
    if isinstance(section_key, str):
        if section_key.startswith("bp:"):
            suffix = section_key.split(":", 1)[1]
            return f"b{suffix}" if suffix.isdigit() else ""
        if re.fullmatch(r"b\d+", section_key):
            return section_key
    return ""


def _normalize_items_list(items):
    return list(items or [])


def _normalize_interaction_mode(mode: str | None) -> str:
    if mode in CHECKLIST_INTERACTION_MODES:
        return mode
    return DEFAULT_CHECKLIST_INTERACTION_MODE


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


def _normalize_packed_quantity_map(raw_map):
    normalized = {}
    for key, value in (raw_map or {}).items():
        normalized_key = _normalize_text(str(key))
        if not normalized_key:
            continue
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            continue
        if parsed <= 0:
            continue
        normalized[normalized_key] = parsed
    return normalized


def _get_item_quantity(quantity_map, item_name: str) -> int:
    normalized_key = _normalize_text(item_name)
    return _normalize_quantity_map(quantity_map).get(normalized_key, 1)


def _get_item_packed_quantity(quantity_map, item_name: str) -> int:
    normalized_key = _normalize_text(item_name)
    return _normalize_packed_quantity_map(quantity_map).get(normalized_key, 0)


def _hydrate_packed_quantities(items, checked_items, quantity_map, packed_map):
    hydrated = _normalize_packed_quantity_map(packed_map)
    for item in checked_items or []:
        hydrated[_normalize_text(item)] = max(
            _get_item_packed_quantity(hydrated, item),
            _get_item_quantity(quantity_map, item),
        )
    for item in items or []:
        normalized = _normalize_text(item)
        hydrated[normalized] = min(
            _get_item_packed_quantity(hydrated, item),
            _get_item_quantity(quantity_map, item),
        )
        if hydrated[normalized] <= 0:
            hydrated.pop(normalized, None)
    return hydrated


def _format_item_with_quantity(item_name: str, quantity_map, packed_map=None) -> str:
    quantity = _get_item_quantity(quantity_map, item_name)
    if packed_map is not None:
        return f"{item_name} {_get_item_packed_quantity(packed_map, item_name)}/{quantity}"
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


def _build_checklist_sections(
    checklist,
    actor_user_id: int | None = None,
    own_only: bool = False,
) -> list[dict]:
    backpacks = list(checklist.backpacks or [])
    if own_only and actor_user_id is not None:
        backpacks = [backpack for backpack in backpacks if backpack.user_id == actor_user_id]

    sections = []
    for backpack in backpacks:
        sections.append(
            {
                "key": _encode_section_key(backpack.id),
                "label": _build_baggage_label(backpack, actor_user_id),
                "items": _normalize_items_list(backpack.items),
                "checked_items": _normalize_items_list(backpack.checked_items),
                "removed_items": _normalize_items_list(backpack.removed_items),
                "item_quantities": _normalize_quantity_map(getattr(backpack, "item_quantities", None)),
                "packed_quantities": _hydrate_packed_quantities(
                    _normalize_items_list(backpack.items),
                    _normalize_items_list(backpack.checked_items),
                    _normalize_quantity_map(getattr(backpack, "item_quantities", None)),
                    getattr(backpack, "packed_quantities", None),
                ),
            }
        )
    return sections


def _build_interactive_checklist_view_data(
    checklist,
    actor_user_id: int | None = None,
    section_key: str | None = None,
    page: int = 0,
    interaction_mode: str | None = None,
) -> dict:
    sections = _build_checklist_sections(checklist, actor_user_id)
    if not sections:
        return {
            "ok": False,
            "message": "В этой поездке пока нет рюкзака. Откройте приложение и добавьте багаж, чтобы бот мог работать с чеклистом.",
        }

    selected_key = _normalize_section_key(section_key)
    safe_mode = _normalize_interaction_mode(interaction_mode)
    selected_section = next((section for section in sections if section["key"] == selected_key), None)
    if not selected_section:
        selected_section = sections[0]
        selected_key = selected_section["key"]

    quantity_map = selected_section.get("item_quantities") or {}
    packed_map = selected_section.get("packed_quantities") or {}
    progress = _get_section_progress(selected_section)
    visible_items = progress["visible_items"]
    checked_count = progress["checked_count"]
    total_count = progress["total_count"]
    page_count = max(1, (len(visible_items) + CHECKLIST_BUTTON_PAGE_SIZE - 1) // CHECKLIST_BUTTON_PAGE_SIZE)
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
        "interaction_mode": safe_mode,
        "interaction_mode_label": CHECKLIST_INTERACTION_MODES[safe_mode],
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
                "label": _format_item_with_quantity(item, quantity_map, packed_map),
                "quantity": _get_item_quantity(quantity_map, item),
                "packed": _get_item_packed_quantity(packed_map, item),
                "partial": 0 < _get_item_packed_quantity(packed_map, item) < _get_item_quantity(quantity_map, item),
                "checked": _get_item_packed_quantity(packed_map, item) >= _get_item_quantity(quantity_map, item),
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
            f"Режим кнопок: {CHECKLIST_INTERACTION_MODES[safe_mode]}\n"
            f"Осталось: {max(total_count - checked_count, 0)}"
            + ("\n\nКнопки ниже работают по выбранному режиму." if total_count else "\n\nВ этом разделе пока пусто.")
        ),
    }


async def build_interactive_checklist_view(
    tg_user: TelegramUser,
    selected_slug: str | None = None,
    checklist_id: int | None = None,
    section_key: str | None = None,
    page: int = 0,
    interaction_mode: str | None = None,
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
            interaction_mode=interaction_mode,
        )


async def toggle_interactive_checklist_item(
    tg_user: TelegramUser,
    checklist_id: int,
    section_key: str,
    page: int,
    item_index: int,
    interaction_mode: str | None = None,
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
        if not _normalize_section_key(section_key):
            updated_view = _build_interactive_checklist_view_data(
                checklist,
                actor_user_id=actor_user_id,
                section_key=None,
                page=0,
                interaction_mode=interaction_mode,
            )
            if not updated_view["ok"]:
                return updated_view
            return {
                "ok": True,
                "view": updated_view,
                "message": "Открыл актуальный рюкзак",
            }

        view = _build_interactive_checklist_view_data(
            checklist,
            actor_user_id=actor_user_id,
            section_key=section_key,
            page=page,
            interaction_mode=interaction_mode,
        )
        if not view["ok"]:
            return view

        if item_index < 0 or item_index >= len(view["items"]):
            return {
                "ok": False,
                "message": "Эта кнопка уже устарела. Откройте чеклист заново.",
            }

        item_name = view["items"][item_index]["name"]
        normalized_item = _normalize_text(item_name)
        selected_mode = _normalize_interaction_mode(interaction_mode)

        def _compute_next_packed(current_packed: int, needed: int) -> int:
            if selected_mode == "unpack":
                return max(0, current_packed - 1)
            if selected_mode == "complete":
                return 0 if current_packed >= needed else needed
            return min(needed, current_packed + 1)

        def _build_feedback(previous_packed: int, next_packed: int, needed: int) -> str:
            progress = f"{next_packed}/{needed}"
            if selected_mode == "unpack":
                if previous_packed <= 0:
                    return f"{item_name} уже пусто"
                return f"{item_name}: {progress}"
            if selected_mode == "complete":
                return f"{item_name}: {progress}"
            if previous_packed >= needed:
                return f"{item_name} уже собрано полностью"
            return f"{item_name}: {progress}"

        backpack_id = int(view["section_key"][1:])
        backpack = next((bp for bp in (checklist.backpacks or []) if bp.id == backpack_id), None)
        if not backpack:
            return {
                "ok": False,
                "message": "Не удалось найти нужный рюкзак. Откройте чеклист заново.",
            }

        quantity_map = _normalize_quantity_map(getattr(backpack, "item_quantities", None))
        packed_map = _hydrate_packed_quantities(
            _normalize_items_list(backpack.items),
            _normalize_items_list(backpack.checked_items),
            quantity_map,
            getattr(backpack, "packed_quantities", None),
        )
        removed_items = [item for item in (backpack.removed_items or []) if _normalize_text(item) != normalized_item]
        needed_quantity = _get_item_quantity(quantity_map, item_name)
        previous_packed = _get_item_packed_quantity(packed_map, item_name)
        next_packed = _compute_next_packed(previous_packed, needed_quantity)
        if next_packed > 0:
            packed_map[normalized_item] = next_packed
        else:
            packed_map.pop(normalized_item, None)
        backpack.packed_quantities = packed_map
        backpack.checked_items = [
            item for item in (backpack.items or [])
            if _get_item_packed_quantity(packed_map, item) >= _get_item_quantity(quantity_map, item)
        ]
        backpack.removed_items = removed_items
        feedback_message = _build_feedback(previous_packed, next_packed, needed_quantity)

        await db.commit()
        updated_checklist = await crud.get_checklist_by_id(db, checklist.id)
        updated_view = _build_interactive_checklist_view_data(
            updated_checklist,
            actor_user_id=actor_user_id,
            section_key=view["section_key"],
            page=page,
            interaction_mode=selected_mode,
        )

        return {
            "ok": True,
            "view": updated_view,
            "message": feedback_message,
        }


async def build_trip_overview_text(tg_user: TelegramUser, selected_slug: str = None) -> str:
    async with SessionLocal() as db:
        current_user = await crud.get_user_by_tg_id(db, str(tg_user.id))
        if selected_slug:
            checklist = await _get_checklist_by_slug_with_session(db, tg_user, selected_slug)
        else:
            checklist = await _get_primary_checklist_with_session(db, tg_user)

        if not checklist:
            return (
                "У вас пока нет поездок в Luggify.\n\n"
                "Откройте mini app, создайте первую поездку, и я смогу подсказывать по ней."
            )

        actor_user_id = current_user.id if current_user else None
        sections = _build_checklist_sections(checklist, actor_user_id, own_only=actor_user_id is not None)

    if not sections:
        return (
            f"Поездка: {format_checklist_title(checklist)}\n\n"
            "В этой поездке пока нет рюкзака, поэтому боту нечего считать."
        )

    progress_items = [_get_section_progress(section) for section in sections]
    total_items = sum(progress["total_count"] for progress in progress_items)
    checked_items = sum(progress["checked_count"] for progress in progress_items)
    remaining_items = sum(progress["remaining_count"] for progress in progress_items)
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
        f"Осталось вещей: {remaining_items}"
    )


async def build_remaining_items_text(tg_user: TelegramUser, selected_slug: str = None) -> str:
    async with SessionLocal() as db:
        current_user = await crud.get_user_by_tg_id(db, str(tg_user.id))
        if selected_slug:
            checklist = await _get_checklist_by_slug_with_session(db, tg_user, selected_slug)
        else:
            checklist = await _get_primary_checklist_with_session(db, tg_user)

        if not checklist:
            return "Пока не вижу поездок. Сначала создайте чеклист, и я подскажу, что осталось собрать."

        actor_user_id = current_user.id if current_user else None
        sections = _build_checklist_sections(checklist, actor_user_id, own_only=actor_user_id is not None)

    if not sections:
        return f"По поездке в {checklist.city} пока нет рюкзака, поэтому боту нечего проверять."

    remaining_rows = []
    total_items = 0
    remaining_total = 0
    show_section_labels = len(sections) > 1

    for section in sections:
        progress = _get_section_progress(section)
        total_items += progress["total_count"]
        remaining_total += progress["remaining_count"]
        quantity_map = section.get("item_quantities") or {}
        packed_map = section.get("packed_quantities") or {}
        for item in progress["remaining_items"]:
            label = _format_item_with_quantity(item, quantity_map, packed_map)
            remaining_rows.append(f"• {section['label']}: {label}" if show_section_labels else f"• {label}")

    if total_items == 0:
        return f"По поездке в {checklist.city} в твоём багаже пока нет вещей."
    if not remaining_rows:
        return f"По поездке в {checklist.city} у вас всё отмечено. Похоже, вы отлично собраны."

    preview = "\n".join(remaining_rows[:10])
    suffix = "\n…" if len(remaining_rows) > 10 else ""
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
