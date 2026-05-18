from __future__ import annotations

from typing import Any, Optional

import crud


def _normalize(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().replace("ё", "е").split())


def _as_payload(recommendation: Any) -> dict[str, Any]:
    if hasattr(recommendation, "model_dump"):
        return recommendation.model_dump()
    if isinstance(recommendation, dict):
        return recommendation
    return {}


def _get_quantity(quantity_map: dict | None, item: str, fallback: int = 1) -> int:
    normalized_item = _normalize(item)
    for key, value in (quantity_map or {}).items():
        if _normalize(key) == normalized_item:
            try:
                return max(int(value), 0)
            except (TypeError, ValueError):
                return fallback
    return fallback


def _set_quantity(quantity_map: dict | None, item: str, value: int) -> dict:
    normalized_item = _normalize(item)
    next_map = dict(quantity_map or {})
    existing_key = next((key for key in next_map if _normalize(key) == normalized_item), item)
    if value <= 0:
        next_map.pop(existing_key, None)
    else:
        next_map[existing_key] = int(value)
    return next_map


def _remove_from_list(items: list[str] | None, item: str) -> list[str]:
    normalized_item = _normalize(item)
    return [existing for existing in (items or []) if _normalize(existing) != normalized_item]


def _append_unique(items: list[str] | None, item: str) -> list[str]:
    result = list(items or [])
    if all(_normalize(existing) != _normalize(item) for existing in result):
        result.append(item)
    return result


def _sync_checked_items(items: list[str] | None, item_quantities: dict | None, packed_quantities: dict | None) -> list[str]:
    checked: list[str] = []
    for item in items or []:
        quantity = max(_get_quantity(item_quantities, item, 1), 1)
        packed = max(_get_quantity(packed_quantities, item, 0), 0)
        if packed >= quantity:
            checked.append(item)
    return checked


def _is_backpack_hidden_for_actor(checklist, backpack, actor_user_id: Optional[int]) -> bool:
    hidden_sections = getattr(checklist, "hidden_sections", None) or []
    return f"backpack:{getattr(backpack, 'id', None)}" in hidden_sections and getattr(backpack, "user_id", None) != actor_user_id


def _can_edit_backpack(checklist, backpack, actor_user_id: int) -> bool:
    if not backpack or not actor_user_id:
        return False
    if getattr(backpack, "user_id", None) == actor_user_id:
        return True
    if _is_backpack_hidden_for_actor(checklist, backpack, actor_user_id):
        return False
    editor_ids = set()
    for raw_value in getattr(backpack, "editor_user_ids", None) or []:
        try:
            editor_ids.add(int(raw_value))
        except (TypeError, ValueError):
            continue
    return actor_user_id in editor_ids


def _find_actor_baggage(checklist, actor_user_id: int, kind: str) -> Optional[Any]:
    owned = [
        backpack
        for backpack in (getattr(checklist, "backpacks", None) or [])
        if getattr(backpack, "user_id", None) == actor_user_id and getattr(backpack, "kind", None) == kind
    ]
    owned.sort(key=lambda backpack: (not bool(getattr(backpack, "is_default", False)), getattr(backpack, "sort_order", 0) or 0, getattr(backpack, "id", 0) or 0))
    return owned[0] if owned else None


def _find_actor_default_baggage(checklist, actor_user_id: int) -> Optional[Any]:
    owned = [
        backpack
        for backpack in (getattr(checklist, "backpacks", None) or [])
        if getattr(backpack, "user_id", None) == actor_user_id
    ]
    owned.sort(key=lambda backpack: (not bool(getattr(backpack, "is_default", False)), getattr(backpack, "sort_order", 0) or 0, getattr(backpack, "id", 0) or 0))
    return owned[0] if owned else None


def _section_has_item(section: Any, item: str) -> bool:
    return any(_normalize(existing) == _normalize(item) for existing in (getattr(section, "items", None) or []))


def _find_editable_source(checklist, item: str, actor_user_id: int) -> tuple[str, Any] | None:
    actor_baggage = [
        backpack
        for backpack in (getattr(checklist, "backpacks", None) or [])
        if getattr(backpack, "user_id", None) == actor_user_id
    ]
    actor_baggage.sort(key=lambda backpack: (not bool(getattr(backpack, "is_default", False)), getattr(backpack, "sort_order", 0) or 0, getattr(backpack, "id", 0) or 0))
    for backpack in actor_baggage:
        if _section_has_item(backpack, item):
            return "backpack", backpack

    if any(_normalize(existing) == _normalize(item) for existing in (getattr(checklist, "items", None) or [])):
        return "shared", checklist

    for backpack in getattr(checklist, "backpacks", None) or []:
        if _can_edit_backpack(checklist, backpack, actor_user_id) and _section_has_item(backpack, item):
            return "backpack", backpack
    return None


def _take_item_from_section(section: Any, item: str) -> dict[str, int]:
    quantity = max(_get_quantity(getattr(section, "item_quantities", None), item, 1), 1)
    packed = max(_get_quantity(getattr(section, "packed_quantities", None), item, 0), 0)
    section.items = _remove_from_list(getattr(section, "items", None), item)
    section.checked_items = _remove_from_list(getattr(section, "checked_items", None), item)
    section.added_items = _remove_from_list(getattr(section, "added_items", None), item)
    section.removed_items = _remove_from_list(getattr(section, "removed_items", None), item)
    section.item_quantities = _set_quantity(getattr(section, "item_quantities", None), item, 0)
    section.packed_quantities = _set_quantity(getattr(section, "packed_quantities", None), item, 0)
    section.checked_items = _sync_checked_items(getattr(section, "items", None), getattr(section, "item_quantities", None), getattr(section, "packed_quantities", None))
    return {"quantity": quantity, "packed_quantity": min(packed, quantity)}


