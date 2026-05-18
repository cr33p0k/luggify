import unittest
from datetime import date
from types import SimpleNamespace

from assistant_plan_service import resolve_requested_trip_day


def checklist(start="2026-05-12", end="2026-05-14"):
    return SimpleNamespace(
        start_date=date.fromisoformat(start),
        end_date=date.fromisoformat(end),
    )


class AssistantPlanServiceTests(unittest.TestCase):
    def test_resolves_today_inside_trip(self):
        result = resolve_requested_trip_day(
            "план на сегодня",
            checklist(),
            today=date(2026, 5, 12),
        )

        self.assertEqual(result.event_date, date(2026, 5, 12))
        self.assertIsNone(result.error)

    def test_resolves_tomorrow_inside_trip(self):
        result = resolve_requested_trip_day(
            "план на завтра",
            checklist(),
            today=date(2026, 5, 12),
        )

        self.assertEqual(result.event_date, date(2026, 5, 13))
        self.assertIsNone(result.error)

    def test_resolves_day_month_inside_trip_year(self):
        result = resolve_requested_trip_day("план на 13.05", checklist())

        self.assertEqual(result.event_date, date(2026, 5, 13))
        self.assertIsNone(result.error)

    def test_resolves_ordinal_day(self):
        result = resolve_requested_trip_day("план на второй день", checklist())

        self.assertEqual(result.event_date, date(2026, 5, 13))
        self.assertIsNone(result.error)

    def test_reports_out_of_range_day(self):
        result = resolve_requested_trip_day("план на 20.05", checklist())

        self.assertIsNone(result.event_date)
        self.assertIn("не входит", result.error)


if __name__ == "__main__":
    unittest.main()
