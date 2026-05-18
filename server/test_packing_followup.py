import unittest
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from packing_followup import (
    build_remaining_packing_context,
    build_packing_command_context,
    extract_packing_followup,
    format_packing_apply_message,
)


class PackingFollowupTests(unittest.TestCase):
    def setUp(self):
        self.recommendations = [
            {
                "item": "Дождевик",
                "priority": "must",
                "reason": "В день прилёта дождь.",
                "reason_tags": ["weather"],
                "suggested_action": "add",
                "target_section": "Ручная кладь",
            },
            {
                "item": "SPF 50",
                "priority": "nice",
                "reason": "Высокий UV.",
                "reason_tags": ["weather"],
                "suggested_action": "add",
                "target_section": None,
            },
        ]
        self.context = build_packing_command_context(self.recommendations)

    def test_builds_context_with_indexes(self):
        self.assertEqual(self.context["type"], "packing_recommendations")
        self.assertEqual(self.context["items"][0]["index"], 1)
        self.assertEqual(self.context["items"][0]["item"], "Дождевик")

    def test_selects_all_recommendations(self):
        result = extract_packing_followup("примени всё", self.context, "ru")
        self.assertTrue(result["recognized_action_request"])
        self.assertEqual([item["item"] for item in result["recommendations"]], ["Дождевик", "SPF 50"])
        self.assertTrue(result["clear_context"])

    def test_selects_by_ordinal_and_item_name(self):
        first = extract_packing_followup("добавь первое", self.context, "ru")
        named = extract_packing_followup("добавь дождевик и SPF", self.context, "ru")
        self.assertEqual([item["item"] for item in first["recommendations"]], ["Дождевик"])
        self.assertEqual([item["item"] for item in named["recommendations"]], ["Дождевик", "SPF 50"])

    def test_skip_clears_context_without_actions(self):
        result = extract_packing_followup("не надо", self.context, "ru")
        self.assertTrue(result["recognized_action_request"])
        self.assertEqual(result["recommendations"], [])
        self.assertTrue(result["clear_context"])

    def test_remaining_context_keeps_unselected_items(self):
        selected = extract_packing_followup("добавь первое", self.context, "ru")["recommendations"]
        remaining = build_remaining_packing_context(self.context, selected)
        self.assertEqual([item["item"] for item in remaining["items"]], ["SPF 50"])

    def test_formats_apply_message(self):
        result = format_packing_apply_message(
            {"actions": [{"type": "add", "items": ["Дождевик"]}], "skipped": []},
            [self.recommendations[0]],
            "ru",
        )
        self.assertIn("Готово", result)
        self.assertIn("Дождевик", result)


if __name__ == "__main__":
    unittest.main()
