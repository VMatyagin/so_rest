import logging
from threading import Thread

from core.authentication import VKAuthentication
from core.models import Event, Voting
from core.utils.sheets import EventReportGenerator, EventsRatingGenerator
from django.core.exceptions import ValidationError
from rest_framework import filters, mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from reversion.views import RevisionMixin
from so.views import refresh_boec_achievements
from voting import serializers

logger = logging.getLogger(__name__)


class VotingViewSet(
    RevisionMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """manage voting in the database"""

    serializer_class = serializers.VotingSerializer
    queryset = Voting.objects.all()

    def get_queryset(self):
        """Return ordered by created_at objects"""
        queryset = self.queryset.order_by("-created_at")
        return queryset
