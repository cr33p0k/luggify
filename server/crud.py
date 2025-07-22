from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import models, schemas
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
    )
    db.add(checklist)
    await db.commit()
    await db.refresh(checklist)
    return checklist

async def get_checklist_by_slug(db: AsyncSession, slug: str):
    result = await db.execute(select(models.Checklist).where(models.Checklist.slug == slug))
    return result.scalar_one_or_none()
