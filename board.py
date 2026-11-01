import os
import re
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


MAX_DAMAGE = 999_999_999_999_999
_DAMAGE_MESSAGE = re.compile(r"[0-9]{1,15}\Z")
TEMPLATE_PATH = Path(__file__).with_name("damage-board.png")
ROW_TOP = 208
ROW_HEIGHT = 54
ROW_COUNT = 30
ROW_TEXT_BOXES = (
    (60, 131),
    (165, 433),
    (459, 590),
    (615, 849),
)
FONT_CANDIDATES = (
    os.environ.get("RANKING_FONT_PATH", ""),
    str(Path(__file__).with_name("NotoSansKR-Variable.ttf")),
    r"C:\Windows\Fonts\malgunbd.ttf",
    r"C:\Windows\Fonts\malgun.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
)


def parse_damage_message(content):
    value = content.strip()
    if not _DAMAGE_MESSAGE.fullmatch(value):
        return None
    damage = int(value)
    return damage if damage <= MAX_DAMAGE else None


def format_damage(damage):
    return f"{damage:,}조"


def sort_members(members):
    return sorted(
        members,
        key=lambda member: int(member.get("damage_jo") or 0),
        reverse=True,
    )


def _load_font(size):
    for path in FONT_CANDIDATES:
        if path and os.path.isfile(path):
            font = ImageFont.truetype(path, size)
            if Path(path).name == "NotoSansKR-Variable.ttf":
                font.set_variation_by_axes([700])
            return font
    raise RuntimeError(
                "한글 폰트를 찾을 수 없습니다. NotoSansKR-Variable.ttf 파일을 확인하세요."
    )


def _restore_text_strip(image, left, top, right, bottom):
    pixels = image.load()
    for y in range(top, bottom):
        left_color = pixels[left - 1, y]
        right_color = pixels[right, y]
        span = right - left + 1
        for x in range(left, right):
            ratio = (x - left + 1) / span
            pixels[x, y] = tuple(
                round(start + (end - start) * ratio)
                for start, end in zip(left_color, right_color)
            )


def _row_text_color(rank, column):
    if rank <= 7:
        return (255, 235, 185)
    if rank <= 14:
        return (213, 240, 251)
    if rank <= 26:
        return (220, 247, 231)
    return (132, 91, 174) if column == 3 else (40, 42, 51)


def _draw_fitted_text(draw, value, center, color, max_width, font_size=19):
    font = _load_font(font_size)
    while font_size > 11 and draw.textbbox((0, 0), value, font=font)[2] > max_width:
        font_size -= 1
        font = _load_font(font_size)
    draw.text(center, value, font=font, fill=color, anchor="mm")


def render_board(members, now=None):
    if not TEMPLATE_PATH.is_file():
        raise FileNotFoundError(f"랭킹 배경 이미지를 찾을 수 없습니다: {TEMPLATE_PATH}")
    ranked = sort_members(members)[:ROW_COUNT]
    with Image.open(TEMPLATE_PATH) as template:
        image = template.convert("RGB")

    timestamp = now or datetime.now(timezone(timedelta(hours=9)))
    draw = ImageDraw.Draw(image)

    _restore_text_strip(image, 780, 111, 858, 134)
    _draw_fitted_text(
        draw,
        timestamp.strftime("%y.%m.%d"),
        (819, 123),
        (179, 171, 191),
        max_width=75,
        font_size=11,
    )

    for index in range(ROW_COUNT):
        row_center = ROW_TOP + index * ROW_HEIGHT + ROW_HEIGHT // 2
        for left, right in ROW_TEXT_BOXES:
            _restore_text_strip(image, left, row_center - 15, right, row_center + 15)

        if index >= len(ranked):
            continue

        member = ranked[index]
        values = (
            str(index + 1),
            str(member["nickname"]),
            f"{int(member.get('level') or 0):,}",
            format_damage(int(member.get("damage_jo") or 0)),
        )
        centers = (95, 299, 524, 733)
        widths = (67, 250, 115, 218)
        for column, value in enumerate(values):
            _draw_fitted_text(
                draw,
                value,
                (centers[column], row_center),
                _row_text_color(index + 1, column),
                widths[column],
            )

    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    output.seek(0)
    return output