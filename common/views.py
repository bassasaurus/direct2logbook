from django.contrib.auth.mixins import UserPassesTestMixin
from django.views import View
from profile.views import Profile
from django.shortcuts import redirect, reverse


class ProfileNotActiveMixin(UserPassesTestMixin, View):

    def test_func(self):

        user = self.request.user

        profile = Profile.objects.get(user=user)

        if profile.active and not profile.expired:

            return True

        else:
            return False

    def handle_no_permission(self):

        return redirect(reverse('profile'))
