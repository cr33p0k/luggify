import os
import re
import json
from datetime import datetime, timedelta, date
from urllib.parse import quote as url_quote, urlparse, parse_qs

from env_utils import load_app_env

load_app_env()

import httpx
from fastapi import FastAPI, Query, Depends, HTTPException, Body, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
import time
import asyncio
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
import crud, models, schemas
from database import SessionLocal, async_engine, get_db
from typing import Any, Dict, List, Optional
from auth import (
    verify_password, create_access_token,
    get_current_user, require_current_user
)
from telegram_auth import TelegramAuthError, parse_telegram_auth_payload
from telegram_link import create_telegram_link_token
from packing_logic import (
    build_packing_recommendations,
    build_trip_profile,
    get_default_baggage_kinds,
    normalize_trip_profile as normalize_packing_trip_profile,
    prepare_trip_profile_for_segment,
)
from trip_context import build_ad_hoc_trip_context, build_trip_context
from itinerary_logic import estimate_travel_buffer_minutes, haversine_distance_km
from currency_rates import convert_currency_amount, get_rub_rate, normalize_currency
from places_service import search_nearby_restaurants
from assistant_plan_service import apply_plan_proposals_to_checklist


def _parse_csv_env(name: str, defaults: list[str]) -> list[str]:
    raw = os.getenv(name, "")
    parsed = [item.strip() for item in raw.split(",") if item.strip()]
    return parsed or defaults


# Open-Meteo API (бесплатный, без ключа)
OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_HISTORICAL_URL = "https://archive-api.open-meteo.com/v1/archive"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
LOCATION_COUNTRY_CACHE: dict[str, Optional[str]] = {}
LOCATION_COORDS_CACHE: dict[str, tuple[float, float] | None] = {}
from translations import WMO_CODES, get_item, get_category_map, translate_known_item_label
from ai_service import DEFAULT_URL

default_cors_origins = [
    "http://localhost:5173",
    "http://localhost:5174",
    "https://luggify.vercel.app",
    "https://www.luggify.vercel.app",
]
cors_allowed_origins = _parse_csv_env("CORS_ALLOWED_ORIGINS", default_cors_origins)
cors_allowed_origin_regex = os.getenv(
    "CORS_ALLOWED_ORIGIN_REGEX",
    r"https://.*\.(vercel\.app|up\.railway\.app)",
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_allowed_origins,
    allow_origin_regex=cors_allowed_origin_regex,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)


def build_trip_review_payload(review: models.TripReview) -> dict:
    checklist = getattr(review, "checklist", None)
    author = review.user
    photos = _decode_trip_review_photos(review.photo)
    return {
        "id": review.id,
        "rating": review.rating,
        "text": review.text,
        "photo": photos[0] if photos else None,
        "photos": photos,
        "created_at": review.created_at,
        "updated_at": review.updated_at,
        "user": {
            "id": author.id,
            "email": None,
            "username": author.username,
            "tg_id": author.tg_id,
            "is_stats_public": author.is_stats_public,
            "is_email_verified": author.is_email_verified,
            "created_at": author.created_at,
            "avatar": author.avatar,
            "bio": author.bio,
            "social_links": author.social_links,
            "followers_count": 0,
            "following_count": 0,
            "is_following": False,
        },
        "checklist_slug": checklist.slug if checklist else None,
        "checklist_city": checklist.city if checklist else None,
        "checklist_start_date": checklist.start_date if checklist else None,
        "checklist_end_date": checklist.end_date if checklist else None,
    }


def _decode_trip_review_photos(value: str | None) -> list[str]:
    raw_value = str(value or "").strip()
    if not raw_value:
        return []
    if raw_value.startswith("["):
        try:
            parsed = json.loads(raw_value)
        except Exception:
            parsed = None
        if isinstance(parsed, list):
            normalized: list[str] = []
            for raw_item in parsed:
                photo = str(raw_item or "").strip()
                if photo and photo not in normalized:
                    normalized.append(photo)
            return normalized
    return [raw_value]


def _normalize_trip_review_photos(photo: str | None = None, photos: list[str] | None = None) -> list[str]:
    normalized: list[str] = []
    for raw_photo in ([photo] if photo else []) + list(photos or []):
        value = str(raw_photo or "").strip()
        if not value:
            continue
        if not (value.startswith("data:image") or value.startswith("http")):
            raise HTTPException(status_code=400, detail="Поддерживаются только изображения или ссылки на них")
        if value not in normalized:
            normalized.append(value)
        if len(normalized) >= 8:
            break
    return normalized


def _encode_trip_review_photos(photos: list[str]) -> str | None:
    if not photos:
        return None
    if len(photos) == 1:
        return photos[0]
    return json.dumps(photos, ensure_ascii=False)


def _split_location_segments(value: str | None) -> list[str]:
    if not value:
        return []
    return [segment.strip() for segment in value.split("+") if segment.strip()]


def _extract_city_and_country(segment: str) -> tuple[Optional[str], Optional[str]]:
    parts = [part.strip() for part in segment.split(",") if part.strip()]
    if not parts:
        return None, None
    city = parts[0]
    country = parts[-1] if len(parts) > 1 else None
    if country == city:
        country = None
    return city, country.casefold() if country else None


async def _resolve_country_for_city(city_name: str, client: httpx.AsyncClient) -> Optional[str]:
    normalized_city = re.sub(r"\s+", " ", city_name or "").strip()
    if not normalized_city:
        return None

    cache_key = normalized_city.casefold()
    if cache_key in LOCATION_COUNTRY_CACHE:
        return LOCATION_COUNTRY_CACHE[cache_key]

    headers = {"User-Agent": "Luggify/1.0"}
    try:
        resp = await client.get(
            NOMINATIM_URL,
            params={
                "q": normalized_city,
                "format": "json",
                "limit": 1,
                "addressdetails": 1,
            },
            headers=headers,
            timeout=10.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            if data:
                country = (data[0].get("address", {}) or {}).get("country")
                LOCATION_COUNTRY_CACHE[cache_key] = country.casefold() if country else None
                return LOCATION_COUNTRY_CACHE[cache_key]
    except Exception:
        pass

    LOCATION_COUNTRY_CACHE[cache_key] = None
    return None


async def collect_location_stats(checklists) -> tuple[set[str], set[str]]:
    cities: set[str] = set()
    countries: set[str] = set()
    unresolved_cities: set[str] = set()

    for checklist in checklists:
        for segment in _split_location_segments(getattr(checklist, "city", None)):
            city, country = _extract_city_and_country(segment)
            if city:
                cities.add(city.casefold())
            if country:
                countries.add(country)
            elif city:
                unresolved_cities.add(city)

    if unresolved_cities:
        async with httpx.AsyncClient() as client:
            resolved = await asyncio.gather(
                *[_resolve_country_for_city(city, client) for city in sorted(unresolved_cities)]
            )
        for country in resolved:
            if country:
                countries.add(country)

    return cities, countries


def _safe_positive_int(value, fallback: int = 1) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed > 0 else fallback


def count_total_items_for_user(checklists, user_id: int) -> int:
    total = 0

    def count_section_items(items, removed_items, item_quantities) -> int:
        removed = set(removed_items or [])
        quantity_map = item_quantities or {}
        section_total = 0

        for item in items or []:
            if item in removed:
                continue
            section_total += _safe_positive_int(quantity_map.get(item, 1))

        return section_total

    for checklist in checklists:
        if checklist.user_id == user_id:
            total += count_section_items(
                checklist.items,
                checklist.removed_items,
                checklist.item_quantities,
            )

        for backpack in checklist.backpacks or []:
            if backpack.user_id == user_id:
                total += count_section_items(
                    backpack.items,
                    backpack.removed_items,
                    backpack.item_quantities,
                )

    return total


def is_checklist_participant(checklist: models.Checklist, user_id: int) -> bool:
    if not checklist or not user_id:
        return False
    if checklist.user_id == user_id:
        return True
    if get_linked_child_profile_for_user(checklist, user_id):
        return True
    return any(bp.user_id == user_id for bp in (checklist.backpacks or []))


def can_edit_shared_section(checklist: models.Checklist, user_id: int) -> bool:
    return is_checklist_participant(checklist, user_id)


def get_baggage_editor_ids(checklist: models.Checklist, owner_user_id: int, child_profile_id: str | None = None) -> list[int]:
    editor_ids: list[int] = []
    for backpack in checklist.backpacks or []:
        if backpack.user_id != owner_user_id:
            continue
        if (backpack.child_profile_id or None) != (child_profile_id or None):
            continue
        for raw_value in backpack.editor_user_ids or []:
            try:
                parsed = int(raw_value)
            except (TypeError, ValueError):
                continue
            if parsed <= 0 or parsed == owner_user_id or parsed in editor_ids:
                continue
            editor_ids.append(parsed)
    return editor_ids


def is_backpack_hidden_for_viewer(
    backpack: models.UserBackpack,
    checklist: models.Checklist,
    user_id: int | None,
) -> bool:
    if not backpack or not checklist:
        return False
    if f"backpack:{backpack.id}" not in (checklist.hidden_sections or []):
        return False
    return backpack.user_id != user_id


def can_edit_baggage(backpack: models.UserBackpack, checklist: models.Checklist, user_id: int) -> bool:
    if not backpack or not checklist or not user_id:
        return False
    if not is_checklist_participant(checklist, user_id):
        return False
    if backpack.user_id == user_id:
        return True
    if checklist.user_id == user_id and backpack.child_profile_id:
        return True
    if backpack.child_profile_id:
        child_profile = get_trip_child_profile(checklist, backpack.child_profile_id)
        if get_child_profile_linked_user_id(child_profile) == user_id:
            return True
    if is_backpack_hidden_for_viewer(backpack, checklist, user_id):
        return False
    return user_id in get_baggage_editor_ids(checklist, backpack.user_id, backpack.child_profile_id)


def can_manage_baggage(backpack: models.UserBackpack, user_id: int, checklist: models.Checklist | None = None) -> bool:
    if not backpack or not user_id:
        return False
    if backpack.user_id == user_id:
        return True
    if checklist and checklist.user_id == user_id and backpack.child_profile_id:
        return True
    if checklist and backpack.child_profile_id:
        child_profile = get_trip_child_profile(checklist, backpack.child_profile_id)
        return get_child_profile_linked_user_id(child_profile) == user_id
    return False


def get_trip_child_profile(checklist: models.Checklist, child_profile_id: str | None) -> dict[str, Any] | None:
    if not checklist or not child_profile_id:
        return None
    trip_profile = normalize_packing_trip_profile(checklist.trip_profile or {})
    for profile in trip_profile.get("child_profiles") or []:
        if isinstance(profile, dict) and str(profile.get("id") or "") == str(child_profile_id):
            return profile
    return None


def get_child_profile_linked_user_id(profile: dict[str, Any] | None) -> int | None:
    if not isinstance(profile, dict):
        return None
    try:
        linked_user_id = int(profile.get("linked_user_id") or 0)
    except (TypeError, ValueError):
        return None
    return linked_user_id if linked_user_id > 0 else None


def get_linked_child_profile_for_user(checklist: models.Checklist, user_id: int | None) -> dict[str, Any] | None:
    if not checklist or not user_id:
        return None
    trip_profile = normalize_packing_trip_profile(checklist.trip_profile or {})
    for profile in trip_profile.get("child_profiles") or []:
        if get_child_profile_linked_user_id(profile) == user_id:
            return profile
    return None


async def link_trip_child_profile_to_user(
    db: AsyncSession,
    checklist: models.Checklist,
    child_profile_id: str | None,
    user_id: int,
) -> dict[str, Any] | None:
    child_profile = get_trip_child_profile(checklist, child_profile_id)
    if not child_profile:
        return None

    trip_profile = normalize_packing_trip_profile(checklist.trip_profile or {})
    child_profiles: list[dict[str, Any]] = []
    for profile in trip_profile.get("child_profiles") or []:
        if not isinstance(profile, dict):
            continue
        next_profile = dict(profile)
        if str(next_profile.get("id") or "") == str(child_profile_id):
            next_profile["linked_user_id"] = user_id
            child_profile = next_profile
        elif get_child_profile_linked_user_id(next_profile) == user_id:
            next_profile["linked_user_id"] = None
        child_profiles.append(next_profile)

    trip_profile["child_profiles"] = child_profiles
    checklist.trip_profile = trip_profile
    child_backpacks_result = await db.execute(
        select(models.UserBackpack).where(
            models.UserBackpack.checklist_id == checklist.id,
            models.UserBackpack.child_profile_id == child_profile_id,
        )
    )
    child_backpacks = child_backpacks_result.scalars().all()
    personal_backpacks_result = await db.execute(
        select(models.UserBackpack).where(
            models.UserBackpack.checklist_id == checklist.id,
            models.UserBackpack.user_id == user_id,
            models.UserBackpack.child_profile_id.is_(None),
        )
    )
    personal_backpacks = personal_backpacks_result.scalars().all()
    default_seen = any(backpack.is_default for backpack in personal_backpacks)
    child_has_default = any(backpack.is_default for backpack in child_backpacks)
    child_default_seen = False
    for index, backpack in enumerate(child_backpacks):
        backpack.user_id = user_id
        backpack.child_profile_id = None
        if default_seen:
            backpack.is_default = False
            continue
        if backpack.is_default:
            backpack.is_default = not child_default_seen
            child_default_seen = True
            default_seen = True
        elif not personal_backpacks and not child_has_default and not child_default_seen and index == 0:
            backpack.is_default = True
            child_default_seen = True
            default_seen = True
    await db.commit()
    await db.refresh(checklist)
    return child_profile


def normalize_item_key(value: str | None) -> str:
    return (value or "").strip().lower().replace("ё", "е")


def get_map_quantity(quantity_map: dict | None, item: str, fallback: int = 0) -> int:
    normalized_key = normalize_item_key(item)
    if not normalized_key:
        return fallback
    raw_value = (quantity_map or {}).get(normalized_key, fallback)
    try:
        parsed = int(raw_value)
    except (TypeError, ValueError):
        return fallback
    return parsed


def set_map_quantity(quantity_map: dict | None, item: str, value: int, *, keep_zero: bool = False) -> dict:
    normalized_key = normalize_item_key(item)
    next_map = dict(quantity_map or {})
    if not normalized_key:
        return next_map
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = 0
    if parsed <= 0 and not keep_zero:
        next_map.pop(normalized_key, None)
        return next_map
    next_map[normalized_key] = parsed
    return next_map


def get_map_text(text_map: dict | None, item: str, fallback: str | None = None) -> str | None:
    normalized_key = normalize_item_key(item)
    if not normalized_key:
        return fallback
    for key, value in (text_map or {}).items():
        if normalize_item_key(str(key)) != normalized_key:
            continue
        text_value = str(value or "").strip()
        return text_value or fallback
    return fallback


def set_map_text(text_map: dict | None, item: str, value: str | None) -> dict:
    normalized_key = normalize_item_key(item)
    next_map = {
        normalize_item_key(str(key)): str(raw_value).strip()
        for key, raw_value in (text_map or {}).items()
        if normalize_item_key(str(key)) and str(raw_value or "").strip()
    }
    if not normalized_key:
        return next_map
    text_value = str(value or "").strip()
    if not text_value:
        next_map.pop(normalized_key, None)
        return next_map
    next_map[normalized_key] = text_value
    return next_map


def rebuild_checked_items(items: list[str] | None, item_quantities: dict | None, packed_quantities: dict | None) -> list[str]:
    checked_items: list[str] = []
    for item in items or []:
        needed = max(1, get_map_quantity(item_quantities, item, 1))
        packed = max(0, get_map_quantity(packed_quantities, item, 0))
        if packed >= needed:
            checked_items.append(item)
    return checked_items

# Словарь переводов погодных условий



class PackingRequest(BaseModel):
    city: str
    start_date: str
    end_date: str
    trip_type: str = "city_break"
    trip_activities: List[str] = []
    baggage_format: str = "flexible"
    accommodation_type: str = "hotel"
    laundry_access: str = "limited"
    packing_style: str = "balanced"
    trip_note: str = ""
    gender: str = "unspecified"  # male, female, unspecified
    transport: str = "plane"     # plane, train, car, bus
    traveling_with_pet: bool = False
    has_allergies: bool = False
    traveling_with_children: bool = False
    adults: int = 2
    children_ages: List[int] = []
    child_profiles: List[Dict[str, Any]] = []
    infants_count: int = 0
    language: str = "ru"
    origin_city: str = ""
    participant_user_ids: List[int] = []

class TripSegment(BaseModel):
    city: str
    start_date: str
    end_date: str
    trip_type: str = "city_break"
    transport: str = "plane"

class MultiCityPackingRequest(BaseModel):
    segments: List[TripSegment]
    trip_activities: List[str] = []
    baggage_format: str = "flexible"
    accommodation_type: str = "hotel"
    laundry_access: str = "limited"
    packing_style: str = "balanced"
    trip_note: str = ""
    gender: str = "unspecified"
    traveling_with_pet: bool = False
    has_allergies: bool = False
    traveling_with_children: bool = False
    adults: int = 2
    children_ages: List[int] = []
    child_profiles: List[Dict[str, Any]] = []
    infants_count: int = 0
    language: str = "ru"
    origin_city: str = ""
    return_transport: str = "plane"
    participant_user_ids: List[int] = []


def build_runtime_packing_profile(profile: dict | None = None, overrides: dict | None = None) -> dict:
    normalized = crud._normalize_packing_profile(profile)
    if overrides is None:
        return normalized

    override_gender = str(overrides.get("gender") or "").strip().lower()
    normalized["gender"] = override_gender if override_gender in {"male", "female"} else "unspecified"
    normalized["traveling_with_pet"] = bool(overrides.get("traveling_with_pet"))
    normalized["has_allergies"] = bool(overrides.get("has_allergies"))
    normalized["traveling_with_children"] = bool(overrides.get("traveling_with_children"))
    return normalized


async def resolve_request_trip_profile(
    *,
    trip_type: str,
    trip_activities: list[str] | None = None,
    accommodation_type: str = "hotel",
    laundry_access: str = "limited",
    packing_style: str = "balanced",
    baggage_format: str = "flexible",
    adults: int = 2,
    children_ages: list[int] | None = None,
    child_profiles: list[dict[str, Any]] | None = None,
    infants_count: int = 0,
    trip_note: str = "",
    language: str = "ru",
) -> dict:
    return await build_trip_profile(
        {
            "trip_type": trip_type,
            "trip_activities": trip_activities or [],
            "accommodation_type": accommodation_type,
            "laundry_access": laundry_access,
            "packing_style": packing_style,
            "baggage_format": baggage_format,
            "adults": adults,
            "children_ages": children_ages or [],
            "child_profiles": child_profiles or [],
            "infants_count": max(infants_count, 0),
            "trip_note": trip_note,
        },
        language=language,
    )


async def build_personal_baggage_items_for_segments(
    segments: list[dict[str, str]],
    profile: dict,
    trip_profile: dict,
    language: str,
) -> dict[str, Any]:
    items: set[str] = set()
    item_quantities: dict[str, int] = {}
    for segment in segments:
        data = await calculate_packing_data(
            segment["city"],
            segment["start_date"],
            segment["end_date"],
            prepare_trip_profile_for_segment(trip_profile, segment["trip_type"]),
            segment["transport"],
            profile.get("gender", "unspecified"),
            bool(profile.get("traveling_with_pet")),
            bool(profile.get("has_allergies")),
            bool(profile.get("traveling_with_children")),
            language,
        )
        items.update(data["items"])
        for item, quantity in (data.get("item_quantities") or {}).items():
            item_quantities[item] = max(item_quantities.get(item, 0), int(quantity or 1))
    for item in profile.get("always_include_items") or []:
        items.add(item)
        item_quantities[item] = max(item_quantities.get(item, 0), 1)
    sorted_items = sorted(items)
    return {
        "items": sorted_items,
        "item_quantities": item_quantities,
        "item_categories": infer_item_categories(sorted_items, language),
    }


async def build_participant_baggage_payloads(
    db: AsyncSession,
    current_user,
    participant_user_ids: list[int],
    segments: list[dict[str, str]],
    owner_overrides: dict,
    trip_profile: dict,
    language: str,
) -> dict[int, dict[str, Any]] | None:
    unique_participant_ids: list[int] = []
    for raw_value in participant_user_ids or []:
        try:
            parsed = int(raw_value)
        except (TypeError, ValueError):
            continue
        if parsed <= 0 or (current_user and parsed == current_user.id) or parsed in unique_participant_ids:
            continue
        unique_participant_ids.append(parsed)

    if not current_user and unique_participant_ids:
        raise HTTPException(status_code=401, detail="Нужна авторизация для совместного чеклиста")

    if not current_user:
        return None

    payloads: dict[int, dict[str, Any]] = {}
    owner_profile = build_runtime_packing_profile(current_user.packing_profile, owner_overrides)
    payloads[current_user.id] = await build_personal_baggage_items_for_segments(
        segments,
        owner_profile,
        trip_profile,
        language,
    )

    for participant_user_id in unique_participant_ids:
        participant_user = await crud.get_user_by_id(db, participant_user_id)
        if not participant_user:
            raise HTTPException(status_code=404, detail=f"Пользователь {participant_user_id} не найден")
        participant_profile = build_runtime_packing_profile(participant_user.packing_profile)
        payloads[participant_user_id] = await build_personal_baggage_items_for_segments(
            segments,
            participant_profile,
            trip_profile,
            language,
        )

    return payloads


async def ensure_default_baggage_for_participant(
    db: AsyncSession,
    checklist: models.Checklist,
    user_id: int,
    *,
    items: list[str] | None = None,
    item_quantities: dict[str, int] | None = None,
    item_categories: dict[str, str] | None = None,
) -> None:
    existing_backpacks = await crud.get_backpacks_by_user(db, checklist.id, user_id)
    if existing_backpacks:
        return

    default_kinds = get_default_baggage_kinds(getattr(checklist, "trip_profile", None))
    await crud.create_user_backpack(
        db,
        checklist.id,
        user_id,
        kind=default_kinds[0] if default_kinds else "suitcase",
        is_default=True,
        items=items,
        item_quantities=item_quantities,
        item_categories=item_categories,
    )

    for extra_kind in default_kinds[1:]:
        await crud.create_user_backpack(
            db,
            checklist.id,
            user_id,
            kind=extra_kind,
            is_default=False,
            items=[],
            item_quantities={},
        )


class ChecklistResponse(schemas.ChecklistOut):
    daily_forecast: list[schemas.DailyForecast]

ChecklistResponse.model_rebuild()

class StatsResponse(BaseModel):
    total_trips: int
    total_days: int
    average_trip_days: int
    unique_cities: int
    unique_countries: int
    total_items: int
    upcoming_trips: int

class ChecklistStateUpdate(BaseModel):
    checked_items: Optional[List[str]] = None
    removed_items: Optional[List[str]] = None
    added_items: Optional[List[str]] = None
    item_quantities: Optional[dict[str, int]] = None
    packed_quantities: Optional[dict[str, int]] = None
    item_categories: Optional[dict[str, str]] = None
    item_translations: Optional[dict[str, dict[str, str]]] = None
    is_public: Optional[bool] = None
    items: Optional[List[str]] = None
    trip_profile: Optional[schemas.TripProfileData] = None

class BackpackStateUpdate(BaseModel):
    checked_items: Optional[List[str]] = None
    removed_items: Optional[List[str]] = None
    added_items: Optional[List[str]] = None
    item_quantities: Optional[dict[str, int]] = None
    packed_quantities: Optional[dict[str, int]] = None
    item_categories: Optional[dict[str, str]] = None
    item_translations: Optional[dict[str, dict[str, str]]] = None
    items: Optional[List[str]] = None


class ItemLabelTranslationRequest(BaseModel):
    text: str
    source_lang: Optional[str] = "auto"
    target_lang: str = "en"


class BaggageTransferRequest(BaseModel):
    item: str
    source_backpack_id: Optional[int] = None
    target_backpack_id: int


def infer_item_categories(items: list[str] | set[str] | None, language: str) -> dict[str, str]:
    mapping = get_category_map(language)
    fallback_category = "Misc" if language == "en" and "Misc" in mapping else "Прочее"
    categorized: dict[str, str] = {}
    for raw_item in items or []:
        item = str(raw_item or "").strip()
        if not item:
            continue
        category = next(
            (cat for cat, keywords in mapping.items() if any(keyword.lower() in item.lower() for keyword in keywords)),
            fallback_category,
        )
        categorized[item] = category
    return categorized


def _contains_cyrillic(text: str) -> bool:
    return bool(re.search(r"[А-Яа-яЁё]", text or ""))


def _guess_item_label_language(text: str) -> str:
    value = str(text or "").strip()
    if not value:
        return "ru"
    return "ru" if _contains_cyrillic(value) else "en"


async def _translate_item_label_with_ai(text: str, source_lang: str, target_lang: str) -> str | None:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None

    gemini_url = os.getenv("GEMINI_BASE_URL", "").strip() or DEFAULT_URL
    source_name = "Russian" if source_lang == "ru" else "English"
    target_name = "English" if target_lang == "en" else "Russian"
    prompt = (
        f"Translate this short travel packing item label from {source_name} to {target_name}.\n"
        "Return only the translated label, no quotes, no explanations.\n"
        "Keep it concise and natural for a packing checklist.\n"
        f"Label: {text}"
    )
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 80,
            "topP": 0.9,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(f"{gemini_url}?key={api_key}", json=payload)
            if resp.status_code != 200:
                return None
            data = resp.json()
            candidates = data.get("candidates", [])
            answer = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "") if candidates else ""
            cleaned = re.sub(r"\s+", " ", str(answer or "").strip()).strip("\"'` ")
            return cleaned or None
    except Exception:
        return None

class UserPrivacyUpdate(BaseModel):
    is_stats_public: bool

class ChecklistPrivacyUpdate(BaseModel):
    is_public: bool

# ==================== AUTH ENDPOINTS ====================

class VerifyEmailRequest(BaseModel):
    email: str
    code: str
    device_id: Optional[str] = None
    user_agent: Optional[str] = None

class ResendCodeRequest(BaseModel):
    email: str


def _csv_env_values(name: str) -> set[str]:
    return {item.strip() for item in os.getenv(name, "").split(",") if item.strip()}


def _is_admin_user(user) -> bool:
    if not user:
        return False

    admin_ids = _csv_env_values("ADMIN_USER_IDS")
    admin_emails = {item.lower() for item in _csv_env_values("ADMIN_EMAILS")}
    admin_usernames = {item.casefold() for item in _csv_env_values("ADMIN_USERNAMES")}

    return (
        str(getattr(user, "id", "")) in admin_ids
        or str(getattr(user, "email", "") or "").lower() in admin_emails
        or str(getattr(user, "username", "") or "").casefold() in admin_usernames
    )


def _build_user_out(user) -> schemas.UserOut:
    user_out = schemas.UserOut.model_validate(user)
    user_out.is_admin = _is_admin_user(user)
    return user_out


async def require_admin_user(user=Depends(require_current_user)):
    if not _is_admin_user(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав")
    return user

@app.post("/auth/register", response_model=schemas.Token)
async def register(data: schemas.UserCreate, db: AsyncSession = Depends(get_db)):
    """Регистрация нового пользователя с отправкой кода подтверждения"""
    # Проверяем уникальность email
    existing = await crud.get_user_by_email(db, data.email)
    if existing:
        raise HTTPException(status_code=400, detail="Пользователь с таким email уже существует")
    # Проверяем уникальность username
    existing = await crud.get_user_by_username(db, data.username)
    if existing:
        raise HTTPException(status_code=400, detail="Пользователь с таким именем уже существует")
    # Создаём пользователя
    user = await crud.create_user(db, data)
    
    # Generate and send verification code
    from email_service import generate_verification_code, send_verification_email
    code = generate_verification_code()
    user.email_verification_code = code
    user.code_expires_at = datetime.now() + timedelta(minutes=10)
    user.is_email_verified = False
    await db.commit()
    await db.refresh(user)
    
    email_sent = await send_verification_email(data.email, code, data.username)
    
    # Генерируем токен
    access_token = create_access_token(data={"sub": str(user.id)})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": _build_user_out(user),
        "message": (
            f"Аккаунт создан, но письмо на {data.email} пока не отправлено. "
            "Проверьте SMTP-настройки сервера и нажмите 'Отправить ещё раз'."
            if not email_sent
            else f"Код подтверждения отправлен на {data.email}"
        ),
        "email_delivery_failed": not email_sent,
    }


@app.post("/auth/verify-email")
async def verify_email(data: VerifyEmailRequest, db: AsyncSession = Depends(get_db)):
    """Подтверждение email по коду"""
    user = await crud.get_user_by_email(db, data.email)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    if user.is_email_verified:
        return {"verified": True, "message": "Email уже подтверждён"}
    
    if not user.email_verification_code:
        raise HTTPException(status_code=400, detail="Код подтверждения не был отправлен")
    
    if user.code_expires_at and user.code_expires_at < datetime.now():
        raise HTTPException(status_code=400, detail="Код истёк. Запросите новый")
    
    if user.email_verification_code != data.code:
        raise HTTPException(status_code=400, detail="Неверный код подтверждения")
    
    # Mark email as verified
    user.is_email_verified = True
    user.email_verification_code = None
    user.code_expires_at = None
    
    # Save the device as trusted if provided
    if data.device_id:
        new_device = models.UserDevice(
            user_id=user.id,
            device_id=data.device_id,
            user_agent=data.user_agent
        )
        db.add(new_device)
        
    await db.commit()
    
    return {"verified": True, "message": "Email успешно подтверждён"}


@app.post("/auth/resend-code")
async def resend_code(data: ResendCodeRequest, db: AsyncSession = Depends(get_db)):
    """Повторная отправка кода подтверждения"""
    user = await crud.get_user_by_email(db, data.email)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    if user.is_email_verified:
        return {"message": "Email уже подтверждён"}
    
    from email_service import generate_verification_code, send_verification_email
    code = generate_verification_code()
    user.email_verification_code = code
    user.code_expires_at = datetime.now() + timedelta(minutes=10)
    await db.commit()
    
    success = await send_verification_email(data.email, code, user.username)
    if not success:
        raise HTTPException(status_code=500, detail="Не удалось отправить письмо")
    
    return {"message": "Код отправлен повторно"}


