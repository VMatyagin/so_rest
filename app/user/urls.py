from django.urls import include, path
from rest_framework.routers import SimpleRouter
from so.views import BoecProgress
from user import views

app_name = "user"

router = SimpleRouter()

urlpatterns = [
    path("me/", views.ManangeUserView.as_view(), name="me"),
    path("activity/", views.ActivityView.as_view({"get": "retrieve"}), name="activity"),
    path(
        "activity/markAsRead",
        views.ActivityView.as_view({"post": "markAsRead"}),
        name="activity",
    ),
    path(
        "me/achievements/",
        views.AchievementsView.as_view({"get": "list"}),
        name="achievements",
    ),
    path("me/progress/", BoecProgress.as_view({"get": "list"}), name="progress"),
]
