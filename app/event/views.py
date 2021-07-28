import logging
from threading import Thread

from core.authentication import VKAuthentication
from core.models import (
    Activity,
    Competition,
    CompetitionParticipant,
    Event,
    Nomination,
    Participant,
    Season,
    Ticket,
    UsedTicketScanException,
    Warning,
)
from core.utils.sheets import EventReportGenerator, EventsRatingGenerator
from django.core.exceptions import ValidationError
from event import serializers
from rest_framework import filters, mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from reversion.views import RevisionMixin
from so.views import refreshBoecAchievements

logger = logging.getLogger(__name__)


class CreateListAndDestroyViewSet(
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    pass


class EventViewSet(
    RevisionMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """manage events in the database"""

    serializer_class = serializers.EventSerializer
    queryset = Event.objects.all()
    authentication_classes = (VKAuthentication,)
    permission_classes = (IsAuthenticated,)

    filter_backends = [filters.SearchFilter]
    search_fields = ("title",)

    def get_queryset(self):
        """Return ordered by title objects"""
        queryset = self.queryset.order_by("-startDate")

        visibility = self.request.query_params.get("visibility")

        if visibility == "false":
            queryset = queryset.filter(visibility=False)
        if visibility == "true":
            queryset = queryset.filter(visibility=True)

        return queryset

    def iterate_over_boecs(event):
        for boec in event.event_participation.all():
            refreshBoecAchievements(boec=boec)

        competitions_participants = CompetitionParticipant.objects.filter(
            competition__event=event, competition__ratingless=False
        )
        for item in competitions_participants.all():
            for boec in item.boec.all():
                refreshBoecAchievements(boec=boec)

    def perform_update(self, serializer):
        event = self.get_object()
        status = serializer.validated_data.get("status", None)

        if status == 1:

            Thread(target=self.iterate_over_boecs, args=(event,)).start()

        return super().perform_update(serializer)

    @action(
        methods=["post"],
        detail=True,
        permission_classes=(IsAuthenticated, IsAdminUser),
        url_path="report",
        url_name="report",
        authentication_classes=(VKAuthentication,),
    )
    def generateReport(self, request, pk):
        event = Event.objects.get(id=pk)
        reporter = EventReportGenerator("1s_NVTmYxG5GloDaOOw4d7eh7P_zAcobTmIRseYHsg3g")
        Thread(target=reporter.create, args=[event]).start()

        return Response({})

    @action(
        methods=["post"],
        detail=True,
        permission_classes=(IsAuthenticated, IsAdminUser),
        url_path="generate_tickets",
        url_name="generate_tickets",
        authentication_classes=(VKAuthentication,),
    )
    def generate_tickets(self, request, pk):
        event = Event.objects.get(id=pk)
        if not event.isTicketed:
            raise ValueError(f"Event {event} is not ticketed")

        if event.tickets.count() == 0:
            raise ValueError(f"Event {event} has no tickets")

        for ticket in event.tickets.all():
            ticket.generate_uuid()

        return Response({"event_id": event.id, "ticket_count": event.tickets.count()})

    @action(
        methods=["post"],
        detail=False,
        permission_classes=(IsAuthenticated, IsAdminUser),
        url_path="rating",
        url_name="rating",
        authentication_classes=(VKAuthentication,),
    )
    def generateRating(self, request):
        reporter = EventsRatingGenerator("1s_NVTmYxG5GloDaOOw4d7eh7P_zAcobTmIRseYHsg3g")
        Thread(target=reporter.create).start()

        return Response({})


class EventParticipant(RevisionMixin, CreateListAndDestroyViewSet):
    """manage participants in the database"""

    serializer_class = serializers.ParticipantSerializer
    authentication_classes = (VKAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        worth = self.request.query_params.get("worth", None)
        brigadeId = self.request.query_params.get("brigadeId", None)
        status = self.request.query_params.get("status", "approved")
        queryset = Participant.objects.filter(event=self.kwargs["event_pk"])

        if self.request.method == "GET" and status == "approved":
            queryset = queryset.filter(isApproved=True)

        if self.request.method == "GET" and status == "notapproved":
            queryset = queryset.filter(isApproved=False)

        if worth is not None:
            queryset = queryset.filter(worth=worth)

        if brigadeId is not None:
            queryset = queryset.filter(brigade=brigadeId)
        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["event_pk"] = self.kwargs["event_pk"]
        return context

    def perform_create(self, serializer):
        eventId = self.kwargs["event_pk"]
        event = Event.objects.get(id=eventId)
        worth = serializer.validated_data["worth"]

        isApproved = serializer.validated_data.get("isApproved", False)

        if not isApproved and worth > 0 or not event.isTicketed:
            isApproved = True

        if "brigade" not in serializer.validated_data:
            boec_last_season = (
                Season.objects.filter(boec=serializer.validated_data["boec"])
                .order_by("-year")
                .first()
            )
            serializer.save(
                event=event, brigade=boec_last_season.brigade, isApproved=isApproved
            )

        else:
            serializer.save(event=event, isApproved=isApproved)

    @action(
        methods=["post"],
        detail=True,
        permission_classes=(IsAuthenticated,),
        url_path="approve",
        url_name="approve",
        authentication_classes=(VKAuthentication,),
    )
    def approve(self, request, pk, **kwargs):
        participant = Participant.objects.get(id=pk)
        participant.isApproved = True
        participant.save()

        # TODO не создавать отдельные варнинги юзерам
        text = f"Ваша заявка на мероприятие {participant.event} одобрена"
        warning = Warning.objects.create(text=text)
        Activity.objects.create(type=0, boec=participant.boec, warning=warning)
        participant.boec.unreadActivityCount += 1
        participant.boec.save()

        return Response({})

    @action(
        methods=["post"],
        detail=True,
        permission_classes=(IsAuthenticated,),
        url_path="unapprove",
        url_name="unapprove",
        authentication_classes=(VKAuthentication,),
    )
    def unapprove(self, request, pk, **kwargs):
        participant = Participant.objects.get(id=pk)
        participant.isApproved = False
        participant.save()

        # TODO не создавать отдельные варнинги юзерам
        text = f"Ваша заявка на мероприятие {participant.event} отклонена"
        warning = Warning.objects.create(text=text)
        Activity.objects.create(type=1, boec=participant.boec, warning=warning)
        participant.boec.unreadActivityCount += 1
        participant.boec.save()

        return Response({})


class EventCompetitionListCreate(
    RevisionMixin,
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """manage event competitions in the database"""

    serializer_class = serializers.CompetitionSerializer
    authentication_classes = (VKAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        if "event_pk" in self.kwargs:
            return Competition.objects.filter(event=self.kwargs["event_pk"])
        return Competition.objects.all()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if "event_pk" in self.kwargs:
            context["event_pk"] = self.kwargs["event_pk"]
        return context

    def perform_create(self, serializer):
        if "event_pk" in self.kwargs:
            eventId = self.kwargs["event_pk"]
            event = Event.objects.get(id=eventId)
            serializer.save(event=event)
        else:
            super().perform_create(serializer)


class EventCompetitionRetrieveUpdateDestroy(
    RevisionMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """manage event competitions in the database"""

    serializer_class = serializers.CompetitionSerializer
    authentication_classes = (VKAuthentication,)
    permission_classes = [IsAuthenticated]
    queryset = Competition.objects.all()


class EventCompetitionParticipants(RevisionMixin, viewsets.ModelViewSet):
    """manage event competitions in the database"""

    serializer_class = serializers.CompetitionParticipantsSerializer
    authentication_classes = (VKAuthentication,)
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = CompetitionParticipant.objects.all()
        worth = self.request.query_params.get("worth", None)
        if "competition_pk" in self.kwargs:
            queryset = queryset.filter(competition=self.kwargs["competition_pk"])
        if worth is not None:
            if int(worth) == 2:
                queryset = queryset.filter(
                    worth=1, nomination__isRated=True, nomination__isnull=False
                )
            elif int(worth) == 3:
                queryset = queryset.filter(
                    worth=1, nomination__isRated=False, nomination__isnull=False
                )
            else:
                queryset = queryset.filter(worth=worth)
        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if "competition_pk" in self.kwargs:
            context["competition_pk"] = self.kwargs["competition_pk"]
        return context

    def perform_create(self, serializer):
        if "competition_pk" not in self.kwargs:
            raise ValidationError(
                {
                    "error": "You should not use this endpoint for creating "
                    "CompetitionParticipant objects "
                },
                code="validation",
            )
        competitionId = self.kwargs["competition_pk"]
        competition = Competition.objects.get(id=competitionId)
        serializer.save(competition=competition)


class NominationView(RevisionMixin, viewsets.ModelViewSet):
    """manage event competitions in the database"""

    serializer_class = serializers.NominationSerializer
    authentication_classes = (VKAuthentication,)
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Nomination.objects.all()
        if "competition_pk" in self.kwargs:
            queryset = queryset.filter(competition=self.kwargs["competition_pk"])
        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if "competition_pk" in self.kwargs:
            context["competition_pk"] = self.kwargs["competition_pk"]
        return context

    def perform_create(self, serializer):
        if "competition_pk" not in self.kwargs:
            raise ValidationError(
                {
                    "error": "You should not use this endpoint for creating "
                    "CompetitionParticipant objects "
                },
                code="validation",
            )
        competitionId = self.kwargs["competition_pk"]
        competition = Competition.objects.get(id=competitionId)
        serializer.save(competition=competition)

    def perform_destroy(self, instance):
        owner = instance.owner.all()
        if owner.count() > 0:
            for owner in owner.iterator():
                logger.error(owner)
                owner.worth = 1
                owner.save()

        return super().perform_destroy(instance)


class TicketViewSet(
    RevisionMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):

    serializer_class = serializers.TicketSerializer
    authentication_classes = (VKAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        queryset = Ticket.objects.all()
        return queryset

    @action(
        methods=["post"],
        detail=True,
        permission_classes=(IsAuthenticated, IsAdminUser),
        url_path="scan",
        url_name="scan",
        authentication_classes=(VKAuthentication,),
    )
    def scan(self, request, pk):
        ticket = Ticket.objects.get(id=pk)
        previous_scan = ticket.last_scan()
        try:
            ticket.scan()
        except UsedTicketScanException:
            return Response(
                {
                    "error": "Ticket already scanned",
                    "scannedAt": ticket.last_valid_scan().createdAt,
                }
            )
        return Response(
            {"prevScanAt": previous_scan.createdAt, "eventId": ticket.event.id}
        )

    @action(
        methods=["post"],
        detail=True,
        permission_classes=(IsAuthenticated, IsAdminUser),
        url_path="unscan",
        url_name="unscan",
        authentication_classes=(VKAuthentication,),
    )
    def unscan(self, request, pk):
        ticket = Ticket.objects.get(id=pk)
        if not ticket.is_used:
            raise ValueError("Ticket never actually used")
        last_valid_scan = ticket.last_valid_scan()
        last_valid_scan.isFinal = False
        last_valid_scan.save()
        return Response({})
