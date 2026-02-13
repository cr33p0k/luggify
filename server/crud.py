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
        user_id=data.user_id,
    )
    db.add(checklist)
    await db.commit()
    await db.refresh(checklist)
    return checklist


async def get_checklist_by_slug(db: AsyncSession, slug: str):
    result = await db.execute(select(models.Checklist).where(models.Checklist.slug == slug))
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
