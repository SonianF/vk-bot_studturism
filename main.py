import os
import io
import logging
import threading
import time

import requests
from dotenv import load_dotenv
from PIL import Image
from vk_api import VkApi
from vk_api.upload import VkUpload
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.utils import get_random_id

from countries import COUNTRIES, ID_TO_COUNTRY
from include_db import get_user, update_user, reset_user
from session import sessions, UserSession
from vk_utils import get_largest_photo_url
from collage.builder import make_route_collage, CollageInput
from routes import get_route


load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)

GROUP_TOKEN = os.environ["GROUP_TOKEN"]
GROUP_ID = int(os.environ["GROUP_ID"])

vk_session = VkApi(token=GROUP_TOKEN)
vk = vk_session.get_api()
longpoll = VkBotLongPoll(vk_session, GROUP_ID)
upload = VkUpload(vk_session)


_photo_cache: dict[str, str] = {}


def upload_photo_from_file(path: str) -> str:
    """Загружает фото из файла и возвращает attachment-строку."""
    import os

    if not os.path.exists(path):
        raise FileNotFoundError(f"Photo not found: {path}")

    size = os.path.getsize(path)
    log.info("Upload point photo: %s (%d bytes)", path, size)

    with open(path, "rb") as f:
        photos = upload.photo_messages(photos=f)

    if not photos:
        raise RuntimeError(f"VkUpload returned empty for {path}")

    p = photos[0]
    log.info("Uploaded: %s", p)
    return f"photo{p['owner_id']}_{p['id']}"


def get_photo_attachment(path: str) -> str:
    """Возвращает attachment, кэшируя результат."""
    if path not in _photo_cache:
        _photo_cache[path] = upload_photo_from_file(path)
    return _photo_cache[path]


def upload_collage_to_vk(image: Image.Image, peer_id: int) -> str:
    """Загружает PIL.Image в ВК через временный файл.
    """
    import tempfile

    image = image.convert("RGB")
    image.thumbnail((2000, 2000), Image.LANCZOS)

    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False, dir=".")
    tmp_path = tmp.name
    tmp.close()

    try:
        image.save(tmp_path, format="JPEG", quality=85, optimize=False)
        log.info("Collage temp: %s (%d bytes)", tmp_path, os.path.getsize(tmp_path))

        # 3. Загружаем как файл
        photos = upload.photo_messages(photos=tmp_path, peer_id=peer_id)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    if not photos:
        raise RuntimeError("VkUpload returned empty")

    p = photos[0]
    return f"photo{p['owner_id']}_{p['id']}"


def kb_start() -> VkKeyboard:
    kb = VkKeyboard(one_time=True)
    kb.add_button("🚀 Начать путешествие", color=VkKeyboardColor.POSITIVE)
    return kb


def kb_main() -> VkKeyboard:
    kb = VkKeyboard(one_time=True)
    kb.add_button("Казахстан", color=VkKeyboardColor.PRIMARY)
    kb.add_button("Кыргызстан", color=VkKeyboardColor.PRIMARY)
    kb.add_line()
    kb.add_button("Узбекистан", color=VkKeyboardColor.PRIMARY)
    kb.add_button("Армения", color=VkKeyboardColor.PRIMARY)
    return kb


def kb_sub(link: str, country_name: str | None = None) -> VkKeyboard:
    """Меню страны: кнопки только для доступных функций."""
    kb = VkKeyboard(one_time=False)

    country = COUNTRIES.get(country_name, {}) if country_name else {}

    if link:
        kb.add_openlink_button("🌐 Маршрут", link=link)

    has_route = bool(country.get("route_id"))

    if has_route:
        kb.add_line()
        kb.add_button("🗺 Фото-маршрут", color=VkKeyboardColor.SECONDARY)

    kb.add_line()
    kb.add_button("❓ Частые вопросы", color=VkKeyboardColor.SECONDARY)

    kb.add_line()
    kb.add_button("⬅️ Назад", color=VkKeyboardColor.SECONDARY)
    kb.add_button("В главное меню", color=VkKeyboardColor.SECONDARY)
    return kb


