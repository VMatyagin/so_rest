import uuid

from core.models import Event
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from event.serializers import EventSerializer
from rest_framework import status
from rest_framework.test import APIClient

EVENT_URL = reverse("event:event-list")


class PublicEventApiTests(TestCase):
    """test the publicly available event api"""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            f"{uuid.uuid4()}@email.com", "pass123"
        )
        self.client = APIClient()

    def test_login_required(self):
        """test that login is required for retrieving event's list"""
        res = self.client.get(EVENT_URL)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

        self.client.force_authenticate(self.user)
        res = self.client.get(EVENT_URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK)


class PrivateEventApiTest(TestCase):
    """test the authorized user event API"""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            f"{uuid.uuid4()}@email.com", "pass123"
        )

        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_retrieve_event_list(self):
        """test retrieve event"""
        Event.objects.create(state=Event.EventState.CREATED, title="test name")
        Event.objects.create(state=Event.EventState.CREATED, title="Atest name")

        res = self.client.get(EVENT_URL)

        lst = Event.objects.all().order_by("-title")
        serializer = EventSerializer(lst, many=True)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["items"], serializer.data)

    def test_create_event_successful(self):
        """test creating a new event"""
        payload = {"state": Event.EventState.CREATED, "title": "namw"}
        self.client.post(EVENT_URL, payload)
        exists = Event.objects.filter(title=payload["title"]).exists()
        self.assertTrue(exists)

    def test_create_event_invalid(self):
        """test creating a new event with invalid payload"""
        payload = {"title": ""}
        res = self.client.post(EVENT_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
