from __future__ import annotations

import re
from typing import Any, Optional


ORDINAL_ALIASES = {
    "первое": 1,
    "первый": 1,
    "первую": 1,
    "1": 1,
    "1-е": 1,
    "1ое": 1,
    "второе": 2,
    "второй": 2,
    "вторую": 2,
    "2": 2,
    "2-е": 2,
    "2ое": 2,
    "третье": 3,
    "третий": 3,
    "третью": 3,
    "3": 3,
    "3-е": 3,
    "3ье": 3,
    "четвертое": 4,
    "четвертый": 4,
    "четвёртое": 4,
    "четвёртый": 4,
    "4": 4,
    "пятое": 5,
    "пятый": 5,
    "5": 5,
    "шестое": 6,
    "шестой": 6,
    "6": 6,
    "first": 1,
    "second": 2,
    "third": 3,
    "fourth": 4,
    "fifth": 5,
    "sixth": 6,
}

APPLY_ALL_RE = re.compile(
    r"\b(?:примени|добавь|добавить|давай|сделай|ок|окей|ага|да|apply|add|do)\b.*\b(?:все|всё|all|everything)\b|"
    r"^(?:все|всё|all|everything)$",
    re.IGNORECASE,
)
SKIP_RE = re.compile(
    r"\b(?:не\s+надо|ничего|не\s+добавляй|не\s+применяй|пропусти|отмена|cancel|skip|nothing)\b",
    re.IGNORECASE,
)
ACTION_HINT_RE = re.compile(
    r"\b(?:добавь|добавить|примени|переложи|перекинь|убери|оставь|apply|add|move|remove|keep)\b",
    re.IGNORECASE,
)


