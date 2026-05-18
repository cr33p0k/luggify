import sys
import types
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.modules.setdefault("httpx", types.SimpleNamespace())

from packing_logic import build_packing_recommendations, get_default_baggage_kinds
from translations import get_item


class PackingLogicTests(unittest.TestCase):
    def test_default_city_break_list_is_more_focused(self):
        bundle = build_packing_recommendations(
            language="ru",
            trip_days=4,
            avg_temp=22,
            min_temp=16,
            max_temp=27,
            conditions={"Ясно"},
            humidities=[72],
            uv_indices=[6],
            wind_speeds=[12],
            country="HU",
            transport="plane",
            gender="unspecified",
            traveling_with_pet=False,
            has_allergies=False,
            traveling_with_children=False,
            trip_profile={
                "trip_type": "city_break",
                "trip_activities": ["city_break"],
                "baggage_format": "flexible",
                "packing_style": "balanced",
            },
        )
        items = bundle["items"]

        self.assertIn(get_item("passport", "ru"), items)
        self.assertIn(get_item("phone", "ru"), items)
        self.assertIn(get_item("charger", "ru"), items)
        self.assertNotIn(get_item("liquids_bag", "ru"), items)
        self.assertNotIn(get_item("neck_pillow", "ru"), items)
        self.assertNotIn(get_item("earplugs", "ru"), items)
        self.assertNotIn(get_item("eye_mask", "ru"), items)
        self.assertNotIn(get_item("water_bottle", "ru"), items)
        self.assertNotIn(get_item("packing_cubes", "ru"), items)
        self.assertNotIn(get_item("laundry_bag", "ru"), items)
        self.assertNotIn(get_item("dry_shampoo", "ru"), items)

    def test_plane_carry_on_trip_adds_liquids_bag(self):
        bundle = build_packing_recommendations(
            language="ru",
            trip_days=3,
            avg_temp=20,
            min_temp=14,
            max_temp=22,
            conditions={"Облачно"},
            humidities=[],
            uv_indices=[],
            wind_speeds=[],
            country="HU",
            transport="plane",
            gender="unspecified",
            traveling_with_pet=False,
            has_allergies=False,
            traveling_with_children=False,
            trip_profile={
                "trip_type": "city_break",
                "trip_activities": ["city_break"],
                "baggage_format": "carry_on",
                "packing_style": "light",
            },
        )

        self.assertIn(get_item("liquids_bag", "ru"), bundle["items"])

    def test_default_baggage_kinds_follow_baggage_format(self):
        self.assertEqual(get_default_baggage_kinds({"baggage_format": "carry_on"}), ["carry_on"])
        self.assertEqual(get_default_baggage_kinds({"baggage_format": "flexible"}), ["suitcase"])
        self.assertEqual(get_default_baggage_kinds({"baggage_format": "suitcase_plus_carry_on"}), ["suitcase", "carry_on"])


if __name__ == "__main__":
    unittest.main()
