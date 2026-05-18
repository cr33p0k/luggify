import asyncio
import os
from database import SessionLocal
from models import Checklist
from ai_service import ask_travel_ai, build_ad_hoc_trip_context
from sqlalchemy.orm import selectinload
from sqlalchemy import select

async def run():
    async with SessionLocal() as db:
        stmt = select(Checklist).limit(1)
        res = await db.execute(stmt)
        chk = res.scalar_one_or_none()
        
    ctx = build_ad_hoc_trip_context(city="Paris", start_date="2026-06-01", end_date="2026-06-10", language="ru")
    ans = await ask_travel_ai("Paris", "добавь траты 15 евро на музей и 10 долларов на кофе", "ru", trip_context=ctx)
    print("KEYS:", ans.keys())
    print("ANSWER:", ans.get("answer"))
    print("EXPENSES:", ans.get("expense_proposals"))
    print("PACKING:", ans.get("packing_recommendations"))

asyncio.run(run())
