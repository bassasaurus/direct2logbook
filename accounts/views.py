
from django.contrib.auth import login, authenticate
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import render, redirect, reverse

from django.contrib.auth import login, authenticate
from django.contrib.auth.models import User

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView, UpdateView

from accounts.models import Profile
from accounts.forms import ProfileForm, UserForm

from allauth.account.views import EmailView, PasswordSetView, PasswordChangeView, PasswordResetView, PasswordResetDoneView, PasswordResetFromKeyView, PasswordResetFromKeyDoneView
from allauth.socialaccount.views import ConnectionsView
from decouple import config
import stripe
import os
import datetime


class LoginRequiredMixin(LoginRequiredMixin):
    login_url = '/accounts/login'
    # redirect_field_name = None


class OwnObjectUserMixin(UserPassesTestMixin):

    def test_func(self):
        object = self.get_object()
        if self.request.user.pk == object.pk:
            return True
        else:
            return False

    def handle_no_permission(self):

        return redirect(reverse('profile'))


class OwnObjectProfileMixin(UserPassesTestMixin):

    def test_func(self):
        object = self.get_object()
        if self.request.user.pk == object.user.pk:
            return True
        else:
            return False

    def handle_no_permission(self):

        return redirect(reverse('profile'))


class ProfileView(LoginRequiredMixin, TemplateView):
    model = Profile
    template_name = 'profile/profile.html'

    def session_monthly(self, customer_id):

        if os.environ.get('DJANGO_DEVELOPMENT_SETTINGS'):
            plan_monthly = 'plan_FZhtfxftM44uHz'
        else:
            plan_monthly = 'plan_FZi0hBf46jbYVt'

        user = self.request.user
        session_monthly = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=['card'],
            subscription_data={
                'items': [{
                    'plan': plan_monthly,
                }],
            },
            success_url='https://www.direct2logbook.com/payments/success/{}'.format(
                user.pk),
            cancel_url='https://www.direct2logbook.com/payments/cancel/{}'.format(
                user.pk),
            # success_url='http://localhost:8000/payments/success/{}'.format(user.pk),
            # cancel_url='http://localhost:8000/payments/cancel/{}'.format(user.pk),
        )

        return session_monthly.id

    def session_yearly(self, customer_id):

        if os.environ.get('DJANGO_DEVELOPMENT_SETTINGS'):
            plan_yearly = 'plan_FaRGVsApeXu8bS'
        else:
            plan_yearly = 'plan_FbBfx5Pbam2QRa'

        user = self.request.user
        session_yearly = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=['card'],
            subscription_data={
                'items': [{
                    'plan': plan_yearly,
                }],
            },
            success_url='https://www.direct2logbook.com/payments/success/{}'.format(
                user.pk),
            cancel_url='https://www.direct2logbook.com/payments/cancel/{}'.format(
                user.pk),
            # success_url='http://localhost:8000/payments/success/{}'.format(user.pk),
            # cancel_url='http://localhost:8000/payments/cancel/{}'.format(user.pk),
        )

        return session_yearly.id

    def get_context_data(self, **kwargs):
        context = super(ProfileView, self).get_context_data(**kwargs)
        user = self.request.user
        profile = Profile.objects.get(user=user)

        if os.environ.get('DJANGO_DEVELOPMENT_SETTINGS'):
            context['STRIPE_PUBLISHABLE_KEY'] = config('STRIPE_TEST_PUBLISHABLE_KEY')
            context['CHECKOUT_SESSION_ID_MONTHLY'] = 'cus_Fkerl0ew4MHGjD'
            context['CHECKOUT_SESSION_ID_YEARLY'] = 'cus_Fkerl0ew4MHGjD'
        else:
            context['STRIPE_PUBLISHABLE_KEY'] = config('STRIPE_LIVE_PUBLISHABLE_KEY')
            context['CHECKOUT_SESSION_ID_MONTHLY'] = self.session_monthly(profile.customer_id)
            context['CHECKOUT_SESSION_ID_YEARLY'] = self.session_yearly(profile.customer_id)

        today = datetime.datetime.now()

        if today.date() < profile.end_date:
            context['passed_end_date'] = False
        else:
            context['passed_end_date'] = True
        context['profile'] = Profile.objects.get(user=user)
        context['customer_id'] = profile.customer_id
        context['user_email'] = str(user.email)
        context['title'] = "D-> | Profile"
        context['parent_name'] = 'Home'
        context['parent_link'] = reverse('home')
        context['page_title'] = 'Profile'

        return context


class UserUpdateView(LoginRequiredMixin, OwnObjectUserMixin, UpdateView):

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


class ProfileUpdateView(LoginRequiredMixin, OwnObjectProfileMixin, UpdateView):

    def get_context_data(self, **kwargs):
        context = super(ProfileUpdateView, self).get_context_data(**kwargs)

        context['title'] = "D-> | Update Profile"
        context['parent_name'] = 'Profile'
        context['parent_link'] = reverse('profile')
        context['page_title'] = 'Update Profile'
        context['home_link'] = reverse('home')
        return context

    model = Profile
    form_class = ProfileForm
    template_name = 'profile/profile_update.html'
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
