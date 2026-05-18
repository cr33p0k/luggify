from __future__ import annotations

import re
from typing import Any, Optional

from translations import get_item


PACKING_MODE_PATTERNS = {
    "carry_on": re.compile(r"(ручн\w*\s+клад|carry[-\s]?on|hand\s+luggage|при\s+себе|держать\s+с\s+собой|что\s+держать\s+при\s+себе)", re.IGNORECASE),
    "remove": re.compile(r"(что\s+убрать|что\s+лишн|убери\s+лишн|без\s+лишн|только\s+с\s+рюкзак|еду\s+с\s+рюкзак|поеду\s+с\s+рюкзак|сделай\s+.*легч|облегч|что\s+не\s+брать|для\s+коротк\w+\s+поездк|remove|drop|lighter|too\s+much|what\s+to\s+remove|backpack\s+only|carry[-\s]?on\s+only)", re.IGNORECASE),
    "departure_day": re.compile(r"(день\s+выезд|день\s+отъезд|перед\s+выезд|не\s+забыть|в\s+день\s+дорог[иу]|departure\s+day|before\s+leaving|don't\s+forget)", re.IGNORECASE),
    "add_more": re.compile(r"(что\s+(?:еще|ещё)\s+(?:взять|добавить|положить)|что\s+добавить|что\s+докинуть|что\s+я\s+забыл|what\s+else|what\s+to\s+add|did\s+i\s+forget|что\s+еще\s+нужно)", re.IGNORECASE),
}

PACKING_CONTEXT_RE = re.compile(
    r"(вещ|багаж|чемодан|рюкзак|ручн\w*\s+клад|собир|сбор|упаков|пак|packing|baggage|luggage|suitcase|backpack|bag|carry)",
    re.IGNORECASE,
)

CARRY_ON_KEYS = [
    "passport",
    "tickets",
    "booking",
    "insurance",
    "money",
    "phone",
    "charger",
    "powerbank_hand",
    "liquids_bag",
    "meds_personal",
    "neck_pillow",
    "earplugs",
]

DEPARTURE_DAY_KEYS = [
    "passport",
    "tickets",
    "booking",
    "insurance",
    "money",
    "phone",
    "charger",
    "powerbank",
    "meds_personal",
]

OPTIONAL_LIGHTEN_KEYWORDS = {
    "ru": [
        "путеводитель",
        "фотоаппарат",
        "камера",
        "парфюм",
        "духи",
        "органайзер",
        "органайзеры",
        "зонт",
        "полотенце",
        "сухой шампунь",
        "украшения",
        "каблук",
        "визитки",
    ],
    "en": [
        "guidebook",
        "camera",
        "perfume",
        "cologne",
        "packing cube",
        "umbrella",
        "towel",
        "dry shampoo",
        "jewelry",
        "heels",
        "business cards",
    ],
}

REQUEST_STYLE_PATTERNS = {
    "minimal": re.compile(r"(по\s+минимум|налегк|минимальн|компактн|без\s+лишн|travel\s+light|minimal|light\s+packing)", re.IGNORECASE),
    "prepared": re.compile(r"(с\s+запасом|на\s+всяк|перестрах|по\s+максимум|не\s+хочу\s+рисков|be\s+prepared|just\s+in\s+case)", re.IGNORECASE),
    "with_child": re.compile(r"(с\s+ребенк|с\s+ребёнк|для\s+ребенк|для\s+ребёнк|with\s+(?:a\s+)?child|with\s+kids|family)", re.IGNORECASE),
    "no_local_buying": re.compile(r"(не\s+хочу\s+покупать\s+на\s+месте|ничего\s+не\s+покупать\s+на\s+месте|не\s+рассчитыв|buy\s+nothing\s+there|don't\s+want\s+to\s+buy\s+on\s+site)", re.IGNORECASE),
    "comfort_first": re.compile(r"(комфорт|поудобн|удобств|comfort\s+first|stay\s+comfortable)", re.IGNORECASE),
}


