from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any


DAY_PART_ORDER = {
    "morning": 0,
    "day": 1,
    "afternoon": 1,
    "evening": 2,
    "night": 2,
}

DAY_PART_START_MINUTES = {
    "morning": 9 * 60 + 30,
    "day": 13 * 60,
    "evening": 18 * 60,
}

MEAL_SLOTS = {
    "breakfast": {"day_part": "morning", "start": 6 * 60, "ideal": 8 * 60 + 30, "end": 12 * 60},
    "lunch": {"day_part": "day", "start": 12 * 60, "ideal": 13 * 60 + 15, "end": 17 * 60},
    "dinner": {"day_part": "evening", "start": 17 * 60, "ideal": 19 * 60, "end": 24 * 60},
}

EVENT_TYPE_DURATION_MINUTES = {
    "food": 75,
    "restaurant": 75,
    "cafe": 60,
    "walk": 50,
    "rest": 45,
    "snack": 25,
    "street_food": 25,
    "shopping": 75,
    "transport": 60,
    "museum": 105,
    "sight": 90,
    "attraction": 90,
}

ROUTE_OUTLIER_NEAREST_KM = 7.0


def _get_value(item: Any, key: str, default: Any = None) -> Any:
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def _coerce_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def get_event_coordinates(item: Any) -> tuple[float, float] | None:
    lat = _coerce_float(_get_value(item, "lat"))
    lng = _coerce_float(_get_value(item, "lng"))
    if lat is None or lng is None:
        return None
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return None
    return lat, lng


def haversine_distance_km(
    first: tuple[float, float] | None,
    second: tuple[float, float] | None,
) -> float | None:
    if not first or not second:
        return None
    lat1, lng1 = first
    lat2, lng2 = second
    radius_km = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lng / 2) ** 2
    )
    return 2 * radius_km * math.asin(math.sqrt(a))


def estimate_travel_buffer_minutes(distance_km: float | None) -> int:
    if distance_km is None:
        return 20
    if distance_km <= 0.35:
        return 8
    if distance_km <= 0.9:
        return 12
    if distance_km <= 1.8:
        return 18
    if distance_km <= 3.5:
        return 28
    if distance_km <= 6.0:
        return 40
    if distance_km <= 10.0:
        return 55
    if distance_km <= 16.0:
        return 75
    return 95


def normalize_duration_minutes(value: Any, event_type: Any = None) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        normalized_type = str(event_type or "").strip().lower()
        parsed = EVENT_TYPE_DURATION_MINUTES.get(normalized_type, 90)
    if parsed <= 0:
        normalized_type = str(event_type or "").strip().lower()
        parsed = EVENT_TYPE_DURATION_MINUTES.get(normalized_type, 90)
    return max(20, min(parsed, 240))


def _parse_time_minutes(value: Any) -> int | None:
    text = str(value or "").strip()
    try:
        parsed = datetime.strptime(text, "%H:%M")
    except ValueError:
        return None
    return parsed.hour * 60 + parsed.minute


def _format_time(minutes: int) -> str:
    minutes = max(6 * 60, min(minutes, 23 * 60 + 30))
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _normalize_day_part(value: Any, time_value: Any = None) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"morning", "утро"}:
        return "morning"
    if normalized in {"day", "afternoon", "день"}:
        return "day"
    if normalized in {"evening", "night", "вечер"}:
        return "evening"
    parsed_time = _parse_time_minutes(time_value)
    if parsed_time is not None:
        if parsed_time < 12 * 60:
            return "morning"
        if parsed_time < 17 * 60:
            return "day"
        return "evening"
    return "day"


def _detect_meal_type(item: Any) -> str | None:
    text = " ".join(
        str(_get_value(item, key, "") or "")
        for key in ("title", "description", "event_type", "day_part")
    ).lower()
    if "breakfast" in text or "завтрак" in text:
        return "breakfast"
    if "lunch" in text or "обед" in text:
        return "lunch"
    if "dinner" in text or "ужин" in text:
        return "dinner"
    return None


def _clamp_meal_minutes(meal_type: str | None, minutes: int) -> int:
    if not meal_type or meal_type not in MEAL_SLOTS:
        return minutes
    slot = MEAL_SLOTS[meal_type]
    start = int(slot["start"])
    end = int(slot["end"])
    if minutes < start:
        return start
    if minutes > end:
        return end
    return minutes


def _meal_sort_minutes(item: dict[str, Any]) -> int | None:
    meal_type = str(item.get("_meal_type") or "") or _detect_meal_type(item)
    if meal_type in MEAL_SLOTS:
        return int(MEAL_SLOTS[meal_type]["ideal"])
    return None


def _is_meal_item(item: dict[str, Any]) -> bool:
    return bool(item.get("_meal_type") or _detect_meal_type(item))


def _is_route_exempt(item: dict[str, Any]) -> bool:
    event_type = str(item.get("event_type") or "").strip().lower()
    if event_type in {"food", "restaurant", "cafe", "transport", "hotel", "lodging"}:
        return True
    if item.get("must_keep") or item.get("fixed"):
        return True
    return _detect_meal_type(item) is not None


