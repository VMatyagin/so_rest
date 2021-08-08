import datetime
import functools
import os
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional

import reversion
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.contrib.humanize.templatetags.humanize import naturaltime
from django.db import models
from django.db.models import Count, Q, TextChoices
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from django_fsm import FSMField, FSMIntegerField, transition
from rest_framework.exceptions import ValidationError


def recipe_image_file_path(instance, filename):
    """Generate file path for new recipe image"""
    ext = filename.split(".")[-1]
    filename = f"{uuid.uuid4()}.{ext}"

    return os.path.join("uploads/recipe/", filename)


class AutoDateTimeField(models.DateTimeField):
    def pre_save(self, model_instance, add):
        return timezone.now()


class UserManager(BaseUserManager):
    def create_user(self, vk_id, password=None, **extra_fields):
        """creates and saves a new user"""
        if not vk_id:
            raise ValueError("Users must have an vk_id")
        user = self.model(vk_id=vk_id, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)

        return user

    def create_superuser(self, vk_id, password=None):
        """creates and save a new super user"""
        if not password:
            raise ValueError("SuperUsers must have password")
        user = self.create_user(vk_id=vk_id, password=password)
        user.is_staff = True
        user.is_superuser = True

        user.save(using=self._db)

        return user


@reversion.register()
class User(AbstractBaseUser, PermissionsMixin):
    """custom user model that support using id instead of username"""

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"

    vk_id = models.IntegerField(unique=True)

    name = models.CharField(max_length=255, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateField(default=timezone.now)
    updated_at = AutoDateTimeField(default=timezone.now)
    password = models.CharField(max_length=128, blank=True)

    objects = UserManager()

    USERNAME_FIELD = "vk_id"

    def __str__(self):
        return f"{self.vk_id}"


@reversion.register()
class Shtab(models.Model):
    """Shtab object"""

    class Meta:
        verbose_name = "Штаб"
        verbose_name_plural = "Штабы"

    title = models.CharField(max_length=255)
    created_at = models.DateField(default=timezone.now)
    updated_at = AutoDateTimeField(default=timezone.now)

    def __str__(self):
        return self.title


@reversion.register()
class Area(models.Model):
    """Area (direction) object"""

    class Meta:
        verbose_name = "Направления"
        verbose_name_plural = "Направления"

    title = models.CharField(max_length=255)
    short_title = models.CharField(max_length=10)
    created_at = models.DateField(default=timezone.now)
    updated_at = AutoDateTimeField(default=timezone.now)

    @property
    def brigades_count(self):
        return self.brigades.count()

    def __str__(self):
        return self.short_title


@reversion.register()
class Boec(models.Model):
    """Boec object"""

    class Meta:
        verbose_name = "Боец"
        verbose_name_plural = "Бойцы"

    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    middle_name = models.CharField(max_length=255, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    created_at = models.DateField(default=timezone.now)
    updated_at = AutoDateTimeField(default=timezone.now)
    vk_id = models.IntegerField(
        verbose_name="VK id", blank=True, null=True, unique=True
    )
    unread_activity_count = models.IntegerField(default=0)
    telegram_id = models.IntegerField(
        verbose_name="Telegram ID", null=True, unique=True, blank=True
    )

    @property
    def full_name(self):
        return f"{self.last_name} {self.first_name} {self.middle_name}"

    def __str__(self):
        return self.full_name


@reversion.register()
class Brigade(models.Model):
    """Brigade object"""

    class Meta:
        verbose_name = "Отряд"
        verbose_name_plural = "Отряды"

    title = models.CharField(max_length=255)
    area = models.ForeignKey(Area, on_delete=models.RESTRICT, related_name="brigades")
    shtab = models.ForeignKey(Shtab, on_delete=models.RESTRICT)
    boec = models.ManyToManyField(Boec, blank=True, related_name="brigades")
    date_of_birth = models.DateTimeField(null=True, blank=True)
    created_at = models.DateField(default=timezone.now)
    updated_at = AutoDateTimeField(default=timezone.now)

    class BrigadeState(TextChoices):
        CANDIDATE = "candidate", _("Кандидатский")
        MEMBER = "member", _("Действующий")
        DEAD = "dead", _("Мёртвый")

    state = FSMField(
        default=BrigadeState.CANDIDATE,
        choices=BrigadeState.choices,
        verbose_name="Статус отряда",
    )
    last_festival_state = models.CharField(
        choices=BrigadeState.choices, null=True, max_length=255
    )

    def __str__(self):
        return self.title

    @transition(field=state, source="+", target=BrigadeState.MEMBER)
    def accept(self):
        pass

    @transition(field=state, source="+", target=BrigadeState.DEAD)
    def kill(self):
        pass

    @transition(field=state, source="+", target=BrigadeState.CANDIDATE)
    def unaccept(self):
        pass

    def last_season_people_count(self) -> int:
        # Starting from september target year = current year
        # Previous year otherwise
        target_year = (
            datetime.date.today().year
            if datetime.date.today().month >= 9
            else datetime.date.today().year - 1
        )
        return self.seasons.filter(
            is_accepted=True, is_candidate=False, year=target_year
        ).count()


class EventWorth(models.IntegerChoices):
    UNSET = 0, _("Не учитывается")
    ART = 1, _("Творчество")
    SPORT = 2, _("Спорт")
    VOLUNTEER = 3, _("Волонтерство")
    CITY = 4, _("Городское")


@reversion.register()
class Event(models.Model):
    """Event model"""

    class Meta:
        verbose_name = "Мероприятие"
        verbose_name_plural = "Мероприятия"

    class EventState(models.IntegerChoices):
        CREATED = 0, _("Мероприятие создано")
        QUOTA_CALCULATION = 1, _("Расчёт квот")
        # QUOTA_DISTRIBUTION = 2, _("Распределение квот") # Not used
        REGISTRATION = 3, _("Регистрация желающих")
        REGISTRATION_COMPLETE = 4, _("Регистрация окончена")
        TICKETS_GENERATED = 5, _("Билеты сгенерированы")
        PASSED = 6, _("Мероприятие прошло")
        CANCELLED = 7, _("Мероприятие отменено")

    worth = models.IntegerField(
        choices=EventWorth.choices,
        default=EventWorth.UNSET,
        verbose_name="Ценность блоков",
    )
    state = FSMIntegerField(
        default=EventState.CREATED,
        choices=EventState.choices,
        verbose_name="Статус мероприятия",
    )
    title = models.CharField(max_length=255, verbose_name="Название")
    description = models.CharField(
        max_length=255, blank=True, null=True, verbose_name="Описание"
    )
    location = models.CharField(
        max_length=255, blank=True, null=True, verbose_name="Место проведения"
    )
    shtab = models.ForeignKey(
        Shtab, on_delete=models.SET_NULL, null=True, verbose_name="Штаб"
    )
    start_date = models.DateTimeField(verbose_name="Дата начала")
    start_time = models.TimeField(null=True, blank=True, verbose_name="Время начала")

    visibility = models.BooleanField(default=False, verbose_name="Видимость")
    is_canonical = models.BooleanField(default=False, verbose_name="Каноничность")

    is_ticketed = models.BooleanField(default=False, verbose_name="Вход по билетам")

    def __str__(self):
        return self.title

    def quotas_match_participants(self) -> bool:
        if not self.is_ticketed:
            return True
        approved_participants_by_brigade = Brigade.objects.annotate(
            approved_count=Count(
                "event_participants",
                filter=Q(
                    event_participants__is_approved=True,
                    event_participants__worth=Participant.WorthEnum.DEFAULT,
                    event_participants__event_id=self.id,
                ),
            )
        )

        errors: List[Dict[str, Any]] = list()
        for brigade in approved_participants_by_brigade:
            approved_count = approved_participants_by_brigade.approved_count
            allowed_count = self.quotas.filter(bridage_id=brigade.id).count
            if allowed_count < approved_count:
                errors.append(
                    {
                        "brigade": brigade,
                        "allowed": allowed_count,
                        "approved": approved_count,
                        "items": approved_participants_by_brigade,
                    }
                )
        if len(errors) == 0:
            return True
        else:
            for error in errors:
                print(
                    f"Brigade {error['brigade']} has {error['allowed']} quotas and {error['approved']} approved requests"
                )
            return False

    @transition(
        field=state, source=EventState.CREATED, target=EventState.QUOTA_CALCULATION
    )
    def start_quota_calc(self):
        pass

    @transition(
        field=state,
        source=EventState.QUOTA_CALCULATION,
        target=EventState.REGISTRATION,
    )
    def start_registration(self):
        pass

    @transition(
        field=state,
        source=EventState.REGISTRATION,
        target=EventState.REGISTRATION_COMPLETE,
        conditions=[quotas_match_participants],
    )
    def complete_registration(self):
        pass

    @transition(
        field=state,
        source=EventState.REGISTRATION_COMPLETE,
        target=EventState.TICKETS_GENERATED,
        conditions=[is_ticketed],
    )
    def generate_tickets(self):
        pass

    @transition(
        field=state,
        source=[EventState.REGISTRATION_COMPLETE, EventState.TICKETS_GENERATED],
        target=EventState.PASSED,
    )
    def complete(self):
        pass

    @transition(
        field=state,
        source="+",
        target=EventState.CANCELLED,
        custom={"button_name": "Отменить мероприятие"},
    )
    def cancel(self):
        pass

    def distribute_quotas(
        self,
        total_count: int,
        candidates_accepted: bool = False,
        shtab_id: Optional[int] = None,
        area_id: Optional[int] = None,
    ) -> None:
        if self.state != self.EventState.QUOTA_CALCULATION:
            raise ValueError(
                "Can't distribute quotas unless the event is in quota_calculation state"
            )

        if shtab_id is not None and area_id is not None:
            raise ValueError("Can't limit quotas to Shtab and Area simultaneously")

        allowed_brigade_states = [Brigade.BrigadeState.MEMBER]
        if candidates_accepted:
            allowed_brigade_states.append(Brigade.BrigadeState.CANDIDATE)

        if shtab_id is not None:
            brigades = Brigade.objects.get(
                shtab_id=shtab_id, state__in=[allowed_brigade_states]
            )
        elif area_id is not None:
            brigades = Brigade.objects.get(
                area_id=area_id, state__in=[allowed_brigade_states]
            )
        else:
            brigades = Brigade.objects.all(state__in=[allowed_brigade_states])

        total_season_people_count = sum(
            [brigade.last_season_people_count() for brigade in brigades]
        )
        ratio = total_count / total_season_people_count

        self.quotas.delete()

        for brigade in brigades:
            self.quotas.create(
                brigade=brigade, count=brigade.last_season_people_count() * ratio
            )


class UsedTicketScanException(RuntimeError):
    pass


@reversion.register()
class Ticket(models.Model):
    """Event ticket model"""

    class Meta:
        verbose_name = "Билет"
        verbose_name_plural = "Билеты"

    boec = models.ForeignKey(
        Boec, on_delete=models.CASCADE, verbose_name="ФИО", related_name="tickets"
    )

    event = models.ForeignKey(
        Event,
        on_delete=models.RESTRICT,
        verbose_name="Мероприятие",
        related_name="tickets",
    )

    uuid = models.UUIDField(verbose_name="Код", null=True, default=None)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def generate_uuid(self) -> str:
        self.uuid = uuid.uuid4()
        self.save()
        return str(self.uuid)

    @property
    def is_used(self) -> bool:
        """Checks whether there's a final ticket scan for this ticket"""
        return self.ticket_scans.filter(is_final=True).exists()

    def last_scan(self) -> "TicketScan":
        return self.ticket_scans.order_by("created_at").last()

    def last_valid_scan(self) -> "TicketScan":
        return self.ticket_scans.filter(is_final=True).order_by("created_at").last()

    def scan(self):
        if self.is_used:
            raise UsedTicketScanException("Ticket has already been used")
        self.ticket_scans.create(is_final=True)

    def __str__(self) -> str:
        return f"{self.boec} - {self.event}"


@reversion.register()
class TicketScan(models.Model):
    """Event ticket scan model"""

    class Meta:
        verbose_name = "Скан билета"
        verbose_name_plural = "Сканы билетов"

    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        verbose_name="Билет",
        related_name="ticket_scans",
    )

    is_final = models.BooleanField(default=True, verbose_name="Проверен")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def is_final_str(self) -> str:
        return "Проверен" if self.is_final else "Предъявлен"

    def __str__(self) -> str:
        return (
            f"{self.ticket.boec} — {self.ticket.event} — "
            f"{self.is_final_str} {naturaltime(self.created_at)}"
        )


@reversion.register()
class Season(models.Model):
    """Season model"""

    class Meta:
        verbose_name = "Выезжавший на сезон"
        verbose_name_plural = "Выезжавшие на сезон"

    boec = models.ForeignKey(
        Boec, on_delete=models.CASCADE, verbose_name="ФИО", related_name="seasons"
    )
    brigade = models.ForeignKey(
        Brigade, on_delete=models.RESTRICT, verbose_name="Отряд", related_name="seasons"
    )
    year = models.IntegerField(verbose_name="Год выезда")

    is_accepted = models.BooleanField(default=False, verbose_name="Подтвержден")
    is_candidate = models.BooleanField(default=True, verbose_name="Не стал бойцом")

    def __str__(self):
        return f"{self.year} - {self.brigade.title} {self.boec.last_name}"


@reversion.register()
class Position(models.Model):
    """Position model"""

    class Meta:
        verbose_name = "Должность"
        verbose_name_plural = "Должности"

    class PositionEnum(models.IntegerChoices):
        WORKER = 0, _("Работник")
        KOMENDANT = 1, _("Комендант")
        METODIST = 2, _("Методист")
        MASTER = 3, _("Мастер")
        KOMISSAR = 4, _("Комиссар")
        KOMANDIR = 5, _("Командир")

    position = models.IntegerField(
        choices=PositionEnum.choices, verbose_name="Должность"
    )

    boec = models.ForeignKey(
        Boec, on_delete=models.RESTRICT, verbose_name="Боец", related_name="positions"
    )

    brigade = models.ForeignKey(
        Brigade,
        on_delete=models.RESTRICT,
        verbose_name="Отряд",
        related_name="positions",
        null=True,
        blank=True,
    )
    shtab = models.ForeignKey(
        Shtab,
        on_delete=models.RESTRICT,
        verbose_name="Штаб",
        related_name="positions",
        null=True,
        blank=True,
    )
    from_date = models.DateTimeField(default=timezone.now)
    to_date = models.DateTimeField(null=True, blank=True)

    def validate(self, data):
        if not data["brigade"] and not data["shtab"]:
            raise ValidationError(
                {"error": "Either brigade or shtab must have a value."}
            )

    def __str__(self):
        additional_msg = _("Действующий") if (not self.to_date) else ""
        return f"{self.get_position_display()} | {self.boec} | " f"{additional_msg}"


@reversion.register()
class Participant(models.Model):
    """Participant model"""

    class Meta:
        verbose_name = "Участник мероприятия"
        verbose_name_plural = "Участники мероприятия"

    boec = models.ForeignKey(
        Boec,
        on_delete=models.RESTRICT,
        verbose_name="Боец",
        related_name="event_participation",
    )

    event = models.ForeignKey(
        Event,
        on_delete=models.RESTRICT,
        verbose_name="Мероприятие",
        related_name="participant",
    )

    class WorthEnum(models.IntegerChoices):
        DEFAULT = 0, _("Участник")
        VOLONTEER = 1, _("Волонтер")
        ORGANIZER = 2, _("Организатор")

    worth = models.IntegerField(
        choices=WorthEnum.choices,
        verbose_name="Статус участия",
        default=WorthEnum.DEFAULT,
    )

    brigade = models.ForeignKey(
        Brigade,
        on_delete=models.RESTRICT,
        verbose_name="Отряд",
        null=True,
        blank=True,
        related_name="event_participants",
    )
    is_approved = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.boec.last_name} | {self.worth} | {self.event.title}"


