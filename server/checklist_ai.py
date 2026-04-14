import json
import os
import re
from typing import Any, Optional

import httpx

import crud


GEMINI_MODEL = "gemini-2.0-flash"
DEFAULT_GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

ACTION_PATTERNS = {
    "add": [
        r"добав\w*", r"закин\w*", r"впис\w*", r"внес\w*", r"полож\w*", r"докин\w*", r"включ\w*",
        r"add", r"append", r"include", r"put",
    ],
    "remove": [
        r"удал\w*", r"убер\w*", r"вычеркн\w*", r"исключ\w*", r"выкин\w*", r"сотр\w*",
        r"не\s+нуж\w*", r"не\s+понадоб\w*",
        r"remove", r"delete", r"drop", r"erase",
    ],
    "check": [
        r"отмет\w*", r"помет\w*", r"постав\w*\s+галочк\w*", r"отмеча\w*", r"возьм\w*", r"бер\w*",
        r"готов\w*", r"упак\w*", r"собра\w*", r"взял\w*",
        r"check", r"mark", r"tick", r"pack",
    ],
    "uncheck": [
        r"сним\w*\s+отметк\w*", r"убер\w*\s+галочк\w*", r"не\s+бер\w*", r"не\s+отмеча\w*", r"разотмет\w*",
        r"не\s+клади\w*", r"не\s+пак\w*", r"не\s+нуж\w*\s+брать",
        r"uncheck", r"unmark", r"untick",
    ],
}

MOVE_PATTERNS = [
    r"перелож\w*", r"перемест\w*", r"перенес\w*", r"перекин\w*",
    r"move", r"transfer", r"relocate",
]

SHARED_SECTION_ALIASES = [
    "общие вещи", "общий список", "общее", "общак", "shared", "common items", "shared items",
    "обратно", "назад", "back", "shared list",
]

SELF_SECTION_ALIASES = [
    "мой", "моя", "мое", "мои", "мой рюкзак", "моя сумка", "мне", "себе", "у меня", "я",
    "my", "mine", "me", "my backpack", "my bag",
]

CONVERSATIONAL_PREFIX_RE = re.compile(
    r"^(?:ну\s+|а\s+|и\s+|слушай\s+|пожалуйста\s+|плиз\s+|please\s+|"
    r"можешь\s+|сможешь\s+|можно\s+|нужно\s+|надо(?:\s+бы)?\s+|"
    r"давай\s+|хочу\s+|помоги\s+|поможешь\s+|будь\s+добр\s+|"
    r"can\s+you\s+|could\s+you\s+)+",
    re.IGNORECASE,
)

MATCH_STOPWORDS = {
    "для", "в", "во", "на", "из", "с", "со", "к", "по", "под", "над", "от", "до",
    "the", "a", "an", "my", "your", "и", "или", "но", "же", "ну", "это",
}

ITEM_SYNONYMS = {
    "powerbank": "power bank",
    "power-bank": "power bank",
    "пауэрбанк": "power bank",
    "павербанк": "power bank",
    "павер": "power bank",
    "пауэр": "power bank",
    "кроссы": "кроссовки",
    "кросс": "кроссовки",
    "кеды": "кроссовки",
    "загран": "паспорт",
    "загранник": "паспорт",
    "загранпаспорт": "паспорт",
    "бронька": "бронь отеля",
    "бронь": "бронь отеля",
    "страховка": "медицинская страховка",
    "билеты на самолет": "билеты",
    "авиабилеты": "билеты",
    "телефонная зарядка": "зарядка",
    "зарядник": "зарядка",
    "зарядку": "зарядка",
    "зарядное": "зарядка",
    "маска для сна": "беруши/маска для сна",
    "беруши": "беруши/маска для сна",
    "подушка": "подушка для шеи",
}

ITEM_SPLIT_RE = re.compile(r"\s*(?:,|;|\n|\band\b|\bи\b|\bещё\b|\bещё\b)\s*", re.IGNORECASE)

QUANTITY_WORDS = {
    "ноль": 0,
    "один": 1,
    "одна": 1,
    "одно": 1,
    "одну": 1,
    "одинa": 1,
    "раз": 1,
    "два": 2,
    "две": 2,
    "пару": 2,
    "три": 3,
    "четыре": 4,
    "пять": 5,
    "шесть": 6,
    "семь": 7,
    "восемь": 8,
    "девять": 9,
    "десять": 10,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
}

QUANTITY_FILLER_WORDS = {
    "штук",
    "штуки",
    "штука",
    "шт",
    "x",
    "х",
    "pieces",
    "piece",
}

REMOVE_ALL_WORDS = {
    "все",
    "всё",
    "all",
    "целиком",
    "полностью",
}

EVERYTHING_ALIASES = {
    "все", "всё", "все вещи", "всё вещи", "все из этого", "все из списка", "все из чеклиста",
    "everything", "all", "all items", "entire list",
}

ITEM_GROUPS = {
    "documents": {
        "aliases": ["документы", "доки", "бумаги", "docs", "documents"],
        "keywords": ["паспорт", "билет", "бронь", "страхов", "виза", "visa", "карта", "деньги"],
    },
    "warm_clothes": {
        "aliases": ["тёплое", "теплое", "тёплые вещи", "теплые вещи", "тёплую одежду", "теплую одежду", "warm clothes", "warm stuff"],
        "keywords": ["свитер", "кофт", "худи", "толстов", "джемпер", "куртк", "ветровк"],
    },
    "rain": {
        "aliases": ["для дождя", "дождевое", "дождь", "rain gear", "rain stuff", "непромокаемое"],
        "keywords": ["дождевик", "зонт", "водонепрониц"],
    },
    "shoes": {
        "aliases": ["обувь", "shoes", "footwear"],
        "keywords": ["кроссов", "ботин", "обув", "сандал", "кед", "тапк", "шлеп"],
    },
    "electronics": {
        "aliases": ["электроника", "гаджеты", "техника", "electronics", "gadgets", "tech"],
        "keywords": ["power bank", "заряд", "телефон", "ноут", "кабель", "адаптер", "науш", "камера"],
    },
    "sleep": {
        "aliases": ["для сна", "сон", "sleep"],
        "keywords": ["беруш", "маск", "подушк"],
    },
    "hygiene": {
        "aliases": ["гигиена", "туалетка", "toiletries", "cosmetics", "косметика"],
        "keywords": ["жидкост", "шампун", "щетк", "паста", "крем", "укладк", "дезодорант"],
    },
    "medicine": {
        "aliases": ["аптечка", "лекарства", "медицина", "medicine", "meds"],
        "keywords": ["аптеч", "таблет", "лекар"],
    },
    "hand_luggage": {
        "aliases": ["ручная кладь", "carry on", "carry-on"],
        "keywords": ["power bank", "жидкост", "маск", "подушк"],
    },
}

INFO_PATTERNS = {
    "checked": [
        r"что\s+(?:уже\s+)?(?:отмечен\w*|собран\w*|упакован\w*|взял\w*)",
        r"какие\s+вещи\s+(?:уже\s+)?(?:отмечен\w*|собран\w*|упакован\w*)",
        r"show\s+(?:packed|checked)\s+items",
        r"what(?:'s|\s+is)?\s+packed",
    ],
    "remaining": [
        r"что\s+(?:еще|ещё)?\s*остал\w*",
        r"что\s+я\s+забыл\w*",
        r"что\s+(?:еще|ещё)?\s*не\s+(?:собран\w*|отмечен\w*|упакован\w*)",
        r"what(?:'s|\s+is)?\s+left",
        r"what\s+did\s+i\s+forget",
    ],
    "removed": [
        r"что\s+(?:удален\w*|убран\w*|скрыт\w*)",
        r"какие\s+вещи\s+(?:удален\w*|убран\w*|скрыт\w*)",
        r"what(?:'s|\s+is)?\s+removed",
        r"show\s+removed\s+items",
    ],
    "items": [
        r"что\s+в\s+(?:моем|моём|моей|моем|рюкзаке|сумке|общих\s+вещах|общем\s+списке)",
        r"что\s+у\s+.+?\s+в\s+(?:рюкзаке|сумке)",
        r"что\s+лежит\s+в",
        r"покажи\s+(?:мне\s+)?(?:рюкзак|список|вещи)",
        r"show\s+(?:my\s+)?(?:backpack|bag|items|list)",
    ],
}

BAGGAGE_KIND_ALIASES = {
    "backpack": ["рюкзак", "рюкзаке", "рюкзаку", "backpack", "bag"],
    "suitcase": ["чемодан", "чемодане", "чемодану", "suitcase", "luggage"],
    "carry_on": ["ручная кладь", "ручной клади", "ручную кладь", "carry on", "carry-on"],
    "bag": ["сумка", "сумке", "сумку", "bag"],
    "custom": ["багаж", "baggage", "luggage"],
}

BAGGAGE_KIND_DEFAULT_NAMES = {
    "backpack": "Рюкзак",
    "suitcase": "Чемодан",
    "carry_on": "Ручная кладь",
    "bag": "Сумка",
    "custom": "Багаж",
}

CREATE_BAGGAGE_PATTERNS = [
    re.compile(r"^(?:созда\w*|добав\w*)\s+багаж\s+(.+)$", re.IGNORECASE),
]


