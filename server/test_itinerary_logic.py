import unittest

from itinerary_logic import estimate_travel_buffer_minutes, optimize_itinerary_plan_items


class ItineraryLogicTests(unittest.TestCase):
    def test_plan_items_are_ordered_by_nearby_stops_inside_day_part(self):
        optimized = optimize_itinerary_plan_items([
            {
                "event_date": "2026-05-12",
                "day_part": "morning",
                "title": "Start",
                "lat": 47.0,
                "lng": 28.0,
            },
            {
                "event_date": "2026-05-12",
                "day_part": "morning",
                "title": "Far stop",
                "lat": 47.08,
                "lng": 28.08,
            },
            {
                "event_date": "2026-05-12",
                "day_part": "morning",
                "title": "Nearby stop",
                "lat": 47.01,
                "lng": 28.01,
            },
        ])

        self.assertEqual([item["title"] for item in optimized], ["Start", "Nearby stop", "Far stop"])
        self.assertGreater(optimized[2]["travel_buffer_minutes"], optimized[1]["travel_buffer_minutes"])
        self.assertLess(optimized[0]["time"], optimized[1]["time"])
        self.assertLess(optimized[1]["time"], optimized[2]["time"])

    def test_far_places_get_larger_buffers(self):
        self.assertLess(estimate_travel_buffer_minutes(0.5), estimate_travel_buffer_minutes(8.0))

    def test_day_parts_stay_in_day_flow(self):
        optimized = optimize_itinerary_plan_items([
            {
                "event_date": "2026-05-12",
                "day_part": "evening",
                "title": "Evening viewpoint",
                "lat": 47.0,
                "lng": 28.0,
            },
            {
                "event_date": "2026-05-12",
                "day_part": "morning",
                "title": "Museum",
                "lat": 47.001,
                "lng": 28.001,
            },
        ])

        self.assertEqual([item["title"] for item in optimized], ["Museum", "Evening viewpoint"])
        self.assertGreaterEqual(optimized[1]["time"], "18:00")

    def test_meal_times_stay_inside_flexible_windows_when_ai_sends_bad_time(self):
        optimized = optimize_itinerary_plan_items([
            {
                "event_date": "2026-05-12",
                "time": "19:00",
                "day_part": "evening",
                "title": "Обед",
                "event_type": "food",
            },
            {
                "event_date": "2026-05-12",
                "time": "20:15",
                "day_part": "evening",
                "title": "Ужин",
                "event_type": "food",
            },
        ])

        self.assertEqual([item["title"] for item in optimized], ["Обед"])
        self.assertGreaterEqual(optimized[0]["time"], "12:00")
        self.assertLess(optimized[0]["time"], "17:00")

    def test_lunch_follows_nearby_morning_route_instead_of_fixed_time(self):
        optimized = optimize_itinerary_plan_items([
            {
                "event_date": "2026-05-12",
                "time": "11:30",
                "day_part": "morning",
                "title": "Поздний музей",
                "lat": 47.000,
                "lng": 28.000,
                "event_type": "museum",
                "duration_minutes": 90,
            },
            {
                "event_date": "2026-05-12",
                "time": "19:00",
                "day_part": "evening",
                "title": "Обед",
                "lat": 47.002,
                "lng": 28.002,
                "event_type": "food",
            },
        ])

        lunch = optimized[1]
        self.assertEqual(lunch["title"], "Обед")
        self.assertGreater(lunch["time"], "13:00")
        self.assertLess(lunch["time"], "17:00")

    def test_meals_are_separated_by_activities_when_available(self):
        optimized = optimize_itinerary_plan_items([
            {
                "event_date": "2026-05-12",
                "day_part": "morning",
                "title": "Завтрак",
                "event_type": "food",
            },
            {
                "event_date": "2026-05-12",
                "day_part": "day",
                "title": "Обед",
                "event_type": "food",
            },
            {
                "event_date": "2026-05-12",
                "day_part": "evening",
                "title": "Ужин",
                "event_type": "food",
            },
            {
                "event_date": "2026-05-12",
                "day_part": "morning",
                "title": "Утренняя прогулка",
                "event_type": "walk",
            },
            {
                "event_date": "2026-05-12",
                "day_part": "day",
                "title": "Музей",
                "event_type": "museum",
            },
        ])

        titles = [item["title"] for item in optimized]
        self.assertIn("Утренняя прогулка", titles[titles.index("Завтрак") + 1:titles.index("Обед")])
        self.assertIn("Музей", titles[titles.index("Обед") + 1:titles.index("Ужин")])

    def test_extra_meal_is_dropped_when_no_activity_can_separate_it(self):
        optimized = optimize_itinerary_plan_items([
            {
                "event_date": "2026-05-12",
                "day_part": "morning",
                "title": "Завтрак",
                "event_type": "food",
            },
            {
                "event_date": "2026-05-12",
                "day_part": "day",
                "title": "Обед",
                "event_type": "food",
            },
        ])

        self.assertEqual([item["title"] for item in optimized], ["Завтрак"])

    def test_isolated_far_sight_is_removed_from_generated_route(self):
        optimized = optimize_itinerary_plan_items([
            {
                "event_date": "2026-05-12",
                "day_part": "morning",
                "title": "Central 1",
                "lat": 47.000,
                "lng": 28.000,
                "event_type": "sight",
            },
            {
                "event_date": "2026-05-12",
                "day_part": "day",
                "title": "Central 2",
                "lat": 47.004,
                "lng": 28.004,
                "event_type": "sight",
            },
            {
                "event_date": "2026-05-12",
                "day_part": "day",
                "title": "Central 3",
                "lat": 47.008,
                "lng": 28.008,
                "event_type": "museum",
            },
            {
                "event_date": "2026-05-12",
                "day_part": "evening",
                "title": "Other end of town",
                "lat": 47.200,
                "lng": 28.200,
                "event_type": "sight",
            },
        ])

        self.assertNotIn("Other end of town", [item["title"] for item in optimized])
        self.assertEqual(len(optimized), 3)


if __name__ == "__main__":
    unittest.main()
