"""app URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from core.admin import LoginForm
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions

admin.autodiscover()
admin.site.login_form = LoginForm
admin.site.login_template = "core/templates/admin/login.html"

schema_view = get_schema_view(
    openapi.Info(
        title="SO API",
        default_version="v1",
        description="Welcome to the world of SPbSO",
        terms_of_service="https://so.spb.ru",
        contact=openapi.Contact(email="admin@so.spb.ru"),
        license=openapi.License(name="Awesome API"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    re_path(
        r"^doc(?P<format>\.json|\.yaml)$",
        schema_view.without_ui(cache_timeout=0),
        name="schema-json",
    ),
    path(
        "doc/",
        schema_view.with_ui("swagger", cache_timeout=0),
        name="schema-swagger-ui",
    ),
    path("redoc/", schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"),
    path("admin/", admin.site.urls),
    path("api/", include("user.urls")),
    path("api/so/", include("so.urls")),
    path("api/", include("event.urls")),
    path("api/", include("voting.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
