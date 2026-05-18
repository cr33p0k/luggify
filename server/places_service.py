from __future__ import annotations

import math
import os
from typing import Any
from urllib.parse import quote_plus

import httpx


GEOAPIFY_PLACES_URL = "https://api.geoapify.com/v2/places"
RESTAURANT_CATEGORIES = (
    "catering.restaurant,catering.cafe,catering.bar,catering.fast_food"
)
CHAIN_NAME_PATTERNS = (
    "mcdonald",
    "mc donald",
    "kfc",
    "burger king",
    "subway",
    "starbucks",
    "domino",
    "pizza hut",
    "dodo pizza",
    "пицца хат",
    "додо",
    "макдоналд",
    "бургер кинг",
    "pizza mania",
    "andy's pizza",
    "andys pizza",
    "andy’s pizza",
)
BREAKFAST_AVOID_PATTERNS = (
    "pizza",
    "пицц",
    "beer",
    "pub",
    "piv",
    "pivní",
    "piana",
    "mojito",
    "bar",
)
LOCAL_INTERESTING_PATTERNS = (
    "placinte",
    "plăcinte",
    "mold",
    "local",
    "vin",
    "wine",
    "bistro",
    "kitchen",
    "cafe",
    "кафе",
)


def _coerce_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _read_raw_properties(properties: dict[str, Any]) -> dict[str, Any]:
    datasource = properties.get("datasource")
    if isinstance(datasource, dict) and isinstance(datasource.get("raw"), dict):
        return datasource["raw"]
    return {}


def _first_text(*values: Any) -> str:
    for value in values:
        normalized = _normalize_text(value)
        if normalized:
            return normalized
    return ""


def _extract_cuisine(properties: dict[str, Any]) -> str:
    raw = _read_raw_properties(properties)
    cuisine = _first_text(properties.get("cuisine"), raw.get("cuisine"))
    return cuisine.replace(";", ", ").replace("_", " ")


def _infer_cuisine_from_name(name: str) -> str:
    normalized = _normalize_text(name).casefold()
    rules = (
        (("sandwich", "sandwicherie", "сандвич", "сэндвич"), "сэндвичи"),
        (("coffee", "кофе", "roastery"), "кофе и десерты"),
        (("tea", "bubble tea", "чай"), "напитки и десерты"),
        (("pizza", "pizzeria", "пицц"), "пицца"),
        (("sushi", "суши"), "суши"),
        (("burger", "бургер"), "бургеры"),
        (("wine", "vin", "вино", "bar"), "вино и закуски"),
        (("bakery", "boulangerie", "patisserie", "пекар"), "выпечка"),
        (("steak", "гриль", "grill"), "гриль"),
        (("kebab", "шаурм", "shawarma"), "кебаб и уличная еда"),
    )
    for patterns, label in rules:
        if any(pattern in normalized for pattern in patterns):
            return label
    return ""


def _humanize_food_style(value: str, language: str) -> str:
    normalized_parts = [
        part.strip().casefold()
        for part in re_split_cuisine(value)
        if part.strip()
    ]
    if not normalized_parts:
        return ""

    ru_map = {
        "seafood": "морепродукты",
        "fish": "рыба и морепродукты",
        "italian": "итальянская кухня",
        "moldovan": "молдавская кухня",
        "regional": "локальная кухня",
        "local": "локальная кухня",
        "coffee shop": "кофе и десерты",
        "coffee": "кофе и десерты",
        "sandwich": "сэндвичи",
        "sandwiches": "сэндвичи",
        "pizza": "пицца",
        "sushi": "суши",
        "japanese": "японская кухня",
        "burger": "бургеры",
        "burgers": "бургеры",
        "bakery": "выпечка",
        "dessert": "десерты",
        "wine": "вино и закуски",
        "asian": "азиатская кухня",
        "european": "европейская кухня",
        "thai": "тайская кухня",
        "turkish": "турецкая кухня",
        "mexican": "мексиканская кухня",
        "vegan": "веганские блюда",
        "vegetarian": "вегетарианские блюда",
    }
    en_map = {
        "coffee shop": "coffee and desserts",
        "coffee": "coffee and desserts",
        "regional": "local food",
        "local": "local food",
    }
    if language == "ru":
        labels = [ru_map.get(part, part.replace("_", " ")) for part in normalized_parts]
    else:
        labels = [en_map.get(part, part.replace("_", " ")) for part in normalized_parts]

    unique_labels = []
    for label in labels:
        if label and label not in unique_labels:
            unique_labels.append(label)
    return ", ".join(unique_labels[:2])