@app.post("/auth/login")
async def login(data: schemas.UserLogin, response: Response, db: AsyncSession = Depends(get_db)):
    """Авторизация пользователя"""
    user = await crud.get_user_by_email(db, data.email)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь с таким email ещё не зарегистрирован")
    if not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Неверный пароль")
    
    # Check device ID
    if data.device_id:
        stmt = select(models.UserDevice).where(
            models.UserDevice.user_id == user.id,
            models.UserDevice.device_id == data.device_id
        )
        res_device = await db.execute(stmt)
        trusted_device = res_device.scalar_one_or_none()
        
        if not trusted_device:
            # Device not trusted, require verification
            from email_service import generate_verification_code, send_verification_email
            code = generate_verification_code()
            user.email_verification_code = code
            user.code_expires_at = datetime.now() + timedelta(minutes=10)
            await db.commit()
            
            email_sent = await send_verification_email(user.email, code, user.username)
            response.status_code = status.HTTP_202_ACCEPTED
            return {
                "status": "verification_required",
                "message": (
                    "Новое устройство. Код подтверждения отправлен на почту."
                    if email_sent
                    else (
                        f"Новое устройство, но письмо на {user.email} пока не отправлено. "
                        "Проверьте SMTP-настройки сервера и попробуйте ещё раз."
                    )
                ),
                "email_delivery_failed": not email_sent,
            }

    # Generate token if trusted or no device tracking (legacy)
    access_token = create_access_token(data={"sub": str(user.id)})
    
    # Update last_used_at for trusted device
    if data.device_id and trusted_device:
        trusted_device.last_used_at = datetime.now()
        await db.commit()

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": _build_user_out(user),
    }

@app.post("/auth/verify-device-login", response_model=schemas.Token)
async def verify_device_login(data: schemas.VerifyDeviceLogin, db: AsyncSession = Depends(get_db)):
    """Подтверждение входа с нового устройства"""
    user = await crud.get_user_by_email(db, data.email)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь с таким email ещё не зарегистрирован")
    if not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Неверный пароль")
        
    if not user.email_verification_code:
        raise HTTPException(status_code=400, detail="Код подтверждения не был запрошен")
    if user.code_expires_at and user.code_expires_at < datetime.now():
        raise HTTPException(status_code=400, detail="Код истёк. Запросите новый")
    if user.email_verification_code != data.code:
        raise HTTPException(status_code=400, detail="Неверный код подтверждения")
        
    # Mark code as used
    user.email_verification_code = None
    user.code_expires_at = None
    
    # Save the device as trusted if requested AND device_id provided
    if data.remember_device and data.device_id:
        new_device = models.UserDevice(
            user_id=user.id,
            device_id=data.device_id,
            user_agent=data.user_agent
        )
        db.add(new_device)
        
    await db.commit()
    
    access_token = create_access_token(data={"sub": str(user.id)})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": _build_user_out(user),
    }


@app.get("/auth/me", response_model=schemas.UserOut)
async def get_me(user=Depends(require_current_user), db: AsyncSession = Depends(get_db)):
    """Получение профиля текущего пользователя"""
    followers = await crud.get_followers(db, user.id)
    following = await crud.get_following(db, user.id)
    
    user_out = _build_user_out(user)
    user_out.followers_count = len(followers)
    user_out.following_count = len(following)
    return user_out


@app.patch("/auth/me", response_model=schemas.UserOut)
async def update_me(update_data: schemas.UserUpdate, user=Depends(require_current_user), db: AsyncSession = Depends(get_db)):
    """Обновление профиля текущего пользователя (описание, аватар, соцсети)"""
    updated_user = await crud.update_user(db, user_id=user.id, user_update=update_data)
    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )
    
    followers = await crud.get_followers(db, user.id)
    following = await crud.get_following(db, user.id)
    
    user_out = _build_user_out(updated_user)
    user_out.followers_count = len(followers)
    user_out.following_count = len(following)
    return user_out


@app.get("/auth/telegram/link", response_model=schemas.TelegramLinkResponse)
async def create_telegram_link(user=Depends(require_current_user)):
    bot_username = os.getenv("TELEGRAM_BOT_USERNAME", "luggify_bot").strip() or "luggify_bot"
    link_token, expires_at = create_telegram_link_token(user.id)
    return {
        "linked": bool(user.tg_id),
        "tg_id": user.tg_id,
        "bot_username": bot_username,
        "deep_link": f"https://t.me/{bot_username}?start=link_{link_token}",
        "link_command": f"/link {link_token}",
        "expires_at": expires_at,
    }


@app.delete("/auth/telegram/link", response_model=schemas.UserOut)
async def unlink_telegram(user=Depends(require_current_user), db: AsyncSession = Depends(get_db)):
    updated_user = await crud.unlink_telegram_from_user(db, user.id)
    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден",
        )

    followers = await crud.get_followers(db, user.id)
    following = await crud.get_following(db, user.id)

    user_out = _build_user_out(updated_user)
    user_out.followers_count = len(followers)
    user_out.following_count = len(following)
    return user_out


@app.post("/auth/telegram", response_model=schemas.Token)
async def telegram_auth(data: schemas.TelegramAuth, db: AsyncSession = Depends(get_db)):
    """Авторизация через Telegram — автосоздание пользователя при первом входе"""
    try:
        telegram_user = parse_telegram_auth_payload(data)
    except TelegramAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc))

    user = await crud.get_user_by_tg_id(db, telegram_user.tg_id)
    if not user:
        # Создаём нового пользователя из Telegram-данных
        user = await crud.create_user_from_telegram(
            db,
            tg_id=telegram_user.tg_id,
            username=telegram_user.username,
            first_name=telegram_user.first_name,
        )
    access_token = create_access_token(data={"sub": str(user.id)})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": _build_user_out(user),
    }


