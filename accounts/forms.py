from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from accounts.models import Profile

class ProfileForm(forms.ModelForm):

    class Meta:
        model = Profile
        fields = ('company', 'date', 'first_class', 'second_class', 'third_class', 'over_40')

class UserForm(forms.ModelForm):

    class Meta:
        model = User
        fields = ('first_name', 'last_name')
