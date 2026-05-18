import unittest

from trip_context import _build_section


class TripContextTests(unittest.TestCase):
    def test_build_section_matches_categories_case_insensitively(self):
        section = _build_section(
            kind="shared",
            label="Общий список",
            items=["Паспорт", "Зарядка"],
            checked_items=[],
            removed_items=[],
            item_quantities={"паспорт": 1, "зарядка": 1},
            packed_quantities={},
            item_categories={"паспорт": "Документы", "зарядка": "Техника"},
        )

        items_by_name = {item["name"]: item for item in section["items"]}
        self.assertEqual(items_by_name["Паспорт"]["category"], "Документы")
        self.assertEqual(items_by_name["Зарядка"]["category"], "Техника")


if __name__ == "__main__":
    unittest.main()