def detect_packing_mode(question: str) -> Optional[str]:
    normalized = (question or "").strip()
    if not normalized:
        return None

    for mode in ("carry_on", "remove", "departure_day", "add_more"):
        if PACKING_MODE_PATTERNS[mode].search(normalized):
            return mode

    if PACKING_CONTEXT_RE.search(normalized) and re.search(r"(совет|recommend|advice|suggest)", normalized, re.IGNORECASE):
        return "add_more"
    return None


def _normalize(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower()).replace("ё", "е")


def _all_visible_items(trip_context: dict[str, Any]) -> list[dict[str, Any]]:
    baggage = trip_context.get("baggage") or {}
    sections = [baggage.get("shared") or {}, *(baggage.get("backpacks") or [])]
    items: list[dict[str, Any]] = []
    for section in sections:
        label = section.get("label") or "items"
        for item in section.get("items") or []:
            if item.get("is_removed"):
                continue
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            items.append(
                {
                    "name": name,
                    "section": label,
                    "quantity": item.get("quantity"),
                    "packed_quantity": item.get("packed_quantity"),
                    "is_packed": item.get("is_packed"),
                }
            )
    return items


def _item_exists(item_name: str, visible_items: list[dict[str, Any]]) -> bool:
    target = _normalize(item_name)
    return any(_normalize(item.get("name")) == target for item in visible_items)


def _weather_flags(trip_context: dict[str, Any]) -> dict[str, Any]:
    forecast = trip_context.get("daily_forecast") or []
    rain_days = []
    hot_days = []
    cold_days = []
    windy_days = []
    high_uv_days = []

    for day in forecast:
        condition = _normalize(day.get("condition"))
        date = day.get("date")
        temp_min = day.get("temp_min")
        temp_max = day.get("temp_max")
        uv_index = day.get("uv_index")
        wind_speed = day.get("wind_speed")
        if any(token in condition for token in ("дожд", "лив", "морос", "rain", "drizzle", "shower", "storm")):
            rain_days.append(date)
        if temp_max is not None and float(temp_max) >= 26:
            hot_days.append(date)
        if temp_min is not None and float(temp_min) <= 8:
            cold_days.append(date)
        if wind_speed is not None and float(wind_speed) >= 28:
            windy_days.append(date)
        if uv_index is not None and float(uv_index) >= 6:
            high_uv_days.append(date)

    return {
        "rain_days": [day for day in rain_days if day],
        "hot_days": [day for day in hot_days if day],
        "cold_days": [day for day in cold_days if day],
        "windy_days": [day for day in windy_days if day],
        "high_uv_days": [day for day in high_uv_days if day],
    }


def _join_days(days: list[str], language: str, limit: int = 2) -> str:
    if not days:
        return ""
    shown = ", ".join(days[:limit])
    if len(days) > limit:
        return f"{shown} +{len(days) - limit}"
    return shown


def _format_reason_with_days(prefix_ru: str, prefix_en: str, days: list[str], language: str) -> str:
    days_text = _join_days(days, language)
    if not days_text:
        return prefix_ru if language == "ru" else prefix_en
    return f"{prefix_ru}: {days_text}" if language == "ru" else f"{prefix_en}: {days_text}"


def _soften_reason(text_ru: str, text_en: str, language: str) -> str:
    return text_ru if language == "ru" else text_en


def _constraint_flags(trip_context: dict[str, Any]) -> dict[str, Any]:
    trip = trip_context.get("trip") or {}
    profile = trip_context.get("trip_profile") or {}
    transports = [_normalize(item) for item in (trip.get("transports") or [])]
    duration_days = int(trip.get("duration_days") or 0)
    baggage_format = profile.get("baggage_format") or "flexible"
    packing_style = profile.get("packing_style") or "balanced"
    activities = set(profile.get("trip_activities") or [])
    trip_type = profile.get("trip_type") or trip.get("trip_type") or "city_break"
    return {
        "duration_days": duration_days,
        "is_short_trip": bool(duration_days and duration_days <= 3),
        "is_long_trip": bool(duration_days and duration_days >= 6),
        "baggage_format": baggage_format,
        "carry_on_only": baggage_format == "carry_on",
        "has_flight": any(token in {"plane", "flight", "airplane", "самолет", "самолёт"} for token in transports),
        "packing_style": packing_style,
        "activities": activities,
        "trip_type": trip_type,
    }


