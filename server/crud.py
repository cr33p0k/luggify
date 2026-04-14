from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import case, func
from sqlalchemy.orm import selectinload
import models
import schemas
import uuid
from auth import get_password_hash


DEFAULT_BAGGAGE_NAME = "Рюкзак"
DEFAULT_BAGGAGE_KIND = "backpack"

BAGGAGE_KIND_DEFAULT_NAMES = {
    "backpack": "Рюкзак",
    "suitcase": "Чемодан",
    "carry_on": "Ручная кладь",
    "bag": "Сумка",
    "custom": "Багаж",
}


def _normalize_packing_profile_items(items: list[str] | None) -> list[str]:
    normalized: list[str] = []
    for raw_value in items or []:
        item = str(raw_value or "").strip()
        if not item:
            continue
        if item not in normalized:
            normalized.append(item)
    return normalized


def _normalize_packing_profile(profile: dict | None) -> dict:
    source = profile or {}
    gender = (source.get("gender") or "unspecified").strip().lower()
    if gender == "unisex":
        gender = "unspecified"
    if gender not in {"unspecified", "male", "female"}:
        gender = "unspecified"
    return {
        "gender": gender,
        "traveling_with_pet": bool(source.get("traveling_with_pet")),
        "has_allergies": bool(source.get("has_allergies")),
        "always_include_items": _normalize_packing_profile_items(source.get("always_include_items")),
    }


def _normalize_editor_user_ids(editor_user_ids: list[int] | None, owner_user_id: int | None = None) -> list[int]:
    normalized: list[int] = []
    for raw_value in editor_user_ids or []:
        try:
            parsed = int(raw_value)
        except (TypeError, ValueError):
            continue
        if parsed <= 0:
            continue
        if owner_user_id and parsed == owner_user_id:
            continue
        if parsed not in normalized:
            normalized.append(parsed)
    return normalized


# === User CRUD ===

async def create_user(db: AsyncSession, data: schemas.UserCreate):
    """Создание нового пользователя"""
    hashed_password = get_password_hash(data.password)
    user = models.User(
        email=data.email,
        username=data.username,
        hashed_password=hashed_password,
        packing_profile=_normalize_packing_profile(None),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def get_user_by_email(db: AsyncSession, email: str):
    """Получение пользователя по email"""
    result = await db.execute(
        select(models.User).where(models.User.email == email)
    )
    return result.scalar_one_or_none()


async def get_user_by_username(db: AsyncSession, username: str):
    """Получение пользователя по username"""
    result = await db.execute(
        select(models.User).where(models.User.username == username)
    )
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: int):
    """Получение пользователя по ID"""
    result = await db.execute(
        select(models.User).where(models.User.id == user_id)
    )
    return result.scalar_one_or_none()


async def get_user_by_tg_id(db: AsyncSession, tg_id: str):
    """Получение пользователя по Telegram ID"""
    result = await db.execute(
        select(models.User).where(models.User.tg_id == tg_id)
    )
    return result.scalar_one_or_none()


async def update_user(db: AsyncSession, user_id: int, user_update: schemas.UserUpdate):
    """Обновление данных пользователя"""
    user = await get_user_by_id(db, user_id)
    if not user:
        return None
    
    update_data = user_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if key == "packing_profile":
            value = _normalize_packing_profile(value)
        setattr(user, key, value)
        
    await db.commit()
    await db.refresh(user)
    return user


async def bind_telegram_to_user(
    db: AsyncSession,
    user_id: int,
    tg_id: str,
    telegram_username: str = None,
):
    user = await get_user_by_id(db, user_id)
    if not user:
        return None

    existing_owner = await get_user_by_tg_id(db, tg_id)
    if existing_owner and existing_owner.id != user_id:
        is_placeholder = not existing_owner.email and not existing_owner.hashed_password
        if not is_placeholder:
            raise ValueError("Этот Telegram уже привязан к другому аккаунту.")
        existing_owner.tg_id = None
        # Clear the old placeholder binding first so the unique tg_id index
        # does not trip when we attach the same Telegram account to the real user.
        await db.flush()

    user.tg_id = tg_id

    if telegram_username:
        social_links = dict(user.social_links or {})
        social_links.setdefault("telegram", f"@{telegram_username.lstrip('@')}")
        user.social_links = social_links

    await db.commit()
    await db.refresh(user)
    return user


