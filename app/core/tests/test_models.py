from core import models
from django.contrib.auth import get_user_model
from django.test import TestCase
from faker import Faker

fake = Faker(locale="ru_RU")
Faker.seed(4321)


def sample_user(vk_id="test"):
    """create a sample user"""
    return get_user_model().objects.create_user(vk_id=vk_id)


class ModelTests(TestCase):
    def test_create_user_with_vk_id_sussessfull(self):
        """Test creating a new user with an vk_id is successfulll"""
        vk_id = fake.pystr()
        user = get_user_model().objects.create_user(vk_id=vk_id)

        self.assertEqual(user.vk_id, vk_id)
        self.assertTrue(not user.has_usable_password())

    def test_new_user_invalid_email(self):
        """test creating user with no id raises error"""
        with self.assertRaises(ValueError):
            get_user_model().objects.create_user(None)

    def test_create_new_superuser(self):
        """test creating a new superuser"""
        user = get_user_model().objects.create_superuser(fake.pystr(), fake.password())
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)

    def test_create_new_superuser_without_pass(self):
        """test creating a new superuser without pass is failed"""
        with self.assertRaises(ValueError):
            get_user_model().objects.create_superuser(fake.pystr())

    def test_shtab_str(self):
        """test the shtab string representaion"""
        shtab = models.Shtab.objects.create(title=fake.pystr())

        self.assertEqual(str(shtab), shtab.title)

    def test_area_str(self):
        """test the areas string representaion"""
        area = models.Area.objects.create(title=fake.pystr(), shortTitle=fake.pystr())

        self.assertEqual(str(area), area.shortTitle)

    def test_boec_str(self):
        """test the boec's represenation"""
        boec = models.Boec.objects.create(
            firstName=fake.first_name(),
            lastName=fake.last_name(),
            middleName=fake.middle_name(),
        )

        self.assertEqual(
            str(boec), f"{boec.lastName} {boec.firstName} {boec.middleName}"
        )

    def test_brigade_str(self):
        """test the brigage representation"""
        area = models.Area.objects.create(title=fake.pystr(), shortTitle=fake.pystr())
        shtab = models.Shtab.objects.create(title=fake.pystr())
        brigade = models.Brigade.objects.create(
            title=fake.pystr(), area=area, shtab=shtab
        )
        self.assertEqual(str(brigade), brigade.title)

    def test_event_str(self):
        """test the event representation"""
        event = models.Event.objects.create(state=0, title=fake.pystr())

        self.assertEqual(str(event), event.title)

    def test_season_str(self):
        """test the season representation"""
        area = models.Area.objects.create(title=fake.pystr(), shortTitle=fake.pystr())
        shtab = models.Shtab.objects.create(title=fake.pystr())
        brigade = models.Brigade.objects.create(
            title=fake.pystr(), area=area, shtab=shtab
        )

        boec = models.Boec.objects.create(
            firstName=fake.first_name(),
            lastName=fake.last_name(),
            middleName=fake.middle_name(),
        )

        season = models.Season.objects.create(
            boec=boec, brigade=brigade, year=fake.pyint(min_value=2000, max_value=2021)
        )
        self.assertEqual(
            str(season), f"{season.year} - {brigade.title} {boec.lastName}"
        )
