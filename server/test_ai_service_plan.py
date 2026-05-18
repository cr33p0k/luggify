import unittest

from ai_service import (
    _detect_expense_intent,
    _extract_json_object,
    _extract_simple_expense_proposals,
    _normalize_event_change_proposals,
    _normalize_expense_proposals,
    _normalize_packing_recommendations,
    _normalize_plan_proposals,
)
from assistant_intents import detect_assistant_intent


class AiServicePlanProposalTests(unittest.TestCase):
    def test_meal_slots_are_normalized_before_sorting(self):
        proposals = _normalize_plan_proposals(
            [
                {
                    "event_date": "2026-05-14",
                    "time": "19:00",
                    "title": "Обед",
                    "description": "Пообедайте в центре города.",
                    "event_type": "food",
                    "day_part": "evening",
                },
                {
                    "event_date": "2026-05-14",
                    "time": "17:15",
                    "title": "Памятник Штефану Великому",
                    "description": "Короткая прогулка.",
                    "event_type": "sight",
                    "day_part": "evening",
                },
                {
                    "event_date": "2026-05-14",
                    "time": "20:15",
                    "title": "Ужин",
                    "description": "Ужин в ресторане.",
                    "event_type": "food",
                    "day_part": "evening",
                },
            ],
            "2026-05-14",
            "2026-05-14",
        )

        by_title = {proposal["title"]: proposal for proposal in proposals}
        self.assertEqual(by_title["Обед"]["time"], "13:00")
        self.assertEqual(by_title["Обед"]["day_part"], "day")
        self.assertGreaterEqual(by_title["Ужин"]["time"], "19:00")
        self.assertLess(by_title["Ужин"]["time"], "21:00")
        self.assertEqual(by_title["Ужин"]["day_part"], "evening")
        self.assertEqual([proposal["title"] for proposal in proposals][0], "Обед")


class AiServiceExpenseAndEventTests(unittest.TestCase):
    def test_simple_budget_command_builds_expense_proposal(self):
        proposals = _extract_simple_expense_proposals(
            "поставь бюджет 50000 ₽",
            {"expenses": {"base_currency": "RUB"}},
            "ru",
        )

        self.assertEqual(proposals[0]["action"], "set_budget")
        self.assertEqual(proposals[0]["budget_amount"], 50000)
        self.assertEqual(proposals[0]["base_currency"], "RUB")

    def test_simple_expense_command_detects_food_category(self):
        proposals = _extract_simple_expense_proposals(
            "добавь 25 EUR на обед",
            {"expenses": {"base_currency": "RUB"}},
            "ru",
        )

        self.assertEqual(proposals[0]["action"], "create")
        self.assertEqual(proposals[0]["amount"], 25)
        self.assertEqual(proposals[0]["currency"], "EUR")
        self.assertEqual(proposals[0]["category"], "food")

    def test_expense_intent_wins_over_add_keyword(self):
        self.assertEqual(
            detect_assistant_intent("добавь траты 15 евро на музей"),
            "expenses",
        )
        self.assertTrue(_detect_expense_intent("добавь 15 евро на музей"))

    def test_multiple_expenses_are_split_into_proposals(self):
        proposals = _extract_simple_expense_proposals(
            "добавь траты 15 евро на музей и 10 долларов на кофе",
            {"expenses": {"base_currency": "RUB"}},
            "ru",
        )

        self.assertEqual(len(proposals), 2)
        self.assertEqual(proposals[0]["title"], "музей")
        self.assertEqual(proposals[0]["amount"], 15)
        self.assertEqual(proposals[0]["currency"], "EUR")
        self.assertEqual(proposals[1]["title"], "кофе")
        self.assertEqual(proposals[1]["amount"], 10)
        self.assertEqual(proposals[1]["currency"], "USD")

    def test_simple_daily_budget_command_builds_daily_limit_proposal(self):
        proposals = _extract_simple_expense_proposals(
            "поставь дневной лимит 50 EUR",
            {"expenses": {"base_currency": "RUB"}},
            "ru",
        )

        self.assertEqual(proposals[0]["action"], "set_daily_budget")
        self.assertEqual(proposals[0]["daily_budget_amount"], 50)
        self.assertEqual(proposals[0]["base_currency"], "EUR")

    def test_split_expense_command_stores_personal_share(self):
        proposals = _extract_simple_expense_proposals(
            "раздели 60 EUR ужин на троих",
            {"expenses": {"base_currency": "RUB"}},
            "ru",
        )

        self.assertEqual(proposals[0]["action"], "create")
        self.assertEqual(proposals[0]["amount"], 20)
        self.assertEqual(proposals[0]["split_count"], 3)
        self.assertIn("1/3", proposals[0]["note"])

    def test_expense_normalizer_drops_incomplete_actions(self):
        proposals = _normalize_expense_proposals(
            [
                {"action": "create", "title": "музей", "amount": 15, "currency": "EUR"},
                {"action": "create", "title": "", "amount": 15, "currency": "EUR"},
                {"action": "set_budget", "budget_amount": "bad", "currency": "RUB"},
                {"action": "set_daily_budget", "daily_budget_amount": 50, "currency": "EUR"},
            ],
            {"expenses": {"base_currency": "RUB"}},
        )

        self.assertEqual(len(proposals), 2)
        self.assertEqual(proposals[0]["title"], "музей")
        self.assertEqual(proposals[1]["action"], "set_daily_budget")

    def test_event_change_normalizer_sanitizes_bad_time(self):
        proposals = _normalize_event_change_proposals([
            {
                "action": "update",
                "target_event_id": "42",
                "event_date": "2026-05-12",
                "time": "вечером",
                "title": "Прогулка",
            }
        ])

        self.assertEqual(proposals[0]["target_event_id"], 42)
        self.assertIsNone(proposals[0]["time"])

    def test_event_change_normalizer_allows_create_without_target_id(self):
        proposals = _normalize_event_change_proposals([
            {
                "action": "create",
                "target_event_id": None,
                "event_date": "2026-05-12",
                "time": "11:00",
                "title": "Прогулка",
            }
        ])

        self.assertEqual(proposals[0]["action"], "create")
        self.assertIsNone(proposals[0]["target_event_id"])
        self.assertEqual(proposals[0]["title"], "Прогулка")

    def test_json_extractor_repairs_semicolon_separated_model_payload(self):
        payload = _extract_json_object(
            '{\n'
            '"answer": "Понял";\n'
            '"packing_recommendations": [\n'
            '{"suggested_action": "remove"; "item": "Фотоаппарат"; "quantity": 1; "reason": "Лишний вес."}\n'
            ']\n'
            '}'
        )

        self.assertIsNotNone(payload)
        self.assertEqual(payload["answer"], "Понял")
        self.assertEqual(payload["packing_recommendations"][0]["item"], "Фотоаппарат")

    def test_packing_recommendations_get_required_defaults(self):
        proposals = _normalize_packing_recommendations([
            {"suggested_action": "remove", "item": "Фотоаппарат", "quantity": 1, "reason": "Лишний вес."}
        ])

        self.assertEqual(proposals[0]["item"], "Фотоаппарат")
        self.assertEqual(proposals[0]["priority"], "nice")
        self.assertEqual(proposals[0]["risk_level"], "medium")


if __name__ == "__main__":
    unittest.main()
