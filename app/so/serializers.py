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

    fullName = serializers.SerializerMethodField("get_full_name")

    def get_full_name(self, obj):
        return f"{obj.lastName} {obj.firstName} {obj.middleName}"

    class Meta:
        model = Boec
        fields = ("id", "firstName", "lastName", "middleName", "fullName")
        read_only_fields = ("id", "fullName")


class SeasonSerializer(DynamicFieldsModelSerializer):
    """serializer for season objects"""

    brigade = BrigadeShortSerializer(read_only=True)
    brigadeId = serializers.PrimaryKeyRelatedField(
        queryset=Brigade.objects.all(), source="brigade"
    )
    boecId = serializers.PrimaryKeyRelatedField(
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
            "brigadeId",
            "boecId",
            "isCandidate",
            "isAccepted",
        )
        read_only_fields = ("id", "brigade", "boec")


class BoecTelegramSerializer(serializers.ModelSerializer):
    "Serializer for boec objects for Telegram interaction"
    fullName = serializers.SerializerMethodField("get_full_name")

    def get_full_name(self, obj):
        return f"{obj.lastName} {obj.firstName} {obj.middleName}"

    class Meta:
        model = Boec
        fields = (
            "id",
            "fullName",
            "vkId",
        )
        read_only_fields = ("id", "fullName")


class BoecSerializer(serializers.ModelSerializer):
    """serializer for boec objects"""

    fullName = serializers.SerializerMethodField("get_full_name")

    def get_full_name(self, obj):
        return f"{obj.lastName} {obj.firstName} {obj.middleName}"

    class Meta:
        model = Boec
        fields = (
            "id",
            "firstName",
            "lastName",
            "middleName",
            "DOB",
            "fullName",
            "vkId",
        )
        read_only_fields = ("id", "fullName")


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
        fields = ("id", "title", "shtab", "area", "DOB")
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
        fields = ("id", "title", "shortTitle", "brigades")
        read_only_fields = ("id",)


class PositionSerializer(serializers.ModelSerializer):
    """serializer for the position objects"""

    boec = BoecInfoSerializer(required=False)
    brigade = BrigadeShortSerializer(required=False)
    shtab = ShtabSerializer(required=False)
    boecId = serializers.PrimaryKeyRelatedField(
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
            "fromDate",
            "toDate",
            "boecId",
        )
        read_only_fields = ("id", "boec")


class ConferenceSerializer(serializers.ModelSerializer):
    """serializer for conference objects"""

    class Meta:
        model = Conference
        fields = ("id", "brigades", "date", "shtabs")
        read_only_fields = ("id",)