@app.patch("/auth/privacy", response_model=schemas.UserOut)
async def update_privacy(
    privacy: UserPrivacyUpdate,
    user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Обновление настроек приватности пользователя"""
    user.is_stats_public = privacy.is_stats_public
    await db.commit()
    await db.refresh(user)
    return _build_user_out(user)


@app.patch("/auth/avatar", response_model=schemas.UserOut)
async def update_avatar(
    data: schemas.UserAvatarUpdate,
    user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Обновление аватара пользователя"""
    user.avatar = data.avatar
    await db.commit()
    await db.refresh(user)
    return _build_user_out(user)


@app.get("/users/search", response_model=List[schemas.UserSearchResult])
async def search_users(
    q: str = Query(..., min_length=1, max_length=50),
    db: AsyncSession = Depends(get_db),
):
    users = await crud.search_users_by_username(db, q)
    return [
        {
            "id": item.id,
            "username": item.username,
            "avatar": item.avatar,
            "bio": item.bio,
        }
        for item in users
    ]


@app.get("/users/{username}", response_model=dict)
async def get_public_profile(
    username: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[models.User] = Depends(get_current_user)  # Optional, to check friend status later
):
    """Публичный профиль пользователя"""
    user = await crud.get_user_by_username(db, username)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    # Получаем все чеклисты пользователя: и собственные, и совместные
    all_checklists = await get_all_user_checklists(db, user.id)
    visible_checklists = [
        schemas.ChecklistOut.model_validate(c)
        for c in all_checklists
        if c.is_public or (current_user and is_checklist_participant(c, current_user.id))
    ]

    stats = None
    if user.is_stats_public:
        stats = await build_stats_payload(all_checklists, user.id)

    followers = await crud.get_followers(db, user.id)
    following = await crud.get_following(db, user.id)
    
    is_following = False
    follow_status = None  # null, "following", "requested"
    if current_user:
        is_following = any(f.id == current_user.id for f in followers)
        if is_following:
            follow_status = "following"
        else:
            # Check for pending follow request
            pending_req = await crud.get_follow_request(db, current_user.id, user.id)
            if pending_req:
                follow_status = "requested"

    public_reviews = await crud.get_trip_reviews_by_user_id(db, user.id, public_only=True)

    return {
        "id": user.id,
        "username": user.username,
        "created_at": user.created_at,
        "avatar": user.avatar,
        "bio": user.bio,
        "social_links": user.social_links,
        "is_stats_public": user.is_stats_public,
        "followers_count": len(followers),
        "following_count": len(following),
        "is_following": is_following,
        "follow_status": follow_status,
        "stats": stats,
        "checklists": visible_checklists,
        "reviews": [build_trip_review_payload(review) for review in public_reviews],
    }

# === Features: Subscriptions (Followers / Following) ===

@app.post("/users/{username}/follow")
async def follow_user_endpoint(username: str, user=Depends(require_current_user), db: AsyncSession = Depends(get_db)):
    target_user = await crud.get_user_by_username(db, username)
    if not target_user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    if target_user.id == user.id:
        raise HTTPException(status_code=400, detail="Нельзя подписаться на самого себя")
    
    # If target profile is private, create a follow request instead of direct follow
    if not target_user.is_stats_public:
        # Check if already following
        followers = await crud.get_followers(db, target_user.id)
        if any(f.id == user.id for f in followers):
            raise HTTPException(status_code=400, detail="Вы уже подписаны на этого пользователя")
        
        req = await crud.create_follow_request(db, user.id, target_user.id)
        if not req:
            raise HTTPException(status_code=400, detail="Запрос уже отправлен")
        
        # Create notification for target user
        new_notif = models.Notification(
            user_id=target_user.id,
            type="follow_request",
            content=f"{user.username} хочет подписаться на вас",
            link=f"/u/{user.username}",
            is_read=False,
            extra_data={"request_id": req.id, "from_user_id": user.id}
        )
        db.add(new_notif)
        await db.commit()
        
        return {"status": "requested"}
    
    # Public profile — direct follow
    success = await crud.follow_user(db, user.id, target_user.id)
    if not success:
        raise HTTPException(status_code=400, detail="Вы уже подписаны на этого пользователя")
    return {"status": "followed"}

@app.delete("/users/{username}/follow")
async def unfollow_user_endpoint(username: str, user=Depends(require_current_user), db: AsyncSession = Depends(get_db)):
    target_user = await crud.get_user_by_username(db, username)
    if not target_user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    # Try to unfollow first
    success = await crud.unfollow_user(db, user.id, target_user.id)
    if not success:
        # Maybe there's a pending request to cancel
        cancelled = await crud.cancel_follow_request(db, user.id, target_user.id)
        if not cancelled:
            raise HTTPException(status_code=400, detail="Вы не подписаны на этого пользователя")
        return {"status": "request_cancelled"}
    return {"status": "unfollowed"}

@app.delete("/users/{username}/followers/{follower_username}")
async def remove_follower_endpoint(username: str, follower_username: str, user=Depends(require_current_user), db: AsyncSession = Depends(get_db)):
    target_user = await crud.get_user_by_username(db, username)
    if not target_user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    if target_user.id != user.id:
        raise HTTPException(status_code=403, detail="Можно управлять только своими подписчиками")

    follower_user = await crud.get_user_by_username(db, follower_username)
    if not follower_user:
        raise HTTPException(status_code=404, detail="Подписчик не найден")

    success = await crud.remove_follower(db, user.id, follower_user.id)
    if not success:
        raise HTTPException(status_code=400, detail="Этот пользователь не подписан на вас")

    return {"status": "removed"}

@app.get("/users/{username}/followers", response_model=List[schemas.UserOut])
async def get_user_followers(username: str, current_user: Optional[models.User] = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    target_user = await crud.get_user_by_username(db, username)
    if not target_user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    followers = await crud.get_followers(db, target_user.id)
    
    # Enrich with is_following (from perspective of current logged in user)
    enriched_followers = []
    if current_user:
        current_user_following = await crud.get_following(db, current_user.id)
        current_following_ids = {u.id for u in current_user_following}
    
    for f in followers:
        f_out = schemas.UserOut.model_validate(f)
        if current_user:
            f_out.is_following = f.id in current_following_ids
        enriched_followers.append(f_out)
        
    return enriched_followers

@app.get("/users/{username}/following", response_model=List[schemas.UserOut])
async def get_user_following(username: str, current_user: Optional[models.User] = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    target_user = await crud.get_user_by_username(db, username)
    if not target_user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    following = await crud.get_following(db, target_user.id)
    
    # Enrich with is_following (from perspective of current logged in user)
    enriched_following = []
    if current_user:
        current_user_following = await crud.get_following(db, current_user.id)
        current_following_ids = {u.id for u in current_user_following}
        
    for f in following:
        f_out = schemas.UserOut.model_validate(f)
        if current_user:
            f_out.is_following = f.id in current_following_ids
        enriched_following.append(f_out)
        
    return enriched_following

# === Follow Request Endpoints ===

@app.get("/follow-requests", response_model=List[schemas.FollowRequestOut])
async def get_follow_requests(user=Depends(require_current_user), db: AsyncSession = Depends(get_db)):
    """Get all pending incoming follow requests for the current user"""
    requests = await crud.get_pending_follow_requests(db, user.id)
    result = []
    for req in requests:
        from_user_out = schemas.UserOut.model_validate(req.from_user)
        result.append(schemas.FollowRequestOut(
            id=req.id,
            from_user=from_user_out,
            status=req.status,
            created_at=req.created_at
        ))
    return result

@app.post("/follow-requests/{request_id}/accept")
async def accept_follow_request_endpoint(request_id: int, user=Depends(require_current_user), db: AsyncSession = Depends(get_db)):
    """Accept a follow request — auto-follows the requester"""
    # Get request info before accepting (for notification)
    stmt = select(models.FollowRequest).where(
        models.FollowRequest.id == request_id,
        models.FollowRequest.to_user_id == user.id,
        models.FollowRequest.status == "pending"
    )
    result = await db.execute(stmt)
    req = result.scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=404, detail="Запрос не найден")
    
    from_user_id = req.from_user_id
    
    success = await crud.accept_follow_request(db, request_id, user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Запрос не найден")
    
    # Notify the requester that their request was accepted
    new_notif = models.Notification(
        user_id=from_user_id,
        type="follow_accepted",
        content=f"{user.username} принял(а) ваш запрос на подписку",
        link=f"/u/{user.username}",
        is_read=False
    )
    db.add(new_notif)
    await db.commit()
    
    return {"status": "accepted"}

@app.post("/follow-requests/{request_id}/decline")
async def decline_follow_request_endpoint(request_id: int, user=Depends(require_current_user), db: AsyncSession = Depends(get_db)):
    """Decline a follow request"""
    success = await crud.decline_follow_request(db, request_id, user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Запрос не найден")
    return {"status": "declined"}


@app.get("/my-checklists", response_model=List[schemas.ChecklistOut])
async def get_my_checklists(
    user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Получение всех чеклистов текущего пользователя (собственные + совместные)"""
    own_checklists = await crud.get_checklists_by_user_id(db, user.id)
    shared_checklists = await crud.get_shared_checklists_by_user_id(db, user.id)
    
    # Merge, avoiding duplicates
    own_slugs = {c.slug for c in own_checklists}
    all_checklists = list(own_checklists)
    for c in shared_checklists:
        if c.slug not in own_slugs:
            all_checklists.append(c)
    
    return all_checklists


@app.get("/my-trip-reviews", response_model=List[schemas.TripReviewOut])
async def get_my_trip_reviews(
    user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
):
    reviews = await crud.get_trip_reviews_by_user_id(db, user.id)
    return [build_trip_review_payload(review) for review in reviews]


# === Feature: Gamification (Achievements + Levels) ===

ACHIEVEMENTS = [
    {"id": "first_step", "icon": "🎒", "name_ru": "Первый шаг", "name_en": "First Step",
     "desc_ru": "Создайте первый чеклист", "desc_en": "Create your first checklist"},
    {"id": "explorer", "icon": "🧭", "name_ru": "Исследователь", "name_en": "Explorer",
     "desc_ru": "Совершите 3 поездки", "desc_en": "Complete 3 trips"},
    {"id": "globetrotter", "icon": "🌍", "name_ru": "Глобус-троттер", "name_en": "Globetrotter",
     "desc_ru": "Совершите 10 поездок", "desc_en": "Complete 10 trips"},
    {"id": "multi_city", "icon": "🗺", "name_ru": "Мультигород", "name_en": "Multi-City",
     "desc_ru": "Создайте маршрут из нескольких городов", "desc_en": "Create a multi-city route"},
    {"id": "snowbird", "icon": "❄️", "name_ru": "Снежок", "name_en": "Snowbird",
     "desc_ru": "Поездка при температуре ниже 0°C", "desc_en": "Trip with temperature below 0°C"},
    {"id": "beach_lover", "icon": "🏖", "name_ru": "Пляжник", "name_en": "Beach Lover",
     "desc_ru": "Поездка при температуре выше 25°C", "desc_en": "Trip with temperature above 25°C"},
    {"id": "marathoner", "icon": "🏃", "name_ru": "Марафонец", "name_en": "Marathoner",
     "desc_ru": "Суммарно более 30 дней в поездках", "desc_en": "More than 30 days of travel total"},
    {"id": "cosmopolitan", "icon": "🌐", "name_ru": "Космополит", "name_en": "Cosmopolitan",
     "desc_ru": "Побывайте в 5+ странах", "desc_en": "Visit 5+ countries"},
    {"id": "list_keeper", "icon": "📋", "name_ru": "Хранитель списков", "name_en": "List Keeper",
     "desc_ru": "Создайте более 20 чеклистов", "desc_en": "Create more than 20 checklists"},
]

LEVELS = [
    {"name_ru": "Новичок", "name_en": "Novice", "icon": "🌱", "min": 0, "max": 2},
    {"name_ru": "Путешественник", "name_en": "Traveler", "icon": "✈️", "min": 3, "max": 5},
    {"name_ru": "Эксперт", "name_en": "Expert", "icon": "🏅", "min": 6, "max": 7},
    {"name_ru": "Легенда", "name_en": "Legend", "icon": "👑", "min": 8, "max": 9},
]

async def compute_achievements(checklists):
    """Вычисляет ачивки на основе чеклистов пользователя"""
    total = len(checklists)
    total_days = 0
    has_multi_city = False
    has_cold = False
    has_hot = False

    _, countries = await collect_location_stats(checklists)

    for c in checklists:
        if c.start_date and c.end_date:
            days = (c.end_date - c.start_date).days + 1
            if days > 0:
                total_days += days
        if c.city and "+" in c.city:
            has_multi_city = True
        if c.avg_temp is not None:
            if c.avg_temp < 0:
                has_cold = True
            if c.avg_temp > 25:
                has_hot = True

    unlocked = []
    if total >= 1: unlocked.append("first_step")
    if total >= 3: unlocked.append("explorer")
    if total >= 10: unlocked.append("globetrotter")
    if has_multi_city: unlocked.append("multi_city")
    if has_cold: unlocked.append("snowbird")
    if has_hot: unlocked.append("beach_lover")
    if total_days > 30: unlocked.append("marathoner")
    if len(countries) >= 5: unlocked.append("cosmopolitan")
    if total > 20: unlocked.append("list_keeper")

    # Determine progress for each
    results = []
    for a in ACHIEVEMENTS:
        is_unlocked = a["id"] in unlocked
        progress = 0
        if a["id"] == "first_step":
            progress = min(total, 1)
        elif a["id"] == "explorer":
            progress = min(total / 3, 1)
        elif a["id"] == "globetrotter":
            progress = min(total / 10, 1)
        elif a["id"] == "multi_city":
            progress = 1 if has_multi_city else 0
        elif a["id"] == "snowbird":
            progress = 1 if has_cold else 0
        elif a["id"] == "beach_lover":
            progress = 1 if has_hot else 0
        elif a["id"] == "marathoner":
            progress = min(total_days / 30, 1)
        elif a["id"] == "cosmopolitan":
            progress = min(len(countries) / 5, 1)
        elif a["id"] == "list_keeper":
            progress = min(total / 20, 1)

        results.append({
            **a,
            "unlocked": is_unlocked,
            "progress": round(progress, 2)
        })

    # Level
    unlocked_count = len(unlocked)
    level = LEVELS[0]
    for lv in LEVELS:
        if unlocked_count >= lv["min"]:
            level = lv

    return {"achievements": results, "level": level, "unlocked_count": unlocked_count}


async def get_all_user_checklists(db: AsyncSession, user_id: int):
    """Возвращает список всех чеклистов: и собственные, и те, куда добавили"""
    owned = await crud.get_checklists_by_user_id(db, user_id)
    shared = await crud.get_shared_checklists_by_user_id(db, user_id)
    # Объединяем и убираем дубликаты (хотя их быть не должно по логике)
    all_checklists = {c.id: c for c in owned}
    for c in shared:
        all_checklists[c.id] = c
    return list(all_checklists.values())


def can_view_expenses(checklist: models.Checklist, user_id: int | None) -> bool:
    if not checklist:
        return False
    if "expenses" not in (checklist.hidden_sections or []):
        return True
    return bool(user_id and is_checklist_participant(checklist, user_id))


def can_view_itinerary(checklist: models.Checklist, user_id: int | None) -> bool:
    if not checklist:
        return False
    if "itinerary" not in (checklist.hidden_sections or []):
        return True
    return bool(user_id and is_checklist_participant(checklist, user_id))


def get_visible_expenses_for_viewer(checklist: models.Checklist, user_id: int | None) -> list[models.TripExpense]:
    if not can_view_expenses(checklist, user_id):
        return []
    return sorted(
        list(getattr(checklist, "expenses", None) or []),
        key=lambda item: (
            item.expense_date or date.min,
            item.created_at or datetime.min,
            item.id or 0,
        ),
        reverse=True,
    )


def build_expense_summary(
    checklist: models.Checklist,
    expenses: list[models.TripExpense] | None = None,
    *,
    expose_budget: bool = True,
) -> schemas.TripExpenseSummary:
    visible_expenses = list(expenses or [])
    base_currency = normalize_currency(getattr(checklist, "expense_base_currency", None), "RUB")
    total_spent = round(sum(float(expense.amount_base or 0) for expense in visible_expenses), 2)
    by_category: dict[str, float] = {}
    for expense in visible_expenses:
        category = str(expense.category or "other").strip().lower() or "other"
        by_category[category] = round(by_category.get(category, 0) + float(expense.amount_base or 0), 2)
    budget_amount = getattr(checklist, "expense_budget_amount", None) if expose_budget else None
    trip_profile = getattr(checklist, "trip_profile", None) or {}
    expense_profile = trip_profile.get("expenses") if isinstance(trip_profile, dict) else {}
    daily_budget_amount = (
        expense_profile.get("daily_budget_amount")
        if expose_budget and isinstance(expense_profile, dict)
        else None
    )
    today = date.today()
    today_spent = round(
        sum(
            float(expense.amount_base or 0)
            for expense in visible_expenses
            if expense.expense_date == today
        ),
        2,
    )
    remaining = round(float(budget_amount) - total_spent, 2) if budget_amount is not None else None
    today_remaining = (
        round(float(daily_budget_amount) - today_spent, 2)
        if daily_budget_amount is not None
        else None
    )
    return schemas.TripExpenseSummary(
        budget_amount=budget_amount,
        daily_budget_amount=daily_budget_amount,
        base_currency=base_currency,
        total_spent=total_spent,
        remaining=remaining,
        today_spent=today_spent,
        today_remaining=today_remaining,
        by_category=by_category,
        expense_count=len(visible_expenses),
    )


async def build_expense_conversion(
    amount: float,
    currency: str,
    base_currency: str,
) -> dict[str, Any]:
    converted = await convert_currency_amount(amount, currency, base_currency)
    if not converted:
        raise HTTPException(status_code=400, detail="Не удалось получить курс валюты")
    return converted


async def build_checklist_response_payload(
    checklist: models.Checklist,
    user_id: int | None = None,
):
    if not checklist:
        return None

    forecast = checklist.daily_forecast
    if not forecast:
        try:
            forecast = await get_weather_forecast_data(
                checklist.city,
                checklist.start_date,
                checklist.end_date,
                language="ru",
            )
        except Exception:
            forecast = []

    visible_backpacks = [
        backpack
        for backpack in (checklist.backpacks or [])
        if not is_backpack_hidden_for_viewer(backpack, checklist, user_id)
    ]
    expenses_visible = can_view_expenses(checklist, user_id)
    itinerary_visible = can_view_itinerary(checklist, user_id)
    visible_expenses = get_visible_expenses_for_viewer(checklist, user_id)
    visible_hidden_sections = []
    for section in checklist.hidden_sections or []:
        if not section.startswith("backpack:"):
            visible_hidden_sections.append(section)
            continue
        try:
            backpack_id = int(section.split(":", 1)[1])
        except (TypeError, ValueError):
            continue
        backpack = next((item for item in (checklist.backpacks or []) if item.id == backpack_id), None)
        if backpack and not is_backpack_hidden_for_viewer(backpack, checklist, user_id):
            visible_hidden_sections.append(section)

    return ChecklistResponse(
        slug=checklist.slug,
        city=checklist.city,
        start_date=checklist.start_date,
        end_date=checklist.end_date,
        items=checklist.items,
        avg_temp=checklist.avg_temp,
        conditions=checklist.conditions,
        checked_items=checklist.checked_items or [],
        removed_items=checklist.removed_items or [],
        added_items=checklist.added_items or [],
        item_quantities=checklist.item_quantities or {},
        packed_quantities=checklist.packed_quantities or {},
        item_categories=checklist.item_categories or {},
        item_translations=checklist.item_translations or {},
        tg_user_id=checklist.tg_user_id,
        user_id=checklist.user_id,
        is_public=getattr(checklist, "is_public", True),
        origin_city=getattr(checklist, "origin_city", None),
        transports=getattr(checklist, "transports", None),
        trip_type=(checklist.trip_profile or {}).get("trip_type"),
        trip_profile=checklist.trip_profile or {},
        expense_budget_amount=getattr(checklist, "expense_budget_amount", None) if expenses_visible else None,
        expense_base_currency=getattr(checklist, "expense_base_currency", "RUB") or "RUB",
        daily_forecast=forecast,
        events=(checklist.events or []) if itinerary_visible else [],
        backpacks=visible_backpacks,
        expenses=visible_expenses,
        expense_summary=build_expense_summary(checklist, visible_expenses, expose_budget=expenses_visible),
        reviews=[
            build_trip_review_payload(review)
            for review in sorted(checklist.reviews or [], key=lambda item: item.created_at or datetime.min, reverse=True)
        ],
        invite_token=checklist.invite_token if user_id and is_checklist_participant(checklist, user_id) else None,
        hidden_sections=visible_hidden_sections,
    )


async def build_stats_payload(checklists, user_id: int):
    total_trips = len(checklists)
    total_days = 0
    trips_with_dates = 0
    upcoming = 0
    today = datetime.now().date()
    cities, countries = await collect_location_stats(checklists)

    for checklist in checklists:
        if checklist.start_date and checklist.end_date:
            days = (checklist.end_date - checklist.start_date).days + 1
            if days > 0:
                total_days += days
                trips_with_dates += 1

        if checklist.start_date and checklist.start_date > today:
            upcoming += 1

    return {
        "total_trips": total_trips,
        "total_days": total_days,
        "average_trip_days": round(total_days / trips_with_dates) if trips_with_dates else 0,
        "unique_cities": len(cities),
        "unique_countries": len(countries),
        "total_items": count_total_items_for_user(checklists, user_id),
        "upcoming_trips": upcoming,
    }


def build_feedback_stats_payload(checklists):
    removed_counts = {}
    added_counts = {}

    for checklist in checklists:
        for item in (checklist.removed_items or []):
            removed_counts[item] = removed_counts.get(item, 0) + 1
        for item in (checklist.added_items or []):
            added_counts[item] = added_counts.get(item, 0) + 1

    top_removed = sorted(removed_counts.items(), key=lambda x: -x[1])[:10]
    top_added = sorted(added_counts.items(), key=lambda x: -x[1])[:10]

    return {
        "top_removed": [{"item": key, "count": value} for key, value in top_removed],
        "top_added": [{"item": key, "count": value} for key, value in top_added],
    }


def build_follow_request_payloads(requests):
    result = []
    for req in requests:
        from_user_out = schemas.UserOut.model_validate(req.from_user)
        result.append(schemas.FollowRequestOut(
            id=req.id,
            from_user=from_user_out,
            status=req.status,
            created_at=req.created_at
        ))
    return result


def build_subscription_payloads(followers, following):
    following_ids = {user.id for user in following}

    enriched_followers = []
    for follower in followers:
        follower_out = schemas.UserOut.model_validate(follower)
        follower_out.is_following = follower.id in following_ids
        enriched_followers.append(follower_out)

    enriched_following = []
    for followed_user in following:
        followed_user_out = schemas.UserOut.model_validate(followed_user)
        followed_user_out.is_following = True
        enriched_following.append(followed_user_out)

    return enriched_followers, enriched_following


@app.get("/my-profile-bundle", response_model=dict)
async def get_my_profile_bundle(
    user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
):
    checklists = await get_all_user_checklists(db, user.id)
    followers = await crud.get_followers(db, user.id)
    following = await crud.get_following(db, user.id)
    follow_requests = await crud.get_pending_follow_requests(db, user.id)
    reviews = await crud.get_trip_reviews_by_user_id(db, user.id)

    stats, achievements = await asyncio.gather(
        build_stats_payload(checklists, user.id),
        compute_achievements(checklists),
    )
    feedback = build_feedback_stats_payload(checklists)
    enriched_followers, enriched_following = build_subscription_payloads(followers, following)

    return {
        "checklists": [schemas.ChecklistOut.model_validate(checklist) for checklist in checklists],
        "stats": stats,
        "achievements": achievements,
        "feedback": feedback,
        "reviews": [build_trip_review_payload(review) for review in reviews],
        "followers": enriched_followers,
        "following": enriched_following,
        "followRequests": build_follow_request_payloads(follow_requests),
    }


@app.get("/tma/bootstrap", response_model=dict)
async def get_tma_bootstrap(
    slug: Optional[str] = Query(default=None),
    user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
):
    checklists = await get_all_user_checklists(db, user.id)
    selected_checklist = None

    if slug:
        selected_checklist = next((item for item in checklists if item.slug == slug), None)

    if not selected_checklist and checklists:
        selected_checklist = sorted(
            checklists,
            key=lambda item: (
                item.start_date or date.max,
                item.end_date or date.max,
                item.id,
            ),
        )[0]

    return {
        "checklists": [schemas.ChecklistOut.model_validate(checklist) for checklist in checklists],
        "selected_slug": selected_checklist.slug if selected_checklist else "",
        "checklist": await build_checklist_response_payload(selected_checklist, user.id) if selected_checklist else None,
    }


@app.get("/my-achievements")
async def get_my_achievements(
    user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Достижения и уровень пользователя (включая совместные чеклисты)"""
    checklists = await get_all_user_checklists(db, user.id)
    return await compute_achievements(checklists)


# === Feature: Feedback Stats ===

@app.get("/my-feedback-stats")
async def get_my_feedback_stats(
    user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Статистика предпочтений: что чаще удаляют/добавляют (включая совместные)"""
    checklists = await get_all_user_checklists(db, user.id)
    return build_feedback_stats_payload(checklists)


@app.get("/my-stats", response_model=StatsResponse)
async def get_my_stats(
    user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Статистика путешествий пользователя (включая совместные)"""
    checklists = await get_all_user_checklists(db, user.id)
    return await build_stats_payload(checklists, user.id)


# === Feature: Calendar Export (.ics) ===

@app.get("/checklist/{slug}/calendar")
async def export_checklist_calendar(slug: str, db: AsyncSession = Depends(get_db)):
    """Экспорт чеклиста в .ics формат для добавления в календарь"""
    checklist = await crud.get_checklist_by_slug(db, slug)
    if not checklist:
        raise HTTPException(status_code=404, detail="Чеклист не найден")
    
    # Format items for description
    items_text = "\\n".join(f"- {item}" for item in (checklist.items or []))
    city = checklist.city or "Trip"
    start = checklist.start_date.strftime("%Y%m%d")
    end = (checklist.end_date + timedelta(days=1)).strftime("%Y%m%d")  # iCal end is exclusive
    now = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    
    ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Luggify//Trip Planner//EN
BEGIN:VEVENT
DTSTART;VALUE=DATE:{start}
DTEND;VALUE=DATE:{end}
SUMMARY:🧳 {city}
DESCRIPTION:Чеклист Luggify:\\n{items_text}
DTSTAMP:{now}
UID:{slug}@luggify.app
END:VEVENT
END:VCALENDAR"""
    
    return Response(
        content=ics_content,
        media_type="text/calendar",
        headers={"Content-Disposition": f'attachment; filename="luggify-{slug}.ics"'}
    )


# === Feature: Attractions (Google Places + Curated Fallback) ===

ATTRACTIONS_LOCKS = {}
ATTRACTIONS_CACHE_MAX_AGE_DAYS = 60
ATTRACTION_NAME_CACHE: dict[str, Optional[str]] = {}


# Топ достопримечательности для популярных городов (en.wikipedia article titles)
_CURATED = {
    "Paris": ["Eiffel Tower","Louvre","Notre-Dame de Paris","Arc de Triomphe","Sacré-Cœur, Paris","Musée d'Orsay","Palace of Versailles","Champs-Élysées","Panthéon, Paris","Sainte-Chapelle","Centre Pompidou","Les Invalides","Place de la Concorde","Palais Garnier","Pont Alexandre III"],
    "London": ["Tower of London","Buckingham Palace","British Museum","London Eye","Big Ben","Tower Bridge","Westminster Abbey","St Paul's Cathedral","Hyde Park, London","Trafalgar Square","Natural History Museum, London","Tate Modern","Palace of Westminster","Kensington Palace","Hampton Court Palace"],
    "Rome": ["Colosseum","Pantheon, Rome","Trevi Fountain","Roman Forum","Vatican Museums","St. Peter's Basilica","Sistine Chapel","Piazza Navona","Spanish Steps","Castel Sant'Angelo","Borghese Gallery","Piazza Venezia","Palatine Hill","Basilica di Santa Maria Maggiore","Aventine Hill"],
    "New York City": ["Statue of Liberty","Central Park","Empire State Building","Times Square","Brooklyn Bridge","Metropolitan Museum of Art","One World Trade Center","Rockefeller Center","Grand Central Terminal","High Line","Museum of Modern Art","Fifth Avenue","Broadway (Manhattan)","Wall Street","Chelsea Market"],
    "Tokyo": ["Sensō-ji","Meiji Shrine","Tokyo Skytree","Tokyo Tower","Shibuya Crossing","Imperial Palace, Tokyo","Shinjuku Gyoen","Ueno Park","Akihabara","Odaiba","Roppongi Hills","Harajuku","Ginza","Asakusa","Tsukiji fish market"],
    "Istanbul": ["Hagia Sophia","Blue Mosque","Topkapi Palace","Grand Bazaar","Basilica Cistern","Galata Tower","Dolmabahçe Palace","Süleymaniye Mosque","Bosphorus","Spice Bazaar","Maiden's Tower","Taksim Square","Istiklal Avenue","Chora Church","Pierre Loti"],
    "Barcelona": ["Sagrada Família","Park Güell","Casa Batlló","La Rambla, Barcelona","Casa Milà","Gothic Quarter, Barcelona","Camp Nou","Palau de la Música Catalana","Barcelona Cathedral","Magic Fountain of Montjuïc","Barceloneta","Montjuïc","Tibidabo","Port Vell","Picasso Museum (Barcelona)"],
    "Berlin": ["Brandenburg Gate","Berlin Wall","Reichstag building","Museum Island","Checkpoint Charlie","East Side Gallery","Berlin Cathedral","Alexanderplatz","Berlin Television Tower","Charlottenburg Palace","Pergamon Museum","Tiergarten","Potsdamer Platz","Victory Column (Berlin)","Holocaust memorial (Berlin)"],
    "Dubai": ["Burj Khalifa","Palm Jumeirah","Dubai Mall","Burj Al Arab","Dubai Marina","Dubai Fountain","Museum of the Future","Gold Souk","Dubai Frame","Jumeirah Mosque","Mall of the Emirates","Al Fahidi Historical Neighbourhood","Dubai Creek","Miracle Garden","Global Village"],
    "Moscow": ["Red Square","Moscow Kremlin","Saint Basil's Cathedral","Bolshoi Theatre","Moscow Metro","Tretyakov Gallery","Cathedral of Christ the Saviour","Arbat Street","GUM (department store)","Gorky Park (Moscow)","Sparrow Hills","Novodevichy Convent","VDNKh","Pushkin Museum","Kolomenskoye"],
    "Saint Petersburg": ["Hermitage Museum","Church of the Savior on Blood","Peter and Paul Fortress","Saint Isaac's Cathedral","Peterhof Palace","Winter Palace","Nevsky Prospect","Mariinsky Theatre","Catherine Palace","Russian Museum","Palace Square","Kazan Cathedral, Saint Petersburg","Summer Garden","Bronze Horseman","Alexander Column"],
    "Prague": ["Charles Bridge","Prague Castle","Old Town Square (Prague)","Prague astronomical clock","St. Vitus Cathedral","Wenceslas Square","Dancing House","Lennon Wall","Petřín","Powder Tower","Josefov","Vyšehrad","National Museum (Prague)","Municipal House (Prague)","Old Jewish Cemetery, Prague"],
    "Amsterdam": ["Rijksmuseum","Anne Frank House","Van Gogh Museum","Royal Palace of Amsterdam","Dam Square","Vondelpark","Jordaan","Heineken Experience","Magere Brug","Westerkerk","NEMO (museum)","Stedelijk Museum Amsterdam","Bloemenmarkt","Museumplein","Begijnhof, Amsterdam"],
    "Vienna": ["Schönbrunn Palace","St. Stephen's Cathedral, Vienna","Hofburg","Belvedere, Vienna","Vienna State Opera","Kunsthistorisches Museum","Prater","Naschmarkt","Austrian Parliament Building","Albertina","MuseumsQuartier","Rathaus, Vienna","Ringstraße","Graben, Vienna","Vienna Secession"],
    "Bangkok": ["Grand Palace (Bangkok)","Wat Arun","Wat Pho","Khao San Road","Temple of the Emerald Buddha","Jim Thompson House","Lumpini Park","Erawan Shrine","Chatuchak Weekend Market","Chinatown, Bangkok","Asiatique The Riverfront","Wat Saket","MBK Center","Siam Paragon","Floating market"],
    "Beijing": ["Forbidden City","Great Wall of China","Temple of Heaven","Summer Palace","Tiananmen Square","Ming tombs","Beihai Park","Lama Temple","798 Art District","Jingshan Park","Hutong","National Museum of China","Dashilan","Olympic Green","Drum Tower of Beijing"],
    "Sydney": ["Sydney Opera House","Sydney Harbour Bridge","Bondi Beach","Darling Harbour","Taronga Zoo","Royal Botanic Garden, Sydney","Circular Quay","The Rocks, Sydney","Manly Beach","Sydney Tower","Art Gallery of New South Wales","Luna Park Sydney","Barangaroo","Museum of Contemporary Art Australia","Paddy's Markets"],
    "Cairo": ["Great Pyramid of Giza","Egyptian Museum","Great Sphinx of Giza","Khan el-Khalili","Cairo Citadel","Al-Azhar Mosque","Mosque of Muhammad Ali","Cairo Tower","Coptic Cairo","Al-Muizz Street","Tahrir Square","Baron Empain Palace","Hanging Church (Cairo)","Giza pyramid complex","Museum of Islamic Art, Cairo"],
    "Singapore": ["Marina Bay Sands","Gardens by the Bay","Merlion","Sentosa","Singapore Zoo","Orchard Road","Singapore Botanic Gardens","Chinatown, Singapore","Clarke Quay","Little India, Singapore","ArtScience Museum","Raffles Hotel","Esplanade – Theatres on the Bay","National Gallery Singapore","Singapore Flyer"],
    "Athens": ["Acropolis of Athens","Parthenon","Ancient Agora of Athens","Erechtheion","Plaka","Monastiraki","Syntagma Square","Panathenaic Stadium","Acropolis Museum","Temple of Hephaestus","Lycabettus","National Archaeological Museum, Athens","Hadrian's Arch (Athens)","Temple of Olympian Zeus, Athens","Odeon of Herodes Atticus"],
    "Lisbon": ["Belém Tower","Jerónimos Monastery","Praça do Comércio","Alfama","Santa Justa Lift","São Jorge Castle","Tram 28 (Lisbon)","Pastéis de Belém","Ponte 25 de Abril","LX Factory","Oceanário de Lisboa","Pantheon of Portugal","Time Out Market","Bairro Alto","Rossio"],
    "Budapest": ["Hungarian Parliament Building","Buda Castle","Széchenyi thermal bath","Fisherman's Bastion","Chain Bridge (Budapest)","St. Stephen's Basilica (Budapest)","Heroes' Square (Budapest)","Matthias Church","Margaret Island","Great Market Hall (Budapest)","Citadella","Gellért thermal bath","Dohány Street Synagogue","Andrássy Avenue","Vajdahunyad Castle"],
    "Warsaw": ["Royal Castle, Warsaw","Old Town Market Place, Warsaw","Wilanów Palace","Palace of Culture and Science","Łazienki Park","Warsaw Uprising Museum","St. John's Archcathedral, Warsaw","Copernicus Science Centre","National Museum, Warsaw","Saxon Garden","Sigismund's Column","Warsaw Barbican","POLIN Museum","Warsaw Old Town","Belweder"],
    "Madrid": ["Royal Palace of Madrid","Prado Museum","Retiro Park","Puerta del Sol","Plaza Mayor, Madrid","Reina Sofía","Thyssen-Bornemisza Museum","Temple of Debod","Gran Vía","Almudena Cathedral","Santiago Bernabéu Stadium","Cibeles Palace","Royal Botanical Garden of Madrid","Plaza de Cibeles","Puerta de Alcalá"],
    "Milan": ["Milan Cathedral","Galleria Vittorio Emanuele II","Santa Maria delle Grazie","Sforza Castle","Pinacoteca di Brera","La Scala","Navigli","San Siro","Basilica of Sant'Ambrogio","Piazza del Duomo, Milan","Quadrilatero della moda","Cimitero Monumentale di Milano","Pinacoteca Ambrosiana","Arco della Pace","Piazza Mercanti"],
    "Munich": ["Marienplatz","Nymphenburg Palace","Englischer Garten","BMW Welt","Frauenkirche, Munich","Deutsches Museum","Viktualienmarkt","Munich Residenz","Allianz Arena","Hofbräuhaus","Alte Pinakothek","Olympiapark, Munich","Asamkirche","St. Peter's Church, Munich","Karlsplatz"],
    "Florence": ["Florence Cathedral","Uffizi","Ponte Vecchio","Palazzo Pitti","Piazzale Michelangelo","Galleria dell'Accademia","Palazzo Vecchio","Piazza della Signoria","Boboli Gardens","Basilica of Santa Croce, Florence","Basilica of San Lorenzo, Florence","Bargello","Baptistery of Saint John (Florence)","Basilica di Santa Maria Novella","Piazza della Repubblica, Florence"],
    "Geneva": ["Jet d'Eau","St. Pierre Cathedral","Palace of Nations","Place du Bourg-de-Four","Broken Chair","Patek Philippe Museum","Reformation Wall","Bains des Pâquis","Parc des Bastions","Museum of Art and History, Geneva","Brunswick Monument","Jardin Anglais","Conservatory and Botanical Garden of the City of Geneva","Tavel House","Île Rousseau"],
    "Edinburgh": ["Edinburgh Castle","Royal Mile","Arthur's Seat","Holyrood Palace","Scott Monument","Calton Hill","National Museum of Scotland","St Giles' Cathedral","Princes Street","Edinburgh Old Town","Greyfriars Kirkyard","Royal Botanic Garden Edinburgh","Camera Obscura, Edinburgh","Edinburgh Zoo","Dean Village"],
    "Copenhagen": ["Tivoli Gardens","The Little Mermaid (statue)","Nyhavn","Amalienborg","Christiansborg Palace","Rosenborg Castle","Strøget","Christiania (district)","Round Tower (Copenhagen)","National Museum of Denmark","Church of Our Saviour, Copenhagen","Ny Carlsberg Glyptotek","Frederiksberg Garden","Kastellet, Copenhagen","Copenhagen Opera House"],
    "Oslo": ["Oslo Opera House","Vigeland sculpture park","Viking Ship Museum (Oslo)","Akershus Fortress","Holmenkollbakken","Munch Museum","Oslo City Hall","Royal Palace, Oslo","Aker Brygge","Karl Johans gate","Norsk Folkemuseum","Bygdøy","Oslo Cathedral","National Gallery (Oslo)","Fram Museum"],
    "Stockholm": ["Vasa Museum","Gamla stan","Stockholm Palace","Stockholm City Hall","Skansen","ABBA The Museum","Djurgården","Drottningholm Palace","Storkyrkan","Moderna Museet","Fotografiska","Nobel Prize Museum","Stadshuset","Södermalm","Stortorget, Stockholm"],
    "Helsinki": ["Helsinki Cathedral","Suomenlinna","Temppeliaukio Church","Senate Square, Helsinki","Sibelius Monument","Ateneum","Uspenski Cathedral","Market Square, Helsinki","Esplanadi","Kiasma","Oodi","Helsinki Olympic Stadium","Seurasaari","Hakaniemi Market Hall","Kaivopuisto"],
    "Zurich": ["Grossmünster","Lake Zurich","Bahnhofstrasse","Fraumünster","Old Town, Zurich","Swiss National Museum","Kunsthaus Zürich","Lindenhof hill, Zurich","Zurich Zoo","Uetliberg","FIFA World Football Museum","St. Peter, Zurich","Zürichsee","Pavillon Le Corbusier","Botanical Garden of the University of Zurich"],
    "Porto": ["Livraria Lello","Clérigos Tower","Dom Luís I Bridge","Ribeira, Porto","São Bento railway station","Porto Cathedral","Palácio da Bolsa","Crystal Palace Gardens","Serralves","Igreja do Carmo (Porto)","Foz do Douro","Majestic Café","Church of São Francisco (Porto)","Jardim do Morro","Port wine"],
    "Dubrovnik": ["Walls of Dubrovnik","Stradun (street)","Dubrovnik Cable Car","Rector's Palace, Dubrovnik","Lokrum","Fort Lovrijenac","Sponza Palace","Pile Gate","Dominican Monastery, Dubrovnik","Banje Beach","Franciscan Church and Monastery, Dubrovnik","Dubrovnik Cathedral","Trsteno Arboretum","Buža Bar","Orlando's Column, Dubrovnik"],
    "Krakow": ["Wawel Castle","Main Market Square, Kraków","Cloth Hall, Kraków","St. Mary's Basilica, Kraków","Kazimierz","Auschwitz concentration camp","Wieliczka Salt Mine","Wawel Cathedral","Planty Park","Schindler's Factory","Collegium Maius","Barbican of Kraków","Floriańska Street","National Museum in Kraków","Kościuszko Mound"],
    "Seoul": ["Gyeongbokgung","Bukchon Hanok Village","N Seoul Tower","Myeongdong","Changdeokgung","Dongdaemun Design Plaza","Gwanghwamun","Insadong","Lotte World Tower","War Memorial of Korea","Namdaemun Market","Jogyesa","Cheonggyecheon","Itaewon","COEX Mall"],
    "Hong Kong": ["Victoria Peak","Victoria Harbour","Star Ferry","Tian Tan Buddha","Wong Tai Sin Temple","Avenue of Stars, Hong Kong","Temple Street Night Market","Hong Kong Disneyland","Ngong Ping 360","Man Mo Temple","Repulse Bay","Lan Kwai Fong","Chi Lin Nunnery","Ladies' Market","Ocean Park Hong Kong"],
    "Kuala Lumpur": ["Petronas Towers","Batu Caves","KL Tower","Merdeka Square, Kuala Lumpur","Petaling Street","Islamic Arts Museum Malaysia","Sultan Abdul Samad Building","Thean Hou Temple","Perdana Botanical Garden","National Mosque of Malaysia","Central Market, Kuala Lumpur","Aquaria KLCC","Bukit Bintang","National Museum of Malaysia","Istana Negara, Jalan Istana"],
    "Hanoi": ["Hoan Kiem Lake","Temple of Literature, Hanoi","Ho Chi Minh Mausoleum","Old Quarter (Hanoi)","One Pillar Pagoda","Vietnam Museum of Ethnology","Hoa Lo Prison","Long Biên Bridge","West Lake (Hanoi)","Hanoi Opera House","St. Joseph's Cathedral, Hanoi","Tran Quoc Pagoda","Imperial Citadel of Thăng Long","Ngoc Son Temple","Dong Xuan Market"],
    "Delhi": ["Red Fort","India Gate","Humayun's Tomb","Qutub Minar","Lotus Temple","Jama Masjid, Delhi","Akshardham (Delhi)","Raj Ghat","Chandni Chowk","Rashtrapati Bhavan","Connaught Place","Gurudwara Bangla Sahib","Lodhi Garden","Purana Qila","Jantar Mantar, New Delhi"],
    "Mumbai": ["Gateway of India","Chhatrapati Shivaji Maharaj Terminus","Marine Drive, Mumbai","Elephanta Caves","Haji Ali Dargah","Siddhivinayak Temple","Bandra–Worli Sea Link","Chhatrapati Shivaji Maharaj Vastu Sangrahalaya","Colaba Causeway","Juhu Beach","Dharavi","Banganga Tank","Mani Bhavan","Crawford Market","Flora Fountain"],
    "Los Angeles": ["Hollywood Sign","Griffith Observatory","Getty Center","Hollywood Walk of Fame","Santa Monica Pier","Universal Studios Hollywood","Venice Beach, Los Angeles","The Broad","Los Angeles County Museum of Art","TCL Chinese Theatre","Walt Disney Concert Hall","Rodeo Drive","Sunset Boulevard","Dodger Stadium","Natural History Museum of Los Angeles County"],
    "San Francisco": ["Golden Gate Bridge","Alcatraz Island","Fisherman's Wharf, San Francisco","Lombard Street","Chinatown, San Francisco","Palace of Fine Arts","Pier 39","Cable car (railway)","Golden Gate Park","Painted ladies","Coit Tower","Ghirardelli Square","Twin Peaks (San Francisco)","San Francisco Museum of Modern Art","Exploratorium"],
    "Chicago": ["Millennium Park","Cloud Gate","Art Institute of Chicago","Willis Tower","Navy Pier","Magnificent Mile","Chicago Riverwalk","Field Museum of Natural History","Wrigley Field","Museum of Science and Industry (Chicago)","Grant Park (Chicago)","John Hancock Center","Buckingham Fountain","Lincoln Park Zoo","Water Tower (Chicago)"],
    "Toronto": ["CN Tower","Royal Ontario Museum","Distillery District","Ripley's Aquarium of Canada","Art Gallery of Ontario","St. Lawrence Market","Casa Loma","Toronto Islands","Nathan Phillips Square","Kensington Market, Toronto","High Park","Hockey Hall of Fame","Harbourfront Centre","Dundas Square","Bata Shoe Museum"],
    "Mexico City": ["Zócalo","Palacio de Bellas Artes","National Museum of Anthropology","Chapultepec","Coyoacán","Frida Kahlo Museum","Templo Mayor","Basilica of Our Lady of Guadalupe","Paseo de la Reforma","Xochimilco","National Palace (Mexico)","Palace of Chapultepec","Torre Latinoamericana","Angel of Independence","Ciudad Universitaria"],
    "Rio de Janeiro": ["Christ the Redeemer","Sugarloaf Mountain","Copacabana","Ipanema","Maracanã Stadium","Escadaria Selarón","Santa Teresa, Rio de Janeiro","Tijuca National Park","Lapa, Rio de Janeiro","Jardim Botânico, Rio de Janeiro","Museum of Tomorrow","Arcos da Lapa","Pedra da Gávea","Praia Vermelha","Parque Lage"],
    "Buenos Aires": ["Plaza de Mayo","Casa Rosada","La Boca","Recoleta Cemetery","Teatro Colón","Obelisco de Buenos Aires","San Telmo, Buenos Aires","Puerto Madero","Palermo, Buenos Aires","Caminito","Museo Nacional de Bellas Artes","Avenida 9 de Julio","Floralis Genérica","Palacio Barolo","El Ateneo Grand Splendid"],
    "Cape Town": ["Table Mountain","Robben Island","V&A Waterfront","Cape of Good Hope","Kirstenbosch National Botanical Garden","Boulders Beach","Bo-Kaap","Cape Point","Chapman's Peak","District Six Museum","Castle of Good Hope","Camps Bay","Constantia (Cape Town)","Groot Constantia","Two Oceans Aquarium"],
    "Marrakech": ["Djemaa el-Fna","Bahia Palace","Majorelle Garden","Koutoubia","Saadian Tombs","Ben Youssef Madrasa","Menara gardens","El Badi Palace","Marrakech Museum","Mouassine Mosque","Dar Si Said Museum","Tanneries of Marrakech","Agdal Gardens","Bab Agnaou","Le Jardin Secret"],
    "Melbourne": ["Federation Square","Royal Botanic Gardens, Melbourne","Melbourne Cricket Ground","Flinders Street Station","National Gallery of Victoria","Queen Victoria Market","Hosier Lane","Melbourne Museum","St Paul's Cathedral, Melbourne","Eureka Tower","Brighton Bathing Boxes","Melbourne Zoo","Luna Park, Melbourne","State Library of Victoria","Great Ocean Road"],
    "Kazan": ["Kazan Kremlin","Qolşärif Mosque","Temple of All Religions","Bauman Street","Kazan Cathedral (Kazan)","Kazan Arena","Kazan Family Center","Millennium Bridge (Kazan)","National Museum of the Republic of Tatarstan","Palace of Farmers","Söyembikä Tower","Riviera Aquapark","Kazan Kremlin Annunciation Cathedral","Tatar Academic State Opera and Ballet Theatre","Old Tatar Quarter"],
    "Sochi": ["Sochi Olympic Park","Rosa Khutor","Sochi Park","Krasnaya Polyana","Skypark AJ Hackett Sochi","Fisht Olympic Stadium","Akhun Mountain","Riviera Park (Sochi)","Sochi Art Museum","Dagomys Tea Plantation","Stalin's dacha","Sochi Arboretum","Orekhovsky Waterfall","Sochi Discovery World Aquarium","Agura Waterfalls"],
}

_CURATED_CITY_ALIASES = {
    "амстердам": "Amsterdam",
    "афины": "Athens",
    "барселона": "Barcelona",
    "берлин": "Berlin",
    "будапешт": "Budapest",
    "буэнос айрес": "Buenos Aires",
    "варшава": "Warsaw",
    "вена": "Vienna",
    "дубай": "Dubai",
    "единбург": "Edinburgh",
    "казань": "Kazan",
    "каир": "Cairo",
    "копенгаген": "Copenhagen",
    "краков": "Krakow",
    "лиссабон": "Lisbon",
    "лондон": "London",
    "мадрид": "Madrid",
    "милан": "Milan",
    "москва": "Moscow",
    "мюнхен": "Munich",
    "нью йорк": "New York City",
    "нью-йорк": "New York City",
    "осло": "Oslo",
    "париж": "Paris",
    "пекин": "Beijing",
    "петербург": "Saint Petersburg",
    "прага": "Prague",
    "рим": "Rome",
    "санкт петербург": "Saint Petersburg",
    "санкт-петербург": "Saint Petersburg",
    "сеул": "Seoul",
    "сингапур": "Singapore",
    "сочи": "Sochi",
    "стамбул": "Istanbul",
    "стокгольм": "Stockholm",
    "токио": "Tokyo",
    "флоренция": "Florence",
    "женева": "Geneva",
    "хельсинки": "Helsinki",
    "чикаго": "Chicago",
    "эдинбург": "Edinburgh",
}


def _normalize_city_lookup(value: str) -> str:
    return re.sub(r"[^0-9a-zа-я]+", " ", (value or "").replace("ё", "е").casefold()).strip()


_CURATED_LOOKUP = {_normalize_city_lookup(name): name for name in _CURATED}
for alias, target in _CURATED_CITY_ALIASES.items():
    _CURATED_LOOKUP[_normalize_city_lookup(alias)] = target


def _needs_attraction_image_refresh(image_url: str | None) -> bool:
    return not image_url


_LATIN_ATTRACTION_RE = re.compile(r"[A-Za-z]")
_CYRILLIC_ATTRACTION_RE = re.compile(r"[А-Яа-яЁё]")
_ATTRACTION_RU_NAME_OVERRIDES = {
    "parliament viewpoint": "Смотровая на парламент",
    "széchenyi thermal bath": "Купальни Сеченьи",
    "szechenyi thermal bath": "Купальни Сеченьи",
}
_ATTRACTION_RU_WORDS = {
    "academy": "академия",
    "arch": "арка",
    "avenue": "авеню",
    "basilica": "базилика",
    "bath": "купальня",
    "baths": "купальни",
    "bridge": "мост",
    "castle": "замок",
    "cathedral": "собор",
    "chain": "цепной",
    "church": "церковь",
    "citadel": "цитадель",
    "fort": "форт",
    "fortress": "крепость",
    "garden": "сад",
    "gardens": "сады",
    "hall": "зал",
    "heroes": "героев",
    "hill": "холм",
    "island": "остров",
    "liberty": "свободы",
    "market": "рынок",
    "museum": "музей",
    "palace": "дворец",
    "parliament": "парламент",
    "park": "парк",
    "princess": "принцесса",
    "saint": "святого",
    "square": "площадь",
    "statue": "статуя",
    "thermal": "термальные",
    "tower": "башня",
    "viewpoint": "смотровая",
}
_LATIN_TO_RU_DIGRAPHS = {
    "shch": "щ",
    "sch": "щ",
    "yo": "ё",
    "zh": "ж",
    "kh": "х",
    "ts": "ц",
    "ch": "ч",
    "sh": "ш",
    "yu": "ю",
    "ya": "я",
    "ye": "е",
    "yi": "и",
    "iy": "ий",
}
_LATIN_TO_RU_CHARS = {
    "a": "а",
    "b": "б",
    "c": "к",
    "d": "д",
    "e": "е",
    "f": "ф",
    "g": "г",
    "h": "х",
    "i": "и",
    "j": "й",
    "k": "к",
    "l": "л",
    "m": "м",
    "n": "н",
    "o": "о",
    "p": "п",
    "q": "к",
    "r": "р",
    "s": "с",
    "t": "т",
    "u": "у",
    "v": "в",
    "w": "в",
    "x": "кс",
    "y": "и",
    "z": "з",
}


def _is_google_attraction_image(image_url: str | None) -> bool:
    image = str(image_url or "").strip().lower()
    return (
        "googleusercontent.com/place-photos/" in image
        or "googleusercontent.com/places/" in image
    )


def _is_google_place_photo(image_url: str | None) -> bool:
    return _is_google_attraction_image(image_url)


def _needs_ru_attraction_name_localization(name: str | None, lang: str) -> bool:
    normalized_name = str(name or "").strip()
    if lang != "ru" or not normalized_name:
        return False
    return bool(_LATIN_ATTRACTION_RE.search(normalized_name)) and not bool(
        _CYRILLIC_ATTRACTION_RE.search(normalized_name)
    )


def _transliterate_latin_token_to_ru(token: str) -> str:
    normalized = str(token or "").strip()
    if not normalized:
        return ""

    lower = normalized.lower()
    result: list[str] = []
    index = 0
    while index < len(lower):
        matched = False
        for source, target in sorted(_LATIN_TO_RU_DIGRAPHS.items(), key=lambda item: len(item[0]), reverse=True):
            if lower.startswith(source, index):
                result.append(target)
                index += len(source)
                matched = True
                break
        if matched:
            continue
        result.append(_LATIN_TO_RU_CHARS.get(lower[index], lower[index]))
        index += 1

    transliterated = "".join(result)
    if normalized[0].isupper():
        transliterated = transliterated.capitalize()
    return transliterated


def _translate_or_transliterate_attraction_token(token: str) -> str:
    normalized = re.sub(r"[^a-zA-Z]+", "", str(token or "")).strip().lower()
    if not normalized:
        return str(token or "").strip()
    return _ATTRACTION_RU_WORDS.get(normalized) or _transliterate_latin_token_to_ru(token)


def _fallback_translate_attraction_name_to_ru(name: str | None) -> str:
    normalized_name = str(name or "").strip()
    if not normalized_name:
        return ""

    override = _ATTRACTION_RU_NAME_OVERRIDES.get(normalized_name.casefold())
    if override:
        return override

    patterns = [
        (re.compile(r"^(?P<base>.+?)\s+viewpoint$", re.IGNORECASE), lambda base: f"Смотровая {base}"),
        (re.compile(r"^(?P<base>.+?)\s+bridge$", re.IGNORECASE), lambda base: f"{base} мост"),
        (re.compile(r"^(?P<base>.+?)\s+castle$", re.IGNORECASE), lambda base: f"Замок {base}"),
        (re.compile(r"^(?P<base>.+?)\s+palace$", re.IGNORECASE), lambda base: f"Дворец {base}"),
        (re.compile(r"^(?P<base>.+?)\s+basilica$", re.IGNORECASE), lambda base: f"Базилика {base}"),
        (re.compile(r"^(?P<base>.+?)\s+cathedral$", re.IGNORECASE), lambda base: f"Собор {base}"),
        (re.compile(r"^(?P<base>.+?)\s+church$", re.IGNORECASE), lambda base: f"Церковь {base}"),
        (re.compile(r"^(?P<base>.+?)\s+square$", re.IGNORECASE), lambda base: f"Площадь {base}"),
    ]
    for pattern, formatter in patterns:
        match = pattern.match(normalized_name)
        if not match:
            continue
        translated_base = " ".join(
            _translate_or_transliterate_attraction_token(part)
            for part in match.group("base").split()
            if part.strip()
        ).strip()
        return formatter(translated_base).strip()

    translated_tokens = []
    for token in normalized_name.split():
        translated_tokens.append(_translate_or_transliterate_attraction_token(token))
    return " ".join(token for token in translated_tokens if token).strip()


def _extract_google_maps_cid(link: str | None) -> str:
    raw_link = str(link or "").strip()
    if not raw_link:
        return ""
    try:
        parsed = urlparse(raw_link)
        return (parse_qs(parsed.query).get("cid") or [""])[0].strip()
    except Exception:
        return ""


def _normalize_attraction_key(value: str | None) -> str:
    return re.sub(r"\s+", " ", str(value or "").casefold()).strip()


def _is_admin_attraction_image(attraction: dict | None) -> bool:
    if not isinstance(attraction, dict):
        return False
    return attraction.get("image_source") == "admin" or attraction.get("admin_image") is True


def _attraction_matches_target(attraction: dict, target_name: str, target_link: str | None) -> bool:
    current_link = str((attraction or {}).get("link") or "").strip()
    current_cid = _extract_google_maps_cid(current_link)
    target_cid = _extract_google_maps_cid(target_link)
    if current_cid and target_cid and current_cid == target_cid:
        return True
    if current_link and target_link and current_link == target_link:
        return True
    return _normalize_attraction_key((attraction or {}).get("name")) == _normalize_attraction_key(target_name)


def _cached_attractions_need_google_refresh(attractions: list[dict]) -> bool:
    if not attractions:
        return True

    has_preferred_photo = False
    for attraction in attractions:
        image = str((attraction or {}).get("image") or "").strip()
        if not image:
            return True
        if _is_google_place_photo(image) or _is_admin_attraction_image(attraction):
            has_preferred_photo = True

    return not has_preferred_photo


def _cached_attractions_need_name_refresh(attractions: list[dict], lang: str) -> bool:
    if lang != "ru":
        return False
    return any(
        _needs_ru_attraction_name_localization((attraction or {}).get("name"), lang)
        for attraction in (attractions or [])
    )


_COMMERCIAL_ATTRACTION_RE = re.compile(
    r"(cruise|sightseeing|guided|tour|tickets?|boat trip|river cruise|package|excursion|"
    r"экскурс|тур(ы|ы\b|а\b)?|круиз|билет|прогулк|корабл|лодк)",
    re.IGNORECASE,
)
_NON_ATTRACTION_EVENT_RE = re.compile(
    r"(murder|kidnapp|death of|assassination|biography|"
    r"убийств|похищени|биографи|смерть|казнь|теракт|нападени|война|битва)",
    re.IGNORECASE,
)
_ATTRACTION_NAME_HINT_RE = re.compile(
    r"(museum|palace|castle|bridge|cathedral|church|square|park|tower|temple|"
    r"fort|fortress|monastery|basilica|garden|gate|opera|theatre|mosque|market|"
    r"музе|дворец|замок|мост|собор|церков|площад|парк|башн|храм|крепост|монастыр|"
    r"базилик|сад|ворот|театр|мечет|рынок|набереж|фонтан|галере|усадьб|арк)",
    re.IGNORECASE,
)


def _is_obviously_non_attraction_name(name: str | None) -> bool:
    raw_name = str(name or "").strip()
    if not raw_name:
        return True

    if _NON_ATTRACTION_EVENT_RE.search(raw_name):
        return True

    if _ATTRACTION_NAME_HINT_RE.search(raw_name):
        return False

    if "," in raw_name:
        left, right = [part.strip() for part in raw_name.split(",", 1)]
        if left and right:
            left_words = [word for word in re.split(r"[\s-]+", left) if word]
            right_words = [word for word in re.split(r"[\s-]+", right) if word]
            if 1 <= len(left_words) <= 3 and 1 <= len(right_words) <= 3:
                if all(re.fullmatch(r"[A-Za-zА-Яа-яЁё.'’]+", word) for word in left_words + right_words):
                    return True

    return False


def _sanitize_attractions(attractions: list[dict], limit: int) -> tuple[list[dict], bool]:
    sanitized: list[dict] = []
    seen_names: set[str] = set()
    changed = False

    for attraction in attractions or []:
        name = str((attraction or {}).get("name") or "").strip()
        if not name:
            changed = True
            continue

        normalized_name = re.sub(r"\s+", " ", name.casefold()).strip()
        if normalized_name in seen_names:
            changed = True
            continue

        if _COMMERCIAL_ATTRACTION_RE.search(name):
            changed = True
            continue
        if _is_obviously_non_attraction_name(name):
            changed = True
            continue

        seen_names.add(normalized_name)
        sanitized.append(attraction)

        if len(sanitized) >= max(limit, 1):
            break

    if len(sanitized) != len(attractions or []):
        changed = True

    return sanitized, changed


def _merge_attractions(primary: list[dict], secondary: list[dict], limit: int) -> list[dict]:
    merged: list[dict] = []
    seen_names: set[str] = set()

    for source in (primary or [], secondary or []):
        for attraction in source:
            name = str((attraction or {}).get("name") or "").strip()
            if not name:
                continue
            normalized_name = re.sub(r"\s+", " ", name.casefold()).strip()
            if normalized_name in seen_names:
                continue
            if _COMMERCIAL_ATTRACTION_RE.search(name):
                continue
            if _is_obviously_non_attraction_name(name):
                continue

            seen_names.add(normalized_name)
            merged.append(attraction)
            if len(merged) >= max(limit, 1):
                return merged

    return merged


def _finalize_attractions(attractions: list[dict], limit: int) -> list[dict]:
    finalized: list[dict] = []
    seen_names: set[str] = set()
    seen_links: set[str] = set()
    seen_images: set[str] = set()

    for attraction in attractions or []:
        name = str((attraction or {}).get("name") or "").strip()
        link = str((attraction or {}).get("link") or "").strip()
        image = str((attraction or {}).get("image") or "").strip()
        normalized_name = re.sub(r"\s+", " ", name.casefold()).strip()

        if not name or _COMMERCIAL_ATTRACTION_RE.search(name) or _is_obviously_non_attraction_name(name):
            continue
        if normalized_name and normalized_name in seen_names:
            continue
        if link and link in seen_links:
            continue
        if image and image in seen_images:
            continue

        if normalized_name:
            seen_names.add(normalized_name)
        if link:
            seen_links.add(link)
        if image:
            seen_images.add(image)
        finalized.append(attraction)

        if len(finalized) >= max(limit, 1):
            break

    return finalized


async def _restore_google_images_from_cache(
    db: AsyncSession,
    city_name: str,
    cache_key: str,
    attractions: list[dict],
) -> tuple[list[dict], bool]:
    if not attractions:
        return attractions, False

    normalized_city = city_name.strip().lower()
    rows = await db.execute(
        select(models.CityAttraction).where(models.CityAttraction.city_name.like(f"{normalized_city}_%"))
    )
    cached_variants = rows.scalars().all()

    admin_by_cid: dict[str, dict[str, str]] = {}
    admin_by_link: dict[str, dict[str, str]] = {}
    admin_by_name: dict[str, dict[str, str]] = {}
    google_by_link: dict[str, str] = {}
    google_by_name: dict[str, str] = {}
    for variant in cached_variants:
        if not variant or not variant.data:
            continue
        for item in variant.data:
            image = str((item or {}).get("image") or "").strip()
            if not image:
                continue
            if not _is_google_attraction_image(image):
                if not _is_admin_attraction_image(item):
                    continue
                link = str((item or {}).get("link") or "").strip()
                cid = _extract_google_maps_cid(link)
                name = _normalize_attraction_key((item or {}).get("name"))
                admin_payload = {
                    "image": image,
                    "image_position": str((item or {}).get("image_position") or "center center"),
                }
                if cid and cid not in admin_by_cid:
                    admin_by_cid[cid] = admin_payload
                if link and link not in admin_by_link:
                    admin_by_link[link] = admin_payload
                if name and name not in admin_by_name:
                    admin_by_name[name] = admin_payload
                continue
            link = str((item or {}).get("link") or "").strip()
            name = _normalize_attraction_key((item or {}).get("name"))
            if link and link not in google_by_link:
                google_by_link[link] = image
            if name and name not in google_by_name:
                google_by_name[name] = image

    updated_items: list[dict] = []
    changed = False
    for attraction in attractions:
        next_item = dict(attraction)
        current_image = str(attraction.get("image") or "").strip()
        if _is_admin_attraction_image(attraction):
            updated_items.append(next_item)
            continue

        link = str(attraction.get("link") or "").strip()
        cid = _extract_google_maps_cid(link)
        name_key = _normalize_attraction_key(attraction.get("name"))
        admin_replacement = admin_by_cid.get(cid) or admin_by_link.get(link) or admin_by_name.get(name_key)
        if not admin_replacement and _is_google_attraction_image(current_image):
            updated_items.append(next_item)
            continue
        replacement = (
            admin_replacement.get("image")
            if admin_replacement
            else google_by_link.get(link) or google_by_name.get(name_key)
        )
        replacement_position = admin_replacement.get("image_position") if admin_replacement else None
        if replacement and (
            replacement != current_image
            or (replacement_position and next_item.get("image_position") != replacement_position)
        ):
            next_item["image"] = replacement
            if admin_replacement:
                next_item["image_position"] = replacement_position or "center center"
                next_item["image_source"] = "admin"
                next_item["admin_image"] = True
            changed = True
        updated_items.append(next_item)

    return updated_items, changed


async def _restore_localized_names_from_cache(
    db: AsyncSession,
    city_name: str,
    attractions: list[dict],
    lang: str,
) -> tuple[list[dict], bool]:
    if lang != "ru" or not attractions:
        return attractions, False

    normalized_city = city_name.strip().lower()
    rows = await db.execute(
        select(models.CityAttraction).where(models.CityAttraction.city_name.like(f"{normalized_city}_%"))
    )
    cached_variants = rows.scalars().all()

    localized_by_cid: dict[str, str] = {}
    localized_by_link: dict[str, str] = {}
    for variant in cached_variants:
        if not variant or not variant.data:
            continue
        for item in variant.data:
            cached_name = str((item or {}).get("name") or "").strip()
            if not cached_name or _needs_ru_attraction_name_localization(cached_name, "ru"):
                continue
            cached_link = str((item or {}).get("link") or "").strip()
            cached_cid = _extract_google_maps_cid(cached_link)
            if cached_cid and cached_cid not in localized_by_cid:
                localized_by_cid[cached_cid] = cached_name
            if cached_link and cached_link not in localized_by_link:
                localized_by_link[cached_link] = cached_name

    updated_items: list[dict] = []
    changed = False
    for attraction in attractions:
        next_item = dict(attraction)
        current_name = str(attraction.get("name") or "").strip()
        if not _needs_ru_attraction_name_localization(current_name, lang):
            updated_items.append(next_item)
            continue

        link = str(attraction.get("link") or "").strip()
        cid = _extract_google_maps_cid(link)
        replacement = localized_by_cid.get(cid) or localized_by_link.get(link)
        if replacement and replacement != current_name:
            next_item["name"] = replacement
            changed = True
        updated_items.append(next_item)

    return updated_items, changed


def _build_google_places_headers(rapidapi_key: str, field_mask: str) -> dict[str, str]:
    return {
        "x-rapidapi-key": rapidapi_key,
        "x-rapidapi-host": "google-map-places-new-v2.p.rapidapi.com",
        "Content-Type": "application/json",
        "X-Goog-FieldMask": field_mask,
    }


def _build_restaurant_search_query(city_name: str, question: str, language: str) -> str:
    normalized_question = re.sub(r"\s+", " ", str(question or "").strip())
    if not normalized_question:
        return f"best restaurants in {city_name}"

    has_food_signal = bool(
        re.search(
            r"(ресторан|кафе|бар|где\s+поесть|покушать|поужинать|пообедать|завтрак|ужин|обед|"
            r"restaurant|cafe|bar|eat|food|breakfast|lunch|dinner)",
            normalized_question,
            re.IGNORECASE,
        )
    )
    if not has_food_signal:
        return f"best restaurants in {city_name}"

    if language == "ru":
        return f"{normalized_question} {city_name}"
    return f"{normalized_question} in {city_name}"


async def _search_restaurants_for_assistant(
    city: str,
    question: str,
    language: str,
    limit: int = 5,
) -> list[dict[str, Any]]:
    rapidapi_key = os.getenv("RAPIDAPI_KEY", "").strip()
    city_name = city.split(",")[0].strip()
    if not rapidapi_key or not city_name:
        return []

    payload = {
        "textQuery": _build_restaurant_search_query(city_name, question, language),
        "languageCode": language if language in {"ru", "en"} else "ru",
        "maxResultCount": max(1, min(limit, 8)),
    }
    headers = _build_google_places_headers(
        rapidapi_key,
        "places.displayName,places.formattedAddress,places.rating,places.userRatingCount,"
        "places.googleMapsUri,places.priceLevel,places.primaryTypeDisplayName",
    )

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                "https://google-map-places-new-v2.p.rapidapi.com/v1/places:searchText",
                json=payload,
                headers=headers,
            )
        if response.status_code != 200:
            print(f"[Assistant restaurants] Google Places returned {response.status_code}: {response.text[:200]}")
            return []

        places = response.json().get("places", []) or []
        results: list[dict[str, Any]] = []
        for place in places[:limit]:
            if not isinstance(place, dict):
                continue
            name = str(((place.get("displayName") or {}).get("text")) or "").strip()
            if not name:
                continue
            results.append(
                {
                    "name": name,
                    "address": str(place.get("formattedAddress") or "").strip() or None,
                    "rating": place.get("rating"),
                    "reviews_count": place.get("userRatingCount"),
                    "price_level": str(place.get("priceLevel") or "").strip() or None,
                    "type_label": str(((place.get("primaryTypeDisplayName") or {}).get("text")) or "").strip() or None,
                    "link": str(place.get("googleMapsUri") or "").strip() or None,
                }
            )
        return results
    except Exception as exc:
        print(f"[Assistant restaurants] search failed: {exc}")
        return []


async def _search_wikipedia_title(
    query: str,
    wiki_lang: str,
    client: httpx.AsyncClient,
) -> Optional[str]:
    if not query:
        return None
    try:
        response = await client.get(
            f"https://{wiki_lang}.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "list": "search",
                "srsearch": query,
                "format": "json",
                "utf8": 1,
                "srlimit": 1,
            },
            headers={"User-Agent": "Luggify/1.0"},
        )
        if response.status_code != 200:
            return None
        pages = (response.json().get("query") or {}).get("search") or []
        if not pages:
            return None
        return str(pages[0].get("title") or "").strip() or None
    except Exception:
        return None


async def _localize_attraction_names_with_wikipedia(
    attractions: list[dict],
    city_name: str,
    lang: str,
    client: httpx.AsyncClient,
) -> tuple[list[dict], bool]:
    if lang != "ru" or not attractions:
        return attractions, False

    updated_items: list[dict] = []
    changed = False

    for attraction in attractions:
        next_item = dict(attraction)
        current_name = str(attraction.get("name") or "").strip()
        if not _needs_ru_attraction_name_localization(current_name, lang):
            updated_items.append(next_item)
            continue

        override_name = _ATTRACTION_RU_NAME_OVERRIDES.get(current_name.casefold())
        if override_name:
            next_item["name"] = override_name
            changed = override_name != current_name or changed
            updated_items.append(next_item)
            continue

        cache_key = f"ru:{city_name}:{current_name}".casefold()
        localized_name = ATTRACTION_NAME_CACHE.get(cache_key)
        if localized_name is None:
            for query in (
                f"intitle:{current_name} {city_name}",
                f"{current_name} {city_name}",
                current_name,
            ):
                localized_name = await _search_wikipedia_title(query, "ru", client)
                if (
                    localized_name
                    and not _needs_ru_attraction_name_localization(localized_name, "ru")
                    and not _is_obviously_non_attraction_name(localized_name)
                ):
                    break
            ATTRACTION_NAME_CACHE[cache_key] = localized_name or ""

        if localized_name == "":
            localized_name = None

        if (
            localized_name
            and not _needs_ru_attraction_name_localization(localized_name, "ru")
            and not _is_obviously_non_attraction_name(localized_name)
        ):
            next_item["name"] = localized_name
            changed = localized_name != current_name or changed

        updated_items.append(next_item)

    return updated_items, changed


async def _localize_attraction_names_with_google(
    attractions: list[dict],
    city_name: str,
    lang: str,
    rapidapi_key: str,
    client: httpx.AsyncClient,
) -> tuple[list[dict], bool]:
    if lang != "ru" or not rapidapi_key or not attractions:
        return attractions, False

    search_url = "https://google-map-places-new-v2.p.rapidapi.com/v1/places:searchText"
    headers = _build_google_places_headers(
        rapidapi_key,
        "places.displayName,places.googleMapsUri",
    )
    updated_items: list[dict] = []
    changed = False

    for attraction in attractions:
        next_item = dict(attraction)
        current_name = str(attraction.get("name") or "").strip()
        if not _needs_ru_attraction_name_localization(current_name, lang):
            updated_items.append(next_item)
            continue

        current_link = str(attraction.get("link") or "").strip()
        current_cid = _extract_google_maps_cid(current_link)
        try:
            response = await client.post(
                search_url,
                json={
                    "textQuery": f"{current_name} {city_name}",
                    "languageCode": "ru",
                    "maxResultCount": 1,
                },
                headers=headers,
            )
            if response.status_code != 200:
                updated_items.append(next_item)
                continue

            places = response.json().get("places", [])
            if not places:
                updated_items.append(next_item)
                continue

            localized = places[0]
            localized_name = str(((localized.get("displayName") or {}).get("text")) or "").strip()
            localized_link = str(localized.get("googleMapsUri") or "").strip()
            localized_cid = _extract_google_maps_cid(localized_link)
            same_place = (
                (current_cid and localized_cid and current_cid == localized_cid)
                or (current_link and localized_link and current_link == localized_link)
                or not current_link
            )
            if same_place and localized_name and not _needs_ru_attraction_name_localization(localized_name, "ru"):
                next_item["name"] = localized_name
                changed = localized_name != current_name or changed
        except Exception:
            pass

        updated_items.append(next_item)

    return updated_items, changed


def _apply_fallback_ru_name_translation(
    attractions: list[dict],
    lang: str,
) -> tuple[list[dict], bool]:
    if lang != "ru" or not attractions:
        return attractions, False

    updated_items: list[dict] = []
    changed = False
    for attraction in attractions:
        next_item = dict(attraction)
        if _needs_ru_attraction_name_localization(next_item.get("name"), "ru"):
            fallback_name = _fallback_translate_attraction_name_to_ru(next_item.get("name"))
            if fallback_name and fallback_name != next_item.get("name"):
                next_item["name"] = fallback_name
                changed = True
        updated_items.append(next_item)
    return updated_items, changed


async def _hydrate_google_photos_for_final_attractions(
    attractions: list[dict],
    photo_ref_by_link: dict[str, str],
    rapidapi_key: str,
    client: httpx.AsyncClient,
) -> tuple[list[dict], bool]:
    if not attractions or not rapidapi_key or not photo_ref_by_link:
        return attractions, False

    updated_items: list[dict] = []
    changed = False
    for attraction in attractions:
        next_item = dict(attraction)
        current_image = str(attraction.get("image") or "").strip()
        if _is_admin_attraction_image(attraction) or _is_google_attraction_image(current_image):
            updated_items.append(next_item)
            continue

        link = str(attraction.get("link") or "").strip()
        photo_ref = str(photo_ref_by_link.get(link) or "").strip()
        if not photo_ref:
            updated_items.append(next_item)
            continue

        try:
            photo_resp = await client.get(
                f"https://google-map-places-new-v2.p.rapidapi.com/v1/{photo_ref}/media",
                headers={
                    "x-rapidapi-key": rapidapi_key,
                    "x-rapidapi-host": "google-map-places-new-v2.p.rapidapi.com",
                },
                params={"maxWidthPx": "800", "skipHttpRedirect": "true"},
            )
            if photo_resp.status_code == 200:
                image_url = str(photo_resp.json().get("photoUri") or "").strip()
                if image_url and image_url != current_image:
                    next_item["image"] = image_url
                    changed = True
        except Exception:
            pass

        updated_items.append(next_item)

    return updated_items, changed


def _select_best_google_photo_ref(photos: list[dict] | None) -> str:
    candidates = photos or []
    if not candidates:
        return ""

    target_aspect_ratio = 0.82
    best_ref = ""
    best_score = float("-inf")

    for photo in candidates[:5]:
        photo_ref = str((photo or {}).get("name") or "").strip()
        width = int((photo or {}).get("widthPx") or 0)
        height = int((photo or {}).get("heightPx") or 0)
        if not photo_ref:
            continue

        aspect_ratio = (width / height) if width > 0 and height > 0 else target_aspect_ratio
        aspect_penalty = abs(aspect_ratio - target_aspect_ratio) * 1200
        area_bonus = min(width * height, 20_000_000) / 20_000
        long_edge_bonus = min(max(width, height), 5000) / 50
        portrait_bonus = 80 if height >= width else 0
        score = area_bonus + long_edge_bonus + portrait_bonus - aspect_penalty

        if score > best_score:
            best_score = score
            best_ref = photo_ref

    return best_ref


def _build_curated_attractions(city_name: str, limit: int) -> list[dict]:
    normalized_city = _normalize_city_lookup(city_name)
    curated_key = _CURATED_LOOKUP.get(normalized_city)
    if not curated_key:
        return []

    results = []
    for title in _CURATED.get(curated_key, [])[: max(limit, 1)]:
        results.append(
            {
                "name": title,
                "image": None,
                "link": f"https://www.google.com/maps/search/?api=1&query={url_quote(f'{title}, {city_name}')}",
            }
        )
    return results

@app.get("/attractions")
async def get_attractions(
    city: str = Query(...),
    lang: str = Query("ru"),
    limit: int = Query(10),
    db: AsyncSession = Depends(get_db)  # Add DB dependency
):
    """Достопримечательности (Google Places API V2 + DB cache)."""
    city_name = city.split(",")[0].strip()
    cache_key = f"{city_name}_{lang}_{limit}".lower()
    merge_limit = max(limit * 2, limit)
    rapidapi_key = os.getenv("RAPIDAPI_KEY", "").strip()
    curated_results = _build_curated_attractions(city_name, merge_limit)
    
    # 1. Поиск в БД (Кэш)
    cached_obj = await crud.get_city_attractions(db, cache_key)
    if cached_obj:
        sanitized_cached, changed = _sanitize_attractions(cached_obj.data or [], limit)
        merged_cached = _merge_attractions(sanitized_cached, curated_results, merge_limit)
        changed = changed or len(merged_cached) != len(sanitized_cached)
        merged_cached, restored_names = await _restore_localized_names_from_cache(
            db,
            city_name,
            merged_cached,
            lang,
        )
        changed = changed or restored_names
        merged_cached, restored_google = await _restore_google_images_from_cache(
            db,
            city_name,
            cache_key,
            merged_cached,
        )
        changed = changed or restored_google
        needs_name_refresh = bool(rapidapi_key) and _cached_attractions_need_name_refresh(merged_cached, lang)
        if needs_name_refresh:
            async with httpx.AsyncClient(timeout=30) as client:
                merged_cached, localized_changed = await _localize_attraction_names_with_google(
                    merged_cached,
                    city_name,
                    lang,
                    rapidapi_key,
                    client,
                )
                changed = changed or localized_changed
                merged_cached, wiki_changed = await _localize_attraction_names_with_wikipedia(
                    merged_cached,
                    city_name,
                    lang,
                    client,
                )
                changed = changed or wiki_changed
            merged_cached, fallback_changed = _apply_fallback_ru_name_translation(merged_cached, lang)
            changed = changed or fallback_changed
        hydrated_cached = _finalize_attractions(merged_cached, limit)
        if changed:
            cached_obj = await crud.save_city_attractions(db, cache_key, hydrated_cached)
        should_refresh_from_google = bool(rapidapi_key) and (
            _cached_attractions_need_google_refresh(cached_obj.data or [])
            or _cached_attractions_need_name_refresh(cached_obj.data or [], lang)
        )
        if (datetime.now() - cached_obj.updated_at).days < ATTRACTIONS_CACHE_MAX_AGE_DAYS and not should_refresh_from_google:
            return {"attractions": cached_obj.data}

    # Lock для ин-мемори (если несколько юзеров одновременно запросили новый город)
    if cache_key not in ATTRACTIONS_LOCKS:
        ATTRACTIONS_LOCKS[cache_key] = asyncio.Lock()

    async with ATTRACTIONS_LOCKS[cache_key]:
        # Двойная проверка на случай, если другой таск уже сохранил
        cached_obj = await crud.get_city_attractions(db, cache_key)
        if cached_obj:
            sanitized_cached, changed = _sanitize_attractions(cached_obj.data or [], limit)
            merged_cached = _merge_attractions(sanitized_cached, curated_results, merge_limit)
            changed = changed or len(merged_cached) != len(sanitized_cached)
            merged_cached, restored_names = await _restore_localized_names_from_cache(
                db,
                city_name,
                merged_cached,
                lang,
            )
            changed = changed or restored_names
            merged_cached, restored_google = await _restore_google_images_from_cache(
                db,
                city_name,
                cache_key,
                merged_cached,
            )
            changed = changed or restored_google
            needs_name_refresh = bool(rapidapi_key) and _cached_attractions_need_name_refresh(merged_cached, lang)
            if needs_name_refresh:
                async with httpx.AsyncClient(timeout=30) as client:
                    merged_cached, localized_changed = await _localize_attraction_names_with_google(
                        merged_cached,
                        city_name,
                        lang,
                        rapidapi_key,
                        client,
                    )
                    changed = changed or localized_changed
                    merged_cached, wiki_changed = await _localize_attraction_names_with_wikipedia(
                        merged_cached,
                        city_name,
                        lang,
                        client,
                    )
                    changed = changed or wiki_changed
                merged_cached, fallback_changed = _apply_fallback_ru_name_translation(merged_cached, lang)
                changed = changed or fallback_changed
            hydrated_cached = _finalize_attractions(merged_cached, limit)
            if changed:
                cached_obj = await crud.save_city_attractions(db, cache_key, hydrated_cached)
        should_refresh_from_google = bool(rapidapi_key) and (
            _cached_attractions_need_google_refresh((cached_obj.data if cached_obj else []) or [])
            or _cached_attractions_need_name_refresh((cached_obj.data if cached_obj else []) or [], lang)
        )
        if cached_obj and (datetime.now() - cached_obj.updated_at).days < ATTRACTIONS_CACHE_MAX_AGE_DAYS and not should_refresh_from_google:
            return {"attractions": cached_obj.data}

        results = []

        async def return_fallback_results():
            cached_fallback = await crud.get_city_attractions(db, cache_key)
            if cached_fallback and cached_fallback.data:
                sanitized_cached, changed = _sanitize_attractions(cached_fallback.data or [], limit)
                merged_cached = _merge_attractions(sanitized_cached, curated_results, merge_limit)
                changed = changed or len(merged_cached) != len(sanitized_cached)
                merged_cached, restored_names = await _restore_localized_names_from_cache(
                    db,
                    city_name,
                    merged_cached,
                    lang,
                )
                changed = changed or restored_names
                merged_cached, restored_google = await _restore_google_images_from_cache(
                    db,
                    city_name,
                    cache_key,
                    merged_cached,
                )
                changed = changed or restored_google
                needs_name_refresh = bool(rapidapi_key) and _cached_attractions_need_name_refresh(merged_cached, lang)
                if needs_name_refresh:
                    async with httpx.AsyncClient(timeout=30) as client:
                        merged_cached, localized_changed = await _localize_attraction_names_with_google(
                            merged_cached,
                            city_name,
                            lang,
                            rapidapi_key,
                            client,
                        )
                        changed = changed or localized_changed
                        merged_cached, wiki_changed = await _localize_attraction_names_with_wikipedia(
                            merged_cached,
                            city_name,
                            lang,
                            client,
                        )
                        changed = changed or wiki_changed
                    merged_cached, fallback_changed = _apply_fallback_ru_name_translation(merged_cached, lang)
                    changed = changed or fallback_changed
                hydrated_cached = _finalize_attractions(merged_cached, limit)
                if changed:
                    cached_fallback = await crud.save_city_attractions(db, cache_key, hydrated_cached)
                return {"attractions": cached_fallback.data}
            if curated_results:
                fallback_curated_results, _ = _sanitize_attractions(curated_results, limit)
                fallback_curated_results, _ = await _restore_localized_names_from_cache(
                    db,
                    city_name,
                    fallback_curated_results,
                    lang,
                )
                fallback_curated_results, _ = await _restore_google_images_from_cache(
                    db,
                    city_name,
                    cache_key,
                    fallback_curated_results,
                )
                hydrated_curated = _finalize_attractions(fallback_curated_results, limit)
                await crud.save_city_attractions(db, cache_key, hydrated_curated)
                return {"attractions": hydrated_curated}
            return {"attractions": []}

        try:
            if not rapidapi_key:
                return await return_fallback_results()

            url = "https://google-map-places-new-v2.p.rapidapi.com/v1/places:searchText"
            max_result_count = min(max(limit * 3, limit), 20)
            payload = {
                "textQuery": f"top landmarks and tourist attractions in {city_name}",
                "languageCode": lang,
                "maxResultCount": max_result_count
            }
            headers = _build_google_places_headers(
                rapidapi_key,
                "places.displayName,places.rating,places.googleMapsUri,places.userRatingCount,places.photos,places.location,places.priceLevel,places.primaryTypeDisplayName,places.types",
            )
            photo_ref_by_link: dict[str, str] = {}

            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code == 200:
                    places = resp.json().get("places", [])
                else:
                    print(f"RapidAPI returned {resp.status_code}: {resp.text}")
                    places = []

                if not places:
                    return await return_fallback_results()
                
                for p in places:
                    name = p.get("displayName", {}).get("text", "")
                    if not name:
                        continue

                    maps_url = p.get("googleMapsUri", f"https://www.google.com/maps/search/?api=1&query={url_quote(name + ', ' + city_name)}")

                    photos = p.get("photos", [])
                    if photos:
                        photo_ref = _select_best_google_photo_ref(photos)
                        if photo_ref and maps_url and maps_url not in photo_ref_by_link:
                            photo_ref_by_link[maps_url] = photo_ref

                    results.append({
                        "name": name,
                        "image": None,
                        "link": maps_url,
                        "lat": (p.get("location") or {}).get("latitude"),
                        "lng": (p.get("location") or {}).get("longitude"),
                        "rating": p.get("rating"),
                        "price_level": str(p.get("priceLevel") or "").strip() or None,
                        "place_type": (p.get("primaryTypeDisplayName") or {}).get("text") or ((p.get("types") or [None])[0]),
                    })

            if results:
                results, _ = _sanitize_attractions(results, limit)
                results = _merge_attractions(results, curated_results, merge_limit)
                results, _ = await _restore_localized_names_from_cache(
                    db,
                    city_name,
                    results,
                    lang,
                )
                results, _ = await _restore_google_images_from_cache(
                    db,
                    city_name,
                    cache_key,
                    results,
                )
                results = _finalize_attractions(results, limit)
                async with httpx.AsyncClient(timeout=30) as client:
                    results, _ = await _localize_attraction_names_with_google(results, city_name, lang, rapidapi_key, client)
                    results, _ = await _localize_attraction_names_with_wikipedia(results, city_name, lang, client)
                    results, _ = _apply_fallback_ru_name_translation(results, lang)
                    results, _ = await _hydrate_google_photos_for_final_attractions(
                        results,
                        photo_ref_by_link,
                        rapidapi_key,
                        client,
                    )
                results = _finalize_attractions(results, limit)
                await crud.save_city_attractions(db, cache_key, results)
                return {"attractions": results}
                
        except Exception as e:
            print(f"Attractions API V2 error: {e}")
            
        return await return_fallback_results()


def _validate_admin_attraction_image_url(image_url: str) -> str:
    normalized = str(image_url or "").strip()
    if normalized.startswith("data:image/"):
        return normalized
    try:
        parsed = urlparse(normalized)
    except Exception:
        parsed = None
    if not parsed or parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=400, detail="Нужна прямая http/https ссылка на картинку")
    return normalized


_ATTRACTION_IMAGE_POSITIONS = {
    "center center",
    "top center",
    "bottom center",
    "center left",
    "center right",
    "top left",
    "top right",
    "bottom left",
    "bottom right",
}


def _validate_admin_attraction_image_position(position: str | None) -> str:
    normalized = re.sub(r"\s+", " ", str(position or "center center").strip().lower())
    if normalized not in _ATTRACTION_IMAGE_POSITIONS:
        raise HTTPException(status_code=400, detail="Некорректная область отображения картинки")
    return normalized


@app.get("/attractions/image-proxy")
async def proxy_attraction_image(url: str = Query(...)):
    """Проксирование внешней картинки, чтобы её можно было безопасно кадрировать в браузере."""
    normalized_url = _validate_admin_attraction_image_url(url)
    if normalized_url.startswith("data:image/"):
        raise HTTPException(status_code=400, detail="Data URL не нужно проксировать")

    try:
        async with httpx.AsyncClient(timeout=25, follow_redirects=True) as client:
            response = await client.get(
                normalized_url,
                headers={"User-Agent": "Luggify/1.0"},
            )
    except Exception:
        raise HTTPException(status_code=502, detail="Не удалось загрузить картинку по ссылке")

    if response.status_code >= 400:
        raise HTTPException(status_code=404, detail="Картинка по ссылке недоступна")

    content_type = str(response.headers.get("content-type") or "").split(";")[0].strip().lower()
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Ссылка должна вести прямо на файл изображения")

    content = response.content
    if len(content) > 12 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Картинка слишком большая")

    return Response(
        content=content,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=3600"},
    )


def _apply_admin_attraction_image_override(
    attractions: list[dict],
    payload: schemas.AttractionImageUpdate,
    image_url: str,
    image_position: str,
    admin_user_id: int,
) -> tuple[list[dict], bool]:
    updated: list[dict] = []
    changed = False
    updated_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    for attraction in attractions or []:
        next_item = dict(attraction or {})
        if _attraction_matches_target(next_item, payload.attraction_name, payload.attraction_link):
            if (
                next_item.get("image") != image_url
                or next_item.get("image_position") != image_position
                or next_item.get("image_source") != "admin"
            ):
                next_item["image"] = image_url
                next_item["image_position"] = image_position
                next_item["image_source"] = "admin"
                next_item["admin_image"] = True
                next_item["admin_image_updated_at"] = updated_at
                next_item["admin_image_updated_by"] = admin_user_id
                changed = True
        updated.append(next_item)

    return updated, changed


@app.patch("/attractions/image")
async def update_attraction_image(
    payload: schemas.AttractionImageUpdate,
    admin_user=Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Админская замена картинки достопримечательности в общем DB-кэше."""
    image_url = _validate_admin_attraction_image_url(payload.image)
    image_position = _validate_admin_attraction_image_position(payload.image_position)
    city_name = payload.city.split(",")[0].strip()
    if not city_name:
        raise HTTPException(status_code=400, detail="Город не указан")
    cache_key = f"{city_name}_{payload.lang}_{payload.limit}".lower()
    normalized_city = city_name.strip().lower()

    rows = await db.execute(
        select(models.CityAttraction).where(models.CityAttraction.city_name.like(f"{normalized_city}_%"))
    )
    cached_variants = rows.scalars().all()
    if not cached_variants:
        raise HTTPException(status_code=404, detail="Кэш достопримечательностей для города ещё не создан")

    updated_keys: list[str] = []
    for variant in cached_variants:
        next_data, changed = _apply_admin_attraction_image_override(
            variant.data or [],
            payload,
            image_url,
            image_position,
            admin_user.id,
        )
        if changed:
            variant.data = next_data
            updated_keys.append(variant.city_name)

    if not updated_keys:
        raise HTTPException(status_code=404, detail="Достопримечательность не найдена в кэше")

    await db.commit()

    current_cache = await crud.get_city_attractions(db, cache_key)
    if current_cache:
        return {"attractions": current_cache.data, "updated_cache_keys": updated_keys}

    return {"attractions": cached_variants[0].data, "updated_cache_keys": updated_keys}


# === Feature: Flight Search (Travelpayouts) ===
TRAVELPAYOUTS_TOKEN = os.getenv("TRAVELPAYOUTS_TOKEN", "")
AIRLINE_NAME_CACHE: dict[str, str] = {}
AIRLINE_NAME_CACHE_UPDATED = 0
AIRLINE_NAME_CACHE_TTL = 86400  # 24 hours


async def get_airline_name_map(client: httpx.AsyncClient) -> dict[str, str]:
    global AIRLINE_NAME_CACHE, AIRLINE_NAME_CACHE_UPDATED
    if AIRLINE_NAME_CACHE and time.time() - AIRLINE_NAME_CACHE_UPDATED < AIRLINE_NAME_CACHE_TTL:
        return AIRLINE_NAME_CACHE

    try:
        response = await client.get("https://api.travelpayouts.com/data/ru/airlines.json")
        if response.status_code == 200:
            payload = response.json() or []
            AIRLINE_NAME_CACHE = {
                str(item.get("code", "")).upper(): (
                    item.get("name")
                    or (item.get("name_translations") or {}).get("en")
                    or str(item.get("code", "")).upper()
                )
                for item in payload
                if item.get("code")
            }
            AIRLINE_NAME_CACHE_UPDATED = time.time()
    except Exception as e:
        print(f"Airline names error: {e}")

    return AIRLINE_NAME_CACHE

@app.get("/flights/search")
async def search_flights(
    destination: str = Query(..., description="City name"),
    date: str = Query(None, description="YYYY-MM-DD departure"),
    return_date: str = Query(None, description="YYYY-MM-DD return"),
    origin: str = Query(None, description="Origin city name"),
    adults: int = Query(1, description="Number of adults"),
    children: int = Query(0, description="Number of children 2-11"),
    infants: int = Query(0, description="Number of infants 0-1"),
    trip_class: str = Query("0", description="0 economy, 1 business, 2 first"),
):
    """Поиск дешёвых авиабилетов через Travelpayouts API"""
    if not TRAVELPAYOUTS_TOKEN:
        return {"flights": [], "error": "API key not configured"}

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            # Get IATA code for destination
            iata_resp = await client.get(
                "https://autocomplete.travelpayouts.com/places2",
                params={"term": destination.split(",")[0].strip(), "locale": "ru", "types[]": "city"}
            )
            dest_code = ""
            if iata_resp.status_code == 200 and iata_resp.json():
                dest_code = iata_resp.json()[0].get("code", "")

            if not dest_code:
                return {"flights": []}

            # Get IATA code for origin (if provided)
            origin_code = ""
            if origin:
                origin_resp = await client.get(
                    "https://autocomplete.travelpayouts.com/places2",
                    params={"term": origin.split(",")[0].strip(), "locale": "ru", "types[]": "city"}
                )
                if origin_resp.status_code == 200 and origin_resp.json():
                    origin_code = origin_resp.json()[0].get("code", "")

            normalized_adults = max(int(adults or 1), 1)
            normalized_children = max(int(children or 0), 0)
            normalized_infants = max(int(infants or 0), 0)
            max_seated = 9
            seated_total = normalized_adults + normalized_children
            if seated_total > max_seated:
                overflow = seated_total - max_seated
                normalized_children = max(normalized_children - overflow, 0)
            if normalized_infants > normalized_adults:
                extra_infants = normalized_infants - normalized_adults
                normalized_infants = normalized_adults
                normalized_children = min(max_seated - normalized_adults, normalized_children + extra_infants)
            normalized_trip_class = str(trip_class if str(trip_class) in {"0", "1", "2"} else "0")

            def build_aviasales_link(origin_iata: str, destination_iata: str, depart_date: str | None, arrive_back_date: str | None) -> str:
                query_params = {
                    "origin_iata": origin_iata or "",
                    "destination_iata": destination_iata or "",
                    "adults": str(normalized_adults),
                    "children": str(normalized_children),
                    "infants": str(normalized_infants),
                    "trip_class": normalized_trip_class,
                    "depart_date": depart_date or "",
                    "currency": "rub",
                    "oneway": "false" if arrive_back_date else "true",
                    "language": "ru",
                    "with_request": "true",
                }
                if TRAVELPAYOUTS_MARKER:
                    query_params["marker"] = TRAVELPAYOUTS_MARKER
                if arrive_back_date:
                    query_params["return_date"] = arrive_back_date
                filtered_params = {key: value for key, value in query_params.items() if value not in {"", None}}
                return str(httpx.URL("https://www.aviasales.ru/search", params=filtered_params))

            can_use_single_offer_link = normalized_trip_class == "0" and normalized_adults == 1 and normalized_children == 0 and normalized_infants == 0

            def build_aviasales_offer_link(raw_link: str | None, fallback_link: str) -> str:
                if not can_use_single_offer_link:
                    return fallback_link
                if not raw_link:
                    return fallback_link
                link = str(raw_link).strip()
                if not link:
                    return fallback_link
                if link.startswith("http://") or link.startswith("https://"):
                    return link
                if link.startswith("/"):
                    return f"https://www.aviasales.ru{link}"
                return f"https://www.aviasales.ru/{link}"

            generic_link = build_aviasales_link(origin_code, dest_code, date, return_date)
            outbound_search_link = build_aviasales_link(origin_code, dest_code, date, None)
            inbound_search_link = build_aviasales_link(dest_code, origin_code, return_date, None) if return_date and origin_code else ""
            airline_names = await get_airline_name_map(client)

            # Helper: выбрать лучший рейс — приоритет прямым (без пересадок)
            def pick_best_flights(raw_flights, f_origin_default, f_dest_default, flight_type):
                if not raw_flights:
                    return []
                filtered_flights = []
                for raw_flight in raw_flights:
                    raw_trip_class = raw_flight.get("trip_class")
                    if raw_trip_class is None:
                        if normalized_trip_class == "0":
                            filtered_flights.append(raw_flight)
                        continue
                    if str(raw_trip_class) == normalized_trip_class:
                        filtered_flights.append(raw_flight)

                if not filtered_flights:
                    return []

                parsed = []
                for f in filtered_flights:
                    f_origin = f.get("origin", f_origin_default)
                    f_dest = f.get("destination", f_dest_default)
                    f_origin_airport = f.get("origin_airport") or ""
                    f_dest_airport = f.get("destination_airport") or ""
                    origin_label = f_origin_airport or f_origin
                    destination_label = f_dest_airport or f_dest

                    segment_return_date = None
                    fallback_link = build_aviasales_link(
                        f_origin,
                        f_dest,
                        date if flight_type == "outbound" else return_date,
                        segment_return_date,
                    )
                    
                    duration = f.get("duration_to") or f.get("duration") or 0
                    
                    parsed.append({
                        "price": f.get("price") or f.get("value") or 999999,
                        "airline": f.get("airline"),
                        "airline_name": airline_names.get((f.get("airline") or "").upper(), f.get("airline")),
                        "departure_at": f.get("departure_at"),
                        "origin": f_origin,
                        "destination": f_dest,
                        "origin_airport": f_origin_airport,
                        "destination_airport": f_dest_airport,
                        "origin_label": origin_label,
                        "destination_label": destination_label,
                        "transfers": f.get("transfers", 0),
                        "duration": duration,
                        "link": build_aviasales_offer_link(f.get("link"), fallback_link),
                        "type": flight_type,
                    })
                
                # Приоритет: самый дешёвый прямой, иначе самый дешёвый
                direct = [f for f in parsed if f["transfers"] == 0]
                if direct:
                    best = min(direct, key=lambda x: x["price"])
                    best_copy = dict(best)
                    best_copy["tag"] = "Прямой рейс"
                    return [best_copy]
                
                cheapest = min(parsed, key=lambda x: x["price"])
                cheapest_copy = dict(cheapest)
                cheapest_copy["tag"] = "Самый дешёвый"
                return [cheapest_copy]

            # 1. OUTBOUND FLIGHTS
            out_params = {
                "destination": dest_code,
                "token": TRAVELPAYOUTS_TOKEN,
                "currency": "rub",
                "limit": 30,
            }
            if origin_code: out_params["origin"] = origin_code
            if date: out_params["departure_at"] = date
            
            outbound = []
            try:
                out_resp = await client.get("https://api.travelpayouts.com/aviasales/v3/prices_for_dates", params=out_params)
                if out_resp.status_code == 200:
                    raw = out_resp.json().get("data") or []
                    outbound = pick_best_flights(raw, origin_code, dest_code, "outbound")
            except Exception: pass

            # 2. INBOUND FLIGHTS
            inbound = []
            if return_date and dest_code:
                # Определяем пункт назначения для обратного рейса
                inbound_dest = origin_code
                if not inbound_dest and outbound:
                    # Используем origin из найденного outbound рейса
                    inbound_dest = outbound[0].get("origin", "")
                
                in_params = {
                    "origin": dest_code,
                    "token": TRAVELPAYOUTS_TOKEN,
                    "currency": "rub",
                    "limit": 30,
                    "departure_at": return_date,
                }
                if inbound_dest:
                    in_params["destination"] = inbound_dest
                
                try:
                    in_resp = await client.get("https://api.travelpayouts.com/aviasales/v3/prices_for_dates", params=in_params)
                    if in_resp.status_code == 200:
                        raw = in_resp.json().get("data") or []
                        inbound = pick_best_flights(raw, dest_code, inbound_dest or "", "inbound")
                except Exception: pass

            return {
                "flights": outbound + inbound,
                "destination_code": dest_code,
                "generic_link": generic_link,
                "outbound_link": outbound_search_link,
                "inbound_link": inbound_search_link,
            }
    except Exception as e:
        print(f"Flights error: {e}")
        return {"flights": []}


# === Feature: Hotel Search (RapidAPI Booking.com - ntd119/booking-com18) ===

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")
HOTELS_LOCATION_CACHE = {}  # key: city_name_lower -> locationId (permanent, city IDs don't change)
HOTELS_CACHE = {}  # key: (city, check_in, check_out) -> (data, timestamp)
HOTELS_CACHE_TTL = 604800  # 7 дней — экономим запросы (530/мес, ~265 поисков)
HOTELS_CACHE_VERSION = "rooms_v2"

@app.get("/hotels/search")
async def search_hotels(
    city: str = Query(...),
    check_in: str = Query(None, description="YYYY-MM-DD"),
    check_out: str = Query(None, description="YYYY-MM-DD"),
    price_min: int = Query(None, description="Min price per night in RUB"),
    price_max: int = Query(None, description="Max price per night in RUB"),
    review_score: int = Query(None, description="Min review score"),
    min_bedrooms: int = Query(None, description="Min bedroom count"),
    adults: int = Query(2, description="Number of adults"),
    children_ages: str = Query(None, description="Comma-separated children ages"),
    rooms: int = Query(1, description="Number of hotel rooms"),
    currency: str = Query("RUB", description="Display currency"),
    locale: str = Query("ru", description="Booking locale"),
):
    """Поиск отелей через RapidAPI booking-com18 (ntd119) — с фото, ценами, рейтингом"""
    # Используем полное имя города (напр. "Paris, France") для точного поиска
    city_name = city.strip()
    city_short = city.split(",")[0].strip()  # короткое имя для ссылки на Booking

    from datetime import timedelta
    
    def parse_date(d_str):
        if not d_str: return None
        for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%m/%d/%Y"):
            try:
                # `datetime` is already the class, so we use it directly
                return datetime.strptime(d_str, fmt).date()
            except ValueError:
                pass
        return None

    d_in = parse_date(check_in)
    d_out = parse_date(check_out)

    if not d_in:
        d_in = datetime.now().date() + timedelta(days=1)
    if not d_out or d_out <= d_in:
        d_out = d_in + timedelta(days=3)

    t_check_in = d_in.strftime("%Y-%m-%d")
    t_check_out = d_out.strftime("%Y-%m-%d")
    normalized_adults = max(int(adults or 1), 1)
    normalized_currency = str(currency or "RUB").upper()
    if normalized_currency not in {"RUB", "USD", "EUR"}:
        normalized_currency = "RUB"
    normalized_locale = str(locale or "ru").lower()
    if normalized_locale not in {"ru", "en-us", "en"}:
        normalized_locale = "ru"
    normalized_hotel_children_ages = []
    if children_ages:
        for raw_age in children_ages.split(","):
            try:
                age = int(raw_age.strip())
            except (TypeError, ValueError):
                continue
            if 0 <= age <= 17:
                normalized_hotel_children_ages.append(age)
    total_hotel_guests = max(normalized_adults + len(normalized_hotel_children_ages), 1)
    try:
        requested_rooms = int(rooms or 1)
    except (TypeError, ValueError):
        requested_rooms = 1
    normalized_rooms = min(max(requested_rooms, 1), min(total_hotel_guests, 8))
    normalized_review_score = max(min(int(review_score or 0), 10), 0)
    normalized_min_bedrooms = max(min(int(min_bedrooms or 0), 6), 0)
    normalized_price_min = max(int(price_min or 0), 0)
    normalized_price_max = max(int(price_max or 0), 0)
    if normalized_price_max and normalized_price_min and normalized_price_min > normalized_price_max:
        normalized_price_min, normalized_price_max = normalized_price_max, normalized_price_min

    def build_accommodation_unit_plan(adults_count: int, child_ages: list[int], units_count: int):
        group_count = min(max(int(units_count or 1), 1), min(max(adults_count + len(child_ages), 1), 8))
        groups = [{"adults": 0, "children_ages": []} for _ in range(group_count)]

        def pick_target_index(prefer_adult_host: bool = False) -> int:
            best_index = 0
            for index, group in enumerate(groups):
                best_group = groups[best_index]
                group_guests = group["adults"] + len(group["children_ages"])
                best_guests = best_group["adults"] + len(best_group["children_ages"])
                if group_guests != best_guests:
                    if group_guests < best_guests:
                        best_index = index
                    continue
                if prefer_adult_host and group["adults"] != best_group["adults"]:
                    if group["adults"] > best_group["adults"]:
                        best_index = index
                    continue
                if len(group["children_ages"]) != len(best_group["children_ages"]):
                    if len(group["children_ages"]) < len(best_group["children_ages"]):
                        best_index = index
                    continue
                if index < best_index:
                    best_index = index
            return best_index

        for _ in range(max(adults_count, 1)):
            groups[pick_target_index(False)]["adults"] += 1

        for age in child_ages:
            groups[pick_target_index(True)]["children_ages"].append(age)

        for group in groups:
            if group["adults"] > 0 or not group["children_ages"]:
                continue
            donor_index = next((index for index, candidate in enumerate(groups) if candidate["adults"] > 1), None)
            if donor_index is not None:
                groups[donor_index]["adults"] -= 1
                group["adults"] += 1

        normalized_groups = []
        for group in groups:
            normalized_groups.append({
                "adults": group["adults"],
                "children_ages": sorted(group["children_ages"]),
                "total_guests": group["adults"] + len(group["children_ages"]),
            })

        representative_group = max(
            normalized_groups,
            key=lambda group: (group["total_guests"], group["adults"], len(group["children_ages"])),
        )

        return {
            "unit_count": group_count,
            "total_guests": max(adults_count + len(child_ages), 1),
            "groups": normalized_groups,
            "representative_group": representative_group,
        }

    # Кол-во ночей для расчёта цены за ночь
    num_nights = max((d_out - d_in).days, 1)

    c_lower = city_name.lower()
    
    # Список крупных городов для точного попадания (иногда приходит только город без страны)
    ru_cities = [
        "москва", "санкт-петербург", "питер", "спб", "сочи", "казань", 
        "новосибирск", "екатеринбург", "нижний новгород", "краснодар", 
        "калининград", "владивосток", "анапа", "геленджик", "адлер"
    ]
    
    is_russia = "россия" in c_lower or "russia" in c_lower or any(rc in c_lower for rc in ru_cities)

    if is_russia:
        print(f"Hotels search: {city_name} is in Russia. Routing to ru_widgets.")
        placement = build_accommodation_unit_plan(
            normalized_adults,
            normalized_hotel_children_ages,
            normalized_rooms,
        )
        placement_group = placement["representative_group"]
        placement_adults = max(int(placement_group.get("adults", 0) or 0), 1)
        placement_children_ages = [
            int(age)
            for age in placement_group.get("children_ages", [])
            if isinstance(age, int)
        ]
        placement_children_query = ",".join(str(age) for age in placement_children_ages)

        # Sutochno: прямая ссылка в SPA поисковик
        sutochno_target = (
            f"https://sutochno.ru/front/searchapp/search"
            f"?guests_adults={placement_adults}"
            f"&occupied={t_check_in};{t_check_out}"
            f"&term={url_quote(city_short)}"
        )
        if placement_children_query:
            sutochno_target += f"&guests_childrens={placement_children_query}"
        if normalized_review_score > 0:
            sutochno_target += f"&review_score={normalized_review_score}"
        if normalized_min_bedrooms > 0:
            sutochno_target += f"&separate_bedrooms={normalized_min_bedrooms}"
        if normalized_price_max > 0 or normalized_price_min > 0:
            sutochno_price_max = normalized_price_max if normalized_price_max > 0 else 999999
            sutochno_target += f"&price={normalized_price_min},{sutochno_price_max}"
        
        # Ostrovok: хардкодим ID популярных городов, чтобы гарантировать идеальный предзаполненный поиск
        ostrovok_map = {
            "москва": {"id": 2395, "slug": "russia/moscow"},
            "санкт-петербург": {"id": 2042, "slug": "russia/st._petersburg"},
            "питер": {"id": 2042, "slug": "russia/st._petersburg"},
            "спб": {"id": 2042, "slug": "russia/st._petersburg"},
            "сочи": {"id": 5580, "slug": "russia/sochi"},
            "казань": {"id": 1993, "slug": "russia/kazan"},
            "новосибирск": {"id": 2721, "slug": "russia/novosibirsk"},
            "екатеринбург": {"id": 6049238, "slug": "russia/yekaterinburg"},
            "нижний новгород": {"id": 1361, "slug": "russia/nizhniy_novgorod"},
            "краснодар": {"id": 1913, "slug": "russia/krasnodar"},
            "калининград": {"id": 1798, "slug": "russia/kaliningrad"},
            "владивосток": {"id": 3748, "slug": "russia/vladivostok"},
            "анапа": {"id": 258, "slug": "russia/anapa"},
            "геленджик": {"id": 1301, "slug": "russia/gelendzhik"},
            "адлер": {"id": 299, "slug": "russia/adler"}
        }

        o_dates = f"{d_in.strftime('%d.%m.%Y')}-{d_out.strftime('%d.%m.%Y')}"
        
        o_guests = str(placement_adults)
        if placement_children_query:
            o_guests += f"and{placement_children_query.replace(',', '.')}"
        if normalized_min_bedrooms > 0:
            max_bedrooms = max(normalized_min_bedrooms, 6)
            bedroom_values = ".".join(str(value) for value in range(normalized_min_bedrooms, max_bedrooms + 1))
        else:
            bedroom_values = ""

        o_data = ostrovok_map.get(c_lower)
        if o_data:
            ostrovok_target = f"https://ostrovok.ru/hotel/{o_data['slug']}/?q={o_data['id']}&dates={o_dates}&guests={o_guests}"
        else:
            ostrovok_target = f"https://ostrovok.ru/?q={url_quote(city_short)}&dates={o_dates}&guests={o_guests}"
        if normalized_review_score > 0:
            ostrovok_target += f"&reviews_rating={normalized_review_score}"
        if bedroom_values:
            ostrovok_target += f"&bedrooms={bedroom_values}"
        if normalized_price_max > 0 or normalized_price_min > 0:
            ostrovok_price_max = normalized_price_max if normalized_price_max > 0 else 999999
            ostrovok_target += f"&price={normalized_price_min}-{ostrovok_price_max}"
        
        if TRAVELPAYOUTS_MARKER:
            ostrovok_link = f"https://tp.media/r?marker={TRAVELPAYOUTS_MARKER}&p=7038&u={url_quote(ostrovok_target)}&campaign_id=459"
            sutochno_link = f"https://tp.media/r?marker={TRAVELPAYOUTS_MARKER}&p=2690&u={url_quote(sutochno_target)}&campaign_id=99"
        else:
            ostrovok_link = ostrovok_target
            sutochno_link = sutochno_target
            
        return {
            "provider": "ru_widgets",
            "hotels": [],
            "num_nights": num_nights,
            "placement": placement,
            "links": {
                "ostrovok": ostrovok_link,
                "sutochno": sutochno_link
            }
        }

    # Если ключа нет, возвращаем mock-данные (заглушки) чтобы UI не был пустым
    if not RAPIDAPI_KEY:
        print("No RAPIDAPI_KEY found, returning MOCK hotels data.")
        return {
            "hotels": [
                {
                    "name": f"Grand Hotel {city_name}",
                    "stars": 5,
                    "price_per_night": 12500,
                    "price_rub": 12500,
                    "price_usd": 135,
                    "currency": "RUB",
                    "rating": 9.2,
                    "image": None,
                    "review_word": "Превосходно",
                    "link": f"https://www.booking.com/searchresults.ru.html?ss={city_name}",
                },
                {
                    "name": f"City Center Apartments",
                    "stars": 4,
                    "price_per_night": 4500,
                    "price_rub": 4500,
                    "price_usd": 49,
                    "currency": "RUB",
                    "rating": 8.7,
                    "image": None,
                    "review_word": "Отлично",
                    "link": f"https://www.booking.com/searchresults.ru.html?ss={city_name}",
                },
                {
                    "name": f"Budget Hostel {city_name}",
                    "stars": 2,
                    "price_per_night": 1200,
                    "price_rub": 1200,
                    "price_usd": 13,
                    "currency": "RUB",
                    "rating": 7.5,
                    "image": None,
                    "review_word": "Хорошо",
                    "link": f"https://www.booking.com/searchresults.ru.html?ss={city_name}",
                }
            ],
            "error": "RAPIDAPI_KEY not configured. Showing mock data."
        }

    print(f"Hotels search: city='{city_name}', dates={t_check_in}→{t_check_out}, nights={num_nights}, rooms={normalized_rooms}")

    # Проверяем кеш
    cache_key = (
        HOTELS_CACHE_VERSION,
        city_name.lower(),
        t_check_in,
        t_check_out,
        normalized_adults,
        ",".join(str(age) for age in normalized_hotel_children_ages),
        normalized_rooms,
        normalized_currency,
        normalized_locale,
    )
    if cache_key in HOTELS_CACHE:
        cached_data, cached_at = HOTELS_CACHE[cache_key]
        if time.time() - cached_at < HOTELS_CACHE_TTL:
            print(f"Hotels cache hit for {city_name}")
            return {"hotels": cached_data, "num_nights": num_nights}

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            headers = {
                "X-RapidAPI-Key": RAPIDAPI_KEY,
                "X-RapidAPI-Host": "booking-com18.p.rapidapi.com"
            }

            # 1. Получаем locationId — кешируем навсегда (city IDs не меняются)
            city_key = city_name.lower()
            if city_key in HOTELS_LOCATION_CACHE:
                location_id = HOTELS_LOCATION_CACHE[city_key]
                print(f"Hotels location cache hit for {city_name} -> {location_id[:30]}...")
            else:
                ac_resp = await client.get(
                    "https://booking-com18.p.rapidapi.com/stays/auto-complete",
                    headers=headers,
                    params={"query": city_name}
                )

                if ac_resp.status_code != 200:
                    print(f"Hotels auto-complete failed: {ac_resp.status_code}")
                    return {"hotels": []}

                ac_data = ac_resp.json()
                locations = ac_data.get("data", [])
                if not locations:
                    print(f"No locations found for {city_name}")
                    return {"hotels": []}

                # Фильтруем: только города (dest_type=city), а не отели/регионы
                city_locations = [l for l in locations if l.get("dest_type") == "city" or l.get("type") == "ci"]
                if not city_locations:
                    city_locations = locations  # fallback на все результаты

                # Выбираем город с наибольшим кол-вом отелей (избегаем мелкие города-однофамильцы)
                best = max(city_locations, key=lambda x: x.get("nr_hotels", 0) or x.get("hotels", 0) or 0)
                location_id = best.get("id", "")
                if not location_id:
                    return {"hotels": []}

                chosen_label = best.get("label", best.get("name", "?"))
                nr = best.get("nr_hotels") or best.get("hotels") or "?"
                print(f"Hotels: chose '{chosen_label}' ({nr} hotels) for query '{city_name}'")
                HOTELS_LOCATION_CACHE[city_key] = location_id

            # 2. Ищем отели
            search_params = {
                "locationId": location_id,
                "checkinDate": t_check_in,
                "checkoutDate": t_check_out,
                "adults": str(normalized_adults),
                "rooms": str(normalized_rooms),
                "currency": normalized_currency,
                "locale": normalized_locale,
                "sort": "popularity",
            }
            if normalized_hotel_children_ages:
                search_params["children"] = str(len(normalized_hotel_children_ages))
                search_params["childrenAges"] = ",".join(str(age) for age in normalized_hotel_children_ages)

            search_resp = await client.get(
                "https://booking-com18.p.rapidapi.com/stays/search",
                headers=headers,
                params=search_params
            )

            if search_resp.status_code != 200:
                print(f"Hotels search failed: {search_resp.status_code}")
                return {"hotels": []}

            search_data = search_resp.json()
            results = search_data.get("data", [])
            if not results:
                # Попробуем альтернативную структуру
                results = search_data.get("result", [])

            airport_keywords = ("airport", "aeroport", "aéroport", "аэропорт", "palexpo", "terminal")
            wants_airport_area = any(keyword in c_lower for keyword in airport_keywords)

            def extract_distance_km(raw_hotel: dict) -> float | None:
                distance_keys = (
                    "distance",
                    "distanceToCenter",
                    "distanceFromCenter",
                    "distanceToCC",
                    "distance_to_cc",
                    "distance_to_center",
                )
                for key in distance_keys:
                    raw_value = raw_hotel.get(key)
                    if raw_value is None:
                        continue
                    if isinstance(raw_value, (int, float)):
                        return float(raw_value)
                    if isinstance(raw_value, dict):
                        for nested_key in ("value", "distance", "km"):
                            nested_value = raw_value.get(nested_key)
                            if isinstance(nested_value, (int, float)):
                                return float(nested_value)
                    match = re.search(r"(\d+(?:[.,]\d+)?)\s*(km|км)", str(raw_value).lower())
                    if match:
                        return float(match.group(1).replace(",", "."))
                return None

            def is_airport_area(raw_hotel: dict, hotel_name: str) -> bool:
                haystack_parts = [
                    hotel_name,
                    raw_hotel.get("address", ""),
                    raw_hotel.get("district", ""),
                    raw_hotel.get("wishlistName", ""),
                    raw_hotel.get("location", ""),
                ]
                haystack = " ".join(str(part or "").lower() for part in haystack_parts)
                return any(keyword in haystack for keyword in airport_keywords)

            def is_hotel_available(raw_hotel: dict, price_value) -> bool:
                if not price_value:
                    return False
                unavailable_markers = (
                    "soldout",
                    "isSoldOut",
                    "is_sold_out",
                    "isClosed",
                    "is_closed",
                    "isUnavailable",
                    "is_unavailable",
                )
                if any(bool(raw_hotel.get(key)) for key in unavailable_markers):
                    return False
                false_availability_keys = ("available", "isAvailable", "is_available", "hasAvailability", "has_availability")
                for key in false_availability_keys:
                    if key in raw_hotel and raw_hotel.get(key) is False:
                        return False
                return True

            hotels = []
            for h in results:  # парсим все ~20 результатов для качественной сортировки
                # Данные на верхнем уровне (реальная структура API)
                name = h.get("name", "")
                distance_km = extract_distance_km(h)
                airport_area = is_airport_area(h, name)

                # Фото — API возвращает square60, заменяем на square600 для качества
                photo_urls = h.get("photoUrls", [])
                image = photo_urls[0] if photo_urls else None
                if image:
                    image = image.replace("square60", "square600")

                # Рейтинг
                review_score = h.get("reviewScore")
                review_word = h.get("reviewScoreWord", "")
                review_count = h.get("reviewCount", 0) or 0

                # Звёзды (propertyClass или qualityClass)
                stars = h.get("propertyClass") or h.get("qualityClass") or 0

                # Цена и валюта — API возвращает цену за ВЕСЬ период, делим на ночи
                price_breakdown = h.get("priceBreakdown", {})
                gross_price = price_breakdown.get("grossPrice", {})
                total_price = gross_price.get("value")
                price = round(total_price / num_nights, 2) if total_price else None
                currency = gross_price.get("currency", "EUR")
                if not is_hotel_available(h, price):
                    continue

                # Ссылка — самый надежный вариант это поиск по точному имени отеля,
                # Booking.com отлично его понимает и открывает страницу отеля или показывает его на первом месте (без 404)
                name_encoded = url_quote(name)
                booking_children_query = ""
                if normalized_hotel_children_ages:
                    booking_children_query = (
                        f"&group_children={len(normalized_hotel_children_ages)}"
                        + "".join(f"&age={age}" for age in normalized_hotel_children_ages)
                    )
                link = (
                    f"https://www.booking.com/searchresults.html?ss={name_encoded}"
                    f"&checkin={t_check_in}&checkout={t_check_out}"
                    f"&group_adults={normalized_adults}{booking_children_query}&no_rooms={normalized_rooms}"
                )

                # Конвертируем цену в рубли
                price_rub = None
                price_usd = None
                if price and currency and currency != "RUB":
                    rub_rate = await get_rub_rate(currency)
                    if rub_rate > 0:
                        price_rub = round(price * rub_rate)
                elif price and currency == "RUB":
                    price_rub = round(price)
                if price:
                    if currency == "USD":
                        price_usd = round(price)
                    else:
                        rub_value = price_rub
                        usd_rate = await get_rub_rate("USD")
                        if rub_value and usd_rate > 0:
                            price_usd = round(rub_value / usd_rate)

                if name:
                    hotels.append({
                        "name": name,
                        "stars": int(stars) if stars else 0,
                        "price_per_night": round(price) if price else None,
                        "price_rub": price_rub,
                        "price_usd": price_usd,
                        "currency": currency,
                        "rating": review_score,
                        "review_word": review_word,
                        "review_count": review_count,
                        "distance_km": distance_km,
                        "airport_area": airport_area,
                        "image": image,
                        "link": link,
                    })

            # --- Качественная фильтрация и сортировка ---
            # 1. Убираем отели с рейтингом ниже 6.0 ("Bad", "Poor")
            hotels = [h for h in hotels if not h["rating"] or h["rating"] >= 6.0]
            # 2. Сортируем как городскую подборку: сначала не аэропорт,
            #    затем ближе к центру, потом рейтинг и отзывы.
            def hotel_sort_key(hotel: dict):
                distance = hotel.get("distance_km")
                if distance is None:
                    distance_bucket = 1
                elif distance <= 2.5:
                    distance_bucket = 0
                elif distance <= 6:
                    distance_bucket = 1
                elif distance <= 10:
                    distance_bucket = 2
                else:
                    distance_bucket = 3
                airport_penalty = 0 if wants_airport_area or not hotel.get("airport_area") else 1
                return (
                    airport_penalty,
                    distance_bucket,
                    -(hotel.get("rating") or 0),
                    -(hotel.get("review_count") or 0),
                    hotel.get("price_rub") or 10**9,
                )

            hotels.sort(key=hotel_sort_key)
            # 3. Берём топ-10
            hotels = hotels[:10]

            # Фильтруем по цене (в рублях), если заданы границы
            if price_min or price_max:
                filtered = []
                for h in hotels:
                    pr = h.get("price_rub")
                    if pr is None:
                        continue
                    if price_min and pr < price_min:
                        continue
                    if price_max and pr > price_max:
                        continue
                    filtered.append(h)
                hotels = filtered[:10]

            # Сохраняем в кеш ПОЛНЫЕ результаты (до фильтрации)
            # Фильтрация по цене применяется каждый раз заново
            if not (price_min or price_max) and hotels:
                HOTELS_CACHE[cache_key] = (hotels, time.time())

            return {"hotels": hotels, "num_nights": num_nights}
    except Exception as e:
        print(f"Hotels error: {e}")
        import traceback
        traceback.print_exc()
        return {"hotels": []}


# === Feature: eSIM Search (Airalo via Travelpayouts) ===

TRAVELPAYOUTS_MARKER = os.getenv("TRAVELPAYOUTS_MARKER", "")
TRAVELPAYOUTS_PROJECT = os.getenv("TRAVELPAYOUTS_PROJECT", "")

# Маппинг стран → Airalo URL slug
_AIRALO_SLUGS = {
    "France": "france", "Germany": "germany", "Italy": "italy", "Spain": "spain",
    "United Kingdom": "united-kingdom", "United States": "united-states",
    "Turkey": "turkey", "Thailand": "thailand", "Japan": "japan", "China": "china",
    "South Korea": "south-korea", "India": "india", "Brazil": "brazil",
    "Mexico": "mexico", "Argentina": "argentina", "Australia": "australia",
    "Canada": "canada", "Egypt": "egypt", "Morocco": "morocco",
    "South Africa": "south-africa", "United Arab Emirates": "united-arab-emirates",
    "Singapore": "singapore", "Malaysia": "malaysia", "Indonesia": "indonesia",
    "Vietnam": "vietnam", "Philippines": "philippines",
    "Russia": "russia", "Czech Republic": "czech-republic", "Czechia": "czech-republic",
    "Poland": "poland", "Netherlands": "netherlands", "Belgium": "belgium",
    "Austria": "austria", "Switzerland": "switzerland", "Portugal": "portugal",
    "Greece": "greece", "Croatia": "croatia", "Hungary": "hungary",
    "Sweden": "sweden", "Norway": "norway", "Denmark": "denmark", "Finland": "finland",
    "Ireland": "ireland", "Israel": "israel", "Saudi Arabia": "saudi-arabia",
    "Qatar": "qatar", "Georgia": "georgia", "Armenia": "armenia",
    "Azerbaijan": "azerbaijan", "Kazakhstan": "kazakhstan", "Uzbekistan": "uzbekistan",
    "Montenegro": "montenegro", "Serbia": "serbia", "Romania": "romania",
    "Bulgaria": "bulgaria", "Sri Lanka": "sri-lanka", "Maldives": "maldives",
    "New Zealand": "new-zealand", "Colombia": "colombia", "Peru": "peru",
    "Chile": "chile", "Cuba": "cuba", "Dominican Republic": "dominican-republic",
    "Tunisia": "tunisia", "Jordan": "jordan", "Oman": "oman", "Bahrain": "bahrain",
    "Kuwait": "kuwait", "Taiwan": "taiwan", "Hong Kong": "hong-kong",
}

# Перевод названий стран EN → RU
_COUNTRY_RU = {
    "France": "Франция", "Germany": "Германия", "Italy": "Италия", "Spain": "Испания",
    "United Kingdom": "Великобритания", "United States": "США",
    "Turkey": "Турция", "Thailand": "Таиланд", "Japan": "Япония", "China": "Китай",
    "South Korea": "Южная Корея", "India": "Индия", "Brazil": "Бразилия",
    "Mexico": "Мексика", "Argentina": "Аргентина", "Australia": "Австралия",
    "Canada": "Канада", "Egypt": "Египет", "Morocco": "Марокко",
    "South Africa": "ЮАР", "United Arab Emirates": "ОАЭ",
    "Singapore": "Сингапур", "Malaysia": "Малайзия", "Indonesia": "Индонезия",
    "Vietnam": "Вьетнам", "Philippines": "Филиппины",
    "Russia": "Россия", "Czech Republic": "Чехия", "Czechia": "Чехия",
    "Poland": "Польша", "Netherlands": "Нидерланды", "Belgium": "Бельгия",
    "Austria": "Австрия", "Switzerland": "Швейцария", "Portugal": "Португалия",
    "Greece": "Греция", "Croatia": "Хорватия", "Hungary": "Венгрия",
    "Sweden": "Швеция", "Norway": "Норвегия", "Denmark": "Дания", "Finland": "Финляндия",
    "Ireland": "Ирландия", "Israel": "Израиль", "Saudi Arabia": "Саудовская Аравия",
    "Qatar": "Катар", "Georgia": "Грузия", "Armenia": "Армения",
    "Azerbaijan": "Азербайджан", "Kazakhstan": "Казахстан", "Uzbekistan": "Узбекистан",
    "Montenegro": "Черногория", "Serbia": "Сербия", "Romania": "Румыния",
    "Bulgaria": "Болгария", "Sri Lanka": "Шри-Ланка", "Maldives": "Мальдивы",
    "New Zealand": "Новая Зеландия", "Colombia": "Колумбия", "Peru": "Перу",
    "Chile": "Чили", "Cuba": "Куба", "Dominican Republic": "Доминикана",
    "Tunisia": "Тунис", "Jordan": "Иордания", "Oman": "Оман", "Bahrain": "Бахрейн",
    "Kuwait": "Кувейт", "Taiwan": "Тайвань", "Hong Kong": "Гонконг",
}


def _build_airalo_affiliate_link(airalo_path: str) -> str:
    """Формирует affiliate-ссылку Travelpayouts для Airalo."""
    direct_url = f"https://www.airalo.com/{airalo_path}"
    if TRAVELPAYOUTS_MARKER and TRAVELPAYOUTS_PROJECT:
        encoded = url_quote(direct_url, safe="")
        return (
            f"https://tp.media/r?marker={TRAVELPAYOUTS_MARKER}"
            f"&trs={TRAVELPAYOUTS_PROJECT}&p=8310"
            f"&u={encoded}&campaign_id=541"
        )
    return direct_url


@app.get("/esim/search")
async def search_esim(
    city: str = Query(..., description="City name"),
    lang: str = Query("ru"),
):
    """Поиск eSIM пакетов для страны назначения через Airalo (Travelpayouts affiliate)"""
    city_name = city.split(",")[0].strip()

    try:
        # 1. Определяем страну по городу через Nominatim
        country_en = None
        async with httpx.AsyncClient(timeout=10) as client:
            headers = {"User-Agent": "Luggify/1.0 (travel packing app)"}
            geo_resp = await client.get(NOMINATIM_URL, params={
                "q": city_name, "format": "json",
                "accept-language": "en", "limit": 1,
                "addressdetails": 1,
            }, headers=headers)
            if geo_resp.status_code == 200 and geo_resp.json():
                addr = geo_resp.json()[0].get("address", {})
                country_en = addr.get("country")

        if not country_en:
            # Фоллбэк: пробуем вытащить страну из запятой в названии
            if "," in city:
                country_part = city.split(",")[-1].strip()
                # Проверяем прямое совпадение
                for en_name, slug in _AIRALO_SLUGS.items():
                    if country_part.lower() == en_name.lower():
                        country_en = en_name
                        break
                # Проверяем русское название
                if not country_en:
                    for en_name, ru_name in _COUNTRY_RU.items():
                        if country_part.lower() == ru_name.lower():
                            country_en = en_name
                            break

        if not country_en:
            return {
                "esim": None,
                "browse_link": _build_airalo_affiliate_link(""),
            }

        # 2. Находим Airalo slug для страны
        slug = _AIRALO_SLUGS.get(country_en)
        if not slug:
            # Генерируем slug из названия
            slug = country_en.lower().replace(" ", "-")

        country_display = _COUNTRY_RU.get(country_en, country_en) if lang == "ru" else country_en

        # 3. Формируем eSIM данные
        esim_link = _build_airalo_affiliate_link(f"{slug}-esim")

        return {
            "esim": {
                "country": country_display,
                "country_en": country_en,
                "link": esim_link,
                "provider": "Airalo",
            },
            "browse_link": _build_airalo_affiliate_link(""),
        }

    except Exception as e:
        print(f"eSIM search error: {e}")
        return {
            "esim": None,
            "browse_link": _build_airalo_affiliate_link(""),
        }


async def get_weather_forecast_data(city: str, start_date: datetime.date, end_date: datetime.date, language: str = "ru") -> List[schemas.DailyForecast]:
    """Helper to fetch weather forecast for a checklist (used when viewing saved checklists)"""
    async with httpx.AsyncClient() as client:
        # 1. Geocoding
        headers = {"User-Agent": "Luggify/1.0 (travel packing app)"}
        try:
            geo_resp = await client.get(NOMINATIM_URL, params={
                "q": city.split(",")[0].strip(),
                "format": "json",
                "accept-language": "ru",
                "limit": 1,
            }, headers=headers)
            if geo_resp.status_code != 200:
                return []
            geo_data = geo_resp.json()
            if not geo_data:
                return []
            
            lat = float(geo_data[0]["lat"])
            lon = float(geo_data[0]["lon"])
        except Exception:
            return []

        # Dates setup
        # start_date/end_date passed as date objects
        today = datetime.now().date()
        forecast_limit = today + timedelta(days=15)
        
        daily_data = {}

        # 2. Forecast (Open-Meteo)
        if start_date <= forecast_limit:
            forecast_end = min(end_date, forecast_limit)
            try:
                resp = await client.get(OPEN_METEO_FORECAST_URL, params={
                    "latitude": lat,
                    "longitude": lon,
                    "daily": "temperature_2m_max,temperature_2m_min,weathercode",
                    "timezone": "auto",
                    "start_date": start_date.strftime("%Y-%m-%d"),
                    "end_date": forecast_end.strftime("%Y-%m-%d"),
                })
                if resp.status_code == 200:
                    d = resp.json().get("daily", {})
                    times = d.get("time", [])
                    maxs = d.get("temperature_2m_max", [])
                    mins = d.get("temperature_2m_min", [])
                    codes = d.get("weathercode", [])
                    for i, t in enumerate(times):
                        default_desc = "Unknown" if language != "ru" else "Неизвестно"
                        desc, icon = WMO_CODES.get(language, {}).get(codes[i], (default_desc, "01d"))
                        daily_data[t] = {
                            "temp_max": maxs[i],
                            "temp_min": mins[i],
                            "weathercode": codes[i],
                            "condition": desc,
                            "icon": icon,
                            "source": "forecast"
                        }
            except Exception:
                pass

        # 3. Historical (if needed)
        hist_start = max(start_date, forecast_limit + timedelta(days=1))
        if hist_start <= end_date:
            try:
                # Use last year data
                hist_start_ly = hist_start.replace(year=hist_start.year - 1)
                hist_end_ly = end_date.replace(year=end_date.year - 1)
                
                resp = await client.get(OPEN_METEO_HISTORICAL_URL, params={
                    "latitude": lat,
                    "longitude": lon,
                    "daily": "temperature_2m_max,temperature_2m_min,weathercode",
                    "timezone": "auto",
                    "start_date": hist_start_ly.strftime("%Y-%m-%d"),
                    "end_date": hist_end_ly.strftime("%Y-%m-%d"),
                })
                if resp.status_code == 200:
                    d = resp.json().get("daily", {})
                    times = d.get("time", [])
                    maxs = d.get("temperature_2m_max", [])
                    mins = d.get("temperature_2m_min", [])
                    codes = d.get("weathercode", [])
                    
                    # Compute invalid year diff to map back to requested dates
                    # But simpler: just iterate and map to hist_start + i days
                    current_hist_date = hist_start
                    for i, _ in enumerate(times):
                        if current_hist_date > end_date: break
                        
                        default_desc = "Unknown" if language != "ru" else "Неизвестно"
                        desc, icon = WMO_CODES.get(language, {}).get(codes[i], (default_desc, "01d"))
                        date_str = current_hist_date.strftime("%Y-%m-%d")
                        daily_data[date_str] = {
                            "temp_max": maxs[i],
                            "temp_min": mins[i],
                            "weathercode": codes[i],
                            "condition": desc,
                            "icon": icon,
                            "source": "historical"
                        }
                        current_hist_date += timedelta(days=1)
            except Exception:
                pass

        # Convert to list
        result = []
        for date_str in sorted(daily_data.keys()):
            item = daily_data[date_str]
            result.append(schemas.DailyForecast(
                date=date_str,
                temp_min=item["temp_min"],
                temp_max=item["temp_max"],
                condition=item["condition"],
                icon=item["icon"],
                source=item.get("source", "forecast"),
                city=item.get("city"),
                humidity=item.get("humidity"),
                uv_index=item.get("uv_index"),
                wind_speed=item.get("wind_speed")
            ))
        return result


@app.get("/geo/cities-autocomplete")
async def autocomplete_cities(namePrefix: str = Query(..., min_length=2)):
    """
    Гибридный автокомплит: Open-Meteo (быстро, короткие префиксы) + Nominatim (точность, полные названия).
    Объединяет результаты, убирает дубликаты.
    """
    results_open_meteo = []
    results_nominatim = []

    async def fetch_open_meteo():
        url = "https://geocoding-api.open-meteo.com/v1/search"
        params = {"name": namePrefix, "count": 5, "language": "ru", "format": "json"}
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    if "results" in data:
                        return data["results"]
        except Exception:
            pass
        return []

    async def fetch_nominatim():
        # Используем featuretype=city чтобы отсеять мусор, но это параметр reverse. 
        # Для search используем ограничение по addressdetails, но Nominatim всё равно возвращает разное.
        # Просто запрашиваем и потом фильтруем на клиенте (тут).
        params = {
            "q": namePrefix,
            "format": "json",
            "accept-language": "ru",
            "limit": 5,
            "addressdetails": 1,
        }
        headers = {"User-Agent": "Luggify/1.0 (travel packing app)"}
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(NOMINATIM_URL, params=params, headers=headers)
                if resp.status_code == 200:
                    return resp.json()
        except Exception:
            pass
        return []

    # Запускаем параллельно
    import asyncio
    res_om, res_nom = await asyncio.gather(fetch_open_meteo(), fetch_nominatim())

    final_results = []
    seen = set()

    # 1. Приоритет Open-Meteo (обычно релевантнее для префиксов)
    for item in res_om:
        city = item.get("name")
        country = item.get("country_code", "").upper()
        country_name = item.get("country", "")
        admin1 = item.get("admin1")
        
        # Фикс для "Молотов" -> "Пермь" (если вдруг API возвращает старое название)
        # Но массово это не исправить, надеемся на Nominatim
        
        key = f"{city}:{country}:{admin1}"
        if key in seen: continue
        seen.add(key)

        parts = [city]
        if admin1 and admin1 != city: parts.append(admin1)
        if country_name: parts.append(country_name)
        
        final_results.append({
            "name": city,
            "country": country,
            "country_name": country_name,
            "admin1": admin1,
            "lat": item.get("latitude"),
            "lon": item.get("longitude"),
            "fullName": ", ".join(parts),
            "source": "om"
        })

    # 2. Добавляем Nominatim (если такого города ещё нет)
    for item in res_nom:
        addr = item.get("address", {})
        # Извлекаем город
        city = addr.get("city") or addr.get("town") or addr.get("village") or item.get("name")
        if not city: continue
        
        country = addr.get("country_code", "").upper()
        country_name = addr.get("country", "")
        admin1 = addr.get("state", "")

        # Пропускаем, если название совсем не похоже на запрос (Nominatim иногда ищет по улицам)
        # if namePrefix.lower() not in city.lower(): continue # Слишком строго

        key = f"{city}:{country}:{admin1}"
        
        # Nominatim часто возвращает дубли
        if key in seen: continue
        
        # Если такого ключа нет, но координаты ОЧЕНЬ близко к уже найденному -> тоже дубль
        is_duplicate_coord = False
        lat, lon = float(item["lat"]), float(item["lon"])
        for exist in final_results:
            if abs(exist["lat"] - lat) < 0.1 and abs(exist["lon"] - lon) < 0.1:
                is_duplicate_coord = True
                break
        
        if is_duplicate_coord: continue

        seen.add(key)
        
        parts = [city]
        if admin1 and admin1 != city: parts.append(admin1)
        if country_name: parts.append(country_name)

        final_results.append({
            "name": city,
            "country": country,
            "country_name": country_name,
            "admin1": admin1,
            "lat": lat,
            "lon": lon,
            "fullName": ", ".join(parts),
            "source": "nom"
        })

    return final_results

async def calculate_packing_data(
    city: str,
    start_date_str: str,
    end_date_str: str,
    trip_profile: dict | None,
    transport: str,
    gender: str,
    traveling_with_pet: bool,
    has_allergies: bool,
    traveling_with_children: bool,
    language: str = "ru"
):
    # 1. Geocoding
    async with httpx.AsyncClient() as client:
        headers = {"User-Agent": "Luggify/1.0"}
        try:
            geo_resp = await client.get(NOMINATIM_URL, params={
                "q": city.split(",")[0].strip(),
                "format": "json",
                "accept-language": language,
                "limit": 1,
                "addressdetails": 1
            }, headers=headers)
            if geo_resp.status_code != 200 or not geo_resp.json():
                raise HTTPException(status_code=404, detail=f"Город {city} не найден")
            geo_data = geo_resp.json()
        except Exception as e:
            print(f"Geocoding error for {city}: {e}")
            raise HTTPException(status_code=404, detail=f"Ошибка БД: 404: Город {city} не найден ({str(e)})")

        lat = float(geo_data[0]["lat"])
        lon = float(geo_data[0]["lon"])
        addr = geo_data[0].get("address", {})
        country = addr.get("country_code", "").upper()

        start_dt = datetime.strptime(start_date_str, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date_str, "%Y-%m-%d")
        today = datetime.now().date()

        forecast_limit = today + timedelta(days=15)
        daily_data = {}

        # 1) Open-Meteo Forecast
        if start_dt.date() <= forecast_limit:
            forecast_end = min(end_dt.date(), forecast_limit)
            try:
                resp = await client.get(OPEN_METEO_FORECAST_URL, params={
                    "latitude": lat,
                    "longitude": lon,
                    "daily": "temperature_2m_max,temperature_2m_min,weathercode,relative_humidity_2m_mean,uv_index_max,wind_speed_10m_max",
                    "timezone": "auto",
                    "start_date": start_dt.strftime("%Y-%m-%d"),
                    "end_date": forecast_end.strftime("%Y-%m-%d"),
                })
                if resp.status_code == 200:
                    d = resp.json().get("daily", {})
                    times = d.get("time", [])
                    maxs = d.get("temperature_2m_max", [])
                    mins = d.get("temperature_2m_min", [])
                    codes = d.get("weathercode", [])
                    hums = d.get("relative_humidity_2m_mean", [])
                    uvs = d.get("uv_index_max", [])
                    winds = d.get("wind_speed_10m_max", [])
                    
                    for i, t in enumerate(times):
                        default_desc = "Unknown" if language != "ru" else "Неизвестно"
                        desc, icon = WMO_CODES.get(language if language in WMO_CODES else "ru", {}).get(codes[i], (default_desc, "01d"))
                        daily_data[t] = {
                            "temp_max": maxs[i],
                            "temp_min": mins[i],
                            "weathercode": codes[i],
                            "condition": desc,
                            "icon": icon,
                            "source": "forecast",
                            "city": city.split(",")[0].strip(),
                            "humidity": hums[i] if i < len(hums) else None,
                            "uv_index": uvs[i] if i < len(uvs) else None,
                            "wind_speed": winds[i] if i < len(winds) else None,
                        }

            except Exception as e:
                print(f"Forecast error: {e}")

        # 2) Historical
        hist_start = max(start_dt.date(), forecast_limit + timedelta(days=1))
        if hist_start <= end_dt.date():
            try:
                hist_start_ly = hist_start.replace(year=hist_start.year - 1)
                hist_end_ly = end_dt.date().replace(year=end_dt.date().year - 1)
                
                resp = await client.get(OPEN_METEO_HISTORICAL_URL, params={
                    "latitude": lat,
                    "longitude": lon,
                    "daily": "temperature_2m_max,temperature_2m_min,weathercode,relative_humidity_2m_mean,wind_speed_10m_max",
                    "timezone": "auto",
                    "start_date": hist_start_ly.strftime("%Y-%m-%d"),
                    "end_date": hist_end_ly.strftime("%Y-%m-%d"),
                })
                if resp.status_code == 200:
                    d = resp.json().get("daily", {})
                    times = d.get("time", [])
                    maxs = d.get("temperature_2m_max", [])
                    mins = d.get("temperature_2m_min", [])
                    codes = d.get("weathercode", [])
                    hums = d.get("relative_humidity_2m_mean", [])
                    winds = d.get("wind_speed_10m_max", [])
                    
                    current_hist_date = hist_start
                    for i, _ in enumerate(times):
                        if current_hist_date > end_dt.date(): break
                        default_desc = "Unknown" if language != "ru" else "Неизвестно"
                        desc, icon = WMO_CODES.get(language, {}).get(codes[i], (default_desc, "01d"))
                        date_str = current_hist_date.strftime("%Y-%m-%d")
                        daily_data[date_str] = {
                            "temp_max": maxs[i],
                            "temp_min": mins[i],
                            "weathercode": codes[i],
                            "condition": desc,
                            "icon": icon,
                            "source": "historical",
                            "city": city.split(",")[0].strip(), # Add city
                            "humidity": hums[i] if i < len(hums) else None,
                            "uv_index": None,
                            "wind_speed": winds[i] if i < len(winds) else None,
                        }
                        current_hist_date += timedelta(days=1)
            except Exception as e:
                print(f"Historical error: {e}")

    # Process weather data
    daily_forecast = []
    temps = []
    conditions = set()
    humidities = []
    uv_indices = []
    wind_speeds = []

    for date_str in sorted(daily_data.keys()):
        item = daily_data[date_str]
        daily_forecast.append(schemas.DailyForecast(
            date=date_str,
            temp_min=item["temp_min"],
            temp_max=item["temp_max"],
            condition=item["condition"],
            icon=item["icon"],
            source=item.get("source", "forecast"),
            city=item.get("city"),
            humidity=item.get("humidity"),
            uv_index=item.get("uv_index"),
            wind_speed=item.get("wind_speed")
        ))
        temps.append((item["temp_min"] + item["temp_max"]) / 2)
        conditions.add(item["condition"])
        if item["humidity"]: humidities.append(item["humidity"])
        if item["uv_index"]: uv_indices.append(item["uv_index"])
        if item["wind_speed"]: wind_speeds.append(item["wind_speed"])

    avg_temp = round(sum(temps) / len(temps), 1) if temps else None

    # Calculate trip duration
    try:
        trip_days = (end_dt.date() - start_dt.date()).days + 1
    except:
        trip_days = (end_dt - start_dt).days + 1
    trip_days = max(trip_days, 1)
    min_temp = min(daily_data[d]["temp_min"] for d in daily_data) if daily_data else 15
    max_temp = max(daily_data[d]["temp_max"] for d in daily_data) if daily_data else 20
    recommendation_bundle = build_packing_recommendations(
        language=language,
        trip_days=trip_days,
        avg_temp=avg_temp,
        min_temp=min_temp,
        max_temp=max_temp,
        conditions=conditions,
        humidities=humidities,
        uv_indices=uv_indices,
        wind_speeds=wind_speeds,
        country=country,
        transport=transport,
        gender=gender,
        traveling_with_pet=traveling_with_pet,
        has_allergies=has_allergies,
        traveling_with_children=traveling_with_children,
        trip_profile=trip_profile,
    )

    return {
        "items": recommendation_bundle["items"],
        "item_quantities": recommendation_bundle["item_quantities"],
        "avg_temp": avg_temp,
        "conditions": list(conditions),
        "daily_forecast": daily_forecast,
        "country": country,
        "start_date": start_dt.date(),
        "end_date": end_dt.date(),
        "trip_profile": recommendation_bundle["trip_profile"],
    }

async def create_checklist_from_items(
    db,
    items,
    city,
    start_date,
    end_date,
    avg_temp,
    conditions,
    daily_forecast,
    item_quantities=None,
    trip_profile=None,
    user_id=None,
    language="ru",
    origin_city="",
    transports=None,
    participant_baggage_payloads: dict[int, dict[str, Any]] | None = None,
):
    # Categorization logic
    mapping = get_category_map(language)
    categories = {k: [] for k in mapping.keys()}
    fallback_category = "Misc" if language == "en" and "Misc" in categories else "Прочее"
    
    # Always add essentials
    items.update([get_item("passport", language), get_item("insurance", language), get_item("money", language), get_item("tickets", language), get_item("booking", language)])
    normalized_quantities = dict(item_quantities or {})
    for item in items:
        normalized_quantities[item] = max(int(normalized_quantities.get(item, 1) or 1), 1)
    
    for item in items:
        found = False
        for cat, keywords in mapping.items():
            if any(k.lower() in item.lower() for k in keywords):
                categories[cat].append(item)
                found = True
                break
        if not found:
            categories[fallback_category].append(item)

    for k in categories:
        categories[k] = list(sorted(set(categories[k])))
        
    all_items = []
    for k, v in categories.items():
        all_items.extend(v)
    item_categories = infer_item_categories(all_items, language)

    checklist_data = schemas.ChecklistCreate(
        city=city,
        start_date=start_date,
        end_date=end_date,
        items=[] if participant_baggage_payloads else all_items,
        avg_temp=avg_temp,
        conditions=sorted(list(conditions)),
        item_quantities={} if participant_baggage_payloads else normalized_quantities,
        item_categories={} if participant_baggage_payloads else item_categories,
        daily_forecast=[schemas.DailyForecast(**d) if isinstance(d, dict) else d for d in daily_forecast] if daily_forecast else None,
        user_id=user_id,
        origin_city=origin_city or None,
        transports=transports,
        trip_type=(trip_profile or {}).get("trip_type"),
        trip_profile=schemas.TripProfileData(**(trip_profile or {})),
    )
    checklist = await crud.create_checklist(db, checklist_data)

    if participant_baggage_payloads:
        for participant_user_id, participant_payload in participant_baggage_payloads.items():
            await ensure_default_baggage_for_participant(
                db,
                checklist,
                participant_user_id,
                items=participant_payload.get("items"),
                item_quantities=participant_payload.get("item_quantities"),
                item_categories=participant_payload.get("item_categories"),
            )
        checklist = await crud.get_checklist_by_slug(db, checklist.slug)
    
    return await build_checklist_response_payload(checklist, user_id)

# ==================== AI ASSISTANT ====================

class AIAskRequest(BaseModel):
    city: str
    question: str
    language: str = "ru"
    start_date: str = ""
    end_date: str = ""
    avg_temp: Optional[float] = None
    trip_type: str = "city_break"
    trip_profile: Optional[Dict[str, Any]] = None


class ChecklistAssistantAskRequest(BaseModel):
    question: str
    language: str = "ru"


def _serialize_forecast_context(forecast: list[Any] | None) -> list[dict[str, Any]]:
    serialized: list[dict[str, Any]] = []
    for entry in forecast or []:
        if isinstance(entry, dict):
            serialized.append(
                {
                    "date": entry.get("date"),
                    "condition": entry.get("condition"),
                    "temp_min": entry.get("temp_min"),
                    "temp_max": entry.get("temp_max"),
                    "source": entry.get("source"),
                }
            )
            continue
        serialized.append(
            {
                "date": getattr(entry, "date", None),
                "condition": getattr(entry, "condition", None),
                "temp_min": getattr(entry, "temp_min", None),
                "temp_max": getattr(entry, "temp_max", None),
                "source": getattr(entry, "source", None),
            }
        )
    return serialized


def _serialize_itinerary_events(events: list[Any] | None) -> list[dict[str, Any]]:
    serialized: list[dict[str, Any]] = []
    for event in events or []:
        serialized.append(
            {
                "event_id": getattr(event, "id", None),
                "event_date": getattr(event, "event_date", None),
                "time": getattr(event, "time", None),
                "title": getattr(event, "title", None),
                "address": getattr(event, "address", None),
                "description": getattr(event, "description", None),
            }
        )
    return serialized


async def _get_cached_attractions_for_assistant(
    db: AsyncSession,
    city: str,
    language: str,
    limit: int = 14,
) -> list[dict[str, Any]]:
    city_name = city.split(",")[0].strip().lower()
    if not city_name:
        return []

    result = await db.execute(
        select(models.CityAttraction)
        .where(models.CityAttraction.city_name.like(f"{city_name}_{language}_%"))
        .order_by(models.CityAttraction.updated_at.desc())
        .limit(1)
    )
    cached = result.scalar_one_or_none()
    if not cached or not isinstance(cached.data, list):
        return []

    attractions: list[dict[str, Any]] = []
    for attraction in cached.data[:limit]:
        if not isinstance(attraction, dict):
            continue
        attractions.append(
            {
                "name": attraction.get("name"),
                "address": attraction.get("address"),
                "description": attraction.get("description"),
                "lat": attraction.get("lat"),
                "lng": attraction.get("lng"),
                "rating": attraction.get("rating"),
                "price_level": attraction.get("price_level"),
                "place_type": attraction.get("place_type") or attraction.get("type"),
                "link": attraction.get("link"),
                "image": attraction.get("image"),
                "image_position": attraction.get("image_position"),
            }
        )
    return attractions

@app.post("/ai/ask", response_model=schemas.AssistantAskResponse)
async def ai_ask(data: AIAskRequest):
    """AI-ассистент для путешествий"""
    from ai_service import ask_travel_ai
    trip_context = build_ad_hoc_trip_context(
        city=data.city,
        start_date=data.start_date,
        end_date=data.end_date,
        avg_temp=data.avg_temp,
        trip_type=data.trip_type,
        trip_profile=data.trip_profile,
        language=data.language,
    )
    result = await ask_travel_ai(
        city=data.city,
        question=data.question,
        language=data.language,
        start_date=data.start_date,
        end_date=data.end_date,
        avg_temp=data.avg_temp,
        trip_type=data.trip_type,
        trip_profile=data.trip_profile,
        trip_context=trip_context,
    )
    return result


@app.post("/checklists/{slug}/assistant/ask", response_model=schemas.AssistantAskResponse)
async def checklist_assistant_ask(
    slug: str,
    data: ChecklistAssistantAskRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[models.User] = Depends(get_current_user),
):
    """AI-ассистент с контекстом конкретной поездки."""
    from ai_service import ask_travel_ai

    checklist = await crud.get_checklist_by_slug(db, slug)
    if not checklist:
        raise HTTPException(status_code=404, detail="Чеклист не найден")

    if not checklist.is_public and not (current_user and is_checklist_participant(checklist, current_user.id)):
        raise HTTPException(status_code=403, detail="Нет доступа к этой поездке")

    forecast = checklist.daily_forecast
    if not forecast:
        try:
            forecast = await get_weather_forecast_data(
                checklist.city,
                checklist.start_date,
                checklist.end_date,
                language=data.language,
            )
        except Exception:
            forecast = []

    trip_context = build_trip_context(
        checklist,
        viewer_user_id=current_user.id if current_user else None,
        language=data.language,
        forecast=forecast,
        cached_attractions=await _get_cached_attractions_for_assistant(db, checklist.city, data.language),
    )
    result = await ask_travel_ai(
        city=checklist.city,
        question=data.question,
        language=data.language,
        trip_context=trip_context,
    )
    return result


@app.post("/checklists/{slug}/assistant/apply-plan", response_model=schemas.AssistantPlanApplyResponse)
async def checklist_assistant_apply_plan(
    slug: str,
    payload: schemas.AssistantPlanApplyRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_current_user),
):
    checklist = await crud.get_checklist_by_slug(db, slug)
    if not checklist:
        raise HTTPException(status_code=404, detail="Чеклист не найден")
    if not is_checklist_participant(checklist, user.id):
        raise HTTPException(status_code=403, detail="Нет доступа к этому чеклисту")

    try:
        apply_result = await apply_plan_proposals_to_checklist(db, checklist, payload.proposals)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    updated_checklist = await crud.get_checklist_by_slug(db, slug)
    return {
        "applied_count": apply_result["applied_count"],
        "created_event_ids": apply_result["created_event_ids"],
        "checklist": await build_checklist_response_payload(updated_checklist, user.id),
    }


def _sorted_events_with_coordinates(checklist: models.Checklist) -> list[models.ItineraryEvent]:
    events = [
        event for event in (checklist.events or [])
        if getattr(event, "lat", None) is not None and getattr(event, "lng", None) is not None
    ]
    return sorted(
        events,
        key=lambda event: (
            event.event_date or date.max,
            event.time or "99:99",
            event.id or 0,
        ),
    )


def parse_time_to_minutes(value: str | None) -> int | None:
    normalized = str(value or "").strip()
    match = re.match(r"^(\d{2}):(\d{2})$", normalized)
    if not match:
        return None
    hours = int(match.group(1))
    minutes = int(match.group(2))
    if hours > 23 or minutes > 59:
        return None
    return hours * 60 + minutes


def _pick_restaurant_anchor(
    checklist: models.Checklist,
    payload: schemas.AssistantRestaurantSearchRequest,
) -> models.ItineraryEvent | None:
    events = _sorted_events_with_coordinates(checklist)
    if not events:
        return None
    if payload.anchor_event_id:
        for event in events:
            if event.id == payload.anchor_event_id:
                return event
    if payload.event_date:
        same_day = [event for event in events if event.event_date == payload.event_date]
        if same_day:
            target_minutes = parse_time_to_minutes(_normalize_event_time(payload.time))
            normalized_meal = str(payload.meal_type or payload.day_part or "").strip().lower()
            if target_minutes is not None:
                before = [
                    event for event in same_day
                    if parse_time_to_minutes(event.time) is not None and parse_time_to_minutes(event.time) <= target_minutes
                ]
                if before:
                    return before[-1]
                if normalized_meal in {"breakfast", "morning", "завтрак", "утро"}:
                    return same_day[0]
            return same_day[-1]
        return None
    return events[-1]


async def _resolve_location_coordinates(location_name: str) -> tuple[float, float] | None:
    normalized_location = re.sub(r"\s+", " ", location_name or "").strip()
    if not normalized_location:
        return None
    cache_key = normalized_location.casefold()
    if cache_key in LOCATION_COORDS_CACHE:
        return LOCATION_COORDS_CACHE[cache_key]
    headers = {"User-Agent": "Luggify/1.0 (travel route planning app)"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                NOMINATIM_URL,
                params={
                    "q": normalized_location,
                    "format": "json",
                    "limit": 1,
                    "addressdetails": 1,
                },
                headers=headers,
            )
        if resp.status_code == 200:
            data = resp.json()
            if data:
                lat = float(data[0]["lat"])
                lng = float(data[0]["lon"])
                LOCATION_COORDS_CACHE[cache_key] = (lat, lng)
                return LOCATION_COORDS_CACHE[cache_key]
    except Exception:
        pass
    LOCATION_COORDS_CACHE[cache_key] = None
    return None


def _default_food_time(day_part: str | None) -> str | None:
    normalized = str(day_part or "").strip().lower()
    if normalized in {"morning", "breakfast", "утро", "завтрак"}:
        return "09:00"
    if normalized in {"evening", "dinner", "вечер", "ужин"}:
        return "19:00"
    if normalized in {"day", "afternoon", "lunch", "день", "обед"}:
        return "13:00"
    return None


def _normalize_event_time(value: str | None) -> str | None:
    normalized = str(value or "").strip()
    return normalized if re.match(r"^\d{2}:\d{2}$", normalized) else None


@app.post("/checklists/{slug}/assistant/restaurant-options", response_model=schemas.AssistantRestaurantOptionsResponse)
async def checklist_assistant_restaurant_options(
    slug: str,
    payload: schemas.AssistantRestaurantSearchRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_current_user),
):
    checklist = await crud.get_checklist_by_slug(db, slug)
    if not checklist:
        raise HTTPException(status_code=404, detail="Чеклист не найден")
    if not is_checklist_participant(checklist, user.id):
        raise HTTPException(status_code=403, detail="Нет доступа к этому чеклисту")

    anchor = _pick_restaurant_anchor(checklist, payload)
    lat = payload.lat
    lng = payload.lng
    event_date = payload.event_date
    if anchor:
        lat = lat if lat is not None else anchor.lat
        lng = lng if lng is not None else anchor.lng
        event_date = event_date or anchor.event_date
    if lat is None or lng is None:
        city_coords = await _resolve_location_coordinates(checklist.city)
        if city_coords:
            lat, lng = city_coords
    if lat is None or lng is None:
        return {
            "options": [],
            "anchor_event_id": None,
            "anchor_title": None,
            "event_date": event_date or checklist.start_date,
            "time": _normalize_event_time(payload.time),
            "day_part": payload.day_part or "day",
            "provider": "geoapify",
            "attribution": "Geoapify",
            "configured": bool(os.getenv("GEOAPIFY_API_KEY", "").strip()),
            "message": "Добавьте точку с координатами в маршрут, чтобы искать места рядом.",
        }

    try:
        result = await search_nearby_restaurants(
            lat=float(lat),
            lng=float(lng),
            language=payload.language,
            radius_meters=payload.radius_meters,
            limit=payload.limit,
            meal_type=payload.meal_type,
        )
    except httpx.HTTPError as exc:
        print(f"[Geoapify restaurants] search failed: {exc}")
        raise HTTPException(status_code=502, detail="Не удалось получить варианты ресторанов")

    used_place_names = {
        str(event.title or "").strip().casefold()
        for event in (checklist.events or [])
        if str(getattr(event, "event_type", "") or "").lower() == "food" and str(event.title or "").strip()
    }
    options = [
        option for option in (result.get("options") or [])
        if str(option.get("name") or "").strip().casefold() not in used_place_names
    ]
    message = None
    if not result.get("configured"):
        message = "GEOAPIFY_API_KEY не настроен. Добавьте ключ, чтобы искать рестораны рядом."
    elif not options:
        message = "Рядом не нашлось уверенных вариантов. Можно попробовать увеличить радиус."

    return {
        "options": options,
        "anchor_event_id": anchor.id if anchor else None,
        "anchor_title": anchor.title if anchor else None,
        "event_date": event_date or checklist.start_date,
        "time": _normalize_event_time(payload.time),
        "day_part": payload.day_part or "day",
        "provider": result.get("provider") or "geoapify",
        "attribution": result.get("attribution"),
        "configured": bool(result.get("configured", True)),
        "message": message,
    }


@app.post("/checklists/{slug}/assistant/apply-restaurant", response_model=schemas.AssistantRestaurantApplyResponse)
async def checklist_assistant_apply_restaurant(
    slug: str,
    payload: schemas.AssistantRestaurantApplyRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_current_user),
):
    checklist = await crud.get_checklist_by_slug(db, slug)
    if not checklist:
        raise HTTPException(status_code=404, detail="Чеклист не найден")
    if not is_checklist_participant(checklist, user.id):
        raise HTTPException(status_code=403, detail="Нет доступа к этому чеклисту")
    if payload.event_date < checklist.start_date or payload.event_date > checklist.end_date:
        raise HTTPException(status_code=400, detail="Дата события вне диапазона поездки")

    anchor = _pick_restaurant_anchor(
        checklist,
        schemas.AssistantRestaurantSearchRequest(
            anchor_event_id=payload.anchor_event_id,
            event_date=payload.event_date,
        ),
    )
    distance_km = None
    if anchor and anchor.lat is not None and anchor.lng is not None:
        distance_km = haversine_distance_km(
            (float(anchor.lat), float(anchor.lng)),
            (float(payload.option.lat), float(payload.option.lng)),
        )

    created_event = await crud.create_itinerary_event(
        db,
        checklist.id,
        schemas.ItineraryEventCreate(
            event_date=payload.event_date,
            time=_normalize_event_time(payload.time) or _default_food_time(payload.day_part),
            title=payload.option.name.strip(),
            description=payload.option.description,
            address=payload.option.address,
            lat=payload.option.lat,
            lng=payload.option.lng,
            place_source=payload.option.source or "geoapify",
            duration_minutes=75,
            travel_buffer_minutes=estimate_travel_buffer_minutes(distance_km),
            event_type="food",
            meta={
                "day_part": payload.day_part or "day",
                "source": "restaurant_choice",
                "anchor_event_id": payload.anchor_event_id,
                "map_url": payload.option.map_url,
                "category": payload.option.category,
                "distance_meters": payload.option.distance_meters,
                "provider": payload.option.source or "geoapify",
                "provider_attribution": "Geoapify | OpenStreetMap contributors",
                "place_meta": payload.option.meta or {},
            },
        ),
    )
    updated_checklist = await crud.get_checklist_by_slug(db, slug)
    return {
        "created_event_id": created_event.id,
        "checklist": await build_checklist_response_payload(updated_checklist, user.id),
    }


@app.post("/checklists/{slug}/assistant/apply-event-changes", response_model=schemas.AssistantEventChangesApplyResponse)
async def checklist_assistant_apply_event_changes(
    slug: str,
    payload: schemas.AssistantEventChangesApplyRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_current_user),
):
    checklist = await crud.get_checklist_by_slug(db, slug)
    if not checklist:
        raise HTTPException(status_code=404, detail="Чеклист не найден")
    if not is_checklist_participant(checklist, user.id):
        raise HTTPException(status_code=403, detail="Нет доступа к этому чеклисту")

    checklist_event_ids = {event.id for event in (checklist.events or [])}
    created_event_ids: list[int] = []
    updated_event_ids: list[int] = []
    deleted_event_ids: list[int] = []
    applied_count = 0

    for proposal in payload.proposals:
        if proposal.action == "create":
            if not proposal.event_date or not proposal.title:
                raise HTTPException(status_code=400, detail="Для нового события нужны дата и название")
            created = await crud.create_itinerary_event(
                db,
                checklist.id,
                schemas.ItineraryEventCreate(
                    event_date=proposal.event_date,
                    time=proposal.time,
                    title=proposal.title,
                    description=proposal.description,
                    address=proposal.address,
                    event_type="custom",
                    meta={"source": "assistant_event_change", "reason": proposal.reason},
                ),
            )
            created_event_ids.append(created.id)
            applied_count += 1
            continue

        if proposal.target_event_id not in checklist_event_ids:
            raise HTTPException(status_code=400, detail="Предложение ссылается на событие вне этого маршрута")
        if proposal.action == "delete":
            deleted = await crud.delete_itinerary_event(db, proposal.target_event_id)
            if deleted:
                deleted_event_ids.append(proposal.target_event_id)
                applied_count += 1
            continue

        event_update = schemas.ItineraryEventUpdate(
            event_date=proposal.event_date,
            time=proposal.time,
            title=proposal.title,
            description=proposal.description,
            address=proposal.address,
        )
        updated = await crud.update_itinerary_event(db, proposal.target_event_id, event_update)
        if updated:
            updated_event_ids.append(proposal.target_event_id)
            applied_count += 1

    updated_checklist = await crud.get_checklist_by_slug(db, slug)
    return {
        "applied_count": applied_count,
        "created_event_ids": created_event_ids,
        "updated_event_ids": updated_event_ids,
        "deleted_event_ids": deleted_event_ids,
        "checklist": await build_checklist_response_payload(updated_checklist, user.id),
    }


@app.post("/checklists/{slug}/assistant/apply-packing-recommendations", response_model=schemas.AssistantPackingApplyResponse)
async def checklist_assistant_apply_packing_recommendations(
    slug: str,
    payload: schemas.AssistantPackingApplyRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_current_user),
):
    from packing_apply import apply_packing_recommendations

    checklist = await crud.get_checklist_by_slug(db, slug)
    if not checklist:
        raise HTTPException(status_code=404, detail="Чеклист не найден")
    if not is_checklist_participant(checklist, user.id):
        raise HTTPException(status_code=403, detail="Нет доступа к этому чеклисту")

    result = await apply_packing_recommendations(
        db,
        checklist,
        payload.recommendations,
        actor_user_id=user.id,
        language=payload.language,
    )
    return {
        "applied_count": result["applied_count"],
        "actions": result["actions"],
        "skipped": result["skipped"],
        "checklist": await build_checklist_response_payload(result["checklist"], user.id),
    }


@app.post("/checklists/{slug}/assistant/apply-expenses", response_model=schemas.AssistantExpenseApplyResponse)
async def checklist_assistant_apply_expenses(
    slug: str,
    payload: schemas.AssistantExpenseApplyRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_current_user),
):
    checklist = await crud.get_checklist_by_slug(db, slug)
    if not checklist:
        raise HTTPException(status_code=404, detail="Чеклист не найден")
    if not is_checklist_participant(checklist, user.id):
        raise HTTPException(status_code=403, detail="Нет доступа к этому чеклисту")

    applied_count = 0
    created_expense_ids: list[int] = []
    for proposal in payload.proposals:
        if proposal.action in {"set_budget", "set_daily_budget"}:
            if proposal.base_currency:
                checklist.expense_base_currency = normalize_currency(proposal.base_currency, checklist.expense_base_currency or "RUB")
            if proposal.budget_amount is not None:
                checklist.expense_budget_amount = float(proposal.budget_amount)
            if proposal.daily_budget_amount is not None:
                trip_profile = dict(checklist.trip_profile or {})
                expense_profile = dict(trip_profile.get("expenses") or {})
                expense_profile["daily_budget_amount"] = float(proposal.daily_budget_amount)
                trip_profile["expenses"] = expense_profile
                checklist.trip_profile = trip_profile
            applied_count += 1
            continue

        if proposal.action == "create" and proposal.title and proposal.amount is not None:
            base_currency = normalize_currency(checklist.expense_base_currency, "RUB")
            currency = normalize_currency(proposal.currency, base_currency)
            conversion = await build_expense_conversion(float(proposal.amount), currency, base_currency)
            expense = await crud.create_trip_expense(
                db,
                checklist.id,
                schemas.TripExpenseCreate(
                    expense_date=proposal.expense_date,
                    title=proposal.title,
                    category=proposal.category or "other",
                    amount=float(proposal.amount),
                    currency=currency,
                    note=proposal.note,
                ),
                created_by_user_id=user.id,
                amount_base=float(conversion["amount"]),
                base_currency=base_currency,
                fx_rate=float(conversion["rate"]),
                fx_rate_date=str(conversion.get("rate_date") or ""),
                fx_provider=str(conversion.get("provider") or ""),
            )
            created_expense_ids.append(expense.id)
            applied_count += 1

    await db.commit()
    updated_checklist = await crud.get_checklist_by_slug(db, slug)
    return {
        "applied_count": applied_count,
        "created_expense_ids": created_expense_ids,
        "checklist": await build_checklist_response_payload(updated_checklist, user.id),
    }