def _normalize(value: Any) -> str:
    cleaned = str(value or "").lower().replace("ё", "е")
    cleaned = re.sub(r"[\(\)\[\]\{\}\.,!?:;\"'«»/\\+\-_]+", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _recommendation_payload(recommendation: Any) -> dict[str, Any]:
    if hasattr(recommendation, "model_dump"):
        recommendation = recommendation.model_dump()
    if not isinstance(recommendation, dict):
        return {}
    return {
        "item": recommendation.get("item"),
        "priority": recommendation.get("priority"),
        "reason": recommendation.get("reason"),
        "reason_tags": recommendation.get("reason_tags") or [],
        "suggested_action": recommendation.get("suggested_action"),
        "target_section": recommendation.get("target_section"),
    }


def build_packing_command_context(recommendations: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for index, recommendation in enumerate(recommendations[:12], start=1):
        payload = _recommendation_payload(recommendation)
        if not payload.get("item") or not payload.get("suggested_action"):
            continue
        items.append({"index": index, **payload})
    if not items:
        return None
    return {
        "type": "packing_recommendations",
        "items": items,
    }


def _get_context_recommendations(command_context: Optional[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(command_context, dict):
        return []
    if command_context.get("type") != "packing_recommendations":
        return []
    recommendations = []
    for index, raw_item in enumerate(command_context.get("items") or [], start=1):
        if not isinstance(raw_item, dict):
            continue
        payload = _recommendation_payload(raw_item)
        if not payload.get("item") or payload.get("suggested_action") not in {"add", "remove", "move_to_carry_on", "keep"}:
            continue
        try:
            payload["index"] = int(raw_item.get("index") or index)
        except (TypeError, ValueError):
            payload["index"] = index
        recommendations.append(payload)
    return recommendations


def build_remaining_packing_context(
    command_context: Optional[dict[str, Any]],
    selected_recommendations: list[dict[str, Any]],
) -> Optional[dict[str, Any]]:
    recommendations = _get_context_recommendations(command_context)
    selected_keys = {
        (item.get("index"), _normalize(item.get("item")))
        for item in selected_recommendations
    }
    remaining = [
        item
        for item in recommendations
        if (item.get("index"), _normalize(item.get("item"))) not in selected_keys
    ]
    return build_packing_command_context(remaining)


def _extract_indexes(command: str) -> set[int]:
    normalized = _normalize(command)
    indexes: set[int] = set()
    for token in re.findall(r"[a-zа-я0-9-]+", normalized):
        if token in ORDINAL_ALIASES:
            indexes.add(ORDINAL_ALIASES[token])
    for raw_number in re.findall(r"\b\d+\b", normalized):
        try:
            indexes.add(int(raw_number))
        except ValueError:
            continue
    return indexes


def _item_is_mentioned(command: str, item: str) -> bool:
    normalized_command = _normalize(command)
    normalized_item = _normalize(item)
    if not normalized_item:
        return False
    if normalized_item in normalized_command:
        return True
    item_tokens = [token for token in normalized_item.split() if len(token) > 2]
    if not item_tokens:
        return False
    return all(token in normalized_command for token in item_tokens)


def extract_packing_followup(
    command: str,
    command_context: Optional[dict[str, Any]],
    language: str = "ru",
) -> dict[str, Any]:
    recommendations = _get_context_recommendations(command_context)
    if not recommendations:
        return {
            "recognized_action_request": False,
            "recommendations": [],
            "message": "",
            "clear_context": False,
        }

    normalized_command = (command or "").strip()
    if not normalized_command:
        return {
            "recognized_action_request": False,
            "recommendations": [],
            "message": "",
            "clear_context": False,
        }

    if SKIP_RE.search(normalized_command):
        return {
            "recognized_action_request": True,
            "recommendations": [],
            "message": "Ок, ничего не меняю." if language == "ru" else "Okay, I won't change anything.",
            "clear_context": True,
        }

    if APPLY_ALL_RE.search(normalized_command):
        return {
            "recognized_action_request": True,
            "recommendations": recommendations,
            "message": "",
            "clear_context": True,
        }

    selected: list[dict[str, Any]] = []
    indexes = _extract_indexes(normalized_command)
    if indexes:
        selected.extend([item for item in recommendations if item.get("index") in indexes])

    for recommendation in recommendations:
        if _item_is_mentioned(normalized_command, str(recommendation.get("item") or "")):
            selected.append(recommendation)

    deduped: list[dict[str, Any]] = []
    seen = set()
    for recommendation in selected:
        key = (recommendation.get("index"), _normalize(recommendation.get("item")))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(recommendation)

    if deduped:
        return {
            "recognized_action_request": True,
            "recommendations": deduped,
            "message": "",
            "clear_context": False,
        }

    if ACTION_HINT_RE.search(normalized_command):
        return {
            "recognized_action_request": True,
            "recommendations": [],
            "message": (
                'Я помню рекомендации, но не понял, какие применить. Можно сказать "добавь первое" или "примени всё".'
                if language == "ru"
                else 'I remember the recommendations, but I could not tell which ones to apply. Try "add the first one" or "apply all".'
            ),
            "clear_context": False,
        }

    return {
        "recognized_action_request": False,
        "recommendations": [],
        "message": "",
        "clear_context": False,
    }


def format_packing_apply_message(
    apply_result: dict[str, Any],
    selected_recommendations: list[dict[str, Any]],
    language: str = "ru",
) -> str:
    applied_items = []
    for action in apply_result.get("actions") or []:
        applied_items.extend(str(item) for item in action.get("items") or [] if str(item).strip())
    skipped_items = [
        str(item.get("item") or "").strip()
        for item in apply_result.get("skipped") or []
        if str(item.get("item") or "").strip()
    ]
    selected_items = [
        str(item.get("item") or "").strip()
        for item in selected_recommendations
        if str(item.get("item") or "").strip()
    ]

    if language != "ru":
        if applied_items and skipped_items:
            return f"Done: applied {len(applied_items)} recommendation(s): {', '.join(applied_items)}. Could not apply: {', '.join(skipped_items)}."
        if applied_items:
            return f"Done: applied {len(applied_items)} recommendation(s): {', '.join(applied_items)}."
        if selected_items:
            return f"I understood the choice, but could not change the checklist for: {', '.join(selected_items)}."
        return "Okay, I won't change anything."

    if applied_items and skipped_items:
        return f"Готово: применил {len(applied_items)} рекомендации: {', '.join(applied_items)}. Не смог применить: {', '.join(skipped_items)}."
    if applied_items:
        return f"Готово: применил {len(applied_items)} рекомендации: {', '.join(applied_items)}."
    if selected_items:
        return f"Я понял выбор, но не смог изменить чеклист для: {', '.join(selected_items)}."
    return "Ок, ничего не меняю."