def _filter_isolated_route_outliers(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    routed_items = [
        item for item in items
        if get_event_coordinates(item) is not None and not _is_route_exempt(item)
    ]
    if len(routed_items) < 4:
        return items

    excluded_ids: set[int] = set()
    for item in routed_items:
        coords = get_event_coordinates(item)
        nearest_distance = min(
            (
                distance for other in routed_items
                if other is not item
                for distance in [haversine_distance_km(coords, get_event_coordinates(other))]
                if distance is not None
            ),
            default=None,
        )
        if nearest_distance is not None and nearest_distance > ROUTE_OUTLIER_NEAREST_KM:
            excluded_ids.add(id(item))

    if not excluded_ids:
        return items
    return [item for item in items if id(item) not in excluded_ids]


def _item_sort_key(item: dict[str, Any]) -> tuple[int, int, int]:
    meal_minutes = _meal_sort_minutes(item)
    return (
        DAY_PART_ORDER.get(str(item.get("day_part") or "day").lower(), 1),
        meal_minutes
        if meal_minutes is not None
        else (_parse_time_minutes(item.get("time")) if _parse_time_minutes(item.get("time")) is not None else 24 * 60),
        int(item.get("_original_index", 0)),
    )


def _nearest_neighbor_order(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(items) <= 2:
        return sorted(items, key=_item_sort_key)

    remaining = sorted(items, key=_item_sort_key)
    ordered = [remaining.pop(0)]
    while remaining:
        current_coords = get_event_coordinates(ordered[-1])
        if current_coords is None:
            ordered.append(remaining.pop(0))
            continue
        best_index = 0
        best_distance = float("inf")
        for index, item in enumerate(remaining):
            distance = haversine_distance_km(current_coords, get_event_coordinates(item))
            if distance is not None and distance < best_distance:
                best_distance = distance
                best_index = index
        ordered.append(remaining.pop(best_index))
    return ordered


def _separate_adjacent_meals(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = list(items)
    index = 0
    while index < len(ordered) - 1:
        if not (_is_meal_item(ordered[index]) and _is_meal_item(ordered[index + 1])):
            index += 1
            continue

        move_index = next(
            (candidate for candidate in range(index + 2, len(ordered)) if not _is_meal_item(ordered[candidate])),
            None,
        )
        if move_index is not None:
            activity = ordered.pop(move_index)
            ordered.insert(index + 1, activity)
            index += 2
            continue

        # If the AI did not provide enough activities to separate meals, prefer
        # removing the later meal over showing two food stops back to back.
        ordered.pop(index + 1)
    return ordered


def _date_key(value: Any) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return str(value or "").strip()


def optimize_itinerary_plan_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Order plan items by day, day part, and nearby coordinates; then assign route-aware buffers."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for index, raw_item in enumerate(items):
        if not isinstance(raw_item, dict):
            continue
        item = dict(raw_item)
        item["_original_index"] = index
        item["event_date"] = _date_key(item.get("event_date"))
        meal_type = _detect_meal_type(item)
        if meal_type:
            explicit_minutes = _parse_time_minutes(item.get("time"))
            slot = MEAL_SLOTS[meal_type]
            item["day_part"] = str(MEAL_SLOTS[meal_type]["day_part"])
            item["time"] = (
                _format_time(explicit_minutes)
                if explicit_minutes is not None and int(slot["start"]) <= explicit_minutes <= int(slot["end"])
                else None
            )
            item["_meal_type"] = meal_type
            item["event_type"] = item.get("event_type") or "food"
        else:
            item["day_part"] = _normalize_day_part(item.get("day_part"), item.get("time"))
        item["duration_minutes"] = normalize_duration_minutes(item.get("duration_minutes"), item.get("event_type"))
        grouped.setdefault(item["event_date"], []).append(item)

    optimized: list[dict[str, Any]] = []
    for day_key in sorted(grouped):
        day_items = _filter_isolated_route_outliers(grouped[day_key])
        ordered_day: list[dict[str, Any]] = []
        for day_part in ("morning", "day", "evening"):
            bucket = [item for item in day_items if item.get("day_part") == day_part]
            ordered_day.extend(_nearest_neighbor_order(bucket))
        ordered_day = _separate_adjacent_meals(ordered_day)

        current_minutes = 6 * 60
        previous_coords: tuple[float, float] | None = None
        for item in ordered_day:
            day_part = str(item.get("day_part") or "day")
            explicit_minutes = _parse_time_minutes(item.get("time"))
            meal_type = str(item.get("_meal_type") or "") or None
            part_start = (
                int(MEAL_SLOTS[meal_type]["start"])
                if meal_type in MEAL_SLOTS
                else DAY_PART_START_MINUTES.get(day_part, DAY_PART_START_MINUTES["day"])
            )
            current_minutes = max(current_minutes, part_start)
            if explicit_minutes is not None and meal_type is None:
                current_minutes = max(current_minutes, explicit_minutes)
            elif explicit_minutes is not None and meal_type is not None:
                current_minutes = max(current_minutes, explicit_minutes)
            current_coords = get_event_coordinates(item)
            distance_km = haversine_distance_km(previous_coords, current_coords)
            estimated_buffer = 0 if previous_coords is None else estimate_travel_buffer_minutes(distance_km)
            try:
                existing_buffer = int(item.get("travel_buffer_minutes") or 0)
            except (TypeError, ValueError):
                existing_buffer = 0
            travel_buffer = max(existing_buffer, estimated_buffer)
            if previous_coords is not None:
                current_minutes += travel_buffer
            current_minutes = _clamp_meal_minutes(meal_type, current_minutes)
            item["travel_buffer_minutes"] = travel_buffer
            item["time"] = _format_time(current_minutes)
            item.pop("_meal_type", None)
            item.pop("_original_index", None)
            optimized.append(item)
            current_minutes += int(item["duration_minutes"])
            if current_coords is not None:
                previous_coords = current_coords

    return optimized
