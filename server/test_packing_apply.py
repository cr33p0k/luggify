import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from types import ModuleType
from unittest.mock import AsyncMock, patch


sys.path.insert(0, str(Path(__file__).resolve().parent))
fake_crud = ModuleType("crud")
fake_crud.get_checklist_by_id = None
fake_crud.create_user_backpack = None
sys.modules.setdefault("crud", fake_crud)

from packing_apply import apply_packing_recommendations

if sys.modules.get("crud") is fake_crud:
    sys.modules.pop("crud", None)


def obj(**kwargs):
    return SimpleNamespace(**kwargs)


class FakeDb:
    def __init__(self):
        self.commits = 0

    async def commit(self):
        self.commits += 1


def checklist_fixture():
    owner = obj(id=1, username="owner")
    return obj(
        id=10,
        user_id=1,
        user=owner,
        city="Budapest",
        start_date="2026-05-01",
        end_date="2026-05-03",
        items=["Фотоаппарат", "Паспорт"],
        checked_items=["Паспорт"],
        added_items=[],
        removed_items=[],
        item_quantities={"Фотоаппарат": 1, "Паспорт": 1},
        packed_quantities={"Паспорт": 1},
        hidden_sections=[],
        backpacks=[
            obj(
                id=1,
                checklist_id=10,
                user_id=1,
                user=owner,
                name="Рюкзак",
                kind="backpack",
                sort_order=0,
                is_default=True,
                editor_user_ids=[],
                items=["Зарядка"],
                checked_items=[],
                added_items=[],
                removed_items=[],
                item_quantities={"Зарядка": 1},
                packed_quantities={},
            ),
            obj(
                id=2,
                checklist_id=10,
                user_id=1,
                user=owner,
                name="Ручная кладь",
                kind="carry_on",
                sort_order=1,
                is_default=False,
                editor_user_ids=[],
                items=[],
                checked_items=[],
                added_items=[],
                removed_items=[],
                item_quantities={},
                packed_quantities={},
            ),
        ],
    )


class PackingApplyTests(unittest.IsolatedAsyncioTestCase):
    async def test_apply_adds_to_default_baggage(self):
        checklist = checklist_fixture()
        db = FakeDb()
        with patch("packing_apply.crud.get_checklist_by_id", new=AsyncMock(return_value=checklist)):
            result = await apply_packing_recommendations(
                db,
                checklist,
                [{"item": "Дождевик", "suggested_action": "add", "priority": "must", "reason": "rain", "reason_tags": ["weather"]}],
                actor_user_id=1,
            )

        self.assertEqual(result["applied_count"], 1)
        self.assertIn("Дождевик", checklist.backpacks[0].items)
        self.assertEqual(checklist.backpacks[0].item_quantities["Дождевик"], 1)

    async def test_apply_removes_from_shared_section(self):
        checklist = checklist_fixture()
        db = FakeDb()
        with patch("packing_apply.crud.get_checklist_by_id", new=AsyncMock(return_value=checklist)):
            result = await apply_packing_recommendations(
                db,
                checklist,
                [{"item": "Фотоаппарат", "suggested_action": "remove", "priority": "optional", "reason": "light", "reason_tags": ["packing_style"]}],
                actor_user_id=1,
            )

        self.assertEqual(result["applied_count"], 1)
        self.assertIn("Фотоаппарат", checklist.removed_items)
        self.assertNotIn("Фотоаппарат", checklist.item_quantities)

    async def test_apply_moves_existing_item_to_carry_on(self):
        checklist = checklist_fixture()
        db = FakeDb()
        with patch("packing_apply.crud.get_checklist_by_id", new=AsyncMock(return_value=checklist)):
            result = await apply_packing_recommendations(
                db,
                checklist,
                [{"item": "Зарядка", "suggested_action": "move_to_carry_on", "priority": "must", "reason": "road", "reason_tags": ["carry_on"]}],
                actor_user_id=1,
            )

        self.assertEqual(result["applied_count"], 1)
        self.assertNotIn("Зарядка", checklist.backpacks[0].items)
        self.assertIn("Зарядка", checklist.backpacks[1].items)
        self.assertEqual(checklist.backpacks[1].item_quantities["Зарядка"], 1)


if __name__ == "__main__":
    unittest.main()
