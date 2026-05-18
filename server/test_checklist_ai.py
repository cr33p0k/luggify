import sys
import unittest
from os import environ
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, patch


sys.path.insert(0, str(Path(__file__).resolve().parent))

fake_crud = ModuleType("crud")


async def _fake_get_checklist_by_id(_db, _checklist_id):
    return _db.checklist


async def _fake_create_user_baggage(*_args, **_kwargs):
    return None


fake_crud.get_checklist_by_id = _fake_get_checklist_by_id
fake_crud.create_user_baggage = _fake_create_user_baggage

import checklist_ai
from checklist_ai import apply_checklist_ai_actions, parse_checklist_actions

checklist_ai.crud = fake_crud


def obj(**kwargs):
    return SimpleNamespace(**kwargs)


class FakeDb:
    def __init__(self, checklist):
        self.checklist = checklist
        self.commits = 0

    async def commit(self):
        self.commits += 1


def checklist_fixture():
    owner = obj(id=1, username="max")
    backpack = obj(
        id=101,
        checklist_id=10,
        user_id=1,
        user=owner,
        name="Рюкзак",
        kind="backpack",
        child_profile_id=None,
        sort_order=0,
        is_default=True,
        editor_user_ids=[],
        items=["Паспорт", "Бронь отеля", "Зарядка"],
        checked_items=[],
        added_items=[],
        removed_items=[],
        item_quantities={"Паспорт": 1, "Бронь отеля": 1, "Зарядка": 1},
        item_categories={"Паспорт": "Документы", "Бронь отеля": "Документы", "Зарядка": "Техника"},
        packed_quantities={},
    )
    suitcase = obj(
        id=102,
        checklist_id=10,
        user_id=1,
        user=owner,
        name="Чемодан",
        kind="suitcase",
        child_profile_id=None,
        sort_order=1,
        is_default=False,
        editor_user_ids=[],
        items=[],
        checked_items=[],
        added_items=[],
        removed_items=[],
        item_quantities={},
        item_categories={},
        packed_quantities={},
    )
    carry_on = obj(
        id=103,
        checklist_id=10,
        user_id=1,
        user=owner,
        name="Ручная кладь",
        kind="carry_on",
        child_profile_id=None,
        sort_order=2,
        is_default=False,
        editor_user_ids=[],
        items=[],
        checked_items=[],
        added_items=[],
        removed_items=[],
        item_quantities={},
        item_categories={},
        packed_quantities={},
    )
    return obj(
        id=10,
        user_id=1,
        user=owner,
        city="Budapest",
        start_date="2026-05-01",
        end_date="2026-05-03",
        items=["Фотоаппарат"],
        checked_items=[],
        added_items=[],
        removed_items=[],
        item_quantities={"Фотоаппарат": 1},
        item_categories={"Фотоаппарат": "Техника"},
        packed_quantities={},
        hidden_sections=[],
        trip_profile={
            "children_ages": [10],
            "child_profiles": [{"id": "child_veronika", "name": "Вероника", "age": 10}],
        },
        backpacks=[backpack, suitcase, carry_on],
    )


def add_child_backpack(checklist, *, name="Рюкзак", kind="backpack"):
    checklist.backpacks.append(obj(
        id=201,
        checklist_id=10,
        user_id=1,
        user=checklist.user,
        name=name,
        kind=kind,
        child_profile_id="child_veronika",
        sort_order=0,
        is_default=True,
        editor_user_ids=[],
        items=[],
        checked_items=[],
        added_items=[],
        removed_items=[],
        item_quantities={},
        item_categories={},
        packed_quantities={},
    ))
    return checklist.backpacks[-1]


