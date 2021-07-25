import logging
from datetime import datetime

from core.authentication import VKAuthentication
from core.models import (
    Achievement,
    Activity,
    Area,
    Boec,
    Brigade,
    CompetitionParticipant,
    Conference,
    Participant,
    Position,
    Season,
    Shtab,
)
from django.utils.translation import ugettext_lazy as _
from event.serializers import ParticipantHistorySerializer, ParticipantSerializer
from rest_framework import filters, mixins, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from reversion.views import RevisionMixin
from so import serializers
from user.serializers import ActivitySerializer


class ShtabViewSet(RevisionMixin, viewsets.ModelViewSet):
    """manage shtabs in the database"""

    serializer_class = serializers.ShtabSerializer
    queryset = Shtab.objects.all()
    authentication_classes = (VKAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        """Return ordered by title objects"""
        return self.queryset.order_by("title")


class AreaViewSet(RevisionMixin, viewsets.ModelViewSet):
    """manage shtabs in the database"""

    serializer_class = serializers.AreaSerializer
    queryset = Area.objects.all()
    authentication_classes = (VKAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        """Return ordered by shortTitle objects"""
        return self.queryset


class BoecViewSet(RevisionMixin, viewsets.ModelViewSet):
    """manage boecs in the database"""

    queryset = Boec.objects.all()
    authentication_classes = (VKAuthentication,)
    permission_classes = (IsAuthenticated,)
    filter_backends = [filters.SearchFilter]
    search_fields = ("^lastName", "firstName", "middleName")

    def get_serializer_class(self):
        if self.action == "list":
            return serializers.BoecInfoSerializer
        return serializers.BoecSerializer

    def get_queryset(self):
        """Return ordered by id objects"""
        queryset = self.queryset.order_by("lastName")

        brigadeId = self.request.query_params.get("brigadeId", None)
        if brigadeId is not None:
            queryset = queryset.filter(brigades=brigadeId)
        return queryset

    def perform_create(self, serializer):
        serializer.save()

    # @action(methods=['get'], detail=True, permission_classes=(IsAuthenticated, ),
    #         url_path='seasons', url_name='seasons',
    #         authentication_classes=(VKAuthentication,))
    # def handleBoecSeasons(self, request, pk):
    #     seasons = Season.objects.filter(boec=pk)
    #     """get users list"""
    #     serializer = serializers.SeasonSerializer(
    #         seasons, many=True, fields=('id', 'year', 'brigade'))
    #     return Response(serializer.data)


class BoecPositions(RevisionMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = serializers.PositionSerializer
    authentication_classes = (VKAuthentication,)
    permission_classes = (IsAuthenticated,)
    pagination_class = None

    def get_queryset(self):
        return Position.objects.filter(boec=self.kwargs["boec_pk"])


class BoecSeasons(RevisionMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = serializers.SeasonSerializer
    authentication_classes = (VKAuthentication,)
    permission_classes = (IsAuthenticated,)
    pagination_class = None

    def get_queryset(self):
        return Season.objects.filter(boec=self.kwargs["boec_pk"], isAccepted=True)


class BoecParticipantHistory(RevisionMixin, viewsets.GenericViewSet):
    authentication_classes = (VKAuthentication,)
    permission_classes = (IsAuthenticated,)
    pagination_class = None

    def list(self, request, *args, **kwargs):
        event_participant = Participant.objects.filter(
            boec=self.kwargs["boec_pk"], isApproved=True
        )
        competition_participant = CompetitionParticipant.objects.filter(
            boec=self.kwargs["boec_pk"], worth=1
        )

        participant_serializer = ParticipantSerializer(
            event_participant, fields=("event", "worth"), many=True
        )
        competition_participant_serializer = ParticipantHistorySerializer(
            competition_participant, many=True
        )
        return Response(
            {
                "event_participant": participant_serializer.data,
                "competition_participant": competition_participant_serializer.data,
            }
        )


def generateBoecProgress(boec):
    event_participant = boec.event_participation.filter(
        isApproved=True, event__status=1
    )
    participation_default = event_participant.filter(worth=0).count()
    participation_volonteer = event_participant.filter(worth=1).count()
    participation_organizer = event_participant.filter(worth=2).count()

    competition_participant = boec.competition_participation.filter(
        competition__ratingless=False
    )

    # просто подача заявок вместе с победами
    competition_default = competition_participant.count()
    competition_playoff = competition_participant.filter(worth=1).count()

    with_nomination = competition_participant.filter(worth=1, nomination__isnull=False)

    nominations_count = with_nomination.count()

    sport_wins = with_nomination.filter(competition__event__worth=2).count()
    art_wins = with_nomination.filter(competition__event__worth=1).count()

    seasons = boec.seasons.filter(isCandidate=False, isAccepted=True).count()

    return {
        "participation_count": participation_default,
        "volonteer_count": participation_volonteer,
        "organizer_count": participation_organizer,
        "competition_default": competition_default,
        "competition_playoff": competition_playoff,
        "nominations": nominations_count,
        "seasons": seasons,
        "sport_wins": sport_wins,
        "art_wins": art_wins,
    }


def refreshBoecAchievements(boec):
    progress = generateBoecProgress(boec)
    achievements = Achievement.objects.all()

    for ach in achievements:
        user_progress = progress.get(ach.type, 0)

        # если достижение еще не выдано юзеру, то выдаем и генерим уведомление
        # и обновляем счетчик
        if user_progress >= ach.goal and not ach.boec.filter(id=boec.id).exists():
            ach.boec.add(boec)
            Activity.objects.create(type=2, boec=boec, achievement=ach)
            boec.unreadActivityCount += 1

    boec.save()


class BoecProgress(RevisionMixin, viewsets.ViewSet):
    serializer_class = ActivitySerializer
    authentication_classes = (VKAuthentication,)
    permission_classes = (IsAuthenticated,)
    pagination_class = None

    def list(self, request, boec_pk=None):
        if boec_pk == None:
            user = request.user
            boec = Boec.objects.get(vkId=user.vkId)
        else:
            try:
                boec = Boec.objects.get(id=boec_pk)
            except (Boec.DoesNotExist, ValidationError):
                msg = _("Boec doesnt exists.")
                raise ValidationError({"error": msg}, code="validation")

        progress = generateBoecProgress(boec=boec)
        return Response(progress)


class BrigadeViewSet(RevisionMixin, viewsets.ModelViewSet):
    """manage brigades in the database"""

    queryset = Brigade.objects.all()
    authentication_classes = (VKAuthentication,)
    permission_classes = (IsAuthenticated,)
    filter_backends = [filters.SearchFilter]
    search_fields = ("title",)

    def get_serializer_class(self):
        if self.action == "list":
            return serializers.BrigadeShortSerializer
        return serializers.BrigadeSerializer

    def get_queryset(self):
        """Return ordered by title objects"""
        return self.queryset.order_by("title")


logger = logging.getLogger(__name__)


class SubjectPositions(
    RevisionMixin,
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = serializers.PositionSerializer
    authentication_classes = (VKAuthentication,)
    permission_classes = (IsAuthenticated,)
    pagination_class = None

    def get_queryset(self):
        queryset = Position.objects.filter(
            brigade=self.kwargs.get("brigade_pk", None),
            shtab=self.kwargs.get("shtab_pk", None),
        )

        toDate = self.request.query_params.get("hideLast", None)
        if toDate == "true":
            queryset = queryset.filter(toDate=None)
        return queryset.order_by("-toDate")

    def perform_create(self, serializer):
        brigadeId = self.kwargs.get("brigade_pk", None)
        shtabId = self.kwargs.get("shtab_pk", None)
        if brigadeId:
            try:
                brigade = Brigade.objects.get(id=brigadeId)
                serializer.save(brigade=brigade)

            except (Brigade.DoesNotExist, ValidationError):
                msg = _("Invalid brigade.")
                raise ValidationError({"error": msg}, code="validation")

        elif shtabId:
            try:
                shtab = Shtab.objects.get(id=shtabId)
                serializer.save(shtab=shtab)

            except (Shtab.DoesNotExist, ValidationError):
                msg = _("Invalid shtab.")
                raise ValidationError({"error": msg}, code="validation")
        else:
            raise ValidationError(
                {"Error": _("Provide shtab or brigade")}, code="validation"
            )


class BrigadeSeasons(RevisionMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = serializers.SeasonSerializer
    authentication_classes = (VKAuthentication,)
    permission_classes = (IsAuthenticated,)
    filter_backends = [filters.SearchFilter]
    search_fields = ("^boec__lastName", "boec__firstName", "boec__middleName")

    def get_queryset(self):
        return Season.objects.filter(brigade=self.kwargs["brigade_pk"]).order_by(
            "-year"
        )


class SeasonViewSet(RevisionMixin, viewsets.ModelViewSet):
    """manage seasons in the database"""

    serializer_class = serializers.SeasonSerializer
    queryset = Season.objects.all()
    authentication_classes = (VKAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        """Return objects"""
        return self.queryset.order_by("-year")


class ConferenceViewSet(RevisionMixin, viewsets.ReadOnlyModelViewSet):
    """manage conferences in the database"""

    queryset = Conference.objects.all()
    authentication_classes = (VKAuthentication,)
    permission_classes = (IsAuthenticated,)
    serializer_class = serializers.ConferenceSerializer

    def get_queryset(self):
        """Return ordered by title objects"""
        return self.queryset.order_by("date")
