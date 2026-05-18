from __future__ import annotations

import json
import math
import os
import re
from typing import Any

import httpx

from translations import get_item


GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"
DEFAULT_GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

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

TRIP_TYPE_ALIASES = {
    "vacation": "city_break",
    "city_break": "city_break",
    "citybreak": "city_break",
    "city": "city_break",
    "beach": "beach_escape",
    "beach_escape": "beach_escape",
    "business": "business_trip",
    "business_trip": "business_trip",
    "active": "outdoor_adventure",
    "adventure": "outdoor_adventure",
    "outdoor": "outdoor_adventure",
    "outdoor_adventure": "outdoor_adventure",
    "camping": "outdoor_adventure",
    "winter": "winter_trip",
    "winter_trip": "winter_trip",
    "family": "family_trip",
    "family_trip": "family_trip",
    "romantic": "romantic_getaway",
    "romantic_getaway": "romantic_getaway",
}

TRIP_ACTIVITY_ALIASES = {
    "city_break": "city_break",
    "city": "city_break",
    "business_trip": "business_trip",
    "business": "business_trip",
    "beach_escape": "beach_escape",
    "beach": "beach_escape",
    "outdoor_adventure": "outdoor_adventure",
    "adventure": "outdoor_adventure",
    "winter_trip": "winter_trip",
    "winter": "winter_trip",
    "romantic_getaway": "romantic_getaway",
    "romantic": "romantic_getaway",
    "traveling_with_children": "traveling_with_children",
    "children": "traveling_with_children",
    "swimming": "swimming",
    "water": "swimming",
    "hiking": "hiking",
    "trekking": "hiking",
    "workout": "workout",
    "sport": "workout",
    "formal_events": "romantic_getaway",
    "formal": "romantic_getaway",
    "photo_content": "photo_content",
    "photo": "photo_content",
}

ACCOMMODATION_ALIASES = {
    "unspecified": "unspecified",
    "not_specified": "unspecified",
    "none": "unspecified",
    "hotel": "hotel",
    "apartment": "apartment",
    "apartment_hotel": "apartment",
    "hostel": "hostel",
    "camping": "camping",
    "camp": "camping",
}

LAUNDRY_ACCESS_ALIASES = {
    "none": "none",
    "no": "none",
    "limited": "limited",
    "some": "limited",
    "easy": "easy",
    "full": "easy",
}

PACKING_STYLE_ALIASES = {
    "light": "light",
    "minimal": "light",
    "balanced": "balanced",
    "prepared": "prepared",
    "comfort": "prepared",
}

BAGGAGE_FORMAT_ALIASES = {
    "flexible": "flexible",
    "any": "flexible",
    "carry_on": "carry_on",
    "carry-on": "carry_on",
    "hand_luggage": "carry_on",
    "backpack": "carry_on",
    "hiking_backpack": "hiking_backpack",
    "hiking-backpack": "hiking_backpack",
    "trekking_backpack": "hiking_backpack",
    "trekking-backpack": "hiking_backpack",
    "suitcase": "suitcase",
    "suitcase_plus_carry_on": "suitcase_plus_carry_on",
    "suitcase_carry_on": "suitcase_plus_carry_on",
    "suitcase+carry_on": "suitcase_plus_carry_on",
}

TRIP_TYPE_ALLOWED = {
    "city_break",
    "beach_escape",
    "business_trip",
    "outdoor_adventure",
    "winter_trip",
    "family_trip",
    "romantic_getaway",
}
TRIP_ACTIVITY_ALLOWED = {
    "city_break",
    "business_trip",
    "beach_escape",
    "outdoor_adventure",
    "winter_trip",
    "romantic_getaway",
    "swimming",
    "hiking",
    "workout",
    "photo_content",
    "traveling_with_children",
}
ACCOMMODATION_ALLOWED = {"unspecified", "hotel", "apartment", "hostel", "camping"}
LAUNDRY_ACCESS_ALLOWED = {"none", "limited", "easy"}
PACKING_STYLE_ALLOWED = {"light", "balanced", "prepared"}
BAGGAGE_FORMAT_ALLOWED = {"flexible", "carry_on", "suitcase", "suitcase_plus_carry_on", "hiking_backpack"}

