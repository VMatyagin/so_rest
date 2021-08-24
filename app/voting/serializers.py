import logging

from core.models import VoteAnswer, VoteQuestion, Voting
from core.serializers import DynamicFieldsModelSerializer
from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers

logger = logging.getLogger(__name__)


class AnswerSerializer(DynamicFieldsModelSerializer):
    """serializer for the vote answer objects"""

    count = serializers.SerializerMethodField("get_count")

    def get_count(self, obj):
        return obj.voted.count()

    class Meta:
        model = VoteAnswer
        fields = ("id", "text", "count")


class QuestionSerializer(DynamicFieldsModelSerializer):
    """serializer for the vote question objects"""

    answers = AnswerSerializer(many=True)

    class Meta:
        model = VoteQuestion
        fields = (
            "id",
            "text",
            "answers",
        )


class VotingSerializer(DynamicFieldsModelSerializer):
    """serializer for the voting objects"""

    questions = QuestionSerializer(many=True)

    class Meta:
        model = Voting
        fields = (
            "id",
            "text",
            "questions",
        )
