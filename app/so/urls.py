from django.urls import include, path
from rest_framework.routers import SimpleRouter
from rest_framework_nested import routers
from so import views
from so.views import BoecTelegramView, BoecViewSet

router = SimpleRouter()

router.register(r"shtab", views.ShtabViewSet)
router.register("boec", views.BoecViewSet)
router.register(r"brigade", views.BrigadeViewSet)

brigade_router = routers.NestedSimpleRouter(router, r"brigade", lookup="brigade")
brigade_router.register(
    r"positions", views.SubjectPositions, basename="brigade-positions"
)
brigade_router.register(r"seasons", views.BrigadeSeasons, basename="brigade-seasons")

shtab_router = routers.NestedSimpleRouter(router, r"shtab", lookup="shtab")
shtab_router.register(r"positions", views.SubjectPositions, basename="shtab-positions")

boec_router = routers.NestedSimpleRouter(router, r"boec", lookup="boec")
boec_router.register(r"positions", views.BoecPositions, basename="boec-positions")
boec_router.register(r"seasons", views.BoecSeasons, basename="boec-seasons")
boec_router.register(r"history", views.BoecParticipantHistory, basename="boec-history")
boec_router.register(r"progress", views.BoecProgress, basename="boec-progress")

router.register(r"conference", views.ConferenceViewSet)

router.register("season", views.SeasonViewSet)

app_name = "so"

urlpatterns = [
    path("", include(router.urls)),
    path("", include(brigade_router.urls)),
    path("", include(shtab_router.urls)),
    path("", include(boec_router.urls)),
    path(
        "telegram_link/<int:vk_id>/<int:telegram_id>",
        BoecTelegramView.as_view({"put": "telegram_link"}),
        name="telegram_link",
    ),
]