def _extract_request_preferences(question: str) -> dict[str, bool]:
    normalized = (question or "").strip()
    return {
        key: bool(pattern.search(normalized))
        for key, pattern in REQUEST_STYLE_PATTERNS.items()
    }


def _effective_preferences(trip_context: dict[str, Any], question: str) -> dict[str, Any]:
    constraints = _constraint_flags(trip_context)
    request = _extract_request_preferences(question)
    packing_style = constraints["packing_style"]
    if request["minimal"]:
        packing_style = "light"
    elif request["prepared"]:
        packing_style = "prepared"
    elif request["comfort_first"] and packing_style == "light":
        packing_style = "balanced"
    return {
        **constraints,
        "packing_style": packing_style,
        "request_preferences": request,
        "comfort_first": request["comfort_first"],
        "minimal_request": request["minimal"],
        "prepared_request": request["prepared"],
        "with_child_hint": request["with_child"] or "traveling_with_children" in constraints["activities"] or constraints["trip_type"] == "family_trip",
        "avoid_local_buying": request["no_local_buying"] or packing_style == "prepared",
    }


def _make_recommendation(
    *,
    item: str,
    priority: str,
    reason: str,
    reason_tags: list[str],
    suggested_action: str,
    target_section: Optional[str] = None,
) -> dict[str, Any]:
    return {
        "item": item,
        "priority": priority,
        "reason": reason,
        "reason_tags": reason_tags,
        "suggested_action": suggested_action,
        "target_section": target_section,
    }


def _add_missing(
    recommendations: list[dict[str, Any]],
    visible_items: list[dict[str, Any]],
    *,
    item_key: str,
    language: str,
    priority: str,
    reason: str,
    reason_tags: list[str],
    suggested_action: str = "add",
    target_section: Optional[str] = None,
) -> None:
    item = get_item(item_key, language)
    if _item_exists(item, visible_items):
        return
    recommendations.append(
        _make_recommendation(
            item=item,
            priority=priority,
            reason=reason,
            reason_tags=reason_tags,
            suggested_action=suggested_action,
            target_section=target_section,
        )
    )