def kb_questions(country_name: str) -> VkKeyboard:
    questions = list(COUNTRIES[country_name]["questions"].keys())
    kb = VkKeyboard(one_time=False)
    for i, q in enumerate(questions):
        kb.add_button(q, color=VkKeyboardColor.SECONDARY)
        if i % 2 == 1 and i < len(questions) - 1:
            kb.add_line()
    kb.add_line()
    kb.add_button("⬅️ Назад", color=VkKeyboardColor.SECONDARY)
    kb.add_button("В главное меню", color=VkKeyboardColor.SECONDARY)
    return kb


def kb_route_step() -> VkKeyboard:
    kb = VkKeyboard(one_time=False)
    kb.add_button("⏭ Пропустить локацию", color=VkKeyboardColor.SECONDARY)
    kb.add_line()
    kb.add_button("❌ Отменить маршрут", color=VkKeyboardColor.SECONDARY)
    return kb


def send(user_id: int, text: str, keyboard=None, attachment=None):
    vk.messages.send(
        user_id=user_id,
        message=text,
        random_id=get_random_id(),
        keyboard=keyboard.get_keyboard() if keyboard else None,
        attachment=attachment,
    )


def start_route(user_id: int, country_name: str):
    """Запускает сбор фото для страны."""
    country = COUNTRIES[country_name]
    route_id = country.get("route_id")
    if not route_id:
        send(user_id, "Для этой страны фото-маршрут пока недоступен.")
        return

    session = sessions.start(user_id, route_id)
    route = get_route(route_id)

    send(user_id, (
        f"🗺 Фото-маршрут «{route.title}»\n\n"
        f"{route.description}\n\n"
        f"Точек в маршруте: {route.points_count}.\n"
        f"Я буду присылать описание каждой локации — "
        f"а ты фотографируй знаковые места и присылай сюда, чтобы сохранить эти моменты на память.\n\n"
        f"Поехали! 🚀"
    ), kb_route_step())

    send_current_point(user_id, session)


def send_current_point(user_id: int, session: UserSession):
    point = session.current_point()
    if point is None:
        return

    route = session.route()
    idx = session.current_index + 1
    total = route.points_count

    text = (
        f"📍 Точка {idx}/{total}\n\n"
        f"{point.name}\n\n"
        f"{point.description}\n\n"
        f"📷 {point.hint}"
    )

    attachment = None
    if point.foto and os.path.exists(point.foto):
        try:
            attachment = get_photo_attachment(point.foto)
        except Exception:
            log.exception("Failed to upload point photo: %s", point.foto)

    send(user_id, text, kb_route_step(), attachment=attachment)


def handle_route_photo(user_id: int, photo_url: str) -> bool:
    session = sessions.get(user_id)
    if session is None:
        return False

    if session.is_complete():
        return False

    try:
        r = requests.get(photo_url, timeout=30)
        r.raise_for_status()
        content = r.content
        Image.open(io.BytesIO(content)).verify()
    except Exception as e:
        log.exception("Photo download failed")
        send(user_id, f"😔 Не удалось обработать фото. Попробуйте загрузить другое.", kb_route_step())
        return True

    point = session.current_point()
    session.add_photo(content)

    done = session.current_index
    total = session.route().points_count

    if session.is_complete():
        send(user_id, f"✅ {done}/{total}. Все точки пройдены! Собираю коллаж... 🎨")
        build_and_send_collage(user_id, session)
    else:
        send(user_id, f"✅ {done}/{total} — «{point.short}» принято!")
        send_current_point(user_id, session)

    return True


