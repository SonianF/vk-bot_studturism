"""Утилиты для работы с VK API."""

from typing import Any


def get_largest_photo_url(attachments: list[dict[str, Any]]) -> str | None:
    """Возвращает URL самого большого фото из вложений сообщения ВК.

    Перебирает все вложения типа ``photo``, для каждого выбирает
    размер с максимальной площадью (width * height) и возвращает
    его URL.

    Args:
        attachments: Список вложений из ``message["attachments"]``.

    Returns:
        URL самого большого фото или ``None``, если фото нет.
    """
    best_url: str | None = None
    best_area: int = 0

    for attach in attachments:
        if attach.get("type") != "photo":
            continue

        photo = attach.get("photo") or {}
        sizes = photo.get("sizes") or []

        for size in sizes:
            area = size.get("width", 0) * size.get("height", 0)
            if area > best_area:
                best_area = area
                best_url = size.get("url")

    return best_url


def get_all_photo_urls(attachments: list[dict[str, Any]]) -> list[str]:
    """Возвращает URL всех фото (по одному самому большому на каждое).

    Полезно, если пользователь прислал несколько фото одним сообщением.

    Args:
        attachments: Список вложений из ``message["attachments"]``.

    Returns:
        Список URL (по одному на каждое фото).
    """
    urls = []
    for attach in attachments:
        if attach.get("type") != "photo":
            continue

        photo = attach.get("photo") or {}
        sizes = photo.get("sizes") or []
        if not sizes:
            continue

        largest = max(sizes, key=lambda s: s.get("width", 0) * s.get("height", 0))
        url = largest.get("url")
        if url:
            urls.append(url)

    return urls