from django import forms
from django.contrib.auth.models import User
from allauth.account.forms import SignupForm

from django_recaptcha.fields import ReCaptchaField, ReCaptchaV2Checkbox
from decouple import config


class CustomSignupForm(SignupForm):
    first_name = forms.CharField(max_length=30, label='First Name')
    last_name = forms.CharField(max_length=30, label='Last Name')

    if config('DEBUG', cast=bool) is False:
        captcha = ReCaptchaField(
            public_key=config('RECAPTCHA_PUBLIC_KEY'),
            private_key=config('RECAPTCHA_PRIVATE_KEY'),

            widget=ReCaptchaV2Checkbox()
        )

    else:
        pass

    def signup(self, request, user):
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.save()
        return user


class UserForm(forms.ModelForm):

    class Meta:
        model = User
        fields = ('first_name', 'last_name')
