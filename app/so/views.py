import logging
import os

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
from rest_framework import filters, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from reversion.views import RevisionMixin
from so import serializers
from user.serializers import ActivitySerializer

logger = logging.getLogger(__name__)


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


class BoecTelegramView(RevisionMixin, viewsets.ViewSet):
    "Manage telegram links for boec in the db"

    @action(
        methods=["put"],
        detail=True,
    )
    def telegram_link(self, request, vk_id: int, telegram_id: int):
        if request.headers["X-Bot-Token"] != os.getenv("BOT_AUTH_TOKEN"):
            return Response(
                {"error": "Unauthorized"}, status=status.HTTP_401_UNAUTHORIZED
            )
        try:
            boec = Boec.objects.get(vk_id=vk_id)
            if boec.telegram_id != telegram_id:
                boec.telegram_id = telegram_id
                boec.save()
                return Response(
                    serializers.BoecTelegramSerializer(boec).data,
                    status=status.HTTP_201_CREATED,
                )
            else:
                return Response(serializers.BoecTelegramSerializer(boec).data)
        except Boec.DoesNotExist:
            msg = _(f"Boec with VK ID = {vk_id} doesn't exist")
            return Response({"error": msg}, status=status.HTTP_404_NOT_FOUND)
        except ValidationError as e:
            msg = _(f"Validation error: {e.detail}")
            raise ValidationError({"error": msg}, code="validation")


class BoecViewSet(RevisionMixin, viewsets.ModelViewSet):
    """manage boecs in the database"""

    queryset = Boec.objects.all()
    authentication_classes = (VKAuthentication,)
    permission_classes = (IsAuthenticated,)
    filter_backends = [filters.SearchFilter]
    search_fields = ("^last_name", "first_name", "middle_name")

    def get_serializer_class(self):
        if self.action == "list":
            return serializers.BoecInfoSerializer
        return serializers.BoecSerializer

    def get_queryset(self):
        """Return ordered by id objects"""
        queryset = self.queryset.order_by("last_name")

        brigade_id = self.request.query_params.get("brigade_id", None)
        if brigade_id is not None:
            queryset = queryset.filter(brigades=brigade_id)
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
        return Season.objects.filter(boec=self.kwargs["boec_pk"], is_accepted=True)


class BoecParticipantHistory(RevisionMixin, viewsets.GenericViewSet):
    authentication_classes = (VKAuthentication,)
    permission_classes = (IsAuthenticated,)
    pagination_class = None
    serializer_class = ParticipantHistorySerializer

    def list(self, request, *args, **kwargs):
        event_participant = Participant.objects.filter(
            boec=self.kwargs["boec_pk"], is_approved=True
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
                "eventParticipant": participant_serializer.data,
                "competitionParticipant": competition_participant_serializer.data,
            }
        )


def generate_boec_progress(boec: Boec):
    event_participant = boec.event_participation.filter(
        is_approved=True, event__status=1
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

    seasons = boec.seasons.filter(is_candidate=False, is_accepted=True).count()

    return {
        "participationCount": participation_default,
        "volonteerCount": participation_volonteer,
        "organizerCount": participation_organizer,
        "competitionDefault": competition_default,
        "competitionPlayoff": competition_playoff,
        "nominations": nominations_count,
        "seasons": seasons,
        "sportWins": sport_wins,
        "artWins": art_wins,
    }


def refresh_boec_achievements(boec: Boec):
    progress = generate_boec_progress(boec)
    achievements = Achievement.objects.all()

    for ach in achievements:
        user_progress = progress.get(ach.type, 0)

        # если достижение еще не выдано юзеру, то выдаем и генерим уведомление
        # и обновляем счетчик
        if user_progress >= ach.goal and not ach.boec.filter(id=boec.id).exists():
            ach.boec.add(boec)
            Activity.objects.create(type=2, boec=boec, achievement=ach)
            boec.unread_activity_count += 1

    boec.save()


class BoecProgress(RevisionMixin, viewsets.ViewSet):
    serializer_class = ActivitySerializer
    authentication_classes = (VKAuthentication,)
    permission_classes = (IsAuthenticated,)
    pagination_class = None

    def list(self, request, boec_pk=None):
        if boec_pk == None:
            user = request.user
            boec = Boec.objects.get(vk_id=user.vk_id)
        else:
            try:
                boec = Boec.objects.get(id=boec_pk)
            except (Boec.DoesNotExist, ValidationError):
                msg = _("Boec doesnt exists.")
                raise ValidationError({"error": msg}, code="validation")

        progress = generate_boec_progress(boec=boec)
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

        to_date = self.request.query_params.get("hideLast", None)
        if to_date == "true":
            queryset = queryset.filter(to_date=None)
        return queryset.order_by("-to_date")

    def perform_create(self, serializer):
        brigade_id = self.kwargs.get("brigade_pk", None)
        shtab_id = self.kwargs.get("shtab_pk", None)
        if brigade_id:
            try:
                brigade = Brigade.objects.get(id=brigade_id)
                serializer.save(brigade=brigade)

            except (Brigade.DoesNotExist, ValidationError):
                msg = _("Invalid brigade.")
                raise ValidationError({"error": msg}, code="validation")

        elif shtab_id:
            try:
                shtab = Shtab.objects.get(id=shtab_id)
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
    search_fields = ("^boec__last_name", "boec__first_name", "boec__middle_name")

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
