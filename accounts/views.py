from django.shortcuts import reverse
from django.contrib.auth.models import User
from django.views.generic import UpdateView
from allauth.account.views import EmailView, PasswordSetView, PasswordChangeView, PasswordResetView, PasswordResetDoneView, PasswordResetFromKeyView, PasswordResetFromKeyDoneView
from allauth.socialaccount.views import ConnectionsView
from accounts.forms import UserForm
from django.contrib.auth.mixins import LoginRequiredMixin


class LoginRequiredMixin(LoginRequiredMixin):
    login_url = '/accounts/login'
    # redirect_field_name = None


class UserUpdateView(LoginRequiredMixin, UpdateView):

    def get_context_data(self, **kwargs):
        context = super(UserUpdateView, self).get_context_data(**kwargs)

        context['title'] = "D-> | Update Name"
        context['parent_name'] = 'Profile'
        context['parent_link'] = reverse('profile')
        context['page_title'] = 'Update Name'
        return context

    model = User
    form_class = UserForm
    template_name = 'profile/user_update.html'
    success_url = '/accounts/profile/'


# Views from allauth
class EmailView(LoginRequiredMixin, EmailView):

    def get_context_data(self, **kwargs):
        context = super(EmailView, self).get_context_data(**kwargs)

        context['title'] = "D-> | Update Email"
        context['home_link'] = reverse('home')
        context['parent_name'] = 'Profile'
        context['parent_link'] = reverse('profile')
        context['page_title'] = 'Update Email'
        return context


class ConnectionsView(LoginRequiredMixin, ConnectionsView):

    def get_context_data(self, **kwargs):
        context = super(ConnectionsView, self).get_context_data(**kwargs)

        context['title'] = "D-> | Update Social Accounts"
        context['home_link'] = reverse('home')
        context['parent_name'] = 'Profile'
        context['parent_link'] = reverse('profile')
        context['page_title'] = 'Update Social Accounts'
        return context


class PasswordSetView(LoginRequiredMixin, PasswordSetView):

    def get_context_data(self, **kwargs):
        context = super(PasswordSetView, self).get_context_data(**kwargs)

        context['title'] = "D-> | Password Set"
        context['home_link'] = reverse('home')
        context['parent_name'] = 'Profile'
        context['parent_link'] = reverse('profile')
        context['page_title'] = 'Password Set'
        return context


class PasswordChangeView(LoginRequiredMixin, PasswordChangeView):

    def get_context_data(self, **kwargs):
        context = super(PasswordChangeView, self).get_context_data(**kwargs)

        context['title'] = "D-> | Password Change"
        context['home_link'] = reverse('home')
        context['parent_name'] = 'Profile'
        context['parent_link'] = reverse('profile')
        context['page_title'] = 'Passsword Change'
        return context


class PasswordResetView(LoginRequiredMixin, PasswordResetView):

    def get_context_data(self, **kwargs):
        context = super(PasswordResetView, self).get_context_data(**kwargs)

        context['title'] = "D-> | Password Reset"
        context['home_link'] = reverse('home')
        context['parent_name'] = 'Profile'
        context['parent_link'] = reverse('profile')
        context['page_title'] = 'Password Reset'
        return context


class PasswordResetDoneView(LoginRequiredMixin, PasswordResetDoneView):

    def get_context_data(self, **kwargs):
        context = super(PasswordResetDoneView, self).get_context_data(**kwargs)

        context['title'] = "D-> | Password Reset"
        context['home_link'] = reverse('home')
        context['parent_name'] = 'Profile'
        context['parent_link'] = reverse('profile')
        context['page_title'] = 'Password Reset'
        return context


class PasswordResetFromKeyView(LoginRequiredMixin, PasswordResetFromKeyView):

    def get_context_data(self, **kwargs):
        context = super(PasswordResetFromKeyView,
                        self).get_context_data(**kwargs)

        context['title'] = "D-> | Change Password"
        context['home_link'] = reverse('home')
        context['parent_name'] = 'Profile'
        context['parent_link'] = reverse('profile')
        context['page_title'] = 'Change Password'
        return context


class PasswordResetFromKeyDoneView(LoginRequiredMixin, PasswordResetFromKeyDoneView):

    def get_context_data(self, **kwargs):
        context = super(PasswordResetFromKeyView,
                        self).get_context_data(**kwargs)

        context['title'] = "D-> | Password Changed"
        context['home_link'] = reverse('home')
        context['parent_name'] = 'Profile'
        context['parent_link'] = reverse('profile')
        context['page_title'] = 'Password Changed'
        return context
