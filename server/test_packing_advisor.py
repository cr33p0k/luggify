import sys
import unittest
from unittest.mock import patch
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))

from ai_service import ask_travel_ai
from packing_advisor import build_packing_advice, detect_packing_mode
from packing_logic import get_default_baggage_kinds


def base_context():
    return {
        "trip": {
            "city": "Budapest",
            "start_date": "2026-05-01",
            "end_date": "2026-05-04",
            "duration_days": 4,
            "avg_temp": 22,
            "transports": ["plane"],
        },
        "trip_profile": {
            "trip_type": "city_break",
            "trip_activities": ["city_break"],
            "baggage_format": "carry_on",
            "packing_style": "light",
        },
        "daily_forecast": [
            {
                "date": "2026-05-02",
                "condition": "Умеренный дождь",
                "temp_min": 12,
                "temp_max": 18,
                "uv_index": 3,
                "wind_speed": 18,
            },
            {
                "date": "2026-05-03",
                "condition": "Ясно",
                "temp_min": 18,
                "temp_max": 29,
                "uv_index": 7,
                "wind_speed": 12,
            },
        ],
        "baggage": {
            "shared": {
                "label": "shared packing list",
                "items": [
                    {"name": "Паспорт", "quantity": 1, "packed_quantity": 1, "is_removed": False, "is_packed": True},
                    {"name": "Фотоаппарат", "quantity": 1, "packed_quantity": 0, "is_removed": False, "is_packed": False},
                ],
            },
            "backpacks": [
                {
                    "label": "Рюкзак owner",
                    "items": [
                        {"name": "Зарядка", "quantity": 1, "packed_quantity": 0, "is_removed": False, "is_packed": False},
                    ],
                }
            ],
        },
        "packing_summary": {"packed_count": 1, "remaining_count": 2},
        "events": [],
        "participants": [],
        "attractions": [],
    }

def short_trip_context():
    context = base_context()
    context["trip"] = {**context["trip"], "duration_days": 2, "end_date": "2026-05-02"}
    return context


def prepared_context():
    context = base_context()
    context["daily_forecast"] = [
        {
            "date": "2026-05-02",
            "condition": "Ветрено",
            "temp_min": 10,
            "temp_max": 16,
            "uv_index": 2,
            "wind_speed": 32,
        }
    ]
    return context


