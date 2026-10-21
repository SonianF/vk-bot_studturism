"""VK API клиент — единая точка доступа."""

import os
import logging

from dotenv import load_dotenv
from vk_api import VkApi
from vk_api.bot_longpoll import VkBotLongPoll


load_dotenv()

log = logging.getLogger(__name__)

TOKEN = os.environ["GROUP_TOKEN"]
GROUP_ID = int(os.environ["GROUP_ID"])

vk_session = VkApi(token=TOKEN)
vk = vk_session.get_api()
longpoll = VkBotLongPoll(vk_session, GROUP_ID)

log.info("VK client initialized. Group ID: %s", GROUP_ID)