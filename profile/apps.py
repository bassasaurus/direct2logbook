from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = 'profile'

    def ready(self):
        import profile.signal_profile