@app.get("/checklists/{slug}/expenses", response_model=schemas.TripExpenseListResponse)
async def get_checklist_expenses(
    slug: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[models.User] = Depends(get_current_user),
):
    checklist = await crud.get_checklist_by_slug(db, slug)
    if not checklist:
        raise HTTPException(status_code=404, detail="Чеклист не найден")
    viewer_id = current_user.id if current_user else None
    if not checklist.is_public and not (viewer_id and is_checklist_participant(checklist, viewer_id)):
        raise HTTPException(status_code=403, detail="Нет доступа к этому чеклисту")

    visible_expenses = get_visible_expenses_for_viewer(checklist, viewer_id)
    expenses_visible = can_view_expenses(checklist, viewer_id)
    return {
        "expenses": visible_expenses,
        "summary": build_expense_summary(checklist, visible_expenses, expose_budget=expenses_visible),
        "checklist": await build_checklist_response_payload(checklist, viewer_id),
    }


@app.patch("/checklists/{slug}/expenses/settings", response_model=schemas.TripExpenseListResponse)
async def update_expense_settings(
    slug: str,
    payload: schemas.TripExpenseSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_current_user),
):
    checklist = await crud.get_checklist_by_slug(db, slug)
    if not checklist:
        raise HTTPException(status_code=404, detail="Чеклист не найден")
    if not is_checklist_participant(checklist, user.id):
        raise HTTPException(status_code=403, detail="Нет доступа к этому чеклисту")

    next_base_currency = normalize_currency(payload.base_currency, checklist.expense_base_currency or "RUB")
    if payload.budget_amount is not None:
        checklist.expense_budget_amount = float(payload.budget_amount)
    if payload.daily_budget_amount is not None:
        trip_profile = dict(checklist.trip_profile or {})
        expense_profile = dict(trip_profile.get("expenses") or {})
        expense_profile["daily_budget_amount"] = float(payload.daily_budget_amount)
        trip_profile["expenses"] = expense_profile
        checklist.trip_profile = trip_profile
    if next_base_currency != (checklist.expense_base_currency or "RUB"):
        checklist.expense_base_currency = next_base_currency
        for expense in checklist.expenses or []:
            conversion = await build_expense_conversion(expense.amount, expense.currency, next_base_currency)
            expense.amount_base = float(conversion["amount"])
            expense.base_currency = next_base_currency
            expense.fx_rate = float(conversion["rate"])
            expense.fx_rate_date = str(conversion.get("rate_date") or "")
            expense.fx_provider = str(conversion.get("provider") or "")
    await db.commit()
    await db.refresh(checklist)
    visible_expenses = get_visible_expenses_for_viewer(checklist, user.id)
    return {
        "expenses": visible_expenses,
        "summary": build_expense_summary(checklist, visible_expenses),
        "checklist": await build_checklist_response_payload(checklist, user.id),
    }


