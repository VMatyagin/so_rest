import os
from base64 import b64encode
from hashlib import sha256
from hmac import HMAC
from urllib.parse import parse_qsl, urlencode, urlparse

from django.contrib.auth import get_user_model
from django.utils.translation import ugettext_lazy as _
from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication, get_authorization_header

# Защищённый ключ из настроек вашего приложения
client_secret = os.environ.get("VK_CLIENT_SECRET")


def is_valid(query: dict, secret: str) -> bool:
    """

    Check VK Apps signature

    :param dict query: Словарь с параметрами запуска
    :param str secret: Секретный ключ приложения ("Защищённый ключ")
    :returns: Результат проверки подписи
    :rtype: bool

    """
    if not query.get("sign"):
        return False

    vk_subset = sorted(filter(lambda key: key.startswith("vk_"), query))

    if not vk_subset:
        return False

    ordered = {k: query[k] for k in vk_subset}

    hash_code = b64encode(
        HMAC(secret.encode(), urlencode(ordered, doseq=True).encode(), sha256).digest()
    ).decode("utf-8")

    if hash_code[-1] == "=":
        hash_code = hash_code[:-1]

    fixed_hash = hash_code.replace("+", "-").replace("/", "_")
    return query.get("sign") == fixed_hash


class VKAuthentication(BaseAuthentication):
    """
    Authentication based on vk sign keys.

    Clients should authenticate by passing the current location "Authorization"
    HTTP header.  For example:
        Authorization: vk_user_id=494075&vk_app_id=6736218&vk_is_app_user=1&vk_are_notifications_enabled=1&vk_language=ru&vk_access_token_settings=&vk_platform=android&sign=htQFduJpLxz7ribXRZpDFUH-XEUhC9rBPTJkjUFEkRA # NOQA
    """

    keyword = ""

    def authenticate(self, request):
        auth = get_authorization_header(request).split()
        if len(auth) != 1:
            msg = _("Invalid token header")
            raise exceptions.AuthenticationFailed(msg)

        try:
            query_params = dict(
                parse_qsl(urlparse(auth[0].decode()).path, keep_blank_values=True)
            )
        except UnicodeError:
            msg = _(
                "Invalid token header. "
                "Token string should not contain invalid characters."
            )
            raise exceptions.AuthenticationFailed(msg)

        return self.authenticate_credentials(query_params)

    def authenticate_credentials(self, query_params):
        is_sign_validated = is_valid(query=query_params, secret=client_secret)
        if not is_sign_validated:
            raise exceptions.AuthenticationFailed(_("Sign is not valid."))
        try:
            user = get_user_model().objects.get(vkId=query_params.get("vk_user_id"))
            if not user.is_active:
                raise exceptions.AuthenticationFailed(_("User inactive or deleted."))
        except get_user_model().DoesNotExist:
            user = get_user_model().objects.create(vkId=query_params.get("vk_user_id"))

        return (user, query_params.get("vk_user_id"))

    def authenticate_header(self, request):
        return self.keyword
