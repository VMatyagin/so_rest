from core.authentication import VKAuthentication
from core.models import Achievement, Activity, Boec
from django.db.models import Count
from django.utils.translation import ugettext_lazy as _
from rest_framework import generics, permissions, viewsets
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.settings import api_settings
from reversion.views import RevisionMixin
from user.serializers import (
    AchievementSerializer,
    ActivitySerializer,
    AuthTokenSerializer,
    UserSerializer,
)


class CreateTokenView(ObtainAuthToken):
    """create a new auth token for user"""

    serializer_class = AuthTokenSerializer
    renderer_classes = api_settings.DEFAULT_RENDERER_CLASSES


class ManageUserView(generics.RetrieveAPIView):
    """manage the authenticated user"""

    serializer_class = UserSerializer
    authentication_classes = (VKAuthentication,)
    permission_classes = (permissions.IsAuthenticated,)

    def get_object(self):
        """retrieve and return authenticated user"""
        return self.request.user


class ActivityView(RevisionMixin, viewsets.GenericViewSet):
    """manage the activities"""

    serializer_class = ActivitySerializer
    authentication_classes = (VKAuthentication,)
    permission_classes = (permissions.IsAuthenticated,)
    queryset = Activity.objects.all()

    def retrieve(self, request, pk=None):
        try:
            boec = Boec.objects.get(vk_id=self.request.user.vk_id)

            seen = self.request.query_params.get("seen", False)
            activities = Activity.objects.filter(boec=boec, seen=bool(seen)).order_by(
                "-created_at"
            )
            page = self.paginate_queryset(activities)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            serializer = ActivitySerializer(activities, many=True)
        except (Boec.DoesNotExist, ValidationError):
            msg = _("Boec doesnt exists.")
            raise ValidationError({"error": msg}, code="validation")
        return Response(serializer.data)

    @action(
        methods=["post"],
        detail=True,
        permission_classes=(permissions.IsAuthenticated),
        url_path="markAsRead",
        url_name="markAsRead",
        authentication_classes=(VKAuthentication,),
    )
    def markAsRead(self, request, pk=None):
        try:
            boec: Boec = Boec.objects.get(vk_id=self.request.user.vk_id)
            Activity.objects.filter(boec=boec, seen=False).update(seen=True)
            boec.unread_activity_count = 0
            boec.save()
        except (Boec.DoesNotExist, ValidationError):
            msg = _("Boec doesnt exists.")
            raise ValidationError({"error": msg}, code="validation")

        return Response({})


class AchievementsView(RevisionMixin, viewsets.GenericViewSet):
    """manage the achievements"""

    authentication_classes = (VKAuthentication,)
    permission_classes = (permissions.IsAuthenticated,)
    pagination_class = None
    queryset = Achievement.objects.all()
    serializer_class = AchievementSerializer

    def list(self, request, *args, **kwargs):
        queryset = (
            self.filter_queryset(self.get_queryset())
            .annotate(q_count=Count("boec"))
            .order_by("-q_count", "-created_at")
        )

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