@app.post("/checklists/{slug}/expenses", response_model=schemas.TripExpenseListResponse)
async def create_checklist_expense(
    slug: str,
    payload: schemas.TripExpenseCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_current_user),
):
    checklist = await crud.get_checklist_by_slug(db, slug)
    if not checklist:
        raise HTTPException(status_code=404, detail="Чеклист не найден")
    if not is_checklist_participant(checklist, user.id):
        raise HTTPException(status_code=403, detail="Нет доступа к этому чеклисту")

    base_currency = normalize_currency(checklist.expense_base_currency, "RUB")
    currency = normalize_currency(payload.currency, base_currency)
    conversion = await build_expense_conversion(payload.amount, currency, base_currency)
    expense_data = payload.model_copy(update={"currency": currency})
    await crud.create_trip_expense(
        db,
        checklist.id,
        expense_data,
        created_by_user_id=user.id,
        amount_base=float(conversion["amount"]),
        base_currency=base_currency,
        fx_rate=float(conversion["rate"]),
        fx_rate_date=str(conversion.get("rate_date") or ""),
        fx_provider=str(conversion.get("provider") or ""),
    )
    updated_checklist = await crud.get_checklist_by_slug(db, slug)
    visible_expenses = get_visible_expenses_for_viewer(updated_checklist, user.id)
    return {
        "expenses": visible_expenses,
        "summary": build_expense_summary(updated_checklist, visible_expenses),
        "checklist": await build_checklist_response_payload(updated_checklist, user.id),
    }