TRIP_NOTE_HINTS = [
    {
        "tag": "beach",
        "trip_type": "beach_escape",
        "activities": ["swimming"],
        "keywords": ["пляж", "море", "океан", "бассейн", "surf", "swim", "beach", "sea", "pool"],
    },
    {
        "tag": "mountains",
        "trip_type": "outdoor_adventure",
        "activities": ["hiking"],
        "keywords": ["горы", "трек", "поход", "хайк", "hike", "trail", "mountain", "campfire"],
    },
    {
        "tag": "business",
        "trip_type": "business_trip",
        "activities": ["business_trip"],
        "keywords": ["конферен", "встреч", "переговор", "workshop", "conference", "meeting", "client"],
    },
    {
        "tag": "winter",
        "trip_type": "winter_trip",
        "activities": ["hiking"],
        "keywords": ["лыж", "сноуборд", "ski", "snowboard", "snow", "снег"],
    },
    {
        "tag": "family",
        "activities": ["traveling_with_children"],
        "keywords": ["ребен", "ребён", "малыш", "baby", "kid", "toddler", "семь"],
    },
    {
        "tag": "romantic",
        "trip_type": "romantic_getaway",
        "activities": ["romantic_getaway"],
        "keywords": ["свад", "медовый", "романт", "anniversary", "honeymoon", "wedding", "date night"],
    },
    {
        "tag": "fitness",
        "activities": ["workout"],
        "keywords": ["зал", "йога", "бег", "gym", "workout", "run", "fitness", "pilates"],
    },
    {
        "tag": "content",
        "activities": ["photo_content"],
        "keywords": ["съем", "съём", "контент", "камера", "фото", "video", "content", "camera", "shoot"],
    },
]

ACCOMMODATION_NOTE_HINTS = {
    "camping": ["палат", "кемп", "camping", "campground", "tent"],
    "hostel": ["хостел", "hostel", "shared room", "общая комната"],
    "apartment": ["апарт", "квартира", "airbnb", "apartment", "studio"],
    "hotel": ["отель", "hotel", "resort"],
}

LAUNDRY_NOTE_HINTS = {
    "easy": ["стирал", "laundry", "washing machine", "washer", "прачеч"],
    "none": ["без стир", "no laundry", "carry-on only", "ручная кладь"],
}

PACKING_STYLE_NOTE_HINTS = {
    "light": ["налегке", "минимум вещей", "carry-on only", "light packing", "minimal packing"],
    "prepared": ["с запасом", "на все случаи", "prepared", "just in case", "extra outfit"],
}


