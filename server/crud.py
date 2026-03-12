from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import models
import schemas
import uuid
from auth import get_password_hash


# === User CRUD ===

async def create_user(db: AsyncSession, data: schemas.UserCreate):
    """Создание нового пользователя"""
    hashed_password = get_password_hash(data.password)
    user = models.User(
        email=data.email,
        username=data.username,
        hashed_password=hashed_password,
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
        daily_forecast=[f.model_dump(mode='json') if hasattr(f, 'model_dump') else f for f in data.daily_forecast] if data.daily_forecast else None,
        user_id=data.user_id,
        origin_city=data.origin_city,
    )
    db.add(checklist)
    await db.commit()
    await db.refresh(checklist)
    return checklist


async def get_checklist_by_slug(db: AsyncSession, slug: str):
    result = await db.execute(select(models.Checklist).where(models.Checklist.slug == slug))
    return result.scalar_one_or_none()


async def get_checklist_by_id(db: AsyncSession, checklist_id: int):
    result = await db.execute(select(models.Checklist).where(models.Checklist.id == checklist_id))
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
        .where(models.Checklist.user_id == user_id)
        .order_by(models.Checklist.id.desc())
    )
    return result.scalars().all()


async def save_or_update_tg_checklist(db: AsyncSession, data: schemas.ChecklistCreate):
    # Всегда создаём новый чеклист
    return await create_checklist(db, data)


async def update_checklist_state(db: AsyncSession, slug: str, checked_items=None, removed_items=None, added_items=None, items=None):
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
    await db.commit()
    await db.refresh(checklist)
    return checklist

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
        description=data.description
    )
    db.add(new_event)
    await db.commit()
    await db.refresh(new_event)
    return new_event

async def delete_itinerary_event(db: AsyncSession, event_id: int):
    result = await db.execute(select(models.ItineraryEvent).where(models.ItineraryEvent.id == event_id))
    event = result.scalar_one_or_none()
    if event:
        await db.delete(event)
        await db.commit()
        return True
    return False