def _build_add_more_recommendations(trip_context: dict[str, Any], language: str, question: str) -> list[dict[str, Any]]:
    visible_items = _all_visible_items(trip_context)
    weather = _weather_flags(trip_context)
    constraints = _effective_preferences(trip_context, question)
    recommendations: list[dict[str, Any]] = []

    if weather["rain_days"]:
        _add_missing(
            recommendations,
            visible_items,
            item_key="raincoat",
            language=language,
            priority="must",
            reason=_format_reason_with_days("Можно взять на случай дождя", "Could be worth packing for rainy weather", weather["rain_days"], language),
            reason_tags=["weather", "rain", "daily_weather"],
        )
        _add_missing(
            recommendations,
            visible_items,
            item_key="umbrella",
            language=language,
            priority="optional" if constraints["carry_on_only"] or constraints["packing_style"] == "light" else "nice",
            reason=_soften_reason(
                "Можно взять для городских прогулок в дождливые дни, если останется место",
                "Could be useful for city walks on rainy days if you still have room",
                language,
            ),
            reason_tags=["weather", "rain", "city", "baggage_format"],
        )

    if weather["hot_days"] or weather["high_uv_days"]:
        days = weather["high_uv_days"] or weather["hot_days"]
        _add_missing(
            recommendations,
            visible_items,
            item_key="sunscreen_50",
            language=language,
            priority="must",
            reason=_format_reason_with_days("Стоит взять из-за высокого UV или жары", "Worth packing because of high UV or heat", days, language),
            reason_tags=["weather", "uv", "heat", "daily_weather"],
        )
        _add_missing(
            recommendations,
            visible_items,
            item_key="sunglasses",
            language=language,
            priority="must" if constraints["comfort_first"] else "nice",
            reason=_format_reason_with_days("Могут пригодиться из-за яркого солнца", "Could come in handy because of bright sun", days, language),
            reason_tags=["weather", "uv", "daily_weather"],
        )

    if weather["windy_days"]:
        _add_missing(
            recommendations,
            visible_items,
            item_key="windbreaker",
            language=language,
            priority="must" if constraints["avoid_local_buying"] else "nice",
            reason=_format_reason_with_days("Можно взять, если хочешь подготовиться к ветру", "Could be useful if you want to be ready for windy weather", weather["windy_days"], language),
            reason_tags=["weather", "wind", "daily_weather"],
        )

    if weather["cold_days"]:
        _add_missing(
            recommendations,
            visible_items,
            item_key="hoodie",
            language=language,
            priority="must" if constraints["comfort_first"] else "nice",
            reason=_format_reason_with_days("Может пригодиться на прохладное утро или вечер", "Could help on cooler mornings or evenings", weather["cold_days"], language),
            reason_tags=["weather", "temperature_drop", "daily_weather"],
        )

    activities = constraints["activities"]
    if {"city_break", "photo_content"} & activities or constraints["trip_type"] == "city_break":
        _add_missing(
            recommendations,
            visible_items,
            item_key="portable_charger",
            language=language,
            priority="must" if constraints["carry_on_only"] or constraints["avoid_local_buying"] else "nice",
            reason=_soften_reason(
                "Может быть полезна, если будут длинные прогулки, навигация и билеты в телефоне",
                "Could be useful for long walks, navigation, and phone-based tickets",
                language,
            ),
            reason_tags=["activity", "city", "electronics", "departure_day"],
            target_section="ручная кладь" if language == "ru" else "carry-on" if constraints["carry_on_only"] else None,
        )
        _add_missing(
            recommendations,
            visible_items,
            item_key="comfy_shoes",
            language=language,
            priority="must",
            reason=_soften_reason("Обычно это самая удобная база для городских прогулок", "Usually the most reliable base for city walking", language),
            reason_tags=["activity", "walking"],
        )

    if {"hiking", "outdoor_adventure"} & activities or constraints["trip_type"] == "outdoor_adventure":
        _add_missing(
            recommendations,
            visible_items,
            item_key="first_aid_kit",
            language=language,
            priority="must",
            reason=_soften_reason("Для активного маршрута аптечка обычно оправдана", "For active routes, a first-aid kit is usually worth it", language),
            reason_tags=["activity", "safety"],
        )
        _add_missing(
            recommendations,
            visible_items,
            item_key="water_bottle",
            language=language,
            priority="must",
            reason=_soften_reason("На активные дни обычно удобно держать воду под рукой", "On active days it usually helps to keep water close", language),
            reason_tags=["activity", "hydration"],
        )

    if constraints["with_child_hint"]:
        _add_missing(
            recommendations,
            visible_items,
            item_key="baby_wipes",
            language=language,
            priority="must" if constraints["avoid_local_buying"] else "nice",
            reason=_soften_reason(
                "Если поездка с ребёнком, такие вещи обычно лучше не оставлять на последний момент",
                "If the trip includes a child, this is usually worth planning ahead",
                language,
            ),
            reason_tags=["participants", "family"],
        )
        _add_missing(
            recommendations,
            visible_items,
            item_key="kids_clothes",
            language=language,
            priority="nice",
            reason=_soften_reason(
                "Для поездки с ребёнком бывает полезно держать хотя бы один запасной комплект",
                "For travel with a child, it often helps to keep at least one extra outfit",
                language,
            ),
            reason_tags=["participants", "family"],
        )

    if constraints["is_long_trip"]:
        _add_missing(
            recommendations,
            visible_items,
            item_key="laundry_bag",
            language=language,
            priority="nice",
            reason=_soften_reason("На более длинной поездке бывает удобно отделять грязное бельё", "On a longer trip it is often convenient to separate laundry", language),
            reason_tags=["duration", "trip_length"],
        )

    if constraints["carry_on_only"]:
        _add_missing(
            recommendations,
            visible_items,
            item_key="liquids_bag",
            language=language,
            priority="must",
            reason=_soften_reason(
                "Если летишь только с ручной кладью, это обычно удобно подготовить заранее",
                "If you are flying carry-on only, this is usually worth preparing in advance",
                language,
            ),
            reason_tags=["baggage_format", "carry_on", "transport"],
            target_section="ручная кладь" if language == "ru" else "carry-on",
        )

    if constraints["is_short_trip"] and not constraints["carry_on_only"]:
        _add_missing(
            recommendations,
            visible_items,
            item_key="city_backpack",
            language=language,
            priority="optional",
            reason=_soften_reason(
                "Для короткой поездки можно держать дневные вещи отдельно, чтобы не раскрывать чемодан каждый раз",
                "On a short trip, you may want to keep daytime essentials separate instead of reopening the suitcase each time",
                language,
            ),
            reason_tags=["duration", "baggage_format"],
        )

    return recommendations[:8]


