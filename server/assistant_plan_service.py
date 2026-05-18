from __future__ import annotations

import re
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

import httpx

import crud
import schemas
from itinerary_logic import haversine_distance_km, optimize_itinerary_plan_items


GEOAPIFY_GEOCODE_URL = "https://api.geoapify.com/v1/geocode/search"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
PLACE_GEOCODE_CACHE: dict[str, dict[str, Any] | None] = {}


@dataclass
class RequestedTripDay:
    event_date: date | None
    label: str
    error: str | None = None


ORDINAL_DAY_PATTERNS = (
    (0, re.compile(r"\b(?:перв(?:ый|ого|ом|ую)|1(?:й|ый)?|first|day\s*1)\b", re.IGNORECASE)),
    (1, re.compile(r"\b(?:втор(?:ой|ого|ом|ую)|2(?:й|ой)?|second|day\s*2)\b", re.IGNORECASE)),
    (2, re.compile(r"\b(?:трет(?:ий|ьего|ьем|ью)|3(?:й|ий)?|third|day\s*3)\b", re.IGNORECASE)),
    (3, re.compile(r"\b(?:четв[её]рт(?:ый|ого|ом|ую)|4(?:й|ый)?|fourth|day\s*4)\b", re.IGNORECASE)),
    (4, re.compile(r"\b(?:пят(?:ый|ого|ом|ую)|5(?:й|ый)?|fifth|day\s*5)\b", re.IGNORECASE)),
)

DAY_PART_LABELS_RU = {
    "morning": "Утро",
    "day": "День",
    "afternoon": "День",
    "evening": "Вечер",
    "night": "Вечер",
}

DAY_PART_LABELS_EN = {
    "morning": "Morning",
    "day": "Day",
    "afternoon": "Day",
    "evening": "Evening",
    "night": "Evening",
}


def _as_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


def _format_short_date(value: date, language: str = "ru") -> str:
    if language == "en":
        return value.strftime("%d %b %Y")
    return value.strftime("%d.%m.%Y")


def _date_in_trip(value: date, start_date: date, end_date: date) -> bool:
    return start_date <= value <= end_date


def _date_from_day_month(day: int, month: int, start_date: date, end_date: date) -> date | None:
    years = range(start_date.year, end_date.year + 1)
    for year in years:
        try:
            candidate = date(year, month, day)
        except ValueError:
            continue
        if _date_in_trip(candidate, start_date, end_date):
            return candidate
    return None