def _clean_string(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _clean_unique(values: list[Any] | None) -> list[str]:
    cleaned: list[str] = []
    for raw_value in values or []:
        value = _clean_string(raw_value)
        if not value or value in cleaned:
            continue
        cleaned.append(value)
    return cleaned


def _safe_positive_int(value: Any, fallback: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed > 0 else fallback


def _safe_nonnegative_int(value: Any, fallback: int = 0) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed >= 0 else fallback


def _normalize_children_ages(values: list[Any] | None) -> list[int]:
    normalized: list[int] = []
    for raw_value in values or []:
        try:
            parsed = int(raw_value)
        except (TypeError, ValueError):
            continue
        if parsed < 0 or parsed > 17:
            continue
        normalized.append(parsed)
    return normalized[:8]


def _normalize_child_profiles(values: Any, children_ages: list[int]) -> list[dict[str, Any]]:
    raw_profiles = values if isinstance(values, list) else []
    normalized: list[dict[str, Any]] = []
    for index, age in enumerate(children_ages):
        raw_profile = raw_profiles[index] if index < len(raw_profiles) and isinstance(raw_profiles[index], dict) else {}
        raw_id = _clean_string(raw_profile.get("id"))
        child_id = re.sub(r"[^a-zA-Z0-9_-]", "", raw_id)[:48] or f"child_{index + 1}"
        raw_name = _clean_string(raw_profile.get("name"))
        try:
            linked_user_id = int(raw_profile.get("linked_user_id") or 0)
        except (TypeError, ValueError):
            linked_user_id = 0
        normalized.append(
            {
                "id": child_id,
                "name": raw_name[:40],
                "age": age,
                "linked_user_id": linked_user_id if linked_user_id > 0 else None,
            }
        )
    return normalized


def _normalize_slug(value: Any, aliases: dict[str, str], allowed: set[str], fallback: str) -> str:
    normalized = _clean_string(value).lower().replace("-", "_").replace(" ", "_")
    if normalized in aliases:
        return aliases[normalized]
    if normalized in allowed:
        return normalized
    return fallback


def normalize_trip_type(value: Any) -> str:
    return _normalize_slug(value, TRIP_TYPE_ALIASES, TRIP_TYPE_ALLOWED, DEFAULT_TRIP_PROFILE["trip_type"])


def normalize_trip_activities(values: list[Any] | None) -> list[str]:
    normalized: list[str] = []
    for raw_value in values or []:
        activity = _normalize_slug(raw_value, TRIP_ACTIVITY_ALIASES, TRIP_ACTIVITY_ALLOWED, "")
        if not activity or activity in normalized:
            continue
        normalized.append(activity)
    return normalized


def normalize_baggage_format(value: Any) -> str:
    return _normalize_slug(value, BAGGAGE_FORMAT_ALIASES, BAGGAGE_FORMAT_ALLOWED, DEFAULT_TRIP_PROFILE["baggage_format"])


def get_default_baggage_kinds(raw_profile: dict[str, Any] | None) -> list[str]:
    baggage_format = normalize_baggage_format((raw_profile or {}).get("baggage_format"))
    if baggage_format == "carry_on":
        return ["carry_on"]
    if baggage_format == "hiking_backpack":
        return ["backpack"]
    if baggage_format == "suitcase_plus_carry_on":
        return ["suitcase", "carry_on"]
    return ["suitcase"]


def normalize_trip_profile(raw_profile: dict[str, Any] | None) -> dict[str, Any]:
    source = raw_profile or {}
    extracted_tags = _clean_unique(source.get("extracted_tags"))
    note = _clean_string(source.get("trip_note"))
    raw_accommodation = _clean_string(source.get("accommodation_type")).lower().replace("-", "_").replace(" ", "_")
    accommodation_selected = (
        (raw_accommodation in ACCOMMODATION_ALIASES and ACCOMMODATION_ALIASES.get(raw_accommodation) != "unspecified")
        or (raw_accommodation in ACCOMMODATION_ALLOWED and raw_accommodation != "unspecified")
    )
    children_ages = _normalize_children_ages(source.get("children_ages"))
    child_profiles = _normalize_child_profiles(source.get("child_profiles"), children_ages)
    return {
        "trip_type": normalize_trip_type(source.get("trip_type")),
        "trip_activities": normalize_trip_activities(source.get("trip_activities")),
        "baggage_format": normalize_baggage_format(source.get("baggage_format")),
        "accommodation_type": _normalize_slug(
            source.get("accommodation_type"),
            ACCOMMODATION_ALIASES,
            ACCOMMODATION_ALLOWED,
            DEFAULT_TRIP_PROFILE["accommodation_type"],
        ),
        "accommodation_selected": bool(source.get("accommodation_selected")) or accommodation_selected,
        "laundry_access": _normalize_slug(
            source.get("laundry_access"),
            LAUNDRY_ACCESS_ALIASES,
            LAUNDRY_ACCESS_ALLOWED,
            DEFAULT_TRIP_PROFILE["laundry_access"],
        ),
        "packing_style": _normalize_slug(
            source.get("packing_style"),
            PACKING_STYLE_ALIASES,
            PACKING_STYLE_ALLOWED,
            DEFAULT_TRIP_PROFILE["packing_style"],
        ),
        "adults": _safe_positive_int(source.get("adults"), DEFAULT_TRIP_PROFILE["adults"]),
        "children_ages": children_ages,
        "child_profiles": child_profiles,
        "infants_count": len([age for age in children_ages if age < 2]),
        "trip_note": note[:400],
        "context_enhanced": bool(source.get("context_enhanced")),
        "extracted_tags": extracted_tags[:12],
    }


def merge_trip_profiles(base_profile: dict[str, Any] | None, override_profile: dict[str, Any] | None) -> dict[str, Any]:
    base = normalize_trip_profile(base_profile)
    override = normalize_trip_profile(override_profile)
    merged = {
        **base,
        **override,
        "trip_activities": normalize_trip_activities([*(base.get("trip_activities") or []), *(override.get("trip_activities") or [])]),
        "baggage_format": override.get("baggage_format") or base.get("baggage_format") or DEFAULT_TRIP_PROFILE["baggage_format"],
        "accommodation_selected": bool(base.get("accommodation_selected")) or bool(override.get("accommodation_selected")),
        "trip_note": override.get("trip_note") or base.get("trip_note") or "",
        "context_enhanced": bool(base.get("context_enhanced")) or bool(override.get("context_enhanced")),
        "extracted_tags": _clean_unique([*(base.get("extracted_tags") or []), *(override.get("extracted_tags") or [])]),
    }
    return normalize_trip_profile(merged)


def _text_has_keyword(value: str, keyword: str) -> bool:
    normalized_text = f" {value.lower()} "
    normalized_keyword = keyword.lower().strip()
    return normalized_keyword in normalized_text


def _extract_context_with_heuristics(profile: dict[str, Any]) -> dict[str, Any]:
    note = _clean_string(profile.get("trip_note"))
    if not note:
        return {}

    normalized_note = note.lower()
    inferred_trip_type = None
    inferred_activities: list[str] = []
    inferred_tags: list[str] = []
    inferred_accommodation = None
    inferred_laundry = None
    inferred_packing_style = None
    inferred_baggage_format = None

    for hint in TRIP_NOTE_HINTS:
        if any(_text_has_keyword(normalized_note, keyword) for keyword in hint["keywords"]):
            if hint.get("trip_type") and not inferred_trip_type:
                inferred_trip_type = hint["trip_type"]
            inferred_activities.extend(hint.get("activities") or [])
            if hint.get("tag"):
                inferred_tags.append(hint["tag"])

    for accommodation_type, keywords in ACCOMMODATION_NOTE_HINTS.items():
        if any(_text_has_keyword(normalized_note, keyword) for keyword in keywords):
            inferred_accommodation = accommodation_type
            inferred_tags.append(accommodation_type)
            break

    for laundry_access, keywords in LAUNDRY_NOTE_HINTS.items():
        if any(_text_has_keyword(normalized_note, keyword) for keyword in keywords):
            inferred_laundry = laundry_access
            inferred_tags.append(f"laundry:{laundry_access}")
            break

    for packing_style, keywords in PACKING_STYLE_NOTE_HINTS.items():
        if any(_text_has_keyword(normalized_note, keyword) for keyword in keywords):
            inferred_packing_style = packing_style
            inferred_tags.append(f"packing:{packing_style}")
            break

    if any(_text_has_keyword(normalized_note, keyword) for keyword in ["чемодан и ручная кладь", "чемодан + ручная кладь", "suitcase and carry-on", "suitcase + carry-on"]):
        inferred_baggage_format = "suitcase_plus_carry_on"
        inferred_tags.append("baggage:suitcase_plus_carry_on")
    elif any(_text_has_keyword(normalized_note, keyword) for keyword in ["ручная кладь", "без чемодана", "carry-on", "carry on", "hand luggage"]):
        inferred_baggage_format = "carry_on"
        inferred_tags.append("baggage:carry_on")
    elif any(_text_has_keyword(normalized_note, keyword) for keyword in ["рюкзак", "backpack"]):
        inferred_baggage_format = "carry_on"
        inferred_tags.append("baggage:carry_on")
    elif any(_text_has_keyword(normalized_note, keyword) for keyword in ["чемодан", "suitcase"]):
        inferred_baggage_format = "suitcase"
        inferred_tags.append("baggage:suitcase")

    return {
        "trip_type": inferred_trip_type,
        "trip_activities": normalize_trip_activities(inferred_activities),
        "accommodation_type": inferred_accommodation,
        "laundry_access": inferred_laundry,
        "packing_style": inferred_packing_style,
        "baggage_format": inferred_baggage_format,
        "extracted_tags": _clean_unique(inferred_tags),
    }


async def _extract_context_with_ai(profile: dict[str, Any], language: str = "ru") -> dict[str, Any] | None:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    note = _clean_string(profile.get("trip_note"))
    if not api_key or not note:
        return None

    prompt = (
        "Ты анализируешь описание поездки и превращаешь его в структуру для генерации чеклиста.\n"
        "Верни только JSON без markdown и пояснений.\n"
        "Разрешённые trip_type: city_break, beach_escape, business_trip, outdoor_adventure, winter_trip, romantic_getaway.\n"
        "Разрешённые trip_activities: city_break, beach_escape, business_trip, outdoor_adventure, winter_trip, romantic_getaway, swimming, hiking, workout, photo_content, traveling_with_children.\n"
        "Разрешённые accommodation_type: hotel, apartment, hostel, camping.\n"
        "Разрешённые laundry_access: none, limited, easy.\n"
        "Разрешённые packing_style: light, balanced, prepared.\n"
        "Разрешённые baggage_format: flexible, carry_on, suitcase, suitcase_plus_carry_on.\n"
        "Верни JSON формата "
        "{\"trip_type\": string|null, \"trip_activities\": string[], \"accommodation_type\": string|null, "
        "\"laundry_access\": string|null, \"packing_style\": string|null, \"baggage_format\": string|null, \"extracted_tags\": string[]}.\n"
        f"Язык пользователя: {language}\n"
        f"Описание поездки: {note}"
    )

    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.15,
            "maxOutputTokens": 300,
            "topP": 0.8,
            "thinkingConfig": {
                "thinkingBudget": 0,
            },
        },
    }

    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            url = os.getenv("GEMINI_BASE_URL", "").strip() or DEFAULT_GEMINI_URL
            response = await client.post(f"{url}?key={api_key}", json=payload)
            if response.status_code != 200:
                return None

            data = response.json()
            raw_text = (
                data.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
                .strip()
            )
            if not raw_text:
                return None

            text = raw_text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            start = text.find("{")
            end = text.rfind("}")
            if start == -1 or end == -1:
                return None

            parsed = json.loads(text[start:end + 1])
            if not isinstance(parsed, dict):
                return None

            return {
                "trip_type": parsed.get("trip_type"),
                "trip_activities": normalize_trip_activities(parsed.get("trip_activities")),
                "accommodation_type": parsed.get("accommodation_type"),
                "laundry_access": parsed.get("laundry_access"),
                "packing_style": parsed.get("packing_style"),
                "baggage_format": parsed.get("baggage_format"),
                "extracted_tags": _clean_unique(parsed.get("extracted_tags")),
            }
    except Exception as exc:
        print(f"[Packing logic] AI context extraction failed: {exc}")
        return None