@reversion.register()
class EventQuota(models.Model):
    """Number quotas for event participation for a brigade"""

    class Meta:
        verbose_name = "Квота отряда"
        verbose_name_plural = "Квоты отрядов"

    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        verbose_name="Мероприятие",
        related_name="quotas",
    )

    brigade = models.ForeignKey(
        Brigade,
        on_delete=models.RESTRICT,
        verbose_name="Отряд",
        null=True,
        blank=True,
    )

    count = models.IntegerField(verbose_name="Количество мест", null=True, default=None)

    def __str__(self):
        quote_count = f"квот: {self.count}" if self.count is not None else "квот нет"
        return f"{self.brigade} - {self.event}, {quote_count}"


@reversion.register()
class Competition(models.Model):
    """Competition  model"""

    class Meta:
        verbose_name = "Конкурс мероприятия"
        verbose_name_plural = "Конкурсы мероприятий"

    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        verbose_name="Мероприятие",
        related_name="competitions",
    )
    title = models.CharField(max_length=255)
    ratingless = models.BooleanField(default=False)

    def __str__(self):
        return self.title


@reversion.register()
class CompetitionParticipant(models.Model):
    """Competition Participant model"""

    class Meta:
        verbose_name = "Заявка на мероприятие"
        verbose_name_plural = "Заявки на мероприятие"

    competition = models.ForeignKey(
        Competition,
        on_delete=models.CASCADE,
        verbose_name="Конкурс",
        related_name="competition_participation",
    )
    boec = models.ManyToManyField(
        Boec, related_name="competition_participation", blank=True
    )
    # принимаем по факту, что brigades привязывается само и не лезем в бойцы
    brigades = models.ManyToManyField(
        Brigade, related_name="competition_participation", blank=True
    )

    class WorthEnum(models.IntegerChoices):
        DEFAULT = 0, _("Заявка")
        INVOLVEMENT = 1, _("Участие/плей-офф")

    worth = models.IntegerField(
        choices=WorthEnum.choices,
        verbose_name="Статус участника",
        default=WorthEnum.DEFAULT,
    )

    title = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        brigades_title = f"{self.title} "
        for brigade in self.brigades.all():
            brigades_title += f"{brigade.title} | "
        return f"{brigades_title} {self.competition.title} | {self.competition.event.title}"