def re_split_cuisine(value: str) -> list[str]:
    return str(value or "").replace("_", " ").replace(";", ",").split(",")


def _extract_address(properties: dict[str, Any]) -> str:
    raw = _read_raw_properties(properties)
    formatted = _first_text(
        properties.get("formatted"),
        properties.get("address_line2"),
        properties.get("address_line1"),
        raw.get("addr:full"),
    )
    if formatted:
        return formatted
    street = _first_text(properties.get("street"), raw.get("addr:street"))
    house = _first_text(properties.get("housenumber"), raw.get("addr:housenumber"))
    city = _first_text(properties.get("city"), raw.get("addr:city"))
    return ", ".join(part for part in (f"{street} {house}".strip(), city) if part)


def _category_label(categories: list[str], language: str) -> str:
    category_set = {str(item).lower() for item in categories or []}
    if "catering.cafe" in category_set:
        return "Кафе" if language == "ru" else "Cafe"
    if "catering.bar" in category_set:
        return "Бар" if language == "ru" else "Bar"
    if "catering.fast_food" in category_set:
        return "Быстрая еда" if language == "ru" else "Fast food"
    return "Ресторан" if language == "ru" else "Restaurant"


def _build_description(
    properties: dict[str, Any],
    category_label: str,
    distance_meters: int | None,
    language: str,
    meal_type: str | None = None,
) -> str:
    food_style = _humanize_food_style(
        _extract_cuisine(properties) or _infer_cuisine_from_name(properties.get("name")),
        language,
    )
    if not food_style:
        return ""

    if language == "ru":
        return food_style[:1].upper() + food_style[1:] + "."

    return food_style[:1].upper() + food_style[1:] + "."


def _build_map_url(name: str, address: str, lat: float, lng: float, language: str) -> str:
    normalized_name = _normalize_text(name)
    normalized_address = _normalize_text(address)
    if normalized_name and normalized_name.casefold() in normalized_address.casefold():
        query_text = normalized_address
    else:
        query_text = " ".join(part for part in (normalized_name, normalized_address) if part)
    query = quote_plus(query_text or normalized_name or f"{lat:.6f},{lng:.6f}")
    if language == "ru":
        return f"https://yandex.ru/maps/?text={query}&ll={lng:.6f},{lat:.6f}&z=17"
    return f"https://www.google.com/maps/search/?api=1&query={query}"


def _quality_score(properties: dict[str, Any], meal_type: str | None = None) -> int:
    score = 0
    categories = {str(item).lower() for item in (properties.get("categories") or []) if item}
    normalized_meal = str(meal_type or "").strip().lower()
    name = _normalize_text(properties.get("name")).casefold()
    if _normalize_text(properties.get("name")):
        score += 5
    if "catering.restaurant" in categories:
        score += 4
    if "catering.cafe" in categories:
        score += 3
    if "catering.bar" in categories:
        score += 2
    if "catering.fast_food" in categories:
        score -= 6
    if normalized_meal == "breakfast":
        if "catering.cafe" in categories:
            score += 5
        if "catering.bar" in categories or "catering.fast_food" in categories:
            score -= 8
        if any(pattern in name for pattern in BREAKFAST_AVOID_PATTERNS):
            score -= 10
    elif normalized_meal in {"lunch", "dinner"}:
        if "catering.restaurant" in categories:
            score += 3
        if "catering.fast_food" in categories:
            score -= 8
    if any(pattern in name for pattern in LOCAL_INTERESTING_PATTERNS):
        score += 2
    if _normalize_text(properties.get("cuisine")):
        score += 2
    if _normalize_text(properties.get("website")):
        score += 2
    if _normalize_text(properties.get("opening_hours")):
        score += 2
    if _normalize_text(properties.get("phone")):
        score += 1
    contact = properties.get("contact")
    if isinstance(contact, dict) and _normalize_text(contact.get("phone")):
        score += 1
    return score


def _is_uninteresting_chain(name: str) -> bool:
    normalized = name.casefold()
    return any(pattern in normalized for pattern in CHAIN_NAME_PATTERNS)


def _is_wrong_for_meal(name: str, categories: list[str], meal_type: str | None) -> bool:
    normalized_meal = str(meal_type or "").strip().lower()
    normalized_name = name.casefold()
    category_set = {str(item).lower() for item in categories or []}
    if normalized_meal == "breakfast":
        if any(pattern in normalized_name for pattern in BREAKFAST_AVOID_PATTERNS):
            return True
        if "catering.fast_food" in category_set or "catering.bar" in category_set:
            return True
    return False