async def build_trip_profile(raw_profile: dict[str, Any] | None, language: str = "ru") -> dict[str, Any]:
    profile = normalize_trip_profile(raw_profile)
    heuristic_context = _extract_context_with_heuristics(profile)
    ai_context = await _extract_context_with_ai(profile, language)

    inferred_context = {
        "trip_type": (ai_context or {}).get("trip_type") or heuristic_context.get("trip_type"),
        "trip_activities": normalize_trip_activities(
            [*(heuristic_context.get("trip_activities") or []), *((ai_context or {}).get("trip_activities") or [])]
        ),
        "accommodation_type": (ai_context or {}).get("accommodation_type") or heuristic_context.get("accommodation_type"),
        "laundry_access": (ai_context or {}).get("laundry_access") or heuristic_context.get("laundry_access"),
        "packing_style": (ai_context or {}).get("packing_style") or heuristic_context.get("packing_style"),
        "baggage_format": (ai_context or {}).get("baggage_format") or heuristic_context.get("baggage_format"),
        "extracted_tags": _clean_unique(
            [*(heuristic_context.get("extracted_tags") or []), *((ai_context or {}).get("extracted_tags") or [])]
        ),
    }
    if not any(
        [
            inferred_context.get("trip_type"),
            inferred_context.get("trip_activities"),
            inferred_context.get("accommodation_type"),
            inferred_context.get("laundry_access"),
            inferred_context.get("packing_style"),
            inferred_context.get("baggage_format"),
            inferred_context.get("extracted_tags"),
        ]
    ):
        return profile

    next_profile = dict(profile)
    if not profile.get("trip_activities"):
        next_profile["trip_activities"] = normalize_trip_activities(inferred_context.get("trip_activities"))
    else:
        next_profile["trip_activities"] = normalize_trip_activities(
            [*profile.get("trip_activities", []), *(inferred_context.get("trip_activities") or [])]
        )

    if profile.get("trip_type") == DEFAULT_TRIP_PROFILE["trip_type"] and inferred_context.get("trip_type"):
        next_profile["trip_type"] = inferred_context["trip_type"]

    if profile.get("accommodation_type") == DEFAULT_TRIP_PROFILE["accommodation_type"] and inferred_context.get("accommodation_type"):
        next_profile["accommodation_type"] = inferred_context["accommodation_type"]
        next_profile["accommodation_selected"] = True

    if profile.get("laundry_access") == DEFAULT_TRIP_PROFILE["laundry_access"] and inferred_context.get("laundry_access"):
        next_profile["laundry_access"] = inferred_context["laundry_access"]

    if profile.get("packing_style") == DEFAULT_TRIP_PROFILE["packing_style"] and inferred_context.get("packing_style"):
        next_profile["packing_style"] = inferred_context["packing_style"]

    if profile.get("baggage_format") == DEFAULT_TRIP_PROFILE["baggage_format"] and inferred_context.get("baggage_format"):
        next_profile["baggage_format"] = normalize_baggage_format(inferred_context["baggage_format"])

    next_profile["context_enhanced"] = True
    next_profile["extracted_tags"] = _clean_unique([*profile.get("extracted_tags", []), *(inferred_context.get("extracted_tags") or [])])
    return normalize_trip_profile(next_profile)


