from core.models import Boec, User
from django.core.management.base import BaseCommand
from so.views import refresh_boec_achievements


class Command(BaseCommand):
    """Parse JSON file and load data to DB"""

    def handle(self, *args, **options):
        users = User.objects.all()

        for user in users:
            try:
                boec = Boec.objects.get(vk_id=user.vk_id)
            except (Boec.DoesNotExist):
                continue

            refresh_boec_achievements(boec=boec)
