from django.urls import reverse_lazy
from django.shortcuts import redirect, reverse
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.mixins import UserPassesTestMixin
from django.views.generic import TemplateView, UpdateView
from .models import Profile
from .forms import ProfileForm
import stripe
import datetime
from accounts.views import LoginRequiredMixin
from logbook import settings
from django.views import View
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from signature.models import Signature
import base64


class ProfileNotActiveMixin(UserPassesTestMixin, View):

    def test_func(self):

        user = self.request.user
        profile = Profile.objects.get(user=user)

        if profile.active and not profile.expired:
            return True
        elif profile.trial:
            return True
        else:
            return False

    def handle_no_permission(self):

        return redirect(reverse('profile'))


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

        plan_monthly = settings.PLAN_MONTHLY

        user = self.request.user

        session_monthly = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=['card'],
            subscription_data={
                'items': [{
                    'plan': plan_monthly,
                }],
            },
            success_url=self.request.build_absolute_uri(reverse('payment_success', args=[user.pk])),
            cancel_url=self.request.build_absolute_uri(reverse('payment_canceled', args=[user.pk])),
        )

        return session_monthly.id

    def session_yearly(self, customer_id):

        plan_yearly = settings.PLAN_YEARLY

        user = self.request.user

        session_yearly = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=['card'],
            subscription_data={
                'items': [{
                    'plan': plan_yearly,
                }],
            },
            success_url=self.request.build_absolute_uri(reverse('payment_success', args=[user.pk])),
            cancel_url=self.request.build_absolute_uri(reverse('payment_canceled', args=[user.pk])),
        )

        return session_yearly.id

    def get_context_data(self, **kwargs):
        context = super(ProfileView, self).get_context_data(**kwargs)
        user = self.request.user
        profile = Profile.objects.get(user=user)

        billing_ready = bool(
            profile.customer_id and profile.subscription_id and profile.end_date
        )
        context['billing_pending'] = not billing_ready
        context['STRIPE_PUBLISHABLE_KEY'] = settings.STRIPE_PUBLISHABLE_KEY
        context['passed_end_date'] = bool(
            profile.end_date and datetime.date.today() >= profile.end_date
        )

        if billing_ready and not profile.free_access:
            stripe.api_key = settings.STRIPE_SECRET_KEY
            context['CHECKOUT_SESSION_ID_MONTHLY'] = self.session_monthly(
                profile.customer_id)
            context['CHECKOUT_SESSION_ID_YEARLY'] = self.session_yearly(
                profile.customer_id)

        try:
            signature = Signature.objects.get(user=user)
        except:
            signature = None

        context['signature'] = signature
        context['profile'] = profile
        context['customer_id'] = profile.customer_id
        context['user_email'] = str(user.email)
        context['title'] = "D-> | Profile"
        context['parent_name'] = 'Home'
        context['parent_link'] = reverse('home')
        context['page_title'] = 'Profile'

        return context


@method_decorator(never_cache, name='dispatch')
class BillingStatusView(LoginRequiredMixin, View):
    def get(self, request):
        profile = Profile.objects.get(user=request.user)
        ready = profile.free_access or bool(
            profile.customer_id and profile.subscription_id and profile.end_date
        )
        return JsonResponse({'ready': ready})


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
    success_url = reverse_lazy('profile')
