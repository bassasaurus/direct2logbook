from allauth.account.adapter import DefaultAccountAdapter
from django.urls import reverse
from profile.models import Profile
from profile.access import has_logbook_access


class AccountAdapter(DefaultAccountAdapter):
    def populate_username(self, request, user):
        if not user.username:
            first = user.first_name.strip()
            last = user.last_name.strip()
            base = first[:1] + last if first and last else first or last or user.email.split('@')[0]
            user.username = self.generate_unique_username([base])

    def add_message(self, request, level, message_template=None, message_context=None, extra_tags='', message=None):
        if message_template == 'account/messages/logged_in.txt':
            extra_tags = (extra_tags + ' account-welcome-back').strip()
        return super().add_message(request, level, message_template=message_template,
            message_context=message_context, extra_tags=extra_tags, message=message)

    def post_login(self, request, user, **kwargs):
        # Apply after allauth completes authentication and verification, including social login.
        profile = Profile.objects.filter(user=user).first()
        has_access = has_logbook_access(profile)
        kwargs['redirect_url'] = reverse('home' if has_access else 'profile')
        return super().post_login(request, user, **kwargs)