@reversion.register()
class Nomination(models.Model):
    """Nomination model"""

    class Meta:
        verbose_name = "Номинация"
        verbose_name_plural = "Номинации"

    title = models.CharField(max_length=255)
    competition = models.ForeignKey(
        Competition,
        on_delete=models.CASCADE,
        verbose_name="Конкурс",
        related_name="nominations",
    )

    owner = models.ManyToManyField(
        CompetitionParticipant, related_name="nomination", blank=True
    )

    is_rated = models.BooleanField(default=True)

    sport_place = models.IntegerField(
        verbose_name="Место, если спорт", blank=True, null=True
    )

    def __str__(self):
        return f"{self.title} | {self.competition.title}"


@reversion.register()
class Conference(models.Model):
    """Conference model"""

    class Meta:
        verbose_name = "Конференция"
        verbose_name_plural = "Конференции"

    date = models.DateTimeField(verbose_name="Дата проведения")

    brigades = models.ManyToManyField(Brigade, related_name="conference", blank=True)

    shtabs = models.ManyToManyField(Shtab, related_name="conference", blank=True)

    def __str__(self):
        return f"{self.date} | {self.brigades.count()} отрядов | {self.shtabs.count()} штабов"


@reversion.register()
class Warning(models.Model):
    """Warning model"""

    class Meta:
        verbose_name = "Предупреждение"
        verbose_name_plural = "Предупреждения"

    created_at = models.DateField(default=timezone.now)

    text = models.CharField(max_length=255)

    def __str__(self):
        return self.text


