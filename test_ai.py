import asyncio
from sqlalchemy.orm import selectinload
from server.database import SessionLocal
from server.models import Checklist, User
from server.ai_service import ask_travel_ai
from server.trip_context import build_trip_context
from server.crud import get_checklist_by_slug
import os

os.environ["GEMINI_API_KEY"] = os.getenv("GEMINI_API_KEY", "dummy")

async def run_tests():
    async with SessionLocal() as db:
        # Get a checklist
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
            
        print(f"Testing with checklist: {checklist.city} ({checklist.slug})")
        context = build_trip_context(checklist, language="ru")
        
        tests = [
            "Что взять с собой для ребенка 5 лет?",
            "Положи 3 футболки в мой рюкзак",
            "Покажи план на сегодня",
            "Перенеси все события с утра на вечер",
            "Добавь трату 15 EUR на кофе",
            "Составь насыщенный план на первый день",
        ]
        
        for t in tests:
            print(f"\n--- Question: {t} ---")
            try:
                res = await ask_travel_ai(checklist.city, t, "ru", trip_context=context)
                print(f"Answer: {res.get('answer', '')[:150]}...")
                for k in ["plan_proposals", "event_change_proposals", "expense_proposals", "packing_recommendations", "actions"]:
                    if res.get(k):
                        print(f"{k}: {len(res[k])} items")
            except Exception as e:
                print(f"Error: {e}")

asyncio.run(run_tests())