@app.patch("/expenses/{expense_id}", response_model=schemas.TripExpenseListResponse)
async def update_checklist_expense(
    expense_id: int,
    payload: schemas.TripExpenseUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_current_user),
):
    expense = await crud.get_expense_by_id(db, expense_id)
    if not expense:
        raise HTTPException(status_code=404, detail="Трата не найдена")
    checklist = await crud.get_checklist_by_id(db, expense.checklist_id)
    if not checklist or not is_checklist_participant(checklist, user.id):
        raise HTTPException(status_code=403, detail="Нет доступа к этому чеклисту")

    amount = payload.amount if payload.amount is not None else expense.amount
    currency = normalize_currency(payload.currency, expense.currency)
    base_currency = normalize_currency(checklist.expense_base_currency, "RUB")
    conversion = None
    if payload.amount is not None or payload.currency is not None or expense.base_currency != base_currency:
        conversion = await build_expense_conversion(amount, currency, base_currency)
    update_payload = payload.model_copy(update={"currency": currency}) if payload.currency is not None else payload
    await crud.update_trip_expense(
        db,
        expense,
        update_payload,
        amount_base=float(conversion["amount"]) if conversion else None,
        base_currency=base_currency if conversion else None,
        fx_rate=float(conversion["rate"]) if conversion else None,
        fx_rate_date=str(conversion.get("rate_date") or "") if conversion else None,
        fx_provider=str(conversion.get("provider") or "") if conversion else None,
    )
    updated_checklist = await crud.get_checklist_by_id(db, checklist.id)
    visible_expenses = get_visible_expenses_for_viewer(updated_checklist, user.id)
    return {
        "expenses": visible_expenses,
        "summary": build_expense_summary(updated_checklist, visible_expenses),
        "checklist": await build_checklist_response_payload(updated_checklist, user.id),
    }


