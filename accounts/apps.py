from django.apps import AppConfig


class AuthenticationConfig(AppConfig):
    name = 'accounts'

    def ready(self):
        from . import signals  # noqa: F401