def _style_adjustment(packing_style: str) -> int:
    if packing_style == "light":
        return -1
    if packing_style == "prepared":
        return 1
    return 0


def estimate_rotation_quantity(
    days: int,
    laundry_access: str,
    packing_style: str,
    *,
    minimum: int = 1,
    maximum: int = 8,
    none_ratio: float = 1.0,
    limited_ratio: float = 0.65,
    easy_ratio: float = 0.45,
) -> int:
    safe_days = max(int(days or 1), 1)
    ratio = {
        "none": none_ratio,
        "limited": limited_ratio,
        "easy": easy_ratio,
    }.get(laundry_access, limited_ratio)
    quantity = math.ceil(safe_days * ratio) + _style_adjustment(packing_style)
    return max(minimum, min(maximum, quantity))


def prepare_trip_profile_for_segment(base_profile: dict[str, Any] | None, trip_type: Any) -> dict[str, Any]:
    return merge_trip_profiles(base_profile, {"trip_type": trip_type})


def build_packing_recommendations(
    *,
    language: str,
    trip_days: int,
    avg_temp: float | None,
    min_temp: float,
    max_temp: float,
    conditions: set[str],
    humidities: list[float],
    uv_indices: list[float],
    wind_speeds: list[float],
    country: str,
    transport: str,
    gender: str,
    traveling_with_pet: bool,
    has_allergies: bool,
    traveling_with_children: bool,
    trip_profile: dict[str, Any] | None,
) -> dict[str, Any]:
    profile = normalize_trip_profile(trip_profile)
    trip_type = profile["trip_type"]
    trip_activities = set(profile["trip_activities"])
    accommodation_type = profile["accommodation_type"]
    laundry_access = profile["laundry_access"]
    packing_style = profile["packing_style"]
    baggage_format = profile["baggage_format"]
    quantity_packing_style = packing_style
    if baggage_format == "carry_on" and packing_style != "prepared":
        quantity_packing_style = "light"
    elif baggage_format == "suitcase_plus_carry_on" and packing_style == "balanced":
        quantity_packing_style = "prepared"
    children_ages = list(profile.get("children_ages") or [])
    has_infants = any(age < 2 for age in children_ages)
    has_toddlers = any(2 <= age <= 4 for age in children_ages)
    has_young_children = any(5 <= age <= 11 for age in children_ages)
    has_older_children = any(12 <= age <= 17 for age in children_ages)
    scenarios = set(trip_activities)
    if trip_type != "city_break":
        scenarios.add(trip_type)
    if trip_type == "family_trip":
        scenarios.add("traveling_with_children")

    items: set[str] = set()
    quantities: dict[str, int] = {}

    def add_item(item_key: str, quantity: int = 1) -> None:
        label = get_item(item_key, language)
        items.add(label)
        quantities[label] = max(quantities.get(label, 0), max(int(quantity or 1), 1))

    add_item("passport")
    add_item("insurance")
    add_item("money")
    add_item("tickets")
    add_item("booking")
    add_item("copies_docs")

    add_item(
        "underwear",
        estimate_rotation_quantity(
            trip_days,
            laundry_access,
            quantity_packing_style,
            minimum=3,
            maximum=10,
            none_ratio=1.0,
            limited_ratio=0.72,
            easy_ratio=0.48,
        ),
    )
    add_item(
        "socks",
        estimate_rotation_quantity(
            trip_days,
            laundry_access,
            quantity_packing_style,
            minimum=3,
            maximum=10,
            none_ratio=1.0,
            limited_ratio=0.75,
            easy_ratio=0.5,
        ),
    )
    add_item("pajamas", 2 if trip_days >= 7 and quantity_packing_style == "prepared" else 1)

    add_item("toothbrush")
    add_item("deodorant")
    add_item("sanitizer")
    add_item("tissues")
    add_item("hairbrush")

    if accommodation_type in {"hostel", "camping", "apartment"} or packing_style == "prepared":
        add_item("soap")
        add_item("shampoo")
    else:
        add_item("soap")

    if accommodation_type in {"hostel", "camping", "apartment"}:
        add_item("towel")
    elif packing_style == "prepared":
        add_item("towel")

    add_item("phone")
    add_item("charger")
    add_item("headphones")

    if packing_style != "light" or "photo_content" in trip_activities or transport in {"plane", "bus"}:
        add_item("powerbank")

    add_item("painkillers")
    add_item("plasters")

    if has_allergies:
        add_item("antihistamine")

    if gender == "female":
        add_item("makeup")
        add_item("hygiene_fem")
        add_item("cotton_pads")
        if avg_temp and avg_temp >= 18:
            add_item("dress", 1)
    elif gender == "male":
        add_item("shaving_kit")

    if transport == "plane":
        if baggage_format in {"carry_on", "suitcase_plus_carry_on"}:
            add_item("liquids_bag")
    elif transport == "train":
        add_item("wipes")
    elif transport == "car":
        add_item("license")
        add_item("car_charger")
        add_item("sunglasses_driver")
    elif transport == "bus":
        add_item("wipes")

    if max_temp >= 24:
        add_item(
            "tshirt",
            estimate_rotation_quantity(
                trip_days,
                laundry_access,
            quantity_packing_style,
                minimum=3,
                maximum=8,
                none_ratio=0.75,
                limited_ratio=0.55,
                easy_ratio=0.38,
            ),
        )
        add_item(
            "shorts",
            estimate_rotation_quantity(
                trip_days,
                laundry_access,
            quantity_packing_style,
                minimum=1,
                maximum=5,
                none_ratio=0.34,
                limited_ratio=0.25,
                easy_ratio=0.18,
            ),
        )
        add_item("cap")
        add_item("shoes_light")
    elif min_temp >= 15:
        add_item(
            "tshirt",
            estimate_rotation_quantity(
                trip_days,
                laundry_access,
            quantity_packing_style,
                minimum=2,
                maximum=7,
                none_ratio=0.65,
                limited_ratio=0.48,
                easy_ratio=0.34,
            ),
        )
        add_item("long_sleeve", 1 if trip_days < 5 else 2)
        add_item("jeans", 1 if trip_days < 6 else 2)
        add_item("sneakers")
        add_item("jacket_light")
    elif min_temp >= 5:
        add_item("jeans", 2 if trip_days >= 5 else 1)
        add_item("sweater", 1 if trip_days < 6 else 2)
        add_item("hoodie", 1)
        add_item("jacket_light")
        add_item("sneakers")
    else:
        add_item("jeans", 2 if trip_days >= 5 else 1)
        add_item("sweater", 2 if trip_days >= 5 else 1)
        add_item("jacket_warm")
        add_item("hat")
        add_item("scarf")
        add_item("gloves")
        add_item("boots_winter")
        add_item("thermo", 1 if trip_days < 6 else 2)
        add_item("hand_cream")
        add_item("chapstick")

    if min_temp < 0:
        add_item("socks_warm", 2 if trip_days >= 5 else 1)

    if max_temp - min_temp >= 12:
        add_item("hoodie")
        add_item("long_sleeve")

    lower_conditions = {condition.lower() for condition in conditions}
    if any("дожд" in condition or "rain" in condition or "drizzle" in condition for condition in lower_conditions):
        add_item("raincoat")
        add_item("umbrella")
    if any(uv_index > 5 for uv_index in uv_indices) or max_temp >= 26:
        add_item("sunscreen_50")
        add_item("sunglasses")
    elif max_temp >= 20:
        add_item("sunscreen")
    if any(wind_speed > 28 for wind_speed in wind_speeds):
        add_item("windbreaker")
        add_item("scarf_buff")
        add_item("chapstick")
    if accommodation_type == "hostel":
        add_item("lock")
    elif accommodation_type == "camping":
        add_item("tent")
        add_item("sleeping_bag")
        add_item("sleeping_pad")
        add_item("camp_stove")
        add_item("camping_cookware")
        add_item("multitool")
        add_item("matches")
        add_item("headlamp")
        add_item("bug_net")
        add_item("trash_bags")
        add_item("rope")
        add_item("dry_bag")
        add_item("flashlight")
        add_item("first_aid_kit")

    if "city_break" in scenarios:
        add_item("comfy_shoes")
    if "beach_escape" in scenarios or "swimming" in scenarios:
        add_item("swimsuit")
        add_item("flipflops")
        add_item("beach_towel")
        add_item("sunscreen_50")
    if "business_trip" in scenarios:
        add_item("suit")
        add_item("shirts", 2 if trip_days >= 4 else 1)
        add_item("shoes_formal")
        add_item("laptop")
    if "outdoor_adventure" in scenarios or "hiking" in scenarios:
        add_item("trekking_shoes")
        add_item("first_aid_kit")
        add_item("water_bottle")
    if "winter_trip" in scenarios:
        add_item("thermo")
        add_item("fleece")
        add_item("hand_cream")
        add_item("chapstick")
        if min_temp <= -3:
            add_item("goggles")
    if traveling_with_children or "traveling_with_children" in scenarios:
        if has_infants:
            add_item("baby_food")
            add_item("diapers")
            add_item("baby_wipes")
            add_item("stroller")
            add_item("sippy_cup")
        if has_toddlers:
            add_item("baby_wipes")
            add_item("stroller")
            add_item("kids_toys")
            add_item("kids_clothes", 2 if trip_days >= 4 else 1)
            add_item("baby_sunscreen")
            add_item("sippy_cup")
        if has_young_children:
            add_item("kids_toys")
            add_item("kids_clothes", 2 if trip_days >= 4 else 1)
            add_item("child_meds")
            add_item("baby_sunscreen")
        if has_older_children:
            add_item("child_meds")
    if "romantic_getaway" in scenarios:
        add_item("fancy_outfit")
        add_item("shoes_formal")
        if gender == "female":
            add_item("heels")
            add_item("jewelry")

    if "workout" in scenarios:
        add_item("sportswear", 2 if trip_days >= 4 else 1)
        add_item("sneakers")
        add_item("water_bottle")
    if "photo_content" in scenarios:
        add_item("camera")
        add_item("usb_cable")

    if traveling_with_pet:
        add_item("vet_passport")
        add_item("pet_food")
        add_item("pet_bowl")
        add_item("leash")
        add_item("pet_pads")
        add_item("pet_toy")

    tropical_countries = {"TH", "VN", "KH", "LA", "MM", "ID", "MY", "PH", "IN", "LK", "MV", "BR", "CO", "MX", "CR", "CU", "KE", "TZ", "NG"}
    if country in tropical_countries:
        add_item("insect_spray")
        add_item("bite_cream")
        add_item("diarrhea_meds")
        add_item("sunscreen_50")

    conservative_countries = {"SA", "AE", "QA", "OM", "KW", "BH", "IR", "EG", "JO", "MA"}
    if country in conservative_countries:
        add_item("closed_clothing")
        add_item("head_covering")

    temple_countries = {"TH", "KH", "LA", "MM", "IN", "LK", "JP", "CN"}
    if country in temple_countries:
        add_item("closed_clothing")

    if packing_style == "light":
        for item_key in ["guidebook", "camera", "business_cards", "perfume"]:
            label = get_item(item_key, language)
            if label in items and label not in {get_item("camera", language), get_item("portable_charger", language)}:
                quantities[label] = max(1, quantities.get(label, 1))

    return {
        "items": items,
        "item_quantities": {item: max(1, quantity) for item, quantity in quantities.items() if item in items},
        "trip_profile": profile,
    }