def resolve_requested_trip_day(
    prompt: str,
    checklist,
    *,
    today: date | None = None,
    language: str = "ru",
) -> RequestedTripDay:
    start_date = _as_date(getattr(checklist, "start_date", None))
    end_date = _as_date(getattr(checklist, "end_date", None)) or start_date
    if not start_date or not end_date:
        return RequestedTripDay(None, "", "У поездки не указаны даты." if language == "ru" else "Trip dates are missing.")

    normalized = str(prompt or "").strip().lower().replace("ё", "е")
    current_day = today or date.today()

    if re.search(r"\b(today|сегодня)\b", normalized):
        if _date_in_trip(current_day, start_date, end_date):
            return RequestedTripDay(current_day, "сегодня" if language == "ru" else "today")
        return RequestedTripDay(
            None,
            "",
            (
                f"Сегодня {_format_short_date(current_day, language)} не входит в даты поездки "
                f"{_format_short_date(start_date, language)} — {_format_short_date(end_date, language)}."
                if language == "ru"
                else (
                    f"Today {_format_short_date(current_day, language)} is outside this trip "
                    f"({_format_short_date(start_date, language)} — {_format_short_date(end_date, language)})."
                )
            ),
        )

    if re.search(r"\b(tomorrow|завтра)\b", normalized):
        tomorrow = current_day + timedelta(days=1)
        if _date_in_trip(tomorrow, start_date, end_date):
            return RequestedTripDay(tomorrow, "завтра" if language == "ru" else "tomorrow")
        return RequestedTripDay(
            None,
            "",
            (
                f"Завтра {_format_short_date(tomorrow, language)} не входит в даты поездки "
                f"{_format_short_date(start_date, language)} — {_format_short_date(end_date, language)}."
                if language == "ru"
                else (
                    f"Tomorrow {_format_short_date(tomorrow, language)} is outside this trip "
                    f"({_format_short_date(start_date, language)} — {_format_short_date(end_date, language)})."
                )
            ),
        )

    date_match = re.search(r"(?<!\d)(\d{1,2})\.(\d{1,2})(?:\.(\d{2,4}))?(?!\d)", normalized)
    if date_match:
        day = int(date_match.group(1))
        month = int(date_match.group(2))
        raw_year = date_match.group(3)
        candidate = None
        if raw_year:
            year = int(raw_year)
            if year < 100:
                year += 2000
            try:
                candidate = date(year, month, day)
            except ValueError:
                candidate = None
        else:
            candidate = _date_from_day_month(day, month, start_date, end_date)
        if candidate and _date_in_trip(candidate, start_date, end_date):
            return RequestedTripDay(candidate, _format_short_date(candidate, language))
        return RequestedTripDay(
            None,
            "",
            (
                f"Дата {day:02d}.{month:02d} не входит в поездку "
                f"{_format_short_date(start_date, language)} — {_format_short_date(end_date, language)}."
                if language == "ru"
                else (
                    f"{day:02d}.{month:02d} is outside this trip "
                    f"({_format_short_date(start_date, language)} — {_format_short_date(end_date, language)})."
                )
            ),
        )

    for offset, pattern in ORDINAL_DAY_PATTERNS:
        if pattern.search(normalized):
            candidate = start_date + timedelta(days=offset)
            if _date_in_trip(candidate, start_date, end_date):
                return RequestedTripDay(candidate, f"день {offset + 1}" if language == "ru" else f"day {offset + 1}")
            return RequestedTripDay(
                None,
                "",
                (
                    f"В этой поездке нет дня {offset + 1}: даты "
                    f"{_format_short_date(start_date, language)} — {_format_short_date(end_date, language)}."
                    if language == "ru"
                    else (
                        f"This trip has no day {offset + 1}: "
                        f"{_format_short_date(start_date, language)} — {_format_short_date(end_date, language)}."
                    )
                ),
            )

    default_day = current_day if _date_in_trip(current_day, start_date, end_date) else start_date
    label = "сегодня" if default_day == current_day and language == "ru" else _format_short_date(default_day, language)
    return RequestedTripDay(default_day, label)


def build_day_plan_question(prompt: str, event_date: date, language: str = "ru") -> str:
    user_prompt = str(prompt or "").strip()
    if language == "en":
        base = f"Plan one rich, realistic day for {event_date.isoformat()}."
        suffix = f" User request: {user_prompt}" if user_prompt else ""
        return base + suffix
    base = f"Составь насыщенный, реалистичный план только на дату {event_date.isoformat()}."
    suffix = f" Запрос пользователя: {user_prompt}" if user_prompt else ""
    return base + suffix


def force_plan_proposals_date(proposals: list[dict[str, Any]] | None, event_date: date) -> list[dict[str, Any]]:
    normalized = []
    for proposal in proposals or []:
        if not isinstance(proposal, dict):
            continue
        item = dict(proposal)
        item["event_date"] = event_date.isoformat()
        normalized.append(item)
    return normalized


def _proposal_payload(proposal: Any) -> dict[str, Any]:
    if hasattr(proposal, "model_dump"):
        return proposal.model_dump(mode="json")
    if isinstance(proposal, dict):
        return dict(proposal)
    return {}


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _first_trip_city(city: Any) -> str:
    raw_city = _clean_text(city)
    if not raw_city:
        return ""
    return _clean_text(raw_city.split("+", 1)[0].split(",", 1)[0])


def _coerce_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed


def _is_generic_food_proposal(proposal: dict[str, Any]) -> bool:
    event_type = _clean_text(proposal.get("event_type")).casefold()
    if event_type in {"food", "restaurant", "cafe", "bar"}:
        return True
    title = _clean_text(proposal.get("title")).casefold()
    return bool(re.search(r"\b(breakfast|lunch|dinner)\b|завтрак|обед|ужин", title))


def _geocode_cache_key(title: str, city: str, language: str) -> str:
    return f"{language}|{title.casefold()}|{city.casefold()}"


def _normalized_address_from_geoapify(item: dict[str, Any]) -> str | None:
    for key in ("formatted", "address_line2", "address_line1"):
        value = _clean_text(item.get(key))
        if value:
            return value
    return None


async def _resolve_city_coordinates(city: str) -> tuple[float, float] | None:
    if not city:
        return None
    place = await _geocode_place(city, "", language="ru", city_coords=None, allow_city_result=True)
    if not place:
        return None
    lat = _coerce_float(place.get("lat"))
    lng = _coerce_float(place.get("lng"))
    if lat is None or lng is None:
        return None
    return lat, lng


