"""Управление сессиями пользователей."""

import time
from dataclasses import dataclass, field
from threading import Lock

from routes import Route, RoutePoint, get_route


SESSION_TIMEOUT = 3600   # 1 час


@dataclass
class PhotoEntry:
    point_id: str
    content: bytes
    ts: float


@dataclass
class UserSession:
    user_id: int
    route_id: str
    current_index: int = 0
    photos: list[PhotoEntry] = field(default_factory=list)
    visited: set[int] = field(default_factory=set)
    skipped: set[int] = field(default_factory=set)
    started_at: float = field(default_factory=time.time)
    finished: bool = False

    def route(self) -> Route:
        return get_route(self.route_id)

    def current_point(self) -> RoutePoint | None:
        route = self.route()
        if self.current_index >= route.points_count:
            return None
        return route.points[self.current_index]

    def add_photo(self, content: bytes) -> None:
        point = self.current_point()
        if point is None:
            raise RuntimeError("No more points in route")
        self.photos.append(PhotoEntry(point.id, content, time.time()))
        self.visited.add(self.current_index)
        self.current_index += 1

    def skip_point(self) -> None:
        """Пропускает текущую точку."""
        if self.current_point() is None:
            raise RuntimeError("No more points in route")
        self.skipped.add(self.current_index)
        self.current_index += 1

    def is_complete(self) -> bool:
        return self.current_index >= self.route().points_count

    def is_expired(self) -> bool:
        return time.time() - self.started_at > SESSION_TIMEOUT

    def visited_points(self) -> list[RoutePoint]:
        """Точки, для которых есть фото, в порядке маршрута."""
        route = self.route()
        return [route.points[i] for i in sorted(self.visited)]

    def visited_photos(self) -> list[PhotoEntry]:
        """Фото в порядке индексов посещённых точек."""
        by_id = {e.point_id: e for e in self.photos}
        route = self.route()
        return [by_id[route.points[i].id] for i in sorted(self.visited)]

class SessionStore:
    """Потокобезопасное хранилище сессий."""

    def __init__(self):
        self._sessions: dict[int, UserSession] = {}
        self._lock = Lock()

    def get(self, user_id: int) -> UserSession | None:
        with self._lock:
            session = self._sessions.get(user_id)
            if session and session.is_expired():
                del self._sessions[user_id]
                return None
            return session

    def start(self, user_id: int, route_id: str) -> UserSession:
        with self._lock:
            session = UserSession(user_id=user_id, route_id=route_id)
            self._sessions[user_id] = session
            return session

    def remove(self, user_id: int) -> None:
        with self._lock:
            self._sessions.pop(user_id, None)

    def cleanup_expired(self) -> int:
        """Удаляет просроченные сессии. Возвращает число удалённых."""
        with self._lock:
            expired = [uid for uid, s in self._sessions.items() if s.is_expired()]
            for uid in expired:
                del self._sessions[uid]
            return len(expired)


sessions = SessionStore()