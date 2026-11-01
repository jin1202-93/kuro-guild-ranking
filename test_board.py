import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from PIL import Image, ImageFont

from board import (
    format_damage,
    parse_damage_message,
    render_board,
    sort_members,
)


class RankingBoardTests(unittest.TestCase):
    def test_numeric_only_damage_input(self):
        self.assertEqual(parse_damage_message("2600"), 2600)
        self.assertEqual(parse_damage_message(" 2600 "), 2600)
        self.assertIsNone(parse_damage_message("추딜 2600"))
        self.assertIsNone(parse_damage_message("2,600"))
        self.assertIsNone(parse_damage_message("-1"))
        self.assertIsNone(parse_damage_message("1000000000000000"))

    def test_damage_is_displayed_with_comma_and_unit(self):
        self.assertEqual(format_damage(2600), "2,600조")

    def test_members_are_sorted_by_damage_descending(self):
        members = [
            {"nickname": "가", "damage_jo": 100},
            {"nickname": "나", "damage_jo": 350},
            {"nickname": "다", "damage_jo": 250},
        ]
        self.assertEqual(
            [member["nickname"] for member in sort_members(members)],
            ["나", "다", "가"],
        )

    def test_board_renders_a_png_with_empty_and_populated_data(self):
        test_font = ImageFont.load_default()
        fixed_time = datetime(2026, 11, 2, tzinfo=timezone.utc)
        with patch("board._load_font", return_value=test_font):
            for members in (
                [],
                [{"nickname": "테스트", "level": 2288, "damage_jo": 2600}],
            ):
                image_data = render_board(members, now=fixed_time)
                with Image.open(image_data) as image:
                    self.assertEqual(image.format, "PNG")
                    self.assertEqual(image.size, (900, 1866))


if __name__ == "__main__":
    unittest.main()