@reversion.register()
class Achievement(models.Model):
    """Achievement model"""

    class Meta:
        verbose_name = "Достижение"
        verbose_name_plural = "Достижения"

    class ActivityEnum(models.TextChoices):
        PARTICIPATION_DEFAULT = (
            "paticipation_count",
            _("Посещение мероприятия"),
        )
        PARTICIPATION_VOLONTEER = (
            "volonteer_count",
            _("Волонтерство"),
        )
        PARTICIPATION_ORGANIZER = (
            "organizer_count",
            _("Организаторство"),
        )
        COMPETITION_DEFAULT = (
            "competition_default",
            _("Подача заявки"),
        )
        COMPETITION_PLAYOFF = (
            "competition_playoff",
            _("Прохождение в плейофф"),
        )
        NOMINATIONS = (
            "nominations",
            _("Номинации"),
        )
        SEASONS = (
            "seasons",
            _("Сезоны"),
        )
        SPORT_WINS = (
            "sport_wins",
            _("Номинация в спорте"),
        )
        ART_WINS = (
            "art_wins",
            _("Номинация в творчестве"),
        )

    type = models.TextField(
        choices=ActivityEnum.choices,
        verbose_name="Тип",
    )

    boec = models.ManyToManyField(Boec, related_name="achievements", blank=True)

    created_at = models.DateField(default=timezone.now)

    title = models.TextField(max_length=255)
    description = models.TextField(max_length=255)

    goal = models.IntegerField(verbose_name="Цель")

    def __str__(self):
        return f"{self.title} | Обладателей: {self.boec.count()}"


@reversion.register()
class Activity(models.Model):
    """Activity model"""

    class Meta:
        verbose_name = "Уведомление"
        verbose_name_plural = "Уведомления"

    class ActivityEnum(models.IntegerChoices):
        INFO = 0, _("Информация")
        WARNING = 1, _("Предупреждение")
        NEW_ACHIEVEMENT = 2, _("Достижение")

    type = models.IntegerField(
        choices=ActivityEnum.choices,
        verbose_name="Тип",
        default=ActivityEnum.INFO,
    )

    boec = models.ForeignKey(
        Boec,
        on_delete=models.RESTRICT,
        verbose_name="Боец",
        related_name="activities",
    )

    created_at = AutoDateTimeField(default=timezone.now)

    warning = models.ForeignKey(
        Warning,
        on_delete=models.RESTRICT,
        verbose_name="Предупреждение",
        related_name="activities",
        blank=True,
        null=True,
    )

    achievement = models.ForeignKey(
        Achievement,
        on_delete=models.RESTRICT,
        verbose_name="Достижение",
        related_name="activities",
        blank=True,
        null=True,
    )

    seen = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.get_type_display()} | {self.boec} | {self.warning or self.achievement} "
