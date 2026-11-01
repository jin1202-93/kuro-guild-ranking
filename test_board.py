import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from PIL import Image, ImageFont

from board import (
    format_damage,
    parse_damage_message,
    parse_level_message,
    render_board,
    sort_members,
)


class RankingBoardTests(unittest.TestCase):
    def test_damage_input_requires_keyword_and_value(self):
        self.assertEqual(parse_damage_message("추뎀 2600"), 2600)
        self.assertEqual(parse_damage_message(" 추뎀   2600 "), 2600)
        self.assertIsNone(parse_damage_message("2600"))
        self.assertIsNone(parse_damage_message("추뎀"))
        self.assertIsNone(parse_damage_message("추딜 2600"))
        self.assertIsNone(parse_damage_message("추뎀 2,600"))
        self.assertIsNone(parse_damage_message("추뎀 -1"))
        self.assertIsNone(parse_damage_message("추뎀 1000000000000000"))

    def test_damage_is_displayed_with_comma_and_unit(self):
        self.assertEqual(format_damage(2600), "2,600조")

    def test_level_message_requires_exact_keyword_and_valid_level(self):
        self.assertEqual(parse_level_message("레벨 200"), 200)
        self.assertEqual(parse_level_message(" 레벨   9999 "), 9999)
        self.assertEqual(parse_level_message("레벨 10000"), None)
        self.assertEqual(parse_level_message("레벨 -1"), None)
        self.assertEqual(parse_level_message("레벨200"), None)
        self.assertEqual(parse_level_message("레벨 200 추뎀"), None)

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
                    self.assertEqual(image.size, (1024, 1536))

    def test_board_replaces_header_labels_in_template(self):
        test_font = ImageFont.load_default()
        with patch("board._load_font", return_value=test_font):
            image_data = render_board([])
        with Image.open("샘플.png") as template, Image.open(image_data) as result:
            for box in ((136, 250, 178, 286), (863, 250, 910, 286)):
                self.assertNotEqual(
                    template.crop(box).tobytes(), result.crop(box).tobytes()
                )


if __name__ == "__main__":
    unittest.main()