from allauth.account.adapter import DefaultAccountAdapter
from django.urls import reverse
from profile.models import Profile


class AccountAdapter(DefaultAccountAdapter):
    def populate_username(self, request, user):
        if not user.username:
            first = user.first_name.strip()
            last = user.last_name.strip()
            base = first[:1] + last if first and last else first or last or user.email.split('@')[0]
            user.username = self.generate_unique_username([base])

    def post_login(self, request, user, **kwargs):
        # Apply after allauth completes authentication and verification, including social login.
        profile = Profile.objects.filter(user=user).first()
        has_access = profile and (profile.free_access or profile.trial or (profile.active and not profile.expired))
        kwargs['redirect_url'] = reverse('home' if has_access else 'profile')
        return super().post_login(request, user, **kwargs)
