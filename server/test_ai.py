import asyncio
from sqlalchemy.orm import selectinload
from database import SessionLocal
from models import Checklist, User
from ai_service import ask_travel_ai
from trip_context import build_trip_context
import os

os.environ["GEMINI_API_KEY"] = os.getenv("GEMINI_API_KEY", "dummy")

async def run_tests():
    async with SessionLocal() as db:
        from sqlalchemy import select
        stmt = select(Checklist).options(
            selectinload(Checklist.backpacks),
            selectinload(Checklist.events),
            selectinload(Checklist.expenses),
        ).limit(1)
        result = await db.execute(stmt)
        checklist = result.scalar_one_or_none()
        
        if not checklist:
            print("No checklists found")
            return
            
        print(f"Testing with checklist: {checklist.city}")
        context = build_trip_context(checklist, language="ru")
        
        tests = [
            "Добавь пять футболок в мой рюкзак",
            "Убери носки из сумки",
            "Переложи паспорт в ручную кладь",
        ]
        
        for t in tests:
            print(f"\n--- Question: {t} ---")
            try:
                res = await ask_travel_ai(checklist.city, t, "ru", trip_context=context)
                print(f"Answer: {res.get('answer', '')}")
                for k in ["packing_recommendations"]:
                    if res.get(k):
                        print(f"{k}: {res[k]}")
            except Exception as e:
                print(f"Error: {e}")

asyncio.run(run_tests())
