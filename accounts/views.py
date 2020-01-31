from django.shortcuts import redirect, reverse
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.mixins import UserPassesTestMixin
from django.views.generic import TemplateView, UpdateView

from .models import Profile
from .forms import ProfileForm
from pdf_output.models import Signature
from decouple import config
import stripe
import os
import datetime
from flights.views import LoginRequiredMixin


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
            context['STRIPE_PUBLISHABLE_KEY'] = config(
                'STRIPE_TEST_PUBLISHABLE_KEY')
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

        try:
            signature = Signature.objects.filter(user=user).latest()
            context['signature'] = signature
        except ObjectDoesNotExist:
            context['signature'] = False

        context['profile'] = Profile.objects.get(user=user)
        context['customer_id'] = profile.customer_id
        context['user_email'] = str(user.email)
        context['title'] = "D-> | Profile"
        context['parent_name'] = 'Home'
        context['parent_link'] = reverse('home')
        context['page_title'] = 'Profile'

        return context


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
