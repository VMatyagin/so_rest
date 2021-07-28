import logging

from core.auth_backend import PasswordlessAuthBackend
from core.models import Achievement, Activity, Boec, Brigade, Shtab, Warning
from core.serializers import DynamicFieldsModelSerializer
from django.contrib.auth import get_user_model
from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers
from so.serializers import BoecInfoSerializer, BrigadeSerializer, ShtabSerializer

logger = logging.getLogger(__name__)


class UserSerializer(serializers.ModelSerializer):
    """serializer for the users object"""

    brigades = serializers.SerializerMethodField(
        "get_editable_brigades", read_only=True
    )
    seasonBrigades = serializers.SerializerMethodField(
        "get_season_brigades", read_only=True
    )
    shtabs = serializers.SerializerMethodField("get_editable_shtabs", read_only=True)
    boec = serializers.SerializerMethodField("get_boec", read_only=True)
    unreadActivityCount = serializers.SerializerMethodField(
        "get_boec_unread_activity_count", read_only=True
    )

    def get_editable_brigades(self, obj):
        brigades = Brigade.objects.filter(
            positions__to_date__isnull=True, positions__boec__vk_id=obj.vk_id
        ).distinct()

        serializer = BrigadeSerializer(brigades, many=True, fields=("id", "title"))

        return serializer.data

    def get_season_brigades(self, obj):
        brigades = Brigade.objects.filter(seasons__boec__vk_id=obj.vk_id).distinct()

        serializer = BrigadeSerializer(brigades, many=True, fields=("id", "title"))

        return serializer.data

    def get_editable_shtabs(self, obj):
        shtabs = Shtab.objects.filter(
            positions__to_date__isnull=True,
            positions__boec__vk_ud=obj.vk_id,
        ).distinct()

        serializer = ShtabSerializer(shtabs, many=True, fields=("id", "title"))

        return serializer.data

    def get_boec(self, obj):
        try:
            boec_obj = Boec.objects.get(vk_id=obj.vk_id)
            serializer = BoecInfoSerializer(boec_obj)
        except (Boec.DoesNotExist):
            return None
        return serializer.data

    def get_boec_unreadActivityCount(self, obj):
        try:
            boec_obj: Boec = Boec.objects.get(vk_id=obj.vk_id)
            return boec_obj.unread_activity_count
        except (Boec.DoesNotExist):
            return 0

    class Meta:
        model = get_user_model()
        fields = (
            "id",
            "brigades",
            "boec",
            "shtabs",
            "is_staff",
            "season_brigades",
            "unread_activity_count",
        )

    def create(self, validated_data):
        """create a new user and return it"""
        return get_user_model().objects.create_user(**validated_data)

    def update(self, instance, validated_data):
        """update a user and return it"""
        user = super().update(instance, validated_data)

        return user


class AuthTokenSerializer(serializers.Serializer):
    """serializer for the user authentication object"""

    vkId = serializers.IntegerField()
    # password = serializers.CharField(
    #     style={'input_type': 'password'},
    #     trim_whitespace=False
    # )

    def validate(self, attrs):
        """validate and authenticate the user"""
        vk_id = attrs.get("vkId")
        # password = attrs.get('password')

        user = PasswordlessAuthBackend().authenticate(
            request=self.context.get("request"),
            vk_id=vk_id,
            # password=password
        )
        if not user:
            msg = _("Unable to authenticate with provided credentials")
            raise serializers.ValidationError(msg, code="authentication")

        attrs["user"] = user
        return attrs


class WarningSerializer(DynamicFieldsModelSerializer):
    """serializer for Warning"""

    class Meta:
        model = Warning
        fields = ("id", "text")


class AchievementSerializer(DynamicFieldsModelSerializer):
    """serializer for Achievement"""

    achieved_at = serializers.SerializerMethodField("check_status")

    def check_status(self, obj):
        request = self.context.get("request")
        if request:
            boec_id = self.context["request"].query_params.get("boec_id", None)

            if boec_id == None:
                user = request.user
                boec: Boec = Boec.objects.get(vk_id=user.vk_id)
            else:
                try:
                    boec: Boec = Boec.objects.get(id=boec_id)
                except (Boec.DoesNotExist):
                    msg = _("Boec not found")
                    raise serializers.ValidationError({"error": msg})

            is_achieved = obj.boec.filter(id=boec.id).exists()
            if not is_achieved:
                return None

            try:
                activity = Activity.objects.get(boec=boec, achievement=obj)

            except (Activity.DoesNotExist):
                msg = _("Activity not found")
                raise serializers.ValidationError({"error": msg})

            return activity.created_at

        return None

    class Meta:
        model = Achievement
        fields = (
            "id",
            "type",
            "created_at",
            "title",
            "goal",
            "achieved_at",
            "description",
        )


class ActivitySerializer(DynamicFieldsModelSerializer):
    """serializer for Activity"""

    warning = WarningSerializer()
    achievement = AchievementSerializer()

    class Meta:
        model = Activity
        fields = ("id", "type", "created_at", "warning", "achievement")