@app.delete("/expenses/{expense_id}", response_model=schemas.TripExpenseListResponse)
async def delete_checklist_expense(
    expense_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_current_user),
):
    expense = await crud.get_expense_by_id(db, expense_id)
    if not expense:
        raise HTTPException(status_code=404, detail="Трата не найдена")
    checklist = await crud.get_checklist_by_id(db, expense.checklist_id)
    if not checklist or not is_checklist_participant(checklist, user.id):
        raise HTTPException(status_code=403, detail="Нет доступа к этому чеклисту")
    await crud.delete_trip_expense(db, expense)
    updated_checklist = await crud.get_checklist_by_id(db, checklist.id)
    visible_expenses = get_visible_expenses_for_viewer(updated_checklist, user.id)
    return {
        "expenses": visible_expenses,
        "summary": build_expense_summary(updated_checklist, visible_expenses),
        "checklist": await build_checklist_response_payload(updated_checklist, user.id),
    }

@app.get("/ai/suggestions")
async def ai_suggestions(language: str = "ru"):
    """Получить предложенные вопросы для AI-чата"""
    from ai_service import get_suggestions
    return {"suggestions": get_suggestions(language)}


@app.post("/translate-item-label")
async def translate_item_label(payload: ItemLabelTranslationRequest):
    text = re.sub(r"\s+", " ", str(payload.text or "").strip())
    if not text:
        raise HTTPException(status_code=400, detail="Text is required")

    target_lang = (payload.target_lang or "en").strip().lower()
    if target_lang not in {"ru", "en"}:
        raise HTTPException(status_code=400, detail="Unsupported target language")

    source_lang = (payload.source_lang or "auto").strip().lower()
    if source_lang == "auto":
        source_lang = _guess_item_label_language(text)
    if source_lang not in {"ru", "en"}:
        source_lang = _guess_item_label_language(text)

    if source_lang == target_lang:
        return {
            "text": text,
            "translated_text": text,
            "source_lang": source_lang,
            "target_lang": target_lang,
            "provider": "identity",
        }

    known_translation = translate_known_item_label(text, target_lang)
    if known_translation:
        return {
            "text": text,
            "translated_text": known_translation,
            "source_lang": source_lang,
            "target_lang": target_lang,
            "provider": "dictionary",
        }

    translated_text = await _translate_item_label_with_ai(text, source_lang, target_lang)
    if translated_text:
        return {
            "text": text,
            "translated_text": translated_text,
            "source_lang": source_lang,
            "target_lang": target_lang,
            "provider": "ai",
        }

    return {
        "text": text,
        "translated_text": text,
        "source_lang": source_lang,
        "target_lang": target_lang,
        "provider": "fallback",
    }