def _build_carry_on_recommendations(trip_context: dict[str, Any], language: str, question: str) -> list[dict[str, Any]]:
    visible_items = _all_visible_items(trip_context)
    constraints = _effective_preferences(trip_context, question)
    recommendations: list[dict[str, Any]] = []
    target = "ручная кладь" if language == "ru" else "carry-on"

    for key in CARRY_ON_KEYS:
        item = get_item(key, language)
        exists = _item_exists(item, visible_items)
        action = "move_to_carry_on" if exists else "add"
        priority = "must" if key in {"passport", "tickets", "money", "phone", "charger"} or constraints["avoid_local_buying"] else "nice"
        if key in {"passport", "tickets", "booking", "insurance", "money"}:
            reason = "Такие вещи обычно лучше держать при себе, а не в сдаваемом багаже" if language == "ru" else "These are usually better kept with you, not in checked baggage"
            tags = ["baggage_format", "documents"]
        elif key in {"powerbank_hand", "liquids_bag"}:
            reason = "Для перелёта это обычно удобнее и безопаснее держать в ручной клади" if language == "ru" else "For flights, this is usually easier and safer to keep in carry-on"
            tags = ["transport", "carry_on", "baggage_format"]
        else:
            reason = "Может пригодиться под рукой в дороге" if language == "ru" else "Could be useful to keep within reach while traveling"
            tags = ["departure_day", "carry_on"]
        recommendations.append(
            _make_recommendation(
                item=item,
                priority=priority,
                reason=reason,
                reason_tags=tags,
                suggested_action=action,
                target_section=target,
            )
        )

    if constraints["is_short_trip"]:
        _add_missing(
            recommendations,
            visible_items,
            item_key="city_backpack",
            language=language,
            priority="optional",
            reason=(
                "Для короткой поездки можно собрать компактный набор на первый день"
                if language == "ru"
                else "For a short trip, you may want one compact first-day set in carry-on"
            ),
            reason_tags=["duration", "carry_on"],
            suggested_action="add",
            target_section=target,
        )

    return recommendations[:12]