async def unlink_telegram_from_user(db: AsyncSession, user_id: int):
    user = await get_user_by_id(db, user_id)
    if not user:
        return None

    user.tg_id = None

    social_links = dict(user.social_links or {})
    social_links.pop("telegram", None)
    user.social_links = social_links or None

    await db.commit()
    await db.refresh(user)
    return user


async def create_user_from_telegram(db: AsyncSession, tg_id: str, username: str, first_name: str = None):
    """Создание пользователя из Telegram данных"""
    display_name = username or first_name or f"tg_{tg_id}"
    # Проверяем уникальность username, добавляем суффикс если нужно
    existing = await get_user_by_username(db, display_name)
    if existing:
        display_name = f"{display_name}_{tg_id[:6]}"
    user = models.User(
        username=display_name,
        tg_id=tg_id,
        social_links={"telegram": f"@{username.lstrip('@')}"} if username else None,
        packing_profile=_normalize_packing_profile(None),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def follow_user(db: AsyncSession, follower_id: int, following_id: int):
    """Подписка на пользователя"""
    stmt = select(models.followers_association).where(
        models.followers_association.c.follower_id == follower_id,
        models.followers_association.c.following_id == following_id
    )
    result = await db.execute(stmt)
    if result.first():
        return False  # Уже подписан

    insert_stmt = models.followers_association.insert().values(
        follower_id=follower_id,
        following_id=following_id
    )
    await db.execute(insert_stmt)
    await db.commit()
    return True

async def unfollow_user(db: AsyncSession, follower_id: int, following_id: int):
    """Отписка от пользователя"""
    delete_stmt = models.followers_association.delete().where(
        models.followers_association.c.follower_id == follower_id,
        models.followers_association.c.following_id == following_id
    )
    result = await db.execute(delete_stmt)
    await db.commit()
    return result.rowcount > 0

async def remove_follower(db: AsyncSession, user_id: int, follower_id: int):
    """Удалить подписчика у пользователя"""
    delete_stmt = models.followers_association.delete().where(
        models.followers_association.c.follower_id == follower_id,
        models.followers_association.c.following_id == user_id
    )
    result = await db.execute(delete_stmt)
    await db.commit()
    return result.rowcount > 0

async def get_followers(db: AsyncSession, user_id: int):
    """Получить всех подписчиков (кто подписан на user_id)"""
    stmt = (
        select(models.User)
        .join(models.followers_association, models.User.id == models.followers_association.c.follower_id)
        .where(models.followers_association.c.following_id == user_id)
        .order_by(models.followers_association.c.created_at.desc())
    )
    result = await db.execute(stmt)
    return result.scalars().all()

async def get_following(db: AsyncSession, user_id: int):
    """Получить всех, на кого подписан user_id (подписки)"""
    stmt = (
        select(models.User)
        .join(models.followers_association, models.User.id == models.followers_association.c.following_id)
        .where(models.followers_association.c.follower_id == user_id)
        .order_by(models.followers_association.c.created_at.desc())
    )
    result = await db.execute(stmt)
    return result.scalars().all()


# === Follow Request CRUD ===

async def create_follow_request(db: AsyncSession, from_user_id: int, to_user_id: int):
    """Create a pending follow request"""
    # Check if request already exists
    stmt = select(models.FollowRequest).where(
        models.FollowRequest.from_user_id == from_user_id,
        models.FollowRequest.to_user_id == to_user_id,
        models.FollowRequest.status == "pending"
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing:
        return None  # Already has a pending request

    req = models.FollowRequest(
        from_user_id=from_user_id,
        to_user_id=to_user_id,
        status="pending"
    )
    db.add(req)
    await db.commit()
    await db.refresh(req)
    return req

async def get_follow_request(db: AsyncSession, from_user_id: int, to_user_id: int):
    """Check if a pending follow request exists"""
    stmt = select(models.FollowRequest).where(
        models.FollowRequest.from_user_id == from_user_id,
        models.FollowRequest.to_user_id == to_user_id,
        models.FollowRequest.status == "pending"
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

async def get_pending_follow_requests(db: AsyncSession, user_id: int):
    """Get all pending incoming follow requests for a user"""
    stmt = (
        select(models.FollowRequest)
        .where(
            models.FollowRequest.to_user_id == user_id,
            models.FollowRequest.status == "pending"
        )
        .order_by(models.FollowRequest.created_at.desc())
    )
    result = await db.execute(stmt)
    return result.scalars().all()

async def accept_follow_request(db: AsyncSession, request_id: int, owner_id: int):
    """Accept a follow request: auto-follow + delete request"""
    stmt = select(models.FollowRequest).where(
        models.FollowRequest.id == request_id,
        models.FollowRequest.to_user_id == owner_id,
        models.FollowRequest.status == "pending"
    )
    result = await db.execute(stmt)
    req = result.scalar_one_or_none()
    if not req:
        return False

    # Auto-follow
    await follow_user(db, req.from_user_id, req.to_user_id)

    # Delete the request
    await db.delete(req)
    await db.commit()
    return True

async def decline_follow_request(db: AsyncSession, request_id: int, owner_id: int):
    """Decline a follow request"""
    stmt = select(models.FollowRequest).where(
        models.FollowRequest.id == request_id,
        models.FollowRequest.to_user_id == owner_id,
        models.FollowRequest.status == "pending"
    )
    result = await db.execute(stmt)
    req = result.scalar_one_or_none()
    if not req:
        return False

    await db.delete(req)
    await db.commit()
    return True

async def cancel_follow_request(db: AsyncSession, from_user_id: int, to_user_id: int):
    """Cancel a pending follow request (by the requester)"""
    stmt = select(models.FollowRequest).where(
        models.FollowRequest.from_user_id == from_user_id,
        models.FollowRequest.to_user_id == to_user_id,
        models.FollowRequest.status == "pending"
    )
    result = await db.execute(stmt)
    req = result.scalar_one_or_none()
    if not req:
        return False
    await db.delete(req)
    await db.commit()
    return True


# === Checklist CRUD ===

async def create_checklist(db: AsyncSession, data: schemas.ChecklistCreate):
    slug = str(uuid.uuid4())[:8]

    checklist = models.Checklist(
        slug=slug,
        city=data.city,
        start_date=data.start_date,
        end_date=data.end_date,
        items=data.items,
        avg_temp=data.avg_temp,
        conditions=data.conditions,
        tg_user_id=data.tg_user_id,
        checked_items=data.checked_items,
        removed_items=data.removed_items,
        added_items=data.added_items,
        item_quantities=data.item_quantities or {},
        packed_quantities=data.packed_quantities or {},
        daily_forecast=[f.model_dump(mode='json') if hasattr(f, 'model_dump') else f for f in data.daily_forecast] if data.daily_forecast else None,
        user_id=data.user_id,
        origin_city=data.origin_city,
        transports=data.transports,
    )
    db.add(checklist)
    await db.commit()
    await db.refresh(checklist)
    return checklist


async def get_checklist_by_slug(db: AsyncSession, slug: str):
    result = await db.execute(
        select(models.Checklist)
        .execution_options(populate_existing=True)
        .options(
            selectinload(models.Checklist.backpacks),
            selectinload(models.Checklist.events),
            selectinload(models.Checklist.reviews),
        )
        .where(models.Checklist.slug == slug)
    )
    return result.scalar_one_or_none()


async def search_users_by_username(db: AsyncSession, query: str, limit: int = 8):
    cleaned_query = (query or "").strip()
    if not cleaned_query:
        return []

    prefix = f"{cleaned_query}%"
    contains = f"%{cleaned_query}%"
    result = await db.execute(
        select(models.User)
        .where(models.User.username.ilike(contains))
        .order_by(
            case((models.User.username.ilike(prefix), 0), else_=1),
            func.lower(models.User.username),
        )
        .limit(limit)
    )
    return result.scalars().all()


async def get_checklist_by_id(db: AsyncSession, checklist_id: int):
    result = await db.execute(
        select(models.Checklist)
        .execution_options(populate_existing=True)
        .options(
            selectinload(models.Checklist.backpacks),
            selectinload(models.Checklist.events),
            selectinload(models.Checklist.reviews),
        )
        .where(models.Checklist.id == checklist_id)
    )
    return result.scalar_one_or_none()


async def get_checklist_by_tg_user_id(db: AsyncSession, tg_user_id: str):
    result = await db.execute(
        select(models.Checklist)
        .where(models.Checklist.tg_user_id == tg_user_id)
        .order_by(models.Checklist.id.desc())
    )
    return result.scalars().first()


async def get_all_checklists_by_tg_user_id(db: AsyncSession, tg_user_id: str):
    result = await db.execute(
        select(models.Checklist)
        .where(models.Checklist.tg_user_id == tg_user_id)
        .order_by(models.Checklist.id.desc())
    )
    return result.scalars().all()


async def get_checklists_by_user_id(db: AsyncSession, user_id: int):
    """Получение всех чеклистов пользователя"""
    result = await db.execute(
        select(models.Checklist)
        .options(
            selectinload(models.Checklist.backpacks),
            selectinload(models.Checklist.reviews),
        )
        .where(models.Checklist.user_id == user_id)
        .order_by(models.Checklist.id.desc())
    )
    return result.scalars().all()


async def get_shared_checklists_by_user_id(db: AsyncSession, user_id: int):
    """Получение чеклистов, в которых пользователь является коллаборатором (имеет рюкзак)"""
    result = await db.execute(
        select(models.Checklist)
        .options(
            selectinload(models.Checklist.backpacks),
            selectinload(models.Checklist.reviews),
        )
        .join(models.UserBackpack, models.UserBackpack.checklist_id == models.Checklist.id)
        .where(models.UserBackpack.user_id == user_id)
        .where(models.Checklist.user_id != user_id)
        .distinct(models.Checklist.id)
        .order_by(models.Checklist.id.desc())
    )
    return result.scalars().all()


async def save_or_update_tg_checklist(db: AsyncSession, data: schemas.ChecklistCreate):
    # Всегда создаём новый чеклист
    return await create_checklist(db, data)


async def update_checklist_state(
    db: AsyncSession,
    slug: str,
    checked_items=None,
    removed_items=None,
    added_items=None,
    items=None,
    item_quantities=None,
    packed_quantities=None,
):
    result = await db.execute(select(models.Checklist).where(models.Checklist.slug == slug))
    checklist = result.scalar_one_or_none()
    if not checklist:
        return None
    if checked_items is not None:
        checklist.checked_items = checked_items
    if removed_items is not None:
        checklist.removed_items = removed_items
    if added_items is not None:
        checklist.added_items = added_items
    if items is not None:
        checklist.items = items
    if item_quantities is not None:
        checklist.item_quantities = item_quantities
    if packed_quantities is not None:
        checklist.packed_quantities = packed_quantities
    await db.commit()
    await db.refresh(checklist)
    return checklist

async def get_trip_review_by_user_and_checklist(db: AsyncSession, user_id: int, checklist_id: int):
    result = await db.execute(
        select(models.TripReview)
        .where(
            models.TripReview.user_id == user_id,
            models.TripReview.checklist_id == checklist_id,
        )
    )
    return result.scalar_one_or_none()

async def get_trip_reviews_by_user_id(db: AsyncSession, user_id: int, public_only: bool = False):
    stmt = (
        select(models.TripReview)
        .options(selectinload(models.TripReview.checklist))
        .join(models.Checklist, models.Checklist.id == models.TripReview.checklist_id)
        .where(models.TripReview.user_id == user_id)
        .order_by(models.TripReview.created_at.desc())
    )
    if public_only:
        stmt = stmt.where(models.Checklist.is_public.is_(True))
    result = await db.execute(stmt)
    return result.scalars().all()

# === City Attractions CRUD ===

async def get_city_attractions(db: AsyncSession, city_name: str):
    """Получение закэшированных достопримечательностей города"""
    result = await db.execute(
        select(models.CityAttraction).where(models.CityAttraction.city_name == city_name.strip().lower())
    )
    return result.scalar_one_or_none()

async def save_city_attractions(db: AsyncSession, city_name: str, data: list):
    """Сохранение/обновление достопримечательностей города"""
    normalized_name = city_name.strip().lower()
    existing = await get_city_attractions(db, normalized_name)
    if existing:
        existing.data = data
        await db.commit()
        await db.refresh(existing)
        return existing
    
    new_attraction = models.CityAttraction(
        city_name=normalized_name,
        data=data
    )
    db.add(new_attraction)
    await db.commit()
    await db.refresh(new_attraction)
    return new_attraction

# === Itinerary Events CRUD ===

async def create_itinerary_event(db: AsyncSession, checklist_id: int, data: schemas.ItineraryEventCreate):
    new_event = models.ItineraryEvent(
        checklist_id=checklist_id,
        event_date=data.event_date,
        time=data.time,
        title=data.title,
        description=data.description,
        address=data.address
    )
    db.add(new_event)
    await db.commit()
    await db.refresh(new_event)
    return new_event

async def update_itinerary_event(db: AsyncSession, event_id: int, data: schemas.ItineraryEventUpdate):
    result = await db.execute(select(models.ItineraryEvent).where(models.ItineraryEvent.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        return None
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(event, key, value)
    await db.commit()
    await db.refresh(event)
    return event


async def delete_itinerary_event(db: AsyncSession, event_id: int):
    result = await db.execute(select(models.ItineraryEvent).where(models.ItineraryEvent.id == event_id))
    event = result.scalar_one_or_none()
    if event:
        await db.delete(event)
        await db.commit()
        return True
    return False

# === Shared Backpacks CRUD ===

def _normalize_baggage_kind(kind: str | None) -> str:
    normalized = (kind or DEFAULT_BAGGAGE_KIND).strip().lower()
    return normalized or DEFAULT_BAGGAGE_KIND


def _normalize_baggage_name(name: str | None, kind: str | None = None) -> str:
    cleaned = (name or "").strip()
    if cleaned:
        return cleaned
    return BAGGAGE_KIND_DEFAULT_NAMES.get(_normalize_baggage_kind(kind), "Багаж")


async def get_backpacks_by_user(db: AsyncSession, checklist_id: int, user_id: int):
    result = await db.execute(
        select(models.UserBackpack)
        .where(
            models.UserBackpack.checklist_id == checklist_id,
            models.UserBackpack.user_id == user_id,
        )
        .order_by(
            models.UserBackpack.is_default.desc(),
            models.UserBackpack.sort_order.asc(),
            models.UserBackpack.id.asc(),
        )
    )
    return result.scalars().all()


async def get_backpack_by_user(db: AsyncSession, checklist_id: int, user_id: int):
    result = await db.execute(
        select(models.UserBackpack)
        .where(
            models.UserBackpack.checklist_id == checklist_id,
            models.UserBackpack.user_id == user_id,
        )
        .order_by(
            models.UserBackpack.is_default.desc(),
            models.UserBackpack.sort_order.asc(),
            models.UserBackpack.id.asc(),
        )
    )
    return result.scalars().first()

async def get_backpack_by_id(db: AsyncSession, backpack_id: int):
    result = await db.execute(
        select(models.UserBackpack).where(models.UserBackpack.id == backpack_id)
    )
    return result.scalar_one_or_none()


async def create_user_backpack(
    db: AsyncSession,
    checklist_id: int,
    user_id: int,
    name: str | None = None,
    kind: str | None = None,
    is_default: bool | None = None,
    items: list[str] | None = None,
):
    existing_backpacks = await get_backpacks_by_user(db, checklist_id, user_id)
    normalized_kind = _normalize_baggage_kind(kind)
    normalized_name = _normalize_baggage_name(name, normalized_kind)
    initial_items = _normalize_packing_profile_items(items)
    initial_quantities = {item: 1 for item in initial_items}

    if name is None and kind is None:
        existing_default = next((bp for bp in existing_backpacks if bp.is_default), None)
        if existing_default:
            return existing_default

    for backpack in existing_backpacks:
        if backpack.name.strip().lower() == normalized_name.lower():
            return backpack

    max_sort_order = max((bp.sort_order or 0) for bp in existing_backpacks) if existing_backpacks else -1
    should_be_default = True if not existing_backpacks else bool(is_default)
    shared_editor_ids = _normalize_editor_user_ids(
        [editor_id for backpack in existing_backpacks for editor_id in (backpack.editor_user_ids or [])],
        owner_user_id=user_id,
    )

    if should_be_default:
        for existing in existing_backpacks:
            existing.is_default = False

    new_backpack = models.UserBackpack(
        checklist_id=checklist_id,
        user_id=user_id,
        name=normalized_name,
        kind=normalized_kind,
        sort_order=max_sort_order + 1,
        is_default=should_be_default,
        editor_user_ids=shared_editor_ids,
        items=initial_items,
        checked_items=[],
        added_items=[],
        removed_items=[],
        item_quantities=initial_quantities,
        packed_quantities={},
    )
    db.add(new_backpack)
    await db.commit()
    await db.refresh(new_backpack)
    return new_backpack


async def create_user_baggage(
    db: AsyncSession,
    checklist_id: int,
    user_id: int,
    name: str,
    kind: str | None = None,
):
    return await create_user_backpack(
        db,
        checklist_id=checklist_id,
        user_id=user_id,
        name=name,
        kind=kind or "custom",
        is_default=False,
    )

async def update_backpack_items(db: AsyncSession, backpack_id: int, data: schemas.UserBackpackUpdate):
    result = await db.execute(select(models.UserBackpack).where(models.UserBackpack.id == backpack_id))
    backpack = result.scalar_one_or_none()
    if not backpack:
        return None

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if value is None:
            continue
        setattr(backpack, key, value)
        
    await db.commit()
    await db.refresh(backpack)
    return backpack


async def update_baggage_meta(db: AsyncSession, backpack_id: int, data: schemas.UserBaggageUpdate):
    backpack = await get_backpack_by_id(db, backpack_id)
    if not backpack:
        return None

    update_data = data.model_dump(exclude_unset=True)
    owned_backpacks = None
    if update_data.get("is_default") is True or "editor_user_ids" in update_data:
        owned_backpacks = await get_backpacks_by_user(db, backpack.checklist_id, backpack.user_id)

    if update_data.get("is_default") is True and owned_backpacks is not None:
        for existing in owned_backpacks:
            existing.is_default = existing.id == backpack.id

    if "editor_user_ids" in update_data:
        normalized_editor_ids = _normalize_editor_user_ids(
            update_data.get("editor_user_ids"),
            owner_user_id=backpack.user_id,
        )
        update_data["editor_user_ids"] = normalized_editor_ids
        for existing in owned_backpacks or []:
            existing.editor_user_ids = normalized_editor_ids

    for key, value in update_data.items():
        if value is None:
            continue
        setattr(backpack, key, value)

    await db.commit()
    await db.refresh(backpack)
    return backpack


def baggage_has_content(backpack: models.UserBackpack) -> bool:
    return bool(
        (backpack.items or [])
        or (backpack.checked_items or [])
        or (backpack.added_items or [])
        or (backpack.removed_items or [])
    )


async def delete_baggage(db: AsyncSession, backpack_id: int):
    backpack = await get_backpack_by_id(db, backpack_id)
    if not backpack:
        return None, "not_found"

    owned_backpacks = await get_backpacks_by_user(db, backpack.checklist_id, backpack.user_id)
    if len(owned_backpacks) <= 1:
        return None, "last_baggage"
    if backpack.is_default:
        return None, "default_baggage"
    if baggage_has_content(backpack):
        return None, "not_empty"

    checklist = await get_checklist_by_id(db, backpack.checklist_id)
    if checklist:
        checklist.hidden_sections = [
            section
            for section in (checklist.hidden_sections or [])
            if section != f"backpack:{backpack.id}"
        ]

    await db.delete(backpack)
    await db.commit()
    return backpack_id, None

async def generate_checklist_invite_token(db: AsyncSession, checklist_slug: str):
    checklist = await get_checklist_by_slug(db, checklist_slug)
    if not checklist:
        return None
    if not checklist.invite_token:
        # Generate short unique token
        checklist.invite_token = str(uuid.uuid4())[:8]
        await db.commit()
        await db.refresh(checklist)
    return checklist.invite_token

async def get_checklist_by_invite_token(db: AsyncSession, token: str):
    result = await db.execute(select(models.Checklist).where(models.Checklist.invite_token == token))
    return result.scalar_one_or_none()
