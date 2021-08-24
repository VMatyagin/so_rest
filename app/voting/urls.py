from django.urls import include, path
from rest_framework.routers import SimpleRouter
from voting import views

router = SimpleRouter()

router.register(r"voting", views.VotingViewSet)

app_name = "voting"

urlpatterns = [
    path("", include(router.urls)),
]