def _build_remove_recommendations(trip_context: dict[str, Any], language: str, question: str) -> list[dict[str, Any]]:
    visible_items = _all_visible_items(trip_context)
    constraints = _effective_preferences(trip_context, question)
    baggage_format = constraints["baggage_format"]
    packing_style = constraints["packing_style"]
    activities = constraints["activities"]
    optional_keywords = OPTIONAL_LIGHTEN_KEYWORDS.get(language, OPTIONAL_LIGHTEN_KEYWORDS["ru"])
    recommendations: list[dict[str, Any]] = []

    for item in visible_items:
        name = str(item.get("name") or "")
        normalized = _normalize(name)
        if not any(keyword in normalized for keyword in optional_keywords):
            continue
        if item.get("is_packed"):
            priority = "optional"
        else:
            priority = "nice"
        reason_bits = []
        tags = []
        if baggage_format == "carry_on":
            reason_bits.append("только ручная кладь" if language == "ru" else "carry-on only")
            tags.append("baggage_format")
        if constraints["is_short_trip"]:
            reason_bits.append("короткая поездка" if language == "ru" else "short trip")
            tags.append("duration")
        if packing_style == "light":
            reason_bits.append("режим налегке" if language == "ru" else "light packing mode")
            tags.append("packing_style")
        if constraints["avoid_local_buying"]:
            reason_bits.append("но только если не хочешь брать запас" if language == "ru" else "but mostly if you do not need backup options")
            tags.append("preference")
        if "business_trip" not in activities and any(keyword in normalized for keyword in ("визит", "business", "парфюм", "духи")):
            reason_bits.append("не обязательно для этого сценария" if language == "ru" else "not necessary for this trip style")
            tags.append("activity")
        reason = (
            f"Можно не брать, если хочешь облегчить список: {' + '.join(reason_bits) or 'это не самая критичная вещь для всей поездки'}"
            if language == "ru"
            else f"You could skip it if you want a lighter list: {' + '.join(reason_bits) or 'it does not look essential for the whole trip'}"
        )
        recommendations.append(
            _make_recommendation(
                item=name,
                priority=priority,
                reason=reason,
                reason_tags=tags or ["packing_style"],
                suggested_action="remove",
            )
        )

    if constraints["is_short_trip"]:
        short_trip_candidates = ["towel", "packing_cubes", "guidebook"]
        for key in short_trip_candidates:
            item_name = get_item(key, language)
            if not _item_exists(item_name, visible_items):
                continue
            if any(_normalize(existing["item"]) == _normalize(item_name) for existing in recommendations):
                continue
            recommendations.append(
                _make_recommendation(
                    item=item_name,
                    priority="optional",
                    reason=(
                        "Для короткой поездки это можно пропустить, если хочешь сделать список компактнее"
                        if language == "ru"
                        else "On a short trip, you can skip this to keep the list compact"
                    ),
                    reason_tags=["duration", "trip_length"],
                    suggested_action="remove",
                )
            )

    if not recommendations:
        fallback = get_item("guidebook", language)
        recommendations.append(
            _make_recommendation(
                item=fallback,
                priority="optional",
                reason=(
                    "Если захочешь облегчить список, логично сначала отказаться от того, что легко заменить телефоном или купить на месте"
                    if language == "ru"
                    else "If you want to lighten the list, start with things your phone can replace or you can buy locally"
                ),
                reason_tags=["packing_style"],
                suggested_action="remove",
            )
        )

    return recommendations[:8]


def _build_departure_day_recommendations(trip_context: dict[str, Any], language: str, question: str) -> list[dict[str, Any]]:
    visible_items = _all_visible_items(trip_context)
    weather = _weather_flags(trip_context)
    constraints = _effective_preferences(trip_context, question)
    recommendations: list[dict[str, Any]] = []

    for key in DEPARTURE_DAY_KEYS:
        item = get_item(key, language)
        action = "keep" if _item_exists(item, visible_items) else "add"
        if key in {"passport", "tickets", "booking", "insurance", "money"}:
            priority = "must"
            reason = "Лучше отдельно проверить перед выходом, чтобы не искать в последний момент" if language == "ru" else "Worth checking separately before leaving so you are not searching at the last moment"
            tags = ["departure_day", "documents"]
        elif key in {"phone", "charger", "powerbank"}:
            priority = "must" if key != "powerbank" else "nice"
            reason = "Обычно это полезно для связи, навигации и документов в телефоне" if language == "ru" else "Usually useful for communication, navigation, and phone-based documents"
            tags = ["departure_day", "electronics"]
        else:
            priority = "nice"
            reason = "Можно держать под рукой в день дороги" if language == "ru" else "Could be worth keeping handy on travel day"
            tags = ["departure_day"]
        recommendations.append(
            _make_recommendation(
                item=item,
                priority=priority,
                reason=reason,
                reason_tags=tags,
                suggested_action=action,
                target_section="ручная кладь" if language == "ru" else "carry-on",
            )
        )

    if weather["rain_days"]:
        _add_missing(
            recommendations,
            visible_items,
            item_key="raincoat",
            language=language,
            priority="nice",
            reason=_format_reason_with_days("Если дождь попадёт на день дороги, лучше не убирать глубоко", "If rain overlaps with travel day, it may be better not to bury it deep", weather["rain_days"], language),
            reason_tags=["weather", "departure_day", "daily_weather"],
            suggested_action="add",
            target_section="верх багажа" if language == "ru" else "top of bag",
        )

    if constraints["carry_on_only"]:
        _add_missing(
            recommendations,
            visible_items,
            item_key="liquids_bag",
            language=language,
            priority="must",
            reason=_soften_reason(
                "Если летишь с ручной кладью, это удобно отдельно проверить до выхода",
                "If you are flying with carry-on only, this is convenient to check separately before leaving",
                language,
            ),
            reason_tags=["departure_day", "baggage_format", "carry_on"],
            suggested_action="add",
            target_section="ручная кладь" if language == "ru" else "carry-on",
        )

    return recommendations[:12]


