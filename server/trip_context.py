from __future__ import annotations

import re
from collections.abc import Iterable as IterableABC
from datetime import date, datetime
from typing import Any, Iterable, Optional


DEFAULT_TRIP_PROFILE = {
    "trip_type": "city_break",
    "trip_activities": [],
    "baggage_format": "flexible",
    "accommodation_type": "unspecified",
    "accommodation_selected": False,
    "laundry_access": "limited",
    "packing_style": "balanced",
    "adults": 2,
    "children_ages": [],
    "child_profiles": [],
    "infants_count": 0,
    "trip_note": "",
    "context_enhanced": False,
    "extracted_tags": [],
}


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple) or isinstance(value, set):
        return list(value)
    if isinstance(value, (str, bytes, dict)):
        return []
    if isinstance(value, IterableABC):
        return list(value)
    return []


def _as_date_string(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    return text or None


def _parse_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _duration_days(start_date: Any, end_date: Any) -> Optional[int]:
    start = _parse_date(start_date)
    end = _parse_date(end_date)
    if not start or not end:
        return None
    return max((end - start).days + 1, 1)


def _get_attr(source: Any, name: str, default: Any = None) -> Any:
    if isinstance(source, dict):
        return source.get(name, default)
    return getattr(source, name, default)


def _safe_int(value: Any, fallback: int = 0) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return parsed


def _normalize_quantity_map(raw_map: Any) -> dict[str, int]:
    normalized: dict[str, int] = {}
    if not isinstance(raw_map, dict):
        return normalized
    for key, value in raw_map.items():
        item_key = str(key or "").strip()
        if not item_key:
            continue
        normalized[item_key] = max(_safe_int(value, 1), 0)
    return normalized


def _get_quantity(quantity_map: dict[str, int], item: str, fallback: int = 1) -> int:
    if item in quantity_map:
        return max(_safe_int(quantity_map.get(item), fallback), 0)

    normalized_item = item.strip().lower()
    for key, value in quantity_map.items():
        if key.strip().lower() == normalized_item:
            return max(_safe_int(value, fallback), 0)
    return fallback


def _normalize_text_map(raw_map: Any) -> dict[str, str]:
    normalized: dict[str, str] = {}
    if not isinstance(raw_map, dict):
        return normalized
    for key, value in raw_map.items():
        item_key = str(key or "").strip().lower().replace("ё", "е")
        text_value = str(value or "").strip()
        if not item_key or not text_value:
            continue
        normalized[item_key] = text_value
    return normalized


def _get_text_value(text_map: dict[str, str], item: str) -> Optional[str]:
    return text_map.get(item.strip().lower().replace("ё", "е"))


def _serialize_forecast_entry(entry: Any) -> dict[str, Any]:
    return {
        "date": _as_date_string(_get_attr(entry, "date")),
        "city": _get_attr(entry, "city"),
        "condition": _get_attr(entry, "condition"),
        "icon": _get_attr(entry, "icon"),
        "temp_min": _get_attr(entry, "temp_min"),
        "temp_max": _get_attr(entry, "temp_max"),
        "humidity": _get_attr(entry, "humidity"),
        "uv_index": _get_attr(entry, "uv_index"),
        "wind_speed": _get_attr(entry, "wind_speed"),
        "source": _get_attr(entry, "source"),
    }


def serialize_forecast(forecast: Iterable[Any] | None) -> list[dict[str, Any]]:
    serialized: list[dict[str, Any]] = []
    for entry in forecast or []:
        serialized.append(_serialize_forecast_entry(entry))
    return serialized


def serialize_events(events: Iterable[Any] | None) -> list[dict[str, Any]]:
    serialized: list[dict[str, Any]] = []
    for event in events or []:
        serialized.append(
            {
                "event_id": _get_attr(event, "id"),
                "event_date": _as_date_string(_get_attr(event, "event_date")),
                "time": _get_attr(event, "time"),
                "title": _get_attr(event, "title"),
                "description": _get_attr(event, "description"),
                "address": _get_attr(event, "address"),
                "lat": _get_attr(event, "lat"),
                "lng": _get_attr(event, "lng"),
                "place_source": _get_attr(event, "place_source"),
                "duration_minutes": _get_attr(event, "duration_minutes"),
                "travel_buffer_minutes": _get_attr(event, "travel_buffer_minutes"),
                "event_type": _get_attr(event, "event_type"),
                "meta": _get_attr(event, "meta") if isinstance(_get_attr(event, "meta"), dict) else {},
            }
        )
    return sorted(serialized, key=lambda item: (str(item.get("event_date") or ""), _event_sort_time(item), str(item.get("title") or "")))


def _event_sort_time(item: dict[str, Any]) -> str:
    if item.get("time"):
        return str(item.get("time"))
    meta = item.get("meta") if isinstance(item.get("meta"), dict) else {}
    day_part = str(meta.get("day_part") or item.get("day_part") or "").lower()
    if any(part in day_part for part in ("morning", "breakfast", "утро", "завтрак")):
        return "09:00"
    if any(part in day_part for part in ("evening", "dinner", "вечер", "ужин")):
        return "19:00"
    if any(part in day_part for part in ("day", "afternoon", "lunch", "день", "обед")):
        return "13:00"
    if str(item.get("event_type") or "").lower() in {"food", "restaurant", "cafe"}:
        return "13:00"
    return "99:99"


def _is_trip_participant(checklist: Any, viewer_user_id: Optional[int]) -> bool:
    if not viewer_user_id:
        return False
    if _get_attr(checklist, "user_id") == viewer_user_id:
        return True
    for backpack in _as_list(_get_attr(checklist, "backpacks")):
        if _get_attr(backpack, "user_id") == viewer_user_id:
            return True
    return False


def serialize_expenses(checklist: Any, viewer_user_id: Optional[int]) -> dict[str, Any]:
    hidden_sections = [str(item) for item in _as_list(_get_attr(checklist, "hidden_sections"))]
    can_view = "expenses" not in hidden_sections or _is_trip_participant(checklist, viewer_user_id)
    base_currency = str(_get_attr(checklist, "expense_base_currency") or "RUB").upper()
    if not can_view:
        return {
            "visible": False,
            "budget_amount": None,
            "base_currency": base_currency,
            "total_spent": 0,
            "remaining": None,
            "by_category": {},
            "items": [],
        }

    items: list[dict[str, Any]] = []
    by_category: dict[str, float] = {}
    total_spent = 0.0
    today = date.today().isoformat()
    today_spent = 0.0
    for expense in _as_list(_get_attr(checklist, "expenses")):
        amount_base = float(_get_attr(expense, "amount_base", 0) or 0)
        category = str(_get_attr(expense, "category") or "other").strip().lower() or "other"
        expense_date = _as_date_string(_get_attr(expense, "expense_date"))
        total_spent += amount_base
        if expense_date == today:
            today_spent += amount_base
        by_category[category] = round(by_category.get(category, 0) + amount_base, 2)
        items.append(
            {
                "id": _get_attr(expense, "id"),
                "expense_date": expense_date,
                "title": _get_attr(expense, "title"),
                "category": category,
                "amount": _get_attr(expense, "amount"),
                "currency": _get_attr(expense, "currency"),
                "amount_base": amount_base,
                "base_currency": _get_attr(expense, "base_currency") or base_currency,
                "note": _get_attr(expense, "note"),
            }
        )
    budget_amount = _get_attr(checklist, "expense_budget_amount")
    profile = _get_attr(checklist, "trip_profile") or {}
    expense_profile = profile.get("expenses") if isinstance(profile, dict) else {}
    daily_budget_amount = expense_profile.get("daily_budget_amount") if isinstance(expense_profile, dict) else None
    remaining = round(float(budget_amount) - total_spent, 2) if budget_amount is not None else None
    today_remaining = round(float(daily_budget_amount) - today_spent, 2) if daily_budget_amount is not None else None
    return {
        "visible": True,
        "budget_amount": budget_amount,
        "daily_budget_amount": daily_budget_amount,
        "base_currency": base_currency,
        "total_spent": round(total_spent, 2),
        "remaining": remaining,
        "today_spent": round(today_spent, 2),
        "today_remaining": today_remaining,
        "by_category": by_category,
        "items": sorted(items, key=lambda item: str(item.get("expense_date") or ""), reverse=True)[:20],
    }


def normalize_trip_profile(profile: dict[str, Any] | None, trip_type: str | None = None) -> dict[str, Any]:
    normalized = dict(DEFAULT_TRIP_PROFILE)
    if isinstance(profile, dict):
        for key in normalized:
            if key in profile:
                normalized[key] = profile[key]
        for key, value in profile.items():
            if key not in normalized:
                normalized[key] = value
    if trip_type:
        normalized["trip_type"] = trip_type
    normalized["trip_activities"] = [
        str(item).strip()
        for item in _as_list(normalized.get("trip_activities"))
        if str(item).strip()
    ]
    normalized["adults"] = max(_safe_int(normalized.get("adults"), 2), 1)
    normalized["children_ages"] = [
        max(_safe_int(item, 0), 0)
        for item in _as_list(normalized.get("children_ages"))
        if 0 <= _safe_int(item, -1) <= 17
    ][:8]
    raw_child_profiles = _as_list(normalized.get("child_profiles"))
    child_profiles: list[dict[str, Any]] = []
    for index, age in enumerate(normalized["children_ages"]):
        raw_profile = raw_child_profiles[index] if index < len(raw_child_profiles) and isinstance(raw_child_profiles[index], dict) else {}
        raw_id = str(raw_profile.get("id") or "").strip()
        child_id = re.sub(r"[^a-zA-Z0-9_-]", "", raw_id)[:48] or f"child_{index + 1}"
        linked_user_id = _safe_int(raw_profile.get("linked_user_id"), 0)
        child_profiles.append(
            {
                "id": child_id,
                "name": str(raw_profile.get("name") or "").strip()[:40],
                "age": age,
                "linked_user_id": linked_user_id if linked_user_id > 0 else None,
            }
        )
    normalized["child_profiles"] = child_profiles
    normalized["infants_count"] = sum(1 for age in normalized["children_ages"] if age < 2)
    normalized["extracted_tags"] = [
        str(item).strip()
        for item in _as_list(normalized.get("extracted_tags"))
        if str(item).strip()
    ]
    return normalized


def _is_hidden_baggage(backpack: Any, hidden_sections: list[str], viewer_user_id: Optional[int]) -> bool:
    backpack_id = _get_attr(backpack, "id")
    if f"backpack:{backpack_id}" not in hidden_sections:
        return False
    return viewer_user_id is None or _get_attr(backpack, "user_id") != viewer_user_id


def _safe_username(user: Any) -> Optional[str]:
    username = _get_attr(user, "username")
    return str(username).strip() if username else None


def _serialize_items(
    *,
    items: list[str],
    checked_items: list[str],
    removed_items: list[str],
    item_quantities: dict[str, int],
    packed_quantities: dict[str, int],
    item_categories: dict[str, str],
) -> list[dict[str, Any]]:
    checked_lookup = {str(item).strip().lower() for item in checked_items}
    removed_lookup = {str(item).strip().lower() for item in removed_items}
    category_lookup = _normalize_text_map(item_categories)
    serialized: list[dict[str, Any]] = []
    for raw_item in items:
        item = str(raw_item or "").strip()
        if not item:
            continue
        normalized_item = item.lower()
        quantity = max(_get_quantity(item_quantities, item, 1), 1)
        explicit_packed = _get_quantity(packed_quantities, item, -1)
        packed_quantity = quantity if normalized_item in checked_lookup else 0
        if explicit_packed >= 0:
            packed_quantity = min(explicit_packed, quantity)
        serialized.append(
            {
                "name": item,
                "category": _get_text_value(category_lookup, item),
                "quantity": quantity,
                "packed_quantity": packed_quantity,
                "is_packed": packed_quantity >= quantity,
                "is_removed": normalized_item in removed_lookup,
            }
        )
    return serialized


def _visible_item_entries(section: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in section.get("items", []) if not item.get("is_removed")]


def _build_section(
    *,
    kind: str,
    label: str,
    items: Any,
    checked_items: Any,
    removed_items: Any,
    item_quantities: Any,
    packed_quantities: Any,
    item_categories: Any,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    quantity_map = _normalize_quantity_map(item_quantities)
    packed_map = _normalize_quantity_map(packed_quantities)
    category_map = _normalize_text_map(item_categories)
    checked = [str(item).strip() for item in _as_list(checked_items) if str(item).strip()]
    removed = [str(item).strip() for item in _as_list(removed_items) if str(item).strip()]
    section = {
        "kind": kind,
        "label": label,
        "items": _serialize_items(
            items=[str(item).strip() for item in _as_list(items) if str(item).strip()],
            checked_items=checked,
            removed_items=removed,
            item_quantities=quantity_map,
            packed_quantities=packed_map,
            item_categories=category_map,
        ),
        "checked_items": checked,
        "removed_items": removed,
        "item_quantities": quantity_map,
        "packed_quantities": packed_map,
        "item_categories": category_map,
    }
    if extra:
        section.update(extra)
    return section


def _build_baggage_label(backpack: Any) -> str:
    name = str(_get_attr(backpack, "name") or "").strip()
    kind = str(_get_attr(backpack, "kind") or "").strip()
    owner = _safe_username(_get_attr(backpack, "user"))
    label = name or kind or "Багаж"
    return f"{label} {owner}".strip() if owner else label


def serialize_visible_baggage(
    checklist: Any,
    viewer_user_id: Optional[int] = None,
) -> tuple[list[dict[str, Any]], list[int]]:
    hidden_sections = [str(item) for item in _as_list(_get_attr(checklist, "hidden_sections"))]
    visible_backpacks: list[dict[str, Any]] = []
    hidden_baggage_ids: list[int] = []

    for backpack in _as_list(_get_attr(checklist, "backpacks")):
        backpack_id = _get_attr(backpack, "id")
        if _is_hidden_baggage(backpack, hidden_sections, viewer_user_id):
            if backpack_id is not None:
                hidden_baggage_ids.append(backpack_id)
            continue

        user = _get_attr(backpack, "user")
        visible_backpacks.append(
            _build_section(
                kind="backpack",
                label=_build_baggage_label(backpack),
                items=_get_attr(backpack, "items"),
                checked_items=_get_attr(backpack, "checked_items"),
                removed_items=_get_attr(backpack, "removed_items"),
                item_quantities=_get_attr(backpack, "item_quantities"),
                packed_quantities=_get_attr(backpack, "packed_quantities"),
                item_categories=_get_attr(backpack, "item_categories"),
                extra={
                    "backpack_id": backpack_id,
                    "user_id": _get_attr(backpack, "user_id"),
                    "child_profile_id": _get_attr(backpack, "child_profile_id"),
                    "owner_username": _safe_username(user),
                    "name": _get_attr(backpack, "name"),
                    "baggage_kind": _get_attr(backpack, "kind"),
                    "is_default": bool(_get_attr(backpack, "is_default", False)),
                    "sort_order": _get_attr(backpack, "sort_order"),
                },
            )
        )

    return visible_backpacks, hidden_baggage_ids


def _serialize_participants(checklist: Any, trip_profile: dict[str, Any], visible_backpacks: list[dict[str, Any]], language: str = "ru") -> list[dict[str, Any]]:
    participants: dict[str, dict[str, Any]] = {}
    
    # 1. Add the trip owner
    owner = _get_attr(checklist, "user")
    owner_user_id = _get_attr(checklist, "user_id")
    if owner_user_id:
        username = _safe_username(owner)
        participants[str(owner_user_id)] = {
            "user_id": owner_user_id,
            "username": username,
            "name": username or ("Я" if language == "ru" else "Me"),
            "role": "owner",
            "baggage_ids": [],
        }

    # 2. Add children from trip_profile
    child_profiles = trip_profile.get("child_profiles", [])
    for child in child_profiles:
        if not isinstance(child, dict):
            continue
        child_id = str(child.get("id") or "")
        if not child_id:
            continue
        participants[f"child:{child_id}"] = {
            "child_profile_id": child_id,
            "name": child.get("name"),
            "age": child.get("age"),
            "role": "child",
            "baggage_ids": [],
        }

    # 3. Add anyone who has a visible bag (and link to existing participants or create new ones)
    for backpack in visible_backpacks:
        user_id = backpack.get("user_id")
        child_profile_id = backpack.get("child_profile_id")
        
        if child_profile_id:
            key = f"child:{child_profile_id}"
            participant = participants.get(key)
            if not participant:
                participant = participants.setdefault(key, {
                    "child_profile_id": child_profile_id,
                    "name": backpack.get("label"),
                    "role": "child",
                    "baggage_ids": [],
                })
            if backpack.get("backpack_id") is not None:
                if backpack["backpack_id"] not in participant["baggage_ids"]:
                    participant["baggage_ids"].append(backpack["backpack_id"])
        elif user_id:
            key = str(user_id)
            participant = participants.get(key)
            if not participant:
                username = backpack.get("owner_username")
                participant = participants.setdefault(key, {
                    "user_id": user_id,
                    "username": username,
                    "name": username,
                    "role": "participant",
                    "baggage_ids": [],
                })
            if backpack.get("backpack_id") is not None:
                if backpack["backpack_id"] not in participant["baggage_ids"]:
                    participant["baggage_ids"].append(backpack["backpack_id"])

    return list(participants.values())


def _build_packing_summary(shared_section: dict[str, Any], backpacks: list[dict[str, Any]]) -> dict[str, Any]:
    packed_items: list[dict[str, Any]] = []
    remaining_items: list[dict[str, Any]] = []
    removed_items: list[dict[str, Any]] = []
    total_visible = 0
    total_packed = 0

    sections = [shared_section, *backpacks]
    for section in sections:
        label = section.get("label") or "items"
        for item in section.get("items", []):
            payload = {
                "name": item.get("name"),
                "section": label,
                "quantity": item.get("quantity"),
                "packed_quantity": item.get("packed_quantity"),
            }
            if item.get("is_removed"):
                removed_items.append(payload)
                continue
            total_visible += max(_safe_int(item.get("quantity"), 1), 1)
            total_packed += max(_safe_int(item.get("packed_quantity"), 0), 0)
            if item.get("is_packed"):
                packed_items.append(payload)
            else:
                remaining_items.append(payload)

    return {
        "packed_items": packed_items,
        "remaining_items": remaining_items,
        "removed_items": removed_items,
        "packed_count": total_packed,
        "visible_count": total_visible,
        "remaining_count": max(total_visible - total_packed, 0),
    }


def _normalize_attractions(attractions: Iterable[Any] | None, limit: int = 8) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for attraction in attractions or []:
        if not isinstance(attraction, dict):
            continue
        name = str(attraction.get("name") or "").strip()
        if not name:
            continue
        normalized.append(
            {
                "name": name,
                "address": attraction.get("address"),
                "description": attraction.get("description"),
                "lat": attraction.get("lat"),
                "lng": attraction.get("lng"),
                "rating": attraction.get("rating"),
                "price_level": attraction.get("price_level"),
                "place_type": attraction.get("place_type") or attraction.get("type"),
                "link": attraction.get("link"),
            }
        )
        if len(normalized) >= limit:
            break
    return normalized


def build_trip_context(
    checklist: Any,
    *,
    viewer_user_id: Optional[int] = None,
    language: str = "ru",
    forecast: Iterable[Any] | None = None,
    cached_attractions: Iterable[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the canonical AI-visible trip context from an existing checklist."""
    effective_forecast = forecast if forecast is not None else _get_attr(checklist, "daily_forecast")
    raw_trip_profile = _get_attr(checklist, "trip_profile") or {}
    if not isinstance(raw_trip_profile, dict):
        raw_trip_profile = {}
    trip_profile = normalize_trip_profile(
        raw_trip_profile,
        trip_type=raw_trip_profile.get("trip_type"),
    )
    visible_backpacks, hidden_baggage_ids = serialize_visible_baggage(checklist, viewer_user_id)
    shared_section = _build_section(
        kind="shared",
        label="shared packing list",
        items=_get_attr(checklist, "items"),
        checked_items=_get_attr(checklist, "checked_items"),
        removed_items=_get_attr(checklist, "removed_items"),
        item_quantities=_get_attr(checklist, "item_quantities"),
        packed_quantities=_get_attr(checklist, "packed_quantities"),
        item_categories=_get_attr(checklist, "item_categories"),
    )

    return {
        "source": "checklist",
        "language": language,
        "trip": {
            "city": _get_attr(checklist, "city"),
            "origin_city": _get_attr(checklist, "origin_city"),
            "start_date": _as_date_string(_get_attr(checklist, "start_date")),
            "end_date": _as_date_string(_get_attr(checklist, "end_date")),
            "duration_days": _duration_days(_get_attr(checklist, "start_date"), _get_attr(checklist, "end_date")),
            "avg_temp": _get_attr(checklist, "avg_temp"),
            "conditions": [str(item) for item in _as_list(_get_attr(checklist, "conditions")) if str(item).strip()],
            "transports": [str(item) for item in _as_list(_get_attr(checklist, "transports")) if str(item).strip()],
        },
        "trip_profile": trip_profile,
        "daily_forecast": serialize_forecast(effective_forecast),
        "events": serialize_events(_get_attr(checklist, "events")),
        "baggage": {
            "shared": shared_section,
            "backpacks": visible_backpacks,
            "visible_backpacks_count": len(visible_backpacks),
            "hidden_backpacks_count": len(hidden_baggage_ids),
        },
        "participants": _serialize_participants(checklist, trip_profile, visible_backpacks, language),
        "attractions": _normalize_attractions(cached_attractions),
        "expenses": serialize_expenses(checklist, viewer_user_id),
        "packing_summary": _build_packing_summary(shared_section, visible_backpacks),
        "privacy": {
            "viewer_user_id": viewer_user_id,
            "hidden_sections": [str(item) for item in _as_list(_get_attr(checklist, "hidden_sections"))],
            "hidden_baggage_ids": hidden_baggage_ids,
        },
    }


def build_ad_hoc_trip_context(
    *,
    city: str,
    start_date: str = "",
    end_date: str = "",
    avg_temp: Any = None,
    trip_type: str = "city_break",
    trip_profile: dict[str, Any] | None = None,
    daily_forecast: Iterable[Any] | None = None,
    cached_attractions: Iterable[dict[str, Any]] | None = None,
    language: str = "ru",
) -> dict[str, Any]:
    profile = normalize_trip_profile(trip_profile or {}, trip_type=trip_type)
    return {
        "source": "ad_hoc",
        "language": language,
        "trip": {
            "city": city,
            "origin_city": None,
            "start_date": _as_date_string(start_date),
            "end_date": _as_date_string(end_date),
            "duration_days": _duration_days(start_date, end_date),
            "avg_temp": avg_temp,
            "conditions": [],
            "transports": [],
        },
        "trip_profile": profile,
        "daily_forecast": serialize_forecast(daily_forecast),
        "events": [],
        "baggage": {
            "shared": _build_section(
                kind="shared",
                label="shared packing list",
                items=[],
                checked_items=[],
                removed_items=[],
                item_quantities={},
                packed_quantities={},
                item_categories={},
            ),
            "backpacks": [],
            "visible_backpacks_count": 0,
            "hidden_backpacks_count": 0,
        },
        "participants": [],
        "attractions": _normalize_attractions(cached_attractions),
        "expenses": {
            "visible": True,
            "budget_amount": None,
            "base_currency": "RUB",
            "total_spent": 0,
            "remaining": None,
            "by_category": {},
            "items": [],
        },
        "packing_summary": {
            "packed_items": [],
            "remaining_items": [],
            "removed_items": [],
            "packed_count": 0,
            "visible_count": 0,
            "remaining_count": 0,
        },
        "privacy": {
            "viewer_user_id": None,
            "hidden_sections": [],
            "hidden_baggage_ids": [],
        },
    }
