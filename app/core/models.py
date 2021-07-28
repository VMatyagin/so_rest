import os
import uuid

import reversion
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.contrib.humanize.templatetags.humanize import naturaltime
from django.db import models
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
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
    def create_user(self, vkId, password=None, **extra_fields):
        """creates and saves a new user"""
        if not vkId:
            raise ValueError("Users must have an vkId")
        user = self.model(vkId=vkId, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)

        return user

    def create_superuser(self, vkId, password=None):
        """creates and save a new super user"""
        if not password:
            raise ValueError("SuperUsers must have password")
        user = self.create_user(vkId=vkId, password=password)
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

    vkId = models.IntegerField(unique=True)

    name = models.CharField(max_length=255, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateField(default=timezone.now)
    updated_at = AutoDateTimeField(default=timezone.now)
    password = models.CharField(max_length=128, blank=True)

    objects = UserManager()

    USERNAME_FIELD = "vkId"

    def __str__(self):
        return f"{self.vkId}"


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
    shortTitle = models.CharField(max_length=10)
    created_at = models.DateField(default=timezone.now)
    updated_at = AutoDateTimeField(default=timezone.now)

    @property
    def brigades_count(self):
        return self.brigades.count()

    def __str__(self):
        return self.shortTitle


@reversion.register()
class Boec(models.Model):
    """Boec object"""

    class Meta:
        verbose_name = "Боец"
        verbose_name_plural = "Бойцы"

    firstName = models.CharField(max_length=255)
    lastName = models.CharField(max_length=255)
    middleName = models.CharField(max_length=255, blank=True)
    DOB = models.DateField(null=True, blank=True)
    created_at = models.DateField(default=timezone.now)
    updated_at = AutoDateTimeField(default=timezone.now)
    vkId = models.IntegerField(verbose_name="VK id", blank=True, null=True, unique=True)
    unreadActivityCount = models.IntegerField(default=0)
    telegram_id = models.IntegerField(
        verbose_name="Telegram ID", null=True, unique=True, blank=True
    )

    def __str__(self):
        return f"{self.lastName} {self.firstName} {self.middleName}"


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
    DOB = models.DateTimeField(null=True, blank=True)
    created_at = models.DateField(default=timezone.now)
    updated_at = AutoDateTimeField(default=timezone.now)

    def __str__(self):
        return self.title


class EventWorth(models.IntegerChoices):
    UNSET = 0, _("Не учитывается")
    ART = 1, _("Творчество")
    SPORT = 2, _("Спорт")
    VOLONTEER = 3, _("Волонтерство")
    CITY = 4, _("Городское")


@reversion.register()
class Event(models.Model):
    """Event model"""

    class Meta:
        verbose_name = "Мероприятие"
        verbose_name_plural = "Мероприятия"

    class EventStatus(models.IntegerChoices):
        JUST_CREATED = 0, _("Мероприятие создано")
        PASSED = 1, _("Мероприятие прошло")
        NOT_PASSED = 2, _("Мероприятие не прошло")

    status = models.IntegerField(
        choices=EventStatus.choices,
        default=EventStatus.JUST_CREATED,
        verbose_name="Статус мероприятия",
    )
    worth = models.IntegerField(
        choices=EventWorth.choices,
        default=EventWorth.UNSET,
        verbose_name="Ценность блоков",
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
    startDate = models.DateTimeField(verbose_name="Дата начала")
    startTime = models.TimeField(null=True, blank=True, verbose_name="Время начала")

    visibility = models.BooleanField(default=False, verbose_name="Видимость")
    isCanonical = models.BooleanField(default=False, verbose_name="Каноничность")

    isTicketed = models.BooleanField(default=False, verbose_name="Вход по билетам")

    def __str__(self):
        return self.title


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

    createdAt = models.DateTimeField(auto_now_add=True)
    updatedAt = models.DateTimeField(auto_now=True)

    def generate_uuid(self) -> str:
        self.uuid = uuid.uuid4()
        self.save()
        return str(self.uuid)

    @property
    def is_used(self) -> bool:
        """Checks whether there's a final ticket scan for this ticket"""
        return self.ticket_scans.filter(isFinal=True).exists()

    def last_scan(self) -> "TicketScan":
        return self.ticket_scans.order_by("createdAt").last()

    def last_valid_scan(self) -> "TicketScan":
        return self.ticket_scans.filter(isFinal=True).order_by("createdAt").last()

    def scan(self):
        if self.is_used:
            raise UsedTicketScanException("Ticket has already been used")
        self.ticket_scans.create(isFinal=True)

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

    isFinal = models.BooleanField(default=True, verbose_name="Проверен")

    createdAt = models.DateTimeField(auto_now_add=True)
    updatedAt = models.DateTimeField(auto_now=True)

    @property
    def is_final(self) -> str:
        return "Проверен" if self.isFinal else "Предъявлен"

    def __str__(self) -> str:
        return (
            f"{self.ticket.boec} — {self.ticket.event} — "
            f"{self.is_final} {naturaltime(self.createdAt)}"
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

    isAccepted = models.BooleanField(default=False, verbose_name="Подтвержден")
    isCandidate = models.BooleanField(default=True, verbose_name="Не стал бойцом")

    def __str__(self):
        return f"{self.year} - {self.brigade.title} {self.boec.lastName}"


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
    fromDate = models.DateTimeField(default=timezone.now)
    toDate = models.DateTimeField(null=True, blank=True)

    def validate(self, data):
        if not data["brigade"] and not data["shtab"]:
            raise ValidationError(
                {"error": "Even one of brigade or shtab should have a value."}
            )

    def __str__(self):
        additionalMsg = _("Действующий") if (not self.toDate) else ""
        return f"{self.get_position_display()} | {self.boec} | " f"{additionalMsg}"


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
    )
    isApproved = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.boec.lastName} | {self.worth} | {self.event.title}"


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

    isRated = models.BooleanField(default=True)

    sportPlace = models.IntegerField(
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
    """NotificaAchievementtions model"""

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
