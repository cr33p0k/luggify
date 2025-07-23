from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import models
import schemas
import uuid

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

async def save_or_update_tg_checklist(db: AsyncSession, data: schemas.ChecklistCreate):
    # Всегда создаём новый чеклист
    return await create_checklist(db, data)

async def update_checklist_state(db: AsyncSession, slug: str, checked_items=None, removed_items=None, added_items=None):
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
    await db.commit()
    await db.refresh(checklist)
    return checklist
