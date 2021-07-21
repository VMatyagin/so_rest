import logging
import os

import requests
from core.models import User
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)

secret = os.environ.get("VK_CLIENT_SERVICE")


def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


class Command(BaseCommand):
    """Parse JSON file and load data to DB"""

    def handle(self, *args, **options):
        users = User.objects.filter(vkId__isnull=False)

        vk_ids = []

        for user in users:
            check_url = f"https://api.vk.com/method/apps.isNotificationsAllowed?user_id={user.vkId}&access_token={secret}&v=5.131"
            r = requests.get(check_url)
            if r.status_code == 200:
                data = r.json()
                if data["response"].get("is_allowed", False) == True:
                    vk_ids.append(str(user.vkId))

        if len(vk_ids) > 0:
            list = chunks(vk_ids, 100)
            for ids_chunk in list:
                ids = ",".join(ids_chunk)

                message = "Notification"
                url = f"https://api.vk.com/method/notifications.sendMessage?message={message}&user_ids={ids}=&access_token={secret}&v=5.131"
                r = requests.get(url)
                data = r.json()
                logger.error(data)