class PackingAdvisorTests(unittest.TestCase):
    def test_detects_packing_modes(self):
        self.assertEqual(detect_packing_mode("что еще взять?"), "add_more")
        self.assertEqual(detect_packing_mode("что в ручную кладь?"), "carry_on")
        self.assertEqual(detect_packing_mode("сделай список легче"), "remove")
        self.assertEqual(detect_packing_mode("я поеду только с рюкзаком"), "remove")
        self.assertEqual(detect_packing_mode("что не забыть в день выезда"), "departure_day")

    def test_add_more_uses_weather_reasons(self):
        advice = build_packing_advice("что еще взять?", base_context(), "ru")

        self.assertIsNotNone(advice)
        items = {item["item"] for item in advice["recommendations"]}
        self.assertIn("Дождевик", items)
        self.assertIn("Солнцезащитный крем (SPF 50+)", items)
        raincoat = next(item for item in advice["recommendations"] if item["item"] == "Дождевик")
        self.assertIn("weather", raincoat["reason_tags"])
        self.assertIn("2026-05-02", raincoat["reason"])
        sunscreen = next(item for item in advice["recommendations"] if item["item"] == "Солнцезащитный крем (SPF 50+)")
        self.assertIn("daily_weather", sunscreen["reason_tags"])
        self.assertIn("2026-05-03", sunscreen["reason"])

    def test_carry_on_recommends_move_or_add(self):
        advice = build_packing_advice("что держать в ручной клади?", base_context(), "ru")

        self.assertIsNotNone(advice)
        passport = next(item for item in advice["recommendations"] if item["item"] == "Паспорт")
        self.assertEqual(passport["suggested_action"], "move_to_carry_on")
        powerbank = next(item for item in advice["recommendations"] if item["item"] == "Power bank")
        self.assertEqual(powerbank["suggested_action"], "add")
        liquids = next(item for item in advice["recommendations"] if item["item"] == "Жидкости <100мл (в прозрачном пакете)")
        self.assertIn("baggage_format", liquids["reason_tags"])

    def test_remove_recommends_optional_existing_items(self):
        advice = build_packing_advice("что убрать лишнее?", base_context(), "ru")

        self.assertIsNotNone(advice)
        camera = next(item for item in advice["recommendations"] if item["item"] == "Фотоаппарат")
        self.assertEqual(camera["suggested_action"], "remove")
        self.assertIn("baggage_format", camera["reason_tags"])

    def test_backpack_only_uses_local_remove_advice(self):
        advice = build_packing_advice("я поеду только с рюкзаком", base_context(), "ru")

        self.assertIsNotNone(advice)
        self.assertEqual(advice["mode"], "remove")
        self.assertTrue(advice["recommendations"])

    def test_departure_day_mentions_rain_and_carry_on_only(self):
        advice = build_packing_advice("что не забыть в день выезда", base_context(), "ru")

        raincoat = next(item for item in advice["recommendations"] if item["item"] == "Дождевик")
        liquids = next(item for item in advice["recommendations"] if item["item"] == "Жидкости <100мл (в прозрачном пакете)")

        self.assertIn("2026-05-02", raincoat["reason"])
        self.assertIn("carry_on", liquids["reason_tags"])

    def test_short_trip_remove_mode_adds_duration_reasoning(self):
        advice = build_packing_advice("что убрать для короткой поездки?", short_trip_context(), "ru")
        duration_recommendations = [item for item in advice["recommendations"] if "duration" in item["reason_tags"]]

        self.assertTrue(duration_recommendations)

    def test_request_phrase_can_shift_style_to_minimal(self):
        advice = build_packing_advice("собери по минимуму, что еще взять?", base_context(), "ru")
        umbrella = next(item for item in advice["recommendations"] if item["item"] == "Зонт")
        self.assertEqual(umbrella["priority"], "optional")

    def test_request_phrase_can_shift_style_to_prepared(self):
        advice = build_packing_advice("что еще взять с запасом, не хочу ничего покупать на месте?", prepared_context(), "ru")
        windbreaker = next(item for item in advice["recommendations"] if item["item"] == "Ветровка")
        self.assertEqual(windbreaker["priority"], "must")

    def test_request_phrase_understands_family_scenario(self):
        advice = build_packing_advice("еду с ребенком, что еще взять?", base_context(), "ru")
        items = {item["item"] for item in advice["recommendations"]}
        self.assertIn("Детские влажные салфетки", items)

    def test_answer_groups_recommendations_by_priority(self):
        advice = build_packing_advice("что еще взять?", base_context(), "ru")

        self.assertIn("В первую очередь", advice["answer"])
        self.assertIn("Можно взять", advice["answer"])
        self.assertIn("не обязательные указания", advice["answer"])


class PackingAdvisorIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_ask_travel_ai_returns_local_packing_advice_without_gemini_key(self):
        with patch.dict("os.environ", {"GEMINI_API_KEY": ""}, clear=False):
            result = await ask_travel_ai(
                city="Budapest",
                question="что еще взять?",
                language="ru",
                trip_context=base_context(),
            )

        self.assertIn("Что ещё можно добавить под этот сценарий", result["answer"])
        self.assertTrue(result["packing_recommendations"])
        self.assertEqual(result["plan_proposals"], [])

    async def test_ask_travel_ai_handles_backpack_only_locally_without_gemini_key(self):
        with patch.dict("os.environ", {"GEMINI_API_KEY": ""}, clear=False):
            result = await ask_travel_ai(
                city="Budapest",
                question="я поеду только с рюкзаком",
                language="ru",
                trip_context=base_context(),
            )

        self.assertIn("Что можно не брать", result["answer"])
        self.assertTrue(result["packing_recommendations"])


class DefaultBaggageKindsTests(unittest.TestCase):
    def test_carry_on_trip_uses_only_carry_on(self):
        self.assertEqual(get_default_baggage_kinds({"baggage_format": "carry_on"}), ["carry_on"])

    def test_flexible_trip_defaults_to_suitcase(self):
        self.assertEqual(get_default_baggage_kinds({"baggage_format": "flexible"}), ["suitcase"])

    def test_suitcase_plus_carry_on_creates_both_sections(self):
        self.assertEqual(
            get_default_baggage_kinds({"baggage_format": "suitcase_plus_carry_on"}),
            ["suitcase", "carry_on"],
        )


if __name__ == "__main__":
    unittest.main()