class ChecklistAITests(unittest.IsolatedAsyncioTestCase):
    async def test_parse_add_command_keeps_category_hint(self):
        checklist = checklist_fixture()

        parsed = await parse_checklist_actions(
            "добавь пластыри в аптечку",
            checklist,
            language="ru",
            actor_user_id=1,
        )

        self.assertTrue(parsed["recognized_action_request"])
        self.assertEqual(parsed["actions"][0]["type"], "add")
        self.assertEqual(parsed["actions"][0]["category_hint"], "Аптечка")
        self.assertEqual(parsed["actions"][0]["items"], ["Пластыри"])

    async def test_parse_add_to_backpack_does_not_include_section_in_item_name(self):
        checklist = checklist_fixture()

        parsed = await parse_checklist_actions(
            "добавь воду в рюкзак",
            checklist,
            language="ru",
            actor_user_id=1,
        )

        self.assertTrue(parsed["recognized_action_request"])
        self.assertEqual(parsed["actions"][0]["type"], "add")
        self.assertEqual(parsed["actions"][0]["items"], ["Вода"])
        self.assertIn("рюкзак", parsed["actions"][0]["section_hint"])

    async def test_apply_add_to_suitcase_targets_suitcase(self):
        checklist = checklist_fixture()
        db = FakeDb(checklist)
        parsed = await parse_checklist_actions(
            "добавь воду в чемодан",
            checklist,
            language="ru",
            actor_user_id=1,
        )

        result = await apply_checklist_ai_actions(
            db,
            checklist,
            parsed["actions"],
            language="ru",
            actor_user_id=1,
        )

        self.assertTrue(result["applied"])
        self.assertIn("Вода", checklist.backpacks[1].items)
        self.assertNotIn("Вода", checklist.backpacks[0].items)

    async def test_apply_add_to_carry_on_targets_carry_on(self):
        checklist = checklist_fixture()
        db = FakeDb(checklist)
        parsed = await parse_checklist_actions(
            "добавь воду в ручную кладь",
            checklist,
            language="ru",
            actor_user_id=1,
        )

        result = await apply_checklist_ai_actions(
            db,
            checklist,
            parsed["actions"],
            language="ru",
            actor_user_id=1,
        )

        self.assertTrue(result["applied"])
        self.assertIn("Вода", checklist.backpacks[2].items)
        self.assertNotIn("Вода", checklist.backpacks[0].items)

    async def test_apply_add_quantity_to_backpack_keeps_quantity_with_item(self):
        checklist = checklist_fixture()
        db = FakeDb(checklist)
        parsed = await parse_checklist_actions(
            "добавь две футболки в рюкзак",
            checklist,
            language="ru",
            actor_user_id=1,
        )

        self.assertTrue(parsed["recognized_action_request"])
        self.assertEqual(parsed["actions"][0]["type"], "add")
        self.assertEqual(parsed["actions"][0]["items"], ["Футболка"])
        self.assertEqual(parsed["actions"][0]["item_specs"][0]["quantity"], 2)

        result = await apply_checklist_ai_actions(
            db,
            checklist,
            parsed["actions"],
            language="ru",
            actor_user_id=1,
        )

        self.assertTrue(result["applied"])
        self.assertIn("Футболка", checklist.backpacks[0].items)
        self.assertNotIn("Две", checklist.backpacks[0].items)
        self.assertEqual(checklist.backpacks[0].item_quantities["футболка"], 2)

    async def test_parse_create_child_suitcase_without_ai(self):
        checklist = checklist_fixture()
        with patch("checklist_ai._extract_actions_with_ai", new=AsyncMock()) as ai_mock:
            parsed = await parse_checklist_actions(
                "создай веронике багаж чемодан",
                checklist,
                language="ru",
                actor_user_id=1,
            )

        self.assertTrue(parsed["recognized_action_request"])
        self.assertEqual(parsed["actions"][0]["type"], "create_baggage")
        self.assertEqual(parsed["actions"][0]["items"], ["Чемодан"])
        self.assertEqual(parsed["actions"][0]["baggage_kind"], "suitcase")
        self.assertEqual(parsed["actions"][0]["target_user_id"], 1)
        self.assertEqual(parsed["actions"][0]["child_profile_id"], "child_veronika")
        ai_mock.assert_not_awaited()

    async def test_apply_create_child_suitcase_uses_child_profile_scope(self):
        checklist = checklist_fixture()
        db = FakeDb(checklist)
        parsed = await parse_checklist_actions(
            "создай багаж чемодан веронике",
            checklist,
            language="ru",
            actor_user_id=1,
        )

        with patch("checklist_ai.crud.create_user_baggage", new=AsyncMock()) as create_mock:
            result = await apply_checklist_ai_actions(
                db,
                checklist,
                parsed["actions"],
                language="ru",
                actor_user_id=1,
            )

        self.assertTrue(result["applied"])
        create_mock.assert_awaited_once()
        self.assertEqual(create_mock.await_args.kwargs["name"], "Чемодан")
        self.assertEqual(create_mock.await_args.kwargs["kind"], "suitcase")
        self.assertEqual(create_mock.await_args.kwargs["child_profile_id"], "child_veronika")

    async def test_add_items_to_child_backpack_targets_child_baggage_without_ai(self):
        checklist = checklist_fixture()
        child_backpack = add_child_backpack(checklist)
        db = FakeDb(checklist)
        with patch("checklist_ai._extract_actions_with_ai", new=AsyncMock()) as ai_mock:
            parsed = await parse_checklist_actions(
                "добавь 5 футболок веронике в рюкзак",
                checklist,
                language="ru",
                actor_user_id=1,
            )

        self.assertTrue(parsed["recognized_action_request"])
        self.assertEqual(parsed["actions"][0]["type"], "add")
        self.assertEqual(parsed["actions"][0]["items"], ["Футболка"])
        self.assertEqual(parsed["actions"][0]["item_specs"][0]["quantity"], 5)
        ai_mock.assert_not_awaited()

        result = await apply_checklist_ai_actions(
            db,
            checklist,
            parsed["actions"],
            language="ru",
            actor_user_id=1,
        )

        self.assertTrue(result["applied"])
        self.assertIn("Футболка", child_backpack.items)
        self.assertEqual(child_backpack.item_quantities["футболка"], 5)
        self.assertNotIn("Футболка", checklist.backpacks[0].items)
        self.assertEqual(result["message"], "Добавил в рюкзак Вероники: Футболка ×5")

    async def test_add_items_after_child_backpack_targets_child_baggage_without_ai(self):
        checklist = checklist_fixture()
        child_backpack = add_child_backpack(checklist)
        db = FakeDb(checklist)
        with patch("checklist_ai._extract_actions_with_ai", new=AsyncMock()) as ai_mock:
            parsed = await parse_checklist_actions(
                "добавь веронике в рюкзак 5 футболок",
                checklist,
                language="ru",
                actor_user_id=1,
            )

        self.assertTrue(parsed["recognized_action_request"])
        self.assertEqual(parsed["actions"][0]["type"], "add")
        self.assertEqual(parsed["actions"][0]["items"], ["Футболка"])
        self.assertEqual(parsed["actions"][0]["item_specs"][0]["quantity"], 5)
        ai_mock.assert_not_awaited()

        result = await apply_checklist_ai_actions(
            db,
            checklist,
            parsed["actions"],
            language="ru",
            actor_user_id=1,
        )

        self.assertTrue(result["applied"])
        self.assertIn("Футболка", child_backpack.items)
        self.assertNotIn("Веронике", child_backpack.items)
        self.assertEqual(child_backpack.item_quantities["футболка"], 5)
        self.assertEqual(result["message"], "Добавил в рюкзак Вероники: Футболка ×5")

    async def test_info_request_filters_items_by_category(self):
        checklist = checklist_fixture()

        parsed = await parse_checklist_actions(
            "что в документах",
            checklist,
            language="ru",
            actor_user_id=1,
        )

        self.assertEqual(parsed["info_request"]["type"], "items")
        self.assertEqual(parsed["info_request"]["category_hint"], "Документы")

    async def test_apply_add_command_persists_item_category(self):
        checklist = checklist_fixture()
        db = FakeDb(checklist)
        parsed = await parse_checklist_actions(
            "добавь пластыри в аптечку",
            checklist,
            language="ru",
            actor_user_id=1,
        )

        result = await apply_checklist_ai_actions(
            db,
            checklist,
            parsed["actions"],
            language="ru",
            actor_user_id=1,
        )

        self.assertTrue(result["applied"])
        self.assertIn("Пластыри", checklist.backpacks[0].items)
        self.assertEqual(checklist.backpacks[0].item_categories["пластыри"], "Аптечка")

    async def test_apply_check_command_can_target_whole_category(self):
        checklist = checklist_fixture()
        db = FakeDb(checklist)
        parsed = await parse_checklist_actions(
            "отметь документы",
            checklist,
            language="ru",
            actor_user_id=1,
        )

        result = await apply_checklist_ai_actions(
            db,
            checklist,
            parsed["actions"],
            language="ru",
            actor_user_id=1,
        )

        self.assertTrue(result["applied"])
        self.assertIn("Паспорт", checklist.backpacks[0].checked_items)
        self.assertIn("Бронь отеля", checklist.backpacks[0].checked_items)
        self.assertNotIn("Зарядка", checklist.backpacks[0].checked_items)

    async def test_simple_incomplete_command_does_not_call_ai_fallback(self):
        checklist = checklist_fixture()
        with (
            patch.dict(environ, {"CHECKLIST_AI_PARSE_FALLBACK_MODE": "smart"}, clear=False),
            patch("checklist_ai._extract_actions_with_ai", new=AsyncMock(return_value={
                "recognized_action_request": True,
                "actions": [{"type": "add", "items": ["Пластыри"]}],
            })) as ai_mock,
        ):
            parsed = await parse_checklist_actions(
                "добавь пожалуйста",
                checklist,
                language="ru",
                actor_user_id=1,
            )

        self.assertEqual(parsed["actions"], [])
        ai_mock.assert_not_awaited()

    async def test_complex_reorganization_can_use_ai_fallback(self):
        checklist = checklist_fixture()
        with (
            patch.dict(environ, {"CHECKLIST_AI_PARSE_FALLBACK_MODE": "smart"}, clear=False),
            patch("checklist_ai._extract_actions_with_ai", new=AsyncMock(return_value={
                "recognized_action_request": True,
                "actions": [{"type": "remove", "items": ["Фотоаппарат"]}],
            })) as ai_mock,
        ):
            parsed = await parse_checklist_actions(
                "разложи список по уму",
                checklist,
                language="ru",
                actor_user_id=1,
            )

        self.assertTrue(parsed["recognized_action_request"])
        self.assertEqual(parsed["actions"][0]["type"], "remove")
        ai_mock.assert_awaited_once()

    async def test_remove_extra_is_packing_advice_not_literal_item(self):
        checklist = checklist_fixture()
        with patch("checklist_ai._extract_actions_with_ai", new=AsyncMock()) as ai_mock:
            parsed = await parse_checklist_actions(
                "убери лишнее из моего чемодана",
                checklist,
                language="ru",
                actor_user_id=1,
            )

        self.assertFalse(parsed["recognized_action_request"])
        self.assertEqual(parsed["actions"], [])
        ai_mock.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
