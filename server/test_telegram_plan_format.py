import unittest
from datetime import date
from types import SimpleNamespace

from assistant_plan_service import format_telegram_day_plan


class TelegramPlanFormatTests(unittest.TestCase):
    def test_formats_plan_by_day_parts(self):
        checklist = SimpleNamespace(city="Будапешт")
        text = format_telegram_day_plan(
            checklist,
            [
                {
                    "event_date": "2026-05-12",
                    "time": "19:00",
                    "day_part": "evening",
                    "title": "Ужин",
                    "description": "Место можно выбрать позже.",
                    "event_type": "food",
                },
                {
                    "event_date": "2026-05-12",
                    "time": "10:00",
                    "day_part": "morning",
                    "title": "Прогулка у Дуная",
                    "address": "Danube Promenade",
                    "event_type": "walk",
                },
            ],
            date(2026, 5, 12),
        )

        self.assertIn("План дня: Будапешт", text)
        self.assertIn("Утро", text)
        self.assertIn("Вечер", text)
        self.assertIn("Прогулка у Дуная", text)
        self.assertIn("Можно сохранить", text)


if __name__ == "__main__":
    unittest.main()
