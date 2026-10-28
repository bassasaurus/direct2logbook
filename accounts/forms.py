from django.conf import settings
from django import forms
from django.contrib.auth.models import User
from allauth.account.forms import SignupForm
from allauth.socialaccount.forms import SignupForm as SocialSignupForm

from django_recaptcha.fields import ReCaptchaField, ReCaptchaV2Checkbox
from decouple import config


class CustomSignupForm(SignupForm):
    first_name = forms.CharField(max_length=30, label='First Name')
    last_name = forms.CharField(max_length=30, label='Last Name')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not settings.DEBUG:
            self.fields['captcha'] = ReCaptchaField(
                public_key=config('RECAPTCHA_PUBLIC_KEY'),
                private_key=config('RECAPTCHA_PRIVATE_KEY'),
                widget=ReCaptchaV2Checkbox()
            )

    def signup(self, request, user):
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.save()
        return user


class GoogleSignupForm(SocialSignupForm):
    first_name = forms.CharField(max_length=30, label='First Name')
    last_name = forms.CharField(max_length=30, label='Last Name')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial['first_name'] = self.sociallogin.user.first_name
        self.initial['last_name'] = self.sociallogin.user.last_name
        # Keep the signup address tied to the identity returned by Google.
        for name in ('email', 'email2'):
            if name in self.fields:
                self.fields[name].disabled = True
                self.initial[name] = self.sociallogin.user.email

    def save(self, request):
        self.sociallogin.user.first_name = self.cleaned_data['first_name']
        self.sociallogin.user.last_name = self.cleaned_data['last_name']
        self.sociallogin.user.username = ''
        return super().save(request)


class UserForm(forms.ModelForm):

    class Meta:
        model = User
        fields = ('first_name', 'last_name')
