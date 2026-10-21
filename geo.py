"""Преобразование географических координат в пиксели карты."""

from PIL import Image


def geo_to_pixel(
    lat: float,
    lon: float,
    bounds: tuple[float, float, float, float],
    map_size: tuple[int, int],
    padding: int = 40,
) -> tuple[int, int]:
    """Переводит (lat, lon) в (x, y) на карте.

    Args:
        lat: Широта.
        lon: Долгота.
        bounds: (lat_min, lat_max, lon_min, lon_max) — границы карты.
        map_size: (width, height) карты в пикселях.
        padding: Отступ от краёв, чтобы точки не «прилипали».

    Returns:
        (x, y) — координаты на карте.
    """
    lat_min, lat_max, lon_min, lon_max = bounds
    w, h = map_size

    x = (lon - lon_min) / (lon_max - lon_min) * (w - 2 * padding) + padding
    y = (lat_max - lat) / (lat_max - lat_min) * (h - 2 * padding) + padding

    return int(x), int(y)


def fit_map_to_box(
    map_image: Image.Image,
    box_w: int,
    box_h: int,
) -> tuple[Image.Image, tuple[int, int]]:
    """Вписывает карту в прямоугольник, сохраняя пропорции.

    Returns:
        (resized_map, (offset_x, offset_y)) — карта и её смещение
        относительно верхнего левого угла box.
    """
    ratio = min(box_w / map_image.width, box_h / map_image.height)
    new_w = int(map_image.width * ratio)
    new_h = int(map_image.height * ratio)

    resized = map_image.resize((new_w, new_h), Image.LANCZOS)
    offset = ((box_w - new_w) // 2, (box_h - new_h) // 2)

    return resized, offset