def _normalize_item(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def _strip_conversational_prefixes(value: str) -> str:
    return CONVERSATIONAL_PREFIX_RE.sub("", (value or "").strip()).strip(" ,.!?:;-")


def _normalize_for_matching(value: str) -> str:
    cleaned = _normalize_item(value).replace("ё", "е")
    cleaned = re.sub(r"[\(\)\[\]\{\}\.,!?:;\"'«»/\\+\-_]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    for source, target in ITEM_SYNONYMS.items():
        cleaned = re.sub(rf"\b{re.escape(source)}\b", target, cleaned, flags=re.IGNORECASE)

    return re.sub(r"\s+", " ", cleaned).strip()


def _token_stem(token: str) -> str:
    token = _normalize_for_matching(token)
    if not token:
        return ""

    if re.fullmatch(r"[a-z0-9]+", token):
        if token.endswith("ies") and len(token) > 4:
            return token[:-3] + "y"
        if token.endswith("es") and len(token) > 4:
            return token[:-2]
        if token.endswith("s") and len(token) > 4:
            return token[:-1]
        return token

    trimmed = re.sub(
        r"(иями|ями|ами|ого|ему|ому|ыми|ими|иях|ях|ах|ов|ев|ей|ом|ем|ам|ям|"
        r"ый|ий|ой|ая|яя|ое|ее|ые|ие|ую|юю|ки|ка|ку|ке|ой|ою|ею|"
        r"ы|и|а|я|у|ю|е|о|ь)$",
        "",
        token,
    )
    return trimmed or token


def _build_match_signature(value: str) -> dict[str, Any]:
    normalized = _normalize_for_matching(value)
    tokens = [token for token in re.findall(r"[a-zа-я0-9]+", normalized) if token not in MATCH_STOPWORDS]
    roots = {_token_stem(token) for token in tokens if _token_stem(token)}
    prefixes = {root[:4] for root in roots if len(root) >= 4}
    compact = "".join(tokens)
    return {
        "normalized": normalized,
        "tokens": tokens,
        "roots": roots,
        "prefixes": prefixes,
        "compact": compact,
    }


def _dedupe_preserve(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        normalized = _normalize_item(item)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(item.strip())
    return result


def _merge_action_sets(*action_payloads: dict[str, Any]) -> dict[str, Any]:
    recognized = any(payload.get("recognized_action_request") for payload in action_payloads if payload)
    merged: dict[str, dict[str, Any]] = {}

    for payload in action_payloads:
        if not payload:
            continue
        for action in payload.get("actions", []):
            action_type = action.get("type")
            items = _dedupe_preserve(action.get("items") or [])
            if not action_type or not items:
                continue

            key = (
                action_type,
                action.get("source_hint"),
                action.get("target_hint"),
                action.get("section_hint"),
            )
            bucket = merged.setdefault(
                key,
                {
                    "type": action_type,
                    "items": [],
                },
            )
            if action.get("source_hint") is not None:
                bucket["source_hint"] = action.get("source_hint")
            if action.get("target_hint") is not None:
                bucket["target_hint"] = action.get("target_hint")
            if action.get("section_hint") is not None:
                bucket["section_hint"] = action.get("section_hint")
            bucket["items"].extend(items)

    return {
        "recognized_action_request": recognized,
        "actions": [
            {
                **{k: v for k, v in action.items() if k != "items"},
                "items": _dedupe_preserve(action["items"]),
            }
            for action in merged.values()
        ],
    }


def _split_items(raw: str) -> list[str]:
    cleaned = re.sub(
        r"\b(?:пожалуйста|please|pls|плиз|в чеклист|в список|из чеклиста|из списка|"
        r"сейчас|вообще|просто|мне|нам|как собранное|как собранный|как взятое|как упакованное)\b",
        "",
        _strip_conversational_prefixes(raw or ""),
        flags=re.IGNORECASE,
    )
    return _dedupe_preserve([
        re.sub(r"^(?:с|из|для|from)\s+", "", part.strip(" .!?\"'()[]"), flags=re.IGNORECASE)
        for part in ITEM_SPLIT_RE.split(cleaned)
        if re.sub(r"^(?:с|из|для|from)\s+", "", part.strip(" .!?\"'()[]"), flags=re.IGNORECASE)
    ])


def _normalize_quantity_value(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 1
    return parsed if parsed > 0 else 1


def _normalize_quantity_map(raw_map: Optional[dict[str, Any]]) -> dict[str, int]:
    normalized: dict[str, int] = {}
    for key, value in (raw_map or {}).items():
        normalized_key = _normalize_item(str(key))
        if not normalized_key:
            continue
        normalized[normalized_key] = _normalize_quantity_value(value)
    return normalized


def _normalize_packed_quantity_map(raw_map: Optional[dict[str, Any]]) -> dict[str, int]:
    normalized: dict[str, int] = {}
    for key, value in (raw_map or {}).items():
        normalized_key = _normalize_item(str(key))
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


def _get_item_quantity(quantity_map: Optional[dict[str, Any]], item: str) -> int:
    normalized_item = _normalize_item(item)
    if not normalized_item:
        return 1
    return _normalize_quantity_value((quantity_map or {}).get(normalized_item, 1))


def _get_item_packed_quantity(quantity_map: Optional[dict[str, Any]], item: str) -> int:
    normalized_item = _normalize_item(item)
    if not normalized_item:
        return 0
    try:
        return max(int((quantity_map or {}).get(normalized_item, 0) or 0), 0)
    except (TypeError, ValueError):
        return 0


def _set_item_quantity(quantity_map: dict[str, int], item: str, quantity: int) -> None:
    normalized_item = _normalize_item(item)
    if not normalized_item:
        return
    if quantity <= 0:
        quantity_map.pop(normalized_item, None)
    else:
        quantity_map[normalized_item] = quantity


def _set_item_packed_quantity(quantity_map: dict[str, int], item: str, quantity: int) -> None:
    normalized_item = _normalize_item(item)
    if not normalized_item:
        return
    if quantity <= 0:
        quantity_map.pop(normalized_item, None)
    else:
        quantity_map[normalized_item] = max(int(quantity), 0)


def _hydrate_packed_quantities(
    items: list[str],
    checked_items: Optional[list[str]],
    needed_quantities: Optional[dict[str, Any]],
    packed_quantities: Optional[dict[str, Any]],
) -> dict[str, int]:
    hydrated = _normalize_packed_quantity_map(packed_quantities)
    for item in checked_items or []:
        packed = _get_item_packed_quantity(hydrated, item)
        needed = _get_item_quantity(needed_quantities, item)
        _set_item_packed_quantity(hydrated, item, max(packed, needed))
    for item in items or []:
        packed = _get_item_packed_quantity(hydrated, item)
        needed = _get_item_quantity(needed_quantities, item)
        if packed > needed:
            _set_item_packed_quantity(hydrated, item, needed)
    return hydrated


def _sync_checked_items(
    items: list[str],
    needed_quantities: Optional[dict[str, Any]],
    packed_quantities: Optional[dict[str, Any]],
) -> list[str]:
    synced = []
    for item in items or []:
        if _get_item_packed_quantity(packed_quantities, item) >= _get_item_quantity(needed_quantities, item):
            synced.append(item)
    return _dedupe_preserve(synced)


def _format_item_with_quantity(
    item: str,
    quantity_map: Optional[dict[str, Any]],
    packed_quantities: Optional[dict[str, Any]] = None,
) -> str:
    quantity = _get_item_quantity(quantity_map, item)
    packed = _get_item_packed_quantity(packed_quantities, item)
    if packed_quantities is not None:
        return f"{item} {packed}/{quantity}"
    return f"{item} ×{quantity}" if quantity > 1 else item


def _parse_item_spec(raw_item: str, action_type: str) -> dict[str, Any]:
    cleaned = re.sub(r"\s+", " ", (raw_item or "").strip())
    if not cleaned:
        return {
            "raw": raw_item,
            "item": "",
            "quantity": 1,
            "explicit_quantity": False,
            "remove_all": False,
        }

    tokens = cleaned.split()
    quantity = 1
    explicit_quantity = False
    remove_all = False

    while tokens and _normalize_for_matching(tokens[0]) in REMOVE_ALL_WORDS:
        remove_all = True
        explicit_quantity = True
        tokens.pop(0)

    while tokens and _normalize_for_matching(tokens[-1]) in REMOVE_ALL_WORDS:
        remove_all = True
        explicit_quantity = True
        tokens.pop()

    if tokens:
        first_normalized = _normalize_for_matching(tokens[0])
        numeric_match = re.fullmatch(r"(\d+)", first_normalized)
        if numeric_match:
            quantity = max(int(numeric_match.group(1)), 1)
            explicit_quantity = True
            tokens.pop(0)
            if tokens and _normalize_for_matching(tokens[0]) in QUANTITY_FILLER_WORDS:
                tokens.pop(0)
        elif first_normalized in QUANTITY_WORDS:
            quantity = max(QUANTITY_WORDS[first_normalized], 1)
            explicit_quantity = True
            tokens.pop(0)
            if tokens and _normalize_for_matching(tokens[0]) in QUANTITY_FILLER_WORDS:
                tokens.pop(0)

    item_name = " ".join(tokens).strip() or cleaned
    if action_type == "add":
        item_name = _normalize_added_item_text(item_name)

    return {
        "raw": raw_item,
        "item": item_name,
        "quantity": quantity,
        "explicit_quantity": explicit_quantity,
        "remove_all": remove_all,
    }


def _looks_like_quantity_token(token: str) -> bool:
    normalized = _normalize_for_matching(token)
    return bool(
        normalized
        and (
            normalized in QUANTITY_WORDS
            or normalized in QUANTITY_FILLER_WORDS
            or normalized in REMOVE_ALL_WORDS
            or re.fullmatch(r"\d+", normalized)
        )
    )


def _with_item_specs(payload: dict[str, Any]) -> dict[str, Any]:
    actions = []
    for action in payload.get("actions", []):
        action_type = action.get("type")
        if not action_type:
            continue
        item_specs = [
            spec
            for spec in (_parse_item_spec(item, action_type) for item in action.get("items", []))
            if spec.get("item")
        ]
        actions.append(
            {
                **action,
                "items": [spec["item"] for spec in item_specs],
                "item_specs": item_specs,
            }
        )
    return {
        **payload,
        "actions": actions,
    }


def _is_everything_reference(value: str) -> bool:
    normalized = _normalize_for_matching(value)
    if not normalized:
        return False
    return (
        normalized in EVERYTHING_ALIASES
        or bool(re.fullmatch(r"(?:все|всё|everything|all)(?:\s+(?:вещи|items))?", normalized))
    )


def _expand_group_items(requested_item: str, candidates: list[str]) -> list[str]:
    normalized_requested = _normalize_for_matching(requested_item)
    if not normalized_requested:
        return []

    if _is_everything_reference(normalized_requested):
        return _dedupe_preserve(candidates)

    matches: list[str] = []
    for group in ITEM_GROUPS.values():
        group_aliases = {_normalize_for_matching(alias) for alias in group["aliases"]}
        if not any(alias and alias in normalized_requested for alias in group_aliases):
            continue

        group_keywords = {_normalize_for_matching(keyword) for keyword in group["keywords"]}
        for candidate in candidates:
            normalized_candidate = _normalize_for_matching(candidate)
            if any(keyword and keyword in normalized_candidate for keyword in group_keywords):
                matches.append(candidate)

        if matches:
            return _dedupe_preserve(matches)

    return []


def _resolve_requested_items(requested_items: list[str], candidates: list[str]) -> list[str]:
    resolved: list[str] = []
    for requested_item in requested_items:
        direct_matches = _match_existing_items([requested_item], candidates)
        if direct_matches:
            resolved.extend(direct_matches)
            continue

        group_matches = _expand_group_items(requested_item, candidates)
        if group_matches:
            resolved.extend(group_matches)

    return _dedupe_preserve(resolved)


def _extract_info_request(command: str, checklist, actor_user_id: Optional[int] = None) -> Optional[dict[str, Any]]:
    cleaned_command = _strip_conversational_prefixes(command or "")
    lowered = _normalize_for_matching(cleaned_command)
    if not lowered:
        return None

    request_type = None
    for candidate_type, patterns in INFO_PATTERNS.items():
        if any(re.search(pattern, lowered, re.IGNORECASE) for pattern in patterns):
            request_type = candidate_type
            break

    if not request_type:
        return None

    section = _resolve_section_reference(checklist, cleaned_command, actor_user_id)
    return {
        "recognized_action_request": True,
        "actions": [],
        "info_request": {
            "type": request_type,
            "section": section,
        },
    }


def _match_existing_items(requested_items: list[str], checklist_items: list[str]) -> list[str]:
    matches: list[str] = []
    candidate_signatures = [
        (item, _build_match_signature(item))
        for item in checklist_items
    ]

    for requested in requested_items:
        requested_signature = _build_match_signature(requested)
        normalized_requested = requested_signature["normalized"]
        if not normalized_requested:
            continue

        candidate = None
        best_score = -1
        for item, signature in candidate_signatures:
            score = 0
            if normalized_requested == signature["normalized"]:
                score = 100
            elif requested_signature["compact"] and requested_signature["compact"] == signature["compact"]:
                score = 96
            elif requested_signature["compact"] and requested_signature["compact"] in signature["compact"]:
                score = 90
            elif normalized_requested in signature["normalized"] or signature["normalized"] in normalized_requested:
                score = 84
            elif requested_signature["roots"] and requested_signature["roots"].issubset(signature["roots"]):
                score = 78
            elif requested_signature["prefixes"] and requested_signature["prefixes"].issubset(signature["prefixes"]):
                score = 72
            else:
                root_overlap = len(requested_signature["roots"] & signature["roots"])
                prefix_overlap = len(requested_signature["prefixes"] & signature["prefixes"])
                if requested_signature["roots"] and root_overlap:
                    score = max(score, int(58 + (root_overlap / len(requested_signature["roots"])) * 16))
                if requested_signature["prefixes"] and prefix_overlap:
                    score = max(score, int(54 + (prefix_overlap / len(requested_signature["prefixes"])) * 14))

            if score > best_score:
                best_score = score
                candidate = item

        if candidate and best_score >= 62:
            matches.append(candidate)

        if candidate:
            continue

    return _dedupe_preserve(matches)


def _match_single_item(requested_item: str, candidates: list[str]) -> Optional[str]:
    matches = _match_existing_items([requested_item], candidates)
    return matches[0] if matches else None


def _normalize_section(value: str) -> str:
    cleaned = _normalize_item(value).replace("ё", "е")
    cleaned = cleaned.lstrip("@")
    cleaned = re.sub(
        r"\b(?:рюкзак|рюкзака|рюкзаку|рюкзаке|сумка|сумке|сумку|из|в|во|к|на|для|the|to|from|bag|backpack|things|items)\b",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    return re.sub(r"\s+", " ", cleaned).strip()


def _get_baggage_name(backpack) -> str:
    kind = getattr(backpack, "kind", None) or "backpack"
    return (getattr(backpack, "name", None) or BAGGAGE_KIND_DEFAULT_NAMES.get(kind, "Багаж")).strip()


def _get_baggage_label(backpack) -> str:
    owner_name = backpack.user.username if getattr(backpack, "user", None) else f"id:{backpack.user_id}"
    baggage_name = _get_baggage_name(backpack)
    is_default = bool(getattr(backpack, "is_default", False))
    if is_default and _normalize_for_matching(baggage_name) in {"рюкзак", "backpack"}:
        return f"рюкзак {owner_name}"
    return f"{baggage_name.lower()} {owner_name}"


def _get_baggage_aliases(backpack) -> set[str]:
    aliases = set()
    kind = getattr(backpack, "kind", None) or "backpack"
    name = _get_baggage_name(backpack)
    normalized_name = _normalize_for_matching(name)
    if normalized_name:
        aliases.add(normalized_name)
    for alias in BAGGAGE_KIND_ALIASES.get(kind, []):
        normalized_alias = _normalize_for_matching(alias)
        if normalized_alias:
            aliases.add(normalized_alias)
    return aliases


def _pick_actor_backpack(checklist, actor_user_id: Optional[int]):
    if actor_user_id is None:
        return None
    owned = [
        backpack
        for backpack in (checklist.backpacks or [])
        if getattr(backpack, "user_id", None) == actor_user_id
    ]
    if not owned:
        return None
    owned.sort(key=lambda backpack: (
        not bool(getattr(backpack, "is_default", False)),
        getattr(backpack, "sort_order", 0) or 0,
        getattr(backpack, "id", 0) or 0,
    ))
    return owned[0]


def _build_backpack_reference(backpack) -> dict[str, Any]:
    return {
        "kind": "backpack",
        "backpack_id": backpack.id,
        "user_id": backpack.user_id,
        "label": _get_baggage_label(backpack),
    }


def _resolve_default_section_reference(checklist, actor_user_id: Optional[int] = None) -> dict[str, Any]:
    actor_backpack = _pick_actor_backpack(checklist, actor_user_id)
    if actor_backpack:
        return _build_backpack_reference(actor_backpack)
    return {"kind": "shared", "label": "общие вещи"}


def _guess_baggage_kind(name: str) -> str:
    normalized_name = _normalize_for_matching(name)
    if not normalized_name:
        return "custom"
    for kind, aliases in BAGGAGE_KIND_ALIASES.items():
        alias_set = {_normalize_for_matching(alias) for alias in aliases}
        if normalized_name in alias_set or any(alias and alias in normalized_name for alias in alias_set):
            return kind
    return "custom"


def _extract_baggage_management_actions(command: str) -> dict[str, Any]:
    cleaned_command = _strip_conversational_prefixes(command or "")
    if not cleaned_command:
        return {"recognized_action_request": False, "actions": []}

    for pattern in CREATE_BAGGAGE_PATTERNS:
        match = pattern.match(cleaned_command)
        if not match:
            continue
        baggage_name = re.sub(r"\s+", " ", match.group(1).strip(" .,!?:;"))
        if not baggage_name:
            return {"recognized_action_request": True, "actions": []}
        display_name = baggage_name[0].upper() + baggage_name[1:] if baggage_name[0].islower() else baggage_name
        return {
            "recognized_action_request": True,
            "actions": [{
                "type": "create_baggage",
                "items": [display_name],
                "baggage_kind": _guess_baggage_kind(display_name),
            }],
        }

    return {"recognized_action_request": False, "actions": []}


def _extract_move_actions(command: str, checklist, actor_user_id: Optional[int] = None) -> dict[str, Any]:
    cleaned_command = _strip_conversational_prefixes(command or "")
    lowered = cleaned_command.lower()
    if not lowered:
        return {"recognized_action_request": False, "actions": []}

    alias_pattern = "|".join(MOVE_PATTERNS)
    patterns = [
        re.compile(rf"^(?:{alias_pattern})\s+(.+?)\s+(?:из|from)\s+(.+?)\s+(?:в|во|to)\s+(.+)$", re.IGNORECASE),
        re.compile(rf"^(?:{alias_pattern})\s+(.+?)\s+(?:в|во|to)\s+(.+)$", re.IGNORECASE),
        re.compile(r"^(?:верни|вернуть|return)\s+(.+?)\s+(?:в|во|to)\s+(.+)$", re.IGNORECASE),
    ]

    for index, pattern in enumerate(patterns):
        match = pattern.match(cleaned_command)
        if not match:
            continue

        if index == 0:
            items_part, source_hint, target_hint = match.groups()
        else:
            items_part, target_hint = match.groups()
            source_hint = None

        items = _split_items(items_part)
        if not items:
            return {"recognized_action_request": True, "actions": []}

        return {
            "recognized_action_request": True,
            "actions": [{
                "type": "move",
                "items": items,
                "source_hint": source_hint.strip() if source_hint else None,
                "target_hint": target_hint.strip(),
            }],
        }

    special_patterns = [
        (
            "return_from_source",
            re.compile(r"^(?:верни|вернуть|return)\s+(.+?)\s+(?:из|from)\s+(.+?)(?:\s+(?:в|во|to)\s+(.+))?$", re.IGNORECASE),
        ),
        (
            "self_target",
            re.compile(
                r"^(?:я\s+(?:беру|забираю|возьму|заберу)|"
                r"(?:передай|отдай|переложи|перемести|перенеси|перекинь)\s+(?:мне|себе))\s+(.+)$",
                re.IGNORECASE,
            ),
        ),
        (
            "self_target_suffix",
            re.compile(
                r"^(?:отдай|передай|переложи|перемести|перенеси|перекинь)\s+(.+?)\s+(?:мне|себе)$",
                re.IGNORECASE,
            ),
        ),
        (
            "take_from_someone",
            re.compile(r"^(?:забери|возьми|утащи|переложи)\s+(.+?)\s+у\s+(.+)$", re.IGNORECASE),
        ),
        (
            "return_to_shared",
            re.compile(
                r"^(?:верни|положи\s+обратно|скинь\s+обратно|убери\s+обратно|верни\s+обратно)\s+(.+?)(?:\s+(?:в|во|to)\s+(.+))?(?:\s+(?:назад|обратно))?$",
                re.IGNORECASE,
            ),
        ),
        (
            "named_target",
            re.compile(
                r"^(?:отдай|передай|переложи|перемести|перенеси|перекинь)\s+(.+?)\s+(?:в\s+рюкзак\s+|рюкзаку\s+|пользователю\s+)?([a-zа-я0-9_\-]+)$",
                re.IGNORECASE,
            ),
        ),
    ]

    for kind, pattern in special_patterns:
        match = pattern.match(cleaned_command)
        if not match:
            continue

        if kind == "return_from_source":
            items_part, source_hint, target_hint = match.groups()
            items = _split_items(items_part)
            if not items:
                return {"recognized_action_request": True, "actions": []}
            return {
                "recognized_action_request": True,
                "actions": [{
                    "type": "move",
                    "items": items,
                    "source_hint": source_hint.strip(),
                    "target_hint": (target_hint or "общие вещи").strip(),
                }],
            }

        if kind in {"self_target", "self_target_suffix"}:
            items_part = match.group(1)
            items = _split_items(items_part)
            if not items:
                return {"recognized_action_request": True, "actions": []}
            return {
                "recognized_action_request": True,
                "actions": [{
                    "type": "move",
                    "items": items,
                    "source_hint": None,
                    "target_hint": "мой рюкзак",
                }],
            }

        if kind == "take_from_someone":
            items_part, source_hint = match.groups()
            items = _split_items(items_part)
            if not items:
                return {"recognized_action_request": True, "actions": []}
            return {
                "recognized_action_request": True,
                "actions": [{
                    "type": "move",
                    "items": items,
                    "source_hint": source_hint.strip(),
                    "target_hint": "мой рюкзак",
                }],
            }

        if kind == "return_to_shared":
            items_part, target_hint = match.groups()
            items = _split_items(items_part)
            if not items:
                return {"recognized_action_request": True, "actions": []}
            return {
                "recognized_action_request": True,
                "actions": [{
                    "type": "move",
                    "items": items,
                    "source_hint": None,
                    "target_hint": (target_hint or "общие вещи").strip(),
                }],
            }

        if kind == "named_target":
            items_part, target_hint = match.groups()
            if not _resolve_section_reference(checklist, target_hint, actor_user_id):
                continue
            items = _split_items(items_part)
            if not items:
                return {"recognized_action_request": True, "actions": []}
            return {
                "recognized_action_request": True,
                "actions": [{
                    "type": "move",
                    "items": items,
                    "source_hint": None,
                    "target_hint": target_hint.strip(),
                }],
            }

    return {"recognized_action_request": False, "actions": []}


def _resolve_section_reference(checklist, raw_section: Optional[str], actor_user_id: Optional[int] = None) -> Optional[dict[str, Any]]:
    if not raw_section:
        return None

    normalized = _normalize_section(raw_section)
    normalized_full = _normalize_for_matching(raw_section)
    if not normalized:
        return None

    if any(alias in normalized for alias in SHARED_SECTION_ALIASES):
        return _resolve_default_section_reference(checklist, actor_user_id)

    self_requested = any(alias in normalized for alias in SELF_SECTION_ALIASES)
    best_match = None
    best_score = -1

    for backpack in checklist.backpacks or []:
        username = _normalize_item(backpack.user.username if backpack.user else "")
        is_actor_baggage = actor_user_id is not None and backpack.user_id == actor_user_id
        owner_match = bool(username and (normalized == username or username in normalized or normalized in username))
        self_match = self_requested and is_actor_baggage

        baggage_aliases = _get_baggage_aliases(backpack)
        baggage_match = any(
            alias and (
                alias == normalized_full
                or alias in normalized_full
                or normalized_full in alias
            )
            for alias in baggage_aliases
        )

        score = 0
        if owner_match or self_match:
            score += 50
        if baggage_match:
            score += 35
        if getattr(backpack, "is_default", False) and (owner_match or self_match) and not baggage_match:
            score += 20
        if is_actor_baggage and baggage_match and not owner_match:
            score += 15

        if score > best_score:
            best_score = score
            best_match = backpack

    if best_match and best_score > 0:
        return _build_backpack_reference(best_match)

    return None


def _build_shared_section(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": "shared",
        "label": snapshot["shared"]["label"],
        "snapshot": snapshot["shared"],
    }


def _build_backpack_section(snapshot: dict[str, Any], backpack: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": "backpack",
        "backpack_id": backpack["id"],
        "user_id": backpack["user_id"],
        "name": backpack.get("name"),
        "kind_name": backpack.get("kind"),
        "is_default": backpack.get("is_default", False),
        "label": backpack["label"],
        "snapshot": backpack,
    }


def _pick_user_backpack_snapshot(backpacks: list[dict[str, Any]], user_id: Optional[int]) -> Optional[dict[str, Any]]:
    if user_id is None:
        return None
    owned = [bp for bp in backpacks if bp.get("user_id") == user_id]
    if not owned:
        return None
    owned.sort(key=lambda bp: (not bp.get("is_default", False), bp.get("sort_order", 0), bp.get("id", 0)))
    return owned[0]


def _build_default_action_section(snapshot: dict[str, Any], actor_user_id: Optional[int] = None) -> dict[str, Any]:
    actor_backpack = _pick_user_backpack_snapshot(snapshot["backpacks"], actor_user_id)
    if actor_backpack:
        return _build_backpack_section(snapshot, actor_backpack)
    return _build_shared_section(snapshot)


def _iter_candidate_source_sections(
    snapshot: dict[str, Any],
    target_section: Optional[dict[str, Any]],
    actor_user_id: Optional[int] = None,
) -> list[dict[str, Any]]:
    shared_section = _build_shared_section(snapshot)
    actor_backpack = _pick_user_backpack_snapshot(snapshot["backpacks"], actor_user_id)
    other_backpacks = [bp for bp in snapshot["backpacks"] if bp.get("user_id") != actor_user_id]

    ordered: list[dict[str, Any]] = []

    if target_section and target_section.get("kind") == "shared":
        if actor_backpack:
            ordered.append(_build_backpack_section(snapshot, actor_backpack))
        ordered.extend(_build_backpack_section(snapshot, bp) for bp in other_backpacks)
    else:
        ordered.append(shared_section)
        if actor_backpack:
            ordered.append(_build_backpack_section(snapshot, actor_backpack))
        ordered.extend(_build_backpack_section(snapshot, bp) for bp in other_backpacks)

    filtered: list[dict[str, Any]] = []
    for section in ordered:
        if (
            target_section
            and target_section.get("kind") == "backpack"
            and section.get("kind") == "backpack"
            and target_section.get("backpack_id") == section.get("backpack_id")
        ):
            continue
        filtered.append(section)
    return filtered


def _get_backpack_snapshot(snapshot: dict[str, Any], backpack_id: int) -> Optional[dict[str, Any]]:
    return next((bp for bp in snapshot["backpacks"] if bp["id"] == backpack_id), None)


def _find_backpacks_with_item(snapshot: dict[str, Any], requested_item: str) -> list[dict[str, Any]]:
    matches = []
    for backpack in snapshot["backpacks"]:
        if _resolve_requested_items([requested_item], backpack["items"]):
            matches.append(backpack)
    return matches


def _infer_source_section(
    checklist,
    snapshot: dict[str, Any],
    requested_item: str,
    target_section: Optional[dict[str, Any]],
    actor_user_id: Optional[int] = None,
) -> Optional[dict[str, Any]]:
    backpack_matches = _find_backpacks_with_item(snapshot, requested_item)

    if target_section and target_section.get("kind") == "backpack":
        backpack_matches = [bp for bp in backpack_matches if bp["id"] != target_section["backpack_id"]]

    if backpack_matches:
        preferred = next((bp for bp in backpack_matches if bp.get("user_id") == actor_user_id), None)
        selected = preferred or backpack_matches[0]
        return {
            "kind": "backpack",
            "backpack_id": selected["id"],
            "user_id": selected["user_id"],
            "label": selected["label"],
        }

    if _resolve_requested_items([requested_item], snapshot["shared"]["items"]):
        return {"kind": "shared", "label": "общие вещи"}

    return None


def _find_source_section_for_request(
    checklist,
    snapshot: dict[str, Any],
    requested_item: str,
    target_section: Optional[dict[str, Any]],
    actor_user_id: Optional[int] = None,
) -> Optional[dict[str, Any]]:
    explicit_inferred = _infer_source_section(checklist, snapshot, requested_item, target_section, actor_user_id)
    if explicit_inferred:
        if explicit_inferred["kind"] == "backpack":
            return {
                **explicit_inferred,
                "snapshot": _get_backpack_snapshot(snapshot, explicit_inferred["backpack_id"]),
                "matched_items": _resolve_requested_items(
                    [requested_item],
                    (_get_backpack_snapshot(snapshot, explicit_inferred["backpack_id"]) or {}).get("items", []),
                ),
            }
        return {
            **explicit_inferred,
            "snapshot": snapshot["shared"],
            "matched_items": _resolve_requested_items([requested_item], snapshot["shared"]["items"]),
        }

    for section in _iter_candidate_source_sections(snapshot, target_section, actor_user_id):
        matched_items = _resolve_requested_items([requested_item], section["snapshot"]["items"])
        if matched_items:
            return {
                **section,
                "matched_items": matched_items,
            }

    return None


def _take_transfer_state(section: dict[str, Any], actual_item: str) -> dict[str, Any]:
    normalized = _normalize_item(actual_item)
    quantity = _get_item_quantity(section.get("item_quantities"), actual_item)
    packed_quantity = min(
        _get_item_packed_quantity(section.get("packed_quantities"), actual_item),
        quantity,
    )
    return {
        "checked": packed_quantity >= quantity,
        "added": any(_normalize_item(existing) == normalized for existing in section.get("added_items", [])),
        "quantity": quantity,
        "packed_quantity": packed_quantity,
    }


def _remove_item_from_section(section: dict[str, Any], actual_item: str) -> None:
    normalized = _normalize_item(actual_item)
    for key in ("items", "checked_items", "added_items", "removed_items"):
        section[key] = [existing for existing in section.get(key, []) if _normalize_item(existing) != normalized]
    _set_item_quantity(section.setdefault("item_quantities", {}), actual_item, 0)
    _set_item_packed_quantity(section.setdefault("packed_quantities", {}), actual_item, 0)


def _append_unique(target: list[str], item: str) -> list[str]:
    normalized = _normalize_item(item)
    if all(_normalize_item(existing) != normalized for existing in target):
        target.append(item)
    return target


def _resolve_add_canonical_match(requested_item: str, candidates: list[str]) -> Optional[str]:
    requested_signature = _build_match_signature(requested_item)
    normalized_requested = requested_signature["normalized"]
    if not normalized_requested:
        return None

    best_match = None
    best_score = -1
    for candidate in candidates:
        signature = _build_match_signature(candidate)
        score = -1
        if normalized_requested == signature["normalized"]:
            score = 100
        elif requested_signature["compact"] and requested_signature["compact"] == signature["compact"]:
            score = 96
        elif normalized_requested in signature["normalized"] or signature["normalized"] in normalized_requested:
            score = 88

        if score > best_score:
            best_score = score
            best_match = candidate

    return best_match if best_score >= 88 else None


def _normalize_single_added_word(word: str) -> str:
    cleaned = (word or "").strip()
    lowered = cleaned.lower()
    if len(lowered) < 3:
        return cleaned

    if re.fullmatch(r"[а-яё-]+", lowered):
        if lowered.endswith("ку"):
            cleaned = cleaned[:-1] + ("а" if cleaned[-1].islower() else "А")
        elif lowered.endswith("гу"):
            cleaned = cleaned[:-1] + ("а" if cleaned[-1].islower() else "А")
        elif lowered.endswith("ху"):
            cleaned = cleaned[:-1] + ("а" if cleaned[-1].islower() else "А")
        elif lowered.endswith("жу"):
            cleaned = cleaned[:-1] + ("а" if cleaned[-1].islower() else "А")
        elif lowered.endswith("шу"):
            cleaned = cleaned[:-1] + ("а" if cleaned[-1].islower() else "А")
        elif lowered.endswith("чу"):
            cleaned = cleaned[:-1] + ("а" if cleaned[-1].islower() else "А")
        elif lowered.endswith("щу"):
            cleaned = cleaned[:-1] + ("а" if cleaned[-1].islower() else "А")
        elif lowered.endswith("у"):
            cleaned = cleaned[:-1] + ("а" if cleaned[-1].islower() else "А")
        elif lowered.endswith("ю"):
            cleaned = cleaned[:-1] + ("я" if cleaned[-1].islower() else "Я")
    return cleaned


def _normalize_added_item_text(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", (value or "").strip())
    if not cleaned:
        return ""

    if " " not in cleaned:
        cleaned = _normalize_single_added_word(cleaned)

    if cleaned and cleaned[0].isalpha() and cleaned[0].islower():
        cleaned = cleaned[0].upper() + cleaned[1:]
    return cleaned


def _resolve_action_section_snapshot(
    checklist,
    snapshot: dict[str, Any],
    section_hint: Optional[str],
    actor_user_id: Optional[int] = None,
) -> dict[str, Any]:
    section_ref = _resolve_section_reference(checklist, section_hint, actor_user_id) if section_hint else None
    if not section_ref or section_ref.get("kind") == "shared":
        return _build_default_action_section(snapshot, actor_user_id)

    backpack_snapshot = _get_backpack_snapshot(snapshot, section_ref["backpack_id"])
    if not backpack_snapshot:
        return _build_default_action_section(snapshot, actor_user_id)
    return _build_backpack_section(snapshot, backpack_snapshot)


def _canonicalize_section_hint(
    checklist,
    section_hint: Optional[str],
    actor_user_id: Optional[int] = None,
) -> Optional[str]:
    resolved = _resolve_section_reference(checklist, section_hint, actor_user_id) if section_hint else None
    return resolved.get("label") if resolved else None


def _get_actor_username(checklist, actor_user_id: Optional[int]) -> Optional[str]:
    if actor_user_id is None:
        return None

    if getattr(checklist, "user_id", None) == actor_user_id and getattr(checklist, "user", None):
        return getattr(checklist.user, "username", None)

    for backpack in (checklist.backpacks or []):
        if getattr(backpack, "user_id", None) == actor_user_id and getattr(backpack, "user", None):
            return getattr(backpack.user, "username", None)
    return None


def _personalize_section_label(
    label: Optional[str],
    checklist,
    actor_user_id: Optional[int] = None,
    section_user_id: Optional[int] = None,
    language: str = "ru",
) -> Optional[str]:
    if not label:
        return None

    normalized_label = _normalize_for_matching(label)
    if normalized_label == "общие вещи":
        return "общие вещи" if language == "ru" else "shared items"

    if actor_user_id is None or section_user_id != actor_user_id:
        return label

    actor_username = _get_actor_username(checklist, actor_user_id)
    if actor_username:
        normalized_username = _normalize_for_matching(actor_username)
        if normalized_username and normalized_label.endswith(f" {normalized_username}"):
            trimmed = label[: -(len(actor_username) + 1)].strip()
            if trimmed:
                return f"твой {trimmed}" if language == "ru" else f"your {trimmed}"

    return "твой багаж" if language == "ru" else "your baggage"


def _format_section_location(label: Optional[str], language: str = "ru") -> Optional[str]:
    if not label:
        return None
    if language != "ru":
        return f"in {label}"

    mapping = {
        "общие вещи": "в общих вещах",
        "твой рюкзак": "в твоем рюкзаке",
        "твой чемодан": "в твоем чемодане",
        "твой багаж": "в твоем багаже",
        "твоя ручная кладь": "в твоей ручной клади",
        "твой сумка": "в твоей сумке",
    }
    normalized = _normalize_for_matching(label)
    return mapping.get(normalized, f"в разделе «{label}»")


def _resolve_section_prefixed_tail(
    value: str,
    checklist,
    actor_user_id: Optional[int] = None,
    allow_user_prefix: bool = True,
) -> Optional[tuple[str, str]]:
    prefixes = [r"из", r"в", r"во"]
    if allow_user_prefix:
        prefixes.insert(0, r"у")

    match = re.match(rf"^(?:{'|'.join(prefixes)})\s+(.+)$", (value or "").strip(), re.IGNORECASE)
    if not match:
        return None

    tail = match.group(1).strip()
    tokens = tail.split()
    for prefix_length in range(len(tokens), 0, -1):
        if _looks_like_quantity_token(tokens[prefix_length - 1]):
            continue
        section_hint = " ".join(tokens[:prefix_length]).strip()
        items_part = " ".join(tokens[prefix_length:]).strip()
        if not items_part:
            continue
        if _resolve_section_reference(checklist, section_hint, actor_user_id):
            return section_hint, items_part
    return None


def _resolve_leading_section_tail(
    value: str,
    checklist,
    actor_user_id: Optional[int] = None,
) -> Optional[tuple[str, str]]:
    tail = (value or "").strip()
    if not tail:
        return None

    tokens = tail.split()
    for prefix_length in range(min(len(tokens), 4), 0, -1):
        if _looks_like_quantity_token(tokens[prefix_length - 1]):
            continue
        section_hint = " ".join(tokens[:prefix_length]).strip()
        items_part = " ".join(tokens[prefix_length:]).strip()
        if not items_part:
            continue
        if _resolve_section_reference(checklist, section_hint, actor_user_id):
            return section_hint, items_part
    return None


def _extract_actions_fallback(command: str, checklist=None, actor_user_id: Optional[int] = None) -> dict[str, Any]:
    cleaned_command = _strip_conversational_prefixes(command or "")
    lowered = cleaned_command.lower()
    if not lowered:
        return {"recognized_action_request": False, "actions": []}

    explicit_uncheck_request = any(
        re.match(rf"^(?:{alias})\b", cleaned_command, re.IGNORECASE)
        for alias in ACTION_PATTERNS["uncheck"]
    )

    aliases_by_phrase: list[tuple[str, str]] = []
    for action, aliases in ACTION_PATTERNS.items():
        for alias in aliases:
            aliases_by_phrase.append((alias, action))
    aliases_by_phrase.sort(key=lambda item: len(item[0]), reverse=True)

    recognized = False
    actions = []

    for alias, action in aliases_by_phrase:
        if action == "check" and explicit_uncheck_request:
            continue

        matched_scoped_variant = False
        alias_head_match = re.match(rf"^(?:{alias})\s+(.+)$", cleaned_command, re.IGNORECASE)
        if alias_head_match and checklist is not None:
            leading_section = _resolve_leading_section_tail(alias_head_match.group(1), checklist, actor_user_id)
            if leading_section:
                section_hint, items_part = leading_section
                if not (action == "add" and re.match(r"^\s*у\b", section_hint, re.IGNORECASE)):
                    items = _split_items(items_part)
                    if items:
                        recognized = True
                        matched_scoped_variant = True
                        canonical_section = _canonicalize_section_hint(checklist, section_hint, actor_user_id)
                        actions.append({
                            "type": action,
                            "items": items,
                            "section_hint": canonical_section or section_hint,
                        })

            scoped_tail = _resolve_section_prefixed_tail(
                alias_head_match.group(1),
                checklist,
                actor_user_id,
                allow_user_prefix=action in {"check", "remove", "uncheck"},
            )
            if scoped_tail:
                section_hint, items_part = scoped_tail
                items = _split_items(items_part)
                if items:
                    recognized = True
                    matched_scoped_variant = True
                    canonical_section = _canonicalize_section_hint(checklist, section_hint, actor_user_id)
                    actions.append({
                        "type": action,
                        "items": items,
                        "section_hint": canonical_section or section_hint,
                    })

        section_prepositions = r"у|из|в|во" if action in {"check", "remove", "uncheck"} else r"в|во"
        scoped_patterns = [
            re.compile(rf"^(?:{alias})\s+(.+?)\s+(?:{section_prepositions})\s+(.+)$", re.IGNORECASE),
            re.compile(rf"^(?:{section_prepositions})\s+(.+?)\s+(?:{alias})\s+(.+)$", re.IGNORECASE),
            re.compile(rf"^(?:{alias})\s+(.+?)\s+(?:мне|себе)$", re.IGNORECASE),
        ]

        for scoped_pattern in scoped_patterns:
            scoped_match = scoped_pattern.match(cleaned_command)
            if not scoped_match:
                continue

            if scoped_pattern.pattern.startswith("^(?:у|из|в|во)"):
                section_hint, items_part = scoped_match.groups()
            elif scoped_pattern.pattern.endswith("(?:мне|себе)$"):
                items_part = scoped_match.group(1)
                section_hint = "мой рюкзак"
            else:
                items_part, section_hint = scoped_match.groups()

            resolved_section = _resolve_section_reference(checklist, section_hint, actor_user_id=actor_user_id) if checklist else None
            if not resolved_section:
                continue

            recognized = True
            items = _split_items(items_part)
            if items:
                matched_scoped_variant = True
                actions.append({
                    "type": action,
                    "items": items,
                    "section_hint": resolved_section.get("label") or section_hint.strip(),
                })

        if matched_scoped_variant:
            continue

        pattern = re.compile(rf"(?:^|[,.!?\n]\s*|\s+)(?:{alias})\s+(.+?)(?=(?:[,.!?]\s+)|$)", re.IGNORECASE)
        for match in pattern.finditer(cleaned_command):
            if action == "add" and re.match(r"^\s*у\b", match.group(1), re.IGNORECASE):
                recognized = True
                continue
            recognized = True
            items = _split_items(match.group(1))
            if items:
                actions.append({"type": action, "items": items})

    if actions:
        merged: dict[tuple[str, Optional[str]], list[str]] = {}
        for action in actions:
            merged.setdefault((action["type"], action.get("section_hint")), []).extend(action["items"])
        return {
            "recognized_action_request": True,
            "actions": [
                {
                    "type": action_type,
                    "items": _dedupe_preserve(items),
                    **({"section_hint": section_hint} if section_hint else {}),
                }
                for (action_type, section_hint), items in merged.items()
            ],
        }

    return {"recognized_action_request": recognized, "actions": []}


async def _extract_actions_with_ai(command: str, checklist_items: list[str], language: str = "ru") -> Optional[dict[str, Any]]:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None

    prompt = (
        "Ты превращаешь просьбу пользователя в команды редактирования чеклиста.\n"
        "Верни только JSON без markdown и без пояснений.\n"
        "Формат ответа:\n"
        "{\"recognized_action_request\": true|false, \"actions\": [{\"type\": \"add|remove|check|uncheck\", \"items\": [\"...\"]}]}\n"
        "recognized_action_request=true только если пользователь явно просит изменить чеклист.\n"
        "Если это обычный вопрос или совет, верни {\"recognized_action_request\": false, \"actions\": []}.\n"
        "Для remove/check/uncheck старайся использовать точные названия из текущего чеклиста.\n"
        f"Текущий чеклист: {json.dumps(checklist_items, ensure_ascii=False)}\n"
        f"Язык пользователя: {language}\n"
        f"Сообщение пользователя: {command}"
    )

    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 300,
            "topP": 0.8,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            url = os.getenv("GEMINI_BASE_URL", "").strip() or DEFAULT_GEMINI_URL
            response = await client.post(f"{url}?key={api_key}", json=payload)
            if response.status_code != 200:
                return None

            data = response.json()
            text = (
                data.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
                .strip()
            )
            if not text:
                return None

            text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            start = text.find("{")
            end = text.rfind("}")
            if start == -1 or end == -1:
                return None

            parsed = json.loads(text[start:end + 1])
            if not isinstance(parsed, dict):
                return None

            actions = []
            for action in parsed.get("actions", []):
                action_type = action.get("type")
                items = action.get("items") or []
                if action_type not in {"add", "remove", "check", "uncheck"}:
                    continue
                if not isinstance(items, list):
                    continue
                normalized_items = _dedupe_preserve([str(item) for item in items if str(item).strip()])
                if normalized_items:
                    actions.append({"type": action_type, "items": normalized_items})

            return {
                "recognized_action_request": bool(parsed.get("recognized_action_request")) or bool(actions),
                "actions": actions,
            }
    except Exception as exc:
        print(f"[Checklist AI] parse error: {exc}")
        return None


def _build_ai_candidate_items(checklist, actor_user_id: Optional[int] = None) -> list[str]:
    candidates: list[str] = []
    actor_backpack = _pick_actor_backpack(checklist, actor_user_id)
    if actor_backpack:
        candidates.extend(actor_backpack.items or [])

    candidates.extend(checklist.items or [])

    for backpack in checklist.backpacks or []:
        if actor_backpack and backpack.id == actor_backpack.id:
            continue
        candidates.extend(backpack.items or [])

    return _dedupe_preserve(candidates)


async def parse_checklist_actions(
    command: str,
    checklist,
    language: str = "ru",
    actor_user_id: Optional[int] = None,
) -> dict[str, Any]:
    baggage_management_result = _extract_baggage_management_actions(command)
    if baggage_management_result["recognized_action_request"]:
        return _with_item_specs(baggage_management_result)

    info_result = _extract_info_request(command, checklist, actor_user_id)
    if info_result is not None:
        return _with_item_specs(info_result)

    move_result = _extract_move_actions(command, checklist, actor_user_id)
    if move_result["recognized_action_request"]:
        return _with_item_specs(move_result)

    checklist_items = _build_ai_candidate_items(checklist, actor_user_id)
    fallback_result = _extract_actions_fallback(command, checklist, actor_user_id)
    if fallback_result.get("actions"):
        return _with_item_specs(fallback_result)
    ai_result = await _extract_actions_with_ai(command, checklist_items, language)
    if ai_result is not None:
        return _with_item_specs(_merge_action_sets(ai_result, fallback_result))
    return _with_item_specs(fallback_result)


def _build_success_message(
    action_results: list[dict[str, Any]],
    checklist,
    language: str = "ru",
    actor_user_id: Optional[int] = None,
) -> str:
    def format_item_list(item_payload: dict[str, Any]) -> str:
        quantity_map = item_payload.get("item_quantities") or {}
        packed_map = item_payload.get("packed_quantities")
        return ", ".join(
            _format_item_with_quantity(name, quantity_map, packed_map)
            for name in item_payload.get("items", [])
        )

    if language == "en":
        fragments = []
        for item in action_results:
            item_list = format_item_list(item)
            if item["type"] == "move" and item["items"]:
                target_label = _personalize_section_label(
                    item.get("target_label"),
                    checklist,
                    actor_user_id,
                    item.get("target_user_id"),
                    language,
                ) or "target section"
                fragments.append(f"Moved to {target_label}: {item_list}")
            elif item["type"] == "exists" and item["items"]:
                section_label = _personalize_section_label(
                    item.get("section_label"),
                    checklist,
                    actor_user_id,
                    item.get("section_user_id"),
                    language,
                ) or "target section"
                fragments.append(f"{item['items'][0]} is already in {section_label}")
            elif item["type"] == "increase_quantity" and item["items"]:
                section_label = _personalize_section_label(
                    item.get("section_label"),
                    checklist,
                    actor_user_id,
                    item.get("section_user_id"),
                    language,
                ) or "target section"
                fragments.append(f"Increased in {section_label}: {item_list}")
            elif item["type"] == "decrease_quantity" and item["items"]:
                section_label = _personalize_section_label(
                    item.get("section_label"),
                    checklist,
                    actor_user_id,
                    item.get("section_user_id"),
                    language,
                ) or "target section"
                fragments.append(f"Reduced in {section_label}: {item_list}")
            elif item["type"] == "restore" and item["items"]:
                section_label = _personalize_section_label(
                    item.get("section_label"),
                    checklist,
                    actor_user_id,
                    item.get("section_user_id"),
                    language,
                ) or "target section"
                fragments.append(f"Restored in {section_label}: {item_list}")
            elif item["type"] == "add" and item["items"]:
                section_label = _personalize_section_label(
                    item.get("section_label"),
                    checklist,
                    actor_user_id,
                    item.get("section_user_id"),
                    language,
                )
                fragments.append(
                    f"Added to {section_label}: {item_list}" if section_label else f"Added: {item_list}"
                )
            elif item["type"] == "remove" and item["items"]:
                section_label = _personalize_section_label(
                    item.get("section_label"),
                    checklist,
                    actor_user_id,
                    item.get("section_user_id"),
                    language,
                )
                fragments.append(
                    f"Removed from {section_label}: {item_list}" if section_label else f"Removed: {item_list}"
                )
            elif item["type"] == "check" and item["items"]:
                section_label = _personalize_section_label(
                    item.get("section_label"),
                    checklist,
                    actor_user_id,
                    item.get("section_user_id"),
                    language,
                )
                if len(item["items"]) == 1 and item.get("total_quantity") is not None:
                    fragments.append(
                        f"Marked in {section_label}: {item['items'][0]} {item.get('total_packed', 0)}/{item['total_quantity']}"
                        if section_label
                        else f"Marked: {item['items'][0]} {item.get('total_packed', 0)}/{item['total_quantity']}"
                    )
                    continue
                fragments.append(
                    f"Marked in {section_label}: {item_list}" if section_label else f"Marked: {item_list}"
                )
            elif item["type"] == "uncheck" and item["items"]:
                section_label = _personalize_section_label(
                    item.get("section_label"),
                    checklist,
                    actor_user_id,
                    item.get("section_user_id"),
                    language,
                )
                if len(item["items"]) == 1 and item.get("total_quantity") is not None:
                    fragments.append(
                        f"Updated in {section_label}: {item['items'][0]} {item.get('total_packed', 0)}/{item['total_quantity']}"
                        if section_label
                        else f"Updated: {item['items'][0]} {item.get('total_packed', 0)}/{item['total_quantity']}"
                    )
                    continue
                fragments.append(
                    f"Unchecked in {section_label}: {item_list}" if section_label else f"Unchecked: {item_list}"
                )
            elif item["type"] == "create_baggage" and item["items"]:
                fragments.append(f"Created baggage: {item_list}")
            elif item["type"] == "not_found" and item["items"]:
                fragments.append(f"Couldn't find: {item_list}")
        return fragments[0] if len(fragments) == 1 else "\n".join(f"• {fragment}" for fragment in fragments) if fragments else "Checklist updated."

    fragments = []
    for item in action_results:
        item_list = format_item_list(item)
        if item["type"] == "move" and item["items"]:
            target_label = _personalize_section_label(
                item.get("target_label"),
                checklist,
                actor_user_id,
                item.get("target_user_id"),
                language,
            ) or "нужный раздел"
            fragments.append(f"Переместил в {target_label}: {item_list}")
        elif item["type"] == "exists" and item["items"]:
            section_label = _personalize_section_label(
                item.get("section_label"),
                checklist,
                actor_user_id,
                item.get("section_user_id"),
                language,
            )
            fragments.append(f"{item_list} уже есть {_format_section_location(section_label, language) or ''}".strip())
        elif item["type"] == "increase_quantity" and item["items"]:
            section_label = _personalize_section_label(
                item.get("section_label"),
                checklist,
                actor_user_id,
                item.get("section_user_id"),
                language,
            )
            fragments.append(
                f"Добавил в {section_label}: {item_list}" if section_label else f"Добавил: {item_list}"
            )
        elif item["type"] == "decrease_quantity" and item["items"]:
            section_label = _personalize_section_label(
                item.get("section_label"),
                checklist,
                actor_user_id,
                item.get("section_user_id"),
                language,
            )
            fragments.append(
                f"Уменьшил в {section_label}: {item_list}" if section_label else f"Уменьшил: {item_list}"
            )
        elif item["type"] == "restore" and item["items"]:
            section_label = _personalize_section_label(
                item.get("section_label"),
                checklist,
                actor_user_id,
                item.get("section_user_id"),
                language,
            )
            fragments.append(
                f"Вернул в {section_label}: {item_list}" if section_label else f"Вернул: {item_list}"
            )
        elif item["type"] == "add" and item["items"]:
            section_label = _personalize_section_label(
                item.get("section_label"),
                checklist,
                actor_user_id,
                item.get("section_user_id"),
                language,
            )
            fragments.append(
                f"Добавил в {section_label}: {item_list}" if section_label else f"Добавил: {item_list}"
            )
        elif item["type"] == "remove" and item["items"]:
            section_label = _personalize_section_label(
                item.get("section_label"),
                checklist,
                actor_user_id,
                item.get("section_user_id"),
                language,
            )
            fragments.append(
                f"Удалил из {section_label}: {item_list}" if section_label else f"Удалил: {item_list}"
            )
        elif item["type"] == "check" and item["items"]:
            section_label = _personalize_section_label(
                item.get("section_label"),
                checklist,
                actor_user_id,
                item.get("section_user_id"),
                language,
            )
            if len(item["items"]) == 1 and item.get("total_quantity") is not None:
                fragments.append(
                    f"Отметил в {section_label}: {item['items'][0]} {item.get('total_packed', 0)}/{item['total_quantity']}"
                    if section_label
                    else f"Отметил: {item['items'][0]} {item.get('total_packed', 0)}/{item['total_quantity']}"
                )
                continue
            fragments.append(
                f"Отметил в {section_label}: {item_list}" if section_label else f"Отметил: {item_list}"
            )
        elif item["type"] == "uncheck" and item["items"]:
            section_label = _personalize_section_label(
                item.get("section_label"),
                checklist,
                actor_user_id,
                item.get("section_user_id"),
                language,
            )
            if len(item["items"]) == 1 and item.get("total_quantity") is not None:
                fragments.append(
                    f"Обновил в {section_label}: {item['items'][0]} {item.get('total_packed', 0)}/{item['total_quantity']}"
                    if section_label
                    else f"Обновил: {item['items'][0]} {item.get('total_packed', 0)}/{item['total_quantity']}"
                )
                continue
            fragments.append(
                f"Снял отметку в {section_label}: {item_list}" if section_label else f"Снял отметку: {item_list}"
            )
        elif item["type"] == "already_checked" and item["items"]:
            if len(item["items"]) == 1 and item.get("total_quantity") is not None:
                fragments.append(f"{item['items'][0]} уже собрано: {item.get('total_packed', 0)}/{item['total_quantity']}")
            else:
                fragments.append(f"{item_list} уже отмечено")
        elif item["type"] == "already_unchecked" and item["items"]:
            if len(item["items"]) == 1 and item.get("total_quantity") is not None:
                fragments.append(f"Для {item['items'][0]} уже 0/{item['total_quantity']}")
            else:
                fragments.append(f"На {item_list} и так нет отметки")
        elif item["type"] == "already_removed" and item["items"]:
            fragments.append(f"{item_list} уже убрано")
        elif item["type"] == "create_baggage" and item["items"]:
            fragments.append(f"Создал багаж: {item_list}")
        elif item["type"] == "not_found" and item["items"]:
            fragments.append(f"Не нашёл: {item_list}")

    if not fragments:
        return "Чеклист обновлён."

    return fragments[0] if len(fragments) == 1 else "\n".join(f"• {fragment}" for fragment in fragments)


def _build_noop_message(recognized_action_request: bool, language: str = "ru") -> str:
    if recognized_action_request:
        return (
            "Я понял, что вы хотите изменить чеклист, но не смог распознать конкретные вещи."
            if language == "ru"
            else "I understood that you want to edit the checklist, but I couldn't recognize the items."
        )
    return (
        "Это больше похоже на обычный вопрос, а не на команду к чеклисту."
        if language == "ru"
        else "This looks more like a regular question than a checklist command."
    )


def _format_list_message(title: str, items: list[str], empty_message: str) -> str:
    if not items:
        return empty_message
    return f"{title}\n" + "\n".join(f"• {item}" for item in items)


def _build_info_message(
    checklist,
    info_request: dict[str, Any],
    language: str = "ru",
    actor_user_id: Optional[int] = None,
) -> str:
    section = info_request.get("section")
    if not section or section.get("kind") == "shared":
        default_backpack = _pick_actor_backpack(checklist, actor_user_id)
        if default_backpack:
            section = _build_backpack_reference(default_backpack)

    if section and section.get("kind") == "backpack":
        backpack = next((bp for bp in (checklist.backpacks or []) if bp.id == section.get("backpack_id")), None)
        section_items = list(backpack.items or []) if backpack else []
        checked_items = list(backpack.checked_items or []) if backpack else []
        removed_items = list(backpack.removed_items or []) if backpack else []
        quantity_map = _normalize_quantity_map(backpack.item_quantities if backpack else {})
        packed_map = _hydrate_packed_quantities(
            section_items,
            checked_items,
            quantity_map,
            getattr(backpack, "packed_quantities", None) if backpack else None,
        )
        section_label = section.get("label") or "рюкзак"
    else:
        section_items = list(checklist.items or [])
        checked_items = list(checklist.checked_items or [])
        removed_items = list(checklist.removed_items or [])
        quantity_map = _normalize_quantity_map(getattr(checklist, "item_quantities", None))
        packed_map = _hydrate_packed_quantities(
            section_items,
            checked_items,
            quantity_map,
            getattr(checklist, "packed_quantities", None),
        )
        section_label = "общие вещи"

    visible_items = [item for item in section_items if _normalize_item(item) not in {_normalize_item(x) for x in removed_items}]
    remaining_items = [
        item for item in visible_items
        if _normalize_item(item) not in {_normalize_item(x) for x in checked_items}
    ]

    request_type = info_request.get("type")
    if request_type == "checked":
        return _format_list_message(
            f"Уже отмечено в разделе «{section_label}»:",
            [_format_item_with_quantity(item, quantity_map, packed_map) for item in checked_items],
            f"Пока ничего не отмечено в разделе «{section_label}».",
        )
    if request_type == "remaining":
        return _format_list_message(
            f"Ещё осталось собрать в разделе «{section_label}»:",
            [_format_item_with_quantity(item, quantity_map, packed_map) for item in remaining_items],
            f"В разделе «{section_label}» всё уже собрано.",
        )
    if request_type == "removed":
        return _format_list_message(
            f"Скрыто или убрано в разделе «{section_label}»:",
            [_format_item_with_quantity(item, quantity_map, packed_map) for item in removed_items],
            f"В разделе «{section_label}» ничего не скрыто.",
        )
    if request_type == "items":
        return _format_list_message(
            f"Сейчас в разделе «{section_label}»:",
            [_format_item_with_quantity(item, quantity_map, packed_map) for item in visible_items],
            f"Раздел «{section_label}» пока пустой.",
        )

    return _build_noop_message(False, language)


def _build_add_candidate_pool(snapshot: dict[str, Any], action_section: dict[str, Any]) -> list[str]:
    pool = list(snapshot["shared"]["items"])
    for backpack in snapshot["backpacks"]:
        pool.extend(backpack["items"])
    pool.extend(action_section["snapshot"]["items"])
    return _dedupe_preserve(pool)


def _simulate_actions(checklist, actions: list[dict[str, Any]], actor_user_id: Optional[int] = None) -> dict[str, Any]:
    if not actions:
        return {
            "action_results": [],
            "items": list(checklist.items or []),
            "checked_items": _sync_checked_items(
                list(checklist.items or []),
                getattr(checklist, "item_quantities", None),
                _hydrate_packed_quantities(
                    list(checklist.items or []),
                    list(checklist.checked_items or []),
                    getattr(checklist, "item_quantities", None),
                    getattr(checklist, "packed_quantities", None),
                ),
            ),
            "added_items": list(checklist.added_items or []),
            "removed_items": list(checklist.removed_items or []),
            "item_quantities": _normalize_quantity_map(getattr(checklist, "item_quantities", None)),
            "packed_quantities": _hydrate_packed_quantities(
                list(checklist.items or []),
                list(checklist.checked_items or []),
                getattr(checklist, "item_quantities", None),
                getattr(checklist, "packed_quantities", None),
            ),
            "backpacks": [
                {
                    "id": backpack.id,
                    "user_id": backpack.user_id,
                    "name": _get_baggage_name(backpack),
                    "kind": getattr(backpack, "kind", None) or "backpack",
                    "sort_order": getattr(backpack, "sort_order", 0) or 0,
                    "is_default": bool(getattr(backpack, "is_default", False)),
                    "label": _get_baggage_label(backpack),
                    "items": list(backpack.items or []),
                    "checked_items": list(backpack.checked_items or []),
                    "added_items": list(backpack.added_items or []),
                    "removed_items": list(backpack.removed_items or []),
                    "item_quantities": _normalize_quantity_map(getattr(backpack, "item_quantities", None)),
                    "packed_quantities": _hydrate_packed_quantities(
                        list(backpack.items or []),
                        list(backpack.checked_items or []),
                        getattr(backpack, "item_quantities", None),
                        getattr(backpack, "packed_quantities", None),
                    ),
                }
                for backpack in (checklist.backpacks or [])
            ],
        }

    snapshot = {
        "shared": {
            "items": list(checklist.items or []),
            "checked_items": list(checklist.checked_items or []),
            "added_items": list(checklist.added_items or []),
            "removed_items": list(checklist.removed_items or []),
            "item_quantities": _normalize_quantity_map(getattr(checklist, "item_quantities", None)),
            "packed_quantities": _hydrate_packed_quantities(
                list(checklist.items or []),
                list(checklist.checked_items or []),
                getattr(checklist, "item_quantities", None),
                getattr(checklist, "packed_quantities", None),
            ),
            "label": "общие вещи",
        },
        "backpacks": [
            {
                "id": backpack.id,
                "user_id": backpack.user_id,
                "name": _get_baggage_name(backpack),
                "kind": getattr(backpack, "kind", None) or "backpack",
                "sort_order": getattr(backpack, "sort_order", 0) or 0,
                "is_default": bool(getattr(backpack, "is_default", False)),
                "label": _get_baggage_label(backpack),
                "items": list(backpack.items or []),
                "checked_items": list(backpack.checked_items or []),
                "added_items": list(backpack.added_items or []),
                "removed_items": list(backpack.removed_items or []),
                "item_quantities": _normalize_quantity_map(getattr(backpack, "item_quantities", None)),
                "packed_quantities": _hydrate_packed_quantities(
                    list(backpack.items or []),
                    list(backpack.checked_items or []),
                    getattr(backpack, "item_quantities", None),
                    getattr(backpack, "packed_quantities", None),
                ),
            }
            for backpack in (checklist.backpacks or [])
        ],
    }

    items = snapshot["shared"]["items"]
    checked_items = snapshot["shared"]["checked_items"]
    added_items = snapshot["shared"]["added_items"]
    removed_items = snapshot["shared"]["removed_items"]
    item_quantities = snapshot["shared"]["item_quantities"]
    packed_quantities = snapshot["shared"]["packed_quantities"]
    action_results: list[dict[str, Any]] = []

    for action in actions:
        action_type = action["type"]
        raw_items = action["items"]
        item_specs = action.get("item_specs") or [
            {
                "raw": item,
                "item": item,
                "quantity": 1,
                "explicit_quantity": False,
                "remove_all": False,
            }
            for item in raw_items
        ]

        if action_type == "move":
            target_section = _resolve_section_reference(checklist, action.get("target_hint"), actor_user_id)
            if not target_section:
                continue

            moved_items: list[dict[str, Any]] = []
            for spec in item_specs:
                requested_item = spec["item"]
                source_section = _resolve_section_reference(checklist, action.get("source_hint"), actor_user_id)
                if source_section and source_section.get("kind") == "backpack":
                    source_section = {
                        **source_section,
                        "snapshot": _get_backpack_snapshot(snapshot, source_section["backpack_id"]),
                        "matched_items": _resolve_requested_items(
                            [requested_item],
                            (_get_backpack_snapshot(snapshot, source_section["backpack_id"]) or {}).get("items", []),
                        ),
                    }
                elif source_section and source_section.get("kind") == "shared":
                    source_section = {
                        **source_section,
                        "snapshot": snapshot["shared"],
                        "matched_items": _resolve_requested_items([requested_item], snapshot["shared"]["items"]),
                    }

                if not source_section:
                    inferred = _find_source_section_for_request(
                        checklist,
                        snapshot,
                        requested_item,
                        target_section,
                        actor_user_id,
                    )
                    if not inferred:
                        continue
                    source_section = inferred

                target_snapshot = snapshot["shared"] if target_section["kind"] == "shared" else _get_backpack_snapshot(snapshot, target_section["backpack_id"])
                if not source_section.get("snapshot") or not target_snapshot:
                    continue

                actual_items = source_section.get("matched_items") or _resolve_requested_items([requested_item], source_section["snapshot"]["items"])
                if not actual_items:
                    continue

                for actual_item in actual_items:
                    normalized_item = _normalize_item(actual_item)
                    same_section = (
                        source_section["kind"] == target_section["kind"]
                        and (source_section["kind"] == "shared" or source_section.get("backpack_id") == target_section.get("backpack_id"))
                    )
                    if same_section:
                        continue

                    transfer_state = _take_transfer_state(source_section["snapshot"], actual_item)

                    if target_section["kind"] == "shared":
                        _append_unique(snapshot["shared"]["items"], actual_item)
                        target_existing_quantity = _get_item_quantity(snapshot["shared"]["item_quantities"], actual_item)
                        _set_item_quantity(
                            snapshot["shared"]["item_quantities"],
                            actual_item,
                            target_existing_quantity + transfer_state["quantity"],
                        )
                        target_existing_packed = _get_item_packed_quantity(snapshot["shared"]["packed_quantities"], actual_item)
                        _set_item_packed_quantity(
                            snapshot["shared"]["packed_quantities"],
                            actual_item,
                            target_existing_packed + transfer_state["packed_quantity"],
                        )
                        snapshot["shared"]["removed_items"] = [
                            existing for existing in snapshot["shared"]["removed_items"]
                            if _normalize_item(existing) != normalized_item
                        ]
                    else:
                        _append_unique(target_snapshot["items"], actual_item)
                        target_existing_quantity = _get_item_quantity(target_snapshot["item_quantities"], actual_item)
                        _set_item_quantity(
                            target_snapshot["item_quantities"],
                            actual_item,
                            target_existing_quantity + transfer_state["quantity"],
                        )
                        target_existing_packed = _get_item_packed_quantity(target_snapshot["packed_quantities"], actual_item)
                        _set_item_packed_quantity(
                            target_snapshot["packed_quantities"],
                            actual_item,
                            target_existing_packed + transfer_state["packed_quantity"],
                        )
                        if transfer_state["added"]:
                            _append_unique(target_snapshot["added_items"], actual_item)
                        target_snapshot["removed_items"] = [
                            existing for existing in target_snapshot["removed_items"]
                            if _normalize_item(existing) != normalized_item
                        ]

                    _remove_item_from_section(source_section["snapshot"], actual_item)

                    moved_items.append({
                        "name": actual_item,
                        "quantity": transfer_state["quantity"],
                        "packed_quantity": transfer_state["packed_quantity"],
                    })

            if moved_items:
                action_results.append({
                    "type": "move",
                    "items": _dedupe_preserve([entry["name"] for entry in moved_items]),
                    "item_quantities": {
                        _normalize_item(entry["name"]): entry["quantity"]
                        for entry in moved_items
                    },
                    "packed_quantities": {
                        _normalize_item(entry["name"]): entry["packed_quantity"]
                        for entry in moved_items
                    },
                    "target_label": target_section["label"],
                    "target_user_id": target_section.get("user_id"),
                })
            continue

        action_section = _resolve_action_section_snapshot(
            checklist,
            snapshot,
            action.get("section_hint"),
            actor_user_id,
        )
        is_shared_section = action_section["kind"] == "shared"
        section_snapshot = action_section["snapshot"]

        if is_shared_section:
            section_items = items
            section_checked_items = checked_items
            section_added_items = added_items
            section_removed_items = removed_items
            section_item_quantities = item_quantities
            section_packed_quantities = packed_quantities
        else:
            section_items = section_snapshot["items"]
            section_checked_items = section_snapshot["checked_items"]
            section_added_items = section_snapshot["added_items"]
            section_removed_items = section_snapshot["removed_items"]
            section_item_quantities = section_snapshot["item_quantities"]
            section_packed_quantities = section_snapshot["packed_quantities"]

        if action_type == "add":
            add_candidate_pool = _build_add_candidate_pool(snapshot, action_section)
            for spec in item_specs:
                normalized_requested_item = _normalize_added_item_text(spec["item"])
                canonical_match = _resolve_add_canonical_match(normalized_requested_item, add_candidate_pool)
                cleaned_item = canonical_match or normalized_requested_item
                normalized_item = _normalize_item(cleaned_item)
                existing_item = next((existing for existing in section_items if _normalize_item(existing) == normalized_item), cleaned_item)
                already_exists = any(_normalize_item(existing) == normalized_item for existing in section_items)
                is_removed = any(_normalize_item(existing) == normalized_item for existing in section_removed_items)
                current_quantity = _get_item_quantity(section_item_quantities, existing_item)

                if already_exists and is_removed:
                    section_removed_items = [
                        existing for existing in section_removed_items
                        if _normalize_item(existing) != normalized_item
                    ]
                    if spec["explicit_quantity"]:
                        next_quantity = current_quantity + spec["quantity"]
                        _set_item_quantity(section_item_quantities, existing_item, next_quantity)
                        current_packed = _get_item_packed_quantity(section_packed_quantities, existing_item)
                        _set_item_packed_quantity(section_packed_quantities, existing_item, min(current_packed, next_quantity))
                        action_results.append({
                            "type": "increase_quantity",
                            "items": [existing_item],
                            "amount": spec["quantity"],
                            "total_quantity": next_quantity,
                            **({"section_label": action_section["label"]} if action_section["label"] != "общие вещи" else {}),
                            **({"section_user_id": action_section.get("user_id")} if action_section.get("kind") == "backpack" else {}),
                        })
                    else:
                        _set_item_quantity(section_item_quantities, existing_item, current_quantity)
                        _set_item_packed_quantity(
                            section_packed_quantities,
                            existing_item,
                            min(_get_item_packed_quantity(section_packed_quantities, existing_item), current_quantity),
                        )
                        action_results.append({
                            "type": "restore",
                            "items": [existing_item],
                            **({"section_label": action_section["label"]} if action_section["label"] != "общие вещи" else {}),
                            **({"section_user_id": action_section.get("user_id")} if action_section.get("kind") == "backpack" else {}),
                        })
                    continue

                if already_exists:
                    if spec["explicit_quantity"]:
                        next_quantity = current_quantity + spec["quantity"]
                        _set_item_quantity(section_item_quantities, existing_item, next_quantity)
                        current_packed = _get_item_packed_quantity(section_packed_quantities, existing_item)
                        _set_item_packed_quantity(section_packed_quantities, existing_item, min(current_packed, next_quantity))
                        action_results.append({
                            "type": "increase_quantity",
                            "items": [existing_item],
                            "amount": spec["quantity"],
                            "total_quantity": next_quantity,
                            **({"section_label": action_section["label"]} if action_section["label"] != "общие вещи" else {}),
                            **({"section_user_id": action_section.get("user_id")} if action_section.get("kind") == "backpack" else {}),
                        })
                    else:
                        action_results.append({
                            "type": "exists",
                            "items": [existing_item],
                            "total_quantity": current_quantity,
                            **({"section_label": action_section["label"]} if action_section["label"] != "общие вещи" else {}),
                            **({"section_user_id": action_section.get("user_id")} if action_section.get("kind") == "backpack" else {}),
                        })
                    continue
                section_items.append(cleaned_item)
                initial_quantity = spec["quantity"] if spec["explicit_quantity"] else 1
                _set_item_quantity(section_item_quantities, cleaned_item, initial_quantity)
                _set_item_packed_quantity(section_packed_quantities, cleaned_item, 0)
                if all(_normalize_item(existing) != normalized_item for existing in section_added_items):
                    section_added_items.append(cleaned_item)
                section_removed_items = [
                    existing for existing in section_removed_items
                    if _normalize_item(existing) != normalized_item
                ]
                action_results.append({
                    "type": "add",
                    "items": [cleaned_item],
                    "total_quantity": initial_quantity,
                    **({"section_label": action_section["label"]} if action_section["label"] != "общие вещи" else {}),
                    **({"section_user_id": action_section.get("user_id")} if action_section.get("kind") == "backpack" else {}),
                })

        elif action_type == "remove":
            for spec in item_specs:
                matched_items = _resolve_requested_items([spec["item"]], section_items)
                if not matched_items:
                    action_results.append({
                        "type": "not_found",
                        "items": [spec["item"]],
                        **({"section_label": action_section["label"]} if action_section["label"] != "общие вещи" else {}),
                        **({"section_user_id": action_section.get("user_id")} if action_section.get("kind") == "backpack" else {}),
                    })
                    continue

                for item in matched_items:
                    normalized_item = _normalize_item(item)
                    if all(_normalize_item(existing) != normalized_item for existing in section_items):
                        continue

                    current_quantity = _get_item_quantity(section_item_quantities, item)
                    is_already_removed = any(
                        _normalize_item(existing) == normalized_item for existing in section_removed_items
                    )

                    if spec["explicit_quantity"] and not spec["remove_all"]:
                        next_quantity = max(current_quantity - spec["quantity"], 0)
                        if next_quantity > 0:
                            _set_item_quantity(section_item_quantities, item, next_quantity)
                            _set_item_packed_quantity(
                                section_packed_quantities,
                                item,
                                min(_get_item_packed_quantity(section_packed_quantities, item), next_quantity),
                            )
                            action_results.append({
                                "type": "decrease_quantity",
                                "items": [item],
                                "amount": min(spec["quantity"], current_quantity),
                                "total_quantity": next_quantity,
                                **({"section_label": action_section["label"]} if action_section["label"] != "общие вещи" else {}),
                                **({"section_user_id": action_section.get("user_id")} if action_section.get("kind") == "backpack" else {}),
                            })
                            continue

                    if not is_already_removed:
                        section_checked_items = [
                            existing for existing in section_checked_items
                            if _normalize_item(existing) != normalized_item
                        ]
                        section_removed_items.append(item)
                        _set_item_quantity(section_item_quantities, item, 0)
                        _set_item_packed_quantity(section_packed_quantities, item, 0)
                        action_results.append({
                            "type": "remove",
                            "items": [item],
                            **({"section_label": action_section["label"]} if action_section["label"] != "общие вещи" else {}),
                            **({"section_user_id": action_section.get("user_id")} if action_section.get("kind") == "backpack" else {}),
                        })
                    else:
                        action_results.append({
                            "type": "already_removed",
                            "items": [item],
                            **({"section_label": action_section["label"]} if action_section["label"] != "общие вещи" else {}),
                            **({"section_user_id": action_section.get("user_id")} if action_section.get("kind") == "backpack" else {}),
                        })

        elif action_type == "check":
            for spec in item_specs:
                matched_items = _resolve_requested_items([spec["item"]], section_items)
                if not matched_items:
                    action_results.append({
                        "type": "not_found",
                        "items": [spec["item"]],
                        **({"section_label": action_section["label"]} if action_section["label"] != "общие вещи" else {}),
                        **({"section_user_id": action_section.get("user_id")} if action_section.get("kind") == "backpack" else {}),
                    })
                    continue
                for item in matched_items:
                    normalized_item = _normalize_item(item)
                    needed_quantity = _get_item_quantity(section_item_quantities, item)
                    current_packed = _get_item_packed_quantity(section_packed_quantities, item)
                    if current_packed < needed_quantity:
                        next_packed = (
                            min(current_packed + spec["quantity"], needed_quantity)
                            if spec["explicit_quantity"]
                            else needed_quantity
                        )
                        _set_item_packed_quantity(section_packed_quantities, item, next_packed)
                        section_removed_items = [
                            existing for existing in section_removed_items
                            if _normalize_item(existing) != normalized_item
                        ]
                        action_results.append({
                            "type": "check",
                            "items": [item],
                            "total_packed": next_packed,
                            "total_quantity": needed_quantity,
                            **({"section_label": action_section["label"]} if action_section["label"] != "общие вещи" else {}),
                            **({"section_user_id": action_section.get("user_id")} if action_section.get("kind") == "backpack" else {}),
                        })
                    else:
                        action_results.append({
                            "type": "already_checked",
                            "items": [item],
                            "total_packed": current_packed,
                            "total_quantity": needed_quantity,
                            **({"section_label": action_section["label"]} if action_section["label"] != "общие вещи" else {}),
                            **({"section_user_id": action_section.get("user_id")} if action_section.get("kind") == "backpack" else {}),
                        })

        elif action_type == "uncheck":
            for spec in item_specs:
                matched_items = _resolve_requested_items([spec["item"]], section_items)
                if not matched_items:
                    action_results.append({
                        "type": "not_found",
                        "items": [spec["item"]],
                        **({"section_label": action_section["label"]} if action_section["label"] != "общие вещи" else {}),
                        **({"section_user_id": action_section.get("user_id")} if action_section.get("kind") == "backpack" else {}),
                    })
                    continue
                for item in matched_items:
                    normalized_item = _normalize_item(item)
                    current_packed = _get_item_packed_quantity(section_packed_quantities, item)
                    needed_quantity = _get_item_quantity(section_item_quantities, item)
                    if current_packed > 0:
                        next_packed = (
                            max(current_packed - spec["quantity"], 0)
                            if spec["explicit_quantity"]
                            else 0
                        )
                        _set_item_packed_quantity(section_packed_quantities, item, next_packed)
                        section_removed_items = [
                            existing for existing in section_removed_items
                            if _normalize_item(existing) != normalized_item
                        ]
                        action_results.append({
                            "type": "uncheck",
                            "items": [item],
                            "total_packed": next_packed,
                            "total_quantity": needed_quantity,
                            **({"section_label": action_section["label"]} if action_section["label"] != "общие вещи" else {}),
                            **({"section_user_id": action_section.get("user_id")} if action_section.get("kind") == "backpack" else {}),
                        })
                    else:
                        action_results.append({
                            "type": "already_unchecked",
                            "items": [item],
                            "total_packed": current_packed,
                            "total_quantity": needed_quantity,
                            **({"section_label": action_section["label"]} if action_section["label"] != "общие вещи" else {}),
                            **({"section_user_id": action_section.get("user_id")} if action_section.get("kind") == "backpack" else {}),
                        })

        if is_shared_section:
            items = _dedupe_preserve(section_items)
            checked_items = _sync_checked_items(section_items, section_item_quantities, section_packed_quantities)
            added_items = _dedupe_preserve(section_added_items)
            removed_items = _dedupe_preserve(section_removed_items)
            item_quantities = _normalize_quantity_map(section_item_quantities)
            packed_quantities = _normalize_packed_quantity_map(section_packed_quantities)
        else:
            section_snapshot["items"] = _dedupe_preserve(section_items)
            section_snapshot["checked_items"] = _sync_checked_items(section_items, section_item_quantities, section_packed_quantities)
            section_snapshot["added_items"] = _dedupe_preserve(section_added_items)
            section_snapshot["removed_items"] = _dedupe_preserve(section_removed_items)
            section_snapshot["item_quantities"] = _normalize_quantity_map(section_item_quantities)
            section_snapshot["packed_quantities"] = _normalize_packed_quantity_map(section_packed_quantities)

    return {
        "action_results": action_results,
        "items": items,
        "checked_items": _dedupe_preserve(checked_items),
        "added_items": _dedupe_preserve(added_items),
        "removed_items": _dedupe_preserve(removed_items),
        "item_quantities": _normalize_quantity_map(item_quantities),
        "packed_quantities": _normalize_packed_quantity_map(packed_quantities),
        "backpacks": snapshot["backpacks"],
    }


async def preview_checklist_ai_command(
    checklist,
    command: str,
    language: str = "ru",
    actor_user_id: Optional[int] = None,
) -> dict[str, Any]:
    parsed = await parse_checklist_actions(command, checklist, language, actor_user_id)
    actions = parsed["actions"]
    recognized_action_request = parsed["recognized_action_request"]
    info_request = parsed.get("info_request")

    if info_request:
        return {
            "applied": False,
            "recognized_action_request": True,
            "actions": [],
            "raw_actions": [],
            "message": _build_info_message(checklist, info_request, language, actor_user_id),
            "checklist": checklist,
            "requires_confirmation": False,
        }

    if not actions:
        return {
            "applied": False,
            "recognized_action_request": recognized_action_request,
            "actions": [],
            "raw_actions": actions,
            "message": _build_noop_message(recognized_action_request, language),
            "checklist": checklist,
            "requires_confirmation": False,
        }

    baggage_actions = [action for action in actions if action.get("type") == "create_baggage"]
    if baggage_actions:
        owner_id = actor_user_id or checklist.user_id
        existing_names = {
            _normalize_for_matching(_get_baggage_name(backpack))
            for backpack in (checklist.backpacks or [])
            if backpack.user_id == owner_id
        }
        action_results = []
        for action in baggage_actions:
            baggage_name = next(iter(action.get("items") or []), "").strip()
            if not baggage_name:
                continue
            if _normalize_for_matching(baggage_name) in existing_names:
                continue
            action_results.append({"type": "create_baggage", "items": [baggage_name]})

        if not action_results:
            return {
                "applied": False,
                "recognized_action_request": True,
                "actions": actions,
                "raw_actions": actions,
                "message": _build_noop_message(True, language),
                "checklist": checklist,
                "requires_confirmation": False,
            }

        return {
            "applied": False,
            "recognized_action_request": True,
            "actions": action_results,
            "raw_actions": actions,
            "message": _build_success_message(action_results, checklist, language, actor_user_id),
            "checklist": checklist,
            "requires_confirmation": False,
        }

    simulated = _simulate_actions(checklist, actions, actor_user_id)
    action_results = simulated["action_results"]

    if not action_results:
        return {
            "applied": False,
            "recognized_action_request": recognized_action_request,
            "actions": actions,
            "raw_actions": actions,
            "message": _build_noop_message(True, language),
            "checklist": checklist,
            "requires_confirmation": False,
        }

    requires_confirmation = any(
        action["type"] == "remove" and action["items"]
        for action in action_results
    )

    return {
        "applied": False,
        "recognized_action_request": True,
        "actions": action_results,
        "raw_actions": actions,
        "message": _build_success_message(action_results, checklist, language, actor_user_id),
        "checklist": checklist,
        "requires_confirmation": requires_confirmation,
    }


async def apply_checklist_ai_actions(
    db,
    checklist,
    actions: list[dict[str, Any]],
    language: str = "ru",
    actor_user_id: Optional[int] = None,
) -> dict[str, Any]:
    baggage_actions = [action for action in actions if action.get("type") == "create_baggage"]
    if baggage_actions:
        owner_id = actor_user_id or checklist.user_id
        if not owner_id:
            return {
                "applied": False,
                "recognized_action_request": True,
                "actions": actions,
                "message": _build_noop_message(True, language),
                "checklist": checklist,
            }

        existing_names = {
            _normalize_for_matching(_get_baggage_name(backpack))
            for backpack in (checklist.backpacks or [])
            if backpack.user_id == owner_id
        }
        action_results = []
        for action in baggage_actions:
            baggage_name = next(iter(action.get("items") or []), "").strip()
            if not baggage_name:
                continue
            normalized_name = _normalize_for_matching(baggage_name)
            if normalized_name in existing_names:
                continue
            await crud.create_user_baggage(
                db,
                checklist_id=checklist.id,
                user_id=owner_id,
                name=baggage_name,
                kind=action.get("baggage_kind") or _guess_baggage_kind(baggage_name),
            )
            existing_names.add(normalized_name)
            action_results.append({"type": "create_baggage", "items": [baggage_name]})

        updated_checklist = await crud.get_checklist_by_id(db, checklist.id)
        if not action_results:
            return {
                "applied": False,
                "recognized_action_request": True,
                "actions": actions,
                "message": _build_noop_message(True, language),
                "checklist": updated_checklist or checklist,
            }

        return {
            "applied": True,
            "recognized_action_request": True,
            "actions": action_results,
            "message": _build_success_message(action_results, updated_checklist or checklist, language, actor_user_id),
            "checklist": updated_checklist or checklist,
        }

    simulated = _simulate_actions(checklist, actions, actor_user_id)
    action_results = simulated["action_results"]

    if not action_results:
        return {
            "applied": False,
            "recognized_action_request": True,
            "actions": actions,
            "message": _build_noop_message(True, language),
            "checklist": checklist,
        }

    checklist.items = simulated["items"]
    checklist.checked_items = simulated["checked_items"]
    checklist.added_items = simulated["added_items"]
    checklist.removed_items = simulated["removed_items"]
    checklist.item_quantities = simulated["item_quantities"]
    checklist.packed_quantities = simulated["packed_quantities"]
    backpack_map = {backpack.id: backpack for backpack in (checklist.backpacks or [])}
    for backpack_snapshot in simulated["backpacks"]:
        backpack = backpack_map.get(backpack_snapshot["id"])
        if not backpack:
            continue
        backpack.items = _dedupe_preserve(backpack_snapshot["items"])
        backpack.checked_items = _dedupe_preserve(backpack_snapshot["checked_items"])
        backpack.added_items = _dedupe_preserve(backpack_snapshot["added_items"])
        backpack.removed_items = _dedupe_preserve(backpack_snapshot["removed_items"])
        backpack.item_quantities = _normalize_quantity_map(backpack_snapshot.get("item_quantities"))
        backpack.packed_quantities = _normalize_packed_quantity_map(backpack_snapshot.get("packed_quantities"))

    await db.commit()
    updated_checklist = await crud.get_checklist_by_id(db, checklist.id)

    return {
        "applied": True,
        "recognized_action_request": True,
        "actions": action_results,
        "message": _build_success_message(action_results, updated_checklist, language, actor_user_id),
        "checklist": updated_checklist,
    }


async def execute_checklist_ai_command(
    db,
    checklist,
    command: str,
    language: str = "ru",
    actor_user_id: Optional[int] = None,
) -> dict[str, Any]:
    preview = await preview_checklist_ai_command(checklist, command, language, actor_user_id)
    if not preview["recognized_action_request"] or not preview["actions"]:
        return preview
    return await apply_checklist_ai_actions(
        db,
        checklist,
        preview.get("raw_actions") or preview["actions"],
        language,
        actor_user_id,
    )