async def _geocode_place(
    title: str,
    city: str,
    *,
    language: str = "ru",
    city_coords: tuple[float, float] | None = None,
    allow_city_result: bool = False,
) -> dict[str, Any] | None:
    title = _clean_text(title)
    city = _clean_text(city)
    if not title:
        return None

    cache_key = _geocode_cache_key(title, city, language)
    if cache_key in PLACE_GEOCODE_CACHE:
        return PLACE_GEOCODE_CACHE[cache_key]

    query = ", ".join(part for part in (title, city) if part)
    geoapify_key = os.getenv("GEOAPIFY_API_KEY", "").strip()
    if geoapify_key:
        params: dict[str, Any] = {
            "text": query,
            "apiKey": geoapify_key,
            "limit": 3,
            "format": "json",
            "lang": "ru" if language == "ru" else "en",
        }
        if city_coords:
            city_lat, city_lng = city_coords
            params["bias"] = f"proximity:{city_lng},{city_lat}"
            params["filter"] = f"circle:{city_lng},{city_lat},35000"
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                response = await client.get(GEOAPIFY_GEOCODE_URL, params=params)
            if response.status_code == 200:
                for item in response.json().get("results") or []:
                    lat = _coerce_float(item.get("lat"))
                    lng = _coerce_float(item.get("lon"))
                    if lat is None or lng is None:
                        continue
                    if city_coords and not allow_city_result:
                        distance_km = haversine_distance_km(city_coords, (lat, lng))
                        if distance_km is None or distance_km > 35:
                            continue
                    address = _normalized_address_from_geoapify(item)
                    if not address:
                        continue
                    if not allow_city_result and city and city.casefold() not in address.casefold():
                        country_code = _clean_text(item.get("country_code")).casefold()
                        if country_code not in {"md", "ro", "bg", "tr", "gr", "it", "fr", "es", "pt", "de", "at", "cz", "hu", "pl", "rs", "me", "hr", "si", "sk", "ge", "am"}:
                            continue
                    resolved = {
                        "address": address,
                        "lat": lat,
                        "lng": lng,
                        "place_source": "geoapify",
                    }
                    PLACE_GEOCODE_CACHE[cache_key] = resolved
                    return resolved
        except Exception as exc:
            print(f"[Assistant plan geocode] Geoapify failed for {query}: {exc}")

    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            response = await client.get(
                NOMINATIM_URL,
                params={
                    "q": query,
                    "format": "json",
                    "limit": 3,
                    "addressdetails": 1,
                    "accept-language": "ru" if language == "ru" else "en",
                },
                headers={"User-Agent": "Luggify/1.0 (travel assistant)"},
            )
        if response.status_code == 200:
            for item in response.json() or []:
                lat = _coerce_float(item.get("lat"))
                lng = _coerce_float(item.get("lon"))
                address = _clean_text(item.get("display_name"))
                if lat is None or lng is None or not address:
                    continue
                if city_coords and not allow_city_result:
                    distance_km = haversine_distance_km(city_coords, (lat, lng))
                    if distance_km is None or distance_km > 35:
                        continue
                resolved = {
                    "address": address,
                    "lat": lat,
                    "lng": lng,
                    "place_source": "nominatim",
                }
                PLACE_GEOCODE_CACHE[cache_key] = resolved
                return resolved
    except Exception as exc:
        print(f"[Assistant plan geocode] Nominatim failed for {query}: {exc}")

    PLACE_GEOCODE_CACHE[cache_key] = None
    return None


