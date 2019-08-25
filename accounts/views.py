
from django.contrib.auth import login, authenticate
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import render, redirect, reverse

from django.contrib.auth import login, authenticate
from django.contrib.auth.models import User

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, UpdateView

from accounts.models import Profile
from accounts.forms import ProfileForm, UserForm

from allauth.account.views import EmailView, PasswordSetView, PasswordChangeView, PasswordResetView, PasswordResetDoneView, PasswordResetFromKeyView, PasswordResetFromKeyDoneView
from allauth.socialaccount.views import ConnectionsView
from decouple import config
import stripe

class LoginRequiredMixin(LoginRequiredMixin):
    login_url = '/accounts/login'
    # redirect_field_name = None

class UserObjectsMixin():

    def get_queryset(self):
        user = self.request.user
        return super(UserObjectsMixin, self).get_queryset().filter(user=user)

class ProfileView(LoginRequiredMixin, UserObjectsMixin, TemplateView):
    model = Profile
    template_name='profile/profile.html'

    def session_monthly(self, customer_id):
        session_monthly = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=['card'],
            subscription_data={
                'items': [{
                'plan': 'plan_FZhtfxftM44uHz',
                }],
            },
        success_url='https://www.direct2logbook.com/payments/success',
        cancel_url='https://www.direct2logbook.com/payments/cancel',
        )

        return session_monthly.id

    def session_yearly(self, customer_id):
        session_yearly = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=['card'],
            subscription_data={
                'items': [{
                'plan': 'plan_FaRGVsApeXu8bS',
                }],
            },
        success_url='https://www.direct2logbook.com/payments/success',
        cancel_url='https://www.direct2logbook.com/payments/cancel',
        )

        return session_yearly.id

    def get_context_data(self, **kwargs):
        context = super(ProfileView, self).get_context_data(**kwargs)
        user = self.request.user
        customer_id = Profile.objects.get(user=user).customer_id

        context['STRIPE_TEST_PUBLISHABLE_KEY'] = config('STRIPE_TEST_PUBLISHABLE_KEY')
        context['CHECKOUT_SESSION_ID_MONTHLY'] = self.session_monthly(customer_id)
        context['CHECKOUT_SESSION_ID_YEARLY'] = self.session_yearly(customer_id)
        context['profile'] = Profile.objects.get(user=user)
        context['customer_id'] = customer_id
        context['user_email'] = str(user.email)
        context['title'] = "D-> | Profile"
        context['parent_name'] = 'Home'
        context['parent_link'] = reverse('home')
        context['page_title'] = 'Profile'

        return context

class UserUpdateView(UpdateView):

    def get_context_data(self, **kwargs):
        context = super(UserUpdateView, self).get_context_data(**kwargs)

        user = self.request.user
        pk = str(user.profile.pk)

        context['title'] = "D-> | Update Name"
        context['parent_name'] = 'Profile'
        context['parent_link'] = reverse('profile')
        context['page_title'] = 'Update Name'
        return context

    model = User
    form_class = UserForm
    template_name = 'profile/user_update.html'
    success_url = '/accounts/profile/'


class ProfileUpdateView(UpdateView):

    def get_context_data(self, **kwargs):
        context = super(ProfileUpdateView, self).get_context_data(**kwargs)

        user = self.request.user
        pk = str(user.profile.pk)

        context['title'] = "D-> | Update Profile"
        context['parent_name'] = 'Profile'
        context['parent_link'] = reverse('profile')
        context['page_title'] = 'Update Profile'
        return context

    model = Profile
    form_class = ProfileForm
    template_name = 'profile/profile_update.html'
    success_url = '/accounts/profile/'


# Views from allauth
class EmailView(EmailView):

    def get_context_data(self, **kwargs):
        context = super(EmailView, self).get_context_data(**kwargs)

        context['title'] = "D-> | Update Email"
        context['home_link'] = reverse('home')
        context['parent_name'] = 'Profile'
        context['parent_link'] = reverse('profile')
        context['page_title'] = 'Update Email'
        return context

class ConnectionsView(ConnectionsView):

    def get_context_data(self, **kwargs):
        context = super(ConnectionsView, self).get_context_data(**kwargs)

        context['title'] = "D-> | Update Social Accounts"
        context['home_link'] = reverse('home')
        context['parent_name'] = 'Profile'
        context['parent_link'] = reverse('profile')
        context['page_title'] = 'Update Social Accounts'
        return context

class PasswordSetView(PasswordSetView):

    def get_context_data(self, **kwargs):
        context = super(PasswordSetView, self).get_context_data(**kwargs)

        context['title'] = "D-> | Password Set"
        context['home_link'] = reverse('home')
        context['parent_name'] = 'Profile'
        context['parent_link'] = reverse('profile')
        context['page_title'] = 'Password Set'
        return context

class PasswordChangeView(PasswordChangeView):

    def get_context_data(self, **kwargs):
        context = super(PasswordChangeView, self).get_context_data(**kwargs)

        context['title'] = "D-> | Password Change"
        context['home_link'] = reverse('home')
        context['parent_name'] = 'Profile'
        context['parent_link'] = reverse('profile')
        context['page_title'] = 'Passsword Change'
        return context

class PasswordResetView(PasswordResetView):

    def get_context_data(self, **kwargs):
        context = super(PasswordResetView, self).get_context_data(**kwargs)

        context['title'] = "D-> | Password Reset"
        context['home_link'] = reverse('home')
        context['parent_name'] = 'Profile'
        context['parent_link'] = reverse('profile')
        context['page_title'] = 'Password Reset'
        return context

class PasswordResetDoneView(PasswordResetDoneView):

    def get_context_data(self, **kwargs):
        context = super(PasswordResetDoneView, self).get_context_data(**kwargs)

        context['title'] = "D-> | Password Reset"
        context['home_link'] = reverse('home')
        context['parent_name'] = 'Profile'
        context['parent_link'] = reverse('profile')
        context['page_title'] = 'Password Reset'
        return context

class PasswordResetFromKeyView(PasswordResetFromKeyView):

    def get_context_data(self, **kwargs):
        context = super(PasswordResetFromKeyView, self).get_context_data(**kwargs)

        context['title'] = "D-> | Change Password"
        context['home_link'] = reverse('home')
        context['parent_name'] = 'Profile'
        context['parent_link'] = reverse('profile')
        context['page_title'] = 'Change Password'
        return context

class PasswordResetFromKeyDoneView(PasswordResetFromKeyDoneView):

    def get_context_data(self, **kwargs):
        context = super(PasswordResetFromKeyView, self).get_context_data(**kwargs)

        context['title'] = "D-> | Password Changed"
        context['home_link'] = reverse('home')
        context['parent_name'] = 'Profile'
        context['parent_link'] = reverse('profile')
        context['page_title'] = 'Password Changed'
        return context