def _add_item_to_section(section: Any, item: str, quantity: int = 1, packed_quantity: int = 0) -> None:
    current_quantity = _get_quantity(getattr(section, "item_quantities", None), item, 0) if _section_has_item(section, item) else 0
    current_packed = _get_quantity(getattr(section, "packed_quantities", None), item, 0)
    next_quantity = max(current_quantity + max(int(quantity or 1), 1), 1)
    next_packed = min(current_packed + max(int(packed_quantity or 0), 0), next_quantity)
    section.items = _append_unique(getattr(section, "items", None), item)
    section.removed_items = _remove_from_list(getattr(section, "removed_items", None), item)
    section.item_quantities = _set_quantity(getattr(section, "item_quantities", None), item, next_quantity)
    section.packed_quantities = _set_quantity(getattr(section, "packed_quantities", None), item, next_packed)
    section.checked_items = _sync_checked_items(getattr(section, "items", None), getattr(section, "item_quantities", None), getattr(section, "packed_quantities", None))
    section.added_items = _append_unique(getattr(section, "added_items", None), item)


def _mark_item_removed(section: Any, item: str) -> bool:
    if not _section_has_item(section, item):
        return False
    section.checked_items = _remove_from_list(getattr(section, "checked_items", None), item)
    section.removed_items = _append_unique(getattr(section, "removed_items", None), item)
    section.item_quantities = _set_quantity(getattr(section, "item_quantities", None), item, 0)
    section.packed_quantities = _set_quantity(getattr(section, "packed_quantities", None), item, 0)
    section.checked_items = _sync_checked_items(getattr(section, "items", None), getattr(section, "item_quantities", None), getattr(section, "packed_quantities", None))
    return True


async def _ensure_actor_baggage(db, checklist, actor_user_id: int, kind: str):
    existing = _find_actor_baggage(checklist, actor_user_id, kind)
    if existing:
        return existing, checklist
    await crud.create_user_backpack(
        db,
        checklist_id=checklist.id,
        user_id=actor_user_id,
        kind=kind,
        is_default=False,
        items=[],
        item_quantities={},
    )
    updated_checklist = await crud.get_checklist_by_id(db, checklist.id)
    return _find_actor_baggage(updated_checklist, actor_user_id, kind), updated_checklist


async def apply_packing_recommendations(
    db,
    checklist,
    recommendations: list[Any],
    *,
    actor_user_id: int,
    language: str = "ru",
) -> dict[str, Any]:
    applied_actions: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for raw_recommendation in recommendations:
        recommendation = _as_payload(raw_recommendation)
        item = str(recommendation.get("item") or "").strip()
        action = str(recommendation.get("suggested_action") or "").strip()
        if not item or action not in {"add", "remove", "move_to_carry_on", "keep"}:
            skipped.append({"item": item, "reason": "invalid_recommendation"})
            continue

        if action == "keep":
            applied_actions.append({"type": "keep", "items": [item]})
            continue

        if action == "add":
            target = None
            target_section = str(recommendation.get("target_section") or "").lower()
            if "руч" in target_section or "carry" in target_section:
                target, checklist = await _ensure_actor_baggage(db, checklist, actor_user_id, "carry_on")
            if target is None:
                target = _find_actor_default_baggage(checklist, actor_user_id)
            if target is None:
                target, checklist = await _ensure_actor_baggage(db, checklist, actor_user_id, "backpack")
            if not target or not _can_edit_backpack(checklist, target, actor_user_id):
                skipped.append({"item": item, "reason": "no_editable_baggage"})
                continue
            _add_item_to_section(target, item)
            applied_actions.append({"type": "add", "items": [item], "target_baggage_id": target.id})
            continue

        if action == "remove":
            source = _find_editable_source(checklist, item, actor_user_id)
            if not source:
                skipped.append({"item": item, "reason": "item_not_found"})
                continue
            source_kind, source_section = source
            if source_kind == "backpack" and not _can_edit_backpack(checklist, source_section, actor_user_id):
                skipped.append({"item": item, "reason": "access_denied"})
                continue
            if not _mark_item_removed(source_section, item):
                skipped.append({"item": item, "reason": "item_not_found"})
                continue
            applied_actions.append({"type": "remove", "items": [item], "source": source_kind})
            continue

        if action == "move_to_carry_on":
            carry_on, checklist = await _ensure_actor_baggage(db, checklist, actor_user_id, "carry_on")
            if not carry_on or not _can_edit_backpack(checklist, carry_on, actor_user_id):
                skipped.append({"item": item, "reason": "no_editable_carry_on"})
                continue

            if _section_has_item(carry_on, item):
                applied_actions.append({"type": "keep", "items": [item], "target_baggage_id": carry_on.id})
                continue

            source = _find_editable_source(checklist, item, actor_user_id)
            if source:
                source_kind, source_section = source
                if source_kind == "backpack" and not _can_edit_backpack(checklist, source_section, actor_user_id):
                    skipped.append({"item": item, "reason": "access_denied"})
                    continue
                transfer_state = _take_item_from_section(source_section, item)
                _add_item_to_section(
                    carry_on,
                    item,
                    quantity=transfer_state["quantity"],
                    packed_quantity=transfer_state["packed_quantity"],
                )
                applied_actions.append({"type": "move_to_carry_on", "items": [item], "target_baggage_id": carry_on.id})
            else:
                _add_item_to_section(carry_on, item)
                applied_actions.append({"type": "add", "items": [item], "target_baggage_id": carry_on.id})

    await db.commit()
    updated_checklist = await crud.get_checklist_by_id(db, checklist.id)
    return {
        "applied_count": len(applied_actions),
        "actions": applied_actions,
        "skipped": skipped,
        "checklist": updated_checklist or checklist,
    }