async def _enrich_plan_proposals_with_places(checklist, proposals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    city = _first_trip_city(getattr(checklist, "city", ""))
    if not city:
        return proposals
    city_coords = await _resolve_city_coordinates(city)
    enriched: list[dict[str, Any]] = []
    for proposal in proposals:
        item = dict(proposal)
        if (
            _is_generic_food_proposal(item)
            or (_clean_text(item.get("address")) and item.get("lat") is not None and item.get("lng") is not None)
        ):
            enriched.append(item)
            continue
        resolved = await _geocode_place(
            _clean_text(item.get("title")),
            city,
            language="ru",
            city_coords=city_coords,
        )
        if resolved:
            item["address"] = item.get("address") or resolved["address"]
            item["lat"] = item.get("lat") if item.get("lat") is not None else resolved["lat"]
            item["lng"] = item.get("lng") if item.get("lng") is not None else resolved["lng"]
            item["place_source"] = item.get("place_source") or resolved["place_source"]
        elif not _clean_text(item.get("address")):
            title = _clean_text(item.get("title"))
            if title:
                item["address"] = f"{title}, {city}"
                item["place_source"] = item.get("place_source") or "search_fallback"
        enriched.append(item)
    return enriched


async def apply_plan_proposals_to_checklist(db, checklist, proposals: list[Any]) -> dict[str, Any]:
    start_date = _as_date(getattr(checklist, "start_date", None))
    end_date = _as_date(getattr(checklist, "end_date", None)) or start_date
    if not start_date or not end_date:
        raise ValueError("У поездки не указаны даты")

    enriched_proposals = await _enrich_plan_proposals_with_places(checklist, [
        _proposal_payload(proposal) for proposal in proposals
    ])
    applied_count = 0
    created_event_ids: list[int] = []

    for proposal in enriched_proposals:
        proposal_date = _as_date(proposal.get("event_date"))
        if not proposal_date:
            raise ValueError("Некорректная дата события")
        if proposal_date < start_date or proposal_date > end_date:
            raise ValueError("Дата события вне диапазона поездки")

        created_event = await crud.create_itinerary_event(
            db,
            checklist.id,
            schemas.ItineraryEventCreate(
                event_date=proposal_date,
                time=proposal.get("time"),
                title=str(proposal.get("title") or "").strip(),
                description=(proposal.get("description") or None),
                address=(proposal.get("address") or None),
                lat=proposal.get("lat"),
                lng=proposal.get("lng"),
                place_source=proposal.get("place_source"),
                duration_minutes=proposal.get("duration_minutes"),
                travel_buffer_minutes=proposal.get("travel_buffer_minutes"),
                event_type=proposal.get("event_type"),
                meta={
                    "day_part": proposal.get("day_part"),
                    "reason": proposal.get("reason"),
                    "weather_note": proposal.get("weather_note"),
                    "source": "assistant",
                    "image": proposal.get("image"),
                    "image_position": proposal.get("image_position"),
                    "logistics": {
                        "optimizer": "nearest_neighbor_by_day_part",
                    },
                },
            ),
        )
        applied_count += 1
        created_event_ids.append(created_event.id)

    return {
        "applied_count": applied_count,
        "created_event_ids": created_event_ids,
    }


def format_telegram_day_plan(
    checklist,
    proposals: list[dict[str, Any]],
    event_date: date,
    *,
    answer: str = "",
    language: str = "ru",
) -> str:
    city = getattr(checklist, "city", None) or ("Trip" if language == "en" else "Поездка")
    labels = DAY_PART_LABELS_EN if language == "en" else DAY_PART_LABELS_RU
    fallback_label = "Day" if language == "en" else "День"
    title = (
        f"Day plan: {city} · {_format_short_date(event_date, language)}"
        if language == "en"
        else f"План дня: {city} · {_format_short_date(event_date, language)}"
    )

    if not proposals:
        fallback = str(answer or "").strip()
        if fallback:
            return f"{title}\n\n{fallback}"
        return f"{title}\n\n" + ("AI did not return itinerary items." if language == "en" else "AI не вернул пункты маршрута.")

    ordered = optimize_itinerary_plan_items(force_plan_proposals_date(proposals, event_date))
    grouped: dict[str, list[dict[str, Any]]] = {}
    for proposal in ordered:
        day_part = str(proposal.get("day_part") or "day").lower()
        label = labels.get(day_part, fallback_label)
        grouped.setdefault(label, []).append(proposal)

    lines = [title]
    for label in (labels["morning"], labels["day"], labels["evening"]):
        items = grouped.get(label) or []
        if not items:
            continue
        lines.extend(["", label])
        for item in items:
            time = str(item.get("time") or "").strip()
            item_title = str(item.get("title") or "").strip()
            description = str(item.get("description") or item.get("reason") or "").strip()
            address = str(item.get("address") or "").strip()
            prefix = f"{time} · " if time else ""
            lines.append(f"{prefix}{item_title}")
            if address:
                lines.append(f"  {address}")
            if description:
                lines.append(f"  {description[:180]}")

    if language == "en":
        lines.append("\nYou can save this plan to the itinerary.")
    else:
        lines.append("\nМожно сохранить этот план в маршрут.")
    return "\n".join(lines)
