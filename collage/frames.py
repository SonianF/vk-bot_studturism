"""Рамки для фото и гвозди."""

from PIL import Image, ImageDraw, ImageFilter, ImageOps
from collage.text import load_font

def make_photo_with_frame(
    photo: Image.Image,
    cell: int = 320,
    frame_pad: int = 6,
    border: int = 4,
    rotation: float = 0.0,
    caption: str = "",
) -> Image.Image:
    photo = photo.convert("RGB")

    font = load_font(18) if caption else None

    inner_w = cell - 2 * frame_pad
    inner_h = cell - 2 * frame_pad
    photo = ImageOps.contain(photo, (inner_w, inner_h))

    text_gap = 2 if caption else 0
    if caption:
        bbox = ImageDraw.Draw(Image.new("RGBA", (1, 1))).textbbox(
            (0, 0), caption, font=font
        )
        text_h = bbox[3] - bbox[1]
    else:
        text_h = 0

    framed_w = cell
    framed_h = frame_pad + photo.height + text_gap + text_h + frame_pad
    framed = Image.new("RGBA", (framed_w, framed_h), (255, 255, 255, 255))

    px = (framed_w - photo.width) // 2
    py = frame_pad
    framed.paste(photo, (px, py))

    draw = ImageDraw.Draw(framed)
    draw.rectangle(
        [0, 0, framed_w - 1, framed_h - 1],
        outline=(70, 150, 220, 255),
        width=border,
    )

    if caption:
        tx = (framed_w - (bbox[2] - bbox[0])) // 2
        ty = py + photo.height + text_gap - bbox[1]
        draw.text((tx, ty), caption, font=font, fill=(70, 40, 20, 255))

    if rotation != 0.0:
        framed = framed.rotate(
            rotation, resample=Image.BICUBIC,
            expand=True, fillcolor=(0, 0, 0, 0),
        )

    return framed


def draw_pin(canvas: Image.Image, x: int, y: int, r: int = 16) -> None:
    """Рисует гвоздь-кнопку (голубой)."""
    draw = ImageDraw.Draw(canvas, "RGBA")
    draw.ellipse([x - r + 3, y - r + 3, x + r + 3, y + r + 3],
                 fill=(0, 0, 0, 100))
    draw.ellipse([x - r, y - r, x + r, y + r],
                 fill=(60, 140, 220, 255),
                 outline=(255, 255, 255, 255), width=2)
    draw.ellipse([x - r // 2, y - r // 2, x, y],
                 fill=(200, 230, 255, 180))