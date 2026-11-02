import os
import re
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


MAX_DAMAGE = 999_999_999_999_999
MAX_LEVEL = 9999
_DAMAGE_MESSAGE = re.compile(r"추뎀\s+([0-9]{1,15})(?:조)?\Z")
_LEVEL_MESSAGE = re.compile(r"레벨\s+([0-9]{1,4})\Z")
ROW_COUNT = 30
TEMPLATE_PATH = Path(__file__).with_name("샘플.png")
ROW_CENTERS = (
    322, 372, 422, 470, 514, 558, 602,
    644, 683, 722, 761, 800, 839, 877,
    915, 953, 991, 1029, 1065, 1101, 1138, 1174, 1209, 1243, 1277, 1310,
    1345, 1382, 1419, 1456,
)
TEXT_BOXES = ((282, 478), (576, 700), (810, 946))
TEXT_CENTERS = (380, 638, 878)
TEXT_WIDTHS = (178, 112, 124)
HEADER_LABELS = (
    ("순위", (156, 268), (136, 250, 178, 286)),
    ("추뎀", (886, 268), (863, 250, 910, 286)),
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
    match = _DAMAGE_MESSAGE.fullmatch(content.strip())
    if not match:
        return None
    damage = int(match.group(1))
    return damage if damage <= MAX_DAMAGE else None


def parse_level_message(content):
    match = _LEVEL_MESSAGE.fullmatch(content.strip())
    if not match:
        return None
    level = int(match.group(1))
    return level if level <= MAX_LEVEL else None


def format_damage(damage):
    return f"{damage:,}조"


def sort_members(members):
    return sorted(
        members,
        key=lambda member: int(member.get("damage_jo") or 0),
        reverse=True,
    )


def _load_font(size, weight=600):
    for path in FONT_CANDIDATES:
        if path and os.path.isfile(path):
            font = ImageFont.truetype(path, size)
            if Path(path).name == "NotoSansKR-Variable.ttf":
                font.set_variation_by_axes([weight])
            return font
    raise RuntimeError(
        "한글 폰트를 찾을 수 없습니다. NotoSansKR-Variable.ttf 파일을 확인하세요."
    )


def _rank_style(rank):
    if rank <= 7:
        return (255, 225, 160)
    if rank <= 14:
        return (247, 248, 255)
    if rank <= 26:
        return (240, 250, 243)
    return (43, 45, 93)


def _draw_fitted_text(
    draw,
    value,
    center,
    color,
    max_width,
    font_size=19,
    weight=600,
):
    font = _load_font(font_size, weight)
    while font_size > 11 and draw.textbbox((0, 0), value, font=font)[2] > max_width:
        font_size -= 1
        font = _load_font(font_size, weight)
    draw.text(center, value, font=font, fill=color, anchor="mm")


def _draw_centered(draw, value, center, color, font_size, weight=600):
    draw.text(
        center,
        value,
        font=_load_font(font_size, weight),
        fill=color,
        anchor="mm",
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


def render_board(members, now=None):
    if not TEMPLATE_PATH.is_file():
        raise FileNotFoundError(f"랭킹 샘플 이미지를 찾을 수 없습니다: {TEMPLATE_PATH}")
    ranked = sort_members(members)[:ROW_COUNT]
    timestamp = now or datetime.now(timezone(timedelta(hours=9)))
    with Image.open(TEMPLATE_PATH) as template:
        image = template.convert("RGB")
    draw = ImageDraw.Draw(image)

    _restore_text_strip(image, 875, 199, 978, 231)
    draw.text(
        (926, 216),
        timestamp.strftime("%y.%m.%d"),
        font=_load_font(12, 650),
        fill=(245, 239, 255),
        anchor="mm",
    )

    for label, center, (left, top, right, bottom) in HEADER_LABELS:
        _restore_text_strip(image, left, top, right, bottom)
        draw.text(
            center,
            label,
            font=_load_font(17, 700),
            fill=(245, 239, 255),
            anchor="mm",
        )

    for index in range(ROW_COUNT):
        row_center = ROW_CENTERS[index]
        for left, right in TEXT_BOXES:
            _restore_text_strip(image, left, row_center - 15, right, row_center + 15)
        if index >= len(ranked):
            continue

        member = ranked[index]
        values = (
            str(member["nickname"]),
            f"{int(member.get('level') or 0):,}",
            format_damage(int(member.get("damage_jo") or 0)),
        )
        text_color = _rank_style(index + 1)
        for column, value in enumerate(values):
            _draw_fitted_text(
                draw,
                value,
                (TEXT_CENTERS[column], row_center),
                text_color,
                TEXT_WIDTHS[column],
                font_size=22,
                weight=700,
            )

    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    output.seek(0)
    return output