def handle_route_skip(user_id: int, session: UserSession) -> None:
    """Пропускает текущую точку и идёт дальше."""
    point = session.current_point()
    if point is None:
        return

    session.skip_point()

    done = session.current_index
    total = session.route().points_count

    if session.is_complete():
        send(user_id, f"⏭ Пропущено: «{point.short}». {done}/{total}.\n"
                      f"Собираю коллаж из посещённых мест... 🎨")
        build_and_send_collage(user_id, session)
    else:
        send(user_id, f"⏭ Пропущено: «{point.short}».")
        send_current_point(user_id, session)


def handle_route_cancel(user_id: int) -> bool:
    """Отменяет маршрут, если он активен."""
    session = sessions.get(user_id)
    if session is None:
        return False

    sessions.remove(user_id)

    user = get_user(user_id)
    country_name = user[5]
    link = COUNTRIES.get(country_name, {}).get("link", "")

    send(user_id, "❌ Маршрут отменён.", kb_sub(link, country_name) if link else kb_main())
    return True


def build_and_send_collage(user_id: int, session: UserSession):
    """Собирает коллаж только по посещённым точкам."""
    route = session.route()

    try:
        visited_points = session.visited_points()
        visited_photos = session.visited_photos()

        if not visited_points:
            send(user_id, "😔 Ты не посетил ни одной локации — коллаж собрать не из чего.")
            sessions.remove(user_id)
            return

        sub_route = route.with_points(visited_points)

        photos = [
            Image.open(io.BytesIO(entry.content)).convert("RGB")
            for entry in visited_photos
        ]

        collage = make_route_collage(
            CollageInput(route=sub_route, photos=photos)
        )
        attachment = upload_collage_to_vk(collage, peer_id=user_id)

        skipped_names = [route.points[i].name for i in sorted(session.skipped)]
        extra = ""
        if skipped_names:
            extra = "\n\n⏭ Пропущено: " + ", ".join(skipped_names)

        send(
            user_id,
            f"🎉 Готово! Твой маршрут «{route.title}».\n\n"
            f"Посещено точек: {len(visited_points)} из {route.points_count}."
            f"{extra}\n\n"
            f"Спасибо за путешествие!",
            attachment=attachment,
        )
    except Exception as e:
        log.exception("Collage build failed")
        send(user_id, f"😔 Ошибка при сборке коллажа: {e}")
    finally:
        sessions.remove(user_id)

        user = get_user(user_id)
        country_name = user[5]
        link = COUNTRIES.get(country_name, {}).get("link", "")
        if link:
            send(user_id, "Вернуться в меню страны?", kb_sub(link, country_name))