def _has_unavailable_tags(properties: dict[str, Any]) -> bool:
    raw = _read_raw_properties(properties)
    unavailable_keys = (
        "disused",
        "abandoned",
        "demolished",
        "closed",
        "disused:amenity",
        "abandoned:amenity",
        "was:amenity",
        "end_date",
    )
    for key in unavailable_keys:
        value = _normalize_text(raw.get(key) or properties.get(key)).casefold()
        if value and value not in {"no", "false", "0"}:
            return True
    lifecycle_prefixes = ("disused:", "abandoned:", "demolished:", "was:")
    return any(str(key).startswith(lifecycle_prefixes) for key in raw.keys())


def parse_geoapify_restaurants(
    payload: dict[str, Any],
    *,
    language: str,
    limit: int = 5,
    meal_type: str | None = None,
) -> list[dict[str, Any]]:
    options: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    for feature in payload.get("features") or []:
        if not isinstance(feature, dict):
            continue
        properties = feature.get("properties") or {}
        if not isinstance(properties, dict):
            continue
        name = _normalize_text(properties.get("name"))
        if not name:
            continue
        if _has_unavailable_tags(properties):
            continue
        if _is_uninteresting_chain(name):
            continue
        normalized_name = name.casefold()
        if normalized_name in seen_names:
            continue
        seen_names.add(normalized_name)

        lat = _coerce_float(properties.get("lat"))
        lng = _coerce_float(properties.get("lon"))
        if lat is None or lng is None:
            geometry = feature.get("geometry") or {}
            coordinates = geometry.get("coordinates") if isinstance(geometry, dict) else None
            if isinstance(coordinates, list) and len(coordinates) >= 2:
                lng = _coerce_float(coordinates[0])
                lat = _coerce_float(coordinates[1])
        if lat is None or lng is None:
            continue

        categories = properties.get("categories") or []
        if not isinstance(categories, list):
            categories = []
        if _is_wrong_for_meal(name, categories, meal_type):
            continue
        category_label = _category_label(categories, language)
        address = _extract_address(properties)
        distance_meters = properties.get("distance")
        try:
            distance_meters = int(round(float(distance_meters)))
        except (TypeError, ValueError):
            distance_meters = None

        options.append(
            {
                "option_id": _normalize_text(properties.get("place_id")) or f"geoapify-{len(options) + 1}",
                "name": name,
                "description": _build_description(properties, category_label, distance_meters, language, meal_type),
                "category": category_label,
                "address": address or None,
                "distance_meters": distance_meters,
                "lat": lat,
                "lng": lng,
                "source": "geoapify",
                "map_url": _build_map_url(name, address, lat, lng, language),
                "meta": {
                    "place_id": properties.get("place_id"),
                    "datasource": properties.get("datasource"),
                    "categories": categories,
                    "cuisine": properties.get("cuisine"),
                    "opening_hours": properties.get("opening_hours"),
                    "website": properties.get("website"),
                },
                "_score": _quality_score(properties, meal_type),
            }
        )

    options.sort(key=lambda item: (-(item.get("_score") or 0), item.get("distance_meters") if item.get("distance_meters") is not None else 999999))
    return [{key: value for key, value in option.items() if key != "_score"} for option in options[:limit]]


async def search_nearby_restaurants(
    *,
    lat: float,
    lng: float,
    language: str = "ru",
    radius_meters: int = 1200,
    limit: int = 5,
    meal_type: str | None = None,
) -> dict[str, Any]:
    api_key = os.getenv("GEOAPIFY_API_KEY", "").strip()
    if not api_key:
        return {
            "options": [],
            "provider": "geoapify",
            "attribution": "Geoapify",
            "configured": False,
        }

    radius = max(250, min(int(radius_meters or 1200), 3000))
    params = {
        "categories": RESTAURANT_CATEGORIES,
        "filter": f"circle:{lng},{lat},{radius}",
        "bias": f"proximity:{lng},{lat}",
        "limit": min(max(limit * 4, 10), 20),
        "lang": "ru" if language == "ru" else "en",
        "apiKey": api_key,
    }
    async with httpx.AsyncClient(timeout=12) as client:
        response = await client.get(GEOAPIFY_PLACES_URL, params=params)
        response.raise_for_status()
        payload = response.json()

    return {
        "options": parse_geoapify_restaurants(payload, language=language, limit=limit, meal_type=meal_type),
        "provider": "geoapify",
        "attribution": "Geoapify | OpenStreetMap contributors",
        "configured": True,
    }
