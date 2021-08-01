from core.models import Area, Boec, Brigade, Conference, Position, Season, Shtab
from core.serializers import DynamicFieldsModelSerializer
from rest_framework import serializers


class ShtabSerializer(DynamicFieldsModelSerializer):
    """serializer for the shtab objects"""

    class Meta:
        model = Shtab
        fields = ("id", "title")
        read_only_fields = ("id",)


class FilteredListSerializer(serializers.ListSerializer):
    def to_representation(self, data):
        shtabId = self.context["request"].query_params.get("shtab")
        if shtabId is not None:
            data = data.filter(shtab=shtabId)

        return super(FilteredListSerializer, self).to_representation(data)


class BrigadeShortSerializer(DynamicFieldsModelSerializer):
    """serializer with only id and title"""

    class Meta:
        list_serializer_class = FilteredListSerializer
        model = Brigade
        fields = ("id", "title", "area")
        read_only_fields = ("id",)


class BoecInfoSerializer(serializers.ModelSerializer):
    """serializer for boec objects"""

    class Meta:
        model = Boec
        fields = ("id", "first_name", "last_name", "middle_name", "full_name")
        read_only_fields = ("id", "full_name")


class SeasonSerializer(DynamicFieldsModelSerializer):
    """serializer for season objects"""

    brigade = BrigadeShortSerializer(read_only=True)
    brigade_id = serializers.PrimaryKeyRelatedField(
        queryset=Brigade.objects.all(), source="brigade"
    )
    boec_id = serializers.PrimaryKeyRelatedField(
        queryset=Boec.objects.all(), source="boec"
    )

    boec = BoecInfoSerializer(read_only=True)

    class Meta:
        model = Season
        fields = (
            "id",
            "boec",
            "year",
            "brigade",
            "brigade_id",
            "boec_id",
            "is_candidate",
            "is_accepted",
        )
        read_only_fields = ("id", "brigade", "boec")


class BoecTelegramSerializer(serializers.ModelSerializer):
    "Serializer for boec objects for Telegram interaction"

    class Meta:
        model = Boec
        fields = (
            "id",
            "full_name",
            "vk_id",
        )
        read_only_fields = ("id", "full_name")


class BoecSerializer(serializers.ModelSerializer):
    """serializer for boec objects"""

    class Meta:
        model = Boec
        fields = (
            "id",
            "first_name",
            "last_name",
            "middle_name",
            "date_of_birth",
            "full_name",
            "vk_id",
        )
        read_only_fields = ("id", "full_name")


class BrigadeSerializer(DynamicFieldsModelSerializer):
    """serializer for brigade objects"""

    # past_seasons = serializers.SerializerMethodField('get_past_seasons')

    shtab = ShtabSerializer(read_only=True)
    # def get_past_seasons(self, obj):
    #     value_list = obj.seasons.values_list(
    #         'year', flat=True
    #     ).distinct()
    #     group_by_value = {}
    #     for value in value_list:
    #         list = obj.seasons.filter(
    #             year=value
    #         ).only('boec')
    #         serializer = SeasonSerializer(
    #             list, many=True, fields=('boec', 'id'))

    #         group_by_value[value] = serializer.data

    #     return group_by_value

    class Meta:
        model = Brigade
        fields = ("id", "title", "shtab", "area", "date_of_birth", "state")
        read_only_fields = ("id",)


class AreaSerializer(serializers.ModelSerializer):
    """serializer for area objects"""

    brigades = serializers.SerializerMethodField("get_brigades")

    def get_brigades(self, obj):
        queryset = obj.brigades.order_by("title")
        serializer = BrigadeShortSerializer(
            queryset,
            many=True,
            read_only=True,
            context={"request": self.context["request"]},
        )
        return serializer.data

    class Meta:
        model = Area
        fields = ("id", "title", "short_title", "brigades")
        read_only_fields = ("id",)


class PositionSerializer(serializers.ModelSerializer):
    """serializer for the position objects"""

    boec = BoecInfoSerializer(required=False)
    brigade = BrigadeShortSerializer(required=False)
    shtab = ShtabSerializer(required=False)
    boec_id = serializers.PrimaryKeyRelatedField(
        queryset=Boec.objects.all(), source="boec"
    )

    class Meta:
        model = Position
        fields = (
            "id",
            "position",
            "boec",
            "brigade",
            "shtab",
            "from_date",
            "to_date",
            "boec_id",
        )
        read_only_fields = ("id", "boec")


class ConferenceSerializer(serializers.ModelSerializer):
    """serializer for conference objects"""

    class Meta:
        model = Conference
        fields = ("id", "brigades", "date", "shtabs")
        read_only_fields = ("id",)
