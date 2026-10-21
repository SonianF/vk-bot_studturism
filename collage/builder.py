"""Сборка маршрутного коллажа."""

from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from collage.frames import make_photo_with_frame, draw_pin
from routes import Route

import math

CANVAS_W = 1600
HEADER_H = 180
MAP_H = 700
PHOTO_COLS = 3
PHOTO_CELL = 520
PHOTO_GAP = 24
PHOTO_CAPTION_H = 60
PHOTOS_TOP = 800
CAPTION_H = 30
MARGIN_X = 40

ROTATIONS = [-3, 2, -2, 3, -4, 1, 2]

@dataclass
class CollageInput:
    """Входные данные для коллажа."""
    route: Route
    photos: list[Image.Image]

def _rotated_size(w: float, h: float, angle_deg: float) -> tuple[float, float]:
    a = math.radians(abs(angle_deg))
    W = w * math.cos(a) + h * math.sin(a)
    H = w * math.sin(a) + h * math.cos(a)
    return W, H


def _max_rotated_width(cell: int, caption_h: int) -> float:
    """Максимальная ширина рамки после поворота среди всех углов."""
    w, h = cell, cell + caption_h
    return max(_rotated_size(w, h, a)[0] for a in ROTATIONS)


def _fit_cell_to_width(
    bg_width: int,
    cols: int,
    caption_h: int,
    gap: int,
    margin: int,
    start_cell: int = 320,
) -> int:
    """Подбирает cell так, чтобы cols рамок влезли в bg_width."""
    available = bg_width - 2 * margin - gap * (cols - 1)
    if available <= 0:
        return 1

    k1 = max(
        math.cos(math.radians(abs(a))) + math.sin(math.radians(abs(a)))
        for a in ROTATIONS
    )
    k2 = max(
        caption_h * math.sin(math.radians(abs(a)))
        for a in ROTATIONS
    )

    max_cell = (available / cols - k2) / k1
    return max(1, min(start_cell, int(max_cell)))


def make_route_collage(data: CollageInput) -> Image.Image:
    route = data.route
    n = len(data.photos)

    if n != route.points_count:
        raise ValueError(f"Expected {route.points_count} photos, got {n}")

    bg_path = Path("assets/routes/almaty_map.png")
    bg = Image.open(bg_path).convert("RGB")
    canvas_w, canvas_h = bg.width, bg.height

    cell = _fit_cell_to_width(
        bg_width=canvas_w,
        cols=PHOTO_COLS,
        caption_h=CAPTION_H,
        gap=PHOTO_GAP,
        margin=MARGIN_X,
        start_cell=PHOTO_CELL,
    )

    canvas = bg.convert("RGBA")

    rows = (n + PHOTO_COLS - 1) // PHOTO_COLS
    y = PHOTOS_TOP

    for row in range(rows):
        row_items = list(enumerate(zip(data.photos, route.points)))[
            row * PHOTO_COLS:(row + 1) * PHOTO_COLS
        ]

        framed_items = []
        for i, (photo, point) in row_items:
            rotation = ROTATIONS[i % len(ROTATIONS)]
            framed = make_photo_with_frame(
                photo,
                cell=cell,
                frame_pad=6,
                caption=point.short,
            )

            if rotation != 0.0:
                framed = framed.rotate(
                    rotation, resample=Image.BICUBIC,
                    expand=True, fillcolor=(0, 0, 0, 0),
                )
            framed_items.append(framed)

        row_w = sum(f.width for f in framed_items) \
                + PHOTO_GAP * (len(framed_items) - 1)
        row_h = max(f.height for f in framed_items)

        if row_w > canvas_w - 2 * MARGIN_X:
            scale = (canvas_w - 2 * MARGIN_X) / row_w
            framed_items = [
                f.resize((int(f.width * scale), int(f.height * scale)),
                         Image.LANCZOS)
                for f in framed_items
            ]
            row_w = sum(f.width for f in framed_items) \
                    + PHOTO_GAP * (len(framed_items) - 1)
            row_h = max(f.height for f in framed_items)

        x = (canvas_w - row_w) // 2
        for framed in framed_items:
            canvas.alpha_composite(framed, (x, y))
            draw_pin(canvas, x + framed.width // 2, y + 20)
            x += framed.width + PHOTO_GAP

        y += row_h + PHOTO_GAP

    if y > canvas_h:
        canvas = canvas.crop((0, 0, canvas_w, canvas_h))


    if n <= 3:
        bottom = y + 40
        bottom = min(bottom, canvas.height)
        canvas = canvas.crop((0, 0, canvas.width, bottom))

    return canvas.convert("RGB")