"""Текст: заголовок, футер, шрифты."""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from routes import RoutePoint


FONT_PATH = Path("assets/fonts/kazakh.ttf")


def load_font(size: int) -> ImageFont.FreeTypeFont:
    """Загружает национальный шрифт с фолбэком."""
    try:
        return ImageFont.truetype(str(FONT_PATH), size)
    except OSError:
        for fb in ["arial.ttf", "DejaVuSans.ttf", "Georgia.ttf"]:
            try:
                return ImageFont.truetype(fb, size)
            except OSError:
                continue
        return ImageFont.load_default()


def draw_header(canvas: Image.Image, title: str) -> None:
    """Рисует заголовок."""
    draw = ImageDraw.Draw(canvas)
    font = load_font(88)

    bbox = draw.textbbox((0, 0), title, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (canvas.width - tw) // 2
    y = 40

    draw.text((x + 4, y + 4), title, font=font, fill=(0, 0, 0, 80))
    draw.text((x, y), title, font=font, fill=(60, 30, 10))

    line_y = y + th + 30
    draw.line(
        [(canvas.width // 4, line_y), (3 * canvas.width // 4, line_y)],
        fill=(180, 120, 60), width=4,
    )


def draw_footer(
    canvas: Image.Image,
    points: list[RoutePoint],
    offset_y: int,
) -> None:
    """Подписи локаций под картой."""
    draw = ImageDraw.Draw(canvas)
    font_h = load_font(28)
    font_p = load_font(22)

    x = 80
    y = offset_y

    for i, p in enumerate(points, start=1):
        draw.text((x, y), f"{i}. {p.name}", font=font_h, fill=(80, 40, 20))
        y += 36

        max_w = canvas.width - 2 * x - 40
        words = p.caption.split()
        line = ""
        for w in words:
            test = f"{line} {w}".strip()
            bbox = draw.textbbox((0, 0), test, font=font_p)
            if bbox[2] - bbox[0] > max_w:
                draw.text((x + 30, y), line, font=font_p, fill=(60, 30, 10))
                y += 28
                line = w
            else:
                line = test
        if line:
            draw.text((x + 30, y), line, font=font_p, fill=(60, 30, 10))
            y += 28

        y += 12