def handle_message(event):
    user_id = event.message.from_id
    text = (event.message.text or "").strip()
    attachments = event.message.attachments or []


    session = sessions.get(user_id)
    if session is not None:
        session = sessions.get(user_id)
        if session is not None:
            if text in ("❌ Отменить маршрут", "Закончить маршрут"):
                handle_route_cancel(user_id)
                return

            if text == "⏭ Пропустить локацию":
                handle_route_skip(user_id, session)
                return

            url = get_largest_photo_url(attachments)
            if url:
                handle_route_photo(user_id, url)
                return

            send(user_id, "📷 Пришли фото с текущей точки, нажми «⏭ Пропустить локацию» "
                          "или «❌ Отменить маршрут»", kb_route_step())
            return


    user = get_user(user_id)
    reg_state = user[1]
    country_name = user[5]

    if text == "/start":
        reset_user(user_id)
        get_user(user_id)
        send(user_id,
             "👋 Привет! Я помогу тебе спланировать путешествие по странам СНГ.\n\n"
             "Готов начать?",
             kb_start())
        return

    if reg_state == 0:
        if text == "🚀 Начать путешествие":
            update_user(user_id, reg_state=4)
            send(user_id,
                 "Отлично! Теперь ты можешь отправиться в увлекательное путешествие "
                 "по странам СНГ.\n\nВыбирай страну:",
                 kb_main())
            return
        send(user_id, "Нажми кнопку ниже, чтобы начать 👇", kb_start())
        return

    if reg_state == 4:
        if text in COUNTRIES:
            country_id = COUNTRIES[text]["id"]
            update_user(user_id, reg_state=10 + country_id, country=text)
            send(user_id,
                 f"Ты выбрал {text}. Хочешь познакомиться с маршрутом "
                 f"по стране или узнать ответы на вопросы?",
                 kb_sub(COUNTRIES[text]["link"], COUNTRIES[text]['name']))
            return
        send(user_id, "Выбери страну из кнопок 👇", kb_main())
        return

    if reg_state in (11, 12, 13, 14):
        country_id = reg_state - 10
        country_name = ID_TO_COUNTRY[country_id]
        country = COUNTRIES[country_name]
        link = country["link"]

        if text in ("⬅️ Назад", "В главное меню"):
            update_user(user_id, reg_state=4)
            send(user_id, "Главное меню:", kb_main())
            return

        if text == "🗺 Фото-маршрут":
            start_route(user_id, country_name)
            return

        if text == "❓ Частые вопросы":
            update_user(user_id, reg_state=20 + country_id)
            send(user_id, "Выбери вопрос:", kb_questions(country_name))
            return

        send(user_id, "Не понял. Выбери среди вариантов 👇", kb_sub(link, country_name))
        return

    if reg_state in (21, 22, 23, 24):
        country_id = reg_state - 20
        country_name = ID_TO_COUNTRY[country_id]
        country = COUNTRIES[country_name]
        link = country["link"]
        questions = country["questions"]

        if text == "⬅️ Назад":
            update_user(user_id, reg_state=10 + country_id)
            send(user_id,
                 f"{country_name}. Хочешь познакомиться с маршрутом "
                 f"или узнать ответы на вопросы?",
                 kb_sub(link, country_name))
            return

        if text == "В главное меню":
            update_user(user_id, reg_state=4)
            send(user_id, "Главное меню:", kb_main())
            return

        if text in questions:
            update_user(user_id, reg_state=30 + country_id)
            send(user_id, questions[text], kb_questions(country_name))
            return

        send(user_id, "Выбери вопрос из кнопок 👇", kb_questions(country_name))
        return

    if reg_state in (31, 32, 33, 34):
        country_id = reg_state - 30
        country_name = ID_TO_COUNTRY[country_id]
        country = COUNTRIES[country_name]
        questions = country["questions"]

        if text == "⬅️ Назад":
            update_user(user_id, reg_state=20 + country_id)
            send(user_id, "Выбери вопрос:", kb_questions(country_name))
            return

        if text == "В главное меню":
            update_user(user_id, reg_state=4)
            send(user_id, "Главное меню:", kb_main())
            return

        if text in questions:
            send(user_id, questions[text], kb_questions(country_name))
            return

        send(user_id, "Выбери вопрос из кнопок 👇", kb_questions(country_name))
        return



def cleanup_worker():
    while True:
        time.sleep(300)
        try:
            n = sessions.cleanup_expired()
            if n:
                log.info("Cleaned %d expired sessions", n)
        except Exception:
            log.exception("Cleanup worker error")



def main():
    threading.Thread(target=cleanup_worker, daemon=True).start()

    log.info("=" * 60)
    log.info("Bot started. Group ID: %s", GROUP_ID)
    log.info("=" * 60)

    for event in longpoll.listen():
        if event.type != VkBotEventType.MESSAGE_NEW:
            continue
        if not event.from_user:
            continue

        try:
            handle_message(event)
        except Exception:
            log.exception("Handler error")
            try:
                user_id = event.message.from_id
                send(user_id, "😔 Что-то пошло не так. Попробуй ещё раз.")
            except Exception:
                log.exception("Failed to send error message")


if __name__ == "__main__":
    main()