def build_packing_advice(question: str, trip_context: dict[str, Any], language: str = "ru") -> Optional[dict[str, Any]]:
    mode = detect_packing_mode(question)
    if not mode:
        return None

    if mode == "carry_on":
        recommendations = _build_carry_on_recommendations(trip_context, language, question)
        title = "Что можно держать в ручной клади" if language == "ru" else "What you may want in carry-on"
    elif mode == "remove":
        recommendations = _build_remove_recommendations(trip_context, language, question)
        title = "Что можно не брать, если хочешь облегчить список" if language == "ru" else "What you could skip for a lighter list"
    elif mode == "departure_day":
        recommendations = _build_departure_day_recommendations(trip_context, language, question)
        title = "Что стоит держать в фокусе в день выезда" if language == "ru" else "What to keep in mind on departure day"
    else:
        recommendations = _build_add_more_recommendations(trip_context, language, question)
        title = "Что ещё можно добавить под этот сценарий" if language == "ru" else "What else you could add for this trip"

    answer = format_packing_advice_answer(title, recommendations, language)
    return {
        "mode": mode,
        "answer": answer,
        "recommendations": recommendations,
    }


def format_packing_advice_answer(title: str, recommendations: list[dict[str, Any]], language: str = "ru") -> str:
    if not recommendations:
        return (
            f"{title}\nПохоже, базовый список уже выглядит достаточно полным. Без новых ограничений я бы ничего не навязывал."
            if language == "ru"
            else f"{title}\nThe current list already looks fairly complete. I would not push any additions without new constraints."
        )

    priority_label = {
        "must": "в первую очередь" if language == "ru" else "highest priority",
        "nice": "можно взять" if language == "ru" else "worth considering",
        "optional": "по желанию" if language == "ru" else "optional",
    }
    lines = [
        title,
        (
            "Это не обязательные указания, а спокойные рекомендации под формат поездки, погоду и багаж."
            if language == "ru"
            else "These are suggestions, not strict rules, based on your trip format, weather, and baggage."
        ),
    ]
    ordered_priorities = ["must", "nice", "optional"]
    grouped = {
        priority: [item for item in recommendations[:8] if item.get("priority") == priority]
        for priority in ordered_priorities
    }
    index = 1
    for bucket in ordered_priorities:
        items = grouped.get(bucket) or []
        if not items:
            continue
        lines.append(priority_label[bucket].capitalize() if language == "ru" else priority_label[bucket].capitalize())
        for recommendation in items:
            target = recommendation.get("target_section")
            target_suffix = f" -> {target}" if target else ""
            lines.append(
                f"{index}. {recommendation['item']}{target_suffix} — {recommendation['reason']}"
            )
            index += 1
    return "\n".join(lines)
