from django.contrib.auth.mixins import UserPassesTestMixin
from django.views import View
from profile.models import Profile
from django.shortcuts import redirect, reverse, render


def error_400(request, exception):
    context = {
        'title': '400',
        'home_link': reverse('home')
    }
    return render(request, 'errors/400.html', context)


def error_404(request, exception):
    context = {
        'title': '404',
        'home_link': reverse('home')
    }
    return render(request, 'errors/404.html', context)


def error_500(request):
    context = {
        'title': '500',
        'home_link': reverse('home')
    }
    return render(request, 'errors/500.html', context)


def error_403(request, exception):
    context = {
        'title': '403',
        'home_link': reverse('home'),
        'exception': exception
    }
    return render(request, 'errors/403.html', context)


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
