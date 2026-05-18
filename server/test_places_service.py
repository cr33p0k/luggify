import unittest

from places_service import parse_geoapify_restaurants


class GeoapifyRestaurantParsingTest(unittest.TestCase):
    def test_parses_and_prioritizes_named_restaurants(self):
        payload = {
            "features": [
                {
                    "properties": {
                        "place_id": "weak",
                        "name": "Tiny Snack",
                        "lat": 47.01,
                        "lon": 28.82,
                        "categories": ["catering.fast_food"],
                        "distance": 100,
                    }
                },
                {
                    "properties": {
                        "place_id": "rich",
                        "name": "Local Kitchen",
                        "lat": 47.011,
                        "lon": 28.821,
                        "categories": ["catering.restaurant"],
                        "distance": 260,
                        "cuisine": "moldovan",
                        "website": "https://example.test",
                        "opening_hours": "Mo-Su 10:00-22:00",
                    }
                },
                {
                    "properties": {
                        "place_id": "missing-name",
                        "lat": 47.012,
                        "lon": 28.822,
                        "categories": ["catering.restaurant"],
                    }
                },
            ]
        }

        results = parse_geoapify_restaurants(payload, language="ru", limit=2)

        self.assertEqual([item["name"] for item in results], ["Local Kitchen", "Tiny Snack"])
        self.assertEqual(results[0]["source"], "geoapify")
        self.assertEqual(results[0]["lat"], 47.011)
        self.assertEqual(results[0]["lng"], 28.821)
        self.assertEqual(results[0]["description"], "Молдавская кухня.")
        self.assertNotIn("формат", results[0]["description"])
        self.assertNotIn("от точки", results[0]["description"])
        self.assertNotIn("еда:", results[0]["description"])
        self.assertNotIn("дополнительные данные", results[0]["description"])

    def test_extracts_address_and_localized_map_url(self):
        payload = {
            "features": [
                {
                    "properties": {
                        "place_id": "addressed",
                        "name": "Casa Local",
                        "lat": 47.011,
                        "lon": 28.821,
                        "categories": ["catering.restaurant"],
                        "formatted": "Strada Bucuresti 12, Chisinau",
                        "cuisine": "moldovan;regional",
                    }
                }
            ]
        }

        ru_results = parse_geoapify_restaurants(payload, language="ru", limit=1)
        en_results = parse_geoapify_restaurants(payload, language="en", limit=1)

        self.assertEqual(ru_results[0]["address"], "Strada Bucuresti 12, Chisinau")
        self.assertIn("yandex.ru/maps", ru_results[0]["map_url"])
        self.assertIn("google.com/maps", en_results[0]["map_url"])
        self.assertEqual(ru_results[0]["description"], "Молдавская кухня, локальная кухня.")
        self.assertIn("Casa+Local+Strada+Bucuresti+12", ru_results[0]["map_url"])

    def test_breakfast_filters_fast_food_and_pizza(self):
        payload = {
            "features": [
                {"properties": {"place_id": "pizza", "name": "Pizza Mania", "lat": 47.01, "lon": 28.82, "categories": ["catering.restaurant"], "distance": 100}},
                {"properties": {"place_id": "pub", "name": "Beer Pub", "lat": 47.02, "lon": 28.83, "categories": ["catering.bar"], "distance": 120}},
                {"properties": {"place_id": "cafe", "name": "Bonjour Cafe", "lat": 47.03, "lon": 28.84, "categories": ["catering.cafe"], "distance": 180}},
            ]
        }

        results = parse_geoapify_restaurants(payload, language="ru", limit=5, meal_type="breakfast")

        self.assertEqual([item["name"] for item in results], ["Bonjour Cafe"])


if __name__ == "__main__":
    unittest.main()