@app.post("/generate-packing-list", response_model=ChecklistResponse)
async def generate_list(req: PackingRequest, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    segments = [{
        "city": req.city,
        "start_date": req.start_date,
        "end_date": req.end_date,
        "trip_type": req.trip_type,
        "transport": req.transport,
    }]
    resolved_trip_profile = await resolve_request_trip_profile(
        trip_type=req.trip_type,
        trip_activities=req.trip_activities,
        accommodation_type=req.accommodation_type,
        laundry_access=req.laundry_access,
        packing_style=req.packing_style,
        baggage_format=req.baggage_format,
        adults=req.adults,
        children_ages=req.children_ages,
        child_profiles=req.child_profiles,
        infants_count=req.infants_count,
        trip_note=req.trip_note,
        language=req.language,
    )
    data = await calculate_packing_data(
        req.city, req.start_date, req.end_date, resolved_trip_profile, req.transport,
        req.gender, req.traveling_with_pet, req.has_allergies, req.traveling_with_children or bool(req.children_ages) or bool(req.infants_count), req.language
    )
    participant_baggage_payloads = await build_participant_baggage_payloads(
        db=db,
        current_user=current_user,
        participant_user_ids=req.participant_user_ids,
        segments=segments,
        owner_overrides={
            "gender": req.gender,
            "traveling_with_pet": req.traveling_with_pet,
            "has_allergies": req.has_allergies,
            "traveling_with_children": req.traveling_with_children or bool(req.children_ages) or bool(req.infants_count),
        },
        trip_profile=resolved_trip_profile,
        language=req.language,
    )
    return await create_checklist_from_items(
        db, data["items"], req.city, data["start_date"], data["end_date"],
        data["avg_temp"], data["conditions"], data["daily_forecast"],
        item_quantities=data.get("item_quantities"),
        trip_profile=data.get("trip_profile"),
        user_id=current_user.id if current_user else None,
        language=req.language,
        origin_city=req.origin_city,
        transports=[req.transport] if req.transport else None,
        participant_baggage_payloads=participant_baggage_payloads,
    )

@app.post("/generate-multi-city", response_model=ChecklistResponse)
async def generate_multi_city(req: MultiCityPackingRequest, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    all_items = set()
    all_item_quantities = {}
    all_forecast = []
    temps = []
    conditions = set()
    cities = []

    transports = []
    resolved_trip_profile = await resolve_request_trip_profile(
        trip_type=req.segments[0].trip_type if req.segments else "city_break",
        trip_activities=req.trip_activities,
        accommodation_type=req.accommodation_type,
        laundry_access=req.laundry_access,
        packing_style=req.packing_style,
        baggage_format=req.baggage_format,
        adults=req.adults,
        children_ages=req.children_ages,
        child_profiles=req.child_profiles,
        infants_count=req.infants_count,
        trip_note=req.trip_note,
        language=req.language,
    )

    for seg in req.segments:
        cities.append(seg.city.split(",")[0])
        transports.append(seg.transport)
        data = await calculate_packing_data(
            seg.city,
            seg.start_date,
            seg.end_date,
            prepare_trip_profile_for_segment(resolved_trip_profile, seg.trip_type),
            seg.transport,
            req.gender, req.traveling_with_pet, req.has_allergies, req.traveling_with_children or bool(req.children_ages) or bool(req.infants_count), req.language
        )
        all_items.update(data["items"])
        for item, quantity in (data.get("item_quantities") or {}).items():
            all_item_quantities[item] = max(all_item_quantities.get(item, 0), int(quantity or 1))
        all_forecast.extend(data["daily_forecast"])
        if data["avg_temp"]: temps.append(data["avg_temp"])
        conditions.update(data["conditions"])
    
    # Sort forecast by date
    all_forecast.sort(key=lambda x: x.date)
    
    avg_temp = round(sum(temps) / len(temps), 1) if temps else None
    display_city = " + ".join(cities)
    
    # Parse dates for main checklist
    min_date = datetime.strptime(req.segments[0].start_date, "%Y-%m-%d").date()
    max_date = datetime.strptime(req.segments[-1].end_date, "%Y-%m-%d").date()

    # Append return transport as the last element
    transports.append(req.return_transport)

    participant_baggage_payloads = await build_participant_baggage_payloads(
        db=db,
        current_user=current_user,
        participant_user_ids=req.participant_user_ids,
        segments=[
            {
                "city": segment.city,
                "start_date": segment.start_date,
                "end_date": segment.end_date,
                "trip_type": segment.trip_type,
                "transport": segment.transport,
            }
            for segment in req.segments
        ],
        owner_overrides={
            "gender": req.gender,
            "traveling_with_pet": req.traveling_with_pet,
            "has_allergies": req.has_allergies,
            "traveling_with_children": req.traveling_with_children or bool(req.children_ages) or bool(req.infants_count),
        },
        trip_profile=resolved_trip_profile,
        language=req.language,
    )
    
    return await create_checklist_from_items(
        db, all_items, display_city, min_date, max_date,
        avg_temp, list(conditions), all_forecast,
        item_quantities=all_item_quantities,
        trip_profile=resolved_trip_profile,
        user_id=current_user.id if current_user else None,
        language=req.language,
        origin_city=req.origin_city,
        transports=transports,
        participant_baggage_payloads=participant_baggage_payloads,
    )

@app.post("/save-tg-checklist", response_model=schemas.ChecklistOut)
async def save_tg_checklist(data: schemas.ChecklistCreate = Body(...), db: AsyncSession = Depends(get_db)):
    if not data.tg_user_id:
        raise HTTPException(status_code=400, detail="Не передан tg_user_id")
    checklist = await crud.save_or_update_tg_checklist(db, data)
    return checklist

@app.get("/tg-checklist/{tg_user_id}", response_model=schemas.ChecklistOut)
async def get_tg_checklist(tg_user_id: str, db: AsyncSession = Depends(get_db)):
    checklist = await crud.get_checklist_by_tg_user_id(db, tg_user_id)
    if not checklist:
        raise HTTPException(status_code=404, detail="Чеклист не найден для пользователя")
    return checklist

@app.get("/tg-checklists/{tg_user_id}", response_model=List[schemas.ChecklistOut])
async def get_tg_checklists(tg_user_id: str, db: AsyncSession = Depends(get_db)):
    checklists = await crud.get_all_checklists_by_tg_user_id(db, tg_user_id)
    return checklists

@app.get("/checklist/{slug}", response_model=ChecklistResponse)
async def get_checklist(
    slug: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    checklist = await crud.get_checklist_by_slug(db, slug)
    if not checklist:
        raise HTTPException(status_code=404, detail="Чеклист не найден")

    viewer_id = user.id if user else None
    return await build_checklist_response_payload(checklist, viewer_id)

@app.post("/checklists/{slug}/review", response_model=schemas.TripReviewOut)
async def create_or_update_trip_review(
    slug: str,
    payload: schemas.TripReviewCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_current_user),
):
    checklist = await crud.get_checklist_by_slug(db, slug)
    if not checklist:
        raise HTTPException(status_code=404, detail="Чеклист не найден")
    if not is_checklist_participant(checklist, user.id):
        raise HTTPException(status_code=403, detail="Только участник поездки может оставить отзыв")
    if checklist.end_date and checklist.end_date > date.today():
        raise HTTPException(status_code=400, detail="Оставить отзыв можно после завершения поездки")
    normalized_photos = _normalize_trip_review_photos(payload.photo, payload.photos)
    encoded_photos = _encode_trip_review_photos(normalized_photos)

    review = await crud.get_trip_review_by_user_and_checklist(db, user.id, checklist.id)
    if review:
        review.rating = payload.rating
        review.text = payload.text.strip()
        review.photo = encoded_photos
    else:
        review = models.TripReview(
            checklist_id=checklist.id,
            user_id=user.id,
            rating=payload.rating,
            text=payload.text.strip(),
            photo=encoded_photos,
        )
        db.add(review)

    await db.commit()

    result = await db.execute(
        select(models.TripReview)
        .options(selectinload(models.TripReview.checklist))
        .where(models.TripReview.id == review.id)
    )
    saved_review = result.scalar_one()
    return build_trip_review_payload(saved_review)


@app.delete("/checklists/{slug}/review")
async def delete_trip_review(
    slug: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_current_user),
):
    checklist = await crud.get_checklist_by_slug(db, slug)
    if not checklist:
        raise HTTPException(status_code=404, detail="Чеклист не найден")

    review = await crud.get_trip_review_by_user_and_checklist(db, user.id, checklist.id)
    if not review:
        raise HTTPException(status_code=404, detail="Отзыв не найден")

    await db.delete(review)
    await db.commit()
    return {"ok": True}


@app.post("/checklists/{slug}/ai-command", response_model=schemas.ChecklistAICommandResponse)
async def run_ai_checklist_command(
    slug: str,
    payload: schemas.ChecklistAICommandRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_current_user),
):
    from checklist_ai import execute_checklist_ai_command

    checklist = await crud.get_checklist_by_slug(db, slug)
    if not checklist:
        raise HTTPException(status_code=404, detail="Чеклист не найден")
    if not is_checklist_participant(checklist, user.id):
        raise HTTPException(status_code=403, detail="Нет доступа к этому чеклисту")

    forecast = checklist.daily_forecast
    if not forecast:
        try:
            forecast = await get_weather_forecast_data(
                checklist.city,
                checklist.start_date,
                checklist.end_date,
                language=payload.language,
            )
        except Exception:
            forecast = []
    trip_context = build_trip_context(
        checklist,
        viewer_user_id=user.id,
        language=payload.language,
        forecast=forecast,
        cached_attractions=await _get_cached_attractions_for_assistant(db, checklist.city, payload.language),
    )
    result = await execute_checklist_ai_command(
        db=db,
        checklist=checklist,
        command=payload.command,
        language=payload.language,
        actor_user_id=user.id,
        command_context=payload.command_context,
        trip_context=trip_context,
    )
    return {
        "applied": result["applied"],
        "recognized_action_request": result["recognized_action_request"],
        "message": result["message"],
        "actions": result["actions"],
        "checklist": result["checklist"],
        "command_context": result.get("command_context"),
    }


@app.patch("/checklist/{slug}/state", response_model=schemas.ChecklistOut)
async def update_checklist_state(
    slug: str,
    state: ChecklistStateUpdate = Body(...),
    db: AsyncSession = Depends(get_db),
    user=Depends(require_current_user),
):
    checklist = await crud.get_checklist_by_slug(db, slug)
    if not checklist:
        raise HTTPException(status_code=404, detail="Чеклист не найден")
    if not is_checklist_participant(checklist, user.id):
        raise HTTPException(status_code=403, detail="Нет доступа к этому чеклисту")

    updated = await crud.update_checklist_state(
        db,
        slug,
        checked_items=state.checked_items,
        removed_items=state.removed_items,
        added_items=state.added_items,
        item_quantities=state.item_quantities,
        packed_quantities=state.packed_quantities,
        item_categories=state.item_categories,
        item_translations=state.item_translations,
        items=state.items,
        trip_profile=state.trip_profile.model_dump(mode="json") if state.trip_profile else None,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Чеклист не найден")
    return updated


@app.patch("/checklist/{slug}/privacy", response_model=schemas.ChecklistOut)
async def update_checklist_privacy(
    slug: str,
    privacy: ChecklistPrivacyUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_current_user)
):
    """Обновление приватности чеклиста"""
    checklist = await crud.get_checklist_by_slug(db, slug)
    if not checklist:
        raise HTTPException(status_code=404, detail="Чеклист не найден")
    
    # Проверка прав (только владелец)
    if checklist.user_id != user.id:
        raise HTTPException(status_code=403, detail="Нет прав")

    checklist.is_public = privacy.is_public
    await db.commit()
    await db.refresh(checklist)
    return checklist

# === Itinerary / Events API ===

@app.post("/checklists/{slug}/events", response_model=schemas.ItineraryEventOut)
async def add_checklist_event(
    slug: str,
    event_in: schemas.ItineraryEventCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_current_user)
):
    checklist = await crud.get_checklist_by_slug(db, slug)
    if not checklist:
        raise HTTPException(status_code=404, detail="Чеклист не найден")
    if checklist.user_id != user.id:
        raise HTTPException(status_code=403, detail="Нет прав редактировать расписание")
    
    return await crud.create_itinerary_event(db, checklist_id=checklist.id, data=event_in)

@app.patch("/events/{event_id}", response_model=schemas.ItineraryEventOut)
async def update_itinerary_event(
    event_id: int,
    event_in: schemas.ItineraryEventUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_current_user)
):
    result = await db.execute(select(models.ItineraryEvent).where(models.ItineraryEvent.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Событие не найдено")
    
    checklist = await crud.get_checklist_by_id(db, event.checklist_id)
    if not checklist or checklist.user_id != user.id:
        raise HTTPException(status_code=403, detail="Нет прав редактировать")
    
    updated = await crud.update_itinerary_event(db, event_id, event_in)
    if not updated:
        raise HTTPException(status_code=500, detail="Ошибка при обновлении")
    return updated

@app.delete("/events/{event_id}")
async def remove_itinerary_event(
    event_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_current_user)
):
    # Verify ownership through the event's checklist
    result = await db.execute(select(models.ItineraryEvent).where(models.ItineraryEvent.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Событие не найдено")
        
    checklist = await crud.get_checklist_by_id(db, event.checklist_id)
    if not checklist or checklist.user_id != user.id:
        raise HTTPException(status_code=403, detail="Нет прав удалять это событие")
        
    success = await crud.delete_itinerary_event(db, event_id)
    if not success:
         raise HTTPException(status_code=500, detail="Ошибка при удалении")
    return {"status": "ok"}

    checklist.is_public = privacy.is_public
    await db.commit()
    await db.refresh(checklist)
    return checklist

# === Shared Backpacks API ===

@app.post("/checklists/{slug}/invite-token", response_model=dict)
async def generate_invite_token(
    slug: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_current_user)
):
    checklist = await crud.get_checklist_by_slug(db, slug)
    if not checklist:
        raise HTTPException(status_code=404, detail="Чеклист не найден")
    if checklist.user_id != user.id:
        raise HTTPException(status_code=403, detail="Только владелец может генерировать ссылки")
        
    token = await crud.generate_checklist_invite_token(db, slug)
    if not token:
        raise HTTPException(status_code=500, detail="Ошибка генерации токена")
        
    return {"invite_token": token}


@app.post("/join/{invite_token}", response_model=schemas.ChecklistOut)
async def join_shared_checklist(
    invite_token: str,
    child_profile_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    user=Depends(require_current_user)
):
    checklist = await crud.get_checklist_by_invite_token(db, invite_token)
    if not checklist:
        raise HTTPException(status_code=404, detail="Неверная или устаревшая ссылка")
        
    normalized_child_profile_id = (child_profile_id or "").strip() or None
    if normalized_child_profile_id:
        child_profile = get_trip_child_profile(checklist, normalized_child_profile_id)
        if not child_profile:
            raise HTTPException(status_code=400, detail="Ребёнок не найден в контексте поездки")
        linked_user_id = get_child_profile_linked_user_id(child_profile)
        if linked_user_id and linked_user_id != user.id:
            raise HTTPException(status_code=409, detail="Этот детский профиль уже связан с другим участником")
        await link_trip_child_profile_to_user(db, checklist, normalized_child_profile_id, user.id)
        await ensure_default_baggage_for_participant(db, checklist, user.id)
    elif checklist.user_id != user.id:
        await ensure_default_baggage_for_participant(db, checklist, user.id)
        
    # Reload checklist to return fully loaded relationships
    await db.refresh(checklist)
    return checklist


@app.post("/checklists/{slug}/baggage", response_model=schemas.UserBackpackOut)
async def create_baggage(
    slug: str,
    payload: schemas.UserBaggageCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_current_user),
):
    checklist = await crud.get_checklist_by_slug(db, slug)
    if not checklist:
        raise HTTPException(status_code=404, detail="Чеклист не найден")

    child_profile_id = (payload.child_profile_id or "").strip() or None
    target_user_id = payload.user_id or user.id
    if child_profile_id:
        child_profile = get_trip_child_profile(checklist, child_profile_id)
        linked_user_id = get_child_profile_linked_user_id(child_profile)
        if checklist.user_id != user.id and linked_user_id != user.id:
            raise HTTPException(status_code=403, detail="Детский багаж может создать только владелец чеклиста или связанный участник")
        if not child_profile:
            raise HTTPException(status_code=400, detail="Ребёнок не найден в контексте поездки")
        target_user_id = linked_user_id or checklist.user_id or user.id
        if linked_user_id:
            child_profile_id = None
    elif target_user_id != user.id:
        raise HTTPException(status_code=403, detail="Можно создавать багаж только себе")

    if not is_checklist_participant(checklist, target_user_id):
        raise HTTPException(status_code=400, detail="Сначала пользователь должен быть участником чеклиста")

    baggage = await crud.create_user_baggage(
        db,
        checklist_id=checklist.id,
        user_id=target_user_id,
        name=payload.name,
        kind=payload.kind,
        child_profile_id=child_profile_id,
    )
    return baggage


@app.patch("/baggage/{backpack_id}", response_model=schemas.UserBackpackOut)
async def update_baggage(
    backpack_id: int,
    payload: schemas.UserBaggageUpdate,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_current_user),
):
    backpack = await crud.get_backpack_by_id(db, backpack_id)
    if not backpack:
        raise HTTPException(status_code=404, detail="Багаж не найден")

    checklist = await crud.get_checklist_by_id(db, backpack.checklist_id)
    if not checklist:
        raise HTTPException(status_code=404, detail="Чеклист не найден")

    if not can_manage_baggage(backpack, user.id, checklist):
        raise HTTPException(status_code=403, detail="Нет прав редактировать этот багаж")

    updated = await crud.update_baggage_meta(db, backpack_id, payload)
    if not updated:
        raise HTTPException(status_code=404, detail="Багаж не найден")
    return updated


@app.delete("/baggage/{backpack_id}", response_model=dict)
async def delete_baggage(
    backpack_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_current_user),
):
    backpack = await crud.get_backpack_by_id(db, backpack_id)
    if not backpack:
        raise HTTPException(status_code=404, detail="Багаж не найден")

    checklist = await crud.get_checklist_by_id(db, backpack.checklist_id)
    if not checklist:
        raise HTTPException(status_code=404, detail="Чеклист не найден")

    if not can_manage_baggage(backpack, user.id, checklist):
        raise HTTPException(status_code=403, detail="Нет прав удалять этот багаж")

    deleted_id, error_code = await crud.delete_baggage(db, backpack_id)
    if error_code == "last_baggage":
        raise HTTPException(status_code=400, detail="Нельзя удалить единственный багаж пользователя")
    if error_code == "default_baggage":
        raise HTTPException(status_code=400, detail="Сначала назначьте другой багаж основным")
    if error_code == "not_empty":
        raise HTTPException(status_code=400, detail="Сначала освободите багаж от вещей")
    if error_code == "not_found" or deleted_id is None:
        raise HTTPException(status_code=404, detail="Багаж не найден")

    return {"deleted_id": deleted_id}


@app.patch("/backpacks/{backpack_id}/state", response_model=schemas.UserBackpackOut)
async def update_backpack_state(
    backpack_id: int,
    state: BackpackStateUpdate = Body(...),
    db: AsyncSession = Depends(get_db),
    user=Depends(require_current_user)
):
    # Verify owner
    import models
    from sqlalchemy.future import select
    res = await db.execute(select(models.UserBackpack).where(models.UserBackpack.id == backpack_id))
    bp = res.scalar_one_or_none()
    
    if not bp:
        raise HTTPException(status_code=404, detail="Рюкзак не найден")

    checklist = await crud.get_checklist_by_id(db, bp.checklist_id)
    if not checklist:
        raise HTTPException(status_code=404, detail="Чеклист не найден")
    if not can_edit_baggage(bp, checklist, user.id):
        raise HTTPException(status_code=403, detail="Нет прав редактировать этот багаж")
        
    updated_bp = await crud.update_backpack_items(
        db, 
        backpack_id, 
        schemas.UserBackpackUpdate(
            checked_items=state.checked_items,
            removed_items=state.removed_items,
            added_items=state.added_items,
            item_quantities=state.item_quantities,
            packed_quantities=state.packed_quantities,
            item_categories=state.item_categories,
            item_translations=state.item_translations,
            items=state.items
        )
    )
    return updated_bp


@app.post("/checklists/{slug}/transfer-item", response_model=ChecklistResponse)
async def transfer_checklist_item(
    slug: str,
    payload: BaggageTransferRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_current_user),
):
    checklist = await crud.get_checklist_by_slug(db, slug)
    if not checklist:
        raise HTTPException(status_code=404, detail="Чеклист не найден")
    if not is_checklist_participant(checklist, user.id):
        raise HTTPException(status_code=403, detail="Нет доступа к чеклисту")

    item = (payload.item or "").strip()
    if not item:
        raise HTTPException(status_code=400, detail="Не указана вещь")

    target_backpack = await crud.get_backpack_by_id(db, payload.target_backpack_id)
    if not target_backpack or target_backpack.checklist_id != checklist.id:
        raise HTTPException(status_code=404, detail="Багаж назначения не найден")
    if is_backpack_hidden_for_viewer(target_backpack, checklist, user.id):
        raise HTTPException(status_code=403, detail="Этот багаж скрыт от вас")
    if not can_edit_baggage(target_backpack, checklist, user.id):
        raise HTTPException(status_code=403, detail="Нет прав переносить вещи в этот багаж")

    source_backpack = None
    if payload.source_backpack_id is not None:
        source_backpack = await crud.get_backpack_by_id(db, payload.source_backpack_id)
        if not source_backpack or source_backpack.checklist_id != checklist.id:
            raise HTTPException(status_code=404, detail="Исходный багаж не найден")
        if source_backpack.id == target_backpack.id:
            raise HTTPException(status_code=400, detail="Нельзя переместить вещь в тот же багаж")
        if not can_edit_baggage(source_backpack, checklist, user.id):
            raise HTTPException(status_code=403, detail="Нет прав менять этот багаж")
        if item not in (source_backpack.items or []):
            raise HTTPException(status_code=404, detail="Вещь не найдена в исходном багаже")
    else:
        if not can_edit_shared_section(checklist, user.id):
            raise HTTPException(status_code=403, detail="Нет прав менять этот раздел")
        if item not in (checklist.items or []):
            raise HTTPException(status_code=404, detail="Вещь не найдена в списке")

    if payload.source_backpack_id is None:
        moved_quantity = max(1, get_map_quantity(checklist.item_quantities or {}, item, 1))
        moved_packed = max(0, get_map_quantity(checklist.packed_quantities or {}, item, 0))
        moved_category = get_map_text(checklist.item_categories or {}, item)
        moved_translation = dict((checklist.item_translations or {}).get(item) or {})
        checklist.items = [existing for existing in (checklist.items or []) if existing != item]
        checklist.checked_items = [existing for existing in (checklist.checked_items or []) if existing != item]
        checklist.removed_items = [existing for existing in (checklist.removed_items or []) if existing != item]
        checklist.item_quantities = set_map_quantity(checklist.item_quantities or {}, item, 0)
        checklist.packed_quantities = set_map_quantity(checklist.packed_quantities or {}, item, 0)
        checklist.item_categories = set_map_text(checklist.item_categories or {}, item, None)
    else:
        moved_quantity = max(1, get_map_quantity(source_backpack.item_quantities or {}, item, 1))
        moved_packed = max(0, get_map_quantity(source_backpack.packed_quantities or {}, item, 0))
        moved_category = get_map_text(source_backpack.item_categories or {}, item)
        moved_translation = dict((source_backpack.item_translations or {}).get(item) or {})
        source_backpack.items = [existing for existing in (source_backpack.items or []) if existing != item]
        source_backpack.checked_items = [existing for existing in (source_backpack.checked_items or []) if existing != item]
        source_backpack.removed_items = [existing for existing in (source_backpack.removed_items or []) if existing != item]
        source_backpack.item_quantities = set_map_quantity(source_backpack.item_quantities or {}, item, 0)
        source_backpack.packed_quantities = set_map_quantity(source_backpack.packed_quantities or {}, item, 0)
        source_backpack.item_categories = set_map_text(source_backpack.item_categories or {}, item, None)
        source_backpack.checked_items = rebuild_checked_items(
            source_backpack.items or [],
            source_backpack.item_quantities or {},
            source_backpack.packed_quantities or {},
        )

    if item not in (target_backpack.items or []):
        target_backpack.items = [*(target_backpack.items or []), item]
    target_backpack.removed_items = [existing for existing in (target_backpack.removed_items or []) if existing != item]
    target_backpack.item_quantities = set_map_quantity(
        target_backpack.item_quantities or {},
        item,
        max(1, get_map_quantity(target_backpack.item_quantities or {}, item, 0) + moved_quantity),
    )
    target_backpack.packed_quantities = set_map_quantity(
        target_backpack.packed_quantities or {},
        item,
        max(0, get_map_quantity(target_backpack.packed_quantities or {}, item, 0) + moved_packed),
    )
    if moved_category and not get_map_text(target_backpack.item_categories or {}, item):
        target_backpack.item_categories = set_map_text(target_backpack.item_categories or {}, item, moved_category)
    if moved_translation:
        target_translations = dict(target_backpack.item_translations or {})
        target_translations[item] = {
            **dict(target_translations.get(item) or {}),
            **moved_translation,
        }
        target_backpack.item_translations = target_translations
    target_backpack.checked_items = rebuild_checked_items(
        target_backpack.items or [],
        target_backpack.item_quantities or {},
        target_backpack.packed_quantities or {},
    )

    await db.commit()
    return await get_checklist(slug, db, user)

# Toggle section visibility
@app.patch("/checklists/{slug}/hidden-sections")
async def update_hidden_sections(
    slug: str,
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    user=Depends(require_current_user)
):
    checklist = await crud.get_checklist_by_slug(db, slug)
    if not checklist:
        raise HTTPException(status_code=404, detail="Чеклист не найден")
    if not is_checklist_participant(checklist, user.id):
        raise HTTPException(status_code=403, detail="Нет доступа к чеклисту")

    requested_hidden = list(dict.fromkeys(payload.get("hidden_sections", [])))
    current_hidden = set(checklist.hidden_sections or [])
    requested_set = set(requested_hidden)

    changed_sections = current_hidden.symmetric_difference(requested_set)
    for section in changed_sections:
        if section == "shared" or section == "backpacks" or section == "itinerary" or section == "expenses":
            if checklist.user_id != user.id:
                raise HTTPException(status_code=403, detail="Только владелец чеклиста может менять видимость общего раздела")
            continue
        if section.startswith("backpack:"):
            try:
                backpack_id = int(section.split(":", 1)[1])
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail="Некорректный раздел")
            backpack = await crud.get_backpack_by_id(db, backpack_id)
            if not backpack or backpack.checklist_id != checklist.id:
                raise HTTPException(status_code=404, detail="Багаж не найден")
            if not can_manage_baggage(backpack, user.id, checklist):
                raise HTTPException(status_code=403, detail="Только владелец багажа может менять его видимость")
            continue
        raise HTTPException(status_code=400, detail="Некорректный раздел")

    checklist.hidden_sections = requested_hidden
    await db.commit()
    await db.refresh(checklist)
    return {"hidden_sections": checklist.hidden_sections}

@app.post("/checklists/{slug}/invite/{target_user_id}")
async def notify_invite(
    slug: str,
    target_user_id: int,
    child_profile_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    user=Depends(require_current_user)
):
    checklist = await crud.get_checklist_by_slug(db, slug)
    if not checklist:
        raise HTTPException(status_code=404, detail="Чеклист не найден")

    if checklist.user_id != user.id:
        raise HTTPException(status_code=403, detail="Только владелец может приглашать в чеклист")
    
    target_user = await crud.get_user_by_id(db, target_user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    normalized_child_profile_id = (child_profile_id or "").strip() or None
    child_profile = None
    if normalized_child_profile_id:
        child_profile = get_trip_child_profile(checklist, normalized_child_profile_id)
        if not child_profile:
            raise HTTPException(status_code=400, detail="Ребёнок не найден в контексте поездки")
        linked_user_id = get_child_profile_linked_user_id(child_profile)
        if linked_user_id and linked_user_id != target_user_id:
            raise HTTPException(status_code=409, detail="Этот детский профиль уже связан с другим участником")

    if is_checklist_participant(checklist, target_user_id) and not normalized_child_profile_id:
        raise HTTPException(status_code=409, detail="Пользователь уже в чеклисте")
    
    if normalized_child_profile_id:
        await link_trip_child_profile_to_user(db, checklist, normalized_child_profile_id, target_user_id)
        await ensure_default_baggage_for_participant(db, checklist, target_user_id)
    else:
        existing_bp = await db.execute(
            select(models.UserBackpack).where(
                models.UserBackpack.checklist_id == checklist.id,
                models.UserBackpack.user_id == target_user_id,
                models.UserBackpack.child_profile_id.is_(None),
            )
        )
        if not existing_bp.scalar_one_or_none():
            await ensure_default_baggage_for_participant(db, checklist, target_user_id)

    # Generate invite token if not exists
    if not checklist.invite_token:
        await crud.generate_checklist_invite_token(db, slug)
        await db.refresh(checklist)
    
    # Create backpack for the owner if not exists
    if checklist.user_id == user.id:
        await ensure_default_baggage_for_participant(db, checklist, user.id)
    
    # Create notification for target user
    new_notif = models.Notification(
        user_id=target_user_id,
        type="checklist_invitation",
        content=f"{user.username} пригласил(а) вас в чеклист {checklist.city}",
        link=f"/checklist/{slug}",
        is_read=False,
        extra_data={
            "token": checklist.invite_token,
            "child_profile_id": normalized_child_profile_id,
        } if checklist.invite_token else None
    )
    db.add(new_notif)
    await db.commit()
    return {"status": "ok"}

# === Notification Endpoints ===

@app.get("/notifications", response_model=List[schemas.NotificationOut])
async def get_notifications(
    db: AsyncSession = Depends(get_db),
    user=Depends(require_current_user)
):
    from sqlalchemy import desc
    res = await db.execute(
        select(models.Notification)
        .where(models.Notification.user_id == user.id)
        .order_by(desc(models.Notification.created_at))
        .limit(20)
    )
    return res.scalars().all()

@app.patch("/notifications/{notif_id}/read", response_model=schemas.NotificationOut)
async def mark_notification_read(
    notif_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_current_user)
):
    res = await db.execute(
        select(models.Notification).where(models.Notification.id == notif_id)
    )
    notif = res.scalar_one_or_none()
    if not notif:
        raise HTTPException(status_code=404, detail="Уведомление не найдено")
    if notif.user_id != user.id:
        raise HTTPException(status_code=403, detail="Нет прав")
    
    notif.is_read = True
    await db.commit()
    await db.refresh(notif)
    return notif

@app.patch("/notifications/checklist/{slug}/read")
async def mark_checklist_notification_read(
    slug: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_current_user)
):
    target_link = f"/checklist/{slug}"
    # Mark all invitation notifications for this checklist as read
    await db.execute(
        update(models.Notification)
        .where(
            models.Notification.user_id == user.id,
            models.Notification.link == target_link,
            models.Notification.type == "checklist_invitation"
        )
        .values(is_read=True)
    )
    await db.commit()
    return {"status": "ok"}

# === End Shared Backpacks ===

@app.delete("/checklist/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_checklist(slug: str, db: AsyncSession = Depends(get_db)):
    checklist = await crud.get_checklist_by_slug(db, slug)
    if not checklist:
        raise HTTPException(status_code=404, detail="Чеклист не найден")
    await db.delete(checklist)
    await db.commit()
    return

@app.get("/")
async def root():
    return {"message": "Luggify backend is running"}

@app.get("/health")
async def health_check():
    """Health check endpoint - проверяет доступность сервера и подключение к БД"""
    try:
        # Проверяем наличие переменных окружения
        db_url = os.getenv("DATABASE_URL")
        db_status = "configured" if db_url else "missing"

        # Пытаемся подключиться к БД если она настроена
        db_connection = "unknown"
        db_error_details = None
        if db_url and SessionLocal:
            try:
                from sqlalchemy import text
                async with SessionLocal() as session:
                    await session.execute(text("SELECT 1"))
                db_connection = "ok"
            except Exception as e:
                error_msg = str(e)
                db_connection = "error"
                db_error_details = error_msg[:200]
                if "Name or service not known" in error_msg:
                    db_error_details += " | Возможно неправильный хост"
                elif "could not translate host name" in error_msg.lower():
                    db_error_details += " | Проверьте формат DATABASE_URL"
        elif not db_url:
            db_connection = "not_configured"

        result = {
            "status": "ok",
            "database_url": db_status,
            "database_connection": db_connection,
            "message": "Server is running"
        }
        if db_error_details:
            result["database_error"] = db_error_details
        if db_url:
            # Показываем хост из URL (без пароля)
            try:
                from urllib.parse import urlparse
                parsed = urlparse(db_url)
                result["database_host"] = parsed.hostname
                result["database_port"] = parsed.port
            except:
                pass
        return result
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }
